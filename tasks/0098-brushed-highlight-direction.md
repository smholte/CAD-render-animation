# 0098 – Looks: the shine of brushed, ground and turned parts runs across the marks

**Who:** worker · **Status:** open · **Branch:** `task/0098-brushed-highlight-direction`
**Started by:** lead chat, 12 Nov 2026 (0061's open point, found by its subagent B)
**Lane:** Looks – `blender/materials.py` (`_marks`), `core/materials_lib.py` if a look's numbers change,
`blender/material_sheet.py`, tests; guide pictures of the materials
**Model:** Sonnet · effort Medium · **Place:** Claude Code on the web, environment "CAD-render-animation"

## Goal

A brushed or ground plate shows its bright band across the brush lines, and a turned shaft its band along the shaft –
as real parts do – so the owner's shafts, plates and covers look right in close-ups.

## Background

0061 measured (subagent B, Principled BSDF, Anisotropic 0.8): Blender stretches the highlight **along** the Tangent
input (with the tangent along X the highlight was 16.2 px wide along X, 6.0 px along Y). On a real brushed part the
highlight stretches **across** the brush lines. 0061's cut-face marks therefore feed the direction across the grooves
(`blender/toolmarks.py`, top comment). 0046's looks do the opposite in `blender/materials.py` `_marks()`:
- ground / brushed: `tangent = AX_LONG` – the lines' own direction → should be across them (on the face: the cross
  product of the normal and `AX_LONG`, or whatever gives the right result on all faces of a part);
- turned: `tangent = cross(axis, p − centre)` – round the axis, the grooves' own direction → should be along the axis
  on the round side; check the end faces (rings there: the tangent should be radial).
Measure before changing (same way as B: highlight width in two directions on a small render) and after.

## Done when

- [ ] Render test: on a brushed plate and a ground bar the highlight is longer across the lines than along them; on a
      turned shaft longer along the axis than round it (numbers in the report, before/after).
- [ ] Cycles and EEVEE; scripts off; queue; old projects get the change when they open (as 0046's new looks did).
- [ ] Material sheet and the guide pictures that show these looks re-made; the PC-check materials line still passes.
- [ ] GitHub green; report filled in; merge to main and release.

## Not in this task

The cut-face tool marks (0061, done – already right), look strengths per material, the milled look's arcs.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
