# ADR-0001: Group Steps with a Sticky HMM on Original Features

## Status

Accepted

## Context

The project needs to group agent steps into behaviours without being told the groups in advance.
Behaviours last for stretches of steps, so a method that ignores step order throws away information.
A 2D picture of the steps distorts distances, so groups found in the picture can be artifacts of the projection.

## Decision

Use a sticky hidden Markov model (HMM), which prefers to stay in the same behaviour across neighbouring steps, and compare it with a Gaussian mixture model (GMM) that assigns each step on its own.
Both are fit on the real feature values.
The 2D projection is used only to draw the point cloud and never for clustering.
The number of HMM states is chosen from 2 to 8 by held-out likelihood on training tasks.
The `hmmlearn` API and how to express stickiness must be verified against its documentation before implementation.

## Consequences

- The comparison shows whether step order adds anything, and either answer is publishable.
- Verified against `hmmlearn` 0.3.3: `transmat_prior` takes a full matrix of Dirichlet weights, so stickiness is a larger weight on the diagonal and needs no custom prior. The library applies its minimum variance only at initialization, so a four-line subclass floors the variances after every update to stop a state collapsing onto a 0 or 1 flag.
- Behaviours are limited to what the features can express.

## Alternatives

- **K-means:** Rejected because it assumes round groups and ignores step order.
- **HDBSCAN:** Rejected for the MVP because it adds a second comparator without answering the stickiness question, and stays an extra if time remains.
- **Clustering the 2D projection:** Rejected because projection distortion creates false groups.
