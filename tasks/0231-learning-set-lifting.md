# 0231 – Learning set "Lifting": real-size loads on a yard, the load always in view

**Who:** worker · **Status:** done (0.2.176) · **Branch:** `task/0231-learning-set-lifting`
**Started by:** lead, 20 Nov 2026 (study 0224 package A; owner's answers 20 Nov: the tour is the learning environment,
each set its own fitting environment; Q3 several real-size invented loads, each sized to its equipment) · **Model:**
Sonnet · effort Medium
**Area:** `blender/tour.py` – **only** the sets `lifting`, `lifting_make`, `crane_setup` and their check functions; a new
`tools/make_test_loads.py` + `tests/data/test_loads.step` + its `fresing_render/data/` copy + `tests/test_make_test_loads.py`;
`core/functions.py` (`tour=` links only); the guide's tour lines if they name these stops. **Not** `blender/lifting.py`,
`ops_lifting*.py`, `ui_lifting*.py`, `core/lifting*.py` (Lifting L5 = 0232 works there).

## Goal

The three Lifting learning sets look like a real lift: a crane on a yard / quay ground with mats under its outriggers,
lifting **a real-size invented load sized for it**, and every stop shows the load, its CoG and the hook – today all four
Lifting stops hide the load behind the crane's carrier.

## Background

- Study 0224 (`tasks/0224-study-tour-sets-up-to-date.md`): in `lifting_place`, `lifting_cog`, `lifting_hook` and
  `lifting_make` a ray from the camera to the CoG first hits the crane's CARRIER DECK; the CoG close-up shows only
  wheels; no site ground, no mats, a desk-size load (the 1.5 m test crane's boom, 1.2 t). `lifting_make` repeats
  `lifting_hook`.
- **Owner Q3 (20 Nov):** several real-size invented loads, each sized to its equipment – **pallet / IBC** (the small
  crane now, forklifts later in L8), **a skid** (a mid crane), **a 20 ft container** (a big crane).
- The built-in cranes: `fresing_render/data/lifting/` (AT-40 … CC-1600, KB-20 … KB-200). Today the set uses
  `lifting.EXAMPLE_CRANE` / `EXAMPLE_LOAD` / `EXAMPLE_MASS`; those constants and the PC check's example stay as they are
  (0232 works in `lifting.py`) – the tour sets get their own constants in `tour.py`.
- Surroundings: `QUAY` (quayside) is the fitting ground; mats under outriggers if the Lifting set-up offers them (else
  plain invented mat boxes placed by the set as props, named so – say which in the report).
- 0232 (Lifting L5, rigging + rope falls) runs at the same time in `lifting*.py`; it adds its rigging stop to the
  `lifting` set **after this task is merged** – keep the set's build easy to extend (one helper per load).

## What to do

1. `tools/make_test_loads.py` → `test_loads.step`: three invented loads with real sizes and named parts, each with its
   lift points as small named padeyes / corner castings (L5 will rig them): an **IBC on a pallet** (~1.2 × 1.0 × 1.15 m,
   ~1.1 t full), a **pump skid** (~4 × 2 m frame, pump + motor off-centre, 4 padeyes, ~6 t), a **20 ft container**
   (6.06 × 2.44 × 2.59 m, 4 top corner castings, ~18 t gross). No real makes, no logos. Masses entered on the loads
   ("invented" as source).
2. `lifting`: QUAY ground, the crane on mats, the **skid** (or the container with the bigger crane – pick what fits a
   built-in crane's chart at a sensible radius) as the load; cameras for place / CoG / hook that see load, CoG marker
   and hook (and the crane). **A new check in each of these stops: the line from the camera to the CoG is not blocked**
   (ray cast against the scene's parts; the fault no check caught).
3. `lifting_make`: the crane made from numbers **by itself** (boom out, its chart / reach shown), not a second Hook to
   here. `crane_setup`: same ground (QUAY), camera unchanged otherwise.
4. Where a second load fits the set without a new stop, place the others too (IBC near the small crane, container
   beside) so the set reads as a real yard; no new stops beyond what the precheck asks.
5. `changed=` on the three sets, `tools/tour_versions.py --record`; every stop's check passes; `tests/test_tour_clash.py`
   at 0 clashes; `tour=` links in `core/functions.py` if a stop moved.

## Done when

- [ ] Each Lifting stop's picture shows load + CoG + hook (pictures in the report, 400 px, test models only)
- [ ] The new "CoG not hidden" check fails on today's set (proved once) and passes on the new one
- [ ] Loads: real sizes and masses as above, lift points named; test model test green
- [ ] Tour build time of these sets before / after (web machine); full suite green; report filled in, merged, released

## Not in this task

Rigging, slings, falls (0232); forklifts (L8); `blender/lifting.py` and the PC check's example; other tour sets.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 20 Nov 2026

**What changed:** `tools/make_test_loads.py` -> `test_loads.step` (+ copy, `tests/test_make_test_loads.py`): IBC on pallet
(1.2 x 1.0 x 1.15 m, 1.1 t), pump skid (4 x 2 m, pump + motor on the +y side, 6 t, 4 padeyes), 20 ft container (6058 x
2438 x 2591, 18 t, 4 top corner castings); 27 named parts. Masses are entered in the tour as source "estimate" (the app has
no "invented" source). Sets `lifting`, `lifting_make`, `crane_setup` now on the QUAY yard (`_yard`); AT-40 on four plain
mat boxes "Tour crane mat N" (the Lifting set-up has no mats), skid = the load, camera ISO_LEFT. New check
`_cog_in_view` in all three Lifting stops (CoG in the picture, ray camera -> CoG hits only the load, hook block in view at
the hook stop). `lifting_make`: the made AT-100 alone, pose Working + slew 90, readout radius 14.7 m, no Hook to here.
The IBC and the container stand in the yard (no new stops). Pictures: `tasks/0231-pictures/` (400 px).

**Tested and measured** (4-core web machine, real Blender 5.2.3): the check failed on the old set at all 3 stops
('CARRIER DECK' in the way), passes on the new; `tests/test_tour_lifting.py` (10) also proves it fails with a cube in the
way; `test_tour_clash.py` 48 passed; test_tour (Lifting + build) passed. Set build time before -> after: lifting 3.8 -> 2.9 s,
crane_setup 2.9 -> 3.0 s, lifting_make 4.1 -> 5.8 s. GitHub: 2 runs (the full run, then a docs run after merging a
documents-only main), green; released 0.2.176.

**Open points / follow-up tasks:** the guide's Lifting picture and text still show the test crane's boom (the PC check's
example is unchanged, as briefed). 0232 can add its rigging stop to `lifting` using `_skid_load` / `_yard_crane`; IBC and
container are ready for forklifts (L8) and a big crane. The hook picture frames the whole crane, so the skid is small.
