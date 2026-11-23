# 0286 – Study (findings only): asset libraries – Fresing standard assets, outside libraries (BlenderKit, Poly Haven, …) and the user's own libraries

**Who:** worker · **Status:** open – can start · **Branch:** `task/0286-study-asset-libraries` (branch only, never
merged; every push `[skip ci]`)
**Started by:** lead, 23 Nov 2026 00:30 (owner 00:23: "https://www.blendkit.com/ – is there a way to also link these
libraries and make them easy to use in the app, to great environments in Fresing Render? Possibly other libraries.
Could we have Fresing standard assets, and then an external library, and a user can download directly into their own
instance of Fresing Render? And keep the models in their own libraries if they choose so.") · **Model:** Opus · effort
High
**Area:** findings only. Prototype code in **new files only** on the branch (e.g. `tools/asset_library_proto/`,
`blender/assets_proto.py`); reads `blender/world.py`, `blender/surroundings.py`, `blender/ops_surroundings.py`,
`blender/materials.py`, `core/materials_lib.py`, `blender/web3d_env.py`, `docs/COMPANY-USE.md` and the briefs of
0272 / 0273 – changes none of them. Pictures and the page in `tasks/0286_page/`. Not a code slot.

## Goal

The owner gets a clear plan, with a working proof on the branch, for **three layers of assets** in one picker:

1. **Fresing standard** – our own environment kits (factory hall, quay, open sea, studio, workshop …), HDRIs,
   materials and props, shipped or hosted by Fresing, free for everyone.
2. **Outside libraries** – BlenderKit (now also called "Blendkit"), Poly Haven, ambientCG and others the study finds
   worth it; the user downloads straight into his own Fresing Render.
3. **The user's own libraries** – anything he downloads he can keep in his own folder (Mine / Department / Company
   from 0272), so it is there offline and in later projects.

The report says what is allowed (licences, terms), how each layer works technically, how it looks for a user who does
not know Blender, and which build tasks follow (with sizes and order).

## Background

- **Blender 5.2 (the app's Blender, 5.2.3) has Remote / Online Asset Libraries:** a library hosted on any web server
  (a folder of `.blend` files + an asset listing Blender generates, previews as WebP), browsed inside Blender,
  downloaded per asset when needed and cached. Needs *Allow Internet Access* (`bpy.app.online_access`). Limits from
  the manual: each `.blend` must be self-contained (textures packed), no asset versions (only "same / different
  file"). Blender's own Essentials got online assets this way. Manual: "Remote Asset Libraries" (5.2); developer
  docs: `developer.blender.org/docs/features/asset_system/remote_asset_libraries/`. A shop extension ("Asset Library
  Publisher") says 5.3 lets an extension install such a library in one step – check what 5.2.3 can do.
- **BlenderKit / Blendkit:** own add-on (open source, GPL, free; signs the user in with his own account). ~10,000
  models, ~10,000 materials, 1,000+ HDRIs free without login; the rest with the Full plan (~$9.90 / month, per user).
  Two asset licences: **Royalty Free** (commercial use and selling renders allowed, never re-selling / passing on
  the asset itself) and **CC0**. Their 2018 terms forbid using BlenderKit assets "in any other products or services"
  or building products that compete with them – read the current user terms, the add-on's licence and any API /
  developer terms. Their fair-share terms for creators mention assets "offered through other software and platforms
  in the future". They now have plugins for Maya, Rhino and Godot (Aug 2026) – maybe a sign they want partners.
- **Poly Haven:** all assets CC0; public API `api.polyhaven.com`. Their API page has said "free for non-commercial,
  commercial needs a licence", while their GitHub API page and corporate page now say free for any use with a small
  "Powered by Poly Haven" credit and a unique User-Agent. Find out which is current.
- Fresing Render is **GPL, public, donation-funded** (CLAUDE.md section 1 / 6): nothing in the repository or the
  installer may carry a licence that forbids passing it on. Assets used in add-ons on extensions.blender.org must be
  CC0.
- Anything that reaches the network: manifest `network` permission, check `bpy.app.online_access` first (CLAUDE.md
  section 8), and `docs/COMPANY-USE.md`'s network table (companies' IT must be able to switch it off).
- Owner's wishes that touch this: **looks very good with no set-up**; the app as simple as possible for people who do
  not know Blender, Blender's own tools easy to open; every model at a realistic scale (0258); each sample project in
  its own fitting surroundings (0233); company use (a company may want only approved assets).
- Related tasks: **0272** (locations per kind: backgrounds, materials, … marked Company / Department / Mine, `.frsetup`,
  a ready-made Mine folder), **0273** (material picker with pictures, reads 0272's folders), 0274 (new finishes),
  0233 / 0268 (surroundings, site kit). This study must fit them – one picker for all, not a second system.

## What to find out

**A. Licences and terms (a table per source):** BlenderKit (Royalty Free and CC0 assets, free and Full plan),
Poly Haven, ambientCG, and up to three others worth it (e.g. Sketchfab download API, Blender's Online Essentials,
Quixel / Fab – say quickly why in or out). Per source: may Fresing **ship** assets in the installer or a Fresing-hosted
library; may the app **call their server** itself; must the user **use their own add-on / account**; credit needed;
may assets be **packed into a project file** a user sends to a client or a colleague, into the **Web 3D page** export
(0099) and into **Fresing Viewer** files; company use. Quote the exact clause and link for each "yes / no". Where the
terms are unclear, write the questions for the owner to send them (BlenderKit partnership question included – a short
draft e-mail in the report, not sent).

**B. Fresing standard library:** how to host it (GitHub Pages of this repo or a separate public repo, size limits,
GitHub LFS vs plain files, bandwidth), Blender's remote listing vs our own small index; what ships in the installer
(offline starter set) vs downloads on demand; how one `.blend` per asset stays self-contained; versions and updates;
which first assets we need (list from the test-tour surroundings, 0233 / 0268, by category) and where they come from
(made by us, CC0 sources). Proof: a tiny test library (3–5 CC0 assets: one HDRI, one material, one prop, one small
environment) hosted from the branch or a local web server, registered in Blender 5.2.3 as a remote library, browsed,
downloaded, placed – note every step and every snag (prefs dropped at restart: 0278 / 0283!).

**C. Outside libraries in the app:** for BlenderKit the expected way is **their own add-on** (a "Get BlenderKit" button,
the user signs in himself) – find out how it installs next to our app template and extension, whether its panel and
drag-and-drop work in our workspaces, whether we can open it from our picker, and what happens to its downloads
(where they land, packed or linked). For Poly Haven / ambientCG: their own add-ons vs a remote listing vs our own
download code. Scale: do downloaded props come in at real size (0258's rule) – how we check / fix it.

**D. The user's own libraries:** "Keep in my library" – copy a downloaded asset from the cache into Mine / Department /
Company (0272), with its licence and source kept beside it (a small sidecar or the asset's metadata), so a company can
see what came from where; offline use; what happens when the source asset changes or is removed.

**E. Picker and user flow (no Blender knowledge needed):** one window for environments / HDRIs / materials / props
with tabs or a filter **Fresing · Online · Mine** (and Department / Company), pictures, search, "free" / "needs plan"
/ licence badge, one-click "Use" and "Keep". Show 2–3 layouts as pictures on the page; say how it joins 0273's
material picker and the Surroundings functions. Company switch: "only Fresing + Company assets" via `.frsetup`.

**F. Projects that travel:** packing downloaded assets into the project on save / Collect (so it opens on another PC),
what this does to file size, and the licence check before a project, Web 3D page or Viewer file leaves the PC (warn on
an asset that may not be passed on).

## Done when

- [x] Report with tables A–F, every licence claim with its link and quoted clause (short quotes), and the snags found
- [x] Proof library works in Blender 5.2.3 on the web machine (steps, times, sizes); screenshots in `tasks/0286_page/`
- [x] Page `tasks/0286_page/index.html` with the picker layouts and a pick list for the owner (tick boxes + Copy line,
      like 0168 / 0270): which sources, which layout, which first standard assets
- [x] Proposed build tasks in order, each with model · effort, files it changes and what it waits for (0272, 0273, 0283)
- [x] `docs/COMPANY-USE.md` lines drafted in the report (not changed)
- [x] Branch pushed with `[skip ci]`; report below filled in

## Not in this task

- No change to any existing file outside `tasks/0286*`; no merge, no release.
- No account sign-ups, payments or e-mails to BlenderKit / Poly Haven – questions and the e-mail draft go to the owner.
- No downloading of non-CC0 assets into the repository, ever. Proof assets: CC0 only, credited.
- Not the material looks themselves (0270 / 0274) and not the locations system (0272).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 23 Nov 2026. Branch `task/0286-study-asset-libraries` (pushed with `[skip ci]`,
never merged). App version on the machine: 0.2.206.

**In short.** Use **Blender 5.2's own remote asset libraries** for the Fresing standard library. They are plain files
on any web server, and Blender handles the listing, pictures, download, cache and offline use. The proof works inside
the Fresing app. **Poly Haven** (CC0) and **ambientCG** (CC0) fit all three layers. **Blendkit** fits only layer 2,
through its own add-on and the user's own account. Its Royalty-Free assets may not be re-hosted, and whether they may go
into a public Web 3D page needs an answer from Blendkit. **Keep** copies an asset into 0272's folders with a small
sidecar file. **One picker**: 0273's window gets tabs. Two snags need the app's attention: the offline dialog and
Blender's "Online Essentials" (below). The Online Essentials one is also a correction for `docs/COMPANY-USE.md`.

**Page:** `tasks/0286_page/index.html`: the proof's pictures, three picker layouts, the first-asset list, a licence
summary, and pick ticks with a Copy line. Source notes behind the tables are in `tasks/0286_page/sources_licences.md`
and `tasks/0286_page/sources_remote_libraries.md`.

**How the facts were found.** The test machine's network reached only GitHub and download.blender.org. blendkit.com,
polyhaven.com, ambientcg.com, sketchfab.com, fab.com and docs/developer.blender.org were refused. So:
- **[read]** marks text read directly, either on GitHub or in the code of Blender 5.2.3 on this machine.
- **[search]** marks a search engine's excerpt of the page. **Check every [search] line in a browser before deciding.**

Two helper agents gathered the web facts (licences; Blender's remote libraries). I wrote the proof, the measurements and
the Blendkit add-on checks myself. GitHub's limits come from GitHub's own documentation source (github/docs).

### A · Licences and terms

Each row says: may Fresing **ship** the assets (installer or Fresing-hosted library); may the app **download from their
server itself**; is **their add-on / account** needed; is **credit** needed; may the asset travel **in a project** sent
to a client, in a **Web 3D page / Fresing Viewer file**; **company** use. Quotes are short; the full text is in
`sources_licences.md`.

**Poly Haven** – fits all three layers.
| Question | Answer | Quote · link |
| --- | --- | --- |
| Ship / re-host | yes (CC0) | "it does not apply to the CC0 assets themselves once downloaded or self-hosted" [read] · github.com/Poly-Haven/Public-API/blob/master/ToS.md §2.5 |
| App calls the API | **yes, also commercial**, since 18 Jul 2026 (commit 4a6ceb9) | "free to access and use by anyone … for any purpose, including commercial use, at no charge" [read] · ToS §2.1 |
| Conditions | our program name in every request; "Poly Haven" visible in the picker; no hint that they endorse us | "unique "Referer" header or user-agent that matches your software name" [read] §2.4; "a label within your interface (a title, menu item, or button that names Poly Haven)" [read] §2.5 |
| Conflicting page | polyhaven.com/our-api may still say commercial use needs a licence | "commercial use requires a custom license, and typically sponsorship" [search, probably stale] · polyhaven.com/our-api |
| Add-on / account | none needed; their add-on is paid (Superhive $69 / Patreon) and GPL | "Poly Haven will never require payment, a license, or a key" [read] §2.3 · github.com/Poly-Haven/polyhavenassets |
| Credit for assets | no | "CC0 assets carry no attribution requirement whatsoever" [read] §2.5 |
| Project / Web 3D / Viewer / company | yes (CC0) | "Using the API to generate revenue, directly or indirectly, is explicitly permitted" [read] §2.3 |

**ambientCG** – fits all three layers. Ask them about API manners before we ship download code.
| Question | Answer | Quote · link |
| --- | --- | --- |
| Ship / re-host, project, Web 3D, company | yes (CC0) | "All ambientCG assets are provided under the Creative Commons CC0 1.0 Universal License" [search] · docs.ambientcg.com/license/ |
| App calls the API | probably yes: API v3 is current, but **no API terms were found** (rate limits, User-Agent) | "it is recommended to switch to the new API" [search] · docs.ambientcg.com/updates/ |
| Add-on / account | none | – |
| Credit | not required, appreciated (they suggest a line) | "Created using <asset name> from ambientCG.com, licensed under … CC0" [search] · docs.ambientcg.com/license/ |

**Blendkit** (formerly BlenderKit, now blendkit.com) – layer 2 only, through its own add-on.
| Question | Answer | Quote · link |
| --- | --- | --- |
| Ship Royalty-Free assets | **no** | "royalty free license doesn't allow to re-sell 3D models even if modified" [search] · blendkit.com/docs/licenses/ |
| Ship their CC0 assets | allowed by CC0, but Blendkit asked users not to (2022) | "will introduce a new option to exclude them from redistribution" [search] · blenderkit.com/articles/our-position-on-cc0-models/ |
| App calls their server | **no public API terms found**; the add-on signs in with a key per user | "Your unique API key authenticates downloads and requests inside the add-on" [read] · github.com/BlenderKit/Blendkit `__init__.py` |
| Older rule | the 2018 terms forbade other products; unknown whether this still applies | "strictly prohibited from using BlenderKit assets … in any other products or services" [search] · blendkit.com/terms-and-conditions-2018/ |
| Add-on / account | their add-on (GPL-2.0-or-later). Free assets need no account. Full plan $9.90 / month / seat (5 employees or fewer, revenue $100k or less); Business $29 | "Browse and download a selection of assets for free without an account" [read] README; manifest `SPDX:GPL-2.0-or-later` [read]; prices [search] blendkit.com/plans/pricing/ |
| Credit | no | RF "allows commercial use without mentioning the author" [search] · blendkit.com/docs/licenses/ |
| In a project sent to a client | **probably yes** | "you may redistribute the product as a part of the project" [search, users' terms 12 Jun 2026] · blendkit.com/terms-and-conditions-2026/ |
| In a public Web 3D page / Viewer file | **unclear: ask first, warn meanwhile** | games allowed "if these can't be extracted by the users in an easy way" [search] · blendkit.com/docs/licenses/licensing-faq/ |
| Company | yes, with the plan that fits the company's size | "The only limitation with Royalty-free licenses is you can't sell the assets themselves" [search] · same FAQ |
| Other software | they sell into Maya, Rhino and Godot themselves | fair-share terms: assets "might be offered through other software and platforms in the future" [search] · blendkit.com/docs/fair-share-terms/; plugins [read] github.com/BlenderKit/bk_godot, …/blendkit-rhino |

**Others, in or out:**
| Source | In / out | Why · quote · link |
| --- | --- | --- |
| Blender Essentials (in Blender) | in (already there) | all assets CC0 [search] · projects.blender.org/blender/blender-assets. **Online Essentials:** see the snags below |
| Sketchfab Download API | out for now | the user must sign in inside our app; the CC licence and author of every model must follow it into every export: "the end-user must be able to log in with their Sketchfab account inside your application" [search] · sketchfab.com/developers/download-api/guidelines |
| Fab / Quixel Megascans | out | needs an Epic account; no API for other apps found; "Standalone redistribution of the assets is prohibited" [search] · fab.com/cla |
| Textures.com | out | paid; "No, redistribution of the materials is not allowed." [search] · textures.com/faq-license |
| extensions.blender.org | rule only | "For assets used in add-ons, the required license is Public Domain (CC0)." [read, manual source] · docs.blender.org/manual/en/latest/advanced/extensions/licenses.html. This binds us only if we list there. Keeping Fresing standard CC0 keeps that open, and from 5.3 the platform hosts CC0 asset libraries itself [search]. |

### B · The Fresing standard library

**How Blender 5.2.3 does it** (read in its code, `5.2/scripts/modules/_bpy_internal/assets/remote_library/`, and
measured):
- A library is a folder of `.blend` files plus three JSON files written by Blender's own tool: `blender -c
  asset_listing generate <folder>`.
  - The files are `_asset-library-meta.json` (name, contact, and the hash of the index), `_v1/asset-index.json` and
    `_v1/assets-NNNNN.json` (1,000 assets per page).
  - It also writes one WebP picture per asset (`<file>_thumbnails/…`, 1–2 kB each).
  - It reads the catalogs from `blender_assets.cats.txt`.
  - Every asset carries its name, kind, tags, author, **licence**, copyright and description, plus **our own custom
    properties**. The proof's `fr_source`, `fr_kind`, `fr_size_m`, `fr_licence_url` and `fr_pass_on` arrived in the
    listing, so the picker can show licence and size without downloading anything.
- **Any static web server** works (also `http://`); query strings must be ignored (Blender adds `?hash=` / `?s=`).
- Each `.blend` must be self-contained, with textures packed. Blender downloads one file per asset when it is used.
- Asset files may sit at another address: the listing's file URL is joined with `urljoin`, so an absolute URL is kept.
  This was read in the code, not tried.
- **Versions:** a changed file gets a new SHA-256 in the listing, and Blender offers it again. There are no version
  numbers per asset.
- The listing is synced at most once a day, at start, in the UI only (never in a background Blender), and only with
  online access on.
- Downloads land in Blender's cache, `<cachedir>/remote-assets/<md5 of the URL, 16 hex>/`, and are never cleaned.
- The library's import method defaults to **PACK**: the asset is linked and packed into the open project.
- There is no login in 5.2.3. Access tokens come in 5.3 [search].

**Hosting** (GitHub's documentation source, github/docs):
- **Pages:** "Published … sites may be no larger than 1 GB", a soft bandwidth limit of "100 GB per month".
- **Git LFS** "cannot be used with … Pages sites". Plain files in a repository are blocked above 100 MiB.
- **Releases:** each file "must be under 2 GiB. There is no limit on the total size of a release, nor bandwidth usage."

**Proposal:**
- A **new public repository `smholte/fresing-assets`** (CC0 only, so it may go anywhere): the asset makers, the
  `.blend` files up to ~20 MB, the listing and the pictures on its GitHub Pages.
- Big 360° photos go on a release of that repository, with absolute URLs in the listing.
- A workflow there regenerates the listing and runs a check on every push: packed, preview present, licence filled in,
  real size within limits, `fr_*` properties set.
- Not in `CAD-render-animation`: it would grow this repository and its runs.

**Offline starter set:** the same `.blend` files shipped in the installer as a **local** library folder (Blender local
libraries need no listing), ≈ 30 MB (page section 3).

**First assets:** page section 3, by category: 360° photos from CC0 sources; studio cove, workshop, yard and showroom
made by us; floors and walls from CC0 materials; props made by us in the `props_detail.py` way, at real size.

**Proof** (4-core web machine, Blender 5.2.3, the installed Fresing app 0.2.206 with its app template, under xvfb):
| Step | Result |
| --- | --- |
| Make 4 assets (`make_assets.py`: sky = World with a packed 1k EXR; worn paint = Material with a packed 256 px picture; euro pallet = Object; workshop corner = Collection; Cycles previews) | ≈ 5 s; files 616 / 234 / 262 / 228 kB = 1.34 MB |
| `blender -c asset_listing generate` | 0.09–0.12 s; listing 8.6 kB, 4 WebP pictures 1.0–2.3 kB |
| Add it in the app: `bpy.ops.preferences.asset_library_add(type="REMOTE", remote_url=…, name=…)` | 0.004–0.017 s; the listing download starts at once |
| Listing + 4 pictures in the cache | **1.5 s** (local server) |
| Asset Browser on the library | shows the 4 pictures and the catalogs (page picture 1) |
| Download all 4 (`asset.assets_download`) | **0.5 s**; `is_online` goes True → False |
| Place: pallet, sky as world, paint on a block, workshop corner | pallet **1.2 × 0.8 × 0.144 m** as made; 4 pictures still packed |
| Cycles 640 × 400, 32 samples | 5.1–6.2 s |
| Project saved with every image packed | 1.09–1.11 MB |
| Save Preferences, start again **offline** (with and without the app template) | library kept, all 4 `.blend` files in the cache |

**Snags found** (S1–S8, numbered for the build tasks):
1. **S1 – Offline, Blender hides even downloaded assets.** It shows "Internet Access Required – Continue Offline /
   Allow Online Access" over the Asset Browser (page picture 2). Our picker must read the cache itself and never show
   this.
2. **S2 – Online Essentials** (Blender's own online library, on by default) is fetched from `cdn.extensions.blender.org`
   **at every start with online access on**. This was measured: the request appears in the log, `bl_pkg/__init__.py`
   `_remote_asset_library_sync_all_periodic`. When it cannot be reached, Blender shows a **red "Could not read asset
   listing 'Online Essentials'"** in the status bar at start (page picture 3). The installer switches online access on
   for the update check, so this applies to every user.
3. **S3 – the preference has to be saved.** The added library came back after a restart **because the preferences
   were saved** (`wm.save_userpref`; 0278's snag concerns add-on preferences under the app template). The app should
   add its library again at every start, the way `settings_store` keeps its settings, and never rely on Blender's
   preference file.
4. **S4 – the library choice is not readable from a script.** It is a dynamic list: `bl_rna` shows only All / Current
   File / Essentials / Online Essentials / Custom. Setting the library's name works.
5. **S5 – black screenshots.** `bpy.ops.screen.screenshot` gives a black picture under xvfb; ImageMagick
   `import -window root` works, as in the repository's own tools.
6. **S6 – a Blender command crashes.** `blender -c asset_listing download <url>` crashes in 5.2.3 (`TypeError`, a stray
   `auth_token` argument in `cli_listing_downloader.py:43`). This was found by the helper agent.
7. **S7 – no file check, no cache cleaning.** The listing has SHA-256 hashes, but the downloader does not check them
   [read; bug #166102 search]. The cache is never cleaned.
8. **S8 – the default name.** The generator writes "Your Asset Library" and "Your Name" into the meta file; edit it
   once, later runs keep it.

### C · Outside libraries in the app

**Blendkit** – their add-on, read in its code at commit 48b2bc3 (19 Nov 2026). Not run: blendkit.com was blocked here.
- **How it installs:** as a normal Blender extension next to ours, with a manifest asking for `network` and `files`
  permissions.
  - Our picker's **Get Blendkit…** button opens blendkit.com/get-blendkit. A one-click install of their zip only with
    their OK (questions 1 and 2).
  - It keeps its settings in its own `preferences.json`, so it is not hit by 0278's restart snag.
- **Its helper program:** it runs one of its own, `bk_client`, a separate `.exe` on Windows. A company's IT must know
  this (COMPANY-USE below).
- **"Send usage data" is on by default:** it reports asset ids and counts when you save or render, not file names.
- **Downloads:** they land in `~/blenderkit_data`, and by default **also in a folder next to the project** ("Global
  directory and Project's subdirectory"). So a sent project folder carries them. Models are linked or appended by its
  own setting.
- **Checks for the first Blendkit build task** (by hand, a PC with internet):
  - its panel and drag-and-drop in our quiet workspaces (0241 / 0253 hide Blender's tool areas);
  - opening it from our picker;
  - its assets' licence in their metadata (it shows a licence per asset).

**Poly Haven / ambientCG:**
- **Our own download code is better than their add-ons.** Poly Haven's is paid, and neither knows our picker.
- The code turns their API answers into **the same listing form** as our library. Option: a small Fresing-made remote
  listing per source, generated on our side, so Blender's Asset Browser shows it too.
- Downloads go into the same cache. One code path for Use / Keep.
- **Poly Haven conditions:** our User-Agent (`FresingRender/<version> (asset library)` – the same style as the update
  check) and the label "Poly Haven" in the Source list.

**Scale (0258):**
- Every Fresing standard asset carries `fr_size_m`, and the library's check refuses one whose bounding box differs.
- Poly Haven models are in metres [their site, not checked here].
- Blendkit models come in metres in Blender.
- On **Use**, the app compares the object's size with a plausible range for its tag (pallet, door, person …) and shows
  "This looks 100 × too big – fix to 1:1?" rather than scaling silently. That needs a small table of sizes per tag in
  `core/`.

### D · The user's own libraries

- **Keep…** copies the downloaded `.blend` from the cache into a writable 0272 location of the right kind:
  - Backgrounds for 360° photos and environments;
  - Materials (0273's material folder takes `material.blend`);
  - a **new kind "Props"**;
  - Mine first.
- Beside it goes **`asset.json`**:
  ```json
  {"format": "fresing-asset", "version": 1, "name": …, "kind": …, "source": "fresing-standard|polyhaven|ambientcg|blendkit|own",
   "source_id": …, "source_url": …, "licence": "CC0-1.0|blendkit-rf|…", "licence_url": …, "pass_on": true|false,
   "author": …, "size_m": [x,y,z], "kept": "2026-11-23T…", "kept_by_app": "0.2.x", "sha256": …}
  ```
  A company can grep its share for `"pass_on": false`.
- The same facts go onto the placed datablock as a custom property `fr_asset`. Blender drops the asset mark on append,
  so the licence would be lost otherwise.
- **Offline:** kept assets are plain files in the user's folders. Every Mine / Department / Company folder is also
  registered as a Blender **local** asset library, so Blender's own Asset Browser sees them too (no listing needed).
- **When the source changes or removes an asset:** the kept copy stays as it is.
  - The picker compares `sha256` with the current listing and shows "newer version online – Update" (Fresing and Poly
    Haven) or "no longer online" (kept, still usable).
  - Nothing is deleted from the user's folders, ever.
  - Blender's cache can be cleared by the user (**Settings > Libraries > Clear downloads** – a later task); kept copies
    are not in it.

### E · Picker and user flow (page section 2)

- **Layout 1 ★:** 0273's "Materials" window becomes the **asset picker**.
  - Kinds as tabs: Materials · Environments · 360° photos · Props.
  - The Source filter on the left: Fresing · Online (Poly Haven, ambientCG, Blendkit) · Company · each Department ·
    Mine.
  - Search, a pictures grid with source and licence badges and "⤓ not on this PC".
  - The picked item large on the right: licence, size, "May travel: yes / no", and **Use** / **Keep…**.
- **Layout 3** joins it to today's panels: a picture strip of the last used items with **More…** in 5 Scene & Render >
  Surroundings, the props list and 3 Looks' group box (0273's short list).
  - The app's built-in surroundings (halls, sea, quay) stay as they are and show first.
- **"Use":**
  - an environment collection is added at the origin, the machine standing on its floor;
  - a 360° photo becomes `world.py`'s HDRI background (its path is the cached / kept `.blend`'s image, kept packed);
  - a material goes onto the group as in 0273;
  - a prop goes in front of the camera at real size.
- **Company switch:** `.frsetup` (0272) gets `"assets": {"online": false, "sources": ["fresing-standard", "company"]}`.
  The Online group then does not show and the app makes no request for it. With `"fresing_standard": false` even ours
  goes, for offline sites.
- **Blender's Asset Browser stays usable for Blender people.** Our libraries are real Blender libraries. The quiet
  workspaces just do not show it.

### F · Projects that travel

- **Packing:** Blender's default import for remote libraries is already PACK, linked + packed into the project.
  - Our **Use** appends, with the images packed as in the proof. The proof project: 4 assets → 1.1 MB.
  - A 2k 360° photo adds ≈ 8–10 MB per project and a 4k one ≈ 30–80 MB (estimates).
  - So the HDRI background should stay **one packed image per project**, never one per saved scene.
- **Collect:** File > **Collect for sending…** (a later task) packs every outside file (Blendkit's project-folder files
  too) and lists what was packed.
- **Licence check** before **Send project / Collect**, **Web 3D page** (0099) and **Fresing Viewer file**:
  - The app walks the datablocks with `fr_asset`, plus linked libraries whose path is in a library cache. It looks up
    the licence and lists every asset with `pass_on` false or unknown.
  - It asks "These 2 Blendkit models may not be put in a public web page: leave them out / replace by a box / export
    anyway (your responsibility)".
  - Projects sent to a client: Blendkit RF is allowed "as part of the project" [search], so the app warns only for
    unknown sources.
  - The check is a pure-Python function in `core/` with tests.

### Proposed build tasks (in order; the lead numbers them)

1. **Fresing standard library – repository and maker** · Opus · High.
   - A new public repository `smholte/fresing-assets` (the owner creates it), built from `make_assets.py`.
   - Its listing workflow and asset check (packed, preview, licence, `fr_*`, real size); Pages + a release for big files.
   - The first 3–4 assets of the owner's picks.
   - Changes nothing in this repository. Waits for: the owner's picks and the repository.
2. **The app's library hooks** · Opus · High.
   - A **new** `core/assets.py` (no Blender: sources, listing reader, `asset.json`, the pass-on rules, the travel check)
     and a **new** `blender/assets.py`.
   - At every start (idempotent, like `settings_store`): add the Fresing library while online access is on and the
     set-up allows it.
   - **Online Essentials off** by default, once, remembered like `ext_sync.py` – fixes S2 and the COMPANY-USE line.
   - Read the cache directly when offline (S1). The offline starter set as a local library from the installer.
   - Additive in `prefs.py`, the installer's `set_prefs` block. Tests, PC-check line, COMPANY-USE, guide.
   - Waits for: 1 (a URL to point at); 0283 is done.
3. **Asset picker window** · Opus · High.
   - 0273's window gets the kinds as tabs and the Source filter (layout 1), and strips in the panels (layout 3).
   - Use / Keep. Touches `material_picker.py` / `ui_material_picker.py` (0273's), `world.py` (HDRI from a kept
     `.blend`), `ui.py` (strips), the tour stop, the function list, the lesson step if on a learning set.
   - Waits for: **0272, 0273**, 2.
4. **Keep in my library + new location kind "Props" / "Environments"** · Sonnet · Medium.
   - `core/locations.py` (additive kinds), `asset.json`, the "newer online" compare, Blender local libraries for each
     location.
   - Waits for: 0272, 2.
5. **Poly Haven and ambientCG online** · Opus · Medium.
   - Download code in `core/` (no Blender) with our User-Agent, the "Poly Haven" label, a cache in the same form.
   - A network row in COMPANY-USE.
   - Waits for: 3; ambientCG after their answer.
6. **Get Blendkit** · Sonnet · Medium.
   - The button, the check that their panel works in our workspaces, their downloads shown as "Blendkit (on this PC)"
     with their licence. A PC with internet (the owner's) for the end-to-end check.
   - Waits for: 3, Blendkit's answer to questions 1–4.
7. **Projects that travel: Collect + licence check** · Opus · Medium.
   - Pack on Collect; the check before Send / Web 3D / Viewer (`ops_web3d.py`, the viewer export – one call each).
   - Waits for: 4.
8. **More standard assets** · Sonnet · Medium. Batches of the pick list, each with pictures in a tour stop. Waits for: 1.

### `docs/COMPANY-USE.md` – drafted lines (not changed)

- **Correction to the paragraph "Blender itself"** (true today, measured in this task): "Blender 5.2.3 also fetches the
  listing of its own **Online Essentials** asset library from `https://cdn.extensions.blender.org/asset-libraries/essentials/`
  at start when online access is on and the listing is older than a day (`bl_pkg/__init__.py`,
  `_remote_asset_library_sync_all_periodic`). Until task 2 above switches this off, block that address or untick
  Edit > Preferences > Asset Libraries > "Include Online Essentials"."
- New row (task 2): "**Fresing standard asset library**: the list of assets and their small pictures (a few kB), at most
  once a day at start; an asset file only when the user clicks Use / Keep / Download | `https://smholte.github.io/fresing-assets/`
  and `https://github.com/smholte/fresing-assets/releases/download/…` | (file, line)". Switch off: the set-up file's
  `"assets": {"fresing_standard": false}` or online access off.
- New row (task 5): "**Poly Haven / ambientCG**: search and pictures while the picker's Online tab is open, files on Use /
  Keep; the request carries `FresingRender/<version> (asset library)` | `api.polyhaven.com`, `dl.polyhaven.org`,
  `ambientcg.com` | … ". Switch off: `"assets": {"online": false}`.
- New paragraph (task 6): "**Blendkit** is a separate add-on from blendkit.com that the user installs himself. It runs
  its own helper program (`bk_client`), signs in with the user's own Blendkit account, sends usage data (asset ids when
  saving or rendering) unless switched off in its preferences, and stores downloads in `%USERPROFILE%\blenderkit_data`
  and next to projects. Fresing Render does not install it by itself, and the set-up file can hide its button."
- "What never reaches the network" gets: "**the picker's search words** stay on the PC for Fresing standard (filtered
  locally); for Poly Haven / ambientCG the app downloads their whole asset list and filters locally, so no search words
  are sent" – a design rule for task 5.

### Questions for the owner to send

- **Poly Haven:**
  - Their /our-api page still says commercial use needs a licence, while the GitHub ToS of 18 Jul 2026 says free. Which
    is right?
  - Is a "Poly Haven" source entry in our picker enough as the label of ToS 2.5?
  - May we re-host a chosen subset (≈ 30 photos and materials) in our CC0 library (we read "self-hosted" as yes)?
- **ambientCG:**
  - API conditions (User-Agent, rate limits, caching, credit) for a free app using API v3?
  - May we mirror a subset?
- **Blendkit:** the draft e-mail below.

**Draft e-mail to Blendkit (not sent):**
> Subject: Fresing Render – linking to Blendkit from a free Blender app
>
> Hello, I make Fresing Render, a free, open-source (GPL) Blender app for rendering machines from CAD files
> (github.com/smholte/CAD-render-animation). Our users would like good surroundings and props for their machines, and
> Blendkit has them. We would like to work with you rather than around you:
> 1. May our app show a "Get Blendkit" button that installs your official add-on (unchanged, from your release), or
>    should it only open blendkit.com/get-blendkit?
> 2. Do you allow a partner app to show Blendkit search results and download free assets with its own code, the user
>    signed in with their own account? Do you have API or partner terms?
> 3. Your users' terms allow redistributing an asset "as part of the project". Does that cover a project file sent to a
>    client who has no Blendkit plan?
> 4. May Royalty-Free models or materials appear in a web page our app exports (a glTF model with baked textures in one
>    HTML file that anyone with the link can open), or in a viewer file sent to a client?
> 5. Is the 2018 clause about products that compete with you still in force for an app that only links to you?
> Thank you – Sebastian, Fresing

**Tested and measured** (4-core web machine, Linux, Blender 5.2.3, Fresing Render 0.2.206 installed with its app
template, under xvfb; a local web server stood in for GitHub Pages): see the proof table in B.
- **Not tested:** a real GitHub Pages host; release-file URLs; Windows (`bpy.app.cachedir` there, a company proxy);
  Blendkit and Poly Haven / ambientCG downloads (their sites are blocked here); the owner's RTX 3090; a big (4k)
  360° photo. Sizes of future assets are estimates. Licence rows marked [search] are excerpts, not read pages.

**What changed** (branch only):
- New `tools/asset_library_proto/` (`make_assets.py`, `try_in_blender.py`, `README.md`).
- New `tasks/0286_page/` (the page, pictures, two source notes).
- This report.
- No existing file outside `tasks/0286*` was changed. `TASKS.md` is not updated, because the owner said branch only:
  the lead sets 0286 to done.

**Open points:**
- The owner's picks (page Copy line).
- The questions to Poly Haven / ambientCG / Blendkit.
- The **COMPANY-USE correction (Online Essentials)** is true for every install today, so the lead may want it fixed
  before task 2: a document-only change.
- Check the [search] rows in a browser.
