# 0008 – Automatic materials for most parts: part-type library + CAD material names

**Who:** worker · **Status:** open · **Branch:** `task/0008-part-type-rules`
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
  Unsorted. Names look like typical machine-building parts: vendor part numbers (e.g. SMC guided
  cylinder parts like `_MGG25-150(0)_ROD`), assembly names like `CONVEYOR.SYSTEM`,
  `GASCKET.ASSY.UNIT.AS` (sic), aluminium profile frames, sensors, plexiglass guards, a mannequin.
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
   The owner will attach a small Inventor STEP (an assembly with e.g. one aluminium and one rubber
   part) in this chat: check whether Inventor's export contains material names and/or visual
   materials and say so in the report. Also test with a STEP written by OpenCascade with a material
   set, so the path is covered by a test without the owner's file.
4. **Materials:** add library materials that are needed (e.g. nickel-plated brass, black anodised
   aluminium, timing belt rubber, foam, wire mesh, mannequin matte). **Append new ids at the end of
   the stable number table in `core/materials_lib.py`**, never renumber (saved projects use them).

Allowed outside `core/` and `importer/` (the lead works in `blender/` at the same time):
- `blender/build.py`: one line storing the node's `material` on the part object as
  `ob["fr_cad_material"]` (add a `PROP_CAD_MATERIAL` constant);
- `blender/logic.py`: only `facts_for_object` (pass `fr_cad_material` on).

## Done when

- [ ] Part-type library with hundreds of patterns over all families above
- [ ] Rule fields `part_type` and `cad_material`; new default rule order; group starting materials
- [ ] STEP material names read into the cache; mapped to library materials
- [ ] `tests/test_part_types.py` with at least 300 example names (generic and vendor-catalogue
      style) → expected type, plus negatives that must stay unsorted (e.g. "FRAME", "PRODUCT INFO")
- [ ] A coverage number for the owner's attached model (share of parts that get a type), names
      **not** written anywhere in the repository
- [ ] Full test suite passes (`CLAUDE.md` section 5); no version bump (the lead releases)
- [ ] Report below filled in; pull request into `main` (or the branch pushed, if a PR cannot be
      opened from the chat)

## Not in this task

- No changes to `blender/ui*.py`, `blender/ops_*.py` or any other `blender/` file except the two
  hooks above (the lead is changing the Structure and Looks panels in task 0009).
- Existing projects keep their own rule lists; the new defaults reach them via the "Defaults"
  button. Mention in the report if an automatic upgrade seems needed.
- **The repository is public: never commit the owner's STEP files, part-name lists or screenshots.**

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
