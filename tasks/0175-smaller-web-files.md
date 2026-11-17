# 0175 – Smaller web 3D files: animation keys packed and bounded, the model packed inside the page, WebP pictures

**Who:** worker · **Status:** running · **Branch:** `task/0175-smaller-web-files`
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

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
