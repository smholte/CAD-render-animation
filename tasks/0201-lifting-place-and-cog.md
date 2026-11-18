# 0201 – Lifting L4: a Lifting plan section – place a crane from the library, the load with its CoG, "Hook to here", crane use at the hook

**Who:** worker · **Status:** running · **Branch:** `claude/elegant-wozniak-oe3stg` (web session)
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

- [ ] Every crane class placed in a real-app test: joints where `classes.hook_point` says for the file's poses; two
      cranes in one project; Remove leaves nothing behind.
- [ ] `core/lifting_reach.py` tests: every class, ≥ 50 reachable targets each, hook within 5 mm of the target and
      inside the joint limits; unreachable targets refused with the right reason; the lowest-use preference.
- [ ] Load: CoG of the test models within 1 % of a hand / OpenCascade volume calculation (named in the report); box
      load; by-hand marker; contingency and gross load sums in a test.
- [ ] Crane use % in the panel = `lifting.crane_use` for the same inputs (test), with the next safer chart offered for
      an in-between set-up.
- [ ] First-use dialog, workspace, tab 8, Client view without the section (tests); old project opens as before.
- [ ] The render kit and `tests/lifting_rig.py` use `blender/sheet.py` (no copy left); the kit's own tests pass.
- [ ] An independent tester (subagent that did not write the code) breaks it from this brief; findings fixed.
- [ ] Tooltips, guide chapter + pictures, function entries, tour set + stops, PC-check line(s); screenshots of the
      section looked at.
- [ ] GitHub green incl. Windows; merged to `main`, next free version, released; report filled in; `TASKS.md`.

## Not in this task

Rigging, slings, shackles, the hang solver and the load hanging under the hook (L5); the lift path, per-frame checks,
clearances, reach envelope, ground zones and footprint, exclusion zone, lift data box (L6); the printed plan (L7);
workshop equipment (L8); offshore cranes, Hs charts, DAF, foundation tools (L9). Interpolating charts (owner: never
offered). Any change to `core/lifting.py`'s formulas (a gap found: say so in the report, L1's tests stay).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
