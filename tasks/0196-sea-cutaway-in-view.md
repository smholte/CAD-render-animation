# 0196 – Fix: the sea cut-away shows only in renders – make it visible in Solid view and Material Preview

**Who:** worker · **Status:** open – can start (0193 merged, 0.2.148; 0062's pass over the panels is on `main`, 0.2.152) ·
**Branch:** `task/0196-sea-cutaway-in-view`
**Started by:** lead chat, 17 Nov 2026 (owner's screenshots of the demo, 0.2.146) · **Model:** Sonnet · effort Medium ·
**Place:** Claude Code on the web, environment "CAD-render-animation"
**Area:** Sea lane – the cut-away part of `blender/surroundings.py` (`_cutaway`, the sea / seabed / soil-section builds,
`cut_box`), a viewport-only helper (new file if it grows), their tests. Not `section.py` (the parts' cutaway, task 0086).

## Goal

With the sea cut-away on, the owner sees the open box behind the stern – the cable going down, the seabed, the soil
section – while he works in the 3D view, not only in a render.

## Background

- **Owner, 17 Nov 21:02:** in Solid view the sea is one grey sheet over the cut-away (the cameras and the cable under it
  are hidden); in Rendered view the box is open (teal water box, seabed, soil). Screenshots in the lead chat (not
  committed).
- **Cause (lead):** the cut-away is a shader effect only – `surroundings._cutaway` mixes the sea's material to
  see-through inside the box (task 0081; seabed cut 0148). Solid view does not draw materials; Material Preview may
  or may not honour it (check and say).
- The cut-away's box: `surroundings.cut_box(scene)` (origin, aft direction, length, width).

## What to do

1. Find the cheapest way the 3D view (Solid and Material Preview) shows the box open while renders stay exactly as
   now: e.g. a viewport-only Geometry Nodes step on the sea (and the seabed where `sea_cut_ground` is on) that deletes
   the faces inside the box (`show_render` off), or the same cut done in the mesh with the shader kept for renders.
   It must follow the box when the panel's numbers change and ride the vessel motion as the shader's box does.
2. Cost: measure the per-frame cost of the view cut on the demo (it must stay well under 1 ms a frame) and say it.
3. Renders unchanged: a Cycles render of the tour's cut-away stop before / after equal (the picture check the tour
   already uses).

## Rules for this task

- Tests that **failed before**: in Solid view (or the evaluated viewport mesh) no sea face lies inside the box; the
  render's evaluated mesh unchanged; the box moves with the panel's numbers. Real-app picture of the Solid view before
  / after (invented demo / test model only) in `tasks/img/0196_*`.
- Guide: the cut-away section says it shows in the 3D view too. Update the tour stop's "what you should see" if needed.
- Normal finish (sections 2 and 7); take the next free version when you merge.

## Done when

- [ ] The cut-away box is open in Solid view and Material Preview; renders the same as before.
- [ ] Tests and the per-frame cost in the report; GitHub green.
- [ ] Report below filled in; TASKS.md row moved to Done with the version.

## Not in this task

The web page's cut-away (Web 3D lane), the clip distance of the view (0193), the parts' section view (0086).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 18 Nov 2026.

**What changed:** new `blender/sea_view_cut.py`: a Geometry Nodes modifier "FR view cut" (`show_render` off, last in the
stack) on the sea and, with the ground cut, the seabed; `surroundings._build_under_water` puts it on and it takes the
box from the same numbers as the shader (so it follows the panel and the cable; it is rebuilt with the surroundings).
Simple: thin slab + Mesh Boolean, exact edge. Detailed: the points inside the box are let down (depth + 4 m for the
sea, 0.3 m for the seabed) under what lies beneath, so no mesh copy per frame; the edge follows the sea's own mesh
(about 1 m) and a wall stands round the box. The web 3D export reads the base mesh: unchanged. Guide: cut-away section.
Pictures: `tasks/img/0196_solid_before.png` / `_after.png` (Workbench render of the viewport-evaluated mesh with an
invented vessel, not a real-app screenshot; the edge shows spikes where the sea's radial mesh is stretched).

**Tested and measured** (4-core web machine, invented vessel, Detailed, moving waves, ground cut): view cut costs
0–0.5 ms per frame (6.5 ms with vs 6.5–7.0 ms without; a first version that deleted faces cost +3.5 ms, the Boolean
on the Detailed sea 400 ms per update – both dropped). `tests/test_sea_view_cut.py` (8 tests): nothing of sea/seabed
in the box in the view, outside unchanged, follows the panel's numbers, off without the cut-away, cost, Cycles renders
equal to the last digit with and without the modifier. 103 tests of the sea / surroundings files pass.

**Open points / follow-up tasks:** Material Preview not looked at in the real app (no graphics card here; the cut is in
the mesh, so it shows there as in Solid). Stones and hull foam are not cut in the view. The wall spikes could be
smoothed with a finer sea mesh near the box. Real-app picture of the view still to take on the owner's PC.
