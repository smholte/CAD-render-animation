# 0107 – Web 3D model with baked light: a choice per export

**Who:** worker · **Status:** running (13 Nov) · **Branch:** `claude/dazzling-ramanujan-0ipkza`
**Started by:** lead chat, 13 Nov 2026 (owner's wish: "have it really bake in the light properly")
**Lane:** Web 3D (same files as 0106: `blender/web3d.py`, `core/web3d.py`, `ops_web3d.py`, `ui_web3d.py`,
`fresing_render/web/`, their tests). Read only: `world.py`, `surroundings.py`, the Looks lane's materials. Additive:
`props.py` (`FRWeb3D`), the PC check, the tour, the guide.
**Model:** **Opus · effort High** (subagents allowed) · **Place:** Claude Code on the web, environment
"CAD-render-animation"

## Goal

The web 3D model can carry the light of a Cycles render – soft shadows, light in corners, bounce light, and (for a
machine standing still) the sun's shadows too – so it looks close to the app's render from every angle. The owner
picks per export how much is baked.

## Owner's answer (13 Nov)

Baked light: **a choice per export**. The panel offers:
- **Live light only** – as after 0106 (no bake; smallest file, fastest export).
- **Soft light baked, sun live** – shadows from the sky, light in corners and bounce light baked in; the sun's sharp
  shadows stay live (0106), so they move with parts, the vessel and the sea. The choice for animations.
- **Everything baked** – sun shadows baked too; closest to the render, but right only for a machine that stands still:
  with an animation or vessel motion in the export the panel says that baked shadows will not move (and asks once).

**House round trip (owner + House Planner lead, 13 Nov):** the bake is also called by the House lane (Fresing Render
imports a "house scene" package in the format of `smholte/house-scene-format`, bakes it and sends a "bake" package back).
So: **the bake must also work on imported geometry that already has UV set 1, without unwrapping it again, and must
return its results per object id.** Keep the three light choices with exactly these names – **Live only / Soft light
baked, sun live / Everything baked** – the format uses them. Make the bake a function another lane can call (scene or
object list + light choice + sky/sun in, a result per object id out), not only the panel's button. **Write the
"Design" section of the report first and push it (task-file-only push) before building:** the owner passes it to the
House Planner lead, and House Planner's task 0016 starts on it. Never attach `smholte/house-planner-dev` (private);
tests use only the made-up sample packages of `smholte/house-scene-format`.

## Background

- After 0106 the page has a sky/sun from the project (or the export's own choice) and a live sun with shadow maps; bake
  with **the same sky and sun** so baked and live light agree, and with the page's sun switched to "no direct light" on
  surfaces whose sun is baked (no double sun).
- 0099's export shares one mesh between copies of a part. Baked light differs per copy, so either each copy gets its
  own lightmap (second UV set, packed into atlases) or light goes into the vertices (per-vertex colours) for small /
  many-copy parts. glTF has `occlusionTexture` (can use UV set 1, every viewer reads it) for soft light; a full
  light map needs the page's own shader (the page is ours after 0106). Find the split that keeps the file sane:
  measure size and look for the demo vessel (1,261 parts, many repeated rollers/pads) and the Heavy machine.
- Bake with Cycles: on the owner's PC on the GPU (OptiX, as his renders), on the web machines on the CPU (slow – test
  with small models and few samples). The bake works on a copy; the project is never changed (0099 rule). Cancel works
  as for the export today; the panel shows an estimate before a long bake.
- The sea is not baked (it moves); the deck under the vessel is.
- 0099's comparison method: a Cycles render from the app's Iso camera next to the browser view from the same camera.

## Scope

1. Panel choice **Light: Live only / Soft light baked, sun live / Everything baked** + **Bake quality** (samples,
   texels per metre) with tooltips; estimate of bake time and added MB before Export.
2. Bake: lightmap UVs per unique placed part (packed, no overlaps, padding against bleeding), or per-vertex light where
   that is smaller for the same look; denoised; written into the .glb so the page uses it (and other viewers at least
   see the soft light, via `occlusionTexture`, where possible – say which viewers were checked).
3. The page: uses the baked light, takes the baked share out of its live light, keeps the live sun's moving shadows in
   "Soft light baked, sun live".
4. Measure on the demo vessel (Draft + 512, Normal + 1024) and the test mill: bake time (web machine, CPU – and an
   estimate for the RTX 3090, labelled as one), file size per choice, page load; pictures: Cycles render vs page per
   choice (`tasks/img/0107_*.jpg`, invented models only).
5. Tour stop, PC-check line (`web3d.bake`, small model), guide section; the PC check Heavy line reports bake time.

## Done when

- [ ] Scope 1–5; the three choices work with and without 0106's surroundings, with and without animation.
- [ ] Tests (lightmap UVs without overlaps, the file reads back with `core.web3d.problems`, the page pictures if a
      browser is there); an agent that did not write the code tries to break it.
- [ ] GitHub green incl. Windows; report filled in; merge to main and release when green.
- [ ] Owner's check listed in the report: export the demo vessel with each choice on the RTX 3090 (time), open the pages
      on the PC and the phone.

## Not in this task

Changing the app's renders or looks; the website's model (owner decides; never the Fresing 400); light maps for
flexible parts (hoses, cables).

## Design (worker, 13 Nov) – read this first, House lane

### The three choices (names fixed – the house format uses them)

| Id (code, format) | Label in the panel | What is baked | What the page keeps live |
| --- | --- | --- | --- |
| `LIVE` | **Live only** | nothing (as 0106) | everything |
| `SOFT` | **Soft light baked, sun live** | the sky's light without its sun (direct + bounce) **plus the bounce of the sun** (indirect only), all lamps of the scene | the sun's direct light and its moving shadows, all shine (reflections) |
| `ALL` | **Everything baked** | sky + sun + lamps, direct + bounce | shine (reflections, the sun's highlight); the sun adds no matte light on baked surfaces |

How the split is made in Cycles (the app's sun is the sun disc of the sky texture, `world.py`): `SOFT` = pass A *direct*
light with a copy of the world whose sky has `sun_disc` off + pass B *indirect* light with the world as it is (sum =
sky direct + all bounce, no sun direct). `ALL` = one pass, direct + indirect, world as it is. Lamps (0109's floodlights,
a house's own lamps) are in every pass, so they are baked in both choices. With a 360° photo or studio light there is
no separate sun: both baked choices bake all of its light; the page's key light then gives shine only.
Bake type: Cycles `DIFFUSE` without colour (the light a white matte surface receives), on copies with the parts' own
materials (glass and see-through parts let light through), the sea left out, the vessel deck in, parts read at rest
(`vessel_motion.at_rest`), decals baked but casting no shadow. Animated parts are baked in the export frame's pose.
Flexible parts (hoses, cables) cast shadows but get no baked light (not in this task): they stay live.

### The bake as a function another lane calls – `fresing_render/blender/lightbake.py`

```python
from fresing_render.blender import lightbake

CHOICES = (("LIVE", "Live only"), ("SOFT", "Soft light baked, sun live"), ("ALL", "Everything baked"))

result = lightbake.bake(
    objects,                  # placed mesh objects to get light (read only; any scene)
    light="SOFT",             # "SOFT" | "ALL" (also the labels above); "LIVE" returns an empty result
    *,
    world=None,               # bpy World that lights them; None = the objects' scene's world
    sky=None,                 # None = the world as it is; or {"sun_height": deg, "sun_direction": deg} to move the
                              # sky texture's sun on a copy (time of day: morning / afternoon / evening / night)
    occluders=(),             # objects that cast shadows and bounce light but get no result (ground, neighbours)
    lamps=None,               # None = every lamp of the scene shown in renders; or a list of lamp objects
    ids=None,                 # {object: "id"}; default ob["fr_id"] if set, else the object's name
    uv="AUTO",                # "AUTO": the app makes lightmap UVs, or per-vertex light where that is smaller
                              # "UV1":  the mesh's 2nd UV layer as it is – never unwrapped, never changed (house)
                              # "VERTEX": per-vertex light only
    quality="NORMAL",         # "DRAFT" | "NORMAL" | "FINE" (samples and texel budget, see below)
    texels_per_m=None,        # None = from quality and the objects' area; else this many texels per metre
    samples=None,             # None = from quality
    device="AUTO",            # "AUTO" = the GPU the app renders with (OptiX on the owner's PC), else CPU
    progress=None,            # callable(fraction 0..1, text) -> False to cancel (raises core.web3d.Cancelled)
) -> lightbake.Result
```

`lightbake.Bake(...)` takes the same arguments for a panel: `for f in job.steps(): ...` (text in `job.text`),
`job.result` at the end, `job.estimate()` before it starts → `{"seconds_cpu", "seconds_gpu" (labelled an estimate),
"bytes", "texels", "vertices"}`.

`Result`: `items: dict[id, Item]`, `light` ("SOFT" | "ALL"), `reference` (r, g, b), `samples`, `texels_per_m`,
`seconds`, `problems: list[str]` (plain words, e.g. "Roof 12: no 2nd UV layer – baked per vertex").
`Item`: `kind` "MAP" | "VERTEX"; for MAP `pixels` float32 (h, w, 3), row 0 at the bottom, in the object's own UV space
(its UV1 for `uv="UV1"`, else `uv` float32 (corners, 2) = the app-made layout in Blender corner order); for VERTEX
`values` float32 (vertices, 3) in the mesh's vertex order; `texels_per_m`.

**Units:** linear, scene-referred RGB (Rec.709, the render's colour space before exposure and view transform): the
colour a white matte surface shows in the Cycles render. Multiply by a surface's colour to get its matte look.
`reference` = the same light on an open, upward-facing surface with nothing round it (baked on a probe quad alone, the
same passes): `value / reference` is the **light factor** the web page uses (1 = open sky above; corners < 1; a wall
facing a low sun > 1). With a night sky and lamps the reference can be ~0: use the absolute values then.
**Every object gets its own result**, also objects that share a mesh (light differs per copy). Nothing in the
project is changed: copies in a bake scene of its own (a copy of a Cycles scene, 0099 rule), removed at the end, also
on an error or Cancel. Cancel works between bake batches (each batch kept to ~30 s on the CPU).

### Quality

| Quality | Samples | Texel budget (`texels_per_m` = None) |
| --- | --- | --- |
| Draft | 16 | ~1 M texels |
| Normal | 64 | ~4 M texels (one 2048 px atlas) |
| Fine | 256 | ~16 M texels |

Texels per metre = √(budget / total area of the baked parts), at least 4, at most 400; shown in the panel and can be
typed in. Denoised with Blender's own denoiser (OpenImageDenoise through the compositor) after the chart edges are
[built: a NumPy smoothing inside each chart instead – the compositor aborted Blender on machines without a GPU]
padded; a NumPy blur inside each chart when that is not there. Bake margin (Cycles `EXTEND`) = padding.

### Lightmap UVs and per-vertex light – `fresing_render/core/lightmap.py` (no Blender)

- **Charts** per unique mesh: triangles grouped by their main axis and its sign (as `box_uv`), split into connected
  pieces, split again where a piece overlaps itself in projection (rasterised check) → no overlaps by construction;
  UVs in metres per chart. One layout per mesh; **each placed copy gets its own place in an atlas** (copies differ).
- **Pack:** charts of all copies into atlases of 2048 px (skyline packing, largest first, 2 px padding at Draft,
  4 px otherwise), deterministic; a copy whose chart does not fit is scaled down.
- **Vertex or map:** per copy, per-vertex light when `vertices × 3 < texels / 2` (many small repeated parts: bolts,
  rollers, pads), else a map. `uv="UV1"` objects always get a map (their own image, size from their area).
- **Encoding for the file:** 8-bit `v = (F / scale) ^ (1 / 2)`, F = light factor, `scale` = the 99.9th percentile of
  all F of the export (≥ 1), stored once. `encode` / `decode` are in `core/lightmap.py` for the house package too.
- **Estimate:** seconds = texels × samples × passes / rate (rate measured on the web machine's CPU; the RTX 3090 figure
  is an estimate, labelled so); bytes = texels × JPEG bytes per texel (measured) + vertices × 3 per copy.

### In the .glb (glTF 2.0, other viewers keep working)

- Root `extras.fr_light = {"light": "SOFT"|"ALL", "scale": s, "curve": 2.0, "reference": "up"}`.
- A copy with a map: its own mesh entry that **shares** the part's POSITION / NORMAL / TEXCOORD_0 / indices accessors and
  adds its own `TEXCOORD_1` (16-bit normalised); its material is the look's material plus `occlusionTexture
  {index: atlas, texCoord: 1}` (JPEG RGB, the encoding above): one material per look and atlas. Other viewers (three.js
  editor, Blender, Windows 3D Viewer, model-viewer) read it as soft shadowing – which of them were checked goes in the
  report.
- A copy with per-vertex light: its own mesh entry on the shared accessors with the attribute `_FR_LIGHT` (VEC3, u8
  normalised, same encoding). Other viewers ignore it.
- The baked share and choice also go in the page's settings block (`light`, `scale`, `curve`).

### The page

- A baked choice always writes the **three.js page** of 0106. With Surroundings **None** it runs in a plain form: no
  sea, vessel motion, haze or rain; today's plain background; the project's light (sky or studio/photo picture).
  Live only + None stays the model-viewer page, byte for byte.
- Shader (`onBeforeCompile` on the model's materials that have an occlusion map with `texCoord 1` or `_fr_light`):
  F = decode(texel); baked light = F × (the page's own sky light on an up-facing surface, `getIBLIrradiance(up)`
  × environment intensity) [+ the page's sun on an up-facing surface for `ALL`]. It **replaces** the environment's matte
  light on that surface; reflections stay and are dimmed by min(1, luminance F) in corners. `SOFT`: the live sun with
  its shadow map as in 0106. `ALL`: the sun's matte light is off on baked surfaces (no double sun); its highlight stays.
  Because the page multiplies by its *own* sky and sun, baked and live surfaces agree even where the page's sky
  differs a little from Cycles'.

### Panel (5 Scene & Render > Web 3D model)

`FRWeb3D.light` (LIVE / SOFT / ALL, labels as above), `light_quality` (Draft / Normal / Fine), `light_texels` (0 =
auto), estimate line before Export ("Bake about 3 min on this PC's GPU, +4.1 MB"), and with `ALL` plus an animation or
vessel motion in the export a question once: "Baked shadows will not move with the parts. Bake them anyway?".

### Files and who writes them (subagents, CLAUDE.md section 2)

| Owner | Files |
| --- | --- |
| subagent A (worktree) | `core/lightmap.py` (charts, pack, UVs, vertex-or-map, encode/decode, estimate, overlap check) + `tests/test_lightmap.py` |
| subagent B (worktree) | `fresing_render/web/fr_page.js` baked-light shader + the plain form, `core/web3d_env.py` page settings `light`; `tests/test_web3d_light_page.py` (node + headless browser) |
| worker | `blender/lightbake.py`, `blender/web3d.py`, `core/web3d.py` (shared accessors, extras), props / ui / ops, tour stop, PC-check lines `web3d.bake` + Heavy bake time, guide, CHANGELOG, `tests/test_lightbake.py` |
| subagent C (did not write the code) | tries to break it at the end; findings go back to their authors |

House lane: call `lightbake.bake(..., uv="UV1")` on the imported objects with each time of day's `sky` (and snow from
0109 built first); write `Item.pixels` / `values` per object id into the bake package (with `core/lightmap.encode` or
as floats – the format decides). Ask the Web 3D lane (a task) for any change to these signatures.

---

## Report (filled in by the chat that did the task)

**Chat / date:** worker, Claude Code on the web, 13 Nov 2026 · branch `claude/dazzling-ramanujan-0ipkza` · 0.2.89

**What changed:**
- **The bake as a function** (`fresing_render/blender/lightbake.py`, as in the Design): `bake(objects, light, *, world,
  sky, occluders, lamps, ids, uv="AUTO"|"UV1"|"VERTEX", quality, texels_per_m, samples, device, progress)` →
  `Result.items[id]` (MAP: linear light picture + UVs, or the object's own UV1 image; VERTEX: per vertex and per
  corner), `reference`, `reference_sky`, `sun_ratio`, `problems`, `timing`. `Bake(...)` for a panel (steps, estimate,
  cancel). Added to the Design while building: `scene=`, `denoise=`; `Result.sun_ratio` (Cycles' sun ÷ sky on an
  up-facing surface) and `Result.reference_sky`. House lane: unchanged signatures otherwise.
- How it bakes: Cycles `DIFFUSE` without colour on copies in a bake scene of its own (copy of a Cycles scene, 0099
  rule); **one bake object per atlas** (all copies joined in world coordinates – Cycles bakes object by object over
  the whole image: 1,228 objects took > 20 min, joined 31 s); materials as matte copies (Metallic 0, so metal is not
  black); glass parts not baked but letting light through; decals cast no shadow; SOFT = sky direct (sun disc off,
  Sun lamps off) + all indirect; ALL = one pass; lamps baked in both; a probe quad above everything gives the
  reference; smoothing inside each chart (two box passes of `padding` texels; Blender's compositor denoiser aborted
  Blender on GitHub's machines and on Windows without a GPU – first run red), padding by Cycles' EXTEND margin.
- Light UVs (`core/lightmap.py`, subagent A): charts by main axis + connectivity + overlap split, skyline packing with
  every copy in one atlas, small atlases for small models (256–1024 px), per-vertex light for small many-copy parts,
  encoding v = (F/scale)^(1/2).
- The .glb: per copy a mesh entry on the shared accessors + its own `TEXCOORD_1` (u16) and a material with
  `occlusionTexture {texCoord 1}`, or `_FR_LIGHT` (u8 per vertex); `core.web3d`: `weld(extra_uv)`, `mesh_variant`,
  `vertex_attribute`, `problems` checks TEXCOORD_n of occlusion maps and `_` names.
- The page (`fr_page.js`, subagent B): baked matte light = F × the page's own sky light on an up-facing surface ×
  (1 + sun share for ALL), replacing the environment's matte light; reflections dimmed in corners; ALL: the live sun's
  matte light off on baked parts (highlight kept); glass not patched; plain form for Surroundings None. Fixed in 0106's
  code (B): with Live sun shadows off the sun shone straight down.
- Panel fold **Light** (choice, Bake quality, Points per metre 0 = Auto, estimate line, the question for ALL with
  motion), `props.FRWeb3D.light*`, tour stop 54 "Web 3D model with baked light", PC-check lines `web3d.bake` (Full) and
  `heavy.web3d_bake` (Heavy, bake time), guide section "Light" + new panel picture, CHANGELOG 0.2.89.

**Tested and measured** (4-core web session, CPU, no graphics card):
- Tests: `test_lightbake.py` (13), `test_lightmap.py` (27, A), `test_web3d_light_page.py` (9, B: headless shell +
  SwiftShader; on GitHub's Linux runner the browser cases fall back to `node --check` instead of skipping),
  `test_lightbake_break.py` (18, C – the independent tester's), plus test_web3d, test_tour, test_web3d_env, test_pccheck
  locally green; PC-check line `web3d.bake` OK in 9 s (bpy module).
- Bake time / file (sky at 40°, Texture size 512 Draft / 1024 Normal):

  | Model | Choice | Quality | Bake | Light adds | .glb | page |
  | --- | --- | --- | --- | --- | --- | --- |
  | Test mill (9 parts) | Soft | Draft | 18 s | +0.06 MB | 0.14 MB | 1.0 MB |
  | Test mill | Everything | Draft | 7 s | +0.05 MB | 0.14 MB | 1.0 MB |
  | Demo vessel (1,228 parts, 756k tri) | Live only | – | – | – | 3.7 MB | 6.0 MB |
  | Demo vessel | Soft | Draft | 43 s | +2.7 MB | 7.0 MB | 10.2 MB |
  | Demo vessel | Everything | Draft | 29 s | +2.7 MB | 7.0 MB | 10.2 MB |
  | Demo vessel | Soft | Normal | 375 s | +4.3 MB | 9.2 MB | 13.1 MB |
  | Demo vessel | Everything | Normal | 221 s | +4.4 MB | 9.3 MB | 13.2 MB |

  Of the Normal Soft bake: plan (unwrap, pack) 7.7 s, Cycles 356 s (12 calls, 4 atlases of 2048), denoise 10 s
  (measured with the compositor denoiser, since replaced by the NumPy smoothing).
  **RTX 3090: an estimate, not measured** – the panel assumes 20 × these 4 cores (Normal demo ≈ 20–30 s); the owner
  measures it. Page load (headless, software GL): demo vessel 2.9–3.2 s, same as without baked light.
- Pictures (invented models only): `tasks/img/0107_mill_render_soft_all.jpg`, `0107_vessel_render_soft_all.jpg`
  (Cycles render from the page's first view | Soft | Everything) and `0107_vessel_close_soft_all.jpg` (coil close-up,
  Soft | Everything). Everything baked is close to the render's balance; Soft is darker on the deck in the sun
  because the page's live sun is weaker than Cycles' (0106's calibration).
- Other viewers: Blender's glTF importer reads the lit file (second UV set present, test); others not checked here.

**Subagents:** A (`core/lightmap.py` + tests), B (page shader + plain form + page tests), C (independent tester: did not
write the code). C found 12 faults, all fixed by me after it finished and pinned by its tests: mirrored copies baked
black, more than 8 UV layers crashed, a grating with 10,000 bars stopped the bake (now per vertex), object-linked glass
cast a black shadow, glass faces of mixed parts black, colliding ids silently lost (now "#2" + problem), the probe
under a big ground (now above everything, invisible to rays), a Sun lamp baked in Soft (now counted as the sun), the
project's own bake settings (Selected to Active) stopped it, a part without material got no light picture. Re-done
after merging: B's sun term (uFrSunUp) replaced by the sun share after the first comparison picture showed
Everything baked too dark in shade.

**Open points / follow-up tasks:**
- Atlas fill: many small charts with 4 px padding at Normal fill 4 atlases for a 4 M texel budget on the demo vessel;
  smaller padding or merged charts would halve bake time and file (Web 3D lane, later).
- Cancel answers between bake calls: one 2048 atlas at Fine on a CPU is about 2 min (expected, not measured).
- The page's live sun vs Cycles' (Soft looks darker in the sun than the render) – 0106's sun power; a calibration
  task could use `Result.sun_ratio`.
- No OpenImageDenoise: Blender 5.2 has no bake denoiser, and running it through the compositor aborted Blender
  without a GPU. At Draft (16 samples) the smoothing looks clean on the test mill; Fine uses more samples.
- Owner's check (RTX 3090): export the demo vessel with each choice at Normal (Help > Make demo project, then 5 Scene &
  Render > Web 3D model > Light): note the bake time; open the pages on the PC and the phone; compare with a render.
- GitHub: (filled in after the runs)
