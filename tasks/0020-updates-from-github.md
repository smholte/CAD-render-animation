# 0020 – Updates from GitHub: new versions with one click in the app

**Who:** worker · **Status:** open – can start · **Branch:** `task/0020-updates-from-github`
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

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
