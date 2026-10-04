"""Write the JSON contract the site reads, from step facts only."""

import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
from sklearn.decomposition import PCA

from footsteps import features
from footsteps.evaluate import Q1_PATH, Q2_PATH, Q3A_PATH, Q3B_PATH, Q4_PATH
from footsteps.ingest import RUNS_PATH, STEPS_PATH, SUMMARY_PATH
from footsteps.runner import PLANTED_RUNS_PATH, PLANTED_STEPS_PATH
from footsteps.segment import METHODS, SEGMENT_SUMMARY_PATH, SEGMENTATION_PATH

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


def read_states(path: Path) -> dict[str, dict[str, list[int]]]:
    """Method, then run, then the state of each step in order."""
    states: dict[str, dict[str, dict[int, int]]] = {m: {} for m in METHODS}
    for row in pq.read_table(path).to_pylist():
        states[row["method"]].setdefault(row["run_id"], {})[row["step_idx"]] = row[
            "state_id"
        ]
    return {
        method: {
            run_id: [by_step[idx] for idx in sorted(by_step)]
            for run_id, by_step in by_run.items()
        }
        for method, by_run in states.items()
    }


def _jitter(run_id: str, step_idx: int, axis: str) -> float:
    """A repeatable offset in [-1, 1], so identical steps do not draw as one dot."""
    digest = hashlib.sha256(f"{run_id}:{step_idx}:{axis}".encode()).digest()
    return int.from_bytes(digest[:4], "big") / 2**31 - 1


def project(
    ordered_runs: dict[str, list[dict]],
) -> dict[str, list[tuple[float, float]]]:
    """Two principal components of the step features, scaled to 0 to 1, for display only.

    The segmenter never sees these coordinates. The offset is a small fraction of the range.
    """
    run_ids = list(ordered_runs)
    matrix = np.vstack([features.step_features(ordered_runs[r]) for r in run_ids])
    coords = PCA(n_components=2, random_state=0).fit_transform(matrix)
    low, high = coords.min(axis=0), coords.max(axis=0)
    scaled = (coords - low) / np.where(high > low, high - low, 1)
    projected, row = {}, 0
    for run_id in run_ids:
        points = []
        for idx in range(len(ordered_runs[run_id])):
            x = scaled[row, 0] + 0.012 * _jitter(run_id, idx, "x")
            y = scaled[row, 1] + 0.012 * _jitter(run_id, idx, "y")
            points.append(
                (round(float(np.clip(x, 0, 1)), 4), round(float(np.clip(y, 0, 1)), 4))
            )
            row += 1
        projected[run_id] = points
    return projected


def build_site(
    runs_path: Path,
    steps_path: Path,
    summary: dict,
    segmentation: tuple[Path, Path],
    include_outcome: bool = False,
    planted_paths: tuple[Path, Path] | None = None,
    q1_path: Path | None = None,
    q3a_path: Path | None = None,
    q3b_path: Path | None = None,
    q4_path: Path | None = None,
    q2_path: Path | None = None,
) -> dict:
    """The public runs are a hashed sample of the segmented natural runs, and the planted runs are all included because there are few."""
    states_path, segment_summary_path = segmentation
    states = read_states(states_path)
    segment_summary = json.loads(segment_summary_path.read_text())
    runs = {
        row["run_id"]: row
        for row in pq.read_table(runs_path).to_pylist()
        if row["run_id"] in states["hmm"]
    }
    steps = pq.read_table(
        steps_path, filters=[("run_id", "in", list(runs))]
    ).to_pylist()
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
    ordered_steps = {
        run_id: sorted(rows, key=lambda step: step["step_idx"])
        for run_id, rows in steps_by_run.items()
    }
    points = project(ordered_steps)
    run_fields = RUN_FIELDS + (("outcome",) if include_outcome else ())
    exported = []
    # Planted runs come first, because there are few of them and they are the demo.
    for run_id in sorted(chosen, key=lambda run_id: (run_id not in planted, run_id)):
        ordered = ordered_steps[run_id]
        exported.append(
            {
                **{field: runs[run_id][field] for field in run_fields},
                "steps": [
                    {
                        **{field: step[field] for field in STEP_FIELDS},
                        "hmm_state": states["hmm"][run_id][idx],
                        "gmm_state": states["gmm"][run_id][idx],
                        "x": points[run_id][idx][0],
                        "y": points[run_id][idx][1],
                    }
                    for idx, step in enumerate(ordered)
                ],
            }
        )
    # The agreement tables and state names hold counts and shares only, never step text.
    q1 = json.loads(q1_path.read_text()) if q1_path and q1_path.exists() else None
    q3a = json.loads(q3a_path.read_text()) if q3a_path and q3a_path.exists() else None
    q3b = json.loads(q3b_path.read_text()) if q3b_path and q3b_path.exists() else None
    q4 = json.loads(q4_path.read_text()) if q4_path and q4_path.exists() else None
    q2 = json.loads(q2_path.read_text()) if q2_path and q2_path.exists() else None
    return {
        "meta": {
            **({"q1": q1} if q1 else {}),
            **({"q2": q2} if q2 else {}),
            **({"q3a": q3a} if q3a else {}),
            **({"q3b": q3b} if q3b else {}),
            **({"q4": q4} if q4 else {}),
            "dataset": summary["dataset"],
            "revision": summary["revision"],
            "runs_in_dataset": summary["trials_with_steps"],
            "planted_runs": len(planted),
            "segmentation": {
                "n_states": segment_summary["n_states"],
                "natural_runs": segment_summary["natural_runs"],
                "state_shares": segment_summary["state_shares"],
            },
        },
        "runs": exported,
    }


def run() -> None:
    summary = json.loads(SUMMARY_PATH.read_text())
    planted_paths = (
        (PLANTED_RUNS_PATH, PLANTED_STEPS_PATH) if PLANTED_RUNS_PATH.exists() else None
    )
    site = build_site(
        RUNS_PATH,
        STEPS_PATH,
        summary,
        (SEGMENTATION_PATH, SEGMENT_SUMMARY_PATH),
        prereg_tag_exists(),
        planted_paths,
        Q1_PATH,
        Q3A_PATH,
        Q3B_PATH,
        Q4_PATH,
        Q2_PATH,
    )
    SITE_PATH.parent.mkdir(parents=True, exist_ok=True)
    SITE_PATH.write_text(json.dumps(site, indent=1, sort_keys=True) + "\n")
