# 0233 – Learning sets in their own environments: the workshop and studio sets (framing, links, fitting surroundings)

**Who:** worker · **Status:** done · **Branch:** `task/0233-learning-sets-workshop`
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

**Chat / date:** Claude Code on the web, 21 Nov 2026 (Sonnet · Medium). Branch: the session's own branch, merged to `main` as 0.2.199.

**What changed:** (`blender/tour.py`, `core/functions.py` links only; no app code, no test model)

| Set | Surroundings | Why |
| --- | --- | --- |
| looks (Materials) | clean light studio | product look; camera now close on the worn base and trolley (Wear shows) |
| cutaway (Slice), sequence, productvideo, sequenceframe | clean light studio (product light, light-grey background, floor stays "Shadow only") | a visible floor showed its far edge in a turning camera, so it is left out |
| cylinder, hoses, chains, clash, update, swivel, mesh | Clean factory hall | machines in a workshop |
| linkage, waycover, waycover2, copies | Assembly hall | longer machines / two cranes side by side |
| cables | Warehouse | rope, drum and sheaves among pallets and racking |
| served | Clean factory hall | coil close-up |
| props | Warehouse | the real-size line-up (container, pallet, IBC …) |
| people | Quayside + a 20 ft container behind them | study: desk-size crane beside life-size people; the crane is now the small thing at the left |
| weather | stays Quayside | already outdoors |

Framing faults of study 0224: `materials` closer on the worn group; `mechanism` camera keeps the raised 1.5 m platform
in frame; `night` floodlights at strength 4 (was 1, almost black); `weather_step` now shows 0.6 of the video (dusk coming,
rain starting) not the dark end; `sequence` camera a little closer (the column of parts is 1 m tall, so it stays small –
see open points). Links: Couplings → `cables`, Poses → `update`, Props: detail by distance → `props`. `changed=` 0.2.199
on 21 sets and 6 stops, `tour_versions.py --record`, stop texts updated (materials, props, people, weather_step, night).
Subagents: none.

**Tested and measured** (web machine, 4 cores, no graphics card): `tests/test_tour.py` 103 passed (all stops' Go + check);
`tests/test_tour_clash.py` for the 21 sets: 49 passed, 0 clashes; `test_functions`, `test_site` pass; precheck green.
Whole tour build (all 48 sets, `tour.build_all`): 237 s before, 196 s after (the first run was alone but noisier; the added
surroundings cost +1–2 s per set, the most `people` +1.8 s and `crane` noise) – well inside +30 %. 400 px pictures of
every changed stop and a before / after sheet (JPEG): `tasks/img/0233/` (test models only). GitHub runs: see below.

**Open points / follow-up tasks:**
- `sequence`: the model is still smallish at the start (a 1 m column of parts in a 16:9 frame); a camera that follows the
  parts would need a camera move in the animation – not done here.
- `night`: no floodlit spot in the frame (masts are 8 m high; the crane is 1 m); brightness only.
- `tracks` link for Couplings left to 0229 (a second naming of the stop broke `test_a_stop_line_or_section_nobody_names_is_caught`,
  which uses `tracks` as its example; change that test when adding the link).
- Not looked at on a graphics card; the owner should check the quay and halls on his PC.
