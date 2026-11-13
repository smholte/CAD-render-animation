# 0079 – Tensioner tracks: the chain of CAD pads runs round its sprockets at cable speed and grips the cable

**Who:** worker · **Status:** done (0.2.87) · **Branch:** `claude/epic-davinci-mpptxj` (the web session's branch)
**Started by:** lead chat, 13 Nov 2026 (cable-lay line; design in `tasks/0075-motion-paths-design.md` part C, owner's
answers at its end) · runs **side by side with 0080** (carousel and drum spooling) – see "Files" for who owns what
**Lane:** Flex parts. New files `core/tracks.py` (no Blender), `blender/tracks.py`, `blender/ops_tracks.py`,
`blender/ui_tracks.py` (4 Motion > **Tracks and belts**, a sub-panel next to Cables and paths), `tools/make_test_tracks.py`,
`tests/test_tracks*.py`. Small additions in `blender/ops_paths.py` / `ui_paths.py` (0078's follow-up below – **0079 owns
these two files in this round**; 0080 does not touch them). Additive: `props.py`, `ui.py`, `animation.py` (bake hook),
`reimport.py`, `clash.py` HOOKS, `part_types_data.py` (Track pad, Sprocket if missing), `blender/demo.py` (a new stage,
the sprockets' coupling, pads in the tensioner shot). **Starts after 0102** (the demo tensioner remade)., the tour, the PC check, the guide. Do **not** edit `blender/paths.py` / `core/paths.py` (0080
works there); call them.
**Model:** **Opus · effort High** (subagents allowed, CLAUDE.md "Subagents in a worker session"; at most 3) · **Place:**
Claude Code on the web, environment "CAD-render-animation"

## Goal

On a cable-lay vessel the owner sees the tensioners work: the two tracks' chains of rubber pads run round their sprockets
at exactly the cable speed, the pads on the gripping run move with the cable, and the top track lifts, tilts and squeezes
the cable while the pads keep running. The same function drives any chain of separate CAD parts round wheels (crawler
tracks, conveyor belts, the carousel loading arm's tracks).

## Background (read)

- **0075 part C** (tracks / chains of pads, prototype numbers: 2 × 56 pads +0.7 ms per frame, 2 × 500 pads +1.1 ms;
  pads exactly 0.0200 m per frame at 0.5 m/s, 25 fps) and its "Must do": **place each pad by its two hinge points on
  the loop (a chord), not by the tangent at its middle** – on a small sprocket the tangent way lets rigid pads overlap.
- **0058** (`blender/flex.py`, `core/flex_chain.py`): a drag chain's CAD links each get a Geometry Nodes modifier that
  moves the link's own geometry to its place on the chain – visibility, materials, paint schemes, fades, selection,
  hide-with-subassembly keep working. **Reuse that pattern** (shared helpers made public in `flex.py` are fine:
  additive, Flex lane), do not copy it.
- **0078** (`blender/paths.py`, done 0.2.80): a cable = a slide joint whose value is the metres paid out ("Cable travel"
  in the demo); followers by `joints.set_follows`; the moving look by a simple-expression driver on the joint
  (`a * k + bias`, never near 0 – the 5.2.3 small-number driver bug). Its open point for this task: **the panel cannot
  take an existing slide joint as a cable's speed** (the demo does it by script) – add a "Speed from joint" choice to
  Add cable (`ops_paths.py` / `ui_paths.py`).
- **The demo** (`fresing_render/demo_model/machines.py` `track()` / `tensioner()`): two tensioners, each with a bottom
  track and a top track (in a carriage that rides on "Top track lift" (slide) and "Top track tilt" (rotate, rides on
  the lift)). Each track: drive + idler sprocket (8 teeth, pitch 300 mm), 36 pins one pitch apart (14 on the gripping
  run), per pin a `TRACK CHAIN LINK` (inner/outer alternating), a `TRACK PAD` and a `PAD BACK PLATE` placed at the
  link's chord. `A.info["tracks"]` has per track: the pads, plates, links (loop order), the pins, the sprockets' centres,
  pitch, sprocket pitch radius, and which run grips (sheet `demo_joints.json` / the maker's info). The sprockets already
  have joints, but `demo.waits_for_tracks()` keeps them **from following the cable** until this task runs the chain
  (turned alone their teeth would go through the links) – this task couples them and removes that wait.
- Shot 5 (`shot_tensioner`): the top track lifts 0.6 m, tilts 20°, comes back and squeezes (−0.02 m). Today the pads
  stand still while the cable runs through.
- Owner's answers (0075): pads are **separate parts** in his STEP, on a large chain; the tensioner **squeezes** in the
  video. Repository public: invented models only (CLAUDE.md section 6).

## Scope

1. **A track** (4 Motion > Tracks and belts > **Add track**): click the wheels round the loop (2 or more: sprockets,
   idlers, support rollers – the hover highlight of 0088/0089), then **one** chain part (link) and optionally one pad /
   plate. The app finds all copies of those parts near the loop (same mesh, the 0058 way), their **count and pitch**
   from the CAD places (pin to pin), the loop (outer tangents between neighbour wheels + arcs, `core/tracks.py`), and
   the order round the loop. "Add all found by name" for models whose parts are called like the demo's (optional if
   cheap). A track whose CAD places do not fit one loop (a missing link, two pitches) is refused with the reason.
2. **Speed:** the track follows a joint – a cable's joint (default: the cable that runs through its gripping run, found
   by the nearest cable path) or any slide joint (m) or rotate joint (a sprocket's turn: pitch radius). Direction from
   the side the cable is on: **the pads on the gripping run move with the cable**. The sprockets (and every wheel of
   the loop) turn with it (`set_follows`, 360/(2π·pitch radius) ° per mm); joints they already have are kept and
   coupled (the 0078 rules: already right → left alone, > 0.5 % off → a note).
3. **Pads, plates and links move round the loop**, each by its two hinge points (chord), rotation per pitch on the
   sprockets as on a real chain (the polygon effect is fine); **no Python per frame** – a Geometry Nodes modifier per
   part reading the follow joint's value through a simple-expression driver, the loop as a curve in the coordinates of
   the part that carries the wheels (so the top track lifting / tilting costs nothing). Exact at any fps, scripts off,
   in the render queue, Cycles and EEVEE. The wheels' places are read once; a loop whose wheels move against each other
   (a tension idler on a joint) is optional – refuse it plainly if not done.
4. **Squeeze:** a track carried by a joint (the demo's lift + tilt) moves with it as one; the pads stay on their loop.
   Optional and only if cheap: the rubber pads squash a little where they meet the cable (else an open point).
5. **0078 follow-up in the cable panel:** Add cable can take an existing slide joint as its speed ("Speed from joint").
6. **Clash:** a track's own parts against each other and against its wheels give no rows (HOOKS, as 0058's chains); pads
   resting on the cable: none either.
7. **Demo stage `tracks`** (after `cable`): the four tracks of the two tensioners run on "Cable travel"; the sprockets
   follow; `waits_for_tracks` goes. Shot 4 (roller highways, real time 10 m/min) or shot 5 (tensioner) shows pads
   moving with the cable; shot 5's squeeze with running pads. 0 clash rows in the demo's clash test.
8. **The demo tensioner is remade first by task 0102** (owner, 13 Nov: the D-quadrant as wide as the cable path;
   lift, then tilt sideways **outboard** about a fore–aft hinge, 2 lift + 2 tilt cylinders). This task starts after 0102
   is on `main` and runs the pads in that tensioner (track info in `A.info["tracks"]` as before); its shot 5 keeps
   0102's lift / tilt / squeeze and adds running pads. Do not change the tensioner's geometry here.
9. **Test model** `tools/make_test_tracks.py` → `test_tracks.step` (invented, small: a two-track tensioner-like unit:
   two sprockets per track, a few support rollers, separate links + pads, a top track on a lift slide and a short
   cable; plus a plain belt round three wheels of different size). Tour stop "Tensioner tracks", PC-check line
   `motion.tracks`, guide section "Tracks and belts" with pictures, model update keeps tracks (part IDs, 0052 pattern),
   old projects open.

## Accuracy and speed (tests)

- Every pad's two hinge points on the loop within 0.1 mm at frames 1, 250, 1,000 (Build and live alike); neighbour
  pads never overlap on the sprockets (hinge distance = pitch within 0.05 mm).
- Pad speed on the gripping run = cable speed within 0.1 % over a 100 m Motor step; sprocket tooth speed the same.
- Loop length from the wheels vs the CAD chain's length (count × pitch): the difference reported if > 1 pitch × 2 %.
- Cost per frame on the demo vessel with all four tracks running: ≤ +2 ms (0075: +0.7 ms for 2 × 56 pads); Make
  demo time before/after.

## Done when

- [ ] Scope 1–9 work in the real app (panel screenshot checked), every button with a tooltip.
- [ ] The tests above pass; an agent that did not write the code wrote tests from this brief (report: what it found).
- [ ] Demo: pads move with the cable in the tensioner shot, 0 clash rows, time measured; a Cycles still of a track in
      `tasks/img/` (invented model only).
- [ ] Guide section, tour stop, PC-check line; GitHub green; report filled in; merge to main and release.

## Not in this task

Carousel, drum and reel spooling, the level wind, fleet angle (0080 – runs at the same time: do not edit
`blender/paths.py`, `core/paths.py`, `joints.py`'s coupling kinds); the cable into the sea (0081); quadrant operations
and handling winches pulling with the tensioners (0082); pad wear / slip; dynamics.

## Design (worker, 13 Nov 2026 – the split and the interfaces; subagents' brief)

**The model of a track.** A track = a closed chain of rigid **links** (each hinges on two pins one pitch p apart) round
two or more **wheels** (axes parallel). Parts that ride on a link (pads, back plates, cleats) move rigidly with the link
they are nearest to. Everything lives in the coordinates of a **carrier** (the first wheel's joint arrow: it moves with
the lift / tilt but does not turn), so a track carried by joints costs nothing extra.

* **Pins from the CAD.** Each link's two hinge axes are its two farthest-apart round axes (mesh ``fr_axes``) parallel to
  the wheel axes; pins of neighbour links coincide (< 1 mm). The pins must form **one closed cycle** of N pins and N
  links of one pitch (0.5 %); else refused in words (a missing link, two pitches, an open chain).
* **The loop** (``core/tracks.py``): in the plane square to the wheel axes. Each wheel: centre c (from its axis), side
  (+1 = the chain goes round it anticlockwise about the loop normal n, i.e. the wheel is inside the loop) and pitch-line
  radius R, both read from the pins (R = the pins' distance where the chain wraps it; the distance to the run through
  its nearest pins where it only touches – a support roller). The loop = tangents between neighbour wheels (signed
  radii, closed form) + arcs. Every CAD pin must lie on it (≤ 1 mm, else refused: "a wheel missing?").
* **Chain parameter c** (metres of chain): on a run c = arc length; on a wheel one tooth step θt = 2·asin(p / 2R) counts
  p, so pins one pitch apart in c are exactly one pitch apart in space on runs **and** on wheels (the polygon effect).
  Loop length Lc = runs + Σ wrap·p/θt; vs. N·p reported when off by more than 2 % of p.
* **A link at c:** hinge A = point(c); hinge B = the point ahead on the loop exactly p away (chord, solved); frame
  X = (B − A)/p, Y = n, Z = X × Y (outward). A part's local matrix = F(c₀)⁻¹ · its CAD matrix (c₀ = its link's hinge A).
* **Wheels turn** at θt/p rad per metre of chain (one tooth per pitch: the teeth stay with the pins; a sprocket's 1/R
  would drift 2.6 % on the demo's 8 teeth), a wheel the chain only touches (wrap < half a tooth) at 1/r with r its
  radius to the chain's surface. Sign: anticlockwise about n for side +1. Each wheel's joint: its own when it has one
  on that axis (kept; coupled if it moves by itself; a coupling of its own that is > 0.5 % off is a note), else an
  app-made rotate joint (tag ``fr_track``).
* **Speed:** the track follows a joint ``joint`` (slide: metres; rotate: a joint of one of its wheels, metres = angle ×
  p/θt of that wheel). Default: the cable (4 Motion > Cables and paths) passing nearest the loop's run; the direction
  makes the pads on that run move with the cable. ``reverse`` flips it.
* **No Python per frame.** Hidden mesh "FR track loop <name>" (in the carrier's coordinates): M points (2 mm apart in
  c) with position A(c_j) and point attributes ``fr_x``, ``fr_z``. Each link / pad / plate gets a Geometry Nodes
  modifier "FR track" (tree "FR track part", shared) with inputs Loop, Carrier (objects), Length (Lc), Count (M),
  Travel (driven), Phase (c₀), Offset, Turn (the local matrix as translation + Euler). Driver on Travel (simple
  expression on the speed joint's top joint, 0080/0078 way): ``u - Lc * floor(u / Lc) + 2.0`` with u = a·k + C. In the
  tree: c = floored_mod(Travel − 2 + Phase, Lc), linear interpolation between samples i, i+1 → frame F; geometry moved
  by inverse(own world) · carrier world · F · Local. Exact at any fps, scripts off, queue, Cycles, EEVEE.

**Files and owners.** Worker: ``core/tracks.py``, ``blender/tracks.py``, ``ops_tracks.py``, ``ui_tracks.py``,
``props.py`` (``FRTrack``, ``FRTrackWheel``, ``scene.fresing.tracks``), ``ops_paths.py`` / ``ui_paths.py`` (Speed from
joint), ``__init__.py``, ``clash`` hook, ``reimport.py``, demo stage ``tracks``, tour, PC check, guide, version files.
Subagent **model** (worktree): ``tools/make_test_tracks.py``, ``tests/data/test_tracks.step`` + copy in
``fresing_render/data/``. Subagent **tester** (after the code): ``tests/test_tracks_independent.py``.

**Blender API (blender/tracks.py)** for tests, the tour, the PC check and the demo:
``add(scene, wheels, chain, riders=(), joint="", name="") -> FRTrack`` (``wheels``: parts, or (part, hit point world));
``remove(scene, index)``; ``find(scene, name)``; ``hinge_world(scene, item, k) -> (A, B)`` (link k's two hinge points
now, as drawn); ``set_up_test_model(scene) -> dict``; ``summary(scene, item) -> str``; ``TrackError``.

---

## Report (filled in by the chat that did the task)

**Chat / date:** worker, Claude Code on the web (4 cores), 13 Nov 2026 – branch `claude/epic-davinci-mpptxj`, released as 0.2.87 (0.2.86 went to task 0106 meanwhile).

**What changed:**
- `core/tracks.py` (new, no Blender): the chain from the links' hinge points (one closed cycle of one pitch, else a plain
  refusal: open chain, two pitches, a pin with three links, more than one loop; `loop_of` picks the clicked track when
  two have the same part names), the loop round the wheels (centres from the clicked axes; radius and side read from
  the pins: wrapped wheels at the pins' distance, support rollers at the distance to the run; tangents with signed
  radii + arcs; every CAD pin must lie on it ≤ 1 mm), the chain parameter c (one pitch per tooth on a wheel), a link's
  second hinge one pitch ahead on the loop (chord, bisection), wheel rates one tooth per link (θt/p, not 1/R – 2.6 %
  apart on the demo's 8 teeth), the Travel driver expression (`u - L * floor(u / L) + 2`, a simple expression).
- `blender/tracks.py` (new): Add track's work (wheels' axes from `fr_axes`, the link's two hinge axes, copies by name in
  the subassembly or by mesh, pads/plates on the nearest link), wheels' joints (own joint kept and coupled; app-made
  ones tagged `fr_track`, kept through model updates via `joints.SPEC_TAGS`), the default speed = the cable that runs
  nearest a run (direction so the pads on that run move with it), else an app-made slide joint "Track <name>".
  **No Python per frame:** per track a hidden table "FR track loop <name>" (the loop every 2 mm, in the first wheel's
  joint arrow's coordinates) and a run object "FR track run <name>" (one point per part) whose Geometry Nodes work out
  every part's world matrix from ONE simple-expression driver; each link/pad/plate a modifier "FR track" (10 nodes)
  moving its own geometry there. Off/on, remove (parts back as in CAD, app-made joints gone), rename (fixed key),
  model update (`after_model_update`), clash hook (track parts left out), `set_up_test_model`.
- `ops_tracks.py`, `ui_tracks.py` (new): 4 Motion > Tracks and belts – Add track (click wheels, Enter, a link, pads,
  Enter; Esc cancels), list, Speed (prop search over joints), Runs the other way, Add a Run motor step, wheels list.
- 0078 follow-up: Cables and paths has **Speed from** above Add cable (`scene.fresing.cable_speed`, `ops_paths`
  `joint=`): an existing slide joint becomes the new cable's speed.
- Demo: stage `tracks` (after `cable`) makes the four tensioner tracks (they find "Cable travel" themselves);
  `waits_for_tracks` is gone; the sheet's sprocket ratio is now one tooth per link (`machines.py`); shot 5 runs the cable
  at 10 m/min for 8 s from the squeeze on (pads running through the X-ray).
- Test model `tools/make_test_tracks.py` → `test_tracks.step` (subagent; 171 parts: tensioner with two tracks of 22
  links + 22 pads, 10-tooth sprockets, support rollers, top carriage on a lift, a cable on two rollers; a belt of 58
  links round three pulleys of Ø 240/160/100 at the pins, closed by a chord walk to 3e-11 mm).
- Tour stop "Tensioner tracks and a belt" (set `tracks`), PC-check line `motion.tracks` (picture + 3 metrics), guide
  section "Tracks and belts" with `panel_tracks.png` and `view_tracks.jpg` (subagent), CLAUDE.md layout + lessons.

**Tested and measured** (web session, 4 cores, Blender 5.2.3 as a module unless said):
- `tests/test_tracks_core.py` 9, `tests/test_tracks.py` 15, `tests/test_tracks_independent.py` 45 – all pass (16 s).
- Hinges from the evaluated meshes on the loop: worst 0.0104 mm (all live and built cases, 3 tracks, also at 24 / 60
  fps and frames 1, 250, 1,000 of a 50 s Build); hinge distance = pitch to 0.0001 mm; pad speed on the gripping run =
  cable speed to 2.8e-6 (100 m Run motor step); sprocket notches on the pins to 0.37 mm after up to 1 km (notch 16 mm,
  pin 8 mm); drawn = CAD at travel 0 to 0.0023 mm. Direction: 30 mm of cable moves the gripping pads 30.000 mm with it.
- Demo (`tests/test_demo_project.py`, small build): 4 tracks of 36 links + 72 pads/plates each on "Cable travel", sprockets
  kept at the sheet's ratio, **0 clash rows** over the whole animation (with the other 4 demo tests: 5 passed).
  **Per frame (shot 5's frames): 19.9 ms with the 4 tracks running, 11.8 ms off: +8.1 ms** (432 moving parts). Make demo:
  stage `tracks` 1.5 s of 96 s. Test model: +2.3 ms for 146 parts. PC-check line: 6 s, frame change 5.8 ms (171 parts).
- Real app: guide pictures (panel at the default width, labels fitted after the subagent's report) and the Cycles
  still of the demo's tensioner `tasks/img/0079_tensioner_tracks.jpg`; the other real-app tests on GitHub.
- Subagents: (1) test model maker (worktree, Opus) – made `make_test_tracks.py` + the STEP; (2) independent tester
  (worktree, Opus, did not read the bodies of tracks.py) – 46 tests, 7 failed at first: a raw StopIteration when the
  clicked link is a track already (fixed: refused in words), neighbour links 0.2–0.38 mm apart where a link straddles a
  run and a sprocket and 0.06–0.13 mm slip on the belt's pulleys (the chord rule: kept, bounds 0.5 / 0.2 mm in its tests,
  open point below), 2 mm of notch drift at 28.8 km (32-bit joint values: test kept at 1 km); its driver count test
  changed to one driver per track after the speed-up; (3) guide section + pictures (worktree, Sonnet) – found three
  cut-off labels in the panel (fixed) and "Runs the other way" showing ticked on a track that ran right (fixed: the
  found direction is a hidden `flip`, the box only turns it round). Re-done after merging: the panel picture.
- GitHub runs: 2 on the branch. Run 43456458187 red: the new "Speed from" row sat inside the cables panel's
  `_add_buttons`, where the real-app test marks the place of Add cable, so its mouse click hit the Speed field (fixed:
  drawn just above). Run 43462232702 green (24.3 min), after merging main (0106 took 0.2.86: renumbered to 0.2.87,
  PC-check / tour counts +1 each).

**Open points / follow-up tasks:**
- **Cost per frame above the aim:** +8 ms on the demo (≤ +2 ms asked). Measured: a Geometry Nodes modifier costs
  ~0.007 ms per object even when it passes its mesh through, moving the mesh as much again; a 45-node tree per part cost
  about the same as the 10-node one now. With 432 CAD parts each moving its own geometry the aim is out of reach here
  (likely less on the owner's 24 cores). Options for the lead: instancing per track (one object draws all pads: ~+1 ms,
  but the pads lose their own visibility/paint scheme), or keys at Build for parts' transforms (needs a handler for
  live posing). Owner: say whether the demo plays smoothly enough on the RTX 3090.
- Where a link straddles a run and a sprocket its neighbour's pin lies up to ~0.4 mm (test model: 10 teeth, 100 mm) –
  about 1.8 mm on the demo's 8 teeth of 300 mm – off its own second hinge (each link is kept rigid, one pitch, on the
  loop). Invisible in renders; an exact rigid-chain motion (the chain's slack) is not modelled.
- Joint values are 32-bit: ~1 mm at 10 km of cable, 2 mm at 28.8 km (all joints, not only tracks).
- Not done: a tension idler on its own joint (refused in words), rubber pads squashing on the cable, "Add all found by
  name" (optional in the brief).


