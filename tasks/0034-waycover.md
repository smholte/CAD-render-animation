# 0034 – Way covers: telescopic covers that follow a machine axis, set up in one go

**Who:** worker · **Model:** Sonnet · effort Medium · **Place:** Claude Code on the web · **Status:** open – can start
**Branch:** `task/0034-waycover`
**Started by:** lead chat, 6 Nov 2026 · **Lane:** Machining (new files `waycover.py`, `ops_waycover.py`,
`ui_waycover.py`; the sub-panel hangs under 4 Motion like Milling does, with the smallest additive hook).
It *calls* the joint and coupling functions of tasks 0011/0012; it does not change them.

## Goal

The owner (CNC mill maker) wants telescopic **way covers** (bellows replaced by sliding steel sections) to move
with a machine axis in one easy set-up, without building one coupling per section by hand:

- one **slide motion** (the machine axis: a slide joint, existing or made here),
- several **way cover sections** – he picks each section; **a section may be made of several parts**,
- the **total length of movement** is shared out over the sections.

His example: the mill axis moves 500 mm; with 5 sections each section moves 100 mm relative to its
neighbour (so section k is 100·k mm from the fixed end, the last one moves with the axis, 500 mm). Change the
number of sections and the shares change.

## Background

- Task 0012 (couplings) already has "Follows a joint" with a ratio, chains and the Run motor / Move joint steps; a
  telescope is "a chain of 1 mm per mm couplings". Task 0013 built stages into cylinders the same way
  (`core/cylinders.stage_shares`: stage i slides i/(n+1) of the travel). Read both reports and
  `blender/joints.py` (couplings), `blender/machining.py` / `ui_machining.py` (a separate-file sub-panel).
- Couplings must work with "Auto Run Python Scripts" off (simple-expression drivers or AVERAGE) – CLAUDE.md
  section 8. Everything this task makes must too, also in the render queue.
- Section numbering decision (default, from the owner's example): the sections are the **moving** covers;
  the cover housing on the fixed side is not counted. Offer a switch "Fixed housing counts as a section" for
  covers drawn the other way (then 5 sections over 500 mm = 0, 125, 250, 375, 500) and say in the panel which
  one is on, in plain words with the resulting travel per section.
- **Test model:** the owner has a STEP of a way-cover sub-assembly and has said (6 Nov 2026) that it is
  generic enough to be **committed as a test model** (an exception to the public-repository rule; it holds no
  design of his or his clients'). He attaches it in the worker chat – ask for it at the start. Check it first
  (size, part names, nothing that names a client or machine); if it is clean, put it in `tests/data/` (and a copy
  in `fresing_render/data/` for the PC check, size permitting – a test keeps the copies equal) and name it in the
  report. Also make a small generic model with `tools/make_test_waycover.py` (5 nested plates, some of two parts,
  on a base with a slide axis) so the tests do not depend on his file alone. If he has not attached it by the time
  you need it, use the generated one and finish; tell him it can be added later.

## What to build

1. **4 Motion > Way covers** (sub-panel in its own file). Steps top to bottom, as the other panels:
   1. **Axis:** pick the slide joint that drives the covers (list of the project's slide joints; button
      "Make one from the selection" for a machine without a joint yet, using the existing add-joint code).
   2. **Sections:** select the parts of one section (any number of parts or subassemblies), press
      **Add section**; repeat, from the fixed end to the moving end (the order can be changed: up/down).
      A list shows each section with its parts count and its share. Remove / rename a section; "Select the
      section's parts".
   3. **Travel:** "Total length of movement" – read from the axis joint's limits (button) or typed; shown as
      "N sections × X mm". Direction follows the axis; "Flip" if the covers should open the other way.
   4. **Make it** (main button) creates what is needed: each section follows the axis with ratio k/N (a
      coupling from 0012, so poses, Move joint, Run motor, G-code of task 0026, saved scenes and the render
      queue all move the covers), and keeps the sections' limits in step. A state line in the panel header
      (e.g. "5 sections · 100 mm each · follows 'Y axis'").
2. **Behaviour:** changing the number of sections, adding/removing a section, or the travel updates the shares
   at once (or on a button, but never leaves old couplings behind). The axis joint keeps working by itself and
   by hand. Removing the way cover removes the couplings it made and nothing else. A section whose parts
   already follow something is refused with the reason (same style as the other checks).
3. **Kept** in saved projects and through **model updates** (matched by part names/IDs like joints) and in
   templates if joints are.
4. **6 Animation:** nothing new needed if the existing Move joint / Run motor step moves the covers; check it
   with a test and say so in the guide. (If a step "Move axis with way covers" is clearly easier, add it.)
5. **Reuse, don't copy:** share the ratio maths with `core/cylinders.stage_shares` where it fits; the
   panel logic lives in the new files.
6. PC check line `machining.waycover` (CLAUDE.md rule): the generic model, 5 sections, axis to 500 mm → each
   section at its hand-calculated place; `MIN_LINES_FULL` +1. Every button/setting a tooltip. User guide:
   chapter 4 gets "Way covers" with a panel picture and a render of the test model. CHANGELOG, version bump.

## Done when

- [ ] The owner's example holds exactly in a test: axis 500 mm, 5 sections → 100/200/300/400/500 mm
      (and the other numbering with the switch: 125 mm steps); 3 and 8 sections too.
- [ ] A section of several parts moves as one; two sections can not share a part (refused with the reason).
- [ ] Works with scripts off, in a built animation, in the render queue (frames against hand values), after save
      + reopen and a model update; removing the way cover leaves the joints as before.
- [ ] Real-app click test (select parts, Add section ×N, Make it, change the axis value) added to
      `ci_real_app.py`, with its `MIN_CHECKS`; panel screenshot checked.
- [ ] The owner's way-cover model (if attached and clean) is in `tests/data/` and a test runs the set-up on it.
- [ ] Tests, full suite green on GitHub; tooltip check 0 missing; guide, PC-check line, CLAUDE.md layout line, report filled in.

## Not in this task

- Bellows that stretch (a deforming cover), covers on two axes at once, collision/clash checks.
- G-code (task 0026, Motion lane, `ui_motion.py`): the covers follow the axis joints it moves, so no work
  is needed here; whoever merges second updates its branch to `main`.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
