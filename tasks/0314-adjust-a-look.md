# 0314 – Adjust a look: a few plain sliders per material, saved as your own; the cost of each look measured

**Who:** worker · **Status:** open – waits for 0273 (and 0274) · **Branch:** `task/0314-adjust-a-look`
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

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
