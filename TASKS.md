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

- **Looks lane** (rules, materials, importer, 3 Looks): 0008 (done, 0.2.8) → 0010 (done, 0.2.9) → 0015 (done, 0.2.13) → 0023 clean-up (running)
- **Motion lane** (joints, poses, animation; `ui_motion.py` = panels 4 Motion, 6 Animation, 7 Render queue): 0011 (done, 0.2.10) → 0012 (running) → 0013 → 0014
- **Scene & Render lane** (`world.py`, `cameras.py`, `render.py`, panel 5 Scene & Render): 0016 (done, 0.2.12) → 0017 (running) → 0018
- **Quality & delivery lane** (`.github/`, `installer/`, `tools/`, no app code): 0019 (done) → 0020 (running)
- **Docs lane** (`docs/`, Help-menu link): 0021 (done, 0.2.11); later tasks keep their own chapter up to date
- **Part library lane** (`core/part_types_data.py`, `core/part_types.py`, their tests only): 0022 (running)

## Open and running

| # | Task | Who | Status | Branch / file |
| --- | --- | --- | --- | --- |
| 0022 | Part library lane: more parts sorted on import – supplier catalogue codes (Misumi and others); owner attaches the EGR file | worker | running | `task/0022-more-supplier-codes`, tasks/0022-more-supplier-codes.md |
| 0023 | Looks lane: clean-up – tooltips of panels 1–3, "1 face sets" plural, guide chapters 1–3 current | worker | running | `task/0023-looks-clean-up`, tasks/0023-looks-clean-up.md |
| 0012 | Motion lane: couplings (gear, spindle, telescope, jaws) and motors ("run at 12 rpm") | worker | running | `task/0012-couplings-motors`, tasks/0012-couplings-motors.md |
| 0013 | Motion lane: hydraulic/electric cylinders – follow the arm, or drive it by stroke | worker | waiting (0012) | tasks/0013-cylinders.md |
| 0014 | Motion lane: mechanisms – scissor lifts, four-bar arms, other linkages (owner sends examples) | worker | waiting (0013) | tasks/0014-linkages.md |
| 0017 | Scene & Render lane: studio lighting looks, standard camera views, focus by click, one-click turntable video | worker | running | `task/0017-studio-cameras`, tasks/0017-studio-cameras.md |
| 0018 | Scene & Render lane: video finishing – brand kit (logo), title and end card, captions from step names, 16:9 / 1:1 / 9:16 | worker | waiting (0017) | tasks/0018-video-finishing.md |
| 0020 | Quality lane: updates from GitHub – "Update available" + one click in the app (replaces 0005) | worker | running | `task/0020-updates-from-github`, tasks/0020-updates-from-github.md |
| 0001 | Owner's list of interface wishes (first part became 0008–0010; more may follow) | lead | open | – |
| 0002 | Measure on the owner's PC: EGR import time (0.2.3+), animation time per frame with Time test (0.2.4+), EEVEE speed on the RTX 3090 | owner | open | – |
| 0003 | Rest of the first Windows test: own Inventor STEP + still, joint on a real pivot | owner | open | – |
| 0004 | Decide where renders go: "Renders" next to the project (now) or Pictures\Fresing Render\<project> | owner | open | – |
| 0006 | Phase 3, when projects need it: motion paths, several machines in one scene, clash warning, project templates | worker (per feature) | open | – |

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
| 0021 | User guide (Help > Fresing Render user guide, Start menu, next to Install.bat); tooltip style guide, tooltip check and the list of 93 tooltips for the lanes (`docs/TOOLTIPS-TODO.md`) | 0.2.11 |

Details per version: `CHANGELOG.md`.
