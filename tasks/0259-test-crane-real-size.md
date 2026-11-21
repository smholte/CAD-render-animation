# 0259 – The test crane at real size: a ×5 service crane (boom ~7.5 m, boom pin ~2 m up) everywhere – tour, lessons, PC check, guide and the automatic tests

**Who:** worker · **Status:** open – waits for 0234 (its `marine` and `vessel` sets use the test crane) and 0249 merged (same lane; 0250 after this task) · **Branch:**
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

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
