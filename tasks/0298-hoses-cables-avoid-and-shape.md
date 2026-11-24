# 0298 – Hoses and cables round 3: Avoid other parts (collision on / off) and a route you can shape between the two ends

**Who:** worker · **Status:** done (0.2.225) · **Branch:** `task/0298-hoses-avoid-and-shape`
**Started by:** lead, 23 Nov 2026 (owner's list, 23 Nov 19:39: "Hoses and cables improvements. A collision active button,
for collision with other objects. And able to adjust the path it takes, between the two points.") · **Model:** Opus ·
effort High
**Area:** Flex parts lane – `core/flex.py`, `blender/flex.py`, `ops_flex.py`, `ui_flex.py`, the drawn hoses of 0240
(`drawn.py`, `ops_drawn.py`), `paths.py` only where cables need the same; `clash.HOOKS`; tests, test models
(`tools/make_test_flex.py`), tour, PC check (+ Heavy if it costs), guide, CHANGELOG.
**Not:** sea cables and spools (Sea / Flex parts work of 0081 / 0080 stays), drag-chain links (0058's chain solver) unless
the same switch fits them for free.

## Background

Hoses solve as an elastic rod under its own weight between fixed ends (0058); they pass through other parts, and flex
parts are left out of the clash check. 0240 draws hoses / cables by clicking points (fittings, clips, sheaves); its open
points: a drawn route is not re-laid when its sheaves move, clips hold the hose fixed.

## What to do

1. **Avoid other parts** – a switch on each hose / cable row (off by default): on, the solved shape stays outside the
   other parts with its own radius – it lies on them and slides along – live and at Build (scripts-off safe, as today).
   Which parts count: everything visible near it (a box search) or picked ones – choose and say. Measure the cost per
   hose per frame on the test models and on a big scene; a Heavy line if it matters.
2. **Shape the route between the two ends** – for any hose / cable, CAD-read or drawn: its middle line with handles in
   the view: drag a point, click on the line to add a via point, remove one; the solver keeps the hose through the via
   points; **Length**: automatic or a fixed number. Undo, save, model update keep it.
3. 0240's open points: a drawn route re-laid when its sheaves / parts move; clips that ride on their part.
4. A hose with Avoid on can join the clash check (an option on the clash panel).

## Done when

- [ ] Tests: a hose across a block with Avoid on stays outside it at every frame of a motion (distance ≥ radius − a set
      tolerance), off = as today; a via point dragged changes the route, kept over save + reopen and a model update
- [ ] Test model with a block in a hose's way; tour stop `flex_avoid`; PC check line(s); guide + pictures; function
      entries; full suite + GitHub run green; report with the cost numbers; merged, version, release

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 24 Nov 2026 (branch `task/0298-hoses-avoid-and-shape`; release 0.2.225)

**What changed:**
- **Avoid other parts** (`FRFlex.avoid`, a tick under Length): `core/flex_avoid.py` (new, NumPy: a *field* of bodies –
  `Box`, `Ball`, any body – at per-row world places, culled by the hose's reach) and a contact term in `core/flex.py`
  (`solve_hoses(..., avoid=, clear=, seed=)`, `solve_motion(..., avoid=, clear=)`): the hose is solved as before; where
  it comes nearer than its radius + 0.5 mm, it settles again on the fine level with the parts pushing 4 samples per
  segment out (smoothed penalty, in steps: first lifted towards the line of its ends, then square to the surfaces).
  Live: the last pose's answer is the start (stays on its side). Build: frame after frame from the frame before; if
  that jumps, once more backwards (fewer jumps kept). `blender/flex_avoid.py` (new): **which parts – my choice:
  everything shown near it** (within the hose's length of its two ends, in the pose when it is switched on / at each
  Build; not its fittings, clips, other flex parts, drawn objects, hidden or excluded parts; at most 64, nearest
  first); a part's mesh as a body (BVH + `clash.Mesh`'s inside test). Avoided parts join the places read at Build
  and the live "moved?" check (`flex.held_objects`). Off = exactly as before (tested).
- **Shape the route** (`fresing.flex_route`, new `ops_route.py`): the middle line + dots in the view; click the line
  to add a via point, drag it, X removes, Enter / Esc. `blender/flex_route.py` (new): a via point is a clip with
  `via` on, carried by the two end parts by a share of the screw between them (as the CAD guide), passed along the
  bisector of the way in and out; each stretch's share of the length from the route. **Automatic length**
  (`FRFlex.length_auto`). Clear button. Kept over save, undo (one step per edit session) and model update (re-set
  from where it was in the view). CAD-read and drawn hoses alike.
- **0240's open points:** a drawn cable route is laid again from its clicks (kept in their parts' coordinates,
  `paths.ROUTE`) at a model update (`paths.relay`); routes drawn before this version keep their old behaviour. Clips
  already ride on their part (tested by 0240); sliding through a clip was not built.
- **Clash check:** "Check hoses that avoid parts" (`FRClash.hoses`): `clash.ROW_HOOKS` + `flex.clash_rows` give a row
  where such a hose is deeper in an avoided part than the clash depth (from the built shapes, every frame).
- Test model `test_flex_avoid_a/_b.step` (`tools/make_test_flex.py avoid`: a block in a Ø20 hose's way, a lift
  travelling −400 … +100 mm; B adds a lamp); `flex.set_up_test_avoid`. Tour set `flex_avoid`, stops `flex_avoid`,
  `flex_route`; PC check line `motion.flex_avoid`; functions `flex.avoid`, `flex.route`; guide sections + picture
  `view_flex_avoid.jpg`, panel pictures `panel_4_flex*.png` again; CHANGELOG; CLAUDE.md layout.

**Tested and measured** (4-core web machine):
- Real app `tools/ui_test_route.py` (group tour-b): 12/12 in 23 s – the hose lies on the block, the mouse lights up
  the line, a press adds a via point, a drag moves it 100 px up, the hose runs through it, Enter, undo, redo, X over
  the dot removes it, Esc puts it back.
- `tests/test_flex_avoid.py` 22 tests, `tests/test_flex_avoid_independent.py` 36 (one strict xfail, below); the flex,
  drawn, paths, clash and guide tests of the area locally; tour stops built and checked; PC check line OK in 4.7 s.
- Avoid model, lift −400 mm: off 84.6 mm into the block; on: the hose's surface 2.8 mm above it live, worst 0.75 mm
  above over the 101 frames of a Build (measured along the polyline, 800 points). Core: a sagging Ø20 hose over a
  block, 9 lengths / stiffnesses: at most 2.5 mm in (where it bends round a sharp edge, the straight piece between two
  samples cuts the corner).
- Cost: live 15–20 ms per pose while the hose is clear, 0.09–0.16 s while it lies on the block; Build of 101 frames
  4.35 s (without Avoid 0.2 s). Core: 120 frames of one hose against a box 1.4 s. No Heavy line: the cost is per
  hose that has Avoid on and per part near it (capped at 64), not per scene size; the PC check line reports it.
- Independent tester (subagent, did not write the code): 36 tests, found 6 faults – the hose jittered 3–9 mm between
  frames standing still and crept when posed again (contact Newton stopped before settling: now smoothed + up to 60
  steps); a 15–30 mm wall crossed; a part hidden after Avoid was on was still avoided; the documented callable
  signature crashed; odd ids in `Field`. All fixed except: **a wall about as thin as the hose (20 mm for Ø20) can
  still be crossed** (strict xfail, documented in the guide).
- GitHub runs: see below.

**Open points / follow-up tasks:**
- Thin walls (≈ the hose's diameter) can be crossed where the hose sags into them.
- A stiff hose with a lot of slack between fittings in line can come to rest as a high arch over a part rather than
  draped on it (both are shapes the model allows; a frame solved alone picks by its start).
- Parts that come near only during a motion, from further than the hose's length, are not avoided.
- A drawn cable from before 0.2.225 keeps its route as clicked at a model update (its clicks were not kept). Sliding a
  hose through a clip is not built. A drag of a via point solves the hose at every mouse move (0.1 s while it lies
  on a part: the dot can lag a little behind the mouse).

**Owner's check on your PC:**
1. Help > Make test tour project, open the set "A hose avoids a block, a route shaped by hand", press Go on "A hose
   lies on a block": the lift goes down, the black hose lies on the grey block.
2. In 4 Motion > Hoses and drag chains choose HOSE, untick **Avoid other parts**: it sags through the block; tick it
   again.
3. Press **Shape the route**, click on the white line beside the block, drag the dot sideways, press Enter: the hose
   runs through the dot. Ctrl+Z takes it back.
