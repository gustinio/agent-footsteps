"""Write the JSON contract the site reads, from step facts only."""

import hashlib
import json
from pathlib import Path

import pyarrow.parquet as pq

from footsteps.ingest import RUNS_PATH, STEPS_PATH, SUMMARY_PATH

SITE_PATH = Path("results/site.json")

# The page draws every run as a ribbon, so the export is a small fixed sample.
SAMPLE_RUNS = 60

RUN_FIELDS = ("run_id", "task_id", "source", "agent", "model", "n_steps")
STEP_FIELDS = ("tool_category", "result_status")


def sample_run_ids(run_ids: list[str], size: int = SAMPLE_RUNS) -> list[str]:
    """Pick runs by the hash of their id, so the sample never depends on row order or outcome."""
    return sorted(
        run_ids, key=lambda run_id: hashlib.sha256(run_id.encode()).hexdigest()
    )[:size]


def build_site(runs_path: Path, steps_path: Path, summary: dict) -> dict:
    runs = {row["run_id"]: row for row in pq.read_table(runs_path).to_pylist()}
    chosen = set(sample_run_ids(list(runs)))
    steps_by_run: dict[str, list[dict]] = {run_id: [] for run_id in chosen}
    for row in pq.read_table(steps_path).to_pylist():
        if row["run_id"] in chosen:
            steps_by_run[row["run_id"]].append(row)
    exported = []
    for run_id in sorted(chosen):
        ordered = sorted(steps_by_run[run_id], key=lambda step: step["step_idx"])
        exported.append(
            {
                **{field: runs[run_id][field] for field in RUN_FIELDS},
                "steps": [
                    {field: step[field] for field in STEP_FIELDS} for step in ordered
                ],
            }
        )
    return {
        "meta": {
            "dataset": summary["dataset"],
            "revision": summary["revision"],
            "runs_in_dataset": summary["trials_with_steps"],
        },
        "runs": exported,
    }


def run() -> None:
    summary = json.loads(SUMMARY_PATH.read_text())
    site = build_site(RUNS_PATH, STEPS_PATH, summary)
    SITE_PATH.parent.mkdir(parents=True, exist_ok=True)
    SITE_PATH.write_text(json.dumps(site, indent=1, sort_keys=True) + "\n")
