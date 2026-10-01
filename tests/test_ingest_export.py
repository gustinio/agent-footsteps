import json
import subprocess

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


@pytest.mark.parametrize(
    ("fn", "cmd", "expected"),
    [
        ("Bash", "python -m pytest tests/ -q", True),
        ("Bash", "diff out.txt expected.txt", True),
        ("Bash", "test -f /app/report.txt && echo ok", True),
        ("bash_command", ["bash", "-lc", "make check"], True),
        (
            "Bash",
            "python3 -c \"import json; print(len(json.load(open('o.json'))))\"",
            True,
        ),
        ("Bash", "node -e 'console.log(1)'", True),
        ("Bash", "cd repo && python3 - <<'PY'\nprint(1)\nPY", True),
        ("Bash", "python3 script.py", False),
        ("Bash", "cat report.txt", False),
        ("Bash", "git checkout -b fix", False),
        ("Bash", "echo contest", False),
        ("Bash", "$38", False),
        ("Read", "/app/tests/test_outputs.py", False),
        ("Write", "pytest", False),
    ],
)
def test_verification_flag_marks_shell_commands_that_check_work(fn, cmd, expected):
    facts = ingest.step_facts(step(tools=[tool(fn, cmd)]))
    assert facts["verification_flag"] is expected


def test_step_facts_keep_no_text():
    facts = ingest.step_facts(step(tools=[tool("Bash", COMMAND_TEXT)], obs=OUTPUT_TEXT))
    assert set(facts) == {
        "tool_category",
        "result_status",
        "command_hash",
        "verification_flag",
    }
    assert COMMAND_TEXT not in json.dumps(facts)
    assert facts["tool_category"] == "shell"
    assert facts["result_status"] == "ok"


def test_step_without_tools_has_category_none_and_no_hash():
    facts = ingest.step_facts(step())
    assert facts == {
        "tool_category": "none",
        "result_status": "empty",
        "command_hash": None,
        "verification_flag": False,
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


def test_site_json_carries_the_outcome_when_asked(normalized):
    tmp_path, _ = normalized
    summary = {"dataset": "d", "revision": "r", "trials_with_steps": 10}
    site = export.build_site(
        tmp_path / "runs.parquet", tmp_path / "steps.parquet", summary, True
    )
    assert {run["outcome"] for run in site["runs"]} == {"pass", "fail"}


def test_prereg_tag_gates_the_outcome(tmp_path):
    def git(*args):
        subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

    git("init", "-q")
    git("commit", "-q", "--allow-empty", "-m", "start")
    assert not export.prereg_tag_exists(tmp_path)
    git("tag", "prereg")
    assert export.prereg_tag_exists(tmp_path)


def test_verify_files_names_changed_and_missing_files():
    recorded = {"a": {"sha256": "1"}, "b": {"sha256": "2"}, "c": {"sha256": "3"}}
    files = {"a": {"sha256": "1"}, "b": {"sha256": "x"}}
    assert ingest.verify_files(files, recorded) == ["b", "c"]
    assert ingest.verify_files(files, {}) == []


@pytest.fixture
def pipeline(tmp_path, monkeypatch):
    """Point ingest at a small local dataset instead of the network."""
    rows = [
        raw_row(f"run-{n}", "task-0", n % 2, [step(tools=[tool("Bash", "ls")])])
        for n in range(4)
    ]
    write_raw(tmp_path / "raw", rows)
    monkeypatch.setattr(ingest, "download", lambda: tmp_path / "raw")
    monkeypatch.setattr(ingest, "RUNS_PATH", tmp_path / "runs.parquet")
    monkeypatch.setattr(ingest, "STEPS_PATH", tmp_path / "steps.parquet")
    monkeypatch.setattr(ingest, "SUMMARY_PATH", tmp_path / "summary.json")
    return tmp_path


def test_run_is_silent_when_the_files_match_the_record(pipeline, capsys):
    ingest.run()
    capsys.readouterr()
    ingest.run()
    assert capsys.readouterr().err == ""


def test_run_warns_about_a_corrupted_file_and_still_finishes(pipeline, capsys):
    ingest.run()
    recorded = json.loads((pipeline / "summary.json").read_text())["files"]
    capsys.readouterr()
    data_file = pipeline / "raw" / "data" / "train-00000.parquet"
    rows = pq.read_table(data_file).to_pylist()
    rows[0]["reward"] = 1 - rows[0]["reward"]
    pq.write_table(pa.Table.from_pylist(rows), data_file)

    ingest.run()

    assert "train-00000.parquet does not match the recorded checksum" in (
        capsys.readouterr().err
    )
    summary = json.loads((pipeline / "summary.json").read_text())
    assert summary["files"] == recorded
    assert summary["trials_with_steps"] == 4


def test_normalize_counts_tasks_with_both_outcomes(tmp_path):
    body = [step(tools=[tool("Bash", "ls")])]
    rows = [
        raw_row("a1", "t1", 1, body),
        raw_row("a2", "t1", 0, body),
        raw_row("a3", "t2", 1, body),
        raw_row("a4", "t2", 1, body),
        # A trial without steps never reaches the natural arm, so it cannot make a task mixed.
        raw_row("a5", "t3", 1, body),
        raw_row("a6", "t3", 0, None),
    ]
    write_raw(tmp_path / "raw", rows)
    counts = ingest.normalize(
        tmp_path / "raw", tmp_path / "runs.parquet", tmp_path / "steps.parquet"
    )
    assert counts["combinations"][0]["mixed_tasks"] == 1


def combo(agent, mixed, trials):
    return {
        "agent": agent,
        "model": "m",
        "mixed_tasks": mixed,
        "trials_with_steps": trials,
    }


def test_selection_takes_the_most_mixed_tasks_and_breaks_ties_by_trials():
    combos = [
        combo("a", 5, 10),
        combo("b", 9, 10),
        combo("c", 5, 30),
        combo("d", 1, 99),
    ]
    assert [c["agent"] for c in ingest.select_combinations(combos)] == ["b", "c"]
    assert [c["agent"] for c in ingest.select_combinations(combos, 1)] == ["b"]


def stream_event(kind, message):
    return json.dumps({"type": kind, "message": message})


def assistant(message_id, *blocks):
    return stream_event(
        "assistant", {"id": message_id, "content": list(blocks), "usage": {}}
    )


def tool_use(tool_id, name, tool_input):
    return {"type": "tool_use", "id": tool_id, "name": name, "input": tool_input}


def tool_result(tool_id, content):
    return stream_event(
        "user",
        {
            "content": [
                {"type": "tool_result", "tool_use_id": tool_id, "content": content}
            ]
        },
    )


PILOT_STREAM = "\n".join(
    [
        json.dumps({"type": "system", "subtype": "init"}),
        assistant("m1", {"type": "thinking", "thinking": ""}),
        assistant("m1", tool_use("t1", "Bash", {"command": COMMAND_TEXT})),
        tool_result("t1", OUTPUT_TEXT),
        assistant("m2", tool_use("t2", "Bash", {"command": "pytest -q"})),
        tool_result("t2", [{"type": "text", "text": "1 passed"}]),
        assistant("m3", {"type": "text", "text": MESSAGE_TEXT}),
        json.dumps({"type": "result", "subtype": "success"}),
    ]
)


def test_pilot_steps_join_a_message_split_across_lines_and_its_tool_result():
    steps = ingest.pilot_steps(PILOT_STREAM, "pilot")
    assert [s["tools"] and s["tools"][0]["cmd"] for s in steps] == [
        COMMAND_TEXT,
        "pytest -q",
        None,
    ]
    assert [s["obs"] for s in steps] == [OUTPUT_TEXT, "1 passed", None]


def test_pilot_steps_reduce_to_the_same_facts_as_public_steps(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.chdir(tmp_path)
    transcript = tmp_path / "pilot-1.jsonl"
    transcript.write_text(PILOT_STREAM)
    ingest.run_pilot([transcript])
    table = pq.read_table(ingest.PILOT_STEPS_PATH).to_pylist()
    assert [(r["tool_category"], r["verification_flag"]) for r in table] == [
        ("shell", False),
        ("shell", True),
        ("none", False),
    ]
    assert set(table[0]) == {"run_id", "step_idx", *ingest.step_facts(step())}
    shown = capsys.readouterr().out
    assert "pilot-1 1 shell ok True" in shown
    assert COMMAND_TEXT not in shown and MESSAGE_TEXT not in shown


def test_pilot_steps_split_parallel_calls_so_a_repeated_command_stays_visible():
    stream = "\n".join(
        [
            assistant(
                "m1",
                tool_use("t1", "Bash", {"command": "ls"}),
                tool_use("t2", "Bash", {"command": "ls"}),
            ),
            tool_result("t1", "a"),
            tool_result("t2", "a"),
        ]
    )
    steps = ingest.pilot_steps(stream, "pilot")
    assert [s["obs"] for s in steps] == ["a", "a"]
    hashes = [ingest.step_facts(s)["command_hash"] for s in steps]
    assert hashes[0] == hashes[1] is not None
