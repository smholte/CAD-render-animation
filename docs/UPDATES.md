# Updates: how a new version reaches the PCs

Since 0.2.16 the app updates itself (task 0020). Nobody uploads anything by hand: a version bump
merged into `main` is published by GitHub, and every installed app offers it at its next start.

## The path of a new version

1. A worker chat raises the version (`fresing_render/__init__.py` **and**
   `fresing_render/blender_manifest.toml`), adds it to `CHANGELOG.md` and merges into `main`
   (CLAUDE.md section 7).
2. GitHub tests `main` (`.github/workflows/tests.yml`). When every test passed and there is no release
   for this version yet, the job **Publish the release** creates it (not yet "latest"): tag
   `v<version>` on the tested commit, title "Fresing Render <version>", the version's `CHANGELOG.md`
   section as text, and the files
   - `FresingRender-<version>-windows.zip` – the installer, for new PCs (and PCs before 0.2.16)
   - `fresing_render-<version>.zip` – the extension, which the app downloads
   - `index.json` – Blender's standard extension listing, with the full download address of the zip,
     its size and SHA-256
   - `changelog.json` – every version's changes, for "What's new" in the app
3. The job **Windows - an installed old version updates itself from the release** then installs an old
   build on a GitHub Windows machine, lets it find the new release (its own address) and update
   itself, and checks the result (version, app template, update log, the project reopened). Only when
   that passes, **Offer the release to the apps** makes it the newest ("latest") release.
4. On the PCs: a few seconds after the app starts, it reads
   `https://github.com/smholte/CAD-render-animation/releases/latest/download/index.json` (GitHub sends
   that address to the newest release). Newer than the installed version → **Update available** at
   the top of the Fresing tab, with what's new from `changelog.json`.
5. **Update now**: the app downloads the extension zip and checks size and SHA-256, saves the project,
   copies `update_helper.py` out of the extension folder and starts it with Blender's own Python, and
   closes. The helper waits until Blender has closed, installs the zip with Blender's own installer
   (`blender --command extension install-file -r user_default -e <zip>`), checks the installed version,
   copies the app template that ships inside the new extension (`app_template_files/`) into place and
   starts the app again with the same project. That start shows "Updated to …" (or what went wrong;
   the steps are in `<Blender config>/fresing_update/update.log`).

The release page also shows the commit, so `CHANGELOG.md` needs no "Commit" line for new versions.

## Code

| Where | What |
| --- | --- |
| `fresing_render/core/updates.py` | versions, `index.json`, `changelog.json`, download with checks; no Blender |
| `fresing_render/blender/updates.py` | start-up check, the panel, Update now, Help > Check for Fresing Render updates, template refresh |
| `fresing_render/update_helper.py` | installs while Blender is closed, starts the app again; plain Python |
| `fresing_render/blender/prefs.py` | "Check for updates at start-up" and the Updates box in the preferences |
| `tools/build_release.py` | puts the app template and `changelog.json` inside the extension; writes `dist/update-repo/` |
| `tools/release_tools.py` | the release job's plan (publish or not), full download addresses, release text |
| `.github/workflows/tests.yml` | jobs "Publish the release", the release check and the rehearsal clean-up |

The app template (`app_template/fresing_render/`) ships inside the extension. Besides the helper, the
extension also copies it into place at every start when it differs, so an update made another way
brings the right template too.

## Other update addresses

`Install.bat -UpdateUrl "<address of an index.json>"` writes the address to
`<Blender folder>\portable\config\fresing_update.json`; the app then asks there instead of GitHub, for
example a network folder with the files of a release (`index.json`, `changelog.json`, the extension
zip): `\\SERVER\share\fresing\index.json` (a `file://SERVER/…` address works too). Later runs of
Install.bat keep it; `-UpdateUrl default` goes back to GitHub. An install that used the old Blender
update repository keeps that address. For tests the environment variable `FRESING_UPDATE_URL` does
the same.

Company proxies: the app uses the Windows proxy setting (Internet Options). A proxy that needs a
Windows login, or one set by a script (PAC/WPAD), may block the check; the self-test line "Update
check" says so. Then IT can allow github.com and its download servers, or the PC gets new versions
by running the installer.

## Tests

| Test | Where |
| --- | --- |
| versions, listing, changelog, download, helper with a stand-in Blender | `tests/test_updates.py` |
| check, panel in every state, Update now (download, save, helper plan, close), template refresh, Help menu | `tests/test_updates_blender.py` |
| real Blender, real window: old version (0.0.1 with the 0.2.10 app template) finds the update on a GitHub-like local server, Update now, closes, is updated, starts again; new template and Help menu checked | `tools/ci_update_test.py --gui` (real-app job, "update") |
| Windows: old build installed with Install.bat, updates itself from a local copy of the listing (folder with a space and an accent), then Install.bat over it, self-test | `tools/ci_windows_install.ps1 -OldReleaseZip … -UpdateRepo …` (Windows job) |
| Windows: old build updates itself from the published release on GitHub | release check job (`-UpdateFrom github -OnlyUpdate`) |
| the real GitHub address from Linux: check and download of the newest release | `tools/ci_update_test.py --github --expect <version>` |

**Rehearsal:** a branch push whose newest commit message contains `[release rehearsal]` runs the release
jobs as a pre-release `v<version>-rehearsal.<run>`, checks it on Windows and deletes it again.

## Blender version changes

The extension is pinned to Blender 5.2 (`blender_version_min = 5.2.0`,
`blender_version_max = 5.3.0`). A version that needs another Blender is not installed by the app: it
says "needs a new installer" and links to the release page. When moving to the next LTS:

1. Change `$BlenderVersion`, `$BlenderSeries` and `$BlenderSha256` in
   `installer/Install-FresingRender.ps1` (checksum from download.blender.org/release/BlenderX.Y/).
2. Update the version range and the OpenCascade wheel (Python version of the new Blender)
   in the manifest and `tools/build_release.py`.
3. Run the tests against the new `bpy` version, release, and have every PC run the new installer at
   the same time (files saved in a newer Blender may not open in an older one).
