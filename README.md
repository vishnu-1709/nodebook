# Nodebook

Turn lecture slides into an editable mind map where every question, note and
flashcard lives on the topic it belongs to — and the app keeps telling you the
next useful thing to study.

Local-first, open source, single-user. Runs on your own machine with a local LLM
through [Ollama](https://ollama.com). No accounts, no server, no cloud.

> Status: under active development (see `PROGRESS.md`). The spec is in `SPEC.md`.

## Dev setup

Requirements: Python 3.11+, Node 20+, and (for real AI features) Ollama.

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
(cd frontend && npm install)
scripts/dev.sh                    # backend :8765 + Vite :5173 → open http://127.0.0.1:5173
NODEBOOK_FAKE_LLM=1 scripts/dev.sh   # no Ollama needed: canned answers
```

Tests:

```bash
.venv/bin/python -m pytest
(cd frontend && npm test && npx tsc -b)
```

## Data folder

Everything you create is stored as plain JSON files in a folder you choose
(default `~/Documents/Nodebook/`). It can live inside Google Drive / OneDrive.
App settings live separately in your OS config folder.
