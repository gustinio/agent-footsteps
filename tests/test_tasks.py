from pathlib import Path

import pytest

from footsteps import tasks
from footsteps.cli import main

REPO_TASKS = Path(__file__).parent.parent / "tasks"


def write_task(
    root: Path, name: str, setup: str, solution: str, check: str
) -> tasks.Task:
    directory = root / name
    directory.mkdir(parents=True)
    (directory / "prompt.md").write_text("Do the thing.\n")
    (directory / "setup.sh").write_text(setup)
    (directory / "solution.sh").write_text(solution)
    (directory / "check.sh").write_text(check)
    return tasks.Task(name, directory)


def test_every_demo_task_has_all_its_parts_and_behaves_as_expected():
    found = tasks.load_tasks(REPO_TASKS)
    assert len(found) == 10
    for task in found:
        for part in ("prompt.md", "setup.sh", "solution.sh", "check.sh"):
            assert (task.directory / part).is_file(), f"{task.task_id} lacks {part}"
        assert task.prompt.strip()
        result = tasks.selftest(task)
        assert result.ok, f"{task.task_id}: {result.reference_detail}"


def test_selftest_accepts_a_task_whose_checker_separates_solved_from_empty(tmp_path):
    task = write_task(
        tmp_path, "good", "true\n", "echo done > out.txt\n", "test -s out.txt\n"
    )
    result = tasks.selftest(task)
    assert result.reference_passes and result.empty_fails and result.ok


def test_selftest_flags_a_checker_that_passes_an_empty_attempt(tmp_path):
    task = write_task(tmp_path, "lenient", "true\n", "true\n", "true\n")
    result = tasks.selftest(task)
    assert result.reference_passes
    assert not result.empty_fails
    assert not result.ok


def test_selftest_flags_a_solution_the_checker_rejects_and_shows_why(tmp_path):
    task = write_task(
        tmp_path,
        "strict",
        "true\n",
        "echo wrong > out.txt\n",
        'test "$(cat out.txt 2>/dev/null)" = right || { echo "out.txt is wrong"; exit 1; }\n',
    )
    result = tasks.selftest(task)
    assert not result.reference_passes
    assert result.empty_fails
    assert "out.txt is wrong" in result.reference_detail


def test_a_failing_setup_is_an_error_not_a_pass(tmp_path):
    task = write_task(tmp_path, "broken", "exit 3\n", "true\n", "true\n")
    with pytest.raises(RuntimeError, match="setup failed for broken"):
        tasks.selftest(task)


def test_scripts_see_the_task_directory_and_a_fixed_locale(tmp_path):
    task = write_task(
        tmp_path,
        "env",
        'cp "$TASK_DIR/prompt.md" copied.md\n',
        'echo "$LC_ALL" > locale.txt\n',
        'test "$(cat locale.txt)" = C\n',
    )
    assert tasks.selftest(task).ok


def test_tasks_command_exits_nonzero_when_a_task_misbehaves(
    tmp_path, monkeypatch, capsys
):
    write_task(tmp_path, "lenient", "true\n", "true\n", "true\n")
    original = tasks.load_tasks
    monkeypatch.setattr(tasks, "load_tasks", lambda: original(tmp_path))
    with pytest.raises(SystemExit) as exit_info:
        tasks.run()
    assert exit_info.value.code == 1
    output = capsys.readouterr().out
    assert "lenient" in output and "WRONG" in output
    assert "0 of 1 tasks behave as expected" in output


def test_tasks_command_reports_all_demo_tasks_ok(monkeypatch, capsys):
    monkeypatch.chdir(REPO_TASKS.parent)
    assert main(["tasks"]) == 0
    assert "10 of 10 tasks behave as expected" in capsys.readouterr().out
