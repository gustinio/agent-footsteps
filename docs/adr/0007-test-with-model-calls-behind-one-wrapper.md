# ADR-0007: Test with Model Calls Behind One Wrapper

## Status

Accepted

## Context

Results must be reproducible, and tests must not depend on a network, a subscription, or a model's mood.
A language model is used only to label a sample of steps and to act as the agent in the planted runs.
The model must never feed the features, the thresholds or the statistics.

## Decision

All labeling calls go through one wrapper that pins the prompt, caches the result by input, logs tokens, and refuses a call that would exceed the cost cap.
The deterministic stages (features, segmentation, evaluation, export) are tested with `pytest` on small fixtures.
Tests replace the wrapper with fixtures and never reach the network.
Targets that use a model are separate `make` targets that warn they use credit, and `make reproduce` never calls a model.

## Consequences

- A stranger can reproduce every table from the public dataset, downloaded at run time, and the committed text-free step table of the planted runs, without credentials.
- Cached labels make reruns cheap and stable.
- The wrapper is one more component to keep small and correct.

## Alternatives

- **Letting tests call the model directly:** Rejected because tests would cost money and vary between runs.
- **No cache:** Rejected because reruns would spend credit and labels could change between runs.
