---
name: equation-visualizer
description: Deterministically render an equation-explainer spec JSON into a standalone four-pane HTML page (MathJax equation with color-coded spans, plain-English cards, hover/click callouts, grounding quotes and confidence). Use as the final step of the equation-explainer pipeline, after equation-understanding has written the spec.
---

# Equation Visualizer

The rendering layer. **The model never draws the final visual** — it writes a spec, and
this script turns the spec into HTML. That keeps rendering correct, inspectable, and
reproducible, and keeps the renderer's code out of context (you only run it).

## Usage

```bash
python .claude/skills/equation-visualizer/scripts/render_spec.py specs/<file>.json -o output/<name>.html
```

Input: a spec conforming to `../equation-understanding/spec.schema.json`.
Output: a standalone HTML file (MathJax from CDN; no build step, no server needed —
opening the file directly works).

## What it renders

| Pane | Content |
|---|---|
| Left | Paper title, summary, equation source location, raw LaTeX |
| Center | MathJax-rendered equation; each `color_span` becomes a colored, hoverable region; plain-English paragraph below |
| Right | One card per color span (chip + label + explanation) synced with the equation, plus the intuitive analogy |
| Bottom | Grounding quotes with span tags, confidence bar + notes, full symbol map with role badges |

Interactions: hovering a card highlights the matching equation region (and vice versa)
and shows its callout with an SVG connector line; click pins, click again (or click
elsewhere) unpins. The full spec is embedded in the page (`<script id="spec">`) for
inspectability.

## Mechanics you must respect when writing specs

- Each `latex_fragment` is wrapped as `\class{eqspan-<id>}{\textcolor{<color>}{...}}`
  by **first-occurrence string replacement, longest fragment first**. Fragments must be
  verbatim substrings of `equation_latex` and must not overlap; violations print
  warnings and the script exits with code 2.
- MathJax is loaded with the `html` + `color` TeX packages (needed for `\class` /
  `\textcolor`). Don't use other nonstandard packages in `equation_latex`.
- If the page is opened offline, a fallback banner points to the raw LaTeX pane.

## If the output looks wrong

Fix the **spec** (or, for layout bugs, this script) and re-run. Never hand-edit the
generated HTML — it is a build artifact.
