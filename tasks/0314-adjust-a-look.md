# 0314 – Adjust a look: a few plain sliders per material, saved as your own; the cost of each look measured

**Who:** worker · **Status:** done – 0.2.245 · **Branch:** `task/0314-adjust-a-look`
**Started by:** lead, 23 Nov 2026 (owner 21:14: "Pre-made node textures? That are later editable by the user, or
editable by a pre-made menu. How are the current textures made (procedural)? Or are there better ways, or ways better
for performance?") · **Model:** Opus · effort Medium
**Area:** Looks lane – the picker window of 0273 (an **Adjust** part on its right side), `core/materials_lib.py`
(which keys a user may change and their safe ranges), `blender/materials.py` (the node group's inputs named plainly),
`blender/material_sheet.py` / `tools/material_sheet.py` (the cost sheet), tests, guide.
**Not:** new finishes (0274), the picker itself (0273), surroundings' textures (study 0311 point D).

## Goal

Every ready-made look can be changed without knowing nodes: open the material picker, pick a look, move a few sliders
with plain names, see it change on the model, keep it as "my material". An animator can still open the real nodes.
And the owner knows which looks cost render time.

## Background

- All looks are **procedural**: `core/materials_lib.py` describes each as Principled BSDF values + extras (variation,
  bump, orange peel, machining marks read from the part's own axes, cable looks, marine weathering); `blender/
  materials.py` builds the nodes. Reason: STEP parts have no UV maps and long thin triangles, so image textures would
  stretch; procedural looks have no resolution limit, no files, and take any RAL colour. Image textures are used for
  decals, 360° photos, the photo ground, and the 3D page's bake (a 0.2 m tile per look).
- 0273 adds "Save as my material" and "From a Blender material"; it has no simple way to *change* a look.

## What to do

1. **Adjust** in the picker (right side, under the large picture): per look only the sliders that mean something for
   it – Colour (RAL / hex / picker), Shine (roughness), Metal ↔ paint, Wear and edges, Dirt / dust, Pattern size and
   Direction (marked finishes, knurls), Relief strength, Clear coat. Live on the model's group and on the large picture;
   *Reset*; *Save as my material* (0273's own / department / company folders). Safe ranges so nothing turns black or
   glowing.
2. **For experts**: *Open in the shader editor* (Full access) with the node group's inputs named as the sliders.
3. **Cost of each look**: render every look on the material sheet with Cycles at fixed samples and time it (web machine,
   CPU – say so; the RTX 3090 as an expectation); mark looks that cost clearly more than plain paint with a small
   "slower" badge in the picker; the numbers in the report. If one look is clearly too slow, propose a cheaper build.
4. Guide (Looks: Adjust a look), function entry `looks.adjust` (`since=`), a tour stop, a Full PC-check line
   `looks.adjust` (a slider change gives the node value the spec says).

## Design (worker, 25 Nov)

- **Five new group settings** (`FRMaterialGroup.adj_shine` −1…1, `adj_metal` −1…1, `adj_dirt` 0…1, `adj_relief` 0…2
  (1 = as made), `adj_coat` 0…1); Colour, Wear, Rust and a finish's Pattern size / Direction are the group's existing
  fields. `core/look_adjust.py` (no Blender): the sliders (names, ranges, defaults, tooltips), which ones mean something
  for a look (`applies`), clamping, the key text (`key`), the formulas in plain Python (tests).
- **One shared node group "FR adjust"** (`blender/look_adjust.py`) with plainly named inputs: Colour / Metallic /
  Roughness / Normal / Geometry normal / Coat in, **Shine, Metal ↔ paint, Dirt, Relief, Clear coat** as the sliders;
  out Colour / Metallic / Roughness / Normal / Coat. `materials.build_nodes(adjust=)` puts one node "FR adjust" between
  the look and the Principled BSDF only when a value is not its default (or the group was opened in the shader editor):
  untouched looks stay exactly as they are (same nodes, same render time). `mat["fr_adjust"]` = the key; `is_current`
  compares it.
- **Live**: a slider's update sets the node's input when the node is there (no rebuild); otherwise one rebuild.
- **Own materials**: `changes.adjust` = {shine, metal, dirt, relief, coat} (only values that are not the default);
  format 1.1 (an addition; 1.0 apps note it as unknown and leave it out). Picking an entry gives the group the entry's
  adjust values (defaults for built-ins). **Reset** = the picked entry's own values again (colour of a colour-taking
  entry stays the group's).
- **Picker**: under Use for … an "Adjust" box when the group uses the picked entry; the large picture is rendered
  again in the background Blender (the picture runner) 0.8 s after the last change.
- **Open in the shader editor** (`fresing.look_nodes`, Full access only): keeps the node, selects a part of the group
  and opens a window with the Shader Editor.
- **Cost**: `tools/look_costs.py` renders every library material on the picture swatch (Cycles, CPU, fixed samples),
  writes `fresing_render/data/look_costs.json` (time / plain satin paint); `core/look_adjust.slower()` → the "slower"
  badge (≥ 1.5 x) in the grid and the details.
- No subagents (medium effort); an independent tester only if time allows.

## Done when

- [ ] Adjust sliders per look, live, Reset, Save as my material (tests: the saved file holds the changed keys)
- [ ] Open in the shader editor (Full access only)
- [ ] Cost table of every look; "slower" badge where it applies
- [ ] Tests added/updated; full suite passes; screenshots checked; owner's test steps in the report; merged, version,
      release

## Not in this task

New finishes (0274), the picker (0273), surroundings (0311).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 25 Nov 2026 – 0.2.245

**What changed:**
- `core/look_adjust.py` (sliders, ranges, which apply per look, formulas, cost table); `blender/look_adjust.py` (node
  group "FR adjust" with inputs Shine / Metal ↔ paint / Dirt / Relief / Clear coat; live update; keep for the editor;
  open the shader editor in a new window); five `adj_*` group settings in `props.py`; `materials.build_nodes(adjust=)`
  + `is_current` (the node only when a slider moved or the material was opened in the editor).
- Materials window: Adjust box under Use for … (only for the group's own material), Reset (`fresing.look_reset`),
  Open in the shader editor (`fresing.look_nodes`, Full access only), large picture re-rendered 0.8 s after the last
  change, clock badge + "Slower to render: about N x" line.
- Own materials: `changes.adjust` (format 1.1; a 1.0 app notes it as unknown and leaves it out); picking an entry
  sets its sliders (built-ins: defaults); Reset = the entry's values, Wear, Rust and finish settings (paint keeps the
  group's colour).
- `tools/look_costs.py` → `fresing_render/data/look_costs.json`; guide "Adjust a look"; function `looks.adjust`; tour
  stop `look_adjust` (set "looks"); Full PC-check line `looks.adjust`; real-app picker test +5 checks (28).

**Tested and measured** (4-core web machine, no graphics card):
- `tests/test_look_adjust.py` (14 tests incl. the node wiring vs the formulas) + picker / pictures / looks / functions
  tests: 350 passed. Tour: stop checks of the looks set + completeness, clash of the set: pass. PC-check line
  `looks.adjust`: OK (4 s). Real app `--only materials`: 28/28 (Adjust live, picture remade in 5.7 s, the shader editor
  window opens in Full access). Screenshot of the Adjust box looked at.
- **Cost** (Cycles on the processor, AMD EPYC web machine, 4 threads, picker swatch 256 px, 64 samples, best of 3;
  plain satin paint 1.64 s = 1.0): slower ≥ 1.5 x – frosted acrylic 1.67, clear PU tube 1.62, eroded blade paint 1.57.
  Next: polycarbonate 1.49, marine growth 1.49, leather 1.47, spangle 1.41, grille 1.36, served cable 1.35. Fastest:
  clear glass 0.73, chrome 0.80. Plain paint + Wear 0.6: 1.49 x; + Adjust (shine, dirt, coat): 1.00 x. On the RTX 3090
  the ratios are expected to be similar or smaller (an expectation, not measured). No look is so slow that a cheaper
  build is needed now; the see-through ones are slow because of transmission bounces (expected).
- GitHub runs: see below.

**Owner's test steps (on your PC, after Update now):**
1. Open a project, **3 Looks**, pick a group, **More materials…**.
2. Click its material twice (or click it once if it is already the group's): under **Use for <group>** you see
   **Adjust** with sliders. Move **Shine** and **Dirt**: the parts change at once; after a second or so the large
   picture shows the change.
3. Press **Reset**: the sliders go back. Move them again, **Save as my material…**, give a name: another group that
   uses it gets the same sliders.
4. In the workspace **Full access** press **Open in the shader editor**: a window with the nodes opens; the node
   **FR adjust** has the same names.
5. Look for the small clock next to "Acrylic, frosted" in the window: that look renders slower.

**Open points / follow-up tasks:**
- The milled workpiece's cut faces keep their own look (no Adjust on them).
- A paint scheme switch keeps the group's sliders (like Wear today).
- Subagents: none (medium effort; no Windows-only code). Independent tester skipped.
