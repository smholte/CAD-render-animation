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

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
