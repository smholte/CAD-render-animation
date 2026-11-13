# 0078 – Cable paths: one cable speed, the cable over rollers, sheaves and chutes, with a look that moves

**Who:** worker · **Status:** running (13 Nov 2026) · **Branch:** `ccr-6b47eb16-zabyzg` (the web session's branch)
**Started by:** lead chat, 13 Nov 2026 (owner's main goal: the cable-lay line; design in `tasks/0075-motion-paths-design.md`,
owner's answers at its end)
**Lane:** Flex parts (after 0058) – new files `core/paths.py` (no Blender), `blender/paths.py`, `blender/ops_paths.py`,
`blender/ui_paths.py` (4 Motion > **Cables and paths**, next to Hoses and drag chains), `blender/cable_looks.py` (the two
cable looks, registered into the materials list additively – do not rework `materials.py`), `tools/make_test_paths.py`,
`tests/test_paths*.py`; reuse `blender/flex.py` (shapes mesh, node tree pattern, Build hook) – small additive changes
there are fine (this lane). **Demo models lane** too: a new demo stage `cable` in `blender/demo.py`, the demo test.
Additive: `props.py`, `ui.py`, `animation.py` (the bake hook), `reimport.py`, `clash.py` HOOKS, `part_types_data.py`
(Sheave, Roller, Chute if missing), the tour, the PC check, the guide.
**Model:** **Fable · effort High**, split over subagents (CLAUDE.md "Subagents in a worker session") · **Place:** Claude
Code on the web, environment "CAD-render-animation"

## Goal

The owner sees his cable-lay spread work: one cable speed (m/min) moves a cable – power cable black with yellow angled
stripes, or a steel wire rope – visibly along its whole route over rollers, sheaves, guide wheels and chutes, and every
roller and sheave it touches turns at exactly the right speed. In the demo project ("Cable-lay vessel") the cable on the
roller highways and over the chute moves at 10 m/min. Tensioner tracks (0079), carousel/drum spooling (0080), the cable
into the sea (0081) and the quadrant operations (0082) build on this task, so its pieces must be reusable.

## Background (read)

- **0075** sections A (the cable and its speed), F (one speed drives it all) and the summary (points 1–3): the cable is a
  **virtual slide joint** (value = metres paid out; `joints.create(..., allow_empty=True)`), animated by the existing
  Motor / Joint steps; rollers and sheaves are **followers** with ratio 360/(π·D_contact) °/mm (`RATIO_UNITS[("SLIDE",
  "ROTATE")]`); the rope marks move by **simple-expression drivers** on the same joint (scripts off, queue, any fps);
  shapes that change per frame (a sheave on a part that moves) are **baked at Build** and picked per frame by Geometry
  Nodes – live only while posing. The groove is read from the mesh's radial profile (groove bottom + rope radius, 0.1 mm
  in 0075's test; no cache change).
- **0058** (done, 0.2.78) built exactly that mechanism for hoses: one `FR flex shapes` mesh, a `FR flex` modifier that
  replaces a part's CAD geometry by the app-made tube, live handler, `flex.bake` at the end of Build, model update by
  part IDs, clash HOOKS. Read its Design section and `blender/flex.py`; **reuse, do not copy** (a shared helper module is
  fine if both need it). Its report's "Ideas for later": "a rope is a polyline with a tube like a hose".
- **Owner's answers (0075 end):** cable Ø 50–500 mm; speed in **m/min**, lay speed about **10 m/min**; real grooves in his
  sheaves; looks: **steel wire rope** = the typical winch-wire look; **power cable** = **black with yellow angled stripes**;
  **the texture must visibly move along the path**.
- **Demo (0077, 0084, 0091, 0095, 0097):** `demo.py` has the slide joint **"Cable travel"** (m paid out towards the sea)
  that every cable-turned roller already follows (joint sheet `"by": "cable"`, `deg_per_mm` from the contact radius); the
  cable is one static CAD solid `CABLE` along the main route (`demo_model/layout.py`, `route_solid`), diameter, MBR and
  bend radius in the route sheet (`layout.py` "cable"). The demo test leaves the static cable out of its clash check
  (0097: drop that once the cable rests on its rollers). The A&R and tipping wires (0095) are demo-only drivers and
  constraints – not an app function.
- The owner draws cables in his Inventor models too (a swept solid along the route): **reading a CAD cable** is the
  main way in for him; clicking contacts one by one is the fallback.
- Repository public: invented models only; never the Fresing 400 or the employer's work (CLAUDE.md section 6).

## Scope

1. **Cable item** (4 Motion > Cables and paths > **Add cable**): name, diameter (read from the CAD cable or the first
   groove, can be typed), look (Power cable / Steel wire rope / Plain), stripe or lay pitch, MBR (minimum bend radius,
   warn when a path bends tighter). Makes (or takes – the demo's "Cable travel") its virtual slide joint. A Motor step on
   a cable joint shows and takes the speed in **m/min**.
2. **Path from a CAD cable** (**From CAD cable**: pick the solid): centreline with 0058's `flex_fit`, then find the round
   parts it touches (rollers, sheaves, guide wheels, V-cradle pairs, chutes as fixed bends) and fit the path to them:
   straight runs between tangent points, arcs on each wheel on the right side (the side the cable lies on), the groove
   radius from the mesh. The list under the panel shows each contact (name, Ø at the rope centre, wrap angle, side) and
   lets the owner remove, add (click a part – the hover highlight of 0088), flip the side. A cable start and end: a part
   (fixed point) or "free end" (straight on for a set length – the sea's catenary is 0081, the coil 0080).
3. **Everything it touches turns:** each contact without a joint gets an app-made rotate joint on its axis (tagged, like
   0064's) following the cable at 360/(π·D_contact); a contact with an existing joint gets the coupling (the demo's
   followers stay as they are when their ratio is already right – check, report differences).
4. **The cable drawn on the path:** the CAD cable part's geometry replaced by the app-made tube (0058's way: visibility,
   paint schemes, fades, hide-with-subassembly keep working; item off → the CAD shape). Paths whose contacts all stay put
   are drawn once (no per-frame cost); contacts that move against each other (a sheave on the tilting quadrant handler, a
   luffing A-frame) → solved per frame at Build into the shapes mesh, live while posing.
5. **Looks that move** (`cable_looks.py`): power cable black, yellow stripes at an angle (pitch and angle settable), steel
   wire rope (strands with their lay, metallic); the pattern runs along the cable by the paid-out length through a
   simple-expression driver (UV along the length in metres) – exact at any fps, in Cycles and EEVEE, scripts off, queue.
6. **Clash:** a cable resting on its contacts gives no rows against them (HOOKS, as 0058).
7. **Demo stage `cable`** (after `joints`): the demo's `CABLE` becomes a cable path over its rollers and chute, power-cable
   look, on "Cable travel"; the roller-highways shot (4) shows it moving at 10 m/min with the rollers turning; the static
   cable's clash leave-out dropped where the check is clean. Optional if cheap: the A&R and tipping wires (0095) become
   app cable paths with the steel-wire look (else an open point for 0082).
8. Tour stop "Cable over sheaves" (new test model `tools/make_test_paths.py` → `test_paths.step`: a drum, an A-frame with a
   luff joint and 2 sheaves, a V-roller cradle, a chute, a CAD cable swept along them; invented), PC-check line
   `motion.paths`, guide chapter "Cables and paths" with pictures, model update keeps paths, old projects open.

## Accuracy and speed (tests)

- Cable centre on the groove's rope circle within 0.5 mm; no kinks: direction change at every tangent point < 0.1°.
- Every turned contact's surface speed = cable speed within 0.1 % (over a 100 m Motor step); texture offset = paid-out
  length within 1 mm at frame 1,000.
- Bend tighter than MBR → a warning naming the contact; impossible paths (contacts in a line that cannot be wrapped,
  a contact behind another) → a plain refusal, never a broken shape.
- Cost per frame on the demo vessel (1,250 parts) with the cable on: static path ≤ +1 ms; with moving contacts the
  0058 budget (≤ +5 ms). Build time of the demo with the stage: say before/after (0.2.71: 90 s).

## Split with subagents (the worker fixes the interfaces first, writes them under "Design" here, then spawns ≤ 3)

Suggested: **A** `core/paths.py` + tests (tangent runs, wraps, chute arcs, contacts from a centreline, groove profile);
**B** `blender/paths.py` + `cable_looks.py` (items, joints/couplings, the tube via 0058's mechanism, drivers, bake,
model update); **C** test model + **independent tests written from this brief** (did not write A/B); later **D** panel +
operators + real-app test, **F** guide and pictures (Sonnet). The worker owns the shared files, the demo stage, the tour,
the PC check, version, CHANGELOG, `TASKS.md`.

## Done when

- [ ] Scope 1–8 work in the real app (screenshot of the panel checked), every button with a tooltip.
- [ ] The tests above pass; independent tests and a written review (C) in the report.
- [ ] Demo: Help > Make demo project shows the moving cable in shot 4 (and the chute), 0 clash rows in shot 7, time
      measured; a Cycles still of the stripes on the rollers in `tasks/img/` (invented model only).
- [ ] Guide chapter, tour stop, PC-check line; GitHub green; report filled in; merge to main and release.

## Not in this task

Tensioner tracks and pads (0079), carousel/drum spooling incl. spiral groove and Lebus (0080), the catenary into the sea,
water clarity, CPS (0081), quadrant operations (0082), cable stiffness / dynamics, fleet angle on the drum (0080), motion
blur of moving shapes (study #6), the web 3D export of cables (0099 leaves app-made objects out).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
