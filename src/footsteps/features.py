"""Sequence features computed from step facts only."""

import collections
import itertools


def repeat_flags(steps: list[dict]) -> list[bool]:
    """Per step, whether it is a shell command already run earlier in the same run.

    Steps must be in run order. A step without a readable command has no hash and never repeats.
    """
    seen: set[str] = set()
    flags = []
    for step in steps:
        digest = step["command_hash"]
        is_shell = step["tool_category"] == "shell" and digest is not None
        flags.append(is_shell and digest in seen)
        if is_shell:
            seen.add(digest)
    return flags


CATEGORIES = (
    "shell",
    "read",
    "search",
    "edit",
    "plan",
    "web",
    "finish",
    "other",
    "none",
)

# How many earlier steps count as the recent error history.
ERROR_WINDOW = 3

FEATURE_NAMES = (
    *(f"tool_{category}" for category in CATEGORIES),
    "error",
    "empty",
    "verify",
    "repeat",
    "recent_errors",
    "prev_verify",
    "switched_tool",
)


def step_features(steps: list[dict]) -> list[list[float]]:
    """One vector per step, in the order of FEATURE_NAMES, from the step facts only.

    Steps must be in run order. Only earlier steps are used as neighbours, so a prefix of a run
    gets the same vectors as the same steps inside the whole run.
    """
    repeats = repeat_flags(steps)
    vectors = []
    for idx, (step, repeated) in enumerate(zip(steps, repeats)):
        recent = steps[max(0, idx - ERROR_WINDOW) : idx]
        previous = steps[idx - 1] if idx else None
        vectors.append(
            [
                *(float(step["tool_category"] == name) for name in CATEGORIES),
                float(step["result_status"] == "error"),
                float(step["result_status"] == "empty"),
                float(bool(step["verification_flag"])),
                float(repeated),
                sum(s["result_status"] == "error" for s in recent) / ERROR_WINDOW,
                float(bool(previous and previous["verification_flag"])),
                float(
                    previous is not None
                    and previous["tool_category"] != step["tool_category"]
                ),
            ]
        )
    return vectors


RESULT_STATUSES = ("ok", "error", "empty")

WINDOW_COUNT_NAMES = (
    *(f"count_{category}" for category in CATEGORIES),
    *(f"count_{status}" for status in RESULT_STATUSES),
    "count_verify",
    "count_repeat",
)


def window_counts(steps: list[dict]) -> list[float]:
    """Counts of every tool category and result status, and of the verification and repeat facts, in the given steps.

    This is the supervised predictor's view of a window: it holds no discovered state.
    """
    return [
        *(sum(s["tool_category"] == name for s in steps) for name in CATEGORIES),
        *(sum(s["result_status"] == name for s in steps) for name in RESULT_STATUSES),
        sum(bool(s["verification_flag"]) for s in steps),
        sum(repeat_flags(steps)),
    ]


# A run is read in this many equal parts for its trajectory.
PROFILE_PARTS = 3


def run_profile(states: list[int], n_states: int) -> tuple[list[float], list[float]]:
    """The behaviour view of a finished run, from its step states in order.

    The first list is the share of steps in each state within each third of the run (state-major
    within a third), followed by the number of switches between states. The second list is the
    number of times each ordered pair of different states occurs one after the other, divided by
    the steps that could start a switch, so that long runs do not look more switchy for being long.
    An empty third has no steps and so a share of zero.
    """
    n = len(states)
    shares = []
    for part in range(PROFILE_PARTS):
        inside = [s for idx, s in enumerate(states) if idx * PROFILE_PARTS // n == part]
        shares.extend(
            inside.count(state) / len(inside) if inside else 0.0
            for state in range(n_states)
        )
    pairs = collections.Counter(itertools.pairwise(states))
    switches = sum(count for (a, b), count in pairs.items() if a != b)
    moves = [
        pairs[(a, b)] / max(n - 1, 1)
        for a in range(n_states)
        for b in range(n_states)
        if a != b
    ]
    return [*shares, float(switches)], moves


def profile_names(n_states: int) -> list[str]:
    """Names of the entries of the first list from run_profile, 1-based states to match the site."""
    parts = ("first third", "middle third", "last third")
    return [
        f"state {state + 1} share, {part}"
        for part in parts
        for state in range(n_states)
    ] + ["switches"]


def move_names(n_states: int) -> list[str]:
    """Names of the entries of the second list from run_profile."""
    return [
        f"{a + 1} to {b + 1}"
        for a in range(n_states)
        for b in range(n_states)
        if a != b
    ]
