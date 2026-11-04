#!/usr/bin/env bash
# Development: backend with reload on 127.0.0.1:8765 + Vite dev server on 127.0.0.1:5173.
# Usage: scripts/dev.sh            (real Ollama)
#        NODEBOOK_FAKE_LLM=1 scripts/dev.sh   (canned answers, no Ollama needed)
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/pip install -q -r requirements.txt
fi
if [ ! -d frontend/node_modules ]; then
  (cd frontend && npm install)
fi

.venv/bin/uvicorn backend.devserver:app --factory --host 127.0.0.1 --port 8765 --reload --reload-dir backend &
BACK=$!
trap 'kill $BACK 2>/dev/null || true' EXIT

echo "Nodebook dev: open http://127.0.0.1:5173"
(cd frontend && npx vite --host 127.0.0.1 --port 5173)
