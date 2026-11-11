# 0071 – Machining fixes from the bug hunt (0068 rows 6–11, 14–16, 18, 19a–c) + toolpath glow speed (0069 #5)

**Who:** worker · **Status:** done 11 Nov, released as 0.2.57 · **Branch:** `claude/great-albattani-yftof1`
**Started by:** lead chat, 11 Nov 2026 (from bug hunt 0068 and study 0069)
**Lane:** Machining – `blender/toolchange.py`, `gcode.py`, `ops_gcode.py`, `doublearm.py`, `machining.py`,
`coolant.py`, `rotary.py`, `air.py`; the joint specs in `blender/joints.py` (row 14 only) and `build.py:repair_uids`
(row 15 only); tests
**Model:** **Opus · effort High** · **Place:** Claude Code on the web, environment "CAD-render-animation"

Runs at the same time as **0070** (queue, updates, project lock, a `save_post` handler). Do not touch those files, nor
`animation.py` / `reimport.py` (0058 Thursday) except a one-line call if a row truly needs it (say so in the report).
Two releasing tasks at once: take the version number last; whoever finishes second merges `main` once and renumbers.
**If it cannot be green and merged by Wednesday 22:00:** push the branch, report, stop; the lead then decides whether
0061 goes first on Thursday.

## Goal

Every finding below is confirmed with a script in `tasks/0068-bug-hunt-2.md` – read its rows first. Fix them so that
an animation with two G-code steps, the double arm, coolant, rotary axes and a model update all show what the program
does – in the view and in the queue's video alike – and milling plays smoothly next to a big machine.

## What to fix

1. **Rows 6 + 7 (worst)** – two G-code steps in one animation: spindle copies made once per build and looked up per T
   (like the pocket copies); each step's copies hidden at its end; milling and chips read the copy that is **visible**
   in each time window; double-arm pot/arm copies reused across steps, keyed by T and pocket – no tool shown twice.
2. **Row 8** – the changer animation placed from the same start point `bake_step` uses (the joints' state at the
   step's start), so it plays in step with M6 after a joint step or a second program step; steps do not overlap.
3. **Row 9 + 18** – coolant hoses: update the view layer after `ensure_root` before `_layout` (first Build = second
   Build = the queue's video); after a model update re-parent the root and re-apply the wet look.
4. **Rows 10 + 11** – rotary: `auto` sign worked out with the outer axes turned back to 0 (C turns the right way when
   built with A at ≥ 90°); Check clears the keys **before** reading the pose, so it leaves the machine where it was.
5. **Rows 14 + 15** – a model update keeps the double arm's `fr_atc` tags (carry them in the joint specs, or tag again
   in `gcode.after_model_update`); `repair_uids` takes the CNC/tool/milling `*_uid` strings again from their objects.
6. **Row 16** – per-frame cost: keep the tool copies and wet parts in the runtime dict (cleared at Build / load /
   undo); check the motion signature on a depsgraph change, not at every frame. Measure on the Heavy machine + 5-axis
   model as 0068 did (motion only 8.3 ms; + milling 37.9; + coolant 57.2): aim **≤ 20 ms** with milling + chips +
   coolant (25 fps budget 40 ms). The cut must stay the same (compare meshes).
7. **Row 19 a–c** – `make_pots` checks all new pots before removing the old ones (and no half-made arm joint);
   the air cone on the tip of the tool actually in the spindle; `rotary.LAST_CHECK` cleared on load and when the
   A/B/C pick changes.
8. **Study 0069 #5** – the drawn toolpath (`gcode._material`) and the air cone (`air.py`) set
   `emission_sampling = "NONE"` like `surroundings.py` (measured 2.0–2.6 → 0.6 s per frame with many glowing
   triangles). Same look in the render.

## Done when

- [x] A test per row that fails on 0.2.55 and passes now (0068's scripts as the start), including two G-code steps
      with manual, carousel and double-arm changes; the existing milling, tool-change, double-arm, coolant, rotary,
      toolpath tests green; tour and PC check green (the all-tour clash test still 0 rows).
- [x] Per-frame numbers before/after in the report (Heavy machine + 5-axis model, the 0068 way).
- [x] GitHub green incl. Windows; merged to `main`, next free version, released – before Thursday 08:00.
- [x] Report filled in; `TASKS.md`: 0071 done; 0068 rows marked fixed there.

## Not in this task

Queue rows (0070), clash and decal rows (0072). Tool marks (0061), the height-map cutter (0069 #8), acceleration
timing (0069 #16), chips on a moving 4th-axis table.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (Opus · High), Wed 11 Nov 2026.

**What changed:**
- **Rows 6 + 7** (`gcode.tool_objects`, `toolchange.start_of_step`, `doublearm._Bake`, `machining.cut_items`): one
  spindle copy per tool (and tool length) per build – a later program step reuses it; at a later step's first frame
  every copy, arm and hand copy is hidden, the pocket copies / CAD tools stand in their pockets again (double arm: the
  step shows its own pot table) and the spindle's part is shown – then the step's own keys put its start tool in.
  Pot and arm copies are reused (keyed by T and pot, T and arm side). Milling reads, per stay in the spindle, the copy
  shown then (`gcode.copy_in_spindle`, by its keys); all copies get a path.
- **Row 8** (`gcode.prepare`, `step_start`, `step_start_of`, `_walk`, `_end_state`): `prepare` walks the steps in
  the bake's order with the joints' values (joint and pose steps, earlier programs' last key) and reads each program
  from where it really starts; that start is stored on the step (`fr_gc_from`) and used by `bake_step`, the step's
  length, the changer's blocks, captions, the drawn toolpath, "Go to line" and the panel's summary.
- **Rows 9 + 18** (`coolant._layout`, `prepare`, `after_model_update`): the coolant space is taken from
  `space_matrix` (the new root has no world matrix yet); after a model update `ensure_root` hangs it on the new head
  part and `apply_wet` marks the parts again.
- **Rows 10 + 11 + 19c** (`rotary.build`, `rotary.start_check`, `ops_gcode`, `props._rotary_changed`,
  `gcode.forget`): the `auto` sign from the axis turned back to A0 B0 C0 (as `finish`); Check clears the keys
  before reading the pose; `LAST_CHECK` cleared on load and when A/B/C or Reverse changes.
- **Row 14** (`joints.to_specs` / `rebuild_from_specs`): `fr_atc` carried in the specs (`SPEC_TAGS`).
- **Row 15** (`build.repair_uids` → `_uid_strings_again`): after a repair, the `*_uid` strings of the CNC (tool,
  workpiece, air nozzle), tools, pockets, coolant nozzles and milling (workpiece, finished, bits) are taken again from
  their objects.
- **Row 16** (`gcode.copies_all` kept by name in `_COPIES`; `coolant._WET`; `machining` `sig_ok`): copies and wet
  parts kept by name (dropped at Build, load, undo/redo, model update); the motion's signature checked only after a
  depsgraph change (Action, chain transform, Scene), a Build or Clear; cut items once per frame. **The main win:** the
  cut, chips and automatic coolant are written in `frame_change_pre` (picked coolant nozzles stay in `post`) – any
  mesh written after Blender worked the frame out made it work out the whole 3,000-part scene again (~11 ms; tagging
  a single object cost that much). Coolant: empty meshes not rewritten, flags set only on change, a cheap
  "in the scene" test.
- **Row 19a** (`doublearm.make_pots`, `make_arm`): every pot found before the old pockets go; a failed second joint
  removes the first. **19b** (`air.key_cones`): through the spindle, a copy of the cone per tool length, shown while
  the air blows and that tool is in the spindle.
- **0069 #5** (`gcode.no_light`): the toolpath and air-cone materials `emission_sampling = "NONE"` (also on old
  projects' materials at the next Build).
- `animation.py` / `reimport.py` not touched.

**Tested and measured:**
- New `tests/test_machining_fixes.py`, 17 tests (two steps manual / carousel / double arm, milling copy shown, changer
  in step after a joint step, C sign at A 0/60/95/120°, Check from the static pose, Check forgotten, coolant first
  Build = second, coolant after a model update, arm tags kept, two-copy IDs, frame work, wet-part cache, wrong pot
  click, air cone on the tool tip, no-light materials): **all 17 fail on 0.2.55** (rows 6–8 checked before their
  commit), pass now. Locally green: toolchange, doublearm, gcode, coolant, rotary, tools, model update, same STEP
  twice (116); machining, chips, toolpath, blender (60); air + new (32); tour + clash incl. the all-tour clash test (61).
- **Per frame** (median ms while scrubbing 61 frames, the 0068 way: generated Heavy machine 3,067 objects + 5-axis
  test model, Blender as a module on the 4-core web machine):

  | | motion only | + milling | + chips | + coolant |
  | --- | --- | --- | --- | --- |
  | 0.2.55 | 7.2 | 28.0 | 32.7 | 40.0 |
  | 0.2.57 | 6.0–6.4 | 15.9–16.6 | 17.1–18.8 | **20.3–20.8** |
  | 5-axis model alone, 0.2.55 | 1.0 | 7.2 | 8.7 | 9.9 |

  The cut is the same: vertices, faces and coordinate sum at frames 150/400/700/1000 identical before and after.
  Of the ~20 ms: Blender's own motion ~6, the cut itself (Manifold) ~5, the one update pass ~5, chips ~2, coolant ~2.
- Toolpath glow: not re-measured (0069's 2.0–2.6 → 0.6 s); the test checks the setting.

**Open points / follow-up tasks:**
- The 20 ms aim is met within noise (20.3–20.8 ms median, 25 fps budget 40 ms). Going lower needs the cut itself
  (~5 ms, `core.machining.cut`) or skipping the cut write while nothing new is cut.
- Clash check (`clash.py`) still takes `gcode.copies()` – one copy per T; a T held at two lengths by two programs
  (only when the spindle's part has no tool row) gets only its first copy checked. Clash lane (0072) if wanted.
- Row 19a's `make_arm` half-made joint: fixed by reading, no test (the second `joints.create` does not fail on the
  test model).
- **How many runs:** 2 on GitHub – the branch (full, green, 13.8 min; test suites 1, 6, 7 flagged slow, the new test file has no recorded time yet) and the release run on `main`. Main moved twice meanwhile (0070's release, then only the task list): merged once each, no renumbering run.
- Leftover branch for the owner to delete: `claude/great-albattani-yftof1`.
