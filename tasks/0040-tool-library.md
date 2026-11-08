# 0040 – Tool library: many tool types, real shapes, every tool cuts

**Who:** worker · **Status:** running (8 Nov 2026) · **Branch:** `task/0040-tool-library`
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

- [ ] All types made from sizes, shown right in the viewport and in a still; holders generated.
- [ ] Import of a tool STEP: tip and axis right within 0.05 mm on test tools; sizes guessed (fluted end mill: the
      outer Ø, within 0.1 mm – the 0037 Ø12 → Ø10.4 case fixed, test with a fluted test tool).
- [ ] Fusion `.json`/`.tools` and LinuxCNC `.tbl` read into the list (test files made by the worker).
- [ ] A test program with 4 tools (face mill, flat end mill, drill, chamfer) cuts each feature with the right tool:
      depths and widths within 0.05 mm of the program in the milled block.
- [ ] Missing-tool warning with line number; old projects (fixed bits, no list) open and cut as before.
- [ ] Tooltips, guide, picture, PC-check line; tests; GitHub green; merged and released.
- [ ] Report filled in; `TASKS.md` updated (0041 to "open – can start").

## Not in this task

- The tool-change animation: manual change, ATC pockets, changer motion, hand (0041). Here a change may simply
  swap the tool at the M6 frame as today.
- Downloading from the internet inside the app. Air (0039), coolant (0042).
- **Never commit downloaded manufacturer STEP files or tool libraries** (licences; public repository): make test
  tools with OpenCascade and test library files by hand.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
