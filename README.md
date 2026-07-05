# understandthispaper — paper equation explainer

A two-layer Claude agent that turns an arXiv link into a grounded, color-coded
equation explainer page:

1. **Retrieval/extraction layer** — fetch the paper (alphaXiv overview → arXiv HTML →
   full-text markdown → PDF last), extract candidate equations with their surrounding
   prose (exact LaTeX from arXiv HTML `alttext`, no math OCR).
2. **Deterministic visualization layer** — Claude outputs a **structured spec JSON**
   (never the final image); a bundled Python script renders the spec to standalone
   HTML with MathJax, color-coded spans, hover/click callouts, and cited evidence.

```
arXiv link
   │
   ▼
┌───────────────────────── equation-explainer agent (orchestrator) ─────────────────────────┐
│                                                                                            │
│  paper-fetch                equation-understanding             equation-visualizer         │
│  ───────────                ──────────────────────             ───────────────────         │
│  fetch_paper.sh      ──►    extract_equations.py        ──►    render_spec.py              │
│  hf_papers_search.sh        + Claude grounds symbols            (spec JSON → HTML,         │
│  (alphaXiv / arXiv HTML/      against paper sentences,           MathJax + CSS + SVG       │
│   HF papers API)              writes specs/<id>-<slug>.json      callouts, no model        │
│                                                                  drawing involved)         │
└────────────────────────────────────────────────────────────────────────────────────────────┘
   │
   ▼
output/<id>.html  — 4 panes: paper/source · colored equation · English cards · grounding
```

## Layout

```
.claude/
  agents/equation-explainer.md            orchestrator agent (invoke with @equation-explainer)
  skills/
    paper-fetch/                          SKILL.md + fetch_paper.sh, hf_papers_search.sh
    equation-understanding/               SKILL.md + spec.schema.json + extract_equations.py
    equation-visualizer/                  SKILL.md + render_spec.py (deterministic renderer)
specs/                                    spec JSONs written by equation-understanding
output/                                   generated HTML (build artifacts)
workspace/                                fetched papers (gitignored)
```

## Demo

An example spec for the core training objective of
[Beyond Language Modeling (2603.03276)](https://arxiv.org/abs/2603.03276) is included.
Render it:

```bash
python .claude/skills/equation-visualizer/scripts/render_spec.py \
  specs/2603.03276-unified-objective.json -o output/demo.html
```

Open `output/demo.html` in a browser (MathJax loads from CDN). Panes:

- **Left** — paper title, summary, where the equation comes from, raw LaTeX.
- **Center** — MathJax-rendered equation with color-coded spans; hover/click any piece.
- **Right** — one plain-English card per color, hover-synced with the equation, plus an
  intuitive analogy.
- **Bottom** — "why the model reads it this way": cited sentences from the paper tagged
  with the spans they support, a confidence bar, and the full symbol map with role
  badges (input / learned parameter / objective / hyperparameter / ...).

## End-to-end flow (live)

Paste an arXiv link and ask the `equation-explainer` agent to explain the paper's core
equation. It will:

1. `fetch_paper.sh <id>` — alphaXiv overview + arXiv HTML + metadata into `workspace/papers/<id>/`.
2. `extract_equations.py` — list block equations with context; pick the core one.
3. Ground each symbol in paper sentences (inputs vs. learned parameters vs. objectives
   vs. constraints vs. normalization) and write `specs/<id>-<slug>.json`.
4. `render_spec.py` — deterministic HTML build.

## Design rules

- **The model never draws the final visual.** All rendering goes through
  `render_spec.py` so output is correct, reproducible, and inspectable (the full spec
  is embedded in the page).
- **Grounding over summarization.** Every symbol interpretation must cite a nearby
  sentence; unsupported readings are labeled inference and lower the `confidence` score.
- **arXiv HTML before PDF.** LaTeXML keeps exact equation LaTeX; PDFs need math-aware
  OCR (v2: Nougat or similar).
