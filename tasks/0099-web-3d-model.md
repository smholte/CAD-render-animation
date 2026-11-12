# 0099 – Web 3D model: export the machine with baked textures, turn it on the website (study 0069 #15)

**Who:** worker · **Status:** open · **Branch:** `task/0099-web-3d-model`
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

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
