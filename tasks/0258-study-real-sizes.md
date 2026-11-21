# 0258 – Study (findings only): is every test model, prop and person real size? A measured table, a proposed real size per model, and the model categories for the redo

**Who:** worker · **Status:** done (21 Nov 2026) · **Branch:** `task/0258-study-real-sizes`
**Started by:** lead, 21 Nov 2026 (owner 14:13, two screenshots of the test crane beside a person and an IBC on the
quay: "the demo crane used a lot of places should not be this small compared to other models. make sure that the scale
is realistic. and check the size of other objects as well." His pick 14:20: **study first, then one fix task per model
type**) · **Model:** Opus · effort Medium
**Area:** findings only – a report, a table and a few pictures in `tasks/0258-study-real-sizes.md` + `tasks/img/0258/`;
throw-away scripts stay on the branch. **No change to app code, test models, tests or the tour.** Commits `[skip ci]`;
at the end the `tasks/` files go to `main` (a tasks-only push starts no run).

## Why

The test models were made small to keep the tests fast (task 0011 on: the test crane's boom is 1.5 m, its boom pin
0.4 m high). Since 0155 the tour has life-size people (1.65 / 1.75 / 1.85 m) and real-size props (container, pallet,
IBC, gas rack, barrier, tool trolley), and since 0230–0235 the tour is the **users' learning environment** with real
surroundings (quay, deck, halls, sea). Next to those, a small model reads as a toy. The owner wants every model at a
realistic scale. The test crane is fixed at once in **0259** (owner's pick: ×5); this study measures everything else
and says what to fix.

## What to do

1. **List everything with a size** that a user sees in the tour, the lessons, the PC check pictures, the guide pictures
   and the public demo: every `tests/data/*.step` / `fresing_render/data/*` model a `@tour_set` or lesson uses, the
   mesh models (`make_test_mesh`), the Lifting cranes and loads, the props and people (`core/props_detail.py`,
   `core/surroundings.py`), the surroundings themselves (quay, deck, halls: door and ceiling heights, railings,
   bollards, workbench / stand props), the public demo's ship with its deck crane and the wind park.
2. **Measure** each: overall size (bounding box from the STEP with OCP – no Blender needed) and the 2–3 sizes that
   decide how big it reads (boom length and pin height, table / bed, arm length, drum Ø, door height …), and where it
   stands in its set (floor, deck, workbench).
3. **Say what it represents and its real size**: the kind of real machine or thing, and a typical real size range from
   public sources (standards, general handbooks, catalogue ranges – **no maker or model names in the report**). Note the
   source in one line per row.
4. **Verdict per row:** ok · too small · too big · "a desk-size test model on purpose" (only where the real thing is that
   small). Proposed real size (or factor) with one line why. Where a uniform factor would give silly parts (bolts,
   plate thickness, pins), say which parts should get real sizes instead.
5. **Cost of each fix:** how many test files, tour sets, PC-check lines, guide pictures and lessons read the model
   (grep, a count per model), and whether a bigger model changes the import's triangle count (the importer caps the
   facet gap in mm on big parts – `importer/step_reader.py` `FACETS`): measure one import at Normal before / after a
   plain ×k scale for the two biggest candidates (throw-away STEP files on the branch, not in `tests/data/`).
6. **Sort into categories for the redo** (the lead's to-do from the owner's 20 Nov 22:19 "redo all test-tour models,
   one task per model type"): e.g. cranes and lifting, hydraulics and mechanisms, winches / spools / sheaves, tracks,
   hoses and chains, vessels and sea, workshop machines (mills are already 0249 / 0250), studio objects (faces, decals),
   props and surroundings. Per category: which models, the proposed sizes, which tour sets it touches, a suggested order
   (most visible first), model · effort, and what must wait for what (0233–0235 own sets in `tour.py`; 0249 / 0250 the
   mills; 0259 the test crane).
7. **One line-up picture per category** (400–800 px, small Cycles or EEVEE render with Blender as a module): today's
   models standing beside a 1.75 m person and one real-size prop – test models only – plus the same line-up with the
   proposed sizes (a plain scale is fine for the picture). The owner judges by these.

## Done when

- [ ] Table: model / prop → represents → today's key sizes → real size (source) → verdict → proposed size → cost
      (tests, sets, lines, pictures) → category
- [ ] The two import measurements (triangles, time at Normal, web machine) before / after scaling
- [ ] Categories with order, waits, model · effort – ready for the lead to brief
- [ ] Line-up pictures in `tasks/img/0258/` (test models only)
- [ ] `tasks/` files on `main`; branch named in the report

## Not in this task

Any change to models, tests, the tour or the app. The test crane (0259 fixes it now). The mills (0249 / 0250). **Never
the cable-lay vessel's equipment** (private, CLAUDE.md section 6) and **never the Fresing 400** – no test model of its
size class either. The full demo (private).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (4-core web machine), 21 Nov 2026. Branch `task/0258-study-real-sizes` (throw-away
scripts in `study0258/`, the four scaled STEP copies in `study0258/scaled/`); only `tasks/` went to `main`.

**What changed:** nothing in the app, models, tests or tour. This report, the table below and 7 line-up pictures in
`tasks/img/0258/`.

### Result in short

- **Already real size (no work):** the Lifting loads and the 12 Lifting cranes, every prop and person, the surroundings
  (deck, quay, halls, railings, bench), the sample house, the public demo ship + crane and the wind park, and the three
  offshore test models (`test_sea`, `test_moving`, `test_thrusters`; 0234 keeps their sizes), the davit (`test_swivel`)
  and the tensioner + belt (`test_tracks`).
- **Too small (fix):** the test crane (0259, ×5), the cylinder arm and the hose arm (×3), the mesh crane (×2.5), the two
  gantry routers (×2.5 + a stand so the table is at 0.9 m), the way covers (×2), the A-frame of the winch model (×2.5)
  and the carousel of the spool model (×2), the decal model's "drums" (0235).
- **Small on purpose (the real thing is that small):** the bearing unit and the linear axis (`test_sequence*`), the
  four-bar and crank-slider, the clash rig, the painted-faces housing. The scissor table is the right length and height
  but 0.18 m wide – a real lift table is 0.8 m.
- **The rule for every fix:** scale the **layout** (places, lengths, travels), never the **parts that have a real size**:
  bolts, pins, hoses, wire ropes, chain links, drag-chain pitch, cutting tools, bearings, sheet thickness. Most of these
  are real already today (hoses Ø16–20, chain pitch 40, wire Ø20–24, drums and sheaves D/d 22–30, tools Ø4–10).
- **Import cost of a bigger model is small** – except for models with big round parts (sheaves, drums, swept ropes):
  +1–6 % triangles for the arm, router and crane, **+51 %** for the winch + A-frame at ×3 (table below).

### Where the models stand today

Every non-offshore set imports its model at the origin on the studio floor (PRODUCT look, no bench, no surroundings);
`sea_cable`, `moving_cable` use the sea; `vessel_work` the sea with its own hull; `weather` the quay; `flex_drawn` a
factory hall. So a desk-size model stands on the floor next to nothing – the pictures below put a 1.75 m person and a
real prop beside it.

### Table (sizes in m unless marked; boxes = overall length × width × height of the STEP, measured with OpenCascade)

Cost = pytest files naming the model / real-app scripts / tour sets (stops) / PC-check lines / mentions in the guide and
site picture makers / lesson. Sources are general standards and catalogue ranges, no makers.

| Model | Represents | Today: box · key sizes | Real size (source) | Verdict | Proposed | Cost | Cat. |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `test_crane_a` (+ `_b`, `_inv_*`, `_plain`) | service crane on a base | 1.60 × 0.60 × 0.56 · boom 1.55, boom pin 0.40, base 1.0 × 0.6 | service / loader cranes: boom 5–10 m (EN 12999 class, catalogue ranges) | too small | **0259** (×5, real bolts / pins) | 48 / 30 / 10 (38) / 41 (+4 `_b`) / 1 / crane | A |
| `test_cylinder_a` | luffing arm on a post, two cylinders + a telescopic one | 1.67 × 0.44 × 0.65 · arm 1.6, arm pin 0.60, bore ~76 mm, stroke ~0.2 | handling / loader arms 3–6 m; bores 80–160 mm in mobile hydraulics (ISO 6020/6022 series 25–320) | too small | layout ×3 (arm ~4.8, pin ~1.9); bore 100–125 / rod 56–70 real, not ×3 (230); pins Ø50–60; M16 → M24 anchor bolts | 3 / 2 / 1 (1) / 1 / 0 | A |
| `test_flex_hoses_a` | the same arm with hoses on the cylinder, a cable to a slide | 1.30 × 0.69 × 0.65 · arm 1.25, pin 0.60, hoses Ø16–20, fittings 25–35 mm | hoses DN8–DN12, OD 16–22 mm (EN 853 / 856) – real today | arm too small, hoses ok | layout ×3; hoses, fittings, gland keep their Ø (only longer) | 9 / 5 / 2 (7, with `flex_drawn`) / 3 / 5 | A |
| `test_mesh_crane.glb` | small crawler crane (mesh, no CAD faces) | 4.30 × 2.38 × 2.17 · boom 3.0, base 2 × 2, cab 0.8 high, rollers Ø0.5 | mini / small crawler cranes: boom 5–17 m; an operator's cab ≥ 1.5 m high (catalogue ranges) | too small (cab smaller than a person) | ×2.5 (boom 7.5 – the same class as 0259's crane, cab ~2.0) | 5 / 1 / 1 (1) / 1 / 0 | A |
| `test_linkage_a` | scissor lift table + four-bar + crank-slider | 4.0 × 0.23 × 0.96 · scissor platform 1.30 × 0.18, top 0.96; four-bar posts 0.27, crank 0.10; slider stroke ~0.25 | lift tables 1300 × 800 with ~1 m lift (EN 1570-1 sizes); machine mechanisms of this size are real | scissor: right length / height, **too narrow**; four-bar, crank: ok | scissor platform 1.30 × 0.80 (arm pairs ~0.6 apart); the others stay | 3 / 2 / 1 (1) / 1 / 0 | B |
| `test_clash` | two swinging arms on a plate (clash demo) | 1.50 × 0.90 × 0.12 · arms 0.73 / 0.53, pins Ø20 | swing arms / clamps of machines: this size | ok (on purpose small) – stand it on a 0.9 m bench (framing, 0233) | – | 5 / 3 / 1 (1) / 1 / 2 | B |
| `test_sequence` | bearing unit: housing, shaft Ø25, two 6205 bearings, cover, pulley | 0.40 × 0.40 × 0.18 | 6205 = 25 × 52 × 15 mm (ISO 15) – real | ok (on purpose) | detail: the ISO 4032 M24 nut on a Ø25 shaft → a shaft lock nut M25 × 1.5 | 5 / 1 / 2 (2) / 2 / 0 | B |
| `test_sequence_frame` | small linear axis in a portal | 0.40 × 0.40 × 0.19 · portal 0.38 × 0.17 | small linear modules: this size | ok (on purpose) | – | 4 / 1 / 1 (2) / 2 / 0 | B |
| `test_paths_a` | deck winch, A-frame with two sheaves, chute, wire Ø24 | 3.49 × 0.76 × 2.12 · drum Ø0.60, sheaves Ø0.53 / 0.39, A-frame top 2.1, base frame 3.15 | rope drums / sheaves D/d ≥ 18–25 (ISO 4308-1) – real today; overboarding A-frames 3–8 m clear height (catalogue ranges) | rope parts ok; **A-frame too small** (top at a person's height) | A-frame ×2.5 (top ~5), base frame / chute stand to fit; drum, sheaves, wire keep | 14 / 3 / 2 (7) / 2 / 3 | C |
| `test_spool` | level-wind winch + a small cable carousel (basket) | 5.40 × 2.40 × 1.17 · drum Ø0.60 × 0.64, wire Ø20; carousel Ø2.0, core Ø0.6, cable Ø40, coil Ø1.72 | winch: D/d 30 – real; power cable min. bend radius ~12–20 × D (cable handling practice) → core Ø ≥ 1.0–1.6 for Ø40; deck baskets 3–6 m | winch ok; **carousel too small** (its core is inside the cable's bend radius) | carousel ×2 (Ø~4, core Ø1.2–1.6), cable Ø40 kept (more turns); slew post / arm to fit; winch stays. A generic deck basket – nothing like the private demo's carousel | 15 / 3 / 2 (2) / 4 / 3 | C |
| `test_swivel` | davit with a swivelling sheave on a deck | 6.0 × 5.8 × 3.84 · reach 3.35, height 3.6, sheave Ø0.51 | boat / provision davits: 2–6 m reach | ok | – | 3 / 1 / 1 (1) / 1 / 0 | C |
| `test_tracks` | two-track cable tensioner + a timing-belt drive | 2.43 × 1.11 × 2.67 · track frame 1.7, cable Ø60, pads 0.09 × 0.12; pulleys Ø0.09–0.23, belt 48 mm | small linear cable engines: tracks 1.5–3 m, cable up to ~100 mm; timing belts 14M: 40–55 mm wide | ok (0229) | – | 7 / 1 / 1 (1) / 1 / 3 | C |
| `test_sea` | workboat stern with a chute, cable Ø120, bend restrictor | 13.6 × 6.2 × 5.6 · horn Ø2.1, bollards 0.9, M24 | workboat sterns, chutes R 1–4 m, bollards ~0.9 m (ISO 13795 sizes) | ok | – (0234 keeps sizes) | 13 / 3 / 1 (1) / 2 / 3 | D |
| `test_moving` | stern with a gantry, lowering block | 19.0 × 6.2 × 9.95 · gantry 4.7 high, sheave Ø1.08, block 1.4 | plausible for a 14 m stern section | ok | – (0234) | 15 / 1 / 1 (1) / 1 / 0 | D |
| `test_thrusters` | 36 m workboat with two azimuths and a bow thruster | 36 × 12 × 10.65 · props Ø1.8, nozzles Ø2.1 | 30–40 m workboats: beam 10–13 m, props 1.6–2.2 m | ok | – (0234) | 2 / 1 / 1 (1) / 1 / 2 | D |
| `test_gantry` | gantry router with a 3-tool carousel | 1.17 × 0.60 × 0.47 · bed 0.8 × 0.6 on the floor, beam 1.06, tools Ø4–6, carousel Ø0.17 | CNC routers: tables 1250 × 2500 / 1500 × 3000 (sheet sizes), working height 0.85–0.95, router tool changers 8–12 tools Ø0.4–0.6 | **too small** (desk / hobby size, on the floor) | layout ×2.5 (bed ~2.0 × 1.5) on a stand (table at ~0.9); tools, clamps, bolts keep; servos real (80–130 mm); carousel Ø0.4–0.5 with 8 pots. A router, far from the Fresing 400's size class | 9 / 7 / 2 (4) / 4 / 4 | E |
| `test_flex_chains_a` | the same router with three drag chains | 1.05 × 0.60 × 0.50 · chains pitch 40, bend R80, links 20 × 32 | drag chains: pitch 25–100, bend R 50–250 (catalogue ranges) – real today | router too small, chains ok | layout ×2.5 on a stand; chain links keep their size (~47 → ~110 links) | 7 / 3 / 2 (7, with `flex_drawn`) / 3 / 3 | E |
| `test_waycover_b`, `_c` | telescopic way covers on a slide | 1.14 × 0.30 × 0.19 · sections 0.27 × 0.11 | VMC X-axis covers ~2 × travel extended, 0.4–0.8 wide; 0249's VMC: X 1000 → ~2.2 | too small | ×2 (2.2 × 0.6), sheet 1.5–3 mm real; match 0249's X travel | b: 3 / 3 / 1 (1) / 1 / 0 · c: 2 / 0 / 1 (1) / 1 / 2 | E |
| `test_waycover_a` | the owner's real way-cover sub-assembly | 0.34 × 0.04 × 0.38 | real (Inventor) | ok | – (tests only) | 1 / 0 / 0 / 1 / 0 | – |
| `test_mill`, `_toolpath`, `_mill_cabinet` | small VMC | bed 0.7 × 0.5 | – | **0249** | 0249 (larger VMC) | mill 15 / 3 / 5 (7) / 11 / 0 / mill | F |
| `test_atc`, `test_4axis`, `test_5axis` | double-arm ATC, 4th / 5th axis on small mills | bed 0.5 × 0.4–0.5 | – | **0250** | 0250 (on 0249's VMC) | 4 / 3 / 1 · 3 / 1 / 1 · 2 / 1 / 1 | F |
| `test_faces_a` | product housing, cover, bracket, block | 0.86 × 0.60 × 0.10 · housing 0.30 × 0.20 × 0.10 | a small product on a studio table | ok (on purpose) | – (0235) | 3 / 2 / 1 (2) / 2 / 0 | G |
| `test_decals_a` | panel, two "barrels", a box for stickers | 1.10 × 0.30 × 0.30 · panel 0.40 × 0.30, barrels Ø0.12 × 0.30, box 0.10 | 200 l drum Ø0.585 × 0.88 (ISO 15750-3); a machine door panel ~1.2 × 0.8 | **too small** if they read as drums | drums real (Ø0.585 × 0.88, or 60 l Ø0.40 × 0.60), panel ~1.2 × 0.8, box a 0.6 × 0.4 × 0.4 carton – **add to 0235's brief** | 5 / 2 / 1 (1) / 2 / 0 | G |
| `test_loads` | pallet + IBC, pump skid, 20 ft container | 18.2 × 2.5 × 2.6 · skid 4 × 2, container 6.06 × 2.44 × 2.59 | ISO 668, EN 13698-1, UN 31HA1 IBC | ok (0231) | – | 2 / 1 / 2 (6) / 2 / 0 | H |
| Lifting cranes (12 classes) | AT-40…500, CC-100…1600, KB-20…200 | AT carriers 14–22 long; CC up to 122 high; KB-20 8.5 × 3.2 × 4.5 folded | invented at real size (0191) | ok | – | KB-20: 1 set (1) | H |
| Props and people | person 1.65 / 1.75 / 1.85, container, euro pallet, barrier, IBC, gas rack, tool trolley | person 1.75 (1.78 with helmet); container 6.06 × 2.44 × 2.59; pallet 1.2 × 0.8; IBC 1.2 × 1.0 × 1.16; trolley 0.68 × 0.46 × 0.96 | Dutch adults ~1.83 (men) / ~1.69 (women) (anthropometric tables); ISO 668; EN 13698-1 | ok | – | – | H |
| Surroundings | deck, quay, halls, bench | freeboard 3.0, quay 3.0 over water, railings 1.1, roller door ≤ 6 × 5.5, halls 7–11 high, bench top 0.9 | railings ≥ 1.1 (EN ISO 14122-3); work benches 0.85–0.95 | ok | – | – | H |
| `sample-house.hpscene` | made-up house (format sample) | plot 15 × 23, walls 2.8 high | ordinary storey heights 2.6–3.0 | ok | – | 1 set (2) | H |
| Public demo: ship + deck crane, wind park | invented vessel, IEA 15 MW reference turbine | ship 120 × 27, freeboard 3, crane boom 22; rotor 240 | the reference turbine's own sizes | ok | – | – | H |
| Not seen by users: `test_machine`, `test_materials`, tool STEPs | test-only models | machine 1.0 × 0.6 × 0.18 | – | leave | – | (tests, PC lines only) | – |

### Import at Normal before / after a plain scale (web machine, 4 cores, `step_reader` alone, 3 runs each)

| Model | Triangles (unique meshes) | Import time |
| --- | --- | --- |
| `test_cylinder_a` → ×3 | 14,622 → 14,840 (+1.5 %) | 1.8–2.0 s → 1.73–1.75 s |
| `test_gantry` → ×2.5 | 7,580 → 7,640 (+0.8 %) | 1.6–1.76 s → 1.77–1.89 s |
| extra: `test_crane_a` → ×5 | 9,448 → 10,032 (+6 %) | 1.58–1.60 s → 1.43–1.47 s |
| extra: `test_paths_a` → ×3 | 25,516 → 38,520 (**+51 %**) | 1.38–1.53 s → 1.44–1.55 s |

The time is reading the file (~1.4 s); meshing is ~0.1 s. Triangles grow only where big round parts reach the 0.5 mm
facet cap (`FACETS["normal"]`): sheaves, drums and the swept wire rope of `test_paths_a`. Standard parts stay light while
they are under 200 mm. A real-size model with real-size bolts (not ×k bolts) stays near today's count; the cable models
(winch, spool) should check their triangles after the fix. The scaled copies were made by changing the file's length
unit (`study0258/scale_step.py`), geometry untouched.

### Categories for the redo (order: most visible first)

| # | Category | Models · proposed | Tour sets touched | Waits for | Model · effort |
| --- | --- | --- | --- | --- | --- |
| A | Cranes and hydraulic arms | `test_cylinder_a` ×3, `test_flex_hoses_a` ×3 (hoses real), `test_mesh_crane` ×2.5 (the test crane itself is 0259) | `cylinder`, `hoses`, `flex_drawn` (hoses part), `mesh` | 0259 (its real-size pins, bolts and cylinder parts are the pattern), 0233 (frames these sets) | Opus · Medium |
| B | Routers, drag chains, way covers | `test_gantry` ×2.5 on a stand, `test_flex_chains_a` ×2.5 (chains real), `test_waycover_b/_c` ×2 | `gantry`, `atc`, `chains`, `flex_drawn` (chain part), `waycover`, `waycover2` | 0233; 0249 (way covers match its X travel); after A (`flex_drawn`) | Opus · Medium (G-code programs, work zero, tool carousel) |
| C | Winches, sheaves, spools | `test_paths_a` A-frame ×2.5 (rope parts kept), `test_spool` carousel ×2 (winch kept) | `cables`, `flex_drawn` (cable part), `spool`, `served` | 0233; after B (`flex_drawn`) | Opus · High (cable and spool solvers, expected lengths and turns in 30 tests, +51 % triangles) |
| D | Mechanisms (small) | scissor platform 0.18 → 0.80 wide; the bearing unit's shaft nut | `linkage`, `sequence`, `productvideo` | 0233 | Sonnet · Medium (or fold into A) |
| G | Studio objects | decals' drums / panel / box at real size | `decals` | add to **0235** (open, not started) | as 0235 |
| – | No size work | offshore (0234), mills (0249 / 0250), lifting, props, surroundings, house, demo, tracks, davit, clash rig, faces, sequence frame | – | – | – |

`flex_drawn` holds the hoses, the drag chains and the cable at once: A, B and C each change one of its models, so they run
one after another (one lane). D and G can run beside them. Every fix task: same part names, joints and revisions; both
`.step` copies; `changed=` on its sets + `tour_versions.py --record`; 0 clashes; the PC-check lines and guide pictures of
its models; and it re-frames its sets (0233 frames them loosely first).

### Line-up pictures (`tasks/img/0258/`, Cycles, front view, orthographic, same scale in both rows; a plain scale)

1. `1_cranes_arms.jpg` – test crane, cylinder arm, hose arm, mesh crane (today / ×5, ×3, ×3, ×2.5), person + IBC.
2. `2_mechanisms.jpg` – scissor + four-bar + crank, clash rig, bearing unit, linear axis (today = proposed), tool trolley.
3. `3_winches_spools.jpg` – winch + A-frame, winch + carousel, tensioner + belt, davit (×2.5, ×2, ×1, ×1), IBC. (The
   picture scales the whole model; the proposal keeps the drum, sheaves and wire, and the spool's winch.)
4. `4_vessels_sea.jpg` – stern with chute, stern with gantry, workboat (today = proposed), container.
5. `5_routers_covers.jpg` – gantry router, router + drag chains, way covers (×2.5, ×2.5, ×2, ×2), euro pallet. (The
   proposal also puts the routers on a stand: the picture does not.)
6. `6_studio.jpg` – painted faces (×1), panel + drums + box (×3), tool trolley.
7. `7_lifting.jpg` – the loads (today = proposed).

**Tested and measured:** sizes of 37 STEP files (every part's placed box, OpenCascade, `study0258/measure.py`), the glTF
and OBJ mesh models and the sample house (bpy), the props (`core.surroundings.prop_size`). Counts by grep over `tests/`,
`tools/`, `fresing_render/pccheck/` (lines per model constant) and `tour.py` (stops per set). Imports and pictures on
the 4-core web machine. No GitHub run (findings only, `[skip ci]`).

**Open points / follow-up tasks:**
- Lead: brief A, B, C (one lane, `flex_drawn` shared), D; add the decal sizes (G) to 0235's brief; tell 0233 which sets
  stay "too small" until A–D (cylinder, hoses, mesh, gantry, atc, chains, waycover, waycover2, cables, spool, served,
  linkage, flex_drawn).
- Real-app scripts that hard-code clicks or sizes on these models (`tools/ui_test_*.py`: gantry 7, hoses 5, crane 30)
  are the slowest part of each fix – the briefs should say so.
- The test-only variants (`test_crane_b`, `_inv_*`, `_plain`, `test_flex_hoses_b`, `test_paths_b`, `test_cylinder_b`,
  `test_linkage_b`, `test_waycover_d`) follow their `_a` model in the same task.
- Branch `task/0258-study-real-sizes` can be deleted after reading (scripts and scaled copies only).
