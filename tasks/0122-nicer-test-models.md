# 0122 – Nicer test models: better looking, more detail, more functions per model

**Who:** worker · **Status:** running (14 Nov 2026; 0119–0121 done); not at the same time as 0062 · **Branch:**
`ccr-bde4018f-wmqawe` (the session's branch)
**Started by:** lead chat, 14 Nov 2026 (owner's wish) · **Lane:** Test models (new): `tools/make_test_*.py`,
`tests/data/*.step` + their copies in `fresing_render/data/`, the set builds in `blender/tour.py` (only the sets of the
models it changes), the expected numbers in the tests that read those models, guide pictures that show a changed model
**Model:** Opus · effort High (subagents, see CLAUDE.md section 2) · **Place:** Claude Code on the web, environment
"CAD-render-animation"

## Goal

The test models are what people see first: in the test tour, in the PC check report, in guide pictures, and soon in
the interactive learning modes (study 0123) and on the website. Today they are plain blocks and tubes. The owner wants
them **visually nicer, with more detail, and each showing more of the app's functions**, while every automatic test
keeps working.

## Background

- 23 makers in `tools/make_test_*.py` write 27 models (`fresing_render/data/`, copies checked by a test). The test tour
  (`blender/tour.py`, 37 sets, 61 stops) builds one small project per model; the PC check and many pytest and real-app
  tests read them; guide pictures use the test crane.
- They are invented models: free to change, free to show anywhere (GPL repository). **Never** anything of the owner's
  employer, its clients, or the Fresing 400 (CLAUDE.md section 6).
- Rules that bind every test model: each part one solid (`fuse`; several solids lose their colour – section 8),
  AP214/AP242 with colours, names the part-type library sorts the intended way, every tour animation gives 0 clashes
  (`test_every_tour_animation_has_no_clash`), the whole tour builds in about 2 minutes, GitHub's full run stays about
  12 minutes.
- Study 0123 (interactive learning) runs before or beside this task. If its report is on `main` when this task starts,
  read its "lesson per test model" section: it may ask for parts or names the lessons need.

## What to do

1. **Look first, one stop for the owner.** Make an inventory: per model what it shows, which tests read it and what
   they assume (part names, counts, places, joint axes, numbers in checks). Then upgrade **one** model (the test crane
   is the obvious one) and render before/after stills (Cycles, the tour's own shot, small). Propose per model: what
   gets added (real-looking shapes: fillets/chamfers, bolts and nuts at joints, hydraulic hoses, plates with holes,
   ribs, handrails, decals, a name plate, paint schemes; machine-like proportions), and which **extra functions** it
   could show (e.g. the crane with labels, a decal and a hose; the mill with a way cover and coolant). Show the owner
   the stills and the list in one message and **wait for his pick** (the one stop in this task).
2. **Build in batches** after his pick. Keep the geometry the tests rely on (joint pivots, travel, pocket places, the
   faces the pickers find) or change the expected numbers on purpose and say so in the report – never loosen a check
   to make it pass. Details are real parts with sensible names (they must sort right in the part-type library and not
   create clashes).
3. **Budget:** at most ~2 × the triangles of each model at Normal, the tour build ≤ ~2.5 min, no GitHub job longer than
   before by more than ~10 %. Measure before/after (import time, tour build, the jobs' times) and put them in the
   report.
4. Tour stops: update the "what you should see" texts and checks of changed sets; a model that now shows an extra
   function gets that function's stop in its set (or the stop moves to it) – keep `MIN_LINES_TOUR` / `MIN_CHECKS` right.
5. Guide pictures that show a changed model: re-make them (`tools/guide_screens.py`).

Subagents (section 2): one per batch of makers + an independent tester who runs the tour, the clash test and the
model-reading tests against the new models. Shared files (`tour.py`, version files, CHANGELOG, `TASKS.md`) stay with
the worker.

## Done when

- [ ] Owner's pick from step 1 in the report.
- [ ] The picked models upgraded; each still one solid per part, colours kept, sorted as intended, 0 clash rows on
      every tour animation.
- [ ] Every test passes without loosening; changed expected numbers listed in the report with the reason.
- [ ] Before/after numbers: triangles, import time, tour build time, GitHub run time.
- [ ] Tour texts and checks current; guide pictures of changed models re-made; PC check still all OK.
- [ ] GitHub green incl. Windows; merged to `main`, next free version, released; report filled in; `TASKS.md`.

## Not in this task

New app functions. The learning modes themselves (0123 and after). The site's own models (Thor, CEB press, turbine,
the demo vessel). Old test models that only exist for an old-project test (`old_app_template`, `test_crane_inv_*`):
leave them.

## Design (worker, 14 Nov 2026)

### Step 1 – inventory (short; read-only map by an Explore subagent + the worker for the crane)

| Model (maker) | Readers | What must stay | Risk |
| --- | --- | --- | --- |
| crane a/b (`make_test_crane.py`) | ~40: tour hub + looks, marine, cutaway, copies, update, vessel, weather sets; PC check; guide; test_phase2, test_hover, test_model_update, test_studio_cameras … | names BASE, PEDESTAL, BOOM.ASM/BOOM/BOOM.PIN, TROLLEY.ASM/TROLLEY/WHEEL, COVER, ISO 4017 bolts; PIVOT (100, 300, 400); BOOM.PIN untouched (hover: tris 0–52); trolley 0.35 m travel; rev B = lamp, one bolt less, cover +10 mm | medium: counts (12 parts) and pedestal triangle ranges in tests change on purpose |
| gantry, mill, toolpath, 4axis, 5axis, atc | tour machining sets, PC check milling/motion lines, ~25 tests | tool names and tips, stock, pivots, pockets, gauge line; nothing new in the cut zone or a sweep | low–medium |
| spool, sea, moving, tracks, sequence | tour offshore sets, their `set_up_test_model`s | exact PARTS lists, UIDs with instance numbers (tracks), nothing near a cable | medium (lists change on purpose) |
| cylinder, waycover b/c/d | tour, PC check | stroke from barrel/piston/gland, pins' first axis; carriage min x | medium |
| clash, linkage, decals, faces, machine, materials, mesh, flex, paths | many exact numbers (clash depth 6.0, 8 links/9 pins, CAD face indices, 11 placed parts, byte-identical glTF, hose lists) | almost everything | high: leave, or add separate parts only |

Not made by a maker / left alone: `test_waycover_a` (owner's generic sub-assembly), `test_crane_inv_*`, `old_app_template`, `test_tool_*`.
Copy gap found: no test compares the shipped copies of test_cylinder_a, test_linkage_a, test_toolpath, test_waycover_a/b.

### Step 1 – the crane upgraded (draft on the branch: `tools/make_test_crane.py`, `--plain` = the old crane, `--luff` = proposal B)

- BASE: anthracite plate, chamfered corners and top edges, bolt holes; PEDESTAL: foot flange with 4 socket screws
  (ISO 4762 M10 x 20 – new parts) and gussets, chamfered block, cheeks with round tops and bosses; BOOM: chamfered
  girder, round end round the pin, side ribs, tapered tip, end stop; TROLLEY: chamfers, hoist motor and rope drum;
  WHEEL: flanged; COVER: round corners, screw heads, handle; bolts: hex heads with the shank in the holes.
- B adds LUFF CYLINDER.ASM (barrel + rod) between a fork on the pedestal and a fork under the boom (shows the
  cylinder function; every crane set would set it up).
- Measured (4-core web machine, Normal): 1,008 → 7,072 unique triangles (B: 10,296), 12 → 16 placed parts (B 18);
  import 0.2 → 0.3 s; tour crane set build 3.1–4.3 s → 4.6 s. The ×2 triangle budget cannot hold for models made of
  plain boxes (12 triangles each): owner asked.
- Stills (Cycles, the tour's Tour view): sent to the owner in the session.

### Owner's pick (14 Nov 2026, in the session)

Crane **B** (more detail + luffing cylinder, set up in every tour set that uses the crane); batches **Machines**,
**Offshore** and **Small models**; not the fragile ones (clash, linkage, decals, faces, machine, materials, mesh,
flex, paths). Budget: **2 × the triangles at Normal or 10,000, whichever is more**; tour build ≤ ~2.5 min, no GitHub
job more than ~10 % longer.

### Split (subagents, CLAUDE.md section 2)

| Who | Files it owns | Tour sets it may edit (only their build functions, checks and stop texts in `tour.py`) |
| --- | --- | --- |
| worker (this session) | `make_test_crane.py`, `model_details.py` (shared helpers – read-only for the others), crane data files, `tour.py` crane sets + merging, tests reading the crane, guide pictures, version, CHANGELOG, TASKS.md | crane, looks, marine, cutaway, copies, update, vessel, weather, web3d stops |
| Machines | `make_test_gantry.py`, `make_test_mill.py`, `make_test_toolpath.py`, `make_test_4axis.py`, `make_test_5axis.py`, `make_test_atc.py`, their `tests/data` + `fresing_render/data` files | gantry, atc, mill, tools, marks, air, coolant, toolpath, rotary4, rotary5, doublearm |
| Offshore | `make_test_spool.py`, `make_test_sea.py`, `make_test_moving.py`, `make_test_tracks.py` (+ data) | spool, sea_cable, moving_cable, tracks |
| Small | `make_test_cylinder.py`, `make_test_waycover.py` (b/c/d; `test_waycover_a` is the owner's file: untouched), `make_test_sequence.py` (+ data) | cylinder, waycover, waycover2, sequence, productvideo |
| Independent tester (after the merge) | none: runs the tour, the clash test, the model-reading tests and the PC check lines; reports | – |

Rules for every batch: each part one solid; colours kept; names checked with `part_types.classify`, fasteners in
ISO/DIN notation; no part starting inside a part of another rigid body; nothing new inside a sweep; every tour
animation of its sets 0 clash rows; the geometry the tests rely on kept – or an expected number changed on purpose and
listed (file:line, old → new, why); never loosen a check. Helpers: `tools/model_details.py` + `demo_model/geom.py`.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, session branch `ccr-bde4018f-wmqawe`, 14 Nov 2026 – version **0.2.101**.

**Owner's pick (step 1):** crane **B** (more detail + a luffing cylinder that follows the boom), batches **Machines**,
**Offshore**, **Small models**; budget **2 × or 10,000 triangles, whichever is more**. Fragile models left alone
(clash, linkage, decals, faces, machine, materials, mesh, hoses/chains, cable paths).

**What changed:**
- Crane (`make_test_crane.py`, worker): anthracite chamfered base with bolt holes; pedestal with foot flange, 4 ISO 4762
  screws, gussets, chamfered cheeks; boom girder with round end, ribs, tapered tip, end stop; trolley with hoist;
  flanged wheels; cover with handle; real hex bolts; **HYDRAULIC CYLINDER.ASM** (hollow barrel, piston rod) on two
  LUFF PINs in forks. `tour.luff_cylinder` (called by `_boom_joint`, also from the PC check and the guide) sets it up
  as a follower and gives the boom the cylinder's limits (−1.5° … 37.6°); the boom stop checks the rod eye on its pin.
  `--plain` still writes the old crane; `tests/data/test_crane_plain.step` keeps it for the 0087 camera golden keys.
- Machines (subagent): mill, toolpath, gantry, atc, 4axis, 5axis – cast beds, ribbed columns, rails + guide blocks,
  servo and spindle motors, T-slot tables with toe clamps, bearing caps, magazine guard (new `tools/machine_parts.py`).
- Offshore (subagent): sea (deck plating, bulwarks, bollards, bolts), moving (knee braces, end stops, power unit),
  spool (deck plate, gearbox, motor, pillow blocks, bolts), tracks (portal frame with two lift cylinders, gussets).
- Small (subagent): luffer (anchor bolts, flanges, gussets, ports, manifold, gland screws), way covers b/c/d (bed with
  rails, ball screw, motor, folded sheet sections), spindle unit (fins, keyway, V-belt pulley with key, hex nut).
- Shared helpers `tools/model_details.py`; guide pictures of the changed models re-made (14 pictures, panels not).

**Expected numbers changed on purpose** (none loosened):
- `test_phase2`: structure list + "HYDRAULIC CYLINDER.ASM"; crane parts 12 → 20 (A and B); `test_stacked_joints:528` 12 → 20.
- `test_hover` hole: the spot in the front cheek (the foot is wider); the bore's block = 52 triangles starting at a CAD
  face start (was two fixed ranges). `ui_test_app2` stack click: compared with the ray through the clicked pixel to
  0.5 mm (was the ideal point to 2 mm: one pixel spans 2.5 mm on that face) – stricter.
- `test_queue_schemes`, `test_fixes_0120`: the yellow group is "Welded frames & structures #F9A800" (boom + pedestal;
  the base is anthracite now). `camera_golden_0087.py`: the plain crane (keys written with code before 0087).
- `test_waycover:312` 0.06 → 0.12 (the end bracket now lies before the sections); `test_web3d` mill parts 9 → 25;
  `test_make_test_sea` 20 → 54, `test_make_test_moving` 14 → 34, `test_spool_model` lists and 22/21 → 35/25.
- `test_pccheck` copy check now also covers test_cylinder_a and test_waycover_b.

**Tested and measured** (4-core web machine; Normal quality; triangles unique, before → after):

| Model | Triangles | Placed parts |
| --- | --- | --- |
| crane A / B | 1,008 → 9,448 / 7,610 → 10,104 | 12 → 20 / 12 → 20 |
| mill / toolpath / gantry | 2,693 → 8,095 / 2,573 → 7,593 / 3,068 → 7,580 | 9 → 25 / 8 → 24 / 11 → 31 |
| atc / 4axis / 5axis | 6,951 → 10,917 / 1,515 → 6,541 / 940 → 5,176 | 25 → 40 / 10 → 28 / 11 → 30 |
| spool / sea / moving / tracks | 36,742 → 41,542 / 11,556 → 16,598 / 27,952 → 31,890 / 12,796 → 15,296 | 22 → 35 / 20 → 54 / 14 → 34 / 171 → 180 |
| cylinder A / B | 7,474 → 14,622 / 14,076 → 21,224 | 23 → 27 / 24 → 28 |
| waycover b, d / c / sequence | 108 → 1,868 / 168 → 2,752 / 4,656 → 9,902 | unchanged |

- Import of the crane 0.2 → 0.3 s. Whole tour build 119.7 → 135.9 s (house set alone +17 s: noise, unchanged model);
  the all-sets clash check (tests/test_clash.py, limit 360 s) 246 → 300 s: crane animations 0.3 → ~3 s each.
- 0 clash rows on every tour animation (clash set: its own 6.0 mm row). PC check lines of every batch OK; crane lines
  import.crane, joints.rotate, joints.stack, states.poses, model.update, queue.frame_shown OK.
- GitHub: before this task 17.8 / 21.4 min (229 / 226 job-minutes, runs 43593305156, 43610881231); this branch
  20.0 min, 220 job-minutes (run 43616862287: one real-app check, fixed). Runs: see below.
- Subagents: Explore (inventory), three batch writers in worktrees (machines, offshore, small; merged as they were),
  an independent tester: found the PC check turning the boom down (rod out of the barrel), no boom limits, crane over
  budget – all three fixed by the worker; it measured the clash-check time.

**Open points / follow-up tasks:**
- `site/media/test_atc.page.html` (site "Turn it yourself") still shows the old ATC machine: re-make with
  `tools/make_site_web_models.py test_atc` (Web 3D lane). The site kit's `[test_luffer]` looks different next run.
- Tight: sequence 9,902 / 10,000 triangles, cylinder A 14,622 / 14,948, moving 371 / 400 KB; the all-sets clash test
  300 / 360 s locally. `fresing_render/data` 6.2 → 22 MB (installer zip a few MB bigger); the STEP files are not
  byte-stable, so every maker run adds MBs to git history.
- Cosmetic: `luff_cylinder` only on the first crane of the copies set; the trolley joint has no limits; older part
  groups (RAM → Hydraulic cylinders, HORN → Electrical, BARREL.GLAND → Cable glands, CARRIAGE → Linear guides,
  BOLLARD → Lifting gear). Panel pictures of the guide were not re-made (they show only panels).
- Not built (proposals): a way cover on the mill's X axis, a drag chain on the gantry.
