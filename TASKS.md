# Tasks

The shared to-do list of all chats working on Fresing Render. How tasks work: see
`CLAUDE.md` section 2. One file per larger task in `tasks/` (copy `tasks/TEMPLATE.md`).

**Who:** *lead* = the lead chat · *worker* = a separate chat the owner starts for this task ·
*owner* = Sebastian (decision or test on his PC).

**Status:** open · running · waiting (on someone) · done

## Open and running

| # | Task | Who | Status | Branch / file |
| --- | --- | --- | --- | --- |
| 0001 | Owner's list of interface wishes: compare with what 0.2.5 already changed, then do the rest | lead | waiting (owner's list) | – |
| 0002 | Measure on the owner's PC: EGR import time (0.2.3+), animation time per frame with Time test (0.2.4+), EEVEE speed on the RTX 3090 | owner | open | – |
| 0003 | Rest of the first Windows test: own Inventor STEP + still, joint on a real pivot | owner | open | – |
| 0004 | Decide where renders go: "Renders" next to the project (now) or Pictures\Fresing Render\<project> | owner | open | – |
| 0005 | Choose where the update server lives (see docs/UPDATES.md) | owner | open | – |
| 0006 | Phase 3, when projects need it: motion paths, link loops, several machines in one scene, props, clash warning, project templates | worker (per feature) | open | – |
| 0007 | Idea, low priority: faster array extraction for very big single parts (EGR "COMPOUND", 39 % of all triangles, sets the import floor on many cores) | lead | open | – |

## Done

| # | Task | Version |
| --- | --- | --- |
| – | Phase 1 (stills), phase 2 (motion), installer, self-test | 0.1.0 – 0.2.2 |
| – | STEP import on all cores | 0.2.3 |
| – | Faster animation renders, Time test, Show in folder | 0.2.4 |
| – | Side panel redesigned section by section | 0.2.5 |
| – | Code on GitHub; CLAUDE.md, TASKS.md, CHANGELOG.md; way of working agreed | – |

Details per version: `CHANGELOG.md`.
