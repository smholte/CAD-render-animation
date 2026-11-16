# 0145 – Split the demo project's tests: one GitHub job is near the 40-minute limit

**Who:** worker · **Status:** done 16 Nov · **Branch:** `claude/cad-render-task-0145-spnzfk`
**Started by:** lead chat, 16 Nov 2026 (from 0134's report) · **Model:** Opus · effort Medium ·
**Place:** Claude Code on the web, environment "CAD-render-animation"
**Area (Test machinery lane):** `tests/test_demo_project.py` (and new `tests/test_demo_*.py` files split from it),
`tests/conftest.py` / a shared fixture module for the made demo, `tools/ci_groups.py`, `tools/ci_times.json`,
`.github/workflows/tests.yml` only if needed. **No app code.**
**Do not edit:** `fresing_render/` (any), the Web 3D lane (0142 runs there).

## Goal

No GitHub job comes near the 40-minute limit again: the demo project's tests run as several pieces in parallel
groups, each well under ~12 min, the whole run back near its usual length.

## Background

- 0134's report (16 Nov): `tests/test_demo_project.py` has grown to ~22 min alone (tasks 0126/0137 added shots; one
  test 8.5 min). `ci_times.json` re-recorded (184708b) gave it a group of its own; main's run 43798006405 went green but
  **that group took 35.1 min** – one more demo stage pushes it over GitHub's 40-minute job limit and every run fails.
- It has 23 tests; nearly all use one fixture `made` (Make demo once: ~4–9 min) and then check stages. The same was
  done for the clash check in task 0108 (`tests/test_demo_clash.py`: windows in 4 processes) – see CLAUDE.md section
  5 and section 8 ("A test that is longer than the others sets the length of every run").

## What to do

1. Measure each test's time on the web machine (`--durations=0`) and the fixture's.
2. Make the demo **once per run** and share it: e.g. one small job/fixture that makes the demo project and hands the
   saved `.blend` + cache to the others (a file in the workspace, an Actions artifact between jobs, or GitHub's cache
   keyed on the demo maker's and the app's code), so split files do not each pay the ~5–9 min make. Choose the way
   that keeps runs reliable; say why.
3. Split the tests into files of roughly equal time (by shots / topics), each ≤ ~10 min including its share of the
   set-up; the slow 8.5 min test split or sped up if it can be without loosening it.
4. Re-record `ci_times.json` from a green run so the groups balance; the precheck still passes.
5. Nothing loosened: the same checks, the same numbers.

## Done when

- [x] Longest job of a full run (and of the demo groups) measured before/after; no job above ~15 min; whole run time
      before/after in the report. (Demo jobs ≤ 9.9 min; two jobs outside this task's area still reach 16–18 min:
      named under Open points.)
- [x] Every test still runs and checks the same things (count before = after).
- [x] GitHub run green twice in a row (reliability); merged (no app version needed if only tests/tools changed – say
      so); report.

## Not in this task

App code; other slow tests unless they are now the longest job (then name them in the report).

---

## Report (filled in by the chat that did the task)

**Chat / date:** worker, Claude Code on the web, 16 Nov 2026 (branch `claude/cad-render-task-0145-spnzfk`). No app code
changed, so no app version and no release.

**What changed:**
- **The demo is made once per run.** `tests/demo_made.py` makes it (`python tests/demo_made.py <dir>`, a program of its
  own) and writes `made.json` + a copy of the model files beside it. On GitHub a new job **"Linux - make the demo
  project"** makes it (3.7–3.8 min) and hands the folder on as the run artifact `demo-made` (~250 MB, kept 1 day); the
  new jobs **"Linux - test suite demo 1 … 4"** unpack it at the same place and set `FRESING_DEMO_MADE`. Why an artifact
  and not GitHub's cache: the cache would have to be keyed on all the app's code, which nearly every push changes – it
  would miss nearly always, and then every job would make it again at once. On a chat machine the first demo file of a
  pytest session makes it, the others reuse it (a lock file; tried with two files in one session).
- **`test_demo_project.py` split by topic** into `test_demo_project.py` (made, joints, couplings, cylinders, drivers,
  scenes, save/reopen, Cancel, failure, stages, Help menu), `_cable.py` (shots 3–5, tracks, X-ray labels), `_cps.py`
  (shots 8b, 9), `_quadrant.py` (shots 10–12, wires, hidden parts), `_lowering.py`. The shared helpers moved to
  `demo_made.py`. Every test body is byte-for-byte the old one (checked with `ast`), except the lowering test:
- **The lowering test's clash check** (the slowest test: 770 s on GitHub) runs as 12 windows of frames in 4 processes,
  with the same child and the same proof as the demo's whole check (`demo_clash_child.check_in_windows`): 0 rows,
  every moment and every step between two checked, start overlaps from the first frame. GitHub 444 → 357 s.
- **The demo's clash check in two jobs:** `test_demo_clash.py` checks the even windows, the new `test_demo_clash_b.py`
  the odd ones. Each part proves each of its windows held every moment from its first frame to its last; part 0 proves
  the windows follow on each other from the first frame to the last (together: the old proof). The workers start once
  the saved build is read; the re-build and its fingerprint check run while they work (they waited 239 s before, now
  154–172 s). Locally both parts together: 3,806 moments and 46,760 moments between frames – exactly the old single
  check's.
- `tools/ci_groups.py`: files that import `demo_made` go into `DEMO_GROUPS` = 4 groups of their own (precheck output
  `demo`, checked: every file in exactly one group); `.github/workflows/tests.yml`: the two new jobs, the verdict needs
  them; `tools/ci_times.json` recorded from runs 43822741781 and 43826800383; test `test_demo_files_have_groups_of_their_own`;
  CLAUDE.md (section 5 table, a "Things learned" line).

**Tested and measured** (GitHub's runners; the web machine = this session's 4-core machine):

| | Before (main, run 43798006405) | After (run 43822741781) | After (run 43826800383) |
| --- | --- | --- | --- |
| Whole run | 42.5 min | 18.6 min | 20.1 min |
| Longest job | test suite 1 (demo project) 35.1 min | Windows install 17.3 min | test suite 7 16.8 min (queued renders, see below) |
| Demo jobs | 35.1 (project) + clash in suite 2 (12.2) | make 3.7, demo 14.3 / 8.1 / 6.2 / 5.8 | make 3.8, demo 5.5 / 6.3 / 9.2 / 9.1 |
| Demo's path (precheck → make → longest demo job) | – | 18.3 min | 13.4 min |

- Tests: before 23 (`test_demo_project.py`) + 3 (`test_demo_clash.py`) = 26; after 23 + 3 + 1 = 27 – the same 26 with
  the same checks, the demo's clash check now in two parts (two tests). All passed on both runs and locally.
- Web machine: old single file 1,702 s (make 236 s, lowering 599 s); split files 2 + 268 + 276 + 526 s after one make
  of 239 s; lowering 599 → 274 s; demo clash 522 s → 337 + 375 s in two parts.
- GitHub runs of the branch: 43822741781 (green), 43826800383 (green, the clash check in two parts), 43829445081
  (green, `main` merged + times recorded; 26.5 min – a busy GitHub: several plain groups SLOW, Windows 18.4 min, demo
  jobs 4.8–9.9 min, make 5.2), then one more because `main` moved again (task 0142) before the fast-forward. 4 runs
  in all, no failure.

**Open points / follow-up tasks:**
- Not demo: the longest jobs are now **test suite 7** (16.8 min in run 43826800383: `test_video_labels.py`'s queued
  video 381 s + `test_video.py`'s 180 s in one group – the queued renders vary 290–630 s, CLAUDE.md section 8) and
  **Windows - install + self-test** (16.4–17.3 min; CLAUDE.md still says 5.7–6.7 min) – they now set the run's length.
  Suggest a Test machinery task: the two queued-video tests in different groups (or split), and look at why the
  Windows job doubled.
- A new demo check goes into a new `test_demo_project_<topic>.py` with `from demo_made import made` (CLAUDE.md
  section 5), not into a longer file.
