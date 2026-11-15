# 0126 – Demo: the CPS run from the rack to the cable end

**Who:** worker · **Status:** done (0.2.108) · **Branch:** `ccr-8f1ac832-0ayr4f` (the session's branch)
**Started by:** lead chat, 15 Nov 2026 (owner: "all 5 suggested tasks") · **Model:** Opus · effort High
**Area (Demo models lane):** `fresing_render/demo_model/` (rack, ramp, curved slide, the CPS set's parts if they need
splitting), `blender/demo.py` (a new stage before the quadrant stages; shots renumbered only if needed), app code in the
Flex parts lane (`paths*.py`, `core/paths.py`) only where the CPS must ride a path the app cannot yet give, their
tests. **Do not edit:** `sequence.py`, `ui_motion.py` beyond the cable boxes (task 0129); `tools/site_projects/`,
`site/` (task 0128).

## Goal

The demo shows the owner's CPS steps 1–5: one CPS set slides from the rack down the orange ramp and the curved slide
onto the cable highway, travels along the route round the quadrant and down one lane, stops, runs back the other way
to its place in front of the cable, the cable end is connected to its rear end, and then the CPS goes on nose first
into 0082's quadrant sequence.

## Background

- **Owner's description:** `tasks/0083-cable-lay-reference-study.md`, "CPS store" (about line 292) and "CPS on the
  cable end (owner's CPS steps 1–5)" (about line 313), plus his route steps 1–4 just above it. A CPS set is ~15–25 m
  long, ~2× the cable Ø; from the nose: pointed pull head, grey tube, segmented yellow, brown vertebrae, grey, yellow
  bend-restrictor segments next to the cable. These are generic words for the owner's work – the demo stays invented
  (CLAUDE.md section 6: nothing of his employer's design).
- The demo already has a CPS rack + ramp (0084) and a CPS / pull head on the cable that rides over the horn and down
  (0081: "things on the cable (CPS set) ride over the horn and down"); 0082 starts with the CPS on the cable end.
- A CPS is not a straight rigid body on a curved route: its segments must follow the path (like 0081's riders, or
  0079's links one pitch apart). Use what exists before writing a new solver.
- Read the report of 0125 first (it changes the sea stage and maybe the paths code).

## Done when

- [ ] A new demo stage (e.g. `cps`) plays steps 1–5: down the ramp, onto the highway, along the route round the
      quadrant, down one lane, stop, back, connect to the cable end, then into the existing quadrant shots.
- [ ] The CPS's segments stay on the route's middle line within 2 cm on every frame (measured), no segment through a
      roller, cradle or rail: 0 clash rows in the demo (`tests/test_demo_clash.py`).
- [ ] A shot (camera) that shows the run; captions as the other demo shots; "What it can do today" still builds.
- [ ] Make demo time and per-frame cost before/after in the report.
- [ ] If an app ability was added (something on a path that is not a cable): tooltip, guide + anchor, function-list
      entry, tour stop, PC-check line (CLAUDE.md section 6). A demo-only stage needs none of these.
- [ ] Tests; full GitHub run green; report with the owner's check (the new shot on the RTX 3090).

## Not in this task

The quadrant sequence itself (0082, 0125). The site. Glow markers, sediment.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 15 Nov 2026 (branch `ccr-8f1ac832-0ayr4f`), version **0.2.108**. No subagents.

**What changed:**
- **New stage `shot_cps` – shot 8b** (between shot 8 and shot 9, ~24 s, × 15): the lay cable is hidden (cut to camera
  "CPS rack"); the CPS set on the ramp's shelf slides **tail first** down the orange ramp and the curved slide onto side
  B's cradles, round the D at rest, down side A to 1 m before tensioner 2 (camera moves to "CPS on the D"), stops, runs
  back until its pull head is at the D's lane-B bar end. Shot 9 hides it and shows the second end with its own CPS in
  that place ("The cable end is connected to the CPS's rear end …").
  - **Why tail first:** the demo's quadrant shots carry the cable's *second* end, whose CPS has its pull head at the
    D's bar end and its bend restrictors towards the cable (0082). The owner's steps 1–5 (nose first overboard) are
    a first end's. To end in shot 9's pose, the set leaves the rack restrictors first; everything else is his steps.
- **How it moves (no new app ability):** stage `cps_path` reads a thin bar the maker draws along the CPS's middle line
  (`CPS RUN LINE`, `route.cps_run_route`) as a hidden cable "CPS run" (Stays as drawn; 9 bends, 1.2 mm off the bar),
  its speed joint = metres moved; the set rides on it as a rider (0081). So no tooltip/guide anchor/function/tour/PC
  line (a demo-only stage); the guide's demo chapter describes it.
- **The model, so a Ø 408 CPS (2 × cable Ø, its vertebrae's rings 1.02 × that) really fits its way:** pieces of at most
  0.5 m (the tube in 9, the sleeve in 3, the pull head 0.6 m) so they lie on their bends; the slide joins side B at
  the CPS's height on the V cradles – 129.0 mm over the cable's line, worked out from the rollers' profile (it rests
  3 mm over their raised ends, `deck.cps_lift`); the cradle under the slide's last bend removed (the CPS crossed it 100 mm deep;
  307 joints instead of 310, 193 rollers on the lay cable); straights of 350 mm between bends in different planes (the
  path reader could not read them back to back); the D's gutter: lip 123 mm further out, top plate 58 mm higher, the
  tipping eyes' lugs start over the CPS (floor, eyes and A&R eye where they were: moving the A&R eye shifted the whole
  stern and every lane cradle; the lip has a notch round its plate); the troughs deeper (25 mm under the CPS's rings: over the ramp's edge its way bends 10 mm
  under the trough's line); the rack's
  side guides lower (the sets on it touched them by 6 mm). For a cable whose CPS would need more than 150 mm more room
  in the D (Ø 500) the D stays as the cable needs it (`route.d_has_cps_room`).
- **0125's open point 1:** the second end's speed no longer follows Cable travel; it takes Cable travel's value just
  before shot 9 (hidden) and is **hauled in by the D's travel** during it (`demo.haul_in`).

**Tested and measured** (4-core web machine, Blender as a module, the small demo form):
- Shot 8b, every frame (601 frames, `tests/demo_cps_check.py`, new test `test_shot_8b_runs_a_cps_set_from_the_rack`):
  every piece's axis within **15.8 mm** of the CPS's middle line (the 0.6 m pull head on the D's bend); no corner of a
  piece in any of the 902 parts near the way, nor theirs in a piece (every 2nd frame) – **0.0 mm** (on the way there:
  11 mm into the rollers' raised ends before the lift was worked out from their profile, 5.8 mm into the rack's
  guides, 4.7 mm into the ramp's trough over its edge, 1.8 mm of facets resting exactly on the flanges). On the rack at the start the
  set is where CAD has it (< 1 mm).
- Demo clash check (`test_demo_clash.py`, the whole animation incl. the D's travel with the wider gutter): **0 clash
  rows** (657 s here with other tests running). Riders are left out of it by design – the check above is theirs.
- Second end piling up (whole animation, before → after): 0.30 m at the start of shot 9 growing to 36.6 m by the end
  of the D's travel and 59.8 m at most → **nothing in shot 9**; it first piles (0.18 m) while the D is lowered in
  shot 10, 18.6 m by the end of the lowering, 23.3 m at the set-down: the D coming down to the seabed lays the cable
  down under it. Tried too: "lay on" (Cable travel on by the travel, the seabed passing aft) – the same result for
  shots 10–11, but the tensioner pads, the carousel and the arch would run during shot 9.
- Make demo: 220 s → about 253 s (one run with other tests on the machine); its Build 111 s → 142 s (+600 frames).
  Frame change when playing (every 7th frame of the whole animation): 24.4 ms → 24.5 ms per frame.
- Tests: `test_demo_cable_lay.py` 58 passed; `test_paths.py -k demo_vessels`, `test_paths_core.py -k demo_cable`
  passed (193 rollers); `test_demo_project.py` (new tests for shot 8b and the haul-in; counts, stage order, length).

- GitHub: 3 full runs on the branch, all green – 43765129282 (25.7 min), then 43767623115 (25.9 min) after merging
  `main` again (task 0136 had taken 0.2.106: renumbered to 0.2.107), then a third after task 0140 took 0.2.107 (renumbered to 0.2.108): 43770223664 (32.6 min); `main` fast-forwarded to it with the task list.

**Owner's check list (RTX 3090):** Help > Make demo project, then play shot 8b (after "Into the sea"): (1) the set on
the top shelf next to the orange ramp slides down the ramp, restrictors first, and onto the rollers of side B; (2) it
goes round the D-quadrant inside its gutter and onto side A, nothing goes through it; (3) it stops before tensioner 2
and comes back until its pull head sits at the D's bar end; (4) shot 9 starts with the cable end there and the D
carrying it aft – nothing piles up behind the stern while the D travels.

**Open points / follow-up tasks:**
1. While the D is lowered (shots 10–11) the second end still lays down under it (warning "piles up … 0.18 m at frame
   2831", 23 m by the set-down). Ending it needs the app to haul in exactly what would pile up, frame by frame (keep
   tight keeps the hanging length, not the layback) or the vessel to move ahead with the seabed but not the carousel
   and tensioners – Flex parts lane.
2. In shot 9 the second end's own CPS rides on the cable's line (as 0082 made it): round the gutter it is 119 mm
   inside where the run set lies, through the guide rollers (riders are left out of the clash check). A rider "on the
   outside of its cable" (offset where it lies on rollers) would fix it – Flex parts lane.
3. The owner's steps describe a first end (nose first overboard); the demo has no first-end shots.
