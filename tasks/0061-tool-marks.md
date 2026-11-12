# 0061 – Tool marks on cut faces that follow the toolpath

**Who:** worker · **Status:** open – can start (Fable day, 12 Nov; split over subagents, see below) · **Branch:**
`task/0061-tool-marks`
**Started by:** lead chat, 10 Nov 2026 (owner's priority 3 of the big features, 9 Nov: "milled faces own look now,
toolpath marks later")
**Lane:** Machining – `core/machining.py`, `blender/machining.py`, `ui_machining.py`, `ops_machining.py`; reading
(not changing the meaning of) `core/gcode.py` moves (feed, spindle) and `core/tools.py` (flutes); the cut-face look
in `core/machining.py` `cut_look` / `core/materials_lib.py` (additive: a marks part of the cut-face material);
`blender/props.py` (additive); tests; guide "Milling > Cut faces"; PC-check line; test tour stop
**Model:** **Fable · effort High** (the owner's "Fable day") · **Place:** Claude Code on the web, environment
"CAD-render-animation"

Runs at the same time as **0058** (Flex parts lane: `flex*.py`, hooks in `handlers.py`, `animation.py`,
`reimport.py`). Do not touch those, nor coolant, chips, air or toolchange files. Two releasing tasks at once: take the
version number last (CLAUDE.md section 2); whoever finishes second merges `main` once and renumbers.


## Split with subagents (owner, 12 Nov 2026 – CLAUDE.md "Subagents in a worker session")

Suggested split (the worker may change it; write the final plan under "Design" first):
- **Worker:** the design and the interfaces (the move table and the per-face attributes: names, units, one row per
  cutter id), `props.py`, `ui_machining.py`, integration, tests on GitHub, release.
- **A – which move made each face** (`core/machining.py`: an id per cutter, the table, kept through split/cache;
  `blender/machining.py`: the attributes on the milled mesh via `foreach_set`) + tests (two passes across each other).
- **B – the marks** (`core/materials_lib.py` / `cut_look`: the node group for bottom arcs + anisotropic tangent,
  flank lines, scallop arcs, chamfer lines, drill rings; strength per material) + a pure-Python mirror of the formula
  and its test.
- **C – dark facets** (0042 point): the cut faces' normals (flat faces flat, smooth by angle, no shading across
  sharp edges) + a before/after picture.
- **Then:** D – **independent tests** from the "Done when" list by an agent that wrote none of A–C (spacing within
  5 %, re-cut marks, scripts off, queue); E – speed measurements (scrubbing, rebuild, render) one at a time; F – tour
  stop, PC-check line, guide section + picture.

## Goal

A milled face shows the marks of the tool that made it, in the direction the tool went: the swirl arcs of a face mill
on a faced top, the fine arcs and cross-hatch of an end mill's floor, the feed lines along a pocket wall, the
step-down lines of a wall cut in several depths, the scallops between ball-mill passes, the rings at the bottom of a
drilled hole. Today (0.2.43, task 0051) every cut face gets one generic "machined" texture that ignores the toolpath,
so a faced block looks brushed in a random direction. The owner makes milling videos of his Fresing mill for the
landing page and customers: the close-ups must look like a real part off a real machine.

## Background – what is there

- **Cut faces are already known.** `core/machining.py` `Workpiece._tile_mesh` gives every triangle a `source`: the
  stock's CAD face, or -1 when a bit made it. It does this with Manifold's `run_original_id` (the stock's id is
  kept through every boolean). `blender/machining.py` puts the -1 triangles in the cut-face material slot
  (`CUT_SLOT`, look from `cut_look`).
- **The key step for this task:** give each cutter solid its own id (`Manifold.as_original()`) and keep a table
  *id → (bit, segment, its start/end, tool, feed, spindle)*. Then every cut triangle knows **which move made it
  last** – Manifold carries the id through later booleans, so where a later pass re-cuts a face its marks replace
  the old ones, and where it does not, the old marks stay. That is exactly how a real part looks.
- Cutters: `core.Cutter` (convex pieces of the tool profile swept along straight segments, `find_segments`), one per
  segment, built in `blender/machining.py` (~line 996). Tiles are split and cached (`Workpiece.cut`, `_split`,
  `mesh(cache)`); the ids survive `split_by_plane`.
- Feed (mm/min) and spindle (rpm, sign = direction) per move: `core/gcode.py` `Move.feed`, `Move.spindle`.
  Flutes: `core/tools.py` (tool library, 0040). Without G-code (a bit animated by joints) there is no feed: use a
  typical feed per tooth per block material (a small table of your own, e.g. aluminium 0.05 mm, steel 0.03 mm) and
  say so in the panel.
- 0046 made the procedural machining marks (ground, turned, milled, brushed) in `core/materials_lib.py`; 0051 the
  cut-face looks per block material (`cut_look`).
- 0042 noted: the test block's draft mesh shows **dark facets in reflections** on cut faces (also without coolant).
  Tool marks make reflections the main thing you see, so fix the cut faces' normals here (flat faces flat; curved
  walls smooth by angle; no shading across a sharp edge).

## What to build

1. **Which move made each cut triangle** (above): ids per cutter, the table stored with the milling state (not as
   a huge ID property – `idprops.store_array` rules, CLAUDE.md section 8), written onto the milled mesh as
   attributes when the mesh is rebuilt (`foreach_set`, the fast path of `build._new_mesh`): for each cut face the
   move's start point, direction, tool axis, tool radius (and corner radius), mark spacing, tool type and which
   side of the tool cut it (bottom / flank / ball / chamfer / drill tip – from the face normal against the tool
   axis and the profile).
2. **The marks, in the cut-face material** (Cycles and EEVEE, scripts off: shader nodes only, no Python drivers):
   - *Bottom of a flat or bull-nose tool (face mill, end mill floor):* arcs of the tool radius whose centres move
     along the path; spacing = feed per revolution (face mill) or per tooth. For a point p on the face: along =
     (p − start)·dir, side = distance across; leading edge s = along − √(R² − side²) (trailing edge the + sign for
     the faint cross-hatch of the heel); marks = a ridge function of s / spacing. The direction of the arc at p
     (perpendicular to p − centre, in the face) is also the **tangent for anisotropic reflection** – that sheen,
     not the ridges, is what makes a face-milled top look real from a distance. Ridges and sheen both.
   - *Flank (walls):* fine lines across the feed direction spaced by feed per tooth, plus the step-down lines where
     two depths meet (these come from the geometry: make sure the normals show them).
   - *Ball / bull-nose passes:* scallops are in the geometry when the detail allows; add the fine arcs across each
     pass.
   - *Chamfer / V:* lines along the path. *Drill tip:* rings round the hole's axis.
   - Marks strength from the material (aluminium bright and crisp, steel finer, cast iron dull, plastics only faint
     lines, no anisotropy).
3. **Settings** in 4 Motion > Milling > Cut faces: **Tool marks** tick (on by default for new set-ups; old projects
   get it too, like 0046's new looks, with the tick to turn it off), **Mark size** Real ↔ Visible (real spacing is
   often 0.05–0.3 mm – sub-pixel in a whole-machine shot, where only the sheen shows; Visible scales the spacing up
   for close-ups, e.g. up to ×10), **Strength**. Tooltips on all; the panel line says where the feed came from
   ("from the program: F800 S12000, 2 flutes" / "no program: typical feed for aluminium").
4. **Everywhere the cut shows:** view, scrubbing, the render queue in the background, stills, turntables;
   unchanged speed of scrubbing (measure: the mesh rebuild with the new attributes, before/after, on the test mill
   and on the Heavy long milling cut). Model update (0052) and save/reopen keep it working; old projects open.
5. **Test tour stop** "Tool marks on cut faces" in the Machining group (`blender/tour.py`, a set on the test mill
   with a faced top, a pocket and a drilled hole; camera close to the face), `MIN_LINES_TOUR` +1,
   `MIN_CHECKS["tour"]` +1. **PC-check line** `milling.marks` with a Cycles still (`ctx.picture`) and the rebuild time
   (`ctx.metric`), `MIN_LINES_FULL` +1. Guide: "Cut faces" section with a picture (test mill only).

## Done when

- [ ] Each cut triangle knows the move that made it last; a re-cut area shows the new marks, an untouched area the
      old ones (test: two passes across each other).
- [ ] Face mill on the test mill: arcs with the right radius and spacing (pure-Python mirror of the node formula +
      one small Cycles render measured along a line: spacing within 5 % of feed/rev at Mark size Real ×10).
- [ ] End mill pocket: floor arcs in the feed direction, wall lines, step-down lines visible; drilled hole rings.
- [ ] Anisotropic sheen follows the arcs (a render with a light behind shows the swirl).
- [ ] No dark facets on the cut faces of the test block (0042 open point); picture before/after in `tasks/img/`.
- [ ] Works with scripts off, in the queue, after save/reopen and model update; old projects open.
- [ ] Scrubbing speed measured before/after (test mill + Heavy milling cut); render time with/without marks
      (Cycles, processor) in the report.
- [ ] Tour stop, PC-check line, guide section + picture, tooltips; tests for the new code; GitHub green incl.
      Windows; merged to `main`, next free version, released (CLAUDE.md section 7).
- [ ] Report filled in; `TASKS.md`: 0061 done; what the owner should look at on his RTX 3090 (his three-tool demo).

## Not in this task

- Real surface roughness as geometry (displacement) – shader only.
- Chatter marks, built-up edge, burrs, tool wear. Turning (lathe) marks.
- Making toolpaths (0029, merged before this one if on time: its programs are ordinary G-code, so the marks must work
  on them too – run its tour stop once). 4th/5th axis is task 0066 (merged before this one starts, if on time): cuts made
  during a rotary move may keep the plain milled look, but must not break – run 0066's 4-axis test model once.
- Coolant, chips, air, tool changes; anything in the Flex parts lane (0058 runs at the same time).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
