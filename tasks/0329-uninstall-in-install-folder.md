# 0329 – "Uninstall Fresing Render" in the install folder too

**Who:** worker · **Status:** done (0.2.246) · **Branch:** `task/0329-uninstall-in-install-folder`
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

**Chat / date:** Claude Code on the web, 25 Nov 2026 · version 0.2.246

**What changed:**
- **"Uninstall Fresing Render.lnk"** in the install folder and in Blender's folder next to `Fresing Render.exe`:
  program `%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe`, arguments = the Installed-apps entry's
  `UninstallString` without its first word (so "powershell.exe " + arguments is exactly the `UninstallString`, with
  `-Pause`), working folder = PowerShell's own (never inside the folder it removes), tooltip as briefed. **Icon: the
  Fresing icon** (`fresing-render.ico`, like the Installed-apps entry) – Windows' own uninstall icons sit at index
  numbers in shell32 / imageres that differ between Windows versions.
- Made by `Install-FresingRender.ps1` (step 5, next to the entry); by the app at start when missing or wrong
  (`appicon.ensure_uninstall_shortcuts`, after the entry step; plain-Python plan in `core/installed_apps.py`:
  `shortcut_spec`, `uninstall_shortcuts`, `shortcut_needs` – rewritten on another program, other arguments or icon).
  Update now replaces only the extension (the arguments point at `Tools\` and the install folder, which stay); the
  app's start right after the update checks both, and a Blender in a new folder (Install.bat) gets its own.
  `update_helper.py` needed no change: it has no COM to write shortcuts, and the restart's check does it.
- Uninstaller (+ the shipped byte copy): the process' working folder set to %TEMP% too, the folder removal tried 4
  times 1 s apart, a run whose folder is gone says "Fresing Render is not installed in … any more (the folder is
  gone). Nothing to remove." (exit 0) and clears that folder's leftover Installed-apps entry and GPU values. From the
  review: after a removal stopped halfway, `installed.txt` is put back with the script, so the second try is not refused.
- Install.bat's last line; self-test line "Windows: Uninstall shortcut in the install folder"; guide (Remove),
  `README-install.txt` (the three ways), `COMPANY-USE.md` (+ its copy in `fresing_render/licenses/`).
- GitHub's Windows job, part A: both shortcuts checked after Install.bat and after the app's refresh of an older install
  (`appicon_test.py` deletes them first); the uninstall step now runs **the install-folder shortcut's own program +
  arguments** (checked equal to the `UninstallString`) instead of the `UninstallString`, then checks folder, both
  shortcuts, key, GPU values gone and the Documents project kept; then a second run of the repository's uninstaller
  must say "the folder is gone". Install.bat's closing line checked in install.log.

**Tested and measured** (4-core web machine, no Windows): `tests/test_uninstall_shortcut.py` (new, 11 tests) and the
install / icon / toolbox / about tests pass locally; the GitHub run of the branch (Windows parts A and B included) –
see below. Independent review (helper agent that did not write the code): nothing serious; fixed its two points (second
uninstall after a partial removal; a gone folder's leftover entry), the rest is low or cosmetic.

**Open points / follow-up tasks:**
- The shortcut (like Uninstall.bat) removes without an "are you sure?" question; next to `Fresing Render.exe` a
  mis-click is possible. A Yes/No question would be a small follow-up if the owner wants it.
- The CI starts the shortcut's command with Start-Process, not a real Explorer double-click (which would need a
  keyboard for `-Pause`): the working-folder line and the retries are proven only by reading.
- `shortcut_needs` compares the arguments case-sensitively (as the entry's `changes()` does): an app started through a
  path of other letter case would rewrite both shortcuts once.
- **Runs:** 3 full runs (the first cancelled by the review fixes, the second green at 0.2.245, the third after
  renumbering to 0.2.246 because task 0314 took 0.2.245 meanwhile), then the docs run on `main` that published
  v0.2.246, passed the old-version update check and offered it to the apps.
- **Not this task, for the lead:** the landing-page job "Publish" (actions/deploy-pages@v4) fails on `main` on and off
  since 25 Nov ~00:10 – 7 of the last 10 runs, also the stand-alone "Landing page" workflow: "No artifacts named
  github-pages" or, on a re-run, "Multiple artifacts named github-pages … count is 2". One re-run of 0.2.246's job failed
  the same way; the landing page still shows an older version. Needs its own small task (`.github/workflows/pages.yml`).
