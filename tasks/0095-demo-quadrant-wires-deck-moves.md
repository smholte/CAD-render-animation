# 0095 – Demo: quadrant wires as the owner works, cable engine and handling winches moved

**Who:** worker · **Status:** open · **Branch:** `task/0095-demo-quadrant-wires` (or the web session's branch)
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

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
