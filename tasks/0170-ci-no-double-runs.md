# 0170 – Test runs round 4a: no second full run at a release; test groups rebalanced

**Who:** worker · **Status:** open · **Branch:** `task/0170-ci-no-double-runs`
**Started by:** lead, 16 Nov 2026 · **Model:** Opus · effort Medium
**Area:** `tools/ci_precheck.py` (mode decision), `tests/test_ci_tools.py`, `tools/ci_times.json`, `tools/ci_groups.py`
only if the balancing itself needs a change, CLAUDE.md sections 2 and 5. **Not** `.github/workflows/tests.yml` jobs,
**not** `tools/ci_windows_install.ps1` (0169 edits it; 0171 splits it later).
**Lane:** Quality & delivery (beside 0169: no shared files). A CI fix: merged alone, as soon as it is green.

## Goal

A finished task that lands on `main` gets the ~3 min release run (reuse or docs) whenever its code already ran green –
not a second full run of 23–28 min. And a full run is shorter because no pytest group is far longer than the rest.

## Background (lead, measured on GitHub 16 Nov 2026)

- Of the 10 runs on `main` on 16 Nov (13:26–18:47 UTC), 6 were reuse runs (2–4 min) and **4 were full runs of 23–28
  min**, all on a task's last push: 43894557321 `3c63201` "Task 0155: done (0.2.124) – TASKS.md, report",
  43899493566 `9df1f9d` "Task 0160: done (0.2.125) – TASKS.md", 43913541189 `70c3e97` "Task 0154: done (0.2.127) –
  TASKS.md, report; merge main", 43922154105 `7cea408` "Task 0157: report, clip" (parent `3fa6177` = a merge of
  `origin/main` into the branch, pushed together with the report).
- **Lead's reading (to be confirmed first):** after the branch ran green, `main` moved – often only by task-list
  pushes (`TASKS.md`, `tasks/`, from the lead and other workers; those start no run). The worker merges `main` again
  and pushes merge + report to `main`. `decide()` then: (a) finds no green run with this tree (reuse fails – right);
  (b) takes `base = before` (main's old head) and `green_base()` walks **first parents of `main` only**, back to the last
  green `main` commit **before the task's code** → "code changed since …: everything". The task's own green commit
  (the merge's second parent, or the commit before the report) is never looked at, although the diff from it to the
  pushed commit is documents only. Another possible path: the report is pushed while the reuse run of the code merge
  is still running (`has_green_run` sees no success yet). Check both against the four runs (their precheck logs
  print the reason) before changing anything.
- Run lengths today: full runs 20–28 min (0108 reached ~12 min alone on 13 Nov). Within run 43922154105 the pytest
  groups ran 10.0–17.8 min (suite 6: 17.8, suite 4: 15.2, suite 2: 14.3); in 43928823280 suite 4 took 20.2 min, the
  others 9–14. `tools/ci_times.json` was last recorded before several tasks added tests (0157, 0166, 0146, …).
- Earlier rounds: tasks 0063, 0094, 0108, 0127, 0145 (reports in `tasks/`).

## What to build

1. **Mode decision:** when no tree matches, look for the nearest green commit among **all ancestors reachable within
   the push** (`before..sha`, every parent, not only first parents) and the old base; if the diff from that green
   commit to `sha` is documents/version-line only (`docs_only`), the mode is **docs** (on `main` with a new version
   the release then ships this run's build, as docs mode already does). If several green candidates exist, any one
   with a docs-only diff is enough; with none: full, as now. Keep the reason text clear (which green commit, which
   files).
2. **Report pushed too early:** if a candidate commit's run is still **in progress** and would decide the mode, either
   wait for it (bounded, e.g. ≤ 6 min, the reuse run's length) or fall back as now – worker decides, says why. Never
   treat a running or red run as green.
3. **Safety:** the green commit must have a *proven* run (`run_is_proven`: build + verdict green) when its diff is used
   to skip tests; a reuse run (no build job) counts only through the commit whose full run it reused. A merge that
   brings in another task's code still gives full. Tests in `tests/test_ci_tools.py` with fake API answers for: the
   four cases above (built from their real shapes: merge of main + report; report on top of a fast-forward; main moved
   by TASKS.md only), a merge that brings other code (must be full), a candidate whose run is red / cancelled / in
   progress, a docs-only change of a version line.
4. **Replay:** a small check (script or test with recorded answers) that runs the new `decide()` against the real
   commits of the four runs and prints the mode it would now pick; put the output in the report.
5. **Rebalance:** `python3 tools/ci_status.py --run <a recent green full run> --record` (two or three runs if the tool
   takes the slowest of the last 3) and commit `tools/ci_times.json`; check with `python3 tools/ci_groups.py` that no
   pytest group is planned > ~1.2 × the median. If one test file alone is longer than a group should be, name it in
   the report (splitting it = a follow-up, not this task).
6. **CLAUDE.md:** section 2 ("Merge the way that lets GitHub reuse the run") – one line on what now happens when
   `main` moved by task-list pushes only, and section 5's mode list updated.

## Done when

- [ ] Cause confirmed from the four runs' precheck logs (quoted in one line each in the report)
- [ ] New mode decision + tests (item 3) pass; existing `test_ci_tools.py` still passes
- [ ] Replay of the four real cases: docs (or reuse) where the code had run green, full where it had not
- [ ] `ci_times.json` re-recorded; planned group times listed in the report (before/after)
- [ ] The task's own merge goes through the new path where possible; the report says which mode its `main` run got
- [ ] CLAUDE.md updated; report filled in with run count and times; **watch the next two other tasks' releases** only if
      they land while this session is still open (else the lead checks them)

## Not in this task

- No change to job layout, the Windows job or `ci_windows_install.ps1` (0169 now, 0171 later).
- No lane-only branch runs (0171).
- Nothing loosened: no test skipped or shortened.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
