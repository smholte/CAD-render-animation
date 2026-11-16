# 0169 – The Fresing logo as the app's icon and on the splash screen

**Who:** worker · **Status:** open · **Branch:** `task/0169-app-icon`
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

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
