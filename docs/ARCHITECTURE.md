# Architecture

See [PRD.md](PRD.md) for product scope, [PLAN.md](PLAN.md) for build order, and [ADRs](adr/) for decisions.

## System

A batch pipeline turns agent trajectories into named behaviours, evaluates them, and exports one JSON file that a static website displays.
There is no server and no database, and stages exchange files.
Natural runs come from the public Terminal-Bench trajectories, and a small set of planted runs comes from Claude Code on a personal plan.
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

**Runner** (`src/footsteps/runner.py`) executes the planted demo through the Claude Code command line, one task and condition at a time, and writes each transcript as the same step facts as ingest, keeping the raw transcript only in the gitignored `data/` folder.
It owns the steering prompts, the run order, and the token log that enforces the cost cap.
It must not read results or decide when to stop based on them, and it runs in a throwaway working directory on the personal login only.

**Features** (`src/footsteps/features.py`) turns the step facts into behavioural features, such as a repeat flag from command hashes seen earlier in the run, the recent error history, and the tool category and verification flag of a step and its neighbours.
It reads the step facts only.
It must never read raw text, the system prompt, the steering text, or a label, and it must produce the same schema for public and planted runs.

**Segmenter** (`src/footsteps/segment.py`) fits the HMM and the GMM in the original feature space and outputs one state per step.
It owns the state-count rule.
It must not cluster in a 2D projection, and the projection exists only for display.

**Labeler** (`src/footsteps/label.py`) produces rule-based facts, LLM intent labels, and the shuffled sheet for the human sample.
It owns the agreement check against the human sample.
The LLM never sees the steering prompt or the condition, and labels never flow back into features or the segmenter.

**Evaluator** (`src/footsteps/evaluate.py`) computes agreement, the manipulation check, and the whole-run and prefix prediction comparisons with task-grouped folds and bootstrap ranges.
It owns every threshold in the PRD and reads them from one place.
It must not change a threshold, and it must not use the LLM.

**Exporter** (`src/footsteps/export.py`) samples steps, computes the display projection, and writes the JSON contract.
It must never write raw command or output text or any steering text into the JSON.

**Site** (`web/`) reads the JSON and draws the linked views.
It must not compute statistics or call a model, and every number it shows comes from the JSON.

**LLM wrapper** (in `src/footsteps/`) is the only code that calls a model for labeling.
It pins the prompt, caches results by input, logs tokens, and refuses a call that would exceed the labeler reserve or the cap.

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
- `Run`: `run_id`, `task_id`, `source` (public or planted), `agent` (scaffold), `model`, `seed`, `condition` (none, gentle or strong; empty for public runs), `outcome` (pass or fail from the verifier), `n_steps`.
- `Step`: `run_id`, `step_idx`, `tool_category` (shell, read, search, edit, plan, web, finish, other, or none when the step calls no tool), `result_status` (ok, error or empty), `command_hash`, `verification_flag`. These step facts hold no raw text.
  A step is one agent-sourced step of the public trace, and user and system text are not steps.
  When a public step makes several tool calls, the facts come from the first call, and a Claude Code transcript is split so that each tool call is a step.
  `result_status` is inferred from the output text by phrase rules, and is `empty` when there is no output or when the dataset replaced the output with a `$<number>` placeholder.
  `command_hash` is empty when the step has no tool call, no command text, or a placeholder in place of the command.
  `verification_flag` is true when the first tool call is a shell command that contains a test or check word (test, pytest, diff, cmp, assert, verify, validate, check, lint and similar) or runs an inline `python -c`, `node -e` or `python -` heredoc script, and false for every other step. It is a match on the command text, so a command that only mentions such a word also counts.
- `StepFeatures`: `run_id`, `step_idx`, plus behavioural features derived from the step facts only. Never contains raw text, the system prompt or the steering text.
- `Segmentation`: `run_id`, `step_idx`, `method` (HMM or GMM), `state_id`.
- `Label`: `run_id`, `step_idx`, `label`, `labeler` (rule, LLM or human).
- `StateName`: `method`, `state_id`, `name`, `evidence`.
- `Prediction`: `run_id`, `k` (empty for whole-run predictions), `model` (baseline, behaviour view or supervised predictor), `score`, `fold`.

The public trace format was verified on the pinned revision: 52,104 trials, of which 34,462 have steps and 34,397 have at least one agent step, and the rest are dropped from the run and step tables but counted in `results/dataset_summary.json`.
A tool's command is a string, a list or a placeholder, and ingest normalizes all three.
Ingest writes `data/runs.parquet` and `data/steps.parquet` (gitignored), where the run table keeps the outcome for the feasibility counts, and the exporter never writes it before the freeze.
The exporter writes `results/site.json` from a fixed sample of 60 runs chosen by the hash of the run id, and `results/dataset_summary.json` records the pinned revision, file checksums, trial counts, and the model and scaffold combinations with their counts of tasks with mixed outcomes and the combinations the PRD selection rule chooses.

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
