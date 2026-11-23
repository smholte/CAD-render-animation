# 0262 – Real size, category B: the gantry routers ×2.5 on a stand, the drag-chain router ×2.5, the way covers ×2

**Who:** worker · **Status:** done (0.2.215) · **Branch:**
`task/0262-routers-chains-waycovers-real-size`
**Started by:** lead, 21 Nov 2026 (owner 14:20: every model at a realistic scale, one fix task per type; study **0258**
category B) · **Model:** Opus · effort Medium
**Area:** Test models lane – `tools/make_test_gantry.py`, `tools/make_test_flex.py` (the **drag-chain** model only),
`tools/make_test_waycover.py` (`_b`, `_c`, `_d`; **not** `_a`, the owner's real sub-assembly), their `tests/data/` files +
`fresing_render/data/` copies, maker tests; every place that holds their numbers: `blender/tour.py` – the sets `gantry`,
`atc` (if it uses the gantry), `chains`, the chain part of `flex_drawn`, `waycover`, `waycover2` (**numbers, G-code
programs, work zero, cameras and framing only**, not surroundings), `pccheck/checks.py` (their lines), the tests and
tools that read them (`grep -rln "test_gantry\|test_flex_chains\|test_waycover_[bcd]" tests tools fresing_render`), the
real-app scripts (0258: gantry 7 scripts), `tools/guide_screens.py` + guide pictures and texts, the site's web model if
it is one of these, `tools/tour_versions.py`'s record.
**Not:** app code (a fault → report it), hoses (0261) and the cable (0263) of `flex_drawn`, the mills (0249 / 0250).

## Why

Study 0258 (`tasks/0258-study-real-sizes.md`, `tasks/img/0258/5_routers_covers.jpg`): the routers are desk / hobby
size on the floor (bed 0.8 × 0.6), the way covers 1.1 m long – beside 0249's VMC (X travel 1000) they read as toys.

## The sizes (0258's proposal – lead's decision)

- **`test_gantry`**: layout ×2.5 (bed ~2.0 × 1.5, a sheet-size router class) **on a stand** so the table top is at
  ~0.9 m (0.85–0.95 working height). Tools keep their real Ø (4–10 mm, only the holders as real); the tool carousel
  becomes a real router changer size (Ø0.4–0.6, keep its 3 tools unless more is cheap – say which).
- **`test_flex_chains_a`**: the same router ×2.5 on the stand; **drag-chain links keep their size** (pitch 40, bend R80,
  links 20 × 32) – the chains just get longer (~47 → ~110 links; measure the cost).
- **`test_waycover_b`, `_c`, `_d`**: ×2 (~2.2 × 0.6 extended), **matched to 0249's VMC X travel** (read it from
  `make_test_mill.py` after 0249); sheet 1.5–3 mm real.
- **The rule (0258):** scale the layout, never the parts with a real size (bolts, rails, guide blocks, motors, chain
  links, tools, sheet). Same part names, tree, colours, joints, revisions; variants follow their `_a` / `_b`.
- **G-code:** programs, work zero and the toolpath of these sets scaled with the bed – feeds and spindle speeds stay
  real (a bigger router does not cut faster). Program times in tests change: list them.
- **Never the Fresing 400's size class** (small mill, BT30, double-arm changer) – a sheet-size router is far from it.

## Watch

- Real-app scripts that click on the gantry (7) are the slow part: every click / hover must still land.
- Import triangles and times before / after (0258: +1 %; the longer chains add parts – measure); tests' total time
  within about +15 %.
- Every tour animation 0 clashes (the stand and the gantry beam's travel), every stop's check, framing again,
  `changed=` + `python3 tools/tour_versions.py --record` after merging `main` once.
- Search afterwards for the old sizes in guide, stop texts and tooltips.

## Done when

- [x] The makers make the new sizes (all variants, both copies); maker tests green
- [x] Every test, tour stop, real-app script and PC-check line green; changed numbers listed with the reason
- [x] Sets framed again, 0 clashes, `changed=` + the record; guide pictures and texts updated
- [x] Triangles / import times before–after; tests' total time within about +15 %
- [x] A line-up picture (person 1.75 m + euro pallet, test models only) in `tasks/img/0262/`
- [x] Report filled in, merged, released

## Not in this task

Hoses / arms (0261), winches / spools / the cable (0263), mechanisms (0264), the mills (0249 / 0250), surroundings, app
code. **Never the cable-lay vessel's equipment, never the Fresing 400.**

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (4-core web machine), 23 Nov 2026 · released as 0.2.215 · branch
`task/0262-routers-chains-waycovers-real-size`. No subagents (test models and test numbers, no app logic; independent
tester skipped).

**What changed:**
- `tools/make_test_gantry.py` (`test_gantry.step`): the layout x 2.5 (``K``): bed 2000 x 1500 x 100 (top z 0), eight
  real T-slots; new part **`MACHINE STAND`** (120 mm tube frame, pads on the floor at z -900: the table at 0.9 m);
  uprights, beam (x -1050..1550, z 500..650), carriage, Z slide, spindle (Ø125, nose z 275), carousel stand from the floor;
  **carousel Ø425** about (1250, 0), disc **12 mm** thick, top z 350 (x 2.5 would be 25 mm: then only 5 mm of T2 showed
  below it and the real-app click on T2 hit the disc). Real size kept: the tools (T1 tip now (0, 0, 245), T2 (1400, 0,
  320), T3 (1250, 150, 310)), `STOCK 300x200x30`, the 4 clamps and M12 screws at x ±168, T-slots, the size-20 rails
  (longer: Y 1450, X 2500, Z 400) and their guide blocks (80 long); servo motors 110 / 90 mm flanges (were 60 / 50).
  3 tools kept (8 pockets as before). 31 → 32 parts. No part inside another (servo pilots in their faces and the tools
  in the disc as before).
- `tools/make_test_flex.py`, the chains model (`test_flex_chains_a.step`): the same router x 2.5 with the same stand
  (imported from make_test_gantry); **links keep their size** (pitch 40, R80, 20 x 32 x 60): X 18 → 24, Y 16 → 21,
  Z 13 → 17 links (47 → 62); travels X ±375, Y ±250, Z -220 .. +150 (tool on the block at Z -215); pin 0 is now worked
  out from where the last pin is drawn (``CHAIN_END``); the maker's checks hold (runs keep ≥ 2 links, 1.0 mm least gap
  between moving bodies). 62 → 78 parts, 16 → 17 shapes. Docstring rewritten with the new numbers.
- `tools/make_test_waycover.py` (`_b`, `_c`, `_d`; `_a` untouched): layout x 2 (``S``): bed 2000 x 600 x 120, sections
  40 thick, **axis 1000 mm** (the test VMC's X travel); real: rails (20 wide), ball screw Ø24, its bearing blocks, motor,
  bolt heads, T-slots, guide blocks' height, **sheet 3 mm**, wiper lips. `_d` is now `--drawn-at 500`.
- Test set-up numbers in app files (no logic): `waycover.TEST_TRAVEL = 1.0` for `set_up_test_model`.
- Tour (`changed="0.2.215"`, recorded): `gantry`, `atc` (carousel joint at x 1.25, pocket at (1.40, 0, 0.35), close
  camera), `chains` (program x 2.5 in X/Y: X±325 Y±200), `flex_drawn` (gantry placed (0, -1.5, 0.9) so its stand is on
  the hoses model's floor; the two bracket clicks moved; "24 CAD links"), `waycover`, `waycover2` (1000 mm). Stops
  marked changed: gcode, accel, atc, setup, chains, waycover, waycover2, drawn_chain, drawn_replace, chain_types.
  Cameras are fitted by the app on the model (checked on the guide renders and the line-up, not stop by stop).
- **G-code programs:** the programs on the block stay as they were – the block keeps its real size and the work zero is
  its top centre, so the program's coordinates did not change (the brief's "scaled with the bed" would have made the
  block 750 x 500 x 75 under the name "STOCK 300x200x30"). What changed is the machine's start: the tip is 215 mm above
  the zero (was 50). Only the drag-chain demo program (moves in the air, no block) is scaled. The acceleration program
  (`tour._accel_program`) has **48 zigzag steps each way (were 24)**: the long first rapid from 215 mm made the
  accelerated time only 1.19 x the plain one (the checks want > 1.2); 48 steps: 1.29 x (13.1 s against 9.5 s).
- PC check: `machining.waycover` (1000 mm axis, drawn at 400 mm), `machining.waycover_two`, `motion.toolchange` (carousel).
- Real-app scripts: `ui_test_gcode.py` (view, carousel, pocket click on z 350), `ui_test_flex.py` (view on the beam, 24
  links), `ui_test_waycover.py` (1000 mm, 200 mm steps), `ui_test_setup.py` (after View All the 300 mm block was a few
  pixels on a 2.6 m machine: the view now looks at the block).
- Guide pictures made again: `panel_4_waycover.png`, `view_waycover.png` (carriage 600 mm along, alt text too),
  `panel_4_flex_chain.png`, `view_toolchange_atc.png`, `view_toolchange_hand.png`, `view_flex_chains.jpg`,
  `view_chain_types.jpg` (`tools/guide_screens.py`: carousel, pocket, cameras). Guide texts had no sizes of these models.
- Line-up `tasks/img/0262/lineup.jpg` (both routers, the two-cover model, a 1.75 m person, a euro pallet; Cycles, processor).

Numbers in tests that changed (reason: the new sizes unless said): `test_gcode.py` (tip 245, g54 -215, carousel),
`test_toolchange.py` (station (1400, 0, 350), machine z in the pocket 75, T3's place, change position -205 = 5 mm above
Z5), `test_flex.py` (62 links, rows 24/21/17, travels from the maker, the link indices checked, X 2.0 = beyond reach),
`test_flex_fit.py` (pins, counts, `MACHINE STAND`), `test_flex_drawn.py`, `test_flex_drawn_independent.py`,
`test_flex_kinds.py` (bracket clicks; beam/carriage clicks at z 0.6), `test_flex_panel.py` (counts 24 / 21 / 17, 62),
`test_machining_fixes.py` (carousel joint), `test_waycover.py` (the two-cover and drawn-at
tests over their own 1000 mm; the single-cover tests keep a 500 mm axis – the app's sums do not depend on the size).

**Tested and measured** (web machine, 4 cores):
- Import (`step_reader` alone, 2 runs each; triangles of the unique meshes), before → after: gantry Draft 4,798 → 5,341,
  Normal 7,580 → 8,375 (+10 %: the stand, more T-slots); chains Draft 480 → 1,016, Normal 624 → 1,416 (the stand; the
  link is one mesh, placed 62 times instead of 47); way covers b / c / d the same counts (1,716 / 2,600 / 1,716 draft).
  Time 1.3–2.1 s before and after for all five (reading the file).
- Locally green on the new models: `test_gcode`, `test_toolchange`, `test_tools`, `test_clash`, `test_toolpath`,
  `test_toolmarks_moves`, `test_web3d_moving` (126), the flex files and `test_waycover`, `test_model_update`,
  `test_setup_window`, `test_workspaces*`, `test_site`; `test_tour.py` 109/109 (every stop's Go and check);
  `test_tour_clash.py` gantry, atc, chains, flex_drawn, waycover, waycover2: 0 clashes. PC check lines motion.flex,
  motion.drawn, motion.flex_kinds, motion.gcode, gcode.acceleration, motion.toolchange, machining.waycover(_two),
  milling.shows_program: 9/9 OK. Real app: gcode 29/29, flex 31/31, waycover 16/16, drawn 25/25, setup 46/46, panel 39/39.
- Test time: the 11 files that read the gantry, summed per file from `--durations`: 551 s before, 524 s after (−5 %).
- GitHub: 3 full runs. Run 45234685360 stopped in the precheck: 0.2.213 had gone to task 0264 (renumbered). Run
  45234961475: every real-app group, the tour, the PC check and both Windows jobs green; one pytest group red on
  `test_flex_panel.py` (it reaches the chain model through `test_flex`'s constants, so my grep missed it; also fixed
  `test_machining_fixes.py`'s carousel joint, which had passed anyway). Run 45242732869 green (renumbered to 0.2.215:
  0.2.214 had gone to task 0265). GitHub's runners were about twice as slow as usual today (pytest groups 13–31 min
  against 10–14), so its times say nothing about these models.
- `main` fast-forwarded (docs run 45249049139): released v0.2.215, the Windows update-from-release check and "Offer the
  release" green. Its landing-page job failed on GitHub's side ("Fetching artifact metadata failed"); a re-run of the job
  cannot work (two "github-pages" artifacts in one run), so the Landing page workflow was started by hand: run
  45250295464 green.

**Open points / follow-up tasks:**
- `view_flex_chains.jpg` shows the whole router: the real-size chains are now small in the picture; a closer camera
  would show them better (the guide's alt text is still true).
- The size-20 rails and 50–80 mm guide blocks are real parts but light for a 2 m router (size 25–35 would be usual);
  kept by the rule "never scale a real part".
- `flex_drawn` still holds the small cable model (0263 scales it; `DRAWN_PATHS_AT` may need moving again).
- Branch `task/0262-routers-chains-waycovers-real-size` can be deleted on GitHub.
