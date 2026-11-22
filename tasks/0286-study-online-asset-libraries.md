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

- [ ] Report with tables A–F, every licence claim with its link and quoted clause (short quotes), and the snags found
- [ ] Proof library works in Blender 5.2.3 on the web machine (steps, times, sizes); screenshots in `tasks/0286_page/`
- [ ] Page `tasks/0286_page/index.html` with the picker layouts and a pick list for the owner (tick boxes + Copy line,
      like 0168 / 0270): which sources, which layout, which first standard assets
- [ ] Proposed build tasks in order, each with model · effort, files it changes and what it waits for (0272, 0273, 0283)
- [ ] `docs/COMPANY-USE.md` lines drafted in the report (not changed)
- [ ] Branch pushed with `[skip ci]`; report below filled in

## Not in this task

- No change to any existing file outside `tasks/0286*`; no merge, no release.
- No account sign-ups, payments or e-mails to BlenderKit / Poly Haven – questions and the e-mail draft go to the owner.
- No downloading of non-CC0 assets into the repository, ever. Proof assets: CC0 only, credited.
- Not the material looks themselves (0270 / 0274) and not the locations system (0272).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
