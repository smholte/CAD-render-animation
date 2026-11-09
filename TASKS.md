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

- **Looks lane** (rules, materials, importer, 3 Looks): 0008 (done, 0.2.8) → 0010 (done, 0.2.9) → 0015 (done, 0.2.13) → 0023 clean-up (done, 0.2.15) → 0024 decals (done, 0.2.21) → 0046 better materials (done, 0.2.39) → 0055 Looks fixes (done, 0.2.40) → 0056 same STEP twice (done, 0.2.44); lane free
- **Motion lane** (joints, poses, animation; `ui_motion.py` = panels 4 Motion, 6 Animation, 7 Render queue): 0011 (done, 0.2.10) → 0012 (done, 0.2.18) → 0013 (done, 0.2.25) → 0014 (done, 0.2.26) → 0026 G-code (done, 0.2.30) → 0052 model update keeps everything (done, 0.2.41) → 0054 queue fixes (done, 0.2.46); lane free; later: 0050 delayed queue start
- **Scene & Render lane** (`world.py`, `cameras.py`, `render.py`, panel 5 Scene & Render): 0016 (done, 0.2.12) → 0017 (done, 0.2.17) → 0018 (done, 0.2.23) → 0025 (done, 0.2.27) → 0043 hall stays put + MP4 memory (done, 0.2.35); lane free
- **Quality & delivery lane** (`.github/`, `installer/`, `tools/`, no app code): 0019 (done) → 0020 (done, 0.2.16) → 0036 faster automatic tests (done, 0.2.31) → 0031 Claude Code set-up (done 8 Nov) → 0047 landing page on GitHub Pages (done 8 Nov; the owner's renders are swapped in by a later session) → 0053 safe updates and project lock (done, 0.2.42); lane free
- **Docs lane** (`docs/`, Help-menu link): 0021 (done, 0.2.11); later tasks keep their own chapter up to date; 0044 missing pictures (done, 0.2.37); lane free
- **Part library lane** (`core/part_types_data.py`, `core/part_types.py`, `core/fasteners.py`, their tests only): 0022 (done, 0.2.14) → 0030 fasteners in supplier notation (done, 0.2.20); lane free
- **PC check lane** (new `fresing_render/pccheck/`; additive: installer shortcut, Help-menu item, CI steps): 0032 PC check (done, 0.2.24) → 0033 Heavy mode (done, 0.2.32); lane free
- **Machining lane** (new files `machining.py`, `ops_machining.py`, `chips.py`, `ui_machining.py`; sub-panel of 4 Motion in its own file): 0027 material removal (done, 0.2.19) → 0028 chips (done, 0.2.22) → 0029 later (owner decides); 0038 milling memory crash (done, 0.2.33) → 0039 air blast (done, 0.2.34) → 0040 tool library (done, 0.2.36) → 0049 tool library fixes (done, 0.2.38) → 0051 milling fixes + milled faces' own look (done, 0.2.43) → 0041 tool changes + ATC (done, 0.2.45) → 0042 coolant (done, 0.2.47) → toolpath marks on cut faces (open – can start, lead to brief; owner 9 Nov); these four also touch the G-code files (`core/gcode.py`, `blender/gcode.py`, `ui_gcode.py`), so the Motion lane waits for them; 0034 way covers (done, 0.2.28) → 0035 way-cover follow-ups (later)
- **Flex parts lane** (new files `core/flex.py`, `blender/flex.py`, `blender/ops_flex.py`, `ui_flex.py`; small hooks in `handlers.py`, `animation.py`, `reimport.py`): **0058 hoses, cables and drag chains (Fable day, Thursday 12 Nov)**

## Problems found, waiting for a task

The lead turns each into a task (number, brief, model) and then deletes its entry here.

- **Bug hunt 0045 (20 rows)** became tasks on 9 Nov: rows 3, 13, 15, 16, 20c → 0051; 1, 2, 6, 20a → 0052;
  4, 12, 14, 19b–d → 0053; 7–10, 17, 18, 20b → 0054; 5, 19a, 19e, 19f → 0055; 11 → 0056. Row 19g needs nothing.
- **0037 problem 3** (two way covers on one axis): goes with 0035. Problems 4 and 6 are in 0051, problem 5 was fixed
  in 0043, problem 2 in 0040, problem 7 in 0038.

## Open and running

| # | Task | Who | Model · effort | Status | Branch / file |
| --- | --- | --- | --- | --- | --- |
| 0058 | **Fable day.** Flex parts lane (new): hoses, cables and drag chains follow the motion (ends on their parts, fixed length, bend, sag; chain rolls on its bend radius; CAD links re-laid) – owner's priority 1 | worker | **Fable · High** | **Thursday 12 Nov (Fable day)**; after 0050 | tasks/0058-hoses-cables-drag-chains.md |
| 0059 | Quality & delivery + PC check: **test tour** – "Make test tour project" (generic models, every function as a numbered stop with Go, OK/Problem, note, Copy results) + automatic run (PC check mode Tour, HTML report with a picture per stop); rule: every new function adds its stop | worker | Opus · High | running (worker, 9 Nov, branch `task/0059-test-tour`) | tasks/0059-test-tour.md |
| 0060 | Small fixes: floor of a queued still = the video's floor, `ci_status.py --wait` on merge commits, Blender folder 8.3/subst spellings (0053, 0054 open points) | worker | Sonnet · Medium | after 0059 | tasks/0060-small-fixes.md |
| – | Owner's order of the big features (9 Nov), each briefed when its turn comes: **1** hoses/cables/drag chains (0058) · **2** coolant (0042) · **3** tool marks on cut faces that follow the toolpath (Machining, can start: 0042 done) · **4** motion paths (parts/cables along a curve, sheaves, winches) · **5** exact double-arm ATC swap · **6** 4th/5th axis (0029) · **7** clash warning · **8** app-made toolpath (0029, last) | lead | – | plan | – |
| 0050 | Motion lane (panel 7 Render queue): **Start queue in … / at …** with countdown, Cancel, Start now (owner, 9 Nov) | worker | Sonnet · Medium | open – can start (0042 done), before 0058 | tasks/0050-start-queue-later.md |
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
| 0042 | Coolant: M8 flood / M7 mist / M9 (or always / off per step), automatic Loc-Line hoses or nozzle parts, jets, splash at the tool, wet sheen that dries, wet chips, emulsion/oil, flow, draft; every frame from the frame number (Cycles +12 % on the test mill) | 0.2.47 |
| 0054 | Render queue fixes (bug hunt rows 7–10, 17, 18, 20b): queued picture = the frame shown, stopped videos never mix old frames, queue stays in its project, sharp spot in videos, five small queue faults, `//` paths, labels pass 75 → 9 ms per frame on 3,000 parts | 0.2.46 |
| 0057 | Landing page: the owner's new milling video (T1 face mill, T2 end mill, T3 chamfer mill, 27.6 s, 7.0 MB) at the top, old air-blast video removed | no release |
| 0041 | Tool changes: manual (head to the change position, pause 1 s / 0–5 s, optional gloved hand, optional caption) and tool changer (pockets clicked or filled round a carousel, tools in their pockets from the first frame, carousel turns the shortest way, old tool back in its own pocket; rack; changer animation split at its swap; ATC speed); Fit into still exact | 0.2.45 |
| 0056 | The same STEP imported twice: each copy gets its own part IDs (hiding, sets, poses, Show/Hide steps, model updates keep the copies apart); old two-copy projects repaired on open (bug hunt row 11) | 0.2.44 |
| 0051 | Milling: cut faces get their own fresh-cut look (Automatic / Same as the block / Pick), raw stock Aluminium, sawn plate and POM, black; bug hunt rows 3, 13, 15, 16, 20c; chips of the 0046 materials; spindle ticks Motor, programs stored next to the project | 0.2.43 |
| – | Phase 1 (stills), phase 2 (motion), installer, self-test | 0.1.0 – 0.2.2 |
| – | STEP import on all cores | 0.2.3 |
| 0045 | Bug hunt across the whole app: 20 ranked findings with proof (5 lost work + 1 suspected, 6 wrong output, 2 suspected crash risks, slow spots, small ones); old projects 0.2.20/0.2.24/0.2.30 open fine; Heavy machine measured | – (no code) |
| 0048 | Owner's demo with three BT30 tools (face mill, end mill, chamfer mill), M6 + G43; 5 app problems in the report | – (no code) |
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
| 0052 | Model update keeps everything: joints, cylinders, mechanisms and way covers linking two models stay; labels and the sharp spot follow their parts (report names gone ones); a failed update leaves the project as it was; Heavy update 17.0 s → 14.7 s | 0.2.41 |
| 0055 | Looks fixes: group renames keep schemes and scenes' looks, no duplicate group names, safer project load, old caches pruned, chrome rod / shaft looks | 0.2.40 |
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
| 0047 | Landing page https://smholte.github.io/CAD-render-animation/ in Fresing's look: Download for Windows (newest release), the owner's milling video, pictures, user guide, Made by Fresing; republished after every release; picture kit for the owner's PC (5 openly licensed models) | no release |
| 0037 | The owner's own mill set up with block, Ø10 end mill, CNC machine, milling + chips, a 3.4-min G-code demo and its step (45 s); first real-machine test of 0026/0027/0028/0034; 7 app problems for the lead, one crash (milling path re-read) | – (no app change) |
| 0038 | Milling crash fixed: the bits' path is stored safely (Blender 5.2.3 corrupted memory when an array property got a NumPy array of another length); crash tests, old projects, queued MP4 | 0.2.33 |
| 0039 | Air blast: air on/off from the program (M7/M9 or M100–M199, or always with the spindle), through the spindle or an external nozzle, chips blown off the part, "Blow the part clean at the end" with a time slider, optional visible cone; test mill pocket 1,560 → 0 chips on the block | 0.2.34 |
| 0043 | Surroundings stay put on a second import (note + Fit surroundings to the model); 4K MP4 encode peak memory 5.7 -> 1.7 GB | 0.2.35 |
| 0044 | Missing guide pictures: Way covers, Air blast, Labels, Pictures, Music | 0.2.37 |
| 0040 | Tool library: one list per project, 8 tool types from sizes or a STEP, Fusion/LinuxCNC tool files, every tool cuts with its own shape (also after M6), tool length offsets; fluted end mills read on their outer Ø (0037 problem 2) | 0.2.36 |
| 0049 | Tool library fixes: BT30 holder, G43 lengths tip to gauge line (Gauge length field), tool tip kept on the turning spindle's axis (0.065 mm → < 0.01), milling samples at the program's corners, manufacturer STEPs along X; owner tested on his PC 9 Nov: the different tools work with manual tool change | 0.2.38 |
| 0046 | Better materials: machining marks (ground, turned, milled, brushed), anodising sheen, cast iron (as cast, painted), hydraulic chrome rod, orange peel, rubber sheen, glass in EEVEE, Wear slider per group, CAD names, old projects get the new looks, material sheet + PC check line | 0.2.39 |
| 0053 | Safe updates: Update now refuses a colleague's (or a second window's) open project and waits for every Fresing Render of the install; a failed swap puts the old version back; a killed update no longer blocks Update now; two-window project lock; PC check line "Safe updates" (bug hunt rows 4, 12, 14, 19b–d) | 0.2.42 |

Details per version: `CHANGELOG.md`.
