# 0127 – Tests that fail at random: find the cause, fix it

**Who:** worker · **Status:** open · **Branch:** `task/0127-random-test-failures`
**Started by:** lead chat, 15 Nov 2026 (owner: "all 5 suggested tasks") · **Model:** Opus · effort Medium
**Area (Quality & delivery lane + the app file the cause is in):** `tests/`, `tools/ci_*.py`, and – only if the fault is
in the app – the one place it sits (likely `blender/joints.py` table couplings, `blender/rotary.py` /
`blender/machining.py` / `pccheck/checks.py` `milling.rotary`). Keep app changes minimal and say them in the report:
tasks 0125, 0128, 0129 run at the same time (0129 may touch `animation.py`, 0125 the paths code). **Do not edit** the
paths, flex, demo, sequence or site files.

## Goal

With four tasks pushing at once, a test that fails one time in N costs a task a whole extra run (12–25 min) and a
worker's time to prove it was not theirs. Make these failures go away by fixing their cause – never by loosening a
test or adding a blind retry.

## Background

Sightings (run ids are on GitHub; read them with `python3 tools/ci_status.py --run <id> --log "<job>"`):
1. **PC-check line `milling.rotary`:** task 0121, run **43585100027** (Linux PC check): cut radii 24.8 / 25.0 instead of
   23 / 22, the cut took 43 s instead of ~4 s; not reproducible locally (0121 ran it alone: OK). Seen once before on
   Windows (TASKS.md "0067 follow-ups": "If milling.rotary fails on Windows again").
2. **`tests/test_joint_table.py::test_table_moves_the_follower`** (task 0080's table coupling): task 0107, run
   **43488885387**, passed on re-run and 3/3 locally. 0107 suspected the driver race of CLAUDE.md section 8 ("Blender
   runs drivers on several threads … a follower one frame behind": each follower must read the top joint of its chain
   directly).
3. **Near a time limit:** after task 0122 the all-sets clash test (`tests/test_clash.py::
   test_every_tour_animation_has_no_clash`) takes 300 of its 360 s locally; on a busy runner it can time out. Split
   it (per set, or windows as `tests/test_demo_clash.py` does) so no piece is near its limit – same strictness.
4. Look through the last ~2 days of failed runs (`gh api repos/smholte/CAD-render-animation/actions/runs?status=failure`)
   for other tests that failed and then passed with no code change; list them in the report, fix the ones that
   repeat.

## Done when

- [ ] For 1 and 2: the cause is found and written in the report with its proof (what differs between a good and a
      bad run), and fixed where it is. If a cause cannot be reproduced after a fair try: the test prints enough on
      failure to find it next time (values, frame, thread count), and the report says so.
- [ ] The fixed tests run many times in a row without failing (e.g. `test_table_moves_the_follower` 50 times with
      Blender's thread count as on GitHub, `milling.rotary` 10 times) – numbers in the report.
- [ ] Point 3: the all-sets clash test split; the longest piece and the run's length before/after in the report;
      `tools/ci_times.json` recorded from a green run if the groups changed.
- [ ] No test loosened, none dropped, no retry wrappers.
- [ ] Full GitHub run green; report filled in (and a CLAUDE.md section 8 line for what was learned).

## Not in this task

Speeding up the whole run (a later task if the run stays above ~20 min). Features.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
