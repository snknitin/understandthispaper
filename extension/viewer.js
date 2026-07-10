// Viewer: DOM-building port of render_spec.py. Data comes from the service worker's
// cache (extension mode), or window.SAMPLE_DATA (?demo=1, or when opened outside the
// extension, e.g. over plain http while developing).
(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const params = new URLSearchParams(location.search);
  const isExtension = typeof chrome !== "undefined" && !!chrome.storage?.local;
  const CACHE_VERSION = 1;

  const ROLE_COLORS = {
    input: "#0e7490", learned_parameter: "#7c3aed", objective: "#b91c1c",
    constraint: "#a16207", normalization: "#4d7c0f", hyperparameter: "#c2410c",
    index: "#6b7280", operator: "#6b7280", output: "#1d4ed8",
  };

  function el(tag, cls, text) {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  // ---- spec -> DOM (mirrors render_spec.py) -------------------------------

  function wrapSpans(latex, spans) {
    for (const span of [...spans].sort((a, b) => b.latex_fragment.length - a.latex_fragment.length)) {
      const frag = span.latex_fragment;
      if (!latex.includes(frag)) continue; // validator already warned upstream
      latex = latex.replace(frag, `\\class{eqspan-${span.id}}{${frag}}`);
    }
    return latex;
  }

  function namespaceSpec(spec, prefix) {
    const s = JSON.parse(JSON.stringify(spec));
    s.color_spans.forEach((c) => (c.id = prefix + c.id));
    (s.callout_boxes || []).forEach((cb) => (cb.anchor_span = prefix + cb.anchor_span));
    (s.source_quotes || []).forEach((q) => (q.supports = (q.supports || []).map((x) => prefix + x)));
    return s;
  }

  function spanCss(spans) {
    return spans.map((s) =>
      `.eqspan-${s.id} { color: ${s.color}; }\n.card[data-span="${s.id}"] { border-left-color: ${s.color}; }`
    ).join("\n");
  }

  function buildPanel(spec, idx, active) {
    const eq = spec.equation, spans = spec.color_spans;
    const panel = el("div", "eqpanel" + (active ? " active" : ""));
    panel.id = `panel-${idx}`;

    const main = el("main");

    const left = el("section", "pane left-pane");
    left.appendChild(el("h2", null, "Paper & source"));
    left.appendChild(el("div", "summary", spec.paper.summary || ""));
    left.appendChild(el("div", "loc", eq.source?.location || ""));
    left.appendChild(el("div", "srcbox", eq.equation_latex));
    main.appendChild(left);

    const center = el("section", "pane center-pane");
    center.appendChild(el("h2", null, "Equation"));
    center.appendChild(el("div", "eqname", eq.name || "Core equation"));
    center.appendChild(el("div", "equation", `\\[${wrapSpans(eq.equation_latex, spans)}\\]`));
    center.appendChild(el("div", "hint", "hover or click any colored piece — or a card on the right"));
    const plain = el("div", "aside");
    plain.appendChild(el("span", "k", "Plain English"));
    plain.appendChild(document.createTextNode(spec.plain_english_explanation || ""));
    center.appendChild(plain);
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("class", "callout-svg");
    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
    line.setAttribute("stroke", "#111827"); line.setAttribute("stroke-width", "1.5");
    line.setAttribute("stroke-dasharray", "4 3");
    svg.appendChild(line);
    center.appendChild(svg);
    center.appendChild(el("div", "callout"));
    main.appendChild(center);

    const right = el("section", "pane right-pane");
    right.appendChild(el("h2", null, "What each color means"));
    for (const s of spans) {
      const card = el("div", "card");
      card.dataset.span = s.id;
      card.tabIndex = 0;
      const head = el("div", "card-head");
      const chip = el("span", "chip"); chip.style.background = s.color;
      head.appendChild(chip);
      head.appendChild(el("span", "card-label", s.label));
      card.appendChild(head);
      card.appendChild(el("p", "card-body", s.explanation));
      right.appendChild(card);
    }
    if (spec.intuitive_analogy) {
      const asideA = el("div", "aside");
      asideA.appendChild(el("span", "k", "Intuition"));
      asideA.appendChild(document.createTextNode(spec.intuitive_analogy));
      right.appendChild(asideA);
    }
    main.appendChild(right);
    panel.appendChild(main);

    const bottom = el("section", "bottom");
    const bpane = el("div", "pane");
    bpane.appendChild(el("h2", null, "Why the model reads it this way (grounding)"));
    const conf = spec.confidence || { score: 0 };
    const confRow = el("div", "conf");
    const bar = el("div", "confbar");
    const fill = el("div"); fill.style.width = `${Math.round((conf.score || 0) * 100)}%`;
    bar.appendChild(fill);
    confRow.appendChild(bar);
    confRow.appendChild(el("span", "num", (conf.score || 0).toFixed(2)));
    confRow.appendChild(el("span", "notes", conf.notes || ""));
    bpane.appendChild(confRow);
    for (const q of spec.source_quotes || []) {
      const bq = el("blockquote", null, `“${q.quote}” `);
      if (q.location) bq.appendChild(el("span", "qloc", q.location));
      for (const sid of q.supports || []) {
        const tag = el("span", "qtag", sid.replace(/^e\d+-/, ""));
        tag.dataset.span = sid;
        bq.appendChild(tag);
      }
      bpane.appendChild(bq);
    }
    const h2s = el("h2", null, "Symbol map"); h2s.style.marginTop = "16px";
    bpane.appendChild(h2s);
    const table = el("table", "symbols");
    for (const s of spec.symbol_map || []) {
      const tr = el("tr");
      tr.appendChild(el("td", "sym", `\\(${s.symbol}\\)`));
      const td = el("td", null, s.meaning);
      if (s.grounding_sentence) td.appendChild(el("div", "ground", `“${s.grounding_sentence}”`));
      tr.appendChild(td);
      const roleTd = el("td");
      const color = ROLE_COLORS[s.role] || "#6b7280";
      const badge = el("span", "role", (s.role || "").replace(/_/g, " "));
      badge.style.background = color + "1a"; badge.style.color = color;
      roleTd.appendChild(badge);
      tr.appendChild(roleTd);
      table.appendChild(tr);
    }
    bpane.appendChild(table);
    bottom.appendChild(bpane);
    panel.appendChild(bottom);
    return panel;
  }

  // ---- interactions (hover/click sync + callouts) --------------------------

  function bindInteractions(callouts) {
    let pinned = null;
    const eqEls = (id) => document.querySelectorAll(".eqspan-" + id);
    const cards = (id) => document.querySelectorAll(`[data-span="${id}"]`);
    const setHl = (id, on) => {
      eqEls(id).forEach((e) => e.classList.toggle("hl", on));
      cards(id).forEach((e) => e.classList.toggle("hl", on));
    };
    const hideCallout = () => {
      document.querySelectorAll(".callout").forEach((e) => (e.style.display = "none"));
      document.querySelectorAll(".callout-svg").forEach((e) => (e.style.display = "none"));
    };
    const showCallout = (id) => {
      const target = eqEls(id)[0];
      const panel = target && target.closest(".eqpanel");
      if (!target || !panel || !callouts[id]) { hideCallout(); return; }
      const center = panel.querySelector(".center-pane");
      const callout = panel.querySelector(".callout");
      const connector = panel.querySelector(".callout-svg");
      callout.textContent = callouts[id];
      callout.style.display = "block";
      const cr = center.getBoundingClientRect(), tr = target.getBoundingClientRect();
      const top = tr.bottom - cr.top + 14;
      const left = Math.max(8, Math.min(tr.left - cr.left, center.clientWidth - 340));
      callout.style.top = top + "px";
      callout.style.left = left + "px";
      const line = connector.querySelector("line");
      connector.style.display = "block";
      connector.style.left = "0"; connector.style.top = "0";
      connector.setAttribute("width", center.clientWidth);
      connector.setAttribute("height", center.clientHeight);
      line.setAttribute("x1", tr.left - cr.left + tr.width / 2);
      line.setAttribute("y1", tr.bottom - cr.top + 2);
      line.setAttribute("x2", left + 30);
      line.setAttribute("y2", top);
    };
    const unpin = () => { if (pinned) { setHl(pinned, false); pinned = null; } hideCallout(); };
    const bind = (node, id) => {
      node.addEventListener("mouseenter", () => { if (!pinned) { setHl(id, true); showCallout(id); } });
      node.addEventListener("mouseleave", () => { if (!pinned) { setHl(id, false); hideCallout(); } });
      node.addEventListener("click", (ev) => {
        ev.stopPropagation();
        if (pinned === id) { unpin(); return; }
        if (pinned) setHl(pinned, false);
        pinned = id; setHl(id, true); showCallout(id);
      });
    };
    document.querySelectorAll("[data-span]").forEach((n) => bind(n, n.dataset.span));
    document.querySelectorAll('[class*="eqspan-"]').forEach((n) => {
      const m = /eqspan-([a-z0-9_-]+)/.exec(n.className.baseVal === undefined ? n.className : "");
      if (m) bind(n, m[1]);
    });
    document.body.addEventListener("click", unpin);
    return unpin;
  }

  // ---- page assembly -------------------------------------------------------

  function render(data) {
    const paper = data.paper || data.specs[0].paper;
    $("title").textContent = paper.title;
    const meta = $("meta");
    meta.textContent = `arXiv:${paper.arxiv_id} · `;
    const a = el("a", null, `arxiv.org/abs/${paper.arxiv_id}`);
    a.href = paper.source_url || `https://arxiv.org/abs/${paper.arxiv_id}`;
    a.target = "_blank"; a.rel = "noopener";
    meta.appendChild(a);
    if (data.generator?.model) meta.appendChild(document.createTextNode(` · grounded by ${data.generator.model} · rendered deterministically`));

    const multi = data.specs.length > 1;
    const specs = data.specs.map((s, i) => (multi ? namespaceSpec(s, `e${i}-`) : s));

    const style = document.createElement("style");
    style.textContent = specs.map((s) => spanCss(s.color_spans)).join("\n");
    document.head.appendChild(style);

    const callouts = {};
    const panelsHost = $("panels");
    specs.forEach((s, i) => {
      (s.callout_boxes || []).forEach((cb) => (callouts[cb.anchor_span] = cb.text));
      panelsHost.appendChild(buildPanel(s, i, i === 0));
    });

    if (multi) {
      const tabs = $("eqtabs");
      tabs.hidden = false;
      let unpin = () => {};
      specs.forEach((s, i) => {
        const btn = el("button", i === 0 ? "active" : "", s.equation.name || `Equation ${i + 1}`);
        btn.title = s.equation.source?.location || "";
        btn.addEventListener("click", (ev) => {
          ev.stopPropagation();
          unpin();
          tabs.querySelectorAll("button").forEach((b) => b.classList.toggle("active", b === btn));
          document.querySelectorAll(".eqpanel").forEach((p) => p.classList.toggle("active", p.id === `panel-${i}`));
          if (window.MathJax?.typesetPromise && !btn.dataset.retypeset) {
            btn.dataset.retypeset = "1";
            MathJax.typesetPromise([$(`panel-${i}`)]).catch(() => {});
          }
        });
        tabs.appendChild(btn);
      });
      // bindInteractions returns unpin; wire it after typeset below
      window.__setUnpin = (fn) => (unpin = fn);
    }

    if ((data.related || []).length) {
      $("related-section").hidden = false;
      const grid = $("relgrid");
      for (const r of data.related) {
        const card = el("a", "rel");
        card.href = `https://huggingface.co/papers/${r.id}`;
        card.target = "_blank"; card.rel = "noopener";
        card.appendChild(el("div", "rel-title", r.title));
        const metaBits = [`arXiv:${r.id}`, (r.publishedAt || "").slice(0, 4),
          typeof r.upvotes === "number" && r.upvotes > 0 ? `▲ ${r.upvotes}` : ""].filter(Boolean);
        card.appendChild(el("div", "rel-meta", metaBits.join(" · ")));
        if (r.summary) card.appendChild(el("div", "rel-sum", r.summary));
        grid.appendChild(card);
      }
    }

    $("progress").hidden = true;
    $("content").hidden = false;

    const typeset = window.MathJax?.startup?.promise
      ? MathJax.startup.promise.then(() => MathJax.typesetPromise([panelsHost]))
      : Promise.resolve();
    typeset.then(() => {
      const unpin = bindInteractions(callouts);
      if (window.__setUnpin) window.__setUnpin(unpin);
    }).catch((e) => console.error("MathJax typeset failed:", e));
  }

  // ---- data acquisition ----------------------------------------------------

  const STATUS_TEXT = {
    fetching: "Fetching paper sources…",
    extracting: "Extracting equations (exact LaTeX, no OCR)…",
    grounding: "Grounding symbols in the paper's own sentences…",
    repairing: "Output failed validation — repairing…",
    related: "Finding related papers…",
    "need-config": "No model configured. Open the extension's Settings, add a model + key, then run again.",
  };

  async function main() {
    const id = params.get("id");
    const demo = params.get("demo") === "1" || !isExtension || !id;

    if (demo) {
      $("progress-status").textContent = "Loading bundled demo…";
      render(window.SAMPLE_DATA);
      return;
    }

    const cacheKey = `cache:${CACHE_VERSION}:${id}`;
    const poll = async () => {
      const cached = (await chrome.storage.local.get(cacheKey))[cacheKey];
      const job = (await chrome.storage.session.get(`job:${id}`))[`job:${id}`];
      if (cached && (!job || job.status === "done")) { render(cached); return; }
      if (job?.status === "error") {
        $("progress").classList.add("err");
        $("progress-status").textContent = "Failed";
        $("progress-detail").textContent = job.detail;
        return;
      }
      if (job) {
        $("progress-status").textContent = STATUS_TEXT[job.status] || job.status;
        $("progress-detail").textContent = job.status === "need-config" ? "" : (job.detail || "");
        if (job.status === "need-config") { $("progress").classList.add("err"); return; }
      }
      setTimeout(poll, 500);
    };
    poll();
  }

  main();
})();
