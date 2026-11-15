# 0132 – Motion follow-ups: follower value in the joint box, Back to CAD after a Take apart, Put together's first-frame jump

**Who:** worker · **Status:** running · **Branch:** `task/0132-motion-follow-ups`
**Started by:** lead chat, 15 Nov 2026 (owner: "all tasks") · **Model:** Opus · effort Medium
**Area (Motion lane; the clash part in the Clash lane, free):** `blender/ui_motion.py` (the joint box only – **not the
cable boxes**: task 0126 may touch those), `blender/sequence.py`, the Back to CAD code in `animation.py` (additive),
`core/clash.py` / `blender/clash.py` only for point 3, their tests, the guide sections of these steps.
**Do not edit:** `demo_model/`, `demo.py`, `paths*.py` (0126); `site/`, `tools/site_projects/`, `marine_looks.py`
(0128); `house_*` (0130).

## Goal

Three small faults left open by tasks 0127 and 0129, fixed so the owner never sees them.

## Background

1. **Follower value one step behind** (0127 report, point 2 and open points): the joint box shows a follower's value
   from the driver-written copy `motion["fr_value"]` (greyed). With a second driver on the follower's motion (the turn)
   that copy is one step behind after a change (11 of 40 in 0127's loop; also with ratio couplings). Show
   `joints.get_value(...)` there instead (the same value the tests now read). Check the other places that read
   `fr_value` for display or decisions (grep) and say in the report which you changed and which are safe.
2. **Back to CAD right after a Take apart** (0129 open points): all parts fly home at once on straight lines, so bolts
   pass through the cover (0129's tester: 4–7 mm). When the step before Back to CAD (for that subassembly) is a Take
   apart, Back to CAD plays that sequence backwards (the same ways, last part out first in), as Put together would;
   in every other case it stays as it is. Test on `test_sequence.step` / `test_sequence_frame.step`: 0 clash rows.
3. **Put together with no Take apart before it** (0129 open points): its parts jump out at the step's first frame and
   the clash check reads that jump as motion (rows that are not real). The clash check must not sweep a jump that a
   step makes on purpose (a cut between two frames); the view stays as it is. Test: a Put together alone → 0 rows,
   a real clash in the same project still found.

## Done when

- [x] 1: the joint box shows the follower's real value right after a change (test that failed before the fix);
      other `fr_value` readers listed in the report.
- [x] 2: Back to CAD after a Take apart = that sequence backwards; 0 clash rows; other Back to CAD cases unchanged
      (0129's tests still pass); guide sentence in the Back to CAD section.
- [x] 3: no false clash rows from a step's own jump; real ones still found.
- [x] Tooltips, function list (0124) and tour stops still right; tests; GitHub run green; merged; version (CLAUDE.md
      section 7); report.

## Not in this task

Other Motion-lane wishes; the CPS run (0126); the side-panel overhaul (0062); preview-plan speed on big subassemblies.

---

## Report (filled in by the chat that did the task)

**Chat / date:** worker, Claude Code on the web, 15 Nov 2026. No subagents (Medium task; the independent review was
skipped – no Windows-only code; the changed cases are covered by 0129's independent tests plus new ones).

**What changed:**
1. **Follower value.** `ui_motion.value_text` / `_value_row`: the joint list, the joint box ("Angle: -15.0°",
   "Distance: -40.0 mm") and the mechanism's Drive row show a follower's value from `joints.get_value` (greyed label),
   never the driver-written copy `motion["fr_value"]`. Other `fr_value` readers: `machining.py` signature – changed
   (it hashed the driven copy, so the same set-up could give another signature; now left out when a driver writes it,
   the driver itself is hashed); `ui_motion` joint-box/list/mechanism rows – changed; `ui_section.py` (the cut's slide
   joint, app-made, never a follower), `paths.py` (a data-path name list, not a value), `animation.py`, `spool.py`,
   `gcode.py` (read the top joint's keys/F-curves, not the copy), `joints.get_value`/`set_value` – safe.
2. **Back to CAD after a Take apart.** `animation.apart_before(anim, b, inside)`: the last enabled motion step before
   Back to CAD (camera, weather, show/hide, fade do not count) is a Take apart of the same subassembly, one inside it,
   or any with Whole model. Then `_Reversed` (the Take apart's settings, mode Put together, part time scaled to the
   step) is baked by `sequence.bake_step` over the step; when joints or other parts also have to go home, the reverse
   takes the first 70 % (`REVERSE_SHARE`), the rest after it. The step's box says "Right after 'Take apart …': plays
   it backwards first". Guide: Back to CAD point 4.
3. **A step's own jump.** `sequence.bake_step` (Put together) records parts whose key at the step's first frame differs
   from where they were (`Keys.jumps`); Build writes `scene["fr_jumps"]` (JSON frame → names; removed by Clear keys /
   a Build without jumps); `clash._jumps` turns it into a mask (a part or any parent listed) and the check skips the
   sweep between that frame and the one before for those parts only. Every frame is still checked. Guide: Clash check.

**Tested and measured** (4-core web machine, `test_sequence_frame.step`):
- New: `test_panel_shows_a_followers_real_value` (stale copy simulated), `test_put_together_alone_no_rows_but_a_real_clash_is_found`,
  `test_a_jump_is_only_skipped_for_the_parts_that_jump`; changed 0129 tests now assert 0 clash rows:
  `test_back_to_cad_between_take_apart_and_put_together`, `…_without_joints_brings_a_taken_apart_unit_home` (also: the
  last part out comes in first, every part on its own line), `test_riders_put_together_alone_end_on_their_carried_places`.
- Before the fixes these four failed: Back to CAD 3.8–7.0 mm rows (bolts × cover / rail block), Put together alone
  2.5 mm rows at its first frame; after: 0 rows; the portal frame driven through the unit is still found.
- Locally `test_motion_extras_independent.py`, `test_sequence.py`, `test_couplings.py`, `test_clash.py`,
  `test_product_video.py`, `test_machining.py`: 145 passed (5 min). The rest on GitHub.

**Open points / follow-up tasks:**
- Only Put together's own jump is recorded; other deliberate jumps (none known) would need the same `Keys.jumps`.
- A Back to CAD after a Take apart with a step in between that moves something else (a joint) is not reversed (by the
  brief: only when the Take apart is the step right before).
