# ADR-0004: Combine Public Runs with a Small Planted Demo

## Status

Accepted

## Context

The project needs natural runs with pass and fail outcomes, and it needs a control in which a behaviour is planted on purpose.
Generating every run would cost too much, and the author wants no out-of-pocket spend beyond an existing subscription.
Public Terminal-Bench trajectories are free, but they were not produced under controlled instructions.

## Decision

Natural behaviour comes from public Terminal-Bench trajectories, restricted by a written rule to the one or two model and scaffold combinations with the most mixed-outcome tasks.
The planted demo uses Claude Code non-interactively on the author's personal Pro plan, with `--append-system-prompt` planting a "verify everything" instruction in three conditions: none, gentle and strong.
The demo has 10 pre-set tasks and 2 seeds per condition, giving up to 60 runs, and shrinks to 48 or 32 based on the measured cost per run.
The hard cap is the plan's monthly credit, which is quoted at $20 from an unverified source and must be confirmed on the plan page, and every run is logged with its tokens.
The runs use the personal login and never the work account.
A first spike verifies that Claude Code can drive the benchmark tasks, and otherwise 10 custom shell tasks with scripted checkers replace them.

Update 2026-10-01: the spike showed that Claude Code drives the longer benchmark tasks, but scoring them with their own tests needs a real `/app` that the host does not provide, and only three of them were shown to run. The demo therefore uses 10 custom tasks, and the public benchmark tasks stay in the natural arm only.

Update 2026-10-01 (freeze): verification could not be planted in the pilots, so the planted behaviour is repeating a shell command, with the rule "run every shell command twice in a row, with the identical command both times". The gentle dose had no effect and is cut, so the demo has two conditions, none and strong, and 40 runs. The instruction is given in a replaced system prompt and not through `--append-system-prompt`. The exact prompts and the Q2 wording are in the PRD freeze note.

## Consequences

- Planting a known behaviour is the only way to test whether a behaviour name is correct, and it is the part not found in prior work.
- With about 10 tasks the result is an existence check, and the dose trend is exploratory.
- Claude Code adds its own system prompt and tools, so the planted runs and the public runs come from different scaffolds and need a shared feature schema.

## Alternatives

- **Generating all runs:** Rejected because it costs too much.
- **Public data only:** Rejected as the default because it drops the planted-behaviour control, though it remains the fallback if the credit cannot support the demo.
- **OpenRouter with a cheap model:** Rejected because the author prefers not to spend money, though it stays an option if a paid budget is chosen later.
