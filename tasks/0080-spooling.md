# 0080 – Spooling: the cable comes off the carousel and the wire off the drum, layer by layer

**Who:** worker (Claude Code web) · **Status:** running · **Branch:** `claude/epic-cori-m7bsix`
**Started by:** lead chat, 13 Nov 2026 (cable-lay line; design in `tasks/0075-motion-paths-design.md` part D, owner's
answers at its end) · runs **side by side with 0079** (tensioner tracks) – see "Lane" for who owns what
**Lane:** Flex parts. New files `core/spool.py` (no Blender), `blender/spool.py`, `blender/ops_spool.py`,
`blender/ui_spool.py` (4 Motion > **Drums and carousels**, a sub-panel next to Cables and paths),
`tools/make_test_spool.py`, `tests/test_spool*.py`. **0080 owns `blender/paths.py` and `core/paths.py` in this round**
(a cable's start on a spool – additive; 0079 does not edit them). Additive: `joints.py` (one new coupling kind, below),
`props.py`, `ui.py`, `animation.py` (bake hook), `reimport.py`, `clash.py` HOOKS, `part_types_data.py` (Winch drum,
Carousel if missing), `blender/demo.py` (a new stage), the tour, the PC check, the guide. Do **not** edit
`ops_paths.py` / `ui_paths.py` (0079 adds "Speed from joint" there).
**Model:** **Opus · effort High**, split over subagents (CLAUDE.md "Subagents in a worker session"; at most 3; an
independent tester that did not write the code) · **Place:** Claude Code on the web, environment
"CAD-render-animation"

## Goal

The owner sees where the cable comes from: on the carousel the coil's top layer gets smaller turn by turn while the
carousel turns at the right (changing) speed and the loading arm / guide follows the turn being paid out; on a winch the
wire rope comes off the drum turn by turn and layer by layer in the spiral groove, the drum turning faster as the layers
get smaller. One cable speed (m/min) drives it all, as in 0078.

## Background (read)

- **0075 part D** (drum spooling and the carousel): wraps as a helix per layer, the hand reversing each layer, the next
  layer one rope Ø · cos 30° higher; drum angle as a function of payout is **piecewise linear** (one piece per layer) →
  a **"follows by table" coupling** (a driver reading the cable joint whose F-curve has one key per layer change;
  prototype max error 3·10⁻⁶ rad over 100 m and 3 layers). The wraps are one curve trimmed from its start by the payout
  (Trim Curve, length mode) – **no Python per frame**. Its Blender 5.2 lessons (Geometry Nodes inputs by
  `.properties.inputs.<id>.value`, clear a new driver F-curve's keys before writing a table, Trim Curve's `Start_001` /
  `End_001`) are in its report and CLAUDE.md section 8. Carousel: the same with the axes swapped – a flat spiral per
  layer, layers stacked upwards; **draw only the top layer and the turn being laid as cable; the stack below as one
  solid that shrinks with the payout** (else millions of vertices).
- **0078** (`blender/paths.py`, `core/paths.py`, done 0.2.80): the cable's ends are `FIXED` or `WHEEL` (the cable starts
  on its first wheel at a fixed point of that wheel's circle). A spool end is new: **the point where the cable leaves
  the spool moves** (across the drum's width, inwards on the carousel's layer) and the first free span changes with it
  – live while posing, solved per frame at Build (0078's mechanism; one pass through the frames with hoses and cables).
  The moving looks (power cable stripes, wire-rope lay) read the paid-out length; the cable on the spool must show the
  same look.
- **Owner's answers (0075):** cable lay uses a **carousel** (and standalone storage carousels); drums rarely for cable lay
  but standalone **drum / reel winders** exist; winches normally **spiral groove**, now also **Lebus** for one client;
  drum look: spiral groove first, Lebus later.
- **The demo:**
  - Carousel (`machines.carousel`): turntable on support rollers, inner core, rim fence, `CABLE COIL` = one static
    revolved solid (15 flat layers; the top one partly paid out; a notch where the innermost turn leaves), "Carousel
    turn" follows "Cable travel" at a **fixed** ratio taken at the rest coil radius (`deg_per_mm` in the sheet). The
    loading tower's arch only **slews** ("LOADING TOWER: Arch slew"); the coil radius under its guide follows from the
    angle; the guide's roller cage swivels ("Guide cage swivel", sheet `"by": "follows coil"`). Shot 3 turns the
    carousel (time-lapse × 10) while the arch slews 6° by hand.
  - Winches (`machines.winch`): spiral-groove drum (pitch 1.06 × rope Ø), `WIRE ROPE` on the drum as one plain sleeve
    over part of the barrel, "Drum turn" with a fixed `deg_per_mm` at the outer layer; a fairlead sheave + a short rope
    to a shackle on some. One Lebus drum (`lebus_drum`, risers, 35° crossovers) without rope. The A&R and tipping wires
    of the quadrant (0095) are demo-only drivers (0082 makes them app cables) – leave them.
- Repository public: invented models only (CLAUDE.md section 6).

## Scope

1. **A spool** (4 Motion > Drums and carousels > **Add drum** / **Add carousel**): click the drum barrel or the
   turntable (axis from the round face, barrel / core radius, width between the flanges or the coil's inner and outer
   radius from the mesh); the cable (an 0078 cable, or a new one); rope / cable Ø from the cable; **wound at the start**
   (m – or read from a CAD coil / wire solid: the length it holds); first layer starts left / right (inside / outside);
   the cable leaves over / under (inner / outer). The spool's turning joint is made or taken (the demo's "Drum turn",
   "Carousel turn").
2. **"Follows by table" coupling** (`joints.py`, additive, a new coupling kind next to the ratio one): the spool's turn
   follows the cable joint piecewise linearly (one piece per layer; on the carousel one piece per turn or a few – the
   radius changes every turn), written as a driver F-curve table; scripts off, queue, any fps. Old projects unchanged.
3. **The cable on the spool:** drum: the wraps as one curve (helix per layer, hand reversing each layer, layer k at
   rope Ø · cos 30° × k higher), trimmed by the payout, tube with the cable's look; the stack under the current layer as
   a solid if many layers. Carousel: the top layer's turns + the turn being paid out as cable, the full layers below as
   one solid ring that gets lower layer by layer (no million-vertex coil). The CAD coil / wire solid is replaced the 0058
   / 0078 way (item off → the CAD shape again).
4. **The leave point and the free span:** the cable's start sits where it leaves the spool; the span to the first
   contact (the drum's fairlead, the arch's guide) follows it – live while posing, every frame at Build. Fleet angle
   to the first sheave worked out at both drum ends: a warning above **1.5°** (rule of thumb; the owner may change it).
5. **Followers of the layer:** a slide or rotate joint can follow the leave point by table – a **level wind** carriage
   (slide, zig-zag across the drum) and the carousel's **loading arm / arch** (the demo's "Arch slew", angle from the
   leave radius) and the guide cage swivel. Clicked in the panel ("This joint follows the layer").
6. **Lebus (second half; may become a follow-up if the task grows – say so in the report):** on a drum with Lebus
   grooving, the wraps run parallel with two crossover zones per turn (the demo: 35°) and step up at the risers. Plain
   spiral first; Lebus only after scope 1–5 are green.
7. **Clash:** a spool's cable against its drum / turntable / flanges gives no rows (HOOKS).
8. **Demo stage `spool`** (after `cable`): the carousel's coil becomes a spool on "Cable travel"; "Carousel turn" follows
   by table; the arch slews with the layer; shot 3 shows the top layer getting smaller and the arch following (drop the
   hand-made 6° arch step). One handling winch (the one in shot 8, if cheap) gets its wire on the drum by table. 0 clash
   rows in the demo's clash test. Time of Make demo before / after.
9. **Test model** `tools/make_test_spool.py` → `test_spool.step` (invented, small: a spiral-groove winch drum with a
   fairlead sheave on a level-wind carriage and a wire; a small carousel with a coil of 3–4 layers, a guide arm on a
   slew joint and a cable; optional a Lebus drum). Tour stop "Drum and carousel spooling", PC-check line
   `motion.spool`, guide section "Drums and carousels" with pictures, model update keeps spools (part IDs), old projects
   open.

## Accuracy and speed (tests)

- Drum angle vs payout: within 0.01° of the exact helix over 100 m across ≥ 3 layers (0075: 3·10⁻⁶ rad); the leave
  point on the rope circle of its layer within 0.5 mm; length on the spool + paid out = wound at the start within 1 mm.
- Carousel: turn per metre right at every radius within 0.1 %; the coil's top layer and the solid below keep the
  volume (length × cable section) within 1 %.
- Fleet-angle warning names the drum end and the angle; a spool that runs empty or overfills says so in plain words.
- Cost per frame on the demo vessel with the carousel and one winch spooling: ≤ +3 ms; Build of the demo with the
  stage: say before / after.

## Done when

- [ ] Scope 1–5, 7–9 work in the real app (panel screenshot checked), every button with a tooltip; scope 6 done or a
      follow-up written in the report.
- [ ] The tests above pass; an agent that did not write the code wrote tests from this brief (report: what it found).
- [ ] Demo: shot 3 shows the carousel's top layer paying out with the arch following; 0 clash rows; a Cycles still of a
      drum with its layers in `tasks/img/` (invented model only).
- [ ] Guide section, tour stop, PC-check line; GitHub green; report filled in; merge to main and release.

## Not in this task

The demo's deck layout (0102 runs at the same time: it widens the D-quadrant's lane, remakes the tensioners and may
move the handling winches – read places from the sheets, never fixed numbers; do not edit `layout.py`, `deck.py`,
`machines.tensioner`). Tensioner tracks and pads (0079 – runs at the same time: do not edit `ops_paths.py` / `ui_paths.py`, `blender/tracks.py`);
the catenary, water clarity, CPS (0081); quadrant operations, the A&R and tipping wires (0082); rope slack, rope
stretch, dynamics; multi-fall reeving (owner: not needed).

## Design (worker, 13 Nov 2026 – the subagents' brief; keep it current)

Units: metres and radians everywhere in code; mm / degrees only in the panel and in sentences.

### The idea in one paragraph

A **spool** (drum or carousel) holds the start of an 0078 cable. The rope on it is one **wound path** from the anchor
(L = 0, innermost) to the outer end, laid layer by layer (`core/spool.py`, no Blender). With W0 metres wound at the start
and p metres paid out (the cable joint's value x direction), the rope on the spool is the path from 0 to `W0 - p`; its
end there is the **leave point**. Everything else is a function of p only, written once as driver tables (no Python per
frame): the spool's turn ("follows by table", a new coupling kind in `joints.py`), the followers (level wind, loading
arm, guide swivel), and the trimming of the drawn rope (a Geometry Nodes tree on the owner object). The free span from
the leave point to the cable's first contact is 0078's path with a **moving start**: the start is the leave point,
worked out per frame from the spool's own place (the turned drum) and the payout (both read like 0078's carriers), so
the drawn free span always starts exactly where the drawn wraps end.

### Spool frame and the wound path (`core/spool.py`, subagent A)

Spool frame: origin on the axis, local **z = the spool axis**; a point of the rope is `(r cos phi, r sin phi, a)`
(a = place along the axis). The path is a list of **pieces**; in each piece phi, a and r are linear in L (from L0 to
L1). A piece's length is the true length of that curve (Gauss-Legendre), so `L` is the rope length to within 1e-9
relative. `hand` (+1/-1): phi grows (+1) or shrinks (-1) with L.

* **DRUM** (`Spool(kind="DRUM", d, r1, a_lo, a_hi, pitch, start, hand, r_max, groove, crossover, crossover_at,
  climb)`): layer k (0, 1, …) at rope-middle radius `r1 + k·d·cos30°`; rope middles from `a_lo + d/2` to
  `a_hi - d/2`; one helix piece per layer with `(a_hi - a_lo - d) / pitch` turns (a real number: the layer fills edge
  to edge); layer 0 runs from the `start` side (+1: from a_lo), the next back; between layers a **climb** piece
  (default 90° of turn) at the flange: a constant, r from r_k to r_k+1. Layers while `r_k <= r_max`.
  `groove="LEBUS"`: in a layer the rope runs parallel to the flanges (a constant) and shifts by pitch/2 in two
  **crossover** zones per turn (`crossover`, default 35°, the first starting at `crossover_at` – an angle fixed on the
  drum); pieces: parallel, crossover, parallel, crossover … (exact helix pieces each).
* **CAROUSEL** (`Spool(kind="CAROUSEL", d, r_in, r_out, a_bot, start, hand, a_top, climb)`): flat layers; layer k's
  rope middles at `a = a_bot + d/2 + k·d`; an Archimedean spiral from r_in to r_out (start +1, layer 0 inside out) or
  back, the radius changing by d per turn; the climb to the next layer at constant r. Spiral pieces at most
  `min(10°, 0.004·pi·r/d)` of turn each (so the turn per metre is right to 0.1 % everywhere).

API (all vectorised over L / p where it says so; numpy only):

```python
@dataclass class Spool: ...                                    # fields above, metres / radians
@dataclass class Path:  L0, L1, phi0, phi1, a0, a1, r0, r1, layer, kind (arrays, one row per piece), total, spool
wind(spool) -> Path                                            # the whole spool, anchor to full
at(path, L) -> (phi, a, r, layer)                              # vectorised; L clipped to [0, total]
xyz(phi, a, r) -> (..., 3)
tangent(path, L) -> (..., 3)                                   # unit, the way L grows
layer_radius(path, k) / layer_place(path, k)                   # r of a drum layer / a of a carousel layer
polyline(path, L_lo, L_hi, sag) -> (pts (n, 3), L (n,))        # for drawing: points so the drawn tube is within
     # `sag` of the true path; the radius of each point is pushed out so that the straight distance between two
     # neighbours equals their difference in L (to 1e-9 relative) – a Trim Curve by length then cuts at true L
wound_at(path, a, r) -> L                                      # the L whose point is nearest (a, r): the CAD leave point
tangency(rho, alpha, r, hand) -> psi                           # the angle where a rope paid out towards a point at
     # polar (rho, alpha) leaves the circle r: psi = alpha + hand * acos(min(1, r / rho)) (vectorised)
breaks(path, W0, p_lo, p_hi) -> p (sorted)                     # payouts where a piece starts or ends, + p_lo, p_hi
angle_table(path, W0, psi, p) -> theta (same shape as p)       # the spool's turn about +z at payout p:
     # theta(p) = (psi(p) - psi(0)) - (phi(W0 - p) - phi(W0));  psi: array over p (or None = 0)
arm_angle(c_s, c_a, a0, r_target, prefer=0.0) -> angle         # plane geometry (2-vectors): the turn about c_a that
     # brings point a0 to distance r_target from c_s; the answer nearest `prefer`; nan when it cannot
fleet_angles(path, q) -> (at a_lo, at a_hi)                    # rad: drum only; the rope from the top layer's middle
     # at each flange to the point q (spool frame), against the plane square to the axis
stack(path, W0, p, drawn_layers) -> (L_low, solid)             # vectorised over p: draw [L_low, W0 - p] as rope; the
     # full layers below it as one solid: drum = its outer radius (0: none), carousel = its height above a_bot
stack_breaks(path, W0, p_lo, p_hi, drawn_layers) -> p          # where L_low / solid step
capacity(path) -> total;  status(path, W0, p) -> '' | 'empty' | 'full'
```

### "Follows by table" (`joints.py`, worker)

`FRJoint.couple_table` (string, '' = the ratio coupling as before): the owner of the table, e.g. `spool:Drum`. The
table itself is a float array on the follower's motion empty (`fr_table` = x0, y0, x1, y1 …, leader's value -> this
joint's value, internal units, linear between keys and beyond the ends), written with `idprops.store_array`.
`joints.set_table(scene, j, leader, xs, ys, owner)`, `joints.table_of(j)`, `joints.chain_map(scene, j)` -> (top, f):
a chain may hold ratio and table steps (the carousel's support rollers follow "Carousel turn" by ratio, it follows the
cable by table): the drivers then read the top joint and carry the combined table as F-curve keys (simple expression
`a + 2.0`, keys moved by the same BIAS, LINEAR extrapolation, an additive generator takes BIAS off). `get_value`,
`driven_value` and `_write_one` use `chain_map`; `chain_affine` is unchanged for ratio chains and returns
(None, 1, 0) when a table is in the chain. Picking another leader or ratio in the panel drops the table.

### Blender side (`blender/spool.py`, worker; `ops_spool.py`, `ui_spool.py` later)

* `FRSpool` in `scene.fresing.spools`: kind, cable (name), part/part_uid (clicked), coil/coil_uid (CAD coil or wire
  solid, may be empty), joint (the spool's turn), frame (4 x 4 in the joint's arrow coordinates), the Spool numbers,
  wound, typed flags, followers (`FRSpoolFollower`: joint, mode ACROSS / ARM / ALONG, point), fleet limit (1.5°),
  removed contact (JSON, to put back), state (problem, layer, on spool, fleet angles).
* The cable's start: `a_kind = "SPOOL"`, `a_part` = the spool joint's motion empty. `paths._inputs_of` adds the spool
  slots (the spool's motion empty, the cable joint's frame and motion – the payout is the motion's place on its
  frame) marked **live**: a cable that stays as drawn still reads them (and the slots carried by a follower) where they
  are. `paths._solve_item` asks `spool.starts(scene, cable, rel, slots)` for the start points.
* The drawn rope: the owner object (the CAD coil part, or "FR spool <name>" parented to the clicked part) gets the
  Geometry Nodes modifier "FR spool": Object Info (the hidden polyline mesh "FR spool shapes <name>", owner's
  coordinates, point attribute `fr_s` = L - W0) -> Mesh to Curve -> Trim Curve (length: Start = L_low(p) by a CONSTANT
  table driver, End = W0 - p by a simple-expression driver on the cable joint) -> tube with `fr_cable` (the 0078 look;
  `fr_cable_pay` stays 2.0 = nothing paid out: the rope on the spool does not move along it) + the solid (unit ring /
  sleeve mesh scaled by a CONSTANT table driver).
* Tables written when a spool is made or changed: the spool joint (angle_table, psi from the first contact's
  departure point, carried by an ARM follower when it rides on one), each follower (ACROSS: a(W0-p) - a(W0) along the
  joint's axis; ARM: arm_angle with r_target = sqrt(r(p)^2 + h^2), h the tangent length in the CAD pose; ALONG:
  psi(p) - psi(0) minus the ARM turns it rides on).
* Hooks: `animation.bake` (nothing new: the cable's bake reads the spool slots), `reimport.py` (part IDs), clash HOOKS
  (the coil part), `paths` (start), `flex` (read pass: through paths' slots).

### Test model (`tools/make_test_spool.py`, subagent C)

`test_spool.step` (tests/data + fresing_render/data), invented, every part one solid. See the agent brief in this
file's history (numbers in `NUMBERS` of the maker).

### Subagents

A: `core/spool.py` + `tests/test_spool_core.py`. C: `tools/make_test_spool.py`, `tests/data/test_spool.step`,
`fresing_render/data/test_spool.step`, `tests/test_spool_model.py`. Later: E independent tests (did not write the
code), D panel + real-app test, F guide. Worker: everything else.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (Opus, effort High; 4 cores, no graphics card), 13 Nov 2026, branch
`claude/epic-cori-m7bsix` (the web session's branch). Released as **0.2.83**.

**What changed:**
- **4 Motion > Drums and carousels** (`ui_spool.py`, `ops_spool.py`): Add drum / Add carousel (click picker with the
  hover highlight; the turning joint is taken, or made from the round face clicked), the list (on/off, layer, check),
  the status line ("49.6 m on it, layer 3 of 8; holds 201.5 m", or the warning), On it at start (m), Grooves (Spiral /
  Lebus), Groove pitch, First layer from the other flange / from the rim, the fleet angle at both flanges, **This joint
  follows the layer** (search list) with each follower's way (Across the drum / Arm over the coil / Along the turn),
  More: first layer, inner/outer radius, crossover, fleet warning limit, Read it again. Tooltips: 689, 0 missing.
- **The maths** (`core/spool.py`, no Blender, subagent A): the wound path from the anchor – drum layers as helices
  (spiral groove) or parallel runs with two crossovers per turn (Lebus), climbs at the flange cut into short pieces;
  carousel layers as Archimedean spirals, alternating in/out –, true length per piece, the drawing polyline whose
  chords equal the length, the leave tangent, the spool's turn and the followers as functions of the payout, arm
  angle, fleet angles, the stack of full layers.
- **"Follows by table"** (`joints.py`): a new coupling kind next to the ratio – `set_table`, `chain_map` (a ratio on
  top of a table works: the carousel's support rollers and drive wheels follow "Carousel turn", which follows the
  cable by table), drivers read the top joint, the keys on the driver curve, simple expressions (scripts off), model
  update keeps it (specs), the joint details say "Follows … by a table". Old projects unchanged.
- **The Blender side** (`blender/spool.py`): a cable of 0078 starts on the spool (`a_kind` SPOOL); the leave point is
  worked out per moment from the turned spool and the payout (live slots of the cable, also for a cable that stays as
  drawn), so the free span always starts where the drawn rope ends; the spool's turn and its followers by table; the
  rope on the spool drawn by Geometry Nodes on an object of its own (cut exactly at W0 − p by each point's own length),
  the full layers below as one solid scaled by a step table; the CAD coil hidden by an empty modifier; bends of the
  cable lying on a following arm swing with it; empty / overfull / fleet-angle warnings (panel and Build); clash HOOK
  (the CAD coil left out); model update (part IDs; the cables re-read and taken again); `set_up_test_model`.
- **Demo:** stage `spool` (after `cable`): the carousel's coil is the spool of "Power cable" on "Cable travel" (28.8 km
  on it, 24 layers possible), "Carousel turn" by table, "Arch slew" (arm) and "Guide cage swivel" (along) follow the
  layer; shot 3 pays out 150 m (time-lapse x 90, three turns of the top layer) – the hand-made 6° arch step is gone.
  Handling winch 1 (shot 6): its fairlead rope is a cable on its own speed joint "HANDLING WINCH 1: Wire travel", its
  Lebus drum spools it (shot 6 pays out 6 m instead of turning the drum by hand).
- **Test model** `test_spool.step` (`tools/make_test_spool.py`, subagent C): a spiral-groove winch drum with a
  level-wind fairlead and a wire; a carousel (3 full layers + a partial one) with a slewing arm and a guide sheave.
  Tour stop "Drum and carousel spooling", PC-check line `motion.spool`, real-app test `ui_test_spool.py` (43 checks),
  guide section "Drums and carousels" with two pictures, CLAUDE.md (files, three lessons). Stills:
  `tasks/img/0080_drum_layers.jpg`, `tasks/img/0080_carousel_top_layer.jpg` (Cycles, processor, test model).

**Subagents:** A the maths + 29 tests; C the test model + its test; E the independent tests (46, from the brief; it found
6 real faults: a model update broke both spools, a typed wound length gave a 140° kink and a mis-set level wind, the
drawn rope overshot the leave point by up to 1.7 mm (Trim Curve sums 32-bit lengths), the solid half a cable
narrower than the coil, the fleet warning without its flange in Build's notes, the wrong flange named when the first
layer starts at the other one); D the real-app test, the guide section and its pictures (it found: the panel wrote
while drawing and stopped after its status line, the drawn rope rendered white, the joint list's strings went stale,
a cut-off follower row, the wound length shown in mm). All fixed by the worker except the solid's width (kept: the
brief asks that it keep the cable's volume within 1 %, so it spans the rope middles; E's test now checks that).

**Tested and measured** (web machine, 4 cores, no graphics card, bpy module unless said):
- Tests: `test_spool_core.py` 29, `test_spool_model.py` 10, `test_joint_table.py` 7, `test_spool.py` 11,
  `test_spool_independent.py` 46 (E), the tour stop, the PC-check line (5.8 s), real-app `ui_test_spool.py` 43/43
  (real Blender, xvfb), the demo's tests (incl. a new one for shot 3 and the clash check: 0 rows).
- Accuracy (test model): drum angle within 0.01° of the exact helix over ±50 m across ≥ 3 layers (driver values as
  Blender writes them); leave point on its layer's circle within 0.5 mm (drum and carousel, 25 payouts); rope on the
  spool + paid out = wound within 1 mm; carousel turn per metre within 0.1 % at every radius; carousel stack volume
  within 1 % (core); level wind on the wrap; with it the fleet angle ~0°, without it 12.5° at the far flange (warned).
SPEED_PLACEHOLDER

**Open points / follow-up tasks:**
- The demo's handling winch drums have their fairlead 0.9 m from the flange: the app warns of a fleet angle of 20.9°
  for handling winch 1 (real geometry of the demo; Demo models lane: a level wind or a fairlead further away).
- The carousel's solid spans the rope middles (keeps the volume): half a cable narrower than the coil's edges on each
  side. Owner may prefer the look over the volume.
- A guide that hangs straight above the coil with no free span (the test model) cannot keep its plane along the turn
  without a swivel: the cable leaves at an angle in plan view (the demo has the swivel).
- Lebus: `wound_at` on a parallel run is ambiguous by up to a crossover's turn (the leave point's angle on the drum).
- Not tested: Windows beyond GitHub's install run; the render queue with spools (a queue copy is: open, build, render).
- For the owner's PC: shot 3 and shot 6 of the demo in the real view and a GPU render.
