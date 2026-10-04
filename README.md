# Agent Footsteps

Discovering AI agent behaviours from their footsteps, early enough to flag failing runs.

An experiment that groups the footsteps of LLM agents into named behaviours, checks the names against behaviours planted with prompts, and tests whether those behaviours flag failing runs early.
A footstep is one action an agent takes in a run, such as running a command, and a run is one attempt at a task.

Status: the experiment is complete and the results are below.
`make reproduce` downloads the public data and writes `results/site.json` and `results/dataset_summary.json`, with no text, and with each run's pass or fail outcome only while the git tag `prereg` exists.
`make start` shows the site: one ribbon per sampled run, a linked point cloud, and the results next to their criteria.
The site is not published.
Clone the repo and run `make start`.

## Results

Every criterion was frozen in the [PRD](docs/PRD.md#acceptance-criteria) before the analysis, under the git tag `prereg`.
Q2, Q3a and Q4 are met, with Q4 met only weakly, and Q1 and Q3b are not met.
Ranges are 95% bootstrap ranges that resample tasks.

| Question | Criterion | Result | Verdict |
|---|---|---|---|
| Labeler bar | Cohen's kappa of at least 0.6 against the blind human sample | 0.71 on 150 steps | Met, so the LLM labels are used for Q1 |
| Q1: do the discovered behaviours match names a person would give | On unseen tasks the HMM's states agree with the step labels better than the GMM's and a majority baseline, by more than the range | NMI 0.21 for the HMM, 0.23 for the GMM, 0.00 for majority. HMM minus GMM is -0.02 (range -0.03 to -0.01), HMM minus majority is 0.21 (0.12 to 0.31) | Not met: the HMM beats the majority baseline, but the GMM agrees slightly better, so stickiness adds nothing here |
| Q2: does a planted behaviour show up as its own behaviour | The share of repeated shell commands rises with the instruction on at least 8 of 10 tasks, and the share of steps in the repeating state rises on at least 7 of 10 | Rose on 10 of 10 tasks (0% without, 25% to 58% with), and the repeating state's share rose on 10 of 10 | Met |
| Q3a: do failing runs follow different behaviour patterns | On whole runs the behaviour profile beats run length by more than the range and is within 0.05 AUROC of the supervised predictor | AUROC 0.62 against 0.50 for run length and 0.64 for the supervised predictor. The gain over run length is 0.12 (0.06 to 0.18) | Met |
| Q3b: would an early check have caught the failure | On the first 5, 10 and 15 steps the behaviour view beats counts so far by more than the range and is within 0.05 of the supervised predictor, at every k | AUROC 0.54, 0.54 and 0.51 against 0.49, 0.53 and 0.46 for counts so far. Every range on the difference includes zero, and the supervised predictor is more than 0.05 ahead at k = 15 | Not met |
| Q4: do behaviours hold on unseen tasks | AUROC and agreement drop by no more than 0.05 on unseen tasks | The drops are at most 0.00 for whole runs, and unseen scores are higher than seen ones at every k and for agreement | Met, but see the limits |

The natural arm is 411 runs from 57 tasks with mixed outcomes, drawn from the two selected combinations of the public Terminal-Bench trajectories (terminus-2 with gpt-5.1-codex and terminus-2 with gemini-3-flash-preview), and 47% of the runs fail.
The planted demo is 40 runs of Claude Code, with 2 runs per task and condition.
Model calls cost $6.74 of the $40 cap, with $4.00 for the planted runs and $2.74 for the labeler, as logged in `results/cost_log.jsonl`.

### Limits

- Q3a is a modest signal. An AUROC of 0.62 is better than run length and far from a reliable failure detector.
- Q3b fails: the behaviours from the first 5 to 15 steps did not flag failing runs early. Many runs are short, and only 361, 274 and 206 of the 411 runs have at least 5, 10 and 15 steps.
- Q4 passes in a weak way. The early scores are near 0.5 on both sides, so the pass shows that nothing was lost on unseen tasks and not that anything was learned. The agreement drop has a range from -0.17 to 0.05.
- Q1 is not met. Only 3 of the 8 HMM states got a name other than "mixed" ("thinking without a tool", "repeating" and "exploring"), and "repeating" fits the planted behaviour, which the features encode directly.
- The HMM's size was chosen at 8 states, the top of the 2 to 8 range, because held-out likelihood was still rising.
- Q2 is an easy test. The repeat behaviour is mechanical and artificial, and the features compute the repeat flag directly. Each task rests on two runs per condition.
- The planted demo has one model, one prompt and ten small custom tasks, and it is not a claim about other agents.
- Labels come from an LLM checked against 150 hand-labeled steps, not from a large human annotation.
- The natural data is two model and scaffold combinations from one benchmark, so nothing here says the result transfers to other benchmarks.

### Related work and licensing

[Prior Work](docs/PRIOR_WORK.md) lists what exists and what this project does and does not claim.
The public data is [yoonholee/terminalbench-trajectories](https://huggingface.co/datasets/yoonholee/terminalbench-trajectories), scraped from the [Terminal-Bench 2.0](https://www.tbench.ai/leaderboard/terminal-bench/2.0) leaderboard and declared Apache-2.0 at the pinned revision.
It is downloaded at run time and never committed, and the repo publishes only derived values and identifiers.

## Quickstart

```text
make setup
make reproduce
make start
```

`make reproduce` downloads the public dataset at a pinned revision into `data/`, which is not committed, then regenerates the tables and the site data with no model calls and no cost.
`make start` serves the site in the foreground until you press Ctrl-C, and prints the local address to open.
`make` alone prints the list of targets, and the targets that use model credit are separate and warn before they run.

The pre-registration tag `prereg` is not pushed to this remote, so a fresh clone has no tag and `make reproduce` leaves each run's pass or fail outcome out of `results/site.json`.
Every table is the same either way.
To get the committed `site.json` including outcomes, create the tag at the commit that merged the freeze before reproducing: `git tag prereg 4ecdc55`.
The author's own tag sits on the pre-merge commit of that change, which only exists on the `feat/freeze-prereg-7` branch.

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

`make lint` and `make test`.

## Process

Scoped and built with [sidekitten](https://github.com/gustinio/sidekitten), my workflow for turning a plan into small, reviewed issues shipped with coding agents.

## License

MIT, see [LICENSE](LICENSE).
The public benchmark data is downloaded at run time, is never committed, and keeps its own license.
