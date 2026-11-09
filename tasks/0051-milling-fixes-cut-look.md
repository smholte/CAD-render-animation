# 0051 – Milling fixes from the bug hunt, and milled faces get their own look

**Who:** worker · **Status:** done (0.2.43) · **Branch:** `claude/cad-render-task-0051-qkvu7v`
**Started by:** lead chat, 9 Nov 2026 (bug hunt 0045 rows 3, 13, 15, 16, 20c; 0046 open point "chips";
0037 problems 4 and 6; owner's wish 9 Nov: fresh-cut faces and raw stock looks, his points 1 and 2)
**Lane:** Machining – `blender/machining.py`, `core/machining.py`, `blender/ops_machining.py`, `ui_machining.py`,
`core/chips.py` / `blender/chips.py`, `core/gcode.py` / `blender/gcode.py` / `ui_gcode.py` (rows 16, 0037 problems 4
and 6 only); additive: `core/materials_lib.py` (new materials only), `blender/decals.py` (row 3 only); tests; guide
"Milling" chapter
**Model:** Opus · effort Medium · **Place:** Claude Code on the web, environment "CAD-render-animation"

Runs before 0041 (same lane). Runs at the same time as 0052 (Motion), 0053 (Quality & delivery) and 0055 (Looks):
do not touch `reimport.py`, `joints.py`, `updates.py`, `update_helper.py`, `project_lock.py`, `props.py`
`_group_renamed`, `handlers.py`, `core/part_types_data.py`, or `ops_motion.py` (row 16 is fixed in `gcode.py` alone).

## Goal

In a milling video the block keeps its raw look outside, and everything the tool has cut shows as fresh, bright
metal (or fresh plastic). Four milling faults from the bug hunt are gone, and the new materials of 0046 throw the
right chips.

## Part A – milled faces get their own look (owner, 9 Nov)

Now: `machining.refresh` gives every face of the cut mesh the block's material slot (`mats[src]`); faces made by the
cutter (`src < 0`) get slot 0, so a pocket in a mill-scale block looks like mill scale inside.

1. **Cut faces get a separate material.** Faces from the cutter get their own slot with a "fresh cut" material
   chosen from the block's material:
   - aluminium of any kind (raw plate, anodised, profile) → *Aluminium, machined*;
   - steel raw / machined / ground / turned, zinc-plated, black oxide → *Steel, machined*;
   - stainless → *Stainless, brushed* (or a machined variant if it looks better);
   - cast iron (as cast, painted) → a bare machined cast iron (new material if needed: grey, a little dull);
   - brass / bronze / copper → the same metal, bright;
   - plastic (POM/PE, plastic) → the same plastic, a little more matte;
   - anything else → the block's own material.

   Faces of the CAD block that are only partly cut keep the block's material (one material per face is enough;
   no blending).
2. **Milling panel setting** "Cut faces" with a tooltip: *Automatic (fresh cut)* (default) / *Same as the block* /
   *Pick a material…* (the ready-made list). Old projects open with *Automatic*.
3. **New raw stock materials** (`materials_lib.py`, new ids and numbers only, old ones unchanged):
   *Aluminium, sawn plate* (rolled plate: slightly dull, faint rolling lines along the longest side; for the block's
   outside) and *POM, black*. *Steel, raw / mill scale*, *Cast iron* and *POM / PE, white* already exist. Add them to the
   ready-made materials and to the chips map.
4. The finished-part option (`settings.finished`), the queue, stills and videos all show the cut look the same as the
   view. Test that a queued still has the cut slot.
5. Not in this task: tool marks that follow the toolpath (swirls on floors, lines on walls, face-mill arcs) – owner
   chose "later" (point 3); write it into the report's open points as a later task.

## Part B – fixes (proof and suggested fix in `tasks/0045-bug-hunt.md`, table rows)

- **Row 3 – decal on the workpiece emptied** by any edit while milling is on, and stays empty after Stop milling.
  Take decal geometry/settings from `settings.stock_mesh` when the part is the milled workpiece, and clear
  `fresing_decals` on the cut copy. Test: the row's proof gives > 0 triangles before, during and after.
- **Row 13 – milling frame handler on the render thread** (suspected crash). Return early in `_on_frame` when not on
  the main thread (the cut shown is already right), or lock the interface for UI renders; say which one and why.
- **Row 15 – chips rebuild the whole dependency graph every frame.** Assign the node group's Collection only when it
  changed. Measure the frame change on the row's scene before/after (was 168 ms with chips).
- **Row 16 – G-code step summaries cached by memory address.** Key the cache by program signature + step settings;
  clear it on file load. Test: the row's proof (remove step 1 → the other step shows its own 203 lines).
- **Row 20c – milling frame code** checks `name in scene.objects` ~13× and walks `bpy.data.objects` 3× per frame:
  cache per frame (3–5 ms per frame now). Only if it stays small.
- **0046 open point – chips of new materials:** add `steel_ground`, `steel_turned`, `chrome_rod` → STEEL,
  `cast_iron_painted` → CAST_IRON (plus Part A's new ids) to `core/chips.py:_MATERIAL_KEYS`.
- **0037 problem 4:** picking the spindle in 4 Motion > CNC machine ticks Motor itself (no warning after Build).
- **0037 problem 6:** `gcode_file` accepts a "//" relative path (no warning), and a program picked next to the project
  is stored relative, so the project works on another PC. Check that the queue copy still finds it (bug hunt row 18
  is the same problem for other paths – that row belongs to 0054; only the G-code file and tool table here).

## Done when

- [x] Cut faces with their own look (Automatic / Same as the block / Pick); old projects → Automatic; queue = view.
- [x] *Aluminium, sawn plate* and *POM, black* in the library, ready-made list and chips map.
- [x] Picture for the report: the test mill block with a pocket, before/after (Cycles, small, generic shapes), and
      the new look on the material sheet (`tools/material_sheet.py`).
- [x] Rows 3, 13, 15, 16 fixed with a test each (row 13: test or reasoning in the report); 20c if small.
- [x] Chips keys for the new materials; 0037 problems 4 and 6.
- [x] Render time of the milling test scene before/after (should be the same).
- [x] Tooltips; guide "Milling" chapter (cut faces, raw stock looks) and its picture; PC-check line `milling.*`
      checks that cut faces have the cut material.
- [x] Tests; GitHub green; merged to `main`, next free version, released (CLAUDE.md section 7).
- [x] Report filled in; `TASKS.md`: 0051 done, 0041 "open – can start".

## Not in this task

Tool marks along the toolpath (later). Tool changes / ATC (0041). Coolant (0042). Way covers (0035). The queue's
own faults (0054). Materials of the machine's parts (0046 is done; only add new ids here).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, branch `claude/cad-render-task-0051-qkvu7v`, 9 Nov 2026 – released as 0.2.43.

**What changed:**
- **Cut faces' own look** (Part A): the milled mesh gets one extra material slot after the block's own slots
  (`fr_cut_slot`); faces the cutter made use it, uncut faces keep their CAD face's slot. Setting **Cut faces**
  (Automatic / Same as the block / Pick a material…, `cut_look`, `cut_material`); old projects open with Automatic
  and get the slot at the next frame. Automatic is `core/machining.cut_look(block id)`: a library material plus
  tweaks (no new ids for the cut looks): aluminium → *Aluminium, machined*; raw/machined/ground/turned/plated steel,
  black oxide, chrome → *Steel, machined*; stainless → stainless without brushing, with milling marks; cast iron
  (both) → grey machined iron; brass/bronze/copper/nickel → same metal, 0.1 less rough, milling marks; plastics →
  same plastic, +0.12 roughness; paint and the rest → the block's own. Materials "FR_cut …" rebuilt when the look
  changes; a group look change in 3 Looks shows at once. Stop milling takes the slot off again.
- **Found on the way:** uncut faces never kept their CAD face: Manifold's `original_id()` of the stock is -1, so every
  face counted as cut (painted CAD faces on a milled block also showed slot 0). Fixed in `core/machining.Workpiece`
  (the id is read from the mesh's run).
- New library materials *Aluminium, sawn plate* (47) and *POM, black* (48); chips map for those plus `steel_ground`,
  `steel_turned`, `chrome_rod`, `cast_iron_painted`.
- Row 3: decals live on the CAD mesh (`decals.cad_mesh`); the milled mesh's copied list is cleared, older projects
  are mended on the next frame. Row 13: **both** – milling locks the interface for renders started in the window
  (`use_lock_interface`, also set on load for projects that mill), and `_on_frame` returns at once off the main thread
  when the lock is off (user switched it off). Why both: returning early alone would freeze the cut in a Ctrl+F12
  animation from the window; the lock alone can be undone by the user. In the background (queue) nothing changes.
  Row 15: the node group's Collection is set only on change. Row 16: summaries keyed by program (file size + time or
  the kept copy) + every `gcode_*` setting; cleared on file load. Row 20c: per-frame memo of "part in scene" and the
  tool copies (`machining._FRAME`), copies only read with a tool schedule.
- 0037 problem 4: `gcode.spindle_is_motor` ticks Motor once per newly picked spindle (unticked by hand it stays off).
  Problem 6: `gcode_file` / `tool_table` allow `//`; a file in or below the saved project's folder is stored as
  `//…`; the absolute path is kept (`fr_gcode_abs`, `fr_tool_table_abs`) and used when `//` finds nothing (the
  queue's copy lives in `_queue/<time>/`).
- PC-check line `milling.cut_look` (MIN_LINES_FULL 41 with the lines of 0052 and 0053); real-app milling test +1 check (25); guide: Milling (Cut
  faces, logos), raw stock in "What the materials look like", spindle Motor, program next to the project; pictures
  `panel_4_milling.png`, `material_sheet.jpg`.

**Tested and measured** (4-core web session, no graphics card):
- New tests: `test_machining.py` (cut look, Same/Pick, old project, decals ×2, render thread, objects walked once,
  queued still shows the cut look – fails with "Same as the block"), `test_chips.py` (chip keys; frame change does
  not update every object – failed before the fix), `test_gcode.py` (summaries after removing a step – failed before:
  5 lines instead of 203; spindle Motor; relative program/tool table, queue copy, moved project folder).
- Row 15, test mill + 3,000 empties, chips Few, median frame change: **88.9 → 23.2 ms** (bug hunt measured 168 ms).
- Row 20c, same scene, milling only, the frame handler: **7.0 → 3.6 ms** per frame (cProfile, 58 frames).
- Render time of the milling test scene (pocket, Cycles CPU, 480 × 320, 64 samples), Same as the block → Automatic:
  steel 7.84 → 8.04 s, aluminium 8.48 → 8.77 s (+3 %: the milling marks in the cut material).
- Pictures: `tasks/img/0051_cut_look_cycles.jpg` (top: mill-scale steel, bottom: sawn aluminium; left Same as the
  block, right Automatic), `tasks/img/0051_new_materials_cycles.jpg` (sawn plate, machined, POM black/white, mill
  scale, machined steel).
- Locally: the tests of the changed areas, `ui_test_milling` (25/25), PC-check lines milling.cut / cut_look / chips,
  tooltip check 474/474. GitHub: see runs below.

**Open points / follow-up tasks:**
- Later task (owner, 9 Nov): tool marks that follow the toolpath on cut faces (swirls on floors, lines on walls,
  face-mill arcs) – the cut faces now have their own material, which that task can build on.
- Picking a face *on the milled block* (paint faces, a new decal) while milling uses the milled mesh, which has no CAD
  faces: stop milling (or switch Cut material off) to place a decal on the block. Not changed here.
- Bug hunt row 18 (other `//` paths in the queue copy) stays with 0054; the G-code file and tool table no longer need it.
- Runs: 2 on the branch. Run 42617370033 green (full, 14.1 min; test suites 1, 3, 4 and callouts flagged SLOW, 11–13 min
  against 4–9 usual – the whole run was slow, not one test); then 0052 took 0.2.41 meanwhile, so main was merged
  again and the version renumbered to 0.2.42 (second run, green: 42619684638); 0053 took 0.2.42 meanwhile, so once more: 0.2.43 (third run), then main fast-forwarded to it (reuse).
- Leftover branch for the owner to delete on github.com: `claude/cad-render-task-0051-qkvu7v`.
