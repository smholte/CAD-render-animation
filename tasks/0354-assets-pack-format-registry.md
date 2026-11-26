# 0354 – Assets pack P1: pack format, registry and test pack (invisible)

**Who:** worker · **Status:** done · **Branch:** `task/0354-assets-pack-format-registry`
**Started by:** lead, 25 Nov 2026 23:3x (0344's P1; owner's picks 23:17) · **Model:** Opus · effort High · Claude Code
on the web, environment "CAD-render-animation"
**Area:** new **Assets** lane – new files only: `fresing_render/core/assets_pack.py`, `fresing_render/core/assets_registry.py`,
`fresing_render/pccheck/assets_test_pack.py` (the test-pack maker, shipped so the PC check can make it on a user's PC
later), `tools/make_test_assets_pack.py` (a thin command-line wrapper around it), their tests, CHANGELOG + version files.
**Not:** any existing app file – nothing calls the new modules yet (that is 0355); `pccheck/checks.py` (0346 adds lines
now; the PC-check line comes with 0357); `installer/`, `.github/` (0356, 0358); the looks themselves.

## Goal

The invisible base of the Fresing assets pack: the app can find and read a pack folder (`pack.json`), check it without
ever crashing, and answer "pack item or today's built-in look?" for any asset id – and one maker writes a small made-up
test pack at test time, so every later task can test with and without a pack. **Nothing changes for users.**

## Background (read first – only the parts named)

- `tasks/0344-study-assets-pack-plan.md`: **"Owner's picks"** (top – they win where the report differs), report **"In
  short"**, **1.1** (zip and folder layout, `pack.json` fields), **1.2** (where the app looks: `FRESING_ASSETS`, a
  company folder, the install folder; background Blenders), **1.5** (a broken or missing pack), **2.1** (ids =
  `<kind>:<today's code id>`, every pack id has a code twin), **2.2** (how a system asks, in which order; nothing in the
  hot paths touches the disk), **2.3** (the contract per kind), **2.5** (what a project stores – names only; storing is
  0355), **5** (qualities and budget).
- The proof on branch `task/0344-study-assets-pack-plan`, folder `tools/assets_pack_proto/` (`git fetch origin
  task/0344-study-assets-pack-plan`, then `git show origin/task/0344-study-assets-pack-plan:tools/assets_pack_proto/<file>`):
  `registry_proto.py` is the shape of the two core modules (19 self-checks), `make_test_pack.py` the shape of the maker,
  `README.md` how they ran. Study code – take what fits, don't copy blindly.
- Patterns to follow: the demo kits' outside folder found by an environment variable (`core/demo_kits.py`,
  `FRESING_DEMO_KITS`); the settings file's "ignore, one line, never a crash" rules (`core/settings_file.py`, 0283).
- CLAUDE.md section 6, "Old projects – the baseline" and the assets-pack rules: this task is part of the groundwork the
  baseline waits for.

## What to do

1. **`core/assets_pack.py`** (plain Python, no `bpy`): read and check `pack.json` as in 1.1 / 1.5 – format and format
   version, the app window `app_min`–`app_max`, one contract number per kind (`CONTRACTS`), ids (`<kind>:<id>`; a file
   path outside the pack folder is refused), `qualities` (draft 1k · normal 2k · final 4k – pick 2), per-set `budget_mb`
   and per-asset `cost` (render time against its code twin – pick 10: above 1.3 × only with an `approved_slower` mark
   from the owner's pick page), the pack's total size (pick 11: ~300 MB for 1.0 – a warning number, not a hard stop).
   **Never raises:** no `pack.json` → no pack, nothing said; damaged / not ours / newer format / app outside the window →
   no pack + **one** plain note (the technical reason to the console); a bad row or a newer contract → that id uses its
   code look, one note counts them. A `verify()` that checks every listed file's size and sha256 – only called after an
   install or a pack update (0356 / 0358 call it), never at every start. **Where to look** (1.2): `FRESING_ASSETS` → a
   folder the caller passes in (the company set-up's shared pack – its `.frsetup` part comes with 0358) →
   `<install folder>\Fresing Assets`. It must work in a background Blender too (queue, tour / demo builds, PC check),
   which never reads the settings file.
2. **`core/assets_registry.py`** (plain Python): the kinds and today's code ids per kind (2.1's table) – **read them from
   the code modules where they live** (`materials_lib.UIDS`, `finishes`, `studio`, `surroundings`, …) so a new code
   look is never missed; `weather` stays code. `resolve(...)` answers pack item or code in 2.2's order (the project's
   own copy first is the Blender side's job in 0355 – give it what it needs to ask); a pack-only id must name a code
   twin or a `fallback`, else it is refused with a note; `problems()` for Settings and the PC check later. Answers come
   from memory – the pack's index is read once.
3. **The test-pack maker** – one function in `pccheck/assets_test_pack.py`, called by `tools/make_test_assets_pack.py`
   and by the tests (no second copy): writes a small made-up CC0 pack into a given folder **at test time** –
   `pack.json`, a placeholder `LICENSE-ASSETS.txt` that says it is a test pack, one item per kind that has a contract
   (at least: a material node group "FRP <id>" on 2.3's material contract – inputs `Colour` + numbers, outputs
   `Colour` / `Metallic` / `Roughness` / `Normal`, no BSDF and no Output inside; a finish group; a light picture; a
   prop; an environment module with its own floor material), small pictures at 1k and 2k made by code, the 256 px
   picker pictures, and a **second version `1.1.0`** with one changed look and one changed picture (0355's update tests
   need it). **No binary in the repository.** Data only – no Text datablocks, no Python drivers, no scripts, no handlers
   (1.5). Quick: aim under 30 s; say the time and size in the report. It needs Blender to write the `.blend` files – run
   it the way the other makers do (background Blender or bpy as a module, CLAUDE.md section 4).
4. **Tests:** plain tests for every rule of 1.5 (missing, damaged, not ours, newer format, outside the window, a bad
   row, a path outside the pack, a newer contract per kind, a size / sha256 mismatch in `verify()`), the ids (every code
   id of every kind resolves; a pack-only id without a twin or fallback is refused), the resolve order, read-once (a
   second answer opens no file). One real-Blender test: the maker writes a pack, `assets_pack` reads it with no notes,
   every `.blend` opens and holds what `pack.json` lists and nothing that can run code.
5. CHANGELOG: one plain line ("groundwork for the Fresing assets pack – no visible change"). No guide chapter, function
   entry, PC-check line or tour stop – nothing is visible yet; if the precheck asks for one, say so in the report
   instead of adding UI.

## Done when

- [ ] The two core modules, the maker and their tests are on `main`; the app looks and works exactly as before (no
      existing app file changed).
- [ ] Every rule of 0344 report 1.5 has a test; the full run on GitHub is green.
- [ ] Report: the modules' interfaces written out (functions, arguments, what they return, the notes' texts) – **0355,
      0356 and 0358 build on them**; the maker's time and size; anything in 0344's plan that turned out different.
- [ ] Report filled in, merged, released (section 7).

## Not in this task

Bringing anything into a project (0355); Settings > Assets and the switch (0357); the installer, the pin and pack
updates (0358); the pack checks, CI jobs and releases (0356); real looks; licence texts. Never the owner's files; never
his employer's name.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 25–26 Nov 2026 · 0.2.264

**What changed:** four new files, no existing app file touched (only the version lines and CHANGELOG):
`core/assets_pack.py`, `core/assets_registry.py`, `pccheck/assets_test_pack.py`, `tools/make_test_assets_pack.py`;
tests `tests/test_assets_pack.py` (103 plain tests) and `tests/test_assets_test_pack.py` (7, Blender as a module in a
child process). Nothing calls the modules yet – the app looks and works exactly as before.

**Interfaces (0355, 0356, 0358 build on these)**

`core/assets_pack.py` (no bpy; never raises):
- Constants: `FORMAT` "fresing-assets", `FORMAT_VERSION` 1, `PACK_JSON`, `FOLDER` "Fresing Assets", `ENV`
  "FRESING_ASSETS", `CONTRACTS` {kind: n} (material, finish, light, hdri, environment, prop, person = 1; decal,
  cable_look, crane, project, weather = 0 = "no pack items yet" – a plug-in task raises its kind to 1; weather stays
  0), `KINDS`, `BLEND_KINDS` {kind: allowed datablock collections}, `PICTURE_KINDS` {kind: file endings},
  `SOCKETS` (material / finish node-group contract: required inputs, outputs, optional outputs), `FORBIDDEN_NODES`
  (BSDFs, outputs, Bevel, AO, Script …), `FINISH_ATTRIBUTES`, `PIXEL_ATTRIBUTE`, `DEFAULT_QUALITIES`, `SLOWER` 1.3,
  `TOTAL_WARN_MB` 300.
- `find(app_version, folder="", binary_path="") -> Found` – looks in `places()`: `FRESING_ASSETS` **alone** when set;
  else `folder` (the company's shared pack) then `<install folder>/Fresing Assets` (install folder = Blender's
  parent holding `installed.txt`, the rule of `appicon.install_dir`; pass `bpy.app.binary_path` – works in
  background Blenders, reads no settings file). The **first place holding a pack.json** is used, damaged or not.
- `read(root, app_version) -> Found` – `Found(pack, state, note, detail, where)`; `state` none · ok · damaged ·
  not_ours · newer · app_old · app_new; `note` = ONE plain line ("" = nothing to say); `detail` = for the console.
- `Pack(root, id, title, version, app_min, app_max, licence, licence_id, qualities, sets, files, assets, left_out,
  contracts)`; `pack.path(rel)` → full path or "" when outside the folder (also through a link); `pack.bytes`.
- `Asset(id, kind, file, datablock, contract, fallback, picture, textures, set, since, changed, size_m, cost,
  approved_slower, sha256, bytes)`, `.code_id`.
- `verify(pack, progress=None) -> Verified(ok, problems, files, bytes)` – size + sha256 of every file in `files`;
  only after an install / update. `size_problems(pack)` – set above `budget_mb`, pack above 300 MB (warnings).
- `split_id`, `path_ok`, `inside`, `install_folder`, `places`, `rows_note(n)`, `describe(found)`.
- Notes (texts): `NOTE_DAMAGED` "The Fresing assets pack could not be read – it may be damaged. The app uses its
  built-in looks." · `NOTE_NOT_OURS` "The folder of the Fresing assets pack holds something else. …" · `NOTE_NEWER`
  "The Fresing assets pack is newer than this app – update Fresing Render to use it. Until then …" · `NOTE_APP_OLD`
  "The Fresing assets pack {version} needs Fresing Render {app_min} or newer – update the app. …" · `NOTE_APP_NEW`
  "… was made for Fresing Render up to {app_max} – get its newer version under Updates. …" · `NOTE_ROWS` "{n items}
  of the Fresing assets pack {is/are} left out (a newer app is needed, or the pack's list is damaged there). The app
  uses its built-in looks for them."

`core/assets_registry.py` (no bpy):
- `code_ids() -> {kind: frozenset}` read once from the code: `materials_lib.UIDS`, `finishes.FINISHES`,
  `studio.LOOKS`, `surroundings.KINDS` / `PROPS`, `props_detail.OUTFITS`, `decal_art.STICKER_KEYS`,
  `blender/cable_looks.KINDS`, `lifting_model.classes.CLASSES`, `weather.PRESETS`, projects = the tour's
  `@tour_set` ids (read with `ast`, no Blender) + `blender/lessons/` modules; hdri = none. `code_full_ids()`.
- `Registry.build(found, code=None)`: `.usable` {id: Asset}, `.refused` [(id, why)] (pack-only without a twin;
  material / finish always need a twin, `TWIN_ONLY`; others may name a `fallback` code id), `.note` (one line: rows
  left out + refused, or the pack-level note), `.items(kind)`, `.has(id)`, `.pack`, `.version`, `.problems()` (plain
  lines for Check the pack / PC check).
- `resolve(full_id, source="pack", use_pack=True) -> Choice(source, id, asset, pack_version)`: pack when the
  project's source is "pack", the switch is on and the item is usable; else the same code id; else the pack row's
  fallback; else `Choice("code", "")` (the caller's default). Step 1 (the project's own copy) is the Blender side's:
  `stamp(choice)` gives the `fr_asset` value {id, pack, version, contract, sha}.
- `current(app_version, folder="", binary_path="")` reads the pack ONCE (later calls answer from memory, tested: no
  file opened); `forget()` after a pack update or in tests.

`pccheck/assets_test_pack.py`: `make(folder, version="1.0.0", app_min="0.0.1", app_max="") -> {seconds, bytes,
files, folder}` – writes into `<folder>.making`, moves it in place when whole; replaces an earlier test pack, refuses
a folder with other files; leaves the caller's open file as it was (a caller's datablock with one of its names is set
aside and named back – tested). `VERSIONS` ("1.0.0", "1.1.0"). Items: `material:paint_satin` (procedural),
`material:cast_iron` (two pictures, 1k + 2k), `finish:knurl_diamond` (reads `fr_fx_o` + `fr_pixel_angle`),
`light:PRODUCT` (EXR 2048 x 1024), `hdri:test_hall` (pack-only, fallback `light:OVERCAST`, 1k + 2k), `prop:PALLET`
(`fr_lod` 1 / 2, z from 0), `environment:FACTORY` (bench + floor tile, own floor material `fr_env` "floor"); 256 px
picker pictures; placeholder `LICENSE-ASSETS.txt` (test pack, CC0). 1.1.0: paint_satin rougher (0.36 → 0.42), cast
iron's roughness picture new (`…_rough_v2.png`); every other file byte-equal between versions (tested).

**Tested and measured** (4-core web machine, Linux, Blender 5.2.3):
- Maker: 1.0.0 = 23 files, 3.48 MB, 3.6–4.2 s; 1.1.0 = 23 files, 3.57 MB, 4.7–5.6 s (bpy as a module). In the real
  Blender binary in the background (`blender -b --factory-startup --python tools/make_test_assets_pack.py -- …`):
  5.4 s inside, 23 s with Blender's start; read with no note, `verify` OK.
- Every rule of 0344 1.5 has a test: missing, damaged (bad JSON, NaN / Infinity, not UTF-8, > 4 MB, 22 bad heads), not
  ours, newer format, outside the window (both ends, pre-release), 30 kinds of bad row incl. paths outside the pack
  (`..`, absolute, drive, backslash, hidden, unlisted, a link out of the folder), a newer contract for each of the 12
  kinds, a look > 1.3 x without the owner's OK, `verify` size / sha256 / missing; ids (every code id of every kind
  resolves with and without a pack; pack-only without twin or fallback refused); the resolve order; read-once.
- Real-Blender test: both versions read with no notes, `verify` OK, every `.blend` holds the listed datablock and no
  Text, driver, script node or linked library; node groups on the 2.3 contract with no BSDF / Output; pictures
  relative, inside the pack and listed in the row's `textures`.
- Local: 110 tests of the two files in 10 s. GitHub: 4 full runs – the first green (run 45717235569, 31 min; the
  runner pool was shared), the second after merging main because 0327 took 0.2.261 meanwhile (renumbered to 0.2.262), the third because 0326 took 0.2.262 (renumbered to 0.2.263), the fourth because 0346 took 0.2.263 (renumbered to 0.2.264).

**Different from 0344's plan:**
- `pack.json` has a **`files` table** (every file of the pack: bytes + sha256) – the one list `verify` reads; asset rows
  only name paths (`file`, `picture`, `textures`), and `Asset.sha256` / `bytes` come from that table (1.1 had them per
  row; shared pictures would be listed twice).
- Kinds follow 2.1 (the proof's `world` / `texture` are gone); decal, cable_look, crane, project have contract 0 until
  their plug-in task; `person` code ids = the outfits (a pack person replaces an outfit's figure; poses stay code);
  project ids = tour sets + lessons.
- A look > 1.3 x its code twin without `approved_slower` is **left out by the app** too (not only a CI warning).
- An unknown id resolves to `Choice("code", "")` (the proof picked the first code id of the kind).
- The first place holding a pack.json wins even when it is damaged (its note is shown; no silent fall-through to the
  install folder's pack).
- The test pack has no person (the 17-bone rig contract belongs to 0362).

**Open points / follow-up tasks:**
- No independent review (plain Python, no Windows-only code – CLAUDE.md "saving usage"); 0355 has one.
- `code_ids()` imports `blender/cable_looks.py` (no bpy at its top) and parses `blender/tour.py` with `ast` – a test
  compares every kind with its module; if tour.py's decorator changes form, `tour_sets` needs it too.
- The PC-check line and Settings > Assets come with 0357; 0356's `assets_check.py` can reuse `SOCKETS`,
  `FORBIDDEN_NODES` and the inspection in `tests/test_assets_test_pack.py`.
