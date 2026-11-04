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

- **Looks lane** (rules, materials, importer, 3 Looks): 0008 (done, 0.2.8) → 0010 (done, 0.2.9) → 0015 (can start)
- **Motion lane** (joints, poses, animation; `ui_motion.py` = panels 4 Motion, 6 Animation, 7 Render queue): 0011 (running) → 0012 → 0013 → 0014
- **Scene & Render lane** (`world.py`, `cameras.py`, `render.py`, panel 5 Scene & Render): 0016 (can start) → 0017 → 0018
- **Quality & delivery lane** (`.github/`, `installer/`, `tools/`, no app code): 0019 (can start) → 0020
- **Docs lane** (`docs/`, Help-menu link): 0021 (can start)

## Open and running

| # | Task | Who | Status | Branch / file |
| --- | --- | --- | --- | --- |
| 0015 | Looks lane: rule sets – one naming scheme per company, chosen per project, switchable | worker | open – can start | tasks/0015-rule-sets.md |
| 0011 | Motion lane: several joints on one subassembly, moves add up | worker | running | `task/0011-stacked-joints`, tasks/0011-stacked-joints.md |
| 0012 | Motion lane: couplings (gear, spindle, telescope, jaws) and motors ("run at 12 rpm") | worker | waiting (0011) | tasks/0012-couplings-motors.md |
| 0013 | Motion lane: hydraulic/electric cylinders – follow the arm, or drive it by stroke | worker | waiting (0012) | tasks/0013-cylinders.md |
| 0014 | Motion lane: mechanisms – scissor lifts, four-bar arms, other linkages (owner sends examples) | worker | waiting (0013) | tasks/0014-linkages.md |
| 0016 | Scene & Render lane: surroundings – sea, vessel deck, quayside, clean factory, CNC hall, assembly hall, warehouse; 360° photos with shadow floor; props for scale | worker | open – can start | tasks/0016-surroundings.md |
| 0017 | Scene & Render lane: studio lighting looks, standard camera views, focus by click, one-click turntable video | worker | waiting (0016) | tasks/0017-studio-cameras.md |
| 0018 | Scene & Render lane: video finishing – brand kit (logo), title and end card, captions from step names, 16:9 / 1:1 / 9:16 | worker | waiting (0017) | tasks/0018-video-finishing.md |
| 0019 | Quality lane: automatic tests on GitHub at every push, Linux and a Windows install + self-test | worker | open – can start | tasks/0019-github-tests.md |
| 0020 | Quality lane: updates from GitHub – "Update available" + one click in the app (replaces 0005) | worker | waiting (0019) | tasks/0020-updates-from-github.md |
| 0021 | Docs lane: user guide (Help menu, shipped with the installer) + tooltip style guide and check | worker | open – can start | tasks/0021-user-guide.md |
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

Details per version: `CHANGELOG.md`.
