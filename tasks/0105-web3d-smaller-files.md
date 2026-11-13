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

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
