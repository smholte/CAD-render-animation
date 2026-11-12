# 0096 – Machining follow-ups: no dive after a tool change, chips on a table that carries the 4th axis, crisp floor edges

**Who:** worker · **Status:** done (0.2.76) · **Branch:** `claude/adoring-lovelace-rln7b8`
**Started by:** lead chat, 12 Nov 2026 (open points of 0061 and 0066)
**Lane:** Machining – `core/toolchange.py`, `core/gcode.py` (the `Schedule` part), `blender/gcode.py`, `core/chips.py`,
`blender/chips.py`, `core/cut_normals.py`, `core/toolmarks.py`, `blender/toolmarks.py`, `blender/machining.py`, their
tests; the tour's machining sets only if a program needs it. The Motion lane waits (G-code files).
**Model:** Opus · effort Medium · **Place:** Claude Code on the web, environment "CAD-render-animation"

## Goal

The owner's milling videos never show a tool going into the block where the program does not cut, chips land where
they would on a real 4-axis machine, and the tool marks' floors meet slopes with a crisp edge.

## Background

1. **Stray hole after M6 (most important – it is in the owner's kind of program).** The tour's "Three tools" program
   (`blender/tour.py`, `TOOLS_TOUR`) has `T2 M6 G43 H2` on one line, so the **program is right**. Yet after the manual
   change the head goes back to where it was (X20 Y0 Z10) and the end mill, 27.7 mm longer than the face mill, goes
   17.7 mm into the block (0061 report; with 0.2.73's marks the hole even shows rings). Cause to confirm in
   `core/toolchange.py` ("the head … pauses, and goes back"): the way back is planned with the old tool's length.
   0061's own tour set works around it by lifting to Z50 before M6.
   What LinuxCNC does (check its docs for `TOOL_CHANGE_POSITION` / `TOOL_CHANGE_QUILL_UP`): it does **not** go back after
   M6; the next programmed move starts from the change position, with the offset that is in force then (G43 Hn in the
   same block applies right after the change). Choose the rule that matches the machine and gives no dive:
   - with G43 for the new tool: the way back (if the app keeps one) ends where the **new** tool's tip is at the
     program's point – Z first from above, then X/Y, never below the last programmed tip height;
   - **without** G43 for the new tool (old offset still in force): do what the machine would do, and say so – a line in
     the Build result / step check ("T2 is 27.7 mm longer than T1 and has no G43: it goes 17.7 mm below Z10"). The
     clash check (0065) should then also show it.
   - The same for the ATC and double-arm changes (0041, 0064): look whether their way back has the same fault.
2. **Chips on a table that moves and carries the 4th axis** (0066 open point): chips falling past the chuck land on
   the fixed bed instead of the moving table. `core/chips.py` has two spaces (riding = with the workpiece, world); a
   third space – the rotary's carrier (the slide under the 4th axis) – is needed. Test model `test_4axis.step` has a
   moving column, so make a variant (or a set-up in the test) where X moves the table under the A axis.
3. **A floor meeting a long gentle slope (< 30°)** is blended with it at their edge (0061: 197 of 2,229 mm² of floor on
   0029's test model after finishing). `core/cut_normals.py` needs a crease rule for two big planes, keeping 0061's
   rule "a big flat face keeps its own normal next to small facets" and its seam behaviour.
4. **Drill-point rings** use a fixed 0.08 mm; take the feed per turn (F/S) like the other marks.
5. **F12 straight after scrubbing:** a still made with Blender's own F12 within 0.3 s of scrubbing or while playing can
   get the quick normals (0061). Make every render (also F12 and Render Animation) write the exact normals first; the
   app's own renders and the queue already do.

## Done when

- [ ] Tour "Three tools": no cut anywhere outside the programmed cuts (a test checks the block's volume / the cut
      faces against the three programmed passes); the 0061 marks set may go back to an ordinary Z10 change (optional).
- [ ] A test program without G43 after M6 gives the check line with the depth, and the clash check shows it.
- [ ] ATC and double-arm tour sets: the same test (no dive); the changer animations unchanged otherwise (0.0003 mm
      hand-overs of 0064 still hold).
- [ ] Chips: a table that slides under the 4th axis carries the chips that fall on it; chips past it still land on the
      bed; old 4-axis set-ups unchanged.
- [ ] Floor/slope: on 0029's test model the floor area blended with a slope drops to near 0; 0061's facet test (0
      level faces off) and seam test still pass; per-frame time unchanged within 10 % (0061's scrubbing table).
- [ ] Drill rings spaced by F/S (test like 0061's spacing test).
- [ ] F12 right after scrubbing renders the exact normals (test with the render handlers).
- [ ] Guide (Milling, Tool changes) updated where it describes the way back; the existing tour stops' texts updated;
      no new tour stop needed (fixes), unless the no-G43 check line is new – then one line in the tool-change stop.
- [ ] Tests added; GitHub green; report filled in; merge to main and release.

## Not in this task

Hoses / drag chains (0058, Flex lane), the Looks lane's brushed tangent (0098), the demo model (0097), a steep/shallow
toolpath split (later). Two passes side by side at the same depth keeping the first pass's marks: leave (no material is
removed there).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 12 Nov 2026, branch `claude/adoring-lovelace-rln7b8` (no subagents).

**What changed:**
1. **No dive after M6.** Cause confirmed, slightly different from the brief's guess: with the head staying put (the
   tour's "Three tools"), the new tool went in at the swap with the *old* tool's spindle height and the spindle then
   rose over the rest of the pause – T2 (28 mm longer) went 17.7 mm into the block. Now (`core/toolchange.py`):
   `Changer.lengths` (the tools' length offsets, mm) is set by `blender/toolchange.changer`; the way out and back is
   planned for the spindle (`_way`: up first when rising, down last when falling), the lift fades on the first leg
   out and grows on the last leg back only (`Change.lift_end/lift_start`, `lift_knots`); a manual change position
   keeps the spindle at the longer tool's lift and is never lower than the program's point; head staying: the
   spindle rises before a longer tool goes in (while the hand has the old tool away) and comes down after.
   ATC: the pockets still have lift 0 (hand-overs unchanged). Double arm: same legs; an arm change without head
   travel keeps the old rule (the arm grips at the spindle).
2. **M6 without G43.** `core/gcode.Reader` keeps the G43 Hn in force (`Move.h`, G43 without H = tool in the
   spindle, G43.1/G43.2/G49 = the app's rule); `Schedule._length_tools` gives every change the tool whose offset is in
   force after it (`Change.h`). When it is not the new tool, the old offset stays (as on the machine), the Build and
   the step's Details say "T2 (M6 on line 9) is 27.7 mm longer than T1 and has no G43 H2: …", and the clash check
   adds a row tool × workpiece with that depth (`gcode.g43_rows`, `clash.Check._program_rows`). A program with no G43
   at all keeps every tool's own length.
3. **Chips on a table carrying the 4th axis.** `core/chips.py` has a third space, carrier (2): chips falling past the
   chuck go to it, land on the table (`SimIn.carrier`, `carry_c`), past it to world. `blender/chips.carrier()` = the
   next moving object above the workpiece's mover; `machining.sample` stores its matrix per frame
   (`fr_carrier_m`); a third point cloud "FR Chips (on the table)" follows it. Without a carrier the bake is bit for
   bit the same (hash compared on the 4-axis test model).
4. **Floor meets a gentle slope.** On 0029's model the blended floor was beside the long, very narrow strips of a
   ball pass (22.5°, ≤ 0.65 mm wide): the floor's own triangles at that edge are slivers, so the "big flat face
   keeps its normal" rule saw two equally small planes. `core/cut_normals.py` now measures a plane's reach over its
   whole flat region (`_regions`: coplanar triangles joined edge to edge, their box) for planes steeper than RUN_IN
   (16°) to each other, with a ratio of 3 (`BIG_STEEP`). Round walls and ball scallops (< 16°) are judged as before.
   Two planes about as big as each other at 20° (0061's floor + 4 mm chamfer test) still blend – the actual case
   was not "two big planes".
5. **Drill rings** spaced by the feed per turn (F/S), like the wall rings (`core/machining.py`); 0.08 mm only when no
   feed is known.
6. **F12 right after scrubbing.** The render handler writes the exact normals only with the interface locked; the
   quick-normal path now switches "Lock Interface" on again (set only on change), so F12 / Render Animation always
   gets the exact normals.
Guide (Tools, Tool changes, Tool marks, 4th axis), tour stop texts "tools" and "hand" updated. No new tour stop,
no PC-check line (fixes; the G43 line is a warning text).

**Tested and measured** (web session, 4 cores, bpy module):
- Tour "Three tools" milled: deepest cut −17.7 mm before (test fails on 0.2.73), −6.0 now (the slot), nothing below
  Z−1 at X20 Y0 (`test_three_tools_cuts_nothing_outside_the_program`).
- Test gantry, T3 10 mm longer: tip lowest −8.4 / −5.0 mm below the program during changes before, ≥ −0.01 now for
  Stay (with hand), Z up, change position and ATC (first/last legs). Core: every change kind with the brief's
  27.7 mm, change positions above and just above the program. No-G43 program: line, Details, 10.0 mm below, clash row.
- 4-axis with a table sliding 60 mm under A: chips on the bar, on the table (on its top, inside its outline,
  following it) and on the bed.
- 0029's model, floor faces shaded off flat after finishing: 197 → 0 mm² of 2,229 (test tightened from 10 % to 1 %).
  0061's facet, seam and normals tests pass.
- Time: scrubbing uses the quick normals, which this task does not touch (per-frame time unchanged). The exact
  normals of the whole 28,000-triangle cut of 0029's model in one call: 81 ms before, 114 ms now (+33 ms, the
  regions and the steep-edge test; measured here, 4 cores). They are worked out once 0.3 s after the frame stands
  still and before a render, so the owner sees it only as a slightly later sharp shading after scrubbing.
- Local: the tests of toolmarks (done, moves, marks), chips, rotary, doublearm, toolchange, gcode, machining,
  toolpath, air, coolant, cut normals, core G-code and tool change: 269 passed; real app `gcode` 29/29.
- Drill rings: 0.05 and 0.2 mm per turn give exactly that spacing.

**GitHub runs:** 3 on the branch. The first failed one real-app check (`ui_test_gcode.py` compared T1's tip with
the program also during the tool change, where the spindle now rises 5.5 mm for the longer T2): it now skips the
changes, as the pytest version does. Released as 0.2.76 (0.2.74 and 0.2.75 were taken by 0098 and 0097 meanwhile: one more run).

**Open points / follow-up tasks:**
- The exact normals cost +33 ms on a 28,000-triangle cut (above); could be trimmed if the owner notices.
- 0061's marks set still lifts to Z50 before M6 (optional in the brief; left so its pictures stay the same).
- Two planes of about the same size at 16–30° still blend (by design of 0061); a real "two big planes" crease would
  need a size in mm (the round-wall strips are the same shape).
