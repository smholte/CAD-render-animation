# 0173 – Demo realism from study 0152: lay data, lighter cable, an ROV at the touch-down, the tipping winches spooled

**Who:** worker (web session) · **Status:** done · **Branch:** `ccr-1db7fd83-auleup`
**Started by:** lead, 17 Nov 2026 · **Area:** Demo models lane (`fresing_render/demo_model/`, `blender/demo.py` stages and
captions, `tools/make_demo_*.py`, `tests/test_demo_*.py`) + Flex lane for two small points (`core/catenary.py`'s
`WET_200`; the order in `paths._bake` for a cable that follows a kept-tight wire). **Model · effort:** Opus · High.
Claude Code on the web, environment "CAD-render-animation".

## Goal

The cable-lay demo looks and reads like a real, controlled lay to an offshore engineer: the lay numbers on screen in
the into-the-sea shot, a cable weight that matches real cables, an ROV watching the touch-down, consistent time-lapse
captions – and the last two demo winches (the tipping winches) spool their wire like the others.

## Background

- Study **0152** (`tasks/0152-*.md`, report on `main`) compared the demo with public references: almost everything is
  plausible. Its proposals 1, 2, 3, 4 and 6 are this task (proposal 5 – a fuller carousel – was done in 0159;
  7 and 8 – the pull-in variants – are later, owner decides).
- **0174** (0.2.139) drew every spool layer as cable and gave every demo winch its wire rope, except the two
  **tipping winches**: a Build baked their drum wire standing still, because `paths._bake` reads the places of a cable
  whose speed follows a kept-tight wire *before* that wire's payouts are written. The code that spools them is in
  0174's branch history (commit "every demo winch spooled": a lead cable + `set_follows` ratio ±1) – see 0174's
  report and its winch table. They also have a 6.5° fleet angle (no level wind, 2.6 m lead).
- **0172** (0.2.138) changed the D's gutter / set-down; its tests hold the demo's current numbers.

## What to build

1. **"Lay data" box in shot 8** (0152 #1): top tension, bottom tension, layback, departure angle, lay speed, water
   depth – from `paths_sea.numbers` (the sea stage writes them to the notes today) – shown as a label / card in the
   shot (the app's label system, 0027/0091 style), values changing with the frame where they change. Speed caption
   says **"surface lay"**. Readable in the shot's 4K and HD frames; also in the web page if labels go there (if not:
   say so in the report, no web work here).
2. **Wet weight 51 → ~38 kg/m at Ø 200** (0152 #2; `core/catenary.WET_200`, scaled with Ø² as now). **Lead's choice:
   keep the layback at 32 m** – the catenary's shape stays the same, only the tensions change (bottom ≈ 7.7 kN, top
   ≈ 18.9 kN, 66°), so the cut-away and the touch-down do not move. Update the expected numbers in the catenary / sea
   tests and the demo's notes; check other models that use `WET_200` (test models, the tour) and say which changed.
3. **An invented work-class ROV in shot 8** (0152 #3): box frame with buoyancy block, thrusters, two lights and a
   camera, a tether to the vessel's stern (an app hose/cable if it stays cheap at Build; otherwise a slack tether that
   rides with the ROV – say which and why). One joint (or a rider) keeps it beside and a little above the touch-down
   as the vessel lays; it looks at the touch-down. Lights on in the night shot (0166's shot 13) if the ROV is there.
   Left out of the clash check (as the park, 0166) with its clearance to the cable and seabed tested instead.
   Triangle budget: say what it costs; ≤ ~40,000 triangles.
4. **Handler tilt in shots 9 and 12** (0152 #4): the caption gets its "× N" like the other time-lapse captions (or the
   move is slowed to ~8–10 s – pick one, say which).
5. **Captions in shot 5** (0152 #6): name the tensioner class ("15–20 t tensioner") and the cable ("Ø 200 mm, MBR 3.5 m")
   once.
6. **The tipping winches spooled** (0174's open point): fix the order in `paths._bake` (a cable whose speed follows a
   kept-tight wire reads that wire's payouts after they are written), then spool both tipping winches' drums with
   their wire (0174's code from its branch history). Add a fairlead / short level wind so the fleet angle is ≤ ~2°, or
   say why not. Test: the drum wire's length on the drum changes with the tipping, matching the wire's payout within
   a few cm, and the Build is the same at any frame shown (0138's rule).
7. Every visible change: guide (the demo section), the demo's notes, test-tour/PC-check lines only where a function
   changed (point 6 may need none – say so).

## Design (worker, 17 Nov 2026)

Split (one owner per file):
- **Subagent "rov maker"** (worktree): new `fresing_render/demo_model/rov.py` – `build(p: Params) -> (Asm, info)`, an
  invented work-class ROV in its own coordinates (mm): origin at the middle of the skids' underside, +x forward (where
  camera and lights look), +y port, z up; about 3.0 x 1.8 x 1.9 m. Parts (each ONE solid with a colour, `geom.Part`):
  `ROV FRAME` (box frame of beams, grey), `ROV BUOYANCY` (yellow foam block on top), `ROV SKID` (runners),
  `ROV THRUSTER DUCT` x 7 (4 horizontal vectored at the corners, 3 vertical) each with a `ROV PROPELLER` in a turning
  sub-assembly, `ROV LIGHT` x 2 + `ROV LIGHT LENS` x 2 (front, either side), `ROV CAMERA` + `ROV CAMERA LENS` (front,
  middle), `ROV MANIPULATOR` x 2 (simple folded arms), `ROV TETHER TERMINATION` (top, aft). Joints: one rotate
  joint per propeller "ROV: Thruster k turn" (drive by "operator"). `info`: `tether` (point + direction, mm),
  `camera` (point + view direction), `lights` (points), `box` (min, max), `triangles_hint`. In `layout.py`:
  `FILES["rov"] = "demo_rov.step"`, `"rov"` in `MACHINE_FILES`, built with the park (`with_park`), its info in the
  route sheet as `"rov"`. Test `tests/test_demo_rov_model.py` (no Blender). Budget ≤ 40,000 triangles.
- **Worker:** everything else. `core/catenary.WET_200` 51 → 38; `paths._bake` (kept-tight cables first, then the
  cables whose speed follows a kept-tight joint get their places read again after the payouts are written);
  `core/callouts.py` + `blender/callouts.py`: a label on a cable into the sea may hold live fields (`{top}`,
  `{bottom}`, `{layback}`, `{angle}`, `{depth}`, `{speed}`, `{laid}`, `{hanging}`), several lines; `demo.py`: the lay
  data label and captions, the ROV stage (import, Still, place beside the touch-down looking at it, lights, tether,
  clash hook), the tipping winches spooled (0174's code) with a fairlead.

## Done when

- [x] Points 1–7; Make demo project runs; its clash check stays at 0 rows (ROV left out, its clearances tested)
- [x] Expected numbers in the demo / catenary / sea tests updated with a one-line reason each; nothing loosened
- [x] Stills of shot 8 (lay data box + ROV, day and night if shot 13 shows it), shot 5's caption and a tipping-winch
      close-up, as `tasks/img/0173_*` (the demo is invented – fine to commit), named in the report
- [x] Make demo time and the project size before/after in the report
- [x] An independent tester (a subagent that did not write the code) checks points 2 and 6 by reading and running
- [ ] Tests added/updated; full suite passes on GitHub; report filled in; merged; release as usual (section 7)
- [x] Report ends with the owner's steps (which shots to look at on the RTX 3090)

## Not in this task

- Pull-in variants (0152 #7, #8) – owner decides later.
- Drum layers riding up over crossings (0174's first open point), the full coil on the web page (0174 / Web 3D lane),
  0172's open points 1–4 (Flex lane, later).
- The web player (0179 is running in the Web 3D lane: `fresing_render/web/`, `blender/web3d.py`, `core/web3d*.py`).
- The vessel's freeboard, sea state, lay speed (0152 found them plausible).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (worker session), 17 Nov 2026, branch `ccr-1db7fd83-auleup`. Released as
**0.2.141**.

**What changed:**
1. **Lay data box in shot 8** – labels got two new abilities (any project, 5 Scene & Render > Labels): several lines
   (type `\n`; the box grows, lines left-aligned) and **live fields** on a cable that hangs into the sea: `{top}`,
   `{bottom}` (kN), `{layback}`, `{angle}`, `{depth}`, `{speed}` (m/min, from the speed joint's keys), `{laid}`,
   `{hanging}` – filled in again for every frame of a video or still (`core/callouts.fill`,
   `blender/callouts.label_text` / `live_values`; `video._lines` draws them left-aligned at the measured line step).
   The demo's label "Lay data" (top/bottom tension, layback, departure angle, lay speed, water depth) points at the
   middle of the hanging cable (the touch-down lies at the picture's lower edge) during shot 8; the caption says
   "surface lay". Shot 8's camera aimed lower and wider so horn A, the
   touch-down and the ROV stay in the picture all through (lens 19, orbit −5°; the ROV above the caption's band).
   Web page: a part card shows a label's fields filled in as at the frame exported (`web3d.part_labels`, one line
   after 0179 was merged); the card shows one block of text (its line breaks as the page's CSS treats them).
2. **38 kg/m at Ø 200** (`core/catenary.WET_200`, scaled with Ø² as before). Layback mode keeps the shape: the demo's
   cable leaves horn A at 68° with the touch-down 32.0 m behind; tensions now **7.3 kN bottom, 19.4 kN top** (were
   9.8 / 26.1; the brief's 7.7 / 18.9 used h = 30 m, the demo's horn leaves 32.7 m over the seabed). Test models,
   tour and PC check use Layback mode: only their tension numbers change; no test held an absolute tension (they test
   T_top − T_bottom = w g h). Tooltip, guide and docstring say 38.
3. **The ROV** (`demo_model/rov.py`, own file `demo_rov.step`, made by a subagent; `blender/demo_rov.py`): frame,
   buoyancy, skids, 7 ducted thrusters (propellers turn, Run motor), two lights (emission lenses), a pan-tilt camera,
   two manipulators, bend restrictor. 31,014 triangles at Normal (the brief's budget 40,000), plus its tether.
   Station from the maker (`rov.station`): level with the touch-down, 8 m inboard of the cable (the far side from shot
   8's camera, seen through the cut-away), 2.5 m over the
   seabed, facing it. It is **Still** for vessel motion; no joint is needed to keep pace (the vessel stands still in
   the scene, the seabed moves). Measured: the touch-down moves ±1 m with the heave and drifts up to ~3 m aft over
   shots 1–8b (the lay's lengths are fixed per moment); the ROV keeps its station and the touch-down in view (within
   ~19°). **Tether:** a hose (4 Motion > Hoses) from its restrictor to the transom, 46.7 m, so it follows the vessel's
   heave – cheap: the hoses' pass through the frames is the same one the cables use (no extra pass), its solve ~1 s.
   Shown in shots 1–8b, hidden from shot 9 (the second end is laid beside turbine B). Not in shot 13 (night): there
   it is hidden, so "lights on at night" does not arise; its lights glow all the time. Left out of the clash check
   (`demo_rov._clash_hook`); its clearance tested instead: ≥ 3 m from the lay cable, 1.5–4 m over the seabed at every
   37th frame of shots 1–8b.
4. **Handler tilt:** captions in shots 9 and 12 say "(x 30)" (2 min real estimated / 4 s on screen) – chosen over a
   slower move to keep the video's length.
5. **Shot 5's first caption:** "A 15–20 t tensioner on the Ø 200 mm power cable (MBR 3.5 m): the top track lifts
   (real speed)".
6. **Tipping winches spooled** – `paths._bake`: cables kept tight go first and write their payouts; a cable whose
   speed follows one of them, or whose carriers a joint following one of them moves, is then put right **without a
   second pass through the frames**: the motion empties of the joints involved are read in the same pass (`_plan`),
   and each place is corrected from the value the pass saw to the written one (`_after_tight`:
   W' = M · L(seen)⁻¹ · L(written) · M⁻¹ · W, outermost joint first). A first version read the frames again (+70 s per
   demo Build, ~24 Builds in the demo tests); the correction gives the same shapes as a re-bake to 1e-4 m. The two
   tipping winches got **narrow drums** (240 mm between flanges, was 800; `layout.TIPPING_DRUM_LENGTH`): fleet angle
   **1.7°** (was 6.5°), its warning set at 2°; no level wind (no room on the stern). 0174's code brought back
   (`demo._tipping_winch`). Every demo winch is now spooled.
7. Guide: demo section (ROV, cable weight, lay data, tipping winches, captions), Labels section (lines and live
   fields). Test tour stop `sea_cable` and PC-check line `motion.sea_cable` now also add and check a lay-data label
   (shared `tour.add_lay_label`); no new stop or line (labels and the sea cable exist; the tipping drums are demo
   content). Changelog 0.2.141.

**Tested and measured** (4-core web machine, the demo made with `tests/demo_made.py` (small form), Blender as a
module, `tools/measure_cables.py`; before = main at 0.2.139):

| | before | after |
| --- | --- | --- |
| Make demo | 339 s | 354 s (ROV stage 9.5 s, tipping drums +8 s in `winch_wires`) |
| Build animation (inside the make) | 117 s | 122 s (one pass through the frames as before; the ROV tether's solve) |
| Saved project | 220.8 MB | 226.4 MB |
| Sea numbers (demo) | 9.8 / 26.1 kN, 68°, 32.0 m | 7.3 / 19.4 kN, 68°, 32.0 m |
| Tipping drums | CAD sleeve, fleet 6.5° | spooled, 54 m on each, fleet 1.7°; ~34 m paid out in shots 10–11 |

Tests: new `tests/test_label_fields.py` (3: fields, lines, a drawn 7-line box in a still), `tests/test_demo_rov_model.py`
(9, 2 by me: station, tether), `tests/test_demo_project_realism.py` (8: 38 kg/m tensions, lay data at every 25th
frame of shot 8 at HD and 4K inside the picture, shot 8 framing, captions, ROV still/beside/clear/hidden, tether
hose, lights, tipping drums follow the tipping payout and turn by their table), `tests/test_paths_moving.py` (+1:
failed before the fix), `tests/test_tight_followers_independent.py` (21, the independent tester's); updated
`test_catenary.py` (38 kg/m, the demo's numbers), `test_demo_project.py` (joint count + 4 travel joints + 7 ROV joints,
11 spooled, stage order, the tipping drum wires' shapes the same when Build starts at the last frame),
`test_demo_project_quadrant.py` (tipping drums by table again). Locally: those files on the made demo, the tour's
`sea_cable` stop, `test_weather.py`/`test_label_fields.py` together, guide/functions/tooltips (830 ok).

**Subagents:** (1) "rov maker" (worktree): `rov.py`, its `layout.py` hooks and `test_demo_rov_model.py`; I added the
station and the tether afterwards. (2) **Independent tester** of points 2 and 6 (did not write the code): 21 tests;
it found three faults – a leftover "51 kg/m" docstring, a follower that also had "keep tight" ticked stayed still, a
cable carried by a part whose joint follows a kept-tight winch stayed still – all fixed by me (its tests kept; two of
its pass-count expectations changed from "one extra pass" to "no extra pass" after the second design).

**Open points / follow-up tasks:**
- Web page: a label's live numbers are those of the frame exported, not moving with the page's animation; its line
  breaks follow the card's CSS (Web 3D lane, if wanted).
- Hoses (flex) and swivels on a part moved by a follower of a kept-tight winch are still read before the payouts
  (the tester's note; flex Build comes before the cables) – nothing in the demo does this.
- The touch-down drifts ~3 m aft over shots 1–8b and moves ±1 m with the heave; the ROV could follow it with a joint
  keyed after the cables' Build if wanted.
- The test tour's `spool` stop fails on some GitHub runners (the tight-string solver takes the other branch round
  GUIDE SHEAVE at frame 233, where the full spool's leave point moves on) – Flex lane (0174's stop); seen in 0179 and
  here, green on a re-run both times.
- `tools/ci_times.json` not re-recorded: the new demo file (`test_demo_project_realism.py`, ~3.5 min here) and
  `test_tight_followers_independent.py` (~1.5 min) join their groups with the default estimate.
- 0152 #7 / #8 (pull-in variants): owner decides.

**Stills** (invented content, Cycles CPU, 1280 × 720, 24 samples): `tasks/img/0173_shot8_lay_data_rov.jpg` (shot 8:
the Lay data box, the ROV beside the touch-down, the caption with "surface lay"), `tasks/img/0173_shot5_caption.jpg`
(shot 5's caption), `tasks/img/0173_tipping_winch.jpg` (a tipping winch's narrow drum with its wire in layers going
up the swivel post while the D is lowered). No night still: the ROV is hidden in shot 13.

**GitHub runs:** 6 full runs started. Red: suite 2 (my label test left the add-on registered: fixed) and demo 2
(expected numbers for the ROV's joints and stage order: fixed); one red in the precheck (0179 took 0.2.140:
merged, renumbered to 0.2.141); two cancelled by newer pushes; run 44065946876 on 32d286e red only on the test
tour's `spool` stop ("no longer touches 'GUIDE SHEAVE' at frame 233"), green after re-running that job twice.
That stop is 0174's and fails on some GitHub runners only (0179's report, open point 4); measured here, the wrap
round GUIDE SHEAVE at frames 220–244 stays 0.92–1.44 rad (CAD 1.52), far from "lifted" – the runner's solver picks
the other branch at frame 233. It passed here alone, under full CPU load, and after group 5's other files.
`main` fast-forwarded to the merge of main (documents only) on top of the green commit.

**The owner's check on the RTX 3090:**
1. Install 0.2.141 (Update now), then **Help > Make demo project…** > **Make it**; open it when it is ready.
2. **6 Animation > What it can do today > Build & play**, or render it in the render queue.
3. Shot 8 ("Into the sea", about 1 min in): the Lay data box beside the hanging cable (tensions about 7 and 19 kN,
   layback ~32–34 m, 67–68°, 10.0 m/min, 30 m); the yellow ROV 8 m beside the touch-down with two bright lights and
   its tether up to the stern. The caption ends "(surface lay)".
4. Shot 5: the first caption names the 15–20 t tensioner and the Ø 200 mm cable (MBR 3.5 m).
5. Shots 9 and 12: the handler's tilt captions end "(x 30)".
6. Shots 10–11 (the D lowered and tipped): the two tipping winches at the stern turn and their wire comes off the
   drum layer by layer (seen at the stern, behind the CPS rack).
