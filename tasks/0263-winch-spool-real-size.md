# 0263 – Real size, category C: the winch model's A-frame ×2.5, the spool model's carousel ×2 (rope parts kept)

**Who:** worker · **Status:** done (0.2.226, 24 Nov 2026) · **Branch:**
`task/0263-winch-spool-real-size`
**Started by:** lead, 21 Nov 2026 (owner 14:20: every model at a realistic scale, one fix task per type; study **0258**
category C) · **Model:** Opus · effort High
**Area:** Test models lane – `tools/make_test_paths.py` (`test_paths_a` + `_b`), `tools/make_test_spool.py`, the cable part
of `tools/make_test_flex.py` if `flex_drawn`'s cable needs it, their `tests/data/` files + `fresing_render/data/` copies,
maker tests; every place that holds their numbers: `blender/tour.py` – the sets `cables`, `spool`, `served` and the
cable part of `flex_drawn` (**numbers, cameras and framing only**, not surroundings), `pccheck/checks.py` (their lines),
the tests and tools that read them (`grep -rln "test_paths\|test_spool" tests tools fresing_render`; 0258: expected
lengths and turns in ~30 tests), real-app scripts, `tools/guide_screens.py` + guide pictures and texts,
`tools/tour_versions.py`'s record.
**Not:** app code – the cable, spool and catenary solvers (`core/paths.py`, `core/spool.py` …) stay as they are (a fault
found → report it); the public demo; `test_tracks`, `test_swivel`, the offshore models (already real).
**Private vessel:** no – public test models only (CLAUDE.md section 6).

## Why

Study 0258 (`tasks/0258-study-real-sizes.md`, `tasks/img/0258/3_winches_spools.jpg`): the rope parts are real already
(drum Ø0.60, sheaves Ø0.53 / 0.39, wire Ø20–24, D/d 22–30), but the A-frame is 2.1 m tall and the carousel Ø2.0 with a
core too small for its Ø40 cable – beside people they look like models of models.

## The sizes (0258's proposal – lead's decision)

- **`test_paths_a`** (+ `_b`): the **A-frame and base frame ×2.5** (clear height ~5 m, inside 3–8 m); **drum, sheaves,
  wire, chute keep their size and names** – the rope route gets longer, the sheaves sit higher. The deck winch stays.
- **`test_spool`**: the **carousel ×2** (Ø ~4.0, core Ø ≥ 1.0–1.6 for the Ø40 cable's bend radius); the **level-wind
  winch stays** as it is (real). Coil, layers and cable Ø kept; more cable fits – say how much the test length changes.
- **The rule (0258):** scale the layout, never the parts with a real size. Same part names, tree, colours, joints,
  revisions; variants follow their `_a`.

## Watch

- **Expected numbers:** cable lengths, payouts, turns, layer counts, leave angles and fleet angles change for a real
  reason now (longer routes, a bigger core) – not "old × k". Work each new expected value out from the geometry (or the
  solver's own closed form) and say in the report how; never copy what the code prints into the test.
- **Triangles:** 0258 measured **+51 %** for `test_paths_a` at ×3 (the big round parts reach the 0.5 mm facet cap). Keep
  the rope parts at their size and measure again; if it is still large, say so and propose before touching the importer.
- The spool's carousel layers alternate (CLAUDE.md section 8): with another core / layer count keep the partly
  paid-out top layer the right way round – check the guide cage / leave point stays on its rollers.
- Every tour animation 0 clashes, every stop's check, framing again, `changed=` + `python3 tools/tour_versions.py
  --record` after merging `main` once; tests' total time within about +15 %.
- A change the private demo kit could feel (none expected – only test models change) → say so in the report.

## Done when

- [x] The makers make the new sizes (both copies, variants); maker tests green
- [x] Every test, tour stop, real-app script and PC-check line green; every changed expected number listed with how it
      was worked out
- [x] Sets framed again, 0 clashes, `changed=` + the record; guide pictures and texts updated
- [x] Triangles / import times before–after; tests' total time within about +15 %
- [x] A line-up picture (person 1.75 m + IBC, test models only) in `tasks/img/0263/`
- [x] Report filled in, merged, released

## Not in this task

Arms / hoses (0261), routers / chains / way covers (0262), mechanisms (0264), the solvers, the public demo, surroundings.
**Never the cable-lay vessel's equipment, never the Fresing 400.**

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (4-core web machine), 23 Nov 2026 · version 0.2.226 · branch
`task/0263-winch-spool-real-size`. No subagents (test models and their numbers; the independent checks of the numbers
were scripts written for this, see below).

**Owner's wish during the task (23 Nov, in the chat, with a picture of the old cable model):** "This should be Winch
cable and the winch should fill up with cable" – asked back: wire wound on the drum that winds on and off in the app,
the part name WIRE ROPE kept. Done as below; it goes beyond the brief (a new part and a test set-up that uses the
spool function).

**What changed:**
- `tools/make_test_paths.py` (`test_paths_a/_b`): base frame and A-frame x 2.5 (``K``): base 7875 long, rails
  ±700..±950, top z 250; luff axis (3750, 0, 1825), legs 3000 to SHEAVE 1, 300 thick; hinge pins Ø125; A-frame about
  5 m tall. Kept: drum Ø400/Ø600, sheaves, sheave pins, V rollers, chute, Ø24 rope, bearing blocks. SHEAVE 2 stays 100
  above the luff axis (at 250 luffing lowers it 8.5 mm and the rope would sink 1.7 mm into the V rollers at ±15°; at
  100: 0.66 / 0.35 mm, as before). The top cross beam moved to the legs' back half (v -300..0): x 2.5 behind the legs
  the rope from the drum ran through it at +15°; now both rope runs pass ≥ 75 mm clear over the whole luff range.
  **Winch:** new part **WIRE ON DRUM** (two full layers of Ø24 wire, r 200..244.785 = 212 + 24 cos 30° + 12, one
  revolved solid); the rope lies on it (middle r 256.785). The drum is **300 between its flanges** (was 400): the app's
  drum check wants a fleet angle ≤ 1.5° and SHEAVE 1 is 5.4 m away (400 wide gave 2.0°, 300 gives 1.46°). Revision B's
  GUARD moved onto the rails behind the drum. 17 → 18 parts (B 19), docstring rewritten.
- `paths.set_up_test_model(scene, winch=False)`: always makes "Drum turn" (drum + its wire turn together); with
  `winch=True` the drum is also a winch drum (`paths.TEST_DRUM` = "Winch drum", spool.add): the rope starts on it,
  39.7 m on it (layer 3 of 4, holds 67.5 m). The tour set `cables`, the PC check `motion.paths` and the guide pictures
  use `winch=True`; the path-reader tests keep the plain set-up (6 contacts, the first on WIRE ON DRUM).
- `tools/make_test_spool.py` (`test_spool`): the carousel x 2 in plan (``KC``) about its axis, now at x 4000 (1 m clear of
  the winch): plinth r 1800, turntable / rim r 2000, core r 600..640 (Ø1.28: 17 cable diameters to the inner layer's
  middle), layers r 680..1680 (25 turns), top layer from r 1200 (12 turns), guide at (5200, 0, 430), arm pivot
  (6600, 0, 0), reach 1400, deck plate -700..7000 x ±2400. Heights, the Ø40 cable, its 3 full + 1 partial layers (the
  top layer still laid from the rim inwards: the leave point stays at its inner end, the arm geometry is the old one
  x 2, so the arm angles are the same), guide sheave, pins, clamp and the whole winch unchanged. The cable no longer
  lies 2.2 mm in the guide's lip (it bends round the carousel at r 1200 now). **Test length: 166.2 m → 664.6 m on the
  carousel (x 4.0)**; the power cable 1748.1 → 2690.6 mm.
- App code (outside the brief – a fault the new model showed): `core/web3d_tubes.trimmed` and its JavaScript twin
  `web/fr_tubes.js` ended a spool rope's cut with the 1e-6 margin meant for its start; on the 664 m carousel at its
  first frame a vertex lies one float32 step (0.06 mm) past the cut, the page kept the next vertex too (folded onto the
  cut): one ring more than the app (4 web-3D tests failed). The end is now compared strictly, as the app's tree does.
- Test set-up numbers in app files: `spool.set_up_test_model` (carousel and arm axes), `tour` (`DRAWN_PATHS_AT` y 2.5,
  the drawn route's four clicks, "Drum turn" in `drawn_cable_setup`, `_check_cables` for the winch, `_check_spool`'s
  carousel turn), PC check `motion.paths`, `ui_test_paths.py` / `ui_test_spool.py` (views, the click finder's sample,
  coil radii).
- Tour: `changed="0.2.226"` on the sets cables, spool, served, flex_drawn and the stops cables (text: the drum full of
  wire), drawn_cable, spool, served; `tour_versions.py --record`.
- Guide pictures made again: `view_cables_rope`, `view_cables_luffed`, `view_cables_looks`, **new**
  `view_cables_winch.jpg` (+ its line in the guide), `view_drawn_cable`, `view_spools`, `view_spools_full` (the carousel
  "paid out to its 2nd layer" now leaves 280 m: layer 1 is 185 m), `panel_cables`, `panel_spools`. `guide_screens.py`
  has a mode `cables` for the four cable pictures (they had no maker before). `view_cables_served` is the cable only:
  not changed.
- Line-up `tasks/img/0263/lineup.jpg` (cable machine, spool model, 1.75 m person, IBC; front, orthographic, Cycles).

**How the expected numbers were worked out** (never copied from the code's output):
- The cable model's rope: a separate script with plain trigonometry that finds every straight run by bisection on the
  tangent condition (not the maker's closed form), from the layout alone: lengths 14841.509 / 14483.249 / 15107.289 mm
  at 0 / -15 / +15°, wraps (drum, sheave 1, sheave 2, chute) 143.261 / 172.444 / 119.183 / 50.000° at 0° etc. – equal to
  the maker's to the last digit. Start (868.215, 600) and end (8013.111, 573.117), roller axes and touch points from
  the layout by hand.
- The carousel: the Archimedean spiral's length in closed form (b/2 (θ√(1+θ²) + asinh θ)): 185356.846 per full layer,
  108574.513 for the top layer, 664645.050 in all; part boxes by hand from the radii.
- The winch: turns per layer from the flanges and the app's pitch for a drum without a groove (1.06 d = 25.44 mm):
  10.849 / 10.849 / 5.425 turns at r 212 / 232.785 / 253.569 = 38.968 m, plus the app's two climbs of a quarter turn
  (0.731 m) = 39.70 m, as the app shows. 1 m off layer 3 turns the drum 1 / 0.2536 rad = 226° (measured 226°).
- Tests changed for another reason: the luff angle that lays SHEAVE 1 into the drum is now -135° (was -110°: 3 m legs);
  there SHEAVE 2 swings above the rope (its seat ~400 mm over the straight), so the cable also says "no longer touches
  SHEAVE 2" and flipping SHEAVE 1 back gives that note instead of OK. "Away" (SHEAVE 2 lifted off) 0.75 / 3.2 / 3.6 m (was
  0.3 / 1.6 / 1.9: the run between the sheaves is 2.8 x longer). The "wrap far wider than drawn" warning moved to
  SHEAVE 1 (SHEAVE 2's 119° is less than the 120° margin). The carousel's turn after 6 m: > 4.5 rad (6 / 1.24 … 6 / 1.20 =
  4.8 … 5.0; was > 6.0 at r 0.6). The rope is read in pieces as the app reads a cable (`paths.centreline`) in
  `test_paths_model.py` / `test_paths_independent.py`: one `tube_centreline` stops at 1,024 cuts (14 mm apart on 14.8 m).

**Tested and measured** (4-core web machine):
- Import (`step_reader` alone, 2 runs each), before → after: cable model Draft 11,620 → 11,952 triangles (+2.9 %),
  Normal 25,516 → 25,716 (+0.8 %; the rope parts kept their size, so not the +51 % the study measured at x 3); spool
  model Draft 21,196 → 22,376 (+5.6 %), Normal 41,542 → 44,660 (+7.5 %). Time 1.2–2.8 s before and after.
- The 28 test files that read these models: 653 passed, **886 s before, 800 s after (−10 %)**; plus the new
  `test_paths_winch.py` (3 tests, 7 s). Maker tests, `test_web3d_tubes_core.py`, the tour stops of the four sets, their
  clash check (0 clashes each) green; `test_tour.py` 171/172 before the carousel fix, then the changed stops green.
- PC check lines motion.paths, motion.spool, looks.served_cable, web3d.moving, motion.drawn: 5/5 OK (bpy module).
- Real app (xvfb): `ui_test_paths.py` 36/36, `ui_test_spool.py` 43/43.
- GitHub: 3 full runs. Run 45292265199 stopped in the precheck: 0.2.220 had gone to task 0316 (renumbered to
  0.2.221). Run 45292487479: everything green but one test that came with main (`test_remove_independent.py`, task
  0292's): it removed WINCH DRUM to see the cable named – the rope runs over WIRE ON DRUM now, so that part is removed
  instead. Run 45296284849 green, but main had moved with code and 0.2.221 had gone to task 0296: merged once more,
  renumbered to 0.2.222, a fourth full run (45301254782, green) – meanwhile 0.2.222 went to task 0302: merged again,
  renumbered to 0.2.223, a fifth run (45309915972, green) – meanwhile 0.2.223 went to task 0308: merged again,
  renumbered to 0.2.224, a sixth run (45318515161, green) – meanwhile 0.2.224 went to task 0290: merged again,
  renumbered to 0.2.225, a seventh run (45328947436, green) – meanwhile 0.2.225 went to task 0298: merged again,
  renumbered to 0.2.226, an eighth run (45335595420): two failures from the merge – task 0298's new
  `test_flex_avoid.py` clicked the cable model at its old size (now the real-size spots of the tour), and the new
  test file put two files that skip one test on GitHub in one group (`test_spool_independent.py` added to
  `SKIPS_ON_GITHUB` in `tools/ci_groups.py`) – a ninth run. (Nine runs: six version clashes, two real failures.)

**Open points / follow-up tasks:**
- The cable panel shows a spool start as "Start on: Joint Drum turn (motion)" (the joint's empty): a plain-words text
  like "Start: on the drum Winch drum" would read better (Motion lane, small).
- The tour's `cables` animation pays 1 m out (the drum empties a little); hauling in to show it filling needs the free
  end shortened (it is 1.25 m). Say if the stop should haul in instead.
- The site's two built pages (`site/media/test_atc.page.html`, `thor.page.html`) carry an older copy of `fr_tubes.js`;
  they are made again by the site kit.
- Private demo kit: nothing it uses changed (only test models, test set-ups and the web page's cut of a spool rope,
  which the kit's web export would only draw more exactly).
- Branch `task/0263-winch-spool-real-size` can be deleted on GitHub after the merge.
