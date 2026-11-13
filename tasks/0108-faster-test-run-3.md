# 0108 – Faster test run (round 3): shorter runs, also when several tasks push at once

**Who:** worker · **Status:** done · **Branch:** `task/0108-faster-test-run-3`
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

**Chat / date:** Claude Code on the web (worker), 13 Nov 2026. No version change (no app code): no release.

**Measured first** (GitHub, green full runs 43435919960, 43438261138, 43442195417, 43440853982): runs took 14.8–19.7 min
alone, 156–171 job-minutes on ~25 jobs. Start-up per job is small (0.3–0.7 min: venv and Blender come from the cache);
no queueing in those runs. The minutes are the tests themselves. Floors: the demo project's file (one group, 7–18.5 min;
its clash check 321–801 s), the PC check job (14.3 min), the tour (8–12.4), suite groups up to 14 min. Slowest test
functions: demo clash check 801 s, air queue render 325–627 s, phase2 queue still+video 232–288 s, video labels
208–374 s, idprops queue MP4 135–276 s, video "every option" 166–183 s, tour automatic run 156–164 s, tour clash check
139–147 s. Profile of the demo clash check (4-core web machine): 800 s, of which 23 s reading frames and 757 s the
pair tests at each moment, on one core.

**What changed:**
- **Demo clash check split by frames** (`tests/test_demo_clash.py` new, `tests/demo_clash_child.py` new; the test left
  `test_demo_project.py`, whose fixture is unchanged): the animation in 36 windows, 4 worker processes take them one at a
  time. **As strict as before:** every moment and every step between two moments lies in a window (asserted); start
  overlaps are measured at the animation's first frame, held parts and once-per-turn pairs are decided once over the
  whole animation as the whole check does, and each window gets its slice. Proof test on the clash test model: the
  windows give exactly the whole check's rows (pairs, frames, depth) and start overlaps, incl. the post caught between
  two frames; a window measuring from its own first frame would have allowed the arms 2.9 mm more. On the demo the
  windows make exactly the whole check's 38,835 moments between frames, 0 rows. The saved project is built: workers
  do not build again (the test builds again and asserts the same key fingerprint); the whole animation is read once
  and handed over in a file.
  Seconds: locally the check 800 s on one core → 172 s per worker (file 5.8 min); GitHub: test 801 s + fixture 98 s in
  a 18.5 min group → 412 s + 115 s (file 8.9 min, run 43474297961).
- **PC check halves rebalanced:** `render.eevee` + `queue.eevee` (120 + 155 s) to `pccheck-b`; its small UI tests to
  scenes/motion. pccheck 14.3 → 9.1–10.4 min, pccheck-b 5.5 → 8.4–9.4. Windows skips `milling.toolpath`, `motion.fade`
  (51 + 33 s, pure app code, still run on Linux).
- **Test tour in two jobs** (`tour`, `tour-b`: every other stop, both make the projects; the precheck checks they add
  up to every stop of `blender/tour.py`): 9.8–12.9 min → 9.2 + 6.2.
- `paths` real-app test from paths-heavy (9.4–11.7 min) to machines: paths-heavy 6.0–7.3.
- **9 pytest groups** (was 7), balanced on recorded times; `tools/ci_times.json` re-recorded (run 43476950544).
- `tools/ci_pytest_summary.py`: skips that mean "no GL context" / "no real Blender" no longer count against
  `--max-skipped` (two EEVEE tests landed in one group and turned it red); any other skip still counts. Test added.
- CLAUDE.md sections 2, 5 and 8 updated.

**Tested and measured:** GitHub runs on the branch: 43458109736 green 16.9 min (3 tasks' runs at once: 8 jobs queued
5 min); 43469849219 red (the skip rule above; and `ui_test_spool.py` failed 8 of 43 checks once – passed 43/43 locally
and in every other run: flaky, not touched here); 43474297961 green 14.7; **43476950544 green 12.4 min alone, no
queueing**, 170 job-minutes on 28 jobs (before: 156–171 on ~25). Longest jobs there: suite 8 12.0 (two queue
renders: idprops 276 s + video 183 s), Windows 11.1, pccheck 10.4. Test counts: pytest +3 (demo_project −1,
demo_clash +3, ci_tools +1); real-app checks and PC-check lines the same (moved between jobs; the tour's
"Make test tour project" now runs in both tour jobs). After merging main twice (0079, 0109 came in; 0109's weather lines joined pccheck-b): runs 43480381561 green 12.7 min and
43482661794 green 15.8 min (suite 2 ran 15.4 min, flagged SLOW: the runner, not the plan). Runs needed: 6 on the branch
(one red, above; two after merging main).

**Not reached:** "≤ about 11 min" – 12.4 min alone. What is left is queue renders whose time varies 2x between runs
(air 290–627 s alone in a group; idprops 135–276; video labels 190–374) and the Windows job (7–11 min).

**Open points / follow-up tasks:**
- **Proposal (not done), queue-render tests** – the floor now: the air test's queue render renders 21 frames at 12–17 s
  each locally, of which the picture is ~4 s (measured: the same frame rendered in-process at the same size); the rest is
  the app's per-frame work in the background run (milling, chips, air). Options for the lead: (a) an app task that makes
  that per-frame work cheaper (helps users too); (b) run `test_air.py::test_queue_render_blows_the_part_clean`,
  `test_idprops.py::test_queue_makes_the_mp4_after_the_count_changed` and `test_video_labels.py`'s queued video daily on
  `main` instead of at every push (a scheduled workflow; a red daily run would need a line in TASKS.md "Problems found" by
  the workflow or a check in `ci_status.py` that every session runs at its start).
- **Task 0110 (clash check faster) is running** and changes `blender/clash.py`: `tests/demo_clash_child.py` subclasses
  `Check` and uses `_start`, `_hold_still`, `_still_pairs`, `windows`, `unround`, `round_memo`, `band_memo`. Whoever
  merges second keeps `test_demo_clash.py` green; better: 0110 gives `Check` a supported way to check a window of
  moments with the whole animation's decisions, and the child uses that.
- With 9 + 10 jobs a run uses 20 jobs at once when alone (GitHub's free limit, from its documentation): two tasks pushing
  together still queue. Fewer machine-minutes per run needs the queue renders above to get cheaper.
- `ui_test_spool.py` step "'level' typed into its search, Enter" failed once on GitHub (spool lane).
