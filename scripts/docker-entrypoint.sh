#!/bin/sh

set -eu

echo "[startup] Starting the single RAG runtime; corpus updates are coordinated in-process."

exec python -m rag.server
