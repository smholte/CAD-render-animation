# 0356 – Assets pack P5: the pack checks in the public repository (no private CI)

**Who:** worker · **Status:** done 28 Nov · **Branch:** `task/0356-assets-pack-checks`
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

**Chat / date:** Claude Code on the web, 28 Nov 2026 (report final) · no version raised (tools / CI task, `[full run]` commits)

**What changed:**
- **`tools/assets_check.py`** (new) – the one set of pack checks, on a pack folder or `FresingAssets-<v>.zip`:
  zip safety (one top folder, no `..`, no links, name = pack.json's version); pack.json through `core/assets_pack.read`
  with **no note** (every left-out row named with its reason); `verify` (size + sha256), no unlisted file, data files
  only (`.blend .exr .hdr .png .jpg .jpeg .tx .txt`); `LICENSE-ASSETS.txt` inside, listed, not empty; code twin / named
  `fallback` (`Registry.refused`); 256 px picker picture for every item; picture sizes from the head (PNG / JPEG / EXR):
  ≤ its 1k / 2k / 4k, every 1k / 4k has its 2k variant, 4k only for hdri, light / hdri EXRs 2:1; set budgets (problem),
  pack > 300 MB (warning); `cost` given for every item with a code twin (> 1.3 x without `approved_slower` is already a
  left-out row). Then a **Blender child** (the venv's `bpy`, or `--blender <binary>`): every `.blend` holds its
  datablock, **data only** (no Text, no Python driver beyond simple expressions, no OSL Script node, no linked library,
  pictures relative + listed + in the row's `textures`, none packed), the kind's contract (sockets, no BSDF / Output /
  forbidden node inside – also in nested groups –, finish reads `fr_fx_*` + `fr_pixel_angle`, prop `fr_lod` FACE 1 / 2
  and floor at z = 0, environment collection not empty), appends into an empty project with readable pictures, and
  **a small Cycles render of every item** (64 px, 8 samples; plane + ortho camera for groups, framed objects with a
  transparent film for props / environments, the world for light / hdri pictures) – pink > 2 % or mean < 0.01 = a
  problem. Output `OK – …` or `PROBLEM:` / `WARNING:` lines, exit 1. Also `--pin` (checks the pin, prints key=value for
  CI), `--fetch <tag>` (downloads a release's zip; checks pre-release, `LICENSE-ASSETS.txt` beside it, `assets.json`
  against the zip), `--listing <zip>` (writes `assets.json`). (Brief: "one render per kind" – every item is rendered,
  0.3 s each: the first try only rendered the first look of a kind and missed a black second one.)
- **`tests/test_assets_check.py`** (new, 51 tests, ~35 s): the test pack passes with renders of all 6 kinds; one broken
  copy per check (4 zip, 3 pack.json, 4 files, 2 licence, 2 twin, 6 pictures, 2 size, 2 cost, 6 pin, 12 broken
  `.blend`s made by a Blender child, pink, black, fetch, listing).
- **`tests/real_pack/test_real_pack.py`** (new): the app's with-pack tests on a REAL pack (`FRESING_ASSETS_REAL`); in no
  pytest group, skipped without the variable; plug-in tasks add their real-pack checks here.
- **`tests.yml`**: `push: branches: ["**"], tags-ignore: ["assets-*"]` (GitHub applies no paths filter to tag pushes,
  and a tags filter alone stops branch runs – so every branch and every tag but `assets-*`, as before);
  job **"Linux - real assets pack"** (`if: needs.precheck.outputs.realpack == 'true'`: pin read with `--pin`, cache key
  `assets-<version>-<sha256>`, on a miss `curl` + `sha256sum -c`, `assets_check.py`, `tests/real_pack` with
  `--max-skipped 0`) – self-contained, 0358's Windows steps go into a job of their own; verdict needs it (`rp_ok`: must
  pass when planned, skipped otherwise).
- **`tools/ci_precheck.py`**: rule "every release whose tag does not start with `v` is a pre-release"
  (`check_release_kinds`; today's drafts site-kit / stress-model / movements_steps are pre-releases → pass);
  output `realpack` = pin exists and (full run, or a lane run that changed the pack code). **`tools/ci_groups.py`**:
  `REALPACK_FILES` (`core/assets_pack.py`, `core/assets_registry.py`, `tools/assets_check.py`) and `tests/real_pack/`
  mark a lane plan `realpack`.
- **`.github/workflows/assets-check.yml`** "Check an assets pack" (by hand, input = tag): `--fetch`, every check,
  `tests/real_pack`. **`.github/workflows/assets-release.yml`** "Release an assets pack" (by hand, main only) + 
  **`docs/ASSETS-RELEASE.md`** (owner's deploy-key steps) – step 6's fallback, see below.
- CLAUDE.md section 5: "Assets pack checks" (for the lead to review); test_ci_tools.py: 5 new tests.

**Step 5 / step 6 – the upload test:** the tag filter was merged to `main` first (f2fdf08). Then the one-time test
(create pre-release `assets-0.0.1-test`, upload 1 MB of zeros, download it back, compare, delete release + tag) was
**refused by this session's own safety check before any call reached GitHub** ("destructive or unwanted action") –
nothing was created, nothing needs deleting. As the brief says, not retried another way. Instead the key route:
`assets-release.yml` clones `fresing-assets-src` with a read-only deploy key (the only secret,
`ASSETS_SRC_DEPLOY_KEY`), builds with its `tools/build_pack.py`, runs the public checks, deletes the working files and
publishes with the workflow's own token (`contents: write` in that job only); inputs reach the shell through `env`
only; no artifact, no `set -x`, the build log stays on the runner. The owner's one-time steps: `docs/ASSETS-RELEASE.md`.
Not run yet (needs the private repository and the key) – its first real use is 0365. Whether a tag made by the
workflow's own token starts a run is moot (GITHUB_TOKEN starts none, and `assets-*` is ignored anyway).

**How 0365 builds, checks and uploads a pack (exact commands):**
1. In the session (both repositories attached, public one beside the private one), Blender 5.2.3 as `~/venv` bpy:
   `~/venv/bin/python ../fresing-assets-src/tools/build_pack.py --version 1.0.0 --out dist` → `dist/Fresing Assets/`
   + `dist/FresingAssets-1.0.0.zip` (0365 writes this maker; the workflow calls it with exactly these arguments).
2. `~/venv/bin/python tools/assets_check.py dist/FresingAssets-1.0.0.zip` → `OK – every pack check passed`;
   `FRESING_ASSETS_REAL="dist/Fresing Assets" ~/venv/bin/python -m pytest tests/real_pack -q` → all pass.
3. Push the working files to `fresing-assets-src` main; the owner (once) adds the deploy key and secret
   (`docs/ASSETS-RELEASE.md`), then runs **Actions → Release an assets pack** (version `1.0.0`, one line on what is new).
4. **Actions → Check an assets pack** → `assets-1.0.0` (green before any pin).
5. A branch moves `installer/assets_pin.json` (0358's file; fields as in the docstring of `assets_check.py`:
   `--listing` output + `"tag"`): its full run runs "Linux - real assets pack" on the cached download.

**Tested and measured** (4-core web machine, Linux, Blender 5.2.3 as a module and the real binary):
- Test pack 1.0.0 (23 files, 3.5 MB): every check incl. 7 renders in **3 s** (bpy module) / 6 s (real Blender
  `--blender`). `tests/test_assets_check.py` 51 passed in ~35 s; `test_ci_tools.py` 69 passed.
- GitHub: run 46137032967 (6472daf, full, 29 min, green, "real assets pack" skipped – no pin); then the merge of main
  (only task files) fast-forwarded to `main` (f2fdf08; its run 46139353485 docs mode, green); run 46139572716 of 2aeaff1
  (release route, full, 34 min, green, "real assets pack" skipped). After merging main (0374): run 46142341316 failed
  once in 0374's new `test_cable_lay_0374_independent.py::test_KNOWN_FAULT_a_coil_read_from_a_coarse_faceted_tube_…`
  (11.6 mm deviation against its 6.5 mm bound; passes on this Xeon and passed on 0374's own run) – green on a re-run of
  that job: a processor-dependent number in 0374's test, not this task's code (for the lead: a follow-up for the cable
  lane). Then main moved again (0372): one more full run of the merge – see TASKS.md / the last run on main.
- No job uses the private repository or a secret except `assets-release.yml` (by hand, never run yet).

**Open points / follow-up tasks:**
- 0358: write `installer/assets_pin.json` in the format `read_pin` checks (version, tag, file, url, sha256, bytes,
  licence_id) – `assets_check.py --listing` + `"tag"` gives it; the "real assets pack" job then runs by itself.
- 0365: `tools/build_pack.py --version <v> --out <dir>` in the private repository (the workflow's contract); the owner's
  deploy-key steps before the first release.
- The render check judges "pink / black" only; whether a look is *right* stays the owner's pick page.
- The precheck reads the newest 100 releases only (as before for versions); an old non-`v` release beyond them is not
  checked.
- No independent review (no Windows code; CI-only workflows) – the lead may want one of `assets-release.yml` before its
  first use, since it is the one place a secret is used.
