# 0374 – Cable-lay line: slack cables on a gutter, two cables over one sheave, set-down depth, the 7 s sea-cable solve, touch-down drift, drum layers, spline routes, copying cables

**Who:** worker · **Status:** done (0.2.271) · **Branch:** `task/0374-cable-lay-line-fixes`
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
| A | 0172's sweep: 3.5 m gutter 1 m over the seabed tipping 30° → flat, slack cable (`test_flex_followups_independent.py`) | Two answers: the leave point's fixed point **folds** – the one the cable lies at goes away and the next is at the far end (65° / 5.5 m in one step); also the blend of "down" and the lay direction cancelled where they point opposite ways, and a piled cable's "straight down" switched on at once | Rule over time in `hang_off_steady` (`_slide`): between neighbouring frames the leave point moves at most `SLIDE` 0.1 m + 4 x what the wheel / the length moved; wraps blended instead of directions, the cable's own wrap weighted by how much of it lies in the wheel's plane. (An ease of a piled cable's "straight down" was tried and taken out: the tester found it made moments flicker between two answers) | small |
| B | 0172's `test_KNOWN_FAULT_…_kinks` (49°) | The free bend is cut where it reaches the seabed, still pointing down; the piled hang beside it has no rounding | **Not done (open point)** – needs the piled hang rounded too (a reverse bend back to the seabed) | ~½ day |
| C | `test_paths_a` + a second rope drawn over SHEAVE 1 (`test_paths_shared.py`) | Both cables already shared the sheave's joint (it turns with the first); the second's note was a generic "follows … not this cable"; removing the first **deleted** the sheave's joint under the second | Plain note naming the other cable, red when both lie in one groove; `paths._hand_over` gives a shared joint to the other cable at Remove | small |
| D | – | `set_down_depth` left the public app with the vessel's equipment (task 0247): it is in the private kit only | **Not in this repository** (Private vessel: never) – a private-vessel task | – |
| E | 4,481-moment hang-off near the seabed (pure, `scratchpad bench`) | Every fixed-point round and bisection step went over all moments; `_bend_fit` a 64-step grid + bisection; the free bend's "settled" at 1e-10 rad took 80 rounds; `a_for_span` 128 rounds where ~56 reach full precision | Only unsettled moments each round; `_bend_fit` in closed form; settled at 1e-8 rad (40 nm on a 4 m gutter); `a_for_span` stops at 1e-14 | 2.33 s → 0.41 s |
| F | `test_catenary.py` `…touch_down_moves_with_the_heave…` | **Heave: physics** – with the cable's length and end fixed, 1 m of heave moves the touch-down 2.6–2.7 m (demo numbers: h 32.7 m, a 19.6 m); ±1 m in the demo = ±0.4 m heave. **Drift ~3 m aft over shots 1–8b:** with "Vessel speed: payout" the seabed moves by the paid-out length, while the length on deck between the speed joint and the hang-off can change (a carousel's leave point moving over its layers, the chute's path) – then less cable goes overboard than the seabed moves and the touch-down moves aft. Consistent with that setting; not verified on the private demo (not in this repository) | Kept; explained; a test pins the heave physics | – |
| G | 0174's note | Drum layers are at constant radius r1 + k·0.866 d; a layer laid the other way crosses the turns below twice a turn and would ride at 1.0 d there | **Not done (open point)** – changes 0080's tables, every drum test's numbers, the demo's drum | ~1 day |
| H | `test_paths_core.py` / `test_paths_independent.py` spline, coil, wave, tightening bend | `read_cable` refused a stretch that is neither straight nor one arc | Read as a row of short bends fitted from their own points (left out of the joint refit); the refit only recomputes a bend's own ties (a 30-bend route 32 s → 1–2 s). **Fleet kink: not done** – tried (an ease into the groove over ½ r), but 5 exactness checks of the read-back, the drum's helix and the sea hang-off rely on the arcs in their planes | spline: small |
| I | `test_copy.py` `…cable_read_from_cad_comes_along…` | Copy left cables, drums, tracks out (said in the window) | A CAD-read cable (its part, wheels and ends all in the copy) is read again on the copied parts after the copy has moved beside the original, with its drum; drawn / sea cables and tracks are still named | small |

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (worker session), 28 Nov 2026, branch `ccr-3cdfcf28-c4vcwe`. Version 0.2.271.

**What changed:** (rows: the Findings table above)
- **A** `core/catenary.py`: `hang_off_steady` slides the leave point round its wheel over time (`_slide`, `SLIDE` 0.1 m
  per frame + `SLIDE_FOLLOW` 4 x what the wheel and the length moved; `hang_off(psi_fixed=)` works out a slid moment);
  `_way_want` blends the wraps of "down" and the lay (weighted by how much of the cable's direction lies in the
  wheel's plane, beyond both ends the turn nearer the lay's end). 0172's `test_KNOWN_FAULT_tipping…` is a normal test
  with the brief's bounds (< 10°, < 0.5 m; now 2.2° / 0.31 m, was 51° / 4.5 m and 180° / 7.2 m).
- **C** `blender/paths.py`, `ui_paths.py`: `_sharing`, `_shared_note` (note `SHARED` …, red with "ONE groove"),
  `_hand_over` at Remove, notes of the other sharers worked out again after a Remove.
- **E** `core/catenary.py`: active moments only in the fixed point / bisection, `_bend_fit` closed form, `BEND_TOL`
  1e-8, `a_for_span` stops at `SPAN_TOL`; `_vec_rows` (a (3,) start with exactly 3 moments).
- **H** `core/paths.py`: `_not_arcs` / `_gradual(every=True)`; bends of such stretches `gradual` (left out of
  `_refine`); `_refine` recomputes only a bend's own ties.
- **I** `blender/copy.py`: `_cable_stays`, `_cables` (after the copy is placed), the joints of a cable read again not
  listed as left out, counts `cables` / `drums` in the window's line, roll-back of cables and drums.
- **F**: a test (`test_catenary.py`); D, G, B: not changed (table).
- Guide (Copy and paste, Cables and paths), function list (`structure.copy`, `offshore.cables` `changed=0.2.271`),
  PC-check line `place.copy_cable` (`MIN_LINES_FULL` 167), CHANGELOG 0.2.271.

**Independent tester** (subagent, wrote `tests/test_cable_lay_0374_independent.py` from the brief): 7 faults – a crash
with exactly 3 moments (`_rows` took a (3,) start for one row per moment), a batch flickering between "normal" and
"stretched" (136 jumps, 1 before; it also made a tilted gutter 3.3x slower – caused by the piled-cable ease, taken
out), a slid moment losing its free bend for one frame, a third cable's note naming the removed cable – all fixed
(their tests pass); three kept as `test_KNOWN_FAULT_…` (open points 1–3 below). Held: `_bend_fit` vs a dense scan
(3,000 cases), fast real moves followed exactly, frames with gaps / repeats / backwards, clean splines and coils,
refusals, three cables sharing a sheave, pasting twice, a copy of a subassembly, a drawn cable beside a copied one.

**Tested and measured** (4-core web machine, other jobs on it):
- Row E: 4,481-moment hang-off of a gutter lowered and tipped to the seabed with a heave: **2.33 s → 0.41 s**. The public
  sea test model's 4,501-frame cable: 0.56 s for its whole sea solve (before these changes). The private demo's second
  end (7 s) not measured here – at the same ratio it would be ~1.2 s (Owner's check).
- Row H: spline 300 points → 32 bends, 1.6 mm, 1.1 s; coil 3 turns → 43 bends, 4.6 mm, 1.7 s (before: refused; with
  the refusal simply dropped: 32 s each).
- Locally: test_catenary, test_catenary_bight, test_flex_followups_independent, test_paths_sea(_independent),
  test_paths_settle, test_paths_seabed_speed, test_paths_core, test_paths_independent, test_paths_shared (new),
  test_cable_lay_0374_independent (new), test_paths, test_paths_kept, test_flex_drawn, test_paths_moving,
  test_paths_swivel, test_paths_rollers, test_paths_update_same, test_spool, test_copy, test_copy_independent,
  test_functions; PC check lines place.copy_cable, place.copy, motion.paths (OK; paste with a cable 0.8 s).
- No UI block > 2 s on the public demo's cables: its only cable (the crane wire on its drum) is not a sea cable; the
  sea-cable solve that blocked is the one measured above. Not measured in the made demo.
- UI: the only visible change is a note line in the cables panel with two cables on one sheave – no screenshot taken.

**Open points / follow-up tasks:**
1. **The catenary's start still jumps 3–7 m in one frame where the free bend switches on or off** (the cable becomes
   "short", or the leave point comes up through the floor) while a gutter tips through flat – older than 0374 (5–13 m
   before). The leave point itself slides now. (`test_KNOWN_FAULT_tipping…_free_bend_switches`)
2. **Row H with noise:** a spline with 20 µm noise is read 3.3–5 mm off (brief ~2 mm), 0.1 mm noise is refused; a coil
   from a coarse faceted tube (rings every 3 cm) is refused (5.7 mm), every 1 cm reads at 1.3 mm. A CAD cable at
   Draft quality may still be refused – try Normal.
3. **Row H fleet-angle kink** (not done): an ease into the groove over ½ r was tried; it broke 5 exactness checks the
   read-back, the drum's helix and the sea hang-off rely on – needs those to compare with the eased drawing.
4. **Row G** drum layers riding over crossings / Lebus half-pitch nesting (not done, ~1 day: 0080's tables and every
   drum test's numbers change).
5. **Row B** the seabed corner (not done, ~½ day: the piled hang rounded too). Still `test_KNOWN_FAULT_…kinks` (49°).
6. **Row D** `set_down_depth` limits: in the private kit only – a "Private vessel: yes" task.
7. **Row F** drift: the likely cause (seabed follows the payout while the deck length changes) is not confirmed on the
   private demo; if wanted, a "Vessel speed: what goes overboard" setting.
8. Copy: drawn cables, cables into the sea and tracks are still left out (said in the window).

**Owner's check** (after Update now to 0.2.271):
1. Open your private cable-lay demo, change the sea state (5 Scene & Render) and watch the re-bake: it should not stop
   the window for more than ~2 s at a time.
2. Play shot 11 (the D tipped flat): the cable should slide off the gutter's end over a few frames, never jump.
3. In a project with a wire rope from a winch drum over sheaves: select the model's top row, **Ctrl+C**, **Ctrl+V** –
   the copy's window lists "1 cable, 1 drum"; in 4 Motion > Cables and paths the copy's rope "… (2)" runs by itself.

**GitHub runs:** 2 full runs of the branch. The first (06b3be2) was cancelled by me once the tester's faults were found
(nothing had failed before that). The second (60a923d, run 46139912580): green, 25.4 min under load, `main` fast-forwarded to
the branch. No version clash.

**Subagents:** one independent tester (wrote `tests/test_cable_lay_0374_independent.py` from the brief; resumed once after a
container restart). Its faults were fixed by the worker (not sent back).

**Branches to delete on GitHub:** `ccr-3cdfcf28-c4vcwe` (merged).
