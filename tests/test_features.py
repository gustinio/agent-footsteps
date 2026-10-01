import pytest

from footsteps import features


def step(category="shell", status="ok", digest=None, verify=False):
    return {
        "tool_category": category,
        "result_status": status,
        "command_hash": digest,
        "verification_flag": verify,
    }


def named(vector):
    return dict(zip(features.FEATURE_NAMES, vector))


def test_vectors_follow_the_feature_names():
    vectors = features.step_features([step(), step("read")])
    assert len(vectors) == 2
    assert all(len(v) == len(features.FEATURE_NAMES) for v in vectors)


def test_a_step_is_described_by_its_tool_result_and_checks():
    first = named(features.step_features([step("edit", "error", "a", True)])[0])
    assert first["tool_edit"] == 1 and first["tool_shell"] == 0
    assert first["error"] == 1 and first["empty"] == 0
    assert first["verify"] == 1
    assert first["switched_tool"] == 0 and first["prev_verify"] == 0


def test_repeat_flag_marks_a_command_run_before():
    rows = features.step_features(
        [step(digest="a"), step(digest="b"), step(digest="a")]
    )
    assert [named(r)["repeat"] for r in rows] == [0, 0, 1]


def test_recent_errors_count_only_the_window_of_earlier_steps():
    steps = [step(status="error")] * 5 + [step()]
    shares = [named(v)["recent_errors"] for v in features.step_features(steps)]
    assert shares[0] == 0
    assert shares[1] == pytest.approx(1 / features.ERROR_WINDOW)
    assert shares[4] == 1
    assert shares[5] == 1


def test_neighbour_features_look_back_and_never_ahead():
    steps = [step(verify=True), step("read"), step("read"), step("edit", "error")]
    whole = features.step_features(steps)
    for k in range(1, len(steps) + 1):
        assert features.step_features(steps[:k]) == whole[:k]
    assert named(whole[1])["prev_verify"] == 1
    assert named(whole[1])["switched_tool"] == 1
    assert named(whole[2])["switched_tool"] == 0
