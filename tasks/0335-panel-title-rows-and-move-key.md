# 0335 – Whole title row opens a panel; second G unlocks (0328 F6 + row 29)

**Who:** worker · **Status:** open · **Branch:** `task/0335-panel-title-rows-and-move-key`
**Started by:** lead, 25 Nov 2026 (from 0328's report, owner's focus: user friendliness) · **Model:** Sonnet · effort Medium
**Area:** Side panel + Place (two small fixes, separate files) – `blender/panels.py` (`draw_title`), `blender/place.py` (the move key), their tests, guide, CHANGELOG.
**Not:** any panel's own content (other tasks own those files).

## Goal

Clicking anywhere on a section or sub-panel title row opens / closes it, as in Blender's own panels; pressing G on a model that import locked says "Press G again to unlock and move" and a second G does it.

## What to do

Fix 0328's rows **17, 29** (`tasks/0328-bug-and-friction-hunt-8.md`, table "Rows"; grouping "Grouping into fix tasks"). `panels.py` is used by every panel: screenshot every section before and after (`tools/ui_screens.py`).

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
