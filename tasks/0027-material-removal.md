# 0027 – Milling: the tool removes material from the workpiece

**Who:** worker · **Status:** done (0.2.19) · **Branch:** `task/0027-material-removal`
**Started by:** lead chat, 5 Nov 2026 · **Lane:** Machining (new files: `blender/machining.py`,
`core/machining.py`, `blender/ui_machining.py`; a small additive hook in `blender/queue.py` /
`queue_runner.py` if the render needs one; `blender/props.py` additive; `docs/USER-GUIDE.md`
(new chapter); `tests/`). Must not edit `ui_motion.py`, `joints.py` or `animation.py` (Motion
lane): its panel is a new sub-panel with `bl_parent_id` of panel 4 Motion, in its own file.

## Goal

The owner picks two parts – the **milling bit** and the **workpiece** – and from then on, whenever
the bit moves through the workpiece in an animation, material disappears, as on the real machine.
No modelling, no manual booleans. Works with any motion (joints, poses, and later G-code from task
0026), in the viewport and in the background render queue.

## Background

- The owner's startup builds a CNC milling machine; milling animations are his main use.
- The tool's motion comes from the existing animation (keyframes on joints); the tool's world
  position per frame is known.
- The owner's machine is 3-axis first; a 4th and 5th axis come later. **Lead's advice:** build
  the removal behind one small interface so the method can be swapped, and compare first:
  **A. Mesh booleans, step by step**, with Blender's fast "Manifold" boolean solver (new in 4.5,
  in the Boolean modifier and the Mesh Boolean node): each frame, subtract the volume the bit swept
  since the last frame (for a straight move of a round bit: the convex hull of the bit at the start
  and at the end) from the workpiece mesh, the state carried from frame to frame (a Geometry Nodes
  simulation zone, which also bakes for the render queue, or Python per frame). Exact sharp edges
  like the CAD part, and it works in any direction, so 4/5-axis later needs no new method.
  Risk: the mesh gets more faces with every cut; long programs may get slow – measure.
  **B. Height map** (1. below) as the fast 3-axis fallback if A is too slow. SDF volume grids
  (2. below) only if both fail. Choose with numbers.
- **Approaches in detail** (measure, then choose; say why in the report):
  1. **Height map ("Z-map")** of the workpiece seen from the tool axis: a grid of heights
     (e.g. 0.1–0.25 mm cells); each frame the tool's shape is stamped along its path since the
     last frame (numpy). Fast, exact for 3-axis milling (pockets, contours, faces, drilling from
     above), cannot do undercuts. The workpiece's top is a dense mesh updated per frame (in the
     queue: before each frame is rendered; in the viewport: on frame change, with snapshots every
     N frames so scrubbing backwards is quick).
  2. **Blender's volume (SDF) grid nodes** (Mesh to SDF Grid, SDF Grid Boolean, Grid to Mesh in
     Geometry Nodes): the swept tool volume subtracted from the workpiece – general (any
     direction), may be too slow/heavy at fine detail. Check what Blender 5.2.3 offers.
  - References for ideas (do not copy code without checking the licence): CAMotics (GPL, 3-axis
    simulator), Fabex/BlenderCAM (GPL Blender add-on with a result simulation).
- Tool shape: read from the bit's geometry (diameter from its round faces, as joint picking does;
  tip flat / ball / corner radius / V / drill point), editable; from Fusion's tool comments once
  task 0026 reads them.
- Optional **"finish at the CAD part"**: the owner also picks the finished part (the CAD model of
  the machined part); removal never goes below its surface, so the end result is exactly the CAD
  part even if the motion is only roughly right.

## What to build

1. "Milling" sub-panel (under 4 Motion): pick the bit, pick the workpiece (stock), optional
   finished part, detail (fine / normal / fast), "Reset workpiece". Several bits allowed.
2. Removal during animations (viewport scrubbing forwards and backwards, playback, background
   queue, stills at any frame) with the chosen approach; cut surfaces look like machined metal
   (the workpiece's material; slight tool marks optional).
3. Saved with the project; model updates keep the set-up when the two parts are still there.
4. Tooltips; new user guide chapter "Milling".

## Done when

- [x] Prototype comparison with numbers (speed per frame, memory, look) in the report
- [x] Tests: a generic test model (block + flat and ball bit, `tools/make_test_*.py`): a straight
      slot, a pocket and a drilled hole have the right width/depth (within one cell), scrubbing
      back and forth gives the same result, the queue render shows the cut, "finish at CAD part"
      never cuts below it
- [x] Time per frame measured on the test machine for a 200 × 200 mm block at each detail level
- [x] Real-app click test step, screenshots, full suite, GitHub run green; merged and released

## Not in this task

- Chips (0028). G-code reading (0026, Motion lane). 4/5-axis and toolpaths made by the app (0029).

---

## Report (filled in by the chat that did the task)

**Chat / date:** worker chat, 5 Nov 2026 (Opus). Version 0.2.19, no installer (owner's usage rule).

**Choice (measured on the 2-core test machine, 200 × 200 × 40 mm block, flat Ø10, feed 2.67 mm/frame):**

| Method | Zig-zag pocket (3,831 frames) | Round pocket of short pieces (1,567 frames) | Look, memory |
| --- | --- | --- | --- |
| A. Manifold boolean **per frame** (lead's first idea) | 26 ms/frame, grows with the mesh (4 → 38 ms), 70,000 triangles | 12–16 ms/frame | exact; mesh grows ~27 triangles per frame (the floor keeps every frame's circle) |
| A'. Manifold boolean **per straight move** (chosen) | **3.6 ms/frame**, flat over time, 2,454 triangles | 11 ms/frame, 27,000 triangles | exact, sharp edges like CAD; 50–480 MB (kept states ≤ 256 MB) |
| B. Height map 0.25 mm | stamping 0.06 ms, but the 800 × 800 mesh costs 109 ms/frame into Blender, 1.28 M triangles, ~580 MB | same | staircase on round and slanted walls (0.25 mm ≈ 2–3 px in HD), no undercuts |
| C. SDF volume grid nodes | present in Blender 5.2.3, not tried: A' already met the targets | | |

A convex bit swept along a straight line is exactly the hull of the bit at both ends, so one boolean per straight move
is exact; the move in progress is cut on the fly each frame. Manifold is the library Blender's own "Manifold"
boolean uses; its Python wheel (manifold3d 3.5.4, Apache-2.0, 1 MB) is bundled like OpenCascade, so the work runs
in numpy/C without Blender operators (also in the frame handler and the render queue).

**What changed:**
- `core/machining.py`: bit shapes (flat, ball, corner radius, V-bit, drill recognised from the part's outline,
  otherwise the outline itself; shanks wider than the cutter as separate convex pieces), straight segments,
  workpiece tiles (split when a piece passes 12–30 k triangles), kept states by work done (≤ 0.25 s to go back,
  ≤ 256 MB), finish at the CAD part (each cut minus the finished part).
- `blender/machining.py`: set-up (workpiece shows its own "(milled)" mesh, CAD mesh untouched), the bits' path
  relative to the workpiece read with frame_set (plus sub-frames on curved cutting moves), a fingerprint of all
  keys/drivers/parents that move them (re-read by itself a moment after a change), frame handler, queue hook
  (`prepare` after the bake and before a still), model-update hook (set-up kept by part ID).
- 4 Motion > **Milling** sub-panel (`ui_machining.py`, `ops_machining.py`), tooltips all "ok"; props additive.
- Self-test line "Milling (Manifold library)"; wheel in manifest, `build_release.py`, CI downloads (env
  `MANIFOLD_VERSION`); `tools/make_test_mill.py` + `tests/data/test_mill.step`; `tools/bench_milling.py`.
- User guide: "Milling" in chapter 4 with a panel picture (test mill, not the crane).
- `tools/tooltip_report.py`: knows the Milling panel; clears its type cache (a second check in one test run
  segfaulted on stale types).

**Tested and measured:**
- 20 core tests (slot width/depth/volume to 0.3 %, ball pocket floor, 118° drill hole volume, half a move,
  scrubbing gives bit-identical meshes, finish at CAD part never cuts below it, tiles give the same volume) and
  14 Blender tests on the test mill (shapes recognised, slot from an animation, table moving, ball groove, finished
  part, re-read after a rebuild, save/open, off/stop, model update, panel draws, tooltips, **real render queue:
  the last frame shows the slot, the first does not**). Real app `ui_test_milling.py`: 17/17 (clicks in the view
  pick bit and block, scrub, play, rebuilt animation followed, undo/redo, save/open, Stop milling).
- Time per frame, all detail levels (fine / normal / fast), mean: pocket flat 4.6 / 3.6 / 2.7 ms, ball 27 / 11 / 5.1 ms;
  round pocket flat 16.5 / 10.8 / 8.2 ms, ball 19 / 13 / 8.2 ms. Scrubbing back 80–1,400 ms; opening a project at the
  last frame 0.3–27 s (everything up to there is cut once). Mesh into Blender 1.8 ms for 2,454 triangles.
- Reading the path: 0.06 ms per frame on the test mill, 10 ms per frame with 2,800 parts riding on the head.
- GitHub run green on the branch and on main (see the CHANGELOG commit). Locally only the milling tests, the
  guide and CI-tool tests and the model-update tests (saving usage). Helper-agent review skipped: no Windows-only code.

**Open points / follow-up tasks:**
- Owner test on his PC: the self-test line confirms the bundled library loads on Windows (GitHub's Windows job
  runs it too); a real milling animation on his machine.
- Painting faces on the workpiece while milling is set up acts on the milled mesh (lost at the next frame):
  paint first, then set up milling. Hidden finished part: if a saved scene shows it again it overlaps the block.
- Found, not this lane: the "Show joint arrows in the view" toggle raises NameError (`_show_joints` is not
  visible to the lambda in `props.py`); undo/redo after "Build animation" run from a script crashes Blender (also
  on main without milling; buttons are fine) – both in CLAUDE.md lessons / for the Motion lane.
- For 0026 (G-code): arcs come in as many short moves (11–16 ms/frame); a G-code task could hand the path in
  directly (exact arcs, no frame_set) through `core.machining.Path`. For 0028 (chips): `Timeline.at(T)` and the
  bits' paths give where and when material is removed.
