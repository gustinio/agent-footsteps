import pytest

from footsteps import evaluate


@pytest.fixture(autouse=True)
def few_resamples(monkeypatch):
    monkeypatch.setattr(evaluate, "BOOTSTRAP_RESAMPLES", 40)


def make_runs(failing_states, n_tasks=10):
    """Two passing and two failing runs on every task, all with six identical steps.

    Length and the fact counts cannot tell the runs apart, so only the states can.
    """
    steps, outcomes, task_of_run, states = [], {}, {}, {}
    for task in range(n_tasks):
        for copy, failed in enumerate((False, False, True, True)):
            run_id = f"t{task}r{copy}"
            task_of_run[run_id] = f"task{task}"
            outcomes[run_id] = "fail" if failed else "pass"
            states[run_id] = failing_states if failed else [0] * 6
            steps += [
                {
                    "run_id": run_id,
                    "step_idx": idx,
                    "tool_category": "shell",
                    "result_status": "ok",
                    "command_hash": str(idx),
                    "verification_flag": False,
                }
                for idx in range(6)
            ]
    return evaluate.q3a_runs(steps, outcomes, task_of_run, states, 2)


def test_runs_carry_the_three_views_and_their_outcome():
    rows = make_runs([0, 0, 0, 0, 1, 1])
    assert len(rows) == 40
    assert sum(row["failed"] for row in rows) == 20
    row = rows[0]
    assert row["length"] == [6.0]
    assert len(row["profile"]) == 7 and len(row["moves"]) == 2
    assert len(row["counts"]) == len(evaluate.features.WINDOW_COUNT_NAMES)


def test_q3a_passes_when_the_profile_separates_failing_runs_and_length_does_not():
    result = evaluate.q3a_table(make_runs([0, 0, 0, 0, 1, 1]), 2)
    assert result["auroc"]["behaviour"]["estimate"] == 1.0
    assert result["auroc"]["length"]["estimate"] == 0.5
    assert result["differences"]["behaviour_minus_length"]["low"] > 0
    assert result["beats_length"] and result["near_supervised"] and result["passes"]
    assert result["tasks"] == 10 and result["failing_share"] == 0.5
    top = result["signal"]["profile"][0]
    # The two states mirror each other in the last third, so either may lead.
    more_in = {e["name"]: e["more_in"] for e in result["signal"]["profile"]}
    assert more_in["state 2 share, last third"] == "failing"
    assert more_in["state 1 share, last third"] == "passing"
    assert top["name"].endswith("share, last third") and top["clear"]
    assert result["signal"]["moves_tested"] == 2


def test_q3a_fails_when_the_profile_tells_nothing_beyond_length():
    result = evaluate.q3a_table(make_runs([0] * 6), 2)
    assert result["auroc"]["behaviour"]["estimate"] == 0.5
    assert not result["beats_length"]
    assert not result["passes"]


def test_q3a_is_repeatable():
    rows = make_runs([0, 0, 0, 0, 1, 1])
    assert evaluate.q3a_table(rows, 2) == evaluate.q3a_table(rows, 2)
