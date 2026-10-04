# PRD: Agent Footsteps

See [ARCHITECTURE.md](ARCHITECTURE.md) for system design and [PLAN.md](PLAN.md) for build order.
Related work and what this project does and does not claim is in [PRIOR_WORK.md](PRIOR_WORK.md).

## Problem

AI agents sometimes reach a wrong answer by a wrong path, and engineers who evaluate or monitor them usually see only the final pass or fail, or read raw transcripts by hand.
Plenty of work tries to predict when an agent will fail, and some tries to find recurring patterns in what agents do, such as repeating the same command or testing their own work.
The work reviewed rarely checks that such a pattern is real, by making an agent behave that way on purpose and seeing whether the pattern shows up.
It also rarely checks whether a pattern warns of failure any better than something simple, like the number of errors so far.

## Goal

Find behaviours in agent runs automatically, name them, check the names against behaviours planted with instructions, and measure whether time spent in those behaviours predicts which runs fail.
The result is published as an open experiment with an interactive site.

## Terms

A **run** is one attempt by an agent at one task, and it ends as a pass or a fail.
A **step** is one action an agent takes in a run, such as running a command.
A **behaviour** is a recurring kind of step sequence, such as verifying, exploring or repeating.
A **planted behaviour** is one induced on purpose by an instruction given to the agent, here a rule to run every shell command twice.
An **HMM** (hidden Markov model) assigns each step to a behaviour and prefers to stay in a behaviour for several steps.
A **GMM** (Gaussian mixture model) is the simpler comparison that assigns each step to a behaviour on its own.
**AUROC** is a score from 0.5 (coin flip) to 1 (perfect) for how well a method separates runs that fail from runs that pass.
A **prefix** is the first k steps of a run.
A **bootstrap range** shows how much a number would wobble on different data.

## MVP Scope

### Reader

- Reads the README and the interactive site to see the claim, the figures, and the honest limits.
- Explores steps in a linked point cloud and colored timeline, filtered by data source, condition and outcome.
- Sees every behaviour name with its evidence and the pre-registered success and failure criteria next to the results.

### Reproducer

- Clones the repo and runs `make reproduce` to download the public data at a pinned revision and regenerate the tables and the site data with no model calls and no cost.
- Runs any stage that uses a model only through an explicit target that warns it uses credit.

### System

- A natural arm built from free public Terminal-Bench trajectories, restricted to a rule-selected model and scaffold, and to tasks with mixed pass and fail outcomes.
- A planted demo of 40 runs (10 pre-set tasks, 2 conditions, 2 seeds each), as frozen below.
- Behavioural step features, an HMM segmenter, and a GMM comparator, both fit in the original feature space.
- Two-layer labeling used only to check the discovered behaviours, with a blind human sample of 100 to 200 steps.
- Failure analysis on whole runs (Q3a) and on the first k steps (Q3b), compared with run length, counts so far, and a trained supervised predictor.
- A static React site fed by one JSON file, run locally with `make start` and not deployed.
- A hard spending cap on the list-price cost that Claude Code reports, as frozen below.

## Acceptance Criteria

All thresholds below are frozen before any analysis result is seen.
The freezing point is the git tag `prereg`, which must exist before the analysis code that produces results is written, meaning the features, the segmentation and the evaluation.
Ingest, the exporter, the spike counts and the pilot are not analysis results and come before the tag.
Changing a threshold afterwards requires a dated note in this file and a statement of the change in the write-up.

### Freeze, 2026-10-01

Enforcement follows option B: the thresholds and the tag are binding, while hiding outcomes before the tag and the never-cut list in [PLAN.md](PLAN.md#cut-order) are defaults and recommendations that the author can override with a dated note.
The exporter therefore leaves the outcome out unless the tag exists, and does not block a run otherwise.

- **Combinations.** terminus-2 with gpt-5.1-codex@openai (44 mixed tasks, 432 trials with steps) and terminus-2 with gemini-3-flash-preview@gemini (39 mixed tasks, 444 trials with steps), as selected by the rule above from `results/dataset_summary.json` at the pinned revision.
- **Minimums and the gate.** The natural arm needs at least 30 mixed-outcome tasks and 300 trials with steps in each selected combination. Both are met, so no question is dropped or reduced by the gate. Q3b still reports the runs dropped at each k.
- **Verification flag.** The rule in ingest at this commit is frozen, and it stays a step fact because the failure features use it. It is no longer the planted behaviour.
- **Comparison models.** Confirmed as proposed above.
- **Planted behaviour.** The planted behaviour is repeating a shell command, and the spike notes in [spike.md](spike.md) record that verification could not be planted. The design has two conditions, none and strong, and the gentle dose is cut because it had no effect as worded.
- **Demo tasks in run order.** `access-log-report`, `archive-dig`, `backup-script`, `config-fix`, `csv-merge`, `git-detective`, `permission-audit`, `photo-rename`, `template-render`, `word-pipeline`, in the order of the `tasks/` folder. The step counts of these tasks are not measured, and they are reported with the runs.
- **Runs.** Each task is run with both conditions and seeds 1 and 2, giving 40 runs, in the order task, seed, condition. Both conditions run Claude Code non-interactively on `claude-sonnet-5` with the tools Bash, Read, Write, Edit, Glob and Grep, and with Claude Code's system prompt replaced by "You are a coding agent working in a terminal. Complete the task the user gives you."
- **Steering prompts.** Condition none adds nothing. Condition strong adds "Run every shell command twice in a row, with the identical command both times, and compare the two outputs before moving on."
- **Budget.** The plan has no dollar credit, so the cap is a list-price total, taken from the `total_cost_usd` that Claude Code reports for each call. The working ceiling is $40, set against the author's weekly allowance, which the spike measured at about 0.3 weekly percentage points per list-price dollar. The planted runs are budgeted first, at $12 for 40 runs against a measured $0.23 a run, and the remaining $28 is the labeler reserve. The labeler batches many steps per call, because each call carries about 10,000 tokens of overhead, and its sample shrinks to fit the reserve.
- **Limits stated in advance.** The repeat behaviour is mechanical and artificial, the features compute the repeat flag directly so finding it is an easier test than finding a behaviour the features do not encode, and the instruction was chosen by trying behaviours on pilot runs, which are excluded from all analysis.

- **Selection rule.** The public-data model and scaffold combination is the one or two combinations with the most tasks that have mixed outcomes across their trials, ties broken by trial count.
- **Viability gate.** The natural arm proceeds only if the selected combinations meet minimum numbers of mixed-outcome tasks and runs, which are written here at the freeze from the counts alone.
  If they fall short, the questions that cannot be supported are dropped or reduced here before the tag.
- **Comparison models.** These are proposed here and confirmed at the freeze.
  The run-length baseline is a logistic regression on run length.
  The counts-so-far baseline is a logistic regression on the number of errors and the number of different tools in the window.
  The behaviour view is a logistic regression on the state shares and the number of switches.
  The supervised predictor is a gradient-boosted trees model on the counts of every tool category and result status and the verification and repeat facts in the window, with no discovered states.
- **HMM size rule.** The number of HMM states is chosen from 2 to 8 by held-out likelihood on training tasks.
- **Q1, do discovered behaviours match names a person would give.** On tasks unseen in training, the HMM's states agree with the step labels better than the GMM's and better than a majority-label baseline, with the difference larger than the bootstrap range.
  Agreement is measured with normalized mutual information.
  A failure is reported as "stickiness adds nothing here".
- **Labeler bar.** The LLM labeler is used for the full label set only if its agreement with the human sample is at least 0.6 on Cohen's kappa.
  Otherwise Q1 is reported on the human sample only.
- **Q2, does a planted behaviour show up as its own behaviour.** The manipulation check passes: the share of shell steps that repeat a command already run earlier in the same run, by command hash, is higher with the instruction than without it on at least 8 of 10 tasks.
  While the runs are in progress an interim rule applies: after the first 3 tasks in run order, if that share rose on fewer than 2 of them, the runs stop and the instruction is redesigned, and the 8 of 10 criterion is judged only after all 10 tasks have run.
  The pilots on 3 tasks ran the same check before the freeze and are excluded from the analysis.
  The repeating behaviour is the discovered state in which most steps carry the repeat flag, and if no state qualifies then Q2 is reported as not detected.
  Then the share of steps in the repeating behaviour is higher in steered runs than in baseline runs on at least 7 of 10 tasks, with every task plotted as its own point.
  If the check fails, the instruction is redesigned before any more runs are spent, recorded as a dated note in this file with a new tag `prereg-2`, and the runs made with the earlier prompt are reported.
- **Population.** Q1, Q3a, Q3b and Q4 use the public natural arm only, and the planted runs are used for Q2 only.
- **Q3a, do failing runs follow different behaviour patterns over the run.** Each finished run is described by its behaviour trajectory: the share of steps in each discovered state in the first, middle and last third of the run, and the number of switches between states.
  From this profile a classifier separates failing from passing runs better than run length alone in AUROC, with the difference larger than the bootstrap range, and within 0.05 AUROC of the trained supervised predictor.
  The report names the states and transitions that carry the signal, with bootstrap ranges.
  Folds are grouped by task so no task appears in both training and testing.
- **Q3b, would an early check have caught the failure.** Offline, on recorded runs, using only the first k steps for k in 5, 10 and 15 and only runs with at least k steps, the behaviour view beats the baseline in AUROC with the difference larger than the bootstrap range, and comes within 0.05 AUROC of the trained supervised predictor.
  The baseline is counts so far, meaning the number of errors and the number of different tools used in the first k steps, because the public data records tokens and time per trial and not per step.
  Whole-run length is drawn as a reference line labelled as unfair because it uses information from the future.
  The report states how many runs drop out at each k.
  Restarting or cancelling a run is future work.
- **Q4, do behaviours hold on unseen tasks.** AUROC and agreement on unseen tasks drop by no more than 0.05 relative to seen tasks.
  Seen tasks means a run-level split in which a task can appear in both training and testing, and unseen tasks means the task-grouped folds.
  A larger drop is reported as a limit.
- **Negative results.** Any failed criterion is reported with the same prominence as a success.
- **Cost.** Total spend stays within the $40 list-price cap, the labeler stays within the reserve fixed at the freeze, the planted runs are budgeted before the labeler, and every model call is logged with its token counts.
- **Reproduction.** `make reproduce` runs on a fresh clone with no credentials and no model calls, needing only the download of the public dataset.
- **Novelty wording.** The README claims only what [PRIOR_WORK.md](PRIOR_WORK.md) allows.

## Out of Scope

- Cross-benchmark transfer, because the sample sizes cannot support it.
- More than one planted behaviour, because one behaviour with a manipulation check is the minimum control.
- Text-embedding features as the main method, because existing tools already do this; it stays an extra only if time remains.
- HDBSCAN and other comparison methods, for the same reason.
- Mid-run hints, corrective steering, restarting or cancelling runs, and reinforcement learning, which are future work.
- A novel failure predictor, because the prediction side is already well covered by prior work and is only used as a benchmark.

## Constraints

- One author.
- Hard cost cap: $40 of list-price cost as reported by Claude Code, because the personal Claude Pro plan has rolling allowances and no dollar credit.
- Planted-demo runs use the personal login.
- The public benchmark data keeps its own license, so it is downloaded at run time and never committed.
- By default the site shows no pass or fail outcome until the `prereg` tag exists, and the site is not published to GitHub Pages: readers clone the repo and run `make start`, a decision dated 2026-10-04.
