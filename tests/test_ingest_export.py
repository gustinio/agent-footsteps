import json

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from footsteps import export, ingest

# Sentinels that must never reach a table a person could publish.
COMMAND_TEXT = "SECRET_COMMAND_TEXT --flag"
OUTPUT_TEXT = "SECRET_OUTPUT_TEXT"
MESSAGE_TEXT = "SECRET_MESSAGE_TEXT"


def step(src="agent", tools=None, obs=None, msg=MESSAGE_TEXT):
    return {"src": src, "msg": msg, "tools": tools, "obs": obs}


def tool(fn, cmd):
    return {"fn": fn, "cmd": cmd}


@pytest.mark.parametrize(
    ("fn", "cmd", "expected"),
    [
        ("bash_command", "ls", "shell"),
        ("Bash", "ls", "shell"),
        ("run-shell-command", "ls", "shell"),
        ("run_\nshell_command", "ls", "shell"),
        ("Read", "/app/x", "read"),
        ("str_replace_editor", "view", "read"),
        ("str_replace_editor", "str_replace", "edit"),
        ("Grep", "x", "search"),
        ("TodoWrite", "x", "plan"),
        ("WebFetch", "x", "web"),
        ("mark_task_complete", "", "finish"),
        ("call_llm_batch", "x", "other"),
    ],
)
def test_tool_category_maps_scaffold_names(fn, cmd, expected):
    assert ingest.tool_category(fn, cmd) == expected


@pytest.mark.parametrize(
    ("obs", "expected"),
    [
        (None, "empty"),
        ("", "empty"),
        ("$34", "empty"),
        ("total 42\ndrwxr-xr-x", "ok"),
        ("bash: Rscript: command not found", "error"),
        ("Traceback (most recent call last):\n  File", "error"),
        ("<returncode>1</returncode>\n<output>", "error"),
        ("<returncode>0</returncode>\n<output>fine", "ok"),
        ("done\nSyntaxError: bad", "error"),
        ("the word terror inside a line", "ok"),
    ],
)
def test_result_status_reads_the_output_text(obs, expected):
    assert ingest.result_status(obs) == expected


def test_command_hash_ignores_whitespace_and_handles_list_commands():
    assert ingest.command_hash("ls   -la\n") == ingest.command_hash("ls -la")
    assert ingest.command_hash(["bash", "-lc", "ls"]) == ingest.command_hash(
        "bash -lc ls"
    )
    assert ingest.command_hash("ls") != ingest.command_hash("pwd")


@pytest.mark.parametrize("cmd", ["$38", "", "  \n"])
def test_command_hash_is_empty_without_a_readable_command(cmd):
    assert ingest.command_hash(cmd) is None


def test_step_facts_keep_no_text():
    facts = ingest.step_facts(step(tools=[tool("Bash", COMMAND_TEXT)], obs=OUTPUT_TEXT))
    assert set(facts) == {"tool_category", "result_status", "command_hash"}
    assert COMMAND_TEXT not in json.dumps(facts)
    assert facts["tool_category"] == "shell"
    assert facts["result_status"] == "ok"


def test_step_without_tools_has_category_none_and_no_hash():
    facts = ingest.step_facts(step())
    assert facts == {
        "tool_category": "none",
        "result_status": "empty",
        "command_hash": None,
    }


def test_step_uses_the_first_tool_call():
    facts = ingest.step_facts(step(tools=[tool("Read", "/a"), tool("Bash", "ls")]))
    assert facts["tool_category"] == "read"


def test_run_steps_drops_prompts_and_system_text():
    steps = [step(src="system"), step(src="user"), step(tools=[tool("Bash", "ls")])]
    assert len(ingest.run_steps(json.dumps(steps), "run")) == 1


@pytest.mark.parametrize("raw", [None, "null", "[]"])
def test_run_steps_accepts_trials_without_steps(raw):
    assert ingest.run_steps(raw, "run") == []


@pytest.mark.parametrize(
    "bad",
    [
        {"src": "agent", "msg": "", "tools": None},
        step(src="robot"),
        step(obs="x" * (ingest.OBS_LIMIT + 1)),
        step(tools=[{"fn": "Bash"}]),
    ],
)
def test_run_steps_rejects_data_that_breaks_the_documented_format(bad):
    with pytest.raises(ValueError, match="run-1"):
        ingest.run_steps(json.dumps([bad]), "run-1")


def raw_row(trial_id, task, reward, steps, agent="claude-code", model="m"):
    return {
        "task_name": task,
        "agent": agent,
        "model": model,
        "reward": reward,
        "trial_id": trial_id,
        "steps": None if steps is None else json.dumps(steps),
    }


def write_raw(raw_dir, rows):
    (raw_dir / "data").mkdir(parents=True)
    pq.write_table(pa.Table.from_pylist(rows), raw_dir / "data" / "train-00000.parquet")


@pytest.fixture
def normalized(tmp_path):
    rows = [
        raw_row(
            f"run-{n}",
            f"task-{n % 3}",
            n % 2,
            [
                step(src="user"),
                step(tools=[tool("Bash", COMMAND_TEXT)], obs=OUTPUT_TEXT),
                step(tools=[tool("Bash", "ls")], obs="bash: x: command not found"),
            ],
        )
        for n in range(10)
    ]
    rows.append(raw_row("run-empty", "task-0", 0, None))
    write_raw(tmp_path / "raw", rows)
    counts = ingest.normalize(
        tmp_path / "raw", tmp_path / "runs.parquet", tmp_path / "steps.parquet"
    )
    return tmp_path, counts


def test_normalize_writes_text_free_tables_and_counts(normalized):
    tmp_path, counts = normalized
    runs = pq.read_table(tmp_path / "runs.parquet").to_pylist()
    steps = pq.read_table(tmp_path / "steps.parquet").to_pylist()
    assert len(runs) == 10
    assert counts["trials"] == 11
    assert counts["trials_with_steps"] == 10
    assert counts["agent_steps"] == 20
    assert [s["step_idx"] for s in steps if s["run_id"] == "run-0"] == [0, 1]
    assert [s["result_status"] for s in steps if s["run_id"] == "run-0"] == [
        "ok",
        "error",
    ]
    tables = (tmp_path / "runs.parquet").read_bytes() + (
        tmp_path / "steps.parquet"
    ).read_bytes()
    for text in (COMMAND_TEXT, OUTPUT_TEXT, MESSAGE_TEXT):
        assert text.encode() not in tables


def test_sample_is_stable_and_ignores_input_order():
    ids = [f"run-{n}" for n in range(200)]
    first = export.sample_run_ids(ids, 20)
    assert len(first) == 20
    assert export.sample_run_ids(list(reversed(ids)), 20) == first


def test_site_json_has_step_facts_and_no_outcome_or_text(normalized):
    tmp_path, _ = normalized
    summary = {"dataset": "d", "revision": "r", "trials_with_steps": 10}
    site = export.build_site(
        tmp_path / "runs.parquet", tmp_path / "steps.parquet", summary
    )
    rendered = json.dumps(site)
    assert len(site["runs"]) == 10
    first = site["runs"][0]
    assert first["steps"] and set(first["steps"][0]) == {
        "tool_category",
        "result_status",
    }
    assert first["n_steps"] == len(first["steps"])
    assert "outcome" not in rendered
    for text in (COMMAND_TEXT, OUTPUT_TEXT, MESSAGE_TEXT, "command_hash"):
        assert text not in rendered
