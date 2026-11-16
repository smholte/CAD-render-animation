# 0174 – Spools full of real cable: every layer drawn as one continuous cable on carousels and drums, wound fully in and out; every winch of the demo with its steel wire rope

**Who:** worker (web session) · **Status:** running · **Branch:** `task/0174-full-spools` (a web session may name its own)
**Started by:** lead chat, 17 Nov 2026 (owner's wish, 16 Nov 23:59, with a screenshot of the demo's carousel) ·
**Model:** Opus · effort High · **Place:** Claude Code on the web, environment "CAD-render-animation". Subagents
allowed (CLAUDE.md section 2).
**Area:** Flex lane, spool part only: `core/spool.py`, `blender/spool.py`, `ui_spool.py`, `ops_spool.py`, their tests,
`tools/make_test_spool.py` + its model copies; the demo's `spool` stage and the set-up of the winches' wires in
`blender/demo.py` (+ `demo_model/` where a winch has no rope in its CAD); the spool ropes on the web page
(`blender/web3d.py` / the page script: the spool part only); `tools/measure_cables.py`; the tour stop `spool`, the
PC-check line `motion.spool`, the guide section `#drums`.
**Do not edit (0172 runs beside this task in the Flex lane):** `core/paths.py`, `core/catenary.py`, `blender/paths*.py`,
`ui_paths.py`, the demo's sea / quadrant stages and `set_down_depth`. If this task needs a change there, write it in the
report as a follow-up instead. In `demo.py` change only the `spool` stage, the winch set-up and their expected numbers;
whoever of 0172 / 0174 merges second updates its branch to `main` and the demo tests' expected numbers (CLAUDE.md
section 2). Not the Machining lane (0167) or the CI files (0170/0171).

## Goal

The owner (screenshot of the demo's carousel, 0.2.118+): the carousel shows its top layer as cable and under it a black
cylinder. He wants **cable all the way**: every layer drawn as cable, **one continuous cable** from the core to the
end, which can be **wound fully out and fully in** – the layers come off and go on one by one until the core is empty
(or full). The same for **winch drums** (every layer, Lebus crossovers on every layer, the climbs at the flanges). And
**every winch of the demo** has its real steel wire rope on its drum.

## Background

- `blender/spool.py` (0080): `DRAWN = {"DRUM": 2, "CAROUSEL": 1}` layers are drawn as rope (object "FR spool <name>",
  its Geometry Nodes trim the wound path by driven lengths); the full layers below are **one solid** ("FR spool solid
  <name>", a sleeve on a drum, a ring on a carousel) scaled by a step table (`_solid_mesh`, `S.stack`,
  `S.stack_breaks`). That solid is the black cylinder the owner sees.
- 0159 filled the demo's carousel to the rim: 23 + 1 layers, 43.5 km of Ø 200 mm served cable; the top layer must be an
  even one (CLAUDE.md section 8, the carousel's alternating layers). 0158/0164: the served-cable look with spiral
  bands on spools too; a coil follows a look change at once.
- 0142: the web page draws spool ropes as the wound path + a cut in its shader (the full layers as the solid).
- Spooled on the demo today: the carousel, handling winch 1, the A&R winch. **Not spooled (wire only as CAD or as a
  cable without a rope on its drum):** at least handling winch 2, the two tipping winches (their wires are app cables
  kept tight since 0095/0125; the drum only follows the speed), the deck crane's hoist (0153). The worker lists every
  winch and drum of the demo vessel (and the park's cranes/davits, 0166) and says which got what.
- Size: 43.5 km of cable as a tube is far more geometry than anything else in the demo. Most of it is hidden under the
  layers above, but whatever is paid out shows the layer below, so all of it must be there when needed. How to draw it
  cheaply (one static wound mesh trimmed by the paid-out length, fewer sides on turns that are covered, instancing per
  turn, a top-layer window at full detail …) is the worker's design – write it under "Design" before building.

## What to do

1. **Every layer as cable** on carousels and drums, the solid gone: one continuous centre line from the anchor at the
   core (carousel) / flange (drum) through every layer, crossovers and climbs to the leave point, drawn as the cable's
   own look (served cable, wire rope, power cable) with its bands running on without a jump at layer changes.
   Neighbouring turns touch and do not overlap (each turn in the groove of the turns below, as 0080's maths places them).
2. **Wind fully in and out:** the cable joint's whole range – from all paid out (core / drum empty, the cable's anchor
   end visible) to full – gives the right picture at every value, live and after Build; the followers (loading arm,
   level wind, guide swivel) follow over the whole range. A test winds the test spool from empty to full and back.
3. **Every winch of the demo with its steel wire rope:** each winch drum on the demo vessel gets its wire as a spooled
   cable with the steel wire rope look (0078's "Wire ropes"), on its drum in layers, leading to its sheave / fairlead
   as the CAD shows; a winch with no rope in its CAD gets an invented one in `demo_model/` (each part one solid, CLAUDE.md
   section 8). Anchor chains (windlasses) are not wire: leave them, say so.
4. **Cost, measured before/after on the demo** (machine named; `tools/measure_cables.py`, Make demo): Build, playback
   per frame, live posing of the cable joint, memory, saved project size. Aims: playback no more than ~3 ms a frame
   above today, Make demo no more than ~15 % longer; if an aim cannot be met, measure the best design found and say
   what it costs. A Heavy PC-check line if the cost depends on the coil's size (CLAUDE.md section 6).
5. **Web page:** the full coil on the page if it adds no more than ~5 MB to the demo's page; else the page keeps today's
   top layer + solid, measured and stated in the report (Web 3D follow-up).

## Rules

- New behaviour gets a test (the continuity of the centre line through every layer change, no overlap between
  neighbouring turns, the full range in and out, a drum with Lebus crossovers on several layers, an even/odd layer count
  on a carousel). Nothing loosened; every tour set and the demo stay 0 clashes.
- An **independent tester** (a subagent that did not write it) tries to break it: a nearly empty and a full spool, a
  joint value past either end, a spool with one layer, a carousel whose axis points down (`FRSpool.zsign`), a model
  update, an old project (0.2.118-style, solid) opening and getting the new drawing.
- The tour stop `spool` and the PC-check line `motion.spool` check the new drawing (a full spool emptied and filled);
  the guide section `#drums` gets the new behaviour and a new picture of the test spool; tooltips if a setting changes.
  CHANGELOG + version last (section 7).
- The owner's check on his PC goes in the report as numbered steps (Help > Make demo project, the carousel camera,
  scrub the cable payout fully out and in; the winches' close-ups).

## Done when

- [ ] 1–3 done on carousels and drums, the solid gone, one continuous cable, full range in and out
- [ ] Every demo winch listed with what it got; wire rope look on each
- [ ] Before/after table (Build, playback ms, posing, memory, project size, page size); small before/after picture of
      the carousel in `tasks/img/0174_*` (the demo's invented vessel only)
- [ ] Tests added/updated; GitHub run green; merged; version; report filled in

## Not in this task

The cable paths and the sea (0172 runs: `paths*.py`, catenary, shot 11); 0152's demo realism (0173, after 0172 and this
task – both edit `demo.py`); anchor chains; cables or hoses swaying in wind.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
