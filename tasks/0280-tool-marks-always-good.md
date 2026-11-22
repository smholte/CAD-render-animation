# 0280 – Tool marks look as good as Learning-hub stop 60 everywhere, with no set-up

**Who:** worker · **Status:** done (0.2.205) · **Branch:** `task/0280-tool-marks-always-good`
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

- [x] Report says why stop 60 looked right and the others didn't
- [x] No moiré, no black walls, no sand noise, floor arcs visible – in every set above, defaults only (picture sheet)
- [x] `core/toolmarks.py` and its tests still mirror the material; render-compare tests updated
- [x] Tour stop 60 and the Machining stops' `changed=` (`python3 tools/tour_versions.py --record`); guide pictures
- [x] Full suite + GitHub run green; report filled in; merged, version, release (CLAUDE.md section 7)

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 21 Nov 2026 (worker, Opus · High). Released as **0.2.205**.

**Why stop 60 looked right and the others didn't** (measured on the tour sets, renders on the 4-core web machine):
1. **Stop 60 cheats with Mark size 7 and a camera 12.5 cm away.** Its face mill feeds 0.3 mm per turn, × 7 = 2.1 mm,
   which is about 30 px on the picture. Every other set uses Mark size 1 with 0.03–0.15 mm per tooth and a camera
   0.3–1.5 m away: 0.05–0.5 px per mark. The old shader faded the ridges out below 1–3 px, so **floors showed no
   marks at all**, only the sheen (the owner's point 4).
2. **The old fade looked only at the distance, not at the angle.** A pocket wall seen from above is squeezed 3–10 ×,
   so its lines were drawn at 0.2–1 px while the fade still let them through: **moiré stripes** (point 1), and the
   0.08 mm step-down line (≈ 0.3 px) **speckled** along the top of the walls (point 3, the edge strips).
3. **Walls were a mirror.** The cut faces are metal, roughness 0.2; a vertical wall mirrors the floor/room below the
   horizon. EEVEE (no ray tracing) takes that from the world, which is black there: **black walls**, at any roughness
   I tried (0.2–0.5). Cycles mirrored the dark-blue backdrop: dark blue walls and blue-ish floors (point 2, point 4).
   Stop 60's camera looks low over a faced top, which mirrors the bright lamps.
4. **The coolant set made it worse:** the wet sheen set every wet face to roughness 0.12 and colour × 0.58 – a
   darker mirror – and the drops on the clear film caught the lamps as **white specks** (the "sand").
5. Not a look problem but found on the way: since the VMC test mill (0249) the table carries the block 90 mm away at
   the end of stop 60's program, so the stop's own camera (and the guide picture made from it) showed the uncut top.

**What changed:**
- `core/toolmarks.py` + `blender/toolmarks.py` (node group v3, rebuilt in place in old projects): marks drawn at a
  **level of detail** – every mark up close, every 2nd, 4th … further away – chosen so the drawn marks lie 5–10 px
  apart on the picture (`LOD_PX` 5), from the camera distance, the pixel angle and how slanted the face is seen
  (Geometry > Incoming, `slant`); two levels mixed by the fraction, each coarser mark is also a finer one, so
  nothing jumps while the camera moves. Marks drawn more than 3 mm apart fade out by 6 mm (`CAP_FROM`, `CAP_TO`):
  the whole machine shows the sheen. Step-down line ≥ 1.5 px wide, leaning less by as much. **Satin**: walls
  (kinds FLANK, RINGS_WALL) +0.15 roughness and 30 % of the metal diffuse, other cut faces 40 % of that (look key
  `satin`: aluminium 1, steels/brass 0.8, cast iron 0.6, plastics 0). The group now also passes Metallic
  (`materials.build_nodes` links it). Shader nodes only, scripts off fine.
- `blender/coolant.py` (wet sheen v2, an older patch is replaced, not stacked): colour × 0.8, roughness → 0.28; the
  clear wet film keeps the gloss.
- `tour.py`: stop 60's camera rides on the table (X.ASM). Stops 55, 56, 58–60, 62–68 and the functions "Tool marks"
  and "Coolant" `changed="0.2.205"`; `tour_versions.json` recorded.
- Mark size tooltip and the guide's Tool marks / Coolant text; guide pictures `milling_marks.jpg`, `coolant.jpg`,
  `air_blast.jpg` made again. No new setting.
- Picture sheet: `tasks/0280_page/index.html` – per set, before (0.2.201) and after, stop camera / mid / floor
  close-up / wall close-up, EEVEE and Cycles, 480 × 270 px.

**Tested and measured** (4-core web machine, bpy module + xvfb; tour sets of the invented test models):
- New tests: levels keep the drawn marks 5–10 px apart, a slanted face gets a coarser level, two levels meet without
  a jump, fade far, satin per kind, step-line area kept when widened; in the nodes: Level and Fade against the
  formula (straight above, 4 distances, a small picture, a scaled object), ridge and normal at level ≈ 3.6 pixel by
  pixel (mean error 0.03 / 0.005), +1 level at a 60° view, Metallic per kind; coolant: an older wet patch is
  replaced once and goes back exactly. `test_toolmarks*.py`, `test_coolant.py`, `test_machining_fixes.py`,
  `test_milling_shows.py`, the marks tour clash test: all pass.
- `test_sheen_follows_the_arcs` now measures the streak's angle without the floor's satin (its diffuse share makes
  a round glow that blurred the angle to 49° instead of 37°); with satin it still leans the right way and is long.
- `test_queue_render_shows_the_cut`: the slot is clearly visible, but satin cut faces are nearer the block's grey:
  0.18 % of the picture differs by > 25 levels (was ≥ 0.2 %); lower bound now 0.1 %.
- Picture sheet: 12 sets × 8 views before and after. No black walls left in any set, no speckle in the coolant set,
  floor arcs and wall lines visible in every close-up and mid view, no moiré seen.
- GitHub: 3 full runs. Run 1 (code only) red on the queue test above; run 2 green (44960347677); task 0278 took 0.2.204 meanwhile, so main was merged once more and renumbered: run 3 green (44962616395), main fast-forwarded to it.

**Open points / follow-up tasks:**
- The marks' level is set from the render camera's picture size (`Pixel angle`); in the 3D view with another zoom /
  window size they are drawn up to about 2 × finer or coarser than in the render – still a few pixels apart.
- At a coarser level the marks of two straight moves of one face can be off by up to one drawn mark at the seam
  (the moves line up only to the real spacing).
- Pocket walls are lit from above only, so they read mid grey next to light floors in EEVEE; bright, but not as
  bright as floors. EEVEE's screen-space ray tracing (off in the app's looks) would let them mirror the floor.
- Subagents: none (one shader + its mirror; the review was by the picture sheet).

**Owner's check on your PC:** after **Update now** to 0.2.205: Help > Make the Learning hub, then open stops 60, 65,
66, 67 and 68, switch the 3D view to Rendered (EEVEE and Cycles) and orbit close to a pocket wall and a slot floor:
walls bright satin with fine upright lines, floors with arcs, no stripes that wander while you orbit, no black walls.
