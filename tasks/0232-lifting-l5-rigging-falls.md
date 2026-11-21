# 0232 – Lifting L5: rigging (lift points, slings, shackles, spreader, the load hanging under the hook) + the hoist rope reeved in several falls

**Who:** worker · **Status:** done · **Branch:** `claude/wizardly-gates-yursxk`
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

- [x] 0180's C2 / C3 hand cases come out of the solver + checks on a real hang within 0.5 %; C10 hand case
- [x] The load hangs under the hook and follows Hook to here, a pose and a joint step; Set down; Build keeps it
- [x] AT-100: 8 falls drawn over 4 + 4 sheaves to the drum; hook up 1 m → drum payout 8 m (± a layer step); the time
      per hook move on the AT-100 and the CC-1600 measured (web machine; expectation for the owner's PC said as such)
- [x] Model update (same file) keeps lift points, rigging and the hang; Client view cannot edit them
- [x] Rigging stop(s) in the `lifting` set on 0231's loads; guide, function list, PC-check lines, tooltips; precheck,
      `tests/test_tour_clash.py` 0 clashes, full suite green; report filled in, merged, released

## Not in this task

The lift path and per-frame checks (L6), the printed plan (L7), detailed rigging-gear makers and forklifts (L8),
offshore DAF on rigging (L9), `reimport.py`, other tour sets.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (worker), 20 Nov 2026 – branch `claude/wizardly-gates-yursxk` (the session's
branch, not `task/0232-…`).

**What changed:**
- `core/lifting_hang.py` (new): the hang solver – rigid bodies (load, spreader) on legs that only pull, least potential
  energy by damped Newton (legs as very stiff springs: 0.1 mm stretch under the whole weight), forces = stiffness x
  stretch; stability from the energy's curvature (roll-over, turns freely, slack legs, legs too short, tilt notes);
  `single`, `with_spreader`, `checks` (C2 / C3 / C4 from `core/lifting.py` on the solved geometry), `design_force`.
  ~5–20 ms per hang.
- `core/lifting_reeve.py` (new): falls → head / block sheaves and dead end, the rope's path in three frames (drum,
  head, block), payout = falls x hook travel, the drum's turn and rope radius from `core/spool.py`'s layers
  (`drum_table`), `guess` for a crane file without reeving.
- `core/lifting.py`: **C10 Hoist line pull** = gross / (falls x E), E = (K^N − 1)/(K^S·N·(K − 1)), K = 1.04 roller /
  1.09 plain – source **API RP 9B (14th ed., 2015)**; hand case 10 t on 8 falls: E 84.16 %, 1.485 t, 22.85 % of 6.5 t.
  `wll_use` titles keep the leg's letter ("Shackle A", was "Shackle a").
- `core/lifting_gear.py` (new): 85 invented built-in rigging items in the library format (chain grade 8 / wire / round
  slings 1-, 2-, 4-leg; bow shackles 2–150 t; spreader beams SB-10/25/50; lifting frame LF-20 for a 20 ft container);
  own gear = library files (kinds sling, shackle, spreader_beam, lifting_frame; table `rigging`). `core/lifting_library`
  knows the fields `reeving` and `rigging`.
- Crane files: `reeving` (rope Ø from the winch's line pull, head / block sheave radii and pitch, block axle above the
  hook, the drum; JSON only – `lifting_model/equipment.py` + `make_lifting_cranes.py --json-only`; models, rig and chart
  hashes unchanged, so placed cranes are not "made again"). Make a crane gets it from the maker; Set up a crane writes a
  guessed one (`lifting_rig_out.py`) and `falls` in its hook block.
- `blender/lifting_rope.py` (new): **Reeve the rope** – one polyline mesh, three vertex groups tied by **Hook modifiers**
  to the motion empties of slew, hook swing and hoist, a tube by Geometry Nodes; app-made head and block sheaves; a
  drum joint "<crane> · Hoist drum" following the hoist by a table (spool layers) with the drum and its rope coil (radius
  by a table driver). No Python per frame. New cranes are reeved at **Place**; older projects keep the one-piece rope
  until **Reeve the rope** (Equipment). The CAD "HOIST ROPE" part is excluded and its cable removed.
- `blender/lifting_rig.py` (new): lift points (Find by name: padeye, lug, eye, top corner casting – a padeye's hole
  axis; Add by a click with the hover picker), gear, **Hang on the hook** (an empty on the hoist's motion in the solved
  pose + a Child Of "FR hang" on the load's parts, inverse identity), slings / shackles / master link / spreader drawn as
  app objects on the hook, **Set down**, **Remove**, the result as JSON on the load (stale when mass / gear / points
  change), `after_model_update`, `check_hang`.
- `blender/lifting.py` (additive): Place reeves; Remove sets a hung load down and takes the reeving; removing a load
  takes its rigging; the readout's gross includes the rigging mass; `line_pull`; model update keeps points and hang.
- UI: new sub-panel **8 Lifting plan > Rigging** (`ui_lifting.py`, `core/places.py`), operators in
  `ops_lifting_rig.py`; Equipment shows the reeving / Reeve the rope; Hook & capacity the line pull; Load the rigging
  mass. Function list `lifting.rig`, `lifting.hang`, `lifting.reeve`; guide sections + `panel_8_lifting_rigging.png`
  (and the other three Lifting pictures again); PC-check lines `lifting.hang`, `lifting.reeve`; tour stops
  `lifting_rig` (skid on a 4-leg chain set, tilted, rope in 4 falls) and `lifting_spreader` (empty container 2.3 t on
  the LF-20) in the `lifting` set, with stop set-ups so earlier stops show the loads unrigged.

**Tested and measured** (web machine, 4 cores, no graphics card; Blender as a module unless named):
- Hand cases out of the solver: C2 T_A 6.988 / T_B 4.881 t (rel. 5e-4), C3 12.289 t rigid / 6.145 equal / 7.681 DNV,
  98.3 % and 76.2 %; the same C2 and C3 cases **on real hangs in the app** (box loads, `tests/test_lifting_rigging.py`)
  within 0.5 %; spreader 6.5625 t top legs, 5.0 t bottom legs.
- AT-100: 8 falls drawn over 4 + 4 sheaves; hook 1 m up → drawn rope 8.00 m longer, drum turned within a layer step
  of 8 m. CC-1600: 28 falls over 14 + 14.
- **Time per hook move** (set the hoist + update the scene, 20 moves): AT-100 **0.74 ms** reeved vs 0.37 ms without
  the rope; CC-1600 **2.95 ms** vs 2.06 ms. PC check line on this machine: 0.80 ms. Expectation for the owner's PC
  (not measured there): about the same or less – the rope is a few hundred points moved by Blender's own modifiers.
- Hang on the hook: 137–155 ms (the skid, 4 legs, incl. drawing the gear).
- Follows Hook to here, a Build (frame 1 after bake), Set down stays put, save + open keeps hang and rope, model update
  of `test_loads.step` (same file) keeps the 4 points and the hang (CoG within 2 mm), Client view: Hang / Find / Add /
  Reeve are refused.
- Local: `test_lifting_hang.py` (11), **`test_lifting_hang_independent.py` (42, written by an independent subagent from
  the brief)**, `test_lifting_reeve.py`, `test_lifting_rigging.py` (7), `test_lifting_plan*.py`,
  `test_lifting_with_rest.py`, `test_setup_crane*.py`, `test_tour_lifting.py` (13), `test_tour.py` (102),
  `test_tour_clash.py[lifting]`, PC-check lines lifting.* (6 OK), tooltip report strict (884 ok), precheck.
- Subagents: one independent tester (tests from the brief and study 0180, not the code): 42 tests; it found **one real
  fault** – on a 2-leg sling the load's heading drifted (free turn about the vertical; up to 6° depending on the
  crane's heading). Fixed by a hair of yaw stiffness (`YAW`); its test passes now. A segfault found by
  `test_setup_crane.py` (a joint-list item kept across adding the drum joint) was fixed before merging.

**GitHub runs:** 10 for the branch. Run 1 red: the independent tester's turn-invariance case failed on another CPU
(the heading spring too weak – made firmer) and a real-app Set-up test counted the new drum joint (fixed). Run 2 green,
but other tasks took the version first six times (0241, 0239, 0237, 0246, 0247, 0230, 0248, 0238 – each a merge of
`main` and a renumber, 0.2.184 → 0.2.192); one of those runs failed only on two skipping test files in one pytest group
(fixed on `main` by the lead's CI change). `main` fast-forwarded to the green commit f81e401; release v0.2.192 published,
the Windows update check and "offer to the apps" green. The landing page job failed in GitHub's deploy step ("artifact
metadata" – a GitHub service error, also on 0251's push); re-run once: green.

**Open points / follow-up tasks:**
- The lead line runs straight from the drum to the lead sheave (on the telescopic cranes inside the boom box); real
  cranes guide it along the boom top over rollers – a look for L8/L9.
- The drum's coil is a cylinder whose radius steps with the layers; the turns are not drawn one by one.
- With vessel motion on, a hung load would get the deck's motion twice (its parts' own Child Of + the hook): L9.
- Shackle side load (C4 note) is not worked out from the padeye's plane yet; hitch modes (choke, basket) are in the
  gear files but the legs are always straight.
- A load set down "where it is" stays in the air if the hook was not lowered first (as the panel says).
- Leftover branch: none new (the session's branch `claude/wizardly-gates-yursxk`).
