# 0374 – Cable-lay line: slack cables on a gutter, two cables over one sheave, set-down depth, the 7 s sea-cable solve, touch-down drift, drum layers, spline routes, copying cables

**Who:** worker · **Status:** open – can start · **Branch:** `task/0374-cable-lay-line-fixes`
**Started by:** lead, 28 Nov 2026 (open points of 0078, 0172, 0173, 0174, 0192, 0293 – the owner's main goal is the
cable-lay line) · **Model:** Opus · effort High (+ an independent tester helper for the row fixes)
**Area:** Flex + Paths (cables): `blender/flex.py`, `flex_route.py`, `core/flex.py`, `core/flex_fit.py`,
`core/catenary.py`, `blender/paths*.py`, `core/paths.py`, `blender/spool.py`, `core/spool.py`, `tracks.py` /
`core/tracks.py`, `blender/copy.py` + `ops_copy.py` (only copying cables / drums / tracks), their tests, the cable tour
stops (own spots), the guide's cable parts. **Not:** `vessel_motion*`, `vessel_work.py`, `core/sea.py`, the sea in
`surroundings.py` (0375), hose / cable **kinds and looks** (`core/flex_kinds.py`, `cable_looks.py`, `ui_flex.py` –
0376 later), `demo.py` (0371), `clash.py`.
**Private vessel:** never in this repository. Use the public demo "Vessel in a wind park", the 0229 stand-ins or a small
test model made in the test. The owner checks his private demo afterwards (Owner's check line).

## Goal

The cable-lay features behave right in the cases the reports left open, and nothing blocks the window for more than
~2 s.

## Rows (read each report's "Open points")

- **A (0172 #1)** a slack cable on a gutter that tips through flat jumps its leave point in one step (held by a
  `test_KNOWN_FAULT_…`): a rule over time – keep the end it was at until the other is clearly better.
- **B (0172 #2)** the corner where a free bend is cut at the seabed (KNOWN_FAULT, 49° / 66° in the demo): round it if
  the piled hang can be rounded too; else say why.
- **C (0172 #3)** two cables over one sheave: make a small test model; make it work (both cables keep their own groove /
  order) or refuse plainly in the panel.
- **D (0172 #4)** `set_down_depth` returns `guess + 20 m` without the joint's limits.
- **E (0192)** one sea cable's catenary solve (`paths_sea.solve`) blocks ~7 s: faster, or in steps with progress – no
  block over ~2 s.
- **F (0173)** the touch-down drifts ~3 m aft over the shots and moves ±1 m with the heave: find whether it is physics
  (keep, explain) or an error (fix).
- **G (0174)** drum layers cross the turns below at 0.866 d: let a layer ride up over each crossing (and a Lebus layer
  nest half a pitch over the one below) – it changes 0080's tables; update their tests honestly.
- **H (0078)** a route with a helix / spline stretch is refused (Inventor sweeps have them): accept it; a fleet angle
  shows as a kink where the cable meets a sheave: make it smooth.
- **I (0293)** cables, drums and tracks are not copied by Copy: copy them with their joints, carriers and spools, or
  say plainly in the copy window what was left.

## How

1. **Findings first, in this file** (no stop): one row each – repeat case on a public model, cause, fix, cost.
2. Fix in the order A, C, D, E, F, H, I, G, B. If the task grows past about a day of work, merge what is done and
   list the rest as open points – don't leave a half-done row.
3. KNOWN_FAULT tests that are fixed become normal tests; nothing loosened.

## Done when

- [ ] Findings table; every row fixed or explained with the reason
- [ ] No UI block over ~2 s on the public demo's cables (measured, in the report)
- [ ] Tests added / updated; full suite passes (also on GitHub)
- [ ] (UI) screenshots checked with tools/ui_screens.py; every new button has a tooltip; the user guide, PC-check line,
      tour stop and function-list entry follow the change (`since=` / `changed=`)
- [ ] (Windows-only code) reviewed by a helper that did not write it
- [ ] Report below filled in (incl. **Open points** and an **Owner's check** line when he should try something), merged,
      released (CLAUDE.md section 7)

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
