# 0077 – Demo project "Cable-lay vessel" (Help > Make demo project)

**Who:** worker · **Status:** done (0.2.68) · **Branch:** `claude/sweet-mendel-tecn1z`
**Started by:** lead chat, 12 Nov 2026 (plan in tasks/0075, model from 0076 + 0084, facts and shot list in 0083)
**Lane:** Demo models – new files only: the model maker moves into the extension (see "Where the model maker lives"),
new `blender/demo.py`, `blender/ops_demo.py`; additive: one Help-menu item next to the test tour (`pccheck/ops.py`
draws that menu), `blender/props.py` only if needed; a tour stop, a PC-check line, a guide chapter
**Model:** Opus · effort Medium (stuck: High) · **Place:** Claude Code on the web, environment "CAD-render-animation"

## Goal

One click in the app – **Help > Make demo project…** – writes the invented cable-lay vessel spread (0076/0084), imports
it, sets it up the way the owner would (groups and looks, joints, cylinders, sea, cameras) and saves a ready project
with a **demo video of what the app can do today**. The owner can show it to others, and every later motion-paths task
(0078–0082: cable, tensioner tracks, spooling, catenary, quadrant) adds its part to this same project and video.

## Background

- The model maker is `tools/make_demo_cable_lay.py` + `tools/demo_cable_lay/` (OpenCascade, one parameter set). It
  writes 9 STEP files (assembly 32.8 MB), `demo_cable_route.json` (routes, tensioner lift/tilt, quadrant, arch, CPS,
  quay) and `demo_joints.json` (**307 joints**, 244 of them turned by the cable; `rides_on` = stacked joint,
  `follows` = coupling). Writing all files took 57 s, the import 11.2 s at Normal (1,252 placed parts, 1.97 M triangles)
  on the 4-core web machine. Read 0084's report (end of `tasks/0084-demo-deck-relayout.md`) for what exists and
  where; 0076's report for the sheets' format.
- 0083 (`tasks/0083-cable-lay-reference-study.md`): item 8 looks/paint, item 9 vessel motion, "Facts per task" →
  0077 (real speeds, time-lapse factor in a caption, carousel 0.14–0.40 rpm, squeeze stroke and time, quadrant tip
  0→90° shown in 10–20 s, X-ray highlight + arrow chevrons), and the **shot list** (1 min 45 s, 11 shots + 2b). The
  owner wants **loading from the quay and laying** in the demo.
- The app already has everything the "today" video needs: joints, stacks, couplings, motors (0011/0012), cylinders
  (0013), Open sea / vessel deck / quayside (0016), light looks, camera views, depth of field (0017), captions, title
  and end card, brand kit (0018), labels (0025), Fade / X-ray (0073), camera Ride along / Fly a path / Watch part
  (0087), render queue, every paint scheme (0074).
- Running at the same time: **0085 vessel motion at sea** (Sea lane), **0086 cutaway** (Cutaway lane), **0088 hover
  highlight** (Pick & hover lane), and today **0058 flex parts** + **0061 tool marks** (Fable day). None of them touches
  the demo files. Whichever of 0077 and 0085 merges **second** wires vessel motion into the demo (Calm, the sea's own
  waves) and makes shot 1 ride it; say in the report which way it went.
- Precedent for writing a model at run time inside the app: the PC check Heavy (`pccheck/heavy.py` starts
  `pccheck/heavy_scene.py` as its own program with Blender's Python and the bundled OpenCascade). The test tour
  (`blender/tour.py`, `ops_tour.py`) shows how the app makes a project in Documents, per version, with progress.

## What to build

### Where the model maker lives

The demo must be made on the owner's Windows PC from the installed app, so the maker must ship with the extension.
Move `tools/demo_cable_lay/` into the package (for example `fresing_render/demo_model/`, no Blender, run as its own
program like `heavy_scene.py`); `tools/make_demo_cable_lay.py` and `tests/test_demo_cable_lay.py` keep working through
it (thin wrapper, same arguments). No relative-import surprises when it runs as a script; nothing of it may need
`tools/`. Check the zip size stays reasonable (code only; no STEP in the zip). Update CLAUDE.md section 3.

### Make demo project

- **Help > Make demo project…** (next to the test tour items) and **Help > Open demo project**. One project per app
  version in `Documents\Fresing Render\Demo\<version>\` (like the tour); making it again replaces it after a question.
  Progress in the status bar with the stage ("Writing the model 2/9", "Importing", "Joints 120/307", "Animation"),
  **Cancel** at any moment, a plain message when it fails (and what is left behind). Blender stays usable while the
  model is written and imported (subprocess + ImportJob, as the import does).
- **Scene set-up, everything through the app's own functions** (the same calls the buttons make, so the project is
  exactly what a user would have made):
  - import `demo_cable_lay.step` at Normal; groups and looks as 0083 item 8 (deck and machine paint, rubber pads,
    steel, the cable black with yellow stripes as far as a fixed material can show it today – the moving stripe is
    0078);
  - **all 307 joints** from `demo_joints.json`: type, axis, limits, `rides_on` as stacks, `follows` as couplings; the
    cable-turned rollers follow one **"Cable travel"** slide joint (m of cable) so 0078 only has to put the cable on
    it. Where the sheet gives a joint per cylinder (tensioner lift, quadrant handler), make them app **cylinders**
    (Drives the arm / slide) when the pin points are in the route sheet, otherwise plain joints – say which in the report;
  - surroundings **Open sea** with the model's own hull (waterline from the sheet), Sun look; a second saved scene
    **"Loading at the quay"**: Quayside surroundings + `demo_quay_loading.step` imported in the same coordinates
    (its joints from the joint sheet);
  - **saved camera views** for the shots below; a brand kit "Demo" (generic logo text, not a company's);
  - every animation and drivers work with **scripts off**; the render queue renders it.
- **Animation "What it can do today"** (60–80 s, 25 fps, captions with the time-lapse factor where used, e.g.
  "× 10"), built from existing steps only, following 0083's shot list as far as today's features go:
  1. establishing shot – **Fly a path** round the vessel on the sea (rides the vessel if 0085 is in);
  2. the deck from above – slow orbit;
  3. carousel turning (real rpm × time-lapse), the arch slewing to follow, the coil;
  4. the roller highways – rollers turning with "Cable travel", camera **Ride along** low beside the route;
  5. tensioner: top track lifts and tilts out, closes again and squeezes (cylinders), **X-ray** of the tensioner with
     **labels** on its parts;
  6. handling winch drum turning, close-up with **depth of field** on the Lebus crossovers;
  7. quadrant: travels aft on its rails, the handler tilts over the stern, the quadrant tips (time-lapse caption);
  8. end card.
  Shots that need 0078–0082 (cable moving, tracks running, spooling, catenary, under water) are left out; leave a
  clear place for them (see next point).
- **Built so later tasks add to it:** `demo.py` builds the project as a list of small named stages (model, looks,
  joints, surroundings, cameras, each shot); 0078–0082 add or replace one stage each (like `@tour_set`). Write the
  pattern in the module docstring.
- Optional, only if cheap: arrow chevrons along the route showing the cable's direction (decal arrows) – 0083's ref.

### Speed (measure, name the machine)

- Make demo project from nothing on the 4-core web machine: total and per stage (write, import, joints, animation
  Build). Expected on the owner's 24 cores: well under that – say it is an expectation.
- With the demo open: time per frame while scrubbing the "today" animation (the Ride along / Watch part steps read parts
  per frame – 0087 did not measure that on a big model), the Build time, and a 960 × 540 Cycles still on the processor.
- If anything is slow on this model (more than ~1 s per frame change, a Build over ~60 s), report it with numbers as an
  open point; do not start optimising other lanes' code.

### Owner's checks

- **Tour stop** "Demo project" with a cheap check (the demo exists for this version, opens, 307 joints, the animation's
  length) – do not build the demo inside the tour build (the tour must stay fast); if the demo is missing, the stop
  says "Help > Make demo project first". Raise the counts (CLAUDE.md section 6).
- **PC-check line** in **Heavy** (`pccheck/heavy.py`, modes H): makes the demo, a still of the overview, a few frames
  of the animation; metrics: make time, Build time, time per frame, peak memory; scaled-down form for GitHub (a smaller
  cable Ø or fewer parts – whatever the maker's parameters allow; the scaled form must stay under ~3 min on a runner).
  Raise `MIN_LINES_HEAVY`.
- **Guide:** a short chapter "Demo project" (what it is, how to make and open it, what the video shows, that it is an
  invented vessel), one picture.

## Done when

- [x] The maker ships with the extension and still works from `tools/`; `tests/test_demo_cable_lay.py` green.
- [x] Help > Make demo project… / Open demo project; progress, Cancel, replace-question, failure message; per version.
- [x] Project: looks, 307 joints (stacks + couplings as the sheet says), cylinders where possible, Cable travel joint,
      Open sea scene + "Loading at the quay" scene, saved cameras, "What it can do today" animation with captions.
- [x] Tests (new `tests/test_demo_project.py`, Blender as a module; a scaled-down model is fine for speed): every joint
      of the sheet exists with its type/limits/rides_on/follows; a coupling turns at the right ratio; the animation
      builds with 0 clash rows (`clash` check on it; a real clash = a fault in the model or the set-up, fix it there);
      scripts-off drivers only; save + reopen + Build again gives the same keys; Cancel leaves no half project.
- [x] Measurements above in the report; one 960 × 540 picture of the overview and one of the tensioner X-ray shot in
      `tasks/img/0077-*.png` (invented model only).
- [x] Tour stop, Heavy PC-check line, guide chapter, tooltips (`tooltip_report.py` 0 missing), CHANGELOG, version last.
- [x] GitHub run green on the branch and on `main`; release published; report filled in; `TASKS.md`: 0077 done.

## Not in this task

The moving cable, tensioner track motion, spooling, catenary, under-water view, quadrant operations (0078–0082); vessel
motion itself (0085); hover picking (0088); any change to the joint, cylinder, camera or surroundings code – if
something there is missing or wrong for the demo, write it down as an open point for its lane.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (4 cores), 12 Nov 2026 · version 0.2.68 · branch `claude/sweet-mendel-tecn1z`.

**What changed:**
- **The maker ships with the extension:** `tools/demo_cable_lay/` → `fresing_render/demo_model/` (no Blender, only
  relative imports inside); new `demo_model/make.py` runs it as its own program (it loads its folder as a package by
  path, so nothing of `tools/` is needed) with `--only <keys>` and `--progress <json>`. `layout.write(only=…,
  progress=…)`: the demo writes only `demo_cable_lay.step` + `demo_quay_loading.step` (no Lebus drum: 25 s saved).
  `tools/make_demo_cable_lay.py` is a thin wrapper (same arguments); `pictures.py` → `tools/demo_cable_lay_pictures.py`.
  Zip: +0.23 MB of code (extension 52.7 MB).
- **`blender/demo.py`:** the project as named **stages** (`@stage(id, title, after=…)`, same id replaces; pattern in the
  module docstring; shots advance `d.t`): model (maker subprocess + import at Normal), looks, joints, cylinders,
  surroundings, cameras, brand, seven shots, finish (Build). `build_project` removes an older demo of the version,
  writes `making.json` while it runs, deletes the whole folder on Cancel or failure, writes `demo.json` (summary).
  `Documents\Fresing Render\Demo\<version>\Demo cable-lay vessel <version>.blend` + `model\`.
- **`blender/ops_demo.py`:** Help > **Make demo project…** (dialog; "is there already: it is replaced"), a background
  Blender via the PC check's launcher (`-- demobuild <folder>`), status bar "Making the demo project: Joints 120/307 …",
  Help > **Cancel demo project** (cancel file; after 4 s the build's program tree is killed: `taskkill /T` on Windows,
  the process group on Linux; the folder is deleted), Help > **Open demo project**; the result read from
  `Make demo result.json`; a failure says why and that nothing but the log is left.
- **Set-up, all through the app's own calls:** 10 demo groups by part name ("Assign selected" + `ensure_group`,
  0083 item 8: machinery RAL 5010, orange RAL 2004, structure RAL 1003, deck RAL 7037, walkways RAL 6011, rubber pads,
  steel, rollers, black cable, galvanised wire; 1,181 parts); **all 307 joints** with type, axis, limits, `rides_on` as
  stacks (base = the lower joint's motion), `follows` as couplings at the sheet's ratio; the 236 cable-turned joints +
  the carousel follow **Cable travel** (slide, m of cable paid out, moves nothing, sits on the deck) at the sheet's
  °/mm; the quay file's 108 joints ("QUAY: …"); **cylinders: the quadrant handler's two** (pin points in the route
  sheet; Follow mode on the handler tilt). **The tensioners' four lift cylinders stay plain parts of the lift joint**
  (the sheet gives no pin points for them). Surroundings: Open sea, Sun look, water level = the sheet's waterline,
  **vessel motion on (Calm, Bow quarter)** – 0085 merged first, so this task wired it; saved scene **Loading at the
  quay** (Quayside, quay model shown; vessel motion is off there: it only works on Sea/Deck); 8 saved cameras + their
  scenes; brand kit "Demo" (a generic logo picture).
- **Animation "What it can do today"** (68.5 s body + 3 s title + 3 s end card = 74.5 s, 25 fps, 1,713 frames,
  captions on): 1 Fly a path round the vessel watching the carousel (6 s), then **Ride along on the hull** (levelled,
  3 s); 2 Move to "Deck from above" + Orbit 30°; 3 Cable travel 16.7 m in 10 s (**× 10**: 10 m/min real, carousel
  0.2 rpm real) + arch slew 6°; 4 Cable travel on (× 3), camera flies along the highway; 5 tensioner 2: lift 0.6 m,
  tilt 20°, back, squeeze −20 mm (real speed), then **X-ray** of its two frames with **4 labels** only during that
  step, fade back; 6 handling winch drum one turn, close-up with **background blur** on the drum; 7 a flight over the
  D-quadrant to the handler at the stern, watching the handler.
- **Faults the clash check found and what was done:** (1) the tensioner top track's **tilt hinge landed metres off**,
  so the track swung 7 m down through the deck: `joints.create` inside `joints._batch` reads a stacked joint's base
  before the batch's update, and a joint made a moment earlier has no world matrix yet – the demo updates first
  (Motion lane open point below). (2) The **track sprockets** turned with the cable while the chain stands still
  (teeth through the links): they get their joints but follow the cable only once 0079 runs the tracks
  (`demo.waits_for_tracks`). (3) The **quadrant system cannot move yet** (model faults, below): shot 7 flies over it.
  (4) **`core/clash.split_long`** (Clash lane, free): halving at the longest edge grew like 3ⁿ (a 60 m sliver became
  59,049 pieces, the hull bottom ~2·10⁹: the check ran out of 15 GB). Now a long thin face is cut into a strip
  (≈ 2 × length / 25 mm pieces, same surface and sides), a wide face stays whole, a mesh past 600,000 pieces is cut
  coarser. Largest demo mesh now 427 k pieces in 0.2 s; `test_clash.py` + `test_clash_core.py` green (new test).
- Tour stop **"Demo project: cable-lay vessel"** (hub set; reads `demo.json`, never makes the demo; without it: "Help >
  Make demo project first"); **Heavy line `heavy.demo`** (make, Build, ms per frame over 40 frames, a still, peak
  memory; scaled form = Draft meshes, no quay); guide chapter **"Demo project"** + picture; CLAUDE.md section 3 + 3
  lessons in section 8; CHANGELOG 0.2.68. `MIN_LINES_TOUR` 42, `MIN_LINES_HEAVY` 13, `MIN_CHECKS` tour 42 /
  pccheckheavy 13.

**Tested and measured** (4-core web machine, no graphics card):
- **Make demo project from nothing** (real maker, Normal meshes, `build_project`): **148 s** – writing the model
  48.9 s, import of both files 21.8 s, **joints 69.0 s** (415), looks 0.1, cylinders 0.8, surroundings 1.8, cameras
  0.5, the shots 0.4, Build 4.4 s; peak memory 0.9 GB. On the owner's 24 cores: **an expectation only** – the maker
  and the joints run on one core, so maybe 60–90 s; the import part scales.
- With the demo open (Blender as a module, no viewport drawn): **Build 4.7 s**; **7.5 ms per frame change** over the
  whole animation (every 10th frame), Ride along on the hull 9.1 ms, Fly a path 7.2–8.0 ms (0087's open question: no
  cost worth naming on this model); **960 × 540 Cycles still on the processor (Preview): 161 s**; peak memory 3.1 GB
  (after the still). The viewport's own drawing is not in these numbers (no screen here).
- `tests/test_demo_project.py` (new, 13 tests, scaled form): every sheet joint with type, limits, stack, coupling,
  ratio and its axis in the model's frame; a coupling turns at 250 mm × its °/mm (driver and the part's matrix), the
  carousel's support rollers through two couplings; the handler cylinders follow the tilt; all 300+ drivers simple
  expressions (scripts off); saved scenes, cameras, brand, animation 60–80 s with the × 10 caption; **save + reopen +
  Build again: the same keys**; **0 clash rows over the whole animation** (parts that only turn about their own
  round axis + the static cable left out of the check, and the test proves they turn about their own axis: 240 s on
  the Draft model); Cancel half-way through the joints and a failing maker both leave no folder; the stage list can
  be extended and replaced; Help-menu tooltips. Locally: whole file 6 min 15 s, green; `test_demo_cable_lay.py` 35,
  `test_tour.py` + `test_user_guide.py` 60, `test_clash.py` + `test_clash_core.py` 34, all green. Tooltip check: 603,
  0 missing.
- Full clash check on the full-size demo **with** the spinning parts: stopped after 47 min (not done); with them left
  out: 12.5 min, 1,839 moments + 32,870 between, 355,868 narrow tests – the rows it found are the faults above.
- Pictures (Cycles CPU, 960 × 540, Preview): `tasks/img/0077-overview.png` (the open sea, labels off),
  `tasks/img/0077-tensioner-xray.png` (shot 5 at the X-ray step). Invented model only.
- GitHub: **1 full run on the branch, green on the first try** (run 43145128900, 12.3 min; test suite 6 with the new
  test file 12.0 min, paths-heavy with `heavy.demo` 10.5 min – both flagged SLOW against the old times; recording the
  new times in `tools/ci_times.json` would rebalance the groups – left for a later tools push). `main` fast-forwarded to
  the green commit: run 43146614649 (reuse, 2.4 min) published **v0.2.68**, the Windows update-from-the-release check
  passed, offered to the apps.

**Open points / follow-up tasks:**
- **Demo models lane / 0082 – the quadrant system is not free to move** (clash check, full-size model): the D's
  travel aft runs into the S-bend's **roller cradles** at once (125 mm, frames 3–30 of the travel; also its gutter
  50 mm and a pad eye 30 mm); the **handler frame cuts its hinge brackets** past about 30° of tilt (139 mm); the
  **parked handling wire** stays behind when the handler tilts (233 mm) and the D passes through it (125 mm); the
  handler cylinders' rod leaves its barrel near 70° (2 rows); the rail wheels show short 2–50 mm rows while turning
  fast (worth a look: wheel axis vs. its round centre). Until then shot 7 only flies over it; the quadrant tip is not
  shown.
- **Clash lane:** parts that turn in place (300 rollers, the coil, support rollers at 50× the carousel) make the check
  take hours on this model (the box corners move, so every pair is tested again, plus many moments between frames).
  A "turns about its own round axis" shortcut (skip pairs of such a part as long as its axis stays put relative to the
  other) would let the owner check the whole demo. The static cable lying on the rollers is another costly contact.
- **Motion lane:** (a) `joints.create` inside `joints._batch` computes a stacked joint's axis from its base before the
  update – a base joint made in the same batch has no world matrix yet (the tilt hinge landed metres off; the demo
  works round it). (b) `create` and `set_follows` each update the whole scene (0.1 s on this model): 69 s for 415 joints.
- **Scene & Render lane:** labels tied to a step also show in stills (documented), and the four X-ray labels crowd at
  the bottom edge of the picture (two boxes overlap).
- **Looks:** the cable is plain black; the yellow stripes need a moving texture (0078). The Lebus close-up of 0083's
  shot list is a spiral-groove drum here: the Lebus drum is only a separate file (`demo_drum_lebus.step`).
- Not done: arrow chevrons along the route (optional, skipped). Helper-agent review skipped: the only Windows-only
  code is `ops_demo.kill_tree` (`taskkill /F /T /PID`, the standard way) – the owner's first Cancel on Windows
  confirms it; the Windows CI job runs `heavy.demo` (maker + import + joints) from the installed app.
- The demo's "since" numbers say 0.2.68; the shot timings (`demo.py`) are a first cut – the owner may want slower
  camera moves.
