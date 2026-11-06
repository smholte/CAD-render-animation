# 0036 – Automatic tests: from 35–50 minutes to about 15, and no repeated full runs

**Who:** worker · **Model:** Opus · effort Medium · **Place:** Claude Code on the web · **Status:** open – can start
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

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
