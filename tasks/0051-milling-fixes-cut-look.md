# 0051 – Milling fixes from the bug hunt, and milled faces get their own look

**Who:** worker · **Status:** running · **Branch:** `claude/cad-render-task-0051-qkvu7v`
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

- [ ] Cut faces with their own look (Automatic / Same as the block / Pick); old projects → Automatic; queue = view.
- [ ] *Aluminium, sawn plate* and *POM, black* in the library, ready-made list and chips map.
- [ ] Picture for the report: the test mill block with a pocket, before/after (Cycles, small, generic shapes), and
      the new look on the material sheet (`tools/material_sheet.py`).
- [ ] Rows 3, 13, 15, 16 fixed with a test each (row 13: test or reasoning in the report); 20c if small.
- [ ] Chips keys for the new materials; 0037 problems 4 and 6.
- [ ] Render time of the milling test scene before/after (should be the same).
- [ ] Tooltips; guide "Milling" chapter (cut faces, raw stock looks) and its picture; PC-check line `milling.*`
      checks that cut faces have the cut material.
- [ ] Tests; GitHub green; merged to `main`, next free version, released (CLAUDE.md section 7).
- [ ] Report filled in; `TASKS.md`: 0051 done, 0041 "open – can start".

## Not in this task

Tool marks along the toolpath (later). Tool changes / ATC (0041). Coolant (0042). Way covers (0035). The queue's
own faults (0054). Materials of the machine's parts (0046 is done; only add new ids here).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
