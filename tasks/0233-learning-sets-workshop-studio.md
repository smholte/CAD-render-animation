# 0233 – Learning sets in their own environments: the workshop and studio sets (framing, links, fitting surroundings)

**Who:** worker · **Status:** open · **Branch:** `task/0233-learning-sets-workshop`
**Started by:** lead, 20 Nov 2026 (study 0224 package D, widened by the owner's answers 20 Nov: the tour is the users'
learning environment; **each set its own environment that fits the project and shows off its functions – from plain, to
see-through, to a full ocean or a factory**) · **Model:** Sonnet · effort Medium
**Area:** `blender/tour.py` – **only these sets** and their own helpers / checks: `looks`, `cutaway` (Slice), `cylinder`,
`linkage`, `waycover`, `waycover2`, `hoses`, `chains`, `cables`, `served`, `swivel`, `copies`, `update`, `clash`,
`sequence`, `productvideo`, `sequenceframe`, `props`, `people`, `weather`, `mesh`; `core/functions.py` (`tour=` links
only); the guide's tour lines if they name these stops. No test model changes, no app code.

## Goal

Each of these learning sets opens in surroundings that fit what it teaches – machines in a factory or workshop hall,
looks and product videos in a clean studio, Slice in a see-through view, people and props on a quay or in a warehouse
round real-size things, weather outdoors – with cameras that frame the subject, so the set can be shown as it is.

## Background

- Study 0224 (`tasks/0224-study-tour-sets-up-to-date.md`): all 66 non-machining stops work; almost every set is PRODUCT
  light, plain grey studio, a default ISO camera. Its table names the framing faults: `materials` (Wear not visible at
  the camera's distance), `mechanism` (the scissor platform at 1.5 m out of frame), `night` and `weather_step` (almost
  black at 400 px – a floodlit spot in frame; `weather_step` at ~0.6 instead of the end), `sequence` (model small at the
  start), `people` (a desk-size crane beside life-size people → people on the Quay round a real-size prop). Links to
  add (`tour=` in `core/functions.py`, no new stop): `scene.props_detail` → props, `poses.pose` → update,
  `joints.couplings` → `cables` (and `tracks`, which 0229 owns: the link only).
- Surroundings (`core/surroundings.py`): `SEA`, `DECK`, `QUAY` and halls `FACTORY`, `CNC`, `ASSEMBLY`, `WAREHOUSE`
  (seen from inside; walls see-through from outside); the studio looks (PRODUCT etc.); props and people (0155, 0157).
  "See-through" = a set whose point is seeing inside (Slice, cut-away, X-ray look).
- **Lead's default per set** (change it where another fits better – say why in the report): `looks` studio (showroom
  light, closer camera on the worn group); `cutaway` see-through (Slice shown in the studio); `cylinder`, `linkage`,
  `waycover`, `waycover2`, `hoses`, `chains`, `swivel`, `clash`, `copies`, `update`, `mesh` a hall (`FACTORY` /
  `ASSEMBLY`; a desk-size test model on a workbench or stand prop where that reads better than on the floor);
  `cables`, `served` `WAREHOUSE` or `FACTORY`; `sequence`, `productvideo`, `sequenceframe` studio (product-video look);
  `props`, `people` `QUAY` or `WAREHOUSE` with real-size props (container, pallet, IBC – 0155's props); `weather`
  outdoors (`QUAY`) with a floodlit spot for night.
- Owner rules: never the Fresing 400; never the demo vessel's equipment; test models only in pictures. The app's aim:
  simple for users who do not know Blender – a set must still show its function first, the surroundings second.
- Others at the same time in `tour.py`: 0230 (crane hub + `mill`), 0231 (Lifting sets), 0229 (`tracks`), 0234
  (offshore sets), 0235 (`faces`, `decals`). Each owns its sets; `tools/tour_versions.py`'s record file is shared –
  merge `main` once at the end and re-run `--record`.

## What to do

1. For each set: its surroundings, light / look, camera(s) and frame so the subject fills the picture and the function
   reads; the framing fixes above; stops' "what you should see" texts updated where the picture changed.
2. The `tour=` links above.
3. `changed=` on every set you changed, `tools/tour_versions.py --record`; every stop's Go + check passes; every set
   0 clashes (`tests/test_tour_clash.py`); the tour's build time before / after (web machine) – keep the whole tour's
   build within about +30 % (study: 169 s); say which set costs most and why.
4. A 400 px picture per changed stop in `tasks/img/0233/` (test models only), a before / after sheet for the owner.

## Done when

- [ ] Every listed set in a fitting environment (table in the report: set → surroundings → why)
- [ ] The five framing faults of study 0224 fixed; the links added; precheck green
- [ ] Build time within the limit; all stops' checks; 0 clashes; full suite green; report filled in, merged, released

## Not in this task

Test model changes (0235 for faces / decals; 0234 for the hulls); the crane hub, `mill` and the other milling sets,
the Lifting sets, `tracks`, `spool`, the offshore sets, `house`, `operator`; lessons (0230); app code.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
