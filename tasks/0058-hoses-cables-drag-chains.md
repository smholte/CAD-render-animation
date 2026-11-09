# 0058 – Hoses, cables and drag chains that follow the motion

**Who:** worker · **Status:** open – can start after 0054 is merged (it changes `animation.py`) · **Branch:**
`task/0058-hoses-cables-drag-chains`
**Started by:** lead chat, 9 Nov 2026 (owner's priority 1 of the big features, 9 Nov)
**Lane:** new **Flex parts** lane – new files `core/flex.py` (no Blender: shapes, lengths, solver),
`blender/flex.py`, `blender/ops_flex.py`, `ui_flex.py` (sub-panel of 4 Motion in its own file); small hooks only in
`blender/handlers.py` (frame + load), `blender/animation.py` (`bake`), `blender/reimport.py` (carry over, the 0052
pattern), `blender/props.py` (new property groups, additive), `core/part_types_data.py` (recognise hoses / chains,
additive); tests; guide chapter "Hoses and drag chains"; PC-check line
**Model:** **Fable · effort High** (the owner's "Fable day") · **Place:** Claude Code on the web, environment
"CAD-render-animation"

May run at the same time as 0042 coolant (Machining lane): do not touch machining, chips, air, G-code, toolchange
files. If it needs a change in `gcode.py` (drag chains following the axes during a G-code run), keep it to a hook
and say so in the report.

## Goal

When a machine moves, its hydraulic hoses, cables and drag chains (energy chains) move with it like the real thing:
both ends stay on their parts, the length stays the same, they bend smoothly and sag under their own weight, and
a drag chain rolls over its own bend radius. Today they stay stiff in the CAD pose, so they stretch, float or pass
through parts in every animation – on the owner's mill (drag chains on the axes) and on offshore cranes and
cylinders (hydraulic hoses).

## What the owner works with

- STEP from Inventor and Fusion. Hoses are usually one solid per hose (tube along a path) with fittings as separate
  parts; cables often too. Drag chains are either many identical link parts (igus-style, one part per link, as
  bought-in STEP) or one simplified solid.
- Motion comes from joints, stacked joints, cylinders, mechanisms (0011–0014) and G-code runs (0026/0041).
- Renders: Cycles stills, EEVEE/Cycles videos, the render queue in the background (no window), turntables.

## Scope

1. **Hose / cable between two ends.** The user picks the hose part (or the app finds it: part-type rule "Hoses &
   cables", names like hose, slang, schlauch, kabel, cable). The app reads its centreline and diameter from the mesh
   (a tube's skeleton; works for bent CAD hoses) and its two ends: each end belongs to the part it touches (the
   fitting), with the end's direction. Length = the CAD centreline length (can be changed). Each frame the shape is
   solved from the ends' positions and directions: fixed length, bending stiffness (stiff hydraulic hose ↔ soft
   cable – one slider), gravity sag, minimum bend radius. The CAD solid is hidden and replaced by an app-made tube
   (same diameter, the hose part's material; optional braid/rubber look via the 0046 materials).
2. **Drag chain (energy chain).** Fixed end on one part, moving end on another, travel along one axis (from the
   joint that moves it). Shape: two straight runs + a half-circle with the chain's bend radius, the upper run lying
   on the lower run (or hanging/self-supporting – setting), the bend moves at half the speed of the moving end.
   If the CAD has the chain's links as separate identical parts, the app re-lays those link parts along the shape
   (pitch from the CAD); otherwise it builds links from a simple profile (width, height, pitch, bend radius, colour).
   Vertical and side-mounted chains too (chain plane from the CAD).
3. **Panel** 4 Motion > **Hoses and drag chains**: list, Add hose (pick part), Add drag chain (pick links or the
   chain part, then fixed end, moving end), per item: on/off, stiffness, sag, bend radius, length, "Fit to the CAD
   pose" (reset), a warning when the motion needs more length than the hose has or a bend tighter than allowed
   ("Hose 'X' is too short at frame 120"). Tooltips on every button.
4. **Everywhere the motion shows:** scrubbing, playback, Build animation, the render queue in the background, stills
   in saved poses, turntables, G-code runs, cylinders driven by stroke. Deterministic: the same frame gives the same
   shape whatever frame came before (no simulation that needs earlier frames, or a cached one that is rebuilt on
   change) – the queue renders frames out of order.
5. **Model update** keeps hoses and chains (by part IDs, as joints in 0052); old projects open unchanged (nothing
   added until the user adds a hose or chain).
6. Not now: hoses touching and pushing other parts (collision); cables over sheaves and winch drums (that is the later
   "motion paths" task); hoses with three or more ends; cable bundles. Write ideas into the report.

## Accuracy and speed (tests)

- Ends exact (< 0.1 mm, direction < 1°); hose length within 0.5 %; no bend under the minimum radius (or the
  warning); drag chain: length constant within one pitch, links never overlap, the bend radius exact, the moving end
  exactly on its part over the whole stroke.
- Speed: the Heavy machine (`pccheck/heavy_scene.py`) with 20 hoses and 3 drag chains (test parts added by the test):
  frame change ≤ 20 ms extra; Cycles still render time not more than the extra geometry costs.
- Generic test models made by the worker in the repository (the repository is public – no owner models): a gantry
  with a drag chain on each axis (link parts as separate solids), an arm with a hydraulic hose across a joint, a
  cylinder with two hoses on its barrel, a soft cable hanging between two moving parts. Pictures of each in the report
  (Cycles, small).

## Done when

- [ ] Hoses/cables and drag chains as above, in the panel, recognised by part type where possible.
- [ ] Works in view, Build animation, queue (background), stills, turntable, G-code run (the test gantry driven by a
      short program), cylinders by stroke; deterministic frames (test: render frame 50 after frame 10 and after 90 →
      same shape).
- [ ] Model update keeps them; save/reopen; old projects (0.2.30, 0.2.45) unchanged.
- [ ] The tests above, the speed numbers in the report; an independent review by a helper agent of the solver
      (`core/flex.py`) (CLAUDE.md section 2).
- [ ] Guide chapter "Hoses and drag chains" with pictures; PC-check line `motion.flex`; tooltips.
- [ ] GitHub green; merged to `main`, next free version, released (CLAUDE.md section 7).
- [ ] Report filled in; `TASKS.md`: 0058 done; what the owner should check on his own mill and crane.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
