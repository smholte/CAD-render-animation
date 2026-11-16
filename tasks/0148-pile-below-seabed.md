# 0148 – Sea cut-away also cuts the seabed: the monopile visible down to its toe

**Who:** worker · **Status:** done (0.2.114) · **Branch:** `task/0148-pile-below-seabed`
**Started by:** lead chat, 16 Nov 2026 (open point of 0128) · **Model:** Sonnet · effort Medium ·
**Place:** Claude Code on the web, environment "CAD-render-animation"
**Area (Scene & Render – sea):** `blender/surroundings.py` (the seabed and `_cutaway`), `core/surroundings.py` /
`core/sea.py` where the seabed is laid out, `tools/site_projects/iea15*.py` + `site/render_kit/projects/iea15_offshore.json`
(the "Seabed" shot), their tests, the guide's sea section. **Do not edit:** `fr_page.js` / web export (0142, 0143),
`paths*`, `demo*`, `tests/test_demo_*` (0145), milling (0146).

## Goal

With the sea cut-away on, the cut goes on into the ground: a soil section (a few layers, sand → clay, as a look) where
the box cuts the seabed, so the offshore turbine's monopile shows below the seabed down to its toe, with the scour
protection on top.

## Background

0128's report: the "Seabed" camera and a 90 m cut-away box round the pile exist, but "the pile below the seabed stays
hidden: the seabed is an opaque surface, so it cannot be shown without changing the sea code (0125's files)". 0125 is
done; the sea lane is free.

## What to build

1. The seabed becomes a solid of the project's chosen depth (or keeps a surface plus a cut face) that the cut-away box
   cuts like the water; the cut faces get a soil look (layers, a little noise; one material, plain-Python formula for
   the test as other looks have).
2. Parts below the seabed (piles, J-tubes, a buried cable later) are drawn inside the cut; outside the box the seabed
   still hides them.
3. A setting "Show the ground in the cut-away" (on by default when a part reaches below the seabed), tooltip, guide.
4. The turbine's sheet: the Seabed shot shows the pile to its toe; the kit sheet updated (the site-kit run green).

## Done when

- [ ] Tests: a pile that goes 30 m into the ground is visible in the cut (render or ray test), hidden outside it; old
      projects with a cut-away open unchanged (setting off for them).
- [ ] Small render of the turbine's Seabed shot (stand-in turbine) in `tasks/img/0148_*`.
- [ ] Tooltips, guide, PC-check line or tour stop, function list; GitHub run green; merged; version.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 16 Nov 2026 (Sonnet).

**What changed:** the seabed is see-through inside the cut-away box and a soil section (`core/sea.py` `SOIL_LAYERS`,
material "soil section", `surroundings._soil_mesh`) shows the box's walls and floor, as deep as the lowest part + 5 m.
Setting `sea_cut_ground` (goes on by itself in `_sea_cutaway_changed` when water level > water depth; off for old
projects; settings key unchanged when off). UI rows for water depth, clarity, cut-away, ground. Turbine sheet: the pile
below the seabed shown, water level 75 m, `cutaway.ground`, "Seabed" camera inside the ground. Guide, function list,
PC-check line `scene.sea_ground` (MIN_LINES_FULL 83). Picture: `tasks/img/0148_seabed_shot.png` (stand-in turbine, Cycles
CPU draft, dark because the pit only gets sky light through the box).

**Tested and measured** (4-core web machine, invented vessel + red pile; stand-in turbine): `tests/test_sea_cutaway.py`
18 passed (pile 30 m in the ground visible in the cut, hidden with the ground off and behind the wall outside the box;
soil colours per layer = `core.sea.soil_colour`; old key unchanged); site turbine tests 88 passed; tooltip check, function
and guide tests passed. The PC-check line and the full GitHub run were not run locally.

**Open points / follow-up tasks:** the kit run on `site-kit` has to be started for the owner's renders; the pit is dark
in the Seabed shot (the owner may want a work light there).
