# 0175 – Smaller web 3D files: animation keys packed and bounded, the model packed inside the page, WebP pictures

**Who:** worker · **Status:** done · **Branch:** `task/0175-smaller-web-files`
**Started by:** lead chat, 17 Nov 2026 (study 0149, proposals 1–3) · **Lane:** Web 3D (`core/web3d.py`,
`blender/web3d.py`, `core/meshopt.py`, `fresing_render/web/`, their tests)
**Model:** Opus · effort Medium · **Place:** Claude Code on the web, environment "CAD-render-animation"

## Goal

The demo's web page from tens of MB to about 10–15 MB with the same picture and motion, so it opens on a phone.

## Read first

`tasks/0149-web-size-study.md` (measurements and ranked proposals), then `tasks/0142-web-moving-cables.md` (0142 already put node
tracks through meshopt and thinned them to 1 mm: 155 → 46 MB) and 0179's report (the page on a phone). **First measure
where the demo's export stands today** (0.2.141: cables, people, ROV, labels) – sizes by part as in 0149's table.

## What to do (0149's ranks 1–3, what 0142 did not do yet)

1. Animation: rotations 16-bit, error-bounded keys (0.1 mm / 0.05°, checked against every frame in a Python test),
   still tracks dropped, blink tracks only at changes, shared time lists; cable / rope / coil shapes the same rule.
2. Page packing: the model gzip-packed inside the one-file page (`DecompressionStream`), a fast base64 read, WebP
   pictures (`EXT_texture_webp`) where the light atlases show no banding, exact duplicate shapes stored once.
3. Better meshopt packing in the app's writer (index codec, vertex-cache order, 12-bit light UVs, octahedral normals,
   key filters) – only where the NumPy fallback stays correct and Windows' library has the functions.
4. Every saved choice still works (Page quality, surroundings items, baked light, part tools, saved views); old
   exported pages are not touched.

## Done when

- [ ] Before / after sizes of the demo's page by part (machine named), the page side by side (picture + motion) in the
      report; the site's web models made again if they get smaller (`tools/make_site_web_models.py`).
- [ ] Tests: the error bound, the page reads the packed model (headless check as the lane's tests do), WebP fallback.
- [ ] PC-check line if something visible can break on Windows; guide's web 3D section updated (file size).
- [ ] GitHub green incl. Windows; merged to `main`, next free version, released; report filled in; `TASKS.md`.

## Not in this task

0149's ranks 4–8 (draw calls, light layout per shape, decimation, first view in two parts, rollers from the cable
travel) – the report says which is worth doing next.

---

## Report (filled in by the chat that did the task)

**Chat / date:** worker, Claude Code on the web (Opus · Medium), 17 Nov 2026 · version 0.2.143

**What changed:**
- `core/web3d_keys.py` (new, no Blender): a moving part's kept moments chosen against **every frame as three.js plays
  them** (its `slerpFlat` and `compose` in NumPy, with the file's own numbers): 0.1 mm, 0.05° and 1 mm at the far end
  (0142's rule kept for long parts). Turns 16-bit (a part whose 16-bit turn would move its far end > 0.25 mm keeps
  float turns), translations on a 2^-16 m grid; meshopt's **QUATERNION** and **EXPONENTIAL** filters in NumPy (bit
  for bit against Blender's meshopt bridge in a test; the bridge also exports them on Windows – the glTF add-on calls
  them there); times on one EXPONENTIAL grid per animation. A path that never changes gets no track; a shown/hidden
  STEP track keeps only its changes (+ the ends).
- `core/web3d.py`: `Gltf.accessor(filt=, filtered=)`, the reader decodes the two filters, `animation()` writes them;
  identical meshes written once (content hash); WebP pictures through `EXT_texture_webp` (required, no fallback copy),
  `texture_image()`, `image_size()` reads WebP.
- `blender/web3d.py`: uses the keys; `best()` = WebP only when smaller than the JPG and as faithful (mean error ≤ 1.25 x
  the JPG's + 0.25, worst 0.1 % ≤ JPG's + 2 of 255, read back by Blender), JPG otherwise or when Blender cannot write
  WebP; light-map UVs on a grid of 2 steps a texel (≤ ¼ texel off) scaled back by `KHR_texture_transform` on the
  occlusion texture.
- `blender/web3d_drawn.py`, `core/web3d_tubes.py`, `web/fr_tubes.js`: the moving cables' 16-bit points (`q`) and ring
  turns (`nq`) as moment-to-moment differences (`qd`/`nqd`; lossless, summed back by the page and `read_arrays`).
- `core/web3d_env.py` + `web/fr_page.js`: the model gzip-packed in the page (`data-gzip="1"`, `DecompressionStream`),
  `page_glb()` reads packed and old pages (`tools/build_site.py` uses it); `?places=1` writes the animated nodes'
  places (tests). The "data: address" read 0149 proposed was measured **slower** (0.8–1.3 s vs 0.15 s for atob + loop
  on the 42 MB page): not used.
- PC-check line `web3d.small` (MIN_LINES_FULL 93), function `web.export` names it; guide (Smaller file, File size);
  the site's two web models made again (test mill 2.54 → 1.73 MB page, Thor 7.26 → 4.38 MB).

**Tested and measured** (4-core web machine, no graphics card; the invented demo made full size by
`demo.build_project` on 0.2.141 code, exported as the owner does: 1024 px, hide names, smaller file, animation,
surroundings = project, soft light baked Normal; before = `main` 0.2.141, after = this branch):

| Part of the file | before MB | after MB |
| --- | ---: | ---: |
| **.glb** | **73.0** | **50.2** |
| **page** | **98.4** | **41.7** |
| moving cables (`fr_tube`; the cable into the sea q + nq 16.9 → 7.2) | 20.2 | 10.2 |
| pictures (806; 675 became WebP) | 15.4 | 8.2 |
| light-map UVs (TEXCOORD_1) | 6.7 | 4.2 |
| node animation (rotation + translation + times + STEP) | 9.8 | 7.3 |
| points / UV0 / triangles / normals | 15.9 | 15.6 |
| JSON | 4.5 | 4.2 |

Keys: 938 still paths dropped, STEP keys 452,581 → 305; translation keys went up (0.1 mm instead of 1 mm) but take
fewer bytes. Export 3,304 s → 3,422 s (the marine own-bakes alone ~30 min; the WebP read-back adds seconds).
Page in headless Chromium (software GL): same picture at two moments, mean difference 0.34 / 255 (picture packing),
`tasks/img/0175_demo_side.jpg` (before | after | difference × 8); model read 0.15 s + unpacked 0.3–0.5 s; JS heap 364–386
MB both. Load-until-ready swings 7–15 s for the same page in software GL: not compared.
Tests: `tests/test_web3d_keys.py` (15: the bound at every frame for 5 kinds of motion, filters vs Blender's library,
file read back, page packing, WebP, duplicates), `tests/test_web3d_keys_blender.py` (4: the mill with a sliding,
turning and blinking part – every frame, the page's places in headless Chromium, WebP and the JPG fallback); the lane's
web3d, moving-cable, light-page, own-bake, player, site tests pass locally. PC-check line web3d.small OK (6 s).
GitHub: 2 full runs – run 44122009282 red (`test_lightbake_break` read the light UVs without the new texture
transform; the test fixed), run 44129883813 green; `main` fast-forwarded to it (reuse run).

**Open points / follow-up tasks:**
- The brief's 10–15 MB is not reached: the demo grew since 0149 (3.6 M triangles, was 1.9 M; 806 pictures with the
  marine looks, was 13). What is left is mostly shapes (~16 MB) and cables (10 MB): 0149's ranks 6 (lighter big
  shapes) and 4 (draw calls) are next; the cable into the sea could use a looser tolerance or the sea's own motion.
- Vertex-cache order (rank 3) not done: Blender's meshopt bridge (Windows) has no `optimizeVertexCache`. Octahedral
  normals not done (int8 normals are already 4 bytes; no gain measured).
- The cable that travels far (`Part 1379`, float `q`, 1.95 MB) is not delta-coded.
- No subagents were used (Medium effort; the Windows-relevant part is the filters, checked against Blender's library).
- Leftover branch to delete on github.com: `task/0175-smaller-web-files`.
