# 0076 – Demo model: an invented cable-lay vessel spread (carousel, tensioners, quadrant, winches)

**Who:** worker · **Status:** open – can start (Wed 11 Nov evening) · **Branch:** `task/0076-demo-cable-lay-model`
**Started by:** lead chat, 11 Nov 2026 (owner's request: a demo of his field without his company's CAD)
**Lane:** new **Demo models** lane – new files only: `tools/make_demo_cable_lay.py` (+ helpers in `tools/demo_cable_lay/`
if it grows), `tests/test_demo_cable_lay.py`, `tasks/img/0076-*.png`. No app code (`fresing_render/`), no version, no
release.
**Model:** **Opus · effort High** (new geometry, many machines, a wrong layout is expensive for every later task) ·
**Place:** Claude Code on the web, environment "CAD-render-animation"

Runs at the same time as 0058 and 0061 (Thursday): it touches none of their files. **Merge to `main` before Thu 12 Nov
08:00**; if not ready then, stay on the branch and merge only after 0058 and 0061 are merged (one more run is fine).

## Goal

The owner cannot give his employer's CAD models to an AI, and the repository is public. So the app gets its **own,
invented** model of a complete cable-lay spread on a cable-lay vessel – realistic sizes and parts, nothing copied from
any company or vessel. It is:
- the test and demo model for all motion-paths tasks (cable along a path, tensioner tracks, carousel, cable into the sea,
  quadrant) – 0075's proposed `test_cable_lay.step` becomes this, bigger;
- the base of the **demo project** (task 0077: joints, cameras, sea, vessel, animation, Help > Make demo project), which
  the owner opens, studies and uses as an example and for videos;
- importable by the owner as a normal STEP in Fresing Render.

## What the owner works with (his answers, 11 Nov)

He designs cable-lay spreads for offshore wind (export and inter-array cables). Cable **Ø 50–500 mm**, lay speed about
**10 m/min**. Usually a **carousel** (on the vessel, and standalone storage carousels); a drum/reel only rarely for cable
lay; a **chute** or the **quadrant** at the stern depending on the client. Two **track tensioners** in a row; their
tracks are a large chain with **pads as separate parts**, and the tensioner **squeezes** the cable (top track down by
cylinders). A **quadrant** (curved frame that carries the cable end over the stern at its minimum bend radius) with a
**quadrant handling winch** and **tipping winches**. **Handling winches** that help the tensioners when extra pull is
needed. Winch drums: **spiral groove** normally, **Lebus** for one client. **CPS** (cable protection system) on the cable
end. Steel wire rope on the winches; the power cable is black with yellow angled stripes (the look comes from a later
task – this task only models solids).

## Scope

One script `tools/make_demo_cable_lay.py` writes the STEP files (AP214, with colours and part names, the way the other
`tools/make_test_*.py` do with OCP) into a folder given on the command line. All sizes from one parameter set at the top
(cable Ø default **200 mm**, range 50–500 mm; minimum bend radius MBR default **3.5 m** – scaled with the cable Ø; lay
direction to the stern). Generic English part names that the app's part-type library sorts (check `core/part_types_data.py`:
cylinders, winch drums, sheaves, rollers, motors, gearboxes, bolts in DIN/ISO notation where bolts are modelled at all –
few, not thousands).

1. **Vessel** (`demo_vessel.step`): a generic cable-lay vessel about 120 m × 27 m – a real hull shape (bow, flat
   midship, transom stern; not boxes), freeboard ~3 m, main deck, deckhouse forward, bulwarks/railings simplified,
   a **carousel well** amidships, a **stern opening** for the chute and quadrant. Lightweight (a few hundred thousand
   triangles at Normal). Waterline at z = 0 (the app's sea).
2. **Carousel** (`demo_carousel.step`, placed in the vessel's well): outer Ø ~24 m, inner core Ø ≥ 2·MBR, rim height
   ~5 m, turntable on support rollers, drive units, rim fence; **loading arm / radius controller** over it (slewing
   arm with a cable guide that moves in/out over the coil). A second, smaller **standalone storage carousel**
   (`demo_storage_carousel.step`, quay/deck version) from the same code.
3. **Cable route carousel → tensioners**: roller tracks / cable gutter with rollers (each roller a separate turning part),
   guide wheels and radius controllers at every bend (bend radius ≥ MBR), a cable straightener if it fits.
4. **Two track tensioners in a row** (`demo_tensioner.step`, placed twice): frame, top and bottom track; each track a
   **chain of links with a pad per link as separate parts** (pitch ~300 mm, about 40–60 pads per track), drive sprockets
   and idlers (turning parts), hydraulic motors/gearboxes, **squeeze cylinders** that lower the top track onto the cable,
   opening for the cable Ø range.
5. **Stern**: **overboarding chute** (curved, radius ≥ MBR, rollers), and the **quadrant** (quarter circle of radius ≥
   MBR with a cable gutter and a hang-off point, its hinge at the stern) with the **quadrant handling winch** (spiral-groove
   drum, wire over sheaves to the quadrant) and **two tipping winches** (smaller, spiral groove). An A-frame or davit only
   if the handling wire needs one.
6. **Handling winches** (`demo_handling_winch.step`, placed twice beside the tensioners): drum with **spiral groove**
   (helical groove cut in the drum, real geometry), wire spooled on it as a simplified solid, fairlead/sheaves. One drum
   variant with **Lebus-style grooving** (parallel grooves with crossover zones; as close as reasonable) as a separate part
   file `demo_drum_lebus.step`.
7. **Sheaves** everywhere with a **real groove** (a torus-shaped groove whose major radius is the rope/cable centre radius
   – 0075 reads the groove from the mesh).
8. **Cable**: the route's centreline written as `demo_cable_route.json` (points, the wheel/roller each section wraps,
   radii, tangent points) so the motion-paths tasks can lay the cable without guessing; plus a simple static **cable solid**
   along the route from the carousel to the stern (named `CABLE`) for stills before the cable tasks exist.
9. **CPS**: a cable protection system on the cable end – bend restrictor / polymer sleeve segments, centraliser and latch
   at the end, separate parts, as a sub-assembly on the cable end at the quadrant.
10. **Joint sheet** `demo_joints.json`: every joint a later set-up should make – name, type (rotate/slide), the parts that
    move, axis point + direction in model coordinates, limits, and what drives it (carousel turn, loading arm slew + in/out,
    every roller/sheave/sprocket turn, track squeeze, quadrant tip about its hinge, winch drums, chute rollers). Task 0077
    makes the joints from it by script; 0075's "Cable" joint drives the turning ones later.
11. One assembly file `demo_cable_lay.step` with everything placed (vessel + spread), and the machines also as separate
    files (so a user can import just the spread on the app's Vessel deck surroundings).

Nothing may resemble a particular company's or vessel's design or name (no "Nexus", no company names, no copied layouts):
generic, from general engineering knowledge.

## Accuracy, size and speed

- MBR respected along the whole route (test); sheave groove radius = cable/rope centre radius (test, < 0.1 mm); pads equal
  pitch, no overlaps; the quadrant radius ≥ MBR; the cable solid follows the route JSON within 1 mm.
- Size: whole assembly at **Normal** detail ≤ ~3 M placed triangles (measure with the importer: unique / placed, import time
  on the web session); note the triangle split per machine in the report.
- **File size:** if a STEP is larger than ~5 MB, do not commit it: commit only the script, and the tests / task 0077 write
  the files at run time (as `pccheck/heavy_scene.py` does). Small files may go into `tests/data/` (say which in the report).

## Done when

- [ ] `tools/make_demo_cable_lay.py <out folder>` writes all files above; every part has a name; colours set (e.g. vessel
      hull, deck grey, machines in a common offshore yellow, tracks/pads dark).
- [ ] `tests/test_demo_cable_lay.py`: the script runs, the importer reads every file (tree + meshes), part counts (pads per
      track, rollers, sheaves), groove radii, MBR on the route, route JSON ↔ cable solid, joint sheet names exist in the
      STEP, triangles under the budget.
- [ ] 3–4 small Cycles pictures (the app's importer + Open sea or Vessel deck surroundings; overview, tensioners close,
      quadrant at the stern, carousel with loading arm) in `tasks/img/0076-*.png` – invented model, may be public.
- [ ] GitHub green; merged to `main` (no version, no release).
- [ ] Report filled in; `TASKS.md`: 0076 done, 0077 "open – can start".

## Not in this task

App code, joints in a project, cameras, animation (= 0077); the moving cable, tensioner track motion, spooling, catenary,
quadrant operations (= motion-paths tasks 0078–0082); 0058 and 0061 files.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
