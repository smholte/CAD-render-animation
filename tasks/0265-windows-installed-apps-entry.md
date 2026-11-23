# 0265 – Fresing Render in Windows' "Installed apps": uninstall it from Settings like any program

**Who:** worker · **Status:** done, 0.2.214 · **Branch:**
`task/0265-installed-apps-entry`
**Started by:** lead, 21 Nov 2026 (owner 15:42, two screenshots of Settings > Apps > Installed apps: searching "fresing"
finds only **Fresing ToolBox** (0.1.0, Fresing, Uninstall), searching "blender" only his own separate Blender 5.2.2 –
"Fresing Render is not available to be deleted from installed apps") · **Model:** Opus · effort Medium
**Area:** Quality & delivery lane – `installer/Install-FresingRender.ps1`, `installer/Uninstall-FresingRender.ps1`,
`installer/Uninstall.bat`, `tools/build_release.py` (only if the uninstaller must ship inside the install),
`fresing_render/update_helper.py` (the version shown after Update now), `fresing_render/appicon.py` (an older install
gets the entry once – it already makes missing shortcuts), `fresing_render/selftest.py` (one line), `tools/ci_windows_install.ps1`,
their tests, `docs/README-install.txt`, the guide's install / uninstall part, `docs/COMPANY-USE.md` (what the installer
writes on the PC).
**Not:** anything else in the app; the owner's own Blender (its entry is his, not ours – leave it).

## Why

The installer (no admin rights, `%LOCALAPPDATA%\FresingRender`, portable Blender) writes no entry in Windows'
list of programs, so the only way out is `Uninstall.bat` in the downloaded installer folder – which a user has usually
deleted. Every normal Windows program, Fresing ToolBox included, can be removed from Settings.

## What to do

1. **The entry (per user, no admin):** the installer writes
   `HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\FresingRender` with `DisplayName` "Fresing Render",
   `DisplayVersion` (the app's version), `Publisher` "Fresing" (as ToolBox), `DisplayIcon` (the app's icon), `InstallLocation`,
   `InstallDate`, `EstimatedSize` (KB, measured from the folder), `URLInfoAbout` / `HelpLink` (the GitHub page / guide),
   `NoModify` = 1, `NoRepair` = 1, `UninstallString` and `QuietUninstallString`. A repair / re-install writes it again;
   an install to another `-InstallDir` points it there.
2. **An uninstaller that lives with the install:** copy `Uninstall-FresingRender.ps1` into the install folder (e.g. the
   Tools folder). It removes the folder it lives in, so the entry starts it from a copy in `%TEMP%` (or another way that
   works – say which). Started from Settings it shows its window: what it removes, **"Your projects, renders and
   backups are kept"**, the result, and closes on a key. Fresing Render still open → it says so and stops (as today).
   It removes the registry entry last, only when the folder is gone. `Uninstall.bat` in the installer folder keeps working.
3. **Update now** (`update_helper.py`) sets `DisplayVersion` (and `EstimatedSize`) to the new version; an install made
   before this task gets the entry once at its next start (where `appicon.py` makes missing shortcuts), so the owner
   does not have to re-install.
4. **Self-test line** "Windows: in Installed apps" – the entry is there, its version is the app's, its uninstaller
   exists (Windows only; skipped elsewhere).
5. **Guide + `README-install.txt`:** "Remove Fresing Render: Settings > Apps > Installed apps > Fresing Render > ⋯ >
   Uninstall – your projects stay." `COMPANY-USE.md`: the one registry key the installer writes (per user).

## Watch

- **Windows-only code:** have it reviewed by an agent that did not write it (CLAUDE.md section 6). Installer files stay
  **plain ASCII** (`test_the_installer_files_are_plain_ascii`) – also the texts the uninstaller shows. PowerShell
  `${Name}` inside strings (section 8).
- **GitHub's Windows job** (`ci_windows_install.ps1`, part A) proves it: after install the key exists with the right
  version, size > 0 and an `UninstallString` that points at a file that exists; after the old build's in-app update the
  version is the new one; then the **`UninstallString` itself** is run (not `Uninstall.bat`) unattended and the folder,
  the shortcuts and the key are gone, a project file put in Documents beforehand is still there. Keep part A's time
  about the same.
- `LOCALAPPDATA` with a space and an accent (the CI already uses one): quote every path in the strings.
- Never remove anything outside the install folder but what the uninstaller removes today (shortcuts, Fresing
  Render's part of the Toolbox folder).
- A full run (`installer/` is a shared path) – raise the version at the end as usual.

## Done when

- [x] After an install, Settings > Apps > Installed apps lists "Fresing Render", version, Fresing, size; Uninstall
      there removes it and keeps projects (proved on GitHub's Windows machine as above)
- [x] Update now shows the new version there; an older install gets the entry at its next start
- [x] Self-test line; guide, README-install and COMPANY-USE updated
- [x] Independent review of the Windows code done (say who and what it found)
- [x] Report filled in (with the owner's check steps: numbered, click by click), merged, released

## Not in this task

Code signing (later, owner 20 Nov); an MSI or admin install; Fresing ToolBox's installer (its own project).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, Sonnet 5.5, 23 Nov 2026

**What changed:**
- `core/installed_apps.py` (new, no Blender): the key `HKCU\...\Uninstall\FresingRender` – name, version, Fresing, icon, folder, date, size, links, NoModify / NoRepair, `UninstallString` (with `-Pause`) and `QuietUninstallString`; `ensure()` copies the uninstaller into `Tools\` and writes only what differs. The app calls it at start (`appicon.refresh_installed`), so an older install gets the entry once.
- `installer/Install-FresingRender.ps1` writes the same key (new last section, guarded); `Uninstall-FresingRender.ps1` runs from a copy in %TEMP% when started from the install folder, shows what it removes and that projects are kept, waits for a key with `-Pause`, refuses a folder without `installed.txt`, removes the key last and only for its own folder, puts itself back when some files could not be removed. A byte copy ships in `fresing_render/installer_files/` (a test compares them). `Uninstall.bat` unchanged.
- `update_helper.py`: after Update now sets version + size and refreshes the uninstaller. Self-test line "Windows: in Installed apps" (`MIN_CHECKS` 15). Guide (anchor `remove`), README-install, COMPANY-USE (the one per-user key), CLAUDE.md.
- CI (`ci_windows_install.ps1`): key checked after Install.bat and after the old build's in-app update (new version); the uninstall step runs the key's own `UninstallString` via cmd, with a project file in Documents that must survive and the key gone. `appicon_test.py` counts shortcuts only and checks the uninstaller is made again.

**Tested and measured:** 13 new pytest tests (values, changes, ensure, Update now, files); related suites green locally. GitHub runs: first run failed only in Windows part A (`appicon_test` counted the new .ps1 as a seventh shortcut) – fixed; the next full runs were green incl. Windows A (~16 min, as before) and B; version clash with 0264 cost one more full run (3 runs in all). Independent review (a separate agent that did not write the code, reading the code only): no blocker; 5 points fixed (uninstaller's working folder, sanity check of `-InstallDir`, uninstaller put back after a failed removal, installer section guarded, no empty icon written). Not run on a real Windows desktop: the Settings window itself (GitHub ran the key's UninstallString).

**Open points:** The Settings page's own look (icon, size column) is for the owner to see. Owner's check: 1. Update to 0.2.214 with **Update now** and start the app once. 2. Open Windows **Settings > Apps > Installed apps**, search "fresing": **Fresing Render 0.2.214, Fresing** is listed. 3. Close Fresing Render, click **⋯ > Uninstall** (twice to confirm): a window lists what goes, says your projects stay, closes on a key. Do this only if you want it removed – re-install with Install.bat afterwards.
