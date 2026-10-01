# Implementation Plan

See [PRD.md](PRD.md) for scope, [ARCHITECTURE.md](ARCHITECTURE.md) for system design, and [ADRs](adr/) for decisions.

Build incrementally according to [AGENTS.md](../AGENTS.md).
Each phase must leave the system runnable and verifiable.
From phase 1 on, each phase is a vertical slice: it extends the pipeline, the JSON contract and the site together, and its demo path is to run `make reproduce` and `make start` and look at the new element.

Guardrails for the site:

- By default the exported JSON and the page contain no pass or fail outcome until the `prereg` tag exists. This is an exporter default under option B in the PRD, not a hard block.
- The exported JSON and the page contain derived fields only, never raw command text, output text, reasoning text or steering text.
- The site runs locally until phase 9, and only derived data is ever published, as recorded in the license finding in [PRIOR_WORK.md](PRIOR_WORK.md).
- The first site slice (phase 1) is time-boxed, and if it overruns, cut it down to the ribbons alone.

## 0. Repository Skeleton and CI

- Create the layout in [AGENTS.md](../AGENTS.md) except `web/`: `pyproject.toml`, `src/footsteps/` with a `cli.py` that lists the stages, `tests/`, `data/` (fully gitignored) and `results/`, and `LICENSE` (MIT).
- Add the `Makefile` with the targets `help`, `setup`, `lint`, `test`, `reproduce`, `run-demo`, `label` and `clean`, each calling `uv run`, and add `start` and `build` in phase 1.
- Implement `clean` as removing build output and caches while never touching downloaded data, raw transcripts or results.
- Re-enable the push and pull_request triggers in `.github/workflows/ci.yml`, confirm it calls the make targets `lint` and `test`, and confirm that the GitHub repository (already created, with the remote set) has the description "Discovering named behaviours in LLM agent trajectories and testing if they flag failing runs early" and the topics `llm-agents`, `agent-evaluation`, `agent-trajectories`, `terminal-bench`, `hidden-markov-model`, `failure-analysis` and `agent-observability`, after checking that each topic exists.

**Done:** `make lint` and `make test` pass locally on the skeleton with one trivial test, and CI passes after the first push.

## 1. Ribbon Viewer Walking Skeleton

- Download the public dataset with the Hugging Face tooling, pin the exact revision that the tooling reports, and record a checksum of the downloaded files.
- Verify the documented step format (`src`, `msg`, `tools` with function and command, and `obs` truncated to 5,000 characters) on the real data, and record the trials per task and the model and scaffold combinations.
- Implement ingest into the step table of step facts: a tool category, a result status inferred from the output text, and a hash of the normalized command, computed from the text that is then discarded.
- Scaffold `web/` with Vite, React, TypeScript, Tailwind CSS and shadcn/ui, so the first screen is built on styled components.
- Choose the drawing library by comparing candidates against their documentation, and record it in a new ADR.
- Implement the exporter and the first version of the JSON contract with runs and steps, tool category and result status, and no outcome and no text.
- Build the first page: each run as a row of steps colored by tool category and result status.
- Add the Makefile targets `start` and `build`, extend `setup` and `lint` to `web/`, and add the Node setup and the site build job to CI.

**Done:** `make reproduce` writes `results/site.json` from the pinned download, `make start` shows real run ribbons locally, `make build` succeeds, and CI passes.

## 2. Feasibility Spike

- Make the download step compare the files with the recorded checksum, and on a mismatch print a warning and continue, because a failed download is the only condition that stops `make reproduce`.
- Count the tasks with mixed outcomes per model and scaffold combination, then apply the selection rule from the PRD to choose the one or two combinations, and record the counts, without looking at any behaviour results.
- Read the monthly credit of the personal plan on its usage page and record it as the cap, and confirm that `claude auth status` shows the personal plan and not a work account.
- Decide how the labeler reaches a model, defaulting to the Claude Code command line on the personal login with JSON output, and verify that it reports token counts, otherwise estimate tokens from text length with a safety margin.
- Try two Claude Code non-interactive runs on Terminal-Bench tasks, and measure tokens and cost for a 10-run pilot.
- Map the tool names in the pilot transcripts onto the same tool categories as the public data, and record any tool that does not fit.
- Define the rule-based verification flag, add it to ingest as a step fact, and run the pilot as 2 tasks with no instruction and with the strong instruction to check that the flag rises. The pilot runs are excluded from all analysis.
- If Claude Code cannot drive the benchmark tasks, take the custom task set in phase 2A. The spike took it, because too few benchmark tasks run on the host.

**Done:** `docs/spike.md` is committed with the counts, the chosen combinations, the recorded cap, the labeler route, the measured cost per run, the tool mapping, the pilot manipulation result, and a go or fallback decision for the planted demo.

## Spike Outcome

2026-10-01: the spike recorded in [spike.md](spike.md) found that a planted verification instruction did not raise the verification flag in four pilots, but a planted repeating instruction did, in two pilots (29% and 31% of steps against 0%). The planted demo continues with repeating as its behaviour, and the freeze rewrote the Q2 wording in the PRD and cut the gentle dose, leaving two conditions.

## 2A. Custom Task Set

- Write 10 shell tasks that an agent needs at least about 10 steps to finish, each with a scripted checker.
- Test each checker with a reference solution that must pass and an empty attempt that must fail.

**Done:** the 10 tasks and checkers are committed and pass their self-test, and the planted demo uses them, while Q1, Q3 and Q4 stay on public data.

**Status:** built on 2026-10-01, with the self-test run as `uv run footsteps tasks`. The spike found only 3 benchmark tasks that run on the host, so all 10 demo tasks are custom and none comes from Terminal-Bench. The tasks are designed to need about 10 steps, but their step counts are not yet measured, and the freeze checks them in the pilot before fixing the run order.

## 3. Freeze the Pre-Registration

- Update the PRD with the chosen model and scaffold combinations, the minimum numbers of tasks and runs the natural arm needs, the list of 10 demo tasks in run order, the exact steering prompts for each condition, the verification flag rule, confirmation of the comparison models in the PRD, and the final run count (40, with the gentle dose cut).
- Fix the budget split in the PRD: the planted runs first, then a labeler reserve chosen from the measured cost per run, with the labeler sample sized to that reserve.
- Record option B as a dated PRD note: thresholds and the tag are binding, and hiding outcomes before the tag and the never-cut list are defaults and recommendations.
- Apply the viability gate: if the counts fall below the minimums, record which questions are reduced or dropped before freezing.
- Commit the update and tag it `prereg`.
- After the tag exists, add the outcome to the export and enable the site's pass or fail toggle.
- Record a later prompt redesign as a dated note in the PRD with the new prompt and a new tag `prereg-2`, and report the runs made with the earlier prompt.

**Done:** the tag `prereg` exists, no analysis code that produces results predates it, and the site shows outcomes only from this point.

**Status:** frozen on 2026-10-01 with the demo tasks run in the order of the `tasks/` folder, because their step counts were not measured in a pilot.

## 4. Planted Runs

- Implement the runner with the token log and the cap check, have it write each planted step as the same step facts as ingest with the raw transcripts kept only in the gitignored `data/` folder, and run the pre-registered runs in order.
- Apply the interim stop rule from the PRD after the first 3 tasks, and redesign the prompt under the phase 3 rule if it triggers.
- Commit the step table of the planted runs with no raw text, and show the planted runs as ribbons in the site.

**Done:** the planted runs are complete or stopped by the rule, their step table is committed, the site shows them as ribbons, and the cost log shows the spend against the cap.

**Status:** built and run on 2026-10-01. All 40 runs were made in the pre-registered order (`footsteps runner --tasks 1`, then `--tasks 3`, then the rest), and the interim rule said continue, with the repeat share higher with the instruction on 3 of the first 3 tasks. The manipulation check rose on 10 of 10 tasks, and the spend was $4.00 of the $12 planted budget. Steps per run ranged from 4 to 23 and the medians were 7 without the instruction and 15 with it, which the PRD said to report. 19 of 20 runs passed their checker in each condition. The runs carried the author's user-level Claude Code instructions and the claude.ai connector tools were present but not allowed, as in the pilots. The planted tables are `results/planted_runs.parquet` and `results/planted_steps.parquet`, and the cost log is `results/cost_log.jsonl`.

## 5. Segmentation and Point Cloud

- Implement the behavioural features as summaries of the step facts only, and the shared schema for public and planted runs.
- Define one task-fold assignment with a fixed seed that Q1, Q3 and Q4 all use, and a run-level split that serves as the seen-task condition for Q4.
- Implement the HMM and the GMM in the original feature space with the state-count rule.
- Verify the `hmmlearn` API against its documentation, and record the chosen approach in an ADR if stickiness needs a custom transition prior.
- Export the display projection and the state of each step, and show the linked point cloud and state-colored ribbons in the site.

**Status:** built on 2026-10-02. The features are 16 flags and shares in `FEATURE_NAMES`, with only earlier steps as neighbours so that a prefix of a run has the same features inside the whole run. The natural arm is the selected combinations on tasks where that combination has both outcomes, which is 411 runs on 57 tasks. The HMM size rule picked 8 states, the top of the range, because held-out likelihood rose with every added state, which is a limit to report and not a reason to widen the range after the freeze. The GMM uses the same state count. Planted runs are placed on the natural model and are never used to fit it. The fixed seed is 0, with 5 task folds from the hash of the task id, and a separate run-level split for the seen-task condition. Stickiness needed no custom prior, because `hmmlearn` takes a full matrix as the transition prior. It did need a small subclass, because the library applies its minimum variance only when it initializes, so a state could otherwise collapse onto a flag. Ingest also had to change: the dataset leaves the trial id empty on most rows, including every natural-arm row, so ingest now derives a run id from agent, model, trial name and start time.

**Done:** `make reproduce` regenerates `results/site.json` with states, the site shows the linked point cloud and state-colored ribbons, and the tests pass on synthetic fixtures generated in code.

## 6. Labeling and Behaviour Names

- Implement the rule-based facts and the LLM wrapper with pinned prompts, caching, and a cost check against the labeler reserve.
- Draw the human sample of 100 to 200 steps across the discovered states and rule facts, including steps from both training tasks and held-out tasks so that Q4 can compare agreement on seen and unseen tasks, and write it as a shuffled sheet with the run, task and condition hidden.
- Label the sheet by hand.
- Compute labeler agreement against the human sample and the Q1 agreement scores.
- Name each discovered state from its label evidence.
- Commit the labels as run and step identifiers with no raw text, and extend `make reproduce` to read them and produce the Q1 table with no model calls.
- Show each behaviour name with its evidence, and the Q1 result next to its pre-registered criterion, in the site.

**Status:** the first part is built on 2026-10-02: the rule facts, the LLM wrapper and the blind sheet, with the model not yet run and the sheet not yet labeled. The rule facts are repeats an earlier command, follows an error, has no tool call, and is the last step. The sample is dealt across HMM state, rule fact and a held-out flag (tasks in task fold 0), taken from the natural arm only, so the steering prompt and condition are out of reach of the labeler. The first 150 steps of the deal of 2,000 are the human sheet, so the model labels them first. The wrapper uses `claude-haiku-4-5-20251001`, 40 steps per call, and stops with what is labeled when the reserve (the cap less the planted budget) is used up.

**Done:** the Q1 table and the labeler agreement value are written to `results/`, the LLM stage runs only through `make label`, `make reproduce` regenerates the Q1 table from the committed labels, and the site shows the behaviour names.

## 7. Failure Patterns and Filters

- Build the whole-run behaviour profile (share of steps per state in each third of the run, and the number of switches), and compare a classifier on it with run length and with the supervised predictor for Q3a, and report the states and transitions that carry the signal.
- Implement the first-k-step prefixes, the counts-so-far baseline, the behaviour-view predictor, and the supervised predictor for Q3b, with task-grouped folds and bootstrap ranges, and draw whole-run length as a labelled reference line.
- Compute the unseen-task comparison for Q4.
- Extend `make reproduce` to produce the Q3a, Q3b and Q4 tables.
- Show the Q3a, Q3b and Q4 results next to their criteria in the site, and add the filters for data source and outcome.

**Done:** the Q3a, Q3b and Q4 tables are written to `results/` by `make reproduce` with the number of runs dropped at each k, and the site shows them with working filters.

## 8. Planted Behaviour Analysis and Q2

- Project steered runs onto the natural behaviours, or use their own behaviours in the fallback, and compute the Q2 results.
- Judge the final 8 of 10 criterion for the manipulation check only after all tasks have run.
- Extend `make reproduce` to read the committed step table of the planted runs and produce the Q2 results with no model calls.
- Show the Q2 results with every task plotted as its own point, and add the condition filter, in the site.

**Done:** the Q2 table and the per-task differences are written to `results/`, `make reproduce` regenerates them from the committed step table, and the site shows them.

## 9. Pages Deployment and Write-Up

- Confirm that the license finding in [PRIOR_WORK.md](PRIOR_WORK.md) still holds for the pinned revision.
- Add the GitHub Pages workflow.
- Write the README results section with the honest limits, and finalize [PRIOR_WORK.md](PRIOR_WORK.md) after checking the load-bearing entries against the papers.
- Run `make reproduce` on a fresh clone and confirm it regenerates every table and `results/site.json` with no model calls.

**Done:** the README states every result against its pre-registered criterion, `make reproduce` works on a fresh clone, and the Pages build publishes the site.

## Cut Order

If time runs short, cut in this order:

1. Text-embedding ablation (an extra that starts out of scope).
2. The gentle dose in the planted demo, which the freeze has already cut.
3. HDBSCAN and any extra comparison methods (an extra that starts out of scope).
4. Site polish such as search and extra views, keeping the ribbons, the linked point cloud, and the filters.
5. The planted demo, as a last resort, which drops Q2 and leaves Q1, Q3 and Q4 on public data.

The site itself from phase 1 is not cut, because every later phase is checked through it.

Never cut (a recommendation under option B in the PRD, with the tag and the thresholds the only binding items):

- The pre-registration tag and the frozen criteria.
- Keeping outcomes out of the site and the export until the tag exists.
- The run-length and counts-so-far baselines and the task-grouped folds.
- The manipulation check in the planted demo, while the demo exists.
- The blind human label sample.
- The cost cap and the token log.
