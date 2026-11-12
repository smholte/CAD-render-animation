# 0077 – Demo project "Cable-lay vessel" (Help > Make demo project)

**Who:** worker · **Status:** running · **Branch:** `claude/sweet-mendel-tecn1z`
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

- [ ] The maker ships with the extension and still works from `tools/`; `tests/test_demo_cable_lay.py` green.
- [ ] Help > Make demo project… / Open demo project; progress, Cancel, replace-question, failure message; per version.
- [ ] Project: looks, 307 joints (stacks + couplings as the sheet says), cylinders where possible, Cable travel joint,
      Open sea scene + "Loading at the quay" scene, saved cameras, "What it can do today" animation with captions.
- [ ] Tests (new `tests/test_demo_project.py`, Blender as a module; a scaled-down model is fine for speed): every joint
      of the sheet exists with its type/limits/rides_on/follows; a coupling turns at the right ratio; the animation
      builds with 0 clash rows (`clash` check on it; a real clash = a fault in the model or the set-up, fix it there);
      scripts-off drivers only; save + reopen + Build again gives the same keys; Cancel leaves no half project.
- [ ] Measurements above in the report; one 960 × 540 picture of the overview and one of the tensioner X-ray shot in
      `tasks/img/0077-*.png` (invented model only).
- [ ] Tour stop, Heavy PC-check line, guide chapter, tooltips (`tooltip_report.py` 0 missing), CHANGELOG, version last.
- [ ] GitHub run green on the branch and on `main`; release published; report filled in; `TASKS.md`: 0077 done.

## Not in this task

The moving cable, tensioner track motion, spooling, catenary, under-water view, quadrant operations (0078–0082); vessel
motion itself (0085); hover picking (0088); any change to the joint, cylinder, camera or surroundings code – if
something there is missing or wrong for the demo, write it down as an open point for its lane.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
