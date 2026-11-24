# 0316 – Update now: choose to save or not (also for a project that was never saved)

**Who:** worker · **Status:** done (0.2.220) · **Branch:** `task/0316-update-without-saving`
**Started by:** lead, 23 Nov 2026 22:41 (owner, with a screenshot of the error "This project has never been saved:
save it first (File > Save As…), then press Update now": "what if I don't want to save the project – allow me to
bypass and update and not save")
· **Model:** Opus · effort Medium
**Area:** `fresing_render/blender/updates.py` (preflight, the Update now confirm, `finish_update`, quitting), its tests
(`tests/test_updates.py`, `tests/test_updates_blender.py`), the real-app update test (`tools/ci_update_test.py`) if it
needs a case, `docs/UPDATES.md`, the user guide's updating part, CHANGELOG.
**Not:** the names a first save proposes (0291 – it may run at the same time; this task only *calls* the app's normal
Save as, so 0291's name proposal applies once it lands), where backups go (0246), the other refusals of `preflight`
(import running, render queue, delayed queue, project open elsewhere, other Blenders) – those stay as they are.

## Goal

**Update now** never stops just because the project has unsaved work. The user chooses in the Update now box: save
first, or update without saving. Today a never-saved project is refused with an error, and a saved one is saved
without asking.

## What to do

1. **No more refusal for "never saved".** Drop the `project_dirty() and not bpy.data.filepath` refusal from
   `preflight()`; the choice moves into the confirm box (point 2). The other refusals stay.
2. **The Update now box** (today `invoke_confirm` with one button) shows a choice whenever the project has unsaved
   changes – one window with plain buttons (the app's own popup style; 0282's `form_window` only if it fits a small
   box):
   - **Saved project with changes:** "Save and update" (default, as today) · **"Update without saving"** · Cancel.
     Text: "Without saving, the app opens again with the project as you last saved it – the changes since then are
     lost."
   - **Never saved, with changes:** **"Save as… and update"** (opens the app's normal Save as; once the file is saved,
     the update goes on by itself; a cancelled file browser = nothing happens, Update now stays offered) · **"Update
     without saving"** · Cancel. Text: "Without saving, the app opens again empty – this project is not kept as a
     project file."
   - **No unsaved changes:** as today (one "Update now" button).
   - Tooltips on every button (CLAUDE.md section 6).
3. **Update without saving** – a safety copy, then no questions:
   - If automatic backups are on (0246), write one backup copy first (`backups.make(force=True)` or the like): a saved
     project's copy goes to its normal backups, a never-saved one's to "Unsaved projects". Mark it as dealt with, so the
     next start does **not** ask to restore it (the user chose not to save). The box says one line: "A backup copy is
     kept (Backups)". Backups off: no copy, and the line is not shown.
   - Then quit **without Blender's own "Save changes?" question** (a dirty file makes `wm.quit_blender` ask in a
     window – e.g. switch `preferences.view.use_save_prompt` off for this quit only, never saved into the user's
     preferences; find the clean way and say which).
   - The restart opens the saved project file as it is on disk (saved project), or the app's empty start (never
     saved) – `restart_command` without a file path then.
   - The project lock (`project_lock`) is released as on a normal close.
4. **Save as… and update:** after the save (watch `save_post` once, or poll as `_close_when_saved` does), go on exactly
   like "Save and update" today (helper, close, reopen with the new file). If the save fails or is cancelled: no
   update, a plain status line, Update now stays offered.
5. **Background / scripts** (`bpy.app.background`, tests): an operator property `save: 'SAVE' | 'DONT_SAVE'`
   (default `SAVE`); a never-saved project in the background with `SAVE` reports the same plain sentence as today
   (no file browser there).

## Done when

- [x] `preflight()` no longer refuses a never-saved project; the other refusals unchanged (tests)
- [x] Blender tests: saved + dirty → Save and update saves; Update without saving does not touch the project file
      (mtime + content unchanged), writes one backup when backups are on, none when off, and the next start offers no
      restore for it; never saved + Update without saving → restart command has no file; never saved + Save as and
      update → continues after the save, stops cleanly on cancel; no "Save changes?" on the quit
- [x] Real-app update test (`tools/ci_update_test.py --gui`, the "update" job): one run with an unsaved new project and
      **Update without saving** – the app closes without a question, updates, opens empty
- [x] Screenshot of the box in both forms checked with `tools/ui_screens.py`
- [x] `docs/UPDATES.md` + the user guide's updating part (the choice, what "without saving" means, the backup copy),
      PC-check line if Update now has one, function entry `changed=`; CHANGELOG
- [x] Full suite + GitHub run green; report; merged, version, release

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 23 Nov 2026 – 0.2.220

**What changed:**
- `blender/updates.py`: the "never been saved" refusal left `preflight()` (the other refusals unchanged). Update now
  with unsaved changes opens its own box (`invoke_popup`, the operator's `draw`, 560 px): **Save and update** /
  **Save as… and update** (never saved) · **Update without saving** · **Cancel** (`fresing.update_box_cancel`); texts
  from `box_text()`, the line "A backup copy is kept (Backups)." only with backups on; each button has its own
  tooltip (`description()` by the `save` value). No unsaved changes: the one-button confirm as before. Operator
  property `save` = 'SAVE' / 'DONT_SAVE' (default SAVE; a never-saved project + SAVE in the background is refused
  with the old sentence).
- Save as… and update: `start_save_as` opens Blender's Save As; the timer `_wait_save_as` starts the update once
  `bpy.data.filepath` is set, or – the file browser (found by its `active_operator` = WM_OT_save_as_mainfile,
  checked in the real Blender) closed with no file – leaves a red line "Not saved, so the update did not start…"
  above Update now.
- Update without saving (`update_without_saving`): `backups.keep_unsaved_work` makes one backup (only with backups
  on) and marks every backup the next start would offer for this work as dealt with (a saved project: its backups
  newer than the file – `core.newest_newer` now skips handled names; never saved: this session's unsaved backups);
  then the helper and `quit_app(ask=False)`. **The clean way to skip "Save changes?"** (`no_save_question`):
  `preferences.view.use_save_prompt = False` for this close, and `preferences.is_dirty` set back so Blender's
  close never writes it (pending preference changes of the user are saved first when Auto-Save Preferences is on,
  as that close would have done). The restart command names `bpy.data.filepath` – the file as on disk, or none.
  The project lock is released at exit as on any close (`project_lock`'s atexit).
- Panel texts: Update now's hint says it asks first; the download line says "closes without saving" when chosen.
- Docs: USER-GUIDE "Updates: one click" (the choice, without saving, the backup copy; the old "save first" line
  gone), UPDATES.md step 5 + test table; function entry `help.updates` `changed="0.2.220"`; CHANGELOG.
- No PC-check line: Update now's choice closes the app, which a PC check cannot do; `updates.safe` is unchanged.

**Tested and measured** (4-core web machine, no graphics card):
- `tests/test_updates_blender.py` (25, 8 new): preflight no refusal; Save and update saves; Update without saving
  leaves the project file (mtime + bytes), one backup in Backups, the restart names the saved file, the next start
  offers nothing (and without the mark it would have offered that backup); backups off: no copy; never saved +
  without saving: restart without a file, backup in Unsaved projects, no offer; never saved + SAVE in the background:
  refused; the Save-as timer goes on after a save and stops with the note on cancel; `no_save_question` leaves the
  preferences unchanged. Backups tests (core + Blender) and `test_updates.py` pass.
- Real app (`tools/ci_update_test.py --gui`, real Blender 5.2.3 under Xvfb): two runs now – "save" (34/34) and
  **"dont_save"** – a new project never saved with a change, the box opens, Update without saving: the app closed by
  itself (no question; the test fails after 30 s if it does not), updated and opened empty, "Save changes?" on again,
  one backup in Unsaved projects, no restore offered (35/35). Each update took 25 s from the old app's start. The
  box's two forms checked on the run's screenshots (`update_box*.png`; text 96 characters per line).
- GitHub: see the runs below.

**Open points / follow-up tasks:**
- The Save As file browser itself is not clicked in a real-app test (its timer is unit-tested; the browser's
  detection checked in the real Blender). 0291's name proposal will apply once it lands (this task calls Blender's
  Save As).
- Helper agents: none (no Windows-only code; the change is shared Blender code).

