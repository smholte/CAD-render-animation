# 0053 – Safe updates and project lock: no overwrite of a colleague's project, no stuck or broken install

**Who:** worker · **Status:** running · **Branch:** `claude/compassionate-cerf-2ychkv`
**Started by:** lead chat, 9 Nov 2026 (bug hunt 0045 rows 4, 12, 14, 19b, 19c, 19d)
**Lane:** Quality & delivery – `blender/updates.py`, `update_helper.py`, `blender/project_lock.py`,
`pccheck/ops.py` (`ensure_shortcuts` only); their tests; guide "Updates" and "Shared projects"
**Model:** Opus · effort High · **Place:** Claude Code on the web, environment "CAD-render-animation"

Runs at the same time as 0051 (Machining), 0052 (Motion) and 0055 (Looks). Do not touch `reimport.py`, joints,
machining, chips, G-code, decals, `props.py`, `handlers.py`, `queue.py`. Windows-only code: **an independent review
by a helper agent that did not write it** (CLAUDE.md section 2, "Saving usage").

## Goal

"Update now" can never save over a project a colleague has open, can never be blocked for good by an install that
was killed half-way, and a failed install never leaves the owner with plain Blender and no Fresing tab.

## Background (proof and suggested fixes: `tasks/0045-bug-hunt.md`)

- **Row 4 – Update now saves over a shared project.** `preflight` never asks `project_lock`. When
  `project_lock.warning()` is not empty, refuse with "Someone else has this project open: Save As first" (button
  stays, the message says why).
- **Row 12 – a killed helper blocks Update now for good.** `installing.json` stays; Windows reuses PIDs and "access
  denied" counts as alive. Write the helper's start time into it; ignore and delete it when older than
  wait + install time × 4, or when the PID is not `python.exe`.
- **Row 14 – a failed swap leaves no extension and no backup** (Windows, suspected). Copy `ext_dir` to a backup in
  `fresing_update/` before installing, restore it when the version check finds the folder missing; the app then
  opens with the old version and a message.
- **Row 19b – same user, same PC, two windows:** no "in use" warning (`_is_me` ignores the pid). Compare the pid too.
- **Row 19c – the helper waits only for the app's own PID**, not for a queue or PC-check Blender of the same install.
  Wait for every `blender.exe` under the install folder (as Install.bat does).
- **Row 19d – `ensure_shortcuts` decodes PowerShell output as UTF-8** without `errors="replace"`: an accented path
  ends the thread. Add `errors="replace"`.

## Done when

- [ ] Each row fixed with a test (Linux where possible; Windows parts in the Windows CI job or by a mock); the
      helper-agent review of the Windows code named in the report.
- [ ] Update now with a colleague's lock: refused with the message; without a lock: unchanged.
- [ ] A forced failed swap (test) restores the old extension.
- [ ] Guide "Updates" (what happens when an update is refused or fails) and "Shared projects" (two windows).
- [ ] Tests; GitHub green, including the Windows install and "Offer the release"; merged to `main`, next free
      version, released (CLAUDE.md section 7).
- [ ] Report filled in; `TASKS.md`: 0053 done.

## Not in this task

The queue and its runner (0054). Import caches (0055). Anything in the app's panels apart from the update message.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 9 Nov 2026 (version 0.2.41)

**What changed:**
- Row 4: `updates.preflight` reads the project's lock afresh (`lock_holder`); someone else's lock → "Someone else has
  this project open (… ): Save As first …", also after the download (before saving). The button stays; the update
  notice shows a red line with the same advice. No lock: unchanged.
- Row 12: `installing.json` now holds `started` and `exe`; `update_helper.busy_helper` deletes it when the helper has
  ended, it is older than `BUSY_MAX_SECONDS` (2 × wait + 4 installs + pauses + 10 min ≈ 75 min; old files: file
  time), the PID cannot be read, or the PID's program is not the helper's Python (`QueryFullProcessImageNameW`).
- Row 14: the helper copies `ext_dir` to `fresing_update/backup/` before installing; when the folder is gone
  afterwards (also after a crash of the helper) it is put back (rename, else copy over, read-only files cleared,
  3 tries). Status: "… could not be installed (…), so the old version X was put back". Backup removed afterwards.
- Row 19b: `project_lock._is_me` compares the PID: a live Blender of the same user/PC is "you, in another Fresing
  Render window on this PC"; a dead or reused PID is taken over.
- Row 19c: `update_helper.other_blenders` (K32EnumProcesses + image path under the Blender folder, as Install.bat);
  Update now refuses while one runs, and the helper waits for them too (5 min, then status + restart, nothing
  changed). The busy note is written before that wait, so a Desktop start meanwhile says "being installed".
- Row 19d: `pccheck.ops.run_powershell` with `encoding="utf-8", errors="replace"`.
- PC check: new line `updates.safe` (Full; MIN_LINES_FULL 39) runs the Windows process code, the stale-note check
  and backup/put-back with an accented temp path on the owner's PC and in the Windows CI job.
- `tools/ci_update_test.py` waits (≤ 2 min) until no other Blender of that folder runs before its Update now.
- Guide: "Updates: one click" (when Update now refuses, when an update fails) and "Projects on a shared drive"
  (two windows).

**Tested and measured** (Linux web session, 4 cores, test crane; no Windows here):
- New tests: `test_updates.py` (stale notes ×5 kinds, other Blenders found/waited for/given up on, failed swap puts
  0.2.14 back with its wheels, helper crash after the folder was removed, put-back over read-only leftovers),
  `test_updates_blender.py` (colleague's lock refused before and after download, second window, own lock fine, panel
  line, stale note shows Update now), `test_phase2.py` (two-window lock), `test_pccheck.py` (non-UTF-8 PowerShell
  output). Local: these files all pass; PC-check line `updates.safe` OK (bpy module).
- Real app, in-app update (`ci_real_app.py --only update`): 29/29, 24 s; backup of the (small) test extension 0.0 s.
  The backup time of the real extension with its wheels on Windows is not measured (expected seconds).
- Windows code (process listing, image names, backup/put-back with rename): **independent review by a helper agent**
  that did not write it — no blocker; its "should fix" points were done (put-back over leftovers, unreadable PID =
  not ours, exact helper path, longer busy limit, alive check, kernel32 cached, CI wait).
- GitHub runs: see below.

**Open points / follow-up tasks:**
- Matching the Blender folder by path misses other Blenders when Windows reports another spelling (8.3 short names,
  subst drives): then the old behaviour (no wait). The PC check line shows whether it matches on the owner's PC.
- Blender re-installs an extension's wheels at start; after a put-back the old wheels are expected to come back that
  way (not tested on Windows).
