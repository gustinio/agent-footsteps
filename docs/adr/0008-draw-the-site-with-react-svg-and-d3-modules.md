# ADR-0008: Draw the Site with React SVG and Individual D3 Modules

## Status

Accepted

## Context

The site starts with run ribbons and later adds a point cloud and a timeline that are linked, as decided in [ADR-0006](0006-publish-results-as-a-static-site-fed-by-one-json-file.md).
The drawing approach has to work with React, draw a sampled set of shapes, and let a selection in one view highlight shapes in another.
The candidates were compared against their own documentation:

- **D3:** "a low-level approach built on web standards", used directly with SVG and Canvas, and "a suite of 30 discrete libraries" such as `d3-scale`, `d3-quadtree` and `d3-delaunay` that can be "used independently". Its documentation says it can be paired with React.
- **visx:** "a collection of reusable low-level visualization components" that uses d3 for the calculations and React for updating the DOM, with modular packages ("pick and choose the packages you need").
- **Observable Plot:** a library for visualizing tabular data in the grammar of graphics style, which produces SVG charts. The pages read did not describe React use or linked selection.
- **Apache ECharts:** renders with Canvas or SVG and is documented to handle large data. The pages read did not describe cross-chart linking or React use.

## Decision

React renders the page and draws each view as SVG elements.
Individual D3 modules are added in the phase that needs them, for example `d3-scale` for axes and `d3-delaunay` for picking the nearest point.
The first slice draws ribbons as plain SVG rectangles and needs no D3 module yet.
No chart framework is used, so the linked selection is ordinary React state shared by the views.

## Consequences

- There is no framework to fight when a view needs a custom shape or a link between views.
- Every shape is a DOM element, which is fine for the sampled data but would need Canvas if the sample grew to tens of thousands of shapes.
- Axes, legends and hover behaviour are written by hand.
- Only the D3 modules that are used reach the bundle.

## Alternatives

- **visx:** Rejected because it adds a wrapper layer over d3 that the page does not need for custom shapes.
- **Observable Plot:** Rejected because the documentation reviewed does not show linked selection between charts, and a selection shared across charts is the core need.
- **Apache ECharts:** Rejected because its documentation reviewed does not show cross-chart linking or React use, and it brings a large configuration surface for views that are mostly custom.
