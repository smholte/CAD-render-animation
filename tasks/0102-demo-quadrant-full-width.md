# 0102 – Demo: the D-quadrant as wide as the cable path; the tensioners lift and tilt out of its way

**Who:** worker · **Status:** open · **Branch:** `task/0102-demo-quadrant-full-width`
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

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
