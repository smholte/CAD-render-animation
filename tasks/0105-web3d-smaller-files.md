# 0105 – Web 3D model: half-size files for big models and less memory when baking

**Who:** worker · **Status:** running · **Branch:** `claude/great-davinci-atwmky`
**Started by:** lead chat, 13 Nov 2026 (0099's open points; owner: "all three" of the free-lane tasks)
**Lane:** Web 3D: `blender/web3d.py`, `core/web3d.py`, `ops_web3d.py`, `ui_web3d.py`, `fresing_render/web/` (the
viewer page), their tests. If a bundled encoder is needed: the extension's wheels (`blender_manifest.toml` wheel list,
`tools/requirements-dev.txt`, the packaging in `tools/build_release.py` – additive; say so in the report). Additive:
`props.py`, the PC check, the guide. Runs side by side with 0080, 0101, 0102, 0103, 0104 – none of them touches these
files. The landing page (`site/`) only if the site's own model gets smaller with it (no new models on the site: the
owner decides).
**Model:** **Opus · effort Medium** · **Place:** Claude Code on the web, environment "CAD-render-animation"

## Goal

5 Scene & Render > Web 3D model makes files about half the size for big models (the demo vessel, the Heavy machine), and
the page still opens offline from the one file, on a phone too; baking at 2048 px no longer needs ~5.5 GB on a big
model.

## Background (0099's report)

- The .glb has 16-bit points and UVs (Heavy 53 → 35 MB); the demo vessel at Draft + 512 px ≈ 6.9 MB. **Mesh compression
  (meshopt, `EXT_meshopt_compression`) would roughly halve the Heavy and demo files**, but model-viewer fetches its
  decoder from Google's CDN: for the one-file offline page **the decoder must be inlined**. Draco
  (`KHR_draco_mesh_compression`) is the other choice – compare size, decode time on a phone, licence, and what the
  encoder needs (a Python wheel for Windows inside the extension, or plain NumPy).
- Memory: one atlas per signature at 2048 px used 5.5 GB on the demo vessel – **bake in smaller atlases** (or tiles
  written out as they finish) to lower the peak. Bake time must not grow much.
- The page: model-viewer 4.4.0 (Apache-2.0) in `fresing_render/web/`, one file, works offline. Lost in the web model
  (stays so): edge wear, anisotropic sheen, orange peel, tool marks, cutaway/X-ray, app-made objects.
- Never the Fresing 400 (CLAUDE.md section 6). The demo vessel on the site stays the owner's call (`--web-model`).

## Scope

1. **Compression:** pick meshopt or Draco by measurement (size, decode time in a browser, encoder availability on
   Windows inside Blender's Python, licences – the repository is GPL); a setting "Smaller file (compressed)" (on by
   default for big models, with a tooltip saying older viewers may not open it); the decoder inlined into the page so
   it stays one offline file; the .glb alone still opens in common viewers (say which were checked).
2. **Memory:** the bake's peak memory on the demo vessel at 2048 px at most half of today (measure the peak like the PC
   check Heavy does); same look within the picture checks 0099 uses.
3. Numbers before/after in the report: Heavy (scaled-down on GitHub, full locally if it fits), the demo vessel at
   Draft + 512 and Normal + 2048: file size, export time, peak memory, page load time.
4. The PC-check line `web3d.export` (and `heavy.web3d`) report the new size; guide section updated.

## Done when

- [ ] Scope 1–4; the page opens offline from the one file with the compressed model (tested headless in a browser if
      the session has one, else the decode tested in Node or by a reader in Python – say which).
- [ ] Tests updated (writer/reader round trip with compression), GitHub green incl. the Windows install (a new wheel
      must install there); report filled in; merge to main and release.

## Not in this task

Putting the demo vessel or any new model on the site (owner decides), AR on phones, the looks that are lost in the
web model, animation beyond rigid parts.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (worker), 13 Nov 2026 · branch `claude/great-davinci-atwmky` · 0.2.82

**What changed:**
- **meshopt, not Draco** (measured/checked): model-viewer 4.4.0 already carries the meshopt decoder (WebAssembly inside
  its one file; it switches it on once a "decoder location" script has loaded – the page gives it an empty inline
  `data:` script, so 0 extra bytes and no internet). Draco would need a 5 MB compiled wheel per platform (DracoPy has
  one for Windows cp313) plus decoder files model-viewer fetches *by path* (hard to inline), and decodes slower on a
  phone. Licences: meshopt MIT, model-viewer Apache-2.0 – both GPL-compatible; no new wheel.
- New `core/meshopt.py`: the vertex codec (ATTRIBUTES, v0) in NumPy – same size as meshopt's own C encoder on the Heavy
  model (7.76 / 2.97 MB), read back by meshopt's own decoder (tests, and node + `meshopt_decoder.js` 0.22). Triangle
  lists: the TRIANGLES codec through **Blender's own meshopt library** via ctypes (Blender 5.2's glTF add-on bridge
  `bf_intern_meshopt_bridge`, or `libmeshoptimizer` next to bpy as a module); without it a NumPy INDICES codec
  (~65 % bigger index data). Python readers for all three codecs (`core.problems`, tests).
- `core/web3d.py`: `Gltf(compress=)` writes `EXT_meshopt_compression` views + the data-less fallback buffer, numbers
  vertices in first-use order, and (compressed only) stores points in steps of at least 0.05 mm (POS_STEP; Heavy
  17.9 MB at 0.02 mm, 17.2 at 0.05). Pictures and animation stay plain. The page: decoder switched on right after the
  viewer script; the website page names its model as `data-src` and a script sets it (an attribute `src` could start
  loading before the decoder; `tools/build_site.py` checks `data-src` too).
- Panel: **Smaller file** (on by default; packs from 200,000 triangles – `COMPRESS_FROM`; tooltip names the viewers
  that read it). Result line says "compressed".
- Memory: bake atlases 2048 px instead of 4096 (`ATLAS_MAX`), finished tiles kept as 8-bit pixels (`pack_tile`).
- PC check `web3d.export`: exports compressed, checks Blender's meshopt library was found and that **Blender's own
  glTF importer reads the packed file back** (same triangles) – on Linux and Windows at every push. `heavy.web3d`:
  full size must be compressed and < 20 MB (was 40). Guide section + `docs/img/panel_5_web3d.png`.
- `tools/web3d_measure.py`: one export in its own process → size, time, peak memory (the numbers below).

**Tested and measured** (web machine, 4 cores, no graphics card, Blender 5.2.3 as a module; before = `main` at 0.2.80):

| Model | Setting | File before → after | Export time | Peak memory (whole process) |
| --- | --- | --- | --- | --- |
| Heavy, 2,992 parts, 2.26 M unique triangles (Normal) | 1024 | 34.5 → **17.2 MB** | 4.6 → 6.2 s | 1.18 → 1.18 GB |
| Heavy | 2048 | 35.1 → **17.8 MB** | 9.9 → 10.2 s | 2.48 → **1.77 GB** |
| Demo vessel, 1,261 parts, 1.03 M unique triangles | Normal + 2048 | 24.7 → **12.2 MB** | 58.2 → 45.8 s | 5.24 → **2.51 GB** (48 %) |
| Demo vessel | Normal + 1024 | 22.5 → 10.1 MB | 15.1 → 12.3 s | 3.84 → 1.62 GB |
| Demo vessel | Draft + 512 | 6.9 → 3.7 MB | 3.2 → 3.7 s | 1.33 → 1.32 GB |

  Page load in headless Chromium (software GL, SwiftShader): demo Draft page 10.3 MB plain 9.3 s → 6.0 MB packed 9.2 s;
  demo Normal + 2048 packed (17 MB page) 17 s; Heavy packed (24 MB page) 27 s. Pictures of plain vs packed: same
  (test mill: identical pixels; demo: only the title text differs). Decoding is not the slow part. Phone: not tested
  (no phone here) – expectation only.
  Readers checked: model-viewer 4.4.0 (Chromium), meshopt's own decoder (node, 0.22), Blender 5.2.3's glTF importer
  (real Blender, Linux: the PC-check line; Windows: the same line on GitHub). Blender as a Python module has no glTF
  bridge library, so its importer cannot read a packed file (the app is real Blender).
  New tests: `tests/test_meshopt.py` (19), `test_web3d_core.py` +4, `test_web3d.py` +1; local: these, `test_site.py`,
  `test_user_guide.py`, the tour's web3d stop, PC-check `web3d.export` in real Blender.
  Subagents: none (no Windows-only code: the library is found through the glTF add-on's own `dll_path`; the Windows
  run proves it).

**Open points / follow-up tasks:**
- Normals could be packed with meshopt's octahedral filter (2.97 MB of the Heavy 17 MB) – small gain, not done.
- The site's model (test mill, 2,693 triangles) stays plain: compression would save 0.01 MB.
- Owner, on the RTX PC after the update: 5 Scene & Render > Web 3D model, export the demo vessel at 2048 – note the
  time; open the page, and send it to your phone.
