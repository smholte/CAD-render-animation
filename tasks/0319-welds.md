# 0319 – Welds: pick two sets of faces (like Inventor), a real bead where they meet – steel, stainless, aluminium, painted or bare, rust where it belongs

**Who:** worker · **Status:** open – can start · **Branch:** `task/0319-welds`
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

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
