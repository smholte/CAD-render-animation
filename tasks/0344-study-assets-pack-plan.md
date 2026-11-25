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

**What changed:** new files only – this report; the pick page `tasks/0344_page/` (`index.html`, one picture); the proof
`tools/assets_pack_proto/` (`make_test_pack.py`, `try_pack.py`, `run_proof.py`, `registry_proto.py`, `README.md`,
`results_25nov.md`). `TASKS.md` not touched (branch only – the lead sets 0344 to done). Three read-only helper agents
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
   Blender upgrade and **Update now** (which replaces only the extension folder); the uninstaller removes it. A small
   `assets.json` beside each release's `index.json` names the pack version that app version was tested with (works for
   IT's approved folder too); the app offers a new pack version with its size, the user clicks. The built pack is
   downloaded from a public download-only repository; its sources stay private.
7. **Making the assets:** a private source repository, one folder per set; a pick page per set with today's look next
   to 2–3 new candidates on the same test models; the owner's picks and changes kept in `OWNERSHIP.md`; workers build,
   the owner approves every set before it ships.
8. **Order:** six invisible tasks first (format + registry + test pack · bring / keep / update · Settings > Assets ·
   installer + update · CI both ways + the private repository · the update-looks action), then the plug-in points per
   system with a made-up test pack (still no visible change), then one asset set at a time (★ first: paints). Licence
   texts, the first-start question, the nudge lines and the shop last, when the owner says so.

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
  folder. Older apps ignore it (`pick_package` keeps only `fresing_render`).
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

**1.6 Where the public download lives.** ★ A public **download-only** repository `smholte/fresing-assets`: README,
`LICENSE-ASSETS.txt`, releases `assets-1.2.0` with the zip, no sources (0286 had planned this name for a CC0 library;
the owner's 0343 picks turn it into the paid-for-companies pack). GitHub releases: no total limit, < 2 GiB per file
(0286). The sources (working `.blend` files, the owner's photos, makers, pick pages, `OWNERSHIP.md`) live in a
**private** `smholte/fresing-assets-src` (section 6). **Not** on the app's own release page: a pack release there would
need a non-`v` tag (the precheck reads every `v` tag as an app version, `ci_precheck.py:539–541`) and must never become
"latest" (every app's update address is `releases/latest/download/index.json`, `core/updates.py:30`; the site reads the
newest release too), and every app release would upload it again. Draft releases cannot serve it (only people with
access see drafts).

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
| **Web 3D export** | `Look` / `Baker` read the first top-level BSDF; finishes as numbers or tiles | nothing, thanks to the contract; optionally `Look.__init__` reads web numbers from the pack (as `fr_finish_web`). The page is the user's output (0343 licence point 4) | code | `test_web3d*`: a pack material bakes, no pink, both ways | Web 3D · small · low |
| **Fresing Viewer** (MIT) | reads exports only (`.glb` + extras) | nothing; no pack inside the Viewer | – | – | Viewer · none |
| **PC check + Stress** | `@line`s; CI allows only "no graphics card" skips; Stress = 16 lines with peak memory | Full: `assets.pack` (makes the test pack, reads it, brings one item per kind, falls back when it is gone), `assets.update_looks`; Heavy: `heavy.assets` (pack looks on the Heavy machine: time, memory); Stress: `stress.assets` (the real pack on the owner's PC: graphics memory and render time with real pictures at Normal / Final); history kept apart with / without pack (picture flags) | lines use the test pack – never skipped | the lines themselves; `MIN_LINES_*` raised | PC check · medium · low |
| **Backups** (0246) | a full `.blend` copy | nothing – packed pictures travel; the 2 x free-space rule covers the bigger files; "Use the new looks" saves a backup first | – | a backup of a pack project opens complete from `Backups\` | – · none · low |
| **Render queue** | opens a copy (`relative_remap`), runs `world.apply` and scheme rebuilds, no settings | nothing (copies in the project); a job's scheme naming a look the project lacks → registry in the background, else code | code | a queued pack project renders without the pack | Motion · small · low |
| **Model update** (0052 / 0324) | keeps groups and materials | new groups get looks by the project's source | code for new groups | update a pack project on a PC without the pack | Import · small · low |
| **Templates, rule sets, schemes, saved scenes** | ids as text | nothing | code twins | – | – · none |
| **Own materials** (0273 "From a Blender material") | `material.blend` appended | a user may build on a pack group; the copy is then inside their `material.blend` – the licence text must say this is fine inside a company / project (L1) | – | – | Repository & company use (text) |
| **Client view** | the lock allows light looks, saved scenes, queue, render | rebuilds use the project's copies first; Settings > Assets and "Use the new looks" stay off its allow list | – | real-app test: Client view on a pack project without the pack | Settings · small · low |
| **Workspaces** | – | the new functions' entries in their families | – | precheck | – · none |
| **Settings** (0271 / 0283) | `prefs.py` → `fresing_settings.json` automatically | a tab **Assets**: pack found (version, size, place, licence), switch **Use Fresing assets for new looks** (on when a pack is there), Check the pack, the pack update line; the `.frsetup` can set it (`apply_settings`) | "Not installed" | real-app `ui_test_settings` + a restart | Settings · small · low |
| **First-start set-up** (0276) – LAST | steps welcome / work / pc / company / hub / done; only on a new settings folder | a row in the step "company": **Private · Education · Non-profit · Company**; Company → price + Buy link once; nothing locked. Existing users: one card in What's new of the version that starts selling | – | `test_first_setup*` | Start & learn · small · low |
| **About + export windows** – LAST | `core/about.REQUIRED` = 4 app files; a missing one fails `app.licences` | the pack's licence gets its **own optional** finder (never in `REQUIRED`); lines "Fresing assets 1.2 – Fresing Assets Licence" + "Licensed to …" (licence file) + a button; **nudge** (said Company, no licence file): one grey line in About and at the bottom of each Make output window – never a popup, never blocking | the GPL lines only | `test_about` both ways | Repository & company use · small · low |
| **Installer + update + uninstall** | section 1 | 1.2 – 1.4; Windows code → an independent review | `-NoAssets` | Windows job A / B: install with and without the pack, an update of the pack, uninstall leaves nothing | Quality & delivery · large · medium-high |
| **CI** | full / docs / reuse / lane runs, no pack | public: everything stays without a pack; the test pack is made by a tool at test time (no binary in the repository); a job **with the real pack** once one is pinned (downloads the pinned zip by sha256 into GitHub's cache, brings every id, renders tiny pictures – no pink, no Python); private repository: its own tiny workflow (section 6) | – | – | Quality & delivery · medium · low |
| **User guide + function list** | – | chapter "Fresing assets" (what, the switch, updates, old projects, Use the new looks, companies); entries `settings.assets`, `assets.update_looks`, `assets.update_pack` (later `help.licence`); `THIRD-PARTY-NOTICES.md` §2.3 + line 80; COMPANY-USE file and network tables | – | precheck, `test_user_guide` | Docs · small · low |
| **House import** | brings House Planner's own materials | nothing (only sky and weather are shared) | – | – | House · none |

Found by reading, not run (not about the pack – for the lead): `build_nodes` clears a material's nodes in place but
keeps its `fr_coolant_patch`, so `coolant.is_patched` stays true and the per-frame `_patch_new_materials` does not put
the wet sheen back – a wet group whose look is changed during a coolant shot may lose its sheen (`coolant.py` 311–318,
556–568).

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
- **Nothing heavier by default:** the switch decides for new projects; old projects stay as they are (section 4).

### 6 · Making the assets

**Private source repository `smholte/fresing-assets-src`** (the owner creates it empty; rules like
`fresing-render-vessel`: private, workers only with "Private assets: yes" in the task header, nothing of it copied into
the public repository; the owner's GitHub Free minutes: one Linux job, push to `main` + by hand, no schedule, ≤ ~10 min,
no artifacts, superseded runs cancelled):

```
CLAUDE.md, README.md
sets/<set>/                 one folder per set (paints-1, metals-1, finishes-1, studio-hdri-1, floors-1, workshop-1 …)
   SET.md                   what it holds (ids), status: draft / on its pick page / approved / shipped in <version>
   OWNERSHIP.md             the owner's record (below)
   make.py + params.json    the set's maker and the numbers the owner chose – a rebuild gives the same files
   sources/                 the owner's photos, scans, references (never in the pack)
   pick/                    the pick page as it was shown (index.html + pictures)
tools/  build_pack.py · check_pack.py · render_swatches.py · hdri_merge.py · photo_to_tile.py · make_tx.py
.github/workflows/pack.yml
```

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

**The pack's CI** (private): build every approved set → `Fresing Assets/` + `pack.json` + zip; check format, sha256,
contracts, every `.blend` opens in Blender 5.2.3 in the background, no Python, picture sizes and budgets, every pack id
has its code twin in the public app at the pinned tag (the public repository is cloned without a token, as the vessel
kit does); a release by hand: the zip to the public download repository (a worker task with both repositories
attached, or the owner uploads it – two clicks).

### 7 · Order of tasks

Never broken in between: until a set is approved and pinned, every task adds only things that are invisible without a
pack, and the public CI keeps running without one. New lane **Assets** (new files `core/assets_pack.py`,
`core/assets_registry.py`, `blender/assets.py`, `ops_assets.py`, `ui_assets.py`, `tools/make_test_assets_pack.py`,
`pccheck/assets_test_pack.py`, their tests; additive: `prefs.py`, `props.py`, `handlers.py`).

| # | Task | Lane | Model · effort | Size | Waits for |
| --- | --- | --- | --- | --- | --- |
| P0 | Owner: picks on `tasks/0344_page/`; creates the empty repositories `fresing-assets-src` (private) and `fresing-assets` (public, download only) when P5 starts | owner | – | – | – |
| P1 | **Pack format, registry, test pack** (invisible): `core/assets_pack.py` (pack.json, the rules of 1.5), `core/assets_registry.py` (today's ids per kind, resolve, `problems()`), the made-up CC0 test pack made by a tool at test time (`tools/make_test_assets_pack.py`; the same maker shipped as `pccheck/assets_test_pack.py`), pure tests | Assets | Opus · High | medium | P0 |
| P2 | **Bring, keep, update** (invisible): `blender/assets.py` (append + pack pictures + `fr_asset` + one per id / version / picture file + names), the project fields, `fr_look_src` helpers, the update engine without UI, background Blenders; tests both ways (old 0.2.195 project, client open, queue copy, backup open, undo) | Assets | Opus · High | large | P1 |
| P3 | **Settings > Assets + the switch**; PC-check lines `assets.pack`; function entries; guide chapter | Settings | Sonnet · Medium | small | P2 |
| P4 | **Where the pack lives:** installer (download the pinned pack like Blender, staging folder, `-NoAssets`, offline zip next to Install.bat), `assets.json` + pin (`installer/assets_pin.json`, `build_release.py`, `release_tools.py`), the in-app pack update (own folder, swap at start), uninstall, `.frsetup` `assets` key, COMPANY-USE tables, Windows CI with and without; **independent review** (Windows code) | Quality & delivery | Opus · High | large | P1 (app side after P3) |
| P5 | **CI both ways + private repository:** real-app test `ui_test_assets.py` (lightest group), the "with the real pack" job (on once a pack is pinned); the private repository's CLAUDE.md, README, set layout, `build_pack` / `check_pack`, workflow; the public download repository's README + licence placeholder | Quality & delivery | Opus · Medium | medium | P1 |
| P6 | **Use the new Fresing looks** (before / after, list, backup, undo step; Fresing menu, Settings > Assets, 3 Looks hint) | Assets | Opus · Medium | medium | P2, P3 |
| P7 | **Looks plug-in:** `build_nodes` base-look swap, finishes `BUILDERS`, `is_current` stamp, the picker's pack pictures + badge, `look_costs`, Web 3D check; with the test pack | Looks | Opus · High | medium | P2 (and 0340 merged) |
| P8 | **Light + HDRI plug-in:** `look_image` / `studio_image` by name, Backgrounds level "Fresing", Web 3D environment | Scene & Render | Opus · Medium | medium | P2 |
| P9 | **Surroundings / props / people plug-in:** materials by key, modules in the code layout, `make_mesh` contract, rig contract | Scene & Render | Opus · High | large | P2 (people after 0303's picks) |
| P10 | **Learning + small looks plug-in:** hub "Fresing projects", tour / lessons both ways; cable / marine / tool marks / welds / chips / decals dispatch | Learning (+ Flex, Machining, Welds, Looks) | Sonnet · Medium | medium | P2 |
| S1 | **First set: paints & coatings** (gloss, satin, matte, powder coat, marine, hammertone, wrinkle, anti-skid) – no pictures, every model uses them, quick to judge; pick page → OK → pack 1.0.0 → pin in an app release (first visible change: new projects only) | private repo + Looks | Opus · High | medium | P4, P5, P7 |
| S2… | One set per task, each with its pick page and the owner's OK: metals + fastener finishes · plastics, rubber, glass · finishes (25) · studio light + **his HDRIs** · floors + walls from **his photos** · environments (workshop, hall, quay, showroom) · props · people · cables, hoses, welds, marine, chips · decal art · showcase + learning projects · detailed crane classes | private repo (+ the plug-in lane when needed) | Opus · High first, Sonnet · Medium for later batches | medium each | S1, the matching plug-in task |
| P11 | (optional) **Final 4k from the pack folder** (`.tx`, render-time swap) – only if 2k looks soft in his Final renders; measured first | Scene & Render | Opus · High | medium | S5, Stress numbers |
| L1 | **Licence texts** (0343 P2: `LICENSE-ASSETS`, README, THIRD-PARTY, COMPANY-USE, own materials built on pack groups, Web 3D pages) | Repository & company use | Sonnet · Medium | small | owner says "start selling" |
| L2 | **First-start question + nudge + licence file** ("Licensed to …" in About; the nudge line in About and the export windows; `.frsetup` `licence`) | Start & learn + Repository & company use | Opus · Medium | small | L1 |
| L3 | **Shop + landing page** (Paddle product, prices, Buy link, download page with the licence) | Site | Sonnet · Low | small | L1, owner's shop account |
| L4 | Owner: Benelux trademark (classes 9 + 42) before the first sale | owner | – | – | – |

P3 ∥ P4 ∥ P5 can run at the same time (different lanes); P7 ∥ P8 ∥ P9 ∥ P10 too (one task per lane). The first
visible change for users is S1's pin; until then every PC runs today's looks.

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
- The repository names (`fresing-assets-src` private, `fresing-assets` public download-only), the folder name
  `Fresing Assets` and the zip name are proposals; the owner creates the repositories when P5 starts.
- The lead may want to tell the 0286 owner-picks follow-ups that "Fresing standard (CC0, public)" is replaced by this
  pack; 0286's Poly Haven / ambientCG / Blendkit layers stay as they were.
