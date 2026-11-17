# 0196 – Fix: the sea cut-away shows only in renders – make it visible in Solid view and Material Preview

**Who:** worker · **Status:** open – starts **after 0193 is merged** (both change `blender/surroundings.py`) ·
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

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
