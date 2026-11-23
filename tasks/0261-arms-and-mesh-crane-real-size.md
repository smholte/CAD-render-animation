# 0261 – Real size, category A: the cylinder arm and the hose arm ×3, the mesh crane ×2.5

**Who:** worker · **Status:** done (23 Nov 2026, 0.2.211) · **Branch:**
`task/0261-arms-mesh-crane-real-size`
**Started by:** lead, 21 Nov 2026 (owner 14:20: every model at a realistic scale – "study first, then one fix task per
type"; study **0258** category A) · **Model:** Opus · effort Medium
**Area:** Test models lane – `tools/make_test_cylinder.py`, `tools/make_test_flex.py` (the **hoses** model only),
`tools/make_test_mesh.py` (the mesh crane), their `tests/data/` files + `fresing_render/data/` copies, the maker tests;
every place that holds these models' numbers: `blender/tour.py` – the sets `cylinder`, `hoses`, `mesh` and the hose
part of `flex_drawn` (**numbers, cameras and framing only**, not the surroundings 0233 gave them), `pccheck/checks.py`
(their lines), the tests and tools that read them (`grep -rln "test_cylinder\|test_flex_hoses\|test_mesh_crane" tests
tools fresing_render`), `tools/ui_test_*.py` scripts that click on them, `tools/guide_screens.py` + the guide pictures
and texts that show them, `tools/tour_versions.py`'s record.
**Not:** app code (a fault found → report it), the drag chains and cable of `flex_drawn` (0262, 0263), the test crane
(0259), surroundings.

## Why

Study 0258 (`tasks/0258-study-real-sizes.md`, table + `tasks/img/0258/1_cranes_arms.jpg`): next to a 1.75 m person the
arms and the mesh crane are toys – the mesh crane's cab is smaller than a person.

## The sizes (0258's proposal – lead's decision, the owner can change it later)

- **`test_cylinder_a`** (+ `_b`): layout ×3 – arm ~4.8 m, arm pin ~1.9 m; cylinders a real bore / rod for the load
  (0258: bore 100–125, rod 56–70, ISO 6020/6022 series), stroke ×3.
- **`test_flex_hoses_a`** (+ `_b`): the same arm ×3; **hoses, fittings and the gland keep their real Ø** (Ø16–20,
  fittings 25–35 mm) and only get longer; the cable to the slide likewise.
- **`test_mesh_crane.glb`**: ×2.5 (boom ~7.5 m – the same class as 0259's crane; cab ≥ 1.5 m high).
- **The rule (0258):** scale the **layout** (places, lengths, travels), never the parts that have a real size – bolts,
  pins, hoses, fittings, sheet thickness. Real-size bolts and pins with names that follow the size, in the same
  supplier notation as 0259 (`ISO 4017 M… x … - 8.8 HDG`, `ISO 4762 M… x … - 12.9`).
- **Keep the structure:** same part and assembly names, tree, colours, joints, revisions (B keeps its differences);
  `--inventor-names` / `--plain` variants follow their `_a` model. Old saved-project fixtures stay as they are.

## Watch

- **Real-app scripts are the slow part** (0258: hoses 5, crane-like clicks): every hard-coded click, hover spot or size
  in `tools/ui_test_*.py` must still land on the same faces.
- **Numbers in tests:** most become "old × 3" (or × 2.5); every number that changed for another reason gets one line in
  the report. Hose lengths, MBR warnings and clip spacing are real-size rules – check they still hold.
- **Import weight:** measure triangles and import time at Draft / Normal before / after (0258 expects +1–6 %); the
  tests' total time within about +15 %.
- Every tour animation 0 clashes, every stop's check, cameras framed again on the new size; `changed=` on every touched
  set + `python3 tools/tour_versions.py --record` after merging `main` once.
- `flex_drawn` holds the hoses, chains and cable at once: this task changes only its hose part; 0262 and 0263 follow
  in the same lane.
- Search the repository afterwards for the old sizes in texts (guide, stop texts, tooltips).

## Done when

- [x] The three makers make the new sizes (all variants); both copies of each file updated; maker tests green
- [x] Every test, tour stop, real-app script and PC-check line green; changed numbers listed with the reason
- [x] Sets `cylinder`, `hoses`, `mesh`, `flex_drawn` framed again, 0 clashes, `changed=` + the record
- [x] Guide pictures of these models made again; texts with the new sizes
- [x] Triangles / import times before–after in the report; tests' total time within about +15 %
- [x] A line-up picture (new models beside a 1.75 m person and the IBC, test models only) in `tasks/img/0261/`
- [x] Report filled in, merged, released

## Not in this task

Drag chains, cable, routers, way covers, winches, spools (0262, 0263); mechanisms (0264); the test crane (0259);
surroundings; app code. **Never the cable-lay vessel's equipment, never the Fresing 400.**

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (4-core web machine), 23 Nov 2026 · released as 0.2.211 · branch
`task/0261-arms-mesh-crane-real-size`. No subagents (independent tester skipped: test models, no app code).

**What changed:**
- `tools/make_test_cylinder.py` (`test_cylinder_a/_b`): the layout x 3 (``K``): pivot (300, *, 1800), barrel pins
  (1500, *, 450), rod pins (2400, *, 1350), cylinders at y 240 / 960, the telescopic one at 600; the structure (base,
  post, brackets, arm) is built at the first numbers, scaled x 3 with OpenCascade, then given real-size bores. Real
  parts: pins Ø60 (bores Ø60.4), cylinders bore Ø125 / barrel Ø150 / rod Ø70 / piston Ø123, eyes Ø100 x 90, the
  telescopic rod Ø80, anchor bolts `ISO 4017 M24 x 120 - 8.8 HDG` (holes Ø26; was `M16 x 100 - 8.8`), ports, screws and
  pipe at real size. Stroke x 3: pin to pin 1272.79, closed 1092.79, full stroke 570. Same 27 parts, names, tree,
  colours; B as before. **No part lies inside another any more** (the old one had 3 overlaps: the base pin in the
  telescopic barrel 1,587 mm³, each rod 2,849 mm³ in its rod eye).
- `tools/make_test_flex.py` (hoses model only, `test_flex_hoses_a/_b`): the layout x 3, the same way; pins Ø60, the
  cylinder as above (pin to pin 1986.35, ±521 mm, arm -21.6° … +21.4°), the slide's travel ±450. **Hoses, fittings,
  glands and the cable keep their Ø** (16 / 20 / 10 mm, fittings 24 / 30 across flats) and only get longer: ARM 3000.81
  (B 3150.56, 5.0 % longer as before), CYL A 1413.55, CYL B 1756.04, cable 3286.14 mm. The maker's own checks hold
  (bends ≥ 3.5 D, ≥ 3 mm to other parts, spare > 7 %, bodies apart over the motion). The docstring has the new numbers.
- `tools/make_test_mesh.py` (`test_mesh_crane.glb` + `_b`): x 2.5 (``S``): base 5 x 5 x 1 m, ring Ø4.0 / Ø3.0,
  boom 7.5 m, cab 2.0 x 2.25 x 1.975 m (was 0.79 high), wheels Ø1.25; the boom pin a real r 0.05 (x 2.5 would be
  Ø300); B: the cab 2.5 cm higher, hook block x 2.5. `test_mesh_single.glb` / the OBJ unchanged.
- Both copies of every file (`tests/data/`, `fresing_render/data/`); `test_mesh_crane.glb` is byte-stable.
- Tour: `cylinder` (pins, pivot, "Stroke 0 → 450 mm", stop text 450 mm), `hoses` (slide 360 mm out, 660 back),
  `flex_drawn` (the gantry moved to y -1.5, the cable model to y 1.9 – they overlapped the bigger base; the drawn hose's
  four clicks; the kind row past the rail's end at x 1.80 / 2.20, y 1.08 / 1.17 / 1.26), `mesh` (the ring click, Ø4000).
  `changed="0.2.211"` on the 4 sets and the stops cylinder, hoses, drawn_hose, flex_kinds, mesh_import; record made.
  Cameras are fitted by the app on the model, so the framing followed by itself (checked on the stops' pictures of the
  line-up / guide renders, not one by one).
- `blender/flex.py` `set_up_test_hoses`: the pivot and the two pins (test set-up numbers, not app logic).
- PC check: `joints.cylinder` (stroke 300 mm), `motion.flex` (slide 0.3), `motion.flex_kinds` (camera), `import.mesh`
  (Ø4000).
- Real-app scripts: `ui_test_cylinder.py` (pins, view, strokes x 3), `ui_test_flex.py` (pivot, hose end, a close view on
  the arm's hose – a Ø20 hose seen from 3 x further was too thin to click), `ui_test_drawn.py` (fitting points; a close
  view on each fitting before it is clicked, the view change in its own step).
- Guide pictures made again: `view_flex_before_after.jpg`, `view_drawn_hose.jpg`, `view_flex_kinds.jpg` (camera a
  little higher: the 300 mm base filled the lower half), `panel_4_flex.png` (hose length 3003 mm). Guide texts had no
  sizes of these models.
- Line-up picture `tasks/img/0261/lineup.jpg` (both arms, the mesh crane, a 1.75 m person, the IBC; Cycles, processor).

Numbers in tests – "old x 3" (arms) or "x 2.5" (crane) unless listed: `test_cylinders.py`, `test_model_update.py`,
`test_flex.py` (lengths new, slides x 3), `test_flex_fit.py` (the maker's numbers), `test_flex_drawn*.py` (click spots
moved onto the bigger parts – not x 3 where a spot had to stay clear of a hose: base clips at (1.8, -0.36) and
(2.55, -0.36), 114 mm from the CAD arm hose), `test_flex_panel.py`, `test_mesh_import.py`, `test_mesh_reader.py`.
Changed for another reason:
- `test_motion_fixes.py::test_hoses_moved_as_one_body_are_not_solved_again`: a hose carried along rigidly may differ from
  a fresh solve by **2 mm per metre of hose** (was 2 mm flat): the 3.3 m cable differed by 3.9 mm. The error of a shape
  carried along grows with its length; nothing else in the test changed.
- The arm hose's hump was drawn lower (z 1380 instead of 1500 = 500 x 3): the real-size Ø20 hose 3 m long sags more than
  the drawn route under its own weight and `test_the_guide_is_the_cad_centreline_…` (≤ 12 % of the length) failed by
  0.4 %; revision B's hump lowered to keep it 5.0 % longer.
- The cable's sag point 50 mm lower (z 940): with the slide's travel x 3 it had 6.7 % spare, the maker wants > 7 %.

**Tested and measured** (web machine, 4 cores):
- Import (`step_reader` alone, 2 runs each), before → after: cylinder arm Draft 9,386 → 9,140 triangles, Normal 14,622 →
  14,294 (−2 %); hose arm Draft 10,292 → 11,630 (+13 %), Normal 23,022 → 29,340 (+27 %: the hoses are 3 x longer at
  the same facets per mm). Time 1.2–1.7 s before and after (reading the file). The mesh crane: same triangle count.
- Locally green: `test_cylinders.py` (28), the two cylinder tests of `test_model_update.py`, `test_flex.py` (32),
  `test_flex_fit.py` (114), `test_flex_drawn.py` + `_independent` (47), `test_flex_panel`, `test_motion_fixes`,
  `test_flex_kinds`, `test_web3d_moving` (54), the 8 mesh test files (287), `test_tour.py` (109: every stop's Go and
  check; the build 240 s limit held), `test_tour_clash.py` for `cylinder`, `hoses`, `mesh`, `flex_drawn` (0 clashes).
  Real app: cylinder 22/22, flex 31/31, drawn 25/25. PC check lines joints.cylinder, motion.flex, motion.drawn,
  motion.flex_kinds, import.mesh: 5/5 OK in 18 s.
- GitHub: 2 full runs. Run 45189832091 red on one PC-check line I had missed (`import.mesh_fbx` still wanted the old
  Ø1.6 m ring, Linux and Windows); run 45195301091 green; `main` fast-forwarded, reuse run 45200874984 published 0.2.211,
  the Windows update-from-release check and "Offer the release" green.
- Test time: GitHub's runners were slow all day (task 0272's run this morning: suites 13–25 min against "usually"
  10–14). Per test file against 0272's run: the files that read these models 1,307 → 1,400 s (+7 %), every other file
  +32 % – the models did not make the tests slower beyond the brief's +15 %. On the web machine `test_tour.py`'s build
  stayed under its 240 s.

**Open points / follow-up tasks:**
- `flex_drawn` still holds the small gantry and cable model (0262, 0263 scale them; their places `DRAWN_CHAINS_AT`,
  `DRAWN_PATHS_AT` will need moving again).
- The hose arm's slide carriage and valve block are scaled x 3 too (a 540 x 240 x 300 manifold): plausible for a 4.5 m
  arm, but a "more detail" redo could make them real catalogue sizes.
- The PC check's picture `flex_kinds` keeps its own camera (moved to the new row); not looked at here.
