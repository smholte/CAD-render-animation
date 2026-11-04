# 0010 – Paint single faces of a part

**Who:** worker · **Status:** open – can start (0008 merged in 0.2.8) · **Branch:** `task/0010-face-painting`
**Started by:** lead chat, 4 Nov 2026 · **Lane:** Looks · **Area:** `importer/step_reader.py` (only
if face numbers per triangle are missing from the cache), `blender/build.py`, `blender/materials.py`,
`blender/logic.py`, `blender/reimport.py` (face sets only), 3 Looks part of `blender/ui.py`,
`blender/ops_panels.py`, `blender/props.py` (additive), render/queue only if needed, `tests/`.

## Goal

Owner's point 4 (4 Nov 2026): a part is painted as a whole by default, but faces can be picked on
the model (add/remove) and given their own material or colour.

Also asked (4 Nov 2026): paint and finishes from Inventor (appearances, Finish features) and
Fusion 360 appearances. STEP carries them as colours, also per face. **Faces painted in CAD must
come in painted** (from the cached face colours), and rules may give such a face colour its own
material (e.g. colour X → anodised aluminium) while the rest of the part keeps its own.

## Background / design notes (lead)

- Copies of a part share one mesh; materials are linked per object (`material_slots[0].link =
  "OBJECT"`). Face sets stored on the mesh (polygon `material_index` + extra slots) apply to every
  copy of that part type, while each copy can still get its own material per slot.
- The cache already holds CAD face colours per triangle (`c{mid}` arrays + palette) – unused so
  far; they can seed face sets.
- Face picks must survive a model update when the part did not change (same face/triangle
  layout), and say so when it did.

## What to build

1. **Faces painted in CAD come in painted.** At import (and model update), each unique part with
   individually coloured faces gets face sets from the cached face colours; a face set is sorted
   like a part (by default a "Colour #RRGGBB" paint group; a rule may give it another material,
   e.g. that colour → anodised aluminium). The rest of the part keeps the part's group.
2. **Paint faces by hand.** In 3 Looks, "Paint faces" mode: click faces on the model to add them
   to a face set, click again (or Shift) to remove; a picked face is a whole CAD face (all its
   triangles), not one triangle. Then choose its material/colour or group, like for a part.
   "Back to whole part" removes a face set.
3. **Copies:** a face set applies to every copy of that part (they share one mesh); the material
   of a face set may differ per copy when the owner asks for "only this copy" (object-linked
   material slots).
4. **Model update:** face sets stay when the part did not change (same faces); when it did, the
   update report says which parts lost face sets.
5. Old projects and caches keep working (bump `CACHE_VERSION` only if the cache must change).
6. Faces with their own **appearance name** in the STEP (a style on single faces – Fusion/Inventor
   write them) get that appearance's material, like whole parts do since 0.2.8
   (`importer/step_meta.py`, `core/cad_materials.py`).

**Small follow-ups from task 0008's report, also in this task** (same lane and files):
- Old projects: replace their untouched old default rules by the new ones automatically
  (`rules.upgraded_rules()`, hook in `blender/logic.ensure_default_rules` or a load handler).
- Wire mesh: real holes through a grid texture in the material (`blender/materials.py`).
- Ready-made material "Aluminium, black anodised" (`blender/finder.py` PRESETS) → the new
  `aluminium_anodized_black`.
- If the owner attaches his big Inventor model: measure how many parts the part-type library
  sorts (number in the report and the progress note only, never names).
- Privacy: `tests/test_fasteners.py` contains a name from the owner's model ("THETA3…"); replace
  it with a generic name.
- **Tooltips** for every button and setting in panels 1 Import, 2 Structure and 3 Looks, also the
  existing ones (`CLAUDE.md` section 6).

## Done when

- [ ] Generic STEP test model with individually coloured faces (new or extended
      `tools/make_test_*.py`); tests: faces come in painted, a rule turns a face colour into
      another material, hand-picked face set (add/remove, whole CAD faces), per-copy material,
      model update keeps face sets of unchanged parts and reports changed ones, save + reopen,
      background render (queue) shows the face materials
- [ ] Real-app click test step (paint faces through the buttons) and screenshots of 3 Looks checked
- [ ] Full suite passes; report filled in; merged and released (CLAUDE.md sections 2 and 7)

## Not in this task

- Rule sets per company (task 0015, after this one). Joints/motion (other lane).

---

## Report

**Chat / date:**

**What changed:**

**Tested and measured:**

**Open points / follow-up tasks:**
