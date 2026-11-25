# 0331 – First start stays open; windows open in a good place (0328 F2)

**Who:** worker · **Status:** running · **Branch:** `task/0331-first-start-and-windows`
**Started by:** lead, 25 Nov 2026 (from 0328's report, owner's focus: user friendliness) · **Model:** Opus · effort Medium
**Area:** Start & learn lane – `blender/first_setup.py`, `core/first_setup.py`, `blender/welcome.py` (only for row 1), `blender/ops_setup.py`, `blender/ops_make.py`, `blender/form_window.py`, the product video panel, `blender/ops_backups.py` (words only), their tests, guide, CHANGELOG.
**Not:** `lock.py`, `ops_settings.py`, `ui_settings.py`, `ui_topbar.py` (0295 runs there), `quiet.py` (0332), `ui_web3d.py` (0336).

## Goal

A new user sees "Set up Fresing Render" and it stays until Next / Skip / Close; every function / output window opens beside the side panel or over the middle of the view (the next one a little offset), never empty for seconds, never splitting the main window.

## What to do

Fix 0328's rows **1, 12, 25, 34 + the 0213 open point (Set-up window Back / Next in the Client view) + the "Your PC" words and the backups words of row 32** (`tasks/0328-bug-and-friction-hunt-8.md`, table "Rows"; grouping "Grouping into fix tasks"). Row 1 first (a new user's first minute). **Ask the owner once** to try a fresh first start on his PC: give him steps that do not lose his own settings (or a way to put them back), and the "For the lead chat" text to paste back. Do not wait for his answer to fix row 1.

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
