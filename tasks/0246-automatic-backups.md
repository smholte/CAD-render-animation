# 0246 – Automatic project backups

**Who:** worker · **Status:** open – waits for 0241 (`ui_topbar.py`) · **Branch:** `task/0246-automatic-backups`
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

- [ ] `core/backups.py`: names, the keep rule (last N + one per day for D days, the newest of each day kept), "newer
      than the saved project", free-space check – unit tests with fake times and files, incl. a day boundary, N = 0,
      D = 0, and foreign files left alone
- [ ] Real-app tests: a backup made after the interval when something changed, none when nothing changed, none in the
      Client view, none while each `busy_job` kind runs (one stand-in is enough per kind), the open project's path,
      dirty mark and undo unchanged after a backup, the save handlers quiet, Restore replaces and keeps the old file,
      the start question for a saved and for an unsaved project
- [ ] **Measured:** time of one backup save of the demo project (~226 MB) and of a small tour project on the web
      machine; how long the app stalls. If the demo stalls more than about 2 s, say so in the report with the numbers
      and propose a fix (compression off/on, a background copy) – do not build a background save in this task
- [ ] Four settings (tick box, minutes, last N, days D) in Fresing's settings with tooltips; ranges: 1–60 min, N 1–50,
      D 0–60
- [ ] Fresing > Restore a backup… (after merging 0241's `ui_topbar.py`), greyed in the Client view
- [ ] One test-tour stop in a set that no running task owns (check the "Area" lines of 0230, 0232, 0233, 0234 first and
      name the set in the report), `since=` on the stop and the function-list entry; the guide's saving chapter + one
      picture; one PC-check line `backups.makes_one` (a backup in a temp folder, the keep rule, nothing else deleted)
- [ ] (Windows-only code: Documents path, file times, replacing a file Blender has open, long paths on a share)
      reviewed by a helper that did not write it; the Windows job green
- [ ] Tests added/updated; full suite passes
- [ ] (UI) screenshots checked with tools/ui_screens.py
- [ ] Report below filled in, merged, released

## Not in this task

- Blender's own auto-save and File > Recover – leave them.
- `welcome.py`, the splash and the rest of the Start & learn lane (0241 runs, 0222 package B follows).
- A background or incremental save – only a proposal in the report if the measurement asks for one.
- Backups of the render queue's copies, the tour or demo projects being built, House Planner or Toolbox files.
- The private vessel (0226's packages).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
