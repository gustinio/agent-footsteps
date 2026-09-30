# ADR-0002: Features Describe Agent Behaviour

## Status

Accepted

## Context

The idea comes from recognizing what an object is doing in video from its motion and not its appearance.
For an agent the appearance is the text of a step, and the motion is what changes from step to step: which tool, whether a command repeats, whether a result is checked.
Text-based tools already exist for agent transcripts, and text can also leak the instruction being tested into the features.

## Decision

Ingest computes per-step facts from the text and then discards the text: the tool category, the result status, a hash of the normalized command, and a rule-based verification flag.
Features are behavioural summaries of those facts: a repeat flag from command hashes seen earlier in the run, the recent error history, and the tool category and verification flag of a step and its neighbours.
The feature code reads the step facts only, so it has no access to raw text, the system prompt or the steering text.
Public and planted runs share one feature schema.
Text embeddings are an optional extra comparison, not the main method.

## Consequences

- The behaviours found cannot be explained by the planted instruction's wording.
- The features must be defined so that tool names from different agent scaffolds map to the same categories, which needs a mapping that the feasibility spike verifies.
- The step facts hold no raw text, so the repeat flag, the verification flag and the committed planted-run table can be recomputed and published without it.
- Behaviours that only differ in what is said, and not in what is done, are invisible.

## Alternatives

- **Text embeddings as the main features:** Rejected because existing tools such as Hodoscope already do this and the text could leak the steering prompt.
- **Raw tool names:** Rejected because different scaffolds use different names for the same action.
