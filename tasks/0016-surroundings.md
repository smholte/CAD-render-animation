# 0016 – Surroundings: offshore, quayside and factory backgrounds

**Who:** worker · **Status:** done · **Branch:** `task/0016-surroundings`
**Started by:** lead chat, 4 Nov 2026 · **Lane:** Scene & Render · **Area:** `blender/world.py`,
new `blender/surroundings.py` (+ data in `core/` if useful), `blender/prefs.py` (library folders),
the **5 Scene & Render** part of `blender/ui.py`, `blender/ops_main.py` (background operators
only), `blender/props.py` (additive), `tests/`, `tools/` (test helpers).

## Goal

One click puts the machine in a believable place: **offshore** (sea, calm or rough; on a vessel
deck; on a quayside) or a **workshop/factory** (a clean factory hall, a CNC machining hall, an
assembly hall, a warehouse), with a few props for scale (a person, a container, a pallet). The
machine stands on the floor with real contact shadows and reflections.

## Background

- Today 5 Scene & Render offers Background: solid colour, 360° photo (HDRI file), sky,
  transparent; Lighting: built-in studio (an HDR image made in code, `world._studio_pixels`),
  HDRI, sky; a floor with its own colour. The shared library folder (add-on preferences,
  `prefs.library_dir(...)`) already has HDRIs ("360° photos").
- The chats cannot download from most websites, and the repository is public: everything
  shipped must be made in code (procedural modelling/shaders, Blender's Ocean modifier, Nishita
  sky) or be free of rights. Real photos come from the **owner's library**: he can download
  free CC0 360° photos himself (for example from Poly Haven: factory halls, workshops, harbours)
  and drop them in the library folder – write him a short list of good ones and the click steps.
- Renders already take long (owner's first animation: ~15 s per frame at 1440p on the RTX 3090).
  Surroundings must not blow that up: keep a "Simple / Detailed" choice and measure.

## What to build

1. **Built-in 3D surroundings** (made in code, generic): sea surface (calm / rough, foam optional,
   animated waves for videos), vessel deck (steel deck plates, railings, a few containers),
   quayside (concrete, bollards, water), clean factory hall (epoxy floor with walkway lines,
   columns, roof trusses, skylights, light lines), CNC machining hall (as before plus rows of
   generic machine-tool boxes and racks), assembly hall, warehouse (racks, pallets). The machine
   is placed on the floor/deck automatically (lowest point of the model at floor height; centred).
2. **Photo surroundings:** a 360° photo from the library as background with a **shadow catcher**
   floor, so the machine stands in the photo; floor height and photo rotation adjustable.
3. **Props for scale:** person (generic mannequin, 1.8 m), 20 ft container, euro pallet, safety
   barrier; placed with one click next to the machine, movable, hidden in one click.
4. Settings live in 5 Scene & Render under Background (follow the layout rules in `blender/ui.py`:
   choice first, then its settings; rarely used settings in a fold). Saved scenes, templates and
   the render queue (background renders) keep the surroundings.
5. **Tooltips** (new rule, `CLAUDE.md` section 6) for every button and setting in panel
   5 Scene & Render, also the existing ones.

## Done when

- [x] Every surrounding renders in the background queue (tests: build each, render a small CPU
      frame, no missing textures); machine placed on the floor; saved scene/template keeps it
- [x] Render time per surrounding measured on the test machine (small CPU frame, model named),
      Simple vs Detailed, in the report
- [x] List of recommended free 360° photos for the owner + click steps to add them (in the
      report and in `docs/`)
- [x] Real-app click test step and screenshots of panel 5 checked (generic test models only)
- [x] Full suite passes; report filled in; merged and released (`CLAUDE.md` sections 2 and 7)

## Not in this task

- Studio lighting and camera presets, turntable (0017); logo, titles, captions (0018).
- Anything in panels 1–4, 6, 7 (other lanes).

---

## Report (filled in by the chat that did the task)

**Chat / date:** worker chat, 4–5 Nov 2026 (two sessions: the first stopped at its usage limit
with the work uncommitted on disk; the second reviewed it, fixed what follows and finished).

**What changed:**
- `core/surroundings.py` (new, no Blender): the Background choices (stored by number: the old
  four keep 0–3), layouts of the sea, vessel deck, quayside and four halls around a machine of
  any size (keep-out box, default camera's quarter kept free, fixed random seed), props for
  scale (person 1.8 m, 20 ft container, euro pallet with load, safety barrier).
- `blender/surroundings.py` (new): meshes from the layouts under the empty "FR Surroundings"
  (placed under the machine; the model is never moved), procedural materials (no image files),
  sea with geometry-nodes swell + animated ripples + foam, 360° photo dome + ground that
  catches the machine's shadow and otherwise looks exactly like the photo, props.
  Rebuilt only when its settings or the model change.
- Fixed in the second session: hall walls and the roll-up door faced outwards (a hall looked
  plain grey from any camera outside it, and see-through from inside); new **cut-away** in
  halls (anything between camera and machine, and the roof structure when the camera is above
  the light lines, is left out of the picture for camera rays only); more transparent steps for
  halls (black specks); the floor uses all non-excluded parts, so a saved scene that hides the
  base no longer lifts the floor (it moved 5 cm on the test model); cut-away nodes only on
  materials that can be in the way (−13% render time in halls).
- `world.py`: builds the surroundings in `apply` (never stops a render if it fails); offshore is
  lit by the sky; the studio floor is hidden when the surroundings bring their own.
- Panel 5 (`ui.py`): Background list with headings Studio / Photo / Offshore / Workshop; the
  chosen surrounding's settings below it; Light and Floor only where they apply; **More** fold
  (floor gap, show in the view, Put on the floor again); sub-panel **Props for scale**;
  header shows the background. `ops_surroundings.py`: Add prop, Delete all props, Put on the
  floor again. `props.py`: new settings (additive). `states.py`/`ops_main.py`: saved scenes and
  templates keep the surroundings settings and "Show props".
- Tooltips for every setting and button in panel 5 (also the existing ones).
- Docs: `docs/SURROUNDINGS.md` (owner: surroundings, props, render times, recommended free
  360° photos with click steps; the panel links to it), `docs/DEVELOPMENT.md` (how it works),
  `CLAUDE.md` (layout, tests, lessons learned).
- Tests: `tests/test_surroundings.py` (75 tests); real-app test `tools/ui_test_surroundings.py`.

**Tested and measured** (name the machine and the model):
All on the 2-core Linux test machine (no graphics card), generic test models only.
- Full pytest suite after merging main (0.2.10): 1,377 passed (11 min). New: 75 tests in `tests/test_surroundings.py`:
  layouts for 3 machine sizes × 7 surroundings × Simple/Detailed keep the machine's space and
  the camera's view free; hall panels face inwards; every surrounding builds and renders a
  small CPU frame with no image files, machine on the floor; rebuilt only on real changes;
  floor gap and Put on the floor again; floor stays when the base is hidden; cut-away removes
  a column between camera and machine (and the same column without it blocks); saved scene and
  template keep it; waves move between frames (and stand still when off); props; photo ground
  looks exactly like the photo away from the machine; panel draws for every background and
  light; tooltips; **background queue** renders a vessel deck still + 2-frame video (80 s)).
- Real app (Blender 5.2.3 Linux, `tools/ui_test_surroundings.py`). Run 1: 22/23 (the click check
  looked before the app finished the pick on the next mouse move: test fixed); run 2 after the
  panel fixes, without the queue part: 17/17. On GitHub (run 41937731835, merged branch, 4 cores):
  23/23 in 3.6 min, all other jobs green too. Covered:
  every surrounding chosen in the app (build 0.01–0.28 s each), live preview of a hall, props
  added / undo / redo, a click through the hall selects the boom's subassembly (the hall
  cannot be clicked), Show props, Put on the floor again, queue in a background Blender: deck
  still in Cycles + deck video and hall video in **EEVEE** (software OpenGL, 45 s per 540×540
  frame), save + reopen keeps everything without rebuilding. Panel 5 screenshots for every
  kind of background at the default side-panel width looked at: two problems found and fixed
  ("Moving waves" cut off; "Clean factory hall" ran into the panel title).
- Render time per surrounding: crane test model scaled to 6.4 × 2.4 × 2.0 m, 640 × 360,
  quality Preview, CPU, camera 2.2 × the Fit distance. Studio 31.2 s; 360° photo 29.2 s
  (ground off) / 25.1 s (ground on). Simple / Detailed: open sea 29.2 / 30.3 s, vessel deck
  28.3 / 29.9 s, quayside 25.9 / 30.3 s, clean factory hall 48.4 / 62.7 s, CNC hall
  69.8 / 86.6 s, assembly hall 43.1 / 48.1 s, warehouse 52.3 / 81.3 s. Before the cut-away
  nodes were limited to things that can be in the way (400 × 225): factory 22.0 → 19.2 s, CNC
  30.4 → 27.4 s. Tried and not taken (≤ 1 s gain, visibly less real): hall objects out of
  reflections, floor without clear coat.
- Packaged install: Linux build of the zip installed into the real Blender with
  `extension install-file` (the real-app test ran from it).

**Open points / follow-up tasks:**
- The "Saved scenes" sub-panel inside panel 5 lives in the Motion lane's files
  (`ui_motion.py`, `ops_motion.py`): its button "Remove scene" (`fresing.shot_remove`) has no
  tooltip yet. Left for the Motion lane (task 0011 was running there) or the tooltip check of
  task 0021.
- `docs/USER-GUIDE.md` did not exist yet (task 0021): it should link to `docs/SURROUNDINGS.md`.
- Halls render 1.4–2.8× slower than the studio on the processor. For long videos: Simple, or a
  360° photo with ground (no slower than the studio). To measure on the RTX 3090 (task 0002).
- EEVEE (Fast preview) with surroundings was checked on the Linux test machine (software
  OpenGL) only; the owner should glance at one Fast preview video in a hall.
- Ideas, not done: a "photo matched" sea (HDRI + water plane), more hall variants (crane
  sizes, colours), weather (fog, rain) for offshore.
