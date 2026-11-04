# Nodebook — UI Spec

The look and layout to build. **Reference mockups:** `docs/ui/*.png` (what it should look
like) and `docs/ui/*.html` (open in a browser and inspect exact sizes, colours, spacing).
Match them closely. Where this file and a mockup differ, **this file wins** (some features
were added after the mockups).

Library defaults never win: if Mind-Elixir or any component's default look differs from
this spec, override it.

---

## 1. Foundations

### Tokens (`frontend/src/styles/tokens.css`)

| Token | Light | Dark |
|---|---|---|
| `--ground` (page) | `#F4F5F7` | `#15171C` |
| `--surface` (cards, panels) | `#FFFFFF` | `#1D2027` |
| `--surface-2` (subtle fills) | `#F7F8FA` | `#252932` |
| `--border` | `#E3E6EB` | `#2E333D` |
| `--border-strong` (inputs, buttons) | `#D5D9E0` | `#3A404C` |
| `--text` | `#16181D` | `#E8EAEE` |
| `--text-2` (secondary) | `#3E4450` | `#B9BEC8` |
| `--muted` | `#5B616E` | `#8E95A2` |
| `--accent` | `#2F4FC9` | `#6E8BFF` |
| `--accent-soft` | `#EEF1FC` | `#232B4A` |
| `--ink` (root node, primary dark buttons) | `#16181D` | `#E8EAEE` (text `#15171C`) |
| `--line` (map connectors) | `#C9CED8` | `#4A505C` |
| `--status-got` | `#0F766E` | `#2BB3A6` |
| `--status-revising` | `#FBBF24` | `#FBBF24` |
| `--status-confused` | `#EA580C` | `#FB7A3C` |
| `--status-confused-soft` | `#FFF1E8` | `#3A2418` |
| `--status-confused-text` | `#9A3412` | `#FDBA8C` |

Theme: `data-theme="light|dark"` on `<html>`, default follows `prefers-color-scheme`.
Never pure black or pure white backgrounds in dark mode.

### Type
- IBM Plex Sans (UI), IBM Plex Mono (counts, shortcuts, slide counts). Bundled locally.
- Sizes: page title 30/700 · screen title 18/600 · panel title 22/700 · focus title 32/700 ·
  body 14–15/400 · small 13 · labels 12/600 uppercase +0.04em (sidebar section only).

### Spacing, shape, motion
- 4px grid. Common: 8, 12, 16, 20, 24, 32, 40.
- Radius: buttons/inputs 8 · cards 12 · large cards 14–16 · chips 6 (square) or 14–16 (pill).
- Borders 1px. No shadows except a very soft one on popovers/menus.
- Motion: 150–200 ms ease-out for panel open/close, card flip, status colour change. Nothing else animates.
- Min touch target 44px for primary controls; 32px allowed for chips inside panels.

### Shared components
- **Button primary:** `--accent` bg, white text, 600, h 44, px 16, radius 8.
- **Button dark:** `--ink` bg (Start review, Test me, Check my answer).
- **Button secondary:** `--surface` bg, 1px `--border-strong`, `--text`.
- **Chip toggle (pill):** off = surface + border-strong; on = `--accent-soft` bg, `--accent` text, 1px `#B8C3EE` (or filled accent for source chips in Generate).
- **Slide chip:** `--accent-soft` bg, `--accent` text, 12px, radius 6 — click opens slide preview popover.
- **Status segmented control:** 3 equal buttons Confused / Revising / Got it; selected uses that status's soft bg + 1.5px status border + status text colour.
- **Status dot:** 9px circle filled with status colour; not started = 1.5px outline `--muted`. Always paired with a text label somewhere nearby (a11y).
- **Count badge:** mono 11px, pill, `--accent` bg white text (kept questions) or `--border` bg (secondary counts).
- **Shortcut hint:** mono 12px `--muted`, e.g. `G generate · N note`.
- **Tabs:** text tabs, selected = 600 + 2px `--accent` underline.
- **Empty states:** one sentence + one primary action. No illustrations.

---

## 2. App shell (all screens except Review session and Focus mode)

- **Left sidebar** 240px, `--surface`, right border. Top: wordmark **"Nodebook"** (text only, 18/700). Nav: Today · Review (due badge) · Notes inbox (count). Section label **COURSES**, course list, **+ New course** (dashed border button). Bottom: Settings, Shortcuts `?`, Ollama status line (green dot + model name, or orange "Ollama not running").
- Active nav item: `--accent-soft` bg, 600.
- **Pomodoro chip** in the top-right of every screen's header (and in Focus/Review headers): clock icon when idle; `18:42` mono when running; click opens a small popover (start/pause, preset, skip).
- On narrow widths (<900px) the sidebar collapses to a top bar with a menu button.

---

## 3. Screens

### 3.1 Today — `docs/ui/today.png`
- Header: date (13 muted) + "Today" (30/700). Right: **+ Quick note `N`** (secondary), **Generate `G`** (primary).
- **Next-action cards** (grid, auto-fit min 260px, gap 16): Due for review (big number + "cards · about N min" + dark **Start review**) · Fading soon (topic name 18/600, lecture + count, "Open topic →") · Next exam (days big number, exam name, "N topics still confused" in confused text colour).
- **Upcoming reminders** card (not in mockup): list sorted overdue (confused colour) → today → next 7 days; each row: tag chip, text, relative date, checkbox to complete; tag filter chips at top; "+ Reminder `R`" button.
- **Lectures** card for the current/last course: rows = lecture name · stacked status bar (10px tall, radius 5: got/revising/confused/not started) · node count (mono). Legend top-right. "+ Add lecture (drop PPT / PDF)" dashed button.
- No notes inbox on Today.
- v0.1 hides Due/Fading cards (no FSRS yet) and shows "Weak topics" instead.

### 3.2 Lecture map + side panel — `docs/ui/map-side-panel.png`
**Header bar** (surface, bottom border, h ~68): back link "← Course name" · lecture title 18/600 · tabs Map / Sources / Notes (segmented, grey track) · right: shortcut hint, **Recall test: rebuild this map** (secondary, v0.2), `⋯` menu (Generate, Note, Regenerate map, Export).

**Coverage banner** (when slides are uncovered): `--accent-soft` bg, radius 12, text "Slides 2, 24 and 25 aren't in the map — add them?" + View (secondary) · Add to map (primary) · Dismiss (text).

**Map canvas** (fills remaining space): `--surface` with dot grid (`radial-gradient(var(--border) 1px, transparent 1px)` 20px), radius 12, 1px border. Toolbar top-left (vertical, small): layout, fit to screen, zoom ±.

**Map nodes — every level boxed (most important rule):**
| Level | Style |
|---|---|
| Root | `--ink` bg, white 15/700, radius 10, padding 12×20, min-width 140 |
| Level 1 | `--surface` bg, 1px `--border-strong`, radius 8, padding 8×12, 14/500 |
| Level 2+ | same box, 13/400, padding 6×12 |
| Selected | `--accent-soft` bg, 2px `--accent` border, 600 |
| Hover | border `--accent` at 50% |
- Inside each node: status dot (left) · label (wraps, max-width 220px, **never truncated**) · kept-question badge (right, only if > 0).
- **Connectors:** 2px `--line`. Elbow or smooth curves both fine; no underline-style nodes.
- Layout: root left, children to the right (Mind-Elixir right-side layout). On load and after regenerate: **fit to view**.
- New node default label "New topic", opens straight into edit mode.
- Right-click menu: Expand · Split · Merge with… · Simplify · Delete. AI results show a preview diff (green new nodes) with Apply / Cancel.
- Footer hint chips under the canvas: "Right-click a node: Expand · Split · Merge · Simplify" · "Drag to rearrange".

**Side panel** (right, 420px, surface, left border, padding 20×24), shown when a node is selected:
1. Breadcrumb (13 muted) + node title (22/700) · **Expand `F`** button top-right.
2. Slide chips row · **Test me · 3 Qs** (dark button) on the right.
3. Status segmented control.
4. Tabs: **Thread · n** / **Notes · n** / **Practice · n** (mockup says "Cards" — use "Practice").
5. **Thread tab:**
   - Kept exchanges first. User bubble: `--ink` bg, white, radius 12 12 4 12, right-aligned, max 85%. AI bubble: `--surface-2`, radius 12 12 12 4. Try-first question bubble: `--accent-soft` with "Try first" label 12/600 accent.
   - Under each AI answer: Make flashcard · Pin as note · Add as child (small secondary buttons, 32px).
   - **Keep pin** icon button on each exchange (top-right of the exchange group). Kept = filled pin + accent.
   - **Recent doubts** section below kept ones: same bubbles at 70% opacity text-2 colour (contrast must stay ≥ 4.5:1), label "Temporary · clears in N days".
   - After ≥ 3 back-and-forths: inline soft prompt "Keep this?" [Keep] [No].
6. **Composer** pinned to bottom: chips Try first: on · Hint only · More help ▾ (Explain why, Give example) · input "Ask about <node>…" + **Ask** (primary).

No node selected → panel shows lecture summary: node counts by status, uncovered slides, "Click a node to start".

### 3.3 Focus mode — `docs/ui/focus-mode.png`
- Same panel content, full screen, centred column max 820px, `--ground` background, no sidebar, no map.
- Header: "↙ Collapse to map + panel" (left) · breadcrumb (centre) · pomodoro chip + "Esc to exit" (right).
- Title 32/700 + slide chips; status control right-aligned.
- **Test yourself card:** `--ink` bg, white text: "Test yourself on this topic" + "3 recall questions from slides x–y · about 2 min" + white **Test me** button. Always above the tabs.
- Thread bubbles: user = surface + border; AI = surface + border; try-first = accent-soft.
- Composer in a bordered surface box at the bottom.
- Transition panel ↔ focus: 180 ms expand; keep draft text and scroll position.

### 3.4 Test me (modal over panel or Focus)
- One question at a time, progress `1 / 3`. Question 18/600. Textarea "Your answer". **Check** (dark). Result row: Correct (got colour) / Partly (revising) / Wrong (confused) + one-line feedback + slide chip. Next →. End: score summary + "Back to topic".

### 3.5 Generate — `docs/ui/generate.png`
- Full screen with header: "← Back" · "Generate · <course>" · "Saved this session: n".
- Left column (min 340px): **1 · Use these sources** (source chips, selected = filled accent with ✓; "+ Upload" dashed) · **2 · Make** (2×2 radio cards: Practice questions / Flashcards / Summary / Explain a topic; selected = accent-soft + 2px accent) · **3 · Steer** input + chips Harder / Easier / Conceptual / Numerical.
- Right column: result card (surface, radius 14, padding 28): "Question n" (mono) + "Similar to PYQ 2023, Q4(b)" · question 20/500 · "Saves to [L5 › Least squares ▾]" · **Your answer** textarea · **Check my answer** (dark) + "Skip, show answer" (underlined muted text) + "AI answers · check them" tag (confused-soft bg, confused-text).
- Action row (3 equal buttons, h 52): Discard · Next → · **Save + review later** (primary). Hint line: "Saved questions come back in your review queue". Shortcut hints `D` `→` `S`.

### 3.6 Review session — `docs/ui/review-session.png`
- No sidebar. Top: "✕ End session" · "<course> · 9 cards + 3 saved questions" · `5 / 12` mono · pomodoro chip. 4px progress bar.
- Centred card max 680px, padding 40, radius 16: node path (13 muted) + status · question 24/600 · divider · answer 18 (after flip; questions require the answer box first) · links Open node · See slide n.
- Rating row, 4 equal buttons h 64: Again (confused text, soft border) · Hard · **Good** (primary) · Easy, each with next interval in mono 12. Keys `1 2 3 4`, space = flip.

### 3.7 Course page
- Header: course name 30/700 · Generate · + Add lecture.
- Tabs: Lectures (rows as on Today) · Sources (file list: name, type icon, pages, "used in" lecture, upload) · Saved (filterable list of practice items + notes by type/lecture) · Notes (course notes).

### 3.8 Onboarding & Settings
- Onboarding: centred card max 560px, 3 steps with a step indicator: Data folder → Ollama check (status, Install link, Retry) → Models (RAM shown; recommended model per slot with "Recommended" badge, vision badge; Download with progress bar; "Test on my slides").
- Settings: left list of sections (General, AI models, Study, Pomodoro, Data), right form. Plain, no extra decoration.

### 3.9 Quick note, reminder, pomodoro popovers
- Quick note (`N`): small popover centred near the top, single-line input expanding to 3 lines, destination chip ("→ L5 › Least squares", changeable), Enter saves, Esc closes. Toast "Saved" 1.5 s.
- Reminder (`R`): same popover; parsed date and tags shown as chips below the input before confirming.
- Break screen: full overlay `--ground`, centred "Break — look away from the screen for a bit", remaining time mono, Skip break (secondary). No images.

---

## 4. Done = looks right
For each screen, put a screenshot next to the matching `docs/ui/*.png` (light and dark) in
PROGRESS.md and check: every map node boxed, no truncated labels, status colours visible,
contrast ≥ 4.5:1, keyboard shortcuts work, nothing animates beyond §1.
