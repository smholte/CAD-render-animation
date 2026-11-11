# 0084 – Demo model: deck re-layout as the owner works (oval route through both tensioners, quadrant on rails)

**Who:** worker · **Status:** done (12 Nov) · **Branch:** `claude/epic-hopper-et0knn` (the session's branch)
**Started by:** lead chat, 11 Nov 2026 (after 0076 and the reference study 0083)
**Lane:** **Demo models** – `tools/make_demo_cable_lay.py`, `tools/demo_cable_lay/`, `tests/test_demo_cable_lay.py`,
`tasks/img/0084-*.png`. No app code (`fresing_render/`), no version, no release.
**Model:** **Opus · effort High** (layout, route geometry and new mechanisms) · **Place:** Claude Code on the web,
environment "CAD-render-animation"

Runs next to 0058 and 0061 (Thursday, Fable day): touches none of their files. **Merge to `main` before Thu 12 Nov
08:00**; if not ready then, merge only after 0058 and 0061 are merged (one more run is fine).

## Goal

0076 made the invented cable-lay spread, but its deck is one straight line (tensioners in a row, one chute in the
middle, a quarter-circle quadrant hinged at the transom). The owner's answers in 0083 show how such a spread really works.
Re-lay the demo model so the demo project (0077) and the motion tasks (0078–0082) show **his** way of working – still
invented, generic shapes and sizes, nothing copied one-to-one from his reference pictures.

## Read first

`tasks/0083-cable-lay-reference-study.md`: **"The owner's answers and step pictures"** (deck layout, cable route during
lay, coil, CPS run, quadrant sequence, cable look) and **"Check against 0076"** (16 rows). `tasks/0076-…` report for
how the code is built.

## Scope – the lead's decisions on 0083's check table

- **Row 1 – deck lanes and the oval route:** two side lanes of raised roller highways (V roller cradles on trestles, a
  grating walkway beside each), the quadrant's middle lane between them with **rails**, a **lower path 1–1.5 m below**
  side A. Route: coil → arch → down the tower → lower path aft on side A → **stern-corner radius controller** (180°) →
  forward on side B **through tensioner 1** → round the **quadrant at its stationary position** (180°, forward end of the
  middle lane) → aft on side A's highway **through tensioner 2** → down **side A's overboarding chute** ("horn") into the
  sea. All bends ≥ MBR (keep 1.15 × MBR). Route JSON = this oval route.
- **Row 2 – tensioners:** one in each side lane; the top-track carriage **lifts** (squeeze cylinders, stroke covering
  Ø 50–500 + clearance) **and tilts back** about a hinge at its aft end. Both in the joint sheet.
- **Rows 3–4:** gripping run **14 links** (4.2 m at 300 mm pitch); pads **150–160° V**, dark matte rubber on a steel back
  plate; squeeze stroke covers the Ø range.
- **Row 5 – Lebus:** two crossovers per turn of **~35°** each, 180° apart, plus riser/filler wedges at the flanges.
- **Row 7 – quadrant system rebuilt:** a **D-shaped quadrant** (semicircle radius ≥ MBR with spokes, a straight bar,
  cable gutter round the curve, hang-off point) on **rail bogies** in the middle lane; a separate **quadrant handler**
  (frame hinged at the transom, tilted 0→~100° by hydraulic cylinders, a **top-centre pulley**); the **quadrant handling
  winch in front of the carousel**, its wire aft over the handler's pulley to the quadrant; **two tipping winches on the
  stern, port and starboard**, wires over **swivelling sheaves** to the two ends of the D's bar. Joints: quadrant slide
  along the rails, handler tilt 0–100°, quadrant hang/tip about its wire point, sheave swivels, winch drums.
- **Row 8:** route rollers about **1.5 m apart** on the straights (instanced copies of one part).
- **Row 9:** one **linear cable engine** (wheel pairs) on side B between the stern corner and tensioner 1 – its wheels
  turn with the cable (a test for 0078).
- **Row 10:** a bellmouth / roller cage where the cable lifts off the coil.
- **Row 13 – loading tower:** an **overhead arch** (~180° radius controller, rollers along its inside) that **only
  slews** about the tower's axis; a hanging guide frame drops the cable into the coil (no trolley in/out). Joint: slew.
- **Row 14:** a hole at the foot of the core with a clamp inside; the coil as flat layers (layer 1 outwards, layer 2
  inwards); the cable end through the hole.
- **Rows 11 + 15 – CPS store:** a rack along one side with 4–6 CPS sets, an **orange twisted ramp** and a curved slide
  to the route at the quadrant's stationary position. CPS look as 0083 describes (pull head, grey tube, yellow
  segments, vertebrae, bend restrictors), ~15–25 m long.
- **Row 16:** chutes are the curved overboarding **horns** at the stern ends of the side lanes (side A used; a horn on
  side B too), the middle lane's stern end is the handler.
- **Quay loading (for 0077):** an extra file `demo_quay_loading.step`: a quay with the standalone storage carousel and a
  route from it to the vessel's stern corner, placed for the vessel moored alongside (0077 shows loading from the quay).
- Rows 6, 12: keep. Optional only if cheap: lightening holes in the rim plates.

Keep: one parameter set, files made at run time (none committed), triangle budget (whole assembly at Normal ≤ ~3 M
placed), every sheave groove a torus at the rope/cable centre radius, `demo_joints.json` with uids that exist.

## Done when

- [x] All files written by `tools/make_demo_cable_lay.py`, with the layout above; route JSON = the oval route through
      both tensioners and round the quadrant; joint sheet updated (tensioner lift + tilt, quadrant rails, handler tilt,
      quadrant tip, sheave swivels, arch slew, cable engine wheels, rollers).
- [x] `tests/test_demo_cable_lay.py` updated: MBR on the oval for Ø 50–500, route passes through both tensioners' grip
      lines and round the quadrant curve, rollers ≤ 1.6 m apart on straights, pad count/pitch, Lebus crossovers ~35°,
      every joint uid exists, triangle budget, quay file imports.
- [x] 4–6 small Cycles pictures (overview from above, the stern with handler/quadrant/horns, the tensioners, the
      arch over the carousel, the CPS rack + ramp, the quay) in `tasks/img/0084-*.png`.
- [x] GitHub green; merged to `main` (no version, no release).
- [x] Report filled in (what changed per row, triangles before/after, open points); `TASKS.md`: 0084 done, 0077 open.

## Not in this task

App code, joints in a project, animation (0077); the moving cable, tracks, spooling, catenary, quadrant motion
(0078–0082); 0058 / 0061 files.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (4 cores), 11–12 Nov 2026 (night).

**What changed** (only `tools/demo_cable_lay/`, `tools/make_demo_cable_lay.py`, `tests/test_demo_cable_lay.py`,
`CLAUDE.md` tools line; new `tools/demo_cable_lay/deck.py`; no app code, no version):
- **Row 1 – lanes and the oval.** Side A = starboard, side B = port, lanes at y = ±(quadrant radius + 1.8 m) = ±5.85 m
  at Ø200 (the D passes between the tensioners). V roller cradles (two rollers in a 120° V, each with its joint) on
  portal trestles, grating walkways with a handrail. Lower path **2.0 m outboard and 1.35 m below side A** (directly
  under side A it would run into tensioner 2's bottom track), rollers on stands. Route: coil -> roller cage -> up the
  hanging guide -> arch -> down the tower -> lower path aft -> **stern turn 180° (R 6.85 m) under the quadrant's rails**
  -> side B: rise (vertical S) -> cable engine -> tensioner 1 -> horizontal S -> **round the D-quadrant 180° (R 4.05 m)**
  -> S -> side A aft -> tensioner 2 -> horn A -> sea; 190 m. All bends of the oval >= 1.15 x MBR (4.05 m at Ø200).
  The stern turn lies just forward of the handler (not in the corner itself): a 180° turn across the middle lane must
  cross the quadrant's path; it passes under the rail girders (cable top 3.90 m, girder underside 4.00 m).
- **Row 2 – tensioners.** One per side lane, side by side (x 24.2–30.4 m). The top track sits in a carriage on a **lift
  frame**: four side cylinders, lift -76 mm (squeezes Ø50) … +902 mm (past Ø500 + 600 mm to let the cable out); the
  carriage **tilts back 0–25°** about a hinge at its **aft** end (both tensioners, `rides_on` the lift). Open top.
- **Rows 3–4.** Gripping run **14 links (4.2 m)**, 36 pads per track; pads **160° V** (40 mm deep), dark rubber block on
  a separate **steel back plate** part.
- **Row 5.** Lebus crossovers **35°** (two per turn, 180° apart) + a **riser wedge** at each flange (ramp over 120°).
- **Row 7 – quadrant system.** **D-quadrant** (gutter round the curve with 24 vertical rollers, spokes, straight bar,
  hang-off pad eye at the bar's middle, tipping pad eyes at the bar's ends) on **4 rail bogies** (8 wheels, `follows`
  the travel) at the middle lane's forward end = the oval's forward turn. **Rails** on girders and trestles from the
  handler to the D. **Quadrant handler** hinged at the transom (0–100°, two hydraulic cylinders with pin points in the
  route sheet, rails on top, **top pulley**). **Quadrant handling winch in front of the carousel** (between the D and
  the carousel's well, on a pedestal); its wire runs aft over the D, over the handler's top pulley and hangs parked on
  the handler. **Tipping winches port and starboard on the stern**, wires over **swivel sheaves** (head swivels on its
  post, ±120°) and hang parked (0083: they are connected when the quadrant is on the handler). Joints: quadrant travel
  (0 … 41.3 m aft), quadrant tip (about the bar through the hang-off point, rides on the travel), handler tilt, top
  pulley, swivels, sheaves, drums.
- **Row 8.** Highway cradles and lower-path rollers every **1.5 m** (31 cradles, 23 rollers; a station is left out where
  a tensioner, the cable engine or another stretch of cable stands in the way).
- **Row 9.** **Linear cable engine** on side B between the stern turn and tensioner 1: 4 wheel pairs (rubber tyres),
  motors, top carriage with a squeeze joint, 8 wheel joints turned by the cable.
- **Row 10.** The arch's **roller cage** (bellmouth) where the cable lifts off the coil, on a swivel under the guide.
- **Row 13.** **Loading tower** beside the carousel (on the lower path's line) with an **overhead arch** (two 90°
  radius controllers + a 0.85 m straight, rollers inside, top chord) that **only slews** (-16 … +25°: the guide reaches
  coil radius 4.5 … 10.5 m), a hanging guide frame with a platform and guide rollers. No trolley.
- **Row 14.** Coil in **15 flat layers** (notches between them) + a partly paid-out top layer; the **cable end** runs
  along the core and through a **hole at the foot of the core** to a **clamp** inside (turns with the carousel).
- **Rows 11 + 15.** **CPS rack** (port, aft half: 3 levels x 2 rows, **5 CPS sets** of 15 m: pull head, grey tube,
  yellow segments, brown vertebrae, grey sleeve, yellow bend restrictors, Ø400), an **orange twisted ramp** (30° twist)
  and a **curved slide** (S-curve) onto side B's highway. The ramp runs outboard of tensioner 1, so the slide joins
  the route just **forward of tensioner 1** (6.6 m before the quadrant's curve), not at the curve itself.
- **Row 16.** Horns at the stern ends of both side lanes (A carries the cable); the middle lane's stern end is the
  handler; the bulwark is open across the stern and where the quay's cable comes aboard.
- **Quay file** `demo_quay_loading.step` (model coordinates, vessel moored starboard side to): quay slab, fenders,
  bollards, the **storage carousel (now Ø16 m)** on its base frame, a quay loading tower with its own arch, cradles
  across the quay and on the vessel's deck, a 90° **boarding bend** onto side A's highway heading forward (where it
  meets the oval: loading = the oval backwards from there), and the cable. Its joints are in the joint sheet.
- Sheets: `demo_cable_route.json` routes main (the oval), core_end, cps_slide, quay_loading; tensioners with grip
  lines, lift limits, tilt hinge, back plates; quadrant (curve, hang-off, eyes, rails, travel, handler with cylinders);
  arch (span, rest guide, slew limits); CPS store; quay; roller stations. `demo_joints.json`: **307 joints** (244 turned
  by the cable; 0076: 121), `rides_on` for stacked joints, relative `follows`.
- Kept: one parameter set; files made at run time; groove tori; `demo_handling_winch.step` (two handling winches now
  on starboard, outboard of the lower path). A bigger cable grows everything (Ø500: carousel Ø46 m, beam 49 m, 170 m
  vessel – a valid test, not a pretty demo).

**Tested and measured** (web session, 4 cores):
- `tests/test_demo_cable_lay.py`: 35 tests, 82 s locally (most of it writing + importing the files). New: the oval's
  order and both 180° turns for Ø 50/120/200/350/500, the route through both tensioners' grip lines and round the
  quadrant's curve, the arch reaching core … rim by slewing alone, MBR on the quay / CPS / core-end routes, rollers
  <= 1.6 m apart on the straights (longer gaps only at a machine or a crossing), pads 160° (flank normals 10°), rubber +
  steel plate, no overlaps, lift/tilt limits and hinge at the aft end, Lebus 35° + 2 risers, core hole, coil layers,
  quay file, every joint uid / follows / rides_on exists (assembly and every machine file).
- Importer, Normal, `demo_cable_lay.step` (32.8 MB): 156 unique / 1,252 placed parts, **1.97 M placed triangles
  (0076: 1.46 M; budget 3 M)**, 11.2 s. Biggest: winch drums 0.44 M, hull bottom 0.28 M, cable rollers 0.25 M, rim
  fence 0.14 M, chain links 0.13 M. Writing all 9 files: 57 s.
- Files: assembly 32.8 MB, carousel + tower 13.6, quay 11.4, storage carousel 7.9, quadrant system 4.7, Lebus 4.1,
  winch 2.4, vessel 1.5, tensioner 1.3 MB; none committed.
- Pictures `tasks/img/0084-*.png` (Cycles on the processor, app importer, Sun look, Open sea, 960 x 540, Preview,
  35–50 s each; saved as 256-colour PNGs, ~0.2 MB each): overview, stern, tensioners, arch, cps, quadrant, quay (7:
  the D-quadrant got its own view, since it now lies at the middle lane's forward end, not at the stern).
- GitHub: 3 full runs, all green (12.5, 16.5, 13.8 min): `main` moved twice while the run went
  (tasks 0035 and 0087 released), so the branch was merged again each time; no failure.

**Open points / follow-up tasks:**
- The stern turn is not in the stern corner but a few metres forward of the handler (see row 1); if the owner's
  vessel turns the cable in the corner itself, his answer decides how the D passes it.
- The CPS slide joins side B forward of tensioner 1, not at the quadrant's curve (the D's gutter has a lip).
- Wires are parked in the rest pose (handling wire on the handler, tipping wires below their swivel sheaves); 0082
  connects them to the D's hang-off and bar-end pad eyes.
- The quadrant's tip joint rides on its travel; on the handler it must also ride the handler's tilt (0082 decides).
- For 0077: joints from `demo_joints.json`; the quay file imports into the same coordinates for the loading scene.
