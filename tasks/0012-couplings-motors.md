# 0012 – Couplings and motors: one joint moves several things

**Who:** worker · **Status:** running · **Branch:** `task/0012-couplings-motors`
**Started by:** lead chat, 4 Nov 2026 · **Lane:** Motion · **Area:** same as task 0011.

## Goal

One joint can drive others, so one animation step moves a whole mechanism: telescope sections
that extend together, two gripper jaws that close towards each other, a spindle or rack that turns
rotation into travel, a gearbox. Motors (the owner's most used drive, together with cylinders) can
simply run: "turn at 12 rpm for 5 s".

## Background

- Builds on task 0011 (stacked joints); read its report first.
- Joint values are `fr_value` on the motion empty; a driver of type AVERAGE copies it into the
  rotation/location, on purpose without Python expressions so files work with "Auto Run Python
  Scripts" off. Couplings must also work with scripts off: use only drivers that Blender evaluates
  without Python (`driver.is_simple_expression` is True, e.g. `a * 2.5 + 0.1`), or plain AVERAGE.
- Animation steps are baked to keyframes (`blender/animation.py: bake`); background renders use
  the keys and drivers.

## What to build

1. **Coupling:** in the joint details, "Moves by itself" or "Follows joint [A]" with a ratio and an
   offset. All combinations: rotate→rotate (gear ratio, −1 for opposite), slide→slide (telescope,
   jaws), rotate→slide (spindle/rack: mm per turn), slide→rotate (pinion on a rack, rolling wheel:
   degrees per mm). Chains A→B→C allowed; loops refused with a clear message. A following joint
   cannot be moved by hand, in poses or in animation steps (it shows "follows A") – its limits,
   if set, warn when exceeded.
2. **Motor:** a rotate joint can be marked "Motor (turns without end)": no limits, value shown in
   turns as well as degrees. New animation step **"Run motor"**: speed (rpm, or mm/s for a slide),
   duration, ramp up/down (uses the existing easing). Coupled joints follow (winch drum, wheels,
   conveyor rollers).
3. Saved data: couplings and motor flag in specs (model update), poses store only free joints,
   old projects open unchanged.
4. **Tooltips** for every button and setting in panels 4 Motion, 6 Animation and 7 Render queue,
   and the "Saved scenes" sub-panel of panel 5 (its code is in this lane's files), also the
   existing ones: the Motion rows of `docs/TOOLTIPS-TODO.md` (54), delete them when done.
5. User guide chapters 4 and 6 and their pictures (`CLAUDE.md` section 6).

## Done when

- [ ] Tests: each coupling type against hand-calculated values, chain of three, loop refused,
      coupled joints after a model update, save + reopen, file with scripts disabled still moves
      (check the drivers are simple expressions), motor step: 12 rpm for 5 s = 1 turn
- [ ] Real-app click test step and screenshots of 4 Motion checked
- [ ] Full suite passes; report filled in; merged and released (CLAUDE.md sections 2 and 7)

## Not in this task

- Hydraulic cylinders (0013) and closed linkages such as scissors (0014).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
