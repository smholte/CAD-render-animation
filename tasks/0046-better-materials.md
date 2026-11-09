# 0046 – Better materials: real metals, machined surfaces, paint with wear

**Who:** worker · **Status:** done (0.2.39) · **Branch:** `claude/fervent-bardeen-gdfzcs`
**Started by:** lead chat, 8 Nov 2026 · **Lane:** Looks – `core/materials_lib.py`, `blender/materials.py`,
`core/cad_materials.py`, panel 3 Looks in `blender/ui.py`, `blender/props.py` (additive), tests, guide chapter 3,
PC check line, CHANGELOG
**Model:** Opus · effort Medium · **Environment:** "CAD-render-animation" (real Blender at start, CLAUDE.md section 4)

Runs next to 0040 (Machining) and 0043 (Scene & Render). Do **not** change `core/chips.py`, milling, surroundings,
the queue or the part library (`part_types_data.py`) – if a material needs them, write it in the report.

## Goal

Straight after import the owner's machines look like real machines, not "CAD-clean": metals with the right sheen
and fine surface marks, painted steel that looks painted, optional slight wear on edges – in Cycles, and as close as
possible in Fast preview (EEVEE). Old projects pick up the new looks.

## Background

- 42 materials today in `core/materials_lib.py` (`MATERIALS`, stable numbers in the dict below it – keep every
  existing id and number; new ones get new numbers). Each is one Principled BSDF; a few have a noise for roughness
  variation or a bump (`blender/materials.py` `build_nodes`). "Stainless, brushed" has `anisotropic=0.0`: there is
  no brushed look yet.
- STEP parts have **no UV maps**. Patterns must come from object coordinates in real size (model in mm), and must
  look the same on every copy of a part (one mesh per unique part, many objects).
- `ensure_material` only rebuilds a node tree when the material id or colour changes, so old projects keep the old
  look. Stamp a look version on each material (e.g. `fr_look_version`) and rebuild when it is older, also on load.
- The owner's machines: CNC mill (cast iron bed, ground steel ways, machined aluminium, black anodised parts,
  painted covers, way covers, rubber bellows, glass/polycarbonate doors) and offshore machines (marine paint, hot-dip
  galvanised steel, stainless, hydraulic chrome rods, rubber hoses). Most renders are marketing stills and videos:
  **clean by default**.
- Render times on the owner's PC (RTX 3090): Cycles HD still ~3 s, 4K queued frame ~16 s, EEVEE ~0.4–0.9 s/frame.
  Better looks must not make renders noticeably slower.

## What to build

1. **Improve the existing metals** and add what is missing, at least:
   - *Steel, ground* (fine straight grinding lines, for ways and shafts) and *Steel, turned* (fine rings round the
     part's axis); *Aluminium, machined* with faint face-milling arcs; brushed stainless that really looks brushed
     (direction along the part's longest side).
   - *Cast iron*, as-cast (rough, slightly mottled) and painted cast iron; *Hydraulic chrome rod*.
   - Anodised aluminium (natural, black, colour) with the soft satin sheen of real anodising.
   Marks are fine (sub-millimetre), subtle at normal viewing distance, and never look like a texture pasted on.
2. **Paint:** keep the RAL colours; add a subtle orange-peel on gloss/satin/marine paint and a believable
   powder-coat structure. **Wear slider** per group in 3 Looks (0 = new, default; up to "used"): lighter/bare metal
   on sharp edges, a little dirt in corners. Must work with the coarse STEP triangles (test on the test models: if
   Cycles' bevel/AO/pointiness does not give clean edges on them, find another way or leave wear out and say why).
3. **Rubber, plastics and glass:** rubber that is not pure black (slight sheen, dust), black plastic vs. glossy
   plastic, polycarbonate/glass that reads as glass in both engines.
4. **CAD names:** extend `core/cad_materials.py` so Inventor/Fusion appearance names map to the new materials
   (e.g. "Aluminum – Anodized", "Steel – Polished", "Cast Iron", "Rubber"). Part library stays as it is.
5. **Old projects:** opening a project saved with 0.2.34 rebuilds its materials with the new looks, keeps every
   group's choice and colour, and still opens in the app (CLAUDE.md section 6).
6. **Material sheet:** a tool that renders every material on the same small set of shapes (block with a chamfer,
   cylinder, round shaft) in one picture, Cycles and EEVEE. Put before/after sheets of the changed materials in the
   report (rendered on the web machine, CPU, small size – generic shapes only). Also a **PC check line**
   `looks.materials` that renders the sheet (`ctx.picture`) so the owner can judge it on his RTX 3090.
7. Tooltips for new settings; guide chapter 3 updated with one new picture; CHANGELOG in plain words.

## Done when

- [x] New and improved materials as in 1–3; every existing id still works; new ids numbered.
- [x] Wear slider (default 0) per group, or a reason in the report why wear was left out.
- [x] Render time measured before/after on the same scene (Cycles HD still, EEVEE frame, on the web machine; name
      it): at most ~10 % slower, or the report says which material costs more and why it is worth it.
- [x] Old-project test: a 0.2.34 project opens with new looks, same groups and colours.
- [x] Material sheet before/after in the report; PC check line added (`MIN_LINES_FULL` raised).
- [x] Tests for the material definitions, the CAD-name mapping and the rebuild of old materials; tooltip check 0
      missing; GitHub green; merged and released; `TASKS.md` updated; report filled in.

## Not in this task

Chip, workpiece-cut and surroundings materials (other lanes). Image textures or downloaded material packs (licences,
size). Per-part wear painting by hand. Decals.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 9 Nov 2026 – branch `claude/fervent-bardeen-gdfzcs`, version 0.2.39

**What changed:**
- `core/materials_lib.py`: new keys `marks` (machining marks), `peel` (orange peel), `sheen`. New materials 43
  *Steel, ground*, 44 *Steel, turned*, 45 *Cast iron, painted* (Paint, takes a colour), 46 *Hydraulic chrome rod*;
  every old id and number kept. Improved: steel machined + aluminium machined (faint face-milling arcs), stainless
  brushed (brushed lines + anisotropy along the longest side), aluminium profile (faint extrusion lines), the three
  anodised (rough clear coat = satin sheen, fine grain), cast iron (mottled, sand-cast relief), galvanised (spangle),
  gloss/satin/marine paint (orange peel, also under the coat), powder coat (finer structure), rubber/cable/belt (not
  pure black, sheen, dust), matte plastic (moulded grain), gloss plastic (glossier).
- `blender/materials.py`: node builder rewritten. Marks without UV maps: each mesh stores its longest side, round
  axis and box centre (`fr_ax_*`, set by `assign` → `ensure_axes`, recomputed when the vertex count changes); the
  shader reads them with Object attributes (checked: Cycles and EEVEE both read mesh custom properties), so every
  copy looks the same. Ground/brushed = stretched noise along the long axis, turned = 1D noise of (axial + radial
  distance) → rings on the side and on the end faces, milled = 1D noise of the Voronoi distance (arcs). Anisotropy
  follows the marks (tangent object → world). Glass/PC: Cycles keeps real glass, a second output for EEVEE
  (transparent + Fresnel gloss) – before it rendered dark grey in EEVEE.
- **Wear** (`FRMaterialGroup.wear`, 0–1, default 0, slider under Material in 3 Looks): Bevel-node edge mask broken
  up by noise → bare steel under paint, polished brighter edges on metals; AO dirt in corners. Rubber/plastic/glass
  get only the dirt. Only built when wear > 0 (no cost at 0). Bevel is Cycles-only: EEVEE shows only the dirt (tooltip
  and guide say so). Clean on the STEP triangles of the test crane (no streaks along triangles). Wear is per project
  group; rule sets and paint schemes do not store it (they keep material + colour only).
- **Old projects:** materials carry `fr_look_version` (`LOOK_VERSION = 2`); `ensure_material` rebuilds when older, and
  the load handler calls `logic.upgrade_looks` → materials rebuilt with their group's material, colour and wear.
- `core/cad_materials.py`: hard chrome / piston rod / Hartverchromt → chrome rod; steel ground/polished,
  geslepen/geschliffen → steel ground; turned/gedraaid/gedreht → steel turned; gray/grey iron → cast iron. "Ground"
  alone (ground plane) maps to nothing; a named metal wins over the finish ("Aluminum - Turned" stays aluminium).
- Ready-made materials (`blender/finder.py`): steel ground, steel turned, hydraulic chrome rod, cast iron painted.
- **Material sheet:** `blender/material_sheet.py` + `tools/material_sheet.py` (block with chamfer, disc, shaft per
  material; studio light, AgX; Cycles or EEVEE; `--wear`). PC check line `looks.materials` (Full; GPU 1600 px 64
  samples, else 800 px 12 samples), `MIN_LINES_FULL` 37 → 38.
- Guide chapter 3: Wear step, "What the materials look like" with the sheet (`docs/img/material_sheet.jpg`), new
  panel picture `panel_3_looks.png`. Tooltip check: 470 ok, 0 missing.

**Tested and measured** (web machine, 4 cores, no graphics card, processor):
- Render time, test crane (`test_crane_a.step`, Product light look, HD 1920 × 1080, Cycles *Preview* on the processor;
  EEVEE frame, software OpenGL), same scene, `main` vs. this branch: Cycles **114.5 s → 115.2 s (+0.6 %)**, EEVEE
  **44.3 s → 45.0 s (+1.6 %)**. With wear 0.4 on every group: Cycles 163.8 s (+43 %), EEVEE 49.4 s (+10 %) – the
  bevel and AO rays; wear is off by default and costs nothing at 0.
- Material sheet, Cycles 1200 px 32 samples: 21.7 s before, 21.6 s after (12 materials).
- Before/after sheets (generic shapes): `tasks/img/0046_before_cycles.jpg` / `0046_after_cycles.jpg`, EEVEE
  `0046_before_eevee.jpg` / `0046_after_eevee.jpg` (glass now see-through), new materials `0046_new_cycles.jpg`,
  wear 0.7 `0046_wear07_cycles.jpg`.
- Tests: `tests/test_materials_look.py` (28: ids/numbers, keys, brief materials, CAD names, every material builds with
  and without wear, axes, EEVEE glass output, wear slider rebuilds, old project saved without look version → load
  rebuilds with the same groups and colours). Locally also test_core, test_part_types(_blender), test_pccheck,
  test_user_guide, test_updates: pass. PC check line `looks.materials` run locally (bpy module): OK, 7.5 s.
- GitHub runs: 2. Run 1 (42542385670) red in real app ui: `ui_test_faces.py` "undo takes the painting back" – its
  "click on the side panel" hit the middle of the panel's bottom rows, which the new Wear row had moved onto a
  button; that button's own undo step was undone instead of the painting. Fixed in the test (click the panel's
  empty right margin), 10/10 locally. Run 2 on the merged commit: green, then `main` fast-forwarded (reuse).

**Open points / follow-up tasks:**
- Part library (not touched, as the brief says): "Chrome rods & linear shafts" still get *Chrome*, "Shafts" and
  "Linear guides" *Steel, machined*. Switching them to *Hydraulic chrome rod* / *Steel, ground* is a one-line change
  each in `core/part_types_data.py` (Part library lane).
- `core/chips.py` `_MATERIAL_KEYS` (not touched): the four new ids are not in it, so a workpiece with *Steel, ground /
  turned* or *Cast iron, painted* gets the default (ALU) chips. Add "steel_ground"/"steel_turned"/"chrome_rod":
  STEEL and "cast_iron_painted": CAST_IRON (Machining lane).
- The owner should judge the looks on his RTX 3090 with the PC check line (larger sheet) and a real machine; the
  strength of the marks is one number per material in `materials_lib.py`.
- Wear in EEVEE shows only the corner dirt (no Bevel node in EEVEE).
