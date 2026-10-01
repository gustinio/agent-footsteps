"""Run the planted demo through Claude Code and reduce each transcript to step facts."""

import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from footsteps import ingest, tasks

MODEL = "claude-sonnet-5"
TOOLS = ("Bash", "Read", "Write", "Edit", "Glob", "Grep")
BASE_PROMPT = (
    "You are a coding agent working in a terminal. "
    "Complete the task the user gives you."
)
STEERING = {
    "none": "",
    "strong": (
        "Run every shell command twice in a row, with the identical command both times, "
        "and compare the two outputs before moving on."
    ),
}
CONDITIONS = tuple(STEERING)
SEEDS = (1, 2)

# The plan has no dollar credit, so the cap is a list price total taken from the cost
# that Claude Code reports. The planted runs are budgeted first and the rest is left
# for the labeler.
TOTAL_CAP_USD = 40.0
PLANTED_BUDGET_USD = 12.0
STAGE = "runner"

# A single run of about ten steps takes under a minute, so a longer one is stuck.
RUN_TIMEOUT_SECONDS = 900

TRANSCRIPT_DIR = Path("data/planted")
PLANTED_RUNS_PATH = Path("results/planted_runs.parquet")
PLANTED_STEPS_PATH = Path("results/planted_steps.parquet")
COST_LOG_PATH = Path("results/cost_log.jsonl")

AGENT = "claude-code"


@dataclass(frozen=True)
class PlannedRun:
    task: tasks.Task
    seed: int
    condition: str

    @property
    def run_id(self) -> str:
        return f"{self.task.task_id}-s{self.seed}-{self.condition}"


def plan(task_list: list[tasks.Task]) -> list[PlannedRun]:
    """Run order is task, then seed, then condition, so each task finishes before the next starts."""
    return [
        PlannedRun(task, seed, condition)
        for task in task_list
        for seed in SEEDS
        for condition in CONDITIONS
    ]


def system_prompt(condition: str) -> str:
    return " ".join(part for part in (BASE_PROMPT, STEERING[condition]) if part)


def read_cost_log(path: Path = COST_LOG_PATH) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def spent(entries: list[dict], stage: str | None = None) -> float:
    return sum(
        entry["cost_usd"] for entry in entries if stage in (None, entry["stage"])
    )


def remaining_budget(entries: list[dict]) -> float:
    """What the next run may spend: the tighter of the planted budget and the total cap."""
    return min(
        PLANTED_BUDGET_USD - spent(entries, STAGE), TOTAL_CAP_USD - spent(entries)
    )


def log_cost(run: PlannedRun, result: dict, path: Path = COST_LOG_PATH) -> dict:
    usage = result["usage"]
    entries = read_cost_log(path)
    entry = {
        "stage": STAGE,
        "run_id": run.run_id,
        "model": MODEL,
        "input_tokens": usage["input_tokens"],
        "cache_creation_input_tokens": usage["cache_creation_input_tokens"],
        "cache_read_input_tokens": usage["cache_read_input_tokens"],
        "output_tokens": usage["output_tokens"],
        "cost_usd": result["total_cost_usd"],
        "spent_usd": round(spent(entries, STAGE) + result["total_cost_usd"], 6),
        "budget_usd": PLANTED_BUDGET_USD,
        "cap_usd": TOTAL_CAP_USD,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        handle.write(json.dumps(entry) + "\n")
    return entry


def claude_command(run: PlannedRun, budget: float) -> list[str]:
    return [
        "claude",
        "-p",
        run.task.prompt,
        "--model",
        MODEL,
        "--output-format",
        "stream-json",
        "--verbose",
        "--tools",
        ",".join(TOOLS),
        "--allowedTools",
        ",".join(TOOLS),
        "--permission-mode",
        "dontAsk",
        "--system-prompt",
        system_prompt(run.condition),
        "--no-session-persistence",
        "--max-budget-usd",
        f"{budget:.4f}",
    ]


def check_login() -> None:
    """Planted runs use the personal Pro login and never a work account."""
    status = json.loads(
        subprocess.run(
            ["claude", "auth", "status"], capture_output=True, text=True, check=True
        ).stdout
    )
    if (
        status.get("subscriptionType") != "pro"
        or status.get("authMethod") != "claude.ai"
    ):
        raise SystemExit(
            "runner: Claude Code is not logged in with the personal Pro plan, so no run was made"
        )


def run_claude(run: PlannedRun, workdir: Path, budget: float) -> str:
    """The one place that calls the model, so tests replace it with a recorded transcript."""
    completed = subprocess.run(
        claude_command(run, budget),
        cwd=workdir,
        capture_output=True,
        text=True,
        timeout=RUN_TIMEOUT_SECONDS,
        check=False,
    )
    return completed.stdout


def final_result(transcript: str) -> dict:
    for line in reversed(transcript.splitlines()):
        event = json.loads(line)
        if event.get("type") == "result":
            return event
    raise RuntimeError("the transcript has no result line, so its cost is unknown")


def read_table(path: Path) -> list[dict]:
    return pq.read_table(path).to_pylist() if path.exists() else []


def completed_run_ids() -> set[str]:
    return {row["run_id"] for row in read_table(PLANTED_RUNS_PATH)}


def record_run(run: PlannedRun, outcome: str, facts: list[dict]) -> None:
    """Add one finished run to the committed tables, which hold step facts and no text."""
    run_rows = read_table(PLANTED_RUNS_PATH) + [
        {
            "run_id": run.run_id,
            "task_id": run.task.task_id,
            "source": "planted",
            "agent": AGENT,
            "model": MODEL,
            "seed": run.seed,
            "condition": run.condition,
            "outcome": outcome,
            "n_steps": len(facts),
        }
    ]
    step_rows = read_table(PLANTED_STEPS_PATH) + [
        {"run_id": run.run_id, "step_idx": idx, **fact}
        for idx, fact in enumerate(facts)
    ]
    PLANTED_RUNS_PATH.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(run_rows), PLANTED_RUNS_PATH)
    pq.write_table(pa.Table.from_pylist(step_rows), PLANTED_STEPS_PATH)


def execute(run: PlannedRun, budget: float) -> bool:
    """Make one run in a throwaway directory. Returns False when the run did not finish."""
    with tempfile.TemporaryDirectory() as directory:
        workdir = Path(directory)
        tasks.prepare(run.task, workdir)
        transcript = run_claude(run, workdir, budget)
        TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
        (TRANSCRIPT_DIR / f"{run.run_id}.jsonl").write_text(transcript)
        result = final_result(transcript)
        entry = log_cost(run, result)
        print(
            f"{run.run_id}: ${entry['cost_usd']:.2f}, spent ${entry['spent_usd']:.2f} "
            f"of ${PLANTED_BUDGET_USD:.0f} planted budget (${TOTAL_CAP_USD:.0f} cap)"
        )
        if result.get("is_error") or result["subtype"] != "success":
            print(
                f"{run.run_id}: ended with {result['subtype']}, not recorded",
                flush=True,
            )
            return False
        facts = [
            ingest.step_facts(step)
            for step in ingest.pilot_steps(transcript, run.run_id)
        ]
        verdict = tasks.check(run.task, workdir)
        record_run(run, "pass" if verdict.returncode == 0 else "fail", facts)
        return True


def run(task_limit: int | None = None) -> None:
    """Make the planned runs that are not yet recorded, stopping when the budget is used.

    The runner never looks at what the runs did, so the interim stop rule is applied
    between invocations by reading the evaluator's table, and task_limit is how an
    invocation stops after the first few tasks.
    """
    check_login()
    planned = plan(tasks.load_tasks()[:task_limit])
    done = completed_run_ids()
    for planned_run in planned:
        if planned_run.run_id in done:
            continue
        budget = remaining_budget(read_cost_log())
        if budget <= 0:
            print("runner: the budget is used up, stopping before the next run")
            raise SystemExit(1)
        execute(planned_run, budget)
    print(f"runner: {len(completed_run_ids())} of {len(planned)} planned runs recorded")
