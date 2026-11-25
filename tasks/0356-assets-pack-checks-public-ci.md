# 0356 – Assets pack P5: the pack checks in the public repository (no private CI)

**Who:** worker · **Status:** waits – after 0354 · **Branch:** `task/0356-assets-pack-checks`
**Started by:** lead, 25 Nov 2026 23:3x (0344's P5; owner's picks 23:17, pick 12) · **Model:** Opus · effort Medium ·
Claude Code on the web, environment "CAD-render-animation"
**Area:** Quality & delivery lane – new `tools/assets_check.py` (+ its tests), new by-hand workflow
`.github/workflows/assets-check.yml` (`workflow_dispatch` only); additive: `.github/workflows/tests.yml` (one "Real
pack" Linux job, skipped while `installer/assets_pin.json` does not exist), `tools/ci_precheck.py` (the pre-release
rule), `docs/` only for the steps below. **Not:** app code (`fresing_render/`), `installer/` (0358 – it also edits
`tests.yml` after you, so keep your job self-contained), the private repository (the owner creates it when the first set
starts – its set-up files come with 0365).

## Goal

**One set of pack checks, all in the public repository, zero of the owner's private GitHub minutes** (pick 12): a
worker runs them in its session before it uploads a pack, and GitHub runs the same ones on the published download before
any app release names it. Plus the answer to 0344's one open question: **can a worker session publish a pack as a
release download?**

## Background (read first – only the parts named)

- `tasks/0344-study-assets-pack-plan.md`: **"Owner's picks"** (top), report **1.5** (data only), **1.6** (the public
  download: tag `assets-<version>`, always a pre-release, files on the release, the pin, how CI fetches it, who
  uploads), **1.7** (no private CI), the **CI** row of section 3's table, **6** "Quality bar" and "Building and releasing
  a pack version – no private CI".
- 0354's report: `core/assets_pack.py` (`verify()`, the notes), the contracts, the test-pack maker.
- Blender's zip in CI as the pattern for the pack's download + cache (`tests.yml`, the Blender steps around lines
  317–331 and 492–518 at 0.2.257); the stress model's release upload as the pattern for an upload by the REST API
  (`tools/make_test_stress.py --publish`); the places that read only "latest" or `v` tags (`core/updates.py:30`,
  `tools/build_site.py:102–111`, `tools/ci_precheck.py:539–541`, the rehearsal clean-up in `tests.yml:773–788`).

## What to do

1. **`tools/assets_check.py <pack folder or zip>`** – what a worker runs before an upload and CI runs after it:
   `pack.json` through `core/assets_pack.py` (no notes allowed), every listed file present with its size and sha256,
   contracts, **data only** (every `.blend` opened in Blender 5.2.3 in the background: no Text datablocks, no Python
   drivers beyond simple expressions, no OSL Script nodes, no handlers), every `.blend` appends into an empty project,
   a **code twin in the app** for every id (or a named `fallback`), the 256 px picture for every picker item,
   `LICENSE-ASSETS.txt` inside, picture sizes (2k in-project variants present; 4k only where allowed), the set budgets
   and the pack total (~300 MB for 1.0, pick 11), each look's `cost` against its code twin (pick 10: ≤ 1.3 × or the
   owner's mark), and **one small render per kind – no pink, no black**. Plain output: OK / one line per problem; exit
   code for CI. Tests: it passes on 0354's test pack and fails, with the right line, on a broken copy of it (one test per
   check).
2. **"Real pack" job in `tests.yml`** (Linux): reads `installer/assets_pin.json`; **skipped while there is no pin**
   (today); with a pin: restores `actions/cache` with the key `assets-<version>-<sha256>`, on a miss downloads the zip
   from the release (public, no token) and checks it with `sha256sum -c` – exactly Blender's steps – then runs
   `assets_check.py` on it. In every full run once a pin exists, and in a lane run when the pin or the pack code
   changed. Keep the job's own steps in one block so 0358 can add its Windows steps without touching yours.
3. **By-hand workflow `assets-check.yml`** ("Check an assets pack"): input = a release tag (`assets-1.0.0`); downloads
   that release's zip, runs `assets_check.py` and the app's with-pack tests against it – so a new pack can be checked
   **before** a branch moves the pin.
4. **Precheck rule:** every release whose tag does not start with `v` must be a pre-release (an `assets-*` release can
   never become "latest"); a test for it.
5. **First, tags must start no test run.** `tests.yml`'s `push:` has no tag filter, and GitHub does not apply path filters
   to tag pushes – a release tag made by a session's own token (unlike one made by a workflow's `GITHUB_TOKEN`) would
   start a full run on that tag. Make `assets-*` tags start nothing (check GitHub's rule first: a filter for tags alone
   can stop the branch runs too), merged to `main` **before** step 6; step 6 then checks that its test release started no run.
6. **The one-time upload test (needs the owner's OK – see "Owner's OK" below):** from this session, by GitHub's REST
   API, create a pre-release `assets-0.0.1-test` on `smholte/CAD-render-animation` titled "Test – not an app version,
   delete me", upload a 1 MB file of zeros, download it back by its public address, compare, then **delete the
   release and its tag** and check they are gone. Say in the report exactly what worked. If the session is refused:
   write `.github/workflows/assets-release.yml` (`workflow_dispatch` only, never on pull requests; it will clone the
   private working files with a read-only deploy key, build and check the pack with the cached Blender, upload with its
   own token, and never put a working file into a log or an artifact) plus the owner's click-by-click steps for the
   deploy key in `docs/` – its first real use is 0365. Last resort: a draft release the owner publishes.
7. Docs: a short section "Assets pack checks" in CLAUDE.md section 5 (what runs where, how a worker checks a pack
   before upload) – the lead reviews it.

## Owner's OK for step 6

**Owner, 25 Nov 23:4x: "Yes, try once"** – one 1 MB test pre-release `assets-0.0.1-test`, checked and deleted again. If GitHub refuses the session, prepare the key route (step 6) and say so in the report – don't retry other ways.

## Done when

- [ ] `assets_check.py` with its tests, the skipped-until-pinned "Real pack" job, `assets-check.yml` and the precheck
      rule are on `main`; the full run is green and no job uses the private repository or a secret.
- [ ] Steps 5 and 6 done as the owner allowed, the test release deleted again, the result in the report.
- [ ] Report: how 0365 (first set) builds, checks and uploads a pack – the exact commands; the runs this task needed.
- [ ] Report filled in, merged (a tools / CI task: `[full run]` in the last code commit if the version is not raised –
      section 2).

## Not in this task

The installer, the pin file and pack updates in the app (0358); Settings > Assets (0357); the private repository and
its makers (0365); real looks; licence texts. Never the owner's files; never his employer's name.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
