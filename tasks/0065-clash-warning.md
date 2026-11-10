# 0065 – Clash warning: parts that run into each other in an animation

**Who:** worker · **Status:** done (10 Nov, 0.2.53) · **Branch:** `claude/peaceful-heisenberg-t8bw07`
**Started by:** lead chat, 10 Nov 2026 (owner's priority 7 of the big features; the only one not waiting on a busy
lane: 4 motion paths waits for 0058, 5 double-arm = 0064 running, 6 4th/5th axis is in the Machining lane)
**Lane:** new **Clash lane** – new files `core/clash.py` (no Blender), `blender/clash.py`, `blender/ops_clash.py`,
`blender/ui_clash.py` (a sub-panel of 6 Animation in its own file, like `ui_machining.py`); additive: `blender/props.py`,
the render queue's add-to-queue note (`ops_motion.py` `queue_add`, a few lines), PC check, test tour, guide chapter 6
**Model:** **Opus · effort High** · **Place:** Claude Code on the web, environment "CAD-render-animation"

Runs at the same time as **0064** (Machining lane: tool changes, G-code). Do not touch tool-change, G-code, milling,
chips, coolant or air files, nor `handlers.py`, `animation.py`, `reimport.py` (0058 starts there Thursday). Two
releasing tasks at once: take the version number last; whoever finishes second merges `main` once and renumbers.

**Defaults the lead chose (owner can change them before or after):** the check runs on a button (not by itself after
Build); a clash = overlap deeper than **0.5 mm**; the cutting part of a milling tool against the workpiece is not a
clash (it is meant to cut), everything else of the tool, holder and spindle is.

## Goal

The owner animates big machines (offshore winches, cranes, his CNC mill with G-code, tool changers, mechanisms,
cylinders). A part driving through another part ruins a video and, worse, can hide a real design fault. After
building an animation he presses **Check for clashes** and gets a short list: *which two parts, from which frame to
which, how deep*, click a row and the view jumps there with both parts shown in red.

## What to build

1. **What is checked** (so a normal assembly gives zero warnings):
   - Only pairs that **move relative to each other** somewhere in the animation. Parts that keep their place
     against each other all the time (one welded frame, a bolt in its hole, everything on one joint) are never
     compared – group parts into "rigid bodies" per animation first (same world matrix change at every frame).
   - Pairs that already touch or overlap at the animation's first frame (CAD contact, press fits, a pin in its
     bore that turns) only count when the overlap gets **deeper than at the start by more than the clash depth**.
   - Milling: the tool's cutting length (from the tool library, 0040) against the workpiece is skipped; the
     holder, spindle nose and the uncut shank are checked against workpiece, vice and table. Chips, coolant, air,
     labels, decals, toolpath, surroundings and props are left out. (0058's hoses later: leave a hook, say so.)
   - Hidden parts (Show/Hide steps, visibility sets) are skipped while hidden.
2. **How** (worker's design, measured): broad phase on bounding boxes per rigid body per frame; narrow phase on the
   triangles (`mathutils.bvhtree.BVHTree.overlap` is fast in Blender; or your own in `core/clash.py` with NumPy);
   depth = how far the meshes go into each other (a good estimate is enough, say how it is worked out). Fast moves
   (G-code rapids, a turning arm) are checked **between frames too**, so a part cannot jump through another in one
   frame step (sub-steps where a body moves more than a few mm per frame).
3. **The panel** 6 Animation > **Clash check**: Check for clashes (big blue), progress + Cancel, the result in the
   header ("3 clashes", "No clashes", "Not checked since the last Build"). The list: part A × part B (their names
   as in the tree), frames from–to, deepest overlap in mm. Click a row: go to the deepest frame, select both
   parts, show them red (a viewport overlay or a temporary colour – never change their material), frame them in
   the view. A timeline marker at the start of each clash. Clash depth and "Warn about near misses (closer than …
   mm)" (off by default) as settings. Results stored with the project (small), cleared when the animation is
   built again.
4. **Render queue:** adding an animation that has clashes, or was never checked, gives a one-line note (it does
   not stop anything).
5. **Speed:** measure on the test crane, the test mill with G-code, and PC check Heavy's 3,000-part machine
   (scaled down on GitHub). Aim: Heavy machine, 10 s of animation, well under a minute on the owner's PC –
   say what you measured on the web machine and what you expect on his.
6. **Test models:** a small test animation with a known clash (two arms that meet, depth known to 0.1 mm) and one
   with none (a mechanism and a cylinder moving through their whole range). The test gantry with G-code where the
   holder hits a block placed too high.
7. Every button and setting has a tooltip; guide chapter 6 gets a "Clash check" part with a picture; PC-check
   line `animation.clash` (+ a Heavy line for the speed); test-tour stop "Clash check" (a set with the known clash).

## Done when

- [ ] Known clash found with the right parts, frames and depth (±0.2 mm); no false clashes on the test crane,
      mechanism, cylinder, way cover, tool changer (manual + ATC) and milling test projects.
- [ ] A fast move cannot pass through a part between two frames (test).
- [ ] Click a row → frame, selection, red highlight, framing; materials untouched; markers set and cleared.
- [ ] Results saved with the project, cleared at Build; queue note.
- [ ] Speed measured (numbers in the report); Heavy line.
- [ ] Tests (core without Blender + bpy), a real-app test of the panel (in the lightest `GROUPS` group), PC-check
      line + `MIN_LINES_FULL` / `MIN_LINES_HEAVY`, tour stop + `MIN_LINES_TOUR` / `MIN_CHECKS["tour"]`, tooltip report
      strict, guide.
- [ ] GitHub run green; merged to `main` and released (version taken last).
- [ ] Report: design in a few lines, numbers, runs needed, what the owner should try on his own models.

## Not in this task

Fixing clashes for the user, clash-free toolpaths, hoses/cables (0058), anything in the Machining lane (0064, then
0061), the surroundings.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (Opus), 10 Nov 2026. Released as **0.2.53**.

**What changed:**
- **Design** (`core/clash.py` without Blender, `blender/clash.py`): every frame of the built animation (+ the G-code
  program's corners between frames) is set once and every part's world matrix and `hide_render` read in one
  `foreach_get`. **Rigid bodies** = parts whose motion `M(t)·M(0)⁻¹` is the same at every moment (sorted along a
  random projection, then compared within 0.02 mm): never compared with each other. **Broad phase:** body boxes, then
  part boxes. **Between frames:** per part pair, the relative motion of its box corners between two frames; above
  4 mm, extra moments at a screw-motion interpolation of each body (exact for a turn or a slide), at most 48, stopped
  for a pair once it is found inside. **Narrow phase / depth:** both ways round, the mesh's corners near the other and
  points spread over its triangles that cut the other's surface (BVH `overlap`) are tested against the other mesh
  (nearest point + its face's side; beside an edge 3 rays vote); the deepest few then "climb" over their own surface
  to the deepest spot nearby. The result is never deeper than the truth. A pair counts when it is deeper than
  `start + 0.5 mm + ½·start` (start = overlap at frame 1, measured once more finely); touching pairs start at ~0.
  Speed-ups: a bound from the last measured moment (a pair that moved < x against the other cannot be > x deeper,
  one far inside is surely still inside), a corner pre-test when a clash is sure, vectorised pair bookkeeping.
- **Tools:** the cutting zone (tip → end of flutes, radius) of milling bits, the CNC tool, tool-list parts and the
  G-code tool copies is skipped against the workpiece (milling's / the CNC set-up's); with milling on the workpiece
  is the cut mesh at that moment (`machining._timeline().mesh_at`), without it the shank (cutter radius, up to the
  stick-out) may follow its hole. A copy's part above its gauge line is never checked; a tool against the parts of
  its spindle's CAD assembly and against parts carrying changer pockets is skipped. `HOOKS` for 0058 (hoses).
- **Panel** 6 Animation > Clash check (`ui_clash.py`, `ops_clash.py`): Clash depth, Warn about near misses (off) +
  Closer than, Check for clashes (modal: progress in the header, Cancel / Esc), result line, list (A × B, frames,
  depth), click a row → deepest moment, both selected, red (gpu draw handler, materials untouched), view zoomed;
  Show again, No red, More > Clear the result. Markers "Clash: A × B" at each clash start. Results in
  `scene.fresing.clash` with a fingerprint of the built keys; a depsgraph handler + timer clears them after a Build
  with other keys (the same keys built again keep them). Queue note in `ops_motion.queue_add` (4 lines).
- **Test model** `test_clash.step` (`tools/make_test_clash.py`): arm B turns into place, arm A comes down 6.0 mm into
  it (flat faces: the same in every mesh quality, deepest at the last frame), a block 2.0 mm under A's path, a thin
  post for the fast move. PC check `animation.clash` (Full) and `heavy.clash` (Heavy); tour set + stop "Clash check:
  two arms meet"; real-app test `ui_test_clash.py` (21 checks, group machines); guide part with two pictures.
- **Found by the check:** the tour's "Boom up" turned the boom down through the base (axis along +Y): fixed in
  `tour._boom_joint`. Also: Blender's BVH nearest-point search is mm off on long sliver faces (now split ≤ 25 mm),
  the app-made tool copies have faces turned both ways (now turned right per mesh) – both in CLAUDE.md section 8.

**Tested and measured** (4-core cloud machine, Xeon 2.3 GHz; bpy module unless said):
- Known clash: ARM.A × ARM.B, **6.0 mm** at the last frame (hand calculation from the arms' places: 6.0 ± 0.05),
  first frame within 1 of the hand value; real app (normal mesh) 6.0 mm, 21/21.
- Fast move: an arm swung 90° within one frame is found against the post at frame 1.45; without the moments between
  frames it is not (test).
- No false clashes (`tests/test_clash.py`): crane (5 animations) 0, way cover 0, cylinder 0 (with the two cylinders
  the tour never set up left out), mechanisms only the slider-crank's crank pin through the solid bearing block
  (10.0 mm, a fault of the test model; the tour's lift cylinder is no part of its mechanism and was left out), tool
  changes by hand 0, ATC only the test gantry's crude shapes (spindle through the carousel disc, the gantry side
  through the disc), milling 0 (and with the tool zones switched off the bit is reported: the rule does it).
- Speed (`clash.check`): test crane 0.1–0.3 s; clash model 2 s; mechanisms set (49 parts touching everywhere,
  76 frames) 15 s; ATC program (2,983 frames) 7 s; gantry G-code 1.5 s. PC check Heavy machine, **10 s, 3,000 parts:
  73 s** (normal meshes; its made-up animation drives modules through each other: 1,668 clash rows, 3,409 pairs,
  184k narrow tests); 1,000 parts 4.2 s, scaled-down 300 parts 0.25 s. Before the speed-ups the 3,000-part run took
  232 s. **Expected on the owner's PC:** about half (faster single core) – not measured; a real machine with few
  clashes is far quicker than this worst case.
- Locally: test_clash (27), test_clash_core, test_tour, test_pccheck, test_panels, test_blender, tooltip report
  --strict (0 missing), PC-check lines animation.clash / heavy.clash (scaled down), real-app clash + tourui.
- GitHub runs: see below.

**Open points / follow-up tasks:**
- The Heavy line's own animation is a worst case (modules through each other); 73 s here. If the owner's number is
  over a minute: cache the rigid bodies' pair lists between frames, or run the narrow phase on several cores.
- Depth of parts that overlap a lot in CAD (an eye drawn in a solid bracket) is an estimate within a few mm; such
  pairs only count when they go in by half their start overlap more.
- **Double-arm changer (0064, merged during this task):** its tour project lists 27 clashes – the generic arm (a plain
  bar) goes 28–60 mm into the spindle and into the pots during the swap. Real overlaps of that simple model, not
  check errors; the lead decides whether a double-arm swap's arm/pot/spindle contacts should be skipped like pockets
  (a few lines in `clash._mounted`) or the test model's arm get grippers.
- 0058 (hoses): add `clash.HOOKS` to leave hoses out (or check them).
- The owner should try: his CNC mill with a G-code program (a holder against the vice), a winch/crane animation;
  click a row and look whether the pair is real.
