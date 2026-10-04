import pytest

from footsteps import evaluate, features


@pytest.fixture(autouse=True)
def few_resamples(monkeypatch):
    monkeypatch.setattr(evaluate, "BOOTSTRAP_RESAMPLES", 40)


def step(run_id, idx, category="shell", status="ok"):
    return {
        "run_id": run_id,
        "step_idx": idx,
        "tool_category": category,
        "result_status": status,
        "command_hash": str(idx),
        "verification_flag": False,
    }


def make_rows(failing_states, n_tasks=10, short_runs=0):
    """Two passing and two failing runs on every task, all with eight identical steps.

    The first `short_runs` runs have only three steps, so they drop out of the early check.
    Only the states of the first five steps can tell failing runs from passing ones.
    """
    steps, outcomes, task_of_run, states = [], {}, {}, {}
    for task in range(n_tasks):
        for copy, failed in enumerate((False, False, True, True)):
            run_id = f"t{task}r{copy}"
            task_of_run[run_id] = f"task{task}"
            outcomes[run_id] = "fail" if failed else "pass"
            steps += [step(run_id, idx) for idx in range(3 if short_runs > 0 else 8)]
            short_runs -= 1
            if len([s for s in steps if s["run_id"] == run_id]) >= 5:
                states[run_id] = failing_states if failed else [0] * 5
    return steps, outcomes, task_of_run, {5: states}


def test_prefix_counts_are_errors_and_different_tools_so_far():
    steps = [
        step("r", 0, "read"),
        step("r", 1, "shell", "error"),
        step("r", 2, "shell", "error"),
        step("r", 3, "none"),
    ]
    assert features.prefix_counts(steps) == [2.0, 2.0]
    assert features.prefix_counts(steps[:1]) == [0.0, 1.0]


def test_runs_with_fewer_than_k_steps_drop_out_and_views_read_only_the_prefix():
    steps, outcomes, task_of_run, prefixes = make_rows([0, 0, 1, 1, 1], short_runs=6)
    rows = evaluate.q3b_runs(steps, outcomes, task_of_run, prefixes, 2)[5]
    assert len(rows) == 34
    row = rows[-1]
    assert row["length"] == [8.0]
    assert row["baseline"] == [0.0, 1.0]
    assert len(row["profile"]) == 7 and len(row["counts"]) == len(
        features.WINDOW_COUNT_NAMES
    )
    assert sum(row["counts"][: len(features.CATEGORIES)]) == 5


def test_q3b_passes_when_the_prefix_states_separate_failing_runs_and_the_baseline_cannot():
    steps, outcomes, task_of_run, prefixes = make_rows([0, 0, 1, 1, 1], short_runs=4)
    rows_by_k = evaluate.q3b_runs(steps, outcomes, task_of_run, prefixes, 2)
    result = evaluate.q3b_table(rows_by_k, total_runs=40)
    (entry,) = result["per_k"]
    assert entry["k"] == 5 and entry["runs"] == 36 and entry["runs_dropped"] == 4
    assert entry["auroc"]["behaviour"]["estimate"] == 1.0
    assert entry["auroc"]["baseline"]["estimate"] == 0.5
    assert entry["differences"]["behaviour_minus_baseline"]["low"] > 0
    assert entry["passes"] and result["passes"]
    assert set(entry["auroc"]) == {"length", "baseline", "behaviour", "supervised"}


def test_q3b_fails_when_the_states_do_not_differ():
    steps, outcomes, task_of_run, prefixes = make_rows([0] * 5)
    rows_by_k = evaluate.q3b_runs(steps, outcomes, task_of_run, prefixes, 2)
    result = evaluate.q3b_table(rows_by_k, total_runs=40)
    assert not result["per_k"][0]["beats_baseline"] and not result["passes"]


def labeled_steps(unseen_aligned):
    """Steps whose label equals their state on seen tasks, and on unseen tasks only when unseen_aligned."""
    rows = []
    for run in range(6):
        for idx in range(10):
            for held in (False, True):
                state = idx % 2
                aligned = not held or unseen_aligned
                rows.append(
                    {
                        "run_id": f"{held}{run}",
                        "step_idx": idx,
                        "held_out": held,
                        "hmm_state": state,
                        "label": "a" if (state if aligned else (idx // 2) % 2) else "b",
                    }
                )
    return rows


def test_agreement_drop_is_seen_minus_unseen_and_judged_against_the_bar():
    same = evaluate.agreement_drop(labeled_steps(True))
    assert same["seen"] == same["unseen"] == 1.0 and same["passes"]
    worse = evaluate.agreement_drop(labeled_steps(False))
    assert worse["drop"]["estimate"] > evaluate.Q4_MAX_DROP and not worse["passes"]
    assert worse["seen_steps"] == worse["unseen_steps"] == 60


def test_q4_compares_run_level_and_task_grouped_folds_and_waits_for_labels():
    steps, outcomes, task_of_run, prefixes = make_rows([0, 0, 1, 1, 1])
    rows_by_k = evaluate.q3b_runs(steps, outcomes, task_of_run, prefixes, 2)
    whole = evaluate.q3a_runs(
        steps, outcomes, task_of_run, {r: [0] * 8 for r in outcomes}, 2
    )
    result = evaluate.q4_table(whole, rows_by_k, None)
    assert [stage["stage"] for stage in result["auroc"]] == [
        "whole run",
        "first 5 steps",
    ]
    prefix = result["auroc"][1]
    assert prefix["seen"] == prefix["unseen"] == 1.0 and prefix["passes"]
    assert result["auroc_passes"] and result["agreement"] is None
    assert result["passes"] is None
    judged = evaluate.q4_table(whole, rows_by_k, labeled_steps(True))
    assert judged["passes"] is True
