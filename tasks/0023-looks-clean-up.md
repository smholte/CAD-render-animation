# 0023 – Looks lane clean-up: tooltips and small fixes

**Who:** worker · **Status:** done (0.2.15) · **Branch:** `task/0023-looks-clean-up`
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

- [x] Tooltip report clean for panels 1–3; TOOLTIPS-TODO rows gone
- [x] Plural fix with a test
- [x] Guide chapters 1–3 current
- [x] Full suite passes, GitHub run green; report filled in; merged and released
      (`CLAUDE.md` sections 2 and 7)

## Not in this task

- `core/part_types*.py` (task 0022 runs there). Panels 4–7 (other lanes).

---

## Report (filled in by the chat that did the task)

**Chat / date:** worker chat, 5 Nov 2026 (afternoon).

**What changed:**
- **Tooltips, sections 1–3.** The 14 Looks-lane rows of `docs/TOOLTIPS-TODO.md` are done and
  deleted. Where one operator sits on two buttons it now has a `description()` with one text per
  button: open all / close all next to Find in the tree, Show only the unsorted parts / Show
  only these, + / From clicked part (names the clicked part), rule up / down, tick / untick all.
  The button "From active part" is now called "From clicked part" (no Blender word on it).
  New texts for the update report's ×, Select the ticked parts, and the name fields of the
  visibility-set and paint-scheme lists. Blender words taken out of the other tooltips of these
  sections ("active group", "parent", "cached imports", "active copy"), and Only this copy says
  what it does. The If / test drop-downs of a sorting rule explain each choice
  (`props.FIELD_HELP`, `props.OP_HELP`). The value field said "has no value" for the choice
  that is called "is empty". `tools/tooltip_report.py`: nothing missing or weak left in panels
  1–3 (Paint faces and Props for scale are now mapped to their lanes in the report).
- **Tooltips broke mid-sentence.** Blender keeps the line breaks of an operator's docstring, so
  every docstring wrapped in the source showed a tooltip broken in the middle of a sentence (on
  `main` before this task: 23 operators, all lanes, e.g. Render image, Add camera, Defaults).
  `register()` in `fresing_render/__init__.py` now joins the lines; a test checks every
  operator. Lanes can keep wrapping docstrings in the source.
- **"1 part", not "1 parts".** `core/words.py` (`plural`, `verb`) used in panels 1–3 (Paint
  faces header "1 face sets" → "1 face set", 2 Structure header, model box "on 1 core",
  subassembly "(1 part)", visibility set, 3 Looks header "1 group", unsorted warning "1 part
  matches no rule: it is in 'Unsorted'", Find "1 name, 1 part"), in the messages of their
  buttons, in the rule-set switch window ("1 part changes group", "1 group goes away"…), the
  rule-set menu, the model update report and the import progress line. Clean-up's message now
  names the button as it is labelled (Restore all).
- **User guide, chapters 1–3** checked line by line against the panels on `main` (0.2.13):
  chapter 3 had the old "Rule: all of … → this group" button (now Make it a rule under
  "Everything in … to this group"), only {color}/{finish}/{kind} as group-name placeholders
  ({part_type} and {cad_material} were missing), + and From active part without where the rule
  goes, no Select the ticked parts, and Show all where Show everything again is meant.
  Chapters 1 and 2 matched. Pictures: all panel pictures of sections 1–3 made again in the real
  app (`tools/guide_screens.py`, test crane); all came out pixel-identical to the ones in
  `docs/img/` except panel_1_import (only "read in 3 s" instead of 1 s: not replaced),
  panel_3_faces (header now "1 face set": replaced) and panel_3_rules (From clicked part:
  replaced).

**Tested and measured** (name the machine and the model):
- New tests: `test_plural_says_one_part_and_two_parts` (core), `test_counts_of_one_are_singular_in_panels_1_to_3`
  (draws panels 1–3 with counts of 1 and 3, the Structure header, the rule-set switch window and
  menu text), `test_tooltips_have_no_line_breaks` (every operator). The two panel tests failed on
  the code of `main` before the fix ("1 parts"; 27 operator tooltips with a line break, 23 of them
  shown) and pass now.
- Full suite on the 2-core test machine: 1,426 passed on the branch; after merging `main`
  (0.2.14, task 0022): 1,650 passed. GitHub run of the branch before the merge: all four jobs
  green (pytest 1,426 passed; real app ui1 23/23, ui2 39/39, faces 10/10, surroundings 23/23,
  rule sets 17/17, paths 8/8; Windows install + self-test OK).
- Tooltip check (`tools/tooltip_report.py`), whole side panel: `main` before 237 buttons and
  settings, 41 missing, 27 weak; now 39 missing, 15 weak – the 14 that were the Looks lane's,
  none left in panels 1–3 (the rest are the Motion and Scene & Render lanes').
- Real app (Blender 5.2.3 Linux build under xvfb, test crane): guide pictures of sections 1–3 made
  twice; compared pixel by pixel with `docs/img/`. The renamed button fits ("From clicked part",
  not cut off at the default side-panel width).
- User guide built (`tools/build_guide.py`) and the changed passages read in the page; release zip
  built from `main` (`tools/build_release.py`).
- Nothing here changes import, render or sorting speed: no timings measured.

**Open points / follow-up tasks:**
- Outside the Looks lane, touched on purpose (small, additive): `fresing_render/__init__.py`
  (`register()` joins docstring lines; other lanes' operators get one-line tooltips too),
  `ops_motion.py` (only the docstring of the update report's ×, `fresing.report_clear`, which is
  drawn in 1 Import), `reimport.py` (one line: the report title), `tools/tooltip_report.py`
  (lane map). Lanes that merge after this can keep wrapping docstrings.
- Other lanes' messages can still say "1 subassemblies added" (`ops_motion.py` joint members),
  "1 pieces … moved apart" (Explode) and "1 props deleted" (`ops_surroundings.py`):
  `core/words.plural()` is there for them when those lanes next touch the files.
- Next in the Looks lane: 0024 decals can start.
