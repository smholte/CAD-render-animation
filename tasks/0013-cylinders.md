# 0013 – Hydraulic and electric cylinders

**Who:** worker · **Model:** Opus · **Status:** waiting (0012) · **Branch:** `task/0013-cylinders`
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

- [ ] Generic test model with an arm, pivot and cylinder (new `tools/make_test_*.py`, no owner
      data); tests: follow mode at several arm angles (eyes stay on pins within 0.01 mm), drive
      mode stroke → arm angle against hand calculation, both after a model update and reopen
- [ ] Real-app click test step (add a cylinder through the buttons) and screenshots checked
- [ ] Full suite passes; report filled in; merged and released (CLAUDE.md sections 2 and 7)

## Not in this task

- Mechanisms with closed loops of several links (scissor lifts, four-bar arms): task 0014.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
