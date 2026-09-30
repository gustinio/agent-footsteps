"""Download the public trajectories and reduce each step to text-free facts."""

import collections
import hashlib
import json
import re
import statistics
import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

DATASET = "yoonholee/terminalbench-trajectories"
REVISION = "04e8940f5b6736a7ce8d22224fe2f2af74163ed2"

RAW_DIR = Path("data/terminalbench")
RUNS_PATH = Path("data/runs.parquet")
STEPS_PATH = Path("data/steps.parquet")
SUMMARY_PATH = Path("results/dataset_summary.json")

STEP_KEYS = {"src", "msg", "tools", "obs"}
# The PRD allows one or two, and two keeps more public runs for the natural arm.
SELECTED = 2
SOURCES = {"user", "agent", "system"}
OBS_LIMIT = 5000

# The dataset replaces some long strings with a "$<number>" reference, so the
# text behind it is unavailable and must not be mistaken for a real command or output.
_PLACEHOLDER = re.compile(r"\$\d+")

# Scaffolds name the same action differently, so categories key on the tool name
# lowercased with separators normalised. Anything unlisted is "other".
_CATEGORIES = {
    "shell": (
        "bash_command bash execute_bash shell run_shell_command execute bashoutput "
        "interact_with_shell wait_shell_command kill_shell_command killshell "
        "execute_ipython_cell"
    ),
    "read": "read read_file read_many_files view_image open_image image_read read_media",
    "search": "grep glob ls list_directory search_file_content",
    "edit": "edit write write_file replace replace_file edit_file str_replace_editor",
    "plan": "todowrite update_plan task_tracker write_todos save_plan think enterplanmode exitplanmode",
    "web": "webfetch websearch google_web_search web_fetch fetch_url web_search http_request",
    "finish": "mark_task_complete finish end_execution",
}
_CATEGORY_OF = {
    fn: category for category, fns in _CATEGORIES.items() for fn in fns.split()
}

# Result status is inferred from the output text, so it is a heuristic: a run
# that prints one of these phrases counts as an error even if the agent expected it.
_ERROR = re.compile(
    r"Traceback \(most recent call last\)"
    r"|command not found"
    r"|No such file or directory"
    r"|Permission denied"
    r"|<returncode>\s*(?!0\s*<)-?\d+"
    r"|[Ee]xit (?:code|status)[: ]+[1-9]"
    r"|(?im:^\w*error\b)"
    r"|\bfatal:"
)


def download() -> Path:
    from huggingface_hub import snapshot_download

    return Path(
        snapshot_download(
            DATASET,
            repo_type="dataset",
            revision=REVISION,
            local_dir=RAW_DIR,
            allow_patterns=["data/*", "README.md"],
        )
    )


def _is_placeholder(value) -> bool:
    return isinstance(value, str) and _PLACEHOLDER.fullmatch(value) is not None


def tool_category(fn: str, cmd) -> str:
    name = "".join(fn.split()).replace("-", "_").lower()
    # The editor tool multiplexes viewing and editing through its first argument.
    if name == "str_replace_editor" and cmd == "view":
        return "read"
    return _CATEGORY_OF.get(name, "other")


def result_status(obs: str | None) -> str:
    if not obs or _is_placeholder(obs):
        return "empty"
    return "error" if _ERROR.search(obs) else "ok"


def command_hash(cmd) -> str | None:
    if _is_placeholder(cmd):
        return None
    text = " ".join(str(part) for part in cmd) if isinstance(cmd, list) else str(cmd)
    normalized = " ".join(text.split())
    if not normalized:
        return None
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def check_step_format(step, where: str) -> None:
    """Fail loudly if real data stops matching the documented step format."""
    if not isinstance(step, dict) or set(step) != STEP_KEYS:
        raise ValueError(f"{where}: unexpected step keys")
    if step["src"] not in SOURCES:
        raise ValueError(f"{where}: unexpected step source {step['src']!r}")
    obs = step["obs"]
    if obs is not None and (not isinstance(obs, str) or len(obs) > OBS_LIMIT):
        raise ValueError(
            f"{where}: obs is not a string of at most {OBS_LIMIT} characters"
        )
    tools = step["tools"]
    if tools is not None and (
        not isinstance(tools, list)
        or any(
            not isinstance(tool, dict)
            or set(tool) != {"fn", "cmd"}
            or not isinstance(tool["fn"], str)
            for tool in tools
        )
    ):
        raise ValueError(f"{where}: unexpected tools shape")


def step_facts(step: dict) -> dict:
    """Reduce one step to its facts, which are all that survives of its text."""
    tools = step["tools"]
    if tools:
        first = tools[0]
        category = tool_category(first["fn"], first["cmd"])
        digest = command_hash(first["cmd"])
    else:
        category, digest = "none", None
    return {
        "tool_category": category,
        "result_status": result_status(step["obs"]),
        "command_hash": digest,
    }


def run_steps(steps_json: str | None, where: str) -> list[dict]:
    """Step facts for the agent's own steps, since prompts and system text are not actions."""
    facts = []
    for step in (json.loads(steps_json) if steps_json else None) or []:
        check_step_format(step, where)
        if step["src"] == "agent":
            facts.append(step_facts(step))
    return facts


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_files(files: dict, recorded: dict) -> list[str]:
    """Names of recorded files whose checksum differs from the downloaded one, or that are missing."""
    return [
        name
        for name, entry in recorded.items()
        if files.get(name, {}).get("sha256") != entry["sha256"]
    ]


def select_combinations(combinations: list[dict], count: int = SELECTED) -> list[dict]:
    """Rank by tasks with mixed outcomes, then by trials, without reading any behaviour."""
    ranked = sorted(
        combinations,
        key=lambda c: (
            -c["mixed_tasks"],
            -c["trials_with_steps"],
            c["agent"],
            c["model"],
        ),
    )
    return ranked[:count]


def _spread(counts: list[int]) -> dict:
    return {
        "min": min(counts),
        "median": statistics.median(counts),
        "max": max(counts),
    }


def normalize(raw_dir: Path, runs_path: Path, steps_path: Path) -> dict:
    """Write the run and step tables from the raw files and return counts for the summary."""
    run_rows, step_rows = [], []
    trials_per_cell = collections.Counter()
    combo_trials = collections.Counter()
    combo_with_steps = collections.Counter()
    outcomes_per_cell = collections.defaultdict(set)
    for path in sorted(raw_dir.glob("data/*.parquet")):
        for batch in pq.ParquetFile(path).iter_batches(batch_size=500):
            for row in batch.to_pylist():
                combo = (row["agent"], row["model"])
                trials_per_cell[(row["task_name"], *combo)] += 1
                combo_trials[combo] += 1
                facts = run_steps(row["steps"], row["trial_id"])
                if not facts:
                    continue
                combo_with_steps[combo] += 1
                outcomes_per_cell[(row["task_name"], *combo)].add(row["reward"] == 1)
                run_rows.append(
                    {
                        "run_id": row["trial_id"],
                        "task_id": row["task_name"],
                        "source": "public",
                        "agent": row["agent"],
                        "model": row["model"],
                        "condition": None,
                        # Kept for the feasibility counts only, and never read by features or exported before the freeze.
                        "outcome": "pass" if row["reward"] == 1 else "fail",
                        "n_steps": len(facts),
                    }
                )
                step_rows.extend(
                    {"run_id": row["trial_id"], "step_idx": idx, **fact}
                    for idx, fact in enumerate(facts)
                )
    runs_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(run_rows), runs_path)
    pq.write_table(pa.Table.from_pylist(step_rows), steps_path)
    mixed_tasks = collections.Counter(
        (agent, model)
        for (_, agent, model), seen in outcomes_per_cell.items()
        if len(seen) == 2
    )
    return {
        "trials": sum(combo_trials.values()),
        "trials_with_steps": len(run_rows),
        "agent_steps": len(step_rows),
        "steps_without_readable_output": sum(
            1 for r in step_rows if r["result_status"] == "empty"
        ),
        "steps_without_command_hash": sum(
            1 for r in step_rows if r["command_hash"] is None
        ),
        "trials_per_task_and_combination": _spread(list(trials_per_cell.values())),
        "combinations": [
            {
                "agent": agent,
                "model": model,
                "trials": combo_trials[(agent, model)],
                "trials_with_steps": combo_with_steps[(agent, model)],
                "mixed_tasks": mixed_tasks[(agent, model)],
            }
            for agent, model in sorted(combo_trials)
        ],
    }


def run() -> None:
    # Read the pin before the summary is rewritten below.
    recorded = (
        json.loads(SUMMARY_PATH.read_text()).get("files", {})
        if SUMMARY_PATH.exists()
        else {}
    )
    raw_dir = download()
    files = {
        path.name: {"sha256": file_sha256(path), "bytes": path.stat().st_size}
        for path in sorted(raw_dir.glob("data/*.parquet"))
    }
    for name in verify_files(files, recorded):
        print(
            f"warning: {name} does not match the recorded checksum, continuing anyway",
            file=sys.stderr,
        )
    counts = normalize(raw_dir, RUNS_PATH, STEPS_PATH)
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(
        json.dumps(
            {
                "dataset": DATASET,
                "revision": REVISION,
                # The recorded checksum stays the reference, so a corrupted download cannot rewrite it.
                "files": {**files, **recorded},
                **counts,
                "selected": select_combinations(counts["combinations"]),
            },
            indent=2,
        )
        + "\n"
    )
