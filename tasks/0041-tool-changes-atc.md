# 0041 – Tool changes: manual change and ATC, animated from the program

**Who:** worker · **Status:** done (0.2.45, 9 Nov 2026) · **Branch:** `claude/beautiful-noether-xsd1e0`
**Started by:** lead chat, 7 Nov 2026 (owner accepted: 2B-ii – the operator's hand as an optional choice in the
animation set-up; 2C-ii split – this is part 2 after 0040; pause at a manual change short by default and adjustable)
**Area:** Machining lane + G-code – `core/gcode.py` / `blender/gcode.py` (M6 handling, timing), `animation.py`
(step length), `ui_gcode.py` (changer set-up), `core/tools.py` / `blender/tools.py` from 0040 (pockets); tests; guide
**Model:** Opus · effort High

## Goal

Every M6 in the program is animated by itself. On a machine without a changer: the head goes to the change
position, a short pause, the tool is swapped (optionally by an operator's hand). On a machine with an ATC: all tools
sit visibly in their pockets from the first frame, and at each M6 the machine moves to the changer, the changer
moves, the old tool goes back into its pocket and the new one comes out.

## Background

- 0026 already plays a saved motion sequence for the changer at each M6 and hides the carousel part of the loaded
  tool (`tasks/0026-gcode-motion.md`). 0040 adds the tool list with a place per tool (spindle / pocket / bench) and
  makes every tool cut.
- The owner's new Fresing machine has an ATC; the older, smaller one has none – both must work.

## What to build

1. **Machine type** in 4 Motion > CNC machine: "Manual tool change" or "Automatic tool changer (ATC)".
2. **Manual change at M6:**
   - Head moves to a change position (set in the set-up: machine coordinates, or "stay where it is" / "Z up only").
   - **Pause, short by default: 1 s; slider 0–5 s** in the G-code step ("Tool change pause"). The owner finds a
     long pause boring in a video.
   - Old tool disappears, new one appears (quick fade or a cut), optional caption "Tool change: T3 Ø50 face mill"
     (tick box, uses the existing caption look from 0018).
   - **Optional operator's hand** (tick box "Show hand" in the G-code step, off by default): a simple app-made
     gloved hand (own design, no downloaded model) reaches in, takes the old tool out of the spindle, puts the new
     one in, leaves. Its timing fits inside the pause; if the pause is too short for it, the pause grows to the
     hand's minimum and the step's Details say so.
3. **ATC set-up:**
   - Pockets: pick the carousel/rack parts or click positions; number them; the tool list's place field (0040)
     links tools to pockets. Pockets follow the carousel when it turns.
   - The changer's motion: the existing saved motion sequence (0026), plus for a carousel "turn to pocket N" made
     by the app (the carousel's rotate joint turns the shortest way to the needed pocket).
   - Tool change position (machine coordinates).
4. **ATC at M6:** move to the change position → carousel turns to the old tool's pocket → old tool into its pocket →
   carousel turns to the new tool's pocket → new tool into the spindle → back to the program. Tools needed by the
   program are visible in their pockets from frame 1; an empty pocket stays empty; the tool in the spindle is not
   also shown in its pocket. Time per change: from the motion's own speeds, with a slider "Changer speed"
   (slower / real / faster) for the video.
5. **Timing:** the step's length includes all changes; "Fit into" (0026) still hits its length (changes shortened
   proportionally, with a minimum). Cutting stays exactly on the program between changes.
6. Tooltips on every control; user guide chapter "Tool changes" with pictures (manual, ATC); PC-check line.

## Done when

- [x] Manual change: pause default 1 s, slider 0–5 s works; caption optional; tool swapped at the right frame.
- [x] Hand: optional, off by default, looks clean in a still; fits in the pause or lengthens it with a note.
- [x] ATC on a test changer (carousel with 8 pockets, 4 tools): every tool visible in its pocket from frame 1, the
      right pocket comes round each time, old tool back in its own pocket, new tool in the spindle; checked frame by
      frame at each change in a test.
- [x] "Fit into" still exact with changes; tool tip on the program path between changes within 0.01 mm.
- [x] Old projects (0026 changer sequence, no pockets) open and play as before.
- [x] Tooltips, guide, pictures, PC-check line; tests; GitHub green; merged and released.
- [x] Report filled in; `TASKS.md` updated.

## Lead notes after 0040 (8 Nov 2026)

- 0.2.36's CHANGELOG says old projects "cut as before", but an old project with tool changes whose tools have
  different stick-outs now moves the spindle ("Tool lengths move the spindle", on by default). Say this plainly in the
  guide's Tools / tool-change text (and how to untick it for the old look).
- From 0040's report: `place`/`pocket` fields are stored but unused (yours now); the spindle's length adjustment ramps
  from the swap to the end of the change – fit it into the change animation.
- Test suites 1 and 4 were flagged SLOW in 0040's runs (9.5–11.5 min vs 4–5): after your green run, record the times
  (`python3 tools/ci_status.py --run <green run> --record`) and commit `tools/ci_times.json`.
- Task 0048 (owner's demo with face mill + chamfer mill, no code) may run at the same time; it uses M6 with
  `G43 Hn`. Your changes must keep such a program building without edits.

- 0049 (before you) changes G43 lengths to tip-to-gauge-line and adds samples at corners: build on it.

## Not in this task

- Tool list, shapes and cutting (0040). Air (0039), coolant (0042).
- Tool length measuring (probe) animation; pallet changers – possible later ideas, not now.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (worker), 9 Nov 2026 · version 0.2.45

**What changed:**
- New `core/toolchange.py` (no Blender): each M6 is planned as timed phases – head travel (Z first going up, Z last
  coming down, rapid speeds ÷ "Rapids faster"), pause (with the hand: 2.8 s minimum, `hand_keys`), carousel turns
  (shortest way, within the joint's limits unless it is a motor; time = pockets turned × "Turn per pocket" ÷ "ATC
  speed", at least 0.2 s), the changer's own animation split at its swap. `Schedule` (core/gcode.py) puts a `Change`
  on every TOOL piece: `point_at` and `samples` follow the head's travel; `tool_events` keep their old form. "Fit
  into": changes may take at most half of the seconds, all phases scaled by one factor (bisection), each phase not
  under its minimum. `T1 M6` with T1 in the spindle (its row's part is the spindle tool) = no change.
- New `blender/toolchange.py`: pockets (rows: part, point, direction in the part's space; arrows "FR pocket N"),
  "Click pockets" (eyedropper, several clicks), "Fill the carousel" (N pockets round the joint's axis), stations worked
  out from the pockets and the spindle's gauge line (rack: per pocket; carousel: the station pocket at value 0, and
  the joint value that brings each pocket there), which tool stands where (row Pocket → nearest pocket to the row's
  CAD part → T number; Bench = none), pocket copies ("FR tool Tn pocket", one per tool per build), the hand (mesh
  made by the app: palm, 4 fingers, thumb, cuff; blue nitrile material; its own action with location + visibility
  keys; copies of the tools it carries as its children), carousel keys, captions, model update, the upgrade of old
  projects (a step with a changer animation → ATC on load; load_post step "tool changer").
- `gcode.py`: `timing()` builds the Changer; `prepare()` splits the changer animation per change (`Shifted` with
  offset/scale, carousel steps left out with a warning when the app turns it); `_lift` (G43 lengths): with head
  travel 0 at the changer, ramps on the way out and back; without travel as before (from the swap). Old `_tool_keys`
  replaced by `toolchange.tool_keys`.
- Props: `cnc.changer`, `change_mode`, `change_pos`, `carousel_joint`, `pockets`, `pocket_count`, `pockets_reverse`,
  `station`, `pocket_time`, `atc_lift`; step: `gcode_tc_time` is now "Pause at M6" (default 1 s, 0–5 s),
  `gcode_hand`, `gcode_tc_caption`, `gcode_changer_speed`. Rows' place/pocket now used (0040's open point).
- UI: 4 Motion > CNC machine > **Tool changes** (new sub-panel, pocket list); the step's fold shows Pause at M6, Show
  hand, Caption, Changer, ATC speed and the notes. Captions go into MP4s also with step captions off
  (`video.captions_of`). Tool list changes recompute step lengths in ATC mode. `animation.bake`: no extra frame from
  float rounding at the end of "Fit into".
- Guide chapter "Tool changes" (5 new pictures, `guide_screens.py` modes `toolchange` / `toolchange_view`), the
  lead's note on "Tool lengths move the spindle" for old projects; CLAUDE.md layout; PC-check line
  `motion.toolchange` (MIN_LINES_FULL 43); real-app `ui_test_gcode.py` +4 checks (MIN_CHECKS 29).

**Tested and measured** (4-core cloud test machine, test gantry):
- `tests/test_toolchange_core.py` (12) and `tests/test_toolchange.py` (18): manual pause/slider/position/swap frame,
  tip on the program between changes < 0.01 mm also with "Fit into" (exactly 12.0 s / 301 frames), hand (off by
  default, 2.8 s, holds the tool, clean closed mesh), captions, ATC with 8 pockets and 4 tools checked at every drop
  and swap (the right pocket at the station within 0.01 mm – 0.0001 mm measured –, the machine at the station, the
  old tool back in its own pocket, the new one in the spindle, never in both places), shortest turns, ATC speed, Fit into with changes squeezed to half,
  changer animation split, old project with a changer animation (3.0 s per change, swap at 1.5 s, head still), rack,
  bench tool, two tools in one pocket warn, two program steps, save/reopen, model update, joint rename.
- Existing suites of the area: test_gcode (one test now sets the machine to ATC, as an old project gets on load),
  test_tools, test_air, test_machining, test_video, test_panels, test_gcode_core: all pass (163 + 41).
- PC check `motion.toolchange` (bpy, no GPU): OK in 61 s locally (most of it the hand picture; now rendered at
  480 × 360), pockets at the spindle to 0.0001 mm; `motion.gcode` still OK. Real app `--only gcode`: 29/29 in 32 s.
- GitHub: see "Runs" below.

**Open points / follow-up tasks:**
- The hand grips at the spindle tool's gauge line − 30 mm; on the test gantry (no holder) that is on the tool itself.
  The owner should look at it on his own machine with BT30 holders (PC check picture "Manual tool change").
- The tools in the test gantry's carousel hang under the disc, so the spindle visibly passes through the disc at the
  station (the test model, not the app). A double-arm changer is shown with the same up/down motion plus its own
  animation; an exact arm swap would be a later idea.
- A program step that starts after another one keeps the carousel's turn times worked out from frame 1's carousel
  position (only matters when an earlier step turned the carousel by hand).
- Lead note 0040 (record CI times): see Runs.
