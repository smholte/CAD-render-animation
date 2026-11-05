# Tasks

The shared to-do list of all chats working on Fresing Render. How tasks work: see
`CLAUDE.md` section 2. One file per larger task in `tasks/` (copy `tasks/TEMPLATE.md`).

**Who:** *lead* = the lead chat (plans only, no building or testing) · *worker* = a separate chat
the owner starts for this task; it finishes with merge and release (CLAUDE.md section 2) ·
*owner* = Sebastian (decision or test on his PC).

**Status:** open · running · waiting (on someone) · done

## Lanes

Tasks that touch the same files are in one **lane** and run one after the other; different
lanes run at the same time, each in its own worker chat. Shared files: `blender/props.py`, `blender/reimport.py`
(additive changes only) and `blender/ui.py` (each lane only its own panels); whoever merges second
updates its branch to `main`.

- **Looks lane** (rules, materials, importer, 3 Looks): 0008 (done, 0.2.8) → 0010 (done, 0.2.9) → 0015 (done, 0.2.13) → 0023 clean-up (done, 0.2.15) → 0024 decals (can start)
- **Motion lane** (joints, poses, animation; `ui_motion.py` = panels 4 Motion, 6 Animation, 7 Render queue): 0011 (done, 0.2.10) → 0012 (running) → 0013 cylinders → 0014 linkages → 0026 G-code
- **Scene & Render lane** (`world.py`, `cameras.py`, `render.py`, panel 5 Scene & Render): 0016 (done, 0.2.12) → 0017 (done, 0.2.17) → 0018 (can start) → 0025
- **Quality & delivery lane** (`.github/`, `installer/`, `tools/`, no app code): 0019 (done) → 0020 (done, 0.2.16); lane free
- **Docs lane** (`docs/`, Help-menu link): 0021 (done, 0.2.11); later tasks keep their own chapter up to date
- **Part library lane** (`core/part_types_data.py`, `core/part_types.py`, `core/fasteners.py`, their tests only): 0022 (done, 0.2.14) → 0030 fasteners in supplier notation (can start)
- **Machining lane** (new files `machining.py`, `chips.py`, `ui_machining.py`; sub-panel of 4 Motion in its own file): 0027 material removal (running) → 0028 chips → 0029 later

## Open and running

| # | Task | Who | Model | Status | Branch / file |
| --- | --- | --- | --- | --- | --- |
| 0024 | Looks lane: decals – logos, text, type plates, CE/warning stickers and pictures on the model itself | worker | Opus | open – can start | tasks/0024-decals.md |
| 0012 | Motion lane: couplings (gear, spindle, telescope, jaws) and motors ("run at 12 rpm") | worker | (running) | running | `task/0012-couplings-motors`, tasks/0012-couplings-motors.md |
| 0026 | Motion lane: G-code (LinuxCNC) drives the machine – X/Y/Z joints + spindle motor follow a CNC program, tool changes (ATC) | worker | Opus | waiting (0014) | tasks/0026-gcode-motion.md |
| 0027 | Machining lane: milling – pick bit and workpiece, material disappears where the bit cuts (viewport and renders) | worker | (running) | running | `task/0027-material-removal`, tasks/0027-material-removal.md |
| 0028 | Machining lane: chips per bit type and material (aluminium curls, steel, brass, plastic ribbons, wood dust) | worker | Opus | waiting (0027) | tasks/0028-chips.md |
| 0029 | Machining lane, later: milling without a CAM program (app-made toolpath), 4/5-axis | owner decides | Opus | later | tasks/0029-milling-later.md |
| 0030 | Part library lane: fasteners in supplier notation (Misumi set screws, WRENCHBOLT, BOLT5-20) | worker | Sonnet | open – can start | tasks/0030-fasteners-supplier-notation.md |
| 0013 | Motion lane: hydraulic/electric cylinders – follow the arm, or drive it by stroke | worker | Opus | waiting (0012) | tasks/0013-cylinders.md |
| 0014 | Motion lane: mechanisms – scissor lifts, four-bar arms, other linkages (owner sends examples) | worker | Opus | waiting (0013) | tasks/0014-linkages.md |
| 0018 | Scene & Render lane: video finishing – brand kit (logo), title and end card, captions from step names, watermark, 16:9 / 1:1 / 9:16 | worker | Sonnet | open – can start | tasks/0018-video-finishing.md |
| 0025 | Scene & Render lane: labels with lines pointing at parts, picture cards between steps, music under videos | worker | Sonnet | waiting (0018) | tasks/0025-callouts-pictures-music.md |
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

Details per version: `CHANGELOG.md`.
