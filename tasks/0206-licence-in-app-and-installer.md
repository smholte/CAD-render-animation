# 0206 – The licence inside the app and the installer: About Fresing Render, licence files in every install

**Who:** worker · **Status:** waiting – **after 0205** (its `LICENSE` and `THIRD-PARTY-NOTICES.md`) **and 0181**
(shares the Help / Fresing menu and `core/functions.py`) · **Branch:** `task/0206-licence-in-app`
**Started by:** lead chat, 18 Nov 2026 (owner: a company wants to use the app; follow-up of 0205)
· **Lane:** Start & learn (`ui_topbar.py`, the Help menu) + Quality & delivery (`installer/`, `tools/build_release.py`)
**Area:** new `fresing_render/blender/about.py` (+ its operator and test); additive: `ui_topbar.py` / the Help menu
(one item), `tools/build_release.py` (files into both zips), `installer/Install-FresingRender.ps1` (licence line, files
copied), `core/functions.py` (one entry), the guide, the PC check
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

## What to build

1. **About Fresing Render** (Fresing menu and Help menu, one operator): logo, name, version, "© 2026 Fresing",
   "GPL-3.0-or-later – free software, no warranty" (one plain line), the Blender version it runs on, buttons
   **Licence** (opens the installed `LICENSE`), **Third-party licences** (opens the installed notices), **Using it in
   a company** (the installed `COMPANY-USE` page, else its GitHub address). Works offline. Tooltips on every button.
2. **Files in every install:** `LICENSE`, `THIRD-PARTY-NOTICES.md` (and the licence files of the wheels and web
   scripts the notices name) inside the extension zip, so an update brings them too; the Windows zip carries them at
   its top; the installer copies them next to the app and keeps Blender's own licence folder (check it is there after
   an install).
3. **Installer:** prints one line at the start – "Fresing Render <version> – GPL-3.0-or-later, no warranty. Licence:
   <folder>\LICENSE" – no "I agree" step (the GPL needs none).
4. The rules for a visible change (CLAUDE.md section 6): function-list entry + guide anchor with `since=`, a PC-check
   line ("Licence files present"), tooltips, the guide (a short "About and licences" part), a test-tour stop only if
   the section 6 rules ask for one.

## Done when

- [ ] About opens from both menus in the real app (real-app test), all buttons work offline, the texts fit at 100–200 %
      display scaling (Windows job).
- [ ] Both release zips contain the files (test on `build_release.py`); an update from an older version brings them
      (the update test checks one file); the Windows install has them and Blender's licence folder.
- [ ] PC-check line green on Linux and Windows.
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
