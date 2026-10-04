import json

import pytest

from footsteps import evaluate, label
from footsteps.cli import main


def make_rows(n_runs=12):
    """Runs where the HMM state tracks the intent exactly, and the GMM state is unrelated to it."""
    intents = ["explore", "modify", "verify"]
    rows, labels = [], {}
    for run in range(n_runs):
        for idx in range(6):
            intent = intents[idx % 3]
            key = (f"run{run}", idx)
            rows.append(
                {
                    "run_id": key[0],
                    "step_idx": idx,
                    "hmm_state": idx % 3,
                    "gmm_state": (run + idx // 2) % 3,
                    "fact": "none",
                    "held_out": run % 2 == 0,
                }
            )
            labels[key] = intent
    return rows, labels


def test_kappa_decides_whether_the_llm_labels_are_used():
    human = {
        ("a", 0): "explore",
        ("a", 1): "modify",
        ("a", 2): "verify",
        ("a", 3): "other",
    }
    agreeing = evaluate.labeler_agreement(human, dict(human))
    assert agreeing["kappa"] == 1.0 and agreeing["passes"]
    flipped = {key: "explore" for key in human}
    disagreeing = evaluate.labeler_agreement(human, flipped)
    assert not disagreeing["passes"]
    assert disagreeing["labels_used"] == "human sample only"


def test_without_any_shared_step_the_llm_labels_are_not_trusted():
    assert not evaluate.labeler_agreement({("a", 0): "explore"}, {})["passes"]


def test_untrusted_llm_labels_are_left_out_and_human_labels_win():
    human = {("a", 0): "explore"}
    llm_labels = {("a", 0): "verify", ("a", 1): "modify"}
    assert evaluate.label_set(human, llm_labels, False) == human
    assert evaluate.label_set(human, llm_labels, True) == {
        ("a", 0): "explore",
        ("a", 1): "modify",
    }


def test_q1_passes_when_states_follow_the_labels_better_than_the_gmm():
    rows, labels = make_rows()
    result = evaluate.q1_result(rows, labels, labels, 3)
    q1 = result["q1"]
    assert q1["nmi"]["hmm"] == 1.0
    assert q1["nmi"]["gmm"] < q1["nmi"]["hmm"]
    assert q1["nmi"]["majority"] == 0.0
    assert q1["held_out_runs"] == 6
    assert q1["passes"]


def test_q1_fails_when_the_gmm_agrees_as_well_as_the_hmm():
    rows, labels = make_rows()
    for row in rows:
        row["gmm_state"] = row["hmm_state"]
    assert not evaluate.q1_result(rows, labels, labels, 3)["q1"]["passes"]


def test_q1_counts_only_held_out_tasks():
    rows, labels = make_rows()
    assert evaluate.q1_result(rows, labels, labels, 3)["q1"]["held_out_steps"] == 36


def test_states_are_named_from_facts_first_then_the_dominant_intent():
    rows = (
        [{"hmm_state": 0, "fact": "repeat", "label": "verify"} for _ in range(6)]
        + [{"hmm_state": 1, "fact": "none", "label": "explore"} for _ in range(6)]
        + [
            {"hmm_state": 2, "fact": "none", "label": label_}
            for label_ in ["explore", "modify", "verify", "other", "explore", "modify"]
        ]
        + [{"hmm_state": 3, "fact": "none", "label": "explore"}]
    )
    named = evaluate.name_states(rows, 4)
    assert [state["name"] for state in named] == [
        "repeating",
        "exploring",
        "mixed",
        "too few labels",
    ]
    assert named[1]["intents"]["explore"] == 1.0


def test_collect_human_keeps_ids_and_no_text(tmp_path, monkeypatch):
    monkeypatch.setattr(label, "SHEET_PATH", tmp_path / "sheet.csv")
    monkeypatch.setattr(label, "KEY_PATH", tmp_path / "key.json")
    monkeypatch.setattr(label, "HUMAN_LABELS_PATH", tmp_path / "human.csv")
    (tmp_path / "key.json").write_text(
        json.dumps([{"id": 1, "run_id": "r", "step_idx": 3}])
    )
    (tmp_path / "sheet.csv").write_text(
        'id,tool,command,output,message,label\n1,bash_command,SECRET,"out",msg, Verify \n'
    )
    label.collect_human()
    assert (tmp_path / "human.csv").read_text().splitlines() == [
        "run_id,step_idx,label",
        "r,3,verify",
    ]
    assert evaluate.read_human(tmp_path / "human.csv") == {("r", 3): "verify"}


def test_collect_human_rejects_an_unlabeled_row(tmp_path, monkeypatch):
    monkeypatch.setattr(label, "SHEET_PATH", tmp_path / "sheet.csv")
    monkeypatch.setattr(label, "KEY_PATH", tmp_path / "key.json")
    monkeypatch.setattr(label, "HUMAN_LABELS_PATH", tmp_path / "human.csv")
    (tmp_path / "key.json").write_text(
        json.dumps([{"id": 1, "run_id": "r", "step_idx": 3}])
    )
    (tmp_path / "sheet.csv").write_text(
        "id,tool,command,output,message,label\n1,a,b,c,d,\n"
    )
    with pytest.raises(SystemExit):
        label.collect_human()
    assert not (tmp_path / "human.csv").exists()


def test_label_collect_flag_is_wired(monkeypatch):
    called = []
    monkeypatch.setattr(label, "collect_human", lambda: called.append(1))
    assert main(["label", "--collect"]) == 0 and called
