# 0367 – Shorter top-bar menus and Blender's side-panel tabs hidden (0222 package C) + 0332's open points

**Who:** worker · **Status:** done (0.2.270) · **Branch:** `task/0367-shorter-menus-blender-tabs`
**Started by:** lead, 25 Nov 2026 23:5x (owner allowed extra code tasks for the night; 0222 package C, order A → B → C
agreed 20 Nov – A = 0241 and B = 0253 are done) · **Model:** Opus · effort Medium
**Area:** Start & learn lane –
- `blender/lock.py`: it already draws a shorter File menu for the Client view – use the same pattern.
- `blender/ui_topbar.py`: the Help menu, Fresing's lines.
- `blender/panels.py`: Blender's own sidebar panel classes registered again with a `poll`, as `panels.install` already
  does for the app's own panels.
- `blender/keys.py`: only the Keys tab's "Blender's own keymap" button.
- `app_template/` if a menu needs it.
- `core/functions.py`, additive. Their tests, the guide, the PC-check line, the tour stop / lesson text that names a
  menu, CHANGELOG.

**Not:**
- `handlers.py` (0326 runs there) – no load handler is needed, menus and panels are drawn by class.
- `pccheck/checks.py`: 0348 adds to it – add your PC-check line as a new function of your own, never change existing
  lines. Whoever merges second updates its branch.
- `tour.py`: 0348 adds to it – only text of a stop that names a menu.
- The right-click menu and keys (0253, done); 0297's Blender / Fresing Render switch button (a study page waiting for the
  owner's pick); package D (timeline header, Fresing View menu – later); the Settings window's other tabs.

## Goal

A new user who opens a top-bar menu sees only what the app uses, and Blender's Tool / View / Animation / Item tabs no
longer push the Fresing panel away. **Workspace > Full access** and **Fresing > Show all of Blender** bring everything
back exactly as today.

## Background

- Study 0222 (`tasks/0222-study-blender-parts-new-users.md`, on `main`): the table rows "1 File / Edit / Render / Window /
  Help menu" and "10 Side panel tabs", the package list ("C – Shorter top-bar menus …") and the **owner's answers (20 Nov
  16:22)**. Pictures: `tasks/img/0222/menus_topbar.png`, `window_numbered.png`.
- Since the study: 0241 (quiet window, File > New / Ctrl+N = New project, Fresing > Show all of Blender), 0253 (keys,
  F12 / Ctrl+F12 = the app's render, short right-click menu), 0276 (first-start set-up), 0331 / 0332 / 0333 (windows,
  Client lock, workspaces). **Check what is already done on today's `main` and do only the rest.** List both in the
  report.
- 0332's open points (`tasks/0332-*.md`, report):
  1. Blender's **Item** tab (panel "Transform") still shows beside Fresing when a part is selected outside Full access →
     hidden with the other tabs here.
  2. The Keys tab's "Blender's own keymap" button opens Blender's Preferences (Keymap), also in the Client view →
     greyed in the Client view, with a tooltip that says why.
  3. While a render runs the image editor shows Blender's progress text – **keep it** (it is the progress).

## What to do (outside Full access; Full access and "Show all of Blender" show Blender's own menus and tabs)

1. **File:** keep Open, Open Recent, Revert, Recover, Save, Save As, Save Copy, Quit. New = New project (check). Import =
   the app's Import STEP… / Import mesh…. Hide Link, Append, Data Previews, External Data, Clean Up, Defaults, Export.
   The Client view keeps its own shorter menu as today.
2. **Edit:** keep Undo, Redo, Undo History, Menu Search, Preferences; hide the rest.
3. **Render:** the app's Render image, Render animation, Render queue, View last render (F11) instead of Blender's.
4. **Window:** keep Toggle Window Fullscreen, Save Screenshot, Show Status Bar; hide the rest. Check that Ctrl+Page Up /
   Down cannot switch to a workspace with no way back (0253 may have done it).
5. **Help:** Fresing's lines as today; Blender's lines (Manual, Support, …, Report a Bug, Save System Info) in one
   sub-menu "Blender" at the bottom.
6. **Side panel:** Blender's tabs Tool, View, Animation, Item and glTF Variants hidden. Another add-on's tab must still
   show. Blender 5.2.3 is pinned – test against its real classes, not a list typed by hand.
7. 0332's points 1 and 2 above.
8. Every changed entry has its tooltip; the guide's menu pictures and text, the function list and the PC-check line
   follow (CLAUDE.md section 6).

## Done when

- [x] Each menu as above outside Full access, and Blender's full menu with Full access / Show all of Blender – tests
      both ways, also in the Client view.
- [x] The five tabs hidden outside Full access and back with it; a test add-on panel in the sidebar still shows; the
      Fresing panel stays in front after selecting a part.
- [x] Keys tab button greyed in the Client view, with its tooltip.
- [x] Screenshots checked with `tools/ui_screens.py` (each menu, the sidebar with a part selected); guide pictures
      updated.
- [x] Tests added / updated; full suite passes; GitHub run green (incl. the Windows install); CHANGELOG.
- [x] Report filled in (what was already done before this task, what this task did), merged, released.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 25–26 Nov 2026 (worker).

**Already done before this task (left as it was):** File > New / Ctrl+N = New project only (0241); Edit = Undo, Redo,
Undo History, Menu Search, Fresing Settings (0332 – Fresing Settings in place of Blender's Preferences, kept); Ctrl+Page
Up / Down swallowed outside Full access (0253); Blender's side-panel tabs Tool / View / Animation and the Python panels of
Item hidden in the main window (0332); the render's progress text kept (0332 point 3).

**What changed:**
- **File** (quiet window): New project, Open, Open Recent, Revert, Recover, Save, Save As (the app's, task 0291), Save
  Copy, Import STEP…, Import mesh model…, Import House Planner scene… (the last two hung in Blender's File > Import list,
  which is gone – they would have been unreachable), Quit. project_name.py's File swap asks `quiet.file_menu` first. The
  Client view keeps lock.py's own File menu.
- **Render**: the app's Render Image (`fresing.render`), Render Animation (`fresing.key_render`, as Ctrl+F12), Render
  Queue… (Make's queue window), View Last Render (F11).
- **Window**: Toggle Window Fullscreen, Show Status Bar, Save Screenshot.
- **Help**: Blender's own lines not drawn; one line "Blender" at the very bottom (appended again at every switch so it
  stays last) opens `TOPBAR_MT_fresing_help_blender` = Blender's own Help draw (Manual … Report a Bug, Save System Info).
- **Side panel**: "glTF Variants" joins the hidden tabs (late-registered panels are caught at each switch). The **Item**
  tab's "Transform" panel is C code (no Python class; registering one of that name replaces it for good – measured): while
  quiet its C `poll` pointer is swapped for that of Blender's own "Vertex Weights" panel (false in Object Mode) and
  written back in Full access and at unregister (`panels.hide_c_panels`). The panel type is reached from a Fresing panel
  being drawn and every field read is checked first (idname, label, category, flag, poll, draw; Blender 5.2 only);
  otherwise nothing is written and the tab stays. A first try with Blender's INSTANCED flag was dropped: an existing
  Transform panel was then still drawn when Item was chosen.
- **Keys tab**: "Blender's own key settings" greyed in the Client view, tooltip says why.
- Guide (menus list + picture `docs/img/quiet_menus.png`, Item tab, Keys button, File > Import texts), function entry
  `help.quiet_menus`, PC-check line `app.menus` (new function), two tour-stop `where` texts (File > Import …), CHANGELOG.

**Tested and measured** (4-core web machine, Blender 5.2.3 Linux, test app only):
- `tests/test_quiet_menus_0367.py` 13 tests (menus' lines, Help swap keeps Fresing's lines, the "Blender" line stays
  last, glTF tab hidden / another add-on's tab kept, the poll write and put-back on a stand-in struct, nothing written
  when not found or not matching, Keys button).
- New real-app test `tools/ui_test_menus.py` (group callouts, 34 checks, ~0.4 min): each quiet menu drawn, Help's
  sub-menu, the Transform panel found and hidden, Item / Tool / View / Animation cannot be chosen with a part selected,
  another add-on's tab shows and draws, Fresing stays in front, Full access brings Item / View and Blender's File back,
  Back hides them, the Client view's File menu and greyed key button. Screenshots of every menu and the side panel
  looked at.
- PC-check lines app.menus, app.quiet, app.keys OK (bpy module).

**Version / runs:** released as 0.2.270. GitHub runs: 10 on the branch – 1 precheck (version taken), 2 real failures
of old tests this task changes (ui_test_layout used the Item tab as "another tab"; the Client-view operator test
expected Blender's key button to work there) – fixed; 1 failure of `test_update_reuse[decals]` that did not repeat
(passes alone, in its file and with its group's neighbours, 4 runs locally; nothing of this task touches decals or
model updates – flaky, watch it); 1 verdict failure because the new test file moved an xfail and a skip into one group
(`tools/ci_pytest_summary.py` now does not count an xfail as a skip); 5 green runs lost to other tasks releasing the
same version first (0.2.262 … 0.2.269, a busy night). Local: `ui_test_names` failed once under load (pytest alongside)
and passed twice alone.

**Subagents:** none (the work was one lane, small files).

**Open points / follow-up tasks:**
- The Transform panel's hiding is a pointer swap inside Blender (no other way for a C panel). It is checked on Blender
  5.2.3 Linux; on Windows the same struct layout is expected (plain C++ struct) and the checks refuse anything else –
  the owner sees it on his PC: select a part, the side panel shows only the Fresing tab.
- In Full access Blender's Item tab still shows in the app's own windows (output / Settings windows) as before (0308).
