# 0039 – Air blast: blow the chips away

**Who:** worker · **Status:** running · **Branch:** `ccr-84b37d86-ng46l7` (the web session's branch)
**Started by:** lead chat, 7 Nov 2026 (owner accepted: option 1B, plus the "clean at the end" tick box with a time slider)
**Area:** Machining lane – `core/chips.py`, `blender/chips.py`, `ui_machining.py`; additive in `core/gcode.py` /
`blender/gcode.py` / `ui_gcode.py` (the air code and nozzle in 4 Motion > CNC machine); tests; user guide chapter
**Model:** Opus · effort Medium

## Goal

While air is on, the chips near the jet are blown away from the cut and off the block, so the finished part stays
visible. The owner chooses which G-code switches air, and where the air comes from (through the spindle/tool or an
external nozzle). Optionally a short final blast blows the part clean at the end of the step.

## Background

- The owner's 4K demo of his mill (task 0037, rendered with 0.2.31): by the end the block is buried under chips, so
  the pockets, holes and contour are hardly visible. Air blast is how real machines clear chips.
- Chips (task 0028): `core/chips.py` (35 presets, gravity, bounce, piling up; coolant mist already exists as a
  look), `blender/chips.py`. The G-code reader (0026) already knows M7, M8, M9 (`core/gcode.py`) but they do
  nothing yet. Read `tasks/0028-chips.md` and `tasks/0026-gcode-motion.md` only where needed.
- Coolant (M8 flood, liquid look) is **not** in this task – the owner chose it as its own later task (0042).
- The path store helper `blender/idprops.py` (0038): use it for any array kept in an ID property.

## What to build

1. **Air on/off from the program.** 4 Motion > CNC machine: "Air on code" (default M7) and "Air off code" (default
   M9), a custom M-code allowed (M100–M199). Tick box "Air always on while the spindle turns" for programs without
   the code. The step knows from the program at which frames air is on.
2. **Where the air comes from**, chosen in the CNC machine set-up:
   - *Through the spindle / tool:* blows down along the tool, moves with it.
   - *External nozzle:* pick a part of the model (its tip and direction found from its shape, editable) or click a
     point and aim it; it moves with the part it is fixed to (head or frame).
   Settings: strength (soft / normal / strong or a slider), cone angle, reach.
3. **What it does to chips:** chips inside the cone get a push depending on distance and angle; they slide, bounce
   and pile up further away (on the table, in the vise, in the corners of the machine), not back on the part. Chips
   that already lie on the block are blown off too. Same frame-by-frame result every time (no random change between
   renders of the same frame).
4. **Optional visible air:** tick box "Show air" – a faint cone or mist, off by default.
5. **"Blow the part clean at the end"**: tick box in the G-code step, with a small slider "Time at end" (default
   2 s, range 0.5–10 s). The step is made that much longer; the tool stays up, air blows over the block from the
   chosen nozzle (moving over the part if through-spindle), the chips leave the block, the last frames show the clean
   part. Works with or without air codes in the program.
6. Tooltips on every new control; user guide chapter (milling/chips) with a picture; PC-check line (milling with
   air: ms per frame with and without air).

## Done when

- [ ] M7/M9 (or the chosen codes) switch air in the step; "always on" works; air state visible in the step's Details.
- [ ] Through-spindle and external nozzle both work, the nozzle follows its parent part.
- [ ] Measured on the test mill: chips on the block at the last frame with air off vs. on (count), and with
      "Blow the part clean" the block top has (nearly) no chips in the last frame. Numbers in the report.
- [ ] Same frame rendered twice gives the same chips; the queue renders it right (a short draft job).
- [ ] Time per frame with air on is at most a little higher than without (measure, say how much).
- [ ] Old projects open unchanged (air off by default).
- [ ] Tooltips, guide chapter and picture, PC-check line; tests added; GitHub green; merged and released.
- [ ] Report filled in; `TASKS.md` updated (0040 to "open – can start").

## Not in this task

- Coolant flood / liquid (0042, later). Tool library and tool changes (0040, 0041).
- The other 0037 problems listed in `TASKS.md`.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
