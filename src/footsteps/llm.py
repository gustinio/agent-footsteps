"""The only code that calls a model for labeling: a pinned prompt, a cache by input, a token log and a cost check."""

import hashlib
import json
import subprocess
from pathlib import Path

from footsteps import runner

MODEL = "claude-haiku-4-5-20251001"
# Changing the prompt or the model changes every cache key, so old labels are never mixed with new ones.
PROMPT_VERSION = "intent-v1"
INTENTS = ("explore", "modify", "verify", "other")
SYSTEM_PROMPT = (
    "You label the steps of a coding agent working in a terminal. "
    "For each step you are given, choose the intent that best describes what the step does. "
    "explore: reads, lists, searches or inspects to learn about the task or the files. "
    "modify: creates, edits, deletes or runs something that changes files or state. "
    "verify: checks that something already done is right, by running a test or a check or by reading a result back. "
    "other: anything else, including a step with no action. "
    "The user message is a JSON list of steps, each with an index i, the tool, the command, the output and the agent's message. "
    'Reply with only a JSON list of objects like {"i": 0, "label": "explore"}, one per step, and nothing else.'
)

# The labeler takes what is left of the cap once the planted budget is set aside, and never spends the planted share.
RESERVE_USD = runner.TOTAL_CAP_USD - runner.PLANTED_BUDGET_USD
STAGE = "labeler"

CACHE_PATH = Path("data/label_cache.jsonl")


class BudgetUsedUp(Exception):
    """Raised before a call when no reserve is left, so the caller can stop and keep what it has."""


def remaining_budget(entries: list[dict]) -> float:
    """What the next call may spend: the tighter of the labeler reserve and the total cap."""
    return min(
        RESERVE_USD - runner.spent(entries, STAGE),
        runner.TOTAL_CAP_USD - runner.spent(entries),
    )


def request(batch: list[dict]) -> str:
    """The user message: the steps by index, and nothing about the run, the task or how it was made."""
    return json.dumps([{"i": i, **step} for i, step in enumerate(batch)])


def cache_key(batch: list[dict]) -> str:
    material = "\n".join((PROMPT_VERSION, MODEL, SYSTEM_PROMPT, request(batch)))
    return hashlib.sha256(material.encode()).hexdigest()


def read_cache(path: Path = CACHE_PATH) -> dict[str, list[str | None]]:
    if not path.exists():
        return {}
    entries = (json.loads(line) for line in path.read_text().splitlines() if line)
    return {entry["key"]: entry["labels"] for entry in entries}


def run_claude(prompt: str, budget: float) -> str:
    """The one place that calls the model, so tests replace it with a recorded transcript."""
    completed = subprocess.run(
        [
            "claude",
            "-p",
            prompt,
            "--model",
            MODEL,
            "--output-format",
            "stream-json",
            "--verbose",
            "--tools=",
            "--system-prompt",
            SYSTEM_PROMPT,
            "--no-session-persistence",
            "--max-budget-usd",
            f"{budget:.4f}",
        ],
        capture_output=True,
        text=True,
        timeout=runner.RUN_TIMEOUT_SECONDS,
        check=False,
    )
    return completed.stdout


def parse_labels(text: str, count: int) -> list[str | None]:
    """One label per step, or None where the reply is missing, repeated or not one of the four intents."""
    labels: list[str | None] = [None] * count
    try:
        replies = json.loads(text[text.index("[") : text.rindex("]") + 1])
    except ValueError:
        return labels
    for reply in replies if isinstance(replies, list) else []:
        if not isinstance(reply, dict):
            continue
        idx, label = reply.get("i"), reply.get("label")
        if (
            isinstance(idx, int)
            and 0 <= idx < count
            and labels[idx] is None
            and label in INTENTS
        ):
            labels[idx] = label
    return labels


def log_cost(key: str, result: dict, path: Path = runner.COST_LOG_PATH) -> dict:
    usage = result["usage"]
    entries = runner.read_cost_log(path)
    entry = {
        "stage": STAGE,
        "batch": key[:16],
        "model": MODEL,
        "input_tokens": usage["input_tokens"],
        "cache_creation_input_tokens": usage["cache_creation_input_tokens"],
        "cache_read_input_tokens": usage["cache_read_input_tokens"],
        "output_tokens": usage["output_tokens"],
        "cost_usd": result["total_cost_usd"],
        "spent_usd": round(runner.spent(entries, STAGE) + result["total_cost_usd"], 6),
        "budget_usd": RESERVE_USD,
        "cap_usd": runner.TOTAL_CAP_USD,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        handle.write(json.dumps(entry) + "\n")
    return entry


def classify(batch: list[dict]) -> list[str | None]:
    """Intent labels for a batch of steps, from the cache when the same batch was labeled before."""
    key = cache_key(batch)
    cached = read_cache()
    if key in cached:
        return cached[key]
    budget = remaining_budget(runner.read_cost_log())
    if budget <= 0:
        raise BudgetUsedUp
    transcript = run_claude(request(batch), budget)
    result = runner.final_result(transcript)
    entry = log_cost(key, result)
    print(
        f"labeler: ${entry['cost_usd']:.2f}, spent ${entry['spent_usd']:.2f} "
        f"of ${RESERVE_USD:.0f} reserve (${runner.TOTAL_CAP_USD:.0f} cap)"
    )
    if result.get("is_error") or result["subtype"] != "success":
        raise RuntimeError(f"the labeler call ended with {result['subtype']}")
    labels = parse_labels(result["result"], len(batch))
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CACHE_PATH.open("a") as handle:
        handle.write(json.dumps({"key": key, "labels": labels}) + "\n")
    return labels
