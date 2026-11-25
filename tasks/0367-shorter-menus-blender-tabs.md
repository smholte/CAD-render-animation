# 0367 – Shorter top-bar menus and Blender's side-panel tabs hidden (0222 package C) + 0332's open points

**Who:** worker · **Status:** running · **Branch:** `task/0367-shorter-menus-blender-tabs`
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

- [ ] Each menu as above outside Full access, and Blender's full menu with Full access / Show all of Blender – tests
      both ways, also in the Client view.
- [ ] The five tabs hidden outside Full access and back with it; a test add-on panel in the sidebar still shows; the
      Fresing panel stays in front after selecting a part.
- [ ] Keys tab button greyed in the Client view, with its tooltip.
- [ ] Screenshots checked with `tools/ui_screens.py` (each menu, the sidebar with a part selected); guide pictures
      updated.
- [ ] Tests added / updated; full suite passes; GitHub run green (incl. the Windows install); CHANGELOG.
- [ ] Report filled in (what was already done before this task, what this task did), merged, released.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
