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
PILOT_STEPS_PATH = Path("data/pilot_steps.parquet")
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
    "edit": "edit write write_file replace replace_file edit_file str_replace_editor notebookedit",
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

# A shell command verifies when it runs a test or checker, compares or checks
# something already made, or runs an inline script (a -c or -e flag, or a
# heredoc on stdin), which is how agents read a result back. It is a match on
# the command text, so a command that only mentions one of these words (for
# example in a file name) also counts.
_VERIFY = re.compile(
    r"\b(?:tests?|pytest|unittest|tox|diff|cmp|assert|verify|validate|check"
    r"|checksum|sha256sum|md5sum|lint|mypy|ruff)\b"
    r"|\b(?:python3?|node)\s+(?:-[ce]\b|-\s*<<)",
    re.IGNORECASE,
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


def _normalized_command(cmd) -> str | None:
    if _is_placeholder(cmd):
        return None
    text = " ".join(str(part) for part in cmd) if isinstance(cmd, list) else str(cmd)
    return " ".join(text.split()) or None


def command_hash(cmd) -> str | None:
    normalized = _normalized_command(cmd)
    if normalized is None:
        return None
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def verification_flag(category: str, cmd) -> bool:
    normalized = _normalized_command(cmd)
    return (
        category == "shell"
        and normalized is not None
        and _VERIFY.search(normalized) is not None
    )


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
        verifies = verification_flag(category, first["cmd"])
    else:
        category, digest, verifies = "none", None, False
    return {
        "tool_category": category,
        "result_status": result_status(step["obs"]),
        "command_hash": digest,
        "verification_flag": verifies,
    }


def run_steps(steps_json: str | None, where: str) -> list[dict]:
    """Step facts for the agent's own steps, since prompts and system text are not actions."""
    facts = []
    for step in (json.loads(steps_json) if steps_json else None) or []:
        check_step_format(step, where)
        if step["src"] == "agent":
            facts.append(step_facts(step))
    return facts


def raw_agent_steps(raw_dir: Path, wanted: set[str]) -> dict[str, list[dict]]:
    """The agent steps of the wanted public runs with their text, in the order the step table indexes them.

    Only the labeler reads this, for the few steps it shows a model or a person, and the text goes to
    nothing that is committed.
    """
    found = {}
    for path in sorted(raw_dir.glob("data/*.parquet")):
        for batch in pq.ParquetFile(path).iter_batches(batch_size=500):
            for row in batch.to_pylist():
                trial = run_id(row)
                if trial in wanted and row["steps"]:
                    found[trial] = [
                        step
                        for step in json.loads(row["steps"])
                        if step["src"] == "agent"
                    ]
    return found


def step_text(step: dict) -> dict:
    """What a reader needs to judge one step: the first tool call, its output and the agent's own message.

    A value the dataset replaced with a placeholder is blank, and long text is cut to keep a batch small.
    """
    tools = step["tools"]
    first = tools[0] if tools else None

    def readable(value, limit: int) -> str:
        if value is None or _is_placeholder(value):
            return ""
        return value[:limit]

    return {
        "tool": first["fn"] if first else "",
        "command": readable(first and _normalized_command(first["cmd"]), 600),
        "output": readable(step["obs"], 800),
        "message": readable(step["msg"], 600),
    }


def _pilot_command(tool_input: dict) -> str:
    """The text a Claude Code tool call acts on, as the public data's command field."""
    for key in ("command", "file_path", "pattern", "url", "query"):
        if isinstance(tool_input.get(key), str):
            return tool_input[key]
    return json.dumps(tool_input, sort_keys=True)


def _pilot_result_text(content) -> str:
    if isinstance(content, list):
        content = "".join(
            block.get("text", "") for block in content if isinstance(block, dict)
        )
    return content if isinstance(content, str) else ""


def pilot_steps(transcript: str, where: str) -> list[dict]:
    """Claude Code stream-json lines as agent steps in the public step format.

    The stream splits a message into a line per content block that all share
    the message id. Each tool call is its own step, because Claude Code issues
    parallel calls in one message and each is a separate action, so a repeated
    command stays visible. A message without a tool call is one step.
    """
    messages: dict[str, dict] = {}
    results: dict[str, str] = {}
    for line in transcript.splitlines():
        event = json.loads(line)
        if event.get("type") == "assistant":
            message = event["message"]
            entry = messages.setdefault(message["id"], {"text": "", "tools": []})
            for block in message["content"]:
                if block["type"] == "text":
                    entry["text"] += block["text"]
                elif block["type"] == "tool_use":
                    entry["tools"].append(block)
        elif event.get("type") == "user":
            content = event["message"]["content"]
            for block in content if isinstance(content, list) else []:
                if block.get("type") == "tool_result":
                    results[block["tool_use_id"]] = _pilot_result_text(
                        block.get("content")
                    )
    steps = []
    for entry in messages.values():
        calls = entry["tools"] or [None]
        for position, block in enumerate(calls):
            obs = results.get(block["id"]) if block else None
            steps.append(
                {
                    "src": "agent",
                    "msg": entry["text"] if position == 0 else "",
                    "tools": (
                        [{"fn": block["name"], "cmd": _pilot_command(block["input"])}]
                        if block
                        else None
                    ),
                    # Cut to the public data's limit so both sources see the same output head.
                    "obs": obs[:OBS_LIMIT] if obs else obs,
                }
            )
    for step in steps:
        check_step_format(step, where)
    return steps


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


def run_id(row: dict) -> str:
    """The dataset's trial id, or a stable stand-in when it is blank.

    The pinned revision leaves the trial id empty on most rows, and every such row would then share one run.
    The agent, model, trial name and start time are unique across the pinned revision's rows.
    """
    if row["trial_id"]:
        return row["trial_id"]
    key = "|".join(
        str(row.get(field)) for field in ("agent", "model", "trial_name", "started_at")
    )
    return hashlib.sha256(key.encode()).hexdigest()[:36]


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
                trial = run_id(row)
                facts = run_steps(row["steps"], trial)
                if not facts:
                    continue
                combo_with_steps[combo] += 1
                outcomes_per_cell[(row["task_name"], *combo)].add(row["reward"] == 1)
                run_rows.append(
                    {
                        "run_id": trial,
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
                    {"run_id": trial, "step_idx": idx, **fact}
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


def run_pilot(paths: list[Path]) -> None:
    """Reduce Claude Code transcripts to step facts and print the step table.

    Pilot runs only test the pipeline, so they go to their own table and never
    into the public tables or the summary.
    """
    rows = []
    for path in paths:
        for idx, step in enumerate(pilot_steps(path.read_text(), path.name)):
            rows.append({"run_id": path.stem, "step_idx": idx, **step_facts(step)})
    PILOT_STEPS_PATH.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows), PILOT_STEPS_PATH)
    print("run_id step tool_category result_status verification_flag")
    for row in rows:
        print(
            f"{row['run_id']} {row['step_idx']} {row['tool_category']} "
            f"{row['result_status']} {row['verification_flag']}"
        )


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
