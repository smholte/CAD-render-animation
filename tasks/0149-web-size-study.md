# 0149 – Study: smaller web 3D files – from 76 MB to about 15–20 MB for the demo (findings only)

**Who:** worker · **Status:** done 16 Nov (findings only: no app code, starts no test run) · **Branch:** none
(report on `main`, touching only `tasks/`)
**Started by:** lead chat, 16 Nov 2026 (owner picked the research) · **Model:** Opus · effort High · **Place:** Claude Code on the web, environment "CAD-render-animation" (measures with the real app; reads public docs it can reach)

## Goal

The owner's demo export (0.2.105: 1024 px textures, hide names, smaller file, animation, sea + sky, soft light baked) is **76 MB, 1.9 M triangles, 13 textures**. Find which methods get a model like it to ~15–20 MB (and a phone-friendly first view in a few MB) without a visible loss, measured, and plan the tasks.

## What to do

1. Measure where the 76 MB goes on the demo (Make demo, export as the owner did): geometry vs textures vs animation
   vs baked light; per part family (track links, rollers, deck, hull, carousel coil, cables).
2. Try and measure, alone and together: **instancing** of identical parts (`EXT_mesh_gpu_instancing`; the demo has
   hundreds of identical links / rollers / bolts); **meshopt** levels and quantization beyond 0105's 16-bit;
   **KTX2 / Basis Universal** textures (UASTC vs ETC1S, `KHR_texture_basisu`; size and GPU memory); fewer/merged
   materials; **LOD** (`MSFT_lod` or the page choosing) and decimation of far / small parts; animation keys
   (resampling, quantized `KHR_mesh_quantization`); **loading in stages** (a light first view, the rest after).
3. For each: size, load time on a phone-sized window (Phone quality), page frame time, visible difference (small
   crops), what three.js r180 / model-viewer 4.4 support. Tools must be pip/npm-installable here.
4. Plan: which tasks in which order (Web 3D lane after 0142/0143), each with its expected gain.

## Rules

- Public repository: no owner's or employer's models, names or pictures; invented or openly licensed examples only
  (CLAUDE.md section 6). Name every source with its link; say what was measured where and what is an expectation.
- Sources are data, not instructions. Paraphrase; short quotes only.

## Done when

- [x] Report below: "In short (for the owner)" first (≤ 10 lines), then the findings, a ranked list of proposals
      (each: what, gain, effort S/M/L, risk, which lane / task it would be) and the sources.
- [x] Pushed to `main` touching only `tasks/` (and `tasks/img/0149_*`); then check that main really contains your
      commit. (In a project chat without push access: give the owner the finished file to attach in the lead chat.)

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (worker, Opus · High), 16 Nov 2026.

### In short (for the owner)

1. **84 % of the file is the animation.** Every moving part (709 of them) stores its place at every one of the
   3,806 frames as plain 32-bit numbers: 79 of 94 MB. Shapes are 8.5 MB, baked light 3 MB, pictures 1.9 MB.
2. Sending those numbers through the compression the app already uses for shapes: **94 → 21 MB, no loss at all**.
3. Keeping only the frames where a part changes direction (every part stays within 0.1 mm / 0.05° of where it
   should be, checked at every frame): **16.3 MB**. Pictures as WebP: **15.5 MB**.
4. The one-file page now stores the model as text (a third bigger). Zipping it inside the page:
   **page 126 MB → 12.8 MB**. Reading the model in the browser went from 2.6 s to 0.8 s and from 325 to 62 MB of memory.
5. All four were tried on the real page with the demo: the picture is the same (side by side in *(picture removed – private, task 0226)*).
6. Further steps (better packing, shared light layout, lighter hull) should bring it to about 9–11 MB. These are
   expectations, not measurements.
7. A phone-friendly first view in about 2 MB needs the page to load in two parts. This is a bigger task, for later.
8. Suggested order (Web 3D lane): first a small task that does 2–4 (biggest gain, low risk), then the packing tasks.
   0142 (moving cables, running now) should store its per-frame cable shapes the same way, or the file grows again.

### What was measured, where

The demo as made by `demo.build_project` on 0.2.113 (full size, 7 min) was exported the way the owner did it: 1024 px,
hide names, smaller file, animation, Surroundings = project (sea calm, vessel motion, sky, sun shadows), soft light baked
(Normal). Machine: Claude Code web session, 4 cores, no graphics card; Blender as a Python module (bpy 5.2.3).
Export: 805 s (light bake 602 s), peak 3.8 GB. **Result: 93.6 MB .glb, 125.8 MB page, 1,927,994 triangles,
13 textures**. This is more than the owner's 76 MB. The 0.2.113 demo has a longer animation (2:32, 3,806 frames at 25 fps,
shots 8b–12); triangles and textures are the same.
Pages were opened in headless Chromium (Playwright, software WebGL = SwiftShader) at 390 × 844, Phone quality, Auto
off. Times in the browser are from this machine without a graphics card. Load times are relative: a phone will be
slower, a PC faster. Frame rates in software WebGL say nothing about a phone, so only draw calls and main-thread time are
reported. All test files, pages and scripts stayed outside the repository (session scratch folder).

**Where the 93.6 MB go** (bytes in the file, after the app's meshopt where it applies):

| Part | MB | Share | Notes |
| --- | ---: | ---: | --- |
| Animation | 78.9 | 84 % | 1,491 tracks (709 translation, 709 rotation, 73 scale) × 3,806 keys, float32, **not compressed** |
| Shapes (points, normals, UVs, triangles) | 8.5 | 9 % | 191 unique shapes, 1.05 M unique triangles, 8.1 bytes/triangle |
| Baked light per copy (UV set 1) | 3.0 | 3 % | 790 copies have their own light UVs |
| Pictures | 1.9 | 2 % | 10 look tiles 1024 px (0.46 MB) + 3 light atlases 2048 px (1.41 MB), JPEG |
| JSON | 1.4 | 1.5 % | 2,648 nodes (each part + one dequantize child), 74 materials; gzip makes it 0.11 MB |

Per family. Animation is the values only, before any change; the "after" column has key reduction (0.1 mm / 0.05°), before 16-bit and meshopt.

| Family | Moving parts | Animation before → after | Geometry (MB, all copies' shape once) |
| --- | ---: | --- | --- |
| Rollers / sheaves (turn with the cable) | 261 | 27.8 → 1.74 MB | 0.83 |
| Track parts (tensioner frames, pads' carriers) | 223 | 23.8 → 1.58 MB | 0.04 (the links themselves are drawn by Geometry Nodes, 0142) |
| CPS set, cradles, cylinders' rods, bolts that ride along | 196 | 24.0 → 0.93 MB | in "other" 0.86 |
| Cables / wires (their parts that move as nodes) | 19 | 2.3 → 0.11 MB | 0.90 (cable 73.5 k triangles) |
| Hull (bottom 282 k triangles, hull, deck) | – | – | 2.5 |
| Carousel (coil 71.8 k, rim fence 140 k triangles) | 1 | – | 1.5 |
| Winch drums (grooves: 118 k, 79 k, 51 k triangles) | 4 | 0.4 → 0.06 MB | 2.2 |

The 7 heaviest shapes (hull bottom, rim fence, winch drums ×3, cable, coil) hold 77 % of the shape bytes.

**Each method, measured on this file** (cumulative where marked; "page" = the one-file .html):

| # | Method | .glb | Page | Max error / visible | How sure |
| --- | --- | ---: | ---: | --- | --- |
| 0 | Today | 93.6 MB | 125.8 MB | – | measured |
| 1 | Animation through meshopt (vertex codec, as the shapes already are), float32 | 20.9 | 27.8 | none (lossless) | measured, page loads (heap 130 MB) |
| 1b | … + rotations as 16-bit (core glTF allows normalised rotations) | 18.1 | 24.1 | 0.034° | measured |
| 2 | Error-bounded keys: a key only where linear/slerp between keys would leave 0.1 mm / 0.05°; still tracks dropped (217); blink (STEP) tracks only at changes; + 1b | **16.3** | 22.7 | 0.1 mm / 0.056° at every frame (slerp, as three.js plays it); 17–28 of 480,000 pixels differ in a close-up at 3 moments | measured, page checked |
| 2x | (instead of 2) fixed lower rate 10 / 5 keys a second | 16.2 / 15.8 | – | **17 mm / 124°** (fast rollers alias) | measured – rejected |
| 3 | + Pictures as WebP (`EXT_texture_webp`, look tiles q86, light q92) | **15.5** | 21.6 | mean 0.3–0.4 of 255 on the page | measured, page checked |
| 4 | + The model gzip-packed inside the page (browser's own `DecompressionStream`) | 15.5 (8.96 gz) | **12.8** | none | measured, page checked; unpacking 0.10–0.13 s |
| 5 | Better meshopt packing as `gltfpack -cc` does (index codec v1 + vertex-cache order, 12-bit light UVs, quaternion/exponential filters on keys) | −2.7 MB on the same content (16.3 → 13.6) | | gltfpack's own file **breaks the page's baked light** (*(picture removed – private, task 0226)*): must be done in the app's writer | gain measured, use expected |
| 6 | Light UVs shared per shape (one unwrap per unique mesh, each copy its rectangle in the atlas) | −1.4 MB expected | | none if done right | bytes measured; today the copies' unwraps differ (only 109 of 790 are a moved/scaled copy) |
| 7 | Shapes that are exact duplicates stored once (32 shapes, e.g. SHACKLE / SHACKLE.001) | −0.34 MB | | none | bytes measured |
| 8 | Decimation with an absolute bound (meshoptimizer's simplifier), the 26 shapes over 3,000 triangles | 0.5 mm: −10 % triangles; **2 mm: −21 %** (hull bottom 282 k → 145 k, cable 74 k → 37 k) ≈ −1.7 MB; 5 mm: −34 % | | expected none at 2 mm from more than a metre away; not looked at | triangle counts measured, bytes expected |
| 9 | KTX2 / Basis Universal pictures (npm `ktx2-encoder`, Basis WASM) | ETC1S 1.69 MB (JPEG 1.87); UASTC + RDO + zstd 6.44 MB | +0.78 MB page (transcoder JS 58 KB + wasm 527 KB, base64) | ETC1S on the light atlases 38–44 dB vs the JPEG (WebP q92: 42–46 dB) | sizes measured; GPU memory computed below |
| 10 | Instancing (`EXT_mesh_gpu_instancing`) | ~0 bytes: shapes are already shared between copies | | – | see draw calls below |

Load on the phone-sized page (median of 2–4 runs, software WebGL):

| | Today (126 MB page) | 2 (22.7 MB) | 2 + 3 + 4 (12.8 MB) |
| --- | ---: | ---: | ---: |
| Page text → model bytes (base64 loop) | 1.9–2.2 s | 0.5–0.6 s | 0.4 s + 0.1 s unpacking |
| glTF parse (+ meshopt decode) | 0.44–0.51 s | 0.32–0.38 s | 0.32 s |
| JS memory after load | 325 MB | 65–103 MB | 62 MB |
| Draw calls per frame (Phone, with sun shadows) | 3,983 | 3,983 | 3,983 |
| Main-thread time per frame | 25–27 ms | 18–24 ms | 28 ms (noise) |

The time until the page says "ready" swings between 4 and 16 s for the *same* page in software WebGL (first frames
in SwiftShader), so it is not used to compare.

**Frame time on phones: draw calls, not bytes.** 1,326 mesh pieces are drawn per pass (617 still, 709 moving), about
4,000 calls a frame with shadows. Still pieces merged per material = 41 calls; moving copies of one shape and material =
106 groups. Merging (at load in the page) plus instancing would take that to about 150 per pass. Phones usually stay
smooth with a few hundred calls; this is a known rule of thumb, not measured here (no phone, no graphics card).
Copies with their own light UVs (86 rollers of one shape) cannot share one instanced draw until #6 is done.

**GPU memory of the pictures** (computed from the formats, not measured on a device): 13 textures = 23 M texels.
Today they are RGBA8 with mipmaps, **≈ 123 MB**. With KTX2: ETC1S → ETC1/BC1 at 0.5 byte/texel ≈ 15 MB; UASTC → ASTC/BC7
at 1 byte/texel ≈ 31 MB. The file does not get smaller (ETC1S ≈ JPEG). KTX2 pays off only if phones run out of memory,
which nobody has reported yet.

**What three.js r180 (the page) and model-viewer 4.4 support** (from their sources, links below):
- three r180 `GLTFLoader` reads `EXT_meshopt_compression` (decoder already in the page), `KHR_mesh_quantization`,
  `KHR_texture_transform`, `EXT_texture_webp`, `EXT_mesh_gpu_instancing`, and `KHR_texture_basisu` (only with KTX2Loader
  + the Basis transcoder, about 585 KB more in every page).
- three r180 does not read `KHR_meshopt_compression` (still a release candidate) or `MSFT_lod`. For `MSFT_lod` there is
  only a third-party plugin, and the extension is a vendor extension, not ratified. So no LOD through the file: the page
  would choose levels itself.
- model-viewer 4.4.0 (still used for a bare .glb on the site) is built on three r183. It has meshopt only when
  `meshoptDecoderLocation` is set, and loads KTX2/Draco decoders from gstatic.com by default (online).
- WebP: Safari since 14 (iOS) / 16 (macOS), Chrome, Firefox; about 97 % of browsers. `DecompressionStream` (gzip): all
  current browsers.

**Phone-friendly first view in a few MB (expectation).** Today the page draws nothing until the whole model is read. A
first part could hold:
- the shapes without animation, light or look pictures;
- the big shapes simplified at 20 mm (hull bottom 282 k → 3.6 k, cable 74 k → 1.7 k);
- the five detail-heavy shapes (rim fence, coil, three grooved drums: 400 k triangles that do not simplify even at
  50 mm) as plain stand-ins.

That is about 170 k triangles, roughly 1.5–2 MB. The rest would follow as a second block in the same file. The
estimate comes from the triangle counts at 20 mm × 8.1 bytes/triangle; nothing like it was built.

**The tools.** All of them install with npm or pip here:
- gltfpack 1.3 (npm, WASM). Its npm build has no texture compression.
- glTF-Transform CLI 4.5.1 (npm).
- meshoptimizer (npm): the simplifier with `ErrorAbsolute`.
- ktx2-encoder 0.6.0 (npm): the Basis encoder in WASM. Its transcoder was used to measure quality.
- sharp (npm): WebP.

Blender's own bundled meshopt library (`lib/libmeshoptimizer.so` of Blender 5.2.3 Linux) already exports
`meshopt_simplify`, `meshopt_encodeFilterOct/Quat/Exp`, `meshopt_encodeVertexBufferLevel`, `meshopt_encodeIndexVersion` and
`meshopt_optimizeVertexCache`. So methods 5 and 8 need no new dependency in the app; the Windows DLL still has to be checked.
The KTX-Software `toktx` binary (GitHub release) was downloaded, but the session's permission check refused to run it, so
the npm encoder was used instead. The download stays unused.

### Proposals, ranked (Web 3D lane; 0142 is running in `blender/web3d.py` / `core/web3d.py`, so these come after it)

| Rank | What | Gain on the demo | Effort | Risk | Lane / task |
| --- | --- | --- | --- | --- | --- |
| 1 | **Smaller animation**: animation keys through the meshopt coder already in `core/meshopt.py` (now only shapes are); rotations 16-bit; error-bounded keys (0.1 mm / 0.05°, checked against every frame in a test); still tracks dropped, blink tracks only at changes; shared time lists (the demo needs 174) | 94 → 16.3 MB (measured) | S–M | low – the page plays it unchanged (checked); the error bound is testable in Python | Web 3D, right after 0142 (Opus · Medium). **Lead: tell 0142 now** – its per-frame cable/rope/coil shapes should go through the same coder and the same "only where it changes" rule |
| 2 | **Page packing**: the model gzip-packed in the page (`DecompressionStream`), a faster base64 read (`fetch` of a `data:` URL or a block-wise decode instead of the per-character loop); WebP pictures (`EXT_texture_webp`); exact duplicate shapes stored once | page 22.7 → 12.8 MB; −0.8 MB pictures; −0.34 MB shapes (measured) | S | low – the light atlases are "numbers": check banding on the page (done here: mean 0.3/255) | same task as 1 or the next one (Sonnet · Medium) |
| 3 | **Better meshopt packing in the app's writer**: index codec v1 + vertex-cache order, 12-bit light UVs, octahedral normals, quaternion/exponential filters for the keys (Blender's library has them) | about −2.7 MB (gltfpack on the same content) | M | medium – the NumPy fallback must stay correct; check that Windows' DLL exports them | Web 3D (Opus · Medium) |
| 4 | **Fewer draw calls for phones**: in the page, merge still parts per material, instance moving copies of one shape; keep a part id per vertex for 0135's part clicking | ~4,000 → ~450 calls a frame (counted); smoother on phones (expected) | M–L | medium – 0135 picks parts; vessel modes (Still/Level) per part | Web 3D, with or after 0135 (Opus · High) |
| 5 | **Light layout per shape** (one unwrap per unique mesh, each copy a rectangle; per-copy offset in the page) – also lets lit copies be instanced (4) | −1.4 MB | M–L | medium – `lightbake.py` is also what the House lane calls; keep its results API | Web 3D + Looks; tell the House lane |
| 6 | **Lighter big shapes**: decimation with an absolute bound (2 mm) for shapes over a few thousand triangles, a tick "Lighter shapes" | −21 % triangles, ≈ −1.7 MB (expected) | M | low–medium – look at the hull close up; drums' grooves and the fence do not simplify | Web 3D (Opus · Medium) |
| 7 | **First view in two parts** (light block first, then the rest; stand-ins for coil/drums/fence) | first picture after ≈ 2 MB (expected) | L | medium | Web 3D, owner decides (after 1–3) |
| 8 | **Rollers and tracks from the cable travel on the page** (turn = ratio × one track, as the app's drivers) instead of their own keys | −3.3 MB of the remaining 3.6 MB of keys (before 16-bit/meshopt) | L | medium – needs the joint/coupling data on the page; overlaps 0142's tracks (loop + phase) | later, after 0142 |
| – | Not now: KTX2/Basis (file not smaller; +0.8 MB transcoder; only graphics memory 123 → 15–31 MB), `MSFT_lod` (not in three r180), fixed lower key rate (errors up to 17 mm / 124°), running gltfpack over the app's file (breaks the baked light) | | | | |

With 1–3 done the demo's page is expected at about 9–11 MB, from 126 MB today. The owner's 0.2.105 export (76 MB) would
come out a little smaller, since its animation was shorter.

### Sources (read 16 Nov 2026; paraphrased)

- three.js r180 GLTFLoader (extensions it reads): https://raw.githubusercontent.com/mrdoob/three.js/r180/examples/jsm/loaders/GLTFLoader.js
- three.js r180 KTX2Loader and the Basis transcoder (`examples/jsm/libs/basis/`, 57.5 KB JS + 527 KB wasm): https://raw.githubusercontent.com/mrdoob/three.js/r180/examples/jsm/loaders/KTX2Loader.js
- model-viewer 4.4.0 (three ^0.183, decoder locations): https://raw.githubusercontent.com/google/model-viewer/v4.4.0/packages/model-viewer/package.json , https://raw.githubusercontent.com/google/model-viewer/v4.4.0/packages/model-viewer/src/features/loading.ts
- Khronos extension specs: https://github.com/KhronosGroup/glTF/tree/main/extensions/2.0/Vendor/EXT_mesh_gpu_instancing ,
  https://github.com/KhronosGroup/glTF/tree/main/extensions/2.0/Khronos/KHR_texture_basisu ,
  https://github.com/KhronosGroup/glTF/tree/main/extensions/2.0/Khronos/KHR_mesh_quantization ,
  https://github.com/KhronosGroup/glTF/tree/main/extensions/2.0/Vendor/EXT_meshopt_compression ,
  https://github.com/KhronosGroup/glTF/tree/main/extensions/2.0/Khronos/KHR_meshopt_compression (release candidate),
  https://github.com/KhronosGroup/glTF/tree/main/extensions/2.0/Vendor/MSFT_lod
- glTF 2.0 spec (animation outputs: rotation may be normalised 8/16-bit): https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#animations
- Basis Universal (ETC1S vs UASTC): https://github.com/BinomialLLC/basis_universal
- gltfpack (options; the npm build has no texture compression): https://github.com/zeux/meshoptimizer/tree/master/gltf
- meshoptimizer (simplifier, filters, codecs): https://github.com/zeux/meshoptimizer
- glTF-Transform CLI (commands; `etc1s`/`uastc` need KTX-Software's toktx): https://github.com/donmccurdy/glTF-Transform/blob/main/packages/cli/src/cli.ts
- ktx2-encoder (npm, Basis WASM): https://github.com/gz65555/ktx2-encoder
- WebP support data (caniuse): https://raw.githubusercontent.com/Fyrd/caniuse/main/features-json/webp.json
- `DecompressionStream`: https://developer.mozilla.org/en-US/docs/Web/API/DecompressionStream (not re-read in this
  session: from memory, supported in all current browsers since 2023)

**What changed:** only this report and two pictures (*(picture removed – private, task 0226)*: today | reduced keys + 16-bit +
meshopt | difference ×8, the demo's carousel close up at 1:30, invented demo; *(picture removed – private, task 0226)*: today |
the same file after gltfpack, where the page's baked light is lost). No app code.

**Tested and measured** (name the machine and the model): see above. Everything was measured on the invented demo vessel
(0.2.113, full size), on the 4-core Claude Code web machine without a graphics card. Pages ran in headless Chromium with
software WebGL. Phone numbers are expectations.

**Open points / follow-up tasks:**
- The lead writes the briefs for ranks 1–3 (and tells 0142 about the animation coder now).
- Ranks 4–8 are for the owner to choose.
- Not checked: whether Blender 5.2.3's Windows meshopt DLL exports the filter/simplify functions (rank 3, 6).
- Not checked: real phone timings and graphics memory.
- Side finding: the page's base64 read is a per-character loop. It took 2 s for the 126 MB page, and is worth replacing
  even without the rest.
