# 0099 – Web 3D model: export the machine with baked textures, turn it on the website (study 0069 #15)

**Who:** worker · **Status:** done · **Branch:** `claude/elegant-fermat-u6q25p`
**Started by:** lead chat, 12 Nov 2026 (owner's pick from study 0069: #15, **with baked textures** – owner, 12 Nov)
**Lane:** Web 3D (new) – new files `blender/web3d.py`, `blender/ops_web3d.py`, `blender/ui_web3d.py` (a sub-panel of
5 Scene & Render: "Web 3D model"), `core/web3d.py` (sizes, budgets, file lists – plain Python), `tests/test_web3d*.py`;
additive: `props.py`, `ui.py` (register the sub-panel), the tour, the PC check, the guide; the website part:
`site/` and `tools/build_site.py` (Quality & delivery lane is free).
**Model:** Opus · effort High (texture baking pipeline + size budget: a wrong design is expensive) · **Place:** Claude
Code on the web, environment "CAD-render-animation"

## Goal

From any project the owner makes, in one click, a single `.glb` file of the machine that looks like the app's renders
(materials **baked to textures**, not plain colours), small enough for a web page and a phone, plus a one-file viewer
page he can send to a customer. The landing page shows such a model that visitors can turn and zoom.

## Background

- Study 0069 M4: glTF export works in bpy 5.2.3 after a normal app import (test_machine 12 objects, 8,291 triangles →
  0.15 MB GLB in 0.1 s). Google's **model-viewer** (Apache-2.0) shows a GLB on a web page: orbit, zoom, environment
  light, AR on phones later.
- The app's looks are Blender shader node trees (0046 materials, wear, machining marks, paint schemes, decals, painted
  faces, cut-face marks of 0061). glTF only carries a PBR material: base colour, metallic-roughness, normal map
  (+ occlusion, emission). The owner chose **baked textures** over plain colours.
- `tools/build_site.py --check` allows links only to GitHub and fresing.nl outside the credits: the viewer script must
  be **stored in the site** (`site/vendor/…`, with its licence and a line in `site/CREDITS.md`), not loaded from a CDN.
- The repository is public (CLAUDE.md "Repository is public"): the landing page may only show an **openly licensed
  model** (the render kit's EVO / FarmBot / CEB press / Thor / OpenArm – check that the licence allows publishing the 3D
  model itself, not only pictures) or an **invented** one. **The Fresing 400 is not ready to be shown to the public in
  full (owner, 12 Nov): never put it, or any part of it, on the site or in a test, picture or report.** The milling
  video on the landing page only shows a basic interior. Never the employer's work either. The `--web-model` option
  exists for a model the owner sends later and explicitly releases for the site.

## Design the worker decides (write it in this file under "Design" before building)

- **Bake per look, not per part (lead's preference – measure first).** Many parts share one look; a per-part bake of
  3,000 parts would be huge and slow. Suggested: for each distinct look (material + its settings) bake small tileable
  maps (base colour, roughness, metallic, normal for the marks/orange peel) once, and give every part box-projected UVs
  in mm so the texture lands at the same scale as in the renders. Per-part bakes only where the look depends on the
  part itself: decals, painted faces, wear edges if kept, cut faces with tool marks. Say what is lost (e.g. wear on
  edges, anisotropic sheen – glTF's anisotropy extension: check whether Blender's exporter and model-viewer support it).
- **Size budget:** one Texture size choice (512 / 1024 / 2048), JPG/WebP for colour, mesh compression (Draco or
  meshopt – whichever model-viewer reads and Blender writes; 0069 saw no gain from Draco in the bpy module, check in
  real Blender), optional triangle reduction for small parts (bolts). Targets to measure, not promises: test mill
  < 5 MB, the 3,000-part Heavy model < 40 MB, the cable-lay demo said in the report.
- **What goes in:** the visible parts as shown (hidden parts, Show only, cutaway – decide and say), the current pose;
  surroundings off (a floor shadow / environment from model-viewer instead). Part names: the app's display names, or
  "Part 1…" with a tick "Hide part names" (customers should not see internal part numbers – default on).
- **Motion (only if cheap):** rigid parts' motion of one saved animation as glTF animation (object keys); otherwise
  leave as a follow-up. Material removal, chips, coolant, hoses (0058) and vessel motion are not exported.

## Design (worker, 12 Nov 2026)

Measured first (web machine, 4 cores, bpy 5.2.3, test mill): Cycles bakes one object per pass over the *whole* target
image, so 8 looks as 8 planes into one atlas took 18 s at 1024 px; the same as **one** object with one quad per tile
took 3–5 s for 9–16 tiles. So: one bake object, one bake call per atlas (at most 4096 px square).

- **Own GLB writer** (`core/web3d.py`, plain Python + NumPy), not Blender's exporter: the project is never changed (no
  UV layer or material swapped on the owner's meshes), copies of a part share one glTF mesh, names are under our
  control (Hide part names), normals as int8 (`KHR_mesh_quantization`, three.js and Blender read it), no Draco (it
  would need a decoder from Google's CDN: the viewer page must work offline). Blender Z-up -> glTF Y-up by one root node.
- **Bake per channel source, not per part.** For every material on a visible part, each Principled input (Base Color,
  Alpha, Roughness, Metallic, Normal) is either a constant (-> glTF factor, no texture) or fed by nodes. Fed inputs
  get a *signature* of the nodes upstream; equal signatures are baked once (all paint_satin colours share one orange
  peel normal map). Each source is one tile: a 0.2 m square, `Texture size` px, wired into an Emission shader on a
  quad of the one bake object (the normal as n*0.5+0.5). A tile that comes out flat (spread < 1/255) becomes a factor.
  Tiles are made seamless (cross-fade with a half-shifted copy) and saved as JPG (colour PNG when it has holes).
- **UVs:** box projection per triangle in the part's own axes (metres / 0.2 m), so the texture has the renders' scale
  and moves with the part; right-handed U/V per side.
- **Decals** are baked one by one (their own UVs, colour + alpha, clamped), as transparent meshes on their part.
- **What goes in:** parts and decals visible in the view (hidden parts, Show only: left out), at the current frame
  (pose); surroundings, tool copies, chips, coolant, hoses: not. Cutaway and X-ray look: whole, opaque parts.
- **Lost in the web model** (said in the panel and guide): edge wear and corner dirt (they come from the part's own
  shape), the anisotropic sheen of brushed / ground / turned metal (glTF's anisotropy needs per-part tangents),
  tool marks on cut faces, sub-pixel machining marks. Kept: colours, gloss, metal, orange peel, cast/blasted bump,
  coat (`KHR_materials_clearcoat`), glass (`KHR_materials_transmission`), lights (emission), grids with holes, decals.
- **Hide part names** (default on): nodes "Part 1…", meshes "Mesh 1…", materials "Look 1…".
- **Animation** (tick, only when an animation is built): the world place of every moving part sampled per frame
  (translation + rotation, linear), one glTF animation.
- **Viewer page:** `<name>.html` = one file: model-viewer 4.4.0 (Apache-2.0, `fresing_render/web/`, the UMD build with
  three.js and lit inside) inlined, the GLB inlined as base64 and handed over as a Blob URL (fetch of file:// fails).
- **Work in the window:** a modal operator steps a generator (collect, bake batches, meshes, animation, write) with
  progress and Cancel/Esc; files are written to a temporary name and renamed at the end.
- **Website:** the landing page stays script-free (its `--check` rule): a "Turn it yourself" section with a poster
  picture links to `model/index.html`, a small viewer page that loads `vendor/model-viewer-umd.min.js` and
  `media/<model>.glb` only when opened. `build_site.py --web-model <glb> --model <id>` swaps the model.
  Site model: an invented one (the app's own test/demo models) – never the Fresing 400.

## Done when

- [ ] 5 Scene & Render > **Web 3D model**: Texture size, Hide part names, (Include animation if built), **Export…** →
      `<name>.glb` + `<name>.html` (one file: model-viewer inlined or next to it in a folder – the owner must be able to
      email or upload it and open it offline in a browser), a line with size, triangles, textures, time. Tooltips.
- [ ] Looks: a render of the app's view and a model-viewer screenshot (headless Chromium if available on the web
      machine, else three.js / Blender re-import of the GLB) of the test mill side by side in `tasks/img/`; base
      colours within a small tolerance on flat lit areas; paint schemes: the active scheme is exported.
- [ ] Measured: export time and file size for the test mill, the Heavy model and the demo vessel at each texture size.
- [ ] Scripts off, the queue not needed (export runs in the window; a big model shows progress and can be cancelled).
- [ ] Website: `tools/build_site.py` puts a "Turn it yourself" section with one openly licensed (or invented) model on
      the landing page; `--check` passes (vendored viewer, credits); `--web-model <file.glb> --model <id>` swaps in a
      model the owner sends later and releases for the site (like `--take`; not the Fresing 400 – see Background). The page still loads fast (model loads only when scrolled to / clicked).
- [ ] Tour stop "Web 3D model", PC-check line `web3d.export`, guide section with a picture.
- [ ] Tests added; GitHub green; report filled in; merge to main and release.

## Not in this task

AR on phones (USDZ for iPhone), a web configurator, hoses/flex parts (0058), changes to the 0046 looks themselves
(0098 is in the Looks lane at the same time – read their materials, do not edit `materials.py`; if a hook is needed
there, say so in the report).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, branch `claude/elegant-fermat-u6q25p`, 12 Nov 2026. Released as 0.2.77.

**What changed:**
- New panel **5 Scene & Render > Web 3D model** (`blender/web3d.py`, `ops_web3d.py`, `ui_web3d.py`, `core/web3d.py`,
  `props.FRWeb3D`): Texture size 512/1024/2048, Hide part names (default on), Include animation (only with a built
  animation), **Export…** (file window, progress + Cancel/Esc in the panel) → `<name>.glb` + `<name>.html`, a result
  line (size · triangles · pictures · time) with Open page / Show in folder. Design: see "Design" above.
- Own glTF 2.0 writer (no Blender exporter, the project is never changed): copies share one mesh; 16-bit points
  (steps ≤ 0.05 mm, ≤ 1 mm on big parts without decals), 16-bit UVs in 1/128 tile + `KHR_texture_transform`, 8-bit
  normals (`KHR_mesh_quantization`); UVs only on meshes whose looks have a picture; identical looks merged (names
  hidden). `core.web3d.problems()` checks a file against the glTF rules that matter to a viewer.
- Baking: every Principled input fed by nodes is baked once per node signature (paint colours share), as quads of
  ONE object into one atlas (≤ 4096 px), after a 48 px look that drops inputs that are one number (normals probed at
  the final pixel size). Bevel/AO (wear, dirt) get their flat values in the bake copy. Tiles made seamless
  (cross-fade with a half-shifted copy, spread kept). Decals baked on their own UVs (PNG with alpha, clamped).
- **Bug found and fixed in the real app:** creating the bake scene and switching it to Cycles froze Blender while a
  material preview rendered (Blender waits for the preview thread, which needs the Python lock). The bake scene is
  now a copy of a Cycles scene, emptied (test + CLAUDE.md section 8).
- Viewer page: model-viewer 4.4.0 (Apache-2.0, UMD build with three.js + lit) in `fresing_render/web/`, inlined with
  the model as base64 → one file that opens offline (file:// cannot fetch a separate .glb). Start view = the app's
  Iso view (45°, 65°).
- Website: the landing page stays script-free; new section **Turn it yourself** (poster → `model/index.html`, which
  loads `vendor/model-viewer-umd.min.js` and `media/test_atc.glb` only when opened). Model: the invented test mill
  with the double-arm tool changer (`tools/make_test_atc.py`, 0.36 MB). `build_site.py --web-model <glb> --model <id>`
  swaps it (poster made with headless Chromium, `tools/web3d_shot.js`), `--check` checks the viewer page (only own
  files, viewer + licence there, model valid and ≤ 15 MB, credited) and refuses `fresing_400` ids.
- Tour stop "Web 3D model" (crane set, exports next to the tour); PC check lines `web3d.export` (Full) and
  `heavy.web3d` (Heavy); guide section + `docs/img/panel_5_web3d.png`; MIN_LINES_FULL 59, HEAVY 14, TOUR 44.

**Tested and measured** (web machine, 4 cores, no graphics card, bpy 5.2.3; files read back with `core.problems`,
0 problems everywhere):

| Model (import quality) | Texture size | File | Export time | Peak memory |
| --- | --- | --- | --- | --- |
| Test mill, 9 parts, 2,693 triangles (Normal) | 512 / 1024 / 2048 | 0.1 / 0.3 / 1.0 MB | 0.4 / 2.5 / 14.8 s | 0.5 / 1.3 / 3.8 GB |
| Heavy, 2,992 parts (600 unique), 8.2 M triangles shown, 2.26 M unique (Normal) | 512 / 1024 / 2048 | 34 / 35 / 35 MB | 3.3 / 4.2 / 9.6 s | 1.2 / 1.3 / 2.6 GB |
| Demo vessel, 1,261 parts, 1.93 M triangles (Normal) | 512 / 1024 / 2048 | 22 / 23 / 25 MB | 4.4 / 12.9 / 49 s | 1.4 / 4.2 / 5.5 GB |
| Demo vessel (Draft, 0.79 M triangles) | 512 / 1024 | 6.9 / 7.5 MB | 2.9 / 11.6 s | 1.3 / 4.0 GB |
| Every library look (48, wear 0.3) on test-machine copies | 1024 | 2.1 MB, 30 pictures | 27 s | – |

  Before the size work the Heavy file was 53 MB and the demo 27–30 MB (32-bit points and UVs on every mesh).
  The viewer page is 1.1 MB (viewer) + 4/3 × the file. Headless Chromium with software GL showed the test mill page in
  2.4–3.5 s and the Draft demo page in 11 s. Looks: `tasks/img/0099_looks.jpg` – left a Cycles render of the test mill
  (app's Iso camera, 64 samples), right the browser view from the same camera: colours and gloss agree; base
  colours equal the materials' exactly (test, within 1/255 sRGB); polished steel looks darker in the browser (it
  mirrors model-viewer's own room light, not the app's studio). Paint schemes: the active scheme is exported (test).
  In the real app (xvfb): Export in the window with progress, Cancel → no file and no leftovers, a second export
  writes both files. New tests: `tests/test_web3d_core.py` (16), `tests/test_web3d.py` (13), `test_site.py`
  (+1); the tour stop and both PC-check lines run locally. Subagents: none. No Windows-only code (no independent
  review needed); JPG pictures are written by Blender itself.

**GitHub runs:** branch run 43331545895 green at the first try (20.2 min; suites 2 and 3 flagged SLOW: 10.1 and
19.8 min against 4.6 and 8.8 usually – not looked into). `main` fast-forwarded to it (mode reuse): 0.2.77 published,
the old-version update check passed, offered to the apps. Its **Landing page** job failed: the Pages runner's bare
Python had no numpy, which `build_site.py` now imports through `core/web3d.py` (and `tee` hid the error until the
upload). Fixed in `pages.yml` (numpy installed, `shell: bash` with pipefail) + a test; branch run 43334976404 green,
`main` fast-forwarded (reuse). The Pages run of that push built fine but GitHub's publish step timed out getting its
token (GitHub side); a re-run of the job cannot publish (two artifacts of one name in a run), so the page was
published with a fresh run by hand (Actions → Landing page → Run workflow): run 43337972621, green. 3 runs in all.
Note for the lead: pytest group 3 now takes ~19.5 min, set by `test_demo_project.py::test_no_clash_in_the_animation`
(781 s since task 0097) – the longest job of every run.

**Open points / follow-up tasks:**
- The site shows the invented tool-changer test mill. The invented cable-lay demo vessel also works well (6.9 MB at
  Draft + 512) but is **not** on the site: its deck was laid out with the owner (task 0084) – the owner decides
  (`--web-model`). Never the Fresing 400.
- Lost in the web model (said in the panel and the guide): edge wear and corner dirt, the anisotropic sheen of
  brushed/ground/turned metal, paint's orange peel (0.3° tilt – below one step of an 8-bit normal map), tool marks,
  the cutaway and X-ray look; also app-made objects (G-code tool copies, chips, coolant, hoses) – only parts and
  decals go in. Animation: rigid parts' places per frame.
- Big files: a mesh compression (meshopt) would roughly halve the Heavy and demo files, but model-viewer fetches its
  decoder from Google's CDN; it would have to be inlined (follow-up if the owner wants big models online).
- Memory at 2048 px on big models (5.5 GB on the demo vessel): baking in smaller atlases would lower it (follow-up
  if it matters on the owner's PC).
- Owner, on his PC after the update: open a project, 5 Scene & Render > Web 3D model > Export…, then Open page; try
  the page on a phone (e-mail it to yourself).
