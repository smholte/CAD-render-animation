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

- [ ] `make_test_crane.py` makes the ×5 crane (A and B, Inventor names, plain); both copies of each STEP updated
- [ ] Every test, tour stop, lesson step and PC-check line green with it; numbers that changed listed with the reason
- [ ] Every tour set with the crane framed again, 0 clashes, `changed=` + the record
- [ ] Guide pictures of the crane made again; guide and stop texts with the new sizes
- [ ] Import triangles / times before–after in the report; tests' total time within about +15 %
- [ ] A line-up picture: the new crane beside a 1.75 m person and the IBC (test models only) in `tasks/img/0259/`
- [ ] Report filled in, merged, released

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

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
