# Tasks

The shared to-do list of all chats working on Fresing Render. How tasks work: see
`CLAUDE.md` section 2. One file per larger task in `tasks/` (copy `tasks/TEMPLATE.md`).

**Who:** *lead* = the lead chat (plans only, no building or testing) · *worker* = a separate chat
the owner starts for this task; it finishes with merge and release (CLAUDE.md section 2) ·
*owner* = Sebastian (decision or test on his PC).

**Status:** open · running · waiting (on someone) · done

## Lanes

Tasks that touch the same files are in one **lane** and run one after the other; the two lanes
can run at the same time, in two worker chats. Shared files (`blender/props.py`,
`blender/reimport.py`): additive changes only; whoever merges second updates its branch to `main`.

- **Looks lane** (rules, materials, importer, 3 Looks): 0008 (running) → 0010 → 0015
- **Motion lane** (joints, poses, animation, 5 Motion): 0011 (running) → 0012 → 0013 → 0014

## Open and running

| # | Task | Who | Status | Branch / file |
| --- | --- | --- | --- | --- |
| 0008 | Looks lane: automatic materials for most parts: large part-type library + CAD material names from the STEP (owner's points 17–18) | worker | running | `task/0008-part-type-rules`, tasks/0008-part-type-rules.md |
| 0010 | Looks lane: paint single faces; faces painted in CAD come in painted (owner's point 4) | worker | waiting (0008) | tasks/0010-face-painting.md |
| 0015 | Looks lane: rule sets – one naming scheme per company, chosen per project, switchable | worker | waiting (0010) | tasks/0015-rule-sets.md |
| 0011 | Motion lane: several joints on one subassembly, moves add up | worker | running | `task/0011-stacked-joints`, tasks/0011-stacked-joints.md |
| 0012 | Motion lane: couplings (gear, spindle, telescope, jaws) and motors ("run at 12 rpm") | worker | waiting (0011) | tasks/0012-couplings-motors.md |
| 0013 | Motion lane: hydraulic/electric cylinders – follow the arm, or drive it by stroke | worker | waiting (0012) | tasks/0013-cylinders.md |
| 0014 | Motion lane: mechanisms – scissor lifts, four-bar arms, other linkages (owner sends examples) | worker | waiting (0013) | tasks/0014-linkages.md |
| 0001 | Owner's list of interface wishes (first part became 0008–0010; more may follow) | lead | open | – |
| 0002 | Measure on the owner's PC: EGR import time (0.2.3+), animation time per frame with Time test (0.2.4+), EEVEE speed on the RTX 3090 | owner | open | – |
| 0003 | Rest of the first Windows test: own Inventor STEP + still, joint on a real pivot | owner | open | – |
| 0004 | Decide where renders go: "Renders" next to the project (now) or Pictures\Fresing Render\<project> | owner | open | – |
| 0005 | Choose where the update server lives (see docs/UPDATES.md) | owner | open | – |
| 0006 | Phase 3, when projects need it: motion paths, several machines in one scene, props, clash warning, project templates | worker (per feature) | open | – |

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

Details per version: `CHANGELOG.md`.
