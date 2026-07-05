---
name: equation-understanding
description: Extract candidate equations from a fetched paper and produce a grounded explanation spec (symbol map, color spans, plain-English reading, analogies, cited evidence, confidence). Use as step 2-3 of the equation-explainer pipeline, after paper-fetch. Output is a spec JSON, never a drawn visual.
---

# Equation Understanding

Turns a fetched paper into a **spec JSON** that the equation-visualizer renders. The
contract: you do the interpretation, the renderer does the drawing. Never emit HTML/SVG
from this skill.

## Step 1: Extract candidate equations

If `workspace/papers/<id>/paper.html` exists (arXiv LaTeXML build):

```bash
python .claude/skills/equation-understanding/scripts/extract_equations.py workspace/papers/<id>/paper.html
```

This prints block equations as JSON (`latex`, `context` = surrounding prose). arXiv HTML
keeps the original LaTeX in `alttext` attributes, so no math OCR is involved.

If only `fulltext.md` exists, grep for display math (`$$...$$`, `\[...\]`, `\begin{equation}`).
If only the PDF exists, treat any recovered equation as low-confidence and say so in the
spec's `confidence.notes`.

## Step 2: Pick the equation

Default to the paper's core equation — training objective, main theorem, headline
formula — unless the user pointed at a specific one. Record the choice and where it
appears (`equation.source.location`).

## Step 3: Ground every symbol (this is the point of the skill)

For the chosen equation, answer from the paper text — not from generic math intuition:

1. **What does each symbol refer to in this paper?** (`symbol_map[].meaning`)
2. **What role does it play?** One of: `input`, `learned_parameter`, `objective`,
   `constraint`, `normalization`, `hyperparameter`, `index`, `operator`, `output`.
   (`symbol_map[].role`)
3. **Which neighboring sentences justify this reading?** Quote or closely paraphrase
   them (`symbol_map[].grounding_sentence`, plus paper-level `source_quotes`).

If the text doesn't support an interpretation, mark it as inference in the explanation
and lower `confidence.score`. Never fabricate a quote.

## Step 4: Emit the spec

Write to `specs/<id>-<slug>.json`, conforming to
[spec.schema.json](spec.schema.json). Key constraints the renderer relies on:

- `color_spans[].latex_fragment` must be a **verbatim substring** of `equation_latex`,
  and spans must not overlap or nest. 3-6 spans is the sweet spot.
- Pick colors with good contrast on white; the demo palette is
  `#2563eb #d97706 #7c3aed #dc2626 #059669 #0891b2`.
- `plain_english_explanation`: one paragraph a smart non-specialist can follow.
- `intuitive_analogy`: one concrete everyday analogy; name what maps to what.
- `callout_boxes`: one per span id, 1-3 sentences, shown on hover.
- `confidence`: 0-1 score + notes on what was reconstructed vs. read verbatim, and what
  would raise the score (e.g. "re-ground against arXiv HTML eq. (3)").

Validate before handing off: every `callout_boxes[].anchor_span` and
`source_quotes[].supports[]` entry must be an existing span id, and every fragment must
be found in `equation_latex` (the renderer warns, but fix it here).
