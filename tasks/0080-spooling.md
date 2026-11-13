# 0080 – Spooling: the cable comes off the carousel and the wire off the drum, layer by layer

**Who:** worker · **Status:** open · **Branch:** `task/0080-spooling`
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

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
