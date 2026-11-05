# 0023 – Looks lane clean-up: tooltips and small fixes

**Who:** worker · **Status:** running · **Branch:** `task/0023-looks-clean-up`
**Started by:** lead chat, 5 Nov 2026 · **Lane:** Looks · **Area:** panels 1 Import, 2 Structure,
3 Looks (`blender/ui.py` those panels, `blender/ops_main.py`, `blender/ops_panels.py`,
`blender/ops_import.py`, `blender/props.py` descriptions), `docs/USER-GUIDE.md` chapters 1–3,
`docs/TOOLTIPS-TODO.md`. Small task.

## Goal

Every button and setting in sections 1–3 explains itself when the owner hovers over it, and the
small loose ends of tasks 0010/0015/0021 are tidied up.

## What to do

1. The 14 Looks-lane rows of `docs/TOOLTIPS-TODO.md` (mostly one text shared by two buttons that
   do different things): write proper tooltips (style guide at the top of `docs/USER-GUIDE.md`),
   delete the rows; `tools/tooltip_report.py` shows nothing left for panels 1–3.
2. "Paint faces" header says "1 face sets": singular/plural right everywhere in panels 1–3
   (search for other count labels with the same problem).
3. User guide chapters 1–3: check they match what is on `main` now (0.2.13 and later: rule sets,
   paint faces); pictures from the test crane (`tools/guide_screens.py`).

## Done when

- [ ] Tooltip report clean for panels 1–3; TOOLTIPS-TODO rows gone
- [ ] Plural fix with a test
- [ ] Guide chapters 1–3 current
- [ ] Full suite passes, GitHub run green; report filled in; merged and released
      (`CLAUDE.md` sections 2 and 7)

## Not in this task

- `core/part_types*.py` (task 0022 runs there). Panels 4–7 (other lanes).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
