# Nodebook — Product & Technical Spec (v0.1 + v0.2)

> Turn lecture slides into an editable mind map where every question, note and
> flashcard lives on the topic it belongs to — and the app keeps telling you the
> next useful thing to study.

Local-first, open source, single-user. Runs on the user's own machine with a
local LLM through Ollama. No accounts, no server, no cloud.

---

## 1. Principles (every feature must pass these)

1. **One focused place.** Slides, questions, notes and revision live on the map. No general chat outside it.
2. **Organized by topic.** Everything is attached to a course → lecture → node. Nothing gets lost in a scroll.
3. **Produce, don't consume.** Learning features make the user recall, explain or answer before reading.
4. **Progress = what you can do,** not what you've collected.
5. **Calm UI.** No animations beyond 150–200 ms transitions, no gamification, no background effects.
6. **Fast to use.** Any action ≤ 2 clicks from the course page; global keyboard shortcuts.

**Out of scope for v0.1/v0.2:** logo/branding work, accounts, sync, collaboration,
general chat, gamification (points/badges/confetti), OCR for scanned PDFs,
AI-verified numericals, PYQ heat map, exam plan, cross-lecture links, global search
(these last four are v0.3).

---

## 2. Architecture

```
Browser (React SPA)  ──HTTP/SSE──►  FastAPI (127.0.0.1:<port>)  ──HTTP──►  Ollama (localhost:11434)
                                         │
                                         └── Data folder (plain JSON files + copied sources)
```

- **One process.** FastAPI serves the built React app as static files and the API under `/api`. Same origin → no CORS.
- **Binds to 127.0.0.1 only.** Never 0.0.0.0.
- **Long jobs** (map generation, model pulls) run as in-process background jobs; the UI polls `GET /api/jobs/{id}` for progress.
- **AI chat responses** stream over SSE.
- **Provider layer** (`backend/llm/`): an `LLMProvider` interface with `chat()`, `chat_stream()`, `structured(schema)`, `list_models()`, `pull()`. Implement `OllamaProvider` (native API, uses `format=<json schema>` for structured output). Keep an `OpenAICompatProvider` stub behind the same interface for later. Tests use a `FakeProvider`.
- **Two model slots** in settings: `map_model` (heavy, rare) and `study_model` (light, frequent).

### Tech stack

| Layer | Choice |
|---|---|
| Backend | Python 3.11+, FastAPI, Uvicorn, Pydantic v2, httpx |
| Parsing | PyMuPDF (PDF text + page render), python-pptx (PPTX text + images) |
| Scheduling | `fsrs` (py-fsrs) — v0.2 |
| Dates | `dateparser` (natural-language reminders) |
| Anki export | `genanki` — v0.2 |
| Frontend | React + TypeScript + Vite, TanStack Query, Zustand, Mind-Elixir (map) |
| Styling | Plain CSS with design tokens (CSS variables), light/dark/system |
| Tests | pytest (+ httpx test client), Vitest for key UI logic |
| Packaging | PyInstaller (one-folder build) + launcher; GitHub Actions for Win/Mac/Linux |

Adding any dependency not in this table → **ask the user first** (see §10).

### Repo layout

```
nodebook/
  backend/
    app.py            # FastAPI app, static serving, startup
    api/              # routers: courses, lectures, map, nodes, threads, notes,
                      # generate, practice, review, reminders, settings, jobs, ollama
    core/             # storage, ids, jobs, paths, schemas (pydantic)
    llm/              # provider interface, ollama, fake
    pipeline/         # parse_pdf, parse_pptx, map_builder, coverage
    prompts/          # *.md prompt templates, versioned
    launcher.py       # entry point for the executable
  frontend/src/
    app/ (shell, routes, shortcuts)  screens/  components/  api/  styles/tokens.css
  tests/  (backend/, fixtures/decks/)
  config/recommended_models.json
  scripts/ build_exe.py  dev.sh
  SPEC.md  CLAUDE.md  README.md
```

---

## 3. Data (plain files in a user-chosen folder)

Default location: `~/Documents/Nodebook/`. App settings live separately in the OS
config dir (`platformdirs`), so the data folder can sit inside Google Drive/OneDrive.

```
Nodebook/
  inbox.json                 # unsorted quick notes
  reminders.json
  sessions.jsonl             # pomodoro sessions (append-only)
  usage.jsonl                # local feature-use counts (dev only, never shown/sent)
  courses/<course_id>/
    course.json
    sources/<source_id>.<ext>   + sources.json (metadata)
    notes.json               # course-level notes
    review_log.jsonl         # v0.2, append-only
    lectures/<lecture_id>/
      lecture.json           # title, order, source_ids, map_status, uncovered_slides
      map.json               # nodes
      threads.json           # kept exchanges, by node_id
      recent.json            # temporary doubts with expires_at
      notes.json             # lecture + node notes
      practice.json          # review items (cards + saved questions)
      results.jsonl          # test-me / recall / explain results (append-only)
```

### Rules
- **IDs:** ULID strings for every entity. Reference by ID, never by label or name.
- **Every JSON file** has `"schema": <int>`. Bump + write a migration when shapes change.
- **Atomic writes:** write `*.tmp` then `os.replace`. One write lock per file in-process.
- **Paths:** all file access goes through `core/paths.py`, which rejects anything outside the data folder.
- **Course "Saved" view** is a query over `practice.json` + notes, not a separate copy.

### Core shapes (pydantic models in `core/schemas.py`)

```jsonc
// map.json
{ "schema": 1, "lecture_id": "…", "root_id": "…",
  "nodes": { "<id>": {
    "id": "…", "label": "Least squares", "parent_id": "…", "children": ["…"],
    "sources": [{ "source_id": "…", "slide": 9 }],
    "status": "not_started|confused|revising|got_it",
    "status_mode": "manual|auto",          // auto = performance-driven (v0.2)
    "last_studied_at": null, "origin": "ai|user" } } }

// threads.json — kept exchanges only
{ "schema": 1, "by_node": { "<node_id>": [ {
    "id": "…", "kept_at": "…",
    "messages": [{ "role": "user|assistant", "kind": "question|try_first|attempt|answer|hint", "content": "…" }] } ] } }

// recent.json — temporary doubts (same exchange shape + node_id + expires_at, 7 days)

// practice.json
{ "schema": 1, "items": [ {
    "id": "…", "type": "card|question", "node_id": "…|null",
    "front": "…", "back": "…", "answer_status": "ai_unverified|verified",
    "origin": { "kind": "node|thread|generate|note", "source_ids": [], "ref": "PYQ 2023 Q4(b) style" },
    "fsrs": null,                           // filled in v0.2
    "created_at": "…" } ] }

// reminders.json
{ "schema": 1, "items": [ { "id": "…", "text": "…", "due_at": "…", "tags": ["exam"],
    "course_id": "…|null", "link": { "kind": "course|lecture|node", "id": "…" } , "done": false } ] }
```

`practice.json` and `results.jsonl` exist from v0.1 so v0.2 needs no migration.

---

## 4. Map generation pipeline (the core quality risk)

1. **Extract** per slide/page: text, slide number, has-images flag. PDF → PyMuPDF (also render PNG thumbnails at ~1000px). PPTX → python-pptx text + embedded images. If LibreOffice is found on the system, convert PPTX → PDF for thumbnails; otherwise show text-only slide view.
2. **Chunk** ~12 slides per chunk.
3. **Per-chunk pass** (`map_model`, structured JSON): list topics with their subtopics and which slide numbers support each.
4. **Merge pass:** combine chunk topics into one tree. Constraints in prompt and enforced in code: depth ≤ 3 below root, ≤ 7 children per node, every node has ≥ 1 source slide, labels ≤ 6 words, no duplicates.
5. **Validate** with pydantic. On failure retry once with the error message; then fall back to a flat "one node per chunk topic" map and tell the user.
6. **Coverage check:** list slides not referenced by any node → stored as `uncovered_slides`, shown in the UI ("Slides 14, 21 aren't in the map — add them?").
7. **Vision (optional):** if the model reports vision capability and a slide has little text but images, send the rendered slide image in step 3.

Progress is reported per step through the job endpoint. Generation must never block the UI.

---

## 5. Features

Tags: **[v0.1]** or **[v0.2]**. Each has acceptance criteria (AC).

### 5.1 Shell & navigation [v0.1]
- Sidebar: Today, Review (due count), Notes inbox (count), course list, + New course. Wordmark "Nodebook" (text only, no logo).
- Global shortcuts: `N` quick note, `G` generate, `P` pomodoro, `R` reminder, `F` expand panel, `Esc` close/collapse, `?` shortcut list, `Ctrl/Cmd+B` collapse/expand the sidebar. Disabled while typing in inputs (except Esc).
- Sidebar collapses to a 56px icon rail; the lecture map opens with it collapsed; the last choice is remembered per screen type.
- Theme: light / dark / follow system (default). Dark = `#15171C` ground, off-white text — never pure black/white.
- **AC:** every screen reachable in ≤ 2 clicks from Today; shortcuts work from every screen.

### 5.2 Courses, lectures, sources [v0.1]
- Create/rename/delete course; add lecture by dropping PPTX/PDF; reorder lectures.
- Sources shelf per course: any uploaded file (slides, PYQs, notes, textbook PDFs). A file need not belong to a lecture.
- **AC:** upload a 40-slide PDF → lecture created, source copied into `sources/`, map job starts automatically.

### 5.3 Mind map [v0.1]
- Render with Mind-Elixir. Node shows label, status dot, kept-question count badge.
- Edit: double-click or F2 rename inline, Tab add child, Enter add sibling, Delete/Backspace delete (undo toast), drag to move, click the arrow to collapse/expand; Ctrl/Cmd+Z undo and Ctrl/Cmd+Shift+Z redo for all map edits. F or the Expand button opens the selected node in Focus mode (double-click never does).
- Right-click menu: Rename, Add child, Add sibling, AI: Expand into subtopics / Split / Merge with sibling / Simplify label, Delete. AI results are previewed before applying.
- Edits preserve node IDs, sources, threads and practice items.
- Coverage banner for uncovered slides.
- **AC:** rename/move a node → its thread and cards still attached after reload.

### 5.4 Side panel + Focus mode [v0.1]
- Click node → side panel (quick mode): breadcrumb, source slide chips (click = slide preview), status, **Test me** button, tabs Thread / Notes / Practice, ask box.
- `F` or Expand → same panel full screen (Focus mode); map hidden; `Esc` collapses. Thread, scroll position and draft text carry over.
- Opening Focus or Test me updates `last_studied_at`.
- **AC:** expand/collapse keeps the unsent draft and scroll position.

### 5.5 Node Q&A thread [v0.1]
- Context sent to `study_model`: node label + path, source slide text, last 3 kept exchanges of the node, mode instructions. Streamed answer.
- **Try first** (default on): AI asks the user what they think first; after the attempt it corrects/confirms. **Hint only** toggle: nudge, no full answer. "More help ▾": Explain why, Give example.
- **Temporary by default:** new exchanges go to `recent.json` (expire after 7 days, shown lighter under "Recent doubts").
- **Keep** (pin) saves the whole exchange to `threads.json`. Kept exchanges show first and are counted on the map badge. Setting: "Keep all questions by default".
- From a kept exchange: Make flashcard, Pin as note, Add as child node.
- Gentle "Keep this?" suggestion after ≥ 3 back-and-forths.
- **AC:** temporary doubts older than 7 days are gone on next launch; kept ones never expire; undo available for 5 s after un-keep.

### 5.6 Test me [v0.1]
- Generates 3 recall questions from the node's source slides. User types answers; AI grades each (correct / partly / wrong + one-line feedback, citing the slide).
- Result appended to `results.jsonl`.
- **AC:** questions reference only that node's slides; grading result is saved and visible in node history.

### 5.7 Notes & inbox [v0.1]
- Quick capture (`N`) from anywhere → saved to the current context (node > lecture > course); outside any course → inbox.
- Inbox: AI suggests a destination (course/lecture/node); one tap to file; "Change" to pick manually.
- **AC:** capture → saved in < 1 s without leaving the current screen.

### 5.8 Generate panel [v0.1]
- Opens from anywhere (`G`). Pick sources (chips from the course's Sources + lectures), type (Practice questions / Flashcards / Summary / Explain a topic), optional steer text + chips (Harder, Easier, Conceptual, Numerical).
- One result at a time. Questions have an answer box → **Check my answer** (AI grades); "Skip, show answer" is low-key. Worked answers carry an "AI answer · check it" tag until marked verified.
- **Saves to** an AI-suggested node (changeable; unassigned at course level if nothing fits). Discard / Next / Save (`D`, `→`, `S`).
- Destinations: question/card → `practice.json` (joins review in v0.2); summary → node or lecture note; explanation → kept exchange on the node.
- Every saved item records its origin (sources + "PYQ 2023 Q4(b) style").
- **AC:** Next never repeats an earlier item in the session; saved items appear on the target node immediately.

### 5.9 Today screen [v0.1, extended v0.2]
- v0.1: date, Quick note + Generate buttons, weak nodes (confused), lecture progress bars (got it / revising / confused / not started), upcoming reminders (overdue, today, next 7 days; tag filter), exam countdown from the nearest `#exam` reminder.
- v0.2 adds: due review count + Start review, "Fading soon" (FSRS retrievability predicted < 0.85 within 2 days), weekly summary line.
- Notes inbox is **not** on Today (sidebar badge only).
- **AC:** with no data, Today shows a single clear "Add your first course" action.

### 5.10 Reminders [v0.1, .ics in v0.2]
- Quick add (`R` or on Today): natural-language text → parsed date + `#tags` → confirm. Built-in tags: exam, assignment, lab, quiz, revise; custom tags with colour.
- Optional link to course/lecture/node; clicking opens it.
- `#exam` reminders drive the exam countdown. No separate exam setting.
- v0.2: "Add to calendar" → `.ics` file.
- Notifications only while the app is open (documented honestly).
- **AC:** "lab exam 14 nov #exam" → due date Nov 14, tag exam, countdown shows it.

### 5.11 Pomodoro [v0.1, recall in v0.2]
- Global timer chip in the shell on every screen; `P` start/pause; presets 25/5, 50/10, custom.
- Keeps running across navigation; remaining time in the browser tab title; optional system notification (ask permission once).
- Break screen: "Break — look away from the screen". Skip allowed. Never interrupts typing: shows "finish your thought", switches after 60 s.
- During a session: suppress suggestions/nudges.
- v0.2: end-of-session "Quick brain check" — 3 questions from nodes touched this session; summary line "25 min · 2 nodes · 8 cards".
- **AC:** timer survives navigation and page refresh (state persisted).

### 5.12 Practice & review [v0.2]
- Practice tab on each node: its cards + saved questions; add/edit/delete.
- Card sources: generated from node slides, from kept exchanges, from notes, from Generate.
- FSRS scheduling (`fsrs` package) for both cards and questions; ratings Again/Hard/Good/Easy (keys 1–4, space to flip). Questions use the answer box before reveal.
- Review session screen: one item, nothing else; links to node and slide; course-wide queue, filter by lecture.
- Anki export (`genanki`) per course or lecture.
- **AC:** ratings update `fsrs` state and `review_log.jsonl`; due counts on Today match the queue.

### 5.13 Recall tests [v0.2]
- **Blank-map recall:** labels hidden; user types the label for each node position; fuzzy match first, LLM judges near-misses (synonyms) → score per node.
- **Explain-it-back:** user explains a node in their own words; AI lists what's missing or wrong with slide citations.
- Both append to `results.jsonl`.

### 5.14 Performance-based status [v0.2]
- `status_mode: auto` by default once a node has ≥ 3 results; manual override sets `manual`.
- Rule (tunable in one place): got_it if last 3 recall results ≥ 80% and no Again in last 2 reviews; confused if last 2 results < 50% or ≥ 2 Agains in a week; else revising.
- Course progress overview uses these statuses.

### 5.15 Settings & Ollama onboarding [v0.1]
- First run wizard: choose data folder → check Ollama (`GET /api/tags`); if down: "Install Ollama" link + Retry.
- Read system RAM (`psutil`) → recommend models from `config/recommended_models.json` (editable without code changes); one-click pull with progress (`/api/pull`).
- Any installed model selectable per slot; label vision-capable models; "Test on my slides" runs map generation on a chosen deck and shows the result.
- Repeated JSON failures from a model → visible warning suggesting a larger model.
- Also: theme, pomodoro presets, keep-all-questions toggle, Export/Import course (zip), open data folder.

### 5.16 Local usage log [v0.1]
- Append feature-use events to `usage.jsonl` (feature name + timestamp only). Never displayed in UI, never sent anywhere. Off switch in settings.

---

## 6. UI reference

**The full UI spec is in `UI.md`, with reference mockups in `docs/ui/` (PNG + HTML). Follow it exactly; library defaults never override it.**

Screens: Today · Course · Lecture map + side panel · Focus mode · Generate · Review session · Settings/Onboarding.

Tokens (light): ground `#F4F5F7`, surface `#FFFFFF`, border `#E3E6EB`, text `#16181D`, muted `#5B616E`, accent `#2F4FC9`.
Status: got it `#0F766E` · revising `#FBBF24` · confused `#EA580C` · not started = outline. Status always shown with a text label too.
Font: IBM Plex Sans (UI), IBM Plex Mono (counts, shortcuts) — bundle locally, no CDN.
Accessibility: real buttons/inputs/labels, text contrast ≥ 4.5:1, touch targets ≥ 44 px, full keyboard use.

---

## 7. Prompts

- Live in `backend/prompts/*.md` with a version header. Loaded at startup; never inline long prompts in code.
- Required: `map_chunk`, `map_merge`, `node_answer` (modes: normal / try_first / hint), `test_me_generate`, `grade_answer`, `generate_items`, `suggest_node`, `file_note`, `explain_back_review`, `recall_judge`.
- Every prompt that uses slides must say: answer only from the provided slides; if not covered, say so.
- Structured outputs always use a JSON schema generated from the pydantic model.

---

## 8. One-run executable

- `backend/launcher.py`: pick a free port → start Uvicorn → open the default browser → single-instance lock (second launch just opens the browser to the running app).
- `scripts/build_exe.py`: builds the frontend (`vite build`) into `backend/static/`, then PyInstaller one-folder build with fonts, prompts and config included.
- GitHub Actions workflow builds Windows, macOS and Linux artifacts on tag `v*` and attaches them to a GitHub Release.
- Ollama is not bundled; onboarding handles it.
- **AC:** on a clean machine with Ollama installed, download → double-click → onboarding appears in the browser within 10 s.

---

## 9. Quality bar

- **Tests:** storage (atomic writes, migrations), parsers (fixture decks), map pipeline with `FakeProvider` (valid tree, caps, coverage), FSRS integration, reminder parsing, API happy paths. `pytest` must pass before each milestone is done.
- **Performance:** UI interactions < 100 ms; map of 100 nodes renders smoothly; uploads up to 100 MB.
- **Errors:** every LLM/Ollama failure shows a plain message and a retry; no silent failures; no data loss on crash (atomic writes).
- **Docs:** README with what it is, install (Ollama + executable), dev setup, data folder explanation, honest limitations (local model quality depends on RAM; notifications only while open).

---

## 10. Milestones (build in order; each ends usable)

| # | Milestone | Done when |
|---|---|---|
| M1 | Skeleton: FastAPI + React shell, settings, data folder, storage layer, Ollama status | App runs via `scripts/dev.sh`; courses can be created and persist |
| M2 | Upload → parse → map pipeline → render | A real deck produces a validated map with slide links + coverage banner. **Checkpoint: user tests on 3 real decks locally** |
| M3 | Map editing + AI node actions | AC 5.3 pass |
| M4 | Side panel + Focus + thread (try-first, temporary/keep) | AC 5.4, 5.5 pass |
| M5 | Test me + notes/inbox | AC 5.6, 5.7 pass |
| M6 | Generate panel | AC 5.8 pass |
| M7 | Today + reminders + pomodoro (v0.1 parts) | AC 5.9–5.11 pass |
| M8 | Onboarding wizard + recommended models + executable build | AC 8 pass. **v0.1 release. Checkpoint: user uses it for ~1 week before M9** |
| M9 | Practice tab + FSRS + review session + Anki export | AC 5.12 pass |
| M10 | Blank-map recall + explain-it-back | 5.13 works on a real lecture |
| M11 | Performance-based status + course progress | 5.14 rules covered by tests |
| M12 | Today v0.2 (due, fading soon, weekly) + .ics + pomodoro recall | 5.9–5.11 v0.2 parts pass. **v0.2 release** |
