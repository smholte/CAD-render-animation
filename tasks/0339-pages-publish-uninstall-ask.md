# 0339 – Landing page publishes again; uninstall shortcut asks first

**Who:** worker · **Status:** open – can start · **Branch:** `task/0339-pages-publish-uninstall-ask`
**Started by:** lead, 25 Nov 2026 (0329's report: the landing-page "Publish" job fails on and off since 25 Nov ~00:10;
owner 12:1x: "Yes, ask first" before the shortcut / Uninstall.bat removes the app) · **Model:** Opus · effort Medium
**Area:** Quality & delivery lane – `.github/workflows/pages.yml` and the landing-page / publish part of
`.github/workflows/tests.yml` (nothing else in it), `installer/Uninstall-FresingRender.ps1`, `installer/Uninstall.bat`,
`installer/Install-FresingRender.ps1` (only the shortcut's / entry's arguments if a switch is needed),
`fresing_render/installer_files/` copy, `fresing_render/core/installed_apps.py` (only if the shortcut's arguments change),
`tools/ci_windows_install.ps1`, their tests, guide's uninstall part, `docs/README-install.txt`, CHANGELOG.
**Not:** the site's content (`site/`), any app code beyond the line above.

## Goal

Every release shows on the landing page again, and a mis-click on "Uninstall Fresing Render" next to `Fresing Render.exe`
no longer removes the app without a question.

## What to do

1. **Pages publish** (0329's open point): `actions/deploy-pages@v4` fails in ~7 of 10 runs on `main` – "No artifacts
   named github-pages", on a re-run "Multiple artifacts named github-pages … count is 2"; the stand-alone "Landing page"
   workflow too. Find the cause from the runs' logs (two workflows / jobs uploading `github-pages` in one run? a
   concurrency group that cancels the upload but not the deploy? `upload-pages-artifact` version vs `deploy-pages`?) and
   fix it so one run uploads exactly one artifact and deploys it. Prove it: the landing page shows the newest version
   after your merge, and two runs close together both end green (or the second waits).
2. **Ask first** (owner): started from the **"Uninstall Fresing Render" shortcut or `Uninstall.bat`**, the uninstaller
   asks once "Remove Fresing Render from this PC? Your projects, renders and backups are kept. (Y/N)" – N or closing
   the window changes nothing. **Not** from Settings > Installed apps (Windows asks there already) and never in the
   quiet / unattended command (`QuietUninstallString`, CI): give the uninstaller a switch for that and say which.
3. CI part A: the unattended run still removes everything; one extra check that a "No" answer leaves the install whole
   (keep part A's time about the same).

## Watch

- `tests.yml` is shared by every task's run: change only the publish part, and check a normal task run still goes the same
  way (lane-only runs, docs runs, release runs).
- Installer files stay **plain ASCII**; Windows-only code reviewed by an agent that did not write it (CLAUDE.md section 6).
- CI status needs the push attach (`gh api repos/...`); note the run numbers in the report.

## Done when

- [ ] Landing page shows the newest release; the next releases publish green (name the runs)
- [ ] Shortcut and Uninstall.bat ask Y/N; Settings > Installed apps and the quiet command do not
- [ ] Tests added/updated; full suite passes; Windows job green
- [ ] Report below filled in, merged, released

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
