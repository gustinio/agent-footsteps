"""Rule facts, the blind sheet for the human sample, and the intent labels from the LLM wrapper."""

import collections
import csv
import hashlib
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from footsteps import features, ingest, llm, runner, segment

SHEET_PATH = Path("data/label_sheet.csv")
KEY_PATH = Path("data/label_key.json")
LLM_LABELS_PATH = Path("results/llm_labels.parquet")
HUMAN_LABELS_PATH = Path("results/human_labels.csv")

# The PRD sets 100 to 200 steps for the human sample, and the ADR sets about 2,000 for the LLM.
HUMAN_SAMPLE = 150
LLM_SAMPLE = 2000
# Each call carries about 10,000 tokens of overhead, so a batch is large enough to share it.
BATCH_SIZE = 40

# Tasks in this fold of the shared task folds count as held out, and the rest as training tasks,
# so the sample holds steps from both and a later check can compare agreement on seen and unseen tasks.
HELD_OUT_FOLD = 0

# Checked in this order to give a step its one fact when it has several, so rarer facts are not hidden.
RULE_FACTS = ("last", "repeat", "after_error", "no_tool")


def rule_facts(steps: list[dict]) -> list[set[str]]:
    """Per step, which rule facts hold, from the step facts only. Steps must be in run order."""
    repeats = features.repeat_flags(steps)
    facts = []
    for idx, (step, repeated) in enumerate(zip(steps, repeats)):
        held = set()
        if idx == len(steps) - 1:
            held.add("last")
        if repeated:
            held.add("repeat")
        if idx and steps[idx - 1]["result_status"] == "error":
            held.add("after_error")
        if step["tool_category"] == "none":
            held.add("no_tool")
        facts.append(held)
    return facts


def primary_fact(held: set[str]) -> str:
    return next((fact for fact in RULE_FACTS if fact in held), "none")


def candidates(
    steps: list[dict], states: dict[str, int], task_of_run: dict[str, str]
) -> list[dict]:
    """Every natural-arm step with the strata the sample is drawn across."""
    folds = segment.task_folds(task_of_run.values())
    by_run = collections.defaultdict(list)
    for step in steps:
        by_run[step["run_id"]].append(step)
    rows = []
    for run_id, run_steps in by_run.items():
        run_steps.sort(key=lambda step: step["step_idx"])
        for step, held in zip(run_steps, rule_facts(run_steps)):
            rows.append(
                {
                    "run_id": run_id,
                    "step_idx": step["step_idx"],
                    "state": states[(run_id, step["step_idx"])],
                    "fact": primary_fact(held),
                    "held_out": folds[task_of_run[run_id]] == HELD_OUT_FOLD,
                }
            )
    return rows


def _digest(*parts) -> str:
    return hashlib.sha256(":".join(map(str, parts)).encode()).hexdigest()


def draw(rows: list[dict], count: int) -> list[dict]:
    """The first count steps of a deal across state, rule fact and held-out strata.

    One step from each stratum in turn, with every choice fixed by a hash, so any prefix of the
    result is spread over the strata and a rerun draws the same steps.
    """
    strata = collections.defaultdict(list)
    for row in rows:
        strata[(row["state"], row["fact"], row["held_out"])].append(row)
    queues = [
        sorted(
            strata[key],
            key=lambda row: _digest("draw", row["run_id"], row["step_idx"]),
        )
        for key in sorted(strata, key=lambda key: _digest("stratum", *key))
    ]
    drawn = []
    for pass_number in range(max(map(len, queues), default=0)):
        drawn.extend(queue[pass_number] for queue in queues if pass_number < len(queue))
    return drawn[:count]


def sheet_rows(
    sample: list[dict], steps: dict[str, list[dict]]
) -> tuple[list[dict], list[dict]]:
    """The shuffled sheet with only step text and a blank label, and the key that maps its ids back."""
    shuffled = sorted(
        sample, key=lambda row: _digest("sheet", row["run_id"], row["step_idx"])
    )
    sheet, key = [], []
    for sheet_id, row in enumerate(shuffled, start=1):
        sheet.append(
            {
                "id": sheet_id,
                **ingest.step_text(steps[row["run_id"]][row["step_idx"]]),
                "label": "",
            }
        )
        key.append(
            {"id": sheet_id, "run_id": row["run_id"], "step_idx": row["step_idx"]}
        )
    return sheet, key


def load_natural() -> tuple[list[dict], dict[str, str]]:
    """Natural-arm steps with their HMM state, as the sample is drawn from, and the task of each run."""
    summary = json.loads(ingest.SUMMARY_PATH.read_text())
    arm = segment.natural_arm(
        pq.read_table(ingest.RUNS_PATH).to_pylist(), summary["selected"]
    )
    task_of_run = {run["run_id"]: run["task_id"] for run in arm}
    steps = pq.read_table(
        ingest.STEPS_PATH, filters=[("run_id", "in", list(task_of_run))]
    ).to_pylist()
    return steps, task_of_run


def draw_natural() -> tuple[list[dict], dict[str, str]]:
    steps, task_of_run = load_natural()
    states = {
        (row["run_id"], row["step_idx"]): row["state_id"]
        for row in pq.read_table(
            segment.SEGMENTATION_PATH, filters=[("method", "=", "hmm")]
        ).to_pylist()
    }
    return draw(candidates(steps, states, task_of_run), LLM_SAMPLE), task_of_run


def write_sheet() -> None:
    """Write the sheet and its key to data/, which is never committed because the sheet holds step text."""
    sample = draw_natural()[0][:HUMAN_SAMPLE]
    texts = ingest.raw_agent_steps(ingest.RAW_DIR, {row["run_id"] for row in sample})
    sheet, key = sheet_rows(sample, texts)
    SHEET_PATH.parent.mkdir(parents=True, exist_ok=True)
    with SHEET_PATH.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["id", "tool", "command", "output", "message", "label"]
        )
        writer.writeheader()
        writer.writerows(sheet)
    KEY_PATH.write_text(json.dumps(key, indent=2) + "\n")
    print(
        f"{len(sheet)} steps written to {SHEET_PATH}, with the run, task and condition left out"
    )


def collect_human() -> None:
    """Turn the filled sheet into run and step identifiers with a label, so the committed file holds no raw text."""
    key = {row["id"]: row for row in json.loads(KEY_PATH.read_text())}
    collected = []
    with SHEET_PATH.open(newline="") as handle:
        for row in csv.DictReader(handle):
            label = row["label"].strip().lower()
            if label not in llm.INTENTS:
                raise SystemExit(
                    f"sheet row {row['id']} has label {row['label']!r}, expected one of {', '.join(llm.INTENTS)}"
                )
            entry = key[int(row["id"])]
            collected.append(
                {
                    "run_id": entry["run_id"],
                    "step_idx": entry["step_idx"],
                    "label": label,
                }
            )
    if len(collected) != len(key):
        raise SystemExit(f"the sheet has {len(collected)} rows, the key has {len(key)}")
    HUMAN_LABELS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with HUMAN_LABELS_PATH.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["run_id", "step_idx", "label"])
        writer.writeheader()
        writer.writerows(collected)
    print(f"{len(collected)} human labels written to {HUMAN_LABELS_PATH}")


def label_steps(sample: list[dict], texts: dict[str, list[dict]]) -> list[dict]:
    """Intent labels from the wrapper in batches, stopping with what it has when the reserve is used up."""
    labeled = []
    for start in range(0, len(sample), BATCH_SIZE):
        batch = sample[start : start + BATCH_SIZE]
        try:
            labels = llm.classify(
                [
                    ingest.step_text(texts[row["run_id"]][row["step_idx"]])
                    for row in batch
                ]
            )
        except llm.BudgetUsedUp:
            print(
                "label: the labeler reserve is used up, stopping with what is labeled"
            )
            break
        labeled.extend(
            {
                "run_id": row["run_id"],
                "step_idx": row["step_idx"],
                "label": label,
                "labeler": "llm",
            }
            for row, label in zip(batch, labels)
            if label is not None
        )
    return labeled


def run() -> None:
    runner.check_login()
    sample, _ = draw_natural()
    texts = ingest.raw_agent_steps(ingest.RAW_DIR, {row["run_id"] for row in sample})
    labeled = label_steps(sample, texts)
    LLM_LABELS_PATH.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(labeled), LLM_LABELS_PATH)
    print(f"{len(labeled)} of {len(sample)} sampled steps labeled")
