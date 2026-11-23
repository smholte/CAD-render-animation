# 0316 – Update now: choose to save or not (also for a project that was never saved)

**Who:** worker · **Status:** running · **Branch:** `task/0316-update-without-saving`
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

- [ ] `preflight()` no longer refuses a never-saved project; the other refusals unchanged (tests)
- [ ] Blender tests: saved + dirty → Save and update saves; Update without saving does not touch the project file
      (mtime + content unchanged), writes one backup when backups are on, none when off, and the next start offers no
      restore for it; never saved + Update without saving → restart command has no file; never saved + Save as and
      update → continues after the save, stops cleanly on cancel; no "Save changes?" on the quit
- [ ] Real-app update test (`tools/ci_update_test.py --gui`, the "update" job): one run with an unsaved new project and
      **Update without saving** – the app closes without a question, updates, opens empty
- [ ] Screenshot of the box in both forms checked with `tools/ui_screens.py`
- [ ] `docs/UPDATES.md` + the user guide's updating part (the choice, what "without saving" means, the backup copy),
      PC-check line if Update now has one, function entry `changed=`; CHANGELOG
- [ ] Full suite + GitHub run green; report; merged, version, release

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
