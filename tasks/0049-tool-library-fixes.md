# 0049 – Tool library fixes from the owner's demo (0048): BT30, gauge lengths, tip accuracy, sharp corners

**Who:** worker · **Status:** open – can start · **Branch:** `task/0049-tool-library-fixes`
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

- [ ] BT30 in the holder list (generic shape, tooltip, guide).
- [ ] G43 lengths = tip to gauge line; a test with two tools in different holders gives the right spindle offsets;
      old one-holder projects unchanged (test).
- [ ] Item 3: cause named in the report; fixed to ≤ 0.02 mm on straight moves, or reported as not small.
- [ ] Item 4: a test with a 90° corner at high feed cuts within 0.05 mm of the corner; sample time before/after named.
- [ ] Item 5: X-axis tool and holder STEPs (generated) read with the right tip and axis.
- [ ] Tooltips, guide "Tools" chapter, PC-check line `milling.tools` extended (no new line needed unless visible).
- [ ] Tests; GitHub green; merged to `main`, next free version, released (CLAUDE.md section 7).
- [ ] Report filled in; `TASKS.md`: 0049 done, 0041 "open – can start".

## Not in this task

Tool-change animation, pockets, ATC (0041). Coolant (0042). Way covers (0035). The owner's files.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured:**

**Open points / follow-up tasks:**
