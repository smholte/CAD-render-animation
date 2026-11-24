# 0323 – Welds from the CAD file: solid weld beads in a STEP are recognised, split per weld, sized, and get the app's weld looks

**Who:** worker · **Status:** waits for 0320 (same files: `core/welds.py`, `blender/welds.py`, `ui_welds.py`) ·
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

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
