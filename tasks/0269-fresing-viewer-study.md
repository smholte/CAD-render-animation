# 0269 – Study (findings + design only): Fresing Viewer – a stand-alone viewer for STEP (and more) that works and looks like Fresing Render's exported 3D page, with a round trip to Fresing Render through ToolBox

**Who:** worker · **Status:** done (findings only) · **Branch:** `task/0269-fresing-viewer-study` (findings only, `[skip ci]`)
**Started by:** lead, 21 Nov 2026 (owner 16:59–17:09: "a viewer that opens a STEP file directly – yes, but the exported
3D web viewer from Fresing Render stays its own offline file with all functions included"; "a ToolBox tool, with its own
licence"; "I want to keep the same working and looks as the exported 3D viewer"; round trip: pictures, videos and a
baked 3D page all come back; this lead builds it, with ToolBox integration like Fresing Render's; its own page with a
direct button to Fresing Render and back, other tools in a fold-down; formats: STEP and Fresing Render's own 3D page
first, then IGES, STL / 3MF / OBJ, glTF / GLB – "try to keep measuring and other functions for the other formats")
· **Model:** Opus · effort High
**Area:** only `tasks/0269-fresing-viewer-study.md` (this report) and `tasks/img/0269_*` (small pictures); a throw-away
prototype on the branch is allowed (never merged). No app code, no `site/`.

## Goal

The owner and the lead get a clear plan for **Fresing Viewer** before anything is built: what it is, how it opens each
format, how it stays the same as the exported 3D page, how it talks to Fresing Render through ToolBox, where it lives,
its licence, and 3–6 build tasks in order with sizes.

## Background

- **The exported 3D page** (Web 3D lane, `fresing_render/web/fr_page.js`, `fr_player.js`, `core/web3d.py`): one
  offline HTML file per model with baked light, motion, settings menu, part tools (click a part, measure points /
  planes / Ø / centre to centre), slice by face or X / Y / Z (0218), measuring labels + edges (0219), Film (0252), phone
  layout (0179). It stays as it is: the Viewer is a separate tool.
- **ToolBox** (`smholte/ToolBox`, `smholte/toolbox-format`, MIT): tools on one PC hand files to each other through a
  `Toolbox` folder (manifests, inboxes, jobs). Fresing Render already has its inbox (`core/toolbox.py`,
  `blender/toolbox_inbox.py`) and the House Planner round trip (0114, 0217) – the model for this round trip. The
  ToolBox lead planned a `view-step` step after its router: this Viewer replaces / fills that – read their task list.
- **House Planner** (https://smholte.github.io/house-planner/) is a browser app that already writes to and reads from
  the Toolbox folder (PC Chrome / Edge) – the closest example of a web tool in ToolBox.
- **Licence:** the Viewer has its own licence (owner). The exported page's player code is the owner's own (no outside
  code was ever accepted), so it may be reused under the Viewer's licence – say how to share it without two copies
  drifting apart (a small shared package, or the Viewer as the source the app copies, or …).
- **Never** the Fresing 400 or anything of the owner's employer as a sample.

## Questions to answer

1. **Formats, in the owner's order:** STEP (AP203 / 214 / 242: assembly tree, names, colours) and **Fresing Render's
   own 3D page** (open its model in the Viewer with its looks and motion) first; then IGES; STL / 3MF / OBJ; glTF / GLB.
   For each: reader (e.g. OpenCascade compiled to WebAssembly – occt-import-js, opencascade.js – its licence, size,
   load time; three.js loaders for meshes), what is lost (exact faces, units, assembly, colours).
2. **Measuring and the other tools on every format:** on exact CAD (STEP / IGES) – true faces, planes, cylinders; on
   meshes – fitted planes / cylinders, edges from angles; what works, what is approximate, how the page says so.
3. **Same working and look as the exported page:** which parts of `fr_page.js` / `fr_player.js` carry over, what is
   new (file open, assembly tree, big-file progress), and how both stay in step.
4. **Speed and size:** a 2,000-part STEP of ~80 MB (use an openly licensed one, e.g. the Thor STEP built by
   `tools/a4_to_step.py`, or the EGR-like public GrabCAD class of model) – time to first picture and memory on the web
   machine; the Viewer page's own size.
5. **Round trip through ToolBox:** "Send to Fresing Render" → which job (model + settings: a still, a turntable, a
   video, a baked 3D page) → Fresing Render does it → **pictures, videos and the baked 3D page** come back and show in
   the Viewer. Which toolbox-format messages are new (a format change goes to the ToolBox lead through the lead post –
   list it, do not send it); what the Viewer needs from Fresing Render's inbox.
6. **Where it lives and runs:** its own public repository (name proposal), a page on GitHub Pages now
   (later perhaps viewer.fresing.nl), works offline after the first visit (installable page?), Chrome / Edge / Firefox
   / Safari and phone – what works where (the Toolbox folder needs the File System Access API: which browsers).
7. **Its page and links:** a landing page like Fresing Render's (0267 style: light, mono labels, numbered cards),
   direct buttons Fresing Render ↔ Fresing Viewer, "More tools" fold-down (House Planner); the app mark (brand rule:
   F + lowercase initial – "Fv"? check the Brand Specification's rule and say it needs the owner's and the Fresing
   lead's OK).
8. **Task split:** 3–6 build tasks in order, each with model · effort, what it delivers, what it waits for.

## Done when

- [x] Report with answers 1–8, a table of formats × functions (works / approximate / not), measured numbers, sizes
- [x] Proposals that need the owner marked **Owner decides** (repository name, licence, app mark, browsers)
- [x] Nothing merged to `main` except this file and its pictures (lead merges the report or the worker pushes it with
      `[skip ci]`)

## Not in this task

Building the Viewer; changing toolbox-format (only a list); the landing page (0267); the exported 3D page.

---

## Report (filled in by the chat that did the task)

**Chat / date:** worker, Claude Code on the web (4 cores, no graphics card), 21 Nov 2026. Branch
`task/0269-fresing-viewer-study`; the throw-away prototype stayed on the web machine (not committed – it was 40 lines of
plain test code around the reader).

### In short

- **It can be built, and the 3D page code carries over almost whole.** The exported page's controls, part tools,
  measuring, slice, labels and phone layout are generic; only the baked light, motion, Film, tubes and sea need
  Fresing Render's data. One change in Fresing Render first: the page must take its model from a function call, not
  only from inside its own HTML file.
- **STEP in the browser works today** with **occt-import-js** (OpenCascade in WebAssembly, LGPL-2.1, 3.1 MB to
  download). Measured in Chromium on this machine: a small model 2.7 s, a 3,000-part model (22.6 MB) **91 s**, a
  2,088-part model of **78 MB 150 s**, about **2.7 GB** memory. Too slow as it comes: it meshes every copy of a part
  again and hands everything over at the end. **A modified build** (mesh each part once, parts shown as they come,
  face types out, several helpers) is the first real build task; expected 4–5 × faster (one measurement below).
- **Exact measuring on STEP works without new maths:** the reader keeps each CAD face as a block of triangles, and its
  points lie on the true surface – the diameters fitted from them came out exact (Ø6, Ø13.2, Ø190 … off by
  < 0.00001 mm). On STL / OBJ the faces must be guessed from angles: 91 % of the test mill's faces were found whole.
- **Fresing Render's own 3D page opens with everything** (looks, motion, Film, exact measuring) – the Viewer is the
  same player.
- **The round trip needs no change to the toolbox format**: new *actions* in the two tools' manifests, Fresing
  Render's 3D page as Fresing Render's own file type, render settings in the job's `options`. Two small additions are
  worth asking the ToolBox lead for (video and 3MF/IGES as built-in types) – listed, not sent.
- **Five build tasks** (section 8), the first two in Fresing Render and the new repository side by side.

### 1. Formats

| Format | Reader | Size to load | Kept | Lost |
| --- | --- | --- | --- | --- |
| **STEP** AP203 / 214 / 242 | occt-import-js 0.0.23 (Viktor Kovács, LGPL-2.1, OpenCascade inside) – later our own modified build of it | 7.6 MB wasm = **3.1 MB gzipped** + 97 KB | exact CAD faces (as triangle blocks), names, colours per part and per face, the tree (depth kept, see note), units → mm | the face *type* is not handed out (plane / cylinder …: fitted, see 2); edges are not handed out; copies of a part are not shared (each copy meshed again) |
| **Fresing Render 3D page** (`.html`) | the page itself: its `fr-env` settings and `fr-glb` model (gzip + base64) read out of the file | nothing extra | everything: looks, baked light, motion, Film, labels, exact measuring data (`fr_faces`), views | nothing |
| **IGES** | occt-import-js (`ReadIgesFile`) | same as STEP | exact faces (948 of 948 faces of the test mill made into IGES, 1.9 s) | as a rule no names, no tree, colours only when the CAD wrote them (our test file had none) |
| **STL** | three.js `STLLoader` (MIT, in the bundle) | ~10 KB | triangles | names, colours, units (taken as mm, a switch mm / m / inch), parts (one STL = one part), CAD faces |
| **3MF** | three.js `3MFLoader` (+ fflate, MIT) | ~40 KB | parts with names, components (a tree with places), colours / materials, units in the file | CAD faces |
| **OBJ** (+ MTL) | three.js `OBJLoader`, `MTLLoader` | ~30 KB | objects / groups with names, colours from the MTL | units, the tree (flat), CAD faces |
| **glTF / GLB** | three.js `GLTFLoader` – the one the page already uses | already in the page | tree, names, PBR materials, animations, metres | CAD faces – **unless** it is a `.glb` written by Fresing Render (then `fr_faces` is in it: exact) |

Notes: the reader's result keeps the assembly's depth only partly (the invented 3,000-part machine came back with 2
levels); our build should hand out the full tree with copies (section 8, V2). A STEP **wider than 4 GB of memory**
cannot be read by any WebAssembly reader in a 32-bit page; Chrome and Firefox have a 64-bit mode since early 2025,
Safari not (from the browsers' notes, not tried).

Other readers looked at: **opencascade.js** (LGPL-2.1, the whole OpenCascade, 67 MB package; a custom build can be
smaller but needs its own build pipeline) – more than we need. **Online 3D Viewer** (3dviewer.net, MIT, same author as
occt-import-js) is the prior art: it uses occt-import-js the same way; the Viewer keeps our own look and tools instead.

### 2. Functions × formats

✓ works as on the exported page · ≈ approximate (the page says so) · – not possible

| Function | STEP / IGES | Fresing Render page / its .glb | glTF / GLB (other) | 3MF | OBJ | STL |
| --- | --- | --- | --- | --- | --- | --- |
| Turn, zoom, views, studio light, shadows, quality / Auto | ✓ | ✓ (+ its sky, sea, baked light) | ✓ | ✓ | ✓ | ✓ |
| Part click + Part info (name) | ✓ | ✓ | ✓ | ✓ | ✓ (object) | ≈ one part |
| Assembly tree (new) | ✓ | – (the page has a flat list) | ✓ | ✓ | flat list | – |
| Measure: points, distance | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Measure: flat face, angle, distance between faces | ✓ exact (fitted on the true face) | ✓ exact | ≈ face from angles | ≈ | ≈ | ≈ |
| Measure: Ø, axis, centre to centre | ✓ exact | ✓ exact | ≈ | ≈ | ≈ | ≈ |
| Edges (line / circle) for labels | ✓ fitted on the face borders (as the app's `web3d_faces.edges` does) | ✓ | ≈ from sharp angles | ≈ | ≈ | ≈ |
| Slice by face or X / Y / Z, fade the rest | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ (slice by X / Y / Z; by face ≈) |
| Motion, Film, cables, sea, baked light | – (none in a STEP) | ✓ | animations ✓ | – | – | – |
| Colours | ✓ | ✓ | ✓ | ✓ | ✓ (MTL) | – (one grey) |
| Units | ✓ | ✓ | ✓ (metres) | ✓ | asked (mm default) | asked (mm default) |

**How "exact" was checked (test mill, 948 CAD faces, read by occt-import-js):** 904 flat, 36 cylinders, 8 others
(cones, fillets). The cylinders' diameters fitted from their own points: Ø6, 10, 12, 13.2, 16, 18, 20, 36, 48, 50, 58,
80, 86, 94, 100, 116, 170, 178, 190 – largest error 3.5 × 10⁻⁹ mm. So a modified reader is not needed for exactness;
it only makes cones / tori / spheres sure (their type comes from OpenCascade instead of a fit).

**How "approximate" was checked:** the same mill as a plain triangle soup (what an STL gives), faces grown where
neighbouring triangles differ by less than 15–30°: **865 of 948 CAD faces found exactly** (91 %), 34 regions ran
over two or more CAD faces (a hole into its fillet, two faces that meet flat). On meshes the page marks a found face
"≈ from the mesh" and shows a measured Ø with "≈"; points and distances between points stay exact.

### 3. Same working and look – what carries over

From the map of `fresing_render/web/` (all hand-written, no build step, one HTML file per export):

| File | Size | In the Viewer |
| --- | --- | --- |
| `three-viewer.min.js` (three.js r180 bundle) | 796 KB | as is, plus STL / OBJ / MTL / 3MF loaders in the same bundle (`tools/build_web_viewer.py`, one entry line each) |
| `fr_page.js` (scene, loader, orbit, sky, quality, views, Film, baked light) | 132 KB | as is, **after one change**: today it reads `#fr-env` / `#fr-glb` from its own HTML at start (fr_page.js:2346–2385); it needs a call `frPage.open({gltf or scene, settings})` that the exported page uses for itself and the Viewer for every file |
| `fr_player.js` (gear menu, playback, views pill, help, phone layout) | 78 KB | as is; the Viewer adds its own items through the same menu |
| `fr_tools.js` (Part info, Measure, Slice, Fade, labels) | 74 KB | as is; reads the face data `{runs, rows, edges}` per mesh – the Viewer writes the **same structure** from the reader's face blocks (a JavaScript copy of `core/web3d_faces.py`: classify, fit, pack) |
| `fr_measure.js`, `fr_math.js`, `fr_tubes.js` | 40 KB | as is |

**New in the Viewer:** the start screen (drop a file / Open… / recent files), the file readers and their helper,
a progress bar with part counts and Cancel, the assembly tree (show / hide / isolate, search), a units switch for STL /
OBJ, "Send to Fresing Render", the results shelf (pictures, videos, 3D pages that came back), the Toolbox folder bar.

**How both stay in step (Owner decides, with the licence):**
- **Proposal A (recommended): Fresing Render stays the source** of the player files (they are tested there every day
  with real exports). The owner marks those files "GPL-3.0-or-later **or MIT**" (he wrote them all – no outside code
  was ever accepted – so he may dual-licence his own code). The Viewer keeps a pinned copy (`player/`, with the Fresing
  Render version it came from) and a test that fails when its copy differs from the pinned tag; one command copies the
  newer files. The same way Fresing Render already pins the toolbox format's code (`tests/data/toolbox/tbf-v0.1.1`).
- Proposal B: a third small repository "fresing-3d-player" (MIT) that both copy. Cleaner on paper, but a third place to
  test and release; not worth it for two users.
- Rule for both: Viewer-only code lives in its own `fv_*.js` files and talks to the player only through `frPage`'s
  hooks (`listeners`, `beforeDraw`, `partTools`) – never by editing the copied files.

### 4. Speed and size (measured on the 4-core web machine; Chromium headless, software drawing)

Test models: the PC check's invented machine (`pccheck/heavy_scene.py`, no real design) – 3,000 parts (600 different)
and a 2,100-different-parts version of **77.7 MB** (2,088 placed, like the EGR line's 78 MB / 2,789 placed). Thor's
STEP was not used (needs its sources cloned); the invented machine is the same size class.

| Model | File | Parts (meshes) | Triangles | Browser: drop → first picture | Of that: reading | Memory (peak) |
| --- | --- | --- | --- | --- | --- | --- |
| Test mill | 2.8 MB | 44 | 6,800 | **2.7 s** | 2.5 s | small |
| Invented machine, 3,000 placed / 600 different | 22.6 MB | 2,992 | 1.9 M | **91 s** | 90 s | ~1.1 GB (Node) |
| Same 600 different parts, each placed once | 21.0 MB | 829 | 1.2 M | 36 s (Node) | – | 0.8 GB (Node) |
| Invented machine, 2,088 placed / 2,100 different | **77.7 MB** | 3,175 | 5.0 M | **150 s** | 148 s | **~2.7 GB** (all browser processes) |

- Building the three.js scene and drawing the first picture took **0.3–0.4 s** even for 5 M triangles; all the time
  is the reader. While it reads, the page shows nothing new: the reader gives no progress and no parts until the end.
- **For comparison, OpenCascade natively** (Python, one core, same machine): 3,000-part file 13.6 s (read 1.5, transfer
  3.2, mesh 8.9), 78 MB file 49 s (read 5.3, transfer 11.8, mesh 32.1). The app's own import of the EGR line was
  40–52 s (docs/DEVELOPMENT.md).
- **What a modified reader saves (expectation, from the rows above):** meshing each different part once – the 3,000-part
  file read like its 600-part twin, **91 → ~30 s**; meshing on 3 helpers beside the main reading, the 78 MB file
  **150 → ~60–70 s** here, less on a 24-core PC; parts appear as they are meshed, so the first parts show after the
  reading + transfer (~25 s here for 78 MB). To be measured in task V2.
- **The Viewer page itself:** player + three.js ≈ 1.0 MB (≈ 0.3 MB gzipped); the STEP / IGES reader 3.1 MB gzipped,
  loaded only when such a file is opened, then kept offline.

### 5. Round trip through ToolBox

**Two ways, both without a format change:**

1. **"Make it in Fresing Render" (unattended)** – the Viewer sends the model and Fresing Render sends the results back:
   - Viewer → Fresing Render: a job with the STEP, action **`make`** (new in Fresing Render's manifest; accepts `step`;
     returns `png`, `jpeg`, `ext:mp4`, `nl.fresing.render.page`), `return: "show-results"`, and in `options`: what to
     make (`still` / `turntable` / `page`), the view (eye, target, field of view – the Viewer's current view), size,
     light look, and the hidden parts.
   - Fresing Render: imports (as today's `import-step`), sorts parts and gives materials by its rules, sets the camera,
     makes each output, shows progress ("Turntable 34 of 120") in `status.json`, then one **reply job** with all files.
   - Fresing Render's 3D page comes back too; the Viewer opens it in place of the STEP (same player – now with baked
     light and exact measuring), and shows pictures and videos on a results shelf beside the model.
2. **"Open in Fresing Render" (to work on it)** – motion, a video with joints, labels: that needs the owner's hands.
   - Viewer → Fresing Render: today's action `import-step` (no `return`).
   - Later, in Fresing Render: **Make > Send to Fresing Viewer** writes a new job into the Viewer's inbox (action
     `show-results`, the files, `options.model` = the STEP's fingerprint so the Viewer puts them next to the right
     model). Allowed today: a tool may send jobs to any tool whose manifest accepts the types.

**The Viewer's own manifest** (`nl.fresing.viewer`, `kind: web`, `url` its page): actions `open-model` (accepts `step`,
`glb`, `gltf`, `stl`, `obj`, `nl.fresing.render.page`, `ext:igs`, `ext:iges`, `ext:3mf`) and `show-results` (accepts
`png`, `jpeg`, `ext:mp4`, `nl.fresing.render.page`). `sends: ["step"]`.

**What Fresing Render needs (its own tasks):** the `make` action in `core/toolbox.py` `ACTIONS` + `blender/toolbox_inbox.py`
(an unattended run: import → sort → camera from `options` → outputs → reply; "Make now" prompt as for the bake); its
own type `nl.fresing.render.page` in its manifest's `types` (detect: a marker near the top of every exported page – a
`<meta name="generator" content="Fresing Render 3D page">` in the head, added in task V1, so it is inside the 64 KiB
the format looks at); "Send to Fresing Viewer" in Make.

**List for the ToolBox lead (not sent – the lead sends it through the lead post):**
1. Built-in types worth adding (minor, additions only): **`mp4`** (by content: `ftyp` at byte 4 – a `head_matches`
   rule `ftyp(isom|iso2|mp41|mp42|avc1)` works today), **`3mf`** (`zip_has` `3D/3dmodel.model`), **`iges`** (extensions
   `.igs`, `.iges`; no sure content rule – extension only). Until then `ext:mp4`, `ext:3mf`, `ext:igs` work.
2. Nothing else: `options` already belongs to the receiving tool, `returns` takes several types, a reply carries
   several files, progress and cancel exist. Build on **format 0.2** (waiting for its tag, ToolBox task 0011).
3. ToolBox's router (step B, its task 0006) can offer "Fresing Viewer" for a dropped `.step` like any web tool. No
   `view-step` step was found in ToolBox's `TASKS.md` or `docs/step-b-router.md` (perhaps only in the lead post): the
   ToolBox lead should drop it in favour of this Viewer.

### 6. Where it lives and runs

- **Repository: `smholte/fresing-viewer`, public** (Owner decides the name). Plain HTML / JavaScript, no server;
  the only build step is the three.js bundle and the reader's WebAssembly (both committed, as Fresing Render does).
- **Page: `https://smholte.github.io/fresing-viewer/`** now; `viewer.fresing.nl` later is one DNS line + a `CNAME`
  file. Note: under `smholte.github.io` it **shares the Toolbox-folder permission** with House Planner and Fresing
  Render's site (format section 9: permission belongs to the site) – fine, all three are the owner's; on its own
  domain it asks once more.
- **Offline after the first visit:** a service worker keeps the page and, after the first STEP, the reader. It can be
  **installed** as an app (Chrome / Edge: "Install Fresing Viewer"); an installed app also **opens `.step` files from
  Explorer** (web-app file handlers) and keeps the Toolbox-folder permission by itself.
- **Browsers** (from the browsers' own notes, not all tried here – only Chromium was run):

| | Open files (drop / Open…) | STEP / IGES | Big STEP (2–3 GB memory) | Toolbox folder (send / results) | Install, open from Explorer |
| --- | --- | --- | --- | --- | --- |
| Chrome / Edge on a PC | ✓ | ✓ (measured, Chromium) | ✓ up to 4 GB | ✓ | ✓ |
| Firefox on a PC | ✓ | ✓ | ✓ up to 4 GB | – (no folder access) | – |
| Safari on a Mac | ✓ | ✓ | smaller limit | – | – |
| Phone / tablet | ✓ (file picker) | small models only | – | – (format: no Toolbox folder on a phone) | add to home screen |

  Where the folder is missing the Viewer hides "Send to Fresing Render" (as the format says) – everything else works.

### 7. Its page and links

- **Landing page** in the 0267 style (light, mono section labels, numbered cards, cut-corner green button): what it
  opens, "Measure on the real CAD faces", "Send to Fresing Render", which browsers; the Viewer itself one click away
  ("Open a file").
- **Tool switcher:** direct buttons **Fresing Render ↔ Fresing Viewer**, "More tools ▾" with House Planner – the same
  `site/tools.json` list 0267 makes; the Viewer gets one line there (`direct: true`) once its page exists, and its own
  copy of the list (one small file).
- **App mark (Owner decides, with the Fresing lead):** by the rule in ToolBox task 0004 ("F + the app's lowercase
  initial") it is **"Fv"** – the F unchanged, a **v** drawn new to the word mark's construction (as the t of "Ft"),
  white on the Deep Charcoal square with the green swoosh. The rule's source, the Brand Specification §4.6–4.7 in
  `smholte/Fresing`, was **not read** (not in this session's repositories): the Fresing lead checks it.

### 8. Build tasks, in order

| No. | Where | What it delivers | Model · effort | Waits for | Size |
| --- | --- | --- | --- | --- | --- |
| **V1** | Fresing Render, Web 3D lane | `frPage.open({...})`: the page loads a model from a call (the export calls it for itself – no visible change); the player files marked "GPL-3.0-or-later or MIT"; the generator meta tag; a JavaScript copy of `web3d_faces` classify / fit / pack (`fr_faces.js`, tested against the Python on the test models); STL / OBJ / 3MF loaders in the three.js bundle | Opus · Medium | **0256** (it edits `fr_page.js`); the owner's licence answer | M |
| **V2** | new repo `fresing-viewer` | the reader: occt-import-js **forked** (LGPL-2.1 stays, its source public in our fork) and changed – each different part meshed once + copies, typed arrays, the full tree, face types / axes / radii, progress per part, parts handed out as they come; 3 helpers; measured on the two invented machines (target: 78 MB first parts < 40 s, all < 80 s on the web machine) | Opus · High | – (may run beside V1) | L |
| **V3** | `fresing-viewer` | the Viewer: start screen, open / drop, all formats of section 1, the tree, the player copied from V1 with its pin test, measuring with "≈" on meshes, progress + Cancel, offline + install + file handlers; tests in Chromium on Fresing Render's test models and the invented machines | Opus · High | V1, V2 | L |
| **V4** | Fresing Render, Toolbox lane | the `make` action (still / turntable / 3D page, unattended), its own page type, "Send to Fresing Viewer" in Make, tests with a stand-in Viewer (as the House Planner stand-in) | Opus · Medium | V1 (meta tag); format 0.2 pinned | M |
| **V5** | `fresing-viewer` | Toolbox: the Viewer's manifest and inbox (format 0.2 code copied as House Planner does), "Send to Fresing Render" with the view, the results shelf, opening a returned page in place; the owner's round-trip test on his PC (Edge) | Opus · Medium | V3, V4 | M |
| V6 | `fresing-viewer` site | landing page, Fv mark, tool switcher both ways; the Viewer line in Fresing Render's `site/tools.json` | Sonnet · Low | V3; the mark approved | S |

V1 and V2 can start together; V4 can start after V1. The owner's first look at a working Viewer is after V3.

### Owner decides

1. **Licence** of the Viewer (recommended: **MIT**, like ToolBox and the toolbox format; the reader stays LGPL-2.1 as
   a separate file, which MIT allows) – and whether the player files of Fresing Render become "GPL-3.0-or-later or
   MIT" so the Viewer may use them (Proposal A in section 3).
2. **Repository name** `smholte/fresing-viewer` (public) and the address (GitHub Pages now; `viewer.fresing.nl` later?).
3. **App mark "Fv"** – with the Fresing lead (Brand Specification).
4. **Browsers:** Chrome / Edge on a PC fully; Firefox / Safari open and measure but cannot send to Fresing Render;
   phones only small models – OK?
5. **Unattended "Make it in Fresing Render"**: may Fresing Render sort parts and give materials by its rules without
   asking (one "Make now" click as for the bake), or should it always open the project for the owner first?

**What changed:** this task file only (the report). TASKS.md: 0269 done, the Viewer lane's next steps.

**Tested and measured:** see section 4 (web machine, 4 cores, Chromium headless with software drawing, Node 22;
models: Fresing Render's test mill and the PC check's invented machine at two sizes, written for this task, not
committed). The prototype page (a helper running occt-import-js + three.js r180, first picture timed) and the fit
scripts were throw-away and are not in the repository.

**Open points / follow-up tasks:** V1–V6 above. Not measured: the owner's PC (24 cores, RTX 3090), Firefox, Safari,
phones; a real CAD export (Inventor / Fusion) of 2,000 parts – the first run of V2 should use one the owner may share,
or Thor's STEP (`tools/a4_to_step.py`). Subagent: one read-only helper mapped `fresing_render/web/` (section 3); nothing
it found was re-done.
