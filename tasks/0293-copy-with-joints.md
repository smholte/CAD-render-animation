# 0293 – Copy a model, subassembly or parts with its joints and mechanisms, and place the copy

**Who:** worker · **Status:** waits – after 0292 (same lane) · **Branch:** `task/0293-copy-with-joints`
**Started by:** lead, 23 Nov 2026 (owner's list, 23 Nov 19:39: "I want to be able to easily copy an entire assembly or
selected parts, that allows me to place it somewhere else in the project. This also copies joints and mechanisms with
it.") · **Model:** Opus · effort High
**Area:** Place lane (after 0292): new `blender/copy.py` + `ops_copy.py` (or inside 0292's files), additive:
`context_menu.py`, `lock.py` (Ctrl+C / Ctrl+V outside Full access), `props.py`, `core/functions.py`; reads `joints.py`,
`cylinders.py`, `linkages.py`, `waycover.py`, `flex.py`, `paths.py`, `decals.py`, `callouts.py` through their own create
functions; tests, guide, tour, PC check, CHANGELOG.
**Not:** a copy inside Full access with Blender's Shift+D (stays Blender's), model update internals (`reimport.py`)
beyond what the copy's rule below needs.

## What to do

1. **Copy / Paste** (right-click > Copy, Paste here; 2 Structure; Ctrl+C / Ctrl+V outside Full access) of a model, a
   subassembly or the selected parts. The copy brings: its joints (limits, couplings *inside* the copied set), cylinders,
   mechanisms (linkages), way covers, hoses / cables / chains whose both ends are in the copy, decals, labels on its
   parts, its groups and looks. A coupling or hose to something outside the copy: pick one rule (keep it linked to the
   same outside joint / leave it out) and say it in the window. Meshes are shared (linked data), so the project barely
   grows. Names get " (2)", " (3)" …
2. The copy lands beside the original (or at the mouse) and 0292's **Place** opens for it at once.
3. **Model update of the original:** decide and state – recommended: a copied *whole model* is a second instance of
   the same model and follows a model update; a copied subassembly / parts is frozen (its own parts). Test whichever is
   chosen.
4. Undo in one step; save + reopen; Build with both; the clash check sees both.

## Done when

- [ ] Tests: the crane copied with its joints + cylinder → both cranes move independently, Build, clash check, save +
      reopen, undo; a subassembly with a mechanism copied; a hose between two copied parts follows the copy
- [ ] Independent tester tries to break it (couplings to outside joints, copy of a copy, remove 0292 of the original)
- [ ] Real-app test; PC check line `place.copy`; tour stop; function entry; guide + pictures; full suite + GitHub run
      green; report; merged, version, release

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**

**Owner's check on your PC:**
