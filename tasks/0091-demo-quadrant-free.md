# 0091 – Demo: the quadrant system moves freely, quadrant shot, Lebus close-up

**Who:** worker · **Status:** done · **Branch:** `claude/inspiring-keller-9fp79j` (the web session's branch)
**Started by:** lead chat, 12 Nov 2026 (0077's open points)
**Lane:** Demo models – `fresing_render/demo_model/` (the maker), `blender/demo.py`, `blender/ops_demo.py`,
`tests/test_demo_*.py`, `tools/make_demo_cable_lay.py`; no other app code (anything wrong elsewhere: an open point)
**Model:** Opus · effort Medium (3D geometry of an invented model) · **Place:** Claude Code on the web, environment
"CAD-render-animation"

## Goal

The demo's quadrant system can do its whole move without parts running through each other, and the demo video shows it:
the D-quadrant travels aft on its rails to the handler, the handler tilts over the stern and the quadrant tips. The
drum close-up shows a real Lebus drum, and the X-ray labels no longer overlap.

## Background – what 0077 found (clash check on the full-size demo, report of `tasks/0077-demo-project.md`)

- The D's travel aft runs into the S-bend's **roller cradles** at once (125 mm, frames 3–30 of the travel); its
  **gutter** 50 mm and a **pad eye** 30 mm too.
- The **handler frame cuts its hinge brackets** past about 30° of tilt (139 mm).
- The **parked handling wire** stays behind when the handler tilts (233 mm) and the D passes through it (125 mm).
- The handler cylinders' **rod leaves its barrel** near 70° (2 rows) – the stroke or the pin points are wrong.
- The **rail wheels** show short 2–50 mm rows while turning fast: check the wheel's joint axis against its round centre.
- The demo's stern turn stays where it is (owner, 12 Nov): the cable passes 10 cm under the rail girders.
- The quadrant's tip joint rides on its travel; on the handler it must also ride the handler's tilt (0084's note).

## What to build

- Fix the model, not the check: raise or split the cradles where the D passes (or move the S-bend's cradles to stands
  that leave the middle lane free), give the hinge brackets room for 0–100°, let the parked handling wire hang from the
  handler (a part that moves with it), make the cylinders' stroke and pins fit 0–100°, put each wheel's joint on its
  own round centre. Keep every route rule of 0084 (bends ≥ 1.15 × MBR, rollers ≤ 1.6 m apart).
- The quadrant's tip: a joint that rides on the handler's tilt once the D is on the handler (a second stacked joint is
  fine; say which way you chose).
- **Shot 7** of the demo: the D travels aft (time-lapse caption), the handler tilts over the stern, the quadrant tips –
  0 clash rows over the shot.
- **Lebus close-up (shot 6):** one deck winch gets the Lebus drum (35° crossovers + risers, 0084) so the close-up shows it.
- **X-ray labels (shot 5):** no two label boxes overlap and none touches the picture's edge (move the label points or
  the camera in `demo.py`).

## Done when

- [x] Clash check on the full-size demo over the quadrant shot: 0 rows (with the spinning parts left out as in 0077);
      a test on the scaled form checks the quadrant's whole move.
- [x] Shot 7 and the Lebus close-up in the animation; the animation still 60–80 s; `tests/test_demo_project.py` and
      `tests/test_demo_cable_lay.py` green; two new pictures `tasks/img/0091-*.png` (quadrant tipped, Lebus close-up).
- [x] Make demo project time measured again (should stay about 148 s on the web machine).
- [x] GitHub green; merged to `main` with the next free version; report filled in; `TASKS.md` updated.

## Not in this task

The clash check's speed with spinning parts (0092), joint-creation speed (0093), the moving cable (0078) and the quadrant
operations with wires and cable (0082).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (4 cores), 12 Nov 2026 · version 0.2.69 · branch
`claude/inspiring-keller-9fp79j` (the web session's branch, in place of `task/0091-…`).

**What changed** (all in the Demo models lane: `demo_model/`, `blender/demo.py`, tests; two count texts in
`tour.py`, `heavy.py`, `ops_demo.py`):
- **Cradles:** the S-bend cradles whose box reaches into the D's lane (|y| < 4,410 mm) are **lifting cradles**
  (`deck.lifting_cradle`): the trestle's legs are guide tubes, the cradle sits on a lift frame (top beam + two posts
  in the tubes, 10 mm clear) that drops 650 mm (top then 116 mm under the D's underside). 4 stations (2 per side,
  `layout.lift_drop`); joints "Cradle 11 drop" (operator) and three that follow it. Route rules of 0084 untouched
  (same stations, same spacing).
- **Stack:** "Quadrant travel" rides on "Handler tilt" (with the handler down its rails continue the deck's, so the
  travel is the same); "Quadrant tip" rides on the travel. One chain, no second joint: once on the handler the D
  tilts with it and tips about its hang-off.
- **Handling wire:** it ran from the winch over the D to the pulley (the D went through it, the handler left it
  behind). Now: drum → low under the D at y = 0 (through a slot in the stern turn's web, under its cable) → a **hinge
  sheave on the handler's hinge axis** (cheek plates) → along the frame (a part of HANDLER FRAME, tilts with it) →
  over the **top pulley, now below the D's underside** (the D rolls over the handler's forward end; before, the
  pulley head stood 600 mm into its way) → parked end + shackle hanging beyond the handler's end.
- **Handler:** first cross beam moved from 600 to 1,100 mm (it swung through the hinge brackets past ~30°), hinge
  bosses 10 mm clear of the bracket cheeks, a slot in the end beam for the pulley. **Cylinders:** base pins moved
  from forward of the frame's end to just forward of the transom, outboard of the brackets (806 mm from the hinge,
  rod pin 1,507 mm): the cylinder's angle now changes the same way over 0–100° (before it stood still near 75°, which
  is where the "rod leaves its barrel" rows came from – see open points); bore 115 mm round a 100 mm rod.
- **Rail wheels:** their axes were on their round centres already; the flange cut 25 mm into the rail head and the
  tread into the bogie's top plate: tread 150 wide over the 140 mm head, flange inboard beside it, wheel Ø 240.
- **Shot 7** (16.4 s): cradles drop (1.5 s), the D travels 41.3 m aft (6.9 s, caption "× 60", 6 m/min), camera
  flies along, then moves to "Stern"; the handler tilts 0 → 100° (4 s), the quadrant tips 40° (2.5 s). Shots 2 and 4
  are 2 s and 1 s shorter: the animation is **72.4 s + 6 s cards = 78.4 s**.
- **Lebus:** both handling winches have the Lebus barrel (35° crossovers) + two risers, less wire on the drum (45 %)
  so the grooves show; shot 6's caption says so. (+12 s of writing time for the Lebus barrel, both winches share it.)
- **X-ray labels:** with the new timings no two boxes overlap and all lie inside the picture with the placer's margin
  on every frame of the step (full size and scaled, at 1920×1080, 1280×720, 960×540). Nothing to move; a test now
  guards it. Note: the placer clamps them to the picture's margin (22 px at HD) because the whole vessel's outline
  covers the picture – a Scene & Render lane matter if they should sit further in.

**Tested and measured** (4-core web machine, no graphics card):
- **Clash check, full-size demo, shot 7** (spinning parts + the static cable left out as in 0077, now also the D's
  rail wheels – they turn ~170° a frame in the time-lapse): **0 rows**, 45 s, 1,132 parts, 377 moments + 11,711
  between. Before the fixes (scaled form): 396 rows (cradle rows gone first, then D × pulley head 125 mm, hang-off ×
  wire 40 mm, wire × hinge sheave 1 mm, rod × barrel 2.1 mm, rail wheels 0.5 mm).
- `tests/test_demo_project.py` (scaled form, 15 tests, 2 new: shot 7 moves the whole system and the D keeps its place
  on the tilting handler; X-ray labels): the whole-animation clash check → **0 rows** with the sea at rest (see open
  points). `tests/test_demo_cable_lay.py` 37 (2 new: the quadrant's way free, cradles, stack, wire route; Lebus
  winches), `test_user_guide.py` + `test_updates.py` 49: green locally.
- **Make demo project** (full size, alone on the machine): **134 s** (0077: 148 s) – writing 47 s, import 15 s,
  joints 64 s (419), Build 5 s.
- Pictures (Cycles CPU, Preview, rendered 1920×1080, stored 960×540): `tasks/img/0091-quadrant-tipped.png` (end of
  shot 7: handler at 100°, quadrant tipped, 141 s), `tasks/img/0091-lebus-closeup.png` (shot 6, 177 s).
- GitHub: **1 full run on the branch, green on the first try** (run 43211497548, 13.8 min). `main` fast-forwarded
  to that commit: run 43213547402 (reuse, 2.4 min) published **v0.2.69**, the Windows update-from-the-release
  check passed, offered to the apps.

**Open points / follow-up tasks:**
- **Clash lane (0092, running): `core/clash.screw_between` reads a body's turn with `acos` from float32 matrices.**
  When a body turns very slowly but moves a lot between two frames (any slide while the vessel's sway is at a
  turning point; a cylinder whose angle stands still) the turn is off by ~1e-4 rad and the in-between place by up
  to centimetres (measured: a handler cylinder's rod 41 mm off at frame 1684.86). It gave false 1–2 mm rows
  (tensioner lift × base frame, hinge sheave × wire) whose presence depends on the sea's phase. Suggested fix: the
  angle from `atan2(|skew part|, trace part)`, or a straight move when the turn is tiny. Until then the demo's test
  checks with the sea at rest (`vessel_motion.at_rest`: the sway moves the whole model as one, so no real clash is
  hidden); the full-size shot-7 check above ran with the sea moving and was clean.
- The cable stays in place while the D travels and the cradles drop (it is a static solid): 0078 / 0082.
- Labels at the picture's margin (see above): Scene & Render lane if wanted.
- Helper-agent review skipped: no Windows-only code.
