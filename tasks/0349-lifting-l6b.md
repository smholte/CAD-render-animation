# 0349 – Lifting L6b: clearances along the path, reach envelope, exclusion zone, ground footprint + the makers' fixes

**Who:** worker · **Status:** running · **Branch:** `claude/cad-render-animation-0349-9y2i9w`
**Started by:** lead, 28 Nov 2026 (0348 done 0.2.269, 0327 done 0.2.261; 0180's L6 plan) · **Model:** Opus · effort High
**Area:** Lifting lane – `core/lifting_path.py`, `blender/lifting_path.py`, `core/lifting_reach.py`, `core/lifting.py`,
`blender/lifting*.py`, `ops_lifting*.py`, `ui_lifting*.py`, the makers (`ops_lifting_make.py`, `core/lifting_library.py`,
`lifting_rig*.py`, `setup_crane.py`, `fresing_render/lifting_model/`), the Lifting tour stops (own spots), their tests,
guide. `core/clash.py` / `blender/clash.py` **additive only** (a minimum-distance query, if the existing gap search can't
give it) – the Clash lane's own fixes (0378) wait for this task. **Not:** 0211's demo (after L7–L9).

## Part 1 – L6b (0180 report: the L6 plan, lines ~290–310; 0348's "What L6b needs")

- **Clearances along the path:** minimum distance boom / load / rigging ↔ obstacles at every moment (the clash check's
  gap search 0065 / 0110 as a distance); rows join `Checks.at` (the search already handles them); a threshold the user
  sets (default from a public guideline, cited), colour like C1–C6.
- **Reach envelope:** the chart curve as a range diagram (2D, in the plan / data box) + a 3D ring in the view.
- **Exclusion zone:** a ring / polygon on the ground round the lift (load path + margin), drawn and printable.
- **Ground footprint:** pads / tracks coloured by C5 / C6 pressure per moment (`Supports.items`).
- All in the printable plan where 0201 / 0348 put checks.

## Part 2 – the makers (do first: they change what Part 1 shows)

- **AT / KB samples' masses don't fit their sample charts** (0348): the charts' tipping assumed the carrier at the slew
  axis; the files' carrier CoG is its solid's centre (AT-40: 4.2 m forward, front pads at 2.7 m) → C5 red at 96 % chart
  use, an outrigger lifts off at 6 t. Fix in the makers (outriggers at the carrier's ends, or charts from the real CoGs).
- **CC-750 "Steep":** boom pendant bar L × rod L 4.9 mm in its own pose (0203) + a **clash test of every built-in pose**
  of every maker.
- **Library picture after Replace** stays the old one until a restart (0204: the cache keys on the path).

## Done when

- [ ] Part 2 fixed with tests; Part 1's four features with tests, tooltips, guide, tour stop, function list
- [ ] A lift on the Lifting set shows all four, and the printed plan has them (pictures in the report)
- [ ] Tests added / updated; full suite passes (also on GitHub)
- [ ] (UI) screenshots checked with tools/ui_screens.py; every new button has a tooltip; the user guide, PC-check line,
      tour stop and function-list entry follow the change (`since=` / `changed=`)
- [ ] (Windows-only code) reviewed by a helper that did not write it
- [ ] Report below filled in (incl. **Open points** and an **Owner's check** line when he should try something), merged,
      released (CLAUDE.md section 7)
- [ ] **Owner's check** line

**Running beside it (weekend 28–29 Nov):** 0371 Demo · 0355 / 0356 Assets · 0372 Welds · 0347 Machining · 0349
Lifting · 0353 Web 3D + House · 0373 guide-picture tool · 0374 cable-lay line · 0375 Sea · 0377 Start & windows ·
0379 PC check · findings-only 0380 / 0381. Shared files only additively, each in its own spot: `props.py`, `tour.py`,
`core/functions.py`, `tools/guide_screens.py` (0373 owns its start-up code), `pccheck/checks.py` / `heavy.py` (0379
owns the lines it names). Whoever merges second updates its branch to `main`; versions: CLAUDE.md section 7 step 0.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
