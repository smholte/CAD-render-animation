# 0042 – Coolant: flood and mist while milling

**Who:** worker · **Status:** open – can start · **Branch:** `task/0042-coolant-flood`
**Started by:** lead chat, 9 Nov 2026 (owner's priority 2 of the big features, 9 Nov; placeholder since 7 Nov)
**Lane:** Machining – a new `core/coolant.py` + `blender/coolant.py` next to `air.py` (0039), its settings in
`ui_machining.py` / the G-code step fold in `ui_gcode.py`, `core/gcode.py` (M7/M8/M9 events, additive), chips
(wet chips), `core/materials_lib.py` (new ids only); tests; guide "Milling" chapter; PC-check line
**Model:** **Fable · effort High** (the owner's "Fable day"; Opus · High would also do) · **Place:** Claude Code on
the web, environment "CAD-render-animation"

May run at the same time as 0058 (Flex parts lane): do not touch `handlers.py` apart from a one-line registration,
`animation.py`, `reimport.py`, `props.py` beyond its own additive property group, `part_types_data.py`, or any
flex file.

## Goal

A milling video with coolant looks like the real machine: when the program says M8, liquid jets from the nozzles
onto the tool, splashes where the tool cuts, the block and table get a wet sheen, chips come out wet; M9 stops it and
the wet look dries slowly. It looks good in Cycles (stills and videos) and acceptable in EEVEE, without a long
simulation.

## How air blast does it now (0039) – follow the same pattern

Air from the program (air-on code M7 by default, off M9 – settable in `core/air.py`) or always on, from the spindle or a
nozzle, "Blow the part clean at the end". Coolant gets the same choices so the two feel alike, and both can be on.
Owner's choice 9 Nov: in his demo air comes only from "Blow the part clean at the end".

## Scope

1. **When:** from the program (M8 flood, M7 mist, M9 off), always on, or off; per G-code step, like air. Air already
   uses M7 by default: when coolant is on, M7 means mist unless the step's air code says otherwise – write the rule
   into the guide and test both together (M9 stops both, as on LinuxCNC).
2. **Where from:** nozzles picked on the spindle head (points + direction, like the air nozzle) or "Automatic":
   2–4 flexible nozzles (Loc-Line look, made by the app) around the spindle, aimed at the tool tip, following the
   tool's length after each tool change (0041).
3. **Look:**
   - jets: a liquid stream from each nozzle to the tool, slight spread, break-up into droplets near the tool;
   - at the tool: splash and spray that follows the cut, more when cutting than when moving in the air;
   - wet surfaces: block, table and vice get a wet sheen (darker, glossier, thin film; drops on vertical faces), drying
     a few seconds after M9;
   - chips: wet chips look darker/shinier, fly less far and stick more while coolant is on;
   - coolant type: emulsion (milky white, translucent – default) or clear oil; flow slider (low ↔ flood).
4. **Deterministic frames:** the queue renders out of order, so each frame's coolant comes from the frame number
   (seeded particles/meshes), not from a simulation that needs earlier frames (or a cache that is rebuilt on change).
5. **Cost:** Cycles still render time with coolant ≤ +30 % on the milling test scene (measure; say what costs most);
   EEVEE frame time ≤ +50 %. A "Draft" switch for quick views.
6. Not now: coolant through the spindle (through-tool), fog/steam, puddles that collect over minutes, liquid running
   off the table edge. Ideas into the report.

## Done when

- [ ] M7/M8/M9 or always on; nozzles picked or Automatic; jets, splash, wet sheen, wet chips, emulsion/oil, flow.
- [ ] Works in view, Build animation, queue (background), stills, Fit into, after tool changes; deterministic frames
      (test: frame 50 rendered after 10 and after 90 is the same).
- [ ] Old projects unchanged (no coolant unless switched on); save/reopen; model update keeps the nozzles.
- [ ] Pictures for the report (generic test mill, Cycles): a still close-up with flood, a short clip (a few seconds,
      small MP4 in the report folder `tasks/img/`, ≤ 3 MB), before/after drying.
- [ ] Render time numbers as in 5; tests for the timing (M-codes, drying) in `core/coolant.py` without Blender.
- [ ] Guide "Milling" (Coolant) with a picture; PC-check line `milling.coolant`; tooltips.
- [ ] GitHub green; merged to `main`, next free version, released (CLAUDE.md section 7).
- [ ] Report filled in; `TASKS.md`: 0042 done, the tool-marks task "open – can start".

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
