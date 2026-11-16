# 0145 – Split the demo project's tests: one GitHub job is near the 40-minute limit

**Who:** worker · **Status:** open – can start now · **Branch:** `task/0145-split-demo-tests`
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

- [ ] Longest job of a full run (and of the demo groups) measured before/after; no job above ~15 min; whole run time
      before/after in the report.
- [ ] Every test still runs and checks the same things (count before = after).
- [ ] GitHub run green twice in a row (reliability); merged (no app version needed if only tests/tools changed – say
      so); report.

## Not in this task

App code; other slow tests unless they are now the longest job (then name them in the report).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
