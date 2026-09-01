#!/bin/sh

set -eu

echo "[startup] Starting the single RAG runtime; corpus updates are coordinated in-process."
python -m rag.corpus_volume_bootstrap

exec python -m rag.server
