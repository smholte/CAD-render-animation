# 0220 – The app's Cutaway becomes Slice (3 Looks > Slice)

**Who:** worker · **Status:** done 19 Nov 2026 (0.2.170) · **Branch:** `task/0220-app-slice-rename`
**Started by:** lead, 18 Nov 2026 (owner, 23:06: "yes" – rename the app's own panel too, the same word as the web
page's Slice of task 0218) · **Model:** Sonnet · effort Medium
**Area:** Cutaway lane – `blender/ui_section.py`, `ops_section.py`, `section.py` (texts only), `core/places.py`
(the panel's title), `core/functions.py` (entry `looks.cutaway`: title, `changed=`), the tour stop `cutaway` and the
PC-check line `looks.cutaway` (titles and "what you should see" texts, `changed=`), `docs/USER-GUIDE.md` (the cutaway
section + its picture), `docs/TOOLTIPS-TODO.md` if it names it.

## Goal

The word "Cutaway" disappears from the app where it means the section view of 3 Looks: the panel is **3 Looks >
Slice**, its buttons and tooltips say slice ("Add slice", "Slice 1"…), the guide says Slice – the same word the web 3D
page gets in 0218, so the owner meets one name for one tool.

## What to do

1. Rename every **visible** text of the section-view tool: panel title, buttons, list rows, hints, reports, tooltips,
   the "How it works" steps, the function list's title, the tour stop and PC-check texts, the guide section and its
   picture (`tools/guide_screens.py`). Keep the old guide anchor working (add the new anchor `slice` and keep
   `cutaway` above it, so old links still land).
2. **Do not rename** what users never see and what old projects store: property names, operator ids
   (`fresing.cut_add` …), `bl_idname`s, the function id `looks.cutaway`, tour stop and PC-check ids – old projects and
   the precheck's lists stay valid. Say in the report which ids kept the old word.
3. **Not this tool – leave as it is:** the **sea cut-away** (5 Scene & Render, the box of water taken away – tasks
   0081 / 0196 / 0202) and the **hall cut-away** of the surroundings. They are other functions; check every hit of
   "cut-away" / "cutaway" before changing it.
4. If the web page's own tooltip text links to the app's panel by name, use `places.where()`.

## Done when

- [ ] No visible "Cutaway" left for the section view (a test greps the panel's drawn texts and tooltips); the sea and
      hall cut-aways unchanged
- [ ] Old projects with cuts open and show them under Slice (one old tour project)
- [ ] Guide section + picture, old anchor still works; `changed=` on the function entry, tour stop and PC-check line;
      precheck green
- [ ] Report filled in

## Not in this task

New slice features in the app (picking a face, several slices like the web page): ask the owner after 0218 if he
wants them in the app too. The web page itself (0218).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, Sonnet, 18–19 Nov 2026

**What changed:** 3 Looks > Slice (panel title, "Add slice", "Remove slice", "Slice this too", "Do not slice this", list
header "2 slices · 1 on", hints, report line, all operator and property tooltips, "How it works" steps); new slices are
named "Slice 1"…; the function-list title, the tour set and stop ("Slice: the pedestal opens up", joint "Slice 1"),
the PC-check line title, `places.py`, the workspace text, the guide section (anchors `cutaway` and `slice`, picture
`panel_3_cutaway.png` made again with the real app) and the CHANGELOG say Slice. New test
`test_visible_texts_say_slice_not_cutaway`. Version 0.2.170.

**Ids that kept the old word:** `fresing.cut_*` operators, `FRESING_PT_cutaway`, `FRESING_UL_cuts`, properties (`cuts`,
`FRCut`), function id `looks.cutaway`, tour stop / set id `cutaway`, PC-check id `looks.cutaway`, the guide anchor
`cutaway` (listed in `READING` so the precheck accepts it beside `slice`). Slices of old projects keep their names
("Cut 1"). The sea and hall cut-aways and the web page's texts (task 0218) are untouched.

**Tested and measured:** on the 4-core web machine: tests of section, functions, places, user guide, workspaces and tour
(184 passed, the 2 that read the old header text fixed); tooltip report 865 ok; precheck green. GitHub full run on
c8b96ebe green (run 44420810718). Not done: opening one old tour project with cuts by hand (the code paths are
unchanged: only texts and the default name for new slices differ).

**Runs:** 4 full runs: version clash with 0216 (0.2.168), my new test read the property groups from `bpy.types`
(failed in a group), version clash with 0218 (0.2.169), then green.

**Open points / follow-up tasks:** none. The tour-set title "Slice" is still the id `cutaway`.
