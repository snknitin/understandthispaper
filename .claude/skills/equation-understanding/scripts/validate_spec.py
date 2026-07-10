#!/usr/bin/env python3
"""Deterministic spec validator — the hard gate between the LLM and the renderer.

Checks structure, span fragments, cross-references, and value ranges without any LLM
involvement. Exit 0 = all specs valid; exit 1 = errors (listed on stderr). The same
rules are mirrored in extension/lib/validate.js for the browser pipeline.

Usage:
    python validate_spec.py specs/<file>.json [more.json ...]
    python validate_spec.py --json specs/*.json     # machine-readable report
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROLES = {"input", "learned_parameter", "objective", "constraint", "normalization",
         "hyperparameter", "index", "operator", "output"}
SPAN_ID_RE = re.compile(r"^[a-z][a-z0-9_-]*$")
COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def validate(spec: dict) -> list:
    """Return a list of human-readable error strings (empty = valid)."""
    errors = []
    err = errors.append

    def need(obj, path, key, typ):
        val = obj.get(key)
        if val is None:
            err(f"{path}.{key} is missing")
            return None
        if typ and not isinstance(val, typ):
            err(f"{path}.{key} must be {typ.__name__}")
            return None
        return val

    paper = need(spec, "spec", "paper", dict) or {}
    need(paper, "paper", "arxiv_id", str)
    need(paper, "paper", "title", str)

    eq = need(spec, "spec", "equation", dict) or {}
    latex = need(eq, "equation", "equation_latex", str) or ""
    if latex and "\\\\[" in latex:
        err("equation.equation_latex must not include display delimiters (\\[ \\])")

    spans = need(spec, "spec", "color_spans", list) or []
    if not spans:
        err("color_spans must have at least one span")
    ids = set()
    for i, s in enumerate(spans):
        p = f"color_spans[{i}]"
        if not isinstance(s, dict):
            err(f"{p} must be an object"); continue
        sid = need(s, p, "id", str) or ""
        if sid in ids:
            err(f"{p}.id '{sid}' is duplicated")
        ids.add(sid)
        if sid and not SPAN_ID_RE.match(sid):
            err(f"{p}.id '{sid}' must match ^[a-z][a-z0-9_-]*$")
        color = need(s, p, "color", str) or ""
        if color and not COLOR_RE.match(color):
            err(f"{p}.color '{color}' must be #rrggbb")
        need(s, p, "label", str)
        need(s, p, "explanation", str)
        frag = need(s, p, "latex_fragment", str) or ""
        if frag and latex and frag not in latex:
            err(f"{p}.latex_fragment not found verbatim in equation_latex: {frag[:60]!r}")
        if frag and latex and latex.count(frag) > 1:
            err(f"{p}.latex_fragment is ambiguous ({latex.count(frag)} occurrences): {frag[:60]!r}")
    for i, a in enumerate(spans):
        for j, b in enumerate(spans):
            if i != j and isinstance(a, dict) and isinstance(b, dict):
                fa, fb = a.get("latex_fragment", ""), b.get("latex_fragment", "")
                if fa and fb and fa in fb:
                    err(f"span '{a.get('id')}' fragment is contained in span '{b.get('id')}' — spans must not overlap")

    symbols = need(spec, "spec", "symbol_map", list) or []
    for i, s in enumerate(symbols):
        p = f"symbol_map[{i}]"
        if not isinstance(s, dict):
            err(f"{p} must be an object"); continue
        need(s, p, "symbol", str)
        need(s, p, "meaning", str)
        role = need(s, p, "role", str)
        if role and role not in ROLES:
            err(f"{p}.role '{role}' not one of {sorted(ROLES)}")

    need(spec, "spec", "plain_english_explanation", str)

    for i, cb in enumerate(spec.get("callout_boxes", [])):
        p = f"callout_boxes[{i}]"
        anchor = need(cb, p, "anchor_span", str)
        need(cb, p, "text", str)
        if anchor and anchor not in ids:
            err(f"{p}.anchor_span '{anchor}' does not match any color_spans id")

    quotes = need(spec, "spec", "source_quotes", list) or []
    for i, q in enumerate(quotes):
        p = f"source_quotes[{i}]"
        need(q, p, "quote", str)
        for sid in q.get("supports", []):
            if sid not in ids:
                err(f"{p}.supports '{sid}' does not match any color_spans id")

    conf = need(spec, "spec", "confidence", dict) or {}
    score = conf.get("score")
    if not isinstance(score, (int, float)) or not (0 <= score <= 1):
        err("confidence.score must be a number in [0, 1]")

    return errors


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("specs", type=Path, nargs="+")
    ap.add_argument("--json", action="store_true", help="machine-readable report on stdout")
    args = ap.parse_args()

    report, failed = {}, False
    for path in args.specs:
        try:
            spec = json.loads(path.read_text(encoding="utf-8"))
            errors = validate(spec)
        except (json.JSONDecodeError, OSError) as e:
            errors = [f"unreadable: {e}"]
        report[str(path)] = errors
        if errors:
            failed = True
            for e in errors:
                print(f"FAIL {path}: {e}", file=sys.stderr)
        else:
            print(f"ok   {path}")
    if args.json:
        print(json.dumps(report, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
