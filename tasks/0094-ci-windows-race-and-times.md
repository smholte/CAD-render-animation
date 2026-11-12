# 0094 – Test machinery: Windows install script race, test groups rebalanced

**Who:** worker · **Status:** done (12 Nov) · **Branch:** `task/0094-ci-race-times`
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

- [x] The script change reviewed; one full GitHub run green on the branch with the new grouping; merged to `main`
      (fast-forward to the green commit, CLAUDE.md section 2); report filled in; `TASKS.md` updated.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 12 Nov 2026

**What changed:** `tools/ci_windows_install.ps1` (line 195): the process path is read once into `$procPath` before it is tested and used, so a process ending in between no longer gives the null error. No other place in the script reads `.Path` twice. `tools/ci_times.json`: times of the newest green full run (43145128900, the 0077 tree) recorded.

**Tested and measured:** a helper agent that did not write the change reviewed it (correct; CRLF kept; it suggested a name that cannot clash with the `$p` process handles – done). Windows code could not run here; GitHub's Windows job ran it green. One full run on the branch (43203347012): green, 11.6 min (before: 12.3 min, slowest job test suite 6 at 12.0 min; now the slowest is test suite 4 at 11.1 min and callouts at 10.6). Real-app groups all within 5–10.6 min, so no test was moved. Merged by fast-forward to `main` (no version, no release). One run needed, no clash.

**Open points / follow-up tasks:** none.
