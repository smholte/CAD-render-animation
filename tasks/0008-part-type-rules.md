# 0008 – Automatic materials for most parts: part-type library + CAD material names

**Who:** worker · **Status:** done (0.2.8) · **Branch:** `task/0008-part-type-rules`
**Started by:** lead chat, 4 Nov 2026 · **Area:** `fresing_render/core/` (rules, new part-type
library, material library), `fresing_render/importer/step_reader.py`, plus exactly two small
hooks named below. Nothing else.

## Goal

When a STEP is imported, most parts get a sensible, good-looking material on their own: aluminium
profiles look like anodised profiles, seals are black rubber, pneumatic cylinders anodised
aluminium with chrome rods, plexiglass is clear, cables black, and so on. The owner wants "a very
large and wide set of rules to automate most parts colouring".

## Background

- Today the default sorting rules (`core/rules.py`, `default_rules()`) only know fasteners (parsed
  from names by `core/fasteners.py`: DIN/ISO, finish) and CAD colours ("Colour #RRGGBB" groups,
  satin paint in that colour). Everything else goes to "Unsorted" (satin paint RAL 7035).
- On the owner's latest model (2,745 parts, an Inventor STEP without colours) 2,694 parts ended up
  Unsorted. Names look like typical machine-building parts: vendor part numbers (pneumatic
  cylinder parts, guides), assembly names with typing errors, aluminium profile frames, sensors,
  plexiglass guards, a mannequin. (No real part names in this public repository.)
- Sorting runs automatically after every import (`blender/logic.py: apply_rules`): rules are checked
  top to bottom, the first match decides the group; a group gets its starting material from
  `core/rules.py: default_material_for_group`. Materials are in `core/materials_lib.py`.
- A STEP colour is only a flat RGB value. The app turns it into a group with a proper material.
  Rule of thumb agreed with the owner: **the part type decides the material; the CAD colour only
  decides the colour of paints and coloured plastics.**

## What to build (decided with the owner and the lead)

1. **Part-type library** – new module `core/part_types.py` (data-driven; a table or a JSON file in
   `core/data/` is fine). Each type: id, group name (e.g. "Seals & O-rings"), material id (+ colour
   when the material needs one), and match patterns:
   - keywords, case-insensitive, word-aware (`ROD` must not match `PRODUCT`), with English, Dutch
     and German variants and common misspellings (SEAL/AFDICHTING/DICHTUNG, GASKET/GASCKET/PAKKING,
     PROFILE/PROFIEL/PROFIL …);
   - vendor part-number patterns (regex): SMC (MGG, CDQ2, CQ2, MXS, MGP, CXS, CY…), Festo (DSNU,
     ADN, DSBC, DGSL, VUVG…), Bosch Rexroth and item profiles (3842…, 0.0.0xx…), Misumi (HFS, SBRB,
     PSFJ, LHFR…), igus (E2, chainflex, iglidur), SKF/FAG bearings (6205-2RS, NU…, 2208…), HIWIN/THK
     rails and carriages (HGR, HGH, HGW, SHS, SSR…), Norelem/Ganter/Elesa handles and levelling feet
     (GN…, LV.F…), sensors (IFM, Sick, Balluff, Pepperl+Fuchs, Keyence codes), Rittal enclosures,
     signal towers (Werma, Patlite), valves and fittings (push-in KQ2, QS…);
   - size patterns where useful (`40x40`, `4040`, `45x90`, `Ø20`).
   Cover at least these families, each with a sensible material from the library (add materials
   where needed, see 4):
   aluminium profiles + their caps, connectors, T-nuts, brackets · plates, blocks, brackets
   (choose a sensible default and say why in the report) · shafts, rods, pins, dowels, keys ·
   pneumatic cylinders (body anodised aluminium, rod chrome), valves, valve terminals ·
   fittings, hoses, tubes · linear rails, carriages, ball screws, bushings · bearings, housings ·
   couplings, gears, pulleys, sprockets, chains, timing belts · springs · seals, O-rings, gaskets,
   wipers · cables, cable chains, cable glands · sensors, switches, light curtains · motors,
   gearboxes, servo drives · electrical enclosures, terminal boxes, PLC/IO, push buttons, emergency
   stops, signal towers · handles, knobs, levelling feet, casters, rubber buffers · guards, windows,
   doors (polycarbonate/plexiglass, wire mesh) · plastics (POM, PE, PA, PEEK, PTFE, PVC) by name ·
   rubber, foam, felt · stainless parts (SS, RVS, INOX, 1.4301, 304, 316) · labels, nameplates ·
   human figures / mannequins · welded frames and sheet metal (paint, take the CAD colour when there
   is one). Aim wide: hundreds of patterns.
2. **One rule, not hundreds:** add a rule field `part_type` (and `cad_material`, see 3) to
   `FIELDS` / `PartFacts` in `core/rules.py`, filled by the library. New default order:
   the six fastener rules → `Part type has any value → {part_type}` → `CAD material has any value →
   {cad_material…}` (mapped to a library material) → `Colour {color}` → Unsorted. The sorting-rules
   list in the app must stay short; the library is behind the single part-type rule.
   Paint-type part types take the part's CAD colour when it has one (one group per type and colour);
   metals, rubber and clear plastics ignore it. `default_material_for_group` must give every new
   group its right starting material.
3. **CAD material names from the STEP (point 18)**: read material names when the file carries them
   (XCAF `XCAFDoc_MaterialTool` / `XCAFDoc_Material`, and visual materials `XCAFDoc_VisMaterialTool`
   with base colour/metallic/roughness if present). Store per node in `tree.json` as `material`
   (bump `CACHE_VERSION`, old caches are re-read), map common names to library materials
   ("Aluminum 6061", "Aluminium", "Steel", "Stainless Steel", "Rubber", "ABS Plastic", "Glass" …).
   The owner has no Inventor access at the moment, only **Fusion 360**: he will attach a small
   Fusion 360 STEP (an assembly with e.g. one aluminium and one rubber part, exported with
   File > Export > STEP) in this chat. Check whether it contains colours, material names and/or
   visual materials and say so in the report; Inventor follows when he has access again.
   Known: his big Inventor model ("EGR…", 78 MB) is STEP **AP203** (`CONFIG_CONTROL_DESIGN`, written
   by an AutoCAD Mechanical Desktop 2009 / PDElib translator) and has no colours and no
   `MATERIAL_DESIGNATION` at all – AP203 cannot carry them. Write in the report which export
   setting (AP214 / AP242) the owner should use in Inventor and Fusion to keep colours/materials.
   Also test with a STEP written by OpenCascade with a material set, so the path is covered by a
   test without the owner's file.
4. **Materials:** add library materials that are needed (e.g. nickel-plated brass, black anodised
   aluminium, timing belt rubber, foam, wire mesh, mannequin matte). **Append new ids at the end of
   the stable number table in `core/materials_lib.py`**, never renumber (saved projects use them).

Allowed outside `core/` and `importer/` (the lead works in `blender/` at the same time):
- `blender/build.py`: one line storing the node's `material` on the part object as
  `ob["fr_cad_material"]` (add a `PROP_CAD_MATERIAL` constant);
- `blender/logic.py`: only `facts_for_object` (pass `fr_cad_material` on).

## Done when

- [x] Part-type library with hundreds of patterns over all families above
- [x] Rule fields `part_type` and `cad_material`; new default rule order; group starting materials
- [x] STEP material names read into the cache; mapped to library materials
- [x] `tests/test_part_types.py` with at least 300 example names (generic and vendor-catalogue
      style) → expected type, plus negatives that must stay unsorted (e.g. "FRAME", "PRODUCT INFO")
- [~] A coverage number for the owner's attached model (share of parts that get a type), names
      **not** written anywhere in the repository – Fusion test file: 2 of 2; the big Inventor model was
      not attached in this chat (see report)
- [x] Full test suite passes (`CLAUDE.md` section 5)
- [x] Merged into `main` and released by this chat (rule changed 4 Nov 2026, `CLAUDE.md`
  sections 2 and 7; task 0009 is merged in `main` as 0.2.7 – update the branch to it first)
- [x] Report below filled in; pull request into `main` (or the branch pushed, if a PR cannot be
      opened from the chat)

## Not in this task

- No changes to `blender/ui*.py`, `blender/ops_*.py` or any other `blender/` file except the two
  hooks above (the lead is changing the Structure and Looks panels in task 0009).
- Existing projects keep their own rule lists; the new defaults reach them via the "Defaults"
  button. Mention in the report if an automatic upgrade seems needed.
- **The repository is public: never commit the owner's STEP files, part-name lists or screenshots.**

---

## Report (filled in by the chat that did the task)

**Chat / date:** worker chat, 4 Nov 2026 (started before the "worker merges and releases" rule;
finished under it: merged into `main` and released as 0.2.8).

**What changed:**

- **Part-type library** – `core/part_types.py` (matching) and `core/part_types_data.py` (data,
  plain Python with comments; how to add a word is explained at the top). 63 part types in 62
  groups (plus 24 material groups) over all families of the brief plus rod ends, conveyor rollers, robots, tooling, offshore
  lifting gear and winches; ~3,300 keywords (English, Dutch, German, misspellings like BEARRING)
  and ~170 vendor part-number patterns (SMC, Festo, Schunk, item, Bosch Rexroth, Misumi, igus,
  SKF/FAG/INA, HIWIN, THK, NSK, KHK, Sick, ifm, Balluff, Pepperl+Fuchs, Keyence, Omron,
  Schmersal, Siemens, Beckhoff, Wago, Phoenix, Schneider, ABB, Pilz, Rittal, SEW, Neugart,
  Wittenstein, Werma, Patlite, KUKA/ABB/Fanuc/UR, Ganter/Elesa/Kipp, Crosby...).
  Matching rules, each covered by tests:
  - word-aware (`ROD` never in `PRODUCT`); `*END`/`START*` keywords for German/Dutch compounds
    (`KUGELLAGER`, but `SCHALTER` is a switch, not a `…HALTER` holder); camelCase is split;
  - a keyword inside a longer one does not count ("SHAFT SEAL" is a seal); a generic shape beats
    a bought product in either word order ("SENSOR BRACKET", "BRACKET SENSOR", "FLANGE MOTOR" are
    all brackets/flanges); otherwise the last word wins (the noun ends English names and compounds);
  - **parent assemblies:** a part with a generic name inside a bought product is part of it
    (BODY inside "CDQ2B32-50DZ" = cylinder; its ROD = chrome rod via the product's roles);
    motors, sensors, valves, signal towers, robots and mannequins keep one colour throughout.
    Only products and bought multi-part items (bearing units, casters, couplings, fittings…)
    pass their type down; **machine modules never do** ("…UNIT", "…SYSTEM", "…STATION",
    "…PRESS", "…TEST", "BELT DRIVE ASSY", also with "ASM"/"AS"/"_RH" after the word – otherwise
    an O-ring fitting station would turn all its plates into rubber);
  - a material in the name sorts generic shapes ("PLATE RVS" → Stainless steel parts,
    "BLOK POM ZWART" → "POM parts, black"); short words like SS/AL/PE only next to another word;
  - CAD colour: only paint-type groups and coloured plastics take it ("Covers & panels #1F4E79");
    metals, rubber and clear parts ignore it (the agreed rule of thumb).
- **Plates, blocks & brackets default:** machined aluminium when the part has no CAD colour,
  satin paint in the CAD colour when it has one; a material in the name or a known CAD material
  decides first. Why: in automation lines like the EGR model (profiles, SMC parts, no colours)
  uncoloured machined plates are mostly bare aluminium; a part the designer coloured is painted.
  Covers/panels, sheet metal and welded frames default to RAL 7035 paint (powder coat for sheet
  metal) and take the CAD colour.
- **Rules** (`core/rules.py`): fields `part_type` and `cad_material` appended at the end of
  `FIELDS` (Blender stores the position of each choice; old projects keep theirs). Default order:
  6 fastener rules → `Part type has any value → {part_type}` → `CAD material has any value →
  {cad_material}` → `Colour {color}` → Unsorted (9 rules). For generic shapes a known CAD material
  wins over the name ("PLATE" with "Aluminum 6061" goes to the CAD-material group); bought parts
  keep their type (Fusion's default material "Steel" must not make seals steel).
  `default_material_for_group` knows every library group, "<group> #RRGGBB", "<group>, black",
  and CAD-material groups ("Paint - Enamel Glossy (Red) #C00000" → gloss paint in that colour).
- **CAD material names** – `core/cad_materials.py` maps Fusion/Inventor/OpenCascade material and
  appearance names to library materials ("Aluminum - Satin", "Steel, Galvanized",
  "Paint - Enamel Glossy (Red)", "ABS Plastic", "Polycarbonate"…); "Default", "Generic" and
  unknown names count as no material, so the CAD colour still decides.
  `importer/step_meta.py` reads the names straight from the STEP text (see below why not through
  XCAF): `PROPERTY_DEFINITION('material property','material name',…)` (Autodesk and OpenCascade),
  `MATERIAL_DESIGNATION`, and the style name of each body (`FILL_AREA_STYLE`/`COLOUR_RGB` name =
  Autodesk appearance), mapped to parts by product name (two products with one name and different
  materials are left out). The reader stores per node `material` (the name that decides the look:
  a known appearance, else the material), `material_name` and `appearance`; `CACHE_VERSION` 4
  (old caches are read again).
- **New library materials** appended to the number table (34–41): nickel plated, aluminium black
  anodized, zinc die-cast, belt rubber, foam, felt, mannequin matte, wood (new menu category "Other").
- **Hooks:** `build.py` stores `ob["fr_cad_material"]` (`PROP_CAD_MATERIAL`); `logic.facts_for_object`
  passes it on. No other `blender/` change.
- **Self-test:** new line "CAD material names and part types" (imports a small STEP with materials
  through the real import job and sorts a part by the library); `data/test_materials.step` ships for it.
- `rules.upgraded_rules()` gives the new defaults for a project whose rule list is still the
  untouched old default list (see open points).
- Tests of task 0009 that renamed parts to "SEAL RING …" and expected them unsorted now use
  names the library does not know.

**Owner's Fusion 360 STEP** (2 parts, attached in this chat, not in the repository): AP214
(`AUTOMOTIVE_DESIGN`, Autodesk Translation Framework v15.15). It carries **colours, material
names** ("Rubber", "Aluminum", with density) **and appearance names** ("Rubber - Soft",
"Aluminum - Satin", as style and colour names). OpenCascade 8.0 reads the material names into
XCAF, but in the Python binding the lookup from part to material crashes the process, and it
keeps no appearance names (no XCAF visual materials from STEP) – hence the text reader. Result:
both parts sorted by their appearance: black rubber and machined aluminium.

**Export settings for the owner:** Fusion 360: File > Export > STEP as it is now (AP214) keeps
colours, materials and appearances. Inventor: File > Export > CAD Format > STEP, Options >
Application Protocol **"214 – Automotive Design"** (or "242"); AP203 – what the EGR file is –
cannot carry colours or materials. Inventor uses the same Autodesk translator, so the same names
are expected, but this is not yet checked with an Inventor file.

**Coverage:** owner's attached model (Fusion, 2 parts): 2 of 2 parts get a material (both from
the CAD appearance; their names "Component1/2" say nothing). The big Inventor model (EGR, 2,745
parts) was not attached in this chat, so its coverage is **not measured** – next step for the
owner (see open points).

**Independent check of the library** (names the library was not written from): a helper agent
that had not seen the library wrote 300 realistic part names from machine building (English,
Dutch, German, vendor codes, typing errors) with the group it expected. Before tuning **246 of
300 (82 %)** went to the expected group. The misses were real gaps (typing errors like CYLIDNER,
hydraulic "CYL" short forms, filters, JIC/ORFS fittings, Miki/igus codes, "4 PIN"/"WITH BRAKE"
words that describe a product, "STEP" alone taken for a stair); they were fixed and are now in the
tests. After tuning 286 of 300 (95 %) – this second number is no longer independent. Of the 14
left, 6 are finer splits the library makes on purpose ("Plate PE500 green" → "PE parts, green",
"Block PEEK" → "PEEK parts"), the rest are borderline ("Band brake winch" → winch, "As D30" –
Dutch for shaft, too short to trust).

**Tested and measured** (2-core Linux test machine):
- Tests: full suite **1,252 passed** (0.2.7 had 132 test functions; the 955 example names count
  one each). New: `test_part_types.py` (955 example names → group, 72 negatives,
  word order, parent assemblies, machine modules, qualifiers, materials, colours, 50 CAD material names,
  rules, data consistency, no keyword taken by another type's vendor code), `test_step_meta.py`
  (Autodesk structure written by hand, OpenCascade file `tests/data/test_materials.step` made by
  `tools/make_test_materials.py`, reader, import job as a separate process, old caches),
  `test_part_types_blender.py` (import → `fr_cad_material` → groups and materials in Blender).
- Packaged Linux install + self-test (0.2.8 zip built with Linux wheels): every line OK, including
  the new "CAD material names and part types" (1.1 s), except "Render HD on graphics card" (no
  graphics card on the test machine, as in every release).
- Speed: sorting 2,800 placed parts with 600 names well under 1 s (test limit 3 s, cached per
  name). Reading material names from a 78 MB STEP full of named entities: 1.8 s; files without
  names (like the AP203 EGR file) are skipped after a quick look: 0.3 s for 78 MB with a million
  unnamed colours, less without colours. The EGR import itself (50 s on the owner's PC) is not
  otherwise changed.

**Open points / follow-up tasks:**
- **Coverage on the real model:** the owner can attach the EGR STEP (or a re-export as AP214) in a
  chat; the number goes in the progress note, not in the repository.
- **Inventor export check:** one small Inventor STEP (AP214) with an aluminium and a rubber part.
- **Old projects** keep their 7-rule list; "Defaults" in the rules fold brings the new one.
  An automatic upgrade is cheap and safe with `rules.upgraded_rules()` (only when the list is the
  untouched old default) – a two-line hook in `blender/logic.ensure_default_rules` or a load
  handler; left to the lead because it touches `blender/`.
- **Wire mesh** renders as a black powder-coated panel: real holes need a grid texture in the
  node builder (`blender/materials.py`).
- The 0.2.7 ready-made material "Aluminium, black anodised" could now use the new
  `aluminium_anodized_black` (`blender/finder.py`).
- Faces with their own appearance (style on single faces) are not read yet – task 0010.
- The rules are heuristics: watch the first real imports for parts in a surprising group and
  add keywords (`part_types_data.py`) or module words where needed.
- **Privacy:** the first commits of this task's branch (before the lead removed the owner's part
  names from the brief) had some of the owner's part names in the tests. `main` got the task as
  one squashed commit without them, and the branch was moved onto that commit. GitHub can still
  show the old commits to someone who has their exact link; making the repository private (or
  asking GitHub support to purge them) closes that. Files from earlier chats still name the
  owner's EGR model (`CLAUDE.md`, and an EGR-style part name in `tests/test_fasteners.py`) – for
  the lead to decide.
