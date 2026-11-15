# 0132 – Motion follow-ups: follower value in the joint box, Back to CAD after a Take apart, Put together's first-frame jump

**Who:** worker · **Status:** open – can start · **Branch:** `task/0132-motion-follow-ups`
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

- [ ] 1: the joint box shows the follower's real value right after a change (test that failed before the fix);
      other `fr_value` readers listed in the report.
- [ ] 2: Back to CAD after a Take apart = that sequence backwards; 0 clash rows; other Back to CAD cases unchanged
      (0129's tests still pass); guide sentence in the Back to CAD section.
- [ ] 3: no false clash rows from a step's own jump; real ones still found.
- [ ] Tooltips, function list (0124) and tour stops still right; tests; GitHub run green; merged; version (CLAUDE.md
      section 7); report.

## Not in this task

Other Motion-lane wishes; the CPS run (0126); the side-panel overhaul (0062); preview-plan speed on big subassemblies.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
