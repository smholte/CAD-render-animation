# 0024 – Decals: logos, text and pictures on the model

**Who:** worker · **Model:** Opus · **Status:** done (0.2.21) · **Branch:** `task/0024-decals`
**Started by:** lead chat, 5 Nov 2026 · **Lane:** Looks · **Area:** new `blender/decals.py`,
`blender/faces.py` / `blender/materials.py` (only where decals hook in), `blender/reimport.py`
(decals only), the 3 Looks part of `blender/ui.py`, `blender/ops_panels.py`, `blender/props.py`
(additive), `docs/USER-GUIDE.md` chapter 3, `tests/`.

## Goal

The owner puts a logo, a type plate, text or a picture on the machine itself – a company logo on
a cover, a type plate with his text, CE and warning stickers, a serial number – and it sits on the
surface like a real sticker, also in animations and background renders.

## Background

- Read the report of 0010 (face sets: whole CAD faces with their own material slot; picking a CAD
  face with a click; kept through model updates when the faces did not change) and of 0018 (brand
  kits: company logos in the shared library – use the same logos; if 0018 is not merged yet, read
  its brief and keep the library folder compatible).
- Copies of a part share one mesh: a decal may be on all copies (default for a type plate on a
  bought part) or on one copy only (a serial number) – like "Only this copy" in Paint faces.
- Must render in the background queue and with Python scripts disabled (plain material nodes).

## What to build

1. **Add decal** (3 Looks, new fold "Logos & stickers"): choose an image (from the library:
   company logos, a new folder of stickers; or a file) or type text (font, colour, background
   colour or none, border), then click the spot on the model. The decal lands flat on that face,
   centred on the click, upright by default.
2. Move, turn and size it with handles or numbers (mm); "Fit to face"; mirror; how see-through.
3. A small built-in sticker set made in code (no downloaded artwork): CE mark, generic warning
   triangles (hand crush, electrical, hot surface, hanging load) drawn as simple vector shapes,
   arrows, a type-plate template with fields (company, type, serial number, year, weight).
4. List of the decals of the clicked part (rename, hide, delete), and of the whole project.
5. Model updates keep a decal when its face did not change (like face sets), and say so when it
   did; saved scenes and templates keep decals; old projects open unchanged.
6. Tooltips; user guide chapter 3 with pictures (test crane).

## Done when

- [x] Tests: image and text decals on a curved and a flat face, all copies vs one copy, move/size
      by numbers, model update keeps/reports, save + reopen, background render shows the decal
      (pixel check), built-in stickers render
- [x] Real-app click test step (add a decal with a click) and screenshots of 3 Looks checked
- [x] Full suite passes, GitHub run green; report filled in; merged and released

## Not in this task

- Logo corner, titles, watermark in the *picture* (0018); labels with lines pointing at parts (0025).

---

## Report (filled in by the chat that did the task)

**Chat / date:** worker chat (claude.ai project), 5–6 Nov 2026.

**What changed:**
- 3 Looks > **Logos & stickers** (`ui_decals.py`, right after Paint faces): Picture / Text / Sticker,
  Only this copy, **Add decal…** (click the spot on the model; a click on the side panel does nothing).
  List of the clicked part's decals (rename, eye = off, ×), details box: Move with the mouse (follows
  the mouse over its part, also onto another face; wheel turns 15°/Shift 5°, Ctrl+wheel ×1.1, click =
  done, Esc = back), Fit to face, Upright, Width/Height (mm, Keep proportions), Right/Up, Turn, Mirror,
  See-through, Finish (matt/satin/gloss/metal), colours + background + border, font file (+ menu of the
  fonts on the PC), type-plate fields, picture file + White see-through, Put it on this copy only / on
  every copy. Folds: All decals in this project, Library (opens `<library>/Logos` and `Stickers`, made
  when missing; without a library `Documents\Fresing Render\Logos|Stickers`).
- `core/decal_geometry.py`: flat faces projected; cylinders recognised from the face's normals and
  points and **unrolled** (the sticker keeps its size round a barrel); the face's triangles cut to the
  outline, lifted 0.2 mm; fit to face (shrinks until the outline lies on the face: discs, notches);
  finding the spot again after a model update.
- `core/decal_art.py`: a small scan-line filler; text (Blender's font curves → triangles), CE mark,
  type plate, five warning signs, two arrows – drawn as three masks (ink / background / border) that
  the material colours, so colour, background and border change at once.
- `blender/decals.py`: settings in `Mesh.fresing_decals` (every copy) / `Object.fresing_decals` (one
  copy); one decal object per copy (child of the part, not selectable, no shadow), mesh shared by the
  copies; hidden with its part by MAX drivers on `hide_render`/`hide_viewport` (part's hide_render,
  decal's own `fr_off`); pictures packed into the .blend; plain-node material. `logic.Tree` skips
  decals. Model update (`reimport.py`, decals only): decals move to the matched part when their spot is
  still on it (also when the part changed elsewhere), else kept but off + a report line. Templates:
  `Template.decals`, put on parts of the same name where the spot is on the part. A click on a
  sticker while painting faces paints the face under it (`decals.through`).
- Tooltips for every new button and setting (check: 337 found, 0 missing, 0 weak; the check now also
  reads `ui_decals.py`). User guide chapter 3: section "Logos & stickers" with the panel picture and a
  render of the test crane with decals (`docs/img/panel_3_decals.png`, `docs/img/decals.jpg`;
  `tools/guide_screens.py`: mode `decals`, `GUIDE_ONLY`). Test models `tests/data/test_decals_a/b.step`
  (`tools/make_test_decals.py`).

**Tested and measured** (2-core test machine):
- pytest: 12 new without Blender (geometry, fit, locate, art) and 13 in Blender (picture on a flat face,
  sticker + text round a barrel, every copy / one copy, numbers, hide with part + animation keys, click
  on a sticker, remove, every sticker drawn, model update keeps 4 decals and reports 1, save + reopen with the
  picture file deleted, template on revision b, panel draws, queue render: red/blue halves of a picture
  the right way round and the warning sign's yellow). Neighbouring tests (faces, panels, core) pass.
- Real app: new `tools/ui_test_decals.py` 13/13 (add with a click, side-panel click, centre where
  clicked, move/wheel/Ctrl+wheel, Esc puts back, undo/redo, one copy); painted faces 10/10 again.
- Scripts off: real Blender 5.2.3 with `-Y` on a saved project: the decal hides at frame 5 with its
  part's animated hide_render and shows at frame 1 (by hand; drivers are MAX, checked in pytest).
- Speed: stickers drawn in 0.2–0.45 s; adding a decal on the test model 0.17 s. Worst case, a synthetic
  part of 600,000 triangles in one round face: add 0.96 s, changing the width or one mouse move 0.09 s
  (1.0 s before: mesh data kept 5 s, only triangles near the decal looked at, mesh written with
  `foreach_set`), Fit to face 0.86 s. Guide render with decals (960×540, Preview, CPU): 33 s.
- Independent review skipped (Saving usage): no Windows-only code apart from listing
  `%WINDIR%\Fonts`; covered by the tests above.

**Open points / follow-up tasks:**
- Motion lane (`ops_motion._raycast`, joint axis click) and Scene & Render lane (`ops_scene`, Sharp
  at click): a click on a sticker says "missed the model". Fix: pass the hit through
  `decals.through(ob, index, loc, normal)` (two lines each).
- Owner test on his PC: his company logo (PNG) and a type plate on a real machine, a GPU render; the
  font menu (Windows fonts); the library folders on the network.
- Not done: SVG logos (PNG/JPG/TIF/BMP/WEBP only; 0018 brand kits may want SVG), a decal across
  several CAD faces (a bent sheet: it is cut at the face edge), true wrapping on cones/spheres (they
  get a flat projection). In the Solid view a decal is a see-through tinted patch; the picture shows
  in Material Preview and renders.
- For 0018 (brand kits): logos can live in `<library>/Logos` – the folder this task lists.
- Branch `task/0024-decals` can be deleted on github.com.
