# Tasks

The shared to-do list of all chats working on Fresing Render. How tasks work: see
`CLAUDE.md` section 2. One file per larger task in `tasks/` (copy `tasks/TEMPLATE.md`).

**Who:** *lead* = the lead chat (plans only, no building or testing) · *worker* = a separate Claude Code session on the web (older tasks: a chat)
the owner starts for this task; it finishes with merge and release (CLAUDE.md section 2) ·
*owner* = Sebastian (decision or test on his PC).

**Status:** open · running · waiting (on someone) · done

## Lanes

Tasks that touch the same files are in one **lane** and run one after the other; different
lanes run at the same time, each in its own worker chat. Shared files: `blender/props.py`, `blender/reimport.py`
(additive changes only) and `blender/ui.py` (each lane only its own panels); whoever merges second
updates its branch to `main`.

- **Looks lane** (rules, materials, importer, 3 Looks): 0008 (done, 0.2.8) → 0010 (done, 0.2.9) → 0015 (done, 0.2.13) → 0023 clean-up (done, 0.2.15) → 0024 decals (done, 0.2.21) → 0046 better materials (open – can start)
- **Motion lane** (joints, poses, animation; `ui_motion.py` = panels 4 Motion, 6 Animation, 7 Render queue): 0011 (done, 0.2.10) → 0012 (done, 0.2.18) → 0013 (done, 0.2.25) → 0014 (done, 0.2.26) → 0026 G-code (done, 0.2.30); lane free
- **Scene & Render lane** (`world.py`, `cameras.py`, `render.py`, panel 5 Scene & Render): 0016 (done, 0.2.12) → 0017 (done, 0.2.17) → 0018 (done, 0.2.23) → 0025 (done, 0.2.27) → 0043 hall stays put + MP4 memory (open)
- **Quality & delivery lane** (`.github/`, `installer/`, `tools/`, no app code): 0019 (done) → 0020 (done, 0.2.16) → 0036 faster automatic tests (done, 0.2.31) → 0031 Claude Code set-up (done 8 Nov) → 0047 landing page on GitHub Pages (running)
- **Docs lane** (`docs/`, Help-menu link): 0021 (done, 0.2.11); later tasks keep their own chapter up to date; 0044 missing pictures (open – can start)
- **Part library lane** (`core/part_types_data.py`, `core/part_types.py`, `core/fasteners.py`, their tests only): 0022 (done, 0.2.14) → 0030 fasteners in supplier notation (done, 0.2.20); lane free
- **PC check lane** (new `fresing_render/pccheck/`; additive: installer shortcut, Help-menu item, CI steps): 0032 PC check (done, 0.2.24) → 0033 Heavy mode (done, 0.2.32); lane free
- **Machining lane** (new files `machining.py`, `ops_machining.py`, `chips.py`, `ui_machining.py`; sub-panel of 4 Motion in its own file): 0027 material removal (done, 0.2.19) → 0028 chips (done, 0.2.22) → 0029 later (owner decides); 0038 milling memory crash (done, 0.2.33) → 0039 air blast (done, 0.2.34) → 0040 tool library (running) → 0041 tool changes + ATC → 0042 coolant (later); these four also touch the G-code files (`core/gcode.py`, `blender/gcode.py`, `ui_gcode.py`), so the Motion lane waits for them; 0034 way covers (done, 0.2.28) → 0035 way-cover follow-ups (later)

## Problems found, waiting for a task

The lead turns each into a task (number, brief, model) and then deletes its entry here.

- **Four smaller problems from 0037** (two way covers on one axis; Motor not ticked when the spindle is picked;
  second import re-lays the hall; "//" program path): `tasks/0037-owner-mill-gcode-demo.md`, problems 3–6.
  (Problem 2, the fluted end mill read as Ø10.4, is part of 0040; problem 7 was done in 0038.)

## Open and running

| # | Task | Who | Model · effort | Status | Branch / file |
| --- | --- | --- | --- | --- | --- |
| 0040 | Machining lane: tool library – one list per project, 8 tool types from sizes or imported STEP, Fusion/LinuxCNC tool files, every tool cuts with its own shape (also after M6); fixes 0037 problem 2 | worker | Opus · High | running – Claude Code on the web, 8 Nov | task/0040-tool-library |
| 0041 | Machining lane: tool changes – manual (short pause 1 s, slider 0–5 s, optional caption, optional operator's hand) and ATC (pockets, tools visible, carousel turns, swap animated) | worker | Opus · High | open – after 0040 | tasks/0041-tool-changes-atc.md |
| 0042 | Machining lane, later: coolant flood (M8, liquid look) – brief when the owner asks | owner decides | – | later | – |
| 0043 | Scene & Render lane: a second import keeps the surroundings in place (0037 problem 5, + "Fit surroundings to the model" button); 4K MP4 encode without gigabytes of cached frames | worker | Sonnet · Medium | open – can start | tasks/0043-hall-relay-mp4-memory.md |
| 0044 | Docs lane: missing guide pictures – Way covers, Air blast, Labels, Pictures, Music (taken out of 0035) | worker | Sonnet · Low | open – can start | tasks/0044-guide-pictures.md |
| 0045 | No lane (reads only, changes no app code): bug hunt across the whole app – crashes, lost work, old projects, wrong output, slow spots; ranked findings with proof, for the lead to turn into tasks | worker | Opus · High | open – can start | tasks/0045-bug-hunt.md |
| 0046 | Looks lane: better materials – ground/turned/machined steel and aluminium, brushed stainless, cast iron, chrome rod, anodising, orange-peel paint, optional edge wear (slider, default 0), CAD names, old projects get the new looks, material sheet + PC-check line | worker | Opus · Medium | open – can start | tasks/0046-better-materials.md |
| 0047 | Quality & delivery lane: landing page on GitHub Pages in Fresing's look (owner brings brand, colours, logos) – pictures/video of free openly licensed models rendered on the owner's PC with a ready-made kit, Download for Windows, user guide in the browser, "Made by Fresing" with link to fresing.nl; updates itself at every release | worker | Opus · Medium | running – Claude Code on the web, 8 Nov | task/0047-landing-page |
| 0029 | Machining lane, later: milling without a CAM program (app-made toolpath), 4/5-axis | owner decides | Opus · High | later | tasks/0029-milling-later.md |
| 0035 | Machining lane, follow-up to 0034/0025: the carriage as last way-cover section (share 1, no new joint), 8 sections tested in Blender; guide pictures of Way covers, Labels, Pictures/Music | worker | Sonnet · Medium | later – owner put it on hold (6 Nov); after 0031 | tasks/0035-waycover-follow-ups.md |
| 0001 | Owner's list of interface wishes (first part became 0008–0010; more may follow) | lead | – | open | – |
| 0002 | Measure on the owner's PC: EGR import time (0.2.3+), animation time per frame with Time test (0.2.4+), EEVEE speed on the RTX 3090 | owner | – | open | – |
| 0003 | Rest of the first Windows test: own Inventor STEP + still, joint on a real pivot | owner | – | open | – |
| 0004 | Decide where renders go: "Renders" next to the project (now) or Pictures\Fresing Render\<project> | owner | – | open | – |
| 0006 | Phase 3, when projects need it: motion paths, several machines in one scene, clash warning, project templates | worker (per feature) | – | open | – |

## Done

| # | Task | Version |
| --- | --- | --- |
| – | Phase 1 (stills), phase 2 (motion), installer, self-test | 0.1.0 – 0.2.2 |
| – | STEP import on all cores | 0.2.3 |
| – | Faster animation renders, Time test, Show in folder | 0.2.4 |
| – | Side panel redesigned section by section | 0.2.5 |
| 0007 | Triangles read in one block (biggest EGR part 2.6 s → 0.3 s); self-test checks Time test and noise removal | 0.2.6 |
| – | Code on GitHub; CLAUDE.md, TASKS.md, CHANGELOG.md; way of working agreed | – |
| 0009 | Structure and Looks: explorer tree, highlight, find & sort parts, show only, ready-made materials (owner's points 1–3, 5–16) | 0.2.7 |
| 0008 | Part-type library (63 types, ~3,300 keywords, ~170 order-code patterns) and CAD material/appearance names from STEP (owner's points 17–18) | 0.2.8 |
| 0010 | Painted faces: faces painted in CAD come in painted, paint faces by hand (whole CAD faces, per copy), kept through model updates; wire mesh with holes; old default rules upgraded (owner's point 4) | 0.2.9 |
| 0011 | Stacked joints: several joints on one subassembly, the moves add up; Swap order; stacks survive model updates | 0.2.10 |
| 0016 | Surroundings: open sea, vessel deck, quayside, clean factory, CNC hall, assembly hall, warehouse (Simple/Detailed, halls never hide the machine); 360° photo with its ground and shadow; props for scale; tooltips in panel 5; guide with free 360° photos | 0.2.12 |
| 0015 | Rule sets: one naming scheme per company (rules + group looks + group names), a file per rule set in the shared library, picked per project with a preview before switching; Standard built in; templates and old projects keep working | 0.2.13 |
| 0019 | Automatic tests on GitHub at every push: Linux suite + real app, Windows install + self-test + uninstall (about 10 min per run) | – (no release needed) |
| 0020 | Updates inside the app: "Update available" → Update now (saves, closes, installs, opens again), app template updated too; GitHub publishes every new version on `main` as a release, checks it on Windows, then offers it to the apps; task-list-only pushes start no test run | 0.2.16 |
| 0021 | User guide (Help > Fresing Render user guide, Start menu, next to Install.bat); tooltip style guide, tooltip check and the list of 93 tooltips for the lanes (`docs/TOOLTIPS-TODO.md`) | 0.2.11 |
| 0022 | Supplier catalogue codes (Misumi and others); fewer wrong groups (PALLET, LINK, sensor posts); EGR 55 % → 67 % sorted | 0.2.14 |
| 0023 | Looks lane clean-up: every button and setting of sections 1–3 has its own tooltip, "1 part" not "1 parts", tooltips no longer break mid-sentence (all lanes), guide chapters 1–3 current | 0.2.15 |
| 0017 | Light looks (product, white endless, dark, sun, overcast), light in words, one-click camera views framing model or selection, background blur with a clicked sharp spot, one-click turntable video into the queue | 0.2.17 |
| 0012 | Couplings (a joint follows another: gears, telescopes, jaws, spindles, racks, rolling wheels) and motors with the Run motor step; works with scripts off; every tooltip of panels 4, 6, 7 and Saved scenes | 0.2.18 |
| 0027 | Milling: pick the bit(s) and the workpiece, material disappears where a bit cuts (view, scrubbing, render queue); flat/ball/corner radius/V/drill recognised; optional finish at the CAD part; Manifold mesh booleans per straight move | 0.2.19 |
| 0030 | Fasteners in supplier notation: Misumi-style set screws (MSSF5-5), WRENCHBOLT, BOLT5-20, NUT5, WASHER6; the owner's DIN/ISO bolts, nuts and washers with all coatings are now covered by tests | 0.2.20 |
| 0024 | Decals: logos, text, type plates, CE mark, warning signs and arrows on parts with a click; flat or wrapped round cylinders; every copy or one copy; move with the mouse, size in mm; kept through model updates and in templates; library folders Logos and Stickers | 0.2.21 |
| 0028 | Chips while milling: per workpiece material and bit type (curls, commas, crumbs, ribbons, shavings, spirals, dust), thrown in the turning direction, land and pile up on block, table and bed, gone where the bit cuts again; None/Few/Realistic, coolant mist, Clear chips; worked out once per motion, the same every time; the queue renders them | 0.2.22 |
| 0018 | Video finishing: brand kits in the library (logo, colours, font, contact line), logo in a corner of videos and stills, title card, end card, captions from the step labels, watermark per render job, crop or extend for 1:1 and 9:16 | 0.2.23 |
| 0032 | PC check: Start menu / Desktop / Help > PC check (Quick about 3 min, Full about 15 min), 30 lines on the test models, own STEP file optional; HTML report with pictures, speed vs the last runs on the PC, picture checks, new lines on top; text block with numbers only for the lead chat; runs on GitHub (Linux + Windows) | 0.2.24 |
| 0033 | PC check Heavy: a big generated machine (3,000 parts), import, structure/search/explode/save, Cycles HD and 4K pictures, EEVEE per frame, a 10 s EEVEE video and a 3 s Cycles clip through the queue with contact sheets, Detailed halls, a long milling cut with chips, playback under load, own-model 4K and video; peak memory; Cancel; scaled-down form on GitHub. Owner's run: 12 min on the RTX 3090 | 0.2.29, 0.2.32 |
| 0013 | Cylinders: barrel turns about its pin, rod's eye stays on its pin when the arm moves (constraints, scripts off); Drives the arm: set the stroke, the arm turns (law of cosines, slide too); closed length and stroke read from the parts; telescopic stages; Move cylinder step; "Show joint arrows" NameError fixed | 0.2.25 |
| 0025 | Labels with lines that stay on their (moving) parts, picture cards over videos (full screen or corner), music under MP4 videos with fades; PC-check line | 0.2.27 |
| 0014 | Mechanisms: scissor lifts (height, rollers), four-bar and parallel arms, slider-cranks, other planar linkages; pins found from shared holes; exact solver that never flips; drive by angle, height or a cylinder; Lift height step; kept through model updates. Owner's example files still to try | 0.2.26 |
| 0034 | Way covers: telescopic covers follow one slide axis; sections picked (several parts each), travel shared out (500 mm / 5 sections = 100 mm each), Housing counts (0/125/250/375/500), Flip, Read from the axis; every section is a slide joint that follows the axis, so poses, steps, G-code and the render queue move them; the owner's 5-section way-cover STEP is a test model | 0.2.28 |
| 0026 | G-code drives the machine: LinuxCNC reader (arcs in all planes, cycles, offsets, parameters, o-words), 4 Motion > CNC machine (axes, spindle, tool, work zero, tools), step Run G-code program (exact path, spindle, tool changes with tool-changer animation, toolpath); joints no longer snap to CAD within 0.1 mm | 0.2.30 |
| 0036 | Faster automatic tests: precheck first (version clash in ~1 min), pytest and real app as parallel jobs (full run 11–14 min, was 35–50), a push to `main` whose tree already ran green releases without repeating the tests (1.7 min), docs-only pushes ~2 min | 0.2.31 |
| 0031 | Stored set-up for Claude Code sessions on the web (venv, Blender 5.2.3, xvfb, ImageMagick ready at start, 0 s) | no release |
| 0037 | The owner's own mill set up with block, Ø10 end mill, CNC machine, milling + chips, a 3.4-min G-code demo and its step (45 s); first real-machine test of 0026/0027/0028/0034; 7 app problems for the lead, one crash (milling path re-read) | – (no app change) |
| 0038 | Milling crash fixed: the bits' path is stored safely (Blender 5.2.3 corrupted memory when an array property got a NumPy array of another length); crash tests, old projects, queued MP4 | 0.2.33 |
| 0039 | Air blast: air on/off from the program (M7/M9 or M100–M199, or always with the spindle), through the spindle or an external nozzle, chips blown off the part, "Blow the part clean at the end" with a time slider, optional visible cone; test mill pocket 1,560 → 0 chips on the block | 0.2.34 |

Details per version: `CHANGELOG.md`.
