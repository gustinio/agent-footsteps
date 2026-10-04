"""The pre-registered tests, with every threshold in one place."""

import collections
import csv
import json
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    cohen_kappa_score,
    normalized_mutual_info_score,
    roc_auc_score,
)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from footsteps import features, ingest, label, runner, segment, tasks

Q1_PATH = Path("results/q1.json")
Q3A_PATH = Path("results/q3a.json")
Q3B_PATH = Path("results/q3b.json")
Q4_PATH = Path("results/q4.json")
Q2_PATH = Path("results/q2.json")

# From the PRD's Q2 manipulation check: the repeat share must be higher with the
# instruction than without it on this many of the ten tasks, and the interim rule
# stops the runs if it rose on fewer than the interim minimum of the first three.
INTERIM_TASKS = 3
INTERIM_MIN_RISES = 2
FINAL_MIN_RISES = 8
# The repeating behaviour is the state where more than this share of natural steps carry the repeat
# flag, and its share of steps must be higher with the instruction on at least this many tasks.
REPEAT_STATE_SHARE = 0.5
STATE_MIN_RISES = 7
Q2_CRITERION = (
    "The share of shell steps that repeat an earlier command is higher with the instruction than "
    "without it on at least 8 of 10 tasks, and the share of steps in the discovered repeating "
    "state is higher on at least 7 of 10 tasks."
)

# From the PRD's labeler bar: the LLM labels stand in for the full label set only at this agreement
# with the human sample, and otherwise Q1 is reported on the human sample alone.
KAPPA_BAR = 0.6
Q1_CRITERION = (
    "On tasks unseen in training, the HMM's states agree with the step labels better than the "
    "GMM's and better than a majority-label baseline, with the difference larger than the "
    "bootstrap range (normalized mutual information)."
)
BOOTSTRAP_RESAMPLES = 1000
BOOTSTRAP_RANGE = (2.5, 97.5)

# From the PRD's Q3a: the behaviour profile must beat run length by more than the bootstrap range,
# and come within this much AUROC of the supervised predictor.
Q3A_SUPERVISED_MARGIN = 0.05
Q3A_CRITERION = (
    "From the behaviour profile of a finished run (the share of steps in each state in each third, "
    "and the number of switches), a classifier separates failing from passing runs better than run "
    "length alone, with the difference larger than the bootstrap range, and within 0.05 AUROC of the "
    "supervised predictor. Folds are grouped by task."
)
# From the PRD's Q3b: the same two bars as Q3a, judged at every prefix length k, on the runs with at
# least k steps. The lengths themselves are the segmenter's, which decodes the prefix states.
Q3B_SUPERVISED_MARGIN = 0.05
PREFIX_LENGTHS = segment.PREFIX_LENGTHS
Q3B_CRITERION = (
    "From only the first k steps of a run, for k in 5, 10 and 15 and on runs with at least k steps, "
    "the behaviour view separates failing from passing runs better than the counts-so-far baseline "
    "(errors and different tools used), with the difference larger than the bootstrap range, and "
    "within 0.05 AUROC of the supervised predictor, at every k. Folds are grouped by task."
)

# From the PRD's Q4: AUROC and agreement on tasks unseen in training may be at most this much below
# the same measures on seen tasks.
Q4_MAX_DROP = 0.05
Q4_CRITERION = (
    "AUROC of the behaviour view and agreement of the states with the step labels drop by no more "
    "than 0.05 on unseen tasks relative to seen tasks. Seen means a run-level split in which a task "
    "can be in both training and testing, and unseen means folds grouped by task."
)

# How many profile entries and state-to-state moves the report names. Not a pre-registered test.
SIGNAL_SHOWN = 6

# Naming is not a pre-registered test. A state gets a name only when this share of its labeled
# steps agrees, and only when at least this many of its steps were labeled.
NAME_SHARE = 0.5
MIN_LABELED = 5
FACT_NAMES = (
    ("repeat", "repeating"),
    ("after_error", "reacting to an error"),
    ("no_tool", "thinking without a tool"),
)
INTENT_NAMES = {
    "explore": "exploring",
    "modify": "modifying",
    "verify": "verifying",
    "other": "other",
}


def repeat_counts(runs: list[dict], steps: list[dict]) -> dict:
    """Per task and condition, the shell steps and how many of them repeat an earlier command."""
    steps_by_run = collections.defaultdict(list)
    for step in sorted(steps, key=lambda s: (s["run_id"], s["step_idx"])):
        steps_by_run[step["run_id"]].append(step)
    counts: dict = collections.defaultdict(lambda: [0, 0])
    for row in runs:
        run_steps = steps_by_run[row["run_id"]]
        cell = counts[(row["task_id"], row["condition"])]
        cell[0] += sum(
            flag and step["tool_category"] == "shell"
            for flag, step in zip(features.repeat_flags(run_steps), run_steps)
        )
        cell[1] += sum(step["tool_category"] == "shell" for step in run_steps)
    return counts


def manipulation_table(
    runs: list[dict], steps: list[dict], task_order: list[str]
) -> list[dict]:
    """One row per task that has both conditions, in run order."""
    counts = repeat_counts(runs, steps)
    table = []
    for task_id in task_order:
        if (task_id, "none") not in counts or (task_id, "strong") not in counts:
            continue
        shares = {
            condition: counts[(task_id, condition)][0]
            / max(counts[(task_id, condition)][1], 1)
            for condition in runner.CONDITIONS
        }
        table.append(
            {"task_id": task_id, **shares, "rose": shares["strong"] > shares["none"]}
        )
    return table


def interim_verdict(table: list[dict], task_order: list[str]) -> str:
    """continue, stop or pending, after the first tasks in run order."""
    first = set(task_order[:INTERIM_TASKS])
    judged = [row for row in table if row["task_id"] in first]
    if len(judged) < min(INTERIM_TASKS, len(task_order)):
        return "pending"
    rises = sum(row["rose"] for row in judged)
    return "continue" if rises >= INTERIM_MIN_RISES else "stop"


def labeler_agreement(human: dict, llm_labels: dict) -> dict:
    """Cohen's kappa of the LLM against the human sample, and which labels Q1 may use as a result."""
    shared = sorted(set(human) & set(llm_labels))
    kappa = (
        float(
            cohen_kappa_score(
                [human[k] for k in shared], [llm_labels[k] for k in shared]
            )
        )
        if shared
        else None
    )
    trusted = kappa is not None and kappa >= KAPPA_BAR
    return {
        "kappa": None if kappa is None else round(kappa, 4),
        "compared_steps": len(shared),
        "bar": KAPPA_BAR,
        "passes": trusted,
        "labels_used": "llm with human overrides" if trusted else "human sample only",
    }


def label_set(human: dict, llm_labels: dict, trusted: bool) -> dict:
    """The labels Q1 reads: the human ones always, plus the LLM ones where the labeler is trusted."""
    return {**(llm_labels if trusted else {}), **human}


def _agreements(rows: list[dict]) -> dict[str, float]:
    labels = [row["label"] for row in rows]
    return {
        "hmm": normalized_mutual_info_score(labels, [r["hmm_state"] for r in rows]),
        "gmm": normalized_mutual_info_score(labels, [r["gmm_state"] for r in rows]),
        # One label for every step carries no information, so its agreement is zero by definition.
        "majority": 0.0,
    }


def _interval(values: list[float]) -> dict:
    low, high = np.percentile(values, BOOTSTRAP_RANGE)
    return {"low": round(float(low), 4), "high": round(float(high), 4)}


def q1_table(rows: list[dict]) -> dict:
    """NMI between states and labels on the held-out tasks, with a bootstrap over runs for the differences.

    Steps of one run move together because they share a task and an agent, so runs are resampled and not steps.
    """
    held_out = [row for row in rows if row["held_out"]]
    estimate = _agreements(held_out)
    by_run = collections.defaultdict(list)
    for row in held_out:
        by_run[row["run_id"]].append(row)
    run_ids = sorted(by_run)
    rng = np.random.default_rng(segment.SEED)
    gaps = {"hmm_minus_gmm": [], "hmm_minus_majority": []}
    for _ in range(BOOTSTRAP_RESAMPLES):
        picked = rng.integers(len(run_ids), size=len(run_ids))
        sample = [row for idx in picked for row in by_run[run_ids[idx]]]
        resampled = _agreements(sample)
        gaps["hmm_minus_gmm"].append(resampled["hmm"] - resampled["gmm"])
        gaps["hmm_minus_majority"].append(resampled["hmm"] - resampled["majority"])
    differences = {
        name: {
            "estimate": round(estimate["hmm"] - estimate[other], 4),
            **_interval(values),
        }
        for (name, values), other in zip(gaps.items(), ("gmm", "majority"))
    }
    return {
        "criterion": Q1_CRITERION,
        "held_out_steps": len(held_out),
        "held_out_runs": len(run_ids),
        "nmi": {name: round(value, 4) for name, value in estimate.items()},
        "differences": differences,
        "passes": all(d["low"] > 0 for d in differences.values()),
    }


def name_states(rows: list[dict], n_states: int) -> list[dict]:
    """A name for each HMM state from the labels and rule facts of its labeled steps, with the evidence."""
    named = []
    for state in range(n_states):
        mine = [row for row in rows if row["hmm_state"] == state]
        count = len(mine)
        intents = collections.Counter(row["label"] for row in mine)
        facts = collections.Counter(row["fact"] for row in mine)
        name = "too few labels"
        if count >= MIN_LABELED:
            name = "mixed"
            for fact, fact_name in FACT_NAMES:
                if facts[fact] / count >= NAME_SHARE:
                    name = fact_name
                    break
            else:
                intent, top = intents.most_common(1)[0]
                if top / count >= NAME_SHARE:
                    name = INTENT_NAMES[intent]
        named.append(
            {
                "state": state,
                "name": name,
                "labeled_steps": count,
                "intents": {
                    intent: round(intents[intent] / count, 4) if count else 0.0
                    for intent in INTENT_NAMES
                },
                "facts": {
                    fact: round(facts[fact] / count, 4) if count else 0.0
                    for fact, _ in FACT_NAMES
                },
            }
        )
    return named


def labeled_steps(
    rows: list[dict], human: dict, llm_labels: dict
) -> tuple[dict, list[dict]]:
    """The labeler agreement, and the steps that have a label the labeler's agreement allows."""
    agreement = labeler_agreement(human, llm_labels)
    labels = label_set(human, llm_labels, agreement["passes"])
    return agreement, [
        {**row, "label": labels[(row["run_id"], row["step_idx"])]}
        for row in rows
        if (row["run_id"], row["step_idx"]) in labels
    ]


def q1_result(rows: list[dict], human: dict, llm_labels: dict, n_states: int) -> dict:
    """rows hold every natural step with its states, rule fact and held-out flag; labels come in separately."""
    agreement, labeled = labeled_steps(rows, human, llm_labels)
    return {
        "labeler": agreement,
        "q1": q1_table(labeled),
        "states": name_states(labeled, n_states),
    }


def read_human(path: Path = label.HUMAN_LABELS_PATH) -> dict:
    with path.open(newline="") as handle:
        return {
            (row["run_id"], int(row["step_idx"])): row["label"]
            for row in csv.DictReader(handle)
        }


def read_llm(path: Path = label.LLM_LABELS_PATH) -> dict:
    if not path.exists():
        return {}
    return {
        (row["run_id"], row["step_idx"]): row["label"]
        for row in pq.read_table(path).to_pylist()
    }


def q1_inputs() -> list[dict]:
    """Every natural step with both methods' states, its rule fact and its held-out flag."""
    steps, task_of_run = label.load_natural()
    states = {method: {} for method in segment.METHODS}
    for row in pq.read_table(segment.SEGMENTATION_PATH).to_pylist():
        if row["run_id"] in task_of_run:
            states[row["method"]][(row["run_id"], row["step_idx"])] = row["state_id"]
    rows = label.candidates(steps, states["hmm"], task_of_run)
    for row in rows:
        row["hmm_state"] = row.pop("state")
        row["gmm_state"] = states["gmm"][(row["run_id"], row["step_idx"])]
    return rows


def run_q1() -> None:
    if not label.HUMAN_LABELS_PATH.exists():
        print("q1: no human labels yet, so no agreement or names (see footsteps label)")
        return
    n_states = json.loads(segment.SEGMENT_SUMMARY_PATH.read_text())["n_states"]
    result = q1_result(q1_inputs(), read_human(), read_llm(), n_states)
    Q1_PATH.write_text(json.dumps(result, indent=2) + "\n")
    kappa, q1 = result["labeler"], result["q1"]
    print(
        f"labeler kappa {kappa['kappa']} on {kappa['compared_steps']} steps, bar {KAPPA_BAR}, "
        f"labels used: {kappa['labels_used']}"
    )
    print(
        f"q1 on {q1['held_out_steps']} held-out steps: NMI {q1['nmi']}, "
        f"{'passes' if q1['passes'] else 'fails'}"
    )
    for state in result["states"]:
        print(
            f"state {state['state'] + 1}: {state['name']} ({state['labeled_steps']} labeled)"
        )


def _ordered_by_run(steps: list[dict]) -> dict[str, list[dict]]:
    by_run = collections.defaultdict(list)
    for step in sorted(steps, key=lambda s: (s["run_id"], s["step_idx"])):
        by_run[step["run_id"]].append(step)
    return by_run


def q3a_runs(
    steps: list[dict],
    outcomes: dict[str, str],
    task_of_run: dict[str, str],
    states: dict[str, list[int]],
    n_states: int,
) -> list[dict]:
    """One row per natural run with the three views of it: length, behaviour profile and fact counts."""
    by_run = _ordered_by_run(steps)
    rows = []
    for run_id in sorted(by_run):
        profile, moves = features.run_profile(states[run_id], n_states)
        rows.append(
            {
                "run_id": run_id,
                "task_id": task_of_run[run_id],
                "failed": outcomes[run_id] == "fail",
                "length": [float(len(by_run[run_id]))],
                "profile": profile,
                "moves": moves,
                "counts": features.window_counts(by_run[run_id]),
            }
        )
    return rows


def _logistic():
    return make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000))


# Each view is paired with the model that reads it. Only the supervised predictor is a tree model.
Q3A_MODELS = {
    "length": ("length", _logistic),
    "behaviour": ("profile", _logistic),
    "supervised": (
        "counts",
        lambda: GradientBoostingClassifier(random_state=segment.SEED),
    ),
}


def _out_of_fold(
    rows: list[dict], view: str, make_model, by: str = "task_id"
) -> np.ndarray:
    """Each run is scored by a model fit on the other folds.

    Folds are grouped by task, so no task is in both training and testing, unless by is "run_id",
    which is the seen-task split where the runs of one task can sit on both sides.
    """
    X = np.array([row[view] for row in rows])
    y = np.array([row["failed"] for row in rows])
    assign = segment.task_folds if by == "task_id" else segment.run_folds
    folds = assign(row[by] for row in rows)
    fold_of = np.array([folds[row[by]] for row in rows])
    scores = np.zeros(len(rows))
    for fold in sorted(set(fold_of)):
        test = fold_of == fold
        model = make_model().fit(X[~test], y[~test])
        scores[test] = model.predict_proba(X[test])[:, 1]
    return scores


def _task_resamples(rows: list[dict], rng) -> list[np.ndarray]:
    """Row indices of each bootstrap sample, drawn by task because the runs of a task are not independent."""
    by_task = collections.defaultdict(list)
    for idx, row in enumerate(rows):
        by_task[row["task_id"]].append(idx)
    task_ids = sorted(by_task)
    return [
        np.concatenate(
            [
                by_task[task_ids[t]]
                for t in rng.integers(len(task_ids), size=len(task_ids))
            ]
        )
        for _ in range(BOOTSTRAP_RESAMPLES)
    ]


def _with_range(estimate: float, values: list[float]) -> dict:
    return {"estimate": round(float(estimate), 4), **_interval(values)}


def _signal(rows: list[dict], samples: list[np.ndarray], n_states: int) -> dict:
    """The profile entries and state-to-state moves most tied to failure, each with a bootstrap range.

    An entry's coefficient is from the profile model refit on every resample, and a move's effect is
    its AUROC alone, because the profile holds switch counts and not which switch was made.
    """
    y = np.array([row["failed"] for row in rows])
    profile = np.array([row["profile"] for row in rows])
    moves = np.array([row["moves"] for row in rows])

    def coefficients(index):
        return _logistic().fit(profile[index], y[index])[-1].coef_[0]

    def move_aurocs(index):
        # One AUROC per column, so the failing flag is repeated once for each.
        labels = np.repeat(y[index][:, None], moves.shape[1], axis=1)
        return roc_auc_score(labels, moves[index], average=None)

    everything = np.arange(len(rows))
    coef_samples = np.array([coefficients(i) for i in samples])
    auc_samples = np.array([move_aurocs(i) for i in samples])
    coef, aucs = coefficients(everything), move_aurocs(everything)

    def pick(names, estimates, resampled, centre, key):
        entries = []
        for idx in np.argsort(-np.abs(estimates - centre), kind="stable")[
            :SIGNAL_SHOWN
        ]:
            effect = _with_range(estimates[idx], resampled[:, idx])
            entries.append(
                {
                    "name": names[idx],
                    key: effect["estimate"],
                    "low": effect["low"],
                    "high": effect["high"],
                    "clear": effect["low"] > centre or effect["high"] < centre,
                    "more_in": "failing" if estimates[idx] > centre else "passing",
                }
            )
        return entries

    return {
        "profile": pick(
            features.profile_names(n_states), coef, coef_samples, 0.0, "coefficient"
        ),
        "moves": pick(features.move_names(n_states), aucs, auc_samples, 0.5, "auroc"),
        "moves_tested": int(moves.shape[1]),
    }


def _aurocs(
    rows: list[dict], models: dict, samples: list[np.ndarray]
) -> tuple[dict, dict]:
    """Out-of-fold AUROC of each model for failing runs, and its value on every task resample."""
    y = np.array([row["failed"] for row in rows])
    scores = {
        name: _out_of_fold(rows, view, make_model)
        for name, (view, make_model) in models.items()
    }
    estimate = {name: roc_auc_score(y, score) for name, score in scores.items()}
    resampled = {
        name: [roc_auc_score(y[i], score[i]) for i in samples]
        for name, score in scores.items()
    }
    return estimate, resampled


def _gaps(estimate: dict, resampled: dict, pairs: dict) -> dict:
    return {
        name: _with_range(
            estimate[a] - estimate[b],
            [x - z for x, z in zip(resampled[a], resampled[b])],
        )
        for name, (a, b) in pairs.items()
    }


def q3a_table(rows: list[dict], n_states: int) -> dict:
    """Out-of-fold AUROC of the three views for failing runs, with task-bootstrap ranges and the pre-registered verdict."""
    y = np.array([row["failed"] for row in rows])
    samples = _task_resamples(rows, np.random.default_rng(segment.SEED))
    estimate, resampled = _aurocs(rows, Q3A_MODELS, samples)
    gaps = {
        "behaviour_minus_length": ("behaviour", "length"),
        "supervised_minus_behaviour": ("supervised", "behaviour"),
    }
    differences = _gaps(estimate, resampled, gaps)
    beats_length = differences["behaviour_minus_length"]["low"] > 0
    near_supervised = (
        differences["supervised_minus_behaviour"]["estimate"] <= Q3A_SUPERVISED_MARGIN
    )
    return {
        "criterion": Q3A_CRITERION,
        "runs": len(rows),
        "tasks": len({row["task_id"] for row in rows}),
        "failing_share": round(float(y.mean()), 4),
        "auroc": {
            name: _with_range(estimate[name], resampled[name]) for name in Q3A_MODELS
        },
        "differences": differences,
        "beats_length": bool(beats_length),
        "near_supervised": bool(near_supervised),
        "passes": bool(beats_length and near_supervised),
        "signal": _signal(rows, samples, n_states),
    }


def _natural_outcomes(task_of_run: dict[str, str]) -> dict[str, str]:
    return {
        row["run_id"]: row["outcome"]
        for row in pq.read_table(
            ingest.RUNS_PATH,
            columns=["run_id", "outcome"],
            filters=[("run_id", "in", list(task_of_run))],
        ).to_pylist()
    }


def q3a_inputs() -> tuple[list[dict], int]:
    """The natural runs with their views, and how many states the segmentation chose."""
    steps, task_of_run = label.load_natural()
    outcomes = _natural_outcomes(task_of_run)
    ordered: dict[str, dict[int, int]] = collections.defaultdict(dict)
    for row in pq.read_table(
        segment.SEGMENTATION_PATH, filters=[("method", "=", "hmm")]
    ).to_pylist():
        if row["run_id"] in task_of_run:
            ordered[row["run_id"]][row["step_idx"]] = row["state_id"]
    states = {
        run_id: [by_step[idx] for idx in sorted(by_step)]
        for run_id, by_step in ordered.items()
    }
    n_states = json.loads(segment.SEGMENT_SUMMARY_PATH.read_text())["n_states"]
    return q3a_runs(steps, outcomes, task_of_run, states, n_states), n_states


def run_q3a() -> None:
    rows, n_states = q3a_inputs()
    result = q3a_table(rows, n_states)
    Q3A_PATH.write_text(json.dumps(result, indent=2) + "\n")
    auroc = result["auroc"]
    print(
        f"q3a on {result['runs']} runs from {result['tasks']} tasks: AUROC "
        + ", ".join(
            f"{name} {value['estimate']:.2f} ({value['low']:.2f} to {value['high']:.2f})"
            for name, value in auroc.items()
        )
        + f", {'passes' if result['passes'] else 'fails'}"
    )


# Each view of the first k steps is paired with the model that reads it. The length reference reads
# the whole run's length, which an early check would not have, so it only bounds what is possible.
Q3B_MODELS = {
    "length": ("length", _logistic),
    "baseline": ("baseline", _logistic),
    "behaviour": ("profile", _logistic),
    "supervised": (
        "counts",
        lambda: GradientBoostingClassifier(random_state=segment.SEED),
    ),
}


def q3b_runs(
    steps: list[dict],
    outcomes: dict[str, str],
    task_of_run: dict[str, str],
    prefix_states: dict[int, dict[str, list[int]]],
    n_states: int,
) -> dict[int, list[dict]]:
    """For each k, one row per natural run with at least k steps, holding the views of its first k steps."""
    by_run = _ordered_by_run(steps)
    rows = {}
    for k, states in prefix_states.items():
        rows[k] = [
            {
                "run_id": run_id,
                "task_id": task_of_run[run_id],
                "failed": outcomes[run_id] == "fail",
                "length": [float(len(by_run[run_id]))],
                "baseline": features.prefix_counts(by_run[run_id][:k]),
                "profile": features.run_profile(states[run_id], n_states)[0],
                "counts": features.window_counts(by_run[run_id][:k]),
            }
            for run_id in sorted(by_run)
            if run_id in states
        ]
    return rows


def q3b_table(rows_by_k: dict[int, list[dict]], total_runs: int) -> dict:
    """Out-of-fold AUROC of the views of the first k steps, with task-bootstrap ranges and the runs dropped at each k."""
    per_k = []
    for k, rows in sorted(rows_by_k.items()):
        y = np.array([row["failed"] for row in rows])
        samples = _task_resamples(rows, np.random.default_rng(segment.SEED))
        estimate, resampled = _aurocs(rows, Q3B_MODELS, samples)
        differences = _gaps(
            estimate,
            resampled,
            {
                "behaviour_minus_baseline": ("behaviour", "baseline"),
                "supervised_minus_behaviour": ("supervised", "behaviour"),
            },
        )
        beats_baseline = differences["behaviour_minus_baseline"]["low"] > 0
        near_supervised = (
            differences["supervised_minus_behaviour"]["estimate"]
            <= Q3B_SUPERVISED_MARGIN
        )
        per_k.append(
            {
                "k": k,
                "runs": len(rows),
                "runs_dropped": total_runs - len(rows),
                "tasks": len({row["task_id"] for row in rows}),
                "failing_share": round(float(y.mean()), 4),
                "auroc": {
                    name: _with_range(estimate[name], resampled[name])
                    for name in Q3B_MODELS
                },
                "differences": differences,
                "beats_baseline": bool(beats_baseline),
                "near_supervised": bool(near_supervised),
                "passes": bool(beats_baseline and near_supervised),
            }
        )
    return {
        "criterion": Q3B_CRITERION,
        "natural_runs": total_runs,
        "per_k": per_k,
        "passes": all(entry["passes"] for entry in per_k),
    }


def _drop_in_auroc(rows: list[dict]) -> dict:
    """AUROC of the behaviour view with run-level folds (seen tasks) minus task-grouped folds (unseen)."""
    view, make_model = Q3B_MODELS["behaviour"]
    y = np.array([row["failed"] for row in rows])
    seen = _out_of_fold(rows, view, make_model, by="run_id")
    unseen = _out_of_fold(rows, view, make_model)
    samples = _task_resamples(rows, np.random.default_rng(segment.SEED))
    seen_auroc, unseen_auroc = roc_auc_score(y, seen), roc_auc_score(y, unseen)
    drop = _with_range(
        seen_auroc - unseen_auroc,
        [
            roc_auc_score(y[i], seen[i]) - roc_auc_score(y[i], unseen[i])
            for i in samples
        ],
    )
    return {
        "runs": len(rows),
        "seen": round(float(seen_auroc), 4),
        "unseen": round(float(unseen_auroc), 4),
        "drop": drop,
        "passes": bool(drop["estimate"] <= Q4_MAX_DROP),
    }


def _nmi_by_run(rows: list[dict]) -> float:
    return normalized_mutual_info_score(
        [r["label"] for r in rows], [r["hmm_state"] for r in rows]
    )


def agreement_drop(labeled: list[dict]) -> dict:
    """NMI of the HMM states with the labels on steps of training tasks minus steps of held-out tasks.

    Each side is resampled by run, as in Q1, because the steps of one run move together.
    """
    sides = {}
    for name, held in (("seen", False), ("unseen", True)):
        by_run = collections.defaultdict(list)
        for row in labeled:
            if row["held_out"] == held:
                by_run[row["run_id"]].append(row)
        sides[name] = by_run
    rng = np.random.default_rng(segment.SEED)

    def nmi(by_run, picked=None):
        ids = sorted(by_run)
        chosen = ids if picked is None else [ids[i] for i in picked]
        return _nmi_by_run([row for run_id in chosen for row in by_run[run_id]])

    estimate = {name: nmi(by_run) for name, by_run in sides.items()}
    gaps = []
    for _ in range(BOOTSTRAP_RESAMPLES):
        draws = {
            name: nmi(by_run, rng.integers(len(by_run), size=len(by_run)))
            for name, by_run in sides.items()
        }
        gaps.append(draws["seen"] - draws["unseen"])
    drop = _with_range(estimate["seen"] - estimate["unseen"], gaps)
    return {
        "seen_steps": sum(len(v) for v in sides["seen"].values()),
        "unseen_steps": sum(len(v) for v in sides["unseen"].values()),
        "seen": round(float(estimate["seen"]), 4),
        "unseen": round(float(estimate["unseen"]), 4),
        "drop": drop,
        "passes": bool(drop["estimate"] <= Q4_MAX_DROP),
    }


def q4_table(
    whole_rows: list[dict],
    rows_by_k: dict[int, list[dict]],
    labeled: list[dict] | None,
) -> dict:
    """Seen against unseen tasks for the behaviour view on whole runs and on each prefix, and for label agreement.

    Without labels the agreement part is not judged, and so neither is the whole question.
    """
    stages = [{"stage": "whole run", **_drop_in_auroc(whole_rows)}] + [
        {"stage": f"first {k} steps", "k": k, **_drop_in_auroc(rows)}
        for k, rows in sorted(rows_by_k.items())
    ]
    agreement = agreement_drop(labeled) if labeled else None
    auroc_passes = all(stage["passes"] for stage in stages)
    return {
        "criterion": Q4_CRITERION,
        "auroc": stages,
        "auroc_passes": auroc_passes,
        "agreement": agreement,
        "passes": None
        if agreement is None
        else bool(auroc_passes and agreement["passes"]),
    }


def q3b_inputs() -> tuple[dict[int, list[dict]], int]:
    """The prefix views for each k, and how many natural runs there are before any are dropped."""
    steps, task_of_run = label.load_natural()
    outcomes = _natural_outcomes(task_of_run)
    prefix_states: dict[int, dict[str, dict[int, int]]] = collections.defaultdict(
        lambda: collections.defaultdict(dict)
    )
    for row in pq.read_table(segment.PREFIX_STATES_PATH).to_pylist():
        prefix_states[row["k"]][row["run_id"]][row["step_idx"]] = row["state_id"]
    ordered = {
        k: {r: [by_step[i] for i in sorted(by_step)] for r, by_step in by_run.items()}
        for k, by_run in prefix_states.items()
    }
    n_states = json.loads(segment.SEGMENT_SUMMARY_PATH.read_text())["n_states"]
    return q3b_runs(steps, outcomes, task_of_run, ordered, n_states), len(task_of_run)


def run_q3b_q4() -> None:
    rows_by_k, total = q3b_inputs()
    q3b = q3b_table(rows_by_k, total)
    Q3B_PATH.write_text(json.dumps(q3b, indent=2) + "\n")
    for entry in q3b["per_k"]:
        auroc = entry["auroc"]
        print(
            f"q3b first {entry['k']} steps, {entry['runs']} runs ({entry['runs_dropped']} dropped): AUROC "
            + ", ".join(
                f"{name} {value['estimate']:.2f}" for name, value in auroc.items()
            )
            + f", {'passes' if entry['passes'] else 'fails'}"
        )
    labeled = None
    if label.HUMAN_LABELS_PATH.exists():
        _, labeled = labeled_steps(q1_inputs(), read_human(), read_llm())
    whole_rows, _ = q3a_inputs()
    q4 = q4_table(whole_rows, rows_by_k, labeled)
    Q4_PATH.write_text(json.dumps(q4, indent=2) + "\n")
    for stage in q4["auroc"]:
        print(
            f"q4 {stage['stage']}: AUROC seen {stage['seen']:.2f}, unseen {stage['unseen']:.2f}, "
            f"drop {stage['drop']['estimate']:.2f}, {'passes' if stage['passes'] else 'fails'}"
        )
    agreement = q4["agreement"]
    print(
        "q4 agreement: no human labels yet"
        if agreement is None
        else f"q4 agreement: NMI seen {agreement['seen']:.2f}, unseen {agreement['unseen']:.2f}, "
        f"drop {agreement['drop']['estimate']:.2f}, {'passes' if agreement['passes'] else 'fails'}"
    )


def repeating_state(
    natural_steps: list[dict], states: dict[tuple[str, int], int], n_states: int
) -> dict | None:
    """The natural-fit state in which most steps carry the repeat flag, or None when no state does."""
    counts = np.zeros((n_states, 2))
    for run_id, run_steps in _ordered_by_run(natural_steps).items():
        for idx, flag in enumerate(features.repeat_flags(run_steps)):
            state = states[(run_id, idx)]
            counts[state] += (flag, 1)
    shares = counts[:, 0] / np.maximum(counts[:, 1], 1)
    state = int(np.argmax(shares))
    if shares[state] <= REPEAT_STATE_SHARE:
        return None
    return {"state": state, "repeat_share": round(float(shares[state]), 4)}


def state_share_table(
    runs: list[dict],
    states: dict[tuple[str, int], int],
    state: int,
    task_order: list[str],
) -> list[dict]:
    """Per task and condition, the share of planted steps in the state, for tasks that have both conditions."""
    cells: dict = collections.defaultdict(lambda: [0, 0])
    for row in runs:
        for idx in range(row["n_steps"]):
            cell = cells[(row["task_id"], row["condition"])]
            cell[0] += states[(row["run_id"], idx)] == state
            cell[1] += 1
    return [
        {
            "task_id": task_id,
            **{
                c: cells[(task_id, c)][0] / max(cells[(task_id, c)][1], 1)
                for c in runner.CONDITIONS
            },
            "rose": cells[(task_id, "strong")][0]
            / max(cells[(task_id, "strong")][1], 1)
            > cells[(task_id, "none")][0] / max(cells[(task_id, "none")][1], 1),
        }
        for task_id in task_order
        if (task_id, "none") in cells and (task_id, "strong") in cells
    ]


def q2_result(
    runs: list[dict],
    steps: list[dict],
    natural_steps: list[dict],
    states: dict[tuple[str, int], int],
    n_states: int,
    task_order: list[str],
) -> dict:
    """The manipulation check and the repeating-state check. Neither is judged until every task has run."""
    judged = len(task_order)
    manipulation = manipulation_table(runs, steps, task_order)
    rises = sum(row["rose"] for row in manipulation)
    found = repeating_state(natural_steps, states, n_states)
    state = None
    if found:
        table = state_share_table(runs, states, found["state"], task_order)
        state_rises = sum(row["rose"] for row in table)
        state = {
            **found,
            "table": table,
            "rises": state_rises,
            "needs": STATE_MIN_RISES,
            "passes": len(table) == judged and state_rises >= STATE_MIN_RISES,
        }
    complete = len(manipulation) == judged
    manipulation_passes = complete and rises >= FINAL_MIN_RISES
    return {
        "criterion": Q2_CRITERION,
        "tasks": judged,
        "tasks_run": len(manipulation),
        "interim": interim_verdict(manipulation, task_order),
        "manipulation": {
            "table": manipulation,
            "rises": rises,
            "needs": FINAL_MIN_RISES,
            "passes": manipulation_passes if complete else None,
        },
        # None means no discovered state is mostly repeats, which the PRD reports as not detected.
        "state": state,
        "passes": None
        if not complete
        else bool(manipulation_passes and state and state["passes"]),
    }


def q2_inputs() -> tuple[list[dict], list[dict], list[dict], dict, int, list[str]]:
    natural_steps, _ = label.load_natural()
    states = {
        (row["run_id"], row["step_idx"]): row["state_id"]
        for row in pq.read_table(
            segment.SEGMENTATION_PATH, filters=[("method", "=", "hmm")]
        ).to_pylist()
    }
    n_states = json.loads(segment.SEGMENT_SUMMARY_PATH.read_text())["n_states"]
    return (
        runner.read_table(runner.PLANTED_RUNS_PATH),
        runner.read_table(runner.PLANTED_STEPS_PATH),
        natural_steps,
        states,
        n_states,
        [task.task_id for task in tasks.load_tasks()],
    )


def run_q2() -> None:
    runs, steps, natural_steps, states, n_states, task_order = q2_inputs()
    result = q2_result(runs, steps, natural_steps, states, n_states, task_order)
    Q2_PATH.write_text(json.dumps(result, indent=2) + "\n")
    print("q2 task  share of shell steps that repeat an earlier command")
    for row in result["manipulation"]["table"]:
        print(
            f"{row['task_id']:<20} none {row['none']:.0%}  strong {row['strong']:.0%}"
            f"  {'rose' if row['rose'] else 'did not rise'}"
        )
    print(f"interim rule after {INTERIM_TASKS} tasks: {result['interim']}")
    check = result["manipulation"]
    verdict = {None: "not judged", True: "passes", False: "fails"}[check["passes"]]
    print(
        f"manipulation check: rose on {check['rises']} of {result['tasks_run']} tasks, "
        f"needs {FINAL_MIN_RISES} ({verdict})"
    )
    state = result["state"]
    if state is None:
        print("repeating state: none, so Q2 is reported as not detected")
        return
    print(
        f"repeating state {state['state'] + 1} ({state['repeat_share']:.0%} of its natural steps repeat): "
        f"share of steps rose on {state['rises']} of {len(state['table'])} tasks, "
        f"needs {STATE_MIN_RISES} ({'passes' if state['passes'] else 'fails or not yet judged'})"
    )


def run() -> None:
    run_q1()
    run_q3a()
    run_q3b_q4()
    run_q2()
