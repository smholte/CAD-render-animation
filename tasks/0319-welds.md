# 0319 – Welds: pick two sets of faces (like Inventor), a real bead where they meet – steel, stainless, aluminium, painted or bare, rust where it belongs

**Who:** worker · **Status:** done · **Branch:** `claude/cad-render-animation-0319-fwlaf1` (the web session's branch)
**Started by:** lead, 24 Nov 2026 (owner 24 Nov 00:45, ticking study 0270's #21: "for the weld, should be easy to select
place, maybe like Inventor, two different face selections, allowing you to lay down welds the places those faces
intersect. And allow to paint over the weld and different weld for steel, stainless and aluminium… Also allow rust on
weld where logical.") · **Model:** Opus · effort High
**Area:** new **Welds lane** – new files `core/welds.py` (seam finding, bead path, sizes, rules per material),
`blender/welds.py` (bead objects, kept data), `blender/weld_looks.py` (the bead and heat-zone looks, like
`cable_looks.py`), `blender/ops_welds.py`, `blender/ui_welds.py` (a **Welds** sub-panel of 3 Looks + "Add weld…" in a
part's right-click menu), `tools/make_test_weldment.py` (an invented weldment); additive: `props.py`, `reimport.py`
(model update), the face picking of `hover.py`, `context_menu.py`, `core/web3d.py` / `blender/web3d.py` (bake the bead),
the clash check (beads left out), `lock.py` (Client view: see, not edit). **Reads** `materials.py` (the parts' looks and
paint), does not edit it.
**Not:** the finishes (0274), carbon / Rust slider / better looks (0318 – see "Rust"), copy (0293 – see "Copies"),
weld symbols on drawings (later, below).

## Goal

A CAD engineer or a sales person can add realistic welds in a few clicks: pick the faces of one part, pick the faces of
the other, and a bead is laid along every line where they meet – with the right look for steel, stainless or
aluminium, painted with the part or left bare, rusting where it would in real life. An animator can still shape every
bead.

## Background

- Study **0270** #21 (branch `task/0270-study-finishes`; `finishes_proto.py`, the weld T-joint in
  `tools/finish_shapes.py`, the picture on the page): a rippled bead Ø8 mm, ripples 1.6 mm, stainless heat tint straw →
  purple → blue in bands to 16 mm **looks right** and costs ~0 % render time. The line is kept as object properties
  `fr_weld_a / fr_weld_b` on each part it touches (a material reads them per copy) + a bead object. It needs a seam
  picker, a bead that follows the line, and model-update care – this task.
- The mesh knows its CAD faces (`fr_face_starts`, `fr_axis_faces` – see `core/web3d_faces.py`): pick whole CAD faces,
  not triangles. Hover highlight exists for axis picking (`hover.py`).
- CAD parts of a weldment touch or leave a small gap; the faces meet along lines (plate on plate), circles (tube through
  a plate) or saddle curves (tube on tube).

## What to build

1. **Picking (Inventor-like).** *Add weld* → "Pick the faces of the first part" (click, Shift-click for more; hover
   highlight) → *Next* → "Pick the faces of the second part" → the bead is previewed along **every line where the two
   sets meet** (touching, or a gap up to a tolerance – say which); untick segments you do not want; *Done*. Also the
   **quick way**: pick two parts → every line where they meet is offered with ticks. Esc cancels; every step has a
   one-line hint at the top of the 3D view; tooltips on every button.
2. **Weld types and sizes**: fillet (leg / throat size a, one side / both sides), butt (flush cap with a small crown),
   all-round (a closed loop: tube through a plate), intermittent (length + pitch), start / end craters. Defaults from
   the thinner plate's thickness; real sizes in mm.
3. **Process and look per material**, chosen from the parts' looks and changeable: **steel** – MAG, grey-blue oxide,
   even ripples, optional spatter; **stainless** – TIG, fine stacked ripples, heat tint bands (option *Pickled* = no
   tint); **aluminium** – MIG / TIG, bright "stacked coins" ripples, MIG's sooty band beside the bead; optional *stick*
   (slag, spatter) for steel; *Ground flush* for any. Two different materials welded: a calm warning. Heat-zone tint /
   discolouration on the parts next to the bead (as the study's tint, per copy).
4. **Paint over the weld.** *Finish*: **As welded** / **Painted** (default when the parts' group is a paint): the bead
   and its heat zone take the paint of the part (pick which part's paint), the ripples stay visible through the paint.
   Follows the group's colour and Wear (paint wears first at the bead's toes).
5. **Rust where it is logical.** Bare carbon-steel welds and their heat zone rust first (more than the plate);
   painted welds only where Wear has taken the paint off; galvanised parts rust where the weld burnt the zinc unless
   *Zinc-sprayed after welding*; stainless gets no red rust (unpickled stainless outdoors may get a faint tea stain);
   aluminium never rusts. A per-weld Rust value. **If 0318 is merged before you, follow its group Rust slider**
   (one named node group); if not, 0318 connects it – say in the report what it should read.
6. **Kept through everything**: a **model update** finds the faces again (by the CAD face data); a weld whose faces are
   gone is listed "Weld lost its faces – pick again" (never a silent drop). **Motion**: the bead goes with the first
   part; two welded parts on different joints → a warning "these parts are welded but move apart" with *Make them move
   as one* (lead's call – the owner may object). Exploded views and the cutaway section: the bead stays with its part
   and is cut too. **Copies**: if 0293 is merged, a copied subassembly carries its welds (additive hook); if not, leave
   a note for it. **Web 3D page**: the bead baked; what of the heat tint survives – say. **Client view**: welds shown,
   not editable. Clash check: beads left out.
7. **Speed**: an invented weldment with ~300 welds (frame, gussets, tube through plate, tube on tube saddle) – time to
   find the seams, build the beads, save / open, render cost against no welds. Beads light enough for a large machine.
8. Guide (Looks: Welds, with pictures of steel / stainless / aluminium, painted / bare / rusted), function entry
   `looks.welds` (`since=`), a tour stop on the invented weldment, a Full PC-check line (two picked faces give a bead of
   the expected length), a test model maker.

## Done when

- [ ] Two face sets → beads on every meeting line (straight, circle, saddle; touching and small gap) – tests
- [ ] Quick way (two parts) works; segments can be unticked
- [ ] Fillet / butt / all-round / intermittent; sizes in mm; craters
- [ ] Steel / stainless / aluminium looks, pickled, ground flush, painted, rust as above – picture sheet in the report
- [ ] Model update, motion warning, exploded / cutaway, Client view, clash, web 3D – tests or a stated reason
- [ ] ~300-weld weldment timed
- [ ] Tests added/updated; full suite passes; screenshots checked; version fields; owner's test steps; merged, release

## Not in this task

Weld symbols (ISO 2553) as labels and a weld list for drawings – a later task if the owner wants it (say in the report
how hard it would be); the finishes (0274); carbon / Rust slider / better looks (0318); copy itself (0293).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (worker), 24 Nov 2026. Branch `claude/cad-render-animation-0319-fwlaf1` (the web
session's own branch name, not `task/0319-welds`).

**What changed:**
- `core/welds.py` (new, no Blender): the seam finder – CAD edges of one part lying on the other (gap up to 2 mm, sampled
  every 1 mm, ends by bisection), triangle crossings, and at each point the corner in the plane square to the line
  (rays of the nearest faces of both parts; an air sector between a picked face of each = a weld: 35–160° fillet,
  160–200° butt). Seams chained across edges (closed = all round), a second corner on the same line followed too,
  seams meeting at a sharp turn joined with mitred ends (a square post welded round without notches). The bead (rings
  across the corner, fillet legs from the throat a, butt cap + crown, tapers, craters, intermittent pieces even round a
  closed seam, square ends on butt welds), heat-zone strips projected onto both parts (more rows where a flat strip
  would dip under a curved, faceted face), rules per metal (`metal_of`, `defaults`, `rust_of`, `warning`), face prints
  for model updates, seams packed as text for the project.
- `blender/welds.py` (new): settings (`scene.fresing_welds`), `make` / `rebuild` / `refind` / `remove`, two objects per
  weld (bead, heat zone) as children of the first part with MAX hide drivers on both parts, the seams kept in the
  project where they were found (a change of a setting never looks for them where the parts happen to stand – an
  exploded view or a pose), `carry_over` for model updates (with an undo for a failed update), motion check +
  `move_as_one`, painted welds follow their part's paint (`sync_paint` on material updates), the shared test set-up
  (`set_up_test_model`, `pick_test_weld`).
- `blender/weld_looks.py` (new): bead and heat-zone materials (shader nodes only, no scripts): ripples per process,
  steel / stick / stainless (tint, pickled) / aluminium MIG / TIG, ground flush, rust and tea stain, spatter; Painted =
  a copy of the part's own material with the ripples in its normal and rusty toes with Wear.
- `blender/ops_welds.py`, `blender/ui_welds.py` (new): the picker (`Picker`: click / Shift-click, Enter, Esc, live seam
  preview with ticks, its own draw handler: first part blue, second orange, seams green / grey), Weld two parts,
  Remove, Find seams again, Pick again, Tick all, Make them move as one, the right-click **Weld to another part…**;
  3 Looks > Welds.
- Additive: `__init__.py` (registration), `core/places.py`, `core/functions.py` (`looks.welds`, since 0.2.230),
  `context_menu.py` (entry, `ON_PART`, `CLIENT_DROPS`), `hover.py` (a click looks through a weld), `reimport.py` (welds
  carried over, rolled back), `remove.py` (a weld to a removed part is marked lost), `section.py` / `fade.py` /
  `weather_look.py` / `logic.py` (welds go with their part, like decals; left out of the structure tree), `web3d.py`
  (beads exported). `materials.py` not changed (read only).
- Test model `tools/make_test_weldment.py` (TEST.WELDMENT, 7 parts; revision B; `--heavy N`), `tests/data/` and
  `fresing_render/data/test_weldment.step`; tour set + stop "Welds"; PC check line `looks.welds`; real-app test
  `tools/ui_test_welds.py` (group tour, 16 checks); guide section **Welds** with `panel_3_welds.png` and `welds.jpg`;
  `tools/guide_screens.py` mode `welds_panel`.

**Tested and measured** (4-core web machine):
- `tests/test_welds_core.py` (37), `tests/test_welds.py` (34), `tests/test_welds_independent.py` (57, written by an
  independent tester); the tour stop (Go + check), the PC check line (OK, 7.9 s; pick to bead 51 ms), the real-app test
  (16/16), the tests of the shared files touched (251 passed locally); GitHub: see below.
- Test weldment, quick way, every pair right: fin 2 × 200 + 2 × 10 mm fillets; post 2 closed rings 189 mm (π × 60.3 =
  189.4); branch 152 + bore 126 mm; saddle 155 mm closed (corner 78–135°); butt 2 × 300 + 2 × 12 mm.
- **~300 welds** (invented frame, 150 cells, 450 parts, normal quality): 300 welds, 900 seams, 87 m of bead made in
  103 s (0.34 s a weld: finding the seams 0.06 s, the bead 0.03 s, the rest Blender's objects and drivers), 0.9 M
  bead + heat-zone triangles, save 0.49 s, open 0.33 s, file 3.1 MB. Render 800 × 450, 32 samples, Cycles CPU: 16.86 s
  without, 16.85 s with the welds (+0 %). Before a speed-up the 300 took 377 s (a per-triangle Python loop, crossings
  of faceted round faces looked at again).
- Picture sheet (Cycles CPU, test weldment): `docs/img/welds.jpg` – painted fillet, MAG with spatter + a rusty one,
  stainless with heat tint, pickled, aluminium MIG saddle, ground flush butt; `tasks/img/0319_weldment.jpg` the whole
  weldment.
- **Independent tester** (subagent, did not write the code): 57 tests, 16 failed at first – 11 faults, all fixed:
  sheet ≤ 2 mm and thin-wall tubes (a part's far face 2 mm away counted at the corner), seams re-found where an
  exploded view / a pose put the parts (seams and unticks lost), gap 0 and an exact 2.0 mm gap in 32-bit numbers,
  short seams under an overhang, square posts notched at the corners (now mitred joins – my design choice: four
  seams, each can be unticked, joined round the corners; the tester wanted one closed seam), a closed intermittent weld
  with one piece welded all round, two corners on one line, mirrored parts, clicks blocked by an existing weld. A
  second subagent wrote the test model maker.

**Owner's test steps** (on your PC, after Update now to 0.2.230):
1. Help > Make test tour project, open it, go to the stop **Welds** and press **Go**: a small weldment with
   seven welds – blue painted fillet, grey MAG with spatter, a rusty one, stainless with straw-purple-blue tint, a
   matt pickled one, a bright aluminium saddle, a ground-flush butt. Look in Rendered view.
2. Import your own weldment (a frame, a bracket). Open **3 Looks > Welds**, press **Add weld…**, click a face of one
   part (Shift-click for more), press **Enter**, click the faces of the part it is welded to: the seams show green in
   the view. Untick one in the panel (it turns grey), press **Enter**: the bead is there.
3. Click two parts (the second with Shift), press **Weld two parts**: every line where they meet gets a bead.
4. In the weld's box try **Size a**, **Finish** (As welded / Painted / Ground flush), **Metal**, **Rust**; render a
   close-up.
5. Right-click a face of a part: **Weld to another part…** starts with that face.
6. Hide a welded part (the bead hides with it), use Slice on it (the bead is cut too).

**Open points / follow-up tasks:**
- **0318 (Rust slider)**: a weld reads its part's material property `fr_rust` (0 … 1) as the group's rust; 0318 can
  set `mat["fr_rust"]` on the group material (or tell me the node group's name) and the weld follows (the larger of it
  and the weld's own Rust).
- **0293 (copy)**: not merged when this was built. A copied subassembly should copy each weld whose two parts are
  inside it: a new `FRWeld` with the copies as `part_a` / `part_b`, the same faces, `seam_data`, `rel` and settings,
  then `welds.rebuild` (add as a hook in 0293).
- **Web 3D model**: the beads are exported in their colour / paint; the ripples and the heat tint are not (the page
  bakes 0.2 m tiles in the part's space, they live on the weld's own UVs); the heat-zone strips are left out.
- **No Heavy PC-check line**: the weld time grows with the number of welds, measured above with the invented 300-weld
  frame; a Heavy line would need the frame made at run time (`tools/` is not shipped). Ask if wanted.
- Painted welds on a part with **painted faces** take the part's main paint, not a face set's.
- **Weld symbols (ISO 2553) and a weld list** for drawings: the data is all there (kind, throat a, length, all round,
  intermittent piece / pitch); a label showing "a5 ⊿ 4 × 50 (150)" next to each seam with the app's labels and a list
  export would be a medium task (Opus · Medium, ~1 worker session).
- Tester's minor notes left: an extra triangle inside a part's mesh (not closed) can add two short false seams (the
  user unticks them); `core.welds.bead` needs prepared sides (the app always prepares them).
