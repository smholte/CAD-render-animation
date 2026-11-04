# 0010 – Paint single faces of a part

**Who:** worker (starts when 0008 is merged; 0009 is merged) · **Status:** waiting
**Area:** `blender/build.py`, `blender/materials.py`, `blender/logic.py`, `blender/reimport.py`,
Looks panel, render/queue.

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

## Done when

- [ ] To be written when the task starts

---

## Report

**Chat / date:**

**What changed:**

**Tested and measured:**

**Open points / follow-up tasks:**
