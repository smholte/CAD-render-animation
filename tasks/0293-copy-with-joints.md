# 0293 – Copy a model, subassembly or parts with its joints and mechanisms, and place the copy

**Who:** worker · **Status:** running (Claude Code on the web, 23–24 Nov) · **Branch:** `task/0293-copy-with-joints`
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

## Design (worker, 24 Nov 2026)

**Files:** `blender/copy.py` (`plan`, `paste`, `summary`, the model-update hooks `refused_update`, `carry_root`,
`after_root`, `others`), `blender/ops_copy.py` (`fresing.copy`, `fresing.paste`, `fresing.copy_key`,
`fresing.paste_key`, `do_paste`); hooks: `reimport.update_model` (refuse a frozen copy, update the copy group),
`lock.APP_KEYS` (Ctrl+C / Ctrl+V outside Full access), `context_menu.py` (Copy, Paste here, Paste on empty space),
`ui_place.py` (Copy / Paste row, the paste's note at the bottom), `ops_place.py` (Move / turn window taller).

**How a copy is made** – the model update's own path, with every part ID mapped to its copy's:
1. In the CAD pose (vessel at rest): the tops' world places and the set-up that comes along as specs
   (`joints.to_specs`, `cylinders.to_spec`, `linkages.to_spec`).
2. The objects: `ob.copy()` (the mesh is shared), cleaned (keys, constraints, the app's "FR …" modifiers, tags that
   tie it to the original's set-up), put in the CAD tree with their CAD places; part IDs with a free scope `~N/`
   (task 0056's rule). A whole model keeps `fr_source` / `fr_cache` and gets a copy group (`fr_copy_group`, on the
   original too); a subassembly / parts get a new model root of their own, *frozen* (`fr_copy_frozen`).
3. `joints.rebuild_from_specs`, `linkages.rebuild_from_specs`, `cylinders.rebuild_from_specs` with mapped specs
   (names " (2)", members, bases, stacks, couplings mapped; anything outside the copy left out); way covers, hoses /
   drag chains and labels as raw copies of their list items pointed at the copied parts; decals by `decals.sync`.
4. Placed with 0292's `place.move`: beside the original (+X, past every model's box, a gap of 20 % of its width), or
   Paste here: its box's middle over the clicked point, standing on it. Its root's rest place = there ("Back to where
   it was imported" brings it back there). Selected, unlocked, Place's window opens.

**Rules:** what reaches outside the copy is left out (a joint that also moves outside parts, a cylinder / mechanism /
hose / way cover with a piece outside, a coupling to an outside joint) – the copy moves by itself; a joint that sat on
something outside sits on the copy. Cables, drums, tracks, trails, steps and cameras stay with the original (said).
Model update: a whole-model copy follows the original (and back); a subassembly / parts copy is frozen (refused).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**

**Owner's check on your PC:**
