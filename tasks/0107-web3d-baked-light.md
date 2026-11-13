# 0107 – Web 3D model with baked light: a choice per export

**Who:** worker · **Status:** waiting for 0106 · **Branch:** `task/0107-web3d-baked-light`
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

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
