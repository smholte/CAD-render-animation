# Tasks

The shared to-do list of all chats working on Fresing Render. How tasks work: see
`CLAUDE.md` section 2. One file per larger task in `tasks/` (copy `tasks/TEMPLATE.md`).

**Who:** *lead* = the lead chat (plans only, no building or testing) · *worker* = a separate chat
the owner starts for this task; it finishes with merge and release (CLAUDE.md section 2) ·
*owner* = Sebastian (decision or test on his PC).

**Status:** open · running · waiting (on someone) · done

## Open and running

| # | Task | Who | Status | Branch / file |
| --- | --- | --- | --- | --- |
| 0001 | Owner's list of interface wishes (first part became 0008–0010; more may follow) | lead | open | – |
| 0002 | Measure on the owner's PC: EGR import time (0.2.3+), animation time per frame with Time test (0.2.4+), EEVEE speed on the RTX 3090 | owner | open | – |
| 0003 | Rest of the first Windows test: own Inventor STEP + still, joint on a real pivot | owner | open | – |
| 0004 | Decide where renders go: "Renders" next to the project (now) or Pictures\Fresing Render\<project> | owner | open | – |
| 0005 | Choose where the update server lives (see docs/UPDATES.md) | owner | open | – |
| 0006 | Phase 3, when projects need it: motion paths, link loops, several machines in one scene, props, clash warning, project templates | worker (per feature) | open | – |
| 0008 | Automatic materials for most parts: large part-type library + CAD material names from the STEP (owner's points 17–18) | worker | open | `task/0008-part-type-rules`, tasks/0008-part-type-rules.md |
| 0010 | Paint single faces of a part (owner's point 4); faces painted in CAD come in painted – starts when 0008 is merged (same files) | worker | waiting (0008) | tasks/0010-face-painting.md |
| – | Owner's ideas of 4 Nov under discussion: several joints on one part (stacked moves), rule sets per machine (naming schemes), couplings/constraints between joints | lead | planning | – |

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
