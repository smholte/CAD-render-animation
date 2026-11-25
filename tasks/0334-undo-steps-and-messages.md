# 0334 – One undo step per action; messages beside their own button (0328 F5)

**Who:** worker · **Status:** open · **Branch:** `task/0334-undo-steps-and-messages`
**Started by:** lead, 25 Nov 2026 (from 0328's report, owner's focus: user friendliness) · **Model:** Sonnet · effort Medium
**Area:** Looks / Scene & Render – `blender/ops_main.py` (incl. row 13's fit-the-picture after Render image in `RenderStill`), `blender/ui.py` (message place, triangle count words), a new test over all operators, guide, CHANGELOG.
**Not:** operators in files other tasks run in (0295, 0314, 0323, 0329, 0330–0337): the new test lists them as known gaps with the task that owns the file, it does not change them.

## Goal

Ctrl+Z undoes one action at a time everywhere in `ops_main.py`, and a message shows beside the button that made it, not under 1 Import.

## What to do

Fix 0328's rows **6, 30, 13 (only `RenderStill`: show the whole picture fitted) + a test that every operator writing scene data has UNDO + the "0.0 M triangles" words** (`tasks/0328-bug-and-friction-hunt-8.md`, table "Rows"; grouping "Grouping into fix tasks"). Row 6 first.

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
