# 0064 – Double-arm tool changer: the exact arm swap

**Who:** worker · **Status:** running (10 Nov) · **Branch:** `claude/jolly-ramanujan-l2rjv9`
**Started by:** lead chat, 10 Nov 2026 (owner's priority 5 of the big features; owner 10 Nov: his new Fresing mill
gets a **double-arm** changer, **no CAD model of it yet**)
**Lane:** Machining – `core/toolchange.py`, `blender/toolchange.py`, the tool-change part of `core/gcode.py` /
`blender/gcode.py` / `ui_gcode.py` (4 Motion > CNC machine > Tool changes), `blender/props.py` (additive), a new
test-model maker `tools/make_test_atc.py` + its STEP in `tests/data/` and `fresing_render/data/`, tests, guide
"CNC machine > Tool changes", PC-check line, test-tour stop
**Model:** **Opus · effort High** · **Place:** Claude Code on the web, environment "CAD-render-animation"

Runs at the same time as **0063** (Quality lane: CI grouping, `tools/ci_*.py`, no app code, no version). If you add a
real-app test, `GROUPS` / `MIN_CHECKS` in `tools/ci_real_app.py` may have moved under you: merge `main` once at the
end and put yours in the lightest group. **0061 (tool marks, same lane) starts after this task is merged** – finish
and merge as soon as it is green.

## Goal

Today (0.2.45, task 0041) an ATC change is the **umbrella/carousel kind**: the head drives to the pocket, leaves the
old tool, the carousel turns, the head takes the new tool. A double-arm changer only gets "the same up/down motion
plus its own animation" (0041 report). The owner's new mill has a **double-arm changer**: in his videos the arm must
grip both tools, pull them, turn 180° and push them home, and every tool must be **held by something at every frame**
– spindle, arm or pot – with no jump at a hand-over.

## How a double-arm change works (what the video must show)

Typical vertical mill with BT30 holders and a side-mounted disc magazine:
1. **Tn (before M6), while the machine still cuts:** the magazine turns the next tool's pot to the change station
   (the shortest way). Without an earlier Tn: at M6.
2. At the station the **pot tips down 90°** so the tool hangs parallel with the spindle (an option: some magazines
   have pots that are already parallel).
3. **M6:** the head goes to the change position (usually Z up, LinuxCNC's TOOL_CHANGE_POSITION); the spindle
   **stops at its orient angle** (M19: the drive keys line up with the arm).
4. The arm turns from rest (e.g. 60–90°) and **grips both tools at once**: the one in the spindle and the one in
   the pot.
5. The arm **moves down along its axis** (pull-out stroke) – both tools come out.
6. The arm **turns 180°**.
7. The arm **moves up** – both tools go in; spindle and pot clamp.
8. The arm turns back to rest; the pot tips up; the head goes back to the program.
At speed 1 a BT30 tool-to-tool change takes about 1.5–2.5 s. Times are settings with sensible defaults; the
existing "ATC speed" and "Fit into" apply.

**Random pockets follow from the mechanics:** the old tool always lands in the pot the new tool came from (LinuxCNC
`RANDOM_TOOLCHANGER = 1`). So the app keeps track during the program of which tool is in which pot; the pocket table
at the step's start is where they are at frame 1. Say this in the panel and the guide in one line.

## What to build

1. **Changer type:** 4 Motion > CNC machine > Tool changes gets a third kind next to Manual and Tool changer:
   **"Double-arm changer"** (the existing ATC becomes "Carousel / umbrella" in the label; old projects keep exactly
   what they have).
2. **Set-up from the CAD model, few clicks** (the owner's model will come later; it will be an Inventor STEP):
   - pick the **arm** (one part or a subassembly); click its hub – the arm's axis is parallel with the spindle
     through the hub (read it from the part's round faces, like joints do). The grip distance comes from the
     spindle axis; the second grip is opposite it.
   - the **magazine**: the existing carousel joint + pockets (0041), plus the **change station** (the pot that sits
     under the arm's second grip when the arm is at its grip angle – find it, or click it).
   - **pot tip-down:** off, or click the hinge once at the station; the app tips whichever pot is at the station.
   - **rest angle, grip angle, pull-out stroke** (default from the holder: BT30), **orient angle**: read or typed,
     each with a tooltip.
   - A **Check** button that plays one change in the view and reports in words what does not fit (grip not on the
     spindle axis within 0.1 mm, station pot not under the second grip, stroke too short to clear the taper).
   - No joints for the user to make by hand: the app makes the arm's turn + slide itself (stacked joints, 0011, or
     its own empties) and keys them; works with scripts off.
3. **The plan** (`core/toolchange.py`, no Blender): new phases for pot tip, orient, arm grip / pull / turn / push /
   back, and Tn pre-indexing during the cut (the magazine turn may overlap cutting; it must never move a pot that is
   tipped). Hand-overs as events: spindle→arm, pot→arm, arm→spindle, arm→pot. "Fit into" squeezes them like the
   other phases (each to a minimum).
4. **Tools in the right hands:** at every frame each tool copy hangs on exactly one holder (spindle, arm grip, pot);
   at each hand-over both holders are at the same place (**within 0.01 mm**, measured in a test), so nothing jumps.
   The tool in the spindle cuts with its own shape after the change, as today. The render queue shows the same.
5. **Test model:** `tools/make_test_atc.py` makes a small generic mill head with a BT30-like spindle, a double arm
   and a side disc magazine with 12 pots that can tip (OpenCascade, like the other makers; nothing of the owner's).
   A short `.ngc` program with Tn before M6 and three tools.
6. **Old projects:** carousel/umbrella ATC and manual changes unchanged (their tests pass untouched); an 0.2.45–0.2.50
   project opens and plays the same.
7. Every button and setting has a tooltip; guide chapter "Tool changes" gets a "Double-arm changer" part with a
   picture; **PC-check line** `motion.doublearm` (one change on the test model, hand-overs within 0.01 mm, a picture
   at the 180° turn); **test-tour stop** "Double-arm tool change" (new `@tour_set` on the new model).

## Done when

- [ ] A double-arm change plays as in steps 1–8 above on the test model, in the view and through the render queue.
- [ ] Tests: the plan's phases and times (core, no Blender), random pockets over a program with 4+ changes, Tn
      pre-indexing, hand-overs within 0.01 mm at every event, "Fit into", pot tip on/off, scripts off, old ATC and
      manual projects unchanged. Real-app test of the panel (click through the set-up and Check).
- [ ] PC-check line + `MIN_LINES_FULL`; test-tour stop + `MIN_LINES_TOUR` / `MIN_CHECKS["tour"]`; tooltip report
      strict 0 missing; guide chapter and picture.
- [ ] GitHub run green; merged to `main` and released (take the version last; 0063 makes no version).
- [ ] Report: what changed, measured numbers (hand-over error, change time at speed 1, frame time of the test
      change), runs needed and why, what the owner should check on his own model once it exists.

## Not in this task

Chain magazines and tools travelling along a curve (motion paths, owner's #4, later). The operator's hand, manual
changes, coolant/air/chips files. Cut-face looks and tool marks (0061). 4th/5th axis (0029). The PC check's
other lines. CI grouping beyond adding your own test (0063 works there).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (worker), 10 Nov 2026 · version 0.2.51

**What changed:**
- **Plan (core, no Blender).** `core/toolchange.py`: `plan_arm` – a double-arm change in three groups whose tracks run
  side by side: (head out ‖ spindle orient ‖ magazine turn + pot tip down) → arm grip, pull, half turn, push, back →
  (head back ‖ pot tip up). Hand-overs: spindle→arm and pot→arm at the grip's end (`drop`), arm→spindle and arm→pot
  at the push's end (`swap`). `Change.total`/`group_length` (Fit into squeezes every phase to its minimum: arm 0.08 s,
  tip 0.1 s, turn 0.2 s), `tips()`, `orient_span()`, `arm_times()`. A new tool without a pot: by hand (a manual
  pause). `core/gcode.py`: the reader records `Tn` without M6 (`Program.t_events`); `Schedule` keeps the pot table
  (random pockets: the old tool goes into the new one's pot), puts the magazine's work at the Tn (`Change.prep`,
  from the Tn once the change before has tipped its pot up) and plans a change again without it when it would not be
  done before the arm wants the pot (a few rounds, so Fit into stays exact).
- **Blender.** New `blender/doublearm.py` + `ops_doublearm.py`: Click the arm's hub (two joints the app makes, slide +
  stacked rotate, tagged `fr_atc` so Find the axes never takes them; grip angle read from the arm's round claws,
  stroke from the spindle tool's holder: taper + pull stud + 5 mm), Click the hinge (a pocket in every pot – pots
  found by their shared mesh round the magazine – re-homed onto each pot, one "Pot N tip" joint per pot, the tip
  direction worked out), Read from the model, Remove the arm, **Check** (plays one change in the view with a timer;
  reports arm axis, claw on the spindle axis, station pot under the second claw, tool parallel, stroke vs taper).
  The bake: a copy per holder (spindle copies as before; "FR tool Tn on arm" children of the arm's turn, at most two
  per tool; "FR tool Tn pot k" children of the pot) with their places worked out from the joints' frames
  (`world_at`: W, A(θ), R, P_k – see the module docstring), CAD tools in pots hidden from frame 1 (they move between
  pots now), keys for the arm, the pots' tip joints, the magazine and the visibility; the spindle stops at its
  orient angle during the change (`gcode._spindle_keys`). `toolchange.changer()` fills the arm's times; problems()
  for the arm. Props: `changer` gets "Double-arm" (the old ATC is labelled "Carousel / umbrella", value unchanged),
  arm/pot settings and times, `FRCncPocket.tip_joint`.
- **UI.** 4 Motion > CNC machine > Tool changes: the changer is a drop-down now (three names did not fit as
  buttons); the Double-arm part with steps, arm, magazine, pots list, change position, Times fold, Check (big) and
  its result lines. The step shows ATC speed for the arm.
- **Test model** `tools/make_test_atc.py` → `test_atc.step` (tests/data + fresing_render/data; a test checks the
  copies): a small mill (table X/Y, head Z), BT30 T1 in the spindle, a double arm with U claws, a 12-pot disc
  magazine with tipping pots, T2 in pot 2. Shared set-up `doublearm.set_up_test_model` (+ `TEST_PROGRAM`: three
  tools, Tn before every M6) for the tests, the PC check, the tour and the guide pictures.
- PC-check line `motion.doublearm` (MIN_LINES_FULL 47); tour set "doublearm" + stop "Double-arm tool change"
  (MIN_LINES_TOUR / MIN_CHECKS["tour"] 31); real-app test `tools/ui_test_doublearm.py` (19 checks, group "scenes");
  guide: "Double-arm" part of Tool changes with two pictures, manual/carousel panel pictures made again (drop-down);
  CLAUDE.md layout + a "learned the hard way" line (hidden objects are not evaluated).

**Tested and measured** (4-core cloud machine, the new test model, bpy as a module unless named):
- `tests/test_doublearm_core.py` (13): phases and times, random pockets over 5 changes, shortest turns, never a turn
  while a pot is down, tip off, Tn pre-indexing (and too late → at the M6; Tn on the M6 line → none), Fit into
  (exactly 10.0 s, changes squeezed to half, each phase ≥ its minimum), ATC speed, tool without a pot, old ATC
  unchanged. `tests/test_doublearm.py` (8): set-up read from the model (grip 90.00°, stroke 76 mm, 12 pots, Check
  all 0.00 mm), Check finds a wrong grip and a short stroke, every hand-over of 3 changes measured on Blender's
  evaluated parents at the event sub-frame, pot down / magazine still while the arm works, spindle at its orient
  angle, no tip and no spindle joint, Fit into 12.0 s, save/reopen, simple drivers (scripts off), old carousel ATC
  project on the same model unchanged.
- **Hand-over error:** below 0.01 mm everywhere; measured 0.0003 mm (PC check line), 0.00017 mm (real app).
- **Change time at speed 1:** arm 1.6 s tool-to-tool (grip 0.3 + pull 0.25 + turn 0.5 + push 0.25 + back 0.3); the
  whole change on the test mill 5.8 s, most of it the head's Z travel at the test model's 3,000 mm/min.
- **Frame time:** 0.64 ms per frame through the change vs 0.68 ms while cutting (test model, bpy module); bake 0.03 s.
- PC check `motion.doublearm`: OK in 10 s locally. Real app `--only doublearm`: 19/19 in 0.6 min. Tooltip report
  strict: 526, 0 missing. Existing suites of the area pass untouched: test_toolchange, test_toolchange_core,
  test_gcode, test_gcode_core, test_tools, test_machining, test_air, test_panels, test_pccheck, test_tour,
  test_user_guide, test_ci_tools.

**Open points / follow-up tasks:**
- **On the owner's own model** (Inventor STEP, once it exists): select the arm's subassembly before clicking the hub
  (else only the clicked part turns); check the **grip angle's sign** (two claws give +θ and −θ; the app takes +) and
  that **Check** says 0.0x mm for the claw and the station pot – if the pot is off, the change position or the
  station may differ from the CAD pose; the pots must be parts (or subassemblies) of the same shape for 'Click the
  hinge' to find them all; set **Orient angle** so the holder's drive slots line up with the claws.
- A second program step starts again from the pot table of frame 1 (random pockets are not carried from one step
  to the next); the same holds for the start tool (as in 0041).
- 'Remove pocket' / 'Fill the carousel' after 'Click the hinge' leave the pots' tip joints in the joint list until
  'Click the hinge' again or 'Remove the arm' (which removes every joint the app made for the changer).
- The changer animation of the carousel ATC ("Changer" in the step) is not offered for the double arm.

**Runs:** (filled in after the GitHub runs)
