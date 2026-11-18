# 0206 – The licence inside the app and the installer: About Fresing Render, licence files in every install

**Who:** worker · **Status:** open – can start (0205 and 0181 done, 18 Nov) · **Branch:** `task/0206-licence-in-app`
**Started by:** lead chat, 18 Nov 2026 (owner: a company wants to use the app; follow-up of 0205)
· **Lane:** Start & learn (`ui_topbar.py`, the Help menu) + Quality & delivery (`installer/`, `tools/build_release.py`)
**Area:** new `fresing_render/blender/about.py` (+ its operator and test); additive: `ui_topbar.py` / the Help menu
(one item), `tools/build_release.py` (files into both zips), `installer/Install-FresingRender.ps1` (licence line, files
copied, Blender's extension sync off), the app's start (the one-time sync switch for older installs, item 4),
`core/functions.py` (one entry), the guide, the PC check, `docs/COMPANY-USE.md` (only its network lines, item 4)
**Model:** Sonnet · effort Medium · **Place:** Claude Code on the web, environment "CAD-render-animation"

## Goal

Anyone using an installed Fresing Render – or the IT person who installs it – can see the version, who makes it, the
licence and the third-party licences without the internet, and every install carries the licence texts the GPL and
the third-party licences ask for.

## Background

- 0205 adds `LICENSE` (GPL-3.0-or-later), `THIRD-PARTY-NOTICES.md` and `docs/COMPANY-USE.md`; its report says what
  today's install misses (read its "Needs the owner" table and the line on Blender's own licence files first).
- The Fresing top-bar menu (0199, `ui_topbar.py`) and the Help menu exist; 0181 (usage tracker) adds to them – merge
  `main` after 0181 before starting.
- Releases: `tools/build_release.py` builds `fresing_render-<version>.zip` (the extension the app downloads) and
  `FresingRender-<version>-windows.zip` (the installer); `docs/UPDATES.md` describes the path.
- `blender_manifest.toml` already carries `license` and `copyright`.
- 0208 (learn as you go) runs beside this task and also adds one item to the Fresing menu (`ui_topbar.py`) and entries
  to `core/functions.py` – additive both; whoever merges second updates its branch to `main` first.
- **0205's report, points 6 and 7 (lead added 18 Nov after 0205 finished):** (6) the installer sets
  `use_online_access = True` (`installer/Install-FresingRender.ps1`, the `set_prefs.py` block) for the app's own update
  check, and so Blender's own extension repository syncs at every start (`use_sync_on_startup = True`, checked in 5.2.3
  on Linux): Blender may contact `extensions.blender.org` at each start. (7) Licence texts missing on the PC: Fresing
  Render's own GPL, the libraries inside the OpenCascade wheel (FreeImage, LibRaw, OpenEXR, FreeType … – the wheel
  carries none of their texts), meshoptimizer's MIT text; whether Blender's own `license/` folder reaches a Windows
  install was not looked at.

## What to build

1. **About Fresing Render** (Fresing menu and Help menu, one operator): logo, name, version, "© 2026 Fresing",
   "GPL-3.0-or-later – free software, no warranty" (one plain line), the Blender version it runs on, buttons
   **Licence** (opens the installed `LICENSE`), **Third-party licences** (opens the installed notices), **Using it in
   a company** (the installed `COMPANY-USE` page, else its GitHub address). Works offline. Tooltips on every button.
2. **Files in every install:** `LICENSE`, `THIRD-PARTY-NOTICES.md` (and the licence files of the wheels and web
   scripts the notices name) inside the extension zip, so an update brings them too; the Windows zip carries them at
   its top; the installer copies them next to the app and keeps Blender's own licence folder (check it is there after
   an install). Include the texts 0205 found missing (point 7 above): the GPL itself, the licence texts of the
   libraries inside the OpenCascade wheel (from their sources – list each in the report with where it came from),
   meshoptimizer's MIT text. A text that cannot be found here: say so in the report, do not invent it.
3. **Installer:** prints one line at the start – "Fresing Render <version> – GPL-3.0-or-later, no warranty. Licence:
   <folder>\LICENSE" – no "I agree" step (the GPL needs none).
4. **Blender's extension sync off (owner 18 Nov):** Blender's own extension repositories no longer sync at start, so
   the app contacts nothing at start except its own update check. The installer sets `use_sync_on_startup = False` on
   every remote extension repository (keep `use_online_access = True` – the app's update check needs it). Installs
   made before this version get the same once, at the first start after the update (remember that it was done, so a
   user who turns the sync back on keeps it on). Change the lines that say Blender syncs at start – in
   `docs/COMPANY-USE.md` and point 6 of the "Needs the owner" table in `THIRD-PARTY-NOTICES.md` (now: done in 0206) –
   that one fact only; the rest of 0205's texts stay as they are.
   Test: after a Windows install (Windows job) and after the one-time step, no remote repository has sync on start.
5. The rules for a visible change (CLAUDE.md section 6): function-list entry + guide anchor with `since=`, a PC-check
   line ("Licence files present"), tooltips, the guide (a short "About and licences" part), a test-tour stop only if
   the section 6 rules ask for one.

## Done when

- [ ] About opens from both menus in the real app (real-app test), all buttons work offline, the texts fit at 100–200 %
      display scaling (Windows job).
- [ ] Both release zips contain the files (test on `build_release.py`); an update from an older version brings them
      (the update test checks one file); the Windows install has them and Blender's licence folder.
- [ ] PC-check line green on Linux and Windows.
- [ ] Blender's extension sync on start is off after a fresh Windows install and after an update from an older
      version; the app's own update check still works (its existing test green).
- [ ] Version raised, CHANGELOG, full GitHub run green, merged, main contains the commit; report filled in.

## Not in this task

Code signing (study 0207 first). SPDX headers. Any change to the licence or notices texts (0205's files – only read
them; a wrong line goes in the report).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured:**

**Open points / follow-up tasks:**
