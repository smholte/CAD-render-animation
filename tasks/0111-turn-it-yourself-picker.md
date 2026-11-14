# 0111 – "Turn it yourself" with a model picker: the tool-changing mill and the Thor arm, moving

**Who:** worker · **Status:** running (14 Nov 2026) ·
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

- [ ] Picker on the landing page with the two moving models; old link works; phone width checked (screenshot)
- [ ] Adding/removing a model is one command, tested
- [ ] Credits right (Thor CC BY-SA 4.0 for the 3D file); no Fresing 400
- [ ] Tests added; full suite passes; Pages republished; report with sizes and the light choice

## Not in this task

The cable-lay demo vessel on the page (owner decides later; then also the weather-on-the-page task). Gallery renders
(0112). Changes to the export or the bake beyond a fault fix.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
