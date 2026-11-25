# 0329 – "Uninstall Fresing Render" in the install folder too

**Who:** worker · **Status:** running · **Branch:** `task/0329-uninstall-in-install-folder`
**Started by:** lead, 25 Nov 2026 (owner 09:50, two screenshots: the downloaded installer folder has `Uninstall.bat`;
the installed app's folder `%LOCALAPPDATA%\FresingRender\blender-5.2.3-windows-x64\` with `Fresing Render.exe` has no
uninstall to click – "People are quick to delete the install folder, uninstall should be both places.")
· **Model:** Opus · effort Medium
**Area:** Quality & delivery lane – `installer/Install-FresingRender.ps1`, `installer/Uninstall-FresingRender.ps1`
(only if a start from the new shortcut needs it), `fresing_render/appicon.py` (an older install gets the shortcut once,
where it already makes missing shortcuts and the Installed-apps entry), `fresing_render/update_helper.py` (the shortcut
still right after Update now, also when Blender's folder name changes), `fresing_render/selftest.py` (one line),
`tools/ci_windows_install.ps1`, their tests, `docs/README-install.txt`, the guide's install / uninstall part,
`docs/COMPANY-USE.md` (what the installer writes), `CHANGELOG.md`.
**Not:** the app's menus (0295 runs the Settings / Help-menu side), the Start menu and the Desktop (task 0212: one
shortcut only – stays), anything the uninstaller removes today (no more, no less).

## Goal

A user who has deleted the downloaded installer folder finds **"Uninstall Fresing Render"** right where the app is,
double-clicks it, and the app is removed exactly as `Uninstall.bat` and Settings > Apps > Installed apps do it today.

## Background

- Since 0265 (0.2.214) there are two ways out: `Uninstall.bat` in the downloaded folder and Settings > Apps > Installed
  apps. The install also keeps `Tools\Uninstall-FresingRender.ps1` (the Installed-apps entry runs it), but a `.ps1` does
  not run on a double-click in Windows, and the owner did not find it: he looked in the folder with `Fresing Render.exe`.
- The uninstaller already copies itself to `%TEMP%` before removing the folder it lives in, stops when the app is open,
  keeps projects, renders and backups, and removes the registry entry last.

## What to do

1. **One shortcut, two places:** "Uninstall Fresing Render.lnk" with the app's icon (or Windows' uninstall icon – say
   which and why), tooltip "Removes Fresing Render from this PC. Your projects, renders and backups are kept", that runs
   the same command as the Installed-apps entry's `UninstallString` (with `-Pause`, so its window shows what it removed).
   Put it in **the install folder** (`%LOCALAPPDATA%\FresingRender`, or the `-InstallDir` used) **and in the folder of
   `Fresing Render.exe`** (where the owner looked). Paths quoted (`LOCALAPPDATA` with a space and an accent).
2. **Older installs and updates:** an install made before this task gets both shortcuts at its next start (`appicon.py`);
   after Update now they still point at the right files, also when Blender's folder is renamed in a Blender update.
3. **Started from the shortcut inside the folder it removes:** the folder, both shortcuts and the key are gone after it
   (the shortcut file itself must not block the removal); a second run when the folder is already gone says so plainly.
4. **Install.bat's last lines** say where uninstall is: "To remove Fresing Render later: Settings > Apps > Installed
   apps, or 'Uninstall Fresing Render' in <install folder>."
5. **Self-test line** "Windows: Uninstall shortcut in the install folder" (exists, target exists; Windows only).
6. **Guide + `README-install.txt`:** the three ways to uninstall, one line each. `COMPANY-USE.md`: the two new files.

## Watch

- **Windows-only code:** have it reviewed by an agent that did not write it (CLAUDE.md section 6). Installer files stay
  **plain ASCII**; PowerShell `${Name}` inside strings (section 8).
- **GitHub's Windows job** (`ci_windows_install.ps1`, part A) proves it: after install both shortcuts exist and their
  target + arguments equal the entry's `UninstallString`; then run **the shortcut's own command** unattended (instead of
  the `UninstallString` once, or both if part A's time allows – keep it about the same) and check the folder, the
  shortcuts and the key are gone and the project file in Documents is still there.
- A full run (`installer/` is a shared path) – raise the version at the end as usual.

## Done when

- [ ] Both shortcuts made by the installer, by an older install's next start, and kept right by Update now
- [ ] Double-click from inside the install folder removes everything the uninstaller removes today, projects kept
- [ ] Install.bat's closing lines, self-test line, guide, README-install, COMPANY-USE updated
- [ ] Tests added/updated; full suite passes; Windows job green
- [ ] (Windows-only code) reviewed by a chat or helper that did not write it
- [ ] Report below filled in, merged, released

## Not in this task

App menus (0295), Start menu / Desktop (0212), anything else in the app.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
