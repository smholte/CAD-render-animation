# 0040 – Tool library: many tool types, real shapes, every tool cuts

**Who:** worker · **Status:** done (0.2.36, 8 Nov 2026) · **Branch:** `task/0040-tool-library`
**Started by:** lead chat, 7 Nov 2026 (owner accepted: 2A-ii shapes from sizes **and** imported STEP; 2C-ii split –
this is part 1, tool changes and ATC are 0041)
**Area:** Machining lane + G-code – `core/machining.py`, `blender/machining.py`, `core/gcode.py` / `blender/gcode.py`
(tool numbers), `ui_gcode.py` / `ui_machining.py` (a Tools list), new `core/tools.py` (tool list, readers, shapes) and
`blender/tools.py` if needed; chips presets per type; tests; user guide
**Model:** Opus · effort High

## Goal

One tool list per project. A G-code program can use many tools; each tool looks like the real one and cuts with its
own shape, also after a tool change. Tools come from sizes typed in, from files the owner already has (Fusion tool
library, LinuxCNC tool table, the program's tool comments) or from a manufacturer's STEP model he downloads.

## Background

- Today (0026/0027): at M6 the app shows a copy of the next tool (a model part or a simple turned mesh from the
  sizes), but **only the fixed milling bits cut** – the copies don't (`tasks/0026-gcode-motion.md`, open points).
  Tool tip shapes known to milling: flat, ball, corner radius, V, drill point (`tasks/0027-material-removal.md`).
- 0037 problem 2: bit detection read the owner's own fluted Ø12 end mill as a flat Ø10.4 (measured Ø12.06), so a cut
  would be too narrow. Fix it here: with a tool list the cutting shape comes from the list's sizes; detection from a
  mesh only fills in the list as a first guess (outer diameter over all flutes, not the core), and the owner can
  correct it.
- The owner downloads tools from manufacturers' sites (STEP of tool + holder) and Fusion's vendor libraries.
  The app reads files; it does not browse the internet.

## What to build

1. **Tool list** (4 Motion > CNC machine > Tools): rows with T number, name, type, sizes, holder, stick-out
   length, and place (spindle / changer pocket / bench – the pocket field is used by 0041). Add, copy, delete,
   sort by T. Saved with the project.
2. **Types and their sizes:** flat end mill (Ø, flute length, flutes), ball (Ø), bull-nose (Ø, corner radius),
   face mill with inserts (Ø, number of inserts, insert size/lead angle), drill (Ø, point angle), spot/chamfer V
   (Ø, angle), thread mill (Ø, pitch), slot / T-slot cutter (Ø, width, neck Ø). Each type has a sensible default
   so a new row works at once.
3. **Shape of each tool:**
   - *From the sizes:* a clean generated mesh (flutes suggested by a simple helix or flats, inserts as small
     blocks on the face mill) and a generic holder (SK40 / BT40 / HSK63 / ER collet – simple turned shapes, sizes
     editable).
   - *Imported STEP* of the tool, or tool + holder: read with the existing importer, axis and tip found
     automatically (editable), sizes guessed into the row.
   - *A part of the model* (as today).
4. **Readers:** Fusion tool library (`.json`, and `.tools` = zipped JSON; vendor libraries exported from Fusion),
   LinuxCNC tool table (`.tbl`), Fusion's tool comments in the program (exists – now fills the list). Unknown
   fields ignored, unknown types mapped to the nearest type with a note in the list.
5. **Cutting:** milling removes material with the shape of the tool that is in the spindle at that frame (from the
   program's T/M6), for every tool, including after a change. Chips use the preset of the tool's type (face mill
   and drill presets exist; map thread mill / slot cutter to the nearest).
6. **Checks:** a T number used in the program but missing from the list → clear warning with the line number and a
   button "Add T7 as …". Tool longer/wider than plausible for the machine → warning, not an error.
7. Tooltips on every control; user guide chapter "Tools" with a picture; PC-check line (cut with a face mill and a
   drill, ms per frame).

## Done when

- [x] All types made from sizes, shown right in the viewport and in a still; holders generated.
- [x] Import of a tool STEP: tip and axis right within 0.05 mm on test tools; sizes guessed (fluted end mill: the
      outer Ø, within 0.1 mm – the 0037 Ø12 → Ø10.4 case fixed, test with a fluted test tool).
- [x] Fusion `.json`/`.tools` and LinuxCNC `.tbl` read into the list (test files made by the worker).
- [x] A test program with 4 tools (face mill, flat end mill, drill, chamfer) cuts each feature with the right tool:
      depths and widths within 0.05 mm of the program in the milled block.
- [x] Missing-tool warning with line number; old projects (fixed bits, no list) open and cut as before.
- [x] Tooltips, guide, picture, PC-check line; tests; GitHub green; merged and released.
- [x] Report filled in; `TASKS.md` updated (0041 to "open – can start").

## Not in this task

- The tool-change animation: manual change, ATC pockets, changer motion, hand (0041). Here a change may simply
  swap the tool at the M6 frame as today.
- Downloading from the internet inside the app. Air (0039), coolant (0042).
- **Never commit downloaded manufacturer STEP files or tool libraries** (licences; public repository): make test
  tools with OpenCascade and test library files by hand.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (Opus), 8 Nov 2026. Version 0.2.36.

**What changed:**
- New `core/tools.py`: 8 types (flat, ball, bull-nose, spot/chamfer, drill, face mill, thread mill, slot/T-slot) with
  defaults per type; `Spec` (sizes, 0 = "as the type usually has"); cutting shape per type (`cutting_tool`; face
  mill = its insert band, 45° lead widens upward; thread mill = its outer Ø; slot cutter = its disc); drawn meshes
  with helical flutes, face-mill inserts, thread teeth, slot teeth; holders ER / SK40 / BT40 / HSK63 (simple turned
  shapes, nose Ø and gauge length editable); chip type per tool type; readers Fusion `.json`/`.tools` (zip), LinuxCNC
  `.tbl`, program tool comments; unknown types to the nearest with a note; size checks (also against the X/Y/Z joint
  limits); `from_outline` guesses a row from a part's or a STEP's outline (holder start, flute length, face mill).
- `FRCncTool` grew into the tool row (old rows keep their values: the first 5 type ids unchanged, `length` = stick-out).
  New `blender/tools.py`: rows ↔ sizes, add/copy/remove/sort, file reading, STEP import with the app's own reader
  (one combined mesh kept in the project, tip/axis found: file origin, else narrower end, else the end with more
  detail; "Tip at the other end"), part rows read their sizes from the part.
- `gcode.py`: copies at M6 come from the rows (drawn / STEP / part) and carry their sizes; **tool length offsets**
  (option "Tool lengths move the spindle", on): the spindle moves up by the stick-out difference, adjusting from the
  swap to the end of the change; the build writes which tool is in the spindle when (`cnc["fr_tools"]`); a T number
  missing from the list warns with its line ("T7 (line 4) is not in the tool list") and the step offers "Add T7 as …".
- `machining.py`: `cut_items` – with a tool schedule the bit in the spindle is split per stay in the spindle; each
  piece cuts with that tool's sizes (copies are sampled along with the bits). Without a schedule nothing changes.
  Chips use the same pieces and the type's chip preset; the air through the spindle follows the tool that is in.
- **0037 problem 2 fixed**: `core/machining.profile_from_points` reads the widest point of each cross-section from the
  triangles' edges (not only vertices), at vertex heights, an even spread and just above/below flat steps; `classify`
  looks a little above the first stop for the true radius and reads a small corner chamfer as a flat end mill.
- UI: 4 Motion > CNC machine > **Tools** (sub-panel; replaces the old "Tools for tool changes" fold). Tooltips on every
  control (report: 468 ok). PC-check line `milling.tools`; guide chapter "Tools", pictures `panel_4_tools.png`,
  `tools.jpg` (`tools/make_tool_picture.py`), `panel_4_cnc.png` again. Test tools `tools/make_test_tools.py` →
  `tests/data/test_tool_endmill.step` (fluted Ø12, end teeth, 0.3 mm corner chamfer, tilted) and
  `test_tool_facemill.step` (Ø50 face mill in an SK40 holder).

**Tested and measured** (Claude Code web session, 4 cores, no graphics card):
- 4-tool program on the test gantry (`test_tools.py`): face mill Ø50 1 deep, end mill Ø8 slot 3 deep, drill Ø6 10 deep,
  chamfer 90° 2 deep: every depth and edge checked by ray casts at ±0.04 mm – all within 0.05 mm.
- Fluted test end mill: old detection Ø11.4, new Ø12.000; tip (10, 20, 30) mm and axis (0.6, 0, 0.8) exact (< 0.001 mm),
  as a STEP row and as a part. Face mill + SK40 STEP: tip at origin, FACE, Ø50.12 (the inserts' corners), stick-out 40.0,
  insert size 12.
- Fusion json and .tools, LinuxCNC tbl, program comments (`test_tools_core.py`, 17 tests); old project with a fixed bit
  and no list: one cut item, the bit's shape; existing milling, G-code, chips, air, panels, PC-check tests pass.
- PC check `milling.tools` (bpy, 4 cores): OK, read motion 0.02 s, 4.5 ms per frame. Real app `ui_test_gcode.py`
  25/25 locally (2 new checks + the Tools picture). Tool picture render (Cycles CPU, 1400×520, 48 samples): 15 s.
- GitHub: 4 branch runs. 1st cancelled by my own second push (travel warning); 2nd red only in the PC check (Linux
  and Windows): the old line `motion.gcode` built a 2-tool program with an empty list, which now warns – the line now
  presses "Tools from the program" first, as the owner would; 3rd stopped in precheck (0.2.35 taken by task 0043:
  merged main, renumbered to 0.2.36); 4th green (11.2 min), `main` fast-forwarded to it (reuse release). Test suites
  1 and 4 were flagged SLOW in runs 2 and 4 (9.5–11.5 min vs 4–5); `tools/ci_times.json` not re-recorded.

**Open points / follow-up tasks:**
- 0041: the `place`/`pocket` fields are stored but not used yet; tool changes are still an instant swap (the spindle's
  length adjustment ramps after the swap).
- Behaviour change for projects with tool changes: rows with different stick-outs now move the spindle (untick "Tool
  lengths move the spindle" for the old look). A row whose part is the spindle's own tool is the length reference.
- STEP orientation is a guess (origin / narrower end / more detail); a tool+holder STEP whose holder end lies on the
  origin needs "Tip at the other end". Not tested with a real manufacturer file (none may be committed): worth one try
  on the owner's PC with a downloaded tool.
- Cutting length = flute length: a shank wider than the cutter does not cut (a real crash is not shown).
- Hidden objects are not updated by Blender: anything that reads a hidden tool part's position must go through its
  parent (the test does; milling only reads a tool while it is shown).
