from footsteps import evaluate


def natural(repeat_in_state):
    """Two natural runs of four steps: step i is in state i % 2, and the steps in `repeat_in_state` repeat a command."""
    steps = []
    for run in ("a", "b"):
        for idx in range(4):
            repeats = idx % 2 == repeat_in_state
            steps.append(
                {
                    "run_id": run,
                    "step_idx": idx,
                    "tool_category": "shell",
                    "result_status": "ok",
                    "command_hash": "same" if idx < 1 or repeats else str(idx),
                    "verification_flag": False,
                }
            )
    states = {(r, i): i % 2 for r in ("a", "b") for i in range(4)}
    return steps, states


def test_the_repeating_state_is_the_one_where_most_steps_repeat():
    steps, states = natural(repeat_in_state=1)
    found = evaluate.repeating_state(steps, states, 2)
    assert found["state"] == 1 and found["repeat_share"] > 0.5


def test_no_state_qualifies_when_repeats_are_rare():
    steps, states = natural(repeat_in_state=1)
    for step in steps:
        step["command_hash"] = str(step["step_idx"])
    assert evaluate.repeating_state(steps, states, 2) is None


def planted(rising):
    runs, states = [], {}
    for task in rising:
        for condition in ("none", "strong"):
            run_id = f"{task}-{condition}"
            runs.append(
                {
                    "run_id": run_id,
                    "task_id": task,
                    "condition": condition,
                    "n_steps": 4,
                }
            )
            in_state = 3 if condition == "strong" and rising[task] else 0
            for idx in range(4):
                states[(run_id, idx)] = 1 if idx < in_state else 0
    return runs, states


def test_state_share_rises_per_task_and_every_task_is_listed():
    runs, states = planted({"t1": True, "t2": False})
    table = evaluate.state_share_table(runs, states, 1, ["t1", "t2", "t3"])
    assert [row["task_id"] for row in table] == ["t1", "t2"]
    assert [row["rose"] for row in table] == [True, False]
    assert table[0]["strong"] == 0.75 and table[0]["none"] == 0.0


def q2(rising, task_order, repeat_in_state=1):
    runs, states = planted(rising)
    steps = []
    for row in runs:
        for idx in range(4):
            repeats = row["condition"] == "strong" and rising[row["task_id"]] and idx
            steps.append(
                {
                    "run_id": row["run_id"],
                    "step_idx": idx,
                    "tool_category": "shell",
                    "result_status": "ok",
                    "command_hash": "x" if idx == 0 or repeats else str(idx),
                    "verification_flag": False,
                }
            )
    nat_steps, nat_states = natural(repeat_in_state)
    states.update(nat_states)
    return evaluate.q2_result(runs, steps, nat_steps, states, 2, task_order)


def test_q2_is_not_judged_until_every_task_has_run():
    result = q2({"t1": True, "t2": True}, ["t1", "t2", "t3"])
    assert result["passes"] is None and result["manipulation"]["passes"] is None
    assert result["tasks_run"] == 2


def test_q2_passes_when_both_checks_clear_their_bars(monkeypatch):
    monkeypatch.setattr(evaluate, "FINAL_MIN_RISES", 2)
    monkeypatch.setattr(evaluate, "STATE_MIN_RISES", 2)
    result = q2({"t1": True, "t2": True}, ["t1", "t2"])
    assert result["passes"] is True and result["state"]["rises"] == 2


def test_q2_fails_when_the_instruction_does_not_raise_the_share(monkeypatch):
    monkeypatch.setattr(evaluate, "FINAL_MIN_RISES", 2)
    result = q2({"t1": True, "t2": False}, ["t1", "t2"])
    assert result["manipulation"]["passes"] is False and result["passes"] is False
