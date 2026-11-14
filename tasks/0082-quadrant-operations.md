# 0082 – Quadrant operations: the second end goes over the stern on the D, into the sea, tipped off on the seabed

**Who:** worker · **Status:** running (14 Nov) · **Branch:** `ccr-dfd4b55c-97xzhk`
**Started by:** lead chat, 14 Nov 2026 (plan: end of tasks/0075; owner's steps: tasks/0083 "Quadrant sequence";
owner 12 Nov: TASKS.md "Problems found")
**Area:** Flex parts lane (`blender/paths*.py`, `core/paths.py`, `core/catenary.py`, `blender/paths_sea.py`,
`blender/paths_riders.py`, `ui_paths.py`, `ops_paths*.py`) + Demo models lane (`blender/demo.py` stages/shots,
`fresing_render/demo_model/` if the model needs a part, `tests/test_demo_*.py`) + **one small Scene & Render fix**
(the wake direction, below). Additive only: `props.py`, `animation.py`, `reimport.py`, `handlers.py`.
**Do not edit:** 0116's files (`tools/site_projects/`, `site/render_kit/`, `materials_lib.py` while 0116 runs),
0111's (`site/` page and picker, `blender/web3d*.py`, `lightbake.py`).
**Model:** **Opus · effort High** (subagents allowed, CLAUDE.md section 2; an independent tester is required) ·
**Place:** Claude Code on the web, environment "CAD-render-animation"

## Goal

The owner's main goal: the demo project shows the whole **second-end quadrant operation** as he works it, with the
**cable coming along**: the D-quadrant carries the cable's turn aft, over the stern on the handler, down into the
sea **vertical** on the A&R wire, tips near the seabed on the tipping wires, the cable slides off onto the seabed,
and everything comes back. Built with app functions a user can use on his own vessel (not demo-only tricks), so the
same steps work on a real model later.

## Background

- **Owner's steps** (tasks/0083, "Quadrant sequence" 1–15, and the CPS steps) and **owner 12 Nov:** the D is lowered
  into the sea **vertical**, hanging from the A&R wire at its curve's top; it only starts to tip **near the sea
  bottom**, turned by the two tipping wires on the bar's ends; the tipping winches pay out in step while it is
  lowered, then pay out more while the A&R winch holds. Underwater reference: clear blue water, sun rays, sediment
  specks, small glowing markers on the quadrant's hang-off point.
- **What exists:** shot 7 (`shot_quadrant`, 0091/0095/0102): tensioners open (lift, tilt out), cradles drop, the D
  travels aft on its rails onto the handler, the tipping wires are connected, the handler tilts to ~100° – **without
  the cable**: the demo's cable is drawn `still` (0078 follow-up: its turn round the D's gutter would have to travel
  with the D). The A&R and tipping wires are the demo's own constraint/driver wires (0095), not app cables. Shot 8
  (0081): the catenary from the stern chute to the seabed, seabed, water depth, clarity, cut-away.
- **Functions to call, never copy:** cable paths (0078: contacts SHEAVE/ROLLER/CHUTE/BEND with carriers, live handler,
  `bake` at Build), sea end (0081: `paths_sea.add_sea_end`, `numbers`, `tdp_world`, `payout`), riders (0081:
  `paths_riders.add(scene, cable, objects, where="END"|"MARK", at=)`, `remove`, `matrix_now`), tracks (0079: pads
  release when the top track lifts), spooling (0080), vessel motion (0085), cut-away and clarity (0081), clash check
  (0065/0110; demo checks with the sea at rest – CLAUDE.md section 8).
- **Decisions left to this task** (TASKS.md): the D's tip joint rides the handler's tilt; the D's gutter end over
  horn A's upper bend; the clash check confirms the rails clear the cable by ≥ 10 cm (0084).
- **0081 open point to fix here:** the wake is drawn at the waterline's max x and `core/weather.BOW_AZ` puts the bow
  at −x, while the demo has its bow at +x: with vessel speed > 0 (the vessel creeps along the route during the
  lowering) the wake would appear at the bow. Make the wake follow the vessel's real bow (a setting with a sensible
  default read from the model, or the sea's own direction) – old projects keep their look.

## Scope

1. **The cable's turn travels with the D.** The cable from tensioner 1 round the D's gutter to tensioner 2 is no
   longer `still`: its contacts on the D move with the D (rails, handler tilt, lowering, tip), the rest of the route
   stays put. Length kept exactly (the payout bookkeeping of 0078/0081; the tensioners pay out what the moving bight
   needs – when they are open, the carousel/route feeds it). Groove seat on the D's gutter from the mesh as now.
   This must be an **app ability** (a cable contact whose carrier moves along a joint chain, live and at Build),
   with its panel line and tooltip, not a demo-only script.
2. **A&R and tipping wires as app cables** (0075 plan): the A&R wire from its winch drum along the deck over the
   handler's top pulley to the D's eye; the two tipping wires from their winches over the swivel sheaves to the D's
   bar ends. Winch drums turn with the payout (0080's spool where it fits), sheaves turn, the swivel sheaves follow
   the wire. Replace the 0095 driver wires in the demo (keep 0095's test pictures' intent: wires on the right sheaves
   and posts). Wire look `wire_rope`.
3. **The sequence as demo shots** (stage `quadrant_ops` after `sea`; shot numbers after 8; time-lapse with a caption
   "× N" where real speeds would be too slow; real winch/handler speeds from tasks/0083 where given):
   - 9: (owner's 2–7, with the cable now) – shot 7's move again **with the cable on the D**: tensioners open and let
     the cable go, the D carries the bight aft and over the stern; at ~100° the D hangs vertical below the top pulley,
     curve up per 0091, both cable legs going down into the water. (Shot 7 may become this shot – one shot, not two
     copies; keep its 0 clash rows.)
   - 10: (8–10) the A&R winch **lowers the D vertical** into the water and down to near the seabed; the tipping winches
     pay out in step; the vessel creeps along the route (vessel motion and swell as the shot 8 sea); cut-away on, the
     catenary of the laid cable and the bight on the D both visible; sun rays and sediment specks if the existing sea
     can show them (no new sea features beyond what 0081 has – note in the report what is missing).
   - 11: (11–13) the A&R winch **holds**, the tipping winches pay out more: the D **tips** about its A&R-wire point
     towards flat; the cable **slides off** the gutter onto the seabed (the bight becomes laid cable with its sea end,
     the cable end with its CPS/pull head – a rider from 0081 – lies on the seabed; length kept).
   - 12: (14–15) the D is pulled back up and over the stern, the handler tilts back, the D travels back on its rails
     to its stationary place; the tensioners' top tracks come down again at the end.
   Labels per step as the earlier shots; glowing markers at the hang-off point under water if simple (an emissive
   small part), else leave it.
4. **Checks:** clash check **0 rows** over the new shots (sea at rest; wires and the moving cable are left out as
   flex parts – but the D, handler, rails, tensioners and posts are checked); the cable never shorter or longer than
   its length (test over every frame); the bend round the gutter ≥ the cable's MBR (warn otherwise); tipping wires
   never through the handler or the stern (test the wire lines against those parts' meshes).
5. **Tour stop** (a small test model: a cable over a sheave on a carrier that travels, tilts and lowers, with a sea
   end), **PC-check line**, guide section (Cables and paths: "a cable on a moving part"; demo shots 9–12), test
   pictures of the shots for the lead (in the report, described; `demo_overview.jpg` only if the overview changes).

## Done when

- [ ] Cable contacts on a moving carrier: live and at Build, length exact, tested on the tour model and the demo
- [ ] A&R + tipping wires are app cables in the demo; drums and sheaves turn; 0095's driver wires gone
- [ ] Demo shots 9–12 as the owner's steps; Make demo still finishes (time in the report vs 0.2.92)
- [ ] 0 clash rows; length and MBR checks; wake follows the bow; independent tester's findings fixed
- [ ] Tour stop, PC-check line, guide, CHANGELOG; full run green; version taken last

## Not in this task

The CPS run from the rack down the orange ramp (owner's CPS steps 1–5): a later Demo task (0082 only needs a CPS/pull
head on the cable end as a 0081 rider). Mesh import (0117). The turbine (0116) – later the quadrant could lower the
cable end next to its monopile, not now. New sea features (sun rays, specks) beyond what 0081 has.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
