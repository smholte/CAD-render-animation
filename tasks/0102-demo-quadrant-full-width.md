# 0102 – Demo: the D-quadrant as wide as the cable path; the tensioners lift and tilt out of its way

**Who:** worker · **Status:** done (0.2.84) · **Branch:** `task/0102-demo-quadrant-full-width`
**Started by:** lead chat, 13 Nov 2026 (owner's corrections of the demo deck, with his marked-up picture: described in
words below, not committed) · runs side by side with 0080 and 0101; **0079 waits for this task** (it runs the tracks
in the tensioner made here)
**Lane:** Demo models: `fresing_render/demo_model/` (`params.py`, `layout.py`, `deck.py`, `machines.py` `tensioner()`,
`route.py`, the route and joint sheets), `blender/demo.py` (the stages that use the tensioners, the cradles and the
quadrant: `joints`, `cylinders`, shots 5 and 7), `tests/test_demo_*.py`. Not the app's own functions.
**Model:** **Opus · effort High** · **Place:** Claude Code on the web, environment "CAD-render-animation"

## Goal

The demo cable-lay deck works as the owner's real one: the D-quadrant is exactly as wide as the cable path, the cable
runs straight from the two tensioners round the D's gutter (no S-bends), and when the D travels aft over the deck
**between** the tensioners, both tensioners have lifted their top track and tilted it **outward** to their own side,
so the whole width between the two cable lines is clear for the D to pass.

## Background (owner, 13 Nov 2026)

- **The D-quadrant is the same width as the cable's path.** Seen from above, the cable comes up side B (port) through
  tensioner 1 and down side A (starboard) through tensioner 2 in two straight lines, and round the D's curve between
  them: one smooth U, the D's gutter carrying the cable exactly in line with the two lanes. Today (0084, 0091) the lanes
  lie `lane_clear` = 1.8 m outside the D's curve ("room for the D to pass") and the cable makes an S-bend from each lane
  into the gutter over cradles that drop (`lift_drop`, `lifting_cradle`) – **the owner crossed those S-bends out.**
- **The D travels aft over the deck between the tensioners**, so its sides (gutter + cable) pass through both
  tensioners' lines. Everything between the two cable lines, from the cable's height up, must be **fully clear** while it
  passes (the owner drew that band from one tensioner's cable to the other's).
- **Tensioner opening:** first the top track **lifts**, then it **tilts** – sideways, about a hinge **along the cable
  (fore–aft) on the tensioner's outboard side**: **tensioner 1 (port) tilts out to port, tensioner 2 (starboard) out to
  starboard**. Today the hinge runs athwartships at one end (`hinge_end`, axis (0, ±1, 0)) and the track lifts at its
  far end like a lid – wrong. **Two separate hydraulic cylinders per motion:** 2 lift cylinders (today 4) and 2 tilt
  cylinders (today none).
- Earlier owner answers that stay: the stern turn a few metres forward of the quadrant handler, under the rails (12 Nov);
  the D lowered vertical from the A&R wire, tipping near the sea bottom (0082); the deck as re-laid in 0084 otherwise.
- Repository public: invented model only; the owner's picture is not committed (CLAUDE.md section 6).

## Scope

1. **Lanes on the D's width:** the side lanes' cable lines at y = ± the D's cable radius (`lane_clear` → 0 or the
   route made so); no S-bends; the cable round the D's gutter continues straight into both lanes. Whatever the wider
   middle lane touches (rails, rail girders, stern turn under the rails, the lower path, walkways, handling winches on
   the tensioners' lines, CPS, horns) re-placed so the deck still works; the route sheet's bends all ≥ 1.15 × MBR.
2. **The D's swept path is clear:** over its whole travel (`Quadrant travel`, 0 → end), with the tensioners open and
   the cradles in its way dropped, **nothing** is in the box the D (with its gutter, the cable on it, rail bogies, pad
   eyes) sweeps. The lane cradles/rollers inside that sweep drop out of its way (the `lifting_cradle` way, one lead joint
   per lane as today) or are placed outside it; fixed things (tensioner base frames, columns, inboard cylinders) are
   kept outside or below it. Report how high the clear band is and what had to move.
3. **Tensioner remade** (`machines.tensioner`): lift (slide up, 2 cylinders), then tilt (rotate, riding on the lift,
   2 cylinders between the lift frame and the tilting carriage) about a fore–aft hinge on the outboard side, mirrored
   for the two sides so each tilts outboard. Tilt range: from closed to where the top track, carriage, cylinders and
   lift frame are all outside the D's sweep (the lead's sketch showed ~70°; say the angle used). Cylinders as the app's
   cylinders where the `cylinders` stage can do it (barrel on its pin, rod's eye on its pin). Track info
   (`A.info["tracks"]`: pads, links, pins, sprockets, the gripping run) kept in the same form – **0079 reads it**.
4. **Joints sheet and demo stages** follow: "Top track lift", "Top track tilt" (new axis, limits, notes), the cylinders,
   the cradles' drop joints; the sprockets still wait for 0079 (`waits_for_tracks`). Shot 5 (tensioner): lift, tilt out,
   back, squeeze. **Shot 7** (quadrant): before the D travels aft, both tensioners lift and tilt out and the cradles in
   its way drop; the D passes between them; the cable on its gutter as today (0078's demo cable is read again from the
   new route by the `cable` stage – check it still reads: 0 problems).
5. **Tests:** both tensioners tilt **outboard** (the top track's middle moves away from y = 0); **clash check of shot 7
   with the D passing: 0 rows** (the D, its cable and gutter against tensioners, cradles, rails, everything); shot 5
   0 rows; `test_demo_project.py` and the model maker's tests green; the route's bends and the cable's length in the
   sheet.
6. **Pictures (invented model only, `tasks/img/`):** a Cycles still from aft looking forward with both tensioners
   open and the D between them, and one from above of the U (cable round the D, straight into both lanes).

## Done when

- [ ] Scope 1–6; Make demo project builds, time before/after; shots 5 and 7 play with 0 clash rows.
- [ ] Guide's demo section and the demo's notes updated where they describe the tensioner or the D's lane.
- [ ] GitHub green; report filled in (what moved, the tilt angle, the clear band's size); merge to main and release.

## Not in this task

The tracks' pads running (0079, after this); spooling (0080 – runs at the same time: do not touch the carousel or the
winches' drums); the cable into the sea (0081); the quadrant's lowering and tipping wires (0082); app functions.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (worker, Opus), 13 Nov 2026 · branch `task/0102-demo-quadrant-full-width` · 0.2.84

**What changed:**
- **Lanes on the D's width** (`params.py`, `route.py`): `lane_clear` is gone, `lane_y = quadrant_r` (4.05 m at Ø 200);
  the four S-bend arcs are gone – side B runs straight into the gutter, the gutter straight into side A (one U). The
  route's bends are all ≥ 1.15 × MBR (now tested for Ø 50–500). What moved (Ø 200): stern turn radius 6.85 → 5.30 m
  (its lanes are closer), lower path 2.5 m outboard of side A (`lower_off` 2.0 → 2.5: clear of tensioner 2's base),
  tensioners 1.3 m aft (25.98 m), CPS ramp 2.8 m outboard of side B (`CPS_OUT` 2.0 → 2.8: clear of tensioner 1's open
  lift frame; a small cable's S gets a straight between its arcs), the D's rest 4.7 m aft (`quadrant_x` 37.85 m:
  2.1 m forward of the CPS join), A&R winch, handling winches, carousel (61.05 m) and tower move with it. The oval:
  170.5 m (was 188.1). Hull length and beam unchanged.
- **The D** (`deck.quadrant_d`, `d_shape`): exactly as wide as the cable's path (its lip 4.31 m from the middle). Below
  the cable's height its frame (bar, spokes, ring, gutter floor) stays within |y| ≤ R − 450 mm (3.60 m: inside the
  bottom tracks' pads, the horns' rollers and plates); outside that nothing of it is lower than 30 mm under the cable's
  centre (31 mm over the bottom track's pads). Towards its ends (beyond 57° from the front) the gutter is an upper
  channel only: a top plate, guide rollers hanging from it (no stub under them), the outer lip down to the cable's
  centre. An upper bar over the cable's height joins the channel's ends; the tipping eyes sit on brackets over the
  cable's line at y = ±4.20 m, 0.58 m over the channel (their wires clear the gutter by ~140 mm all through the tilt;
  lower down they ran through it). The upper bar ends at the gutter's inner web: closer to the cable it read as a seat
  (a WRAP) in the cable reading of task 0078.
- **The tensioner** (`machines.tensioner`): base frame and bottom track fixed; inboard of the cable line nothing rises
  higher than 586 mm under the cable (its drive moved outboard). Lift frame on two guide columns at the outboard ends,
  **2 lift cylinders** (rods ride on "Top track lift", 0 … 902 mm); the carriage hangs on a **hinge along the cable on
  the outboard side** (760 mm out, at the top pads' level) and **"Top track tilt"** turns it 0 … **70°** out to its own
  side (positive: the inboard side rises, the track swings out over the hinge; tensioner 1 to port, 2 to starboard).
  **2 tilt cylinders** pinned on the lift frame's cheeks and the carriage's levers (pushing, 973 → 1,515 mm), made as
  app cylinders by the demo's `cylinders` stage (pins in the route sheet: `tensioners[].tilt_cylinders`). Open:
  every moving part is outboard of its own cable line; within the D's height (−60 … +450 mm about the cable) 900 mm
  outboard of it. `A.info["tracks"]` unchanged in form (0079 reads it).
- **Cradles:** every highway cradle the D sweeps over is a lifting cradle (21: 6 on side B, 15 on side A), one lead
  joint per lane ("Cradle 3 drop", "Cradle 9 drop" in the sheet's numbering; `drive.lane` = A/B), the others follow;
  none at the top of side B's rise (they would have to drop along a slope) or under the D's bar at rest. Horns: their
  side plates end 10 mm under the cable.
- **Demo project** (`blender/demo.py`): shot 5 = lift, tilt out 70°, back, squeeze (12 s as before); shot 7 = both
  tensioners lift and tilt out, both lanes' cradles drop (3.5 s), then the D travels aft between them; `cradle_drops`
  (one per lane), `tensioner_open`, `TENSIONERS`; cameras "Tensioner" and "Roller highway" on the new lane. Joints:
  308 in the sheet (was 314), `MIN_JOINTS` 309; 6 cylinders (was 2). Animation 79.6 s with the cards (was 78.4).
- Guide (demo section), CHANGELOG, the Heavy PC-check line's text and a check that both tensioners lift and tilt 70°.

**Tested and measured** (Claude Code web machine, 4 cores, no graphics card; invented demo model only):
- New `tests/test_demo_cable_lay.py::test_the_d_quadrants_way_is_clear`: every part's triangles against the room the D
  sweeps over its whole travel (36.6 m) with the tensioners open and the cradles dropped: **0 parts in it**; closed,
  the top tracks are in it (the check sees them), base frames never; un-dropped cradles in it. Open, every moving part
  of a tensioner from the cable's height up is outboard of its own cable line. `test_tensioner_lifts_and_tilts`
  rewritten: tilt about ±x on the outboard side, +30° takes the top track's middle > 300 mm outward and up.
- Tensioner on its own (scratch check, OpenCascade booleans between moving groups): 0 overlaps at lift −76/0/451/902
  mm and tilt 0/15/35/55/70°.
- `tests/test_demo_project.py` (whole demo, small form): **0 clash rows over the whole animation** (shots 5 and 7
  included; sea at rest as before), tilt cylinders follow lift + tilt (+0.54 m at 70°), shot 7 opens both tensioners
  and drops both lanes before the travel; the cable reads with 0 problems (197 rollers, 2 chutes, 8 bends, 170.50 m,
  0.5 mm off the CAD cable). 17 passed. `test_demo_cable_lay.py` 43 passed; `test_paths_core.py` demo tests updated
  (10 arcs, 195 rollers) and pass.
- **Make demo project** (full form, this machine): **74 s, was 77 s** (main before this task, same machine).
- Pictures (Cycles CPU, 24 samples, 1280×720 stored 960×540): `tasks/img/0102-d-between-open-tensioners.png` (from aft,
  both tensioners open, the D between them), `tasks/img/0102-u-from-above.png` (the U from above, at rest).
- The clear band: between the two cable lines nothing of an open tensioner at any height from the cable's up; the D's
  own room is 8.62 m wide, from 30 mm under the cable's centre to 1.79 m over its rail top (tipping eyes), 0.30 m
  over the cable at its edges.
- GitHub: 3 full runs on the branch. The first was red only in `tests/test_paths.py` (it counts the demo cable's
  rollers and bends too: 218 → 195, 14 → 10, 188.06 → 170.50 m); 0105 and 0103 took 0.2.82 and 0.2.83 while it ran, so
  the next two runs were merges of main + renumbering (both green: runs 43435919960, 43438261138, ~15 min each).

**Open points / follow-up tasks:**
- For small cables (under ~Ø 120) the bottom pads' V edges stand higher than the cable's centre; the D's hanging guide
  rollers then cannot reach down to the cable without touching the pads when passing (only Ø 200 is built in tests).
- The cable on its path stays drawn at rest while the D moves (as before, task 0082); at the end of the travel the
  D's gutter end sits over horn A's upper bend, where the cable would have to go (0081/0082 decide the cable's way).
- The guide's demo overview picture (`docs/img/demo_overview.jpg`) still shows the older deck.
- **For the Machining lane (not this task's code):** main's first run of 0.2.84 (43440853982) failed once in the PC
  check line `milling.rotary` – the 4th-axis bar came out uncut ("cut 0.08 s", radius 25 instead of 23/22). The same
  tree passed it on the branch (cut 3.8 s) and 3 times out of 3 here; a re-run of the failed job passed and released.
  Looks like a rare race in the cut's refresh right after the bake (added with 0103?).
- The progress note `claude/render-app-progress.md` lives in the claude.ai project: this session cannot reach it – the
  lead adds the entry.
- No subagents were used (one design across tensioner, D and layout; the risk was in geometry the checks above cover).
