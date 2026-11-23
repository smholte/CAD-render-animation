# Blender 5.2.3 remote (online) asset libraries – research notes (23 Nov 2026)

**Sources.** This session's network blocks docs.blender.org, developer.blender.org, code.blender.org,
projects.blender.org, notes.blender.org and cdn.extensions.blender.org (proxy 403). So the **primary source is the real
Blender 5.2.3 Linux build** at `~/blender-5.2.3/blender-5.2.3-linux-x64`: its Python code (path abbreviations below), RNA
read in a background Blender, strings in the binary, and an end-to-end test (generate → serve on `http://127.0.0.1` →
download with Blender's own downloader). Web facts come from search-engine extracts of the official pages (marked
"(search extract)": not read directly) and from GitHub, which was readable.

Abbreviations: `RL/` = `5.2/scripts/modules/_bpy_internal/assets/remote_library/`, `PKG/` = `5.2/scripts/addons_core/bl_pkg/`.

## 0. What exists in 5.2
- 5.2 LTS release notes, "Online Asset Libraries": *"It is now possible to register remotely hosted asset libraries,
  browse them from within Blender, and download assets as needed. This requires Allow Internet Access to be enabled in
  the Preferences."* and *"The Essentials asset library that comes with Blender was extended with a number of online
  hosted assets. They will appear together with other essentials assets when Allow Internet Access is enabled"*
  (search extract) – https://developer.blender.org/docs/release_notes/5.2/assets/
- Developer docs: *"It must be possible to host an asset library using a static web server. No other server-side
  software should be necessary."* (search extract) – https://developer.blender.org/docs/features/asset_system/remote_asset_libraries/
- Blog: https://code.blender.org/2026/07/remote-asset-libraries/ (not readable here). Tracker: #134495 "Online Assets:
  Remote Asset Library", project "Remote Asset Libraries & Assets Usability" (projects.blender.org/blender/blender/projects/707).
- Not in 5.0/5.1: 5.0's "archive libraries" are packed data, a different feature (search extract).

## 1. Hosting: folder layout, files, generator
Spec = `RL/blender_asset_library_openapi.yaml` (OpenAPI `info.version: 1.0.0`), constants in `RL/listing_common.py`.

```
<library root URL>/                       ← the URL the user enters
  _asset-library-meta.json               ASSET_TOP_METADATA_FILENAME (entry point, fixed name)
  _v1/asset-index.json                   API_VERSIONED_SUBDIR "_v1" + ASSET_INDEX_JSON_FILENAME
  _v1/assets-00000.json, -00001 …         pages (names chosen by the generator; listed in the index)
  <any/sub dir>/<file>.blend              the asset files, paths kept as in the source folder
  <any/sub dir>/<file>_thumbnails/<IdType>/<name>.webp   previews (+ a ".last_modified" stamp file)
  blender_assets.cats.txt                 source catalogs (read by the generator, folded into asset-index.json)
```
- `_asset-library-meta.json` (`AssetLibraryMeta`, required `api_versions`, `name`, `contact{name[,url,email]}`):
  `{"api_versions": {"v1": {"url": "_v1/asset-index.json", "hash": "SHA256:<hex>"}}, "name": …, "contact": {…}}`.
  The generator writes defaults `"Your Asset Library"`, `"Your Name"`, `example@example.org` and **keeps** name/contact
  from an existing file on re-runs (edit it once by hand).
- `asset-index.json` (`AssetLibraryIndexV1`): `schema_version` ("1.0.0"), `asset_size_bytes`, `asset_count`,
  `file_count`, `pages: [{url, hash}]`, `catalogs: [{path, uuids[], simple_name}]`.
- Page (`AssetLibraryIndexPageV1`): `asset_count`, `file_count`, `assets[]`, `files[]`.
  - Asset (`AssetV1`): `name`, `id_type` (e.g. `OBJECT`, `MATERIAL`, `NODETREE`), `files: [relpath]` (first = file holding
    the data-block), `thumbnail: {url, hash}` (optional), `bl_versions: {min[, until]}` (*"Blender shows the asset if
    `min <= blender < until`"*), `meta`: `catalog_id`, `tags`, `author`, `description`, `license`, `copyright`,
    `preferred_import_method` (`APPEND`, `APPEND_REUSE`, `ASSET_IMPORT_PACK`), `properties` (custom props as typed list).
  - File (`FileV1`): `path`, `url` (omitted when the path is URL-safe), `size_in_bytes`, `hash` ("SHA256:hex"),
    `blender_version` (spec says "5.2"; the 5.2.3 generator actually wrote `"5.2.45"`).
- **Hashes:** SHA-256 only, `"SHA256:<hex>"`. Every `URLWithHash` is fetched as `GET {url}?hash={hex}` *"for cache
  busting"*; the meta file is fetched as `GET /_asset-library-meta.json?s=<minutes stamp>` (seen in the server log:
  `?s=12682831`; `HTTP_CACHEBUST_RESOLUTION_SEC = 60`). Requests carry header `X-Blender: 5.2`. The manual says the
  server *"MUST … ignore query string parameters when serving static files"* (search extract).
- **Generate** (registered by `PKG/__init__.py`: `bpy.utils.register_cli_command("asset_listing", …)`):
  ```
  blender -b -c asset_listing generate <library folder> [--page/-p N (default 1000; 0 = one page)] [--limit/-l N]
  blender -c asset_listing -v|-q generate …     (log level before the sub-command)
  ```
  It walks `rglob("*.blend")`, opens each with `bpy.data.libraries.load(..., assets_only=True)`, lists marked assets,
  writes each embedded preview as **WebP, quality 80** (`image.file_format = "WEBP"`), reads all `*.cats.txt`, and
  rewrites the JSON (old `assets-*.json` deleted). Re-run after any change (manual: rerun *"any time an asset or asset
  catalog changes"*, search extract). Measured: 1 file / 2 assets in 0.16 s.
- **Previews only from the data-block's stored preview.** A material marked in a background Blender had no preview, so
  it got no `thumbnail` (tested). Make previews before generating (`ob.asset_generate_preview()` worked for an object in
  background).
- Real public example (GitHub Pages, merged 2 Nov 2026): https://github.com/cartesiancaramel/blender-remote-asset-library-test-v1
  – root has `_asset-library-meta.json`, `_v1/asset-index.json`, `_v1/assets-00000.json`, one 5 MB `.blend`, `.nojekyll`,
  `blender_manifest.toml`. Note: its listed `size_in_bytes` (4,983,308) does not match the committed file (4,980,996) –
  a stale listing is easy to publish.

## 2. Adding a library (user and Python)
- Preferences: 5.2 has its own **Asset Libraries** page (search extract: *"Setup moved to a dedicated Asset Libraries
  page, and the list now includes 'All Libraries' and 'Essentials'"*; manual
  https://docs.blender.org/manual/en/5.2/editors/preferences/asset_libraries.html). **"+" → "Add Remote Asset Library"**
  (operator enum text) → name + URL (manual: *"URL of the online asset library. Only available for online asset
  libraries."*, search extract). Third-party steps: *Preferences > Asset Libraries > + > Add Remote Asset Library*,
  paste URL (https://blender.physicallybased.info/, search extract).
- Operator (5.2.3, introspected): `bpy.ops.preferences.asset_library_add(name="…", remote_url="https://…/", type='REMOTE')`
  – `type` items `REMOTE` ("Add an asset library referencing a remote repository with support for listing and
  updating") / `LOCAL` (default). Works in a background Blender (returned `{'FINISHED'}`).
- `bpy.types.UserAssetLibrary` (5.2.3): `name`, `path`, `enabled`, `remote_url` ("Remote URL to the asset library"),
  `use_remote_url` (**read-only**: "Synchronize the asset library with a remote URL"), `import_method` (`LINK`,
  `APPEND`, `APPEND_REUSE`, `PACK`; **default `PACK`**: "Import the asset as linked data-block, and pack it in the
  current file"), `use_relative_path`. No `library_type` property.
- **Snag:** `prefs.filepaths.asset_libraries.new(name=, directory=)` + setting `remote_url` gives a half library:
  `path` jumps to the cache folder but `use_remote_url` stays False and cannot be set. **Use the operator.**
  (5.3 adds `remote_url` and `extension_id` arguments to `asset_libraries.new()`, search extract of
  https://developer.blender.org/docs/release_notes/5.3/python_api/.)
- `path` of a remote library is set automatically to the cache (binary string: *"The download cache directory of remote
  asset libraries cannot be changed"*); changing `remote_url` moves it to another cache folder.
- **Online access is required**: `PKG/__init__.py remote_asset_library_sync` returns *"skipping …, online access is not
  allowed"* when `bpy.app.online_access` is False. Pref: `prefs.system.use_online_access` ("Allow Online Access",
  System > Network); command-line overrides `--online-mode` / `--offline-mode`. Also gated by
  `prefs.experimental.use_remote_asset_libraries` ("Enable asset libraries served over HTTP/HTTPS", **True** in 5.2.3).
  The Assets page shows "Internet Access Required … Continue Offline / Allow Online Access" when a remote library exists.
- Visibility filter: `prefs.view.asset_access` = `ALL` / `ONLY_ONLINE` / `ONLY_OFFLINE`.

## 3. Sync, download and cache
- **Listing sync:** only in the UI (`if bpy.app.background: return`), only `http://` / `https://` (*"skipping …, can
  only handle http://, https://"*), at add-on start and then if older than `REMOTE_ASSET_LIBS_AUTOSYNC_PERIOD_SEC =
  3600 * 24` (age = mtime of the cached `_asset-library-meta.json`). By hand: `bpy.ops.asset.library_reload_listing()`
  ("Re-download the asset listing of a remote library") or Shift-click on refresh
  (`asset.library_refresh(use_remote_listing=True)`). A cross-process mutex stops two Blenders syncing one library; a
  backup of the old listing is restored if Blender quit mid-download. JSON files > `MAX_JSON_FILE_SIZE_MB = 64` refused.
  Bad paths in a page (absolute, `..`) are rewritten and warned (*"tries to escape the asset library"*).
- **Assets download on demand**, one file at a time (`num_parallel_downloads=1`, FIFO), previews 5 in parallel (LIFO),
  previews re-fetched after `PREVIEW_DOWNLOAD_AGE_THRESHOLD_SEC = 7*24*3600`. Binary strings: *"Asset needs downloading
  first"*, *"Brush '%s' needs downloading before it can be used (check context menu)"*. Operators:
  `asset.asset_download(asset_library_type=, asset_library_identifier=, relative_asset_identifier=)` ("Make the asset
  available without internet access"), `asset.assets_download()` ("Download the selected asset(s)"). Manual: to take a
  library offline, select all (A) in the Asset Browser → **Download Assets** (search extract). Downloads go to
  `<file>.part`, renamed when done; HTTP `ETag`/`Last-Modified` are kept in `_local-meta-cache/`.
- **Import:** the library's `import_method` (default `PACK` = linked + packed into the open file) unless the asset's
  `preferred_import_method` is used; the downloaded `.blend` stays in the cache.
- **Cache path** (measured, Linux): `bpy.app.cachedir` + `remote-assets/<md5(remote_url)[:16]>/` – e.g.
  `~/.cache/blender/remote-assets/ef7615a0e6baf832/` for `http://127.0.0.1:8765/`; Essentials:
  `<cachedir>/remote-assets/online-essentials` (`bpy.types.AssetLibrary.online_assets_cache_path()`). Windows path =
  `bpy.app.cachedir` there (not measured). Contents after the test: `_asset-library-meta.json`, `_v1/asset-index.json`,
  `_v1/asset-index.processed.json`, `_v1/assets-00000.json`, `blender_assets.cats.txt`, `_local-meta-cache/<sha256>`,
  `sub dir/crate.blend`.
- **Cache cleaning:** none found for asset files; only stale `assets-*.json` pages are deleted after a sync.
- **Hash check:** the Python downloader does **not** verify the SHA-256 of a downloaded file (no check in
  `_bpy_internal/http/downloader.py`); the C++ side has a status *"This asset was previously downloaded, but it is
  outdated or inconsistent. Downloading it again is recommended."* (file-hash cache `*/_file_hashes*.sqlite`). Open bug
  #166102 "Remote Asset Library ignoring all the hash information" (5.2.3, search extract).

## 4. Limits
- **Self-contained `.blend` files:** manual: *"each .blend file needs to be independent of any other file, so no linking
  between files, and pack textures and other external files"* (search extract). Only `.blend` is downloadable
  (`asset_download_path` raises *"does not end in .blend"*).
- **No versions per asset** beyond `bl_versions.min/until`; one listing per API version (`api_versions.v1`, `v2` …).
- **Authentication: none in 5.2.3** (no token anywhere in `RL/`; a leftover `""  # auth_token` argument breaks the CLI,
  §7). Access tokens arrive in 5.3 (§6).
- **http:// allowed**, not only https: tested end-to-end with `python3 -m http.server` on `http://127.0.0.1:8765/`
  (listing + one `.blend` downloaded by Blender's own code). **`file://` is accepted by the operator but never synced**
  (sync accepts only http/https). CORS irrelevant (not a browser). Uses Python `requests` (honours proxy env vars),
  8 retries, 300 s timeout.
- Size: no cap on asset files in the code; bug #164924 "Cannot download asset with 2.38GB" (stalls at 90 %, search extract).

## 5. Essentials online
- URL compiled in: `https://cdn.extensions.blender.org/asset-libraries/essentials/`
  (`bpy.types.AssetLibrary.online_assets_url()`; `essentials_library.cc`). Toggle
  `prefs.asset_libraries.use_online_essentials` ("Include Online Essentials", default True): *"Include remote assets in
  the Essentials asset library. Downloading requires Online Access …"*. Release page: *"base meshes, materials,
  high-resolution HDRIs, compositing effects and more, without increasing Blender's download size"* (search extract,
  https://www.blender.org/download/releases/5-2/). **Size: no published figure found**; the CDN is blocked here, so
  `asset_size_bytes` of its `asset-index.json` could not be read.

## 6. Blender 5.3 (released ~10 Nov 2026 per third-party posts; not confirmed from blender.org)
- **Asset-library extensions:** `blender_manifest.toml` with `type = "asset-library"` and a section
  `[asset_library]` `remote_url = "…"`; `blender_version_min = "5.3.0"` (D. Felinto on the test repo PR: *"All the asset
  library extensions need to be at least 5.3."*). One library per extension; installing adds it to Asset Libraries
  (search extract of https://docs.blender.org/manual/en/latest/advanced/extensions/asset_libraries.html). Built with
  `blender --command extension build`. Real manifest (raw GitHub, read):
  ```toml
  schema_version = "1.0.0"
  id = "cartesian_caramel_everyday_nodes"
  type = "asset-library"
  blender_version_min = "5.3.0"
  license = ["SPDX:CC0-1.0"]
  [asset_library]
  remote_url = "https://cartesiancaramel.github.io/blender-remote-asset-library-test-v1/"
  ```
  extensions.blender.org takes **CC0 only** and copies the data to `https://cdn.extensions.blender.org/asset-libraries/<id>/`
  (PR comment: *"since this is where the data will be copied to"*).
- **Access tokens** per library (Advanced settings), and `UserExtensionRepo.use_access_token_for_asset_libraries`;
  `UserAssetLibrary.is_available()` (search extract, https://developer.blender.org/docs/release_notes/5.3/assets/ and
  …/5.3/python_api/). Tracker: #157505 "WIP: Initial support for remote asset-libraries as extensions", #162781 TODOs.
- **Asset Library Publisher** (Superhive, GPL, for 5.3): Check Library → Fix and Copy → Generate Listing; checks packing,
  linked data, missing/empty previews, catalogs, duplicate names; quote: *"In our test, a modular kit that worked fine as
  a normal download arrived without a single texture as a remote library."* – https://superhivemarket.com/products/asset-library-publisher
  (search extract). No source found for "5.3 installs a remote library in one step" other than installing an
  asset-library extension (drag the zip in).

## 7. Known bugs / snags (5.2.3)
- **`blender -c asset_listing download <url>` crashes** in 5.2.3: `TypeError: 'PosixPath' object is not callable` (the
  CLI passes a stray `""  # auth_token` so the arguments shift; `RL/cli_listing_downloader.py:43`). Tested. Workaround:
  call `listing_downloader.RemoteAssetListingDownloader(url, path, on_update, on_done)` from a module (not a
  `--python` script: the downloader's spawned subprocess re-imports `__main__` and fails on `import bpy`).
- Listing sync never runs in background Blender (`bpy.app.background`), so tests/CI must drive it by hand.
- `use_remote_url` read-only; `asset_libraries.new()` cannot make a remote library (§2).
- #159703: first start without internet leaves an empty cache folder → *"file does not exist _asset-library-meta.json"*
  until deleted. #160468: freeze opening a file with an invalid localhost library configured (mutex deadlock).
  #159664: crash on previews from a custom library (beta). #161776: duplicate assets with several versions. #164924,
  #166102 above. (All search extracts of projects.blender.org issue titles.)
- Generator lists assets without checking packing/previews (Publisher's quote above); keep `.blend` + listing in sync
  (the public test repo is already out of sync).
- Fresing note: app-template preferences are not kept over a restart in 5.2.3 (CLAUDE.md §8, task 0278) – check whether
  an added library survives a restart with `--app-template fresing_render`.

## Pages that could not be read (network blocked: docs/developer/code/notes/projects.blender.org, cdn.extensions.blender.org)
Manual 5.2 "Remote Asset Libraries", "Asset Libraries" (prefs), developer docs remote_asset_libraries + sub-pages,
5.2/5.3 release notes, code.blender.org blog, tracker issues, Superhive page, Essentials CDN listing – only search
extracts of them were available. GitHub (test repo) was read directly.
