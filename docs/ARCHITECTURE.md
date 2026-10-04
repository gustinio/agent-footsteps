# Architecture

See [PRD.md](PRD.md) for product scope, [PLAN.md](PLAN.md) for build order, and [ADRs](adr/) for decisions.

## System

A batch pipeline turns agent trajectories into named behaviours, evaluates them, and exports one JSON file that a static website displays.
There is no server and no database, and stages exchange files.
Natural runs come from the public Terminal-Bench trajectories, and a small set of planted runs comes from Claude Code on a personal plan, working on custom shell tasks.
A language model is used in two places only: the agent under test in the planted runs, and a labeler that checks the discovered behaviours.

```text
public Terminal-Bench data ──► ingest ──┐
                                        ├─► step table ─► features ─► segmenter (HMM, GMM) ─┐
Claude Code planted runs ──► runner ────┘                                                   │
                                                                                            ▼
rules + LLM labeler + human sample ─────────────────────────────────► labels ─► evaluator ─► results/*.parquet
                                                                                            │
                                                                                            ▼
                                                                                        exporter ─► results/site.json ─► web/ (static site)
```

## Component Boundaries

**Ingest** (`src/footsteps/ingest.py`) downloads the public trajectories and normalizes them into the step table.
It computes the step facts from each step's text and then discards the text: the tool category, the result status, a hash of the normalized command, and the rule-based verification flag.
It owns the mapping from the source format to the step schema and the record of trials per task.
It also reduces Claude Code stream-json transcripts to the same step facts for the pilot, one tool call per step, into `data/pilot_steps.parquet`, which no analysis reads.
It also compares the downloaded files with the recorded checksum and, on a mismatch, prints a warning and continues.
It must not compute sequence-level features or labels, and it must not write raw text to anything that is committed.

**Tasks** (`src/footsteps/tasks.py` and `tasks/`) hold the 10 custom shell tasks of the planted demo.
Each task folder has the prompt the agent receives, a setup script that builds the starting files in an empty directory, a scripted checker that exits 0 only when the work is right, and a reference solution.
The `footsteps tasks` self-test runs every checker against its reference solution, which must pass, and against an empty attempt, which must fail.
A task is plain shell, needs no container and no network, and the checker lives outside the working directory, so the agent never sees it.
Tasks contain no model call, and the runner reads them without changing them.

**Runner** (`src/footsteps/runner.py`) executes the planted demo through the Claude Code command line, one task and condition at a time, and writes each transcript as the same step facts as ingest, keeping the raw transcript only in the gitignored `data/` folder.
It owns the steering prompts, the run order, and the token log that enforces the cost cap: before each run it passes Claude Code the budget still left, and it stops when none is left.
It skips runs already in the planted tables, so an interrupted or staged invocation resumes where it stopped, and it records a run only when Claude Code finished it.
It must not read results or decide when to stop based on them, and it runs in a throwaway working directory on the personal login only, which it checks before the first run.
The interim stop rule is therefore applied between invocations: `footsteps runner --tasks 3` stops after the first three tasks, and a person reads the evaluator's table before running the rest.

**Features** (`src/footsteps/features.py`) turns the step facts into behavioural features, such as a repeat flag from command hashes seen earlier in the run, the recent error history, and the tool category and verification flag of a step and the step before it.
Only earlier steps are neighbours, so a prefix of a run has the same features as the same steps inside the whole run.
It reads the step facts only, and it has no stage of its own: the segmenter and the exporter call it.
It must never read raw text, the system prompt, the steering text, or a label, and it must produce the same schema for public and planted runs.

**Segmenter** (`src/footsteps/segment.py`) fits the HMM and the GMM in the original feature space and outputs one state per step.
It owns the natural arm (the selected combinations on tasks where that combination has both outcomes), the state-count rule, and the one fixed-seed task-fold assignment and run-level split that Q1, Q3 and Q4 share.
The models are fit on the natural runs only, the GMM uses the HMM's state count, and planted runs are decoded with the natural models.
States are numbered by how many natural steps they hold.
It must not cluster in a 2D projection, and the projection exists only for display.

**Labeler** (`src/footsteps/label.py`) produces rule-based facts, LLM intent labels, and the shuffled sheet for the human sample.
It draws the sample from the natural arm, dealing across HMM state, rule fact and a held-out flag (tasks in task fold 0), and writes the sheet and its key to the gitignored `data/`, because the sheet holds step text.
For that it reads the raw step text through `ingest.raw_agent_steps` and `ingest.step_text`, which cut each step to its tool, command, output and message.
It owns the agreement check against the human sample.
The LLM never sees the steering prompt or the condition, and labels never flow back into features or the segmenter.

**Evaluator** (`src/footsteps/evaluate.py`) computes agreement, the manipulation check, and the whole-run and prefix prediction comparisons with task-grouped folds and bootstrap ranges.
It owns every threshold in the PRD and reads them from one place. So far it holds the manipulation check, the interim stop rule and Q1, which `footsteps evaluate` prints; Q1 also writes `results/q1.json` (labeler kappa against the bar, NMI of the HMM, GMM and a majority label on held-out tasks with bootstrap ranges over runs, and a name with evidence for each HMM state), which the exporter copies into `site.json`.
It must not change a threshold, and it must not use the LLM.

**Exporter** (`src/footsteps/export.py`) samples natural-arm runs from the segmentation, adds every planted run from the committed planted tables, computes the display projection, and writes the JSON contract.
It must never write raw command or output text or any steering text into the JSON, and it includes the outcome only when the `prereg` tag exists.

**Site** (`web/`) reads the JSON and draws the linked views.
It must not compute statistics or call a model, and every number it shows comes from the JSON.

**LLM wrapper** (`src/footsteps/llm.py`) is the only code that calls a model for labeling.
It pins the prompt, caches results by input, logs tokens, and refuses a call that would exceed the labeler reserve or the cap.
The cache is `data/label_cache.jsonl`, keyed by the prompt version, the model and the batch, and the intent labels of a run are written to `results/llm_labels.parquet` as run and step identifiers with no text.
It logs under the stage `labeler` and passes each call the budget left to it, as the runner does.

## Data Model

Core entities:

```text
Task 1─N Run 1─N Step 1─1 StepFeatures
                   │
                   ├─N Segmentation (per method)
                   └─N Label (per labeler)
StateName maps (method, state_id) to a behaviour name
Prediction belongs to a Run, and for early checks to a prefix length k
```

- `Task`: `task_id`, benchmark. One task has many runs.
- `Run`: `run_id`, `task_id`, `source` (public or planted), `agent` (scaffold), `model`, `seed`, `condition` (none or strong; empty for public runs), `outcome` (pass or fail from the verifier), `n_steps`.
- `Step`: `run_id`, `step_idx`, `tool_category` (shell, read, search, edit, plan, web, finish, other, or none when the step calls no tool), `result_status` (ok, error or empty), `command_hash`, `verification_flag`. These step facts hold no raw text.
  A step is one agent-sourced step of the public trace, and user and system text are not steps.
  When a public step makes several tool calls, the facts come from the first call, and a Claude Code transcript is split so that each tool call is a step.
  `result_status` is inferred from the output text by phrase rules, and is `empty` when there is no output or when the dataset replaced the output with a `$<number>` placeholder.
  `command_hash` is empty when the step has no tool call, no command text, or a placeholder in place of the command.
  `verification_flag` is true when the first tool call is a shell command that contains a test or check word (test, pytest, diff, cmp, assert, verify, validate, check, lint and similar) or runs an inline `python -c`, `node -e` or `python -` heredoc script, and false for every other step. It is a match on the command text, so a command that only mentions such a word also counts.
- `StepFeatures`: `run_id`, `step_idx`, plus behavioural features derived from the step facts only. Never contains raw text, the system prompt or the steering text.
- `Segmentation`: `run_id`, `step_idx`, `method` (`hmm` or `gmm`), `state_id`. It covers the natural-arm runs and the planted runs, and is written to `results/segmentation.parquet` with `results/segmentation_summary.json` (the held-out score per state count, the learned self-transition rates and the state shares).
- `Label`: `run_id`, `step_idx`, `label`, `labeler` (rule, LLM or human). The LLM rows are in `results/llm_labels.parquet` and the human rows in `results/human_labels.csv`, both identifiers and labels with no text: the rule facts are computed in memory when the sample is drawn. The blind sheet and its key are local files, `data/label_sheet.csv` and `data/label_key.json`.
- `StateName`: `method`, `state_id`, `name`, `evidence`.
- `Prediction`: `run_id`, `k` (empty for whole-run predictions), `model` (baseline, behaviour view or supervised predictor), `score`, `fold`.

The public trace format was verified on the pinned revision: 52,104 trials, of which 34,462 have steps and 34,397 have at least one agent step, and the rest are dropped from the run and step tables but counted in `results/dataset_summary.json`.
A tool's command is a string, a list or a placeholder, and ingest normalizes all three.
The dataset leaves the trial id empty on most rows, so `run_id` is the trial id when there is one and otherwise a hash of agent, model, trial name and start time, which is unique across the pinned revision.
Ingest writes `data/runs.parquet` and `data/steps.parquet` (gitignored), where the run table keeps the outcome for the feasibility counts, and the exporter writes it only when the `prereg` tag exists, because hiding outcomes before the tag is its default.
The runner appends each finished planted run to `results/planted_runs.parquet` (the run fields above, with `seed`) and `results/planted_steps.parquet` (the step facts), which are committed because they hold no text, and keeps the raw transcripts in `data/planted/`.
`results/cost_log.jsonl` has one line per call with its token counts, `cost_usd` as Claude Code reports it, the stage, and `spent_usd` for that stage against `budget_usd` and `cap_usd`.
The planted budget is $12 of the $40 cap, and the runner passes the smaller of what is left of the budget and of the cap to each call, so a run stops at the cap.
The exporter writes `results/site.json` from a fixed sample of 60 natural-arm runs chosen by the hash of the run id plus every planted run, listed first and carrying its `condition`, and gives every step its HMM and GMM state and its display position (the first two principal components of the step features, scaled to 0 to 1 with a small repeatable offset so identical steps do not stack), and `results/dataset_summary.json` records the pinned revision, file checksums, trial counts, and the model and scaffold combinations with their counts of tasks with mixed outcomes and the combinations the PRD selection rule chooses.

## AI/Agent Boundary

The model is responsible for:

- Acting as the agent under test in the planted runs, driven by the steering prompt.
- Assigning one of four intent labels (explore, modify, verify, other) to a sampled step, blind to the steering prompt.

The model is not responsible for:

- Features, segmentation, thresholds, statistics, or pass and fail outcomes, which come from the public verifier or the task checker.
- Deciding whether a behaviour name is correct, which is decided by agreement with the human sample.
- Choosing how many runs to make or when to stop.

These stay deterministic application logic, testable without the model.

## Frontend / UI Style

The site uses Tailwind CSS with shadcn/ui, chosen for accessible pre-styled controls with little custom CSS.
The point cloud and timeline are drawn as React-rendered SVG with individual D3 modules added as needed, as recorded in [ADR-0008](adr/0008-draw-the-site-with-react-svg-and-d3-modules.md).
The page fetches the exporter's JSON from `results/site.json` at runtime, and Vite bundles that file as an asset on build.

The layout is a three-region dashboard.
A left panel holds the controls: data source, condition, and a run picker.
The main area stacks the point cloud above the colored timeline, linked so that selecting a point highlights its run and step, and hovering a timeline segment highlights its points.
A detail panel shows the tool, result status, behaviour name and outcome of the selected step, and every behaviour name has a legend entry that explains it.

## Observability

Every model call and every planted run appends a record with token counts and estimated cost to `results/cost_log.jsonl`.
The wrapper and the runner read that log before each call and stop when the next call would exceed the cap.
The evaluator writes the counts that the PRD requires: tasks used, mixed-outcome tasks, and runs dropped per prefix length.

## Runtime

Locally, `make` targets call `uv run` for Python stages and `npm` for the site.
`make` alone prints help, `make reproduce` downloads the public data at a pinned revision and regenerates results with no model calls, `make start` runs the site's dev server in the foreground, `make build` produces the production site, and `make clean` removes build output.
In production the site is a static build published on GitHub Pages, and there is no other runtime.

## Stack

- Python 3.12 with `uv`
- `pandas` and `numpy`
- `huggingface_hub` for the pinned download and `pyarrow` for the parquet files
- `scikit-learn`
- `hmmlearn` for the HMM, to be verified against its documentation before use
- `pytest` and `ruff`
- Vite, React and TypeScript
- Tailwind CSS and shadcn/ui
- ESLint and Prettier
- GitHub Actions and GitHub Pages
