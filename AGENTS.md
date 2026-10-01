# Agent Instructions

An experiment that groups LLM agent steps into named behaviours, checks the names against behaviours planted with prompts, and tests whether those behaviours flag failing runs early.

Read before making changes:

1. [PRD.md](docs/PRD.md): product scope and acceptance criteria
2. [ARCHITECTURE.md](docs/ARCHITECTURE.md): system boundaries
3. [PLAN.md](docs/PLAN.md): implementation order
4. Relevant files in [ADRs](docs/adr/)

## Development Workflow

For every change:

1. Identify the relevant requirement and affected boundary.
2. Implement the smallest complete change.
3. Add or update tests with the implementation.
4. Run the relevant focused tests, then `uv run ruff check .` and `uv run pytest`.
5. Verify affected user-visible behavior manually when it changes.
6. Update this file if commands, layout, or workflow conventions change.
7. Update documentation if behavior, scope, or architecture changed.

Keep the system runnable after every change.

## Commands

The Makefile targets and `footsteps` CLI exist from phase 0, and `ingest`, `export`, `tasks`, `runner` and `evaluate` are implemented, `segment` is implemented too, but the other stage subcommands still report "not implemented yet". `evaluate` so far holds only the Q2 manipulation check and the interim stop rule.

- `uv run footsteps <stage>`: run one pipeline stage
- `uv run footsteps ingest --pilot <transcript>...`: reduce Claude Code transcripts to step facts and print the step table, without downloading
- `uv run footsteps tasks`: self-test the custom demo tasks, where each reference solution must pass its checker and an empty attempt must fail it
- `uv run footsteps runner [--tasks N]`: make the planned planted runs that are not yet recorded (uses model credit), or only those of the first N tasks
- `uv run footsteps segment`: fit the HMM and GMM on the natural runs and write the state of every step to `results/segmentation.parquet`, with no model calls
- `uv run footsteps evaluate`: print the repeat share per task and condition, the interim stop rule and the manipulation check
- `uv run ruff check .`: lint
- `uv run pytest`: run tests
- `uv run ruff format --check .`: check formatting
- `make`: print the list of targets
- `make lint`: lint Python and the site
- `make test`: run the Python tests
- `make reproduce`: download the public data at its pinned revision, then ingest, segment and export with no model calls
- `make start`: run the site's dev server in the foreground, stopped with Ctrl-C
- `make build`: build the site for production into `web/dist/`
- `make clean`: remove build output and caches, but never downloaded data, raw transcripts or results
- `make run-demo` (or `make run-demo TASKS=3`) and `make label`: use model credit, so run them only when intended
- `npm ci`, `npm run lint`, `npm run build` inside `web/`: site install, lint and build

## Doc Locations

- PRD: `docs/PRD.md`
- Architecture: `docs/ARCHITECTURE.md`
- Plan: `docs/PLAN.md`
- ADRs: `docs/adr/`
- Issue template: `.github/ISSUE_TEMPLATE/sidekitten.md`
- PR template: `.github/pull_request_template.md`

## Branch Base

- `main`

## Repository Layout

```text
agent-footsteps/
├── AGENTS.md
├── README.md
├── pyproject.toml
├── Makefile
├── docs/            PRD, ARCHITECTURE, PLAN, PRIOR_WORK, adr/
├── src/footsteps/   one module per stage: ingest.py, tasks.py, runner.py, features.py, segment.py, label.py, evaluate.py, export.py, cli.py
├── tasks/           the custom demo tasks: one folder each with prompt.md, setup.sh, check.sh, solution.sh and optional files/
├── tests/           pytest tests for the deterministic stages
├── data/            downloaded public data and raw transcripts (all gitignored)
├── results/         final tables, labels, cost log, planted-run step table and site.json (committed, no raw text)
├── web/             Vite app: src/, public/
└── .github/         issue and PR templates, CI workflow
```

Structure starts flat, with one module per stage, and becomes subfolders only when a stage outgrows one file.

## Architecture Rules

- Ingest normalizes source formats and computes the step facts (tool category, result status, command hash, verification flag) from the text and then discards it, and it must not compute sequence-level features or labels.
- The runner enforces the cost cap and must not read results or stop based on them.
- Features read the step facts only and must never read raw text, the system prompt, the steering text, or a label, and public and planted runs share one schema.
- The segmenter clusters in the original feature space and never in the 2D projection.
- The LLM never sees the steering prompt or the condition, and labels never flow back into features or the segmenter.
- The evaluator owns every threshold and reads it from one place, and it must not use a model.
- The exporter never writes raw command text, output text or steering text into the JSON, and it writes the outcome only when the `prereg` tag exists (option B in the PRD: a default, not a hard block).
- The site computes nothing and every number it shows comes from the JSON.
- Only the LLM wrapper calls a model for labeling.

## Code Style

- Match the surrounding file's conventions: naming, comment density, module structure.
- Comments explain why, never restate what.
- No dead code or half-built public surface.
  Document future work in the project's docs, don't ship it as an unreachable stub.
- Avoid unrelated edits.
  Preserve comments that explain non-obvious behavior.
- Files end with a newline.

## Testing Rules

- Tests never call a model or the network, and they replace the LLM wrapper with fixtures.
- A pre-registered threshold changes only through a dated note in the PRD.

## Scope Discipline

Prefer a narrow, complete implementation over additional features.
If time is limited, cut in the order given in [PLAN.md](docs/PLAN.md#cut-order).

## Documentation

- Do not duplicate product requirements in this file.
- Record new architectural decisions in `docs/adr/`.
- Update the PRD when product scope changes.
- Update ARCHITECTURE.md when boundaries or dependencies change, and its Data Model section whenever the actual entities, fields, or relationships turn out to differ from or go beyond what's documented.
  This happens routinely during implementation, not just when a modeling decision is deliberately revisited, and it drifts silently if it's only updated on purpose.
- Update PLAN.md when implementation order or status changes.
