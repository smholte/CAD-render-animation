# 0016 – Surroundings: offshore, quayside and factory backgrounds

**Who:** worker · **Status:** running · **Branch:** `task/0016-surroundings`
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

- [ ] Every surrounding renders in the background queue (tests: build each, render a small CPU
      frame, no missing textures); machine placed on the floor; saved scene/template keeps it
- [ ] Render time per surrounding measured on the test machine (small CPU frame, model named),
      Simple vs Detailed, in the report
- [ ] List of recommended free 360° photos for the owner + click steps to add them (in the
      report and in `docs/`)
- [ ] Real-app click test step and screenshots of panel 5 checked (generic test models only)
- [ ] Full suite passes; report filled in; merged and released (`CLAUDE.md` sections 2 and 7)

## Not in this task

- Studio lighting and camera presets, turntable (0017); logo, titles, captions (0018).
- Anything in panels 1–4, 6, 7 (other lanes).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
