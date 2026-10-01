"""Sequence features computed from step facts only."""


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
