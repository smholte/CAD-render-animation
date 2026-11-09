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

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
