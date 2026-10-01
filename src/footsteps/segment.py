"""Group steps into behaviours with a sticky HMM and a GMM, both fit on the original features."""

import collections
import hashlib
import json
import logging
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from hmmlearn.hmm import GaussianHMM
from sklearn.mixture import GaussianMixture

from footsteps import features
from footsteps.ingest import RUNS_PATH, STEPS_PATH, SUMMARY_PATH
from footsteps.runner import PLANTED_STEPS_PATH

SEGMENTATION_PATH = Path("results/segmentation.parquet")
SEGMENT_SUMMARY_PATH = Path("results/segmentation_summary.json")

# The fit adds a prior that the reported score leaves out, so the score can dip by a rounding error
# between rounds and hmmlearn then warns that it is not converging. The result is still valid.
logging.getLogger("hmmlearn").setLevel(logging.ERROR)

METHODS = ("hmm", "gmm")

# One seed for every fold assignment and fit, so Q1, Q3 and Q4 share the same folds.
SEED = 0
N_FOLDS = 5

# From the PRD's size rule: the HMM state count is chosen from 2 to 8 by held-out likelihood.
STATE_COUNTS = range(2, 9)

# Extra Dirichlet weight on each state staying where it is, on top of the flat prior.
# It is a modelling choice and not a pre-registered threshold, and the learned self-transition
# rates are written to the summary so its effect can be read.
STICKINESS = 20.0

RESTARTS = 2
EM_ITERATIONS = 50
# Both models need a floor on each feature's variance, because most features are 0 or 1 flags
# and a state that never sees a flag would otherwise score a step that has it as nearly impossible.
VARIANCE_FLOOR = 0.05


def natural_arm(runs: list[dict], selected: list[dict]) -> list[dict]:
    """Runs of the selected model and scaffold combinations, on tasks where that combination has both outcomes."""
    combos = {(c["agent"], c["model"]) for c in selected}
    outcomes = collections.defaultdict(set)
    for run in runs:
        if (run["agent"], run["model"]) in combos:
            outcomes[(run["agent"], run["model"], run["task_id"])].add(run["outcome"])
    return [
        run
        for run in runs
        if (run["agent"], run["model"]) in combos
        and len(outcomes[(run["agent"], run["model"], run["task_id"])]) == 2
    ]


def _balanced_folds(keys, salt: str, n_folds: int = N_FOLDS) -> dict[str, int]:
    """Deal keys into folds by the hash of the key, so the result ignores input order and stays near equal in size."""
    ordered = sorted(
        set(keys),
        key=lambda key: hashlib.sha256(f"{salt}:{SEED}:{key}".encode()).hexdigest(),
    )
    return {key: idx % n_folds for idx, key in enumerate(ordered)}


def task_folds(task_ids) -> dict[str, int]:
    """The fold of each task. No task is in two folds, which is what makes a test fold unseen."""
    return _balanced_folds(task_ids, "task")


def run_folds(run_ids) -> dict[str, int]:
    """The fold of each run regardless of task, for the seen-task condition where a task can sit in both sides."""
    return _balanced_folds(run_ids, "run")


def _steps_by_run(steps: list[dict]) -> dict[str, list[dict]]:
    grouped = collections.defaultdict(list)
    for step in steps:
        grouped[step["run_id"]].append(step)
    return {
        run_id: sorted(rows, key=lambda row: row["step_idx"])
        for run_id, rows in grouped.items()
    }


def feature_sequences(steps: list[dict]) -> dict[str, np.ndarray]:
    return {
        run_id: np.array(features.step_features(rows))
        for run_id, rows in _steps_by_run(steps).items()
    }


def _stack(
    sequences: dict[str, np.ndarray], run_ids: list[str]
) -> tuple[np.ndarray, list[int]]:
    return (
        np.vstack([sequences[run_id] for run_id in run_ids]),
        [len(sequences[run_id]) for run_id in run_ids],
    )


class FlooredGaussianHMM(GaussianHMM):
    """hmmlearn applies its minimum variance only when it initializes, so a state can collapse onto a flag later."""

    def _do_mstep(self, stats):
        super()._do_mstep(stats)
        self._covars_ = np.maximum(self._covars_, VARIANCE_FLOOR)


def fit_hmm(X: np.ndarray, lengths: list[int], n_states: int) -> GaussianHMM:
    """Sticky through hmmlearn's own Dirichlet prior on each row of the transition matrix, which takes a full matrix."""
    prior = np.ones((n_states, n_states)) + STICKINESS * np.eye(n_states)
    best, best_score = None, -np.inf
    for restart in range(RESTARTS):
        model = FlooredGaussianHMM(
            n_components=n_states,
            covariance_type="diag",
            transmat_prior=prior,
            n_iter=EM_ITERATIONS,
            random_state=SEED + restart,
        ).fit(X, lengths)
        score = model.score(X, lengths)
        if score > best_score:
            best, best_score = model, score
    return best


def fit_gmm(X: np.ndarray, n_states: int) -> GaussianMixture:
    return GaussianMixture(
        n_components=n_states,
        covariance_type="diag",
        reg_covar=VARIANCE_FLOOR,
        n_init=RESTARTS,
        random_state=SEED,
    ).fit(X)


def held_out_scores(
    sequences: dict[str, np.ndarray], task_of_run: dict[str, str]
) -> list[dict]:
    """Mean held-out log-likelihood per step of the HMM for each state count, with task-grouped folds."""
    folds = task_folds(task_of_run.values())
    scores = []
    for n_states in STATE_COUNTS:
        total, count = 0.0, 0
        for fold in range(N_FOLDS):
            train = sorted(r for r in sequences if folds[task_of_run[r]] != fold)
            test = sorted(r for r in sequences if folds[task_of_run[r]] == fold)
            if not train or not test:
                continue
            model = fit_hmm(*_stack(sequences, train), n_states)
            X_test, lengths = _stack(sequences, test)
            total += model.score(X_test, lengths)
            count += len(X_test)
        # Rounded because the last digits of a float sum vary between runs, and a rerun should not change a committed file.
        scores.append({"n_states": n_states, "mean_loglik": round(total / count, 6)})
    return scores


def choose_state_count(scores: list[dict]) -> int:
    return max(scores, key=lambda row: row["mean_loglik"])["n_states"]


def segment(
    natural_steps: list[dict],
    task_of_run: dict[str, str],
    planted_steps: list[dict],
) -> tuple[dict[str, dict[str, list[int]]], dict]:
    """States per run and method, for the natural runs and for the planted runs projected onto the natural model.

    Models are fit on the natural runs only, and states are numbered by how many natural steps they hold.
    """
    sequences = feature_sequences(natural_steps)
    scores = held_out_scores(sequences, task_of_run)
    n_states = choose_state_count(scores)
    run_ids = sorted(sequences)
    X, lengths = _stack(sequences, run_ids)
    hmm, gmm = fit_hmm(X, lengths, n_states), fit_gmm(X, n_states)

    def decode(method: str, sequence: np.ndarray) -> np.ndarray:
        model = hmm if method == "hmm" else gmm
        return model.predict(sequence)

    raw = {
        method: {r: decode(method, sequences[r]) for r in run_ids} for method in METHODS
    }
    planted_sequences = feature_sequences(planted_steps)
    planted_raw = {
        method: {r: decode(method, seq) for r, seq in planted_sequences.items()}
        for method in METHODS
    }
    states: dict[str, dict[str, list[int]]] = {method: {} for method in METHODS}
    shares, orders = {}, {}
    for method in METHODS:
        counts = np.bincount(
            np.concatenate(list(raw[method].values())), minlength=n_states
        )
        orders[method] = np.argsort(-counts, kind="stable")
        rank = np.empty(n_states, dtype=int)
        rank[orders[method]] = np.arange(n_states)
        for source in (raw[method], planted_raw[method]):
            states[method].update({r: rank[s].tolist() for r, s in source.items()})
        shares[method] = (counts[orders[method]] / counts.sum()).round(4).tolist()
    stay = np.diag(hmm.transmat_)[orders["hmm"]]
    summary = {
        "seed": SEED,
        "n_folds": N_FOLDS,
        "stickiness": STICKINESS,
        "n_states": n_states,
        "held_out": scores,
        "natural_runs": len(run_ids),
        "natural_tasks": len(set(task_of_run.values())),
        "planted_runs": len(planted_sequences),
        "state_shares": shares,
        "hmm_self_transition": stay.round(4).tolist(),
        "features": list(features.FEATURE_NAMES),
    }
    return states, summary


def states_table(states: dict[str, dict[str, list[int]]]) -> pa.Table:
    rows = [
        {"run_id": run_id, "step_idx": idx, "method": method, "state_id": state}
        for method, by_run in states.items()
        for run_id, run_states in sorted(by_run.items())
        for idx, state in enumerate(run_states)
    ]
    return pa.Table.from_pylist(rows)


def run() -> None:
    summary_in = json.loads(SUMMARY_PATH.read_text())
    arm = natural_arm(pq.read_table(RUNS_PATH).to_pylist(), summary_in["selected"])
    arm_ids = [run["run_id"] for run in arm]
    natural_steps = pq.read_table(
        STEPS_PATH, filters=[("run_id", "in", arm_ids)]
    ).to_pylist()
    planted_steps = pq.read_table(PLANTED_STEPS_PATH).to_pylist()
    states, summary = segment(
        natural_steps, {run["run_id"]: run["task_id"] for run in arm}, planted_steps
    )
    SEGMENTATION_PATH.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(states_table(states), SEGMENTATION_PATH)
    SEGMENT_SUMMARY_PATH.write_text(json.dumps(summary, indent=2) + "\n")
    print(
        f"{summary['natural_runs']} natural runs on {summary['natural_tasks']} tasks, "
        f"{summary['n_states']} states chosen"
    )
