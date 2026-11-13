# 0081 – Cable into the sea: catenary, seabed, water clarity, cut-away, CPS on the cable

**Who:** worker · **Status:** open – can start · **Branch:** `task/0081-cable-into-the-sea` (or the web session's branch)
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

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
