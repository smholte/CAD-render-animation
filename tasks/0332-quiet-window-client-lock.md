# 0332 – Quiet window and Client view lock (0328 F3)

**Who:** worker · **Status:** running · **Branch:** `task/0332-quiet-window-client-lock`
**Started by:** lead, 25 Nov 2026 (from 0328's report, owner's focus: user friendliness) · **Model:** Opus · effort Medium
**Area:** Start & learn lane (quiet window) – after **0295** (both change `lock.py`) – `blender/quiet.py`, `blender/lock.py` (key lists: F2 / Ctrl+F2 / Ctrl+, and the render key), `blender/ops_settings.py` (`quiet_panels`, its use for the main view only), `blender/ops_workspace.py`, their tests, guide, CHANGELOG.
**Not:** the Keys tab (0295, done before you), menus and side-panel tabs as a whole (0222 package C later).

## Goal

"Back to the Fresing window" always brings the app's layout back; the Client view really locks (no renaming, no Preferences); a rendered picture shows whole and fitted with the app's words; outside Full access no Blender sidebar tabs and no redo panel.

## What to do

Fix 0328's rows **5, 7, 13 (the F12 key in `lock.py` and the image editor's header in `quiet.py`; the Render image button's fit is 0334's, in `ops_main.py`), 27, 28** (`tasks/0328-bug-and-friction-hunt-8.md`, table "Rows"; grouping "Grouping into fix tasks"). Rows 7 and 5 first.

## Watch

- Each row's **repeat case** and **proposed fix** are in `tasks/0328-bug-and-friction-hunt-8.md` ("Rows" table) – read those rows first, repeat the
  case, then fix. The proposed fix is a proposal: a better one is fine, say why in the report.
- Row 32's words: change only the words that are in **your** files (the row lists them by place).
- Every visible change: tooltip, user guide, PC-check line, tour stop / function-list entry with `since=` / `changed=`
  (CLAUDE.md section 2). Real-app check (`tools/ci_real_app.py`) for every row that was seen in the real app.
- Two tasks never share a file: stay inside **Area**; a needed change elsewhere → open point in the report.

## Done when

- [ ] Each row's repeat case now gives "what should happen" (a test per row; real-app check where it was seen there)
- [ ] Tests added/updated; full suite passes; GitHub run green
- [ ] (UI) screenshots checked with tools/ui_screens.py
- [ ] Guide, PC-check line, tour / function-list version fields as CLAUDE.md section 2 asks
- [ ] Report below filled in, merged, released

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
