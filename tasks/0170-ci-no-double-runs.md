# 0170 – Test runs round 4a: no second full run at a release; test groups rebalanced

**Who:** worker · **Status:** done · **Branch:** `claude/jolly-dijkstra-0zzdgh`
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

- [x] Cause confirmed from the four runs' precheck logs (quoted in one line each in the report)
- [x] New mode decision + tests (item 3) pass; existing `test_ci_tools.py` still passes
- [x] Replay of the four real cases: docs (or reuse) where the code had run green, full where it had not
- [x] `ci_times.json` re-recorded; planned group times listed in the report (before/after)
- [x] The task's own merge goes through the new path where possible; the report says which mode its `main` run got
- [x] CLAUDE.md updated; report filled in with run count and times; **watch the next two other tasks' releases** only if
      they land while this session is still open (else the lead checks them)

## Not in this task

- No change to job layout, the Windows job or `ci_windows_install.ps1` (0169 now, 0171 later).
- No lane-only branch runs (0171).
- Nothing loosened: no test skipped or shortened.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 16–17 Nov 2026, branch `claude/jolly-dijkstra-0zzdgh`. No subagents (a small,
well-tested change in one file; the replay against the real runs served as the independent check).

**Cause (precheck logs of the four runs, confirmed):** `before` = main's old head, `green_base()` walked main's first
parents only, so the green branch commit under "merge main + report" was never looked at:
- 43894557321 `3c63201` – "code changed since b551640" (main's last green commit before 0155's code; 0155's `ecd603d` ran green)
- 43899493566 `9df1f9d` – "code changed since 3c63201" (0160's `71d79cf` ran green)
- 43913541189 `70c3e97` – "code changed since 0ee069d" (0154's `79e2042` ran green)
- 43922154105 `7cea408` – "code changed since 70c3e97" (0157's `1ba81ca` ran green)
The other path (report pushed while a run was still going) did not occur in the four.

**What changed:**
- `tools/ci_precheck.py` `decide()`: candidates = every commit the push brings (`before..sha`, all parents, newest 40),
  then the old head and its 9 first parents. Each candidate whose diff to the pushed commit is documents/version
  lines only (git, no API) is asked about its runs (at most 12): a finished run with build + verdict green
  (`run_is_proven`) gives **docs**; red / cancelled / reuse-only runs count for nothing. A *docs* run still going is
  waited for (30 s steps, ≤ 6 min); a *full* run still going is not (it would cost more than it saves). The reason text
  names the green commit and the files, or for full the candidates it rejected. `has_green_run`/`green_base` removed
  (only users were here).
- `tests/test_ci_tools.py`: 10 new tests on real little git repositories with a fake API: merge of main + report,
  report on a fast-forward (branch run proves it; reuse-only does not), main moved by TASKS.md only, a merge bringing
  other code (full), candidate red / cancelled / full run going / reuse only (full, no waiting), a docs run still going
  (waits, then docs; never ends → full after 6 min), version line only (docs) vs another line in `__init__.py` (full).
- `tools/ci_replay_mode.py`: replays `decide()` for past runs against the real history and runs (runs started after
  the replayed one hidden, runs still going then shown as going).
- `tools/ci_times.json` re-recorded from runs 43954671134, 43958043514, 43962377331 (slowest of the 3 per file).
- CLAUDE.md sections 2 and 5.

**Replay of the four runs** (`python3 tools/ci_replay_mode.py 43894557321 43899493566 43913541189 43922154105`):
- 43894557321: then full → now **docs** – only documentation since `ecd603d` (proven green): TASKS.md, tasks/0155…, tasks/0166…
- 43899493566: then full → now **docs** – since `71d79cf`: TASKS.md, tasks/0154…
- 43913541189: then full → now **docs** – since `79e2042`: TASKS.md, tasks/0154…
- 43922154105: then full → now **docs** – since `1ba81ca`: tasks/0154…, tasks/img/0157_people_meet.mp4

**Groups (planned by `ci_groups.py`, slowest of last 3 runs per file):**
- before: pytest 1–9 all ~16.0 min; demo 1–4 ~9.1 / 9.6 / 10.0 / 10.1 min
- after: pytest 1–9 all ~13.8 min; demo 1–4 ~13.7 / 14.7 / 14.1 / 14.6 min (no group > 1.2 × median)
- real in run 43962377331: pytest 10.2–15.4 min, demo 10.2–19.4 min, Windows 22.0 min (the run's longest job).
- One file alone is longer than a group should be: **`tests/test_demo_clash.py` 13.7 min** (and `test_demo_clash_b.py`
  11.4 min) – they were ~9 min in task 0108. Splitting them further = a follow-up (Clash/demo lane or 0171).
  Next longest: `test_site_projects.py` 7.5, `test_render_kit.py` 7.3, `test_video_labels.py` 6.9 min.

**Tested and measured:** `tests/test_ci_tools.py` 43 passed locally (web session, 4 cores). GitHub: see runs below.

**Runs:** 3 GitHub runs, all needed. Branch 43969728373 (`ebdf9db`, full, green, 26.6 min); `main` then brought 0169's
code, so the merge ran full again – correctly: 43974041173 (`acdaf05`, green, 27.6 min, precheck "code changed since
every green commit of this push …"). `main` then moved by task-list pushes only (0174, 0176 briefs); this report +
that merge went to `main` directly as the new path's first real case – its mode is in the line below.
Both full runs on busy GitHub (other tasks' runs at the same time): pytest groups 10.5–17.6 min, demo 14.6–19.1.

**Open points / follow-up tasks:**
- `test_demo_clash.py` / `_b.py` have grown to 11–14 min: the demo groups now set the length after Windows.
- Not watched: the next two other tasks' releases (the lead checks them; their precheck line names the green commit).
