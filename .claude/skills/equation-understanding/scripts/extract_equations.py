#!/usr/bin/env python3
"""Extract block equations + surrounding prose from an arXiv LaTeXML HTML page.

arXiv's HTML builds keep the source LaTeX of every equation in the ``alttext``
attribute of ``<math>`` elements, so this is exact extraction, not math OCR.

Usage:
    python extract_equations.py workspace/papers/<id>/paper.html [--min-len 20] [--json out.json]

Prints one JSON object per block equation: {"index", "latex", "context"}.
"""
import argparse
import html
import json
import re
import sys
from pathlib import Path

TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")
# attribute order varies between LaTeXML builds, so match the whole tag and
# check display/alttext independently
MATH_TAG_RE = re.compile(r"<math\b[^>]*>", re.S)
ALTTEXT_RE = re.compile(r'\balttext="([^"]*)"')
# LaTeXML-internal macros that MathJax cannot render
LATEXML_FIXES = [
    ("\\tsum\\slimits@", "\\sum"), ("\\tprod\\slimits@", "\\prod"),
    ("\\tint\\slimits@", "\\int"), ("\\slimits@", ""), ("\\nolimits@", ""),
]


def sanitize(latex: str) -> str:
    for bad, good in LATEXML_FIXES:
        latex = latex.replace(bad, good)
    return latex


def strip_tags(fragment: str) -> str:
    return WS_RE.sub(" ", html.unescape(TAG_RE.sub(" ", fragment))).strip()


def main() -> int:
    # Windows consoles default to cp1252, which chokes on math unicode
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("html_file", type=Path)
    ap.add_argument("--min-len", type=int, default=20,
                    help="skip trivial equations with LaTeX shorter than this")
    ap.add_argument("--context-chars", type=int, default=1200,
                    help="raw HTML window (each side) mined for surrounding prose")
    ap.add_argument("--json", type=Path, default=None, help="also write results to this file")
    args = ap.parse_args()

    text = args.html_file.read_text(encoding="utf-8", errors="ignore")
    results = []
    for i, m in enumerate(MATH_TAG_RE.finditer(text)):
        tag = m.group(0)
        if 'display="block"' not in tag:
            continue
        alt = ALTTEXT_RE.search(tag)
        if not alt:
            continue
        latex = sanitize(html.unescape(alt.group(1)).strip())
        if len(latex) < args.min_len:
            continue
        before = strip_tags(text[max(0, m.start() - args.context_chars):m.start()])
        after = strip_tags(text[m.end():m.end() + args.context_chars])
        results.append({
            "index": i,
            "latex": latex,
            "context": f"...{before[-400:]} [EQUATION] {after[:400]}...",
        })

    for r in results:
        print(json.dumps(r, ensure_ascii=False))
    if args.json:
        args.json.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"wrote {len(results)} equations -> {args.json}", file=sys.stderr)
    if not results:
        print("no block equations found (is this a LaTeXML HTML page?)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
