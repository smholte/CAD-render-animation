# 0232 – Lifting L5: rigging (lift points, slings, shackles, spreader, the load hanging under the hook) + the hoist rope reeved in several falls

**Who:** worker · **Status:** open · **Branch:** `task/0232-lifting-l5-rigging`
**Started by:** lead, 20 Nov 2026 (study 0180 section 9 row L5; owner 18 Nov: "+ wire rope with several falls – reeving
over boom-head and hook-block sheaves, drum") · **Model:** Opus · effort High
**Area:** Lifting lane – new `core/lifting_hang.py` (the hang solver, pure Python), new `core/lifting_reeve.py` (falls,
payout, line pull), new `blender/lifting_rig.py` (rigging in the scene), new `blender/lifting_rope.py` (the reeved rope +
drum); additive: `blender/lifting.py` (plan data, `after_model_update`, readout), `ops_lifting.py`, `ui_lifting.py`
(a **Rigging** step), `props.py`, `core/lifting.py` (only if a check needs a new input), `core/functions.py`, the
PC check, guide chapter "Lifting plans", tests. The `lifting` tour set **only after 0231 is merged** (see below).
**Never `reimport.py`** (0237 works there) – model updates go through `lifting.after_model_update`.

## Goal

The planner rigs the load the way it is really lifted: picks lift points on the load, a sling set (2-leg, 4-leg) or a
spreader beam with its slings, and shackles; the app **hangs the load under the hook** – it tilts until its CoG is under
the hook – and shows each leg's angle and force live, which feed checks C2–C4. The crane's **hoist rope runs in its real
falls**: from the winch drum over the boom-head sheaves, down and up through the hook-block sheaves (8 falls on the
AT-100), so raising the hook winds the drum by falls × the hook's travel, and the readout shows the line pull per fall.

## Background

- **Study 0180** (`tasks/0180-lifting-plans-study.md`): section 2 (rigging items: slings chain / wire / round, shackles,
  spreader / frame, hook blocks), section 3 (checks **C2** 2-leg off-centre, **C3** 3/4-leg "two legs carry" + the DNV
  1.25 skew option + assembly rating 2.1× / 1.5× / refused > 60°, **C4** WLL use, shackle side load > 5°) with hand
  test cases, section 5 step 4 (click lift points with the hover picker of 0088, the app hangs the load, angles and
  forces live), section 9 row L5 (`blender/lifting_rig.py`, `core/lifting_hang.py`, M–L, risk: the hang solver on odd
  CoGs). **C2–C4 already exist** in `core/lifting.py` (L1, `wll_use` and the sling-leg functions): feed them the real
  geometry, do not re-write them.
- **Today:** L4 (0201) places cranes, makes loads with a CoG marker, Hook to here, the readout (rigging = 0 until L5);
  0203 / 0204 rig and make cranes; 0214 fixed the model update, Build after Hook to here, crane updates. The hoist rope
  is **one** cable from the head sheave to the hook block (`blender/lifting.py` `_rope`, the file's `rig.cables`). The
  files already carry `hook_blocks[].falls` and `.sheaves` (AT-100: 8 falls, 4 sheaves) and the makers know the winch
  (`lifting_model/classes.py` `line_pull`, `p["winch"]`; `mobile.py` "HOIST WINCH DRUM").
- **The app's cable machinery:** `paths.py` (cables over sheaves, wraps, `read_cad`, `set_end`), `spool.py` (drums:
  helix / Lebus layers from the payout). 0172's open point: "two cables over one sheave untried" – here each fall has its
  own sheave. Keep it fast: the rope must follow a hook moved by Hook to here / a pose / a joint step without a visible
  wait (measure on the AT-100 and the CC-1600 – the most falls).
- **0231** (running at the same time, Sonnet) makes `tools/make_test_loads.py` (IBC on a pallet, a pump skid with 4
  padeyes and an off-centre CoG, a 20 ft container with 4 corner castings – lift points named) and puts them in the
  `lifting` tour set on a quay. Build your core and panel first; **merge `main` after 0231 is merged**, then add your
  rigging stop(s) to its `lifting` set on its loads. If 0231 is not merged when you get there, say "WAITING FOR YOU:
  0231" and push your branch.
- Lessons of the lane: a Build must not put the crane / load back (0209 row 3); a model update must keep everything
  (row 1); the readout's cache must stay cheap (the side panel's draw does no work).
- Plain plan words only (`lifting.FORBIDDEN_WORDS`, study section 8). Owner's amber limits: 75 % crane, 90 % rigging.

## What to do

1. **Rigging items** (built-in samples, invented, in size classes – detailed makers come with L8): sling sets (chain
   grade 8, wire rope, round sling; 1/2/4 legs; WLL per leg, length, mass/m, mode factors), shackles (WLL 2–150 t with
   their dimensions), a spreader beam (span, WLL, self-weight, top / bottom padeyes). Data in the lifting library format
   (`core/lifting_library.py`), the user's own items as files like cranes. Shapes: simple, made by the app (a shackle
   body + pin, a sling as a straight or Flex rope / chain look, a beam with padeyes).
2. **Lift points:** click on the load (the hover picker of 0088), or pick its named padeyes / corner castings; shown as
   small markers; listed under the load.
3. **The hang solver** (`core/lifting_hang.py`, pure Python + NumPy, its own tests): the load as a rigid body with its
   CoG and mass, legs of fixed length from the hook point (or the spreader's bottom padeyes) to the lift points; find the
   pose with the CoG under the hook and the legs taut (a slack leg is reported, as is a load that would roll over);
   2-leg, 3-leg, 4-leg, with spreader (two stages). Hand cases: 0180's C2 case (10 t, 4.0 m, CoG 1.5 m from A, hook
   3.0 m above → tilt, then T_A / T_B), a symmetric 4-leg = no tilt, an off-centre 4-leg (which legs carry), the
   spreader. Odd CoGs (CoG above the lift points → unstable, said in plain words).
4. **In the scene:** **Hang on the hook** puts the load (its parts, carried as a group) under the hook in the solved
   pose, with the slings, shackles and spreader; it follows the hook (Hook to here, poses, joint steps, a Build) live;
   **Set down** takes it off the hook where it is. The readout gains: rigging mass (added to gross, C1), each leg's angle
   and force, C2/C3/C4 rows (green / amber / red) with "go to" the leg.
5. **The reeved hoist rope** (`core/lifting_reeve.py` + `blender/lifting_rope.py`): from the hook block's `falls` and
   `sheaves` and the head's sheaves (read from the crane's file / its CAD names; Set up a crane (0203) and Make a crane
   (0204) gain the fields they need – head sheaves, block sheaves, drum, dead end), the rope path drum → head sheave(s) →
   block sheave → head … → dead end (on the head or the block, by odd / even falls); the drum winds by falls × the hook's
   travel (spool.py's drum, its layers), turns as a joint; drawn as the app's cable (rope look). Line pull per fall =
   gross / (falls × the reeving efficiency) – take the efficiency formula and a sheave efficiency from a public rigging
   source (name it), hand-check one case – shown in the readout and checked against the winch's `line_pull` when the
   file gives it (a new check **C10 "Hoist line pull"** in `core/lifting.py`, with its hand case). Old projects: the
   one-piece rope keeps working until the user presses **Reeve the rope** (or: reeved at the next Place – say which).
6. **Keep everything:** `after_model_update` keeps lift points, rigging and the hang; Build / undo / save + reopen keep
   them; a crane removed takes its rope and drum winding with it; Client view shows, never edits.
7. **Rigging stop(s)** in the `lifting` tour set (after 0231): the skid on a 4-leg chain set (off-centre CoG, the tilt
   and two legs carrying), the container on a spreader (or 4 legs), the reeved rope visible; checks on the leg forces
   (against the hand formulas) and the rope's falls; `changed=`, re-record, 0 clashes.
8. Guide (Rigging section + the rope), function-list entries (`lifting.rig`, `lifting.hang`, `lifting.reeve`,
   `since=`), PC-check lines (hang the test load, leg forces within 1 % of the hand values; the rope's payout = falls ×
   hook travel), tooltips, `core/places.py` for the new step.
9. **Independent tests** from this brief by a subagent that did not write the solver (study 0180's cases + odd ones).

## Done when

- [ ] 0180's C2 / C3 hand cases come out of the solver + checks on a real hang within 0.5 %; C10 hand case
- [ ] The load hangs under the hook and follows Hook to here, a pose and a joint step; Set down; Build keeps it
- [ ] AT-100: 8 falls drawn over 4 + 4 sheaves to the drum; hook up 1 m → drum payout 8 m (± a layer step); the time
      per hook move on the AT-100 and the CC-1600 measured (web machine; expectation for the owner's PC said as such)
- [ ] Model update (same file) keeps lift points, rigging and the hang; Client view cannot edit them
- [ ] Rigging stop(s) in the `lifting` set on 0231's loads; guide, function list, PC-check lines, tooltips; precheck,
      `tests/test_tour_clash.py` 0 clashes, full suite green; report filled in, merged, released

## Not in this task

The lift path and per-frame checks (L6), the printed plan (L7), detailed rigging-gear makers and forklifts (L8),
offshore DAF on rigging (L9), `reimport.py`, other tour sets.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
