# 0012 – Couplings and motors: one joint moves several things

**Who:** worker · **Status:** done (0.2.18) · **Branch:** `task/0012-couplings-motors`
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

- [x] Tests: each coupling type against hand-calculated values, chain of three, loop refused,
      coupled joints after a model update, save + reopen, file with scripts disabled still moves
      (check the drivers are simple expressions), motor step: 12 rpm for 5 s = 1 turn
- [x] Real-app click test step and screenshots of 4 Motion checked
- [x] Full suite passes; report filled in; merged and released (CLAUDE.md sections 2 and 7; no
      installer: "Saving usage")

## Not in this task

- Hydraulic cylinders (0013) and closed linkages such as scissors (0014).

---

## Report (filled in by the chat that did the task)

**Chat / date:** worker chat, 5 Nov 2026.

**What changed:**
- `joints.py`: `follows` / `couple_ratio` / offsets / `is_motor` on each joint. A follower's value
  and motion are driven by `a * K + C` reading the joint at the top of its chain (`chain_affine`:
  the ratios and offsets of a chain combine) – a simple expression, so it works with scripts off.
  `factor()` turns the typed ratio (turns per turn, mm per mm, mm per turn, ° per mm) into
  internal units. Loops refused (`follow_check`); coupling drivers muted in `cad_pose` (the
  follower's motion at 0); `get_value` of a follower is computed from its chain. Followers keep
  their place when freed or when the leader is removed or gone after a model update. Specs carry
  couplings and the motor flag; `refresh_couplings` rewires everything after an update. Motors:
  ±10,000 turns; followers' limits only warn (Blender clamps keyed/driven custom properties to
  min/max, so both get a wide hard range).
- `animation.py`: Run motor (`MOTOR` step: speed rpm or mm/s, ramps from the Motion choice and
  `ramp`; one key per frame while the speed changes, one per frame when a limit stops it);
  steps and poses skip followers (warning: which joint to move); limit warnings for followers.
- `states.py`: poses store and apply only joints that move by themselves.
- Panels: 4 Motion (Moves by itself / Follows a joint, Joint, ratio with its unit as label,
  Offset, hint in other words, Drives '…', Motor tick box with turns, follower value purple);
  6 Animation (Run motor box, red steps for followers). Tooltips: every button and setting of
  panels 4, 6, 7 and Saved scenes (`tooltip_report`: 248 found, 0 missing, 0 weak);
  `docs/TOOLTIPS-TODO.md` is empty now. `tooltip_report.py` follows helpers of helpers.
- Joint names never empty or twice. User guide chapters 4 and 6 + 2 pictures; README-install;
  CLAUDE.md lessons (clamping, scripts-off testing, driver threads).

**Tested and measured** (2-core Linux test machine, test crane):
- `tests/test_couplings.py`, 35 tests against hand-calculated values: gear (−0.5), jaws (−1),
  telescope (stack, 1:1 → twice as far), spindle (5 mm/turn) and rack (π·40 mm/turn), rolling
  wheel Ø50 (100 mm → 4 rad), offsets, chain of three, loops and itself refused (also through
  the panel field), followers vs hand/poses/steps, limit warnings, CAD pose with an offset,
  remove/rename/type change, save + reopen, all drivers simple expressions, model update A → B
  (couplings, motor, values) and leader gone, old specs, motor without end, Run motor 12 rpm ×
  5 s = 1.00000 turn, ramps (0.8 turn with 1 s ramps, values per frame), followers of a motor,
  slide motor stopping at its limit, panels drawn. Two mutation checks caught by the right tests.
- Real program with scripts disabled (`blender -Y`, `tools/coupling_check_noscripts.py`): the
  couplings move the parts exactly; a Python-only control driver is refused. In `ui_test_app2`
  (now 50 checks, also on GitHub) with clicks for Follows a joint, undo/redo, Motor, + Run motor.
- Speed: 12 joints in one chain, 0.07 ms per frame vs 0.06 ms with every joint keyed.
- Full suite before the review fixes: 1,451 passed; GitHub run of the branch green (4 jobs).
  After the fixes: coupling, stack, phase-2 and CI-tool tests and ui2 locally; full run on GitHub.

**Independent review** (helper agent): 1 near-blocker + 2 should-fix + 2 minor, all fixed with a
test that failed before: followers moved one update late now and then (drivers on several
threads; 29 of 1000 updates in the test before, 0 after, also on 251 played frames); follower
jumped back to CAD when its leader was gone after a model update; freed follower beyond its
limits jumped to the limit; removing a leader while an animation was built; empty/duplicate joint
names; Motor off past 10 turns jumped. Checked fine: units, chains with offsets, stacks with
followers, model updates across stacks, ramps, old specs, drawing code.

**Open points / follow-up tasks:**
- Owner test on his PC with a real mechanism (24 cores: the thread issue above is fixed by design,
  not measured there).
- "Axis stays fixed in the world" and Swap-order splits (from 0011) still open.
- Ratio fields are single precision (gear ratios to about 7 digits).
