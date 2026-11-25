# 0323 – Welds from the CAD file: solid weld beads in a STEP are recognised, split per weld, sized, and get the app's weld looks

**Who:** worker · **Status:** done (0.2.251) ·
**Branch:** `task/0323-welds-from-cad`
**Started by:** lead, 24 Nov 2026 (owner 12:47: "Could we also recognize welds from the imported cad model? Like the
welds placed in inventor or other cad programs." – and: "Could the app recognize the size and material automatically?
And if it's painted over.") · **Model:** Opus · effort High
**Area:** Welds lane – new `core/weld_cad.py` (no Blender: find, split and measure bead bodies), new
`blender/weld_cad.py` (turn them into welds); additive: `core/welds.py` / `blender/welds.py` (a weld "from CAD" keeps
its own mesh), `ui_welds.py` (the "from CAD" rows and buttons), `core/part_types_data.py` (one part type "Weld beads" –
Part library lane is free), `blender/build.py` (one hook after import), `reimport.py` (model update), `props.py`,
`core/functions.py`, `tools/make_test_weldment.py`; tests, guide, tour, PC check, CHANGELOG.
**Not:** the STEP reader itself, welds placed in the app (0319), weld symbols / list code (0320 – CAD welds only feed it),
cosmetic welds (nothing of them is in the file), 2D drawings.

## Goal

A weldment from Inventor (and any CAD program that exports solid welds) comes in with its welds recognised: each bead
becomes its own weld with the app's looks – right metal, painted or bare, rust – and its size in the weld list,
without picking any faces.

## Background

- **How CAD programs export welds** (lead's web check, 24 Nov – check it against the owner's file):
  - **Inventor solid welds** (fillet, groove) are assembly features; STEP export gives them as solid geometry, but
    **all welds of one weldment as one part / one body** (Autodesk forum answer). The beads have a material in
    Inventor, but no density in the STEP (Autodesk forum).
  - **Inventor cosmetic welds** are graphics only → nothing in the STEP.
  - **SolidWorks** weld beads are graphics → not in the STEP.
  - **Creo 8+**: each solid weld is exported as its own body of the part; with STEP AP242 the weld symbol can come as
    PMI.
  - Fusion and others: welds, if any, are ordinary bodies drawn by the user (a part named "Weld…" or just a bead
    shape).
- **0319** (0.2.231): welds placed in the app – `FRWeld` with `part_a` / `part_b`, faces, `seam_data`; `core/welds.py`
  `metal_of`, `defaults`, `warning`, `rust_of`, the bead and heat-zone looks (`weld_looks.py`), painted by default when
  the parts' group is a paint. **0320**: copies take welds, ISO 2553 symbols, a weld list + CSV.
- The importer already reads CAD material names (`build.PROP_CAD_MATERIAL`) and part types by name
  (`core/part_types_data.py`: "Welded frames & structures").
- **The owner's test file**: a small invented Inventor 2027 weldment STEP (2 plates, 1 solid fillet weld, 1 cosmetic
  weld). **Attach only – never commit it, no name, picture or number from it in the repository** (owner 24 Nov). He
  could not attach it on 24 Nov: if it is not in the session at the start, ask for it once in a **"WAITING FOR
  YOU:"** line; if he cannot give it, build against the imitation (step 7) and put a check step for his file in the
  owner's test steps.

## What to do

1. **Find weld bodies at import.** By name: the names Inventor gives the weld part / bodies (read them from the
   owner's file), plus "Weld", "Welds", "Weld bead", "Lasnaad", "Schweißnaht", "Soudure" and the like; by shape: a long
   thin body lying in the corner or gap between two parts, with a triangle / trapezoid / groove cross-section, touching
   both. The shape confirms the name and finds unnamed beads from other CAD ("Found N welds by their shape – check
   them" in the import message). Never a normal part (bars, profiles, keys, gaskets): tests with such look-alikes.
2. **Split** one welds body into one bead per connected piece. A bead that turns a corner stays one weld; pieces with
   the same two parts on one line become one intermittent weld (n × l (e)).
3. **Measure each bead:** the two parts it joins (contact faces), the seam line, the kind (fillet / butt-groove /
   other), the size – fillet legs z1 / z2 and throat a from the cross-section (rounded to 0.5 mm, unequal legs said),
   length, all round when closed, intermittent piece and pitch. A bead touching one part or three: kept, shown as
   "joins N parts".
4. **Material:** the bead's own CAD material when the STEP carries one (Inventor's weld bead material), otherwise from
   its parts with 0319's `metal_of` / `defaults` (steel, stainless, aluminium; mixed metals → 0319's warning). Process
   from 0319's defaults per metal. **Painted or bare:** a CAD file does not say – same rule as 0319: painted when the
   parts' group is a paint, bare otherwise; the user can switch it per weld or for all welds from the CAD at once.
5. **Shape:** keep the **CAD bead's own shape** (its exact size) with the app's looks on it – ripples, heat tint, paint,
   rust (give it UVs along the seam so 0319's materials work), plus 0319's heat-zone strips beside it. A button
   *Use the app's bead instead* per weld and for all (builds 0319's bead on the found seam). Lead's call – the owner
   may change it.
6. **They are normal welds from then on:** in 3 Looks > Welds marked "from CAD"; in 0320's weld list and symbols with
   the measured size; copy / paste (0320); motion – the bead goes with the first part, 0319's warning when the two
   parts are on different joints; model update – a re-import keeps the user's changes on a weld whose bead came back
   in the same place, a bead that is gone is listed ("Weld lost in the new model"), a new bead is added and said;
   Client view, web 3D page, clash (left out, as 0319), undo.
7. **Test models:** `tools/make_test_weldment.py` gets three exports of the same frame: Inventor-like (all welds one
   body in one part, the names Inventor uses – from the owner's file, or your best reading of Autodesk's docs, said in
   the report), Creo-like (one body per weld), and unnamed beads; plus look-alike parts that must not be taken. Expected
   counts and sizes in the tests.
8. Guide (Welds > Welds from the CAD file: what comes through from Inventor, SolidWorks, Creo, Fusion; cosmetic welds
   do not), function entry (`since=`), the 0319 tour stop extended, a Full PC-check line (the Inventor-like frame gives
   N welds with the right sizes), CHANGELOG. Import time of the 300-weld frame before / after.

## Done when

- [ ] Inventor-like, Creo-like and unnamed beads recognised; look-alikes left alone (tests)
- [ ] One welds body split per weld; sizes (a, z, length, all round, intermittent) right within 0.5 mm (tests)
- [ ] Metal from CAD material or parts; painted / bare by 0319's rule, switchable (tests)
- [ ] CAD shape kept with the app's looks; *Use the app's bead instead* works
- [ ] In the weld list / symbols, copy, motion, model update, Client view, web 3D (tests)
- [ ] The owner's Inventor file checked in the session, or a check step for it in his test steps
- [ ] Tests added/updated; full suite passes; screenshots checked; version fields; owner's test steps; merged, release

## Not in this task

Cosmetic welds (not in the file), the STEP reader, weld symbols / list drawing (0320), AP242 weld PMI (if the owner's
file carries any, say what is there – a later task), 2D drawings.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 25 Nov 2026 (one worker session, one independent-tester subagent).

**What changed:**
- `core/weld_cad.py` (new, no Blender): weld names (EN/NL/DE/FR/IT/ES …; never Weld nut, Weldment, Welded frame,
  Weld-on hinge), split a body into its pieces, contact per bead face (7 points per triangle, facing the part), the
  root line read from the bead's own mesh (where its faces on part A meet those on B) with 0319's corner at every point
  – 0319's seam finder only as a fallback, cut to where the bead lies; kind (fillet / groove = the bead fills both
  faces to their ends; its line moved up to the plates' faces where 0319's butt weld lies / OTHER), legs z1 / z2,
  throat a = min(z)·cos(θ/2) or the depth along the middle (concave), cap width, length, all round (a ring, or seams
  round a square post in a loop), intermittent (pieces on one line, regular within 15 %), metal from the CAD material
  name, the shape check for unnamed beads (two parts, a seam under ≥ 60 % of it, legs ≤ 40 mm, section ≤ 1.5 × the
  legs' triangle), UVs along / across, model-update matching. An inside-out piece is turned the right way.
- `blender/weld_cad.py` (new): at the end of an import (`ops_import.finish_import`, after the rules) the model's beads
  become `FRWeld`s with `from_cad` (parts, seams in part A's coordinates, sizes, intermittent, metal, finish by 0319's
  rule); the CAD shape is kept as a mesh in part A's coordinates (`cad_mesh`, UV `fr_weld`), the source part is left
  out (excluded + `fr_weld_source`; Clean-up's "show all" keeps it out). Message: "6 welds from the CAD file …; found N
  by their shape – check them". Model update (`reimport`): kept with the user's settings / lost / new, with undo.
- `blender/welds.py` (additive): the `cad_*` properties, `rebuild` uses the CAD shape (or the app's bead), CAD welds
  never refind their seams, `carry_over` leaves them to `weld_cad`, `remove` drops the CAD mesh. `weld_symbols.py`: a
  loop of seams is one all-round weld. `ui_welds.py`: import icon in the list, the weld's "From the CAD file …" line,
  *Use the app's bead instead* / *Use the CAD shape again*, Kind / Size greyed while the CAD shape is used, *Find in CAD
  file*, fold **From the CAD file** (CAD shape / App's bead / Painted / Bare / Back to the CAD part). 4 operators in
  `ops_welds.py`.
- Part type **Weld beads** (`part_types_data.py`). `tools/make_test_weldment.py --cad inventor|creo|unnamed [B]`
  (the CAD-weld frame: 6 welds incl. intermittent, ring, square-post ring, unequal legs, V groove; 5 look-alikes) and
  `--heavy N --beads`. Guide section *Welds from the CAD file*, function `looks.weld_cad`, tour stop **welds_cad** in
  the Welds set, PC-check line **looks.weld_cad** (Full), real-app welds test +3 checks (import, all App's bead, undo).
- **Inventor's names**: not read from the owner's file (it was not in the session). Autodesk's forum: an Inventor
  weldment's solid welds are an assembly feature and leave a STEP export as one part / one body; the beads have the
  weldment's bead material. The imitation calls the part "Welds" with material "Welded Steel Mild"; the finder takes
  any name with weld / welds / weld bead / Schweißnaht / Lasnaad … and finds unnamed beads by shape anyway.

**Tested and measured** (4-core web machine):
- Tests: `test_weld_cad_core.py` 65, `test_weld_cad_independent.py` 70 (independent tester), `test_weld_cad.py` 16
  (Blender), the 0319 / 0320 weld tests unchanged (237 passed), real-app welds 23/23, tour set welds built + its 3 stops'
  checks, precheck. All three exports give the same 6 welds within 0.5 mm; look-alikes never taken, also when every
  part goes through the full shape check.
- **Import time, 300-weld frame** (`--heavy 100 --beads`, 301 parts, Normal): 1.0 s without the welds → 32 s with them
  (30.3 s finding and making 300 welds: ~0.1 s per weld, about half of it 0319's heat-zone strips). First version took
  > 10 min there: the new parts had no world place yet at the import (all cells on top of each other) – fixed, test
  `test_placed_parts_in_a_grid`. The 6-weld frame: ~1 s.
- Independent tester (subagent, Sonnet): 70 tests from the brief; 1 fault found and fixed (a bead whose triangles face
  inward was not found). No other subagents; nothing re-done after merging.
- **Every other test model** (55 STEP files in tests/data): no weld found; the finder costs 0.02 s on most imports
  (0.67 s at most, test_finishes) – it reads the parts' meshes only when a body may be a bead. The first GitHub run
  found two faults this way: a way-cover flange strip (3 x 40 mm in a corner) taken for a groove weld by shape
  (now: legs at most 3:1, a groove's section at most 1.8 x its V; test over 11 models), and Thor's import (the
  site's robot arm, 517 parts) taking 890 s in the finder – screws and printed shells went through the full check.
  Now: no known part words (screw, washer, pin …), at most 40 CAD faces, 5 x as long as wide, a quick 96-point contact
  look first, contact checks only near the bead, and at an import the search by shape stops after 10 s (said; Find in
  CAD file has no limit). Thor's candidates: 108 → 8, the finder ~20 s (stopped at 10 s at an import).
- GitHub runs: 1st (full) – real-app way covers failed (the flange above), one pytest group stopped at 40 min (Thor in
  `test_site_projects.py`; every group ran 1.5–2 x slower than usual that hour). 2nd–4th: green (two more only
  because 0337 and 0338 took the version numbers meanwhile: 0.2.246 → 0.2.249 → 0.2.250 → 0.2.251). `main`
  fast-forwarded to the green commit a065d156 (release run: see the commit after it).

**Owner's test steps** (on your PC, after the update):
1. Inventor: open your small weldment (2 plates, 1 solid fillet weld, 1 cosmetic weld), **File > Export > CAD
   Format**, choose **STEP**, save.
2. Fresing Render: **Import STEP…**, pick that file. The message under Import should say "1 weld from the CAD file".
3. Open **3 Looks > Welds**: one weld with the import icon. Click it: the line "From the CAD file (by its name) ·
   fillet a… " shows the size – compare it with Inventor's weld (a and length). The cosmetic weld is not there (it is not
   in the STEP file) – that is expected.
4. Press **Use the app's bead instead**, then **Use the CAD shape again**: the bead changes and comes back.
5. Send the lead the line from step 3, and – only if no weld was found – the part names you see in **2 Structure**.

**Open points / follow-up tasks:**
- The owner's Inventor file was not checked in this session (not attached): steps above. If its welds part is named
  differently and not found, the fix is one word in `core/weld_cad.py`.
- **Guide pictures of the Welds panel are wrong** (since 0319): `tools/guide_screens.py welds_panel` grabs the 3D view's
  toolbar ("Active Tool") instead of the side panel – `docs/img/panel_3_welds.png` shows that. Not fixed here (guide
  tool); no picture for the new section either. Follow-up for the guide lane.
- Speed: 0.1 s per weld at the import (300 welds = 30 s on 4 cores). Could be cut by sharing the heat-zone work
  (0319's `_heat`) or doing the welds in helper processes.
- Not read: AP242 weld PMI; a square groove with a root gap (no common edge, the finder does not see a corner) comes
  as OTHER (own shape only) when named, and is not found by shape.
- The tour stop's camera frames both weldments (the close camera fits wider than asked).
