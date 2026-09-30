# Agent Footsteps

Discovering AI agent behaviours from their footsteps, early enough to flag failing runs.

An experiment that groups the footsteps of LLM agents into named behaviours, checks the names against behaviours planted with prompts, and tests whether those behaviours flag failing runs early.
A footstep is one action an agent takes in a run, such as running a command, and a run is one attempt at a task.

Status: scoped and documented, not built yet.
No results exist yet, and the commands below are planned until phase 0 of the plan lands.

## Quickstart

Planned, and unverified until the code exists.

```text
make setup
make reproduce
make start
```

`make reproduce` downloads the public dataset at a pinned revision into `data/`, which is not committed, then regenerates the tables and the site data with no model calls and no cost.
`make start` serves the site in the foreground until you press Ctrl-C.
`make` alone prints the list of targets, and the targets that use model credit are separate and warn before they run.

Requires: `uv`, Node.js, and `make`, plus network access to Hugging Face for the first `make reproduce`.
The optional planted-demo and labeling stages also need Claude Code logged in to a personal plan.

## Docs

- [PRD](docs/PRD.md): product scope
- [Architecture](docs/ARCHITECTURE.md): system design
- [Plan](docs/PLAN.md): build order
- [Prior Work](docs/PRIOR_WORK.md): what exists and what this project claims
- [ADRs](docs/adr/): architecture decisions
- [Agent Instructions](AGENTS.md): workflow for coding agents

## Testing

Planned: `make lint` and `make test`.

## License

MIT, planned as a `LICENSE` file in phase 0 of the plan.
The public benchmark data is downloaded at run time, is never committed, and keeps its own license.
