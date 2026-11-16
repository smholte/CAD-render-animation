# 0148 – Sea cut-away also cuts the seabed: the monopile visible down to its toe

**Who:** worker · **Status:** running · **Branch:** `task/0148-pile-below-seabed`
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

**Chat / date:** Claude Code on the web (Sonnet), 16 Nov 2026 – branch `task/0148-pile-below-seabed`, version 0.2.114. NOT merged:
the lead's note on `main` says two sessions ran this task by mistake and a review session picks one.

**What changed:** the cut-away box is also taken out of the seabed: the seabed material is see-through inside the box
and a soil section (4 walls + floor, layers sand / silty sand / stiff clay / dark clay by depth, noise on the
boundaries; `core/sea.soil_colour` is the formula) shows the ground, deeper than the lowest part (`sea.ground_depth`).
New setting `sea_ground` "Show the ground" (default on; only acts when a part reaches below the seabed; a project saved
before gets it off by `surroundings.upgrade_ground`, a stamp on the root). Water depth, cut-away and clarity now have
rows in 5 Scene & Render. Turbine sheet: the 45 m of monopile is shown (no hidden note), water level 75 m, depth 30 m,
"Seabed" camera looks down into the pit (hand-edited in `iea15_offshore.json`, same as the maker's output; not re-made
with the owner's STEP). PC-check line `scene.sea_ground`, function `scene.sea_ground`, guide section `sea-ground`.

**Tested and measured:** `tests/test_sea_cutaway.py` (18 tests, bpy module, Cycles CPU 96 px): a 34 m pile in the box
shows 1.5x or more red pixels with the ground on than off; a pile outside the box stays hidden (0 px with water, same as
the seabed-only count without); old-project upgrade; settings key unchanged with it off. Site-turbine tests updated.
GitHub run 43826862436 on e00077b: all green (full mode, 32.7 min). Picture: `tasks/img/0148_pile_in_the_ground.jpg`
(stand-in pile, not the turbine). Not run: real Blender locally (download refused), the site-kit run, a render of the
real turbine's Seabed shot.

**Open points / follow-up tasks:** the cut-away settings had no panel rows before; I added them (reviewer may want them
elsewhere). The pit is dark in a narrow box (sun only from above). Release not made (not merged).
