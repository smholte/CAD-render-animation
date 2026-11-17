# 0171 – Test runs round 4b: Windows job split, lane-only runs while a task is in progress

**Who:** worker · **Status:** done (17 Nov 2026) · **Branch:** `task/0171-ci-shorter-runs`
**Started by:** lead, 16 Nov 2026 · **Model:** Opus · effort Medium
**Area:** `.github/workflows/tests.yml`, `tools/ci_windows_install.ps1`, `tools/ci_precheck.py` (a new mode),
`tools/ci_groups.py`, `tools/ci_real_app.py` (`GROUPS` only), their tests, CLAUDE.md sections 2 and 5
**Lane:** Quality & delivery. Waits for 0169 (it edits `ci_windows_install.ps1`) and 0170 (it edits `ci_precheck.py`).

## Goal

A full run takes about 15 min instead of 20–28, and a task's runs while it is being built start fewer jobs, so
several tasks at once queue less on GitHub's 20 jobs.

## Background (lead, measured on GitHub 16 Nov 2026)

- Full run 43922154105 (main, 28 min): the **Windows job** started after the build (+3.5 min waiting for a slot) and
  ran **20.8 min**; in 43928823280 15.1 min. It is the longest job of most runs. Its parts (`ci_windows_install.ps1`):
  the old build's in-app update, the current zip's install + repair, files and shortcuts, self-test, the PC check's
  Windows Full lines, Heavy scaled down, Uninstall.
- One run starts about 28 jobs (precheck, build, 9 pytest groups, 10 real-app groups, demo make + 4 demo groups,
  Windows, verdict); GitHub's free plan runs 20 at a time for the account. With 3–4 tasks pushing, runs queue: 0166's
  runs took 27–36 min on 16 Nov.
- Tasks push 1–4 full runs before they finish (0166: 6 runs on 16 Nov, 3 cancelled by a newer push).
- 0170 fixes the second full run at a release and rebalances the pytest groups; read its report first.

## What to build

1. **Windows job in two (or three) parallel jobs** after the build, each installing what it needs: e.g. A = old
   build's in-app update + install/repair + shortcuts + self-test + Uninstall; B = install + PC check Full lines +
   Heavy scaled down. The worker measures the parts first (the job's step times) and splits where the halves come
   out even. Everything checked today stays checked; the verdict needs all parts; the release's
   "an installed old version updates itself" job is unchanged.
2. **Lane mode while a task is in progress:** a branch push whose version is **not** raised yet (CLAUDE.md: the version
   is taken last, so an unraised version = still being built) runs only the jobs its changed files need: the pytest
   files and real-app groups that cover those files (a mapping in `tools/ci_groups.py`, from the lanes' file lists in
   `TASKS.md` / module imports; when in doubt the group runs), plus build + one Windows part if `installer/`,
   packaging or Windows-only code changed. Any change to shared files (`props.py`, `ui.py`, `reimport.py`,
   `animation.py`, `handlers.py`, `tour.py`, `pccheck/`, the build/packaging, `tools/ci_*`) → full. **A raised
   version, `main`, and a push with `[full run]` in the commit message → full, as now.** The precheck prints which
   groups it picked and why; the verdict says "lane run – not a release check".
3. Tests for the mapping (a change in `blender/web3d.py` picks the web groups and not milling; a `props.py` change
   gives full; a raised version gives full).
4. CLAUDE.md: section 2 (workers: lane runs while building, the full run comes with the version) and section 5 (job
   table + modes).

## Done when

- [x] Windows parts measured, split, all green on a full run; their times in the report (before/after)
- [x] Lane mode works on a test branch (one push touching only a web-3D file: jobs started, time) and full mode
      still runs everything on a version raise
- [x] Tests for the mapping and the mode decision
- [x] A full run alone measured (aim not reached, see report) after the change (aim ≈ 15 min; say what it is)
- [x] CLAUDE.md updated; report with run count and times

## Not in this task

- 0170's mode decision for `main` (keep it as 0170 leaves it).
- No paid runners, no self-hosted runner (public repository; the owner's PC renders).
- Nothing loosened: every test still runs in the full run before a merge.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 17 Nov 2026, branch `ccr-4a8a3359-hvmit4`. No subagents (CI files only; the
real runs on GitHub were the check).

**What changed:**
- **Windows in two parts** (`tools/ci_windows_install.ps1 -Part all|a|b`, matrix in `tests.yml`, `WINDOWS_PARTS` in
  `tools/ci_groups.py`). A: kit window checks, old version updates itself, Install.bat twice, files, icons,
  Fresing Render.exe, self-test, PC check Full, Uninstall. B: Install.bat once, files, PC check Heavy (scaled down).
  Everything checked before is still checked; the verdict needs both; the release's update job is unchanged.
- **Mode lane** (`ci_precheck.decide_plan`, `ci_groups.lane_plan`): a branch push whose version equals main's at the
  merge-base runs only the tests that name its changed files (file name as a word in a test file or real-app script;
  `ops_x`/`ui_x` also pick `x`), regrouped into ~10-min jobs; build + Windows part A only for Windows code; PC check and
  tour never. Full instead: shared files (brief's list + `build.py`, `importer/`, `functions.py`, tour UI, `__init__`
  files, packaging), a file no test names, a raised version, main, a pull request, `[full run]` / `[release
  rehearsal]` in the commit message. A lane run's verdict job is named "… (lane run - not a release check)" and
  `run_is_proven` refuses it, so it can never be the basis of a docs or reuse run.
  Import closure was tried first and dropped: the blender modules import each other in cycles, a change in any
  module reached ~145 of them.
- `ci_status.py`: lane text; `--record` refuses a run that is not full; `--wait` looks 90 s for a run before saying
  "task list only, no run" (0170's open point).
- 10 new tests in `tests/test_ci_tools.py` (web3d picks the web tests, not milling; machining picks real app
  machines; shared files → full; unnamed file → full; Windows code → build + part A; docs, test files, demo files;
  valid groups; a lane run proves nothing; lane / full on version raise / `[full run]` / main / pull request on a git
  repository; the workflow's parts). 62 passed locally. CLAUDE.md sections 2 and 5.

**Tested and measured** (GitHub's runners):
- Windows before (one job): 15.1 (43928823280), 18.3 (43969728373), 22.0 (43962377331), 23.2 min (43974041173);
  inside it Heavy 9.1–11.0, Full 6.3–8.1, self-test 1.9–2.5, everything else ~1.5 min.
- After: A 13.1 / 10.0 min, B 8.6 / 9.5 min (runs 44040414640, 44043751767).
- Full run after the change: 24.3 min (44043751767, green, other tasks' runs at the same time), 22.1 min
  (44040414640). **The aim of ~15 min is not reached:** the longest path is now the demo (make 4.1 + a demo group up to
  19.6 min; `test_demo_clash.py` alone 11–19 min) and some pytest groups (up to 18.9 min on a busy GitHub). Windows is
  no longer the longest job.
- Lane run: push of a web3d-only change (56aeead): run 44047300181, **mode lane, 7.8 min, 3 jobs run** (precheck,
  2 pytest groups of 6–7 min; 26 test files), no build, no real app, no Windows – a full run starts ~30 jobs.
- Full on version raise: the decision on the real history (a web3d change, then the version raised to 0.2.140, local,
  not pushed): lane → "full – version raised (0.2.139 → 0.2.140)".
- Merge: main fast-forwarded to ac9ab99, run 44047282213 mode reuse, green, 1.2 min.

**Runs:** 4. 44040414640 full, red: `test_tour.py::test_go_sets_the_stop_up_and_its_check_passes[spool]` ("Cable
'Power cable' no longer touches 'GUIDE SHEAVE' at frame 233") – not this task's code; passed locally (3 min) and on
0174's runs: a test that fails at random. 44043751767 full after merging main, green. 44047300181 lane try. 44047282213
reuse on main.

**Open points / follow-up tasks:**
- **Spool stop of the tour fails at random** (above): Cables lane, a follow-up like 0127.
- **~15 min needs the demo shorter:** split the demo clash check into more parts (HALVES 2 → 3 or 4) and/or a fifth
  demo group, or a faster demo make. Clash/demo lane or the next CI task.
- Branch `ccr-4a8a3359-hvmit4` holds the lane-try commit 56aeead (a comment in `web3d.py`, never merged): the owner
  may delete the branch on github.com.
- Tasks that do not raise the version must put `[full run]` in their last code commit before merging (CLAUDE.md).
