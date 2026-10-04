# Prior Work

This page records what existing work covers, what this project redoes, and what it claims.
It was compiled on 2026-09-30 from abstracts, summarized full-text fetches and repository pages, so quoted details are secondhand and the absence claims mean "not found in this search", not "proven absent".
The load-bearing entries were checked against the papers on 2026-10-04, as listed under Verification.

## What Exists

| Piece of the plan | Already exists | Status here |
|---|---|---|
| Early failure prediction from partial runs | EarlyEval (arXiv 2609.02783, code at github.com/inphotoo/earlyeval), PrefixGuard (2605.06455), Monitoring Web Agents (2609.02057), Fail-Fast Restart-Smart (2608.03222), AgentForesight (2605.08715) | Used only as a benchmark comparison, not claimed |
| Length or duration baseline | Fail-Fast Restart-Smart (a "Duration" control) | Adapted: run length for finished runs, counts so far for the first k steps |
| Cross-validation grouped by task | Monitoring Web Agents (by task), Fail-Fast (by instance) | Reproduced |
| Repeated seeds per task | Fail-Fast (11 seeds per instance) | Not claimed |
| Interpretable behaviour features | Monitoring Web Agents (31 macro features), EarlyEval (a behavioural feature family of activity counts, last-step properties and event timing, plus textual and reference-solution features) | The specific feature set is new here, the idea is not |
| Unsupervised states or behaviours from traces | Automata from Agent Traces (2608.23670, paper only), ATLAS (2608.14352), Hodoscope (2604.11072), AutoTraceGT (2608.30391), Insights Generator (2605.21347) | The idea is not claimed |
| Point-cloud view of agent steps | Hodoscope (MIT), using LLM-summary embeddings and t-SNE | Not claimed; this study uses behavioural features and named behaviours |
| Counterfactual prompt edits to explain behaviours | CHIVE (alignment.anthropic.com/2026/chive) | Closest existing use of prompt edits; only its title and existence were checked, so it is not claimed to differ beyond what the table says |
| Step-level error labels | TRAIL, AgentRx, AgentErrorBench (AgentErrorTaxonomy), MAST | Vocabulary borrowed in part; none labels behaviours in passing runs |

## What This Study Adds

- Validating discovered behaviour names against behaviours planted with prompts, with an existence check and an exploratory dose trend. No paper found does this.
- An HMM over handcrafted per-step behavioural features. No public repo or paper found applies an HMM to agent steps.
- Colored timelines of segmented behaviour linked to a behaviour point cloud, with points colored by validated names.
- The design combination: task-grouped folds on tasks with mixed outcomes, run-length and counts-so-far baselines, a whole-run trajectory analysis before the early check, and a prefix defined as the first k steps to avoid leaking run length.

## Verification

Checked on 2026-10-04 against the arXiv abstracts and full texts, and the repository license pages:

- Confirmed: Fail-Fast has a supervisor-free Duration control and trains on seeds 0 through 10 of one policy, which is 11 seeds per instance. Monitoring Web Agents has 31 Macro features and five-fold cross-validation split by task. Hodoscope embeds LLM action summaries and projects with t-SNE, and its repository (AR-FORUM/hodoscope) is MIT. EarlyEval's repository exists and is MIT. All ten arXiv ids in the table resolve to papers with the titles and topics given above.
- Corrected: the earlier "115 behavioural features" for EarlyEval was not found in its feature table, which groups features into behavioural, textual and reference-solution families, so the count is no longer stated.
- Not confirmed: the CHIVE post was not read in full, and the absence claims in the table still mean "not found in this search".

## Wording Rules

Never write "first to predict failure early", "first to discover agent behaviours", "first interpretable states", or "first point-cloud view of agent runs".
Write "validated the names using behaviours planted with prompts" and "compared an interpretable view with run-length and counts-so-far baselines and a trained predictor".
Cite every paper, tool and dataset this project uses or builds on, and describe closely related work as the table above does.
Update the table when new related work is found.

## Datasets

- yoonholee/terminalbench-trajectories on Hugging Face: natural runs with a verifier reward, 52,104 trajectories over 89 tasks, 26 agent scaffolds and 49 models, with typically 5 trials per task and agent.
- Its steps hold `src`, `msg`, `tools` (function and command) and `obs` (output truncated to 5,000 characters), with tokens and time recorded per trial and not per step.
- Its dataset card declares Apache-2.0 and says the trajectories "were scraped from tbench.ai using the publicly available leaderboard data".
- The card states no further usage restrictions and no citation requirement, the tbench.ai front page shows no terms or data policy, and the upstream Terminal-Bench code repository is Apache-2.0. These were read on 2026-09-30.
- The uploader is not the original producer, so the declared license covers the compilation and does not settle the rights over other parties' agent outputs, and the terms of the model providers on redistributing outputs were not checked.
- TRAIL (MIT) and AgentRx (CC-BY-4.0): human step-level annotations, useful for borrowing vocabulary.
- Policy: no third-party data is committed, the data is downloaded at run time from a pinned revision, and the project publishes only derived values and identifiers, never raw command text, output text, reasoning text or steering text.
- Attribution: credit the dataset and Terminal-Bench in the README.
- This is a reading of the public pages and not legal advice, and the finding was confirmed again on 2026-10-04: at the pinned revision the card still declares Apache-2.0, still says the trajectories were scraped from the public leaderboard, and still states no further restrictions, and the upstream Terminal-Bench repository is still Apache-2.0. Nothing is published beyond derived values, and the site is not deployed.
