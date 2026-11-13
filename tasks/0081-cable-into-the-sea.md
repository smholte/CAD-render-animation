# 0081 – Cable into the sea: catenary, seabed, water clarity, cut-away, CPS on the cable

**Who:** worker · **Status:** done (0.2.91) · **Branch:** `claude/amazing-mayer-6a324q`
**Started by:** lead chat, 13 Nov 2026 (plan: tasks/0075 section E + the owner's answers at its end; 0083 findings)
**Lane:** Flex parts (owner of this task): new `core/catenary.py`, `blender/paths_sea.py`, `ops_paths_sea.py`, a fold
"Into the sea" in `ui_paths.py`, `tests/test_catenary*.py`, `tests/test_paths_sea*.py`; additive in `blender/paths.py`
(a cable's sea end), `props.py`, `reimport.py`, `animation.py` (bake order only). **Sea** (lane free since 0109):
the sea part of `blender/surroundings.py` and `core/sea.py` – **additive only** (seabed, water depth, clarity,
cut-away); the 0109 sea, white caps, hull foam and wake stay exactly as they are. **Demo models:** a new stage in
`blender/demo.py`, the follow-ups below in `fresing_render/demo_model/`, `tests/test_demo_project.py`.
Runs beside 0107 (Web 3D: `web3d*.py`, `lightbake.py`), 0108 (test machinery: `tools/ci_*`, may split tests in
`tests/test_demo_project.py`) and 0110 (Clash: `core/clash.py`, `blender/clash.py`) – **do not edit their files**:
leave the sea cable out of the clash check through the existing `clash.HOOKS`; tour/PC-check counts in
`tools/ci_real_app.py` / `tools/ci_check_pccheck.py` are the usual "whoever merges second" update. Merge `main` once
before you start measuring (0109 is on `main` as 0.2.88).
**Model:** **Opus · effort High** (new geometry + a look; subagents allowed, CLAUDE.md section 2) · **Place:** Claude
Code on the web, environment "CAD-render-animation"

## Goal

The cable leaves the stern and hangs into the sea the way it really does: a catenary from the horn/chute down to a
touch-down point on the seabed, keeping its exact length as it pays out, the touch-down moving with the vessel and the
payout, the laid cable lying on the seabed behind it. The owner can see it: a **cut-away behind the stern** and a
**water clarity slider**. Things fitted on the cable (a **CPS** set, bend restrictors) ride along it, also down the
catenary. The demo gets a shot of it.

## Background

- **Maths (0075 section E, prototype measured):** cable lying on the seabed from its start, hanging from touch-down to
  the hang-off at height h: s² = h² + 2·a·h, X = a·acosh(1 + h/a), laid + suspended = paid out; one unknown solved by
  bisection (0.017 ms). Length kept exactly (72.0000 m for 72.0 m). **Two edge cases** to keep: *too much cable*
  (more than span + depth: it would pile on the seabed → a warning, never a wrong length) and *so tight it lifts off
  its start* (then a two-point catenary of the same length – a plain bisection silently gave a wrong length there).
  Baked per frame at Build (128 points × 250 frames in one mesh): +1.1 ms per frame, 0.0 mm off the solver. Leave out
  currents, bending stiffness at touch-down, dynamics: the static catenary looks right in a video.
- **Numbers (0083, public sources, est.):** T_top = T_bottom + w·h; layback (horn to touch-down) 26–39 m for 20–50 m
  depth at w ≈ 500 N/m wet (≈ Ø 200 cable) and 10 kN bottom tension; departure angle 60–75° below horizontal; lay
  speed about 10 m/min (owner). A CPS set is 10–25 m long, outer Ø 2–3 × the cable Ø, vertebrae 0.3–0.6 m.
- **Owner's answers (11 Nov):** under water: **a cut-away + clearer water, with a slider to set the water clarity by
  hand**. Cable Ø 50–500 mm. Power cable look = black with yellow angled stripes (0078); the texture must visibly
  move – also down the catenary and **not** on the laid part (it lies still on the seabed).
- **What exists:** 0078 cables and paths (`core/paths.py` tight-string solver with lift-off, `blender/paths.py` cable
  item = CAD part + slide joint "Cable <name>" in metres paid out + contacts; tube drawn by Geometry Nodes from a
  hidden shapes mesh; bake at Build after `flex.bake`). 0080 spool start (`a_kind` SPOOL), 0079 tracks. 0085 vessel
  motion (rig of empties; model, deck and props ride a Child Of; `vessel_motion.at_rest`). 0109: the new sea in
  `core/sea.py` + the sea part of `surroundings.py` (spectrum waves, white caps, hull foam, **wake from a vessel
  speed**, deep-water colour), weather channels `fr_wx_*`. The sea has **no seabed and no depth** yet. The demo's main
  route ends with a free straight line "into the sea (task 0081 makes the catenary)" from horn A to
  `p.sea_end_z` (`demo_model/route.py` `main_route`); the waterline is z = 0; the stern is at x = 0.

## Scope

1. **Sea end of a cable** (4 Motion > Cables and paths > fold **Into the sea**, on the selected cable): Add sea end →
   the last contact (horn, chute, quadrant gutter, sheave) is the hang-off; **water depth** (m; default from the sea
   surroundings' new depth, else typed); the start on the seabed either **"touch-down X m behind the stern"** (the app
   works out where the laid cable begins) or **bottom tension** (kN) with the cable's **wet weight** (kg/m; a default
   from the cable Ø, shown, editable). Lay speed = the cable joint (one cable speed, 0078).
2. **The catenary** (`core/catenary.py`, no Blender): length kept exactly, both edge cases (warning + exact
   two-point shape), the touch-down moving with payout and vessel; the cable **leaves the hang-off where the catenary's
   tangent meets its curve** (like a wheel's tangent point in `paths.py`: no kink); when the catenary is steeper than
   the horn/chute's end it leaves at the end and the app warns ("the cable bends over the end of horn A – more bottom
   tension or a longer chute"). With vessel motion on, the hang-off rides the vessel; the touch-down and the laid cable
   stay on the seabed (world).
3. **Vessel advance:** the scene keeps the vessel where it is; the **seabed and the laid cable move aft** at the vessel
   speed (relative motion). Default "vessel moves with the lay" (vessel speed = lay speed, so the touch-down stays put
   relative to the vessel); a different speed shows the layback growing or shrinking. Use the vessel speed 0109's wake
   reads (one setting, not two); say in the report how they are tied.
4. **Seabed and water** (Sea, additive): water depth on the Sea surroundings; a seabed (sand/silt with a few ripples
   and stones, Simple and Detailed, out to where it cannot be seen); the laid cable lying on it with a little sediment
   near touch-down. **Water clarity** slider (visibility in metres, ~2–40 m, default a North Sea look) for everything
   seen through the water: the catenary, the seabed, the hull below the waterline. Measure before choosing a way: a
   volume only where it pays off (0109: a world volume cost +47 % and rendered black) – a depth/distance fade in the
   materials seen under water is likely cheaper. **Render cost: at most +30 %** on the demo's sea shot (Cycles CPU,
   say what was measured where).
5. **Cut-away behind the stern** (Sea, on/off + size + place, default a box from the transom to past the touch-down,
   as wide as needed): the sea surface (and its white caps, foam, wake) is cut away inside it, its walls show a clean
   water cut (the water colour + clarity, a thin bright edge at the surface), so a camera above the water sees the
   catenary, the touch-down and the seabed. Works in Cycles and EEVEE, in the queue, with scripts off, with vessel
   motion and with every weather (0109) preset.
6. **Things on the cable** (CPS sets, bend restrictors, a pull head): pick a CAD part or a subassembly of segments
   (the demo's `CPS SET`: tube + segments) and where it sits on the cable (metres from the cable end, or at a payout
   mark); it rides along the cable's path – over wheels, through the tensioners' line, down the catenary – each
   segment placed on the curve at its own arc length along the tangent (a stiff tube as one piece on its chord). Kept
   through a model update. Used by 0082 for the CPS run (note this in the report: what 0082 can call).
7. **Bake and speed:** the catenary and the riding parts are baked at Build (0058/0078 style, one mesh, Geometry
   Nodes pick the slice – no Python per frame); live posing through the existing handler. Aim **≤ +2 ms per frame**
   on the demo (measure the shot's frames with and without). The laid cable on the seabed is a still tree (no Scene
   Time) moved by the seabed's motion.
8. **Demo:** new stage `sea` after `tracks`: the cable's sea end at horn A, water depth 30 m, touch-down from the
   0083 numbers, cut-away on, clarity ~12 m; **shot 8 "Into the sea"**: from above and aft of the stern quarter, the
   cable paying out at 10 m/min for ~10 s, the catenary to touch-down and the laid cable on the seabed, vessel motion
   Calm; **0 clash rows** (the sea cable left out, as hoses and cables are). Plus the **small Demo follow-ups**:
   - handling winch 1 warns of a **20.9° fleet angle** (fairlead 0.9 m from the flange; 0080): bring it to ≤ 1.5°
     (spiral-groove/Lebus practice) by moving the lead sheave/fairlead where the deck allows, else give it a level
     wind (0080's ACROSS follower); the app's warning must be gone.
   - **small cables (< ~Ø 120)**: the D's guide rollers cannot reach the cable past the pads (0102) – their reach
     follows the cable Ø; check the D sweep at Ø 50 and Ø 500 (the owner's range).
   - re-render the guide picture `demo_overview.jpg` (it still shows the old deck).
   - Leave: the D's gutter end over horn A's upper bend (0082 decides), the carousel solid's width (owner may prefer it).
9. Every visible change: tooltips, guide section "Into the sea" (+ its panel picture, a still of the cut-away),
   **tour stop** (a small invented test model: a frame with a chute or horn + a cable into the sea; or a new set),
   **PC-check line** `motion.sea_cable` (Full; picture + per-frame metric), a Heavy line only if per-frame cost
   depends on load.

## Done when

- [ ] Catenary unit tests: length exact (≤ 0.1 mm per 100 m) over payout and vessel motion, both edge cases (warning
      text, exact two-point length), tangent at the hang-off continuous (no kink) when the horn allows it, the steep
      case warned; the laid length = vessel advance + what was there.
- [ ] The drawn tube equals the solver at three frames (≤ 1 mm), stripes move on the hanging part and stand still on
      the laid part, scripts-off check (`tools/coupling_check_noscripts.py` style), queue render works.
- [ ] Cut-away + clarity + seabed: pictures from three camera places (above water at the stern quarter, low over the
      cut, looking forward from aft); with weather Off, a sea without a sea end looks exactly as in 0.2.88 (picture
      check); render-time before/after (CPU, named machine) ≤ +30 %.
- [ ] CPS set rides the cable down the catenary on a test model (segments on the curve ≤ 2 mm, none through the
      cable), kept through a model update.
- [ ] Demo: stage `sea`, shot 8, 0 clash rows; fleet angle warning gone; D sweep fine at Ø 50 and Ø 500;
      `demo_overview.jpg` new; Make demo time before/after in the report.
- [ ] Per-frame cost on shot 8 measured with/without (aim ≤ +2 ms); tour stop, PC-check line, guide, tooltips.
- [ ] An **independent tester** subagent (did not write the code) tries to break the catenary and the sea end from
      this brief; its findings fixed or listed.
- [ ] Full suite green on GitHub; report filled in; merged; release.

## Not in this task

- The quadrant operations and the CPS run off the rack onto the cable end (0082), the A&R/tipping wires as app cables.
- Currents, cable dynamics, a camera under water (beyond what the cut-away shows), the web page's seabed/cut-away (a
  later Web 3D task), cables swaying in wind.
- Files of 0107, 0108, 0110 (see Lane).

## Design (worker, 13 Nov 2026 – the subagents' brief)

Units: metres, radians, seconds. World z up; the waterline is the Sea surroundings' water surface (world z of the
"FR Sea" object), else world z = 0.

**Split (one owner per file).**
- *Worker:* `core/catenary.py` (+ `tests/test_catenary.py`), `blender/paths_sea.py` (sea end + riders),
  `blender/ops_paths_sea.py`, the "Into the sea" fold in `ui_paths.py`, the hooks in `paths.py`, `props.py` (the
  settings below are already there), `reimport.py`, `animation.py`, `blender/demo.py` (stage `sea`, shot 8),
  tour, PC check, guide, `TASKS.md`, version, CHANGELOG.
- *Sea subagent (worktree):* the sea part of `blender/surroundings.py` and `core/sea.py` – **additive only**, plus
  `tests/test_sea_cutaway.py`. Nothing else.
- *Demo subagent (worktree):* `fresing_render/demo_model/*.py` and `tests/test_demo_cable_lay.py` only (winch 1
  fleet angle, the D's guide rollers for small cables). What `blender/demo.py` must change it writes in its report.
- *Independent tester (later):* tries to break `core/catenary.py` and the sea end from this brief, own test file.

**Scene settings (props.py, `scene.fresing`, all `update=_world_changed`):** `sea_depth` (m, 30), `sea_clarity`
(m, 10, 2–40: the distance at which a thing behind water has faded to 5 %: absorption σ = 3 / clarity),
`sea_cutaway` (bool), `sea_cut_auto` (bool, True), `sea_cut_length` (60), `sea_cut_width` (24), `sea_cut_start`
(m backwards from the stern, 0), `sea_cut_side` (m sideways, 0).

**The Sea subagent builds (only with Background = Sea; the quay is not touched):**
1. *Seabed* (always with the Sea – it is hidden under the opaque water unless the cut-away is on, so a sea without
   the cut-away renders exactly as 0.2.88): role `seabed` (+ `stones` in Detailed), world z = waterline −
   `sea_depth`, ±1 km round the model, sand/silt material (colour noise, ripple bump; Detailed: a few cm of real
   ripples + a few hundred low stones within ~250 m of the cut box). It **follows the empty "FR seabed motion"** when
   that exists: a Copy Location constraint named `"FR seabed motion"`, `use_offset` True, `use_z` False – helper
   `surroundings.follow_seabed_motion(ob)` (paths_sea calls it too; it makes the empty and drives it).
2. *Cut-away* (only `sea_cutaway`): a box from the stern backwards. Placement: `paths_sea.cut_box(scene)` (call it in
   a try; it returns None or `{"origin": (x, y), "dir": (ux, uy), "length": m, "width": m}` in world – origin = the
   box's front middle, dir = unit "aft"); when it gives None or `sea_cut_auto` is off: aft = −x world, front middle =
   (model's min x − `sea_cut_start`, model's middle y + `sea_cut_side`), `sea_cut_length` × `sea_cut_width`.
   Inside the box the **sea surface, white caps, wake and hull foam are cut away** (their materials get a box test in
   object coordinates read from object attributes, as `fr_wake` is; with the cut-away off the materials are exactly
   0.2.88's – same names, same nodes). The box is **air** (a cut-away: the camera sees the catenary, the touch-down
   and the seabed clearly); around it a **water volume** (a closed ring: outer box = cut box grown by 4 × clarity,
   inner hole = the cut box, from below the seabed to just under the surface): surface Transparent + a thin bright
   line along the top of the inner walls; volume = absorption + emission of the water colour (homogeneous: Cycles
   integrates it without steps) so whatever lies behind a wall – hull below the waterline, the seabed, the cable
   beyond the box – fades to the water's colour with its distance behind the wall (clarity). The water's colour
   follows the light (night: dark). In Detailed the walls' top follows the waves (same waves modifier). EEVEE:
   `volume_intersection_method = "ACCURATE"`. Cycles and EEVEE, scripts off (no Python drivers), the render queue,
   vessel motion and every weather preset.
3. `core/sea.py`: `absorption(clarity)`, `fade(distance, clarity)` (1 − e^(−σd)), the water colour under water –
   numbers the tests compare renders with.
4. **Measure** (Cycles CPU, the web machine, say so): a sea shot with and without the cut-away; ≤ +30 %.

**The sea end (worker; `item.b_kind == "SEA"`, settings `sea_*` on `FRCable`).** Hang-off = the cable's last
shaping contact (SHEAVE, CHUTE, BEND). The **seabed frame** = the empty "FR seabed motion" (one per scene, in flex's
hidden collection): world location = advance · u (horizontal, aft) + (0, 0, waterline); advance = metres paid out
(`sea_speed` LAY: a simple-expression driver on the cable joint) or vessel speed × time (WEATHER: `weather.
vessel_speed` knots, the number the wake reads – one setting). It is a slot of the cable (`paths._inputs_of`), as the
payout is (the cable joint's arrow + motion, as spool.py reads it), so the existing live handler and Build bake
see it move. In the seabed frame: the cable's end lying on the seabed `S = sea_start` (fixed), lay direction
`u = sea_dir`, the cable's middle on the seabed at z = −depth + radius·0.7 (it sinks a little into the silt).
Material bookkeeping: a point at s along the path has the mark m = s − paid out (the looks' rule), so the end on
the seabed is at s = `sea_mark` + paid out, the length from the hang-off point T down to S is
L = `sea_mark` + paid out − s(T) and the laid part's stripes stand still by themselves.
- *Anchor* (Add sea end, any change of mode/layback/tension/depth/laid): at the pose shown, TENSION: a = H / (w g),
  LAYBACK: a from X = a acosh(1 + h/a); S = touch-down + `sea_laid` · u, `sea_mark` = s(T) + s_hang + laid − paid out.
- *Every moment:* `core.catenary.hang_off` – the cable leaves the hang-off wheel where the catenary's tangent meets
  the wheel (fixed point on the wrap ψ, between 0 and the wheel's end: a chute/bend's CAD wrap, a sheave half a
  turn); steeper than the end: it leaves at the end, warning "bends over the end of …"; `core.catenary.hang` – laid
  x + suspended s = L, one unknown (a) by bisection; too much cable (L > distance + h): vertical + the rest snaking on
  the seabed, warning; so tight it lifts off S: the two-point catenary of length L, warning; shorter than the
  straight line: straight, warning. The polyline = the path up to the hang-off wheel's arrival (solver) + that arc
  to T + the catenary (fixed count per Build, by arc length) + the laid part (2 points, or 64 when some frame
  snakes), all in the cable part's coordinates; `fr_s` exact.

**Riders** (`item.riders`, `FRCableRider` with `FRCableRiderPart`s): the parts' own axis (a line through their
middles; one part: its longest extent), each part's place `at` and `length` along it; mark m of its front end
(END: `sea_mark` or the path's end − `at`; MARK: s(last contact) − `at`); per moment each part's chord on the
drawn polyline at s = m + paid out + at … + at + length, moved by the shortest turn from its CAD axis to the chord.
Baked as one hidden mesh of 4×4 matrices (frames × parts, FLOAT4X4 `fr_m`), each part a Geometry Nodes modifier
"FR ride" that picks its matrix (Scene Time → Sample Index) and moves its own geometry (as tracks.py does): no
Python per frame. 0082 calls `paths_sea.add_rider(scene, cable, parts, where, at)`.

---

## Report (filled in by the chat that did the task)

**Chat / date:** worker, Claude Code on the web (session branch `claude/amazing-mayer-6a324q`), 13 Nov 2026. Released as
0.2.91 (0.2.90 went to task 0110 an hour earlier).

**What changed:**
- `core/catenary.py` (new, no Blender): the touching-down catenary (s² = h² + 2ah, X = a acosh(1 + h/a)), one unknown
  (a) by bisection so that laid + hanging = L exactly; the edge cases LIFTED (two-point catenary of length L),
  PILED (straight down + a snake on the seabed with the length kept), STRETCHED (straight, warned); a hang-off
  level with or aft of the cable's end lays the cable towards it; `hang_off` = where the cable leaves its last
  wheel (fixed point on the wrap: the catenary's tangent = the wheel's, else it leaves at the wheel's end with a
  kink: "steep"); `anchor` (touch-down from the layback or from a = H / (w g)); `tensions`, `wet_weight`.
- `blender/paths_sea.py` (new): the sea end of a cable (`b_kind == "SEA"`, settings `sea_*`): the last shaping
  contact is the hang-off; the seabed frame is the empty "FR seabed motion" (advance = payout by a simple-expression
  driver, or Weather & time's vessel speed × time – the speed the wake reads, one setting), a **slot** of the cable
  like the payout (the cable joint's arrow + motion), so the existing live handler and Build bake handle it: the
  catenary costs no Python per frame. The end on the seabed (`sea_start`) and its mark (`sea_mark`) are set at the
  pose shown; from then L = mark + paid out − s(hang-off), so the length is exact, the touch-down follows payout and
  vessel, and the stripes stand still on the laid part. Warnings with their first frame. `cut_box` for the Sea
  (stored with the cable: CAD place, wide enough to see the seabed). `view_matrix`, `set_up_test_model`.
- `blender/paths_riders.py` (new): things on the cable (CPS set, bend restrictor, pull head). The axis is the line
  through the most parts' middles (rings and tube, not chocks); per part its place along it; per cable one "FR ride
  run" object whose Geometry Nodes work out every part's matrix (Sample Curve on the frame's slice of the cable's
  shapes mesh at s and s + length, the shortest turn onto the chord), each part moved by tracks.py's part tree.
  Placed from the cable's end or at a payout mark; flip; kept through a model update; left out of the clash check.
  **For 0082:** `paths_riders.add(scene, cable, objects, where="END"|"MARK", at=metres)`, `remove`, `matrix_now`,
  `rider_parts`; the sea end: `paths_sea.add_sea_end`, `numbers`, `tdp_world`, `payout`.
- `paths.py` (additive): sea slots in `_inputs_of`, `_solve_parts` split out of `_solve_item` (the sea end reuses
  it), sea notes, the seabed synced at Build and at every cable change, riders placed again on every cable change,
  a sea end kept through "From CAD cable again", a cable read so that it ends in the sea. `build.world_bounds`: a
  part tagged `fr_bounds_cad` (sea cable, riders) counts its CAD shape (the floor and the orbit centre no longer
  move with the hanging cable). Panel fold **Into the sea** (+ things on the cable), `ops_paths_sea.py`.
- Sea (subagent, additive, `surroundings.py` + `core/sea.py`): seabed (Simple/Detailed, ripples, stones), water
  depth, **cut-away** (sea surface, white caps, wake and hull foam cut away in a box; a water volume ring round it
  with the **clarity** σ = 3 / clarity and the water's colour following the light; bright top line; waves on the
  walls in Detailed; EEVEE "Accurate"); with the cut-away off the materials are 0.2.88's (tested). I made the
  walls clearer (UNDERWATER ×2.7, less darkening with depth) after the first demo pictures read as a black pit.
- Demo: stage `sea` (30 m, layback 32 m, 120 m on the seabed, cut-away, clarity 12 m) and **shot 8** "Into the sea"
  (10 s at 10 m/min, orbit −10°); the video is now 89.6 s. Demo follow-ups (subagent, `demo_model/`): both handling
  winches got a **level wind** (the deck has 2.6–2.9 m before the D-quadrant; 1.5° needs ~23.5 m) – winch 1's
  follows the spool ACROSS: fleet angle 20.9° → 0.0° at both flanges, the warning is gone; the D's guide rollers:
  the pads' V follows the cable Ø (`pad_v_depth`), roller-to-cable gap at Ø 50: 26.1 → 1.9 mm, Ø 200 / 500 unchanged
  (touching); the D sweep is clear at Ø 50 and Ø 500 (the CPS slide's end shortened at Ø 500 where it was already in
  the D's way). Joint sheet 308 → 310.
- Test model `test_sea.step` (`tools/make_test_sea.py`, subagent): deck, 3 rollers, a 95° horn, a Ø 120 cable into
  the water, a CPS set (6 vertebrae + tube + 2 chocks). Tour stop `sea_cable` (set "Cable into the sea"), PC-check
  line `motion.sea_cable` (picture + frame metric), guide section "Into the sea" + surroundings lines + demo text,
  pictures `panel_cable_sea.png`, `view_sea_cutaway.jpg`, new `demo_overview.jpg`.

**Tested and measured** (4-core web session unless said):
- `tests/test_catenary.py` (8), `tests/test_paths_sea.py` (11: tube = solver ≤ 1 mm at three frames, stripes move
  on the hanging part and stand still on the laid part, real Blender with scripts off, the queue copy builds and
  renders the same, model update, reopen), `tests/test_sea_cutaway.py` (13, subagent), `tests/test_paths_sea_
  independent.py` (independent tester: 69 tests; **9 faults found, all fixed**: catenary under the seabed when the
  hang-off is over the end, seabed driver not set again for a reversed cable / changed vessel speed / Weather off,
  piled cable drawn too short, rider marks shifted by the payout, riders not placed again after a sea-end change
  (MARK and END), scene water depth not followed), `test_demo_project.py`, `test_demo_cable_lay.py` (52),
  `test_tour.py` (68), the cable / spool / panel tests (166) all pass locally.
- Length exact: laid + hanging = L to 1e-9 m; the drawn polyline ≤ 0.1 mm per 100 m (dense check).
- **Per frame on shot 8** (full demo, Blender as a module, median of 2 × 126 frame changes): 27.5 ms with the sea
  end, 25.8 ms without: **+1.7 ms** (aim ≤ +2 ms).
- **Make demo** (full form, same machine, one after the other): main 114.4 s, 0.2.90 118.5 s (+4.1 s; sea stage
  0.8 s).
- **Render cost of the cut-away** (subagent, Cycles CPU, 480×270, 32 samples, Calm, Detailed, CPU seconds because
  the machine was loaded): stern quarter +18 %, from aft +14 % (≤ +30 %). Pictures from three places in the
  subagent's run; the guide still and shot 8 checked by eye.
- Demo numbers: layback 32 m, leaves horn A at 68°, bottom tension 9.8 kN, top 26.1 kN (51 kg/m, 0083's figures).
- GitHub: 6 runs on the branch – 3 red while the guide pictures and the version were not in yet (pushed as
  backups; nothing else failed), 3 green (after 0.2.90's version, after merging main with 0112, after merging main
  with 0110 and renumbering to 0.2.91, 18.9 min) – plus the run on main.

**Open points / follow-up tasks:**
- **Wake direction (0109):** the wake puts the stern at the waterline's max x and `core/weather.BOW_AZ` has the bow
  at −x; the demo (and this task) have the bow at +x. On the demo a vessel speed > 0 would draw the wake at the bow.
  Not changed here (Scene & Render lane decides).
- With "With the lay" the touch-down still moves a little when the deck path length changes (the carousel's leave
  point moves: layback 32.0 → 33.8 m over shot 3's 150 m) – the length bookkeeping is right; the owner may prefer to
  re-anchor per shot.
- Rollers after the hang-off on a horn keep turning with the cable though it left the horn before them.
- The sea end's numbers in the panel are worked out for the frame shown (one solve per frame while the panel draws,
  cached).
- The independent tester's file and the sea subagent's tests stay in the suite.
- Subagents: Sea (seabed, clarity, cut-away), Demo (fleet angle, D rollers), test-model maker (Sonnet), independent
  tester. Re-done after merging: the wall colour, the cut box (placement bug found in the demo picture), `numbers()`
  must not write while drawing (found by the guide's panel picture).
- Leftover branches on GitHub: none pushed besides the session branch.
