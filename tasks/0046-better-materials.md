# 0046 – Better materials: real metals, machined surfaces, paint with wear

**Who:** worker · **Status:** running · **Branch:** `claude/fervent-bardeen-gdfzcs`
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

- [ ] New and improved materials as in 1–3; every existing id still works; new ids numbered.
- [ ] Wear slider (default 0) per group, or a reason in the report why wear was left out.
- [ ] Render time measured before/after on the same scene (Cycles HD still, EEVEE frame, on the web machine; name
      it): at most ~10 % slower, or the report says which material costs more and why it is worth it.
- [ ] Old-project test: a 0.2.34 project opens with new looks, same groups and colours.
- [ ] Material sheet before/after in the report; PC check line added (`MIN_LINES_FULL` raised).
- [ ] Tests for the material definitions, the CAD-name mapping and the rebuild of old materials; tooltip check 0
      missing; GitHub green; merged and released; `TASKS.md` updated; report filled in.

## Not in this task

Chip, workpiece-cut and surroundings materials (other lanes). Image textures or downloaded material packs (licences,
size). Per-part wear painting by hand. Decals.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
