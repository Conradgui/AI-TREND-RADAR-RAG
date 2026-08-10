#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "$0")/.." && pwd)"
site_root="${1:-$project_root/_site}"

(cd "$project_root" && python -m rag.corpus_contract --check-existing)

if [[ -d "$site_root" ]] && find "$site_root" -mindepth 1 -print -quit | grep -q .; then
  echo "[pages] Refusing to reuse non-empty output directory: $site_root" >&2
  exit 1
fi

mkdir -p "$site_root"

for file in index.html manifest.json feed.xml corpus-manifest.json; do
  if [[ ! -s "$project_root/$file" ]]; then
    echo "[pages] Required public file is missing or empty: $file" >&2
    exit 1
  fi
  cp "$project_root/$file" "$site_root/$file"
done

if [[ -f "$project_root/.nojekyll" ]]; then
  cp "$project_root/.nojekyll" "$site_root/.nojekyll"
fi

mkdir -p "$site_root/digests"
if [[ ! -s "$project_root/digests/search-index.json" ]]; then
  echo "[pages] Required public file is missing or empty: digests/search-index.json" >&2
  exit 1
fi
cp "$project_root/digests/search-index.json" "$site_root/digests/search-index.json"

for date_root in "$project_root"/digests/????-??-??; do
  [[ -d "$date_root" ]] || continue
  date_name="$(basename "$date_root")"
  target_root="$site_root/digests/$date_name"
  mkdir -p "$target_root"

  for source in "$date_root"/*.md "$date_root"/*.html "$date_root"/topic-pool.json; do
    [[ -f "$source" ]] || continue
    cp "$source" "$target_root/$(basename "$source")"
  done
done

echo "[pages] Built public site at $site_root"
