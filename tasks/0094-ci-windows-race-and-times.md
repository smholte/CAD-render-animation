# 0094 – Test machinery: Windows install script race, test groups rebalanced

**Who:** worker · **Status:** open – can start · **Branch:** `task/0094-ci-race-times`
**Started by:** lead chat, 12 Nov 2026 (0085's and 0077's open points)
**Lane:** Quality & delivery – `tools/ci_windows_install.ps1`, `tools/ci_times.json`, `tools/ci_*.py` only; no app code,
no version, no release
**Model:** Sonnet · effort Medium · **Place:** Claude Code on the web, environment "CAD-render-animation"

## What to do

1. `tools/ci_windows_install.ps1` around line 195: a process can end between two reads of its `.Path` ("You cannot
   call a method on a null-valued expression", seen once in 0085's run 4). Read `$_.Path` once into a variable, then
   test and use that; look for the same pattern elsewhere in the script. Windows-only code: have a helper agent that did
   not write it review the change (CLAUDE.md section 6); CRLF line endings.
2. Since 0077 two jobs are flagged SLOW (test suite 6 with `test_demo_project.py` 12.0 min, paths-heavy with `heavy.demo`
   10.5 min). Record the newest green full run's times (`python3 tools/ci_status.py --run <id> --record`), commit
   `tools/ci_times.json`; if one real-app group is now much longer than the rest, move a test to the lightest group
   (`GROUPS`, `MIN_CHECKS` unchanged). Say the full-run time before/after.

## Done when

- [ ] The script change reviewed; one full GitHub run green on the branch with the new grouping; merged to `main`
      (fast-forward to the green commit, CLAUDE.md section 2); report filled in; `TASKS.md` updated.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured:**

**Open points / follow-up tasks:**
