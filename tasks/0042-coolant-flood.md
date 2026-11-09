# 0042 – Coolant: flood and mist while milling

**Who:** worker · **Status:** done (0.2.48) · **Branch:** `ccr-de3acade-wz4azs` (the web session's branch)
**Started by:** lead chat, 9 Nov 2026 (owner's priority 2 of the big features, 9 Nov; placeholder since 7 Nov)
**Lane:** Machining – a new `core/coolant.py` + `blender/coolant.py` next to `air.py` (0039), its settings in
`ui_machining.py` / the G-code step fold in `ui_gcode.py`, `core/gcode.py` (M7/M8/M9 events, additive), chips
(wet chips), `core/materials_lib.py` (new ids only); tests; guide "Milling" chapter; PC-check line
**Model:** **Opus · effort High** (lead 9 Nov: runs before the Fable day so Thursday is free for 0058 and tool marks) · **Place:** Claude Code on
the web, environment "CAD-render-animation"

May run at the same time as 0059 test tour (Quality & delivery) and 0058 (Flex parts lane): do not touch `handlers.py` apart from a one-line registration,
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

- [x] M7/M8/M9 or always on; nozzles picked or Automatic; jets, splash, wet sheen, wet chips, emulsion/oil, flow.
- [x] Works in view, Build animation, queue (background), stills, Fit into, after tool changes; deterministic frames
      (test: frame 50 rendered after 10 and after 90 is the same).
- [x] Old projects unchanged (no coolant unless switched on); save/reopen; model update keeps the nozzles.
- [x] Pictures for the report (generic test mill, Cycles): a still close-up with flood, a short clip (a few seconds,
      small MP4 in the report folder `tasks/img/`, ≤ 3 MB), before/after drying.
- [x] Render time numbers as in 5; tests for the timing (M-codes, drying) in `core/coolant.py` without Blender.
- [x] Guide "Milling" (Coolant) with a picture; PC-check line `milling.coolant`; tooltips.
- [x] If the test tour (0059) is merged by then: a tour stop "Coolant" (one entry in `blender/tour.py`); otherwise
      write "tour stop still to add" in the report.
      How (0059 is on `main`): a `stop(...)` entry in its group in `blender/tour.py`, set up in a set's build function
      (`_shot(b, "@<stop id>")` or an animation with `animation=`), a number `check`; raise `MIN_LINES_TOUR`
      (`tools/ci_check_pccheck.py`) and `MIN_CHECKS["tour"]` (`tools/ci_real_app.py`); `pytest tests/test_tour.py`.
- [x] GitHub green; merged to `main`, next free version, released (CLAUDE.md section 7).
- [x] Report filled in; `TASKS.md`: 0042 done, the tool-marks task "open – can start".

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (worker, Opus), 9 Nov 2026. Released as **0.2.48**.

**What changed:**
- `core/coolant.py` (no Blender): coolant spans from the program (flood code M8, mist code M7, off code M9 – M9 always
  stops both; flood and mist can overlap), "always flood / mist while the spindle turns", off; cutting spans (feed moves
  that reach the stock's top); wet level from the spans alone (rises with 0.6 s time constant, dries smoothly within
  "Dries in"), its keys; the liquid of one frame from the frame number alone (hash of drop + cycle, no history): flood
  jets (tube that sags, ripples, spreads, thins and breaks into drops), mist cones, splash thrown off the turning tool
  (1 while cutting, 0.3 while moving in the air with coolant on, mist a third); automatic nozzles on a ring, Loc-Line
  hose mesh (ball/neck/socket profile, round nozzle), the ring.
- `blender/coolant.py`: the coolant space (empty "FR coolant" on the head – the spindle joint's frame or the tool's
  parent – at the tool tip, +Z up the tool); build hooks from `gcode.py` (prepare / record after the tool copies /
  clear / model update); its own frame handler (registered in `__init__`, not in `handlers.py`) draws jets (mesh),
  drops (points + GN ico-sphere instancer) and hoses (re-bent per tool length) at every frame; wet sheen = a few nodes
  in the materials of the wet parts (darker, glossier, clear coat, voronoi drops on steep faces) gated by an object
  property `fr_coolant_wet` and a plain AVERAGE driver on the root's keyed `fr_wet` (works with scripts off);
  unpatching puts the materials back exactly (test). Wet parts: the workpiece + parts round/under it not on the head.
- `ops_coolant.py`, `ui_coolant.py`: panel **4 Motion > CNC machine > Coolant** (tick in the title; Automatic hoses
  1–4, Turn hoses, Show hoses / Parts of the model with Use clicked part, Click point, list, Aim at the tool, flip;
  Liquid emulsion/oil, Flow, Wet sheen + Dries in, Draft; fold Codes). Step setting **Coolant** (From the program /
  Flood while cutting / Mist while cutting / Off) and the line "Coolant: flood 1 time, 4.7 s".
- Props: `FRCoolant` + `FRCoolantNozzle` (`scene.fresing.coolant`), one EnumProperty `gcode_coolant` on the step.
- Chips: `SimIn.wet` – chips born while coolant flows leave 0.6× slower, 1.6× drag, 0.3× bounce; chip material reads a
  per-point `fr_wet` (darker, glossier, coat) written each frame from the wet level (`MAT_VERSION` 2).
- M7 rule (guide): with coolant on, M7 = mist; when the air-on code is M7 too it also blows air (mist is air with drops);
  M9 stops both. Mist code 0 makes M7 air only; another air code keeps them apart. Coolant codes are not reported as
  program problems while coolant is on.
- Test tour (0059 was merged meanwhile): stop **Coolant (flood)** in the Machining group, its own set "Coolant" on
  the test mill (MIN_LINES_TOUR 28 → 29, MIN_CHECKS tour 29).
- PC-check line `milling.coolant` (MIN_LINES_FULL 45 → 46, after 0059's own line); guide section "Coolant" in Milling with 3 pictures
  (`coolant.jpg`, `panel_4_coolant.png`, `panel_6_gcode_coolant.png`); `guide_screens.py` mode `coolant`.
- No change to `handlers.py`, `animation.py`, `reimport.py`, `part_types_data.py`, `core/gcode.py` (its M-code events
  were enough), `core/materials_lib.py` (the liquid looks live in `core/coolant.py`).

**Tested and measured** (4-core cloud test machine, no graphics card; generic test mill `tests/data/test_mill.step`):
- `tests/test_coolant_core.py` (18: codes, M9 stops both, own codes, always/off, wetness rise/dry/any order, keys
  within 5 %, cutting spans, determinism of the liquid, splash range, nozzles aim) and `tests/test_coolant.py`
  (10, Blender module: off by default leaves nothing, flood from the program, **frame 50-style test: the same frame after
  frame 10 and after a later frame gives identical jets and drops**, switched off leaves nothing, mist + air from M7,
  M9 stops both, step Flood/Off, hoses follow the tool after a tool change, picked nozzle + aim/flip + model update +
  remove, save and reopen, wet sheen goes back exactly + Clear keys, wet chips). Neighbour suites
  (chips, air, gcode, chips core): 127 passed. PC-check line locally: OK, 3.5 ms per frame for the coolant.
- Render time, flood frame of a pocket, 800 × 450, Cycles 64 samples + denoise, processor, 2 frames each:
  **42.0 s without coolant, 47.1 s with (+12 %)**; with coolant but no wet sheen 44.1 s (sheen ≈ 5 %, jets/splash/
  hoses ≈ 7 %); Draft 47.2 s (Draft only drops splash/drops – the hoses and sheen stay, so it saves little in
  Cycles; it is for the view). EEVEE (software GL here): 24.4 s without, 24.0 s with – no difference measurable.
  On the owner's RTX 3090 not measured yet (the PC check's new line reports the time of a coolant still).
- Showing a frame in the view: about 3.5 ms for the coolant (PC check line).
- Wet chips (Realistic, pocket): median distance from the middle of the pile 74 mm dry, 57 mm wet.
- Pictures (Cycles, test mill, aluminium block): `tasks/img/0042-flood.jpg` (close-up with flood),
  `tasks/img/0042-wet-then-dry.jpg` (at M9 and 2 s after drying), `tasks/img/0042-flood-clip.mp4` (2 s, 480 × 270,
  120 KB; one frame was re-rendered in a fresh process and fits between its neighbours).
- GitHub: 5 runs. One red on the guide picture not yet committed, one red only on the PC-check line's "since" before
  the version was raised (expected), the version commit green (full); then `main` had moved (0059 test tour took
  0.2.47): merged `main`, renumbered to 0.2.48, added the tour stop, one more full run, green, fast-forwarded `main`.

**Open points / follow-up tasks:**
- The test block's draft mesh shows dark facets in reflections (also without coolant); with a wet film they are more
  visible. A real model with smooth normals looks right; worth a look on the owner's demo.
- Ideas, not done: coolant through the spindle (through-tool), mist/steam in the air, puddles that collect over minutes,
  coolant running off the table edge, drops that run down vertical faces over time, splash that hits the vise and
  table (it now ends at the tool-tip height), nozzle hoses that the owner bends by hand (now: on a ring, turnable).
- Owner to check on his PC: the look of the emulsion in a real milling video (GPU), the hoses' place on his spindle
  (Turn hoses), and the PC check's coolant line.
- Branch `ccr-de3acade-wz4azs` can be deleted on GitHub after the merge.
