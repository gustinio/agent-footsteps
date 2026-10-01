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
