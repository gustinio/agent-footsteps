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
A **planted behaviour** is one induced on purpose by an instruction added to the agent's system prompt.
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
- A planted demo of up to 60 runs (10 pre-set tasks, 3 conditions, 2 seeds each), scaling down to 48 or 32 runs if the cost per run requires it.
- Behavioural step features, an HMM segmenter, and a GMM comparator, both fit in the original feature space.
- Two-layer labeling used only to check the discovered behaviours, with a blind human sample of 100 to 200 steps.
- Failure analysis on whole runs (Q3a) and on the first k steps (Q3b), compared with run length, counts so far, and a trained supervised predictor.
- A static React site fed by one JSON file, deployed on GitHub Pages.
- A hard spending cap equal to the monthly credit of the author's personal Claude Pro plan.

## Acceptance Criteria

All thresholds below are frozen before any analysis result is seen.
The freezing point is the git tag `prereg`, which must exist before the analysis code that produces results is written, meaning the features, the segmentation and the evaluation.
Ingest, the exporter, the spike counts and the pilot are not analysis results and come before the tag.
Changing a threshold afterwards requires a dated note in this file and a statement of the change in the write-up.

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
- **Q2, does a planted behaviour show up as its own behaviour.** The manipulation check passes: the rule-based verification rate is higher with the instruction than without it on at least 8 of 10 tasks.
  While the runs are in progress an interim rule applies: after the first 3 tasks in run order, if the flag rose on fewer than 2 of them, the runs stop and the instruction is redesigned, and the 8 of 10 criterion is judged only after all 10 tasks have run.
  A pilot on 2 tasks runs the same check before the freeze, and the pilot runs are excluded from the analysis.
  The verifying behaviour is the discovered state whose label evidence is mostly the verify intent, and if no state qualifies then Q2 is reported as not detected.
  Then the share of steps in the verifying behaviour is higher in steered runs than in baseline runs on at least 7 of 10 tasks.
  The dose trend across strengths is reported as exploratory, with every task plotted as its own point.
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
- **Cost.** Total spend stays within the cap, the labeler stays within the reserve fixed at the freeze, the planted runs are budgeted before the labeler, and every model call is logged with its token counts.
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
- Hard cost cap: the monthly credit of the author's personal Claude Pro plan, which the docs check put at $20 per month and which must be confirmed on the plan page.
- Planted-demo runs use the personal login.
- The public benchmark data keeps its own license, so it is downloaded at run time and never committed.
- The site shows no pass or fail outcome until the `prereg` tag exists, and it is published to GitHub Pages only after the dataset license has been checked.
