# 0337 – Lifting plans and Remove (0328 F9)

**Who:** worker · **Status:** open · **Branch:** `task/0337-lifting-with-remove`
**Started by:** lead, 25 Nov 2026 (from 0328's report, owner's focus: user friendliness) · **Model:** Sonnet · effort Medium
**Area:** Lifting lane – `blender/lifting.py`, `blender/ui_lifting.py`, one hook in `blender/remove.py` (`plan` / `remove` call `lifting.remove` for a crane root), their tests, guide, CHANGELOG.
**Not:** Remove's own window and other kinds of models (0292 done; only the hook).

## Goal

Removing a placed crane removes all of it (rope, drum, sheaves, joints, poses, its plan entry) or the Remove window says it is a crane; a load with no parts left shows a red line and is not used.

## What to do

Fix 0328's rows **22, 24** (`tasks/0328-bug-and-friction-hunt-8.md`, table "Rows"; grouping "Grouping into fix tasks"). Row 22 first.

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
