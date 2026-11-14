# 0120 – Bug-hunt fixes B: render queue, jobs during a bake, undo during long jobs, weather and redraw

**Who:** worker · **Status:** running (web session) · **Branch:** `task/0120-fixes-queue-render-undo` (or the web session's)
**Started by:** lead chat, 14 Nov 2026, from bug hunt 0118 (`tasks/0118-bug-hunt-3.md`)
**Area:** Scene & Render + queue: `blender/queue.py`, `ops_motion.py` (Add image), `states.py` (saved scene frame), `house_bake.py`, `ops_web3d.py`, `ops_house.py`, `ops_clash.py` (modal undo), `section.py` + `ui_section.py`, `ui_fade.py`, `ui_weather.py`, `weather.py` (`after_clear`), `animation.py` **additively** (a Build warning, `_channelbag`) – 0121 adds one call in `clear_keys`: merge carefully; their tests. **Do not edit:** `spool.py`, `paths_riders.py`, `tracks.py` (0119), `sequence.py`, `flex.py`, `vessel_motion.py`, `reimport.py` (0121), `importer/`, `build.py`, `faces.py` (0117).
**Model:** **Opus · effort Medium** · **Place:** Claude Code on the web, environment "CAD-render-animation"

## Goal

Fix rows **1, 6, 11, 13, 15, 16, 18** of the bug hunt (every-paint-scheme animation jobs render one colour; queued stills at the wrong frame; Start later / Start queue / Ctrl+S during a House bake copies a half-baked project; Ctrl+Z during web 3D export, House bake, clash check; writes at render start off the main thread; Build switching the weather off silently; per-redraw walks, a dead function, the orphan scene action). Row 18 (d) needs only a comment.

## How

- The rows' text in `tasks/0118-bug-hunt-3.md` (Findings) gives where, what happens, the proof and a suggested fix.
  Read each row, repeat its proof first (it must fail), then fix. **Every fix gets a test that failed before**
  (CLAUDE.md section 6). The suggested fix is a suggestion: a better one is fine, say why in the report.
- A row that turns out not to be real (cannot be shown on today's `main`): say so in the report, no change.
- No new features, no UI redesign. A visible change (a new warning, a note) gets its tooltip/guide line; no new tour
  stop or PC-check line is needed for a fix unless the row asks for one.
- One version at the end (take the number last, CLAUDE.md section 2).

## Done when

- [ ] Each row: fixed with a test that failed before, or shown not real (with how)
- [ ] Full run green on GitHub; CHANGELOG in plain words (what the owner would have noticed); version taken last
- [ ] Report filled in; TASKS.md row → done

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed (per row):**

**Tested:**

**Open points:**
