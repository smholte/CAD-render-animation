# 0049 – Tool library fixes from the owner's demo (0048): BT30, gauge lengths, tip accuracy, sharp corners

**Who:** worker · **Status:** done (0.2.38) · **Branch:** `claude/upbeat-pascal-jf4rs4`
**Started by:** lead chat, 9 Nov 2026 (from the 0048 report, problems 1–5) · **Lane:** Machining – `core/tools.py`,
`blender/tools.py`, `core/machining.py` / `blender/machining.py` (sampling only), `core/gcode.py` / `blender/gcode.py`
(G43 lengths only), `ui_gcode.py` (Tools rows); tests; guide "Tools" chapter
**Model:** Opus · effort Medium · **Place:** Claude Code on the web, environment "CAD-render-animation"

Runs before 0041 (same lane, same files). Keep it small: fixes, not new features.

## Goal

Tool lengths are right whatever holder each tool sits in, BT30 is a holder choice, manufacturer tool files that lie
along X come in the right way round, and milling follows the program closely at sharp corners.

## Background (0048 report, `tasks/0048-demo-facemill-chamfer.md`)

1. **No BT30 holder.** List has ER, SK40, BT40, HSK63. Small machines use BT30 a lot (flange Ø46, taper 7:24, gauge
   line as the standard gives it).
2. **G43 length differences use the stick-out** ("tip to holder nose"). With tools in different holders (an arbor
   45 mm long, a chuck 60 mm) the differences are wrong. 0048 worked around it by typing the gauge length (tip to the
   gauge line) into every row. A tool's length for G43 must be **stick-out + holder length** (tip to the gauge line);
   `ToolSpec.holder_length` already exists. Rows from a part or a STEP with the holder inside: offer a "Gauge length"
   field (tip to gauge line) that wins when filled in. Old projects: same result as today when all tools share one
   holder (test it).
3. **Tool tip vs program up to ~0.065 mm** on some frames (also in the 0037 project), sometimes as a Y offset on a
   straight X move. Find the cause (key interpolation? float32? the BIAS of joint drivers? frame rounding at move
   ends?). Fix if it is small; target ≤ 0.02 mm on straight moves. If the fix is not small, report the cause and stop.
4. **Milling cuts sharp corners** of fast moves by up to 0.3 mm: the swept path between two samples goes straight
   across the corner (a straight lead-in meeting a wall at 90° gave a 0.71 mm chamfer instead of 1.0). Add samples at
   every move end / corner of the program (the G-code bake knows them) so the swept path passes through the corner.
   Check the cost: `machining.sample` time and sample count on the test mill before/after.
5. **Manufacturer STEPs lie along X** with the gauge line at the origin (ToolsUnited / Hoffmann layout). Make
   `tip_and_axis` (or the import) handle a tool or a holder alone in that layout: axis found, tip at the far end from
   the gauge line. Test with a generated file of the same layout (sizes only – the owner's files are never committed).

## Done when

- [x] BT30 in the holder list (generic shape, tooltip, guide).
- [x] G43 lengths = tip to gauge line; a test with two tools in different holders gives the right spindle offsets;
      old one-holder projects unchanged (test).
- [x] Item 3: cause named in the report; fixed to ≤ 0.02 mm on straight moves, or reported as not small.
- [x] Item 4: a test with a 90° corner at high feed cuts within 0.05 mm of the corner; sample time before/after named.
- [x] Item 5: X-axis tool and holder STEPs (generated) read with the right tip and axis.
- [x] Tooltips, guide "Tools" chapter, PC-check line `milling.tools` extended (no new line needed unless visible).
- [x] Tests; GitHub green; merged to `main`, next free version, released (CLAUDE.md section 7).
- [x] Report filled in; `TASKS.md`: 0049 done, 0041 "open – can start".

## Not in this task

Tool-change animation, pockets, ATC (0041). Coolant (0042). Way covers (0035). The owner's files.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (4 cores, no graphics card), 9 Nov 2026 · version 0.2.38

**What changed:**
- **BT30** holder (flange Ø46, 7:24 taper Ø31.75 at the gauge line, 48.4 long, pull stud; nose Ø32 and 45 mm by
  default); Fusion holders named "BT30 …" are read as BT30. Holder shapes now come from one table (`_TAPERS`).
- **G43 lengths** = tip to gauge line: `core/tools.gauge_length` = the row's new **Gauge length** if > 0, else
  stick-out + holder length. `gcode.length_offsets` uses it. Gauge length field: in the row for a part/STEP shape, in
  the fold for drawn tools; a line under the sizes shows "Length for G43 (tip to gauge line): … mm". A new part or
  STEP clears a typed gauge length; reading a tool file keeps it.
- **Item 3 – cause:** not keys, float32, BIAS or frame rounding (straight moves on the gantry: 0.0002 mm). The tip read
  from the mesh lies a little beside the axis the **spindle joint turns about**; turning, it goes round in a circle,
  so the steered point leaves the path by up to twice that offset, in any direction (hence "a Y offset on a move
  along X", "some frames", the same size for all tools). Reproduced: spindle axis 0.06 mm beside the tip → 0.117 mm.
  **Fix (small):** `machining.on_turning_axis` puts the tip (and axis) on the axis of the rotate joint that turns the
  part when within 0.5 mm / 3°; used by `gcode._rest_tip` (machine set-up, tool copies), `machining.detect` and
  `machining.sample` (bits). Same case after the fix: 0.0002 mm.
- **Item 4:** the G-code bake records the program's corners (keys where the path turns > 2°) as fractional frames
  (`cnc["fr_corners"]`, cleared with the build); `machining.sample` reads the tool there too and refines from there.
- **Item 5:** `tools.tip_and_axis` – a model along X with the origin on its axis: shank end on the origin → the far
  end is the tip; origin inside (a holder) → the side where the flange sits next to the origin (outline read between
  vertices), else the side that reaches further. Generated files `test_tool_x_endmill.step` (Ø10, tip at X 75) and
  `test_tool_x_bt30.step` (BT30 chuck alone, stud end further out than the nose) from `tools/make_test_tools.py`.
- Guide "Tools" chapter and G-code step text, `panel_4_tools.png` again; PC-check line `milling.tools` now holds both
  tools in BT30 holders of different lengths and checks the 25 mm offset and the corners; CLAUDE.md section 8 entry.

**Tested and measured** (this session, 4 cores):
- New tests: BT30 shape, gauge lengths, Fusion BT30 (`test_tools_core.py`); different holders 85 vs 98 mm → 13 mm,
  typed gauge wins, one-holder (ER, None) projects → the old −2 mm; corner at F1100 within 0.05 mm; X-axis tool and
  holder (`test_tools.py`); turning spindle 0.06 mm off → < 0.01 mm (`test_gcode.py`). Local: test_gcode 22,
  test_tools 16, test_machining 14, cores 91 – all pass. Real app `ui_test_gcode.py` 25/25. Tooltips 471 ok.
- Corner (Ø6 end mill, 90° turn, F1100, test gantry): cut edge on the diagonal 2.78 → 3.00 mm (want 3.0); samples 393 →
  395, `machining.sample` 0.20 → 0.23 s.
- Cost on the test mill (zig-zag pocket 160 × 160, 4 mm stepover, F2500, 4,081 frames, 83 corners, Normal):
  samples 4,146 → 4,163, `machining.sample` 12.2 → 11.9 s (no measurable difference; first pair 21.1/19.1 s while
  other tests ran).
- PC check `milling.tools` (bpy): OK – face 1.00, drill 8.00, BT30 offset 25.00 mm, 5.3 ms per frame.
- GitHub: 1 full run on the branch, green first time (12.6 min; test suites 1 and 4 flagged SLOW, 9.8/11.0 min); then
  main had moved (0045 task list only): merged, fast-forwarded; the push to main ran full again (16.4 min, green), release
  0.2.38 published, update check on Windows and "Offer the release" green. 2 full runs.

**Owner's test (9 Nov, his PC):** the different tools work with manual tool change.

**Open points / follow-up tasks:**
- The owner's 0037/0048 projects were not available here: the cause is shown on the test gantry; on his PC the tip
  check of 0048 should now give ≤ 0.02 mm (if his spindle joint lies more than 0.5 mm off the tool's tip, nothing
  is snapped – that would be a set-up error worth a warning in a later task).
- A STEP of tool + holder can not give its gauge length by itself yet (typed in); the ToolsUnited gauge line on the
  origin could fill it in a later task.
