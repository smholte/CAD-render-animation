# 0344 – Study (findings only): the Fresing assets pack – how every system uses it without breaking the app

**Who:** worker · **Status:** done 25 Nov – findings only (report + pick page on the branch) · **Branch:** `task/0344-study-assets-pack-plan` (branch only, never
merged; every push `[skip ci]`)
**Started by:** lead, 25 Nov 2026 20:4x (owner 20:34: "we must make a plan to how to do this and not break the app. what
additions is needed per system to not break it.") · **Model:** Opus · effort **Max** (owner: high standards – done
well, not fast)
**Area:** findings only. Reads the whole app, `installer/`, `tools/`, `.github/workflows/`, `docs/`, the briefs and
reports of 0228 (demo kits), 0272 (locations), 0273 (material picker), 0274 / 0318 / 0314 (finishes, looks), 0286
(asset libraries), 0340 (paint import), **0343** (report on branch `task/0343-study-paid-company-use`). A small proof
in **new files only** on the branch is allowed (e.g. `tools/assets_pack_proto/`); changes no existing file. Not a code
slot.

## Goal

A plan the owner and the lead can build from, task by task, so that **Fresing's own assets** (materials and node
groups, textures, HDRIs and 360° photos, environments, props, people, showcase and learning models, learning projects)
are **rebuilt as files Fresing owns** and used by every part of the app – **without breaking anything**: not the app
without a pack, not old projects, not the tests, not speed.

## Background – the owner's picks on 0343 (25 Nov 20:34)

1 **rebuild all** Fresing assets as new files Fresing owns, step by step · 2 **in the installer for everyone**, one
question at the first start (Private · Education · Non-profit · Company), a company sees the price and a Buy link once,
nothing locked · 3 one-time per user, updates of pack 1.x · 4 €129 / €59 freelancer (**prices may change; no selling
until the app is much further – the owner has high standards**) · 5 non-profits free for own unsold work · 6 Paddle ·
7 invoice + licence file, About "Licensed to …", **plus a nudge line** in About and the export window when the user
said "Company" and no licence file is found · 8 Benelux trademark before the first sale · 9 Blender support: later ·
10 e-mail, answer in 5 working days · 11 the plain licence draft · 12 **workers (AI) build the assets; the owner sets
the look, picks, adjusts and approves every set on pick pages and adds his own photos** – keep a short record per set of
his choices (ownership).

Ground rules from 0343 (check them, don't re-research): the code stays GPL-3.0-or-later; the pack is its own folder with
its own licence, never inside code files; **the app must run without the pack** (GPL condition and safety); no lock, no
online check (the app is fully offline); today's code looks are GPL for ever in 232 versions – they stay as the free
fallback.

**Changed while running (owner 25 Nov 21:35 – test minutes):** **no tests in the private repository** (the owner's
GitHub Free minutes are shared and limited; public repositories run tests for free). Only the **working files** stay
private (source `.blend` scenes, full-size textures, the owner's raw photos, sets not yet approved, the per-set records of
his choices) – that repository has **no CI**. The **finished pack** is public: a download attached to a GitHub release
(not Git LFS – LFS downloads, also by CI and forks, count against the owner's 10 GB a month), under the **Fresing Assets
Licence** with the licence file inside the pack. **All pack tests run in the public repository** – with and without
the pack – against that release download, cached between runs. Compare this with a private-CI plan in one short table
and recommend one.

## Questions to answer

1. **Pack format and place:** folder and zip layout, `pack.json` (id, version, the app versions it fits, asset list
   with stable ids, licence), where the installer puts it (beside the extension, not inside it), how the in-app update
   updates it apart from the app, how a company's approved-version folder and `.frsetup` (0272) carry it, uninstall,
   a broken or missing pack (the settings-file pattern of 0283: ignore, one line, never a crash). The public
   download of the finished pack as a release asset (size, how a pack version maps to a release, how the installer and
   CI fetch it); the working files stay private.
2. **One asset registry** every system asks ("material `steel.painted`", "HDRI `studio.soft`", "environment
   `quay.small`") → pack item if present, else the built-in code item with the same id; ids never change. Test in
   Blender 5.2.3: **append vs link** of pack materials / node groups / collections into a project – a saved project
   must open on a PC **without** the pack and be sendable to a client; what is stored to re-find the source (id + pack
   version) for "update looks"; file size and load time.
3. **Per system, the additions needed so it does not break** – for each: files, what changes, the fallback, the tests
   both ways, the lane, size, risk. At least: importer + paint rules (0340 / 0287), material library + picker (0273),
   finishes + adjust (0274 / 0314 / 0318), CAD colours / RAL, decals, light looks + world + weather + sea, surroundings
   + props + people, cables / hoses / chains looks, machining chips / coolant, demo kits + demo project, lifting crane
   classes, test tour + Learning hub + lessons (sets that need the pack vs not), material pictures, Web 3D export
   (baking pack textures; the page is the user's output), Fresing Viewer (MIT – exports only), PC check + Stress
   (lines with and without the pack; VRAM and render time with real textures), backups, Client view, workspaces,
   Settings ("Use Fresing assets" switch?), first-start set-up (the usage question), About + export window (licence
   lines, nudge), installer + update + uninstall, CI (all in the public repository: without the pack, with a tiny
   **test pack** made by a tool, and with the real pack from its release download, cached; **no private CI**), the
   user guide + function list.
4. **Old projects:** nothing changes in a project until the user chooses (like 0340); an "Use the new Fresing looks"
   action with before / after; models already imported keep their materials.
5. **Speed and size budget:** texture sizes per quality (Draft / Normal / Final), pack size in the installer, memory on
   the stress model (11,228 parts) and the demo; nothing slower than today without the user choosing it.
6. **Making the assets:** a pipeline per kind (node materials, textures – procedural and from the owner's photos, HDRIs
   from the Insta360, environments, models) built by workers in the private repository (no CI there); the **owner's pick page per
   set** with before / after pictures, his choices recorded (`OWNERSHIP.md` per set); quality bar = clearly better
   than today's code looks.
7. **Order of tasks** (lanes, sizes, model · effort, what waits for what) so the app is never broken in between: first
   the invisible parts (pack format, registry, fallback, test pack, CI both ways), then one asset set at a time, each
   with the owner's OK; licence texts, shop, first-start question and nudge **last, just before selling** (the owner
   decides when).

## Done when

- [x] Report below answers 1–7 with file names and a task table (P-numbers; the lead turns them into tasks).
- [x] The append / link proof was run in Blender 5.2.3 on the branch (say where it ran and what was measured).
- [x] A pick page `tasks/0344_page/index.html` for the owner's choices (plain words, an explanation per choice, ★ first)
      with a diagram of the pack, the registry and the fallback.

## Not in this task

Building anything in the app; licence texts, shop, trademark; making real assets. Never the owner's STEP files or his
employer's name.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (4 cores, Intel Xeon 2.1 GHz, 16 GB, no graphics card), 25 Nov 2026. Branch
`task/0344-study-assets-pack-plan` (pushes `[skip ci]`, never merged). App on the machine: `main` at 0.2.257. Findings
only – no app code, no existing file changed. Not legal advice.

**Owner's changes while running:** 21:35 – no tests in the private repository; the finished pack a public release
download under the Fresing Assets Licence; all pack tests in the public repository (1.6, 1.7, section 6, P5). 21:41 –
outputs that carry files: a licence sentence, and the export never carries the pack's full-size HDRIs or pictures, size
and look cost measured (3.1, P12). The branch took `main` once for the lead's updated brief.

**What changed:** new files only – this report; the pick page `tasks/0344_page/` (`index.html`, three pictures); the
proof `tools/assets_pack_proto/` (`make_test_pack.py`, `try_pack.py`, `run_proof.py`, `registry_proto.py`,
`web3d_measure.py`, `web3d_views.py`, `README.md`, `results_25nov.md`, `results_web3d_25nov.md`). `TASKS.md` not touched (branch only – the lead sets 0344 to done). Three read-only helper agents
(Explore) mapped the look systems, the scene / learning systems and the delivery machinery; I checked their
decision-relevant claims in the code myself (CI skips, `.frsetup` keys, settings in background runs, the lock's marks,
the load upgrades, Web 3D's BSDF lookup, the light pictures). File:line references are `main` at 0.2.257.

### In short

1. **Three layers, nothing else changes.** The **pack** (a folder `Fresing Assets` with `pack.json`, its own licence and
   one `.blend` per asset); **one registry** in the app that answers by id (`material:paint_satin`, `light:PRODUCT`,
   `environment:FACTORY` – today's ids, never changed); **today's code looks as the fallback** under the same id.
   Without a pack the app is exactly today's app.
2. **Append, never link** (proof in Blender 5.2.3, section 2.4): only an *appended* item with its pictures *packed into
   the project* opened complete on a PC without the pack – also after an "update looks". A link went black. Blender 5's
   new "link + pack" lost the pictures; with the pictures packed into the pack's own files it travelled, but the update
   then broke it ("Cannot pack absolute file") and the updated project went black on a client.
3. **A pack look feeds the app's own BSDF; it does not replace the material.** Seven parts of the app read the
   material's one top-level Principled BSDF (Web 3D bake, painted welds, coolant sheen, plastic chips, the park's
   lights, Adjust, the weather / section / fade wraps). So the pack's node group gives Colour, Metallic, Roughness,
   Normal (+ optional coat, tangent, alpha) and the app keeps its BSDF, wear, rust, Adjust and wraps as they are.
4. **Nothing changes in a project by itself.** Each material and each project gets a look-source stamp (`code` /
   `pack:1.2.0`); a project saved before the pack stays `code` until the user presses **Use the new Fresing looks**
   (before / after pictures, a backup first, one undo step). The pack never uses `LOOK_VERSION` or the other stamps that
   rebuild old projects at load today.
5. **Size and memory (measured):** a 3-picture set at 1k / 2k / 4k costs 30 / 66 / 210 MB in Cycles. Blender 5.2.3's new
   **texture cache** (on by default) holds the 4k set at **43 MB** – but only for picture *files* with `.tx` files beside
   them; **packed pictures never use it** (no `.tx` made, 210 MB). So projects carry pictures at **≤ 2k**; 4k is a later
   "Final only" option read from the pack folder.
6. **Place and updates.** `%LOCALAPPDATA%\FresingRender\Fresing Assets\` beside `Tools\` – it survives a repair, a
   Blender upgrade and **Update now** (which replaces only the extension folder); the uninstaller removes it. **The
   finished pack is a public download attached to a release of the public repository** (`assets-1.0.0`, always a
   pre-release, so it can never become the app's "latest"), `LICENSE-ASSETS.txt` inside the zip and beside it. Each app
   release names the pack version it was tested with (`assets.json`); the app offers a newer pack with its size, the
   user clicks.
7. **No private CI (owner 21:35) – recommended over the first plan (table in 1.7).** The private repository holds only
   the working files and runs nothing. A worker builds the pack in its session, runs the public pack checks there and
   uploads the zip as a pre-release; the public CI tests that download (cached, like Blender's zip) before any app
   release names it – **the pin is the gate**. Workers build; the owner approves every set on its pick page; his choices
   stay in `OWNERSHIP.md` in the private repository.
8. **Order:** six invisible tasks first (format + registry + test pack · bring / keep / update · Settings > Assets ·
   installer + update · the pack checks in the public repository · the update-looks action), then the plug-in points per
   system with a made-up test pack (still no visible change), then one asset set at a time (★ first: paints). Licence
   texts, the first-start question, the nudge lines and the shop last, when the owner says so.
9. **Outputs that carry files (owner 21:41).** A licence sentence: assets inside an output (a 3D page, its model file,
   a Fresing Viewer file, a project sent on) may only be used as part of that output. The 3D page never carries a pack
   file or a pack photo at full size: today it already holds only a 256 px light picture, a tone-mapped JPEG background
   and textures baked into 0.2 m tiles (checked: none of the pack's files inside). The plan caps pack items at half
   their full size – background ≤ 2,048 px, baked pictures ≤ 1,024 px per 0.2 m – **measured** (3.1): the page shrinks
   from 2.65 to 1.75 MB and from 5.18 to 2.20 MB; the look changes by 1.7 and 0.6 of 255 (softer distant buildings;
   pictures the same at 0.8 m). The page's own code stays dual GPL / MIT.

### 1 · Pack format and place

**1.1 The pack.** A zip `FresingAssets-<version>.zip` with one top folder `Fresing Assets/`. Never a name starting
`fresing_render-` (the installer, `build_release.py:187–190` and the release upload `tests.yml:677` take any such zip for
the extension) or `FresingRender-*-windows.zip` (CI takes the first one, `tests.yml:517`).

```
Fresing Assets/
  pack.json                       what is in it (table below)
  LICENSE-ASSETS.txt              the Fresing Assets Licence (0343's plain draft until its final text)
  CREDITS.txt                     other people's parts, only if a set ever uses any (CC0 sources)
  materials/<id>.blend            one asset per .blend: a node group "FRP <id>" (contract in 2.3)
  finishes/<id>.blend
  lights/<KIND>.exr               the light looks' pictures (today drawn by code, 2048 x 1024 float)
  hdri/<id>_1k|2k|4k.exr          360° photos (the owner's Insta360); .tx files for the 4k ones (section 5)
  textures/1k|2k|4k/<set>_<map>   shared pictures with versioned names (a file is never overwritten)
  environments/<id>.blend         modules the code layout places (bench, rack bay, container …), not whole halls
  props/  people/  decals/  cranes/<class>/  projects/<id>/
  pictures/<kind>.<id>.jpg        256 px picker pictures, made by the pack's own pipeline
```

| `pack.json` field | Meaning |
| --- | --- |
| `format` `"fresing-assets"`, `format_version` 1 | what the file is; a newer format → the app uses its own looks + one note |
| `id`, `title`, `version` `"1.2.0"` | 1.x = the paid major (owner's pick 3); minor = new sets; patch = fixes |
| `app_min`, `app_max` | the app versions it fits (the demo kits' rule) |
| `contract` | interface version of the node groups (per kind; a row may name its own) |
| `licence`, `licence_id` | `LICENSE-ASSETS.txt`, `"fresing-assets-1.0"` |
| `qualities` | `{"draft": "1k", "normal": "2k", "final": "4k"}` |
| `sets` | per set: title, `approved` (date of the owner's OK), version it shipped in |
| `assets[]` | `id` (`<kind>:<id>`), `kind`, `file`, `datablock` `[collection, name]`, `sha256`, `bytes`, `contract`, `fallback` (only a pack-only item), `picture`, `set`, `since`, `changed`, `textures[]`, `size_m`, `cost` (render time vs its code twin) |

**1.2 Where it lives on a PC.** `<I>\Fresing Assets\`, `<I>` = the install folder (default `%LOCALAPPDATA%\FresingRender`),
beside `Tools\`, `licenses\` and `blender-5.2.3-windows-x64\`:
- a **repair** deletes only `_unpack`, the template and `licenses` and copies them again; a **Blender upgrade** deletes
  only the old `blender-*` folder after moving `portable\`; **Update now** replaces only
  `…\extensions\user_default\fresing_render` (Blender's `install-file`) – a sibling survives all three
  (`Install-FresingRender.ps1` 148–246, `update_helper.py` `run` 471–527);
- never inside `blender-*-windows-x64\` (deleted at a Blender upgrade) or inside the extension (wiped at every update);
- the app finds it in this order: `FRESING_ASSETS` (tests, CI, developers – like `FRESING_DEMO_KITS`), the company
  set-up's folder (1.4), `<I>\Fresing Assets` found from Blender's own path (`appicon.install_dir`, needs
  `installed.txt`). The last two work in **background Blenders** too (queue, tour / demo builds, PC check), which never
  read the settings file (`settings_store.usable`, checked);
- how it gets there (★ page choice 3): the installer downloads the pinned `FresingAssets-<v>.zip` during the install,
  like Blender (sha256 checked; a PC without internet: the zip next to `Install.bat`, as for Blender; `-NoAssets` skips
  it), unpacks it into a staging folder and moves it in place (the installer's own `_unpack` pattern); a repair keeps a
  pack of the same version. PCs updated with Update now never run the installer – they get the pack through 1.3;
- uninstall: inside `<I>`, so the existing `Remove-Item <I> -Recurse` takes it; Documents stay; projects keep their
  copies. Settings > Apps shows the bigger size (EstimatedSize walks `<I>`).

**1.3 Updated apart from the app.**
- Each app release carries **`assets.json`** beside `index.json` = the pack version this app version was tested with:
  `{"format": "fresing-assets-listing", "version": "1.2.0", "file": "FresingAssets-1.2.0.zip", "url": "…",
  "sha256": "…", "bytes": …, "app_min": "…", "changes": "New paints and metals"}`. The app reads it in the existing
  update check as a sibling file (`sibling_url`, as `changelog.json`) – so the same code serves GitHub and IT's approved
  folder. Older apps ignore it (`pick_package` keeps only `fresing_render`). Its `url` is the zip on the pack's own
  release (1.6).
- Installed ≠ listed → one line under Updates and in the update notice: "Fresing assets 1.2 – new paints and metals
  (240 MB) – Download". Never automatic, never during a render.
- Download in a helper thread into its **own** folder `<config>\fresing_assets_update\` (the app update's
  `start_download` deletes every zip in `fresing_update\`, `blender/updates.py:349–354`); size + sha256 checked (the
  app update's `download`); unpacked to `<I>\Fresing Assets.new\`, checked (pack.json, every listed file with its
  sha256); **swapped at the next start** (`Fresing Assets` → `.old` → deleted; the update helper's wait for other
  Blenders of the install). Projects hold copies (2.4), so a swap never changes an open or saved project.
- A new pack version comes with an app release that names it (the pin), so the public CI tests that pair before any PC
  sees it (section 3, CI). That release is small (pin + CHANGELOG line); the big download happens only when the pack
  changed.
- The same `bpy.app.online_access` gate and User-Agent as the update check; one new row in COMPANY-USE's network table.

**1.4 Companies.**
- **Approved version** (COMPANY-USE "Holding one approved version"): IT adds `assets.json` + `FresingAssets-<v>.zip` to
  the folder with `index.json`, `changelog.json` and the extension zip → every PC offers exactly that pack.
- **Or one shared pack:** IT unpacks it once on a share; the `.frsetup` points at it:
  `"assets": {"folder": "\\\\SERVER\\share\\Fresing Assets", "use": true, "update": false}` (later `"licence": {…}`).
  PCs read it in place – read-only is fine, projects take copies. Older apps ignore an unknown top-level key at set-up
  format 1 (`core/locations.py` 248–253, checked).
- **Never the pack inside a `.frsetup`:** 200 MB per file / 1 GB per set-up, an unknown content folder is refused by every
  older app (218–221), and set-ups are copied and unpacked on the main thread (10 s timer).
- **A company that does not buy:** installer option `-NoAssets` and the Settings switch (section 3) – the app is then
  exactly today's.

**1.5 A broken or missing pack** (0283's rules; all of it in `registry_proto.py --selftest`, 19 checks pass):
- no `pack.json` → no pack, nothing said (Settings > Assets: "Not installed");
- damaged / not ours / newer format / app outside `app_min`–`app_max` → no pack + **one** plain note in Settings >
  Assets, the reason in the console, never a crash;
- a bad row (id, a path outside the pack) or a newer contract → that id uses the code look; one note counts them;
- an asset file missing or unreadable when it is brought → what was appended is removed again, the code look is used,
  one note per session – never a half-built material;
- `pack.json` is read once at start in a helper thread; sha256 of the files only after an install or update;
- **data only:** a pack holds no Python. `libraries.load` runs no scripts; the pack's CI refuses Text datablocks, Python
  drivers (only simple expressions, as every Fresing file), OSL Script nodes and handlers. (A demo kit is code – the
  pack must never become one.)

**1.6 The public download (owner 21:35).** The finished pack is a file attached to a GitHub release – not Git LFS
(LFS downloads, also by CI and forks, count against the owner's 10 GB a month) – under the Fresing Assets Licence, with
the licence file inside the pack. Only the working files stay private (section 6).
- **Where:** a release of the public repository `smholte/CAD-render-animation` per pack version: tag `assets-<version>`
  (`assets-1.0.0`), title "Fresing assets pack 1.0.0 – data for the app, not an app version", **always a pre-release**.
  GitHub never makes a pre-release "latest", and only "latest" and `v` tags are read by the apps' update check
  (`core/updates.py:30`, `releases/latest/download/index.json`), the landing page (`tools/build_site.py:102–111`) and
  the precheck (`ci_precheck.py:539–541`); the rehearsal clean-up deletes only its own tag (`tests.yml:773–788`) –
  all checked. A precheck rule (P5) keeps it so: every release whose tag does not start with `v` is a pre-release.
  (The separate download-only repository of the first draft is dropped: with no private CI, the app repository's own
  workflows can write its releases with their own token, and all pack tests live there anyway.)
- **Files on the release:** `FresingAssets-<version>.zip` (the pack, `LICENSE-ASSETS.txt` inside), `LICENSE-ASSETS.txt`
  (readable before the download – "communicated before they download", 0343's Lampel quote) and `assets.json`. The
  release text puts the licence in plain words above the files: free for private use, education and non-profits;
  companies need a licence.
- **Version ↔ release:** one pack version = one release = one zip; a file is never replaced (a fix is `1.0.1`); a
  version whose tests failed stays an unpinned pre-release that no app offers, or is deleted by hand.
- **Size:** each release file < 2 GiB, up to 1,000 files per release, no limit on total size or downloads (GitHub's
  "About releases", [search]); pack 1.0 ≤ 300 MB (page choice 11).
- **The pin:** `installer/assets_pin.json` = version, tag, file, url, sha256, bytes, licence id; every app release copies
  it as `assets.json` (1.3). A pack version reaches PCs only through an app release whose pin passed the public CI.
- **How the installer fetches it:** the pinned url, size and sha256 checked, as Blender's zip
  (`Install-FresingRender.ps1`); offline and in CI: the zip next to `Install.bat`.
- **How CI fetches it:** a step reads the pin and restores `actions/cache` with the key `assets-<version>-<sha256>`; on
  a miss `curl` from the release (public, no token) + `sha256sum -c` – exactly Blender's steps (`tests.yml:317–331`,
  `492–518`). A cache made on `main` is seen by every branch (CLAUDE.md §8); GitHub keeps 10 GB of cache per
  repository and drops an entry unused for 7 days (GitHub's "Dependency caching reference", [search]) – Blender for
  Linux and Windows (~0.8 GB), the venvs and a 0.3 GB pack fit.
- **Who uploads – zero private minutes:** the worker, from its Claude Code session, by the REST API: create the
  pre-release, send the zip to the release's upload address (what `tools/make_test_stress.py --publish` does in its
  workflow). This session's GitHub access has push and admin rights on the public repository (read 25 Nov), but
  whether a session's proxy lets it create a release and send ~300 MB is **not tried** – it would publish a release.
  P5 tries it once with a 1 MB test file and the owner's OK. If it is refused: a by-hand public workflow
  (`assets-release.yml`, `workflow_dispatch` only, never on pull requests) clones the working files with a read-only
  deploy key (one secret; the owner adds it once with click-by-click steps), builds and checks the pack with the cached
  Blender and uploads it with its own token – the working files never go into a log or an artifact (public logs). Last
  resort: the worker leaves a draft for the owner to publish.

**1.7 No private CI – compared (owner 21:35).**

| | Private CI (the brief's first plan) | ★ No private CI (owner 21:35) |
| --- | --- | --- |
| The owner's private minutes | ~10 min per private push or release run, from the Free plan's small monthly allowance shared with his other private repositories (2,000 min on GitHub's Actions billing page, "$12 of compute" on its newer plans page – the two differ, [search]) | **0** – standard runners are free for public repositories |
| Where the pack tests live | two places – private build checks and public app checks – two copies that can drift apart | **one** – the public repository; the worker runs the same checks in its session before it uploads |
| What is tested | the zip before it is public | the published zip, before any app release names it |
| A faulty zip | caught before publishing | stays an unpinned pre-release that nothing offers; fixed by a new patch version |
| Secrets, the owner's set-up | a token so the private CI can publish on the public repository (or the owner uploads) | none if a session can upload (tried once in P5); else one read-only key |
| What becomes public | the zip | the zip and its test logs – the zip is public by design; the working files and the records never |
| A worker's wait | push, then wait for the private run | the checks run in its session at once; the public CI confirms |

**Recommendation: ★ no private CI** (the owner's plan). Zero private minutes, one set of pack checks, and nothing becomes
public that is not public anyway. Its one open point – can a session create the release? – has a sure fallback.

### 2 · One asset registry

**2.1 Ids** = `<kind>:<today's code id>`; never changed, never reused (as `materials_lib.UIDS`):

| Kind | Today's ids (code) | A project keeps it as |
| --- | --- | --- |
| `material` | 87 ids, `UIDS` 1–87 (`core/materials_lib.py:308`) | the group's enum number + `mat_key` |
| `finish` | 25 ids, also material ids (`core/finishes.py:93`) | the material + `fin_*` settings |
| `light` | PRODUCT, WHITE, DARK, SUN, OVERCAST (`core/studio.py:220`) | `lighting` enum; pictures packed by name ("FR Light product studio" …) |
| `hdri` | none ship today (the user's Backgrounds folders) | a file path – not packed today |
| `environment` | COLOR, TRANSPARENT, SKY, HDRI, SEA, DECK, QUAY, FACTORY, CNC, ASSEMBLY, WAREHOUSE (`core/surroundings.py:32`) | `background` enum; "FR Surroundings" keys |
| `prop` | PERSON, CONTAINER, PALLET, BARRIER, IBC, GAS_RACK, TOOL_TROLLEY (`surroundings.py:220`) | `fr_prop` |
| `person` | outfits, poses, looks (`core/props_detail.py:35–53`); the rig, 17 bones | `Object.fresing_person` |
| `decal` | 9 stickers (`core/decal_art.py:343`) | `FRDecal` enums, by position |
| `cable_look` | 6 kinds (`blender/cable_looks.py`) | `FRCable.look`, by position |
| `crane` | 12 classes AT / CC / KB (`data/lifting/`) | `lifting.cranes[]`; the mesh is imported |
| `project` | tour sets, lessons crane / mill / weather | – (opened as a copy) |
| `weather` | 11 presets – **stays code**: the sea is one physics shared with vessel motion, Web 3D and the tests | `weather` enum |

**Every pack id has a code twin with the same id.** For materials it is a must: `g.material = <unknown id>` raises
(an enum; `logic.py:107, 228`, `rule_sets.py:370`, `states.py:574`), and rule sets do not check ids – so a look that only
the pack has first gets a `materials_lib` entry with a UID and a plain code version, in the app release that pins the
pack. Other kinds may name a `fallback` (a new HDRI → `light:OVERCAST`, as a missing photo falls back to Soft studio
today, `world.py:157` – but with a note instead of silently).

**2.2 How a system asks** – `core/assets_pack.py` + `core/assets_registry.py` (no Blender; `registry_proto.py` is their
shape) and `blender/assets.py`, in this order:
1. **The project already has it** (a datablock whose `fr_asset` id matches) → use that copy. Works on a PC without the
   pack, in the Client view (it allows light looks, saved scenes, the queue and render, `lock.py:56–87`) and in the
   queue's background Blender (it opens a copy and runs `world.apply` and the scheme rebuilds again).
2. The project's source is `pack`, the switch is on, the pack has the id and its contract fits → **bring** it: append,
   pack its pictures, stamp `fr_asset`, keep one per id + version (2.4).
3. Otherwise **today's code** builds it (a pack-only id → its code twin).

Answers come from memory (the pack's index read once at start). `world.apply` (rebuilds "FR World" on every call:
every look change, every still, every queue job), the colour / wear sliders (rebuild every group material on a change,
`props.py:84–98`) and the picker's draw must never touch the disk.

**2.3 The contract of a pack item** (Web 3D takes the first top-level BSDF, `web3d.py:191–195`; so do welds, coolant,
chips, the park's lights):
- **Material:** a ShaderNodeTree group "FRP <id>"; input `Colour` (linear – schemes recolour by rebuilding, so never a
  colour baked into a picture) + the numbers the look needs; outputs `Colour`, `Metallic`, `Roughness`, `Normal` and
  optional `Coat Normal`, `Tangent`, `Anisotropic`, `Alpha`. **No BSDF and no Output inside**, no Bevel / AO, object
  coordinates in metres (STEP parts have no UVs), pictures box- or tri-planar and seamless at 0.2 m (Web 3D tiles),
  Cycles and EEVEE. The spec's constants (specular, coat, IOR, transmission, sheen, emission) stay on the app's BSDF.
  `build_nodes` swaps only its base-look block (`materials.py` 441–486) for the group; wear / rust (508), Adjust (513),
  the BSDF (520), glass's EEVEE output, the stamps and the wraps (526–555) stay. (The proof's group gives a Shader for
  brevity; append / link behave the same for any node group.)
- **Finish:** per finish id a group with the `BUILDERS` contract: the `core.finishes.pattern` numbers + colour /
  roughness / metallic in; reads the FACE attributes `fr_fx_*` and the View Layer attribute `fr_pixel_angle` (default
  when < 1e-12); pattern periods divide 0.2 m; still writes `fr_finish` / `fr_finish_web` (its own far numbers).
- **Light picture / HDRI:** linear equirectangular EXR, Blender's mapping lon = −azimuth (`studio.py:103`), the key
  light's azimuth / elevation (light words, Turn), strength 1 = normal, the photo's camera height.
- **Prop:** one mesh with both levels (`fr_lod` 1 / 2), metres, lowest point z = 0, facing −y (`props_scale`).
  **Person:** only a figure on the rig contract (17 bones and parents, vertex groups, 6 shape keys, REST_HEIGHT 1.7835)
  – else the code person stays. **Environment:** modules the code layout places (halls, deck, quay are sized to the
  model); materials under the same names / `fr_env` keys, so weather's tables still apply.
- The app knows one contract number per kind (`CONTRACTS`); a row with a newer one is skipped (1.5).

**2.4 Append or link – the proof** (`tools/assets_pack_proto/`, all numbers in `results_25nov.md`). Real Blender 5.2.3
in the background on the 4-core web machine. A made-up pack (5 items: a procedural node group, a material with 3
pictures, a world with an HDRI, an environment collection with its own copy of the floor material, a pallet; 67.8 MB
with pictures at 1k + 2k + 4k) brought into a project that stands in for a Fresing project (the group material keeps
its own Output, the pack's group is its look, the group's own colour is set on the group node). "Client" = the project
file alone in another folder, the pack hidden. Picture: `tasks/0344_page/img/proof_without_pack.jpg`.

| Way | bring 5 items | project | client without the pack | "update looks" 1.0 → 1.1 | updated, on a client |
| --- | --- | --- | --- | --- | --- |
| ★ **append + pictures packed** | 41 ms | 12.7 MB | **complete**, same picture as with the pack | 57 ms; look changed (roughness 0.36 → 0.42), the group's colour kept | **complete** |
| append, pictures stay in the pack | 41 ms | 0.1 MB | 5 pictures missing – pink | 50 ms (the update packs them) | complete |
| link | 46 ms | 0.09 MB | 5 libraries missing – **black** | 28 ms (relocate + reload) | not tried (already black) |
| link + Blender 5 "pack linked data" | 34 ms | 0.1 MB | datablocks there, **8 pictures missing** – pink | 30 ms | – |
| … with the pictures packed inside the pack's files | 93 ms | 25.2 MB (shared pictures twice) | complete | **fails** to pack again: "Cannot pack absolute file" | **black** (5 libraries missing) |

Also: opening the appended project 54 ms (12.7 MB) vs 11 ms; saving 37 ms vs 7–19 ms. `reuse_local_id=True` stops a
second append of the **same file** making ".001" copies, but not two copies of one material from two pack files (the
environment brings its own floor material) – the app keeps one per id + version (the proof's `_dedupe_materials`).
Blender also makes a new picture datablock with every appended material that uses it; the dropped copies have no users
and are not saved, but P2 should map each picture file to one datablock at once (no packing work twice). `fr_asset` (id, pack, version,
contract) survived append, save, open and update every time – that is what "update looks" finds.

**Decision ★ append + pack the pictures.** It is the only way that is complete everywhere: a client's PC, plain
Blender, a backup opened from `Backups\` (a backup is `save_as_mainfile(copy=True, relative_remap=False)`,
`backups.py:269–273` – relative paths break there), the queue's copy, the Web 3D bake, a pack update or removal. It
also fits the app: the Client view's lock writes `fr_cv` on every object (`lock.py:50`), weather wraps every material in
place, vessel motion adds Child Of to deck objects, the builders stamp custom properties – linked data takes none of
these. It is the app's own way already: own Blender materials are appended as "FRM <name>", never linked ("a link would
break on a PC without the folder", `material_picker.py:14–15`). Cost: the pictures inside the project (section 5).

**2.5 What a project stores.**
- On every brought datablock: `fr_asset` = `{"id", "pack", "version", "contract", "sha"}`.
- On each group material: `fr_look_src` = `code` | `pack:1.2.0`, checked in `is_current` – without it, installing or
  removing the pack would change old projects group by group, because every colour / wear / scheme / saved scene /
  rule-set switch / queue scheme rebuilds through `is_current`.
- On the scene: `assets_source` (`""` = made before the pack → code; `pack`; `code`) and `assets_version`.
- No new enum numbers for existing kinds; the group's `material` and `mat_key` stay as they are.

### 3 · Per system – what it needs so it does not break

"Both ways" = a test with the made-up test pack **and** without any pack. CI accepts no "no pack" skip
(`ci_check_pccheck.py:23` allows only "no graphics card"), so every pack check makes the test pack itself.

| System | Today | With the pack (plug-in point) | Without the pack | Tests both ways | Lane · size · risk |
| --- | --- | --- | --- | --- | --- |
| **Import + paint rules** (0340 / 0287) | ids picked in code: `cad_materials.pick` (STEP subprocess, no package imports), `logic.ensure_group` → `rules.default_material_for_group` | nothing in the importer – it writes ids; 0340's popup look list and fold-out show the registry's pictures with a "Fresing" badge | same ids → code looks | a rule set / template naming a pack look on a PC without the pack → its code twin; `test_part_types*`, `test_rule_sets` unchanged | Import (after 0340) · small · low |
| **Material library + picker** (0273) | `materials_lib` + `build_nodes`; 102 pictures + `hashes.json`; `builtin:` / `preset:` / `own:` | `build_nodes` swaps its base-look block for the pack group; `fr_look_src` in `is_current`; the picker shows the pack's picture + "Fresing" badge; pack rows in `look_costs.json` | today's nodes | every id built both ways; the 0.2.195 project (`tests/data/old_project_0_2_195.blend`) opens unchanged; a pack project on a client; picker both ways | Looks · medium · medium (colour / wear rebuild hot path) |
| **Finishes + Adjust + rust** (0274 / 0314 / 0318) | `finishes.apply` → `BUILDERS` (inline nodes); FACE data; far fade; "FR adjust" after the look | `BUILDERS[kind]` → the pack group on its contract; Adjust and rust unchanged after it | code builders | `test_finishes*`, `test_look_adjust`, `test_rust_carbon*` both ways; tour stop `finishes` gives the same numbers | Looks · medium · medium |
| **CAD colours / RAL** | `ral.py` (215 colours), the colour kept as text | nothing – the pack look takes `Colour` | – | a RAL text gives the same linear colour into a pack look | – · none · low |
| **Decals** | stickers drawn by code; logos / stickers from Locations, packed when used | the pack as a read-only "Fresing" level of the Logos / Stickers lists (`locations.ORDER` already has `builtin: 0`, never filled); Fresing's own signs, not copies of CE / ISO artwork | code stickers | a decal from the pack → the project opens without it | Looks · small · low |
| **Light looks + world** | 5 looks; pictures drawn by NumPy once per project, packed by name (2048 float); `world.apply` rebuilds the world on every call; 360° photos = the user's paths, not packed | `look_image(kind)` / `studio_image()` bring the pack's `light:<KIND>` picture under the **same image name** – nothing else in `world.apply` changes; pack HDRIs listed under Backgrounds as "Fresing", brought + packed + stamped | code pictures by name | `test_studio_cameras` (names, packed) both ways; Web 3D environment; queue copy | Scene & Render · medium · medium |
| **Weather + sea + time** | code only (nodes, GN, drivers, `fr_wx_*`) | stays code; later at most cloud / foam pictures through the same channels | – | – | – · none · – |
| **Surroundings + props + people** | code-built, sized to the model; "FR_env <key>" with `MAT_VERSION`; props upgraded at load (`handlers.py:188`); rig contract | `surroundings.material(key)`, `props_scale.material(key)`, `people.material(key)` (same names + `fr_env` keys); environments = pack modules in the code layout; props through `make_mesh`'s contract; people only on the rig contract; pack id / version stamped apart – never via `fr_prop_ver` / `MAT_VERSION` | code | `test_surroundings`, `test_props_scale` (old project), `test_people*` both ways; halls' render time | Scene & Render · large · medium-high |
| **Cables / hoses / chains, marine, tool marks, welds** | code: `cable_looks.apply` (6 kinds; `fr_cable` attributes, named nodes), `marine_looks`, shared "FR tool marks", weld materials named by a hash with `LOOK_VERSION` | kind dispatch in `cable_looks.apply` / `marine_looks.apply`; `toolmarks.ensure_group` same interface; weld builders – keep attributes, named nodes, Output → Surface. The 3D page draws cables itself, so a pack cable look does not reach it | code | `test_cable*`, `test_marine*`, `test_toolmarks`, `test_weld*` both ways | Flex / Welds / Machining · small each · low |
| **Chips / coolant** | "FR chips <FAM>" (instancer attributes), coolant materials, a wet sheen on every top-level BSDF per frame | `chips._material(fam)`, `liquid_material(kind)`; pack part looks keep the top-level BSDF (the sheen needs it) | code | `test_chips*`, `test_coolant*` both ways | Machining · small · low |
| **Demo kits + demo project** | built per PC in a background Blender from code; a kit = zip + `kit.json` + Python | nothing – the demo's looks follow the registry; a background build finds the pack by `FRESING_ASSETS` / install folder; the pack is never a kit (no code) | code looks | `test_demo_project*` both ways (only pictures differ); `heavy.demo` time | Demo models · small · low (kit `uses` names unchanged – no private run needed) |
| **Lifting crane classes** | `data/lifting/` 12 classes, 11.4 MB (json + STEP + png; a test caps 11.5 MB) | later: more detailed cranes as a second built-in folder in the pack, same format, found by class id; the project imports the mesh | the shipped classes | `test_lifting*` both ways | Lifting · small · low |
| **Test tour + Learning hub + lessons** | built per PC from code + test STEPs; ~30 sets use the Product light picture; checks are numbers (joints, frames, 0 clashes) | sets follow the registry; new showcase / learning projects from the pack listed in the hub as "Fresing projects" (opened as a copy), hidden without the pack | today's sets unchanged | `test_tour.py` and `test_lessons*` both ways: the same numbers, three lesson modes equal | Learning · medium · low |
| **Material pictures** | `tools/material_pictures.py` (`--factory-startup`, no pack) + the hash test | the pack ships `pictures/<kind>.<id>.jpg` from its own pipeline on the same swatch; the hash test stays for code looks | code pictures | every pack item has a picture (pack CI); the picker both ways | Looks · small · low |
| **Web 3D export** | `Look` / `Baker` read the first top-level BSDF and bake each look into a 0.2 m tile at 512 / 1,024 / 2,048 px; the page holds a 256 px HDR light picture and, only with a 360° photo background, a tone-mapped JPEG 1,024 / 2,048 / 4,096 px wide by page quality (`core/web3d_env.QUALITY`) – never a source file (checked, 3.1) | **owner 21:41: never the pack's full-size photos or pictures** – for pack items (`fr_asset`) the background is capped at 2,048 px and the bake at 1,024 px per 0.2 m whatever the export asks (at Best / 2,048 the page would hold a full-width copy of a 4k pack photo and a full-size copy of a 2k pack picture); the light stays 256 px | as today | `test_web3d*` both ways + a new test: a pack project exported at Best / 2,048 holds no pack file and nothing above the caps | Web 3D · small · low |
| **Fresing Viewer** (MIT) | reads exports only (`.glb` + extras) | nothing: a Viewer file is the same `.glb`, so the caps above hold; no pack inside the Viewer; its code stays MIT and the page's player code dual GPL / MIT (0269) | – | – | Viewer · none |
| **PC check + Stress** | `@line`s; CI allows only "no graphics card" skips; Stress = 16 lines with peak memory | Full: `assets.pack` (makes the test pack, reads it, brings one item per kind, falls back when it is gone), `assets.update_looks`; Heavy: `heavy.assets` (pack looks on the Heavy machine: time, memory); Stress: `stress.assets` (the real pack on the owner's PC: graphics memory and render time with real pictures at Normal / Final); history kept apart with / without pack (picture flags) | lines use the test pack – never skipped | the lines themselves; `MIN_LINES_*` raised | PC check · medium · low |
| **Backups** (0246) | a full `.blend` copy | nothing – packed pictures travel; the 2 x free-space rule covers the bigger files; "Use the new looks" saves a backup first | – | a backup of a pack project opens complete from `Backups\` | – · none · low |
| **Render queue** | opens a copy (`relative_remap`), runs `world.apply` and scheme rebuilds, no settings | nothing (copies in the project); a job's scheme naming a look the project lacks → registry in the background, else code | code | a queued pack project renders without the pack | Motion · small · low |
| **Model update** (0052 / 0324) | keeps groups and materials | new groups get looks by the project's source | code for new groups | update a pack project on a PC without the pack | Import · small · low |
| **Templates, rule sets, schemes, saved scenes** | ids as text | nothing | code twins | – | – · none |
| **Own materials** (0273 "From a Blender material") | `material.blend` appended | a user may build on a pack group; the copy is then inside their `material.blend` – the licence text says it stays inside the company's own libraries and projects (L1, 3.1) | – | – | Repository & company use (text) |
| **Client view** | the lock allows light looks, saved scenes, queue, render | rebuilds use the project's copies first; Settings > Assets and "Use the new looks" stay off its allow list | – | real-app test: Client view on a pack project without the pack | Settings · small · low |
| **Workspaces** | – | the new functions' entries in their families | – | precheck | – · none |
| **Settings** (0271 / 0283) | `prefs.py` → `fresing_settings.json` automatically | a tab **Assets**: pack found (version, size, place, licence), switch **Use Fresing assets for new looks** (on when a pack is there), Check the pack, the pack update line; the `.frsetup` can set it (`apply_settings`) | "Not installed" | real-app `ui_test_settings` + a restart | Settings · small · low |
| **First-start set-up** (0276) – LAST | steps welcome / work / pc / company / hub / done; only on a new settings folder | a row in the step "company": **Private · Education · Non-profit · Company**; Company → price + Buy link once; nothing locked. Existing users: one card in What's new of the version that starts selling | – | `test_first_setup*` | Start & learn · small · low |
| **About + export windows** – LAST | `core/about.REQUIRED` = 4 app files; a missing one fails `app.licences` | the pack's licence gets its **own optional** finder (never in `REQUIRED`); lines "Fresing assets 1.2 – Fresing Assets Licence" + "Licensed to …" (licence file) + a button; **nudge** (said Company, no licence file): one grey line in About and at the bottom of each Make output window – never a popup, never blocking | the GPL lines only | `test_about` both ways | Repository & company use · small · low |
| **Installer + update + uninstall** | section 1 | 1.2 – 1.6: the installer fetches the pinned release download (size + sha256, like Blender), offline the zip next to `Install.bat`, `-NoAssets`; the in-app pack update; Windows code → an independent review | `-NoAssets` | Windows job A installs with the cached pack, job B with `-NoAssets`; an update of the pack; uninstall leaves nothing | Quality & delivery · large · medium-high |
| **CI** (owner 21:35: **no private CI**) | full / docs / reuse / lane runs, no pack | all in the public repository: (1) **without** a pack – everything as today; (2) with the **test pack** made by a tool at test time (no binary in the repository); (3) with the **real pack** from its release download (pin + sha256, `actions/cache`, as Blender's zip): a Linux job "Real pack" (pack.json, contracts, a code twin per id, sha256s, sizes, data only; every `.blend` opens and appends; a small render per kind – no pink), the real-app looks tests both ways, Windows A with the pack and B without; in every full run once a pin exists, in a lane run when the pin or the pack code changed, and by hand ("Check an assets pack": a new tag before the pin moves); the precheck's release rule (1.6). The private repository runs nothing | – | – | Quality & delivery · medium · low |
| **User guide + function list** | – | chapter "Fresing assets" (what, the switch, updates, old projects, Use the new looks, companies); entries `settings.assets`, `assets.update_looks`, `assets.update_pack` (later `help.licence`); `THIRD-PARTY-NOTICES.md` §2.3 + line 80; COMPANY-USE file and network tables | – | precheck, `test_user_guide` | Docs · small · low |
| **House import** | brings House Planner's own materials | nothing (only sky and weather are shared) | – | – | House · none |

Found by reading, not run (not about the pack – for the lead): `build_nodes` clears a material's nodes in place but
keeps its `fr_coolant_patch`, so `coolant.is_patched` stays true and the per-frame `_patch_new_materials` does not put
the wet sheen back – a wet group whose look is changed during a coolant shot may lose its sheen (`coolant.py` 311–318,
556–568).

**3.1 Outputs that carry files (owner 21:41).**
- **Licence draft – a sentence for point 4 of 0343's draft** (a lawyer may word it): "**Inside an output.** Assets that
  come inside something made with them – a 3D page or model file, a Fresing Viewer file, a project sent to someone – may
  be used only as part of that output, not taken out and used on their own." Goes into `LICENSE-ASSETS` with L1.
- **What each output carries:**

| Output | What of the pack is inside | Rule |
| --- | --- | --- |
| 3D page (`.html`), its `.glb`, a Fresing Viewer file (the same `.glb`) | pack looks baked into 0.2 m tiles (≤ 1,024 px for pack items); a pack photo as a tone-mapped JPEG background ≤ 2,048 px wide; the light as a 256 x 128 HDR | never a pack file, never a pack photo or picture at full size (checked by a test); the page's code keeps its own licence (dual GPL / MIT, 0269) |
| A project sent to a client (`.blend`) | its copies: pack node groups, pictures and HDRIs at 2k | allowed (0343 point 4): to open and render that project |
| Stills, videos, turntables | pixels only | the user's |
| House bake package, Toolbox hand-offs | light maps, renders | the user's output |
| Own materials built on a pack look | a copy of the pack group inside the user's `material.blend` | only inside the company's own libraries and projects (L1) |

- **Measured** (`tools/assets_pack_proto/web3d_measure.py` + `web3d_views.py`, results in `results_web3d_25nov.md`;
  Blender 5.2.3 as a module, the test crane, pages shot in headless Chromium at page level Best, 960 x 540; the same
  page shot twice differs by 0.0 – the noise floor). A made-up photo-like 360° picture (4,096 x 2,048 EXR, 20.1 MB):

| Background in the page | background picture | whole page | look cost vs 4,096 px – level view, sky / whole (of 255) |
| --- | --- | --- | --- |
| 4,096 px (Best today) | JPEG 905 KB | 2.65 MB | – |
| ★ 2,048 px (Balanced; the cap for pack photos) | JPEG 236 KB | 1.75 MB | 1.72 / 1.49 (PSNR 37.7 / 39.8 dB) – distant windows softer |
| 1,024 px (Phone) | JPEG 75 KB | 1.41 MB | 2.76 / 2.29 (33.3 / 35.7 dB) – buildings blurred |

  The light picture is 256 x 128 (131 KB) at Best and Balanced, 128 x 64 at Phone – far too small to light anything
  else. The pack's concrete (2k colour, roughness, relief; one picture per 0.2 m) on the base plate:

| Bake size per 0.2 m | its baked picture | `.glb` / whole page | export (all looks) | look cost vs 2,048, 0.8 m away – middle / whole |
| --- | --- | --- | --- | --- |
| 2,048 (a full-size copy of the 2k picture) | WebP 2,322 KB | 3.04 / 5.18 MB | 43.9 s | – |
| ★ 1,024 (the app's default; the cap for pack looks) | JPEG 491 KB | 0.81 / 2.20 MB | 9.7 s | 0.56 / 0.47 (PSNR 49.8 / 50.7 dB) – no difference seen |
| 512 | JPEG 114 KB | 0.34 / 1.63 MB | 2.9 s | 1.29 / 1.06 (43.6 / 44.6 dB) |

  At no size did a pack file go into the page (the first 4 KB of each original picture searched in the `.glb`).
  Pictures: `tasks/0344_page/img/web3d_background.jpg`, `web3d_pictures.jpg`. The made-up photo has sharper detail than
  most real ones, so real look costs are likely smaller.

### 4 · Old projects

- **Rule: nothing changes in a project until the user chooses** (as 0340). Projects saved before the pack have no
  `assets_source` → treated as `code`; `is_current` compares the material's `fr_look_src` with the project's source, so
  neither installing, updating nor removing the pack rebuilds anything. The pack never rides on `LOOK_VERSION`,
  `MAT_VERSION`, `fr_prop_ver` or the tool-mark / weld version stamps (they rebuild at load or at the next use).
- **Use the new Fresing looks** (Fresing menu, Settings > Assets, a one-line hint in 3 Looks when a project with code
  looks is open and a pack is there): two small Draft pictures from the active camera – now / with the new looks – and
  the list of what changes (groups, world, environment, props); **OK** saves a backup first (0246's call), makes the
  change as one undo step and keeps every group's own colour, wear, rust, Adjust and finish settings (proof: the group
  node's colour stayed (0.9, 0.55, 0.05) through the update); **Cancel** changes nothing. The same action brings a newer
  pack version into a pack project ("3 looks have a newer version"). Not in the Client view.
- Models already imported keep their materials: the action is per project and explicit; new groups follow the
  project's source.
- **A finding about today's code looks:** they already change old projects without asking, three ways – a
  `LOOK_VERSION` raise rebuilds every group when the project opens (`handlers._on_load` → `logic.upgrade_looks`); a
  surroundings `MAT_VERSION` raise rebuilds them at the next `world.apply`; props are upgraded at load
  (`handlers.py:188`); besides, any change in the code reaches a group at its next rebuild. That is GPL code behaviour
  and outside the pack; whether code looks should also wait for the user is a separate owner choice (page question 6).

### 5 · Speed and size budget

**Today:** installer 76.2 MB, extension zip 69.7 MB (v0.2.257, read from the release by a helper), `data/` 51 MB.
Blender (~400 MB) is downloaded by the installer.

**Measured** (proof `memory` step: Cycles on the processor, 960 x 540, 8 samples, a plane filled by one material with
colour + roughness + normal pictures; made-up pictures, so file sizes are upper values – the 4k normal map alone
37 MB):

| Pictures | as files | files + `.tx` | packed in the project | `.tx` on disk | project |
| --- | --- | --- | --- | --- | --- |
| 1k | 30 MB, 1.9 s | 25 MB, 2.1 s | 30 MB, 1.9 s | 5.8 MB | 3.2 MB packed |
| 2k | 66 MB, 1.9 s | 43 MB, 2.3 s | 66 MB, 1.7 s | 22.6 MB | 12.6 MB packed |
| 4k | 210 MB, 2.3 s | 43 MB, 2.4 s | 210 MB, 2.3 s – `generate_texture_cache` makes **no** `.tx` for packed pictures | 89.3 MB | 49.9 MB packed |

With `.tx` files Cycles loads only the detail the picture needs, so the 43 MB holds for this 960 x 540 close-up; a
larger render loads finer levels (up to the "as files" number). A `.tx` file is 1.8–7.6 x its source (a 2k JPEG
0.49 MB → 3.7 MB). Cycles' memory for pictures grows with the
**distinct** pictures, not with the parts (the stress model's 11,228 parts share their group materials).

**Budget (proposal, each set measured against it on its pick page):**
- **In projects:** pictures packed at **Normal = 2k** (Draft may use 1k through Cycles' own *Viewport Texture Limit* for
  the Live preview); a typical project with one HDRI and one environment (3 picture sets) grows by ≤ ~30 MB. The app
  shows the project's size with its packed pictures.
- **Final 4k** (a later, measured option): at Final quality and with the pack on the PC, the render reads the pack's 4k
  files + `.tx` (made once into the user's texture-cache folder) instead of the packed 2k – 4k detail at the memory of
  2k; without the pack Final uses the packed 2k. Only if 2k looks soft on the owner's Final renders.
- **The pack in the installer:** pack 1.0 ≤ **300 MB** (2k pictures; 4k only for the HDRIs) – the install then
  downloads ~780 MB with Blender (~400 MB) instead of ~480 MB; a per-set budget in `pack.json`, checked by the pack's CI.
- **Memory:** 10 textured looks at 2k ≈ +0.7 GB in Cycles (estimate from the table, linear in distinct sets). On the
  stress model the CPU render line peaked at 6.8 GB (0315); the demo ("Vessel in a wind park") uses the same group
  materials, sea and surroundings, so it adds the same per distinct look. Graphics memory and render time with real
  pictures: measured by `stress.assets` and `heavy.assets` on the owner's RTX 3090 (24 GB) and the tester's RX 6700 XT
  (12 GB) before a set with pictures ships. EEVEE / Material Preview have no texture cache: all pictures at full size.
- **Time:** bringing the 5 small items took 34–46 ms (≈ 8 ms each + reading pictures); a 40-group import with a world
  and an environment ≈ +0.5 s (estimate). Opening: +~40 ms per 12 MB of packed pictures here.
- **Render time:** every pack look is timed against its code twin (0314's look-cost way: Cycles CPU, the swatch);
  **> 1.3 x → it gets the "slower" clock and ships only with the owner's OK on its pick page**. Nothing gets slower than
  today unless he accepted it.
- **Web 3D pages:** pack items capped at half their full size – the page measured 1.75 MB instead of 2.65 MB (background)
  and 2.20 MB instead of 5.18 MB (pictures) at a look cost of 1.7 and 0.6 of 255 (3.1).
- **Nothing heavier by default:** the switch decides for new projects; old projects stay as they are (section 4).

### 6 · Making the assets

**Private repository `smholte/fresing-assets-src` – working files only, no CI (owner 21:35)** (the owner creates it
empty; rules like `fresing-render-vessel`: private, workers only with "Private assets: yes" in the task header, nothing of
it copied into the public repository; **no `.github/workflows/` at all** – zero of the owner's private minutes):

```
CLAUDE.md, README.md        the rules: no workflows, nothing copied to the public repository, how a pack is built
sets/<set>/                 one folder per set (paints-1, metals-1, finishes-1, studio-hdri-1, floors-1, workshop-1 …)
   SET.md                   what it holds (ids), status: draft / on its pick page / approved / shipped in <version>
   OWNERSHIP.md             the owner's record (below)
   make.py + params.json    the set's maker and the numbers the owner chose – a rebuild gives the same files
   sources/                 source .blend scenes, full-size pictures, the owner's photos (never in the pack)
   pick/                    the pick page as it was shown (index.html + pictures)
tools/  build_pack.py · render_swatches.py · hdri_merge.py · photo_to_tile.py · make_tx.py
```

The makers stay private – they are the recipe; publishing them would publish the looks as GPL code. The pack checks
(`tools/assets_check.py`) live in the **public** repository (P5), so the worker and the public CI run the same ones.
GitHub refuses files over 100 MiB and advises repositories under a few GB: photos and pictures go in at a working size;
big sets of raw bracketed photos stay on the owner's PC and only their merged result goes in (no Git LFS).

**Per kind:**

| Kind | How workers build it | The owner's part |
| --- | --- | --- |
| Node materials (paints, metals, plastics, rubber, glass) | a maker writes each node group on the contract (2.3); 2–3 candidates per look | picks, sets gloss / grain / flake on the page |
| Finishes | the same, on the finish contract (FACE data, far fade) | picks per finish |
| Pictures from his photos (concrete, epoxy floor, wood, steel plate, rubber mat, fabric) | photo → seamless tile, colour levelled, roughness + normal estimated, 1k / 2k / 4k | shoots by a one-page guide (shade or overcast, straight on, 1–2 m², a grey card); picks |
| Procedural pictures | baked from node set-ups when a picture renders faster than the nodes (measured) | – |
| HDRIs | his Insta360's HDR / bracketed photos → merged linear EXR, horizon levelled, tripod removed, white balance, sun / light strength measured, 1k / 2k / 4k + `.tx`, a preview | shoots the places (studio corner, workshop, yard, harbour, overcast field); picks |
| Environments | makers in the style of `core/surroundings.py`, as modules for the code layout | picks layouts and looks |
| Props, people | makers like `props_detail` at real size; people on the rig contract (0303's picks first) | picks |
| Showcase / learning projects | built by the app itself (as the site kit) from the pack's items | picks the models and shots |

**The pick page per set** (as 0270 / 0343 / this one): today's look and 2–3 candidates side by side on the same three
public test models (crane, mill, finishes) and the 0270 swatch, same light and camera; render time and memory next to
each; ★ recommended first; adjust fields where useful; a Copy line back to the lead. The worker applies his picks,
renders the final, he looks once more and says OK.

**`OWNERSHIP.md`** (per set, short): date; set id and pack version; the pick page; what he chose and what he changed
(with the numbers); what he turned down; his photos used (file names, date, kind of place – no addresses, no people);
the worker tasks and tools; "Approved by Sebastian, <date>". Why: copyright needs a human's own creative choices
(0343's risk note: assets made mostly by an AI may be weakly protected) – the record shows his choices; his own
photographs are clearly his. Fresing may also turn its own GPL looks into pack files (it holds every right in its code –
no outside code, `CONTRIBUTING.md`; the released versions stay GPL), but the plan **rebuilds** each look with his picks
rather than exporting today's.

**Quality bar:** clearly better than today's code look on the pick page (his judgement), and: no pink or black in any
test render; Draft / Normal / Final work; the Web 3D bake works; render time ≤ 1.3 x its code twin unless he accepts
more; size within the set's budget; the pack checks pass (data only, contracts, sha256, pictures present).

**Building and releasing a pack version – no private CI** (owner 21:35):
1. A worker task ("Private assets: yes", both repositories attached) builds every approved set in its Claude Code session
   with Blender 5.2.3 on the web machine → `Fresing Assets/` + `pack.json` + `FresingAssets-<v>.zip`.
2. In the same session it runs the public checks against that zip (`tools/assets_check.py` and the with-pack tests of
   the public checkout beside it, as the vessel kit uses `FRESING_PUBLIC`): format, sha256, contracts, every `.blend`
   opens in Blender 5.2.3 in the background, data only, picture sizes and budgets, a code twin in the app for every id,
   a small render per kind.
3. It uploads the zip as the pre-release `assets-<v>` (1.6 – by the session, else the by-hand public workflow).
4. It opens a branch of the public repository that moves the pin to `<v>` (with the code twins of new ids, the
   CHANGELOG line). That branch's run is a full run (`installer/` changed): the public CI downloads the release zip
   (then cached), runs the real-pack job, the looks tests both ways and the Windows install with the pack.
5. Green → merged → the app release carries `assets.json`; PCs are offered the pack. Red → fix, `<v>` patch + 1, step 1
   again; the faulty pre-release is never pinned.

### 7 · Order of tasks

Never broken in between: until a set is approved and pinned, every task adds only things that are invisible without a
pack, and the public CI keeps running without one. New lane **Assets** (new files `core/assets_pack.py`,
`core/assets_registry.py`, `blender/assets.py`, `ops_assets.py`, `ui_assets.py`, `tools/make_test_assets_pack.py`,
`pccheck/assets_test_pack.py`, their tests; additive: `prefs.py`, `props.py`, `handlers.py`).

| # | Task | Lane | Model · effort | Size | Waits for |
| --- | --- | --- | --- | --- | --- |
| P0 | Owner: picks on `tasks/0344_page/`; creates the empty private repository `fresing-assets-src` (working files only, no workflows) when the first set starts; says OK to P5's one-time upload test | owner | – | – | – |
| P1 | **Pack format, registry, test pack** (invisible): `core/assets_pack.py` (pack.json, the rules of 1.5), `core/assets_registry.py` (today's ids per kind, resolve, `problems()`), the made-up CC0 test pack made by a tool at test time (`tools/make_test_assets_pack.py`; the same maker shipped as `pccheck/assets_test_pack.py`), pure tests | Assets | Opus · High | medium | P0 |
| P2 | **Bring, keep, update** (invisible): `blender/assets.py` (append + pack pictures + `fr_asset` + one per id / version / picture file + names), the project fields, `fr_look_src` helpers, the update engine without UI, background Blenders; tests both ways (old 0.2.195 project, client open, queue copy, backup open, undo) | Assets | Opus · High | large | P1 |
| P3 | **Settings > Assets + the switch**; PC-check lines `assets.pack`; function entries; guide chapter | Settings | Sonnet · Medium | small | P2 |
| P4 | **Where the pack lives:** installer (fetch the pinned release download like Blender, staging folder, `-NoAssets`, offline zip next to Install.bat), `installer/assets_pin.json` → `assets.json` on every app release (`build_release.py`, `release_tools.py`), the in-app pack update (own folder, swap at start), uninstall, `.frsetup` `assets` key, COMPANY-USE tables, Windows CI with the cached pack and with `-NoAssets`; **independent review** (Windows code) | Quality & delivery | Opus · High | large | P1 (app side after P3) |
| P5 | **Pack checks in the public repository – no private CI:** `tools/assets_check.py` (what the worker runs before an upload and CI after it), the "Real pack" Linux job on the cached release download (on once a pin exists), a by-hand workflow "Check an assets pack" (a tag before the pin moves), the precheck rule (a non-`v` release is a pre-release), real-app test `ui_test_assets.py` (lightest group); **the one-time upload test**: a session creates a 1 MB pre-release `assets-0.0.1-test` by the REST API and deletes it (owner's OK) – if refused, `assets-release.yml` (by hand, read-only deploy key, the owner's click-by-click steps); the private repository's CLAUDE.md / README and `build_pack.py` (no workflows) | Quality & delivery | Opus · Medium | medium | P1 |
| P6 | **Use the new Fresing looks** (before / after, list, backup, undo step; Fresing menu, Settings > Assets, 3 Looks hint) | Assets | Opus · Medium | medium | P2, P3 |
| P7 | **Looks plug-in:** `build_nodes` base-look swap, finishes `BUILDERS`, `is_current` stamp, the picker's pack pictures + badge, `look_costs`, Web 3D check; with the test pack | Looks | Opus · High | medium | P2 (and 0340 merged) |
| P8 | **Light + HDRI plug-in:** `look_image` / `studio_image` by name, Backgrounds level "Fresing", Web 3D environment | Scene & Render | Opus · Medium | medium | P2 |
| P9 | **Surroundings / props / people plug-in:** materials by key, modules in the code layout, `make_mesh` contract, rig contract | Scene & Render | Opus · High | large | P2 (people after 0303's picks) |
| P10 | **Learning + small looks plug-in:** hub "Fresing projects", tour / lessons both ways; cable / marine / tool marks / welds / chips / decals dispatch | Learning (+ Flex, Machining, Welds, Looks) | Sonnet · Medium | medium | P2 |
| P12 | **Outputs carry no full-size pack files (owner 21:41):** in the Web 3D export, a pack photo's background ≤ 2,048 px and pack looks baked ≤ 1,024 px per 0.2 m whatever the export asks (`web3d_env.sky_block`, the `Baker`'s size per look, by `fr_asset`); a test: a pack project exported at Best / 2,048 holds no pack file and nothing above the caps; the export window says so in one grey line when it lowered something; guide line | Web 3D | Sonnet · Medium | small | P2, P7 |
| S1 | **First set: paints & coatings** (gloss, satin, matte, powder coat, marine, hammertone, wrinkle, anti-skid) – no pictures, every model uses them, quick to judge; pick page → OK → the worker builds pack 1.0.0 in its session, runs the public checks, uploads the pre-release `assets-1.0.0`; the pin branch's full run tests the download → app release (first visible change: new projects only) | private repo + Looks | Opus · High | medium | P4, P5, P7 |
| S2… | One set per task, each with its pick page and the owner's OK: metals + fastener finishes · plastics, rubber, glass · finishes (25) · studio light + **his HDRIs** · floors + walls from **his photos** · environments (workshop, hall, quay, showroom) · props · people · cables, hoses, welds, marine, chips · decal art · showcase + learning projects · detailed crane classes | private repo (+ the plug-in lane when needed) | Opus · High first, Sonnet · Medium for later batches | medium each | S1, the matching plug-in task |
| P11 | (optional) **Final 4k from the pack folder** (`.tx`, render-time swap) – only if 2k looks soft in his Final renders; measured first | Scene & Render | Opus · High | medium | S5, Stress numbers |
| L1 | **Licence texts** (0343 P2: `LICENSE-ASSETS` with the "inside an output" sentence of 3.1, README, THIRD-PARTY, COMPANY-USE, own materials built on pack groups, Web 3D pages, the release text of each pack version) | Repository & company use | Sonnet · Medium | small | owner says "start selling" |
| L2 | **First-start question + nudge + licence file** ("Licensed to …" in About; the nudge line in About and the export windows; `.frsetup` `licence`) | Start & learn + Repository & company use | Opus · Medium | small | L1 |
| L3 | **Shop + landing page** (Paddle product, prices, Buy link, download page with the licence) | Site | Sonnet · Low | small | L1, owner's shop account |
| L4 | Owner: Benelux trademark (classes 9 + 42) before the first sale | owner | – | – | – |

P3 ∥ P4 ∥ P5 can run at the same time (different lanes); P7 ∥ P8 ∥ P9 ∥ P10 too (one task per lane), P12 after P7.
The first visible change for users is S1's pin; until then every PC runs today's looks. No task uses private minutes.

**Tested and measured** (4-core web machine, Intel Xeon 2.1 GHz, 16 GB, no graphics card, Linux; real Blender 5.2.3 in
the background; Cycles on the processor):
- The append / link proof (2.4) and the memory table (5): `run_proof.py` ran twice with the same results (the second
  run with a better camera and sky gives the numbers above); the extras (pictures inside the pack's files; packed + `.tx`)
  once per run. ~11 min a run. The made-up pack: 5 items, 67.8 MB, made in ~50 s.
- Blender 5.2.3 facts read from its own code / API: `libraries.load(link, pack, relative, set_fake, recursive,
  reuse_local_id, …)`; `ID.is_linked_packed`; `file.pack_libraries`; Cycles' texture cache (`render.use_texture_cache`
  on by default, `use_auto_generate_texture_cache` off, `render.generate_texture_cache`, `.tx` in `blender_tx\` beside the
  picture, `blender --command maketx`); Cycles' viewport / render texture limits.
- `registry_proto.py --selftest`: 19 / 19.
- The Web 3D measurement (3.1): `web3d_measure.py` (Blender 5.2.3 as a module, the app of this branch, the test crane,
  6 exports: 3 background sizes, 3 texture sizes; 2–44 s each) + `web3d_views.py` (the same pages shot from a level
  view and 0.8 m from the plate in headless Chromium, software GL, page level Best; the same page twice = 0.0
  difference); results in `results_web3d_25nov.md`.
- GitHub facts from GitHub's documentation through search excerpts, not read whole here ([search]): standard runners
  free for public repositories; the Free plan's private allowance (2,000 minutes vs "$12 of compute" – the pages
  differ); release files < 2 GiB each, no total or download limit, 1,000 files per release; Actions cache 10 GB per
  repository, entries unused for 7 days removed. This session's rights on the public repository (push, admin) read
  with `gh api`; creating a release from a session was **not** tried.
- No independent review of this study (findings only, nothing goes to `main`); the facts the decisions rest on were
  checked by hand in the code (listed under "What changed"). The build tasks with Windows code (P4) need one.
- Not measured: anything on a graphics card or on Windows; real photos and HDRIs (the made-up pictures are noisier –
  sizes are upper values); a real network download of a pack; EEVEE memory.

**Open points / follow-up tasks:**
- The owner's picks on `tasks/0344_page/` (Copy line to the lead); then P1 → … as in section 7.
- Today's code looks change old projects without asking (section 4) – the owner's choice 6 on the page.
- The coolant sheen point above (found by reading, not run) – for the lead.
- COMPANY-USE's network table line numbers are out of date (`check_now` is at `updates.py:125`, not 119; the PC check's
  `updates.check` at `checks.py:7033`, not 4261 – a helper's finding); a docs fix for the lead, unrelated to the pack.
- Whether a worker session may create a release and upload ~300 MB (1.6): tried once in P5 with the owner's OK; the
  fallback (a by-hand public workflow with one read-only deploy key) needs the owner's click-by-click set-up once.
- The repository name `fresing-assets-src` (private, working files only), the folder name `Fresing Assets`, the tag
  `assets-<version>` and the zip name are proposals; the owner creates the private repository when the first set starts.
  The download-only public repository of the first draft is dropped (1.6).
- The lead may want to tell the 0286 owner-picks follow-ups that "Fresing standard (CC0, public)" is replaced by this
  pack; 0286's Poly Haven / ambientCG / Blendkit layers stay as they were.
