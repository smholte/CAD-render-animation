# 0111 – "Turn it yourself" with a model picker: the tool-changing mill and the Thor arm, moving

**Who:** worker · **Status:** done (14 Nov 2026, version 0.2.93) ·
**Branch:** `task/0111-turn-it-yourself-picker` (or the web session's branch)
**Started by:** lead chat, 13 Nov 2026 (owner's choices 13 Nov, 20:00)
**Area (Web 3D lane):** `site/index.html`, `site/style.css`, `site/media/` (new .glb files, posters, `media.json`),
`site/CREDITS.md`, `tools/build_site.py`, `tests/test_site.py`, new `tools/make_site_web_models.py`; the export
itself is **called** (`blender/web3d.py`, 0107's `lightbake.bake`), changed only for a fault you find (say so).
Reuses 0112's `tools/make_site_projects.py thor` – does not copy it.
**Model:** **Opus · effort High** · **Place:** Claude Code on the web, environment "CAD-render-animation"

## Goal

The landing page's "Turn it yourself" offers **several 3D models to pick from**, each turning in the browser and
**playing its own animation**: first the invented test mill doing a **tool change**, and the **Thor robot arm**
moving. Adding a model later (the cable-lay demo vessel at sea, models from study 0113) is one command, no code change.

## Background

- Today (0099, 0105, 0106): one model, `site/media/test_atc.glb` (0.4 MB, still), `media.json` "web_model",
  `tools/build_site.py --web-model <file.glb> --model <id> --caption …`; the section links to `model/index.html`
  (model-viewer 4.4.0, vendored, offline). With surroundings the export writes its own three.js r180 page (0106).
  The landing page itself has **no script** (keep it so).
- 0107 adds baked light per export: Live only / Soft light baked, sun live / Everything baked. Animated parts are baked
  in the export frame's pose; Everything baked does not move its shadows → use **Soft light baked, sun live** or
  **Live only** for these two (pick by looking at both; say which and why).
- Test mill: `tools/make_test_atc.py` (invented, GPL like the app; double-arm changer 0064, 12-tool carousel).
- Thor: 0112's project (6 joints + gripper, a seamless 10–12 s loop, 0 clash rows), CC BY-SA 4.0 by Ángel L. M.
- **Never the Fresing 400** in any web model (CLAUDE.md section 6). The demo vessel waits for the owner's decision.

## Scope

1. **The picker** (landing page, no script): one card per model in `media.json` "web_models" (a list; convert the old
   "web_model"): poster, title, one line, file size in MB, "Open the 3D model". Each opens its own page
   `model/<id>/index.html` – model-viewer, or the export's three.js page when that model has surroundings, so a later
   sea model plugs in the same way. Nothing loads before a click. Cards wrap on a phone. Order and default from
   `media.json`. Old link `model/index.html` keeps working (goes to the first model).
2. **Each model page:** the animation **loops by itself**, a play/pause button, drag to turn / scroll to zoom as now,
   the credit + licence line (Thor: "this 3D file CC BY-SA 4.0" with the link), a link back to the landing page.
3. **`tools/build_site.py`:** `--web-model <file.glb or export folder> --model <id> --caption … [--title …] [--order N]`
   adds or replaces one model; `--remove-web-model <id>`; checks: credit present in `media.json` and CREDITS.md,
   poster made, size warning above 10 MB and refusal above 25 MB per model (a vessel later may need the export's Phone
   quality).
4. **The two models**, made reproducibly by `tools/make_site_web_models.py <id>` (re-running gives the same file):
   - **test_atc**: a seamless ~10 s loop – spindle to the change height, arm turns, grips both tools, pulls, swaps
     180°, pushes, returns, carousel indexes to the next pocket; the app's own ATC steps, 0 clash rows. Size ≤ ~2 MB.
   - **thor**: 0112's project and loop. Size: as small as looks right (aim ≤ 8 MB; meshopt from 0105).
   Both with the studio look of the current page, baked light as decided above.
5. Tests: `tests/test_site.py` for the list (each card, page, credit, size), adding and removing a model with a small
   fake .glb, the old link, the landing page still script-free; both .glb files hold one looping animation of the
   right length.

## Done when

- [x] Picker on the landing page with the two moving models; old link works; phone width checked (screenshot)
- [x] Adding/removing a model is one command, tested
- [x] Credits right (Thor CC BY-SA 4.0 for the 3D file); no Fresing 400
- [x] Tests added; full suite passes; Pages republished; report with sizes and the light choice

## Not in this task

The cable-lay demo vessel on the page (owner decides later; then also the weather-on-the-page task). Gallery renders
(0112). Changes to the export or the bake beyond a fault fix.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (Opus, effort High), 14 Nov 2026, branch `ccr-eafefd42-nqnksc`.

**What changed:**
- **Picker** (`tools/build_site.py`, `site/style.css`): media.json "web_model" became the list "web_models" (id, file,
  poster, caption, model, order, seconds; the old form still reads). "Turn it yourself" shows one card per model:
  poster, title, one line, "N MB to download · moves by itself", "Open the 3D model". No script on the landing page;
  cards wrap to one column on a phone (screenshot `tasks/img/0111-turn-phone.jpg`, 390 px, no sideways scroll).
- **Each model page** `model/<id>/index.html`: a plain .glb gets the model-viewer page; an export with baked light or
  surroundings gets the export's own three.js page with three.js / fr_math / fr_page loaded from `vendor/` (cached
  between models; the model stays inside the page). Both get: the animation looping by itself, a Pause/Play button,
  the credit line + "this 3D file <licence>" with its link (Thor: CC BY-SA 4.0 → creativecommons.org), "← Fresing
  Render" back. `model/index.html` (the old address) goes on to the first model (meta refresh, no script).
- **One command** each: `build_site.py --web-model <file.glb | export folder> --model <id> --caption … [--title …]
  [--order N]` (replaces in place, keeps its order), `--remove-web-model <id>` (files go too). Checks: credit in
  media.json **and** CREDITS.md, poster made (refuses without), warning above 10 MB, refusal above 25 MB, never the
  Fresing 400; `--check` checks every model page (viewer from the site, credit, button, size, valid glTF).
- **`tools/make_site_web_models.py test_atc | thor | all`** makes the two models as a user would (project → Build
  animation → Web 3D model with Animation and Soft light) and puts them on the page. Running it again gives the same
  file (test_atc checked byte for byte).
  - **test_atc**: four double-arm changes (T3, T1 at pot 5; T2, T1 at pot 2), magazine starts at pot 2 → indexes to 5
    → back to 2; every tool ends where it started: **seamless 10.1 s loop**, 38,941 triangles, **0.8 MB** .glb,
    **2.2 MB** to download with its page and three.js.
  - **thor**: task 0112's project and loop (10.0 s, 0 clash rows), draft facets, its 372 threaded screws and nuts
    hidden (they were 619,000 of 1,021,000 triangles; at the page's size it looks the same – compared side by side):
    402,926 triangles, **4.8 MB** .glb (12.0 MB with them), **7.5 MB** to download.
- **Light: Soft light baked, sun live** for both. Looked at both on the test mill: Live only (model-viewer) was flat;
  Soft gives the baked sky light and contact shading plus the live sun shadow, which follows the moving arm (Thor) and
  changer. Everything baked was not used (shadows would stay where the first frame had them).
- **Export fault fixed** (`blender/web3d.py`, `core/web3d.py`): an exported animation lost the tool copies of a tool
  change (they are separate objects shown and hidden by keys) – the arm turned with empty hands. Objects whose
  visibility is keyed (tool copies, Show/Hide steps) now come along, scaled to 0 while hidden with STEP keys; their
  place is held while hidden. Test `test_animation_shows_and_hides_parts` (failed before). User guide step 5 of Web
  3D model says so.
- **Export page** (`fresing_render/web/fr_page.js`): `frPage.paused` / `frPage.time` – the hook the site's Pause button
  uses (the page's own behaviour is unchanged).

**Tested and measured** (web machine, 4 cores, no graphics card, software 3D):
- Tests: `tests/test_site.py` (25, new: picker cards/pages/credits/old link, add + remove + order + size refusal with a
  fake one-triangle .glb, both models' loops: one animation of the right length, last moment = first, STEP keys on the
  mill), `tests/test_web3d.py` (16, new test above), `test_web3d_core/light_page/env/env_blender` all pass.
- In headless Chromium: the mill's arm grips both tools, pulls, swaps, pushes, the pot tips back (pictures at 0–4.2 s);
  Pause holds `frPage.time` (0.52 s for 2 s), Play goes on. Speed on a phone could not be measured here.
- Times: mill export 46–92 s (bake 43–88 s); Thor project 8–10 min (its clash check 420 s on the busy machine, 127 s
  in 0112), export 57 s.
- GitHub: 3 runs, all green, no failures – branch full run 43538942213 (25.8 min), the version commit after merging
  `main` (docs mode, 43541635466), `main` 43541825043 (reuse: release v0.2.93 published, an installed old version
  updated itself on Windows, offered to the apps, landing page republished). The live page could not be opened from
  the web machine (its network does not reach github.io).

**What the owner should test** (on the Pixel and the PC, after Pages is republished):
1. Open https://smholte.github.io/CAD-render-animation/ → "Turn it" → two cards, side by side on the PC, one under the
   other on the phone.
2. Tap "Open the 3D model" on the test mill: the arm swaps tools, the magazine turns, it starts again without a jump.
   Tap Pause, then Play. Drag to turn, pinch to zoom. "← Fresing Render" goes back.
3. The same for Thor (7.5 MB: note how long it takes on mobile data and whether it runs smoothly on the Pixel).

**Open points / follow-up tasks:**
- No PC-check line or tour stop: nothing new in the app the owner sees (the export fix is in an existing function;
  its test is in `tests/test_web3d.py`).
- Independent review skipped (no saved-data, Windows or update code).
- Thor's 7.5 MB on a phone: if it is slow on the Pixel, the next step is fewer key frames (its motion is 0.87 MB:
  124 moving parts × 251 frames, every frame kept) or the export's Phone quality.
- The cable-lay vessel / 0113 models: one entry in `MODELS` of `make_site_web_models.py` (a sea model takes the
  export's own page with surroundings the same way).
