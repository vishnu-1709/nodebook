# Nodebook

Turn lecture slides into an editable mind map where every question, note and
flashcard lives on the topic it belongs to — and the app keeps telling you the
next useful thing to study.

Local-first, open source, single-user. Runs on your own machine with a local LLM
through [Ollama](https://ollama.com). No accounts, no server, no cloud.

## What it does (v0.2)

- Drop a PDF or PPTX → a mind map of the lecture, every node linked to its slides; a banner lists
  slides the map doesn't cover.
- Edit the map freely (rename, add, move, delete, undo) and ask the AI to expand, split, merge or
  simplify nodes — always previewed first.
- Click a node to ask questions about it. "Try first" makes you answer before the AI explains; doubts
  are temporary unless you keep them. Test me asks three recall questions from that node's slides.
- Generate practice questions, flashcards, summaries and explanations from your slides and past
  papers, one at a time, and save them onto the right topic.
- Spaced review (FSRS) for flashcards and saved questions: Again / Hard / Good / Easy with keys 1–4,
  a calm one-item-at-a-time session, and Anki export.
- Recall tests: rebuild a map from memory (labels hidden), or explain a topic in your own words and
  see what you missed — with slide references.
- Topic status follows your results automatically (Got it / Revising / Confused) unless you set it.
- Today: due reviews, topics fading soon, exam countdown, reminders ("lab exam 14 nov #exam", add to
  your calendar as .ics), lecture progress and a weekly summary line. Pomodoro on every screen, with a
  quick 3-question brain check at the end of a focus block.

## Install

1. Install **Ollama**: <https://ollama.com/download> and start it.
2. Download Nodebook for your system from the GitHub **Releases** page, unzip it, and run
   `Nodebook` (`Nodebook.exe` on Windows). Your browser opens to the app.
3. The first-run setup asks where to keep your files, checks Ollama, and recommends models for your
   RAM (one-click download). "Test on my slides" shows what a model makes of one of your decks.

Running it again while it's open just opens the browser to the running app.

## Your data

Everything you create is plain JSON in a folder you choose (default `~/Documents/Nodebook/`):
courses, lectures, maps, threads, notes, practice items, reminders. It can live inside Google Drive
or OneDrive. Original slide files are copied into `courses/<id>/sources/`. App settings live
separately in your OS config folder. Courses can be exported/imported as `.zip` from Settings → Data.

Nodebook only talks to the Ollama endpoint you configure (default `http://localhost:11434`). The
server binds to `127.0.0.1` only. A local usage log (feature name + time, in your data folder) can be
switched off in Settings and is never sent anywhere.

## Honest limitations

- Map and answer quality depend on the model you can run, which depends on your RAM. Small models
  (3B) make rougher maps; 14B+ is clearly better. If a model keeps returning broken JSON, Settings
  tells you and suggests a larger one.
- Scanned PDFs (images without text) aren't supported yet — there's no OCR.
- PPTX slide thumbnails need LibreOffice installed; without it you get a text-only slide view.
- Notifications (pomodoro, reminders) only work while the app is open in your browser.
- AI answers are tagged "check it" until you mark them verified.

## Development

Requirements: Python 3.11+, Node 20+, and (for real AI) Ollama.

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
(cd frontend && npm install)
scripts/dev.sh                       # backend :8765 + Vite :5173 → http://127.0.0.1:5173
NODEBOOK_FAKE_LLM=1 scripts/dev.sh   # canned answers, no Ollama needed
```

Tests: `.venv/bin/python -m pytest` and `(cd frontend && npx tsc -b && npm test)`.

Build the one-folder executable: `pip install pyinstaller && python scripts/build_exe.py --zip`.
Pushing a tag `v*` runs `.github/workflows/release.yml` and attaches Windows/macOS/Linux builds to a
GitHub Release.

Specs: `SPEC.md` (product), `UI.md` (look and layout, mockups in `docs/ui/`), progress in `PROGRESS.md`.
