#!/usr/bin/env bash
set -euo pipefail

# Generated indexes and publication metadata may change on every run because
# they contain timestamps. They are publishable only when an actual corpus
# source artifact changed in the same staged diff.
meaningful_changes=0
while IFS= read -r path; do
  case "$path" in
    manifest.json|feed.xml|corpus-manifest.json|digests/search-index.json)
      ;;
    *)
      printf '%s\n' "$path"
      meaningful_changes=1
      ;;
  esac
done < <(git diff --cached --name-only --diff-filter=ACDMRT)

(( meaningful_changes == 1 ))
