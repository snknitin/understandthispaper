#!/usr/bin/env bash
# Search Hugging Face Papers. Usage: hf_papers_search.sh <query terms...>
# Prints: <arxiv_id>\t<title>, top 10 hits.
set -uo pipefail

[ $# -ge 1 ] || { echo "usage: hf_papers_search.sh <query terms...>" >&2; exit 1; }

curl -s -G "https://huggingface.co/api/papers/search" --data-urlencode "q=$*" |
  jq -r '.[0:10][] | "\(.paper.id)\t\(.paper.title | gsub("\\s+"; " "))"'
