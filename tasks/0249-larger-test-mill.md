# 0249 – The small test mill replaced by a larger vertical machining centre (~1000 × 500 × 500 travel) – test mill, toolpath mill, the mill in its own enclosure with sliding doors

**Who:** worker · **Status:** open – waits for 0230 (the `mill` set and `blender/lessons/mill.py`) and 0239
(`core/tc_person.py`) · **Branch:** `task/0249-larger-test-mill`
**Started by:** lead, 20 Nov 2026 (owner 23:35, screenshot of stop 54 "A person changes the tool": "this mill is not
allowed to be in Fresing Render. Replace it with a larger mill. This size gets closer to the one I'm building for
Fresing 400." His picks 23:40 in the answer box below.) · **Model:** Opus · effort High
**Area:** Test models lane – `tools/make_test_mill.py`, `tools/make_test_mill_cabinet.py` (becomes the VMC with its
own enclosure – keep the file name or rename with every caller), `tools/make_test_toolpath.py`, `tools/machine_parts.py`
(new shared parts only), their STEP files in `tests/data/` and `fresing_render/data/`; the tour sets that use them
(`mill`, `tools`, `marks`, `air`, `coolant`, `operator`, `toolpath`) and their checks / texts in `blender/tour.py`;
`blender/lessons/mill.py` (0230's mill lesson: part names, places, framing); `core/tc_person.py` / `blender/tc_person.py`
(the person's reach, stand spot, door, button – numbers only); `blender/toolpath.py` only where it holds this model's
numbers; `pccheck/checks.py` (the lines on these models); the tests that read them (list in "Where it is used");
`tools/guide_screens.py` + the guide pictures and texts of these stops; `tools/bench_*milling*.py`, `bench_chips.py`.
**Not** the double-arm, 4th- and 5th-axis mills (→ 0250), not the gantry router, not the demo.

## Why

The owner's own machine, the **Fresing 400**, is close in size to today's small test mill (bed 700 × 500, table
400 × 300) and is **not to be shown in any form** (owner 12 Nov). The test mills must be clearly a different, larger
class of machine, so nobody can read the Fresing 400 into them.

## Owner's picks (20 Nov 23:40)

- **Size:** a vertical machining centre (VMC) with travels about **X 1000 × Y 500 × Z 500 mm**, table about
  **1200 × 500**, about 2.5 m tall with its own enclosure.
- **Which:** all small mills – this task the test mill, the cabinet mill and the toolpath mill; **0250** the double-arm
  ATC mill and the 4th- / 5th-axis mills, built on this task's machine.
- **"A person changes the tool":** the machine stands on the floor **in its own sheet-metal enclosure with front
  sliding doors** (like a real VMC); the person opens the doors and reaches in. No separate cabinet stand.
- **Old copies:** from now on only – the small mill leaves `main` and every new release; old releases and git history
  stay (as for the vessel, 0226).

## The machine (invented – nothing of a real make, nothing of the Fresing 400)

- Fixed column behind the table (C-frame), the table moves in X on a saddle that moves in Y, the head in Z – the
  common VMC layout. Bed / column as heavy castings with ribs, chamfers; way covers on X and Y (the app's way covers
  can follow them – a bellows or telescopic look); a chip tray round the table.
- **Spindle taper BT40** (not BT30 – BT30 is the Fresing 400's): the BT30 tool holder of the cabinet mill becomes BT40,
  and every text that says BT30 for these stops says BT40 (stop 54, 58 "Tool change by hand (BT30)", guide).
- Enclosure: sheet-metal box with two front sliding doors with windows, a door handle, a control panel arm on the
  right (a plain box with a screen – no maker look), a work light, the release (drawbar) button reachable from the
  front. The person (`tc_person`) stands on the floor in front of the doors – no step, no stand.
- **Keep the workpieces, tools and programs:** the stock 200 × 200 × 40, the finished part, the end mill / ball mill,
  the clamps and the G-code / toolpath tests stay as they are, on the bigger table – put the **work zero in the same
  place relative to the stock** so the machining numbers, cut checks and tool marks need no new expected values where
  possible. Keep the part and assembly names the app and tests look for (`TABLE.ASM`, `X.ASM`, `Z.ASM`, `SPINDLE`,
  `END MILL D10`, `STOCK …`, `RELEASE BUTTON`, `SLIDING DOOR` …); add a `Y.ASM` / saddle only if the tests' joints are
  updated with it.
- **Coolant drain** (owner 20 Nov 23:50, for 0251's liquid): a chip tray under and round the table with a slope,
  troughs along the way covers and a **drain hole** (a separate part `COOLANT DRAIN`) – if 0251's report is out, use its
  list for the tray and drain; else a plain sloped tray to one drain at the front right.
- Detail and size: more detail than today is welcome (owner 22:19: somewhat larger files allowed) – **up to about 4 MB
  per STEP** (today 1.5–1.8 MB); report the sizes and the import time at Normal.

## Where it is used (lead's grep, 20 Nov – check it)

`blender/tc_person.py`, `blender/tour.py` (sets above), `pccheck/checks.py`; tests: `test_air`, `test_chips`,
`test_coolant`, `test_cut_normals`, `test_gcode`, `test_lightbake`, `test_lightbake_break`, `test_machining`,
`test_pccheck`, `test_section`, `test_tc_person_blender`, `test_tc_person_blender_independent`, `test_toolmarks_done`,
`test_toolmarks_moves`, `test_web3d`, `test_web3d_keys_blender`, `milling_crash_child.py`, `test_toolpath`,
`test_fast3axis_hole`, `test_machining_fixes`; tools: `facets_picture.py`, `guide_screens.py`, `ui_test_milling.py`,
`bench_chips.py`, `bench_milling.py`, `bench_milling_dense.py`, `dump_toolpath_program.py`. Guide pictures:
`air_blast.jpg`, `coolant.jpg`, `milling_marks.jpg`, `tools.jpg`, `toolchange_person*.jpg`, `view_toolchange_hand.png`,
`view_toolpath.png`, `panel_4_*` / `panel_6_gcode*` where the model shows. Also look in `site/`, `docs/`, the PC-check
report pictures and `fresing_render/web/` for any picture of the small mill.

## Checks

- Every test above green with the new model; numbers that had to change listed in the report with the reason.
- Stop 54 played through on the new machine: the person walks up, opens the sliding doors, reaches the holder and the
  button without the hands entering the castings or the enclosure (0239's stand spot + 0156's checks), lays the tool
  on the trolley, closes the doors; the clash check on the person and doors clean.
- Every stop of the sets above framed on the bigger machine (the whole machine or the cut, as each stop's text says);
  the tour record (`tour_versions`) re-recorded after merging `main` once.
- A search of the repository for the small mill's sizes / names in pictures and texts comes back empty (except
  `tasks/` and `CHANGELOG.md` history).
- The user guide and PC-check lines updated (`changed=` on the stops' entries).

## Report

Pictures of the new machine **from the test models only** (fine for the repository), the STEP sizes and import times,
the changed numbers, what 0250 should reuse (the shared parts in `machine_parts.py`), open points, the branch to
delete. Owner's PC steps: test tour > Machining > 54 and 58, Go; Milling a slot.
