# 0290 – 4 Motion: Add rotate / slide joint in a fold like the rest; cylinders take several parts or subassemblies per item

**Who:** worker · **Status:** running (23 Nov) · **Branch:** `claude/inspiring-shannon-h7b896` (the web session's branch)
**Started by:** lead, 23 Nov 2026 (owner's list, 23 Nov 19:39: "In the 4. motions section the menu with rotate joint
and add slide joint should be a folded up menu like the rest." – "Setup of cylinders, when choosing the different
parts, you should be able to select multiple parts/assemblies per item (barrel, rod …)") · **Model:** Opus · effort
Medium
**Area:** Motion lane – `blender/ui_motion.py` (the joint buttons of 4 Motion), `blender/ops_cylinders.py`,
`blender/cylinders.py` (reads the picked parts), the Set-up window's cylinder steps (`ui_setup.py` / `ops_setup.py`, only
those steps), `core/places.py` / `core/functions.py` if the fold is a new sub-panel; lessons that point at these
buttons (`blender/lessons/crane.py`); the selected joint's box in `ui_motion.py` (point 3); tests, guide + pictures,
CHANGELOG.
**Not:** joints' own code (`joints.py`), `ops_motion.py` beyond the buttons' place (0282 just changed its dialogs),
linkages, way covers.

## What to do

1. **Joint fold.** The row with Add rotate joint / Add slide joint in 4 Motion becomes a fold of its own, drawn like the
   other functions of the section (0062's title rows: state in the header, "How it works" fold, one `big()` button),
   at the same place in the order. The crane lesson's steps and the lesson highlight still find the buttons (the
   highlight opens folds); tooltips unchanged.
2. **Several parts per cylinder item.** Today "Use selected" (`fresing.cylinder_pick_parts`) takes the selection but
   **replaces** what was picked before. Make each item (barrel, rod, and telescopic stages where they are picked) take
   several parts and/or subassemblies: **Add selected** adds to the item, the item shows its picks as a short list with
   × to drop one, **Clear** empties it; Shift / Ctrl + click in the view and in 2 Structure select several (say in the
   tooltip). The same in the Set-up window's cylinder steps. The cylinder's axis and travel (`core/cylinders.py`, read
   from the parts) use all picked parts. A part may not be in two items (as today).
3. **The panel stays still** (owner 23 Nov 22:05, two screenshots of a follower slide joint "Jaw-2 slide" that rides on
   "Forearm rotate", 200 mm per turn, offset 5 mm, limits 0–1000 mm): when the follower goes outside its limits, the red
   "Beyond its limits now: check the ratio, or the limits" (`ui_motion.py`, the `if j.follows:` branch under the value
   row) appears as two lines and pushes Limits, Moves by itself / Follows a joint, Joint, mm per turn and Offset down –
   so the field the user is dragging jumps away. Put the warning **next to the distance / angle** on the value row (a
   short red "⚠ Beyond limits", the longer text as its tooltip; check it is not cut off at the default side-panel width,
   or shorten it). Then go through the rest of `ui_motion.py` (4 Motion, 6 Animation, 7 Render queue) for other lines
   that come and go while the user drags a value or plays, and keep those boxes still the same way (CLAUDE.md 6, "The
   panel stays still"). Other files' cases: list them in the report, don't change them. A real-app test drags the leader
   past the follower's limit and checks that the rows under the value row keep their place.
4. **Show what a joint moves** (owner 23 Nov 22:24, screenshot: a truck with two wheel joints "Roda rotate" / "Roda rotate
   2" – selecting one in the list showed nothing in the view): clicking a joint in 4 Motion's list (and a mechanism in
   its list) **shows that joint's arrow** (even with "Show joint arrows in the view" off: the selected one only) and
   **highlights the parts it moves** in the view – a clear outline / tint like the lesson highlight (0133), not a
   selection that a following click or G would act on; riders of a stack in a lighter shade; hidden parts are not
   unhidden (say "n parts hidden" in the box). Clicking elsewhere or another joint clears it; never in renders, the
   web export or the PC check's timings. Also give the list rows a real tooltip (Blender shows "joints_index – Select
   List Item." today) if Blender allows it; if not, say so in the report.
5. Test model: a cylinder whose barrel is 3 parts in 2 subassemblies and whose rod is 2 parts (a tour set or a test
   of its own); Pins again and Remove still work.

## Done when

- [ ] Tests (several picks kept, × drops one, travel read from all, Set-up window steps); crane lesson passes
- [ ] Real-app test of the fold; guide text + pictures of 4 Motion; tour stop `changed=`; function entries `changed=`
- [ ] Full suite + GitHub run green; report filled in; merged, version, release

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (worker), 23 Nov 2026 · branch `claude/inspiring-shannon-h7b896` · 0.2.219

**What changed:**
1. **Joint fold** – new sub-panel `FRESING_PT_joints` ("Joints", first under 4 Motion, `DEFAULT_CLOSED`, header "n joints"):
   how-to, Selected, Add rotate / Add slide, the list and the joint box moved into it. 4 Motion's own body keeps only
   the "animation is built" box and Everything back to CAD position (new function entry `joints.cad_position`, so the
   Client view still hides 4 Motion). `core/places.py`, the `joints.*` entries' `panel`, two texts that name the
   place (`where('joints')`) and the guide pictures follow. Lessons / highlight find the buttons through the function
   list (crane + mill lesson tests pass).
2. **Several parts per cylinder item** – `fresing.cylinder_pick_parts` is now **Add selected** (adds; a subassembly
   takes the place of picks inside it, a part inside a picked subassembly is skipped; overlaps leave the other item
   and the message says so), `action=DROP` (×) and `CLEAR` (bin icon). `ui_motion.pick_item` / `draw_cyl_picks` draw an
   item as a title row + one row per pick. A made cylinder's Set-up fold: Add selected per item (barrel, rod, stages),
   × per pick (`fresing.cylinder_parts action=DROP role= index=`; barrel and rod keep ≥ 1), the travel read again from
   all parts (kept when it was typed and still cannot be read). Set up a crane's cylinder step draws the same lists;
   `fresing.crane_cylinder` uses them (else the old ordered pick), `setup_crane.make_cylinder` takes lists (eyes from
   all parts; each pin kept on the part that holds the eye). `core/cylinders.py` already read lists.
3. **Panel stays still** – a follower's warning is a short red "Beyond limits" on its value row (`fresing.limits_note`,
   tooltip = the long text, room kept). In the rest of `ui_motion.py`: the cylinder's "beyond its stroke" line moved
   onto the Stroke row the same way ("Beyond stroke"). Left as they are (state changes, not while dragging / playing,
   or already the last line of their box): the mechanism's status line (bottom of its box), the queue job box's
   progress bar (comes with Running), `_follow_error` (after a button). Other files not changed.
4. **Show what a joint moves** – new `blender/joint_show.py`: `joints_index` / `mechanisms_index` got an update that
   shows the clicked joint's arrow (own GPU lines, ring for rotate; also with arrows off) and tints its parts
   (Fresing Green; parts that also move by another joint – stack riders or a joint inside its subassembly – lighter).
   No selection; hidden parts stay hidden ("n parts hidden" on the box's title row). Ends on another click in the
   list, a selection change, the fold closed, playback, a load; drawn only with overlays on (never in renders / web
   export). **List row tooltip:** set through the index properties' `description` (Blender shows it for the rows).
5. **Test model** – `make_test_cylinder.py C` → `tests/data/test_cylinder_c.step`: SPLIT.ASM, barrel 3 parts in
   2 subassemblies, rod 2 loose parts.

PC check line `joints.show` (MIN_LINES_FULL 126); tour stops joint / stack / cylinder `changed=`, crane set
`changed=`; function entries `changed=`; guide (4 Motion, couplings, cylinders, Set up a crane) + pictures
panel_4_motion(_start), panel_4_coupling, panel_4_cylinders; CHANGELOG 0.2.219.

**Tested and measured** (4-core web machine, Linux, Blender 5.2.3 / bpy): `tests/test_cylinder_parts.py` 18 new tests
(picks kept / added / skipped / ×, clear, never in both items, travel 1092.8 / 570 mm read from 3 + 2 parts, all parts
move together, Set-up fold add / × / last kept / refused overlap, Pins again, Remove, crane step takes the lists,
make_cylinder with lists, the fold's place, joint show + riders + hidden count, ends on selection change, arrow lines,
row tooltips, "Beyond limits" on the value row with the same row structure inside / beyond). Real app
`tools/ui_test_joint_fold.py` (group pccheck-b): 12/12 – the Joints title clicked open, Add rotate joint on screen,
the follower clicked shows 3 parts without selecting, the arm moved past the limit: the Limits row stays at the same
pixels, "Beyond limits" above it and not cut off, another selection ends the show. Local runs of the affected suites
and the real-app cylinder / setupcrane tests: see the push; GitHub runs the rest.
No subagents (Medium effort, one area).

**Open points / follow-up tasks:**
- The tooltip report calls `fresing.limits_note` "weak" (its text is a variable it cannot read); the real tooltip is
  the long sentence.
- The tint is drawn with depth test: parts behind others are not seen through (as in the view itself).
- The owner should check on his PC that the list rows show the new tooltip (Blender shows the index property's
  description; not checked with a hover in the real app here).

**Owner's check on your PC:**
1. Open a project with joints. 4 Motion > click **Joints**: the fold opens with Add rotate joint / Add slide joint.
2. Click a joint in the list: its arrow and the parts it moves light up green in the view; click a part: it goes.
3. A follower with Limits: move the joint it follows past them – "Beyond limits" appears next to the Distance, the
   rows under it stay put.
4. 4 Motion > Cylinders: select two parts (Shift+click), **Add selected** under Barrel – both listed with ×.
