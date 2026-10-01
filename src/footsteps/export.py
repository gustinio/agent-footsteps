"""Write the JSON contract the site reads, from step facts only."""

import hashlib
import json
import subprocess
from pathlib import Path

import pyarrow.parquet as pq

from footsteps.ingest import RUNS_PATH, STEPS_PATH, SUMMARY_PATH
from footsteps.runner import PLANTED_RUNS_PATH, PLANTED_STEPS_PATH

SITE_PATH = Path("results/site.json")

# The page draws every run as a ribbon, so the export is a small fixed sample.
SAMPLE_RUNS = 60

RUN_FIELDS = ("run_id", "task_id", "source", "agent", "model", "condition", "n_steps")
STEP_FIELDS = ("tool_category", "result_status")

# Outcomes stay out of the file until the pre-registration is tagged, so that looking at
# the data cannot steer the criteria. The tag is a default gate, not a hard block.
PREREG_TAG = "prereg"


def prereg_tag_exists(repo: Path = Path(".")) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--quiet", "--verify", f"refs/tags/{PREREG_TAG}"],
        cwd=repo,
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def sample_run_ids(run_ids: list[str], size: int = SAMPLE_RUNS) -> list[str]:
    """Pick runs by the hash of their id, so the sample never depends on row order or outcome."""
    return sorted(
        run_ids, key=lambda run_id: hashlib.sha256(run_id.encode()).hexdigest()
    )[:size]


def build_site(
    runs_path: Path,
    steps_path: Path,
    summary: dict,
    include_outcome: bool = False,
    planted_paths: tuple[Path, Path] | None = None,
) -> dict:
    """The public runs are a hashed sample, and the planted runs are all included because there are few."""
    runs = {row["run_id"]: row for row in pq.read_table(runs_path).to_pylist()}
    steps = pq.read_table(steps_path).to_pylist()
    chosen = set(sample_run_ids(list(runs)))
    planted = set()
    if planted_paths:
        planted_runs, planted_steps = (
            pq.read_table(path).to_pylist() for path in planted_paths
        )
        runs.update({row["run_id"]: row for row in planted_runs})
        steps += planted_steps
        planted = {row["run_id"] for row in planted_runs}
        chosen |= planted
    steps_by_run: dict[str, list[dict]] = {run_id: [] for run_id in chosen}
    for row in steps:
        if row["run_id"] in chosen:
            steps_by_run[row["run_id"]].append(row)
    run_fields = RUN_FIELDS + (("outcome",) if include_outcome else ())
    exported = []
    # Planted runs come first, because there are few of them and they are the demo.
    for run_id in sorted(chosen, key=lambda run_id: (run_id not in planted, run_id)):
        ordered = sorted(steps_by_run[run_id], key=lambda step: step["step_idx"])
        exported.append(
            {
                **{field: runs[run_id][field] for field in run_fields},
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
            "planted_runs": len(planted),
        },
        "runs": exported,
    }


def run() -> None:
    summary = json.loads(SUMMARY_PATH.read_text())
    planted_paths = (
        (PLANTED_RUNS_PATH, PLANTED_STEPS_PATH) if PLANTED_RUNS_PATH.exists() else None
    )
    site = build_site(
        RUNS_PATH, STEPS_PATH, summary, prereg_tag_exists(), planted_paths
    )
    SITE_PATH.parent.mkdir(parents=True, exist_ok=True)
    SITE_PATH.write_text(json.dumps(site, indent=1, sort_keys=True) + "\n")
