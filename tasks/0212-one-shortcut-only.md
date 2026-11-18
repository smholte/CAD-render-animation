# 0212 – One shortcut only: "Fresing Render" on the Desktop and in the Start menu; the extras in the app and the app folder

**Who:** worker · **Status:** done (0.2.167) · **Branch:** `task/0212-one-shortcut-only`
**Started by:** lead, 18 Nov 2026 (owner's request with screenshots) · **Model:** Opus · effort Medium (Windows-only
code: independent review before merging, CLAUDE.md section 6)
**Area:** Quality & delivery lane – `installer/Install-FresingRender.ps1`, `installer/Uninstall-FresingRender.ps1`,
`fresing_render/appicon.py` (`DESKTOP_NAMES`, `shortcut_paths`), `fresing_render/pccheck/ops.py` (the shortcuts an app
updated with Update now makes), `fresing_render/pccheck/launcher.py` (docstring), `tools/ci_windows_install.ps1`,
`docs/README-install.txt`, `docs/USER-GUIDE.md` (install / PC check / self-test text), `docs/COMPANY-USE.md` (+ its copy
in `fresing_render/licenses/`), the menu item below (additive in the Fresing / Help menu).

## Goal

The owner (18 Nov): today Windows shows five entries in the Start menu (Fresing Render, Self test, PC check quick /
full / heavy – plus safe start and User guide in the folder) and three on the Desktop (Fresing Render, PC check, PC
check heavy). He wants **only "Fresing Render"** in the Start menu and on the Desktop. Everything else lives **inside
the app** and **in the app's own folder**.

## What to do

1. **Desktop:** only `Fresing Render.lnk`.
2. **Start menu:** only `Fresing Render.lnk`, directly in Programs (no "Fresing Render" folder with the extras; check on
   GitHub's Windows how Windows 11 lists it – one entry). Keep the AppUserModelID / icon / "Fresing Render.exe" target
   rules of 0169 / 0177 / 0178 for it, and the pinned-taskbar refresh.
3. **The app folder** (`%LOCALAPPDATA%\FresingRender`, a subfolder such as `Tools`): Self test, PC check (quick),
   PC check (full), PC check (heavy), safe start, User guide – with the **Fr icon** (the owner's screenshot shows the
   extras in the Start menu with an older "F" icon: make every shortcut the same Fr icon). A STEP file dropped on a PC
   check shortcut still works there.
4. **In the app:** a "Tools and checks" place in the Fresing menu (or Help menu – follow 0199's menu): Run the self-test,
   PC check (quick / full / heavy – Help > Fresing Render PC check… already exists, reuse it), **Open the app folder**
   (opens the Tools folder in Explorer). Tooltips, function entry (`since=`), guide anchor, PC-check line if it is
   something the owner can see working.
5. **Older installs clean up by themselves:** the installer (install and repair) and the app at start after **Update
   now** (where `pccheck/ops.py` makes missing shortcuts today) remove the old extra shortcuts **by name and only when
   their target is inside the install folder**, remove the empty old Start-menu folder, and make the Tools folder.
   Never touch a shortcut that points elsewhere. Uninstall removes old and new names.
6. **Tests:** `tools/ci_windows_install.ps1` starts the self-test and the PC check from the Tools-folder shortcuts and
   checks that the Desktop and Start menu hold only `Fresing Render.lnk` after install, after repair and after the old
   build updates itself; Uninstall leaves none. Plain-Python tests for the name / place rules (`appicon.py`).
7. **Words:** every text that says "Start menu > Fresing Render - …" (installer's last lines, README-install, guide,
   COMPANY-USE, PC-check report hints, the self-test's report) says where it is now.
8. **0206's small open point** (same docs): `THIRD-PARTY-NOTICES.md` (+ its copy in `fresing_render/licenses/`) still
   says the licence texts are missing – they ship since 0206; correct the words.

## Done when

- [ ] Fresh install, repair, and an old build updated in the app: Desktop + Start menu show only "Fresing Render";
      the Tools folder holds the six extras with the Fr icon; all checked on GitHub's Windows.
- [ ] The app's menu reaches the self-test, the PC checks and the app folder.
- [ ] Independent review of the Windows code (a helper that did not write it); Windows-only paths with a space and an
      accent still work (the CI's folders).
- [ ] Guide, README-install, COMPANY-USE, tooltips, function entry, version fields; tests; full run green.
- [ ] Report filled in, with the owner's check steps on his PC (numbered, click by click: what he should see in the
      Start menu, on the Desktop and in the folder after **Update now** – he must not need to reinstall).

## Not in this task

The app icon itself (0169); code signing (0207, waiting for the owner's budget); the installer's other steps.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 18 Nov 2026 – version 0.2.167.

**What changed:**
- **Installer:** makes only `Fresing Render.lnk` on the Desktop and directly in Programs (no Start-menu folder). The
  six extras go into `%LOCALAPPDATA%\FresingRender\Tools` with the Fr icon: `Self test`, `PC check (quick)` / `(full)` /
  `(heavy)`, `Safe start`, `User guide`. Shortcuts of an older install are removed by name, and only when their target
  lies inside the install folder. The app's own old Start-menu shortcut is moved, so a Pin to Start stays. The old
  folder is removed when it is empty (Explorer's `desktop.ini` aside). Uninstall removes the old and the new names.
- **The app (`appicon.py`):** `refresh_installed`, which runs at every start on Windows (in a thread), now also tidies an
  older install (`old_shortcuts`, `tidy_plan`, `tidy_old`) and makes missing Tools shortcuts (`tools_specs`,
  `ensure_tools`). Neither step needs the icon file. `pccheck/ops.py` no longer makes PC-check shortcuts with
  PowerShell: removed `ensure_shortcuts`, `shortcut_script`, `missing_shortcuts`, `run_powershell` and their tests.
  The shortcut texts now live in `pccheck/core.py`.
- **Menu:** Fresing > **Tools and checks** has **Run the self-test** (new operator; runs the extension's own
  `selftest.py` in its own console window), **PC check…** and **Open the app folder** (new operator, only in an
  installed app). Both new operators are in `lock.ALLOWED`. Function entry `help.tools` (since 0.2.167), guide anchor
  `tools-and-checks`.
- **PC check:** new Full line `app.tools` (`MIN_LINES_FULL` 104). It checks the menu, and on an installed Windows app
  also that no old shortcut of this install is left and that the Tools folder holds the shortcuts. A Desktop or Start
  menu shortcut the user removed shows as a note, not as FAILED.
- **Words:** user guide (install, Start here, self-test, PC check, guide location), README-install, COMPANY-USE (+
  copy), CONTRIBUTING, bug-report form, installer's last lines, docstrings, workflow step names.
  `THIRD-PARTY-NOTICES.md` (+ copy): the licence texts ship since 0206 (four places corrected).
- **Windows CI (`tools/ci_windows_install.ps1`):**
  - `Make-OldLayout` sets up the shortcuts as an install before 0212 had them, (a) before the old build updates itself
    in the app and (b) before the repair; the repair also gets a foreign shortcut with an old name pointing to
    notepad.exe, which must stay.
  - `Check-OneShortcut` checks the Desktop, the Start menu and the Tools folder after the update, after the install,
    after the repair and after the app's refresh of an older install.
  - The self-test and the PC checks now start from the Tools shortcuts (a missing one is a problem).
  - Uninstall checks the new name.
  - `appicon_test.py` checks that an old Desktop extra is removed and a foreign one left alone.
  - `update_test_blender.py` (after the update) runs what the app runs at start and checks the move.

**Tested and measured:** On the 4-core web machine: `test_apptools.py` (new, 4), `test_appicon.py`, `test_winexe.py`,
`test_start.py`, `test_about_blender.py`, `test_pccheck.py`, `test_functions.py`, `test_user_guide.py`,
`test_updates.py` all pass; precheck and tooltip report clean. The Windows parts ran only on GitHub's Windows (see
runs below). Subagent: one independent reviewer of the Windows code. It found no blocking bug. Fixed from its list:
the installer now moves the old app shortcut, desktop.ini is ignored, the tidy runs without an icon file, and the PC
check notes a removed shortcut. Left as it is: Uninstall removes by name without a target check (as before, and as
the brief says).

**Runs:** 5 full runs. 1: the Windows install failed on one line of the task's own test (`appicon_test.py` listed the
shortcuts without the Tools folder; all one-shortcut checks were green). 2–4: green, but each time another task had
released the version number first (0213, 0215, 0214): merged `main`, took the next version. 5: green (0.2.167).

**Open points:**
- The CI starts the updated app in the background, so it calls `refresh_installed` directly. The start-up thread
  itself (`appicon.startup` → `_shortcuts`) is only exercised on a real PC.
- Windows 11 "Pin to Start" made from the old folder entry: the move should keep it, but not checked.
- No test tour stop (a menu and shortcuts only; nothing to show on a test model).

**Owner's check on your PC (no reinstall):**
1. Start Fresing Render as always. When it says **Update available**, click **Update now** and wait until it opens again.
2. Look at the **Desktop**: only **Fresing Render** (the "PC check" and "PC check (heavy)" icons are gone).
3. Click **Start**, then **All** (all apps): one **Fresing Render** entry, no folder "Fresing Render".
4. In the app: top bar **Fresing** > **Tools and checks** > **Open the app folder**. Explorer opens the **Tools**
   folder with six shortcuts, all with the green Fr icon: Self test, PC check (quick), PC check (full), PC check
   (heavy), Safe start, User guide.
5. Optional: Fresing > Tools and checks > **Run the self-test**. A black window runs for a few minutes;
   "Fresing Render self-test.txt" appears on the Desktop.
6. If a pinned Start entry of Fresing Render disappeared, pin it again: Start > All > Fresing Render > right-click >
   Pin to Start.
