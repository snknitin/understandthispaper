#!/usr/bin/env python3
"""Deterministic renderer: equation-explainer spec JSON(s) -> standalone HTML.

The model never draws the final visual. It emits one spec per equation (see
../../equation-understanding/spec.schema.json); this script turns the spec(s) into a
four-pane page — paper/source (left), MathJax equation with color-coded spans (center),
per-color plain-English cards (right), grounding quotes + confidence (bottom) — with
hover/click sync between panes and SVG-arrow callouts.

Passing multiple specs (same paper, one per equation) renders one page with a tab bar:
each tab shows the full four-pane layout for that equation. Paper title/summary come
from the first spec.

Usage:
    python render_spec.py specs/<eq1>.json [specs/<eq2>.json ...] -o output/demo.html
"""
import argparse
import copy
import html
import json
import sys
from pathlib import Path

ROLE_COLORS = {
    "input": "#0e7490", "learned_parameter": "#7c3aed", "objective": "#b91c1c",
    "constraint": "#a16207", "normalization": "#4d7c0f", "hyperparameter": "#c2410c",
    "index": "#6b7280", "operator": "#6b7280", "output": "#1d4ed8",
}


def esc(s: str) -> str:
    return html.escape(str(s), quote=True)


def wrap_spans(latex: str, spans: list, warn) -> str:
    """Wrap each span's fragment in \\class (coloring happens in CSS — a raw '#hex'
    inside \\textcolor is a TeX error). First occurrence only; longest fragments first
    so a short fragment can't steal a longer one's text."""
    for a in spans:
        for b in spans:
            if a["id"] != b["id"] and a["latex_fragment"] in b["latex_fragment"]:
                warn(f"span '{a['id']}' fragment is contained in span '{b['id']}' — spans must not overlap")
    for span in sorted(spans, key=lambda s: -len(s["latex_fragment"])):
        frag = span["latex_fragment"]
        if frag not in latex:
            warn(f"span '{span['id']}': fragment not found verbatim in equation_latex — skipped")
            continue
        wrapped = "\\class{eqspan-%s}{%s}" % (span["id"], frag)
        latex = latex.replace(frag, wrapped, 1)
    return latex


def build_span_css(spans) -> str:
    rules = []
    for s in spans:
        rules.append(f'  .eqspan-{s["id"]} {{ color: {s["color"]}; }}')
        rules.append(f'  .card[data-span="{s["id"]}"] {{ border-left-color: {s["color"]}; }}')
    return "\n".join(rules)


def build_legend(spans):
    cards = []
    for s in spans:
        cards.append(
            f'<div class="card" data-span="{esc(s["id"])}" tabindex="0">'
            f'<div class="card-head"><span class="chip" style="background:{esc(s["color"])}"></span>'
            f'<span class="card-label">{esc(s["label"])}</span></div>'
            f'<p class="card-body">{esc(s["explanation"])}</p></div>'
        )
    return "\n".join(cards)


def build_symbol_table(symbol_map):
    rows = []
    for s in symbol_map:
        role = s.get("role", "operator")
        badge = f'<span class="role" style="background:{ROLE_COLORS.get(role, "#6b7280")}1a;color:{ROLE_COLORS.get(role, "#6b7280")}">{esc(role.replace("_", " "))}</span>'
        ground = esc(s.get("grounding_sentence", ""))
        rows.append(
            f'<tr><td class="sym">\\({esc(s["symbol"])}\\)</td>'
            f'<td>{esc(s["meaning"])}{f"<div class=ground>&ldquo;{ground}&rdquo;</div>" if ground else ""}</td>'
            f'<td>{badge}</td></tr>'
        )
    return "\n".join(rows)


def build_quotes(quotes):
    out = []
    for q in quotes:
        supports = "".join(f'<span class="qtag" data-span="{esc(s)}">{esc(s)}</span>' for s in q.get("supports", []))
        loc = f'<span class="qloc">{esc(q["location"])}</span>' if q.get("location") else ""
        out.append(f'<blockquote>&ldquo;{esc(q["quote"])}&rdquo; {loc} {supports}</blockquote>')
    return "\n".join(out)


PANEL_TEMPLATE = """<div class="eqpanel__ACTIVE__" id="panel-__IDX__">
<main>
  <section class="pane left-pane">
    <h2>Paper &amp; source</h2>
    <div class="summary">__SUMMARY__</div>
    <div class="loc">__EQ_LOCATION__</div>
    <div class="srcbox">__RAW_LATEX__</div>
  </section>
  <section class="pane center-pane">
    <h2>Equation</h2>
    <div class="eqname">__EQ_NAME__</div>
    <div class="equation">\\[__WRAPPED_LATEX__\\]</div>
    <div class="hint">hover or click any colored piece — or a card on the right</div>
    <div class="aside"><span class="k">Plain English</span>__PLAIN_ENGLISH__</div>
    <svg class="callout-svg"><line x1="0" y1="0" x2="0" y2="0" stroke="#111827" stroke-width="1.5" stroke-dasharray="4 3"/></svg>
    <div class="callout"></div>
  </section>
  <section class="pane right-pane">
    <h2>What each color means</h2>
    __LEGEND_CARDS__
    <div class="aside"><span class="k">Intuition</span>__ANALOGY__</div>
  </section>
</main>
<section class="bottom">
  <div class="pane">
    <h2>Why the model reads it this way (grounding)</h2>
    <div class="conf">
      <div class="confbar"><div style="width:__CONF_PCT__%"></div></div>
      <span class="num">__CONF_SCORE__</span>
      <span class="notes">__CONF_NOTES__</span>
    </div>
    __QUOTES__
    <h2 style="margin-top:16px">Symbol map</h2>
    <table class="symbols">__SYMBOL_ROWS__</table>
  </div>
</section>
</div>"""


TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__ — equation explainer</title>
<script>
window.MathJax = {
  loader: { load: ['[tex]/html'] },  // the class macro lives here; it is NOT autoloaded
  tex: { inlineMath: [['\\\\(', '\\\\)']], displayMath: [['\\\\[', '\\\\]']],
         packages: { '[+]': ['html'] } },
  chtml: { scale: 1.15 }
};
</script>
<script id="mathjax-cdn" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js"></script>
<style>
  :root { --border:#e5e7eb; --ink:#111827; --muted:#6b7280; --bg:#f8fafc; --card:#ffffff; }
  * { box-sizing: border-box; }
  body { margin:0; font-family: ui-sans-serif, system-ui, "Segoe UI", sans-serif; color:var(--ink); background:var(--bg); }
  header { padding:16px 24px; background:var(--card); border-bottom:1px solid var(--border); }
  header h1 { margin:0 0 4px; font-size:18px; }
  header .meta { color:var(--muted); font-size:13px; }
  header .meta a { color:#2563eb; text-decoration:none; }
  #eqtabs { display:flex; gap:8px; flex-wrap:wrap; padding:10px 24px 0; }
  #eqtabs button { border:1px solid var(--border); border-bottom:none; background:#f1f5f9; color:#334155;
                   font:inherit; font-size:13px; font-weight:600; padding:8px 16px; border-radius:8px 8px 0 0; cursor:pointer; }
  #eqtabs button.active { background:var(--card); color:var(--ink); box-shadow:0 -2px 0 #2563eb inset; }
  #eqtabs button:hover:not(.active) { background:#e2e8f0; }
  .eqpanel { display:none; }
  .eqpanel.active { display:block; }
  main { display:grid; grid-template-columns: 300px 1fr 340px; gap:16px; padding:16px 24px; align-items:start; }
  .pane { background:var(--card); border:1px solid var(--border); border-radius:10px; padding:16px; min-width:0; }
  .pane h2 { margin:0 0 10px; font-size:12px; text-transform:uppercase; letter-spacing:.06em; color:var(--muted); }
  .left-pane .summary { font-size:13.5px; line-height:1.55; color:#374151; }
  .left-pane .srcbox { margin-top:12px; background:#0f172a; color:#e2e8f0; border-radius:8px; padding:10px 12px;
                  font-family:ui-monospace, Consolas, monospace; font-size:11.5px; white-space:pre-wrap; word-break:break-word; }
  .left-pane .loc { margin-top:8px; font-size:12px; color:var(--muted); }
  .center-pane { position:relative; }
  .eqname { font-size:15px; font-weight:600; margin-bottom:6px; }
  .equation { padding:28px 8px; overflow-x:auto; }
  .center-pane .hint { font-size:12px; color:var(--muted); text-align:center; }
  [class*="eqspan-"] { border-radius:4px; padding:1px 2px; cursor:pointer; transition: background .12s, box-shadow .12s; }
  [class*="eqspan-"].hl { background:#fef9c3; box-shadow:0 0 0 2px #fde047; }
  .card { border:1px solid var(--border); border-left-width:4px; border-radius:8px; padding:10px 12px; margin-bottom:10px; cursor:pointer; transition: background .12s, box-shadow .12s; }
  .card.hl { background:#fefce8; box-shadow:0 0 0 2px #fde047; }
  .card-head { display:flex; align-items:center; gap:8px; }
  .chip { width:12px; height:12px; border-radius:3px; flex:0 0 auto; }
  .card-label { font-weight:600; font-size:13.5px; }
  .card-body { margin:6px 0 0; font-size:13px; line-height:1.5; color:#374151; }
  .aside { margin-top:14px; border-top:1px dashed var(--border); padding-top:12px; font-size:13px; line-height:1.55; color:#374151; }
  .aside .k { font-weight:600; font-size:12px; text-transform:uppercase; letter-spacing:.05em; color:var(--muted); display:block; margin-bottom:4px; }
  .bottom { margin:0 24px 24px; }
  .bottom blockquote { margin:0 0 10px; padding:10px 14px; background:var(--card); border:1px solid var(--border); border-left:4px solid #94a3b8; border-radius:8px; font-size:13px; line-height:1.55; }
  .qloc { color:var(--muted); font-size:12px; margin-left:6px; }
  .qtag { display:inline-block; margin-left:4px; padding:1px 7px; border-radius:999px; background:#eef2ff; color:#4338ca; font-size:11px; cursor:pointer; }
  .qtag.hl { background:#fde047; color:#713f12; }
  .conf { display:flex; align-items:center; gap:12px; margin-bottom:12px; }
  .confbar { flex:0 0 220px; height:10px; border-radius:999px; background:#e5e7eb; overflow:hidden; }
  .confbar>div { height:100%; border-radius:999px; background:linear-gradient(90deg,#f59e0b,#22c55e); }
  .conf .num { font-weight:700; }
  .conf .notes { font-size:12.5px; color:var(--muted); }
  table.symbols { width:100%; border-collapse:collapse; font-size:13px; margin-top:4px; }
  table.symbols td { border-top:1px solid var(--border); padding:8px 6px; vertical-align:top; }
  td.sym { white-space:nowrap; font-size:14px; }
  .role { display:inline-block; padding:1px 8px; border-radius:999px; font-size:11px; white-space:nowrap; }
  .ground { color:var(--muted); font-size:11.5px; margin-top:3px; font-style:italic; }
  .callout { position:absolute; display:none; max-width:320px; background:#111827; color:#f9fafb; font-size:12.5px; line-height:1.5; padding:10px 12px; border-radius:8px; z-index:50; box-shadow:0 8px 24px rgba(0,0,0,.25); }
  .callout-svg { position:absolute; overflow:visible; pointer-events:none; z-index:49; display:none; }
  #fallback { display:none; margin:8px 24px 0; padding:8px 12px; background:#fef2f2; border:1px solid #fecaca; border-radius:8px; font-size:12.5px; color:#991b1b; }
  @media (max-width: 1100px) { main { grid-template-columns:1fr; } }
__SPAN_CSS__
</style>
</head>
<body>
<header>
  <h1>__TITLE__</h1>
  <div class="meta">arXiv:__ARXIV_ID__ · <a href="__SOURCE_URL__">__SOURCE_URL__</a> · generated by equation-visualizer (deterministic renderer — the model wrote the <a href="#spec">spec</a>, not this page)</div>
</header>
__TABS__
<div id="fallback">MathJax failed to load (offline?). The raw LaTeX in each left pane is the source of truth.</div>
__PANELS__
<script type="application/json" id="spec">__SPEC_JSON__</script>
<script>
(function () {
  var CALLOUTS = __CALLOUTS_JSON__;
  var pinned = null;

  function eqEls(id) { return document.querySelectorAll('.eqspan-' + id); }
  function cards(id) { return document.querySelectorAll('[data-span="' + id + '"]'); }
  function setHl(id, on) {
    eqEls(id).forEach(function (e) { e.classList.toggle('hl', on); });
    cards(id).forEach(function (e) { e.classList.toggle('hl', on); });
  }
  function hideCallout() {
    document.querySelectorAll('.callout').forEach(function (e) { e.style.display = 'none'; });
    document.querySelectorAll('.callout-svg').forEach(function (e) { e.style.display = 'none'; });
  }
  function showCallout(id) {
    var target = eqEls(id)[0];
    var panel = target && target.closest('.eqpanel');
    if (!target || !panel || !CALLOUTS[id]) { hideCallout(); return; }
    var center = panel.querySelector('.center-pane');
    var callout = panel.querySelector('.callout');
    var connector = panel.querySelector('.callout-svg');
    callout.textContent = CALLOUTS[id];
    callout.style.display = 'block';
    var cr = center.getBoundingClientRect(), tr = target.getBoundingClientRect();
    var top = tr.bottom - cr.top + 14;
    var left = Math.max(8, Math.min(tr.left - cr.left, center.clientWidth - 340));
    callout.style.top = top + 'px';
    callout.style.left = left + 'px';
    var line = connector.querySelector('line');
    connector.style.display = 'block';
    connector.style.left = '0'; connector.style.top = '0';
    connector.setAttribute('width', center.clientWidth); connector.setAttribute('height', center.clientHeight);
    line.setAttribute('x1', tr.left - cr.left + tr.width / 2);
    line.setAttribute('y1', tr.bottom - cr.top + 2);
    line.setAttribute('x2', left + 30);
    line.setAttribute('y2', top);
  }
  function enter(id) { return function () { if (!pinned) { setHl(id, true); showCallout(id); } }; }
  function leave(id) { return function () { if (!pinned) { setHl(id, false); hideCallout(); } }; }
  function click(id) {
    return function (ev) {
      ev.stopPropagation();
      if (pinned === id) { pinned = null; setHl(id, false); hideCallout(); return; }
      if (pinned) setHl(pinned, false);
      pinned = id; setHl(id, true); showCallout(id);
    };
  }
  function bind(el, id) {
    el.addEventListener('mouseenter', enter(id));
    el.addEventListener('mouseleave', leave(id));
    el.addEventListener('click', click(id));
  }
  function unpin() {
    if (pinned) { setHl(pinned, false); pinned = null; }
    hideCallout();
  }
  function initTabs() {
    var buttons = document.querySelectorAll('#eqtabs button');
    buttons.forEach(function (btn) {
      btn.addEventListener('click', function (ev) {
        ev.stopPropagation();
        unpin();
        buttons.forEach(function (b) { b.classList.toggle('active', b === btn); });
        document.querySelectorAll('.eqpanel').forEach(function (p) {
          p.classList.toggle('active', p.id === 'panel-' + btn.getAttribute('data-panel'));
        });
        // hidden-while-typeset panels can have stale measurements; nudge MathJax once
        if (window.MathJax && MathJax.typesetPromise && !btn.dataset.retypeset) {
          btn.dataset.retypeset = '1';
          MathJax.typesetPromise([document.getElementById('panel-' + btn.getAttribute('data-panel'))]).catch(function () {});
        }
      });
    });
  }
  function init() {
    document.querySelectorAll('[data-span]').forEach(function (el) { bind(el, el.getAttribute('data-span')); });
    document.querySelectorAll('[class*="eqspan-"]').forEach(function (el) {
      var m = el.className.baseVal !== undefined ? null : el.className.match(/eqspan-([a-z0-9_-]+)/);
      if (m) bind(el, m[1]);
    });
    document.body.addEventListener('click', unpin);
  }
  initTabs();
  // window.MathJax starts life as our config object; startup appears once the async
  // CDN script loads, so poll rather than checking immediately
  var tries = 0;
  (function waitForMathJax() {
    if (window.MathJax && MathJax.startup && MathJax.startup.promise) {
      MathJax.startup.promise.then(init);
    } else if (++tries < 50) {
      setTimeout(waitForMathJax, 200);
    } else {
      document.getElementById('fallback').style.display = 'block';
      init();
    }
  })();
})();
</script>
</body>
</html>
"""


def namespace_spec(spec: dict, prefix: str) -> dict:
    """Prefix span ids so multiple equations on one page can't collide."""
    spec = copy.deepcopy(spec)
    for s in spec["color_spans"]:
        s["id"] = prefix + s["id"]
    for cb in spec.get("callout_boxes", []):
        cb["anchor_span"] = prefix + cb["anchor_span"]
    for q in spec.get("source_quotes", []):
        q["supports"] = [prefix + sid for sid in q.get("supports", [])]
    return spec


def build_panel(spec: dict, idx: int, active: bool, warn) -> str:
    eq = spec["equation"]
    spans = spec["color_spans"]

    known = {s["id"] for s in spans}
    for cb in spec.get("callout_boxes", []):
        if cb["anchor_span"] not in known:
            warn(f"callout anchors unknown span '{cb['anchor_span']}'")
    for q in spec.get("source_quotes", []):
        for sid in q.get("supports", []):
            if sid not in known:
                warn(f"quote supports unknown span '{sid}'")

    wrapped = wrap_spans(eq["equation_latex"], spans, warn)
    conf = spec.get("confidence", {"score": 0.0})
    score = float(conf.get("score", 0.0))
    src = eq.get("source", {})

    return (PANEL_TEMPLATE
        .replace("__ACTIVE__", " active" if active else "")
        .replace("__IDX__", str(idx))
        .replace("__SUMMARY__", esc(spec["paper"].get("summary", "")))
        .replace("__EQ_NAME__", esc(eq.get("name", "Core equation")))
        .replace("__EQ_LOCATION__", esc(src.get("location", "")))
        .replace("__RAW_LATEX__", esc(eq["equation_latex"]))
        .replace("__WRAPPED_LATEX__", esc(wrapped))
        .replace("__PLAIN_ENGLISH__", esc(spec["plain_english_explanation"]))
        .replace("__ANALOGY__", esc(spec.get("intuitive_analogy", "")))
        .replace("__LEGEND_CARDS__", build_legend(spans))
        .replace("__QUOTES__", build_quotes(spec.get("source_quotes", [])))
        .replace("__SYMBOL_ROWS__", build_symbol_table(spec.get("symbol_map", [])))
        .replace("__CONF_PCT__", str(round(score * 100)))
        .replace("__CONF_SCORE__", f"{score:.2f}")
        .replace("__CONF_NOTES__", esc(conf.get("notes", "")))
    )


def build_tabs(specs) -> str:
    if len(specs) < 2:
        return ""
    buttons = []
    for i, spec in enumerate(specs):
        eq = spec["equation"]
        label = eq.get("name") or f"Equation {i + 1}"
        loc = eq.get("source", {}).get("location", "")
        title = f' title="{esc(loc)}"' if loc else ""
        buttons.append(
            f'<button data-panel="{i}"{" class=active" if i == 0 else ""}{title}>{esc(label)}</button>'
        )
    return '<nav id="eqtabs">' + "".join(buttons) + "</nav>"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("specs", type=Path, nargs="+",
                    help="one spec JSON per equation; multiple specs (same paper) render as tabs")
    ap.add_argument("-o", "--out", type=Path, default=Path("output/demo.html"))
    args = ap.parse_args()

    warnings = []
    raw_specs = [json.loads(p.read_text(encoding="utf-8")) for p in args.specs]
    multi = len(raw_specs) > 1
    specs = [namespace_spec(s, f"e{i}-") if multi else s for i, s in enumerate(raw_specs)]
    paper = raw_specs[0]["paper"]

    panels, span_css, callouts = [], [], {}
    for i, spec in enumerate(specs):
        panels.append(build_panel(spec, i, active=(i == 0), warn=warnings.append))
        span_css.append(build_span_css(spec["color_spans"]))
        callouts.update({cb["anchor_span"]: cb["text"] for cb in spec.get("callout_boxes", [])})

    embedded = raw_specs if multi else raw_specs[0]
    page = (TEMPLATE
        .replace("__TITLE__", esc(paper["title"]))
        .replace("__ARXIV_ID__", esc(paper["arxiv_id"]))
        .replace("__SOURCE_URL__", esc(paper.get("source_url", f"https://arxiv.org/abs/{paper['arxiv_id']}")))
        .replace("__TABS__", build_tabs(specs))
        .replace("__PANELS__", "\n".join(panels))
        .replace("__SPAN_CSS__", "\n".join(span_css))
        .replace("__CALLOUTS_JSON__", json.dumps(callouts, ensure_ascii=False).replace("</", "<\\/"))
        .replace("__SPEC_JSON__", json.dumps(embedded, ensure_ascii=False).replace("</", "<\\/"))
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(page, encoding="utf-8")
    print(f"wrote {args.out} ({len(page)} bytes, {len(specs)} equation panel(s))")
    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)
    return 2 if warnings else 0


if __name__ == "__main__":
    raise SystemExit(main())
