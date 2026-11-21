# 0259 – The test crane at real size: a ×5 service crane (boom ~7.5 m, boom pin ~2 m up) everywhere – tour, lessons, PC check, guide and the automatic tests

**Who:** worker · **Status:** open – can start (0233, 0234 and 0249 merged; 0250 after this task) · **Branch:**
`task/0259-test-crane-real-size`
**Started by:** lead, 21 Nov 2026 (owner 14:13, two screenshots: the test crane beside a 1.75 m person and an IBC on the
quay looks like a toy – "should not be this small compared to other models. make sure that the scale is realistic."
His picks 14:20: **service crane ×5**, **one crane at real size everywhere – the tests too**) · **Model:** Opus · effort High
**Area:** Test models lane – `tools/make_test_crane.py`, `tests/data/test_crane_*.step` + their `fresing_render/data/`
copies; every place that holds the crane's numbers: `blender/tour.py` (the crane hub set and its stops, and the sets
`looks`, `marine`, `cutaway`, `copies`, `update`, `vessel`, `props`, `people`, `weather` – **numbers, cameras and framing
only**, not their surroundings), `blender/lessons/crane.py`, `pccheck/checks.py` (the crane lines), the tests and tools
that read the crane (lead's count: ~54 test files, ~20 tools – `grep -rln "test_crane" tests tools`), `tools/guide_screens.py`
+ the guide pictures and texts that show the crane, `tools/tour_versions.py`'s record.
**Not:** app code (a fault found → report it), the surroundings / environment of a set (0233 / 0234 own those), the
mills (0249 / 0250), the Lifting cranes (already real size), other small test models (study **0258** first).

## Why

`TEST.CRANE` was made small for fast tests (0011): base plate 1000 × 600, boom 1.5 m, boom pin 0.4 m high, luffing
cylinder bore 52 mm. Since 0155 the tour has life-size people and real-size props, and since 0230–0235 the tour is the
users' learning environment: next to them the crane reads as a toy. It is the most-used model (crane hub, 10 sets, the
crane lesson, the PC check, most guide pictures).

## The size (owner's pick: service crane ×5)

- **Layout ×5:** every place, length and travel of the crane's plan times 5 – base about 5.0 × 3.0 m, boom about 7.5 m
  from the pin, trolley travel and cylinder stroke ×5, the boom's luffing range in degrees unchanged.
- **Head room:** in the CAD pose the boom's underside at least **2.1 m** above the ground, so a 1.85 m person walks under
  it (pure ×5 puts the pin at 2.0 m and the underside near 1.75 m): make the pedestal taller as needed and say the final
  pin height in the report.
- **Real parts, not scaled ones:** plate and wall thicknesses, pins, bolts and screws get real sizes for a crane of this
  size (e.g. anchor bolts and foot screws of a real size – a scaled M12 would be an M60); their **names follow the real
  size** in the same supplier notation (`ISO 4017 M… x … - 8.8 HDG`, `ISO 4762 M… x … - 12.9`) so the part library sorts
  them as today. The cylinder: a real bore / rod for the size.
- **Keep the structure:** the same part and assembly names (`BOOM.ASM`, `BOOM.PIN`, `TROLLEY.ASM`, `HYDRAULIC
  CYLINDER.ASM` …), the same tree, colours, part count and joints; **revision B** the same differences (one bolt gone,
  bolts reordered, `BOOM.LAMP` added, the cover moved – now 50 mm); `--inventor-names` and `--plain` still work.
- **Old saved projects stay old:** fixtures that test opening an older project (`test_crane_inv_*.step`, old-app
  folders in `tests/data/`) are history – leave them as they are; say which you left.
- Detail: as today (the cranes' "more detail" is a later redo task); only what the bigger size needs to look right
  (e.g. a ladder or a rest on the pedestal is welcome if cheap, not required).

## Watch

- **Import weight:** big parts mesh with a gap capped in mm (`importer/step_reader.py` `FACETS`), so a 5× crane gets
  more triangles. Measure triangles and the import time at Draft / Normal before and after (web machine) and the PC
  check's `import.crane` line; keep the tests' total time within about +15 % – if the facets blow it up, say so and
  propose before tuning anything in the importer (that is app code).
- **Numbers in tests:** most should be "old × 5"; every number that changed for another reason gets one line in the
  report. Clicks in real-app tests (a spot 30 mm in from a corner, a face to hover) must still land on the same faces.
- **Every tour animation 0 clashes** (`tests/test_tour_clash.py`), every stop's check, the crane lesson's View / Show me /
  Build it yourself the same project (`tests/test_lessons.py`); cameras of every set that shows the crane framed again
  (the whole crane, or the detail the stop's text names); `changed=` on every touched set +
  `python3 tools/tour_versions.py --record` after merging `main` once.
- **Others in the same files:** 0249 (mills) in `pccheck/checks.py`, `guide_screens.py`; **0233 merged first** (its worker ran
  on the old brief, 21 Nov): it put the sets in halls, a studio, a quay and a warehouse with the 1 m crane – check every
  crane set there again at the new size (camera, the crane fits the hall / quay, people walk under the boom; 0233's
  open points: `people` shows the crane as "the small thing at the left", `night` has no floodlit spot); 0235 and
  0258 run beside it (no shared files). Merge `main` once, right before the version.
- Lifting lane: the Lifting tests and `ui_test_lifting*.py` use the test crane – their loads, radii and charts must still
  make sense at the new size (no load heavier than the crane could lift; say what you changed).
- Search the repository afterwards for the old sizes in texts (guide, stop texts, tooltips that quote "1.5 m boom" …).

## Done when

- [x] `make_test_crane.py` makes the ×5 crane (A and B, Inventor names, plain); both copies of each STEP updated
- [x] Every test, tour stop, lesson step and PC-check line green with it; numbers that changed listed with the reason
- [x] Every tour set with the crane framed again, 0 clashes, `changed=` + the record
- [x] Guide pictures of the crane made again; guide and stop texts with the new sizes
- [x] Import triangles / times before–after in the report; tests' total time within about +15 %
- [x] A line-up picture: the new crane beside a 1.75 m person and the IBC (test models only) in `tasks/img/0259/`
- [x] Report filled in, merged, released

## Not in this task

Surroundings and environments of the sets (0233 / 0234); other test models (after study 0258); the mills (0249 / 0250);
app code. **Never the cable-lay vessel's equipment, never the Fresing 400.**

## Design (worker, 21 Nov 2026)

The crane's numbers, old → new (m unless said; `tools/make_test_crane.py` holds them):

| What | Old | New |
| --- | --- | --- |
| Layout x, y | – | × 5 |
| Layout z | – | × 5 for the base, its bolts, the cover and the pedestal's foot; × 5 **+ 0.4** for everything from the pedestal's block up (boom, trolley, cylinder, pins, lamp) – the pedestal is 400 mm taller for head room |
| Boom pin (pivot) | (0.1, 0.3, 0.4) | (0.5, 1.5, 2.4) |
| Boom | 1.5 long, 0.1 × 0.1 | 7.5 long, 0.5 × 0.5; underside 2.15 m up in the CAD pose |
| Boom tip | (1.6, 0.3, 0.4) | (8.0, 1.5, 2.4) |
| Trolley (TROLLEY.ASM origin) | pivot + (0.6, −0.075, 0.05) | pivot + (3.0, −0.375, 0.25) = (3.5, 1.125, 2.65) |
| Trolley run in the tour | 0.35 | 1.75 (`tour.TROLLEY_RUN`) |
| Base | 1.0 × 0.6 × 0.1 | 5.0 × 3.0 × 0.5 |
| Cover | 0.3 × 0.2 × 0.010 at (0.6, 0.05, 0.1); rev. B +0.01 | 1.5 × 1.0 × **0.012** at (3.0, 0.25, 0.5); rev. B +0.05 |
| Anchor bolts | `ISO 4017 M12 x 40 - 8.8 HDG`, holes Ø13 | `ISO 4017 M30 x 120 - 8.8 HDG`, holes Ø33, at (0.25 / 4.75, 0.25 / 2.75, 0.5) |
| Foot screws | `ISO 4762 M10 x 20 - 12.9`, flange 20 mm | `ISO 4762 M24 x 60 - 12.9`, flange 60 mm |
| Boom pin / bores / boom's round end | Ø40, 0.18 long / Ø40.4 / Ø100 | Ø100, 0.9 long / Ø100.4 / Ø500 |
| Luffing pins | Ø20, 0.044 long (half 0.022) | Ø70, 0.22 long (half 0.11, `tour.LUFF_PIN_HALF`) |
| Luffing cylinder | bore Ø52, piston Ø50, rod Ø22, 6 in / 140 out | bore Ø200, piston Ø198, rod Ø110, 30 in / 700 out (the same −1.5° … 37.6°) |
| Rod eye centre (CAD pose) | (0.52, 0.3, 0.325) | (2.6, 1.5, 2.025) (`tour.LUFF_ROD_EYE`) |
| Barrel pin | (0.19, 0.3, 0.195) | (0.95, 1.5, 1.375) |
| Trolley wheels | Ø60 | Ø300 |
| Rev. B lamp (boom space) | (1.45, 0, 0.08) | (7.25, 0, 0.4) |
| Cut (tour `cutaway`) | starts 0.2 in front | 1.0 (`tour.CUT_FROM`) |

No part lies inside another any more (the first crane's barrel end cap and rod end reached into the forks' plates).
Same names, tree, colours, part count (13 unique, 20 placed) and joints. `tour.CRANE_PIVOT`, `CRANE_PIN_R`,
`CRANE_BOOM` hold the numbers the tour and the PC check use.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 21 Nov 2026 · released as 0.2.203

**What changed:**
- `tools/make_test_crane.py`: the crane x 5 (design table above). Final pin height **2.4 m** (pedestal 400 mm taller than
  pure x 5), boom underside **2.15 m** in the CAD pose. Real parts: anchor bolts `ISO 4017 M30 x 120 - 8.8 HDG` (holes
  Ø33), foot screws `ISO 4762 M24 x 60 - 12.9` (flange 60 mm), boom pin Ø100 (bores Ø100.4), cylinder pins Ø70,
  cylinder bore Ø200 / rod Ø110 / piston Ø198 (same stroke share, same −1.5° … 37.6°), cheeks 80 mm, gussets 25 mm,
  cover 12 mm (rev. B lifts it 50 mm). Same 13 unique / 20 placed parts, names, tree, colours; A, B, `--inventor-names`,
  `--plain` all write. **No part lies inside another any more**: the first crane's barrel end cap and rod end reached
  into the forks' plates (4,049 and 885 mm³; seen with an OpenCascade common of every pair) – the neck is thinner than
  the fork's gap, the end cap starts beyond the plates, the rod end is gone. `model_details.METRIC` got M30.
- `tests/data/` + `fresing_render/data/` `test_crane_a.step`, `test_crane_b.step` (byte copies).
  **Left as they were (old projects):** `test_crane_inv_a.step`, `test_crane_inv_c.step`, `test_crane_plain.step`.
- Tour: `CRANE_PIVOT`, `CRANE_PIN_R`, `CRANE_BOOM`, `TROLLEY_RUN` (0.35 → 1.75 m), `LUFF_ROD_EYE`, `LUFF_PIN_HALF`,
  `CUT_FROM` (0.2 → 1.0 m), the cutaway camera, the second copy 4.5 m over (1.5 m between the bases), the trail 40 mm
  thick, the people stop's and web 3D stop's texts; `changed="0.2.203"` on the 10 crane sets, the people and web3d
  stops; record made. Crane lesson: the trolley's Show me wiggle 1.75 m. PC check: `_tip`, joints.rotate / stack,
  looks.cutaway camera, model.update_safe pivot.
- Tests (numbers "old x 5", z "x 5 + 0.4" from the pedestal up; lines changed for another reason):
  test_phase2, test_hover (Ø100 / Ø100.4 texts, ray spots), test_couplings (wheel tread Ø250: ratio 360/(π·250),
  0.8 rad per 100 mm instead of 4 rad; bolt name), test_stacked_joints, test_model_update, test_joint_batch,
  test_web3d_faces_blender (diameters 33 / 70 / 100 / 100.4 / 110 / 198; the boom's round end Ø500).
  Real-app tests: ui_test_app (pin spot, view centre, boom-up height 4.9 m), ui_test_app2 (trolley top 150 mm in,
  **small-part size 45 → 150 mm**: the crane's smallest parts are now the M24 screws), ui_test_studio (sharp spot within
  1 m of the click, was 0.2 m), ui_test_surroundings, ui_test_vessel, paths_test_blender, ui_screens, guide_screens
  (hover spot, decals 0.3 / 0.3 / 0.2 m wide, type plate "8500 kg").
- Guide: pictures render_crane, looks, decals, cutaway, people_meet, app_after_import, view_joints, view_hover made
  again; "Hole Ø100.4 mm", "Round face Ø 100.0 mm".
- Line-up picture `tasks/img/0259/crane_lineup.jpg` (the crane, a 1.75 m person, the IBC; Cycles, processor).

**Tested and measured** (web machine, 4 cores):
- Import of test_crane_a.step, before → after: Draft 6,098 → 5,890 triangles, Normal 9,448 → 9,374; 0.45–0.56 s each
  (no change). The facets cap did not blow up: the new parts are mostly flat.
- Locally: the 87 test files that read the crane, test_tour.py, test_lessons.py, test_tour_clash.py for the 10 crane
  sets (0 clashes) – green after the fixes; every crane stop's Go + check (37 stops) with a small picture each.
  `test_web3d_env_blender.py::test_page_opens_in_a_browser` fails on the web machine with the old crane too (the
  page's auto-quality step-down under load) – green on GitHub.
- Lifting example (AT-40, the boom as the 1.2 t load): radius 6.79 → 9.93 m, crane use 9 % → 16 %; still within
  limits, nothing changed in the Lifting tests.
- GitHub: every pytest group green on run 44949567994; that run's PC check job stopped at line 105/108 at its 15-minute
  box on a slow runner (every line 1.5x its time on main's run 44930151601, also lines without the crane: House
  29 → 44 s, milling 12 → 20 s); two real-app checks fixed afterwards (small parts, sharp spot).
- Runs: 5 for code (two cancelled by my own pushes, one diagnostic with the old numbers), the release run below.

**Open points / follow-up tasks:**
- The test crane's detail is as before (the cranes' "more detail" redo is later).
- The people stop no longer shows the crane at all (the camera frames people + container); the stop says so.
- `view_joints.png` is close on the crane: the boom tip leaves the picture at the top right (as before, in proportion).
- The PC check (Full, first part) on Linux is near its 15-minute box on a slow runner – not from this task, but worth
  splitting a line to the other half if it happens again.
