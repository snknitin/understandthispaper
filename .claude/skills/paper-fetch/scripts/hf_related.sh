#!/usr/bin/env bash
# Find related papers via the Hugging Face Papers API, keyed by the paper's title.
# Usage: hf_related.sh <arxiv-id-or-url> [outfile]
# Writes a JSON array [{id, title, summary, publishedAt, upvotes}] (self excluded, top 8).
# Note: run at build time — the HF API's CORS policy blocks client-side browser calls.
set -uo pipefail

[ $# -ge 1 ] || { echo "usage: hf_related.sh <arxiv-id-or-url> [outfile]" >&2; exit 1; }

id=$(printf '%s' "$1" | grep -oE '[0-9]{4}\.[0-9]{4,5}(v[0-9]+)?' | head -1)
[ -n "$id" ] || { echo "error: could not parse an arXiv id from: $1" >&2; exit 1; }
id="${id%%v[0-9]*}"  # HF papers ids have no version suffix
outfile="${2:-workspace/papers/$id/related.json}"
mkdir -p "$(dirname "$outfile")"

title=$(curl -s "https://huggingface.co/api/papers/$id" | jq -r '.title // empty' | tr '\n' ' ')
[ -n "$title" ] || { echo "error: no HF papers metadata for $id (title lookup failed)" >&2; exit 1; }
echo "query: $title"

curl -s -G "https://huggingface.co/api/papers/search" --data-urlencode "q=$title" |
  jq --arg self "$id" '[.[] | .paper
      | select(.id != $self)
      | { id, title: (.title | gsub("\\s+"; " ")),
          summary: ((.summary // "") | gsub("\\s+"; " ") | .[0:280]),
          publishedAt, upvotes }
    ] | .[0:8]' > "$outfile"

n=$(jq length "$outfile")
echo "wrote $n related papers -> $outfile"
jq -r '.[] | "\(.id)\t\(.title)"' "$outfile"
