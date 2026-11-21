# 0265 – Fresing Render in Windows' "Installed apps": uninstall it from Settings like any program

**Who:** worker · **Status:** open – can start once a code slot is free (Quality & delivery lane is free) · **Branch:**
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

- [ ] After an install, Settings > Apps > Installed apps lists "Fresing Render", version, Fresing, size; Uninstall
      there removes it and keeps projects (proved on GitHub's Windows machine as above)
- [ ] Update now shows the new version there; an older install gets the entry at its next start
- [ ] Self-test line; guide, README-install and COMPANY-USE updated
- [ ] Independent review of the Windows code done (say who and what it found)
- [ ] Report filled in (with the owner's check steps: numbered, click by click), merged, released

## Not in this task

Code signing (later, owner 20 Nov); an MSI or admin install; Fresing ToolBox's installer (its own project).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
