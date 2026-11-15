# 0127 – Tests that fail at random: find the cause, fix it

**Who:** worker (web) · **Status:** done (15 Nov, no version change) · **Branch:** `ccr-bbe8fc8f-l3cyzo`
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

**Chat / date:** worker, Claude Code on the web (branch `ccr-bbe8fc8f-l3cyzo`), 15 Nov 2026. No subagents.

**What changed:**
1. **`milling.rotary` – cause found and fixed (app, `blender/gcode.py`).** `gcode._rest_tip` cached a tool's tip by
   (name, mesh name, point count, *the mesh's memory address*), and the cache lived on when another project was opened.
   The 5-axis and the 4-axis test models both have "TOOL T1 FLAT D6" with the same mesh name and 106 points, but the
   tips lie 40 mm apart in the tool's own space (z 0.23 / 0.19 m). After `read_homefile` + import, the 4-axis tool's
   mesh now and then got the freed 5-axis mesh's address (same size of memory), so the program drove the 4-axis tool by
   the 5-axis tip. **Proof:** forcing exactly that stale tip reproduces GitHub's failure to the digit – radius 24.82,
   24.82, 25.00, 25.00 mm and the cut 45 s (GitHub run 43585100027: the same radii, 43 s); 36 normal runs here: all OK.
   The tests never saw it because `tests/test_rotary.py` clears `gcode._CACHE` by hand before each model; the PC check
   opens many projects in one Blender. **Fix:** the tip is cached by the mesh's points (`_shape_sig`, a hash of the
   coordinates), and `gcode.forget()` (runs when a project is opened) drops the read programs and tips too.
   Test `test_rotary.py::test_a_tool_tip_never_comes_from_another_projects_tool` – fails on the old code ("a tool tip
   of the project before is still kept"), passes now. The PC-check line also says more when it fails
   (`checks._rotary_why`: how near the path's tip comes to the bar's axis, read and cut times, the bar's and A's angle,
   processors).
2. **`test_table_moves_the_follower` – cause found; the test's fix was already on `main` (ed3cd6f, 13 Nov).** All four
   GitHub failures (runs 43488885387, 43498738567, 43506904896, 43517923768) were the line that read the follower's
   driver-written value copy `motion["fr_value"]`, never the part's turn or `joints.get_value`. Reproduced here: that
   copy is one step behind in 11 of 40 runs of the test's loop, but only while the follower's motion has its second
   driver (the turn): with that driver taken off, 0 of 80; also with ratio couplings (6 of 30), not only tables. A bare
   case of two empties (the leader with a driver on itself, the follower with a driver on a custom property and one on
   its rotation, the value set from Python) does it too: 17 of 3,000; with keyed values played as frames: 0. Tagging
   the follower as well does not help (14 of 3,000). So it is inside Blender 5.2.3's driver evaluation; the app already
   reads `get_value` everywhere. The test's comment now names the cause; CLAUDE.md section 8 has the line.
3. **All-sets clash test split:** `tests/test_tour_clash.py`, one test per tour set (37), each builds only its own
   project (`tour.build_all(only=...)`) and has its own time box (150 s); `test_every_set_was_checked` makes sure no set
   is left out and ≥ 15 animations were checked. Same checks as before. Removed from `tests/test_clash.py`;
   `tools/ci_times.json` recorded from the green run.
4. **Repeats in the last two days' failed runs** (37 runs with a failed job, 13–14 Nov; most were work in progress
   on a branch – version clashes, missing pictures, unfinished code):
   - `milling.rotary`: runs 43525519601, 43585100027 (and 0067, 0070 earlier) → fixed (1).
   - `test_table_moves_the_follower`: 4 runs → (2).
   - the all-sets clash test's time box: run 43621844399 (365 of 360 s) → (3).
   - `ui_test_spool.py` "'level' typed into its search": runs 43469849219 (task 0108) and 43621844399 (task 0122),
     two branches. The button's spot was read from the side panel before its layout settled (clicked at y 1486 / 1512;
     green runs click at 1596 – 3–4 rows apart), so the click missed. Fix: the click waits until two reads a second
     apart give the same spot (at most 10 reads); the checks are unchanged.
   - "2 tests were skipped" (3 runs) and pytest exit 134 (3 runs), 13 Nov: EEVEE without a screen; fixed by task
     0108 (none since).
   - once each, on one task's branch and fixed there: `test_render_fades_in_cycles` 0.81 (0122), the stack-axis click
     (0122), `test_carried_guide…` (one branch, 3 runs).

**Tested and measured** (4-core web machine, test models from `tests/data`):
- `test_table_moves_the_follower`: 50 of 50 in a row, and 50 of 50 with 4 busy processes beside it.
- `milling.rotary` (bpy module): 36 runs, all OK – alone, under load (6), 12 hash seeds, after the four G-code lines
  before it (8), with a fresh import cache each (9); real Blender in the PC check's first half: OK. Cut 4–9 s.
- `tests/test_tour_clash.py`: 38 passed, 316 s in all; longest piece toolpath 45 s, then house 28 s, crane 28 s
  (before: one test of ~300 of 360 s here, 171–365 s on GitHub).
- `test_rotary.py`, `test_gcode.py`, `test_toolchange.py`, `test_doublearm.py`, `test_tools.py`: 91 passed;
  `test_clash.py` + `test_joint_table.py`: 26 passed; `ui_test_spool.py` in the real app: 43/43 (the button read
  twice, clicked at y 1596 as in green runs).
- GitHub: run 43670249797 on the branch green (16.6 min, a busy GitHub: 5 groups flagged slow); there the split clash
  test took 255 s in all, its longest set 39 s (toolpath), then house 29 s, crane 20 s – each far from its 150 s box
  (before: one test of 171–365 s against 360 s). `milling.rotary` OK in the PC check. Times recorded into
  `tools/ci_times.json` from that run; the merge with `main` ran once more: run 43671649506 green (20.1 min, busy GitHub). 2 runs in all, no failure; `main` fast-forwarded to that commit (0557782).

**Open points / follow-up tasks:**
- Motion lane: the joint panel shows a follower's value from `motion["fr_value"]` (greyed), which can be one step
  behind after a change (2.). Show `joints.get_value` there instead.
- Watch point: `decals._mesh_arrays` keys on `me.as_pointer()` too (kept only 5 s, counts checked).
- No version change (the fix reaches the owner's PC check with the next release).
