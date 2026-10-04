# ADR-0006: Publish Results as a Static Site Fed by One JSON File

> Amended 2026-10-04: the site is not deployed to GitHub Pages. Readers clone the repo and run `make start`. The static design, the one JSON file and the rest of this decision stand, and the Pages references below record the original plan.

## Status

Accepted

## Context

The outcome is easier to understand when a reader can click a point and see the run it belongs to.
Static charts cannot show that link, and a live application would need a server and model calls.
The analysis and the site should be able to change independently.

## Decision

The exporter writes one sampled JSON file with coordinates, run, task, condition, outcome, state, behaviour name, tool and result status for each sampled step, plus the state names.
The JSON never contains raw command or output text or any steering text.
A static React page, built with Vite, TypeScript, Tailwind CSS and shadcn/ui and published on GitHub Pages, reads only that file.
It shows a point cloud and a colored timeline that are linked, and all numbers come from the JSON.
The site is built as a vertical slice from phase 1, starting with run ribbons colored by tool category and result status, and each later phase adds one element to it.
By default the JSON and the page contain no pass or fail outcome until the git tag `prereg` exists, so that looking at the data cannot steer the pre-registered analysis. The exporter checks for the tag and does not block anything else.
The site runs locally until the final phase, and nothing is published to GitHub Pages before the dataset license has been checked.
The drawing library is chosen in phase 1 of the plan by comparing candidates against their documentation, and recorded in a new ADR.

## Consequences

- The site has no server and no cost beyond static hosting.
- The JSON contract is the boundary, so a different front end can replace the site.
- The page shows a sample, so its size must be kept small enough to load quickly.
- Every later phase can be checked by looking at the site, and the JSON shape and the drawing library are tested against real data in the first slice.
- The analysis starts later, because a minimal site comes first.

## Alternatives

- **Static charts only:** Rejected because they cannot show the link between a point and its run.
- **A live application with a backend:** Rejected because it adds a server and model calls for no gain on a fixed dataset.
