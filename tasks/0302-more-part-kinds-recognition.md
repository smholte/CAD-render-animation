# 0302 – More part kinds and better recognition: common machine parts from public catalogues, shape hints, "not recognised" made easy to teach

**Who:** worker · **Status:** done (0.2.222) · **Branch:** `task/0302-more-part-kinds`
**Started by:** lead, 23 Nov 2026 (owner's list, 23 Nov 19:39: "More parts, recognitions and materials.") · **Model:**
Opus · effort Medium
**Area:** Part library lane – `core/part_types_data.py`, `core/part_types.py`, `core/fasteners.py`, their tests; the
"not recognised" list only if the app lacks one (3 Looks, along the existing rule sets); guide, CHANGELOG.
**Not:** new looks / finishes (0270 → 0274 and the material picker 0273 do materials), painted steel from Inventor (0287).

## Background

Part names are matched as whole words in English, Dutch and German at once (CLAUDE.md 8: check every new keyword in all
three languages and against `tests/test_part_types.py`'s lists; "LINKS", "PALLET" went wrong before). The owner's own
part names are never committed – he may paste a few unrecognised names in this session to test with.

## What to do

1. **A list of common parts the library does not know yet**, from public sources (Inventor Content Center families,
   supplier catalogue names – hydraulics, linear motion, drives, pneumatics, lifting gear): hydraulic fittings and
   adapters, hose ends, valves and manifolds, pumps, motors and gearboxes, couplings, sensors and encoders, cable glands
   and connectors, linear guides, ball screws, belts and pulleys, sheaves, shackles and rope ends, gaskets and O-rings,
   grease nipples, handles and knobs, castors and levelling feet, aluminium profiles and their fittings, sheet-metal
   covers and brackets, springs, bushings, seals – each with its kind, group and an existing look. Say per entry where
   the name came from.
2. **Recognition beyond names:** for parts named "Part123", cheap and safe shape hints only (thin round with a hole =
   washer, hex prism with a bore = nut …); measure how many parts of the test models would change group.
3. **Teach it easily:** if the app has no such thing yet, a "Not recognised" list (parts left in Other) with **Make a
   rule** that opens the rule sets with the name filled in.

## Done when

- [x] Every new keyword checked in EN / NL / DE with examples in `tests/test_part_types.py`; the test models' groups
      unchanged except where intended (listed in the report)
- [x] Guide (part kinds) updated; full suite + GitHub run green; report; merged, version, release

---

## Report (filled in by the chat that did the task)

**Chat / date:** worker, Claude Code on the web, 24 Nov 2026 · version **0.2.222**

**What changed:**
- **Part library, ~210 new keywords** (`core/part_types_data.py`, table `ADDED_0302`: per type, rows of
  keywords + where the names come from – Parker / Gates / Stauff / Voss, Hydrotechnik, Deublin, perma / SKF,
  Atlas Copco / Kaeser, HYDAC / Elesa, ifm / WIKA / E+H, Heidenhain / Sick / Leuze, KTR / R+W / Ringfeder,
  Schaeffler / THK / Rexroth, Crosby / Pfeifer / Van Beest, RUD / Pewag, Trelleborg / Hallite / Freudenberg,
  Ganter / Elesa / Kipp, item, GGB / igus, Phoenix / Weidmueller / Siemens, Rittal, Inventor Content Center families).
  All go into **existing groups and looks** (no new group). Besides names it did not know (~70 of ~600 tried) it fixes
  names it sorted wrongly: "Lichttaster" (was a push button), "Riemenspanner" (handle), "Schlauchleitung" (cable),
  "Drahtseilklemme" (electrical), "Kreuzrollenführung" / "PROFILE RAIL GUIDE" (plate), "CARDAN SHAFT" (shaft),
  "HOSE END / TAIL / BARB" (hose → fitting), "MEASURING COUPLING" (coupling → fitting), "DRAAIDOORVOER" (electrical →
  fitting), "LINEAR SCALE" (label), "Augplatte" (plate), "Klampe" (lamp), "BRAKE RESISTOR" (brake).
  Left out on purpose (too wide): a bare TANK, RACK, SCHIJF, REDUCER, "Buchse", "STECKVERBINDER" kept as it was.
- **Fasteners** (`core/fasteners.py`): 27 German / Dutch one-word compounds (Federscheibe, Zahnscheibe, Passscheibe,
  Sperrkantring, Schnorr, Nutmutter, Ringmutter, Einschlagmutter, Nietmutter, SLEUFMOER, BLINDKLINKMOER, Senkniet,
  BORGRING, Wurmschraube …); BONDED / SEALING / THRUST WASHER and USIT are no longer fasteners (→ seals, plain
  bearings). `from_shape()` for a fastener known only by its shape (`matched_by="shape"`).
- **Shape hints** (new `core/shape_hints.py`, NumPy only): washer (thin flat ring, round hole, nothing else), hex nut
  (hexagon with a bore, height 0.3–1.3 × across flats, no collar), O-ring (torus). Axis from the surface's second
  moments (the eigenvector whose moment stands apart, the others tried after it); meshes over 20,000 triangles or
  0.16 m are not looked at. Used only when `part_types.shape_may_decide`: no type from the name or parent assemblies,
  no material in the name, no fastener name. `rules.facts_for(shape=)`; `blender/logic.facts_for_object` reads the
  mesh only for such parts, once per mesh per sorting pass (small additive change in the Looks lane's `logic.py` and
  `rules.py`; no saved data, no new rule field).
- **"Not recognised" list:** the app has it already (3 Looks: "… unsorted" in red, **Show only the unsorted parts**;
  Find & sort parts: **Common words in unsorted parts** → one click fills the search → **Make it a rule**), so no new
  panel. Guide (3 Looks, Sorting rules) and CHANGELOG updated.
- PC check line **import.shapes** (Full; a STEP with Part1–Part4 written at run time with OpenCascade, imported and
  sorted; `MIN_LINES_FULL` 132), named in the function `import.step`.

**Tested and measured** (4-core web machine):
- `tests/test_part_types.py` (+137: every added name with EN / NL / DE examples, every added keyword alone gives its
  type, neighbours keep their group), `tests/test_fasteners.py` (+29), new `tests/test_shape_hints.py` (8: 36 shapes ×
  3 qualities × standard / not × as drawn / turned and moved, meshed by the importer's own mesher – washers M6–M30,
  ISO 4032 nuts M6–M30, three O-rings; look-alikes: hex bolts, socket screws, flange with bolt holes, bearing rings,
  disc, spacers, hex bar, hex without bore, square nut, 300 mm ring, block → nothing; a full STEP import; Blender part
  objects). One hint costs < 20 ms on a fine M12 nut.
- **Test models' groups:** all 45 STEP files of `tests/data` read with the importer, 1,241 parts sorted with the old
  (main) and the new library incl. shape hints: **1 part changes group** – test mill cabinet's "CONTROL PANEL" (a box
  with a screen): Covers & panels → Electrical components (intended). Unsorted 6 → 6. The 703 part-name literals in
  the demo ship, lifting cranes, site projects and test-model makers: only that same name changes. No test-model part
  is named so that a shape hint applies, so the hints change nothing there (their own model is in the PC check line).
- PC check `import.shapes` + `import.machine` in Blender as a module: both OK (2.9 s / 2.0 s).
- GitHub: 2 runs. Run 45296857153 (full): all green except the real-app Place/Remove test ("Delete opens the Remove window", a key in the callouts group, task 0292's test; the job ran 11.6 min instead of 5.8, main was green with the same test, nothing of this task touches keys or windows) – green after one re-run of that job. Then main fast-forwarded to it (release by reuse).

**Open points / follow-up tasks:**
- The owner did not paste own unrecognised names in this session; a few of his would show what is still missing
  (names only, in the chat – never committed).
- Shape hints only know three kinds; more (dowel pins, circlips, keys) are possible but get less safe – a short
  plain shaft looks like a dowel pin.
- A rule field "Shape" (to sort by the hint in own rules) was not added: it would be a new saved choice in projects.

**Owner's check on your PC:** after the update, run the PC check (line **import.shapes** must be OK). In your own
model, parts called "Part…" that are washers, nuts or O-rings now land in "Fasteners default" / "Seals & O-rings".
