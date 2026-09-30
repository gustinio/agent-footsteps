import pytest

from footsteps.cli import STAGES, build_parser, main


def test_help_lists_every_stage(capsys):
    with pytest.raises(SystemExit) as exit_info:
        build_parser().parse_args(["--help"])
    assert exit_info.value.code == 0
    help_text = capsys.readouterr().out
    for stage in STAGES:
        assert stage in help_text


def test_unbuilt_stage_fails_loudly(capsys):
    assert main(["ingest"]) == 1
    assert "not implemented" in capsys.readouterr().err
