# 0013 – Hydraulic and electric cylinders

**Who:** worker · **Model:** Opus · **Status:** running (worker chat, 5 Nov 2026) · **Branch:** `task/0013-cylinders`
**Started by:** lead chat, 4 Nov 2026 · **Lane:** Motion · **Area:** same as task 0011.

## Goal

Cylinders – with motors the owner's most used drives (A-frames, cranes, hatches, tensioners,
grippers) – move correctly by themselves: when the arm moves, the barrel turns and the rod slides
out so both eyes stay on their pins. And the other way round: the owner sets the cylinder stroke
(mm) and the arm moves to match.

## Background

- Builds on tasks 0011 and 0012; read their reports first.
- Picking a hole with a click already gives an axis (`joints.axis_from_hit`) – use it to pick the
  two cylinder eyes (pins).
- Must work in background renders and with Python scripts disabled: Blender's own constraints
  (e.g. Damped Track / Locked Track) and simple-expression drivers, or keys written when baking.

## What to build

1. **Add cylinder** (4 Motion): pick the barrel (subassembly), the rod (subassembly), then the pin
   at the barrel end (on the base side) and the pin at the rod end (on the moving part). Check that
   the two pin axes are parallel (planar cylinder); warn if not.
2. **Follow mode:** something else moves (a rotate joint of the arm, a stack, a coupling); the
   barrel turns about its pin to aim at the rod pin, the rod aims back and slides along the barrel.
   Several cylinders on one arm (two side by side) work.
3. **Drive mode:** the cylinder stroke becomes the value the owner sets (in mm, with min/max from
   the CAD lengths or typed in): the arm's rotate joint follows. For one arm on one pivot this is a
   triangle (pivot, barrel pin, rod pin), solved exactly with the law of cosines; pick the solution
   nearest the CAD pose. Poses and animation steps ("Move cylinder": stroke from → to) use the
   stroke. Electric linear actuators are the same thing.
4. Telescopic (multi-stage) cylinders: stages follow each other with task 0012's coupling – show
   how in the report (a test model is enough).
5. Saved data: cylinders in specs (model update), old projects open unchanged.

6. Small, from task 0023: messages in this lane's files still say "1 subassemblies added"
   (joint members) and "1 pieces … moved apart" (Explode): use `core/words.plural()`.

## Done when

- [x] Generic test model with an arm, pivot and cylinder (new `tools/make_test_*.py`, no owner
      data); tests: follow mode at several arm angles (eyes stay on pins within 0.01 mm), drive
      mode stroke → arm angle against hand calculation, both after a model update and reopen
- [x] Real-app click test step (add a cylinder through the buttons) and screenshots checked
- [x] Full suite passes; report filled in; merged and released (CLAUDE.md sections 2 and 7)

## Not in this task

- Mechanisms with closed loops of several links (scissor lifts, four-bar arms): task 0014.

---

## Report (filled in by the chat that did the task)

**Chat / date:** worker chat, 5–6 Nov 2026 (night). Also fixed: "Show joint arrows" NameError (from 0027's report).

**What changed:**
- `core/cylinders.py` (no Blender): `Drive` – pin-to-pin length ↔ arm joint value; rotate joint = triangle
  pivot / barrel pin / rod pin, law of cosines, the solution on the CAD pose's side (sign of the CAD angle);
  slide joint = quadratic, root through the CAD pose; refuses a pin on the pivot axis, a cylinder pointing
  at the pivot, a cylinder at right angles to the slide. `estimate_travel`: rays parallel to the axis at
  0.85 × the piston radius: back to the end cap (in), from the piston's front to the gland (out); without a
  piston/gland a guess from the barrel's ends ("rough guess" in the panel). `stage_shares` (telescopic).
- `blender/cylinders.py`: frame empty on the barrel pin (parent: the part holding it; Z = pin axis, X → rod
  pin), barrel empty with **Locked Track** to the rod-pin empty (on the part holding the rod pin), rod empty
  with **Copy Location** from it; telescopic stage empties with a simple-expression driver
  `d * share - share * L` (`d` = LOC_DIFF between the pins). No Python at run time. The pins are taken in
  the barrel's mid-plane (rod pin projected along its axis). Drive mode keeps the arm joint's own value:
  the stroke field (get/set) converts; the arm joint's limits are set from closed … closed + full stroke.
  The arm joint is found each time (the nearest joint above the rod pin's part; the barrel pin must stay
  put relative to that joint's frame; axis parallel to the pins / a slide at right angles to them); nothing
  extra stored, so removing or renaming joints needs no bookkeeping. Pin carrier: the clicked part when
  it is not the cylinder, else the biggest part around the pin with a hole/shaft on that axis (not a part of
  another cylinder). Specs, `before_model_update` / `rebuild_from_specs` (after the joints), `rebuild()` for
  Set-up changes (parts, stages, pin carriers), remove, rename (animation steps follow).
- `ops_cylinders.py` + 4 Motion > **Cylinders** sub-panel (`ui_motion.py`): Barrel / Rod (selection), Add
  cylinder (two clicks on the pins), list with the stroke now, Follows / Drives the arm, Stroke, Fully in /
  CAD / Fully out, Closed length, Full stroke, From the model (measured / rough guess), Set-up fold (Barrel,
  Rod, Stages, No stages, Barrel pin, Rod pin, Pins again, Select parts).
- 6 Animation: step **Move cylinder** (`animation.py`): stroke eased from → to, the arm joint keyed on every
  frame from the exact inverse (constant speed = constant rod speed); warns beyond the stroke or when it
  cannot drive (reason).
- `joints.check_members`: a cylinder's part cannot get a joint (the cylinder moves it). `build.CYLINDER_KINDS`
  (in `JOINT_KINDS`: not part of the CAD tree). Click on a pin marker selects the cylinder (`handlers.py`).
- Fix: `show_joints` update was a lambda calling `_show_joints`, defined below the class – Blender evaluates
  property definitions while the file is read (with `from __future__ import annotations`): NameError. Now a
  named function above the class; also shows/hides the cylinders' markers. Lesson in CLAUDE.md.
- From 0023: "1 subassembly added", "1 piece … moved apart" (`plural()`).
- Docs: guide chapter 4 "Cylinders" (+ picture) and chapter 6 (Move cylinder); CHANGELOG; CLAUDE.md (layout,
  real-app test list, 2 lessons); `tooltip_report.py` knows the cylinder panel (311 found, 0 missing, 0 weak).

**Telescopic cylinders (brief point 4):** built in rather than set up by hand with couplings: Set-up >
**Stages** takes the sections between the barrel and the rod; with n stages, stage i slides i/(n+1) of the
rod's travel – exactly what a chain of 0012 couplings at 1 mm per mm between neighbouring sections does,
but with no extra joints (the travel comes from the pin distance, so it also works in follow mode, where no
joint value exists to couple to). Test `test_telescopic_stage_slides_half_the_rod_travel` (one stage: half).

**Tested and measured** (2-core Linux test machine, generic test luffer `tests/data/test_cylinder_*.step`
from `tools/make_test_cylinder.py`: arm, two cylinders side by side, one telescopic; no owner data):
- `tests/test_cylinders_core.py` (15): forward/inverse against an independent rotation and a bisection,
  the law of cosines written out by hand, branch continuity, unreachable lengths, out-of-plane pins, slide
  quadratic, refusals, travel from triangles (in 60 mm, out 130 mm exactly; guess without piston).
- `tests/test_cylinders.py` (22) on the real import: eyes on pins at −25…40° (< 0.0001 mm measured), the
  rod on the barrel's line; two side by side; pins found when the cylinder's own eyes are clicked; the
  whole machine turned 30°; refusals; drive mode stroke → angle = law of cosines and = bisection (1e-6 rad),
  limits; slide; Move cylinder step (frames against hand values); pose; telescopic; save + reopen;
  model update A → B (drive mode, typed closed length, values kept, eyes on pins); rod gone; remove;
  rename; Set-up rebuilds; Show joint arrows; constraints only.
- Existing suites touched by the change: couplings, stacked joints, phase 2, panels: 100 passed.
- Real app (Blender 5.2.3, virtual screen): `tools/ui_test_cylinder.py` 22/22 (Barrel / Rod buttons, Add
  cylinder + two real clicks on the pins, follow, Drives the arm, Fully out, stroke field, undo/redo, Move
  cylinder step built and scrubbed, Show joint arrows, save + reopen, Remove); also on GitHub
  (`ci_real_app.py`, MIN_CHECKS 22). Panel screenshot checked.
- Speed (test luffer, 276 frames): playback 0.031 ms/frame with the arm only, 0.078 ms with three cylinders
  (one telescopic); baking a 10 s Move cylinder step 5 ms.

**Independent review:** REVIEW

**Open points / follow-up tasks:**
- Owner test on his PC with a real cylinder (luffing cylinder of a crane or an A-frame).
- Drive mode needs the barrel pin to stay put relative to the arm joint's frame and the rod pin directly on
  that joint; closed linkages (a cylinder driving a four-bar or a scissor lift) are task 0014.
- Telescopic stages share the travel equally; sequential stages (biggest first) could be added if wanted.
- "Pins again" after the parts moved: works for the usual case (clicks on pins/brackets).
