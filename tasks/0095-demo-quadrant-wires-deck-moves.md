# 0095 – Demo: quadrant wires as the owner works, cable engine and handling winches moved

**Who:** worker · **Status:** done (0.2.71) · **Branch:** `task/0095-demo-quadrant-wires` (or the web session's branch)
**Started by:** lead chat, 12 Nov 2026 (the owner's comments on the 0.2.69 demo, with his pictures)
**Lane:** Demo models – `fresing_render/demo_model/` (the maker), `blender/demo.py`, `blender/ops_demo.py`,
`tests/test_demo_*.py`, `tools/make_demo_cable_lay.py`; no other app code (anything needed elsewhere: an open point)
**Model:** Opus · effort High (moving wires between moving parts, a re-layout with the route rules) · **Place:** Claude
Code on the web, environment "CAD-render-animation"

## Goal

The demo's quadrant system is wired the way the owner's vessels are: the A&R / quadrant handling winch is always
hooked onto the top of the D's curve, its wire runs straight along the deck and, with the handler tilted, over the
handler's top pulley down to the D; the two tipping winches' wires run over their swivel sheaves to the bottom corners
of the D. The cable engine and the two handling winches stand where the owner puts them.

## The owner's description (12 Nov 2026, from his marked-up pictures of the demo – described here in words)

1. **A&R wire (the app's "quadrant handling winch").** It is **always connected to the D at the top of its curve**:
   the middle of the curve's outer edge (local +x apex of `dk.quadrant_d`, just outside the gutter lip), the point
   that faces the winch when the D is at its stationary position. While the D is on the deck the wire runs straight
   from the drum to that point and pays out as the D travels aft. When the D is on the handler and the handler tilts
   up, the wire runs from the drum aft, **over the pulley at the handler's top (far) end**, and down to the D. At the
   end of the tilt the D stands **vertical, curve up, straight bar down** near the transom, its connection point just
   below the top pulley.
2. **The sheave at the handler's bottom goes:** the hinge sheave on the hinge pin (+ cheek plates), the wire's deck run
   low under the D, the slot in the stern turn's web made for it (unless something else needs it) and the run along
   the frame. **The handler's top pulley at its far end stays** – placed so the wire bears on it once the handler
   tilts, and the D still rolls onto the handler without touching it.
3. **Tipping wires:** from each tipping winch up over its swivel sheave on its post and down to the D's **bottom
   corners = the two ends of the straight bar** (the existing tipping pad eyes – check they sit at the bar's ends,
   the corners when the D stands vertical). They are connected once the D is on the handler, before the tilt.
4. **Lowering (later, 0082):** the D goes down into the sea **vertical**, hanging from the A&R wire; it only **starts
   to tip near the sea bottom**, turned by the tipping wires. So:
   - the hang-off pad eye moves to the curve's top (point 1) and **"Quadrant tip" turns about that point**, not the
     bar's middle (update the joint sheet's note);
   - **shot 7 no longer tips the D on the handler**: it ends with the handler at 100°, the D vertical, hanging from
     the A&R wire over the top pulley, both tipping wires connected (the owner's two pictures). Use the freed seconds
     for a hold on that picture or keep the animation shorter – it must stay 60–80 s.
5. **Tilt cylinders:** one on each side of the handler, as now – the owner checked: correct, no change.
6. **Cable engine:** it now stands on side B between the rise and tensioner 1. The owner wants it on the **lower
   path**, on the straight run aft from the loading tower, **before the stern turn that rises to side B and tensioner
   1** (he marked roughly the middle part of that straight, from about beside tensioner 2 to well forward of it). Pick
   the spot with room (tensioner 2 and its walkways beside it); rollers fill its old place on side B. Keep the
   tensioners where they are unless the layout really needs them to move (point 7 lines up with them) – say so if
   they move.
7. **Handling winches** (the two Lebus winches now outboard of the lower path, starboard): move them **forward, one
   on each side of the A&R winch**, between the cable's forward S-bends and the carousel well, **each winch's middle
   on the line of a tensioner** (one on side A's line, one on side B's line), wire leading aft along that lane (they
   pull cable ends through the tensioners). **A little smaller** (about 80 % of drum length and diameter is fine).
   Keep the Lebus barrel; shot 6 (Lebus close-up) follows them.

## What to build

- The model changes above in `demo_model/` (keep every route rule of 0084: bends ≥ 1.15 × MBR, rollers ≤ 1.6 m apart;
  the cable engine on the lower level keeps the cable's line).
- **Wires that move with their ends** – the A&R wire and the two tipping wires – in `blender/demo.py` only, with
  scripts off, in the render queue and at any fps. A suggestion: straight wire pieces between app-made empties (drum
  tangent, top pulley, swivel sheave, pad eyes) kept straight and stretched by Blender's own constraints (Copy
  Location + Stretch To / Damped Track) or simple-expression drivers; the piece over the top pulley shown once the
  tilt starts. The A&R drum turns as the wire pays out (a coupling to "Quadrant travel" for the deck part; the tilt
  part may be a joint step – your choice, within a few %). A wire end stays on its eye within a few mm at every frame
  and never shows through steel. These are demo parts, not a new app function: the moving cable (0078, Fable) may
  replace them later – say in the report how.
- Joints: hang-off at the curve's top, "Quadrant tip" about it (it still rides on the travel, which rides on the
  tilt); the joint sheet and `demo_joints.json` updated.

## Done when

- [ ] Clash check on the full-size demo over shot 7: 0 rows (spinning parts, the static cable **and the three wires**
      left out – they touch their sheaves; say so); the scaled-form test checks the whole move.
- [ ] Shot 7 ends as point 4 says; shot 6 shows a moved handling winch; the animation 60–80 s;
      `tests/test_demo_project.py` and `tests/test_demo_cable_lay.py` green (new tests: the A&R wire's end on the
      curve's top at the start, end of travel and 100°; tipping wires on the bar's ends; the hinge sheave gone; cable
      engine on the lower path; each handling winch's middle on its tensioner's line).
- [ ] Three new pictures `tasks/img/0095-*.png` (small): the tilted handler from the side with the A&R wire over the
      top pulley; the same from astern with the tipping wires; the deck from above with the engine and winches.
- [ ] Make demo project time measured again (0091: 134 s on the web machine).
- [ ] GitHub green; merged to `main` with the next free version; report filled in; `TASKS.md` updated.

## Not in this task

Lowering the D into the sea and tipping it near the sea bottom (0082 – point 4 is its brief's start), the moving cable
(0078), the clash check's own code (0092 is running in the Clash lane: if it merges first, take `main`), the flex
parts lane (0058, Fable day).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (4 cores), 12 Nov 2026 · version 0.2.71 · branch
`claude/cad-render-task-0095-8kussy` (the web session's branch, in place of `task/0095-…`).

**What changed** (Demo models lane: `demo_model/`, `blender/demo.py`, the demo tests; count texts in `tour.py`,
`heavy.py`, `ops_demo.py`, the guide's demo chapter):
- **A&R wire** always on a new **A&R pad eye** at the top of the D's curve (middle of the outer edge, 90 mm outside
  the gutter's lip, under the gutter, above the D's underside; a plate square to x, so the wire never runs through
  it). The old hang-off eye, the **hinge sheave + cheeks**, the frame run, the parked end and the **slot in the stern
  turn** are gone. "Quadrant tip" turns about the A&R eye (sheet note updated).
- **Top pulley** (`route.top_pulley`): beyond the handler's far end, its rim 74 mm under the D's underside (the D
  rolls over it); placed so at 100° the wire comes from forward over it and hangs straight down 1.38 m to the eye.
  Flat, the wire clears it; it bears from **9.3°** of tilt. The pulley's brackets reach further aft than the old
  head, so the **stern turn moved 1.16 m forward**; the tensioners **did not move** (that metre came out of the
  engine's old room on side B).
- **Tipping wires:** the swivel sheave is new – a hollow post, a **foot sheave** in a window at its foot, the wire up
  the post's axis (so the head can swivel to any side), the head sheave one radius off the axis, the bearing a sleeve
  15 mm clear of the post. The fixed part (winch → foot sheave → up the post) is in the STEP model; the head points at
  the D's tipping eye when the D comes on and follows the tilt (coupling, exact at 0° and 100°). Tipping eyes: at the
  bar's ends (±4,200 of ±4,350), thinner lugs with Ø180 holes (the wire comes in up to ~60° to the hole's axis).
- **Moving wires** (`demo.py`, stage "wires", demo parts not app code): empties ride on the parts with Child Of; a
  straight piece is a 1 m cylinder kept by Copy Location + Stretch To; a sheave's tangent point is an empty turning
  about the axle towards the far end (Locked Track) with a child one rope radius out; the turns over the pulley and the
  swivel heads are curves whose bevel start / end a simple-expression driver of tilt and travel sets (fitted from 51
  sampled tilts); hidden pieces get scale 0 by driver. No Python: scripts off, render queue, any fps. The tipping
  wires hang parked until the travel is at its end, then end on the bar's ends. For 0078: these 20 objects
  (collection "FR demo wires", tag `fr_demo_wire`) can be deleted and replaced by the moving cable's own wire paths;
  the route sheet's `wires` section names every point and carrier.
- **A&R drum:** "Drum turn" follows "Quadrant travel" (0.0641 °/mm) and rides on a new "Drum turn on tilt", turned by
  one SMOOTH step over the tilt (from 16 % of its time): within **164 mm of the 8.73 m** the wire pays out over the
  tilt (1.9 %); a coupling to the tilt angle would have been 1.43 m off (the wire bears only from ~10°).
- **Shot 7:** cradles drop, travel ×60 with the A&R wire paying out, "The tipping wires are connected …" (1 s), the
  tilt 0 → 100° (4 s) with the drum step, then a slow 8° orbit (3 s) on the end picture: D vertical, curve up, hanging
  from the A&R wire over the top pulley, both tipping wires on. No tip. Animation **72.4 s + 6 s cards = 78.4 s**.
- **Cable engine** on the lower path just forward of tensioner 2 (side A's walkway stops short of it); its
  wheels Ø520 instead of Ø600 so it stands on the deck under the lower line; two cradles fill its old place on side B.
- **Handling winches** at the A&R winch (400 mm aft of its middle: side A's would have stood 40 mm in the loading
  tower's foot frame), each drum's middle on a tensioner's line (y = ±5,850), the fairlead aft, the wire at the
  cable's height (454 mm pedestals), 80 % drum (rc 480, 1,280 long), Lebus barrel kept, motors inboard (side A's
  winch built the other hand). Shot 6 keeps its camera (offset from the drum: it follows).
- 314 joints on the vessel (+3: "Drum turn on tilt", two foot sheaves), 422 with the quay; `MIN_JOINTS` 315.

**Tested and measured** (4-core web machine, no graphics card):
- **Clash check, full-size demo, shot 7** (frames 1401–1824, sea moving; spinning parts and the static cable left out
  as before; the wires are not parts, so the check does not see them – they touch their sheaves): **0 rows**, 36 s,
  1,126 parts, 424 moments + 4,728 between. First try 18 rows "SHEAVE POST × SWIVEL BEARING" 2–4 mm (the bearing sat
  on the post's top face; the step between frames drifts with the sway, 0091 open point) → the sleeve with clearance.
- **Wires, full size, 60 frames over shot 7:** A&R end on the eye (worked out from the D's own part) **0.0 mm** at
  every frame, start on the drum's rope radius ±0, tipping ends 0.0 mm on the bar's ends once connected; no straight
  piece closer to steel than its rope radius (first build: the parked tipping wire grazed its head's base plate by
  12 mm → plate shortened). The A&R wire crosses the **static cable** at the quadrant's apex early in the travel
  (not steel; the cable stays put while the D moves – 0078/0082).
- Static interference check of every new/moved part against the model (OpenCascade common volumes): found the side A
  winch in the tower foot frame (40 mm), the A&R eye's bracket under a gutter roller, and – already there before –
  the swivel post's square foot plate in horn A/B's support: all fixed (round foot plate). Left: welds and ropes in
  their grooves.
- `tests/test_demo_cable_lay.py` **41 passed** (4 new: A&R eye, pulley, no hinge sheave; drum payout; tipping wires
  and bar ends; engine on the lower path, winches on the tensioners' lines). `tests/test_demo_project.py` **16 passed**
  (new: wires follow their ends at the start, end of travel and through the tilt, after a Build at 25 and 50 fps,
  drivers simple, not through steel; shot 7 ends vertical, no tip; the whole-animation clash check: 0 rows).
  `test_user_guide.py` + `test_updates.py` 49 passed.
- **Make demo project** (full size, alone on the machine): **90 s** (0091: 134 s; 0093's fast joints) – writing 54 s,
  import 20 s, joints 2.5 s (422), wires 3.8 s, Build 6.4 s. Scaled form 81–92 s.
- Pictures (Cycles CPU, 24 samples, rendered 1280×720, stored 960×540): `tasks/img/0095-ar-wire-side.png`,
  `0095-tipping-wires-astern.png`, `0095-deck-engine-winches.png`.
- GitHub: **1 full run on the branch, green on the first try** (run 43233484802, 12.2 min). `main` fast-forwarded to
  that commit: run 43235683405 (reuse, 2.5 min) published **v0.2.71**, the Windows update-from-the-release check
  passed, offered to the apps. Its landing-page job failed on a GitHub API error ("fetching artifact metadata
  failed … re-run later"); the Landing page workflow was started again by hand from this session.

**Open points / follow-up tasks:**
- The guide's demo overview picture (`docs/img/demo_overview.jpg`) still shows the 0.2.70 deck (engine on side B,
  winches outboard); small from that far – next guide-picture pass.
- The tipping sheaves' and the top pulley's "turn" joints still follow Cable travel (as since 0084); they should turn
  with their wires (0082 / 0078).
- Helper-agent review skipped: no Windows-only code.
