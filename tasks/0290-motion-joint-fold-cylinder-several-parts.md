# 0290 – 4 Motion: Add rotate / slide joint in a fold like the rest; cylinders take several parts or subassemblies per item

**Who:** worker · **Status:** open – can start after 0282 is merged · **Branch:** `task/0290-joint-fold-cylinder-parts`
**Started by:** lead, 23 Nov 2026 (owner's list, 23 Nov 19:39: "In the 4. motions section the menu with rotate joint
and add slide joint should be a folded up menu like the rest." – "Setup of cylinders, when choosing the different
parts, you should be able to select multiple parts/assemblies per item (barrel, rod …)") · **Model:** Sonnet · effort
Medium
**Area:** Motion lane – `blender/ui_motion.py` (the joint buttons of 4 Motion), `blender/ops_cylinders.py`,
`blender/cylinders.py` (reads the picked parts), the Set-up window's cylinder steps (`ui_setup.py` / `ops_setup.py`, only
those steps), `core/places.py` / `core/functions.py` if the fold is a new sub-panel; lessons that point at these
buttons (`blender/lessons/crane.py`); tests, guide + pictures, CHANGELOG.
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
3. Test model: a cylinder whose barrel is 3 parts in 2 subassemblies and whose rod is 2 parts (a tour set or a test
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
