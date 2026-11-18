# 0214 – Lifting plans with the rest of the app (bug hunt 0209 groups B + C)

**Who:** worker · **Status:** open – can start · **Branch:** `task/0214-lifting-with-the-rest`
**Started by:** lead, 18 Nov 2026 · **Model:** Opus · effort Medium
**Area:** Lifting lane – `blender/lifting.py`, `ops_lifting.py`, `ui_lifting.py`, `blender/sheet.py`, `blender/states.py`,
`core/lifting_reach.py`, `fresing_render/lifting_model/` (row 17), one hook line in `blender/reimport.py` (leave the rest
of `reimport.py` to 0209 group G), row 3 may touch `animation.py` (additive). Runs before L5 (rigging) in this lane.

## Goal

Fix rows **1, 3, 4, 11, 12, 14, 15, 16, 32, 33, 36** (group B) and **17** (group C) of `tasks/0209-bug-hunt-7.md`.
Rows 1 and 3 first – they lose work:
- **1** a model update (even the same file) loses every load on that model and puts its CoG near the origin.
- **3** Build, Hook to here, Build again: the crane jumps back (Build must keep the plan's pose).
- **4** updating a crane's model or deleting its objects drops the crane from the plan and leaves its joints / poses.
- **11** Place / Move with vessel motion on puts the crane 0.34 m into the deck. **16** a box load on a moving deck
  does not ride.
- **12** a crane pose used from Poses / Go to pose moves other models' hand-moved sub-assemblies back to CAD.
- **14** a renamed crane joint: Hook to here says ok with the hook 12 m off. **15** Make again with Replace and another
  hook block: no warning, Hook to here wrong.
- **17** the built-in cranes' own poses (Travel → Set up → Working → Long reach) give clash rows on the crane itself:
  fix the makers / poses (re-make the files with `tools/make_lifting_cranes.py`), never loosen the clash test.
- **32, 33, 36** small: radius past the chart says nothing; CoG symbol in every workspace / camera view; "a outrigger".

## Done when

- [ ] Each row's repeat case is a test that failed before; every built-in crane's pose animation gives 0 clash rows.
- [ ] 0201's open point "more counterweight than the chart picked" stays for L6 (say so).
- [ ] Guide, tooltips where texts changed; tour sets still 0 clashes; full run green.
- [ ] Report filled in.

## Not in this task

L5 rigging; the mesh update of moved groups (row 5, group G).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
