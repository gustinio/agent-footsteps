# Feasibility Spike

Results of the phase 2 spike, recorded as each part finishes.
See [PLAN.md](PLAN.md#2-feasibility-spike) for the parts and [PRD.md](PRD.md) for the selection rule.

## Public Data: Combinations

Counts come from `results/dataset_summary.json`, which `make reproduce` regenerates from the pinned revision with no model calls.
A task is mixed for a combination when at least one of its trials with steps passed and at least one failed.
Only trials with at least one agent step are counted, because those are the runs the natural arm can use.
No behaviour result was read to make this choice.

The selection rule ranks the 109 model and scaffold combinations by mixed tasks, breaking ties by trials with steps.
The PRD allows one or two combinations, and this spike takes the top two to keep more public runs for the natural arm.

| Rank | Scaffold | Model | Mixed tasks | Trials with steps |
| --- | --- | --- | --- | --- |
| 1 | terminus-2 | gpt-5.1-codex@openai | 44 | 432 |
| 2 | terminus-2 | gemini-3-flash-preview@gemini | 39 | 444 |
| 3 | terminus-2 | gemini-2.5-pro@gemini | 38 | 441 |
| 4 | terminus-2 | gpt-5-codex@openai | 37 | 435 |
| 5 | terminus-2 | moonshotai/Kimi-K2-Thinking@together_ai | 36 | 892 |

**Chosen:** terminus-2 with gpt-5.1-codex@openai, and terminus-2 with gemini-3-flash-preview@gemini.
The minimum numbers of mixed tasks and runs for the viability gate are written at the freeze, from these counts.

## Download Integrity

`make reproduce` compares each downloaded file with the checksum recorded in `results/dataset_summary.json`.
On a mismatch it prints a warning naming the file and continues, and the recorded checksum is kept as the reference.
