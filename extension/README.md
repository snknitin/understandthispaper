# Understand This Paper — browser extension (v0, BYOK)

MV3 Chrome extension: open any arXiv paper tab → toolbar button → a new tab with the
color-coded, grounded equation explainer. The LLM makes exactly one grounded call per
paper (plus ≤2 bounded repair calls if output fails the deterministic validator);
fetching, extraction, validation, rendering, and related-papers are plain code.

## Load and test it (2 minutes)

1. Chrome → `chrome://extensions` → toggle **Developer mode** (top right).
2. **Load unpacked** → select this `extension/` folder.
3. Click the extension icon → **See a demo** — the bundled GRPO sample renders
   instantly with no network and no key (this proves MathJax bundling + the viewer).
4. For the real pipeline: icon → **Settings**, pick a provider, model, and key:
   - Anthropic: base `https://api.anthropic.com`, model e.g. `claude-sonnet-5`
   - OpenRouter: base `https://openrouter.ai/api/v1`, any model it serves
   - Local Ollama: base `http://localhost:11434/v1`, model e.g. `qwen2.5:32b`, no key
5. Open an arXiv abs/html page (2024+ papers have HTML builds — try
   `arxiv.org/abs/2412.03572`) → icon → **Explain equations on this page**.
   A viewer tab opens immediately and shows pipeline progress; results are cached
   locally, so reopening the same paper is instant and free.

## Architecture

```
popup.js ── explain(tabUrl) ──► sw.js (service worker)
                                 │ fetch arXiv HTML + alphaXiv overview + HF meta
                                 │ lib/extract.js   (exact LaTeX from alttext, no OCR)
                                 │ lib/prompt.js    → lib/providers.js (ONE llm call)
                                 │ lib/validate.js  (hard gate; ≤2 repair rounds)
                                 │ HF related-papers fetch (service worker: no CORS)
                                 ▼
                       chrome.storage (cache:1:<id>, job:<id>)
                                 ▼
viewer.html + viewer.js  (DOM renderer, bundled MathJax, tabs/panes/callouts)
```

- `lib/extract.js` and `lib/validate.js` mirror the Python scripts under
  `.claude/skills/` — change rules in both places.
- `mathjax/` is bundled (MV3 forbids remote code); `[tex]/html` extension included
  for `\class`.
- `sample/sample_data.js` powers `viewer.html?demo=1` and standalone dev
  (`python -m http.server 8741 --directory extension` → `/viewer.html?demo=1`).

## Store upload (when ready)

Zip the contents of this folder (manifest at zip root), upload at the
[Chrome Web Store developer dashboard](https://chrome.google.com/webstore/devconsole)
($5 one-time registration), publish **Unlisted** first, install from the store link
yourself, then flip to Public. You'll need real icons (current ones are
placeholders), 1–5 screenshots, a privacy policy URL, and permission justifications.

## Not in v0 (by design)

Hosted backend with free-tier quotas + Stripe/Paddle entitlements, shared spec cache,
per-equation in-page buttons, PDF-only (pre-2024) papers, dark mode.
