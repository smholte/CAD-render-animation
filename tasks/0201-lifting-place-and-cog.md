# 0201 – Lifting L4: a Lifting plan section – place a crane from the library, the load with its CoG, "Hook to here", crane use at the hook

**Who:** worker · **Status:** done (0.2.156) · **Branch:** `claude/elegant-wozniak-oe3stg` (web session)
**Started by:** lead chat, 18 Nov 2026 (study 0180, task L4; owner's order 17 Nov: L4 after 0062) · **Lane:** Lifting
**Area:** new `blender/lifting.py`, `blender/ops_lifting.py`, `blender/ui_lifting.py`, `core/lifting_reach.py`,
`blender/sheet.py` (the sheet reader moved into the app), their tests, a new real-app test `tools/ui_test_lifting.py`;
`site/render_kit/projects.py` + `tests/lifting_rig.py` call `blender/sheet.py` instead of their own copy (Site kit lane
is free); additive: `props.py`, `core/functions.py` (family `lifting`, entries), `core/workspaces.py` (built-in
workspace), `core/places.py` (the new section and its sub-panels), `blender/panels.py` (tab 8 only if it does not
come by itself from `places.SECTIONS`), `blender/lock.py` (nothing new in `ALLOWED` unless a view-only button needs
it), the tour (a new set), the PC check, the guide.
**Model:** Opus · effort High · **Place:** Claude Code on the web, environment "CAD-render-animation"

## Goal

The first lifting plan on screen: the user opens the **Lifting plans** workspace, places a ready-rigged crane from the
library on the ground of his project, picks the parts that are the load (or a box), sees its weight and **centre of
gravity**, clicks **Hook to here**, and the crane slews, luffs and telescopes so its hook stands above the load – with
the **crane use %** at that radius from the crane's chart, in the plan's words (never "safe").

## Background (read these, not more)

- Study `tasks/0180-lifting-plans-study.md`: section 5 (UI flow, steps 1–3 and the "Hook to here" of step 5), section 8
  (the words, the disclaimer, first use), section 9 row L4.
- L1 `core/lifting.py` (0182): `crane_use`, `pick_chart`, `lookup`, `Limits`, `status_of`, status words; the owner's
  answers at the top of `tasks/0182-lifting-checks-core.md` (next longer radius only; 75 % / 90 % / 90 %).
- L2 `core/lifting_library.py` (0190): `list_items`, `read_item`, `charts_of`, `hook_blocks_of`, `is_sample`; the user's
  library folder and the built-in one (`BUILTIN_DIR`).
- L3 (0191): `fresing_render/data/lifting/<class>/` (STEP + equipment JSON + picture: `rig` with joints, cylinders,
  poses, `start_pose`, `groups`, `hook`, `cables`, crawler `tracks`; `mass`, `cog`, `charts`, `hook_blocks`, `limits`,
  `sample`), `lifting_model/classes.py` (`layout`, `hook_point`, `hook_radius_height`, `boom_length`: the maker's own
  kinematics), `tests/lifting_rig.py` (the whole rig set-up the tests use today). Its open points: the sheet reader
  lives in `site/render_kit/projects.py` – move it into the app; `pick_chart` answers "No chart" for an in-between
  counterweight or outrigger spread – offer the next safer chart.
- 0062's report (end of `tasks/0062-ui-clean-up.md`): add the key `lifting` to `WORKSPACE_KEYS`, `BUILTIN` and
  `FAMILY_WORKSPACES`; `workspaces=("lifting", …)` on its functions; its panels in `core/places.py`; a new panel follows
  CLAUDE.md section 6 "A new panel".

## What to build

1. **The section.** A new section **"8 Lifting plan"** (`FRESING_PT_lifting`, after 7 Render queue – no section is
   renumbered) with sub-panels in work order: **Equipment**, **Load**, **Hook & capacity**. The family `lifting`
   ("Lifting plans") shows in the new built-in workspace **Lifting plans** (key `lifting`: Lifting plan + Import,
   Structure, Looks, Scene & Render, Animation, Render queue – no CNC, milling, cables, sea), in All functions and Full
   access; never in the Client view. Section tabs gain "8" (All · 1 … 8). Top of the section: the study's line
   "Planning aid only. …" (section 8, word for word) and, when a sample chart is in use, the SAMPLE line.
2. **First use:** the first time the Lifting plan section is opened (per user, a preference), one dialog with the
   planning-aid line and **I understand** / Cancel; nothing of the section works until it is ticked. Never in
   background, tests (a flag), the PC check, the tour.
3. **Equipment – place a crane.** A list of the library (built-ins by kind and class with their picture, then the
   user's own; a broken item shows its problem, as `list_items` gives it). **Place…** imports the item's STEP as a
   further model of the project (the importer's normal path, Normal quality), rigs it from its `rig` with the app's
   joints, cylinders, poses and tracks – through `blender/sheet.py` (moved from the render kit, one copy, the kit
   calls it) – and lets the user click the spot on the ground / deck / any surface (the hover picker's ray, 0088);
   the mouse wheel turns the heading, Esc cancels. Joint names carry the item's name ("AT-100 · Slew") so **two cranes
   in one project** never clash. Then: **pose** (the file's poses: Travel, Set up, Working …), **chart set-up** from the
   item's charts (boom / counterweight / outrigger spread or tracks – only combinations the file has; an in-between
   value offers the next safer chart, with the reason), **Move…** (place again), **Remove** (the model, its joints, its
   plan data). Data per placed crane in the project (`props.py`, additive): item path + chart hash (a changed library
   file is noticed and named), the model root, the set-up.
4. **Load.** **Use selected parts** makes the load group (parts or subassemblies; a part in two loads is refused), or
   **Box…** (length × width × height + mass). Mass: **entered** (t, with its source: weighed / drawing / estimate) or
   **from volume × density** per material group as a first guess (marked "estimate"), contingency factor (default 1.0,
   the study's range), gross load shown as the sum (load × contingency + hook block when the chart does not include it;
   rigging = 0 until L5, said so). **CoG marker**: worked out from the parts' solid volumes (each part's mesh volume and
   centroid, density per group; a part that is not a closed solid falls back to its box and is named), drawn as the
   usual CoG symbol on top of everything; **Move** lets the user put it by hand (then marked "set by hand"; **Back to
   computed**). The marker rides with the load group.
5. **Hook & capacity.** **Hook to here**: click a point (or **Above the load**: the CoG + a clearance the user enters,
   default 2 m above the load's top) – the crane slews, luffs, telescopes / luffs its jib / folds its knuckle and pays
   out the hoist so the hook block's point lands there, within the joints' limits, **plumb**. The solve is plain Python in
   `core/lifting_reach.py` on the maker's kinematics (`classes.hook_point` = the reference: a test compares the
   solved joint values with it for every class, at many targets) – mobile: slew, luff, telescope; crawler: slew, luff
   (+ luffing jib on CC-750/1600); knuckle: slew, main boom, knuckle, extension. Among several answers prefer the one
   with the **lowest crane use** on the chosen chart, then the shortest boom. Out of reach: say by how much (radius or
   height) and leave the crane as it was. Shown live as the hook moves (also by hand-posing): **radius** (slew axis →
   hook, horizontal), **hook height**, **boom length / angle**, the chart row used (next longer radius), **capacity**,
   **gross load**, **crane use %** with the status word and colour (`lifting.crane_use`, the plan's `Limits`). No chart
   for this set-up / radius past the last row: red with the reason.
6. **The usual parts of a visible change:** tooltips; guide chapter "Lifting plans" (section, first use, place, load +
   CoG, hook to here, the words – the SAMPLE line, "within entered limits"); function entries with `since=` and
   `workspaces=("lifting", …)` and guide anchors; a tour set **"Lifting"** (AT-40 + a small invented load from the test
   models, e.g. the test crane's boom as a load): stops place, CoG, hook to here + use %; PC-check line(s)
   `lifting.place` / `lifting.hook` (Full); the real-app test into `TESTS`, `MIN_CHECKS` and the lightest group.

## Rules

- Words: the study's section 8 – never "safe", "approved", "certified", "compliant", "OK to lift", "passed".
- SAMPLE charts stay marked everywhere they show (panel, crane's decal is L7's – not now).
- Units: SI inside (kg, m, N); the panel shows t and m (the equipment file's units where it has its own).
- Speed: placing an AT-500 and Hook to here on the 4-core web machine measured in the report (import, rig, solve);
  the live readout must not slow the side panel's redraw (no work in `draw`: cache, refresh on change – 0195's A3).
- Old projects open unchanged (no Lifting data = nothing shown but the folded section).

## Done when

- [x] Every crane class placed in a real-app test: joints where `classes.hook_point` says for the file's poses; two
      cranes in one project; Remove leaves nothing behind.
- [x] `core/lifting_reach.py` tests: every class, ≥ 50 reachable targets each, hook within 5 mm of the target and
      inside the joint limits; unreachable targets refused with the right reason; the lowest-use preference.
- [x] Load: CoG of the test models within 1 % of a hand / OpenCascade volume calculation (named in the report); box
      load; by-hand marker; contingency and gross load sums in a test.
- [x] Crane use % in the panel = `lifting.crane_use` for the same inputs (test), with the next safer chart offered for
      an in-between set-up.
- [x] First-use dialog, workspace, tab 8, Client view without the section (tests); old project opens as before.
- [x] The render kit and `tests/lifting_rig.py` use `blender/sheet.py` (no copy left); the kit's own tests pass.
- [x] An independent tester (subagent that did not write the code) breaks it from this brief; findings fixed.
- [x] Tooltips, guide chapter + pictures, function entries, tour set + stops, PC-check line(s); screenshots of the
      section looked at.
- [x] GitHub green incl. Windows; merged to `main`, next free version, released; report filled in; `TASKS.md`.

## Not in this task

Rigging, slings, shackles, the hang solver and the load hanging under the hook (L5); the lift path, per-frame checks,
clearances, reach envelope, ground zones and footprint, exclusion zone, lift data box (L6); the printed plan (L7);
workshop equipment (L8); offshore cranes, Hs charts, DAF, foundation tools (L9). Interpolating charts (owner: never
offered). Any change to `core/lifting.py`'s formulas (a gap found: say so in the report, L1's tests stay).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, session branch `claude/elegant-wozniak-oe3stg`, 18 Nov 2026. Version 0.2.156.

**What changed:**
- **Section 8 Lifting plan** (`FRESING_PT_lifting` + Equipment, Load, Hook & capacity; `blender/ui_lifting.py`,
  `ops_lifting.py`, `lifting.py`), family `lifting` and built-in workspace **Lifting plans** (`core/functions.py`
  `WORKSPACE_KEYS`/`FAMILY_WORKSPACES`, `core/workspaces.py` `BUILTIN`; structure, props, blur also shown there), tab 8
  from `core/places.py` by itself. Never in the Client view. Props additive in `props.py` (`FRLiftCrane`, `FRLiftLoad`,
  `FRLiftDensity`, `FRLifting`, `scene.fresing.lifting`), preference `lifting_understood`.
- **First use:** a dialog with the planning-aid line + SAMPLE line, **I understand**; every lifting operator's poll is
  off until then. Not asked in the background, in tour projects or with `FRESING_LIFTING_UNDERSTOOD` (tests).
- **Place…:** the item's STEP through the importer (Normal; modal with progress), rigged through `blender/sheet.py`
  (joints, cylinders, poses; crawler tracks; the hoist rope as a cable ending on the hook block), then it follows the
  mouse (any surface or the level plane), wheel = 15°, click puts it, Esc removes it. Names carry the crane's name
  ("AT-40 · Slew", second copy "AT-40 2"); a crane's poses hold only its joints (`sheet.apply_own_pose`). Move…,
  Remove (model, joints, cylinders, poses, tracks, cable, its collection, the Looks groups and materials only it had).
  Built-ins are found again in the local app folder when a project comes from another PC. A changed / gone file is named.
- **Set-up:** counterweight and outrigger spread (from the pose by default, `lifting_reach.outrigger_spread`), buttons
  only for the files' values; in-between → next lower (safer) chart with the reason; a missing combination steps down.
- **Load:** parts / sub-assemblies (one load per part, a crane is never a load) or a box at the 3D cursor; mass entered
  with its source or volume × density per material group (`core/lifting_load.py`, closed-solid test by edges + moving
  the origin; an open part falls back to its box and is named); contingency; gross sum (rigging 0 until L5). CoG marker
  = an empty parented to the load's first part, drawn as the black/white CoG symbol on top (POST_PIXEL handler); Move
  marks it "set by hand", Back to computed.
- **Hook to here / Above the load:** `core/lifting_reach.py` – the boom in its plane as a closed-form model read from
  the rig (P1, P2, V0, w, h), slew to the nearest turn inside the limits, luff (+ telescope), luffing jib at the jib
  charts' boom angle (80°; any other boom angle gets no chart, said so), knuckle-boom 2-link IK with the lowest hoist
  rope; candidates = a grid + every chart boom + the lengths at the luff limits + bisection to the shortest; ranked by
  lowest crane use, then shortest boom. Checked against the 3-D kinematics (≤ 1 mm) before it is used. Out of reach:
  by how much (further out / closer / higher / lower).
- **Readout:** radius, hook height, boom + angle (jib / knuckle), chart and why, row (next longer), capacity, gross,
  crane use % with the status word and a coloured dot; cached on a cheap key (joint values, crane place, set-up, load):
  0.03 ms per draw cached, 0.3 ms when worked out.
- **Sheet reader moved:** `site/render_kit/projects.py` → `fresing_render/blender/sheet.py` (+ `root`, `prefix`,
  `set_values(m=)`, `apply_own_pose`); the kit's `projects.py` hands every call on to the app (needs 0.2.156);
  `tests/lifting_rig.py` uses the app's copy. `workspaces.used_functions` counts a crane's own joints/poses/cylinders/
  tracks/rope as the lifting plan's (no "show Motion?" question for them).
- Tour set **lifting** (3 stops), PC-check lines `lifting.place`, `lifting.hook` (Full), real-app test
  `tools/ui_test_lifting.py` (22 checks, group motion), guide chapter "8 Lifting plan" with 4 pictures, function
  entries, the "Own lifting equipment" text updated.

**Tested and measured** (4-core web machine, Linux):
- `tests/test_lifting_reach.py` (46): FK = `classes.hook_point` for all 12 classes; ≥ 55 random reachable targets per
  class, hook within 5 mm (measured ≤ 0.001 mm) and inside the limits; out-of-reach reasons and amounts; slew wrap;
  lowest use then shortest boom; next safer chart; readout = `crane_use`; solids, gross sums.
- `tests/test_lifting_plan.py` (15, bpy): place AT-40 / KB-20 (hook block vs maker for every pose), two cranes,
  Remove leaves nothing (objects, meshes, collections, joints, cylinders, poses, cables, tracks), CC-750 with 4+
  cylinders; **CoG of test_machine.step against OpenCascade (BRepGProp volume properties of the whole STEP): volume and
  CoG within 1 %**; box, by-hand marker, gross; first use; workspace / Client view; the empty section draws.
- **Independent tester** (subagent, own worktree, from the brief only): 55 tests in `tests/test_lifting_*_independent.py`,
  found 9 faults – hoist limit rounding refused the hook's own place on crawlers; a reachable point near the low edge
  refused and the "lower" amount 2.3 m off (telescope only on a grid); open tube / open box counted as closed; Remove
  left 20 Looks groups, their materials and empty collections; the 80° jib charts used at any boom angle; "between" for
  a counterweight above all charts; a gone file gave a wrong message and a traceback from Hook to here; built-ins kept
  by absolute path. All fixed; all 55 pass. Also taken: poll on the last three buttons, Work out again re-reads meshes,
  ranking exactly "lowest use, then shortest boom".
- Real app (`ci_real_app.py --only lifting`, real Blender 5.2.3 under xvfb): 22/22 – the dialog confirmed with Return,
  the AT-40 follows the mouse (0.0 mm), wheel 15.000°, click puts it 0.01 mm from the ray's ground point, **all 12
  classes in one project with every pose's hook block within 0.06 mm** of the maker, unique names, Remove, the boom as
  load, Hook to here by a click (hook block on the clicked ground within 5 mm), Above the load, crane use = chart's,
  save + open, everything removed → project as before.
- Tour set built and Go + check of the 3 stops (bpy); PC-check lines 2/2 OK (place AT-40 0.5 s, hook to here 9 ms).
- **Speed (bpy module, 4 cores):** AT-500 import 1.4 s, rig + place 0.4 s, Hook to here 18 ms (max 24); in the real
  app with its rope: AT-500 2.4 s, CC-1600 8.9 s, KB-200 7.1 s per place (first read of the STEP).
- Kit: `test_site_projects.py` and `test_lifting_cranes_mobile.py` pass with the moved reader (8.5 min).
- **GitHub runs: 2 full runs.** Run 1 (44286647247, c7b143d) red: a tour stop title over 32 characters, the tour
  set's title had a colon (an invalid file name for GitHub's artifacts and Windows), the independent bpy test file left
  the add-on registered for the next file of its group (test_paths_moving), and an older workspace test listed the
  built-ins without Lifting plans. Then main moved (0199 took 0.2.155): merged, renumbered to 0.2.156. Run 2
  (44291686081, 30b0fc0) **green, full, Windows A and B included**, 24 min.

**Open points / follow-up tasks:**
- Lead / owner: a crane with more counterweight than the chart picked (in-between value → lower chart) is conservative
  for capacity but not checked for backward stability – say so in L6's checks.
- Hook to here for a user's own crane needs the built-in joint names (Slew, Luff, Telescope, Jib, Main boom, Knuckle,
  Extension, Hoist); other names are refused in words. L2's chart editor could name them.
- Outrigger chart from the pose reads the beams only; the jacks need not be down (L6: "set up" check).
- `docs/img/sidebar_sections.png` still shows seven sections (the 8th shows only folded at the bottom); next guide pass.
- The CoG symbol is drawn at a fixed screen size; a load in the far distance keeps a full-size symbol.
