# 0280 – Tool marks look as good as Learning-hub stop 60 everywhere, with no set-up

**Who:** worker · **Status:** open – can start · **Branch:** `task/0280-tool-marks-always-good`
**Started by:** lead, 21 Nov 2026 (owner 22:00, four screenshots of 0.2.197 – the coolant set's pockets, a close-up of
a pocket wall, a slot with its path lines, and stop **60. Tool marks on cut faces**: "cutting textures needs some
refining, it can look really good like on 60 in the Learning hub, but others less. This needs to be really good
directly with no additional setup. A user is allowed to fine-tune if settings allow that, but it should in all cases
look very nice.") · **Model:** Opus · effort High
**Area:** Machining lane – `blender/toolmarks.py` (the cut-face material), `core/toolmarks.py` (formula + its mirror),
`blender/machining.py` only where it writes the `fr_mk_*` attributes, the Mark size setting (`props.py` ~line 1732,
default only); tests, real-app test, guide pictures, CHANGELOG. **Not** `blender/liquid.py` / coolant (coolant B, same
lane, comes after this or beside it if the lead says so).

## What the owner sees (his screenshots, not in the repository)

Stop 60 (Ø50 face mill arcs, Ø10 pocket floor arcs, walls) looks very good: crisp arcs, real depth, bright satin
aluminium. The other sets don't:
1. **Moiré** – on pocket and slot walls the lines (one per tooth, kind 2 FLANK) are far finer than a pixel, so a
   close-up shows a coarse diagonal stripe pattern that wanders over the wall instead of fine lines.
2. **Black walls** – in the coolant set's pockets the walls read as a dark, almost black mirror (they reflect the
   dark surroundings); machined aluminium walls are bright satin grey.
3. **Grainy / sandy** look on walls and the edge strips (white speckle) instead of clean marks.
4. **Floors with hardly any marks** – a slot floor under the path lines shows a blurred blue-ish band, no clear arcs.

## What to do

1. **Find why stop 60 looks right and the others don't** (mark spacing vs. distance, light, roughness, the kind each
   face got, Mark size, EEVEE vs. Cycles). Write it in the report in plain words.
2. **Make the default always look like stop 60**, at any distance (whole machine, part, close-up), in EEVEE and
   Cycles, Live preview and final render, with no setting touched:
   - marks finer than ~2 px fade smoothly into the plain machined look (no moiré, no shimmer while the camera moves) –
     shader nodes only, it must work with scripts off;
   - walls and floors keep a bright satin machined-aluminium look; the marks change the roughness / bump, they never
     turn a face dark;
   - no sand-like noise; floor arcs and wall lines readable at the distance a person would look;
   - the edge strips at the top of a pocket / slot look like a clean edge, not speckle.
3. Settings the user already has (Mark size, the look strength if there is one) keep working as fine-tuning on top of
   a good default. A new setting only if it is really needed; then a tooltip, the guide and the Settings window's page.
4. **Check every place that cuts:** all Machining stops of the Learning hub (55–69), the test mills (0249's VMC
   included), the coolant set, the gantry / double-arm / operator sets (0223). Never a Fresing 400 model.
5. A before / after picture sheet per stop (far, mid, close-up; EEVEE + Cycles) in `tasks/0280_page/` – invented test
   models only – so the owner can judge the look in one view.

## Done when

- [ ] Report says why stop 60 looked right and the others didn't
- [ ] No moiré, no black walls, no sand noise, floor arcs visible – in every set above, defaults only (picture sheet)
- [ ] `core/toolmarks.py` and its tests still mirror the material; render-compare tests updated
- [ ] Tour stop 60 and the Machining stops' `changed=` (`python3 tools/tour_versions.py --record`); guide pictures
- [ ] Full suite + GitHub run green; report filled in; merged, version, release (CLAUDE.md section 7)

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**

**Owner's check on your PC:**
