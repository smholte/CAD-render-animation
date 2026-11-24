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

**Chat / date:** Claude Code on the web, 23–24 Nov 2026 · version 0.2.226

**What changed:**
- **Copy / Paste** (`blender/copy.py`, `ops_copy.py`): right-click > **Copy** / **Paste here** (on empty space
  **Paste**), 2 Structure > Place > **Copy** / **Paste**, **Ctrl+C** / **Ctrl+V** outside Full access
  (`lock.APP_KEYS`; Full access keeps Blender's). Paste = one undo step; the copy is selected, unlocked, and the
  Move / turn window opens with what came along and what was left out at its bottom. A new or opened project forgets
  the clipboard; after a model update it finds the parts again by their part IDs.
- **What comes along:** parts (meshes shared – 0 new meshes for the crane), looks, groups, hidden / locked state; joints
  whose moving parts are all in the copy (limits, values, stacks, couplings and table couplings between them);
  cylinders; mechanisms; way covers; hoses and drag chains with both ends in the copy; labels; logos (own keys).
  Built by the model update's own code (`to_specs` → `rebuild_from_specs`, part IDs mapped to a free scope `~N/`).
- **The rule (said in the window):** what reaches outside the copy is left out – the copy moves by itself. A joint that
  sat on something outside sits on the copy. Cables, drums, tracks, trails, steps and cameras stay with the original.
- **Model update (point 3):** a whole-model copy is a second instance (`fr_copy_group`, keeps `fr_source` /
  `fr_cache`): updating the original updates its copies and the other way round (`reimport.update_model(copies=)`,
  one report with a line per copy); a subassembly / parts copy is a model of its own, frozen (`fr_copy_frozen`):
  refused for an update, untouched by the original's.
- A paste that fails half-way takes back what it made (`_roll_back`; a failed operator pushes no undo step).
- Function entry `structure.copy`, guide "Copy and paste a model, subassembly or parts" + the keys / right-click lists,
  pictures `panel_2_place.png`, `view_right_click.png`; PC-check line `place.copy` (MIN_LINES_FULL 132); tour set
  "Copy and paste" with stop `copy` (MIN_LINES_TOUR / MIN_CHECKS tour 101); real-app test `copy` (16 checks, group
  callouts); `test_keys_right_click.py` and the PC check's `app.keys` know Paste shows only once something was copied.

**Tested and measured** (web machine, 4 cores, no GPU):
- `tests/test_copy.py` 12 tests: the crane copied with Boom / Trolley / cylinder (shared meshes, scoped IDs, beside it,
  same pose), both move independently, Build moves each by its own steps, clash check finds the copy pasted onto the
  original (and nothing beside it), save + reopen, boom copy frozen (update refused / untouched), a model update
  updates the copy (and back), a coupling to an outside joint left out, copy of a copy + removing the original, the
  four-bar subassembly with its mechanism, the hoses model (hoses follow the copy's joint, originals unchanged),
  operators / keys / menu / Client view / a new project forgets the clipboard, labels.
- **Independent tester** (subagent, did not write the code): `tests/test_copy_independent.py`, 38 tests; it found 5
  faults – a second paste of a model with hoses hung for good (a list item held across `add()`, also in way covers and
  labels), the same when pasting a model and its copy at once, an error half-way left a half-made copy, a table
  coupling inside the copy dropped without a word, Paste greyed after a model update. All fixed; 50 / 50 pass.
- Real app `tools/ui_test_copy.py` 16/16 (≈25 s): Ctrl+C, Ctrl+V → second crane, window opens and says what came
  along, Ctrl+Z takes it away in one step, right-click menu, Paste here on the clicked spot, Client view no copy.
- PC check `place.copy` OK, paste 0.03 s on the crane; tour stop `copy` + its tour clash check (0 clashes); 0292's
  tests, model-update tests (35), right-click tests pass.

**Open points / follow-up tasks:**
- **Cables, drums and tracks are not copied** (their own joints, carriers and spools are much more set-up): the window
  says "add it again on the copy". A follow-up in the cable lane could copy them through their own create functions.
- Clash rows name parts by their CAD name, so a clash between the crane and its copy reads "BOOM × BOOM".
- Ctrl+V in Full access stays Blender's own paste (it pastes Blender's buffer, not the app's copy).
- **0292's real-app test `place` failed 2 of 22 checks (Delete did not open the Remove window) in 2 of ~8 local runs**,
  also on `main` without this task's changes: an intermittent timing problem of that test, not of the feature.
- `main`'s run of 0.2.221 failed only in "Landing page" publishing (two "github-pages" artifacts in one run, a GitHub
  Pages hiccup); the release itself was published and offered.

**Owner's check on your PC** (after Update now to 0.2.226):
1. Open a project with a model that has joints (or the test crane from Help > Make test tour project).
2. Click the model's top row in 2 Structure, press **Ctrl+C**, then **Ctrl+V**: a second model "… (2)" stands beside
   it, and the **Move / turn** window opens; at its bottom it says what came along.
3. In 4 Motion, move a joint of the copy ("… (2)"): only the copy moves.
4. Press **Ctrl+Z**: the copy is gone.
5. Right-click a spot on the floor or the model, then **Paste here**: the copy stands there.
6. Select one subassembly (e.g. a boom), right-click > **Copy**, then right-click > **Paste here**: it becomes its own
   model with its joint; the window lists what was left out (a cylinder whose other end is outside).
