# 0348 – Lifting L6a: the lift path and live checks with the worst moment

**Who:** worker · **Status:** done (0.2.269) · **Branch:** `task/0348-lifting-l6a-lift-path`
**Started by:** lead, 25 Nov 2026 (Lifting lane: L1 0182 … L5 0232 → **L6a** → L6b = 0349 → L7 printed plan) ·
**Model:** Opus · effort High · Claude Code on the web, environment "CAD-render-animation"
**Area:** Lifting lane – new `blender/lifting_path.py` and `core/lifting_path.py` (pure Python: steps, evaluation along
the path, worst-moment search), additions to `ops_lifting.py`, `ui_lifting.py`, `core/lifting.py` (new check rows only),
`core/functions.py` (additive), tests, user guide, CHANGELOG. `pccheck/checks.py`: **add your lines only** – 0333 is
changing that file now; merge `main` first before you release.
**Not:** `blender/handlers.py`, `joints.py`, `logic.py`, `vessel_motion.py` (0326 running – read them, don't change them;
your own frame handler lives in `lifting_path.py`); `core/clash.py`, `blender/clash.py` (0327 running – clearances are
L6b); reach envelope, exclusion zone, ground footprint drawing (L6b); the printed plan (L7); offshore / vessel motion (L9).

## Goal

The lifting plan comes alive: the user sets a pick point and a set-down point, the app makes the lift as steps the user
can change, and **every check is worked out along the whole lift** with its **worst moment** and a "Go there" button.
A sales person sees green / amber / red; an engineer sees the numbers behind them.

## Background (read only the parts named)

- `tasks/0180-lifting-plans-study.md`: section 3 "The checks" (C1–C9, status words, worst moment), section 5 step 5
  "Lift path" and step 6 "Checks", section 9 row L6 (risk: per-frame cost on long paths → evaluate at keys +
  worst-case search).
- `tasks/0201-lifting-place-and-cog.md` and `tasks/0214-lifting-with-the-rest.md` – their "Open points": a crane with
  **more counterweight than the chart picked** is not checked for backward stability; the outrigger chart reads the
  beams only – **the jacks need not be down** (a "set up" check).
- `tasks/0232-lifting-l5-rigging-falls.md` – the hang solver, Hang on the hook / Set down / Remove; its "Open points".
- `tasks/0337-lifting-with-remove.md` – the plan list and Remove.
- `core/lifting_reach.py` – Hook to here (`hook_to`) and `Kinematics.transforms` (many joint values at once).
- The 0173 lay-data box (find it in the cable-lay code) – the pattern for the lift data box.

## What to do

1. **Lift path** (panel step "Lift path"): pick point = where the load hangs now; set-down point by clicking (hover
   picker of 0088) or typing. The app proposes steps – hoist clear, slew, luff / telescope, travel (crawlers), lower –
   using `hook_to`, as the app's ordinary animation steps (so 0330's "keeps the user's keys" holds and the user can drag
   them in the timeline). Or the user picks existing poses / steps. Clearance height for "hoist clear" as a number.
2. **Checks along the path:** every check that applies (C1 crane use, C2–C4 rigging from L5's hang solver, C5 outriggers
   at the slew angle, C6 tracks, …) evaluated at the keys and then a **worst-case search** between keys (not every frame
   blindly – measure both on a long path and report). A table: check, worst value, limit, use %, status colour, frame,
   **Go there**. Grey = not checked, with the reason in words.
3. **The two 0201 open points:** counterweight above the chart's → say so in the check's words and either check backward
   stability from the masses / CoGs we have or show it grey with the reason; outriggers → a "Set up" check (beams out to
   the chart's spread and jacks down) that turns red when the crane lifts with jacks up.
4. **Live while dragging:** moving a joint or the load updates the readout (use-% bar near the hook as today) without
   making the drag slower – measure the drag time with and without the plan (0326 is making drag faster: don't add it
   back).
5. **Lift data box** in renders and videos (load, radius, use %, the worst status so far), the 0173 pattern, off by
   default, one tick.
6. **Words for all levels:** every status line in plain words ("Crane at 82 % of its chart at 23.4 m – amber, your limit is
   75 %"), tooltips on every button, the disclaimer of 0180 section 8 unchanged.
7. **Tests:** `core/lifting_path.py` with hand-worked cases (worst moment found between keys, a path that turns red
   mid-slew, jacks up, counterweight above chart); one Blender test on an AT and a CC crane from the library; an old
   lifting project (0.2.192+) opens and works with no path. PC-check line (Full) + a test-tour stop in the Lifting
   learning set (0231). Guide section + picture, function list entry with `since=`, CHANGELOG.

## Design (worker, 25 Nov)

**core/lifting_path.py** (no Blender, NumPy):
- `Supports(data)`: the crane's masses + CoGs from its file (`mass`, `cog`, `rig.groups[g].moves_with`), the plan's
  counterweight instead of the file's, the boom's CoG moved out by half the telescope's run (estimate, said in words),
  the hook block at the hook and the load plumb under it. `outriggers(...)` → C5 (`lifting.outriggers`, a = file's a,
  b = half the spread the pose gives, mats = file pad or the plan's mat, allowable kPa entered or not checked);
  `tracks(...)` → C6 (`lifting.tracks`, the lower's frame: travel taken out). `set_up(...)` → "Set up": beams out to the
  spread the chart is picked for, jacks at their down end (red with jacks up). `backward(...)` → "Backward stability"
  only when the plan carries more counterweight than the chart: the unloaded crane's CoG keeps 15 % of the base
  (`lifting_model.charts.BACK_RESERVE`) inside; else grey "the chart covers it".
- `Moment` = joint values (deg / mm, by the file's names) → `Checks.at(values)`: one `Row` per check (id, title, use,
  status, value / limit text, plain words, frame). Rigging C2–C4 from the hang (constant while hung; grey when not hung),
  C10 line pull, C1 from `lifting_reach.readout`.
- `search(at, times, keys, inner=3, rounds=14)`: evaluate at the keys, `inner` points in each gap, then golden-section on
  each check's (rank, use) round its 2 best local peaks → per check the worst moment (time, row). `every(at, times)`
  = the blind frame-by-frame reference (measured, report).
- `propose(rig, values, pick, target, clearance, ...)` → steps (kind, label, {joint: value}, seconds): hoist clear, slew,
  luff / telescope (+ hoist so the hook keeps its height), travel (crawler, only when the target is out of reach from
  where it stands), lower. Durations from plain speeds (2–12 s per step).
- `status_line(row)`: "Crane at 82 % of its chart at 23.4 m – amber, your limit is 75 %."

**blender/lifting_path.py**: the plan's path (`FRLifting.path_*` additive in props.py): Propose = the steps as ordinary
"Move joint" steps in an animation "Lift <load>" (tagged `fr_lift_path` on the block's name prefix "Lift ·"), Use an
animation (the user's own poses / steps), Check along the path (Build if needed, read the crane's driven joints'
F-curves, search, result JSON on the plan), Go there (frame of a row), live rows for the current pose (cached on the
readout's key, throttled to ≤ 10 / s while the pose changes), a POST_PIXEL use-% bar beside the hook, the lift data box
(a label with live fields on the hook block, `core/callouts` fields `lift_*`, one tick).
UI: sub-panel "Lift path & checks" after Hook & capacity (`ui_lifting.py`, `core/places.py`). No subagents for writing;
an independent tester (subagent) for `core/lifting_path.py` from this brief.

## Done when

- [x] Pick → set-down proposed as editable steps; poses / own steps usable instead
- [x] Every applying check worked out along the path, worst moment + Go there; grey with reasons
- [x] Counterweight-above-chart and jacks-up cases handled and tested
- [x] Drag time with a plan measured, no slower than without (± 5 %)
- [x] Lift data box (one tick)
- [x] Tests added; full suite passes; GitHub run green
- [x] PC-check line, tour stop, guide, function list, tooltips, CHANGELOG
- [x] 2–3 pictures (the checks table, a red moment, the data box in a render) in `tasks/0348_page/` for the owner
- [x] Report below filled in (incl. "what L6b needs"), merged, released; the owner's check line

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (Opus · High), 25 Nov 2026 · released as **0.2.269**

**What changed:**
- `core/lifting_path.py` (new, no Blender): `Checks.at(values)` = one row per check at one moment – C1 crane use
  (readout), C10 line pull, **Set-up** (beams out to the chart's spread, **jacks down** – jacks up = red), **C5**
  outriggers + mats / **C6** tracks from the file's masses + CoGs (`rig.groups[*].moves_with`, the plan's counterweight,
  boom CoG out by half the telescope run, load plumb under the hook, crawler travel taken out), **Backward stability**
  only when the plan carries more counterweight than the chart (unloaded CoG keeps 15 % of the base inside, the makers'
  `BACK_RESERVE`; else grey "the chart covers it"; C1's words say so too), C2–C4 from the hang (one row per check, the
  worst item). `search` = keys + grid (≥ every 0.2 s in the app) + golden-section round each check's 2 highest peaks;
  `every` = frame-by-frame reference. `propose` = hoist clear / slew / luff-telescope in 6 pieces (hoist keeps the hook
  at the clearance height) / travel (crawler, only when out of reach) / lower; straight-down lifts only hoist; a hoist at
  its top lets the boom raise the load clear. Words: "Crane at 82 % of its chart at 23.4 m – amber, your limit is 75 %."
- `blender/lifting_path.py` (new): Propose → "Move joint" steps of an animation "Lift <load>" (names "Lift · …"), Use an
  animation (own poses / steps), Check along the path (Build, read the crane's leader joints' F-curves, search; JSON on
  the plan; out of date when path / crane / load / ground change), Go there, live rows (looked at ≤ 5× / s, worked out
  only on change), use bar beside the hook (POST_PIXEL), **lift data box** = a label with live fields on the hook block
  (`core/callouts` fields `load`, `radius`, `use`, `worst`, `hook`; string values allowed).
- `ops_lifting.py`: Set-down point… (click, as Hook to here), Propose again, Use an animation, Check along the path,
  Go there. `ui_lifting.py`: sub-panel **Lift path & checks** (`core/places.py`). `props.py` (additive): `FRLifting.path_*`,
  `set_down`, `allowable_kpa`, `mat_size`, `data_box`. `lifting.py`: registers / forgets the new module.
- PC-check line `lifting.path` (Full; MIN_LINES_FULL 161), tour stop `lifting_path` in the Lifting set (MIN_LINES_TOUR /
  MIN_CHECKS tour 120; set `changed` 0.2.269, versions re-recorded), function entries `lifting.path`, `lifting.data_box`,
  guide section "Lift path & checks" + `panel_8_lifting_path.png`, CHANGELOG. `tools/guide_screens.py`: the lifting
  mode's rigging step was broken since the test crane got 5× bigger (legs too short) – fixed, plus the path picture.

**Tested and measured** (4-core web machine):
- `tests/test_lifting_path.py` 17 hand cases (study C5 numbers along a slew: peak 28.341 t at 46.685° between keys 0° /
  90°, found by the search; with 27 t allowed the keys are amber and the middle red; jacks up; beams in; counterweight
  40 t over a 30 t chart; crawler tracks; propose on AT / CC (travel) / KB). **Independent tester (subagent, did not see
  my tests): 86 tests**, found 4 faults – a red band between grid points missed, a straight-down lift re-luffed, the hook
  dipped 0.36–1.09 m below the clearance during the combined luff move, a hoist at its top dropped the clearance – all
  fixed (two of its tests adjusted: luff pieces are short by design; the grid spacing is given). 103 core tests pass.
- `tests/test_lifting_path_app.py` (Blender module, 6 tests): AT-40 + skid hung – the load ends on the clicked point
  (< 1 cm), every check's worst ≥ the frame-by-frame worst; CC-100 tracks; own animation as path; jacks up + counterweight
  over the chart; data box text; out of date after a change; forbidden words.
- **Search vs every frame** (AT-40 skid lift, 814 frames): 198 moments in 175 ms vs 814 frames in 710 ms, same worst
  values (PC-check line on the web machine: 212 ms vs 736 ms).
- **Drag** (set_value + view-layer update, 8 ms between mouse moves, medians of 5 × 40 steps): 9.71 ms without the plan,
  9.85 ms with path + data box + bar (+1.4 %); the plan's own work 0.145 ms per step (1.5 %). After 0326's faster drag
  was merged: 9.09 → 9.46 ms (+4 %), the plan's own work 0.163 ms (1.8 %). Live rows cost ~1.4 ms each, so they run on
  redraw only, at most 5× a second.
- Old project: a 0.2.192 lifting project (AT-40 + skid hung) opened and proposed / checked once here; the test and its
  file were taken out again under the lead's new baseline rule (CLAUDE.md 6, 25 Nov 22:4x: no new old-project tests).
- GitHub: 9 full runs. 1 real failure (the tour's rule: a still stop shows its first frame – fixed), 1 tour-build time
  budget 241 s / 240 s on a runner flagged slow (the Lifting set's build made 0.2 s lighter, green after), and 6 lost
  version races in the night (0.2.260 → 0.2.269: 0325, 0327, 0326, 0346, 0352, 0369, 0366, 0354, 0368 released
  first; each a merge + renumber + new full run). Green run 45759756830 fast-forwarded to `main`.
- Subagents: one independent tester (worktree, 86 tests); no code written by subagents.

**Pictures for the owner** (`tasks/0348_page/`): `1_checks_table.png` (the panel), `2_red_moment.png` (an 8.5 t skid:
the timeline at the outriggers' red moment, the data box "Over entered limit"), `3_data_box.png` (the 6 t lift, data box
in a render).

**Open points / what L6b needs:**
- **The built-in AT and KB samples' masses do not fit their sample charts.** The charts' tipping assumed the carrier at
  the slew axis; the files' carrier CoG is its solid's centre (AT-40: 4.2 m forward, front pads at 2.7 m). So C5 says
  "outside its outriggers" (red) at 96 % chart use, and an outrigger lifts off already at 6 t. Honest for the data
  entered, but it makes the samples look worse than their charts – fix in the makers (outriggers at the carrier's ends,
  or charts from the real CoGs) → Lifting makers task.
- L6b: clearances along the path (rows can join `Checks.at`; the search already handles them), reach envelope,
  exclusion zone, ground footprint coloured by C5/C6 pressure (`Supports.items` gives the items per moment).
- A crawler that must travel luffs out first, then travels with the load at radius (order of the brief); travelling
  first with the load low would be kinder on the tracks – later.
- The use bar is drawn in the 3D view only (not in renders); the data box is the render's.
- A narrow red band shorter than 0.2 s between keys can still be missed by the search (the joints move smoothly, so
  real checks do not do this; the frame-by-frame reference is kept as `every`).
- `tools/guide_screens.py` gives blank pictures unless `FRESING_WORKSPACE_START="All functions"` is set before Blender
  starts (its own setdefault comes too late) – set it in the command.

**Owner's check line:** Update, then open the test tour, Lifting set, stop "Lifting: lift path and checks": the table
shows every check with its colour and frame, the magnifier moves the timeline there, the data box sits on the hook
block; on your own lift click **Set-down point…**, then **Check along the path**.
