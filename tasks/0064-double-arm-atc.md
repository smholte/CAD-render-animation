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

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
