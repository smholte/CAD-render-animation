# 0020 – Updates from GitHub: new versions with one click in the app

**Who:** worker · **Status:** running (worker chat started 5 Nov 2026) · **Branch:** `task/0020-updates-from-github`
**Started by:** lead chat, 4 Nov 2026 · **Lane:** Quality & delivery · **Area:** `.github/`,
`tools/build_release.py`, `installer/`, `blender/prefs.py` (update settings only), `docs/UPDATES.md`,
`CLAUDE.md` section 7, the app template (an update notice if needed). Replaces task 0005.

## Goal

The owner and his colleagues get new versions inside the app ("Update available" → one click), no
new installer each time. Updates are stored on GitHub (owner's decision, 4 Nov 2026).

## Background

- `docs/UPDATES.md`: Blender's extension system reads a repository = an `index.json` plus the
  extension zips; `tools/build_release.py` already writes `dist/update-repo/`; the installer
  accepts `-UpdateUrl` (and `-AccessToken`).
- The repository is public, so GitHub can host the update repository without a token: for
  example the zips as **GitHub Release** files and `index.json` on GitHub Pages or in the
  release. Note for the owner: anyone can then download the app (the code is public already).
- The chats' git policy refuses tag pushes, and GitHub Releases need a tag. A GitHub Actions
  workflow (task 0019) runs with GitHub's own permissions and can create the tag and release
  itself when the version on `main` changes. Check first whether that works; if a step can only be
  done by the owner, give him numbered click steps.
- Found in 0019: chats may push `.github/workflows/` files; they can read runs, jobs and logs
  (`tools/ci_status.py`) but cannot download run artifacts, cannot read
  `actions/permissions`, and cannot delete branches. The Windows install test is
  `tools/ci_windows_install.ps1` (puts the cached Blender zip next to Install.bat); the
  `build` job already makes the installer zip with `tools/build_release.py`. The workflow has
  `permissions: contents: read` – a release job needs `contents: write` for itself only.

## What to build

1. On `main`, when the version in `blender_manifest.toml` changes: GitHub builds the zip, creates
   the release (tag `v<version>`, the installer zip and the extension zip attached, the
   `CHANGELOG.md` section as text) and updates `index.json`.
2. The app checks for updates at start-up and shows "Update available: 0.x.y" with an
   **Update** button and "What's new" (from the changelog); after the update, Blender restarts.
3. Installer: points new installs at the GitHub update URL by default; existing installs get it
   through one last manual install (say so in the changelog).
4. `CLAUDE.md` section 7 rewritten: the worker bumps the version and merges; GitHub publishes;
   the worker gives the owner the release link (and still the zip in the chat).
5. **The app template must update too** (found in task 0021's review): today only Install.bat
   copies it, so an in-app update brings a new extension but an old template (e.g. the Help-menu
   entry for the user guide lives there). Either the update also refreshes the template, or such
   entries move into the extension. Test it: old template + in-app update → new template behaviour.

6. Small, from the lead (5 Nov 2026): pushes that change only the task list (`TASKS.md`,
   `tasks/**`) start a full 12-minute run too, and with six chats pushing, runs queue up. Skip the
   test run for such pushes (`paths-ignore`), but never for a push that also changes anything else.

## Done when

- [ ] A test release goes all the way: version bump on `main` → release on GitHub → an installed
      app (Linux test install) sees and installs the update
- [ ] Windows: the update path checked in the Windows job of 0019 (install old version, update)
- [ ] Owner's steps (if any) written and tested as far as possible
- [ ] Report filled in; merged and released through the new path

## Not in this task

- A private update channel with a token (not needed while the repository is public).

---

## Report (filled in by the chat that did the task)

**Chat / date:** worker chat, 5 Nov 2026.

**What changed:**
- **In the app** (`blender/updates.py`, `core/updates.py`, `update_helper.py`): a few seconds after
  start-up the app reads `…/releases/latest/download/index.json` on GitHub (only with Blender's online
  access on; switch "Check for updates at start-up" in the add-on preferences). Newer version →
  panel **Update available: 0.x.y** at the top of the Fresing tab (registered before 1 Import: a
  negative `bl_order` does not put a panel on top) with **Update now**, **What's new** (from
  `changelog.json`), **Release page**, **Later**. Update now: preflight (installed as an extension,
  no import running, no render queue running, a never-saved project with changes must be saved
  first), download in a thread with progress + Stop, size and SHA-256 checked, save the project,
  a moment later (Blender counts a project as saved only after its event loop ran; closing at once
  asks "Save changes?") copy `update_helper.py` to `<config>/fresing_update/`, write `plan.json`,
  start it with Blender's own Python (`-I`, no console window, breaks away from a job when allowed),
  close Blender. The helper waits for the PID, runs `blender --command extension install-file -r
  <same repo> -e <zip>` (Blender's own installer: unpacks next to the old one, then swaps), checks
  the installed version (one retry), copies the app template that now ships inside the extension
  (`app_template_files/`), writes `status.json` and `update.log`, starts the app again with the same
  app template and project – also when something failed. The next start shows **Updated to 0.x.y**
  with what's new, or what went wrong + **Show the update log**. Help menu: **Check for Fresing
  Render updates** (under the user guide). Self-test line "Update check". Manifest declares
  `network` permission.
- **App template** (point 5): ships inside the extension; the helper copies it, and every start
  copies it again where it differs (an update made another way brings it too). Tested with the
  real 0.2.10 template (`tests/data/old_app_template/`, no Help-menu entry) → after the in-app
  update the Help menu has "Fresing Render user guide".
- **GitHub publishes** (`.github/workflows/tests.yml`, `tools/release_tools.py`): job "Publish the
  release" after all test jobs on `main` when `v<version>` has no release yet – tag on the tested
  commit, installer zip, extension zip, `index.json` with full download addresses, `changelog.json`,
  the CHANGELOG section as text (`--latest`). Job "Windows - an installed old version updates itself
  from the release" installs an old build and lets it update from GitHub. A branch push with
  `[release rehearsal]` in the commit message does all that as a pre-release and deletes it again.
  Point 6: pushes that change only `TASKS.md`/`tasks/**` start no run (`paths-ignore`);
  `tools/ci_status.py` says so instead of waiting.
- **Installer**: always installs the zip next to it into `user_default` (the Blender remote repo
  "fresing" of `-UpdateUrl` is removed if an old install has it); online access on;
  `-UpdateUrl <index.json>` writes the app's update address (`portable\config\fresing_update.json`),
  `-UpdateUrl default` goes back to GitHub; `-AccessToken` gone (not in this task). installed.txt
  says the version and where updates come from.
- **Build**: `tools/build_release.py` stages the extension in one place (`stage_extension`: guide,
  app template, changelog.json; also used by the Linux test builds), writes the update listing with
  changelog.json, can build "as another version with another template" for the tests.
- Docs: `docs/UPDATES.md` (rewritten), `CLAUDE.md` (layout, tests, section 7 release procedure,
  lessons), user guide ("Updates: one click", "Updates do not arrive", two pictures, new Help-menu
  picture; `tools/guide_screens.py` mode "update"), README-install, README, CHANGELOG.

**Tested and measured** (name the machine and the model):
- REPORT-TESTS

**Open points / follow-up tasks:**
- REPORT-OPEN
