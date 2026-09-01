#!/bin/bash

# Start an already configured local AI Trend Radar RAG installation through
# the shared doctor, so launch and diagnosis cannot drift apart.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

exec "${SCRIPT_DIR}/doctor.command" --open
