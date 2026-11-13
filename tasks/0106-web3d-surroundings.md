# 0106 – Web 3D model with its surroundings: moving sea, sky, weather, vessel motion and a live sun

**Who:** worker · **Status:** running · **Branch:** `claude/admiring-turing-bx5rjk` (the session's own branch)
**Started by:** lead chat, 13 Nov 2026 (owner's wish: "also allow adding environment, like the moving sea and weather")
**Lane:** Web 3D: `blender/web3d.py`, `core/web3d.py`, `ops_web3d.py`, `ui_web3d.py`, `fresing_render/web/` (the viewer
page and its bundled libraries), their tests; the website's viewer page `site/model/` + `tools/build_site.py` only as far
as a viewer change needs it (the site keeps its model). **Read only:** `surroundings.py` (the `SEA` table, `_waves`),
`world.py` / `studio` (light looks, sky, sun height, 360° photo), `vessel_motion.py` / `core/vessel_motion.py` (heave,
pitch, roll numbers). Additive: `props.py` (`FRWeb3D`), the tour, the PC check, the guide.
**Model:** **Opus · effort High** (subagents allowed, CLAUDE.md section 2) · **Place:** Claude Code on the web,
environment "CAD-render-animation"
**Next in the lane:** 0107 baked light (uses this task's sky and sun).

## Goal

5 Scene & Render > Web 3D model can put the machine's surroundings on the page: the moving sea, the vessel heaving
and rolling, the sky with clouds at a time of day, haze, rain and spray, a rough sea with white caps, and a sun whose
shadows move with the parts. **The owner picks per export what goes on the page** and how heavy the page may be, so a
page for a phone stays smooth and a page for a big screen looks its best. Still one file that opens offline.

## Background

- 0099 (0.2.77) built the export: own glTF writer, looks baked into tiles, rigid-part animation, one-file offline page
  with **model-viewer 4.4.0** (`fresing_render/web/`). 0105 (0.2.82) added meshopt compression (decoder already inside
  model-viewer, switched on by an empty inline "decoder location" script) and smaller bake atlases.
- 0099's note: polished steel looks darker in the browser because it mirrors model-viewer's own room light, not the
  app's studio – exporting the app's light as the page's environment fixes that too.
- **model-viewer cannot do most of this:** no custom water shader, no particles, no fog, no sun with real shadow maps
  (only a ground contact shadow), little access to its three.js scene. Expect to **move the page to plain three.js**
  (MIT; its `Water`, `Sky` and meshopt decoder examples are MIT too – all GPL-compatible) with small orbit/touch
  controls, inlined as today so the page stays one offline file. Decide by trying; say in the report why. Whatever the
  viewer, keep what the page does today: start in the app's Iso view, turn/zoom/pan by mouse and touch, the animation
  loop, the compressed model, the website's "Turn it yourself" page (`build_site.py --check` stays green).
- The app's sea: `surroundings.SEA` (Calm 0.25 m swell, Rough 1.6 m, wavelengths, ripple bump, foam threshold) and
  `_waves` (seeded directions/phases); vessel motion (task 0085) adds a long swell and moves model + deck by sine
  drivers (heave / pitch / roll, heading, strength, roll period, pivot; "Still / Level" parts). The page should use
  **the same numbers in the same formulas in JavaScript**, so the sea and the vessel on the page move like the app's
  (no per-frame data in the file).
- Sky: light looks Sky (sun height, weather Sun/Overcast), Studio looks, HDRI / 360° photo (`hdri_path`,
  `light_hdri_path`, rotation, strength, exposure).

## Owner's answers (13 Nov)

- Weather on the page: **all four** – sky + clouds at a time of day, haze / fog, rain and spray, rough sea / swell.
- "**Being able to select when making the export if possible, and able to optimize it.**"
- Baked light: a choice per export → task 0107 (needs this task's live sun).

## Scope

1. **Panel** (5 Scene & Render > Web 3D model, a new fold "Surroundings on the page", folded, every control with a
   tooltip): Surroundings **None / As in the project**; when on, ticks that start from the project's settings and can
   be changed for this export only (the project itself never changes):
   - **Sea** – Calm / Rough (white caps in Rough), moving waves; **Vessel motion** (only when the project has it on)
   - **Sky** – time of day (a sun-height slider + sun direction, or From the project), clouds (none / some / overcast);
     a 360° photo or Studio look of the project goes on the page as background and light instead
   - **Haze** – strength
   - **Rain and spray** – strength (spray where waves meet the hull, only with a sea)
   - **Live sun shadows** – on/off
   - **Page quality: Phone / Balanced / Best** – one switch that sets wave grid, ripple detail, rain count, shadow map
     size, sky picture size, pixel ratio; plus **Auto** on the page: it lowers quality by itself when it cannot keep
     ~30 frames per second (and says so in a small corner note), so one page works on a phone and a PC.
   - The result line adds what the surroundings cost in the file (MB).
2. **Sea on the page:** an endless sea to the horizon – the app's swell waves (same `SEA` + `_waves` numbers and
   seed) on a grid round the model, ripples by a moving normal map further out, foam/white caps in Rough, the water
   level and the hull's waterline as in the app. Off when the project has no sea surroundings (unless ticked).
3. **Vessel motion:** the model (and deck) heave, pitch and roll on the page with the app's formula and numbers, in
   step with the sea; Still / Level parts behave as in the app; works together with an exported animation.
4. **Sky and light:** the page's background **and** its light from the same sky (sun + sky colour at the chosen time of
   day, clouds, or the project's 360° photo / Studio look as an equirectangular picture, sized by Page quality), so
   metals mirror what the app shows. A sun (directional light) whose direction matches the sky.
5. **Haze:** distance fades into a colour matching the sky.
6. **Rain and spray:** falling streaks that move on the graphics card (no per-drop work in JavaScript per frame), a
   wet look of the deck/sea (darker, glossier) when rain is on; spray bursts at the bow when it dips in Rough.
7. **Live sun shadows:** shadow map from the sun on the model, the deck and (as a soft darkening) on the sea;
   moving parts and the rolling vessel cast moving shadows. Sized to the model so a 124 m vessel and a 1 m mill both
   get sharp enough shadows (cascades or a fitted frustum – your choice, measured).
8. **Measure** (say the machine; software GL is not a phone): file size added per item, page load time and frames per
   second in headless Chromium at each Page quality on the demo vessel (Draft + 512) and the test mill; pictures of
   each weather from the same camera for the report (`tasks/img/0106_*.jpg`, invented models only).
9. Tour stop "Web 3D surroundings" (the demo vessel or a tour set with a sea), PC-check line (`web3d.surroundings`:
   exports with every item on, checks the page's file and that it opens headless if a browser is there), guide section
   with a panel picture, tooltips.

## Done when

- [ ] Scope 1–9; the page still opens offline from one file, with and without surroundings; with Surroundings None it
      looks as today (apart from the app's own light, if that becomes the default – say so).
- [ ] Every item can be switched per export; Page quality and Auto change what the page does (measured).
- [ ] Tests: the page's settings block written from the panel (unit), the sea/vessel numbers on the page equal the
      app's (unit: the same height at a few points and times as `surroundings`/`vessel_motion` compute), headless
      page pictures per item if a browser is in the session; `build_site.py --check` green.
- [ ] An agent that did not write the page tries to break it (phone-size window, every combination, Auto quality,
      animation + vessel motion together) – its findings fixed or listed.
- [ ] GitHub green incl. Windows; report filled in (subagents, runs, numbers); merge to main and release when green.

## Not in this task

Baked light (0107). Putting the demo vessel or any new model on the website (owner decides; never the Fresing 400).
AR on phones, VR. The looks 0099 lists as lost in the web model. Flexible parts (hoses, cables) on the page. Changing
the app's own sea, sky or vessel motion (read only).

## Design (worker, 13 Nov)

**Viewer decision.** Surroundings **None** keeps today's model-viewer page byte for byte (website, tour, PC check
unchanged). Surroundings **As in the project** writes a new page on plain **three.js r180** (MIT): model-viewer has no
custom water shader, no fog, no particles, no sun shadow map and no access to its scene. The three.js parts are one
committed bundle `fresing_render/web/three-viewer.min.js` (global `FRTHREE`: three + OrbitControls, GLTFLoader, Sky,
HDRLoader, meshopt decoder; built by `tools/build_web_viewer.py` with esbuild, 0.80 MB, smaller than model-viewer's
1.07 MB). Our own page code is readable: `fresing_render/web/fr_math.js` (sea height, vessel channels and matrix –
pure functions, also run by node in the tests) and `fresing_render/web/fr_page.js` (scene, sea shader, sky, clouds,
haze, rain, spray, sun, quality, Auto). Still one HTML file: bundle + page code + settings JSON + base64 model and
pictures inline.

**Files and owners.** `core/web3d_env.py` (new, no Blender): quality table, the page's settings block, sun direction,
picture resampling to three's equirect, Radiance .hdr writer, `sea_height` / `vessel_matrix` reference in Python,
`page_html`. `blender/web3d.py`: `Job(surroundings=dict)` reads the project at rest (`vessel_motion.at_rest`), marks
Still/Level parts (`extras.fr_vm`), adds the Vessel deck's objects as parts when the project's surroundings are the
deck, builds the settings block (`env_settings`) and writes the three.js page. `props.FRWeb3D`: `env_*` settings,
filled from the project when Surroundings is switched on. `ui_web3d.py`: fold "Surroundings on the page".

**Settings block** (`<script type="application/json" id="fr-env">`, Blender world metres, z up; the page turns
(x, y, z) into three's (x, z, -y)): `quality`, `auto`, `levels` (per level: `seg` sea grid segments, `ripple` px,
`rain` streaks, `shadow` px, `pixel_ratio`), `model` {min, max}, `sea` {state, level, origin, near, waves [[a, dx, dy,
k, phase]], own (count of the sea's own waves; the rest is vessel swell), bump, foam (threshold or null), moving,
radius, rim}, `vessel` {pivot, heave/roll/pitch: [base, [[amp, omega, phase]]], bow [x, y, z], hull [length, beam]},
`sky` {kind SKY|PHOTO, sun [x, y, z] towards the sun, elevation, azimuth, clouds NONE|SOME|OVERCAST, strength,
exposure, photo/light = ids of embedded pictures}, `haze` {strength} | null, `rain` {strength, spray} | null,
`shadows`, `time` {start (s of the first frame), moving}.

**Formulas (same as the app).** Sea: h = fade(r) · Σ a sin(k (dx x + dy y) + phase − √(g k) t), fade = smoothstep
from 1 at `near` to 0 at 1.6 `near`, (x, y) from the sea's origin, t = scene seconds (0 when the waves stand still).
Vessel: V(t) = T(p + heave ẑ) · Ry(pitch) · Rx(roll) · T(−p), channel = base + Σ amp sin(phase − ω t). Sun of the
app's sky: (sin r cos h, cos r cos h, sin h) for Rotate light r and Sun height h (measured with Cycles).

**Subagents:** an independent tester (did not write the page) breaks the page at the end; findings fixed or listed.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
