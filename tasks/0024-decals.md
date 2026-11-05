# 0024 – Decals: logos, text and pictures on the model

**Who:** worker · **Model:** Opus · **Status:** waiting (0023) · **Branch:** `task/0024-decals`
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

- [ ] Tests: image and text decals on a curved and a flat face, all copies vs one copy, move/size
      by numbers, model update keeps/reports, save + reopen, background render shows the decal
      (pixel check), built-in stickers render
- [ ] Real-app click test step (add a decal with a click) and screenshots of 3 Looks checked
- [ ] Full suite passes, GitHub run green; report filled in; merged and released

## Not in this task

- Logo corner, titles, watermark in the *picture* (0018); labels with lines pointing at parts (0025).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
