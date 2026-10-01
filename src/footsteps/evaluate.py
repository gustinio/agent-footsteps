"""The pre-registered tests, with every threshold in one place."""

import collections

from footsteps import features, runner, tasks

# From the PRD's Q2 manipulation check: the repeat share must be higher with the
# instruction than without it on this many of the ten tasks, and the interim rule
# stops the runs if it rose on fewer than the interim minimum of the first three.
INTERIM_TASKS = 3
INTERIM_MIN_RISES = 2
FINAL_MIN_RISES = 8


def repeat_counts(runs: list[dict], steps: list[dict]) -> dict:
    """Per task and condition, the shell steps and how many of them repeat an earlier command."""
    steps_by_run = collections.defaultdict(list)
    for step in sorted(steps, key=lambda s: (s["run_id"], s["step_idx"])):
        steps_by_run[step["run_id"]].append(step)
    counts: dict = collections.defaultdict(lambda: [0, 0])
    for row in runs:
        run_steps = steps_by_run[row["run_id"]]
        cell = counts[(row["task_id"], row["condition"])]
        cell[0] += sum(
            flag and step["tool_category"] == "shell"
            for flag, step in zip(features.repeat_flags(run_steps), run_steps)
        )
        cell[1] += sum(step["tool_category"] == "shell" for step in run_steps)
    return counts


def manipulation_table(
    runs: list[dict], steps: list[dict], task_order: list[str]
) -> list[dict]:
    """One row per task that has both conditions, in run order."""
    counts = repeat_counts(runs, steps)
    table = []
    for task_id in task_order:
        if (task_id, "none") not in counts or (task_id, "strong") not in counts:
            continue
        shares = {
            condition: counts[(task_id, condition)][0]
            / max(counts[(task_id, condition)][1], 1)
            for condition in runner.CONDITIONS
        }
        table.append(
            {"task_id": task_id, **shares, "rose": shares["strong"] > shares["none"]}
        )
    return table


def interim_verdict(table: list[dict], task_order: list[str]) -> str:
    """continue, stop or pending, after the first tasks in run order."""
    first = set(task_order[:INTERIM_TASKS])
    judged = [row for row in table if row["task_id"] in first]
    if len(judged) < min(INTERIM_TASKS, len(task_order)):
        return "pending"
    rises = sum(row["rose"] for row in judged)
    return "continue" if rises >= INTERIM_MIN_RISES else "stop"


def run() -> None:
    task_order = [task.task_id for task in tasks.load_tasks()]
    table = manipulation_table(
        runner.read_table(runner.PLANTED_RUNS_PATH),
        runner.read_table(runner.PLANTED_STEPS_PATH),
        task_order,
    )
    print("task  share of shell steps that repeat an earlier command")
    for row in table:
        print(
            f"{row['task_id']:<20} none {row['none']:.0%}  strong {row['strong']:.0%}"
            f"  {'rose' if row['rose'] else 'did not rise'}"
        )
    verdict = interim_verdict(table, task_order)
    print(f"interim rule after {INTERIM_TASKS} tasks: {verdict}")
    if len(table) == len(task_order):
        rises = sum(row["rose"] for row in table)
        print(
            f"manipulation check: rose on {rises} of {len(table)} tasks, needs {FINAL_MIN_RISES}"
            f" ({'passes' if rises >= FINAL_MIN_RISES else 'fails'})"
        )
