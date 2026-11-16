# 0162 – Fix: assembly sequence in any order, Put together shows its parts, riders without a jump; mesh model updates keep unnamed groups

**Who:** worker · **Status:** running · **Branch:** `claude/cad-render-task-0162-ow4q95`
**Started by:** lead chat, 16 Nov 2026 (rows of bug hunt 0147, report in `tasks/0147-bug-hunt-5.md`) ·
**Model:** Opus · effort Medium · **Place:** Claude Code on the web, environment "CAD-render-animation". Subagents
allowed (CLAUDE.md section 2), including an independent tester.
**Area (Motion lane – sequence; Import lane):** `blender/sequence.py`, `blender/reimport.py` (made-name assemblies),
`importer/mesh_reader.py` (`_decode`), the Structure panel's hide hook only where row 21c needs it, their tests, the
guide's sequence and mesh-import sections.
**Do not edit:** `paths*`, `spool`, `flex` (0159, 0160), the Web 3D lane (0161, 0143, 0158), `demo_model/` / `demo.py`
(0153), `surroundings.py` (0148), milling (0146).

## Goal

Take apart / Put together does what it says in any order the owner adds the steps, and work on an unnamed group of an
imported mesh model stays on that group through a model update.

## Background

Read rows 3, 7, 9, 13, 21b and 21c of `tasks/0147-bug-hunt-5.md` first (place in the code, proof, suggested fix).
Repeat each one before fixing it.

- **Row 7 (new in 0.2.107):** nested steps not in strict reverse order (Take apart CARRIAGE, Take apart SLIDE, Put
  together CARRIAGE, Put together SLIDE) leave the carriage apart. A home entry records which subassembly pushed it; a
  Put together pops the newest entry its own subassembly (or one inside it) pushed. Test with that order: carriage
  80 / 284 / 0 / 0 mm, no clash rows; 0140's orders keep their results.
- **Row 9:** Take apart with Hide or Fade, then Put together with Stay: the parts become visible and unfaded from each
  part's come-in, whatever the Put together's own At the end says. Test: 12 of 12 parts render at the last frame.
- **Row 13:** a rider in a Put together whose settings differ from its Take apart starts at its real place and blends
  to the plan line, as non-riders do (no 137.9 mm jump in one frame; ≤ the non-riders' step per frame).
- **Row 21c:** a part hidden in 2 Structure after Build takes the Build off with "Build again" (as other changes after
  Build do), so the render never shows it by surprise.
- **Row 3 (lost work):** unnamed glTF groups ("Node k") all sit at the model's origin, so "same place" pairs the wrong
  ones after a group is added or removed. Pair made-name assemblies through their matched parts (`_made_assemblies`),
  or by the centre of their parts' boxes – not the origin. Test: three unnamed groups at the origin, Hide step and the
  Structure eye on B, update with A removed → both still on B's parts.
- **Row 21b:** decode an OBJ / MTL line by line (UTF-8 first, cp1252 only for a line that is not UTF-8), so "Plåt"
  stays "Plåt" and an update does not report it renamed.

## Done when

- [ ] Every row above fixed, each with a test that failed before the fix.
- [ ] An independent tester tries other step orders (three deep, interleaved, deleted steps, riders in both
      directions) and other unnamed-group changes.
- [ ] Tooltip / guide sentence where the owner sees a change; GitHub run green; merged; version (CLAUDE.md section 7);
      report with a short list for the owner.

## Not in this task

The other rows of 0147 (0160, 0161, 0163); the files of running tasks named above.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (Opus, effort Medium), 16 Nov 2026. Version 0.2.119.

**What changed:**
- Row 7 (`sequence.py`): the home stack holds (subassembly, place). A Put together undoes the newest Take apart of its
  own subassembly or one inside it; entries of subassemblies round it, pushed later, then find the part where it ends.
  With no entry of its own it uses the newest entry and leaves it. A part already home stays (no keys). Back to CAD of
  one subassembly (`animation.py`) drops only the entries inside its scope; outer ones then find the part at CAD.
- Row 9: Put together with Stay shows parts hidden or faded before from their come-in (`_show_again`).
- Row 13: a rider that is out already starts where it is and blends onto its line over its own frames.
- Row 21c (`ops_main.py`, `ops_panels.py`, `ops_motion.py`): the row eye, Show only (row and selected), Hide, Show
  all, Show everything again, Use visibility set and Show only these (3 Looks) take the Build off ("Build again").
- Row 3 (`reimport.py`): assemblies whose own name the reader made are left out of the name and place rules and pair
  only through their parts. A named part inside one keeps its name in the shape-and-place key, and the place compared
  is the middle of its box, not its origin.
- Row 21b (`mesh_reader._decode`): UTF-8 for the whole file, else line by line. Only the short credit read may end in
  the middle of a letter (`cut=True`).
- Guide: the sequence section, 2 Structure and mesh-model updates. Tooltips name "Build again".

**Tested and measured** (4-core web machine, Blender as a module):
- Each row has a test that failed on the old code: `tests/test_sequence.py` (task 0162 section) and
  `tests/test_mesh_import_fixes.py`. Old code: the carriage was still 126 mm out after its own Put together; 0 of 12
  parts showed after Hide → Stay; the rider stepped 10.8 mm per frame while the other parts stepped at most 7.5 mm;
  "Node 4" took group B's Hide step; "PlÃ¥t".
- Independent tester (subagent, worktree): 52 tests in `tests/test_seq_mesh_0162_independent.py` (three-level STEP
  and glTF models made in tmp_path). 18 failed on the first version, from 5 faults: unnamed groups still mixed up
  when parts share a shape; four show/hide buttons without the hook; inner Put together popped the outer entry;
  Back to CAD cleared the outer entries; `_decode` dropped a last cp1252 letter. All are fixed and all pass now.
- Local: sequence, product video, panels, phase2, same-step-twice, model update, the mesh files, guide and updates
  tests pass. Tooltip check: 755 ok.

**Subagents:** one independent tester (Opus). It wrote the test file above. I fixed its five faults myself.

**Open points / follow-up tasks:**
- When an update leaves only **one** unnamed group, the mesh reader makes that group the model's root. Work on the old
  group then has no target (Hide step "gone"). This is an Import lane follow-up: match a made-name root to the old
  group whose parts it holds.
- Row 7's order can be physically impossible. Example: the slide unit comes home while the base plate (lifted by the
  whole model's Take apart) still hangs over it. The clash check shows it, and the guide says so. There is no Build
  warning.
- The tester saw that on an animation with 6 steps, step references kept in a Python list read wrong values (a start
  time near 0) after more steps were added. Look them up again by index (test style, not app code).
