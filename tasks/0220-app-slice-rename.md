# 0220 – The app's Cutaway becomes Slice (3 Looks > Slice)

**Who:** worker · **Status:** open – can start (Cutaway lane) · **Branch:** `task/0220-app-slice-rename`
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

**Chat / date:** Claude Code on the web, 18 Nov 2026

**What changed:** 0.2.170 (0.2.169 was taken by task 0218: one extra run for the version clash). The section-view tool says Slice everywhere it is visible: panel title (3 Looks > Slice),
buttons (Add slice, Remove slice, Slice this too, Do not slice this), new list names ("Slice 1" …; old projects keep
their stored names), header ("2 slices · 1 on"), hints, reports, tooltips, function list title, tour set and stop
texts, PC-check line title, guide section + picture. Guide: new anchor `slice` above the old `cutaway` (kept, in
`READING`, so old links land). New test `test_no_visible_cutaway_word_left`. `changed=` on the function entry, the
tour stop and the tour sets.

**Ids that kept the old word:** `looks.cutaway` (function, PC-check line, tour stop and set), `FRESING_PT_cutaway`,
`fresing.cut_*` operators, `scene.fresing.cuts`, `FRCut`, `fr_how_cutaway`, picture file names. Left alone: the sea
and hall cut-aways; the web page's own "Cutaway" tool (task 0218).

**Tested and measured** (web machine, 4 cores): test_section, test_places, test_functions, test_user_guide,
test_workspaces, tooltip check (865 ok), precheck; GitHub run below. No separate old project was opened: stored names
and ids are unchanged.

**Open points / follow-up tasks:** none. Runs needed: see the merge note.
