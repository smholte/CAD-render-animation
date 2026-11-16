# 0171 – Test runs round 4b: Windows job split, lane-only runs while a task is in progress

**Who:** worker · **Status:** open – **after 0169 and 0170** · **Branch:** `task/0171-ci-shorter-runs`
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

- [ ] Windows parts measured, split, all green on a full run; their times in the report (before/after)
- [ ] Lane mode works on a test branch (one push touching only a web-3D file: jobs started, time) and full mode
      still runs everything on a version raise
- [ ] Tests for the mapping and the mode decision
- [ ] A full run alone measured after the change (aim ≈ 15 min; say what it is)
- [ ] CLAUDE.md updated; report with run count and times

## Not in this task

- 0170's mode decision for `main` (keep it as 0170 leaves it).
- No paid runners, no self-hosted runner (public repository; the owner's PC renders).
- Nothing loosened: every test still runs in the full run before a merge.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
