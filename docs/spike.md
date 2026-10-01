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

## Plan and Cap

`claude auth status` shows a claude.ai login with the Pro subscription, and the author confirmed it is the personal plan and not a work account.
The plan has no dollar credit: the usage page shows 0 dollars of credit and only rolling allowances, a 5 hour limit and a weekly limit.
The dollar cap in the PRD therefore does not exist as written.
The runner and the labeler cannot stop on a dollar balance, so they stop on the `total_cost_usd` that Claude Code reports for each call, which is a list price estimate and not a charge.
The author read the limits at three points while the runs were made:

| Reading | List price spent so far | 5 hour limit | Weekly limit |
| --- | --- | --- | --- |
| Before any run | $0 | 22% | 3% |
| After the first two pilots | $4.81 | 42% | 6% |
| After the next three pilots | $15.26 | not read | 8% |

That is about 0.3 of a weekly point per list-price dollar, and about 4 points of the 5 hour limit per dollar over the first $4.81.
A demo of $9 to $14 would therefore use roughly 3 to 5 weekly points and span one or two 5 hour windows.
The percentages are whole numbers and the author's other Claude Code use draws on the same limits, so these ratios are rough.
The cap to write into the PRD at the freeze is a list price total, with $20 kept as the working figure and the allowance readings above as its justification.

## Labeler Route

The default route works: `claude -p --output-format json` reports `usage` with input, cache and output token counts and `total_cost_usd` for each call, and `--output-format stream-json` reports the same in its final `result` line.
One call with a one-word reply on `--model haiku` cost $0.013 at list price, because Claude Code sends about 10,000 tokens of system prompt and tool text with every call.
With the tool list disabled (`--tools=""`) the cost is still dominated by that overhead, so the labeler should batch many steps into each call and read the cost from the JSON instead of estimating from text length.
No estimate with a safety margin is needed.

## Claude Code Runs

All runs were non-interactive `claude -p --output-format stream-json --verbose` calls with the tools limited to Bash, Read, Write, Edit, Glob and Grep, in a throwaway directory, on `claude-sonnet-5` unless stated.
The tasks come from the Terminal-Bench repository with `/app` rewritten to the throwaway directory, so that no container is needed.
The runs also loaded the author's user-level instructions and settings, which cannot be switched off without losing the login, so the planted runs carry that extra context.

The first pilot used two short tasks, `analyze-access-logs` and `bank-trans-filter`.
The later pilots used three tasks chosen because agents took 10 or more steps on them in the public data: `git-leak-recovery`, `merge-diff-arc-agi-task` and `vulnerable-secret`.
Tasks were chosen from the public step counts only, and `fix-git` was dropped because the GitHub repository its setup clones no longer exists.
Every run ended with the agent finishing the task.
The only test failures were two harness artifacts: `git-leak-recovery` checks a repository checksum that hashes full file paths, so it cannot match outside `/app`, and `merge-diff-arc-agi-task` reads a hidden file from `/tests`, which the path rewrite also had to cover.
A runner that scores these tasks with their own tests unchanged therefore needs a real `/app`, for example through a container or a mount namespace.

| Task | Agent steps per run | List price per run |
| --- | --- | --- |
| `analyze-access-logs` | 3 to 5 | $0.08 to $0.22 |
| `bank-trans-filter` | 5 to 6 | $0.23 to $0.26 |
| `git-leak-recovery` | 7 to 8 | $0.14 to $0.16 |
| `merge-diff-arc-agi-task` | 9 to 11 | $0.24 to $0.32 |
| `vulnerable-secret` | 7 to 12 | $0.17 to $0.31 |

The two short tasks averaged $0.17 per run and the three longer ones $0.22.
The longer tasks averaged 9.1 agent steps per run, where the plan wants about 10.

## Tool Mapping

Every tool the runs used maps to a public category with the existing rules: Bash to shell, Read to read, Write and Edit to edit, Glob and Grep to search.
Tools the runs did not use follow the same rules: TodoWrite to plan, WebFetch and WebSearch to web, and NotebookEdit to edit, which was added.
The other Claude Code tools, such as Task, ToolSearch and the scheduling and document tools, have no public counterpart and fall into other.
The transcript has no finish tool, so the final message is a step with no tool call and the category none.
Claude Code can issue several tool calls in one message, so the pilot reader makes each tool call its own step, where the public data's first-call rule would hide a repeated command.

## Verification Flag

The flag is true for a shell step whose command contains a test or check word, or runs an inline script through `python -c`, `node -e` or a `python -` heredoc.
Each widening came from reading pilot transcripts in which an agent read a result back with an inline script that the earlier rule missed.
Tuning the rule on pilot runs is allowed because they are excluded from all analysis, but the rule must be frozen before any planted run.
The flag marks 8.1% of all public steps and 11.8% of public shell steps.

## Planting Verification

The first pilot gave the agent the instruction "Before you finish, and after every change, verify your work by running a check or test and inspecting the result. Never assume a step worked." and compared 5 runs with it to 5 runs without, on two short tasks.

| Task | Runs per condition | No instruction | Strong instruction |
| --- | --- | --- | --- |
| `analyze-access-logs` | 3 | 1 of 12 steps flagged | 0 of 14 steps flagged |
| `bank-trans-filter` | 2 | 0 of 10 steps flagged | 2 of 12 steps flagged |

The flag rose on one of the two tasks.
On `bank-trans-filter` both strong runs ended with a script that read the output file back, and on `analyze-access-logs` the agent ignored the instruction.
The PRD check needs a rise on at least 8 of 10 tasks.

Three further attempts on the longer tasks, each changing the setup, did not help:

| Attempt | Change | Flag share without | Flag share with |
| --- | --- | --- | --- |
| Longer tasks | Same wording, three tasks with 10 or more steps | 24% | 24% |
| Replaced prompt | Claude Code's system prompt replaced by one sentence, stronger wording | 20% | 19% |
| Smaller model | Same as the previous attempt on `claude-haiku-4-5` | 15% | 14% |

Verification is a poor behaviour to plant, because Claude already verifies about one step in five without being told and does not do more when asked.
Replacing the system prompt did not remove the competing context: the first call still carried about 34,000 input tokens against 42,000 before, because tool definitions and the author's user-level instructions remain.

## Planting Repeating

A look at the 20 no-instruction Sonnet runs found much lower natural rates for two other behaviours: repeating a command (0 of 176 steps) and using the Read, Grep or Glob tools (about 5% of tool calls).
The next two pilots gave each its own mechanical instruction, a rule that can be followed step by step and not a disposition, on the three longer tasks, on Sonnet with Claude Code's system prompt replaced by "You are a coding agent working in a terminal. Complete the task the user gives you.".
The baseline is the 9 no-instruction runs of the replaced-prompt attempt above, and the pass bar was set before the runs: at least 15 points above the baseline overall and higher on at least 2 of 3 tasks.

- Repeat, strong: "Run every shell command twice in a row, with the identical command both times, and compare the two outputs before moving on."
- Repeat, gentle: "When you run a shell command that matters to the result, run it a second time straight after, with the identical command, and compare the two outputs."
- Explore: "Before you create or edit any file, first use the Read tool on at least three different files and the Grep or Glob tool at least twice, and only then start making changes."

The first of the two pilots tried the strong repeat and the explore wording, 3 runs per task.
The explore instruction was ignored: the agents kept looking around through the shell, and the Read, Grep or Glob share of tool calls went from 5% to 6%.
The strong repeat gave 48 of 155 steps repeating an earlier command (31%) against 0 of 95 at baseline, once the reader counted each tool call as a step.
That reader change was made after the first measurement, which had failed at 2%, because the model issues each pair of identical commands as parallel calls in one message and the reader had taken only the first.
Because the change followed the result, the second pilot repeated the strong wording on fresh runs with the reader unchanged, and added the gentle wording.

| Task | No instruction | Gentle | Strong |
| --- | --- | --- | --- |
| `git-leak-recovery` | 0 of 29 steps repeat | 0 of 30 | 16 of 49 (33%) |
| `merge-diff-arc-agi-task` | 0 of 34 | 0 of 41 | 13 of 60 (22%) |
| `vulnerable-secret` | 0 of 32 | 0 of 26 | 15 of 45 (33%) |
| All | 0 of 95 (0%) | 0 of 97 (0%) | 44 of 154 (29%) |

The strong wording replicates (29% against 31%) and passes the bar on all three tasks.
The gentle wording had no effect: the agents judged that no command "mattered to the result" and repeated none, so as worded it is not a lower dose but no instruction.
A middle dose needs a mechanical rule of its own, such as repeating every second shell command, or the gentle dose can be cut, which the cut order allows.

Two limits remain.
The behaviour is mechanical and artificial.
And repeating an earlier command is a rule fact that the features compute directly, so finding it as a discovered state is an easier test than finding a behaviour the features do not encode.

## Decision

**Go with a planted repeating behaviour in place of verification.**

Claude Code drives the longer benchmark tasks, which run 7 to 12 steps at $0.15 to $0.30 a run on Sonnet.
Verification could not be planted, and repeating a command can: the strong wording gave 31% and then 29% of steps repeating an earlier command against 0% without it, higher on all three tasks in both pilots, against the PRD's requirement of a rise on 8 of 10 tasks.

Conditions before the freeze:

1. Ten demo tasks that run on the host are needed, and only three have been shown to do so.
   If fewer than ten are found when the tasks are chosen for the freeze, the missing ones are written as custom tasks with scripted checkers.
2. The gentle dose as worded did nothing.
   The freeze either writes and pilots a mechanical middle dose or cuts the gentle dose, which leaves two conditions and 40 runs for ten tasks and two seeds, about $9 at the measured $0.23 a run.
3. The freeze changes the Q2 criterion in the PRD from the verification rate to the repeated-command rate and names the new behaviour in ADR 0004's place.
   The verification flag stays as a step fact, because the failure-prediction features use it.
4. The write-up states that the repeat behaviour is a rule fact the features compute directly, and that the instruction was found by trying behaviours on pilot runs.

What the spike delivers for the rest of the project:

- The verification flag is defined, tested and computed for every public step.
- The labeler route works: `claude -p --output-format json` reports token counts and cost for each call, and one call carries about 10,000 tokens of overhead, so labeling should batch many steps per call.
- The dollar cap does not exist on this plan, so the labeler reserve is set as a list price total with the limit readings above as its justification.
- Claude Code transcripts reduce to the same step facts as the public data, with each tool call as a step.
- In total the spike used 90 Claude Code runs and one labeler call, about $19 at list price.
