"""Custom shell tasks for the planted demo: setup, scripted checker and self-test."""

import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

TASKS_DIR = Path("tasks")

# A task script is a few shell commands, so a longer run means a hang.
SCRIPT_TIMEOUT_SECONDS = 60


@dataclass(frozen=True)
class Task:
    """One task directory: prompt.md, setup.sh, check.sh, solution.sh and optional files/."""

    task_id: str
    directory: Path

    @property
    def prompt(self) -> str:
        return (self.directory / "prompt.md").read_text()


@dataclass(frozen=True)
class SelfTestResult:
    task_id: str
    reference_passes: bool
    empty_fails: bool
    # What the checker said about the reference solution, shown when it does not pass.
    reference_detail: str

    @property
    def ok(self) -> bool:
        return self.reference_passes and self.empty_fails


def load_tasks(root: Path = TASKS_DIR) -> list[Task]:
    return [
        Task(path.name, path.resolve())
        for path in sorted(root.iterdir())
        if path.is_dir()
    ]


def run_script(task: Task, name: str, workdir: Path) -> subprocess.CompletedProcess:
    # The fixed locale keeps sort order and awk output the same on every host.
    return subprocess.run(
        ["bash", str(task.directory / name)],
        cwd=workdir,
        capture_output=True,
        text=True,
        timeout=SCRIPT_TIMEOUT_SECONDS,
        check=False,
        env={**os.environ, "LC_ALL": "C", "TASK_DIR": str(task.directory)},
    )


def prepare(task: Task, workdir: Path) -> None:
    result = run_script(task, "setup.sh", workdir)
    if result.returncode != 0:
        raise RuntimeError(f"setup failed for {task.task_id}: {result.stderr.strip()}")


def check(task: Task, workdir: Path) -> subprocess.CompletedProcess:
    return run_script(task, "check.sh", workdir)


def selftest(task: Task) -> SelfTestResult:
    """The reference solution must pass the checker, and an empty attempt must fail it."""
    with tempfile.TemporaryDirectory() as reference_dir:
        workdir = Path(reference_dir)
        prepare(task, workdir)
        solved = run_script(task, "solution.sh", workdir)
        verdict = check(task, workdir)
        detail = (solved.stderr + verdict.stdout + verdict.stderr).strip()
        reference_passes = solved.returncode == 0 and verdict.returncode == 0
    with tempfile.TemporaryDirectory() as empty_dir:
        workdir = Path(empty_dir)
        prepare(task, workdir)
        empty_fails = check(task, workdir).returncode != 0
    return SelfTestResult(task.task_id, reference_passes, empty_fails, detail)


def run() -> None:
    results = [selftest(task) for task in load_tasks()]
    for result in results:
        print(
            f"{result.task_id:<20} reference: {'pass' if result.reference_passes else 'FAIL'}"
            f"  empty: {'fail' if result.empty_fails else 'PASS'}"
            f"  {'ok' if result.ok else 'WRONG'}"
        )
        if not result.reference_passes:
            print(f"  {result.reference_detail}")
    good = sum(result.ok for result in results)
    print(f"{good} of {len(results)} tasks behave as expected")
    if good != len(results):
        raise SystemExit(1)
