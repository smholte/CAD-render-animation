# 0273 – Material picker with pictures, this project's short list, own / department / company materials, filters by material, colour and look

**Who:** worker · **Status:** running (0272, 0274, 0318 merged) · **Branch:** `ccr-f130bd57-9cwtzc`
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

## Design (worker, 24 Nov – the plan the code follows)

**Entries.** Everything the picker shows is an *entry* (`core/material_files.Entry`): key, name, source (builtin /
company / department / mine / project), badge, `base` (a built-in id of `materials_lib.MATERIALS`), `changes` (what
differs from the base: `color`, `wear`, `rust`, `finish` = {size, angle, amount, base, kind}), tags (material kind,
colour family, looks), description, picture path, and for a Blender material `blend` (file) + `blend_material` (its
name inside). Keys: `builtin:<id>` (every library material but `blender_material`), `preset:<id>` (the old
Ready-made presets that carry a colour, `materials_lib.PRESETS`), `own:<uuid>` (own / department / company materials,
the uuid from their `material.json`; the same uuid in two folders lists twice, each with its badge).

**Tags** (`materials_lib.TAGS`, `DESCRIPTIONS`, `KINDS`, `COLOURS`, `LOOKS`): Material = Paint, Steel, Stainless,
Aluminium, Other metals, Fastener finish, Plastic, Rubber, Glass & clear, Light, Fabric, Other; Colour = any (takes the
group's colour) or white, grey, black, red, orange, yellow, green, blue, purple, brown, metal; Looks = gloss, satin,
matte, brushed, machined, polished, textured, patterned, see-through, glowing, weathered (one or more). Own materials
with a fixed colour get their family from the hue (`material_files.colour_family`).

**Own material = one folder** in a Materials location (0272): `material.json` + `picture.png` (+ `material.blend`).
`material.json`: `format` "fresing-material", `format_version` "1.0" (lifting library's rules: a higher major is
listed with its problem and never written, a higher minor keeps what it added), `id` (uuid), `name`, `description`,
`author`, `made_with`, `made`, `base`, `changes`, `tags`, and for a Blender material `blend`: {`file`, `material`,
`images_outside`}. A broken folder is an entry with `problems` (listed, greyed, never crashes the window).

**In the project** (`props.py`, additive): `FRMaterialGroup.mat_key` ("" = picked with the Material drop-down, as
in every older project) and `FRSceneSettings.project_materials` (`FRProjectMaterial`: key, name, `data` = the whole
`material.json` as text, `listed` = on the short list, `blend_mat` = the appended Blender material). Using an own
material copies it into `project_materials` (listed or not) and writes its settings into the group's own fields
(material, colour, wear, rust, finish settings): the project renders on a PC without the folder, and paint schemes,
rule sets, the queue, model update and the Web 3D bake see an ordinary group. Changing the group's Material drop-down
to another material drops `mat_key`. A **Blender material** is *appended* (not linked) as "FRM <name>" (fake user):
linked, the project would lose it on a PC without the folder; the group's material "FR <group>" is a copy of it
(`materials.own_blend_material`), its Colour / Wear / Rust are not shown ("its own look, made in Blender"). The
group's Material drop-down shows "Own Blender material" (`blender_material`, UID 87).

**Pictures.** Built-ins: `tools/material_pictures.py` runs real Blender (`material_picture_runner.py`) on the swatch of
study 0270 (a chamfered block, a knurled knob on it, a spun cap leaning in front; meshes with CAD face data so
finishes show), Cycles 32 samples + denoise, 256 px JPEG in `fresing_render/data/material_pictures/` +
`hashes.json` (sha of the material's spec, its finish spec, its picture colour and `material_files.PICTURE_VERSION`).
`tests/test_material_pictures.py` fails on a missing or old picture and names the command. Colour-taking materials:
a picture in a typical colour and, in the window, a chip of the group's colour drawn into the preview's corner
(`material_picker.chip_icon`). Own materials: rendered by the same runner in a background Blender after Save
(the app does not wait), **Make the picture again** per entry.

**The window "Materials"** (`ops_material_picker.py`, `ui_material_picker.py`): made like Fresing Settings (screen
mark `fr_materials` in `ops_setup.PAGE_MARKS`, the page in the toolbar region, size + place kept). Three columns:
filters (search, Source, Material, Colour, Look), the grid (picture + name button; size slider; ★ = Add to this
project; a second click on a picked name = Use), the picked entry (large picture, name, badge, tags, description, the
group's colour / wear, **Use for <group>**, **Add to this project**, **Save as my material…**, **From a Blender
material…**, **Make the picture again**, Show in folder). It follows 3 Looks' picked group. State on the window
manager (`WindowManager.fresing_matpick`), not in the project.

**3 Looks' group box**: above Material, "This project's materials": the short list (listed entries + the ones the
groups use, marked) as small pictures with a name button each (click = use, × = off the list), **More materials…**.
`fresing.group_preset` (the Ready-made menu) is gone: its presets are built-in entries.

**Templates** keep the short list (`Template.materials`: key, name, data); a template's own materials come along.
**Paint schemes** keep `mat_key` (`FRSchemeLook.key`).

Subagents: one (Sonnet) writes the tags and one-line descriptions of every built-in + their test
(`materials_lib.py` tags block only, `tests/test_material_tags.py`); one independent tester at the end.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
