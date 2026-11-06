# 0036 – Automatic tests: from 35–50 minutes to about 15, and no repeated full runs

**Who:** worker · **Model:** Opus · effort Medium · **Place:** Claude Code on the web · **Status:** running
**Branch:** `task/0036-ci-speed`
**Started by:** lead chat, 6 Nov 2026 · **Lane:** Quality & delivery (`.github/`, `tools/ci_*`, `tools/release_tools.py`;
no app code) · **Runs before 0031** (both touch `.github/` and CLAUDE.md section 4/5).

## Goal

A task's AI work takes 20–40 minutes, but each task then waits **1–2 hours** for GitHub: a full run takes
24–50 minutes (CLAUDE.md said 12), and one task is run several times (branch, a re-merge of `main`
because another task took its version number, then `main` again before the release). The owner's rule:
**GitHub minutes are free (public repository) – use them properly.** Make the runs fast by running in
parallel and by not repeating work that is already proven. Nothing that is tested today may stop being tested.

## Background (measured 6 Nov 2026, runs 42247094070 / 42248687039 on `main`)

| Job | Minutes |
| --- | --- |
| Linux - test suite + packaged self-test | 22–29 |
| Linux - real app (simulated clicks, one test after the other, incl. the PC check) | 38 |
| Windows - install + self-test (needs only the 0.5 min `build` job, already parallel) | 11–12 |
| Release jobs | < 1 each |

Runs per task seen today: branch run (24–50 min) → merge of `main` (version/changelog clash, see 5) → run again
→ merge to `main` → run again → release. Read `.github/workflows/tests.yml`, `tools/ci_real_app.py`
(has `--only`), `tools/ci_status.py`, `tools/release_tools.py`, `docs/UPDATES.md` and CLAUDE.md section 5 first.

## What to build

1. **Real-app job as a matrix of parallel jobs.** Split `ci_real_app.py`'s tests over several runners by
   measured time (ui1 ~5–7 min, surroundings ~4–6, the PC check ~6, the others small): for example
   {ui1}, {surroundings + faces + rule sets}, {studio + milling + cylinder + linkage + callouts + waycover + video},
   {PC check Full}, {paths + update}. Balance from the real timings, not by guess; each job installs the
   extension itself (as the script already does) and uses the Blender cache. A new real-app test must be easy
   to add to a group (one list, with `MIN_CHECKS`), and a test that is in no group must fail the run
   (so none is silently dropped).
2. **pytest in parallel.** Try (a) `pytest-xdist` on the 4 cores and (b) a matrix of test-file groups
   balanced by recorded durations (`--durations` file kept in the repo or cache), whichever is faster *and*
   stable. Tests that need their own process (`fresh_process`) and any test that is not safe in parallel stay
   serial in their own group. Same rule: every test file in a group, or the run fails.
3. **Fail fast, first.** A new first job `precheck` (~1 min, no Blender) with `tools/ci_precheck.py`:
   the version in `__init__.py` and `blender_manifest.toml` agree; on a push to a branch/PR the version is
   **greater than the newest release/`main` version** and CHANGELOG has its heading (otherwise "someone
   took your version number: merge `main` and renumber" – the message names the new number) ; `MIN_CHECKS` /
   `MIN_LINES_FULL` are not lower than the lists; every test file/real-app test is in a group; the task list
   parses. When it fails it cancels the rest of the run, so the 35-minute wait never happens for a clash.
4. **Do not repeat a proven tree.** When a push to `main` has the **same git tree** as a commit that already has
   a fully green run (typical: the worker merged `main` into the branch, waited for green, then
   fast-forwarded `main` to that commit), skip the tests and go straight to the release jobs. Find the green
   run through the GitHub API by tree hash (`git rev-parse <sha>^{tree}`); the release job must still check
   "all required jobs of that run green". If no such run exists, run everything as today. Write the rule
   for workers (below, CLAUDE.md) that makes this the normal path.
5. **Cheap path for documentation-only merges.** A push whose changes are only `docs/`, `CHANGELOG.md`,
   `TASKS.md`, `tasks/` (and version numbers in the two version files) runs only `precheck`, the tooltip
   check, the guide build and the packaging of the zip (`build`) – a few minutes – not the whole suite.
   The release job treats it as green. (Task-list-only pushes already start no run.)
6. **Windows in parallel, bounded.** The Windows install job already starts after `build`; keep it parallel,
   check its time (the PC check inside it is 4.5 min) and cache what can be cached (pip, the Blender zip
   already is).
7. **Caches:** pip/venv by hash of `tools/requirements-dev.txt`; the Blender download; the generated test
   models if they are made at run time. Measure the saved minutes.
8. **Visibility:** each job writes its minutes to the run summary; `ci_status.py` prints a total and flags a
   job that takes > 1.5 × its recorded time. CLAUDE.md section 5 gets the new job table and times.
9. **Rehearsal:** the release machinery (4) changes, so prove it with a `[release rehearsal]` push
   (CLAUDE.md section 7) and, once, with a real fast-forward to `main` that reuses a green run – say in
   the report how it was verified.
10. **Rules for all chats** (the lead already wrote the first version into CLAUDE.md section 2, "Working
    efficiently with the automatic tests"): update it with what is now true (fast-forward path, the precheck
    message, cheap docs path, new times).

## Done when

- [ ] Median full run (3 runs on branches, different days/times if possible) ≤ 15 min, all existing checks
      still run; the report lists every job before/after.
- [ ] `precheck` fails a clashing version in about 1 minute (shown by a test push), and passes a normal push.
- [ ] A fast-forward of `main` to a commit with a green run reaches "Offer the release to the apps" in ≤ 3 min
      without re-running the tests; a `main` push without a green run for its tree runs everything.
- [ ] A docs/changelog-only push takes ≤ 5 min; a code push runs everything.
- [ ] Every real-app test and pytest file is in exactly one group (checked); `MIN_CHECKS` kept.
- [ ] CLAUDE.md sections 2 and 5 updated; `docs/UPDATES.md` if the release path changed; report filled in.
- [ ] Windows-only parts (any PowerShell/job changes) reviewed by a helper that did not write them.

## Not in this task

- Changing what the tests check, or app code. The Claude Code set-up (task 0031) comes after this one.
- Other running tasks (0026, 0033, 0035) keep working: their branches pick up the new workflow when they merge `main`
  (say so in the report; do not merge anything that breaks a running branch's old workflow expectations –
  `ci_status.py` must keep working for both).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (worker), 6 Nov 2026

**What changed:**
- `.github/workflows/tests.yml`: first job **precheck**; pytest as a matrix of 4 groups; real app as a matrix of
  6 groups; build; Windows (after build, as before); a **Tests - verdict** job that the release jobs need.
  Every job writes its minutes to the run summary. Three modes, picked by the precheck: *full* (everything),
  *docs* (only docs/CHANGELOG/CLAUDE/README/TASKS/tasks and version lines changed since a green commit: build +
  tooltip check + guide + their tests), *reuse* (push to `main` whose git tree already ran green: no tests; the
  release takes that run's installer files with `download-artifact run-id`, after `release_tools.py verify-run`).
- `tools/ci_precheck.py` (new): version files agree; branch version newer than `main` and every release, with
  its CHANGELOG heading ("someone took your version number: … renumber to 0.2.NN"); `MIN_CHECKS` names every
  real-app test; `MIN_LINES_FULL` / `MIN_LINES_HEAVY` not below the PC check's lines; every real-app test in
  exactly one group and every pytest file in exactly one group; `TASKS.md` tables parse; the mode.
- `tools/ci_groups.py` + `tools/ci_times.json` (new): pytest files balanced over 4 groups by recorded seconds
  (a new file joins by itself; the packaged self-test is one item of the balance).
- `tools/ci_real_app.py`: `TESTS` and `GROUPS` at module level (one list next to `MIN_CHECKS`), `--group`.
  0033's `pccheckheavy` merged in (group paths-heavy).
- `tools/ci_status.py`: prints the mode, the run's total, flags a job > 1.5 × its recorded time, `--record`
  copies a green run's times into `ci_times.json`. Works for old runs too (checked on run 42248687039).
- `tools/ci_pytest_summary.py`: seconds per test file (`PYTEST_FILE_SECS`), `--title`.
- `tools/release_tools.py`: `verify-run` (green, required jobs green, same git tree).
- Caches: a venv cache for the 4 pytest jobs (by the hash of `tools/requirements-dev.txt`), pip cache for the
  real-app jobs; Blender (Linux and Windows) was cached already. Test models are in the repository (none made at
  run time). Windows job: nothing more to cache (it installs no Python packages); it stays parallel after build.
- CLAUDE.md sections 2, 3, 5; docs/UPDATES.md (the reuse path); 21 new tests in `tests/test_ci_tools.py`.

**Tested and measured** (GitHub's free runners, 4 cores):

| Job | Before (runs 42247094070 / 42248687039) | After (runs 42261621440 / 42263700501 / 42266138945 / 42268319993) |
| --- | --- | --- |
| Precheck | – | 0.1 / 0.1 / 0.1 min |
| Linux - test suite (+ packaged self-test) | 22–29 min, one job | 4 groups: 4.6–6.1 / 4.7–7.5 / 5.9–7.6 min |
| Linux - real app | 38 min, one job | pccheck 12.4 / 11.0 / 12.2; callouts 5.7 / 13.8 (with paths) / 9.9; ui 9.7 / 6.5 / 8.4; scenes 11.3 / 8.2 / 5.0; motion 7.5 / 9.6 / 10.0; paths-heavy – / – / 7.2 min |
| Build | 0.7 min | 0.6 / 0.5 / 0.7 min |
| Windows - install + self-test | 11–12 min | 9.8 / 12.0 / 12.0 min |
| **Whole run, push to verdict** | **35–50 min** | **12.7 / 14.2 / 13.0 / 12.8 min (median 12.9)** |

- Precheck clash: run 42268182878 (version set back to 0.2.28 while main had 0.2.29): failed in the precheck
  after 0.1 min, 0.3 min in all, nothing else started, message "someone took your version number: 0.2.28 is not
  newer than 0.2.29 … renumber to 0.2.30". Normal pushes: precheck green in 0.1 min (all runs above).
- DOCSRUN
- REHEARSAL
- REUSE
- pytest-xdist was not tried on GitHub: the slowest single test (`test_video_labels.py`, 265 s, a queued
  video) alone is longer than any group's other files, the render-queue tests already use all 4 cores, and
  the file groups already put the suite (4.6–7.6 min) below the PC check job (11–12 min). xdist could not
  shorten the run.
- Windows-side changes (clock/minutes steps in pwsh, the release-check's artifacts from another run, the
  release conditions) reviewed by a helper agent that did not write them: no defects, three small points
  (guard a missing clock value, `!cancelled()` instead of `always()` for the release, label of a time line),
  all three applied.
- Runs this task needed: RUNS.

**Open points / follow-up tasks:**
- The PC check (Full) job is now the run's length (11–12 min): splitting it would change what it tests
  (one run from the installed launcher). The callouts test varies 5–10 min with its queued video.
- Running branches (0026) pick up the new workflow when they merge `main`; a new real-app test of theirs must
  go into `GROUPS` (the precheck says so). `ci_status.py` reads old and new runs.
- Leftover branch for the owner to delete on github.com: `task/0036-ci-speed`.
