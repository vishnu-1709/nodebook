# Working rules for Claude Code — Nodebook

Read `SPEC.md` fully before any work. It is the source of truth.

## Mode: autonomous
Work continuously through the milestones in order (SPEC §10), M1 → M12, without waiting for review.
Only stop when you genuinely need something from the user (see "Ask the user only when").
SPEC checkpoints (M2, M8) are **non-blocking**: note what the user should test locally in PROGRESS.md and keep going.

## How to work
- One branch per milestone: `m<N>-<name>`. When a milestone's tests pass, merge it into `main` yourself (squash merge), then branch the next one from `main`.
- Small commits with clear messages. Run `pytest` (and frontend tests) before merging a milestone.
- Before each milestone, write a short plan at the top of PROGRESS.md (not a message to the user), then build.

## Never lose work (sessions can stop at any time)
- Commit and push after every working step (at least every ~30 min of work). Never leave important work only uncommitted.
- Keep `PROGRESS.md` up to date on every push: current milestone, done, in progress (exact file/function), next 3 steps, decisions made, things for the user to test locally, how to run.
- When starting any session: read `PROGRESS.md` first and continue from "next steps". Don't redo finished work.

## Ask the user only when
- You need something only they can provide: real lecture decks for fixtures (ask once, early in M2), credentials, or access.
- A product decision is genuinely ambiguous and a wrong guess would be costly to undo. Otherwise pick the option most consistent with SPEC §1 principles, record it under "Decisions" in PROGRESS.md, and continue.
- Something destructive: deleting user data, force-pushing, rewriting `main` history.
- You want a heavy or unusual dependency beyond SPEC §2. Small, well-known libraries are fine: add them and list them under "Decisions".
While waiting for an answer, keep working on anything that doesn't depend on it.

## Environment facts
- This cloud environment usually cannot run real Ollama models. Use `FakeProvider` for tests and development, and list real-model checks for the user in PROGRESS.md.
- Never commit the user's private files; put shareable samples in `tests/fixtures/decks/`.
- Data-shape changes (SPEC §3) are fine before the v0.1 release without migrations; after v0.1, every change needs a migration.

## Code rules
- Python: type hints, pydantic models for all data, no global mutable state outside `core/`. All file I/O through `core/storage.py` + `core/paths.py`.
- Prompts only in `backend/prompts/*.md`. Model recommendations only in `config/recommended_models.json`.
- Frontend: TypeScript strict, CSS tokens from `styles/tokens.css`, no inline colour literals, no UI library beyond those in SPEC.
- Never bind the server to anything but 127.0.0.1. Never send user data anywhere except the configured LLM endpoint.
- Keep the UI calm (SPEC §1): no animations > 200 ms, no gamification, no extra decoration.
