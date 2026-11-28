# 0374 – Cable-lay line: slack cables on a gutter, two cables over one sheave, set-down depth, the 7 s sea-cable solve, touch-down drift, drum layers, spline routes, copying cables

**Who:** worker · **Status:** running · **Branch:** `task/0374-cable-lay-line-fixes`
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

## Findings (worker, 28 Nov 2026)

| Row | Repeat case (public) | Cause | Fix | Cost |
| --- | --- | --- | --- | --- |
| A | 0172's sweep: 3.5 m gutter 1 m over the seabed tipping 30° → flat, slack cable (`test_flex_followups_independent.py`) | Two answers: the leave point's fixed point **folds** – the one the cable lies at goes away and the next is at the far end (65° / 5.5 m in one step); also the blend of "down" and the lay direction cancelled where they point opposite ways, and a piled cable's "straight down" switched on at once | Rule over time in `hang_off_steady` (`_slide`): between neighbouring frames the leave point moves at most `SLIDE` 0.1 m + 4 x what the wheel / the length moved; wraps blended instead of directions, the cable's own wrap weighted by how much of it lies in the wheel's plane; "straight down" eased in over the first metre piled | small |
| B | 0172's `test_KNOWN_FAULT_…_kinks` (49°) | The free bend is cut where it reaches the seabed, still pointing down; the piled hang beside it has no rounding | **Not done (open point)** – needs the piled hang rounded too (a reverse bend back to the seabed) | ~½ day |
| C | `test_paths_a` + a second rope drawn over SHEAVE 1 (`test_paths_shared.py`) | Both cables already shared the sheave's joint (it turns with the first); the second's note was a generic "follows … not this cable"; removing the first **deleted** the sheave's joint under the second | Plain note naming the other cable, red when both lie in one groove; `paths._hand_over` gives a shared joint to the other cable at Remove | small |
| D | – | `set_down_depth` left the public app with the vessel's equipment (task 0247): it is in the private kit only | **Not in this repository** (Private vessel: never) – a private-vessel task | – |
| E | 4,481-moment hang-off near the seabed (pure, `scratchpad bench`) | Every fixed-point round and bisection step went over all moments; `_bend_fit` a 64-step grid + bisection; the free bend's "settled" at 1e-10 rad took 80 rounds; `a_for_span` 128 rounds where ~56 reach full precision | Only unsettled moments each round; `_bend_fit` in closed form; settled at 1e-8 rad (40 nm on a 4 m gutter); `a_for_span` stops at 1e-14 | 2.33 s → 0.57 s |
| F | `test_catenary.py` `…touch_down_moves_with_the_heave…` | **Heave: physics** – with the cable's length and end fixed, 1 m of heave moves the touch-down 2.6–2.7 m (demo numbers: h 32.7 m, a 19.6 m); ±1 m in the demo = ±0.4 m heave. **Drift ~3 m aft over shots 1–8b:** with "Vessel speed: payout" the seabed moves by the paid-out length, while the length on deck between the speed joint and the hang-off can change (a carousel's leave point moving over its layers, the chute's path) – then less cable goes overboard than the seabed moves and the touch-down moves aft. Consistent with that setting; not verified on the private demo (not in this repository) | Kept; explained; a test pins the heave physics | – |
| G | 0174's note | Drum layers are at constant radius r1 + k·0.866 d; a layer laid the other way crosses the turns below twice a turn and would ride at 1.0 d there | **Not done (open point)** – changes 0080's tables, every drum test's numbers, the demo's drum | ~1 day |
| H | `test_paths_core.py` / `test_paths_independent.py` spline, coil, wave, tightening bend | `read_cable` refused a stretch that is neither straight nor one arc | Read as a row of short bends fitted from their own points (left out of the joint refit); the refit only recomputes a bend's own ties (a 30-bend route 32 s → 1–2 s). **Fleet kink: not done** – tried (an ease into the groove over ½ r), but 5 exactness checks of the read-back, the drum's helix and the sea hang-off rely on the arcs in their planes | spline: small |
| I | `test_copy.py` `…cable_read_from_cad_comes_along…` | Copy left cables, drums, tracks out (said in the window) | A CAD-read cable (its part, wheels and ends all in the copy) is read again on the copied parts after the copy has moved beside the original, with its drum; drawn / sea cables and tracks are still named | small |

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
