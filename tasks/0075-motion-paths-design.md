# 0075 – Motion paths the offshore way: design study (findings only, no code changes)

**Who:** worker · **Status:** done 11 Nov – report on its branch, waiting for the lead · **Branch:** `claude/epic-fermat-1y55m0`
(the web session can only push its own branch; `task/0075-motion-paths-design` was not made) (the
report only – **do not push to `main`**; the lead brings it over)
**Started by:** lead chat, 11 Nov 2026 · **Lane:** none – reads code and searches the web; prototypes only in a
scratch folder outside the repository; runs next to every lane
**Model:** **Opus · effort High** · **Environment:** "CAD-render-animation"

## Goal

Motion paths are the owner's priority 4 and the last big feature: cable from a carousel over sheaves through a
tensioner and chute into the sea, a winch drum spooling wire, tensioner track pads running round. Study 0069 (#3)
found how others do it. This study turns that into a **design the lead can write a Fable-day brief from**, building
on 0058 (hoses, cables and drag chains – Thursday) so the two fit together.

## What to do

1. Read `tasks/0058-hoses-cables-drag-chains.md`, `tasks/0069-improvement-study.md` (#3, sources 30–38), CLAUDE.md,
   and the motion code (`joints.py`, `animation.py`, `mechanisms`, `linkages`) – how a speed or a joint drives parts now.
2. Design, with a small prototype for each in Blender (scratch folder; measured ms per frame and how it looks):
   - **Rope over sheaves:** tangent lines + arcs between picked sheaves/drums (radii read from CAD round faces), a mark
     or texture running along at the rope speed, sheaves turning to match.
   - **Tensioner tracks / chains of pads:** rigid pads spaced along a closed path round the track's wheels.
   - **Drum spooling:** layer by layer, opposite hand per layer, the fleet angle to the first sheave.
   - **Catenary into the sea:** keeps its length, touch-down point moves with the vessel.
   - **One cable speed drives it all** (an animation step "Cable speed" or a joint), and how it ties to 0058's curves.
3. For each: what the owner must click (as few as possible), what the app reads from the CAD, scripts-off behaviour,
   the per-frame cost on a 3,000-part model, risks, and what to leave out.
4. **Questions for the owner** (short, with a suggested default each) – which machines he wants first, what must look
   exact and what may be approximate.
5. Write it up in this file below: design per part, prototypes' numbers, a proposed split into tasks (lanes, model,
   order, which can run on a Fable day), the questions. Push to `task/0075-motion-paths-design`.

## Not in this task

Building it. Changing 0058's plan (note conflicts as questions for the lead instead).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (4 cores, no graphics card), 11 Nov 2026. No code in the repository changed;
prototypes in the session's scratch folder (not kept). No GitHub run (only this file changed).

All numbers below were **measured in the web session** (Blender 5.2.3 as a Python module, background, CPU), on a scene
with **3,000 simple parts** (30 shared meshes, like a model's repeated parts) plus the prototype. Baseline frame change
of that scene: **2.5 ms**. The owner's PC and a real 3,000-part model will differ; the *differences* are what count.

### Summary for the lead

1. **Almost everything can run without Python at render time.** One cable speed = one *virtual slide joint* "Cable"
   (value = metres paid out, no members – `joints.create(..., allow_empty=True)` already exists). The existing Motor step
   (mm/s for a slide) and Joint step animate it. Sheaves turn as ordinary **followers** with ratio 360/(π·D) °/mm
   (`RATIO_UNITS[("SLIDE","ROTATE")]`, the "rolling wheel" coupling – the owner could do this by hand today). Rope marks,
   tensioner pads and the drum's wraps are Geometry Nodes inputs driven by the same joint with *simple-expression*
   drivers; the drum's turn (radius changes per layer) is a driver whose F-curve holds one key per layer (a table, no
   Python). Prototype: 12 drivers, all `is_simple_expression`; all checks exact (below). Cost **+0.7 ms per frame**.
2. **What changes shape per frame** (sheaves that move against each other – crane boom, A-frame, a motion-compensated
   sheave – and the catenary behind a moving vessel) is worked out in Python (cheap: 0.16–0.74 ms) but **must not be
   written into a curve/mesh at every frame**: in a frame handler that costs a fixed **+6 ms per frame on 3,000 parts**
   (+0.7 ms on 300), whatever the shape or solver. Instead, **Build animation bakes every frame's shape into one hidden
   "path bake" mesh and Geometry Nodes picks the frame's slice** (Scene Time → Sample Index): **+1.1 ms**, exact (0.0 mm
   against the solver), deterministic, works in the queue and with scripts off. Live posing in the view uses the handler
   (the 6 ms only while the user drags).
3. **The importer cannot give a sheave's rope radius yet.** `step_reader._Axes.add` keeps only the *largest* radius per
   axis: for a grooved sheave that is the flange (460 mm), not the groove. The groove is a torus whose major radius is
   exactly the rope-centre radius (400 mm in the test). A radial profile of the part's mesh finds the groove bottom to
   **0.1 mm** without a cache change (works on old projects); a later cache version could store the torus radii.
4. **This touches 0058** (Thursday): the per-frame write cost and the "bake to slices" answer apply to its hoses and drag
   chains too (20 hoses' curves in one handler: +8.3 ms per frame on 3,000 parts – inside its 20 ms budget, but the
   queue and scrubbing pay it). Questions for the lead at the end; I did not change 0058's plan.

### Design per part

**A. The cable and its speed (shared by everything below)**
- *Owner clicks:* 4 Motion > **Motion paths** > **Add cable** (name, diameter – read from the first sheave's groove, can be
  typed). That makes the virtual joint "Cable <name>" (slide, Motor ticked, no limits). Animate with the existing
  **Run motor** step (shown in m/min) or a Joint step "pay out 0 → 120 m". Reverse = haul in.
- Every path part below *follows* this joint; a machine with two lines (main + aux winch) has two cables.
- A path element hidden by the owner, or a joint changed, is handled like couplings today (Build clears and rebuilds).
- *Scripts off / queue:* only keys on the joint, simple drivers, Geometry Nodes, driver F-curve tables, baked meshes.
- *Model update:* store by part IDs (the 0052 pattern): wheel parts, pad part, drum part, hang-off part; numbers
  (radii, widths) read again from the new revision, typed values kept.

**B. Rope over sheaves (tangent lines + arcs)**
- *Owner clicks:* **Add path** on a cable → click the start (drum, carousel, track exit or any part), then each sheave /
  roller / chute in order, then the end (sea end, hook, a part). Each click on a round face gives the axis
  (`axis_from_hit`); the app reads the groove from the mesh profile (rope-centre radius = groove bottom + rope radius)
  and guesses the wrap side from the order (the rope lies on the outside of the bend of the centre line); a list under
  the path shows each wheel with its Ø and an "over / under" switch. A chute or stinger is a wheel that does not turn.
- *Maths (core, no Blender):* each wheel = centre c, axis n, radius r, wrap side. The rope touches a wheel where
  (q − p)·(p − c) = 0 for the neighbour point q: closed form θ = atan2(q_v, q_u) ± acos(r / |q_uv|) in the wheel's own
  plane; neighbours depend on each other, so alternate over the wheels. **Exact in a plane; with a 5.7° fleet angle
  (sheave 0.3 m sideways over 3 m) tangent error 1e-14 after 3 rounds.** 12 sheaves + points every 20 mm (2,434 points):
  **0.74 ms**.
- *Look:* a tube (12 sides) from the curve; the material reads "length along the rope" (a Geometry Nodes attribute) and
  adds −payout from a driver: marks (or a strand texture) run at the cable speed, also through sheaves that move. Measure
  that length from the drum end (the rope is fixed there), so marks slide over sheaves when a boom luffs without paying
  out – as the real rope does.
- *Sheaves turn:* app-made rotate joint on the sheave's axis (or the owner's existing one) following the cable with
  360/(π·D) °/mm. Prototype: angle = payout / r exactly (3.33333 rad at 2.0 m on r = 0.6 m).
- *Per frame:* fixed sheaves → nothing per frame (shape made once). Moving sheaves → live handler, Build bakes slices.
- *Leave out:* rope stretch, sheave friction, rope riding up the groove flank at a fleet angle (drawn in the sheave plane),
  rope touching other parts.
- *Multi-fall reeving* (hook block, rope up and down n times, hook moves at 1/n): the same path with the hook block's
  sheaves; the block's lift joint follows the cable with ratio 1/n – question 2.

**C. Tensioner tracks / chains of pads**
- *Owner clicks:* **Add track** → click the track's wheels (2 or more, round the loop), click one pad (CAD part). The app
  finds the pad's copies (same mesh, the 0058 drag-chain way), takes the count from them (or length / pitch), hides them
  and lays copies of the pad along the loop. The pads touching the cable move with it (direction set by the side the cable
  is on); the track's wheels follow too. If the track opens/closes by a joint, the loop object is a child of the part
  carrying the wheels: no per-frame work.
- *Maths:* outer tangents between neighbour wheels (closed form), arcs between; pads at s_i = (i·L/N + payout) mod L.
  Belt length exact (7.513274 m expected and found).
- *Prototype:* Geometry Nodes Points → Sample Curve (length mode, floored modulo) → Instance on Points (the pad object),
  offset input driven by the cable: pads move **0.0200 m per frame at 0.5 m/s, 25 fps (expected 0.02)**. 2 × 56 pads:
  part of the +0.7 ms; **2 × 500 pads: +1.1 ms** in total. CAD pads as 112 separate objects instead (handler or keys at
  Build): +0.5 ms, keys for 250 frames written in 1.0 s – also fine, but instancing scales better.
- *Must do in the task:* place each pad by its **two hinge points** on the loop (chord), not by the tangent at its centre
  – on a small wheel the tangent way lets rigid pads overlap; Geometry Nodes can sample at s and s + pitch and align to
  the difference. Sample the loop finely on the arcs (pads rotate per segment of the polyline).
- *Also gives:* caterpillar crawler tracks, conveyor belts, chain drives, the carousel's loading-arm tracks.

**D. Drum spooling (and the carousel)**
- *Owner clicks:* **Add drum** on a cable → click the drum barrel (axis and barrel radius from the round face; the flange
  is the largest radius – the one the cache keeps); width between the flanges from the mesh; rope Ø from the cable;
  **wound at the start** (m) typed; first layer starts left/right; the rope leaves over/under. Optional: click the
  level-wind carriage (a slide joint) – it follows the cable by a table (zig-zag) too.
- *Model:* wraps as a helix per layer, the hand reversing each layer, the next layer one rope Ø · cos 30° higher (lying in
  the grooves of the one below). Drum angle as a function of payout is piecewise linear (one piece per layer) → a
  **"follows by table" coupling**: a driver reading the cable whose F-curve has one key per layer change. Prototype:
  **max error 3·10⁻⁶ rad** over 100 m payout across 3 layers. The wraps are one curve (outside first) trimmed from its
  start by the payout (Trim Curve, length mode) – the trimmed start *is* the point where the rope leaves the drum, and
  the free span to the first sheave starts there (Sample Curve at length 0 → a line). No Python per frame.
- *Fleet angle* to the first sheave: worked out at set-up for both drum ends; a warning above 1.5° (common limit for
  grooved drums – a rule of thumb, owner to confirm).
- *Carousel:* the same spool with the axes swapped (a flat spiral per layer, layers stacked upwards, the turntable is the
  "drum"). A real carousel holds thousands of turns: draw only the top layer and the turn being laid as rope; the stack
  below as one solid ring with a rope texture that shrinks with the payout (else millions of vertices).
- *Leave out:* Lebus crossover zones (two per wrap, where the rope jumps half a Ø) – an option later if the owner wants
  close-ups of the drum (question 4); rope slack on the drum.

**E. Catenary into the sea**
- *Owner clicks:* **Add sea end** on a path → click the hang-off part (chute exit / stinger tip; it moves with the
  vessel), water depth (from the Sea surroundings – it has no seabed yet – or typed), and either "the cable starts on the
  seabed here" (a point) or "the touch-down starts X m behind the vessel" (the app works out the start).
- *Maths:* cable lying on the seabed from its start, hanging from touch-down to the hang-off at height h:
  s² = h² + 2·a·h, X = a·acosh(1 + h/a), and laid + suspended = paid out. One unknown (s), solved by bisection
  (0.017 ms). **Length kept exactly** (polyline check 72.0000 m for 72.0 m paid out). Two edge cases the task must keep:
  *too much cable* (more than span + depth: it would pile on the seabed → warning) and *so tight it lifts off its start*
  (then a two-point catenary of the same length; found by the prototype – a plain bisection silently gave a wrong
  length there).
- *Speed:* the touch-down moves with the vessel and the payout (vessel 12 m forward and 4.5 m paid out over 10 s in the
  prototype). Baked per frame at Build (128 points × 250 frames in one mesh): +1.1 ms per frame, 0.0 mm off the solver.
- *Leave out:* currents, the cable's bending stiffness near touch-down, dynamics; the shape is the static catenary – it
  looks right in a video. Vessel motion at sea is idea #4 of 0069: the hang-off follows whatever moves the vessel.
- *Look:* the Sea surface hides the cable – needs a see-through or cut-away sea near the stern (question 5).

**F. One cable speed drives it all – and how it ties to 0058**
- The chain: Motor/Joint step → "Cable" joint value → (drivers) sheave joints, rope marks, pad offset, drum table, spool
  trim, level wind; (Build bake) moving rope paths and the catenary. The whole spread runs at one speed, and a Pose or
  a still in a saved scene shows the right state for its payout.
- *Shared with 0058* (proposal, the lead decides): the tube-from-curve + material function, the part-type rules
  (add "Sheave", "Winch drum", "Track pad" next to "Hoses & cables"), the live handler + Build-bake mechanism ("bake
  every frame's shape into one mesh, Geometry Nodes picks the slice") as one shared module, and the panel family
  (Motion paths as a second sub-panel of 4 Motion next to Hoses and drag chains). A hose's curve and a rope's path are
  the same kind of object (a polyline with a tube); only the solver differs.

### Prototypes and numbers (web session, 4 cores, bpy module, 3,000-part scene, frame change averaged over 60 frames)

| What | ms per frame | vs. baseline 2.5 ms |
| --- | --- | --- |
| Native set: 3 turning sheaves, rope with running marks, 2 tracks × 56 pads, drum spool + drum table | 3.2 | +0.7 |
| Same with 2 × 500 pads | 3.6 | +1.1 |
| + live handler rewriting the rope over a moving sheave (2,600 points) | 9.9 | +7.4 (maths < 0.7) |
| + live handler rewriting the catenary (128 points) | 8.8 | +6.2 (maths 0.16) |
| Catenary baked at Build, Geometry Nodes picks the slice | 3.6 | +1.1 |
| Write cost alone, 1 curve 2,400 points in `frame_change_pre` / `_post` | 8.4 / 11.0 | +5.9 / +8.5 |
| Write cost alone, 20 curves in one handler | 10.8 | +8.3 |
| Write cost alone, 1 curve, scene of 300 parts | 0.9 | +0.7 (baseline 0.2) |
| 112 CAD pads as separate objects, handler / keys at Build | ~3.7 / ~3.7 | ~+0.5 (keys: 1.0 s to write 250 frames) |

Checks: sheave angle = payout / r exactly; pads 0.0200 m per frame (expected 0.02); spool trimmed by the payout
(15,552 → 15,000 vertices for 5 m paid out); drum table error 3·10⁻⁶ rad; baked catenary 0.0 mm off the solver at frames 1,
77, 250; catenary length exact; 3D tangents with fleet angle exact (1e-14). A Cycles still of the prototype (960×400,
32 samples, CPU): 2.4 s; it looked right after fixing two set-up slips of my own (wrong wrap side, a pad mesh 50 m
off its origin) – the "over/under" switch per wheel is needed.

**Blender 5.2 lessons for the tasks (worth adding to CLAUDE.md section 8 when the first task lands):**
- A Geometry Nodes modifier input is no longer `modifiers["X"]["Socket_1"]`: it is
  `modifiers["X"].properties.inputs.Socket_1.value` (also the driver path). The input's identifier comes from
  `node_group.interface.new_socket(...).identifier`.
- A new driver F-curve (`driver_add`) has a Generator modifier; removing it leaves two keys (0,0) and (1,1) – clear
  `keyframe_points` before writing a table, or the first piece is off (2.3 rad in the prototype).
- Trim Curve in length mode: the inputs are `Start_001` / `End_001` (`Start`/`End` are the factor ones), and End
  defaults to a short length – set it.
- An object hidden in the viewport is not evaluated (known, CLAUDE.md): an instancing source must stay visible (put it
  far away or in an excluded-from-render collection).

### Proposed tasks (numbers by the lead; the lane: **Flex parts**, after 0058, as 0058's report suggests)

| Order | Task | Model · effort | Fable day? | Files |
| --- | --- | --- | --- | --- |
| 1 | **Cable paths: one cable speed, rope over sheaves** – the Cable joint, Add cable / Add path, groove from the mesh, wrap side, sheave followers, rope tube + marks, chute as a fixed wheel, live handler + Build bake (shared with 0058's mechanism), panel, guide, PC-check line `motion.paths`, tour stop, generic test model `test_cable_lay.step` (drum, 3 sheaves on an A-frame with a luff joint, tensioner with 2 tracks of separate pads, chute) made by `tools/make_test_cable.py` | Fable · High (or Opus · High) | **yes** – the base, most design risk | new `core/paths.py`, `blender/paths.py`, `ops_paths.py`, `ui_paths.py`; hooks in `animation.bake`, `reimport.py`, `props.py`, `part_types_data.py` |
| 2 | **Tensioner tracks and chains of pads** – belts round wheels, pads from the CAD pad by hinge points, wheels follow, track opening by a joint; tour stop | Opus · High | no | `paths_track.py` (own file, so 2 and 3 can run side by side after 1) |
| 3 | **Drum and carousel spooling** – layers and hand, "follows by table" coupling (also in `joints.py`: a new coupling kind, additive), level wind, fleet-angle warning, carousel with the solid stack | Opus · High | could be | `paths_drum.py`; small additive change in `joints.py` |
| 4 | **Cable into the sea** – catenary that keeps its length, touch-down moving with the vessel, the two edge cases, seabed in the Sea surroundings, see-through/cut-away sea near the stern | Opus · High | no | `paths_sea.py`; `surroundings.py` (seabed – Scene & Render lane, additive) |

Order 1 → (2 and 3 at the same time) → 4. 4 may wait for idea #4 (vessel motion) if the owner wants both in one video.
The prototype's maths (tangents, belts, spooling, catenary with both edge cases) is all written out above for task 1/2/3/4's
`core/paths.py`.

**Questions for the owner** (suggested default in brackets):
1. Which machine first? *(the cable-lay spread on deck: carousel or drum → tensioner → chute → sea – it uses every part)*
   Others: offshore crane hoist (drum, boom sheaves, hook block), A-frame, anchor-handling winch.
2. Hook blocks with several falls (rope up and down, hook at a fraction of the rope speed)? *(yes, in task 1 if your
   crane has them; say how many falls)*
3. Drum or carousel – which one do your machines have? *(drum first, carousel in the same task)*
4. How exact must the drum look in close-ups – plain layers turning direction each layer, or with the Lebus crossover
   steps? *(plain layers; crossovers later)*
5. The cable under water: should the sea be see-through or cut away behind the stern so the catenary and the touch-down
   show? *(cut-away box behind the stern + clearer water)*
6. Cable speed in the panel: m/min or m/s? *(m/min)*
7. Tensioner pads: are they separate parts in your STEP? *(yes – the app copies your pad; else a simple app-made pad)*
8. Do your sheaves and drums have real grooves in the STEP, or are they plain discs? *(real grooves; else you type the Ø)*
9. Rope look: steel wire rope (strands) or power cable (smooth black with painted length marks), or both?
   *(both – picked per cable)*
10. Must the tensioner visibly squeeze/open in the video? *(only if you already have a joint for it)*

**Questions for the lead (conflicts with 0058, not changed here):**
- 0058 plans per-frame shapes "deterministic … the queue renders frames out of order". If it writes curves in a frame
  handler, every frame costs about 6 ms on a 3,000-part model (measured above), also in the queue. Suggest 0058 bakes
  per-frame shapes into one mesh at Build (Geometry Nodes picks the slice) and keeps the handler for live posing; motion
  paths would then reuse that module. Worth a line in 0058's brief before Thursday?
- Should the tube/material function and the part types "Sheave", "Winch drum", "Track pad" be planned into 0058 so task
  1 here only adds to them?
- Lane: put motion paths in the Flex parts lane after 0058 (as above), or a lane of its own that waits for 0058?
- The importer keeps only the largest radius per axis. Task 1 reads the groove from the mesh (no cache change). Is a
  `CACHE_VERSION` bump to store torus radii worth it later (it would also help joint picking show the groove Ø)?

---

## Owner's answers and the lead's plan (11 Nov 2026, evening)

**Owner's answers to the 10 questions:**
1. First machine: the cable-lay spread – **carousel** usually (chute or quadrant at the stern, depending on the client).
   Cable **Ø 50–500 mm**. Also the **quadrant, quadrant handling winch, quadrant tipping winches**, and **handling winches
   that help the tensioners** when extra pull is needed.
2. Hook blocks with several falls: not needed (none in years).
3. Cable lay: **carousel** and **standalone storage carousels**; a drum rarely for cable lay, but standalone **drum/reel
   winders** exist. Winches: normally **spiral groove** drums, now also **Lebus** for one client.
4. Drum look: **spiral groove**, later **Lebus** grooving.
5. Under water: a cut-away + clearer water, **with a slider to set the water clarity by hand**.
6. Cable speed in m/min; lay speed about **10 m/min**.
7. Tensioner pads: **separate parts**; a large chain with pads on it.
8. Sheave and drum grooves: real grooves (default kept).
9. Looks: **steel wire rope** = the typical winch wire look; **power cable** (laid / in the carousel) = **black with yellow
   angled stripes**. The texture must visibly move along the path.
10. The tensioner **squeezes** in the video.

**No company CAD:** the owner cannot give his employer's models to an AI. Task **0076** makes an invented, generic
cable-lay vessel spread (vessel, carousel + loading arm, cable route, two track tensioners with pad chains, chute,
quadrant + handling/tipping winches, handling winches with spiral-groove and Lebus drums, CPS, route JSON, joint sheet).
It replaces `test_cable_lay.step` above as the test model of every task below. Task **0077** makes the **demo project**
from it (Help > Make demo project: joints, cameras, Open sea / own vessel, waves, an animation); every task below adds its
part to that demo project and its own tour stop.

**Plan (Flex parts lane after 0058; numbers reserved, briefs written when each turn comes):**
| # | Task | Model · effort |
| --- | --- | --- |
| 0078 | Cable paths: one cable speed (m/min), cable along the route over rollers/sheaves/guide wheels, wrap side, groove from the mesh, rollers turn, **cable looks with moving texture** (steel wire rope; power cable black + yellow angled stripes), bake at Build (0058's module) | **Fable · High** |
| 0079 | Tensioner tracks: chain of CAD pads round sprockets/idlers at cable speed, pads grip the cable, **squeeze** by the top-track joint/cylinders | Opus · High |
| 0080 | Carousel spooling (coil layers, carousel turns, loading arm follows the layer), standalone storage carousel; drums: **spiral groove** + **Lebus**, reel winders; level wind/fleet angle | Opus · High |
| 0081 | Cable into the sea: catenary that keeps its length, touch-down, **water clarity slider**, cut-away behind the stern, CPS on the cable; with study #4 vessel motion on waves if the owner wants both | Opus · High |
| 0082 | Quadrant operations: cable end onto the quadrant, quadrant handling winch lowers it, tipping winches tip it over the stern, handling winches pulling with the tensioners (wire to a grip on the cable) | Opus · High |
Order: 0078 → (0079 and 0080 side by side) → 0081 → 0082. 0077 can run before 0078 (new files; Help menu additive).
