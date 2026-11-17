# 0191 – Lifting L3: ready-rigged generic cranes (mobile telescopic, crawler, knuckle-boom) with sample charts

**Who:** worker · **Status:** running · **Branch:** `claude/nice-dijkstra-2wdjla` (the web session's branch)
**Started by:** lead chat, 17 Nov 2026 (study 0180, task split L3) · **Model:** Opus · effort High · **Place:** Claude Code on
the web, environment "CAD-render-animation"
**Area:** Lifting lane – new package `fresing_render/lifting_model/`, new `tools/make_lifting_cranes.py`, the built-in
files in `fresing_render/data/lifting/`, their tests. Runs beside 0190 (L2 library, `core/lifting_library.py`) – do not
edit that file.

## Goal

The app ships ready-rigged, invented cranes in size classes – the parts, the joints (slew, luff, telescope, hoist,
outriggers, tracks), their masses and centres of gravity, and a plausible **sample** load chart per configuration – so a
later task (L4) can drop one into a project and plan a lift with it.

## Background

- Study 0180's report: **section 2 "Equipment catalogue"** (the kinds, size classes, joints and data per item) and
  **"How the app makes them"** (one parametric maker per kind in `lifting_model/`, the pattern of
  `fresing_render/demo_model/`: params → shapes → STEP with one solid per part → a JSON sheet with joints, cylinders,
  poses in the sheet format `site/render_kit/projects.py` already applies). Section 4 is the equipment file format that
  0190 builds the reader for – write the built-ins in that format.
- **Kinds in this task (owner 17 Nov: onshore first):** mobile telescopic AT-40 / AT-100 / AT-250 / AT-500, crawler
  lattice CC-100 / CC-300 / CC-750 / CC-1600, knuckle-boom KB-20 / KB-50 / KB-100 / KB-200. **Not here:** offshore
  pedestal and heavy vessel cranes (with their Hs charts → L9), tower crane (later), workshop gear and rigging (L8).
- Charts: use `core/lifting.py` (0182) – `Chart`, `chart_to_dict`, `validate_charts`, `pick_chart`, `crane_use`. Every
  built-in chart must pass `validate_charts` with no refusals.
- What the app can already rig: joints / couplings (0011–0014), cylinders (0013), coupled slides (way-cover style k/N,
  0035) for telescope sections, cables and drums (0078 / 0080 / 0174) for the hoist, tracks (0079) for crawlers, the
  render-kit sheet reader (0112). The crane test model `tools/make_test_crane.py` (0122) is a small example.
- The one-solid-per-part rule and joint naming of the demo maker (0076) apply.

## What to build

1. One maker per kind (`lifting_model/mobile.py`, `crawler.py`, `knuckle.py` + shared `common.py`); a class is a
   parameter set. Detail in the style of the demo vessel (recognisable carrier, cab, boom sections, hook block, mats /
   pads), not more triangles than needed (report the counts; aim ≤ ~150 k triangles per crane at Normal).
2. Per class: the STEP, the equipment JSON (format of study section 4 / 0190: `kind`, `class`, `name`, `units`, masses
   + CoG per moving group, `rig`, `charts`, `hook_blocks`, `outriggers` / `tracks` / `axles`, `limits`,
   `"sample": true`, `source`: "invented sample – Fresing Render") and a small picture.
3. **Sample charts:** invented, plausible shape (capacity falling with radius, tip-load end, per boom length ×
   counterweight × outrigger spread; crawler per boom × jib × counterweight; knuckle by outreach). You may *read* 2–3
   public brochures per class to keep the magnitudes realistic – **never copy a maker's table, name, logo or model**,
   and do not put brochure files or their numbers in the repository (public repo, CLAUDE.md section 6: "no maker's load
   chart in the repository"). Say in the report which public pages you looked at.
4. Where the files live: built-ins under `fresing_render/data/lifting/<class>/` if all classes together stay ≤ ~10 MB;
   otherwise ship the maker and make each class on first use into the user's cache (report the sizes and the choice).
5. A tool `tools/make_lifting_cranes.py` that rebuilds every class (like `make_test_*.py`).

## Rules for this task

- Tests (Blender as a module): each class imports with the app's importer + sheet reader; every joint moves through its
  range without parts flying apart (slew 360°, luff min → max, telescope in → out with the sections coupled, outriggers
  in → out, hoist up/down, tracks run); the hook height and radius at two poses match the maker's own numbers within
  10 mm; every chart passes `validate_charts`; `crane_use` runs on each class at three radii. Keep the new tests inside
  the time rules of CLAUDE.md section 5 (one file ≤ ~10 min on GitHub; split if needed).
- A short independent review of the charts by a subagent (shape rules, units, the sample flag), not of the geometry.
- If 0190 is already on `main` when you merge: add a test that every built-in reads with `lifting_library` with no
  problems. If not, 0190 adds it.
- Nothing visible in the app yet (L4 puts the Lifting panel up): no tour stop, PC-check line or guide pictures in this
  task; one guide paragraph naming the built-in classes is enough.
- Normal finish (CLAUDE.md sections 2 and 7).

## Done when

- [ ] 12 classes (AT ×4, CC ×4, KB ×4) made by `lifting_model/`, each with STEP + JSON + picture, rigged and charted.
- [ ] The tests above pass locally and on GitHub; sizes and triangle counts in the report.
- [ ] No maker's data or name in the repository (say so in the report).
- [ ] Report below filled in; TASKS.md row moved to Done.

## Not in this task

The library reader (0190), the Lifting panel and placing a crane in a project (L4), rigging and the hang solver (L5),
offshore / vessel cranes (L9), forklifts, hoists, slings and spreaders (L8).

## Design (worker, 17 Nov 2026)

Files: `fresing_render/lifting_model/` – `classes.py` (pure Python: the 12 parameter sets, the derived geometry and the
forward kinematics `hook_point(cls, values)` in mm), `charts.py` (pure Python: the invented sample charts from the
parameters, `core/lifting.py` types), `equipment.py` (pure Python: the equipment JSON of a class), `common.py` (OCP:
shapes and helpers on top of `demo_model/geom.py` – box tubes, lattice, wheels, cab, hook block, cylinders fitted to a
range), `mobile.py`, `crawler.py`, `knuckle.py` (OCP: the tree `Asm` + the rig), `make.py` (writes a class folder:
STEP, JSON). `tools/make_lifting_cranes.py` = the command line (+ `--pictures`: Cycles, bpy module). Tests:
`tests/test_lifting_cranes.py` (no Blender: charts, JSON, words), `tests/lifting_rig.py` (helper: import + rig in the
app), `tests/test_lifting_cranes_<kind>.py` (bpy, one file per kind).

Model frame (all kinds): STEP in mm, Z up, the ground z = 0, the slew axis = the z axis, the boom in the CAD pose along
+x (y across). Radius = horizontal distance of the hook point from the slew axis. Joint values: 0 = CAD pose; degrees
and mm in the sheet (as `site/render_kit/projects.py`).

Rig (`"rig"` of the JSON, the render-kit sheet's form: `joints` with `rides_on` / `follows` + `ratio` / `limits`,
`cylinders`, `poses`, `start_pose`) plus, for L4: `groups` (mass group -> its sub-assemblies and the joint that moves
it), `hook` (the hook block's sub-assembly, its hook point in the CAD pose), `cables` (the hoist rope part from the boom
head to the hook block: L4 makes it a cable of 4 Motion > Cables and paths, its end on the hook block), `tracks`
(crawlers: wheels, one link, one shoe, the speed joint "Travel": tracks.add).

- **Hook plumb at every pose:** "Hook swing" (rotate about the head sheave's axis, rides on the boom tip) follows
  "Luff" with ratio -1 (knuckle: "Hook swing" follows "Main boom", "Hook swing 2" follows "Knuckle"); "Hoist" (slide
  straight down) rides on it and moves the hook block. Hook point = head sheave centre - (d0 + hoist) z.
- **Telescope:** section k rides on section k-1; "Telescope" moves section 2, sections 3..N follow it with ratio 1
  (boom length = L0 + (N-1) x value). Knuckle extensions the same ("Extension").
- **Outriggers / stabilisers:** "Outriggers" (front-left beam out), the other three follow (ratio 1, each along its own
  outward direction); "Jacks" (front-left jack down, to the ground at full stroke), the other three follow.
- **Cylinders** (luff, main boom, knuckle) sit at the model's top level (a cylinder's parts move with no joint); their
  pins and lengths come from `common.fit_cylinder` (the rod stays in the barrel over the whole range, checked).
- **Crawler:** "Travel" (slide along x) moves the whole crane (`CRANE.ASM`, the root never moves); the tracks run on
  "Travel" (the app's tracks, 0079), "Slew" moves the upper works, "Luff" the lattice boom (wire-luffed: no cylinder),
  CC-750 / CC-1600 also "Jib" (a luffing jib, rides on "Luff").
- **Masses / CoG:** masses per group from the parameters (invented, brochure magnitudes); CoG from the group's solids
  (one density) in the CAD pose, m.
- **Charts:** capacity = min(rated top, boom strength / radius, 75 % tipping rule over the outrigger / track edge with
  the boom's own moment), rounded down, then never more than a shorter boom at the same radius; every chart through
  `lifting.validate_charts`. Configurations: mobile boom x counterweight x outrigger spread, crawler boom (+ jib) x
  counterweight, knuckle outreach (extensions out) x stabiliser spread.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
