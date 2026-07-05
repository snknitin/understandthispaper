---
name: paper-fetch
description: Resolve an arXiv/alphaXiv link or id, fetch the paper from the best available source (alphaXiv overview, arXiv HTML, alphaXiv full-text markdown, PDF as last resort), and search Hugging Face Papers for related literature. Use as step 1 of the equation-explainer pipeline or whenever a paper needs to be pulled locally.
---

# Paper Fetch

Retrieval layer for the equation explainer. Everything lands in `workspace/papers/<id>/`.

## Step 1: Resolve the paper id

Accept any of: `arxiv.org/abs/...`, `arxiv.org/pdf/...`, `alphaxiv.org/abs/...`,
`alphaxiv.org/overview/...`, `huggingface.co/papers/...`, or a bare id like
`2603.03276` / `2603.03276v2`. The scripts extract the id with a regex; you don't need
to normalize by hand.

## Step 2: Fetch all sources

```bash
bash .claude/skills/paper-fetch/scripts/fetch_paper.sh <id-or-url> [outdir]
```

This tries, and reports hit/miss for each:

| Priority | Source | File | Why |
|---|---|---|---|
| 1 | `alphaxiv.org/overview/<id>.md` | `overview.md` | Structured AI report — fastest way to understand the paper. Same endpoint the `alphaxiv-paper-lookup` skill uses; prefer invoking that skill when you only need the overview in-context. |
| 2 | `arxiv.org/html/<id>` | `paper.html` | **Preferred equation source.** LaTeXML output keeps every equation's LaTeX in `<math alttext="...">` — no math OCR needed. |
| 3 | `alphaxiv.org/abs/<id>.md` | `fulltext.md` | Extracted full text as markdown; the PDF fallback when no HTML build exists. |
| 4 | `huggingface.co/api/papers/<id>` | `hf_meta.json` | Title, authors, abstract/summary, upvotes. |

Last resort is the raw PDF at `arxiv.org/pdf/<id>`. Plain PDF text extraction is weak on
math; if you must go there, flag it and treat recovered equations as low-confidence
(v2: a math-aware OCR stage such as Nougat).

## Step 3 (optional): Related literature via HF Papers

```bash
bash .claude/skills/paper-fetch/scripts/hf_papers_search.sh "unified multimodal pretraining"
```

Wraps `GET https://huggingface.co/api/papers/search?q=...` (there is no official HF
papers CLI; this REST endpoint is the real thing) and prints `id<TAB>title` lines.
Run one query per theme of the paper (architecture, representation, scaling, ...) for
good coverage.
