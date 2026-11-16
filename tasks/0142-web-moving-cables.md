# 0142 – Web 3D model: cables, ropes, coils, hoses and tracks move and keep their looks on the page

**Who:** worker · **Status:** running (16 Nov) · **Branch:**
`claude/cad-render-animation-0142-qdgqzy` (the web session's branch)
**Started by:** lead chat, 15 Nov 2026 (owner compared the demo in the app and on the page, 15 Nov 23:28) ·
**Model:** Opus · effort High · **Place:** Claude Code on the web, environment "CAD-render-animation"
**Area (Web 3D lane):** `blender/web3d.py` (what is exported for modifier-drawn parts), `core/web3d.py` (the file),
`fresing_render/web/fr_page.js` / the player of 0134 (drawing them), their tests; reads – never edits – `paths*.py`,
`spool.py`, `flex.py`, `tracks.py`, `cable_looks.py`.
**Do not edit:** the cable/flex/spool/track code itself (0137, 0138 run there); `sequence.py`; the Import lane.

## Goal

On the web page the demo's power cable, the wire ropes (A&R, tipping, winches), the coil on the carousel, hoses and
track links look and move as in the app: stripes on the cable that travel with the payout, ropes that follow the
quadrant, the coil that winds down, links that run round their wheels.

## Background (owner's comparison, 15 Nov, demo 0.2.105, export: 1024 px, hide names, smaller file, animation, sea +
vessel motion + sky, Balanced + Auto, soft light baked + sun live: 76 MB, 1.9 M triangles)

- **Cable stripes missing:** the power cable and the carousel's coil are plain black on the page. The cable looks
  (`cable_looks.py`) read the tube's point attribute `fr_cable` (angle, length along) and the object's `fr_cable_pay`;
  the export bakes 0.2 m box-UV tiles, which cannot carry a pattern along a cable.
- **Cables do not move:** today `web3d.py` exports each modifier-drawn part as **one** evaluated shape
  (`live = [... if len(ob.modifiers)]`, ~line 1046) and the animation holds only node transforms (~1154–1176). So the
  power cable, the spool rope, the A&R / tipping / winch wires, hoses (flex), and parts moved by a track's Geometry
  Nodes stand still while everything else moves. Same root for all of them.
- The app solves these at Build into shape tables (`FR flex shapes`, `FR cable shapes <name>`, the spool's trim
  lengths, the track loop + phase): the data already exists per frame.

## What to build

1. Pick a way to carry per-frame shapes that stays small – e.g. each cable/rope/hose as its **centre line per frame**
   (fixed point count, 16-bit, as the app keeps it) plus radius, and the page draws the tube in a vertex shader from a
   data texture sampled by time (as the app's Geometry Nodes pick the frame's slice); the coil as its wound path +
   driven trim lengths; track parts as per-part matrices (or the loop + phase, as `tracks.py`). Compare at least two
   ways by file size and page cost on the demo and say why you chose one. Keep the 0105 size rules.
2. **Cable looks on the page:** UVs along the cable (u = metres along, v = angle) and the stripe pattern (`pattern` in
   `cable_looks.py` = the formula in plain Python) as a small texture or shader, moving with the paid-out length per
   frame; the same for the coil and the wire-rope look.
3. Parts drawn by modifiers that are **not** animated keep today's single shape (no cost).
4. Without "Include animation": the shape at the frame shown, with its stripes.
5. A line in the panel's "Not in the web model" note only for what is still left out.

## Done when

- [ ] On the demo's page: the power cable, the coil, the A&R / tipping / winch wires and the track links move with the
      animation (headless page pictures at 3 moments vs the app at the same frames, side by side in `tasks/img/0142_*`,
      invented demo only); stripes visible and travelling.
- [ ] Tests on the small models (`test_moving.step`, `test_spool.step`, `test_tracks.step`, `test_flex_*.step`): the
      page's shape at a frame matches the app's within a few mm (headless probe).
- [ ] File size and page frame time before/after on the demo (Balanced, the web machine) in the report.
- [ ] Guide, tooltips, function list, PC-check line; GitHub run green; merged; version; short list for the owner.

## Design (worker, 16 Nov)

**What the app draws is read back from Blender, not re-solved.** Every shown part with a modifier (and the spools'
own rope and full-layer objects, kind ``spool``) is an *drawn item*, sorted by what its evaluated mesh is
(`blender/web3d_drawn.py`, new; it only reads `paths`/`flex`/`spool`/`tracks`/`paths_riders` data):

* **rigid** – the evaluated mesh is the part's own mesh moved as one piece (track links and pads, drag-chain links,
  CPS riders): the move is fitted from 4 well-spread points per frame (Kabsch) and goes into the node's place, so it
  is plain glTF node animation (works in model-viewer too).
* **tube** – the evaluated mesh is rings round a centre line (cables of 4 Motion > Cables and paths, hoses): read
  back as the ring centres; the ring orientation is the curve's minimum-twist normal, so only the first normal per
  moment is kept (measured: the page's transport matches Blender's rings within 0.003°), and the length along the
  cable is s0 + the summed chords (matches `fr_cable` within 0.05 mm on the test models).
* **spool** – the rope on a drum/carousel: its whole wound path once (its object turns with the spool) + the trimmed
  range per frame (from the evaluated `fr_L`); the full layers below are an ordinary object with a scale animation.
* **hidden** – the CAD coil a spool hides (empty evaluated mesh): left out. **shape** – anything else a modifier
  changes: its evaluated mesh at the frame shown (as before, but the app's shape, not the CAD one).

**In the file** (`core/web3d_tubes.py`, no bpy): a tube node keeps a fallback mesh (the evaluated tube at the frame
shown: other glTF viewers, and the page before its script runs) and gets `extras.fr_tube` = {points, sides, radius,
per-point lo + step (float) and 16-bit points per stored moment (point-major), first normal + s0 per moment, the
moments' times; `pay` (metres paid out: the look's offset) and `trim` (spool) with their own times; `look` = power
cable / wire rope numbers from `cable_looks.defaults` and `fr_cable_look`}. Moments are thinned by a split-at-worst
search (Douglas–Peucker over time): a moment is kept only where straight-line blending between the kept ones would
be off by more than 1 mm (points), 1 mm at the radius (turn), 2 mm (s, pay). The same thinning is applied to every
moving node's translation/rotation track (tolerance 1 mm at the part's size); visibility (STEP) tracks stay whole.

**On the page** (`fresing_render/web/fr_tubes.js`, new, plain functions also run by node in the tests): per tube,
at time t: blend the two moments, tangents (Blender's poly-curve rule), normals by parallel transport from the first
normal, s by chords; trimmed ends for a spool. Written into a small float texture; the tube's vertex shader builds
each ring from it (no per-vertex work in JavaScript); a shadow (depth) material does the same. The look's stripes
(power cable) and strands/wires/grease (wire rope) are a shader patch of the part's own material, from s, the angle
round the cable and the metres paid out (the formulas of `cable_looks.pattern`/`wires`), fading with the pixel size.

**Compared** (demo, Balanced): (a) per-moment centre lines as above vs (b) the whole evaluated tube per frame as
morph targets / per-frame vertices – numbers in the report.

## Not in this task

The sea under the surface and the sea cut-away on the page → 0143. Part tools → 0135.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
