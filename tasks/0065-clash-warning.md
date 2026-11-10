# 0065 – Clash warning: parts that run into each other in an animation

**Who:** worker · **Status:** open – can start (10 Nov) · **Branch:** `task/0065-clash-warning`
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

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
