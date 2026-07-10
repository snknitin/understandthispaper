// Service worker: orchestrates the pipeline for the active tab's paper.
// fetch sources -> extract equations -> ONE grounded LLM call (+ bounded repair
// loop against the deterministic validator) -> related papers -> cache -> viewer.

import { parsePaperId, extractEquations } from "./lib/extract.js";
import { validateSpec } from "./lib/validate.js";
import { callLLM, extractJson } from "./lib/providers.js";
import { SYSTEM, buildUserPrompt, buildRepairPrompt } from "./lib/prompt.js";

const CACHE_VERSION = 1;
const MAX_REPAIRS = 2;

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type === "explain") {
    const id = parsePaperId(msg.tabUrl);
    if (!id) { sendResponse({ error: "No arXiv id found in this tab's URL" }); return; }
    sendResponse({ ok: true, id });
    runJob(id); // async; viewer tab shows progress
  }
  return false;
});

async function setJob(id, status, detail = "") {
  await chrome.storage.session.set({ [`job:${id}`]: { status, detail, at: Date.now() } });
}

async function fetchText(url) {
  const res = await fetch(url);
  return res.ok ? await res.text() : null;
}
async function fetchJson(url) {
  const res = await fetch(url);
  return res.ok ? await res.json() : null;
}

async function runJob(id) {
  const cacheKey = `cache:${CACHE_VERSION}:${id}`;
  await chrome.tabs.create({ url: chrome.runtime.getURL(`viewer.html?id=${id}`) });

  const cached = (await chrome.storage.local.get(cacheKey))[cacheKey];
  if (cached) { await setJob(id, "done"); return; }

  const { config } = await chrome.storage.local.get("config");
  if (!config?.model) { await setJob(id, "need-config"); return; }

  try {
    await setJob(id, "fetching", "arXiv HTML + alphaXiv overview + metadata");
    const [paperHtml, overview, hfMeta] = await Promise.all([
      fetchText(`https://arxiv.org/html/${id}`),
      fetchText(`https://alphaxiv.org/overview/${id}.md`),
      fetchJson(`https://huggingface.co/api/papers/${id}`),
    ]);

    await setJob(id, "extracting", "block equations from LaTeXML alttext");
    const equations = paperHtml ? extractEquations(paperHtml) : [];
    let context = overview;
    if (!context && !equations.length) {
      // last-ditch: alphaXiv full text (PDF-derived, lower confidence downstream)
      context = await fetchText(`https://alphaxiv.org/abs/${id}.md`);
      if (!context) throw new Error("No usable source: no arXiv HTML build, no alphaXiv text. Pre-2024 PDFs are not supported yet.");
    }

    const title = hfMeta?.title || `arXiv:${id}`;
    const summary = (hfMeta?.summary || "").slice(0, 1200);

    await setJob(id, "grounding", `asking ${config.model} to ground the key equations`);
    const messages = [{
      role: "user",
      content: buildUserPrompt({ arxivId: id, title, summary, overview: context, equations }),
    }];
    let specs = null;
    for (let attempt = 0; attempt <= MAX_REPAIRS; attempt++) {
      const text = await callLLM(config, { system: SYSTEM, messages });
      const parsed = extractJson(text);
      const candidate = parsed.specs || [];
      if (!candidate.length) throw new Error("Model returned no specs");
      const failures = candidate
        .map((s, i) => ({ index: i, errors: validateSpec(s) }))
        .filter((f) => f.errors.length);
      if (!failures.length) { specs = candidate; break; }
      if (attempt === MAX_REPAIRS) {
        // ship the valid subset rather than nothing
        specs = candidate.filter((_, i) => !failures.some((f) => f.index === i));
        if (!specs.length) throw new Error(`Validation failed after ${MAX_REPAIRS} repairs: ${failures[0].errors[0]}`);
        break;
      }
      await setJob(id, "repairing", `${failures.length} spec(s) failed validation, attempt ${attempt + 1}/${MAX_REPAIRS}`);
      messages.push({ role: "assistant", content: text });
      messages.push({ role: "user", content: buildRepairPrompt(failures) });
    }

    await setJob(id, "related", "related papers via Hugging Face");
    let related = [];
    try {
      const results = await fetchJson(
        `https://huggingface.co/api/papers/search?q=${encodeURIComponent(title)}`) || [];
      related = results.map((r) => r.paper).filter((p) => p && p.id !== id).slice(0, 8)
        .map((p) => ({ id: p.id, title: (p.title || "").replace(/\s+/g, " "),
                       summary: (p.summary || "").replace(/\s+/g, " ").slice(0, 280),
                       publishedAt: p.publishedAt, upvotes: p.upvotes }));
    } catch { /* related papers are optional */ }

    await chrome.storage.local.set({
      [cacheKey]: {
        paper: specs[0].paper,
        specs, related,
        generator: { model: config.model, provider: config.provider, at: new Date().toISOString() },
      },
    });
    await setJob(id, "done");
  } catch (e) {
    await setJob(id, "error", String(e.message || e));
  }
}
