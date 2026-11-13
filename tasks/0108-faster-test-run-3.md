# 0108 – Faster test run (round 3): shorter runs, also when several tasks push at once

**Who:** worker · **Status:** open – can start · **Branch:** `task/0108-faster-test-run-3`
**Started by:** lead chat, 13 Nov 2026 (owner asked how to speed up the work with many tasks at once; lead: keep
merging per task, make every run shorter)
**Lane:** Quality & delivery: `.github/workflows/tests.yml`, `tools/ci_*.py`, `tools/ci_times.json`, `conftest.py` /
test helpers, and the **heavy test files only as far as making them cheaper needs** (see "Careful" below). No app code.
**Model:** **Opus · effort Medium** · **Place:** Claude Code on the web, environment "CAD-render-animation"

## Goal

A full test run on GitHub takes **about 11 minutes or less** when it runs alone (today 15–16, up to 22 when several
tasks push at the same time), and it slows down less when 3–4 tasks push at once, so the owner's tasks finish sooner.
**No test is dropped and no check gets weaker.**

## Background (recorded times, `tools/ci_times.json`, run 43423874620 of 0101, 13 Nov)

- pytest is spread over 7 groups by **whole files** (`tools/ci_groups.py`), so the slowest single file sets the floor:
  `tests/test_demo_project.py` **895 s** (a group of its own, ~15 min; its `test_no_clash_in_the_animation` alone ~781 s
  since task 0097), `test_air.py` 666 s (a queue render), `test_video_labels.py` 390 s, `test_phase2.py` 303 s,
  `test_idprops.py` 278 s, `test_clash.py` 265 s. All other groups plan to ~12.7 min.
- The other jobs: real app pccheck 14.3 min, tour 12.1, Windows install + self-test 11.3, paths-heavy 10.3; the rest
  under 9.
- One run uses about 18 jobs at once. GitHub's free plan runs **at most 20 jobs at a time per account** (expectation
  from GitHub's documented limits – check it), so 3–4 tasks pushing together queue behind each other: 0101's run took
  22.7 min, 0099's suites were flagged SLOW. Lowering the **total machine minutes** of a run helps there more than
  adding groups.
- The machinery: precheck picks full / docs / reuse (`tools/ci_precheck.py`); `ci_status.py --record` re-records
  times; new real-app tests go into `TESTS`, `MIN_CHECKS` and `GROUPS` (`tools/ci_real_app.py`). CLAUDE.md section 2,
  "Working efficiently with the automatic tests" and section 5 describe them.

## Scope

1. **Measure first** from the last 3–5 green full runs on `main` (`ci_status.py`): per job, start-up (set-up,
   Blender, venv) vs test time, queue time, and the 10 slowest test *functions* (pytest `--durations`). Say where the
   minutes go before changing anything.
2. **Split by test, not only by file** where one file is the floor: e.g. the demo project's clash check in a group of
   its own with the made project shared or cached between the tests that need it (the fixture makes it once per
   module today), `test_air.py`'s render separately. `ci_groups.py` balances on what you split.
3. **Make the heaviest tests cheaper without weakening them:** e.g. the demo clash check on the frames that matter
   (every frame where something moves against something else is still checked – prove it), shared set-up instead of
   rebuilding the same project, renders at the smallest size that still checks what the test checks. Each change named
   in the report with before/after seconds and why the check is still as strong.
4. **Fewer machine minutes per run:** start-up per job (cache what can be cached: venv, Blender, test models built
   once and passed as an artifact if that is faster), groups that are too small to be worth their start-up merged.
5. **If a test truly cannot get cheaper**, propose (do not do) running it daily instead of at every push, with how a
   red daily run would be seen by every new session – the lead and owner decide.
6. Record the new times (`ci_status.py --record`), update CLAUDE.md sections 2 and 5 (run time, how groups are made).

## Careful – other tasks are running

- **0079 tensioner tracks** (Flex parts + Demo models lane) is running and adds a demo stage `tracks` and its tests,
  most likely in `tests/test_demo_project.py`; **0106 web 3D surroundings** changes `tests/test_web3d*.py`. Do not
  edit test files of a running task beyond what scope 2–3 needs. In `test_demo_project.py` change only the fixture
  and `test_no_clash_in_the_animation` (moving it to its own file is fine); whoever merges second resolves the merge.
- A CI change reaches every task: the rules for **reuse** and **docs** runs and the precheck must keep working for
  branches made before this task (no change in what a worker has to do, unless CLAUDE.md says so in the same commit).
- A CI fix that one task needs is merged alone first (CLAUDE.md).

## Done when

- [ ] A full run on the branch, alone, ≤ about 11 min (say the run ids); the test count is the same or higher (say the
      numbers before/after: pytest tests, real-app checks, PC-check lines).
- [ ] The report lists every test made cheaper or split, with seconds before/after and why it is as strong.
- [ ] `ci_times.json` re-recorded; CLAUDE.md current; GitHub green incl. Windows; merge to main (no app release
      needed unless a version file changes – say so).

## Not in this task

App code; dropping or weakening tests; changing the merge-per-task way of working (owner, 13 Nov: keep it).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
