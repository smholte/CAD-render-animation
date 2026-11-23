# 0290 – 4 Motion: Add rotate / slide joint in a fold like the rest; cylinders take several parts or subassemblies per item

**Who:** worker · **Status:** open – can start after 0282 is merged · **Branch:** `task/0290-joint-fold-cylinder-parts`
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

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**

**Owner's check on your PC:**
