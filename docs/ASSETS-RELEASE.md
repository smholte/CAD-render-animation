# Publishing a Fresing assets pack (task 0356)

A pack is built from the private working files (`smholte/fresing-assets-src`, no workflows there) and published as a
**pre-release** `assets-<version>` of this public repository: `FresingAssets-<version>.zip`, `LICENSE-ASSETS.txt`,
`assets.json`. All checks run here (CLAUDE.md section 5, "Assets pack checks").

**Who uploads.** Task 0356 tried once whether a worker's Claude Code session may create a release itself: the session's
own safety check refused it (28 Nov 2026), so the upload goes through the by-hand workflow **"Release an assets pack"**
(`.github/workflows/assets-release.yml`). It clones the working files with a **read-only deploy key** – the one secret –
builds the pack with the private repository's `tools/build_pack.py` (task 0365), runs the public checks, and publishes
with the workflow's own token. The working files never go into a log or an artifact.

## Once: the deploy key (owner, about 5 minutes – needs `fresing-assets-src` to exist)

A worker makes the key pair in its session and gives you the two parts; or on your PC:

1. Open **PowerShell** and run `ssh-keygen -t ed25519 -N "" -C "assets release" -f assets_src_key`.
   You should see two new files in that folder: `assets_src_key` (private) and `assets_src_key.pub` (public).
2. On github.com open **smholte/fresing-assets-src** → **Settings** → **Deploy keys** → **Add deploy key**.
   Title: `assets release (read-only)`. Key: the whole text of `assets_src_key.pub`. Leave **Allow write access**
   **unticked**. Click **Add key**.
3. On github.com open **smholte/CAD-render-animation** → **Settings** → **Secrets and variables** → **Actions** →
   **New repository secret**. Name: `ASSETS_SRC_DEPLOY_KEY`. Secret: the whole text of `assets_src_key` (the file
   without `.pub`, from `-----BEGIN` to `-----END … KEY-----`). Click **Add secret**.
4. Delete both files from your PC. You should now see the secret's name (not its value) in the list.

## Each pack version (a worker writes the exact values in its report)

1. The worker builds and checks the pack in its session (`tools/assets_check.py` on the zip, `tests/real_pack/`) and
   pushes the working files to `fresing-assets-src` main.
2. You: github.com → **smholte/CAD-render-animation** → **Actions** → **Release an assets pack** → **Run workflow** →
   version (e.g. `1.0.0`), one line on what is new → **Run workflow**. When it is green you should see a new
   pre-release "Fresing assets pack 1.0.0 – data for the app, not an app version" under **Releases**.
3. **Actions** → **Check an assets pack** → **Run workflow** → `assets-1.0.0`: checks the published download.
4. A worker branch moves `installer/assets_pin.json` to it (task 0358 onwards); its full run checks the pack once more.

A version is never published twice (the workflow refuses an existing tag): a fix is the next patch version. A pack
whose checks failed stays an unpinned pre-release that no app offers; you may delete it under Releases (also its tag:
Code → Tags).
