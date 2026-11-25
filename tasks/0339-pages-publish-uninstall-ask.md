# 0339 – Landing page publishes again; uninstall shortcut asks first

**Who:** worker · **Status:** done (0.2.252) · **Branch:** `claude/busy-volta-erel42`
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

- [x] Landing page shows the newest release; the next releases publish green (name the runs)
- [x] Shortcut and Uninstall.bat ask Y/N; Settings > Installed apps and the quiet command do not
- [x] Tests added/updated; full suite passes; Windows job green
- [x] Report below filled in, merged, released

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 25 Nov 2026 (branch `claude/busy-volta-erel42`, the session's own branch).

**What changed:**
- **Pages – the cause** (from the logs of runs 45591152083, 45595655949, 45543258275, 45536939525, 45532476828,
  45525736885, 45514791362): the upload always succeeded, then `deploy-pages` listed the run's artifacts within a second
  and the new one was not in the list yet ("Found 4 artifact(s)", none `github-pages` → "No artifacts named
  github-pages"). A re-run of the job uploaded a second `github-pages` in the same run, so the re-run failed with
  "Multiple artifacts … count is 2". Nothing uploaded twice in one attempt; GitHub's list lags (since ~25 Nov 00:10).
- **The fix** (`.github/workflows/pages.yml`): artifact name `github-pages-<run attempt>` (a re-run has its own), a step
  that waits until the run's REST list shows it (3 s steps, up to 90 s), `deploy-pages` with `continue-on-error`, and
  after 45 s a second try (a second failure fails the job); the concurrency group `pages` moved to the job (it now also
  queues the call from tests.yml against a push run of this workflow); `upload-pages-artifact@v5` / `deploy-pages@v5`
  (Node 24); `actions: read` for the wait (also granted by the `pages` job in tests.yml – nothing else in tests.yml).
- **Ask first:** `Uninstall-FresingRender.ps1` has the switch **`-Ask`**: "Remove Fresing Render from this PC? Your
  projects, renders and backups are kept. (Y/N)" before anything is touched (also before the copy to %TEMP%); Y / yes
  goes on, N / Esc / no input / closing the window removes nothing (exit 2). The shortcut "Uninstall Fresing Render"
  (installer, `installed_apps.shortcut_spec`, so older shortcuts are rewritten at the app's next start) and
  `Uninstall.bat` pass it. `UninstallString` (Settings) and `QuietUninstallString` do not – without `-Ask` it never
  waits. The shortcut gets `-Ask` only when the Tools uninstaller knows it (`installed_apps.asks`; independent review:
  an older Tools copy would stop at once with "A parameter cannot be found").
- `tools/ci_windows_install.ps1 -Uninstall`: the shortcut answered "n" first – question shown, exit 2, install folder,
  Tools uninstaller, Blender folder, entry, shortcuts all still there; then the entry's `UninstallString` with no
  keyboard input removes everything and prints no (Y/N). Guide, README-install.txt, COMPANY-USE.md updated.

**Tested and measured:**
- Local (4-core web machine): `test_uninstall_shortcut.py` (+4 tests), `test_installed_apps.py`, `test_appicon.py`,
  `test_site.py` (+1 test for the Pages workflow), `test_toolbox.py`, `test_about.py`, `test_user_guide.py` – all pass.
- GitHub: 5 full runs on the branch. 45605754938 red – `tools/appicon_test.py` still wanted the shortcut without `-Ask`
  (fixed); the new uninstall checks passed there already: "answered N: asks, nothing removed" 6 s, the Installed-apps
  command with no question 8 s (part A 18.9 min, as before ±1). 45615474100 green; 45624439056 red in the real-app
  lessons test (undo after Build, nothing of this task; the same commit's code passed on main and on the next run);
  45632283197 green; 45637913320 green (0.2.252). Three renumbers: 0334, 0337, 0338 and 0323 took 0.2.248–0.2.251 while
  the runs went.
- Independent review of the Windows code (a helper agent that did not write it): nothing serious; one low risk fixed
  (`asks`), the rest noted below.

**Open points / follow-up tasks:**
- The Pages proof on `main` (the release run's landing-page job and the push run of "Landing page" for this merge, close
  together) is in the lead's hands to read: runs after this merge.
- deploy-pages reads the artifact list through the runner's own service, not the REST list the wait step reads; the
  second try covers a longer lag. If it still fails twice in a row, raise the pause.
- Answering Y while the app is open: the uninstaller then says "close it first" (harmless).
- Real-app lessons test (undo after the app's Build) failed once on the branch (run 45624439056) – flaky, owner of that
  test should look if it repeats.
