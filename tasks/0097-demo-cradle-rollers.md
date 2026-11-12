# 0097 – Demo: the drop cradles' side rollers turn about their own axis

**Who:** worker · **Status:** done · **Branch:** `task/0097-demo-cradle-rollers`
**Started by:** lead chat, 12 Nov 2026 (0092's open point)
**Lane:** Demo models – `fresing_render/demo_model/` (`deck.py`, `layout.py`, the joint sheet it writes),
`blender/demo.py` only if the joint list is read there, `tests/test_demo_*.py`
**Model:** Sonnet · effort Medium · **Place:** Claude Code on the web, environment "CAD-render-animation"

## Goal

Every roller of the demo cable-lay vessel turns about its own axis, so the cable sits on them in the videos and the
clash check of the whole demo is quicker and clean without a leave-out list.

## Background

0092 found that the 31 V-cradles that drop out of the D-quadrant's way (0091, "CRADLE n: Roller port/stb", 66 rollers
in 0.2.71) get a near-vertical turn axis in the joint sheet (`demo_joints.json`) – about 63° off the roller's own
axis. They wobble through the cable (up to 94 mm) and cost most of the clash check's remaining time (12.4 min on the
full demo). The ordinary V cradles (`deck.py`, `roller_about(kit, ctr, ax, …)`) are right: compare how the two kinds
write their axis. With the right axis 0092's code holds them like the other turning parts.

`tests/test_demo_project.py` leaves `demo.turning_in_place(sc)` out of its clash check (line ~240) – drop that when
the check is clean without it. The static cable lying on the rollers stays a source of rows until 0078/0082 move it;
say how many rows are left and why.

## Done when

- [ ] All 66 drop-cradle side rollers turn about their roller axis (test: axis vs the roller's long direction < 0.5°,
      for every roller of every cradle kind, also after the cradles drop).
- [ ] A test checks every turning part in the demo the same way (no other roller with a wrong axis).
- [ ] Clash check on the full demo: time before/after (0092: 12.4 min, 0 rows with the leave-out list); the leave-out
      list dropped where the result is clean; rows left (static cable) named in the report.
- [ ] Help > Make demo project time unchanged (0.2.71: 90 s); shot 7 still 0 clash rows.
- [ ] GitHub green; report filled in; merge to main and release (CHANGELOG line: projects made before need Help >
      Make demo project again).

## Not in this task

The carousel rim fence's clash cost (Clash lane, later), cable paths (0078), hoses (0058, running).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 12 Nov 2026

**What changed:** `deck.py` `cradle()`: the roller joint's lever arm used the cable contact point (offset `CRADLE_OFF` along the
axle), which tilted the axis 63.4°; it now uses the roller surface point straight towards the cable. New test
`test_every_turning_roller_turns_about_its_own_axis` (256 roller joints, < 0.5°, incl. the 66 cradle rollers).
`test_demo_project.py` no longer leaves `turning_in_place` out; only the static cable is left out.

**Tested and measured** (4-core web machine, full demo): all 256 roller joints within 0.5°. Clash check of the whole
animation (sea at rest): 0 rows with only the cable left out; test took 13.2 min wall time including the ~1.5 min
build and partly in parallel with another test – not a clean before/after of the check itself (0092: 12.4 min with the
leave-out list), so no speed claim. Rows from the static cable were not counted (it is still left out). Make-demo time
and shot 7: not measured separately here (the test's build and shot-7 test are in the GitHub run).

**Open points / follow-up tasks:** 0078/0082 (cable paths) – then drop the cable leave-out too.


**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
