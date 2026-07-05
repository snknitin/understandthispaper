#!/usr/bin/env bash
# Fetch a paper's sources into workspace/papers/<id>/.
# Usage: fetch_paper.sh <arxiv-id-or-url> [outdir]
set -uo pipefail

[ $# -ge 1 ] || { echo "usage: fetch_paper.sh <arxiv-id-or-url> [outdir]" >&2; exit 1; }

id=$(printf '%s' "$1" | grep -oE '[0-9]{4}\.[0-9]{4,5}(v[0-9]+)?' | head -1)
[ -n "$id" ] || { echo "error: could not parse an arXiv id from: $1" >&2; exit 1; }

outdir="${2:-workspace/papers/$id}"
mkdir -p "$outdir"
echo "paper id: $id"
echo "outdir:   $outdir"

fetch() { # $1=url $2=outfile $3=label
  local code
  code=$(curl -sL -o "$2" -w '%{http_code}' "$1")
  if [ "$code" = "200" ] && [ -s "$2" ]; then
    echo "ok    $3 -> $2 ($(wc -c <"$2") bytes)"
  else
    echo "miss  $3 (HTTP $code)"
    rm -f "$2"
  fi
}

fetch "https://alphaxiv.org/overview/$id.md"    "$outdir/overview.md"  "alphaxiv overview"
fetch "https://arxiv.org/html/$id"              "$outdir/paper.html"   "arxiv HTML (preferred equation source)"
fetch "https://alphaxiv.org/abs/$id.md"         "$outdir/fulltext.md"  "alphaxiv full text (pdf fallback)"
fetch "https://huggingface.co/api/papers/$id"   "$outdir/hf_meta.json" "hf papers metadata"

echo "pdf (last resort, math-unfriendly): https://arxiv.org/pdf/$id"
