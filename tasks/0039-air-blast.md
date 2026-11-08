# 0039 – Air blast: blow the chips away

**Who:** worker · **Status:** done (0.2.34) · **Branch:** `ccr-84b37d86-ng46l7` (the web session's branch)
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

- [x] M7/M9 (or the chosen codes) switch air in the step; "always on" works; air state visible in the step's Details.
- [x] Through-spindle and external nozzle both work, the nozzle follows its parent part.
- [x] Measured on the test mill: chips on the block at the last frame with air off vs. on (count), and with
      "Blow the part clean" the block top has (nearly) no chips in the last frame. Numbers in the report.
- [x] Same frame rendered twice gives the same chips; the queue renders it right (a short draft job).
- [x] Time per frame with air on is at most a little higher than without (measure, say how much).
- [x] Old projects open unchanged (air off by default).
- [x] Tooltips, guide chapter and picture, PC-check line; tests added; GitHub green; merged and released.
- [x] Report filled in; `TASKS.md` updated (0040 to "open – can start").

## Not in this task

- Coolant flood / liquid (0042, later). Tool library and tool changes (0040, 0041).
- The other 0037 problems listed in `TASKS.md`.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (worker), 7 Nov 2026. Branch `ccr-84b37d86-ng46l7` (the session's own
branch name instead of `task/0039-air-blast`).

**What changed:**
- `core/air.py` (new, no Blender): the jet (speed ~1/distance from 20 mm, Gaussian across the cone, ends at Reach) and
  the *wall jet* where the jet meets a surface (found along its line in the chips' height field): blows outwards
  along the surface, ~1/distance, 15 mm thick. Without the wall jet, air through the spindle did nothing (the chips
  are above the tip). Strengths Soft / Normal / Strong = 8 / 18 / 35 m/s at 20 mm; "Blow the part clean" × 2 and a
  cone of at least 30°.
- `core/chips.py`: flying chips are pulled towards the air's speed (rate 1.5/s × the chip's drag), chips the air
  pushes along a surface do not come to rest, a pushed chip that hits a wall hops up (out of pockets). Lying chips
  where the air is strong are picked up once a frame: the lying chip ends, a **copy** flies on (a chip still rests
  only once, so the Bake format is unchanged; copies grow the arrays by doubling). No random numbers added.
- `core/gcode.py`: the reader keeps M7/M8/M9 and M100–M199 as events; `Schedule.m_times()`, `air_spans(on, off,
  always)` (M9 also stops M7/M8), `Timing.clean` / `clean_sweep`: "Blow the part clean" adds moves (up to 15 mm over
  the highest feed move; through the spindle passes over the cut area for 75 % of the time, then still) – left out
  of the drawn toolpath.
- `blender/air.py` (new): nozzle (from its shape via `machining.detect`, or a clicked point, aimed at the
  workpiece; flip), air frames written by each G-code step at Build (`cnc["fr_air"]`, reset at every build and by
  Clear keys), inputs for the chips (through the spindle = the bit's own path; a nozzle = its pose read per frame in
  `machining.sample`, `fr_air_o/d`), "Show air" cone with visibility keys, model update keeps the nozzle.
- Settings: `FRCnc.air_*` (codes 7/9, always, source, nozzle, tip, aim, strength, cone 15°, reach 250 mm, show),
  `FRAnimBlock.gcode_clean` + `gcode_clean_time` (2 s, 0.5–10). UI: fold **Air blast** in 4 Motion > CNC machine;
  "Air: …" line, **Blow the part clean at the end** + **Time at end** in the step; Details lists the air; Chips panel
  shows it. Operators `cnc_air_nozzle`, `cnc_air_click`, `cnc_air_aim`. A user code chosen for air is no longer
  reported as "not shown".
- PC check line `milling.air` (Full; MIN_LINES_FULL 35 → 36). Guide: 4 Motion > Milling > **Air blast** with a
  render (`docs/img/air_blast.jpg`, test mill, without / with air), the step's settings in 6 Animation.

**Tested and measured** (4-core web session; test mill `tests/data/test_mill.step`, pocket 60 × 40 × 4 mm in 4 s,
chips Realistic, 6,175 chips):
- Chips on the block at the last frame: **1,560 without air; 0 with air through the spindle (Normal); 8 from a
  nozzle on the head (Strong, 28 mm beside the spindle, 60 mm over the block); 0 with only "Blow the part clean" 2 s**
  (also 0 from the nozzle with Normal). Soft from 15 cm away does little (by design: the tooltip says so).
- Time: working the chips out 0.66 s without, 0.91 s with air (+1 s clean); showing a frame 14 / 12 ms; one Cycles
  frame (processor, 800 × 560, 32 samples) 19.7 / 18.7 s. PC check line here: 169 → 0 chips, 12 / 9 ms per frame.
- Same chips twice (positions and ids per frame). Render queue (a background run, draft, 19 frames, camera straight
  down on a patch of the block): 26 % of the patch covered by chips when the program ends, 0 % at the last frame of
  the blast (the test takes about 6 min here).
- New tests: `tests/test_air_core.py` (14), `tests/test_air.py` (15, Blender as a module, incl. the queue run).
  Locally also `test_chips*`, `test_gcode*`, `test_machining*`, `test_user_guide.py`: all passed; tooltip check:
  445 ok, 0 missing. Real-app tests and the Windows run: GitHub only (no Blender download here).
- No helper-agent review (no Windows-only code).
- GitHub: 2 full runs. Run 1 (42415691758) green, but `test_air.py` (8.3 min there, the queue test is most of it)
  made test suite 2 take 17.2 min: times recorded into `tools/ci_times.json` (the four pytest groups now ~9.2 min
  each). Run 2 (42417121128, the merge of `main` with the new times): green in 13.2 min. `main` fast-forwarded to it:
  run 42418174087 (reuse) published v0.2.34, the Windows update check passed, offered to the apps.
- Leftover branch on GitHub: `ccr-84b37d86-ng46l7` (the owner can delete it).

**Open points / follow-up tasks:**
- No panel screenshot of the Air blast fold (no real Blender in this session); the guide shows a render instead.
  `tools/guide_screens.py` can add `panel_4_cnc.png` with the fold open later (0035 does guide pictures).
- Found while making the picture: the test mill's FINISHED PART coincides with the block, so renders of the block
  show black/white triangles unless the finished part is hidden or set as "finished part" – only a test-model
  matter, not an app fault.
- Coolant flood (M8) is 0042; M8 can already be chosen as the air code.
