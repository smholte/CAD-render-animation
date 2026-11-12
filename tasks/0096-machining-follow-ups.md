# 0096 – Machining follow-ups: no dive after a tool change, chips on a table that carries the 4th axis, crisp floor edges

**Who:** worker · **Status:** open · **Branch:** `task/0096-machining-follow-ups`
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

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
