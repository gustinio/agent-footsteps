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
    assert main(["features"]) == 1
    assert "not implemented" in capsys.readouterr().err


def test_ingest_pilot_reduces_a_transcript_without_downloading(
    tmp_path, monkeypatch, capsys
):
    transcript = tmp_path / "run.jsonl"
    transcript.write_text(
        '{"type": "assistant", "message": {"id": "m", "content": [{"type": "text", "text": "done"}]}}\n'
    )
    monkeypatch.chdir(tmp_path)
    assert main(["ingest", "--pilot", str(transcript)]) == 0
    assert "run 0 none empty False" in capsys.readouterr().out
