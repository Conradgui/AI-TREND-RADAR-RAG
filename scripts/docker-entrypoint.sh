#!/bin/sh

set -eu

RECHECK_DAYS="${RAG_CORPUS_RECHECK_DAYS:-30}"
echo "[startup] Checking upstream corpus and incrementally updating the local index..."

# The dashboard must remain reachable while a slow upstream or a first-time
# index build is in progress. The updater writes atomically and the server
# continues to serve the last successful local corpus in the meantime.
(
  if python -m rag.corpus_update --days "$RECHECK_DAYS"; then
    echo "[startup] Corpus update completed."
  else
    echo "[startup] Corpus update failed; serving the last successful local index." >&2
  fi
) &

exec python -m rag.server
