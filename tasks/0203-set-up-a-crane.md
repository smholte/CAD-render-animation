# 0203 – Lifting L4b: "Set up a crane" – rig your own crane STEP step by step in the Set-up window, save it to the library, Hook to here on any crane

**Who:** worker · **Status:** running (18 Nov) – after 0201 (uses its Lifting plan section, placing and Hook to here) ·
**Branch:** `task/0203-set-up-a-crane`
**Started by:** lead chat, 18 Nov 2026 (owner: "easily import cranes and have a rigging menu for the different types,
sub-menus like the set-up of mechanisms"; owner's order 18 Nov: straight after L4) · **Lane:** Lifting
**Area:** new `blender/setup_crane.py` (the crane kinds' step lists for the Set-up window), new `blender/lifting_rig_out.py`
(the scene's rig → the equipment file's `rig`, the reverse of `blender/sheet.py`), `core/lifting_reach.py` (a general
solver – see point 4); additive: `blender/ui_setup.py` (`SETUPS` entries, `CHECKS`, `STEP_OF`), `blender/ui_lifting.py`
(one button "Set up a crane…"), `props.py`, `core/functions.py`, the tour, the PC check, the guide; tests. Beside 0204
(Make a crane): it owns its own files – `ui_lifting.py` is touched by both with one additive line each; the second to
merge updates to `main`.
**Model:** Opus · effort High · **Place:** Claude Code on the web, environment "CAD-render-animation"

## Goal

The owner imports the STEP of a real crane (his own or a maker's model he may use) and makes it a working lifting-plan
crane in about an hour: a Set-up window walks him through it step by step for his kind of crane, using the app's own
joints, cylinders, cables, drums and tracks; at the end the crane is in his library with masses, CoG and his load chart,
and Place, Hook to here and crane use % work on it exactly as on the built-in cranes.

## Background (read these, not more)

- The Set-up window (0062): `blender/ui_setup.py` – `SETUPS = {kind: (title, [(step title, draw), …])}`, `CHECKS` (a
  step already done shows a green tick), `STEP_OF`, `fresing.setup_in_view` for picks in the 3D view; its rule
  "nothing is copied": a step draws the app's own operators and settings. CNC mill and mechanism are the examples.
- 0201's report (when merged): the Lifting plan section, the placed-crane data, `blender/sheet.py` (equipment `rig` →
  joints / cylinders / poses / tracks), Hook to here and `core/lifting_reach.py`.
- L2 `core/lifting_library.py`: `new_item`, `validate`, `write_item`, `chart_rows` (CSV / table entry with the study's
  refusals), `is_sample`. L3's equipment files (`fresing_render/data/lifting/<class>/<class>.json`) are the model of a
  complete `rig`: joint names and kinds, `rides_on`, `follows` + `ratio`, cylinders, poses, `start_pose`, `groups`,
  `hook` (assembly, point, joint, plumb by swing joints with ratio −1), `cables`, crawler `tracks`; `mass` + `cog` per
  group.
- Study 0180 sections 2 (the joints each kind needs), 4 (own equipment), 5 (UI flow).

## What to build

1. **"Set up a crane"** in the Set-up window, opened from 8 Lifting plan > Equipment (**Set up a crane…**) and from the
   Set-up window's kind picker. Kinds, each with its own step list:
   - **Mobile telescopic crane:** Model (the imported STEP; a hint if none) → Slew → Luff (rotate joint + luff cylinder,
     0013) → Telescope (base + sections; the sections coupled by ratio as the app's way covers / L3 do) → Fly jib
     (optional) → Hoist (head sheave, rope as a cable over the sheaves to the winch drum – 0078 / 0080; number of falls
     stored; drawing the falls is L5) → Hook block (its parts, the hook point; plumb by swing joints, as L3) → Outriggers
     (beams + jacks, spreads full / middle / narrow) → Counterweight (its parts, steps in t) → Masses & CoG → Load chart
     → Check → Save.
   - **Crawler crane:** Model → Tracks (0079) + travel → Slew → Boom (luff; boom lengths of the charts) → Luffing jib
     (optional) → Hoist → Hook block → Counterweight → Masses & CoG → Load chart → Check → Save.
   - **Knuckle-boom crane:** Model → Slew (column) → Main boom + cylinder → Knuckle + cylinder → Extensions (coupled) →
     Winch / hook (optional) → Stabilisers → Masses & CoG → Load chart → Check → Save.
   - **Other crane (general):** the same building blocks in a free order, every joint given its **role** by hand – for
     cranes the three kinds do not fit (offshore pedestal cranes come with L9 as their own kind).
   Each step: the parts picked by clicking or by name (search box), the joint made with the app's own operators (hover
   picker 0088 for axes), its limits, its **role** (slew / luff / telescope / jib / knuckle / extension / hoist / swing /
   outrigger / jack / track / travel) stored on the joint; Back / Next; a step done shows its tick. A step that is not
   there on this crane can be skipped (says so).
2. **Masses & CoG:** per group (carrier / lower, superstructure / upper, counterweight, boom, jib, hook block): mass
   entered (t) or from volume × density (0201's load CoG code – reuse, do not copy), CoG computed or set by hand,
   shown as markers.
3. **Load chart:** L2's chart entry – typed table or pasted / read CSV per configuration (boom length / jib /
   counterweight / outrigger spread), with its refusals by row; wind speed, "chart includes hook block"; source text.
   No chart = the crane can be placed and moved but crane use says "Not checked – no chart" (grey).
4. **Hook to here on any crane:** a general solver in `core/lifting_reach.py` that works from a `rig` (joint frames,
   roles, couplings, limits, the hook point) instead of a class's own formulas: slew from the target's direction, then
   the reach joints (luff, telescope, jib, knuckle, extension) by a bounded search / Newton, hoist for the height, plumb
   hook. **Proof:** on all 12 built-in cranes it gives the same joint values as 0201's class solver (hook within 5 mm,
   the same preferred answer: lowest crane use, then the shortest boom); then 0201's class solver may stay as the
   reference in the tests only, the app uses the general one for every crane (say in the report).
5. **Check** (last but one step): runs every driven joint min → max and the poses; the hook stays plumb; the clash check
   on the crane's own motion (0065) with its rows; masses and CoG plausible (sum, CoG inside the footprint at rest);
   chart validated (L1). Problems listed with **Go to step**.
6. **Save to library:** writes the equipment folder (L2's format: `<name>.json` + the STEP copied + a small picture of
   the view) through `write_item` – never into the built-ins; the `rig` written by `lifting_rig_out.py` by part names, so
   the item places in another project from the library exactly as the built-ins do. **Round trip:** save → Place in a new
   project → the same joints, poses, hook point, masses, chart.
7. **The usual parts:** tooltips; guide chapter "Set up your own crane" (one section per kind, the roles, the chart
   entry, the check, the library); function entries (`since=`, `workspaces=("lifting", …)`); a tour stop (a built-in
   crane's STEP rigged from the start by the set-up's own operators – the tour can do the steps by name); PC-check line
   `lifting.setup`; real-app test in `TESTS`, `MIN_CHECKS` and the lightest group.

## Rules

- **Nothing copied** (Set-up window rule): every step draws the app's own operators; what is done in a step shows in
  4 Motion and the other way round.
- The study's words (section 8). An own crane without the owner's chart is never "within limits".
- The repository is public: tests use the built-in cranes' STEP files (invented), never the owner's.

## Done when

- [ ] Real-app test: **AT-40, CC-750 (with its jib) and KB-50 rigged from their bare STEP through the Set-up window only**
      (clicks / names as a user would); the result compared with the built-in `rig` of the same class: same joints,
      roles, couplings, limits, hook point (within 1 mm / 0.1°), same poses; Save → Place in a new project → Hook to here
      gives the class solver's answer.
- [ ] General solver tests: all 12 classes, ≥ 50 targets each, as 0201's; an "Other crane" rig (e.g. a knuckle crane
      rigged with hand roles) solves too; unreachable targets refused with the reason.
- [ ] Check step finds a planted fault of each kind (joint past its limit, hook not plumb, clash, mass missing, chart
      refused) and leads to the step.
- [ ] Masses & CoG, chart entry (table + CSV) and the round trip tested; the library never written into the built-ins.
- [ ] An independent tester (subagent that did not write the code) breaks it from this brief; findings fixed.
- [ ] Tooltips, guide chapter + pictures, function entries, tour stop, PC-check line; screenshots of every kind's
      steps looked at (no cut-off text at 297 px, the Set-up window's width).
- [ ] GitHub green incl. Windows; merged, next free version, released; report filled in; `TASKS.md`.

## Not in this task

Drawing the rope with several falls and its winding (L5); slings and the load under the hook (L5); offshore pedestal and
vessel cranes as kinds (L9); tower and gantry cranes (L8); "Make a crane…" from parameters (0204).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
