import json

import numpy as np
import pytest

from footsteps import features, segment


def fact(category, status, digest=None):
    return {
        "tool_category": category,
        "result_status": status,
        "command_hash": digest,
        "verification_flag": False,
    }


def synthetic_steps(task_count=10, runs_per_task=3, block=10):
    """Runs of two stretches: reading that succeeds, then shell commands that fail, with the task in the run id."""
    steps, task_of_run = [], {}
    for task in range(task_count):
        for trial in range(runs_per_task):
            run_id = f"t{task}-r{trial}"
            task_of_run[run_id] = f"t{task}"
            kinds = ["read"] * block + ["shell"] * block
            for idx, kind in enumerate(kinds):
                row = fact(kind, "ok" if kind == "read" else "error", f"{task}{idx}")
                steps.append({"run_id": run_id, "step_idx": idx, **row})
    return steps, task_of_run


@pytest.fixture(autouse=True)
def small_search(monkeypatch):
    monkeypatch.setattr(segment, "STATE_COUNTS", range(2, 4))
    monkeypatch.setattr(segment, "EM_ITERATIONS", 20)


def test_natural_arm_keeps_selected_combinations_on_mixed_tasks():
    def run(run_id, task, outcome, agent="a", model="m"):
        return {
            "run_id": run_id,
            "task_id": task,
            "agent": agent,
            "model": model,
            "outcome": outcome,
        }

    runs = [
        run("1", "mixed", "pass"),
        run("2", "mixed", "fail"),
        run("3", "all-fail", "fail"),
        run("4", "all-fail", "fail"),
        run("5", "mixed", "pass", agent="other"),
        run("6", "mixed", "fail", agent="other"),
    ]
    arm = segment.natural_arm(runs, [{"agent": "a", "model": "m"}])
    assert [r["run_id"] for r in arm] == ["1", "2"]


def test_task_folds_never_split_a_task_and_ignore_input_order():
    tasks = [f"task-{n}" for n in range(23)]
    folds = segment.task_folds(tasks)
    assert segment.task_folds(list(reversed(tasks * 2))) == folds
    sizes = np.bincount(list(folds.values()), minlength=segment.N_FOLDS)
    assert sizes.max() - sizes.min() <= 1
    assert set(folds) == set(tasks)


def test_run_folds_differ_from_task_folds_so_a_task_spans_folds():
    runs = [f"t{task}-r{trial}" for task in range(10) for trial in range(5)]
    by_run = segment.run_folds(runs)
    spanning = {
        task
        for task in range(10)
        if len({by_run[f"t{task}-r{trial}"] for trial in range(5)}) > 1
    }
    assert len(spanning) > 5


def test_hmm_recovers_the_two_stretches_and_numbers_states_by_size(monkeypatch):
    # With the true count of two, each stretch is one state, which a larger count would split.
    monkeypatch.setattr(segment, "STATE_COUNTS", range(2, 3))
    steps, task_of_run = synthetic_steps()
    states, summary, _ = segment.segment(steps, task_of_run, [])
    assert summary["n_states"] == 2
    for method in segment.METHODS:
        by_position = np.array([states[method][r] for r in sorted(states[method])])
        first, second = by_position[:, :10], by_position[:, 10:]
        # Each stretch is nearly one state, and the two stretches are different states.
        assert np.mean(first == np.bincount(first.ravel()).argmax()) > 0.9
        assert np.mean(second == np.bincount(second.ravel()).argmax()) > 0.9
        assert (
            np.bincount(first.ravel()).argmax() != np.bincount(second.ravel()).argmax()
        )
    shares = summary["state_shares"]["hmm"]
    assert shares == sorted(shares, reverse=True)
    assert sum(shares) == pytest.approx(1, abs=1e-3)


def test_hmm_states_stay_put_more_than_they_leave():
    steps, task_of_run = synthetic_steps()
    _, summary, _ = segment.segment(steps, task_of_run, [])
    assert max(summary["hmm_self_transition"]) > 0.8


def test_planted_runs_are_placed_on_the_natural_model():
    steps, task_of_run = synthetic_steps()
    planted = [
        {"run_id": "planted-1", "step_idx": idx, **fact("read", "ok")}
        for idx in range(6)
    ]
    states, summary, _ = segment.segment(steps, task_of_run, planted)
    assert len(states["hmm"]["planted-1"]) == 6
    assert len(states["gmm"]["planted-1"]) == 6
    assert summary["planted_runs"] == 1 and summary["natural_runs"] == 30
    natural_read_state = states["hmm"]["t0-r0"][0]
    assert set(states["hmm"]["planted-1"]) == {natural_read_state}


def test_models_are_fit_on_the_original_features_and_never_on_a_projection(
    monkeypatch,
):
    seen = []
    real_fit_hmm, real_fit_gmm = segment.fit_hmm, segment.fit_gmm

    def spy_hmm(X, lengths, n_states):
        seen.append(X)
        return real_fit_hmm(X, lengths, n_states)

    def spy_gmm(X, n_states):
        seen.append(X)
        return real_fit_gmm(X, n_states)

    monkeypatch.setattr(segment, "fit_hmm", spy_hmm)
    monkeypatch.setattr(segment, "fit_gmm", spy_gmm)
    steps, task_of_run = synthetic_steps(task_count=6)
    segment.segment(steps, task_of_run, [])
    assert seen and all(X.shape[1] == len(features.FEATURE_NAMES) for X in seen)
    assert not hasattr(segment, "PCA")


def test_held_out_scores_come_from_runs_of_other_tasks(monkeypatch):
    steps, task_of_run = synthetic_steps(task_count=6)
    sequences = segment.feature_sequences(steps)
    trained_on = []
    real_fit_hmm = segment.fit_hmm

    def spy(X, lengths, n_states):
        trained_on.append(len(lengths))
        return real_fit_hmm(X, lengths, n_states)

    monkeypatch.setattr(segment, "fit_hmm", spy)
    scores = segment.held_out_scores(sequences, task_of_run)
    assert [row["n_states"] for row in scores] == [2, 3]
    # With 6 tasks of 3 runs in 5 folds, no fit may see the 3 or 6 runs of its test tasks.
    assert max(trained_on) <= 18 - 3


def test_tables_hold_only_ids_and_states(tmp_path):
    steps, task_of_run = synthetic_steps(task_count=6)
    states, summary, _ = segment.segment(steps, task_of_run, [])
    table = segment.states_table(states)
    assert set(table.column_names) == {"run_id", "step_idx", "method", "state_id"}
    assert table.num_rows == 2 * len(steps)
    json.dumps(summary)


def test_prefix_states_are_decoded_from_the_prefix_alone_for_long_enough_runs(
    monkeypatch,
):
    monkeypatch.setattr(segment, "PREFIX_LENGTHS", (5, 15))
    steps, task_of_run = synthetic_steps(task_count=6)
    short = [s for s in steps if s["run_id"] == "t0-r0" and s["step_idx"] < 8]
    steps = [s for s in steps if s["run_id"] != "t0-r0"] + short
    states, _, prefixes = segment.segment(steps, task_of_run, [])
    assert set(prefixes) == {5, 15}
    assert len(prefixes[5]) == 18 and len(prefixes[15]) == 17
    assert all(len(v) == 5 for v in prefixes[5].values())
    assert "t0-r0" in prefixes[5] and "t0-r0" not in prefixes[15]
    # A run that is read only for its first five steps is the first stretch's state, numbered as in the whole run.
    assert prefixes[5]["t1-r0"] == states["hmm"]["t1-r0"][:5]
    table = segment.prefix_table(prefixes)
    assert set(table.column_names) == {"run_id", "k", "step_idx", "state_id"}
    assert table.num_rows == 18 * 5 + 17 * 15
