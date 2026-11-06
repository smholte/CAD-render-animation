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

- **Looks lane** (rules, materials, importer, 3 Looks): 0008 (done, 0.2.8) → 0010 (done, 0.2.9) → 0015 (done, 0.2.13) → 0023 clean-up (done, 0.2.15) → 0024 decals (done, 0.2.21); lane free
- **Motion lane** (joints, poses, animation; `ui_motion.py` = panels 4 Motion, 6 Animation, 7 Render queue): 0011 (done, 0.2.10) → 0012 (done, 0.2.18) → 0013 (done, 0.2.25) → 0014 (done, 0.2.26) → 0026 G-code (done, 0.2.30); lane free
- **Scene & Render lane** (`world.py`, `cameras.py`, `render.py`, panel 5 Scene & Render): 0016 (done, 0.2.12) → 0017 (done, 0.2.17) → 0018 (done, 0.2.23) → 0025 (done, 0.2.27); lane free
- **Quality & delivery lane** (`.github/`, `installer/`, `tools/`, no app code): 0019 (done) → 0020 (done, 0.2.16) → 0036 faster automatic tests (done, 0.2.31) → 0031 Claude Code set-up (brief to write)
- **Docs lane** (`docs/`, Help-menu link): 0021 (done, 0.2.11); later tasks keep their own chapter up to date
- **Part library lane** (`core/part_types_data.py`, `core/part_types.py`, `core/fasteners.py`, their tests only): 0022 (done, 0.2.14) → 0030 fasteners in supplier notation (done, 0.2.20); lane free
- **PC check lane** (new `fresing_render/pccheck/`; additive: installer shortcut, Help-menu item, CI steps): 0032 PC check (done, 0.2.24) → 0033 Heavy mode (round 1 released 0.2.29, round 2 waits for the owner's Heavy run)
- **Machining lane** (new files `machining.py`, `ops_machining.py`, `chips.py`, `ui_machining.py`; sub-panel of 4 Motion in its own file): 0027 material removal (done, 0.2.19) → 0028 chips (done, 0.2.22) → 0029 later (owner decides); 0034 way covers (done, 0.2.28)

## Open and running

| # | Task | Who | Model · effort | Status | Branch / file |
| --- | --- | --- | --- | --- | --- |
| 0029 | Machining lane, later: milling without a CAM program (app-made toolpath), 4/5-axis | owner decides | Opus · High | later | tasks/0029-milling-later.md |
| 0033 | PC check lane: Heavy mode – big generated scene (~3,000 parts), 4K stills, a 10 s animation rendered fully with a contact sheet, milling+chips at length, peak memory; scaled-down form runs on GitHub; two rounds (owner runs it in between) | worker | Sonnet · Medium | running – round 1 released (0.2.29); round 2 after the owner's run | tasks/0033-pccheck-heavy.md |
| 0035 | Machining lane, follow-up to 0034 (small): (1) way-cover guide chapter gets its panel picture and a render of the test model (`tools/guide_screens.py`, needs the real Blender); (2) accept a cover section that sits on the carriage itself (parts already moved by the axis joint) as the last section, share 1, without a new joint; (3) a test with 8 sections in Blender. Brief to write | lead writes the brief, then worker | Sonnet · Low | open – brief to write | – |
| 0031 | Quality & delivery lane: Claude Code on the web – stored set-up for every session (venv, Blender 5.2.3, xvfb, ImageMagick, download.blender.org allowed), measure set-up time and usage before/after, CLAUDE.md section 4 | lead writes the brief, then worker | Sonnet · Medium | open – brief to write | – |
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
| 0013 | Cylinders: barrel turns about its pin, rod's eye stays on its pin when the arm moves (constraints, scripts off); Drives the arm: set the stroke, the arm turns (law of cosines, slide too); closed length and stroke read from the parts; telescopic stages; Move cylinder step; "Show joint arrows" NameError fixed | 0.2.25 |
| 0025 | Labels with lines that stay on their (moving) parts, picture cards over videos (full screen or corner), music under MP4 videos with fades; PC-check line | 0.2.27 |
| 0014 | Mechanisms: scissor lifts (height, rollers), four-bar and parallel arms, slider-cranks, other planar linkages; pins found from shared holes; exact solver that never flips; drive by angle, height or a cylinder; Lift height step; kept through model updates. Owner's example files still to try | 0.2.26 |
| 0034 | Way covers: telescopic covers follow one slide axis; sections picked (several parts each), travel shared out (500 mm / 5 sections = 100 mm each), Housing counts (0/125/250/375/500), Flip, Read from the axis; every section is a slide joint that follows the axis, so poses, steps, G-code and the render queue move them; the owner's 5-section way-cover STEP is a test model | 0.2.28 |
| 0026 | G-code drives the machine: LinuxCNC reader (arcs in all planes, cycles, offsets, parameters, o-words), 4 Motion > CNC machine (axes, spindle, tool, work zero, tools), step Run G-code program (exact path, spindle, tool changes with tool-changer animation, toolpath); joints no longer snap to CAD within 0.1 mm | 0.2.30 |
| 0036 | Faster automatic tests: precheck first (version clash in ~1 min), pytest and real app as parallel jobs (full run 11–14 min, was 35–50), a push to `main` whose tree already ran green releases without repeating the tests (1.7 min), docs-only pushes ~2 min | 0.2.31 |

Details per version: `CHANGELOG.md`.
