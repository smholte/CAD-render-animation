# 0246 – Automatic project backups

**Who:** worker · **Status:** done (0.2.187) · **Branch:** `task/0246-automatic-backups`
**Started by:** lead chat, 20 Nov 2026 23:05 (owner's answers 22:40 + 22:44) · **Model:** Opus · effort Medium
**Area:** new **Backups lane** – new files `fresing_render/core/backups.py` (pure logic, no `bpy`),
`fresing_render/blender/backups.py` (timer, save, start question), `fresing_render/blender/ops_backups.py` (Restore
window, Show in folder), their tests; **additive only:** `blender/prefs.py` (four settings next to Lesson highlight),
`blender/ui_topbar.py` (**one** entry "Restore a backup…" in the Fresing menu, after 0241's merge), the module
registration, and a "saving a backup" flag read by the existing `save_pre` / `save_post` handlers (`handlers.py`,
`usage.py`, `project_lock.py`, `flex.py`) – one `if backups.saving(): return` line each, nothing else in them. One tour
stop, one PC-check line, the guide chapter on saving, the function list.

## Goal

A user who does not know Blender never loses more than a few minutes of work: Fresing Render saves a backup copy of
the open project every 5 minutes, keeps a sensible number of them next to the project, offers the newest one when
the saved project is older, and has **Fresing > Restore a backup…** to go back to any of them.

## Background

- Today there is only Blender's own auto-save: one file in the temp folder, found through File > Recover, timer in
  Blender's Preferences. A non-Blender user never finds it (lead chat 20 Nov 22:40). Leave Blender's auto-save and its
  `.blend1` versions as they are.
- **Owner's answers (20 Nov 22:40, 22:44):**
  - a backup **every 5 minutes, adjustable** in Fresing's settings;
  - kept in a **`Backups` folder next to the project**; a project **never saved yet** gets its backups in **one app
    folder** under the user's home – use the app's usual place: `Documents\Fresing Render\Backups\Unsaved projects\`
    (as `demo.py` and `decals.py` use `Documents\Fresing Render\…`);
  - keep the **last 5 + one per day for the past 7 days, both numbers adjustable** in Fresing's settings;
  - **no backups in the Client view.**
- **Lead's additions (small follow-ups if the owner disagrees):**
  - a tick box "Make automatic backups" (on by default) in the settings, for someone who wants none on a huge project;
  - skip while a long job runs (`queue.busy_job(scene)`: cable re-bake, House bake, Web 3D export, clash check – their
    temporary state must never reach a file), while a render or the render queue runs, while the test tour or the demo
    project is being built, during an import, while the animation plays, and while a modal Fresing window is open; try
    again 30 s later; never two backups at once;
  - **no backup when nothing changed** since the last backup or save (`bpy.data.is_dirty` plus the app's own change
    counter if it has one) – an untouched project makes no files;
  - a manual save restarts the 5-minute clock;
  - save with `bpy.ops.wm.save_as_mainfile(filepath=…, copy=True)` (or the lower-level `bpy.data` route if that is
    faster): the open project's path, title, "unsaved" mark and undo stay exactly as they were. The save handlers fire
    for a copy too – they must see the "saving a backup" flag and do nothing (no usage count, no "in use" lock change,
    no "last saved" stamp, no flex `read_steps` warning);
  - file names `<project name> backup YYYY-MM-DD HH-MM.blend`; the cleaning deletes **only** files that match that
    pattern in that `Backups` folder – never anything else, never the project itself;
  - **free space and size:** the demo project is ~226 MB, so 12 backups ≈ 2.7 GB. Skip (one message, once per
    session) when the disk has less than 2 × the project's size free. Show the `Backups` folder's total size in the
    settings and in the Restore window;
  - a `Backups` folder that cannot be written (read-only share, no rights): fall back to the app folder above, one
    message naming where the backups go;
  - **the question at start:** when a project opens and its newest backup is newer than the saved file (Blender or the
    PC stopped before a save), a small window: "A backup from 14:35 is newer than your saved project (14:10). Open the
    backup / Keep the saved project". For unsaved projects: when the app starts and `Unsaved projects` holds a backup
    from the last 24 h that was never opened, the same window ("Work that was never saved, from 14:35"). If the welcome
    or What's new window shows at start, this one waits until it is closed – do not change `welcome.py`;
  - **Fresing > Restore a backup…:** this project's backups (time, size, "newer than your saved project" mark), and
    **Restore** = the current project file is first kept as a backup itself, then the chosen backup replaces the
    project file and opens; **Show in folder** (`files.explorer_select_command`). Greyed in the Client view, like
    0221's entry. Tooltip on every button.
- Shared folders: `project_lock.py` already writes `<project>.blend.inuse` next to the project. Backups next to a
  project on a share are the owner's choice; make sure the lock file is not touched by a backup save.
- Owner's aim (19 Nov): as simple as possible for users who don't know Blender. No new side-panel section: the settings
  live with the other Fresing settings, the only visible things are the Fresing-menu entry, the start question and one
  line in the side panel's message after each backup ("Backup saved 14:35").

## Done when

- [x] `core/backups.py`: names, the keep rule (last N + one per day for D days, the newest of each day kept), "newer
      than the saved project", free-space check – unit tests with fake times and files, incl. a day boundary, N = 0,
      D = 0, and foreign files left alone
- [x] Real-app tests: a backup made after the interval when something changed, none when nothing changed, none in the
      Client view, none while each `busy_job` kind runs (one stand-in is enough per kind), the open project's path,
      dirty mark and undo unchanged after a backup, the save handlers quiet, Restore replaces and keeps the old file,
      the start question for a saved and for an unsaved project
- [x] **Measured:** time of one backup save of the demo project (~226 MB) and of a small tour project on the web
      machine; how long the app stalls. If the demo stalls more than about 2 s, say so in the report with the numbers
      and propose a fix (compression off/on, a background copy) – do not build a background save in this task
- [x] Four settings (tick box, minutes, last N, days D) in Fresing's settings with tooltips; ranges: 1–60 min, N 1–50,
      D 0–60
- [x] Fresing > Restore a backup… (after merging 0241's `ui_topbar.py`), greyed in the Client view
- [x] One test-tour stop in a set that no running task owns (check the "Area" lines of 0230, 0232, 0233, 0234 first and
      name the set in the report), `since=` on the stop and the function-list entry; the guide's saving chapter + one
      picture; one PC-check line `backups.makes_one` (a backup in a temp folder, the keep rule, nothing else deleted)
- [x] (Windows-only code: Documents path, file times, replacing a file Blender has open, long paths on a share)
      reviewed by a helper that did not write it; the Windows job green
- [x] Tests added/updated; full suite passes
- [x] (UI) screenshots checked with tools/ui_screens.py
- [x] Report below filled in, merged, released

## Not in this task

- Blender's own auto-save and File > Recover – leave them.
- `welcome.py`, the splash and the rest of the Start & learn lane (0241 runs, 0222 package B follows).
- A background or incremental save – only a proposal in the report if the measurement asks for one.
- Backups of the render queue's copies, the tour or demo projects being built, House Planner or Toolbox files.
- The private vessel (0226's packages).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (worker), 20–21 Nov 2026 · version 0.2.187

**What changed:**
- New `core/backups.py` (names, keep rule, newer-than-saved, free space, fallback folder per project *place*, the small
  state file of unsaved backups already dealt with), `blender/backups.py` (10 s timer, waits, the copy save, Restore,
  start question), `blender/ops_backups.py` (Restore a backup… window, Restore, Show in folder, the start question).
- Backups are `save_as_mainfile(copy=True, relative_remap=False)`: a backup stands in for the project file at the
  project's own place (Fresing's own `//` paths are not remapped by Blender either), so Restore = copy over the project
  file and open it. Opening a backup straight from the folder may miss relative files (said in the guide).
- "Changed" = a scene update counted by a `depsgraph_update_post` handler since the last backup / save / open
  (`bpy.data.is_dirty` stays True after a copy and is not set by scripts in module mode, so it is not used).
- `prefs.py`: four settings + "Automatic backups" box with the folder's size; `ui_topbar.py`: "Restore a backup…"
  before "My usage…" (greyed in the Client view by the lock); one `if backups.saving(): return` in the save handlers of
  `handlers.py` (covers flex's pause/resume, queue, spool), `usage.py`, `project_lock.py`. `flex.py` itself needed
  nothing: its save hooks are called from `handlers.py`.
- An unsaved project's backup restored opens as `Documents\Fresing Render\Recovered projects\Recovered project <time>.blend`.
- The start question waits for the welcome / What's new (without changing `welcome.py`): until the start file is
  written again (an answer), the user changes something, or 3 minutes.
- **Not done (no API):** "while a modal Fresing window is open" – Blender 5.2.3 has no `Window.modal_operators`; the
  long modal jobs are covered by `busy_job`, picks in the 3D view by `hover.active()`.
- Tour stop `backups` (last stop, set **`faces`** – no running task owns it; `changed="0.2.185"`, tour_versions
  recorded); PC-check line `backups.makes_one`; function `help.backups`; guide "Automatic backups" under Start here +
  picture `docs/img/backups_window.png` (from the real-app test's screenshot).

**Tested and measured** (4-core web machine, Blender 5.2.3):
- `tests/test_backups_core.py` (12) and `tests/test_backups_blender.py` (25): day boundary, N = 0, D = 0, foreign
  files and a folder with a backup's name left alone; the copy leaves path / dirty mark as they were; handlers quiet;
  Client view; each `busy_job` kind (re-bake, House bake, Web 3D export, clash check) and queue / tour / demo / import /
  pick; switched off; fallback folder; too little space said once; Restore keeps the work; start question saved +
  unsaved; colleague's project; path too long; a failed save falls back; restore leaves no temp file.
- Real app `tools/ui_test_backups.py` (group `scenes`): 25/25 – the app's own timer made the backup after an Empty
  was added like a button, path + unsaved mark kept, Ctrl+Z / redo work after it, queue / usage / "in use" handlers
  not called, "in use" file untouched, idle app 0 files, Client view 0, clash check 0 then made once it ended, Restore,
  the start question for a saved project (newer backup) and for unsaved work (Esc = turned down, not asked again).
- `tests/test_tour.py` 101 passed (8 min); PC-check line OK (84 kB backup in 0.01 s, 6 deleted, 6 kept).
- **Measured, one backup save** (3 runs each): the full demo project (made here with `small=False`, 246 MB file):
  **1.26 / 1.32 / 1.27 s**; the project's own Ctrl+S 1.0 s. The tour project "Painted faces" (< 1 MB): 0.01–0.02 s.
  The app stalls for that time once every 5 minutes at most (only after a change) – under the 2 s the brief allowed,
  so no background save is proposed. On the owner's PC (NVMe, 24 cores) expected less; on a network share it depends
  on the share (not measured).
- Independent Windows review (a helper agent that did not write the code), 8 findings; fixed: (1) a colleague's
  backups on a shared project were offered / restorable / cleaned by the second user → none offered, Restore refused,
  this user's backups go to the app folder; (2) fallback folder per name only → `<name> <8 hex of the place>`; (3)
  restore's mtime vs a file server's clock ahead → project set newer than every backup; (4) paths > 259 chars or a
  failed save → the fallback folder; (5) `.fresing-restore` left after a failed copy → removed; (6) the write probe
  every 30 s on a read-only folder → remembered per session. (7) OneDrive uploads backups: one line in the guide.
  Not changed: (8) a case-only rename of a project leaves its old backups (safe: only deletes less).
- GitHub: 4 runs. 44837050586 red: `ui_test_start.py` expects every Fresing-menu entry to work in the Client view
  (the backups entry is greyed there on purpose → that test now checks it greyed with its reason, like Show all of
  Blender), and the new test files' default 30 s times moved two Linux-skipping tests into one pytest group (2 skips,
  1 allowed → their real times in `ci_times.json`). 44844452705 green, but 0.2.185 had gone to task 0239 meanwhile;
  then 0.2.186 went to task 0237: renumbered twice. 44850170629 green (0.2.187), `main` fast-forwarded to it; release
  run 44855004085 (mode reuse): published, the Windows update check and "Offer the release" green.
- Subagents: one – the independent Windows review (read-only, general-purpose); its 6 fixes were made by the worker.
- Progress note `claude/render-app-progress.md` (claude.ai project): not reachable from this session – for the lead.

**Open points / follow-up tasks:**
- No check for an open Fresing dialog (no Blender API); a backup during a props dialog is harmless (the dialog's
  values are not in the file).
- A case-only rename of a project (`mill.blend` → `Mill.blend`) leaves its older backups uncleaned (review point 8).
- On the owner's PC: time one backup of his ~150 MB project (the status line shows "Backup saved"); the PC-check line
  `backups.makes_one` gives the time of a small one.




