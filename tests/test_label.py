import csv
import json

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from footsteps import ingest, label, llm, runner
from footsteps.cli import main

COMMAND_TEXT = "SECRET_COMMAND_TEXT --flag"
OUTPUT_TEXT = "SECRET_OUTPUT_TEXT"
MESSAGE_TEXT = "SECRET_MESSAGE_TEXT"
TASK_NAME = "SECRET_TASK_NAME"
RUN_ID = "SECRET_RUN_ID"


def fact(category="shell", status="ok", digest=None):
    return {
        "tool_category": category,
        "result_status": status,
        "command_hash": digest,
        "verification_flag": False,
    }


def raw_step(command, obs=OUTPUT_TEXT, src="agent"):
    return {
        "src": src,
        "msg": MESSAGE_TEXT,
        "tools": [{"fn": "Bash", "cmd": command}] if command else None,
        "obs": obs,
    }


def result_line(text, cost=0.05, subtype="success"):
    return json.dumps(
        {
            "type": "result",
            "subtype": subtype,
            "is_error": subtype != "success",
            "result": text,
            "total_cost_usd": cost,
            "usage": {
                "input_tokens": 1,
                "cache_creation_input_tokens": 2,
                "cache_read_input_tokens": 3,
                "output_tokens": 4,
            },
        }
    )


def intent_reply(labels):
    return json.dumps([{"i": i, "label": value} for i, value in enumerate(labels)])


def test_rule_facts_hold_for_repeats_errors_missing_tools_and_the_last_step():
    steps = [
        fact(digest="a"),
        fact(status="error", digest="b"),
        fact(digest="a"),
        fact(category="none"),
    ]
    assert label.rule_facts(steps) == [
        set(),
        set(),
        {"repeat", "after_error"},
        {"no_tool", "last"},
    ]


def test_a_step_with_several_facts_takes_the_one_checked_first():
    assert label.primary_fact({"repeat", "after_error"}) == "repeat"
    assert label.primary_fact({"last", "no_tool"}) == "last"
    assert label.primary_fact(set()) == "none"


def pool():
    return [
        {
            "run_id": f"r{n}",
            "step_idx": idx,
            "state": (n + idx) % 3,
            "fact": "repeat" if idx == 2 else "none",
            "held_out": n % 2 == 0,
        }
        for n in range(12)
        for idx in range(5)
    ]


def test_draw_is_repeatable_and_a_prefix_spans_the_strata():
    first = label.draw(pool(), 12)
    assert first == label.draw(list(reversed(pool())), 12)
    strata = {(r["state"], r["fact"], r["held_out"]) for r in first}
    assert len(strata) == 12
    assert {r["held_out"] for r in first} == {True, False}


def test_draw_stops_at_the_count_and_at_the_end_of_the_pool():
    assert len(label.draw(pool(), 7)) == 7
    assert len(label.draw(pool(), 1000)) == len(pool())


def test_sheet_hides_run_task_and_condition_and_the_key_maps_it_back():
    sample = [{"run_id": RUN_ID, "step_idx": 1}, {"run_id": RUN_ID, "step_idx": 0}]
    texts = {RUN_ID: [raw_step("ls"), raw_step(COMMAND_TEXT)]}
    sheet, key = label.sheet_rows(sample, texts)
    assert [row["id"] for row in sheet] == [1, 2]
    assert all(row["label"] == "" for row in sheet)
    assert RUN_ID not in json.dumps(sheet)
    by_id = {entry["id"]: entry for entry in key}
    for row in sheet:
        entry = by_id[row["id"]]
        assert row["command"] == ("ls" if entry["step_idx"] == 0 else COMMAND_TEXT)


def write_raw(raw_dir, rows):
    (raw_dir / "data").mkdir(parents=True)
    pq.write_table(pa.Table.from_pylist(rows), raw_dir / "data" / "train-00000.parquet")


def raw_row(trial_id, steps):
    return {
        "trial_id": trial_id,
        "task_name": TASK_NAME,
        "agent": "a",
        "model": "m",
        "reward": 1,
        "steps": json.dumps(steps),
    }


def test_raw_agent_steps_index_like_the_step_table_and_skip_other_runs(tmp_path):
    write_raw(
        tmp_path,
        [
            raw_row("wanted", [raw_step(None, src="user"), raw_step("ls")]),
            raw_row("other", [raw_step("pwd")]),
        ],
    )
    found = ingest.raw_agent_steps(tmp_path, {"wanted"})
    assert list(found) == ["wanted"]
    assert [ingest.step_text(s)["command"] for s in found["wanted"]] == ["ls"]


def test_step_text_blanks_placeholders_and_cuts_long_text():
    text = ingest.step_text(raw_step("$12", obs="x" * 5000))
    assert text["command"] == ""
    assert len(text["output"]) == 800
    assert ingest.step_text(raw_step(None, obs=None))["tool"] == ""


@pytest.fixture
def labeling(tmp_path, monkeypatch):
    """A fake model that labels every step explore, with every output path inside tmp_path."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runner, "check_login", lambda: None)
    calls = []

    def fake_claude(prompt, budget):
        calls.append((prompt, budget))
        count = len(json.loads(prompt))
        return result_line(intent_reply(["explore"] * count))

    monkeypatch.setattr(llm, "run_claude", fake_claude)
    return calls


def batch(*commands):
    return [ingest.step_text(raw_step(command)) for command in commands]


def test_classify_labels_a_batch_and_logs_the_call(labeling):
    assert llm.classify(batch("ls", "pwd")) == ["explore", "explore"]
    (entry,) = runner.read_cost_log()
    assert entry["stage"] == "labeler"
    assert entry["cost_usd"] == 0.05
    assert entry["output_tokens"] == 4
    assert entry["budget_usd"] == llm.RESERVE_USD


def test_the_same_batch_is_served_from_the_cache_without_a_call(labeling):
    llm.classify(batch("ls"))
    llm.classify(batch("ls"))
    assert len(labeling) == 1
    llm.classify(batch("pwd"))
    assert len(labeling) == 2


def test_the_prompt_carries_the_step_text_and_nothing_else(labeling):
    llm.classify(batch(COMMAND_TEXT))
    ((prompt, _),) = labeling
    assert COMMAND_TEXT in prompt
    assert set(json.loads(prompt)[0]) == {"i", "tool", "command", "output", "message"}


def test_a_call_that_would_have_no_reserve_is_refused(labeling, monkeypatch):
    monkeypatch.setattr(llm, "RESERVE_USD", 0.04)
    llm.classify(batch("ls"))
    with pytest.raises(llm.BudgetUsedUp):
        llm.classify(batch("pwd"))
    assert len(labeling) == 1


def test_the_labeler_never_takes_the_planted_share_of_the_cap(labeling):
    runner.COST_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    runner.COST_LOG_PATH.write_text(
        json.dumps({"stage": "runner", "cost_usd": runner.TOTAL_CAP_USD - 0.1}) + "\n"
    )
    llm.classify(batch("ls"))
    assert labeling[0][1] == pytest.approx(0.1)


def test_a_call_that_ended_in_error_is_logged_but_not_cached(labeling, monkeypatch):
    monkeypatch.setattr(
        llm,
        "run_claude",
        lambda prompt, budget: result_line("", subtype="error_max_budget_usd"),
    )
    with pytest.raises(RuntimeError):
        llm.classify(batch("ls"))
    assert len(runner.read_cost_log()) == 1
    assert llm.read_cache() == {}


def test_parse_labels_keeps_only_valid_unrepeated_intents():
    reply = json.dumps(
        [
            {"i": 0, "label": "verify"},
            {"i": 0, "label": "modify"},
            {"i": 1, "label": "guess"},
            {"i": 9, "label": "explore"},
            "junk",
        ]
    )
    assert llm.parse_labels(f"Here you go: {reply}", 3) == ["verify", None, None]
    assert llm.parse_labels("no list here", 2) == [None, None]


def test_label_steps_stops_with_what_it_has_when_the_reserve_is_used_up(
    labeling, monkeypatch
):
    monkeypatch.setattr(label, "BATCH_SIZE", 2)
    monkeypatch.setattr(llm, "RESERVE_USD", 0.06)
    sample = [{"run_id": "r", "step_idx": idx} for idx in range(6)]
    texts = {"r": [raw_step(f"echo {idx}") for idx in range(6)]}
    labeled = label.label_steps(sample, texts)
    assert [row["step_idx"] for row in labeled] == [0, 1, 2, 3]
    assert {row["labeler"] for row in labeled} == {"llm"}


def test_sheet_command_writes_a_blind_csv_and_makes_no_model_call(
    labeling, monkeypatch, tmp_path
):
    write_raw(
        tmp_path / ingest.RAW_DIR,
        [raw_row(RUN_ID, [raw_step(COMMAND_TEXT), raw_step("ls")])],
    )
    sample = [
        {"run_id": RUN_ID, "step_idx": 0, "state": 0, "fact": "none", "held_out": True},
        {
            "run_id": RUN_ID,
            "step_idx": 1,
            "state": 1,
            "fact": "last",
            "held_out": False,
        },
    ]
    monkeypatch.setattr(label, "draw_natural", lambda: (sample, {RUN_ID: TASK_NAME}))
    assert main(["label", "--sheet"]) == 0
    sheet_text = label.SHEET_PATH.read_text()
    rows = list(csv.DictReader(sheet_text.splitlines()))
    assert len(rows) == 2
    assert COMMAND_TEXT in sheet_text
    assert RUN_ID not in sheet_text and TASK_NAME not in sheet_text
    assert labeling == []


def test_label_command_writes_text_free_intent_labels(labeling, monkeypatch, tmp_path):
    write_raw(tmp_path / ingest.RAW_DIR, [raw_row(RUN_ID, [raw_step(COMMAND_TEXT)])])
    sample = [
        {"run_id": RUN_ID, "step_idx": 0, "state": 0, "fact": "none", "held_out": True}
    ]
    monkeypatch.setattr(label, "draw_natural", lambda: (sample, {RUN_ID: TASK_NAME}))
    assert main(["label"]) == 0
    rows = pq.read_table(label.LLM_LABELS_PATH).to_pylist()
    assert rows == [
        {"run_id": RUN_ID, "step_idx": 0, "label": "explore", "labeler": "llm"}
    ]
    assert COMMAND_TEXT not in json.dumps(rows)
