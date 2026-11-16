# 0169 – The Fresing logo as the app's icon and on the splash screen

**Who:** worker · **Status:** done (0.2.133) · **Branch:** `claude/eager-pasteur-w3w05t` (the web session's branch)
**Started by:** lead, 16 Nov 2026 · **Model:** Opus · effort Medium (Windows-only code)
**Area:** `installer/` (Install / Uninstall scripts), `app_template/fresing_render/` (splash, start-up), a new icon
file, a small Windows-only start-up hook in the extension (window/taskbar icon), its tests, guide line, CHANGELOG
**Lane:** Quality & delivery (`installer/`); the app-template and start-up hook are additive.

## Goal

Everywhere Windows shows Fresing Render – Desktop shortcut, Start menu, the window and the taskbar while it runs – the
owner sees the **Fresing app icon**, not Blender's. The splash screen carries the Fresing logo.

## Background

Owner's question (16 Nov): "does the Fresing Render app icon show as the Fresing app logo?" – lead checked: **no**.
- `installer/Install-FresingRender.ps1` `MakeShortcut` sets `$lnk.IconLocation = "$BlenderExe,0"` → every shortcut
  (Desktop "Fresing Render", Start menu "Fresing Render", "– Self test", "– User guide", "– PC check …") shows
  Blender's icon.
- The running app is `blender.exe` / `blender-launcher.exe`, so the window and taskbar show Blender's icon too.
- `app_template/fresing_render/splash.png` (1000 × 500): dark grey, an **amber** bar, "Fresing Render" in text and a
  subtitle – no logo, and the amber is not Fresing Green.
- The logo files already exist (public, on the site): `site/brand/fresing-app-icon.svg` (512 × 512: dark `#1A2027`
  rounded square, green `#479B29` + white F), `fresing-logo_compact_*.svg`, `fresing-logo_full_*.svg`,
  `site/render_kit/fresing_logo.png`.
- **Logo pack:** the owner may attach his logo pack in the first message. If he does, use its files in preference to
  `site/brand` (e.g. a ready `.ico` or PNG sizes). Commit only the files the app uses (the logo is public already); no
  source/working files (`.ai`, `.psd`, fonts) unless he says so. Without a pack: build from `site/brand/*.svg`.
- Brand colour: Fresing Green `#479B29` (the owner's default in 0168 too).
- There is no "Apps & features" entry today (the install is portable, no admin) – do not add one.

## What to build

1. **Icon file** `installer/fresing-render.ico` (or next to the app template, the worker decides where it installs):
   sizes 16, 20, 24, 32, 40, 48, 64, 256 (256 as PNG inside the .ico), made from the app-icon SVG by a script in
   `tools/` (re-runnable, e.g. `tools/make_app_icon.py`), the small sizes checked to stay readable (the F must not
   blur into the square at 16 px – a simplified 16/20/24 px drawing is fine). The installer copies it into the
   install folder.
2. **Shortcuts:** every shortcut the installer makes uses the Fresing icon (`IconLocation = "<icon>,0"`). The self
   test / PC check shortcuts may keep the same icon (no extra variants needed).
3. **Window and taskbar while running (Windows only):** at start-up the app template (or the extension's start-up
   hook) sets the Fresing icon on Blender's main window (Win32 `WM_SETICON` big + small via `ctypes`, only when
   started as Fresing Render, never in background/test runs) and the process' AppUserModelID (e.g.
   `Fresing.Render`) **matching the shortcuts' `System.AppUserModel.ID`**, so the taskbar groups under the Fresing
   icon and a pinned Fresing Render stays Fresing. Must fail silently (a log line, no error box) if anything is
   missing. Extra windows Blender opens (render window, preferences) get the icon too if cheap; say in the report
   what is covered.
4. **Existing installs:** the owner's PC already has Blender-icon shortcuts. After the in-app update (Update now) the
   shortcuts must show the Fresing icon without running Install.bat again (e.g. the extension refreshes the
   shortcuts' icon once on Windows at start-up if they still point at Blender) – or, if that is not safe, the update
   notes and guide say "run Install.bat once more". Worker decides; say which in the report. Uninstall removes the
   icon file with the rest (it removes the install folder; check nothing is left on the Desktop).
5. **Splash screen:** new `splash.png` (1000 × 500, Blender's splash size) with the Fresing logo (compact or full,
   reversed on the dark ground), "Fresing Render" and the subtitle; the accent bar in Fresing Green instead of
   amber. Also a `splash_2x.png` (2000 × 1000) if Blender 5.2 uses it on HiDPI screens. Made by the same script.
6. Guide: one short line where installation / start-up is described; CHANGELOG entry. PC-check line only if the
   worker sees a cheap honest check (e.g. "shortcut icon is Fresing's") – not required.

## Done when

- [ ] `.ico` with all sizes made by a script in `tools/`; small sizes looked at (crops in the report, described)
- [ ] Install.bat makes every shortcut with the Fresing icon – **checked on GitHub's Windows job** (read the
      shortcut's `IconLocation` back with `WScript.Shell` after the install step; fail if it points at blender.exe)
- [ ] The start-up icon hook is tested on GitHub's Windows job as far as possible (the hook runs without error and,
      if a window exists there, `WM_GETICON` returns the set icon); background/test runs never call it
- [ ] AppUserModelID set in the process and on the shortcuts (same string); read back on Windows in the test
- [ ] An existing install picks the icon up (item 4), tested on the Windows job (install an older layout's shortcut,
      run the refresh, read it back) – or the guide's "run Install.bat again" line if the worker chose that
- [ ] New splash with the logo in Fresing Green; screenshot checked (cropped small)
- [ ] Windows-only code reviewed by a helper agent that did not write it (CLAUDE.md section 6)
- [ ] Tests added/updated; full suite passes on GitHub; version + CHANGELOG; merged per section 7
- [ ] Report filled in, incl. **numbered steps for the owner** to check on his PC after Update now: Desktop icon,
      Start menu, taskbar while running, a pinned taskbar icon, the splash

## Not in this task

- No panel/side-bar icons inside Blender (Fresing tab header etc.) – a later idea if the owner asks.
- No change to the website's brand files (`site/brand/`) except reading them.
- No "Apps & features" registration, no admin install, no code signing.
- Other running tasks: 0135 (web player), 0156/0167 (machining, people), 0166 (demo), 0168 (study branch) – none
  touch `installer/` or `app_template/`.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 16 Nov 2026.

**What changed:**
- **Logo pack used** (the owner's `Logo.zip`, attached in the chat): `fresing-app-icon_512px.png` (icon, 32 px and up)
  and `fresing-logo_full_reversed_2400px.png` (splash; its green line is the accent bar) are copied to `tools/brand/`
  as the maker's inputs. Nothing else from the pack is committed (not the `OLD/` folder, no other sizes).
- `tools/make_app_icon.py` (re-runnable, `--check`): writes `fresing_render/brand/fresing-render.ico` (16, 20, 24, 32,
  40, 48, 64, 256; 256 as PNG, the rest 32-bit bitmaps) and `app_template/fresing_render/splash.png` (1000 × 500).
  16/20/24 px are drawn on whole pixels: stem, green bar and middle bar at least 2 px, a 1 px gap under the bar.
  Blender 5.2.3 reads only `splash.png` (its binary has no `splash_2x` string): no `_2x` file.
- `fresing_render/appicon.py` (new, Windows only at run time): shortcut icon + AppUserModelID `Fresing.Render` through
  COM (IShellLinkW / IPropertyStore), the window icon (WM_SETICON big + small and the window class icons, so later
  windows of Blender's class – render window, preferences – have it too), the ID on the process and on each window with
  the relaunch command/icon/name (a pin made from the running window pins Fresing Render). Start-up hook from the
  extension's `register()`: only on Windows, not in background runs, only when started with the Fresing Render app
  template, not with `FRESING_NO_APPICON`; every fault is one console line.
- **Existing installs (item 4): refreshed by the app**, no "run Install.bat again". At start (in a thread) the app copies
  the icon to `<install folder>\fresing-render.ico` and gives every `.lnk` on the Desktop, in Start menu > Fresing
  Render and among the **pinned taskbar icons** whose target lies inside the install folder the Fresing icon; the ones
  that start the app (`--app-template fresing_render`) get the ID too. A shortcut pointing anywhere else is never
  touched; a right one is not written again.
- Installer: copies the icon into the install folder, every shortcut (incl. the user guide) points there, then a
  background Blender step sets the ID on the app shortcuts with the same code. The PC-check shortcuts the app makes
  itself (`pccheck/ops.py`) use the icon too. Uninstall: the icon lives in the install folder, which is removed; the CI
  now also fails when any "Fresing Render*.lnk" is left on the Desktop.
- Guide (Install, step 3), CHANGELOG.

**Tested and measured:**
- Linux (web machine): `tests/test_appicon.py` (19: ico sizes/format, sharp F at 16/20/24, 256 = the pack's icon,
  splash, files up to date, which shortcut gets what, never outside the install folder, start-up gate, installer and
  PC-check shortcut text), `test_pccheck.py`, `test_updates.py`: pass.
- Icon crops looked at: 16 px reads as a white F with a green bar on the dark rounded square, no grey blur; 32–64 px
  are the pack's icon averaged down (no ringing).
- Splash in the real Blender 5.2.3 app (Linux, xvfb): logo, "Fresing Render", subtitle; the version label stays clear.
- GitHub's Windows job (`tools/ci_windows_install.ps1` 3b + `tools/appicon_test.py`): after Install.bat every shortcut's
  `IconLocation` read back with WScript.Shell = the icon file, app shortcuts' ID read with Shell.Application; then two
  shortcuts are turned back into the pre-0169 kind (Blender icon, no ID, icon file deleted), the app's refresh runs and
  everything is read back again; on a window of its own the icon (WM_GETICON) and the window's ID are read back, and the
  process ID. No Blender window exists there (background), so the hook's timer itself is not run on GitHub.
- Independent review of the Windows code by a helper agent that did not write it (read-only): no crash-class fault in
  the COM/ctypes code (vtable indices, GUIDs, PROPVARIANT, Release/CoInitialize balance checked). Fixed after it: the
  icon file was copied by two writers at the first start after an update (now once, on the main thread, unique temp
  name); only this thread's windows are taken (a console window could block); an empty icon path is never written;
  a pinned plain-Blender icon is left alone (only pins that start the app are changed). Left: the hook's GUI timer is
  not run on GitHub (no Blender window there); an old pin may show as a second button until the next sign-in; Windows'
  own window properties are not cleared at close (harmless at exit).

**GitHub runs:** 5 full runs. 1 real failure (my Windows test also judged the runner's own pinned Edge/Explorer icons,
which the app rightly leaves alone; fixed), 3 version clashes (0166, 0135, 0156 merged first: renumbered 0.2.130 →
0.2.131 → 0.2.132 → 0.2.133). Green branch run 43962917731; main fast-forwarded after merging two task-list commits.

**On the owner's PC (16 Nov 2026, after Update now to 0.2.133, his screenshots):** the start-up screen with the logo,
the Fresing F on the taskbar while the app runs, and the three Desktop shortcuts with the F – all as intended.

**Open points / follow-up tasks:**
- Only the owner's PC can show the taskbar and a pinned icon for real (steps for the owner below).
- Windows keeps an old pinned icon's picture in its icon cache; unpin + pin again fixes it (CHANGELOG and guide say so).

**Steps for the owner (after Update now):**
1. Close Fresing Render if it is open, then start it from the Desktop shortcut **Fresing Render**.
2. Wait until the Fresing panel shows. Look at the **taskbar**: the running app shows the green and white Fresing F.
3. Close the app. Look at the **Desktop**: "Fresing Render", "Fresing Render - PC check" and "(heavy)" show the Fresing
   F (if not at once, press F5 on the Desktop).
4. **Start menu** > Fresing Render folder: all its entries show the Fresing F.
5. Start the app again, right-click its taskbar icon > **Pin to taskbar**, close the app: the pinned icon is the F; click
   it: Fresing Render starts (not plain Blender). If you had pinned it before and it still shows Blender's logo: right-click
   > Unpin from taskbar, start the app, pin again.
6. The start-up screen shows the Fresing logo with a green line under it, "Fresing Render" and the subtitle.
