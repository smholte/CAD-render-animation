# 0010 – Paint single faces of a part

**Who:** worker · **Status:** done (0.2.9) · **Branch:** `task/0010-face-painting`
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

- [x] Generic STEP test model with individually coloured faces (new or extended
      `tools/make_test_*.py`); tests: faces come in painted, a rule turns a face colour into
      another material, hand-picked face set (add/remove, whole CAD faces), per-copy material,
      model update keeps face sets of unchanged parts and reports changed ones, save + reopen,
      background render (queue) shows the face materials
- [x] Real-app click test step (paint faces through the buttons) and screenshots of 3 Looks checked
- [x] Full suite passes; report filled in; merged and released (CLAUDE.md sections 2 and 7)

## Not in this task

- Rule sets per company (task 0015, after this one). Joints/motion (other lane).

---

## Report

**Chat / date:** worker chat, 4–5 Nov 2026 (the chat that also did 0008). Merged into `main` and
released as 0.2.9.

**What changed:**

- **Import cache 5** (`importer/step_reader.py`): per unique part `f<mesh>` = the first triangle
  of every CAD face plus the total (a face's triangles are one block), so a click picks a whole
  CAD face; `palette_names` in `tree.json`: appearance names of face colours.
  `importer/step_meta.py` reads styles on single faces (`STYLED_ITEM`/`OVER_RIDING_STYLED_ITEM`
  on a face) and returns {colour: appearance name}; a colour used with two names is left out.
  Old caches (version 4) are read again on the next import, as before.
- **Face sets** (`blender/faces.py`, new): a face set is a list of CAD face numbers with its own
  material slot (polygon `material_index`, slot k+1; slot 0 = the part). Stored as JSON on the mesh
  (`fr_face_sets`, shared by every copy); per-copy choices on the object (`fr_face_copy`); every
  slot object-linked so copies can differ. Meshes from projects before 0.2.9 find their CAD faces
  as connected pieces (two CAD faces never share vertices) – checked equal to the stored list on
  the biggest EGR part (604,832 triangles, 8,598 faces, 0.28 s once).
- **Faces painted in CAD come in painted** (`build.py`): each palette colour of a part becomes a
  face set, except the colour most copies of the part have (some exporters colour every face in
  the body colour). Sorting (`logic.apply_rules` → `faces.sort`): face sets go through the same
  rules with `rules.face_facts` (only colour and CAD material: name rules, part types and
  fasteners never sort single faces) → by default "Colour #RRGGBB" (paint) or the appearance's
  group ("Aluminum - Anodized Glossy (Blue) #3355CC" → coloured anodised aluminium); a rule
  "Colour is #CC1A1A → Anodised red" turns them into another material. Rule match counts include
  face sets; the groups list shows how many face sets a group paints.
- **Paint faces by hand** (3 Looks, new fold "Paint faces"): "Paint with" (a group; empty = the
  selected group), "Only this copy", "Paint faces…" (modal: click = the whole CAD face under the
  mouse gets the group, Shift+click = back to the part, Enter/Esc/right-click or "Done" ends;
  turning/zooming the view and side-panel buttons keep working; undo/redo work). Under it the
  face sets of the clicked part: "Other group…" and "Whole part" per set (also per copy).
  Renaming a group renames it in face sets; removing a group sends its face sets back to the rules
  (CAD faces) or to the part's look (hand-painted).
- **Model update** (`reimport.py` → `faces.carry_over`): face sets and per-copy choices stay
  when the part's faces did not change (same triangle count on every CAD face); faces painted in
  CAD always come from the new file (with the group chosen for them kept); parts that lost painted
  faces are listed in the update report ("…: its faces changed, the faces painted on it are gone").
- **Follow-ups from 0008:** projects whose rules are still the untouched pre-0.2.8 default list get
  the new defaults when opened (load handler → `logic.ensure_default_rules` →
  `rules.upgraded_rules`; a message says so; own rules are kept). New library material
  `wire_mesh` (UID 42): the shader cuts square holes (25 mm mesh, 3 mm wire), used by "Wire mesh &
  fences". Ready-made "Aluminium, black anodised" → `aluminium_anodized_black`. The owner-model
  name in `tests/test_fasteners.py` (and two names in his naming style) replaced by generic ones.
- **Tooltips** for every button and setting in panels 1 Import, 2 Structure and 3 Looks (operator
  docstrings/`description`, property descriptions; a check listed none left without one). The
  clicked part's box shows its CAD material name and wraps long group names.
- `docs/DEVELOPMENT.md`: cache 5 and face sets. `docs/USER-GUIDE.md` does not exist yet (task
  0021 is writing it): its 3 Looks section should describe "Paint faces".

**Tested and measured:**

- Test models: `tools/make_test_faces.py` → `tests/data/test_faces_a.step` / `_b.step` (generic:
  a housing with a red face and a blue face with an Autodesk-style appearance name, a bracket ×2
  with an orange end face, plain parts, a box whose faces all carry the body colour; revision "b"
  changes one part's faces).
- `tests/test_faces.py` (11 tests): faces painted in CAD come in painted (whole CAD faces, slots
  object-linked, appearance → material), a rule turns a face colour into another material (name
  rules do not touch faces), hand painting (add, Shift remove, move between sets, other group,
  whole part), copies (shared sets, "only this copy" both ways), renamed/removed groups, save +
  reopen, model update keeps sets of unchanged parts and reports the changed one, old meshes find
  their faces, **background render through the queue shows the face materials** (pixel check),
  panel draws, plain JSON data. Plus tests for the rule upgrade, the black anodised preset and the
  wire-mesh holes (`test_part_types_blender.py`) and the cache/step_meta changes.
- Full suite: **1,266 passed** (2-core Linux test machine).
- Real app (Blender 5.2.3 Linux, virtual screen, simulated mouse clicks; `tools/ui_test_faces.py`):
  **10/10** – CAD faces painted after import, "Paint faces" starts, a click paints the whole face
  under the mouse, a click on another part, Shift+click, a click on the side panel paints nothing,
  Enter ends, material on the painted face, undo, redo. Side-panel screenshots of 3 Looks
  (`tools/ui_screens.py`, 150 % UI scale) looked at: no cut-off labels in the new fold.
- Packaged Linux install + self-test (0.2.9 zip with Linux wheels): every line OK except "Render HD on
  graphics card" (no graphics card on the test machine, as in every release).
- **Owner's EGR model** (attached in this chat, not in the repository; AP203, so no colours or
  face colours): the part-type library and fastener rules sort **1,540 of 2,789 placed parts
  (55 %)** – 1,491 by part type, 51 as fasteners – and **334 of 582 part names (57 %)**; 1,247
  placed parts stay Unsorted. Many of those carry supplier catalogue numbers the library does not
  know yet (Misumi above all); the rest are in-house abbreviations and generic names (no names here).
- EGR with cache 5 (same machine): import 58.8 s (the face list adds no measurable time; meshing
  17.9 s vs 17.4 s before), cache 55 → 56 MB, build + sort 2.8 s, sorting again 0.04 s, painting a
  face on the biggest part + sorting 0.2 s.

**Open points / follow-up tasks:**

- **More supplier codes:** 45 % of the EGR parts stay Unsorted; adding Misumi catalogue code
  families (and a few in-house words the owner confirms) would raise coverage. Measure again on
  the EGR file (numbers only).
- Faces painted in CAD on the owner's PC: no Fusion/Inventor file with painted faces was available;
  the Autodesk face-style structure was written by hand after the body-style one. Worth one check
  with a small Fusion file (one face with another appearance).
- `docs/USER-GUIDE.md` (task 0021): add "Paint faces" to the 3 Looks section.
- Face sets follow CAD faces; a face that a model update splits or merges loses its paint (the
  report says so). Painting part of a CAD face is not possible (by design).
