# 0063 – Faster test run again (back to about 12 minutes)

**Who:** worker · **Status:** done (10 Nov), alongside 0064 · **Branch:** `task/0063-faster-test-run-again`
**Started by:** lead chat, 10 Nov 2026 (review of 0060: the full run is still ~16 min, the Windows job is now the
long pole)
**Lane:** Quality & delivery – `.github/workflows/`, `tools/ci_*.py`, `tools/ci_times.json`, `tools/ci_groups.py`,
`tools/ci_windows_install.ps1`, test *grouping* and test *speed* only (fixtures, shared set-up), CLAUDE.md section 5
**Model:** **Sonnet · effort Medium** · **Place:** Claude Code on the web, environment "CAD-render-animation"

Thursday 12 Nov two Fable tasks (0058, 0061) run at the same time and both profit from a shorter run, so finish
when you can – no hard deadline (owner, 10 Nov: don't hold tasks back for Thursday). Runs alongside **0064**
(Machining lane, releases a version): if both change `GROUPS` / `MIN_CHECKS` in `tools/ci_real_app.py`, whoever
merges second merges `main` once and keeps both.

## Goal

Every task waits for the full GitHub run once or several times; the owner waits with it. Since task 0036 a full run
took 11–14 min (median 12.8); today it takes **15.7–18 min**. Bring it back to **about 12 min or less, without
running fewer tests or weaker ones**.

## Background – today's numbers (runs on 10 Nov)

| Job | Run 42815485418 (0060 branch, after its regrouping) | Run 42814987723 (main, 0050) | 0036 (6 Nov) |
| --- | --- | --- | --- |
| Total | **15.7 min** | 18.0 min | 12.8 (median) |
| Windows – install + self-test | **14.6 min** (starts after the 0.7-min build) | 14.5 | 9.8 (PC check 4.5) |
| Linux – test suite 4 / 1 / 3 / 2 | **13.7** / 12.4 / 10.9 / 8.4 | 11.2 / 5.7 / 13.3 / 15.8 | 4.6–6.1 |
| Real app pccheck / motion / callouts / scenes / ui / paths-heavy / tour | 11.1 / 10.2 / 8.0 / 8.2 / 8.1 / 7.5 / 4.7 | – | 6.5–12.4 |
| Landing page (after a release, run 42817806576) | **9.9 min** (was ~0.3–1 min) | 0.3 | ~1 |

So there are three long poles: the **Windows job** (it alone now sets the total), **Linux suites 4 and 1**, and the
**landing-page job** after a release (does not hold up a task, but makes "released" ~10 min later than needed).

The 0060 report: times were recorded from run 42812649917 only; "suite 4 / 1 are still the long pole: record again
from the next full run".

## What to do

1. **Find out where the time goes** (read the logs through `tools/ci_status.py --run <id> --log …`, no guessing):
   - Windows job: which steps grew from 9.8 to 14.6 min – the PC check Full (30 → 46 lines since 0.2.24), the old
     build's self-update, the self-test? Time each step.
   - Linux suites: the ten slowest test files and the slowest single tests (`pytest --durations=25` per group in the
     log; add it if it is not there). Why do suites now take 8–14 min when the 0036 split gave 4.6–6.1?
   - Landing page job: why 9.9 min this time.
2. **Make it faster.** Ideas, pick what the numbers support:
   - Record times from **two or three** recent green full runs (not one) and rebalance; let `ci_groups.py` use the
     slowest time seen per file, so one fast run does not unbalance the next.
   - Split the biggest test files, or move expensive shared set-up into session-scoped fixtures (build a test model
     once per group, not per test). Do not change what a test checks.
   - A fifth (or sixth) Linux suite if the split alone cannot reach the goal (runners are free; the owner pays only
     waiting time).
   - **Windows job:** keep everything that is Windows-specific on Windows (install, repair, shortcuts, update helper,
     folder with a space and an accent, `LOCALAPPDATA`, self-test, uninstall, the PC-check *launch* from its Start-menu
     shortcut and its report). The PC-check lines that only test the app (same code as on Linux, already run in the
     Linux `pccheck` group) may run in a Quick or a selected set on Windows – **only** if the Linux job runs the full
     set, and say in CLAUDE.md which lines run where. Alternatively split the Windows job in two parallel jobs (update
     path / fresh install + PC check). Whichever is faster and keeps the coverage.
   - Landing page job: fix what made it slow (e.g. a download or encode that should be cached), or explain why it
     cannot be faster.
3. **Measure:** two full runs on the branch after the change, both green. Record their times (`--record`).

## Done when

- [ ] Report says where the time went, with the numbers per job before and after.
- [ ] Two green full runs on the branch, **each ≤ 13 min** from push to verdict (goal ~12).
- [ ] No test removed, skipped or weakened; `MIN_CHECKS`, `MIN_LINES_FULL`, `MIN_LINES_TOUR` unchanged or higher; every
      PC-check line still runs on at least one runner every full run (CLAUDE.md says which on which).
- [ ] Landing-page job back to about 1 min, or the reason written down.
- [ ] CLAUDE.md section 5 (the job table, the times, "about 11–14 minutes") updated to the new numbers.
- [ ] `tools/ci_times.json` recorded from the new runs.
- [ ] Merged to `main`. **No new version** – no app code changes (like 0031/0036's
      CI-only parts); if you find you must change app code, stop and ask the lead.
- [ ] Report below filled in; leftover branch named for the owner.

## Not in this task

App code (`fresing_render/`), the test tour's stops, the PC check's lines themselves (only *where* they run), the
release jobs' logic (publish / update check / offer). 0058 (Flex parts) and 0061 (Machining) start Thursday – they
must find `main` green.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**

**Chat / date:** Claude Code on the web, 10 Nov 2026.

**Where the time went** (run 42815485418, 15.7 min): Windows job 14.6 min = update + install/repair ~3.5 min, **PC check Full 10.3 min** (46 lines; video.labels 217 s, queue.video 101, queue.time_test 68, scene.turntable 59, tour.make 35, looks.materials 22, milling.coolant 21), Heavy 0.4 min. Linux pytest: 4 groups of ~13 min each (total ~52 min of tests); one test, `test_air.py::test_queue_render_blows_the_part_clean` (queued render in a background Blender), takes ~576 s alone; other queue tests 130–260 s. Real app: pccheck 11.1 min (same lines), callouts/surroundings/ui1 each one test of 6–7.5 min, motion 10.2 (nine tests in one job). Landing page 9.9 min: the Pages service stayed in `syncing_files` for ~9.5 min (step "Publish", `deploy-pages`); the same workflow's runs on site pushes take 22–26 s, so it is GitHub's service, not our build. Nothing in our workflow can speed that up; it comes after "Offer the release", so it holds nothing back.

**What changed** (CI only, no app code, no version): (1) pytest in **7 groups** (`PYTEST_GROUPS`), `test_air.py` alone in one; `ci_times.json` keeps the last 3 times per file and balances by the slowest (`ci_status.py --record`, `merge_file_times`). (2) Real-app jobs regrouped: pccheck, pccheck-b, callouts, paths-heavy, tour, ui, scenes, motion, machines (largest ones alone; comment in `ci_real_app.py`). (3) PC check Full split in two Linux jobs (`tools/ci_pccheck_lines.py`: `video.labels` + `queue.time_test` in `pccheck-b`, which also runs `import.crane` they need; every other Full line in `pccheck`); the precheck fails if the halves stop covering every Full line. (4) Windows runs the Full lines except 7 long app-only renders (`WINDOWS_SKIPS`), launched from the Start-menu shortcut with `FRESING_PCCHECK_ONLY`; all of them still run on Linux. CLAUDE.md section 5 says which lines run where. New tests in `tests/test_ci_tools.py`. `MIN_CHECKS`/`MIN_LINES_*` not lowered (new `MIN_CHECKS["pccheck2"]` = 2).

**Tested and measured** (GitHub runners, 4 cores): run 42827xxx failed in `pccheck-b` (the two lines need `import.crane`; fixed) after 9.1 min. Then two green full runs on the branch: **8.8 min** (42828538561) and **11.9 min** (next one; one pytest group 11.5 min that time, a slow runner). Before: 15.7 / 18.0. Windows job 5.7 / 6.7 min (was 14.6). Times recorded from the first green run (the second is recorded by the next task's merge or by hand with `ci_status.py --record`). Runs needed: 3 (one real failure).

**Open points:** a run's length now varies 9–12 min with runner speed; the air queue test (~6–10 min) is the floor unless its render is made cheaper (changes what it checks – not done). Run-to-run noise: record every green full run. Leftover branch for the owner to delete after merge: `claude/fervent-tesla-q9r5at`.
