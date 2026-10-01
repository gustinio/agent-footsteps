import json

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from footsteps import evaluate, export, features, ingest, runner, tasks
from footsteps.cli import main

COMMAND_TEXT = "SECRET_COMMAND_TEXT --flag"
OUTPUT_TEXT = "SECRET_OUTPUT_TEXT"
MESSAGE_TEXT = "SECRET_MESSAGE_TEXT"


def event(kind, message):
    return json.dumps({"type": kind, "message": message})


def transcript(commands, cost=0.25, subtype="success"):
    """A Claude Code stream with one tool call per command, then a final message and the result line."""
    lines = []
    for n, command in enumerate(commands):
        lines.append(
            event(
                "assistant",
                {
                    "id": f"m{n}",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": f"t{n}",
                            "name": "Bash",
                            "input": {"command": command},
                        }
                    ],
                },
            )
        )
        lines.append(
            event(
                "user",
                {
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": f"t{n}",
                            "content": OUTPUT_TEXT,
                        }
                    ]
                },
            )
        )
    lines.append(
        event(
            "assistant",
            {"id": "end", "content": [{"type": "text", "text": MESSAGE_TEXT}]},
        )
    )
    lines.append(
        json.dumps(
            {
                "type": "result",
                "subtype": subtype,
                "is_error": subtype != "success",
                "total_cost_usd": cost,
                "usage": {
                    "input_tokens": 10,
                    "cache_creation_input_tokens": 20,
                    "cache_read_input_tokens": 30,
                    "output_tokens": 40,
                },
            }
        )
    )
    return "\n".join(lines)


def make_task(root, name, solved_marker="done"):
    folder = root / name
    folder.mkdir(parents=True)
    (folder / "prompt.md").write_text(f"Do {name}.")
    (folder / "setup.sh").write_text("true\n")
    (folder / "check.sh").write_text(f"test -f {solved_marker}\n")
    (folder / "solution.sh").write_text(f"touch {solved_marker}\n")
    return folder


@pytest.fixture
def demo(tmp_path, monkeypatch):
    """Two tiny tasks and a fake model call, with every output path inside tmp_path."""
    monkeypatch.chdir(tmp_path)
    make_task(tmp_path / "tasks", "alpha")
    make_task(tmp_path / "tasks", "beta")
    monkeypatch.setattr(runner, "check_login", lambda: None)
    calls = []

    def fake_claude(run, workdir, budget):
        calls.append((run.run_id, budget))
        # Only the steered runs repeat their command, and only some leave the work done.
        command = f"echo {run.task.task_id}"
        commands = [command, command] if run.condition == "strong" else [command]
        if run.seed == 1:
            (workdir / "done").touch()
        return transcript(commands)

    monkeypatch.setattr(runner, "run_claude", fake_claude)
    return tmp_path, calls


def test_plan_runs_each_task_through_seeds_and_conditions_in_order(demo):
    planned = runner.plan(tasks.load_tasks())
    assert [r.run_id for r in planned] == [
        "alpha-s1-none",
        "alpha-s1-strong",
        "alpha-s2-none",
        "alpha-s2-strong",
        "beta-s1-none",
        "beta-s1-strong",
        "beta-s2-none",
        "beta-s2-strong",
    ]


def test_only_the_strong_condition_adds_the_steering_to_the_system_prompt():
    assert runner.system_prompt("none") == runner.BASE_PROMPT
    strong = runner.system_prompt("strong")
    assert strong.startswith(runner.BASE_PROMPT)
    assert "twice in a row" in strong


def test_command_replaces_the_system_prompt_and_caps_the_spend(demo):
    run = runner.plan(tasks.load_tasks())[1]
    command = runner.claude_command(run, 1.5)
    assert command[command.index("--system-prompt") + 1] == runner.system_prompt(
        "strong"
    )
    assert "--append-system-prompt" not in command
    assert command[command.index("--max-budget-usd") + 1] == "1.5000"
    assert command[command.index("--tools") + 1] == "Bash,Read,Write,Edit,Glob,Grep"


def test_run_records_step_facts_outcome_and_cost(demo):
    tmp_path, _ = demo
    runner.run(1)
    runs = {r["run_id"]: r for r in pq.read_table(runner.PLANTED_RUNS_PATH).to_pylist()}
    assert list(runs) == [
        "alpha-s1-none",
        "alpha-s1-strong",
        "alpha-s2-none",
        "alpha-s2-strong",
    ]
    assert runs["alpha-s1-strong"]["outcome"] == "pass"
    assert runs["alpha-s2-strong"]["outcome"] == "fail"
    assert runs["alpha-s1-strong"]["condition"] == "strong"
    assert runs["alpha-s1-strong"]["n_steps"] == 3
    steps = pq.read_table(runner.PLANTED_STEPS_PATH).to_pylist()
    assert set(steps[0]) == {
        "run_id",
        "step_idx",
        *ingest.step_facts({"src": "agent", "msg": "", "tools": None, "obs": None}),
    }
    log = runner.read_cost_log()
    assert [entry["spent_usd"] for entry in log] == [0.25, 0.5, 0.75, 1.0]
    assert log[0]["input_tokens"] == 10 and log[0]["cap_usd"] == runner.TOTAL_CAP_USD
    # The raw transcript stays in data/, and no committed table holds any text.
    assert (tmp_path / runner.TRANSCRIPT_DIR / "alpha-s1-none.jsonl").exists()
    tables = (
        runner.PLANTED_RUNS_PATH.read_bytes() + runner.PLANTED_STEPS_PATH.read_bytes()
    )
    for text in (COMMAND_TEXT, OUTPUT_TEXT, MESSAGE_TEXT, "echo alpha"):
        assert text.encode() not in tables


def test_run_skips_recorded_runs_and_continues_in_order(demo):
    _, calls = demo
    runner.run(1)
    calls.clear()
    runner.run()
    assert [run_id for run_id, _ in calls] == [
        "beta-s1-none",
        "beta-s1-strong",
        "beta-s2-none",
        "beta-s2-strong",
    ]


def test_each_run_may_spend_only_what_is_left_of_the_budget(demo):
    _, calls = demo
    runner.run(1)
    assert [budget for _, budget in calls] == pytest.approx(
        [runner.PLANTED_BUDGET_USD - 0.25 * n for n in range(4)]
    )


def test_run_stops_when_the_budget_is_used_up(demo, monkeypatch, capsys):
    _, calls = demo
    monkeypatch.setattr(runner, "PLANTED_BUDGET_USD", 0.6)
    with pytest.raises(SystemExit):
        runner.run()
    # After two runs 0.5 of 0.6 is spent, so the third gets 0.1, and the fourth finds nothing left.
    assert len(calls) == 3
    assert calls[-1][1] == pytest.approx(0.1)
    assert "budget is used up" in capsys.readouterr().out


def test_total_cap_is_checked_across_stages(demo):
    runner.COST_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    runner.COST_LOG_PATH.write_text(
        json.dumps({"stage": "label", "cost_usd": 35.0}) + "\n"
    )
    assert runner.remaining_budget(runner.read_cost_log()) == pytest.approx(5.0)


def test_a_run_that_hit_its_budget_is_logged_but_not_recorded(demo, monkeypatch):
    monkeypatch.setattr(
        runner,
        "run_claude",
        lambda run, workdir, budget: transcript(["ls"], 0.3, "error_max_budget_usd"),
    )
    runner.run(1)
    assert runner.read_table(runner.PLANTED_RUNS_PATH) == []
    assert len(runner.read_cost_log()) == 4


def test_a_transcript_without_a_result_line_stops_the_run(demo, monkeypatch):
    monkeypatch.setattr(runner, "run_claude", lambda run, workdir, budget: "")
    with pytest.raises(RuntimeError, match="no result line"):
        runner.run(1)


@pytest.mark.parametrize(
    "status",
    [
        {"subscriptionType": "team", "authMethod": "claude.ai"},
        {"subscriptionType": "pro", "authMethod": "api_key"},
    ],
)
def test_login_check_refuses_anything_but_the_personal_pro_plan(monkeypatch, status):
    class Done:
        stdout = json.dumps(status)

    monkeypatch.setattr(runner.subprocess, "run", lambda *a, **k: Done())
    with pytest.raises(SystemExit, match="personal Pro plan"):
        runner.check_login()


def step_fact(category, digest):
    return {"tool_category": category, "command_hash": digest}


def test_repeat_flags_mark_a_shell_command_seen_earlier_in_the_run():
    steps = [
        step_fact("shell", "a"),
        step_fact("shell", "a"),
        step_fact("shell", "b"),
        step_fact("read", "a"),
        step_fact("shell", None),
        step_fact("shell", None),
        step_fact("shell", "b"),
    ]
    assert features.repeat_flags(steps) == [
        False,
        True,
        False,
        False,
        False,
        False,
        True,
    ]


def make_rows(task_id, condition, repeats):
    run_id = f"{task_id}-{condition}"
    steps = (
        [{"run_id": run_id, "step_idx": 0, **step_fact("shell", "x")}]
        + [
            {"run_id": run_id, "step_idx": n + 1, **step_fact("shell", "x")}
            for n in range(repeats)
        ]
        + [{"run_id": run_id, "step_idx": repeats + 1, **step_fact("none", None)}]
    )
    return {"run_id": run_id, "task_id": task_id, "condition": condition}, steps


def table_for(rises):
    """rises maps a task to (repeats without, repeats with the instruction)."""
    runs, steps = [], []
    for task_id, (none, strong) in rises.items():
        for condition, repeats in (("none", none), ("strong", strong)):
            run_row, run_steps = make_rows(task_id, condition, repeats)
            runs.append(run_row)
            steps += run_steps
    return evaluate.manipulation_table(runs, steps, list(rises))


def test_manipulation_table_uses_the_share_of_shell_steps_that_repeat():
    table = table_for({"a": (0, 3), "b": (1, 1)})
    assert table[0]["none"] == 0 and table[0]["strong"] == 0.75
    assert [row["rose"] for row in table] == [True, False]


@pytest.mark.parametrize(
    ("rises", "verdict"),
    [
        ({"a": (0, 2), "b": (0, 2)}, "pending"),
        ({"a": (0, 2), "b": (0, 2), "c": (0, 0)}, "continue"),
        ({"a": (0, 2), "b": (0, 0), "c": (0, 0)}, "stop"),
        ({"a": (0, 2), "b": (0, 2), "c": (0, 2)}, "continue"),
    ],
)
def test_interim_rule_stops_when_fewer_than_two_of_three_tasks_rose(rises, verdict):
    table = table_for(rises)
    order = list(rises) if len(rises) >= 3 else list(rises) + ["c"]
    assert evaluate.interim_verdict(table, order) == verdict


def test_exporter_adds_every_planted_run_first_with_its_condition(
    demo, write_segmentation
):
    runner.run(1)
    summary = {"dataset": "d", "revision": "r", "trials_with_steps": 0}
    public_runs = demo[0] / "runs.parquet"
    public_steps = demo[0] / "steps.parquet"
    pq.write_table(
        pa.Table.from_pylist(
            [
                {
                    "run_id": "pub-1",
                    "task_id": "t",
                    "source": "public",
                    "agent": "a",
                    "model": "m",
                    "condition": None,
                    "outcome": "pass",
                    "n_steps": 1,
                }
            ]
        ),
        public_runs,
    )
    pq.write_table(
        pa.Table.from_pylist(
            [
                {
                    "run_id": "pub-1",
                    "step_idx": 0,
                    **ingest.step_facts(
                        {"src": "agent", "msg": "", "tools": None, "obs": None}
                    ),
                }
            ]
        ),
        public_steps,
    )
    paths = (runner.PLANTED_RUNS_PATH, runner.PLANTED_STEPS_PATH)
    segmentation = write_segmentation(public_steps, runner.PLANTED_STEPS_PATH)
    site = export.build_site(
        public_runs, public_steps, summary, segmentation, False, paths
    )
    assert [r["source"] for r in site["runs"]] == ["planted"] * 4 + ["public"]
    assert [r["condition"] for r in site["runs"]] == [
        "none",
        "strong",
        "none",
        "strong",
        None,
    ]
    assert site["meta"]["planted_runs"] == 4
    rendered = json.dumps(site)
    assert "outcome" not in rendered and "command_hash" not in rendered
    for text in (COMMAND_TEXT, OUTPUT_TEXT, MESSAGE_TEXT, "echo alpha"):
        assert text not in rendered


def test_cli_runner_passes_the_task_limit(monkeypatch):
    seen = []
    monkeypatch.setattr(runner, "run", lambda limit=None: seen.append(limit))
    assert main(["runner", "--tasks", "3"]) == 0
    assert main(["runner"]) == 0
    assert seen == [3, None]
