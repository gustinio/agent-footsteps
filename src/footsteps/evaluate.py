"""The pre-registered tests, with every threshold in one place."""

import collections
import csv
import json
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
from sklearn.metrics import cohen_kappa_score, normalized_mutual_info_score

from footsteps import features, label, runner, segment, tasks

Q1_PATH = Path("results/q1.json")

# From the PRD's Q2 manipulation check: the repeat share must be higher with the
# instruction than without it on this many of the ten tasks, and the interim rule
# stops the runs if it rose on fewer than the interim minimum of the first three.
INTERIM_TASKS = 3
INTERIM_MIN_RISES = 2
FINAL_MIN_RISES = 8

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


def q1_result(rows: list[dict], human: dict, llm_labels: dict, n_states: int) -> dict:
    """rows hold every natural step with its states, rule fact and held-out flag; labels come in separately."""
    agreement = labeler_agreement(human, llm_labels)
    labels = label_set(human, llm_labels, agreement["passes"])
    labeled = [
        {**row, "label": labels[(row["run_id"], row["step_idx"])]}
        for row in rows
        if (row["run_id"], row["step_idx"]) in labels
    ]
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


def run() -> None:
    run_q1()
    task_order = [task.task_id for task in tasks.load_tasks()]
    table = manipulation_table(
        runner.read_table(runner.PLANTED_RUNS_PATH),
        runner.read_table(runner.PLANTED_STEPS_PATH),
        task_order,
    )
    print("task  share of shell steps that repeat an earlier command")
    for row in table:
        print(
            f"{row['task_id']:<20} none {row['none']:.0%}  strong {row['strong']:.0%}"
            f"  {'rose' if row['rose'] else 'did not rise'}"
        )
    verdict = interim_verdict(table, task_order)
    print(f"interim rule after {INTERIM_TASKS} tasks: {verdict}")
    if len(table) == len(task_order):
        rises = sum(row["rose"] for row in table)
        print(
            f"manipulation check: rose on {rises} of {len(table)} tasks, needs {FINAL_MIN_RISES}"
            f" ({'passes' if rises >= FINAL_MIN_RISES else 'fails'})"
        )
