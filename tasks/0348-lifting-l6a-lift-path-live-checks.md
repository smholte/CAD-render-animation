# 0348 – Lifting L6a: the lift path and live checks with the worst moment

**Who:** worker · **Status:** open – can start · **Branch:** `task/0348-lifting-l6a-lift-path`
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

## Done when

- [ ] Pick → set-down proposed as editable steps; poses / own steps usable instead
- [ ] Every applying check worked out along the path, worst moment + Go there; grey with reasons
- [ ] Counterweight-above-chart and jacks-up cases handled and tested
- [ ] Drag time with a plan measured, no slower than without (± 5 %)
- [ ] Lift data box (one tick)
- [ ] Tests added; full suite passes; GitHub run green
- [ ] PC-check line, tour stop, guide, function list, tooltips, CHANGELOG
- [ ] 2–3 pictures (the checks table, a red moment, the data box in a render) in `tasks/0348_page/` for the owner
- [ ] Report below filled in (incl. "what L6b needs"), merged, released; the owner's check line

---

## Report (filled in by the chat that did the task)
