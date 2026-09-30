# ADR-0003: Label Agent Behaviours

## Status

Accepted

## Context

To check that a discovered group means what it is named, some steps need trusted labels.
Public datasets with step-level annotations were checked: TRAIL, AgentRx and AgentErrorBench label errors in mostly failed runs, and none found labels behaviours in passing and failing runs with repeated trials.
Some proposed labels, such as repeating and recovering from an error, are facts about a step and not behaviours.

## Decision

Labeling has two layers and is used only to check discovered behaviours, never to build them.
The first layer is facts computed by rules: the step repeats an earlier command, follows an error, has no tool call, or is the last step.
The second layer is one of four intents: explore, modify, verify, or other.
An LLM assigns intents on a sampled subset of about 2,000 steps and never sees the steering prompt or the condition.
The author labels a shuffled sample of 100 to 200 steps by hand, drawn across the discovered states and rule facts and including steps from held-out tasks, with the run, task and condition hidden, and the LLM is trusted for the rest only if agreement with that sample is at least 0.6 on Cohen's kappa.
Names such as wandering or guessing are given to discovered behaviours from their evidence and are not labels.

## Consequences

- The human sample is the ruler for every claim about what a behaviour means.
- The LLM stage costs credit, so it draws only on a reserve fixed before the planted runs, and its sample shrinks to fit that reserve and never takes budget from the runs.
- A small sample gives wide agreement ranges, which the write-up reports.

## Alternatives

- **Labeling everything with an LLM alone:** Rejected because its labels could not be checked.
- **Reusing a public taxonomy as is:** Rejected because those taxonomies describe errors in failed runs, not behaviours in all runs.
