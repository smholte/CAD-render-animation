# 0155 – Props for scale and the human figure: detailed and realistic

**Who:** worker · **Status:** done 16 Nov 2026 (0.2.124) · **Branch:** `claude/determined-cori-ilms3e`
**Started by:** lead chat, 16 Nov 2026 (owner: props, hand and human more detailed and realistic; a full human doing a
manual tool change) · **Model:** Opus · effort Medium · **Place:** Claude Code on the web, environment "CAD-render-animation".
Subagents allowed (CLAUDE.md section 2).
**Area:** Surroundings lane: `core/surroundings.py` (`PROPS`, `person()`, `prop_shapes`, sizes), `blender/surroundings.py` (props' meshes and materials), `ops_surroundings.py`, a small assets folder if a CC0 base is used, their tests.
**Do not edit:** the sea (`core/sea.py`) except where props sit on it; the demo model maker (0153); the Web 3D lane (0142/0143); `toolchange.py` (0156); milling (0146).

## Goal

The props that give a machine its scale – the person, pallet, forklift, car, container, etc. – look real in a close render instead of blocky stand-ins, and the person can be posed.

## What to build

1. **Person:** a realistic human figure (proportions, face without a real likeness, hands, work clothes: overalls or
   hi-vis vest, safety shoes, helmet optional, gloves optional), a few heights (1.65 / 1.75 / 1.85 m), a simple rig
   with **poses**: standing, walking, pointing, hands on a control panel, kneeling, operator at a machine; skin and
   cloth looks with subtle variation; 2–3 outfits (workshop, offshore orange, office).
2. **Every other prop** in `PROPS` gets the same care (bevels, real dimensions, decals without brands, wear): check the
   list and say which ones changed; add 2–3 useful ones for offshore and workshop scenes (e.g. a pallet with crates,
   a gas bottle rack, an IBC tank, a toolbox trolley) if missing.
3. Levels of detail: a light version for far away / many copies and the detailed one for close shots, chosen by
   distance to the camera at render (or a setting).
4. Old projects: their props update to the new look on load (or a "Refresh props" button) without moving.

## Rules

- **Licences:** only models you make in code, or openly licensed bases that allow redistribution in a GPL app and a
  public repository – e.g. Blender Studio's *Human Base Meshes* bundle (CC0) or MakeHuman exports (CC0); check and
  name the licence in `site/CREDITS.md` / the extension's credits. No real person's likeness, no branded clothing or
  tools (no logos), no downloaded manufacturer models (CLAUDE.md section 6).
- Keep the shipped size small: measure what the extension zip grows by (aim ≤ +5 MB); light meshes (props are seen
  from afar; the hand / human close up only in tool changes).

## Done when

- [ ] Tests (sizes, poses keep feet on the floor, prop count and names unchanged for old projects, LOD switch); render
      sheet of all props and poses at the same scale.
- [ ] Tooltips, guide (with new pictures of its section), PC-check line / tour stop, function list; GitHub run green;
      merged; version (CLAUDE.md section 7); report with small before/after pictures in `tasks/img/0155_*`, triangles
      and zip size before/after.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 16 Nov 2026 (branch `claude/determined-cori-ilms3e`, the session's assigned
name instead of `task/0155-…`). Note: task 0163's finishing commit (338742b) had set **this** task to "done (0.2.122)" in
`TASKS.md` instead of 0163 itself; corrected first (453b23c).

**What changed:**
- `core/props_detail.py` (new, no Blender): the person – a skeleton of 17 bones posed by joint angles (forward
  kinematics), lofted skin round each bone, a face without a likeness (nose, eyes, brows, ears, lips), hands with four
  fingers and a thumb that curl per pose, safety shoes with soles, hair or a helmet; 6 poses (standing, walking,
  pointing, hands on a panel, kneeling, operator), 3 heights (1.65/1.75/1.85 m, top of the head without helmet), 3
  outfits (workshop navy, offshore orange + reflective bands, office shirt/trousers + hi-vis vest), gloves, 4 looks
  (skin tone + hair). After posing the figure is lifted so its lowest point is on z = 0. Detailed container
  (trapezoid-corrugated sides, corner castings, rails, fork pockets, two door leaves with ribs, 4 locking bars with
  cams, handles, a blank data plate), pallet (EPAL boards and blocks with chamfers, two layers of boxes with tape),
  barrier (one bent tube frame, mid rail, feet with rubber pads, reflective marks). New: IBC tank, gas bottle rack
  (4 bottles, shoulders by EN 1089-3 colours, valve guards, chain), tool trolley (6 drawers, handles, mat, push
  handle, castors). Every prop in DETAILED and LIGHT. New shape `Loft` in `core/surroundings.py` (+ `place`,
  `footprint`); `prop_shapes(kind, lod, **settings)`; the old shapes are `plain_prop_shapes` (old container / pallet
  / barrier = the light versions).
- `blender/props_scale.py` (new): one mesh per prop holds both levels (face attribute `fr_lod` 1/2); the Geometry
  Nodes modifier "FR prop detail" (Active Camera → distance) deletes one of them – no handler, no driver, works in the
  queue and with scripts off. Scene settings `props_detail` (Auto by distance / Always detailed / Always light) and
  `props_far` (30 m). Person settings `Object.fresing_person` (pose, height, clothes, helmet, gloves, look) rebuild the
  mesh in place (name, place, turn kept). `upgrade` in `load_post` (`handlers.py`): props without `fr_prop_ver`
  get the new mesh, same object, name, place. Procedural materials: skin (subsurface), cloth (weave + folds bump,
  sheen), hi-vis, reflective, worn paint (rust spots, dirt near the floor), wood, HDPE tank, metals.
- Panel 5 Scene & Render > Props for scale: 7 buttons, "Selected person" box, fold "Detail".
- Tour stop `props` (new set "Props for scale and people", MIN 66), PC-check line `scene.props` (MIN_LINES_FULL 87),
  function entries `scene.props` (tour + PC check linked) and new `scene.props_detail` (guide anchor `props-detail`),
  guide section rewritten with `props_lineup.jpg`, `props_people.jpg` and a new `panel_5_props.png`;
  `tooltip_report.py` knows `FRPersonSettings` (0 missing). Shared set-up `props_scale.line_up` / `check_line_up`.

**Tested and measured** (4-core web machine, no graphics card):
- `tests/test_props_scale.py` (new, 32 tests): heights ±1 cm, every pose's feet (kneeling: knee) on the floor, all
  pose × outfit × level × gloves build, levels the same size, old prop list and names unchanged, one mesh with both
  levels, LOD by distance and by setting, person settings rebuild in place, an old project (props saved without the
  new data) reopened → same names / places / count, detailed meshes, not rebuilt twice; panel draws the person box.
  `test_surroundings.py` (updated for 7 props), `test_tour.py` + the new set's clash test, `test_functions.py`,
  `test_user_guide.py`: 144 passed locally. PC-check line `scene.props` OK (render 1.7 s, adding everything 1.0 s).
- Triangles detailed / light (before = the old single version): person 6,460 / 2,120 (before 544), container 1,916 /
  268 (268), pallet 1,888 / 252 (252), barrier 1,032 / 180 (180), IBC 2,832 / 64, gas rack 1,784 / 396, trolley
  1,668 / 196. A prop beyond 30 m costs what the old one did.
- Size: the two new modules + the two guide pictures are 118 KB zipped (aim ≤ 5 MB); no meshes or textures shipped.
- GitHub runs: see below.

Pictures: `tasks/img/0155_before.jpg`, `tasks/img/0155_after.jpg` (person, pallet, barrier), the full sheets in
`docs/img/props_lineup.jpg` and `docs/img/props_people.jpg` (every pose in all three outfits, same scale).

**Subagents:** none (one area, and the pieces depend on each other's shapes); an independent tester was skipped to
save usage – nothing Windows-only.

**Open points / follow-up tasks:**
- The person is a stylised, clean figure (lofted shapes), good at scale and in medium shots; a very close portrait
  still reads as a mannequin. A CC0 base mesh (Blender Studio Human Base Meshes, MakeHuman) with a real rig would be
  the next step – not reachable from the web machine, and it needs skin weights per pose (0156 / 0157 may want it).
- Poses are fixed choices (no free bone posing); 0157 (walk paths) can drive the same skeleton by its angles
  (`core/props_detail.skeleton(pose_dict)` takes any angles).
- No forklift or car props (the brief's list named them; `PROPS` never had them) – a small follow-up if wanted.
- A linked duplicate person (Alt+D) shares its mesh: changing one's settings gives it its own mesh, the other keeps
  the old one named "… (old)".
