# 0336 – 3D page follow-ups (0328 F7)

**Who:** worker · **Status:** running · **Branch:** `task/0336-web3d-followups`
**Started by:** lead, 25 Nov 2026 (from 0328's report, owner's focus: user friendliness) · **Model:** Sonnet · effort Medium
**Area:** Web 3D lane – `blender/ui_web3d.py`, `blender/web3d.py`, `core/web3d.py`, `fr_player.js` (and the site copy it is built into), their tests, guide, CHANGELOG.
**Not:** `ops_make.py` window size (0331) – put the result where the eye is inside your own panel instead.

## Goal

After Export the result and Open page are in sight; a greyed choice says why; on a phone held sideways the menu stays clear of the play bar; the user chooses which cameras become page views (the app's own cameras off by default).

## What to do

Fix 0328's rows **14, 15, 21 (0179 open point), 31 + the meshopt word of row 32** (`tasks/0328-bug-and-friction-hunt-8.md`, table "Rows"; grouping "Grouping into fix tasks"). Row 14 first.

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
