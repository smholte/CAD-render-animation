# 0330 – Animation keeps the user's keys (0328 F1)

**Who:** worker · **Status:** open · **Branch:** `task/0330-animation-keeps-user-keys`
**Started by:** lead, 25 Nov 2026 (from 0328's report, owner's focus: user friendliness) · **Model:** Opus · effort Medium
**Area:** Motion lane – `blender/animation.py`, `blender/queue.py` (the warning before a queued Build), `blender/turntable.py`, `blender/lead_motions.py` (logic only, not its panel), their tests, guide, CHANGELOG.
**Not:** `ui_lead_motions.py` (0333), `ui_motion.py` (0333), the Keys / top bar (0295).

## Goal

An animator never loses a key or a step without being asked: a Graph-Editor edit survives the next Build (or the app asks Keep / Replace), a faded part keeps its own hand keys, a second Turntable click replaces only its own orbit step, a lead slider on a built animation says so or takes the Build off, and the timeline fits a new Build.

## What to do

Fix 0328's rows **2, 3, 4, 8, 35** (`tasks/0328-bug-and-friction-hunt-8.md`, table "Rows"; grouping "Grouping into fix tasks"). Rows 3 and 2 first (lost work), then 4, 8, 35.

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
