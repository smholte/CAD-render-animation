# 0027 – Milling: the tool removes material from the workpiece

**Who:** worker · **Status:** running (worker chat started 5 Nov 2026) · **Branch:** `task/0027-material-removal`
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

- [ ] Prototype comparison with numbers (speed per frame, memory, look) in the report
- [ ] Tests: a generic test model (block + flat and ball bit, `tools/make_test_*.py`): a straight
      slot, a pocket and a drilled hole have the right width/depth (within one cell), scrubbing
      back and forth gives the same result, the queue render shows the cut, "finish at CAD part"
      never cuts below it
- [ ] Time per frame measured on the test machine for a 200 × 200 mm block at each detail level
- [ ] Real-app click test step, screenshots, full suite, GitHub run green; merged and released

## Not in this task

- Chips (0028). G-code reading (0026, Motion lane). 4/5-axis and toolpaths made by the app (0029).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
