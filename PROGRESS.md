# Nodebook — Progress

## Current milestone: M1 — Skeleton

### Plan (M1)
1. Backend core: `core/paths.py` (data-folder sandbox), `core/storage.py` (atomic JSON, per-file locks,
   jsonl append, schema versions + migrations), `core/ids.py` (ULID), `core/schemas.py` (pydantic shapes
   from SPEC §3), `core/settings.py` (platformdirs config), `core/jobs.py` (in-process background jobs).
2. LLM layer: `LLMProvider` interface, `OllamaProvider`, `OpenAICompatProvider` stub, `FakeProvider`.
3. API: courses CRUD, settings, jobs, ollama status; FastAPI app serving `backend/static/` + `/api`.
4. Frontend: Vite + React + TS strict, TanStack Query, Zustand; shell (sidebar, Today placeholder,
   course page, settings), tokens.css light/dark/system, shortcut framework, bundled IBM Plex fonts.
5. `scripts/dev.sh`, pytest + vitest.

### Done
- M1 complete: backend core (paths sandbox, atomic storage + per-file locks + migrations registry,
  ULIDs, pydantic schemas, settings in OS config dir, job manager), LLM providers (Ollama, OpenAI-compat
  stub, Fake), API (courses CRUD, settings, jobs, ollama status), React shell (sidebar, Today empty
  state, course page with rename/delete, settings with theme/data folder/Ollama/model slots), global
  shortcut framework (`?` help works), tokens.css light/dark/system, bundled IBM Plex fonts.
- Tests: 19 pytest, 3 vitest.

### Next 3 steps
1. M2: parsers (PDF/PPTX), upload endpoint, map pipeline with FakeProvider
2. M2: map rendering with Mind-Elixir, coverage banner
3. M3: map editing

## Decisions
- **Integration branch:** the cloud harness only allows pushing to `claude/gallant-cray-mdaoqn`, so that
  branch plays the role of `main`. Milestone branches `m<N>-<name>` are local and squash-merged into it.
  Merge it into `main` on GitHub when you're happy (or tell me to).
- Added small libs: `react-router-dom` (routes), `@fontsource/ibm-plex-sans|mono` (bundled fonts),
  `python-multipart` (FastAPI uploads), `jsdom` (vitest env).
- Backend port in dev is 8765 (Vite proxies `/api`). Launcher (M8) picks a free port.
- Derived slide data (extracted text + thumbnails) cached at `courses/<id>/derived/<source_id>/`
  (rebuildable from the source file; not in SPEC §3 layout).

## For the user to test locally
- (none yet)

## How to run
- `scripts/dev.sh` (or `NODEBOOK_FAKE_LLM=1 scripts/dev.sh` without Ollama) → http://127.0.0.1:5173
- Tests: `.venv/bin/python -m pytest`, `cd frontend && npm test && npx tsc -b`
- Dev overrides: `NODEBOOK_CONFIG_DIR` (settings location), `NODEBOOK_FAKE_LLM=1`.
