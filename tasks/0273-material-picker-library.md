# 0273 – Material picker with pictures, this project's short list, own / department / company materials, filters by material, colour and look

**Who:** worker · **Status:** open – waits for 0272 (the Materials locations) and, if it is briefed by then, 0274
(same files) · **Branch:** `task/0273-material-picker`
**Started by:** lead, 21 Nov 2026 (owner 17:27: "I want a material selector with pictures. A user can select a material
for the group it is currently working on, but also add more materials to the current project that it can later add
from a short list. The preset materials should also be able to add from a user's own materials and the organisation's,
and the materials should be categorised into different materials, colours, looks.") · **Model:** Opus · effort High
**Area:** Looks lane – `core/materials_lib.py` (tags on every built-in; nothing else changes in a built-in's look),
a **new** `core/material_files.py` (no Blender: the own-material file format, reading, checks, filters) +
`blender/material_picker.py` / `ops_material_picker.py` / `ui_material_picker.py` (the window), `blender/materials.py`
(build an own material; link one made in Blender), `blender/props.py` (additive: the group's material reference, the
project's short list), `blender/ui.py` (3 Looks > the group box only), `blender/ops_panels.py` (`group_preset` folded
into the picker), `blender/material_sheet.py` + a **new** `tools/material_pictures.py` (the built-ins' pictures),
`fresing_render/data/material_pictures/`, their tests, a real-app test, the guide, CHANGELOG. Reads
`core/locations.py` (0272) for the Materials folders.
**Not:** new finishes (0274, from study 0270); the paint-faces and decal panels (they get the picker later if the owner
wants – note it); the Web 3D bake (must keep working with any material – test it, do not change it).

## Goal

Choosing a material looks like choosing it in a good render program: a **window full of pictures**, filters on the
left, one click puts the material on the group being worked on. A project keeps **its own short list** of chosen
materials right in the group box, and the list of materials grows with the user's **own**, the **department's** and
the **company's** materials, each marked where it comes from.

## What to do

1. **Tags on every material** – three filters, the owner's words: **Material** (Paint, Steel, Stainless, Aluminium,
   Other metals, Fastener finish, Plastic, Rubber, Glass & clear, Light, Fabric, Other – today's `CATEGORIES` map onto
   it), **Colour** (any colour – the group's colour is used; or a colour family: white, grey, black, red, orange, yellow,
   green, blue, metal-coloured…; own materials with a fixed colour get theirs from the hue), **Look** (gloss, satin,
   matte, brushed, machined / turned, polished, textured, knurled / patterned, see-through, glowing, weathered).
   A material can carry more than one look. Tags for every built-in are data in `materials_lib.py`, checked by a test.
2. **Pictures:** every built-in gets a small picture (≈ 256 px, the swatch shape study 0270 proposes – or, if 0270 is
   not done, a rounded block with a knob and a disc), made by `tools/material_pictures.py` with Cycles, kept in
   `fresing_render/data/material_pictures/` with a hash of each material's settings; a test fails when a built-in
   changed and its picture was not made again (it says the one command to run). Paints and other colour-taking
   materials are pictured in a typical colour with a **colour chip** drawn on top showing the group's current colour.
   Own materials get their picture when they are saved (rendered in the background, the app does not freeze; **Make the
   picture again** on each).
3. **The window – "Materials"** (built like 0260's output windows: draggable, stays open, one at a time, remembers its
   place): search box; filters Source (Built-in · Company · each department · Mine) / Material / Colour / Look on the
   left; the picture grid in the middle (size slider); on the right the picked material large, its name, source badge,
   tags, a one-line description, the group's colour and wear, and the buttons **Use for <group>** (also: double-click a
   picture), **Add to this project** (a star on the picture), **Save as my material…**. The window follows the group
   picked in 3 Looks – the user can keep it open and walk through the groups.
4. **This project's materials (the short list)** – in 3 Looks' group box, above the Material row: a row of small
   pictures of the materials added to the project (and, marked, the ones its groups use); one click puts one on the
   group; **More materials…** opens the window. The list is saved in the project and in a project **template** (so a
   company template can carry a standard short list). Remove from the list with a right-click or an × on hover.
5. **Own materials – one folder per material** in a Materials location (0272), like the lifting library (0190):
   `material.json` (name, tags, description, author, made with version, **the built-in it starts from + its changed
   settings** – colour, roughness, finish settings, wear) + `picture.png`, optionally `material.blend` (below). Two
   ways to make one:
   - **Save as my material…** from a group: what the group shows now becomes a material (no Blender knowledge needed).
   - **From a Blender material…** for users who build materials in Blender's own shader editor: pick a material in the
     open project; it is kept in `material.blend` and linked or appended on use (say which and why); the picker shows
     it like any other. Warn plainly when such a material uses image files that are not inside the folder.
   Where to save: the writable Materials folders (Mine first, 0272). A broken material folder is listed with its
   problem, never crashes the window. Newer / older file versions: the lifting library's rules.
6. **The group's material reference:** today `group.material` is an enum with a fixed number per built-in
   (`materials_lib.UIDS`); own materials need a reference that survives (source + id + a copy of the settings inside
   the project, so the project renders on a PC that does not have that folder). Keep old projects opening exactly as
   before; model update, undo, paint schemes, the queue's paint schemes (0074), rule sets with a material, templates and
   the Web 3D bake must all keep working – list in the report what you checked.
7. **Ready-made material…** (`group_preset`) folds into the window (its presets become built-in entries with their
   colour, tagged); the menu goes.

## Watch

- Picture grid in Blender: `bpy.utils.previews` + `template_icon_view` / a grid of `template_icon` buttons – measure the
  window's redraw with ~150 materials (keep it under ~20 ms on the 4-core machine) and the first open with a cold
  cache.
- A Materials folder on a slow or unreachable network (0272's rules: background read, cached list).
- Licences: a company's own Blender materials are theirs; nothing of them goes in the repository or a report.

## Done when

- [ ] Tags on every built-in (test); pictures for every built-in (test with the hash)
- [ ] The Materials window: filters, search, Use for group, Add to this project, Save as my material, From a Blender
      material; real-app test clicks through each
- [ ] The short list in the group box, saved in the project and in a template
- [ ] Own / department / company materials from 0272's locations, with badges; a project with an own material renders
      on a PC without that folder (test)
- [ ] Old projects unchanged (test with a 0.2.19x project); Web 3D export of a project with an own material works
- [ ] Function list, PC-check line, guide chapter with pictures, CHANGELOG; report with the owner's check steps; merged,
      released

## Not in this task

New finishes (0274); sharing materials online; the picker in Paint faces / decals (follow-up if the owner wants it).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
