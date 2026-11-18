# 0212 – One shortcut only: "Fresing Render" on the Desktop and in the Start menu; the extras in the app and the app folder

**Who:** worker · **Status:** running · **Branch:** `task/0212-one-shortcut-only`
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

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
