# 0311 – Study + prototype (findings only): a surroundings maker – terrain, paint, plants, trees, rocks, buildings, roads, water – and new ready-made backgrounds (beach, road, building site …)

**Who:** worker · **Status:** running · **Branch:** `task/0311-study-surroundings-maker` (branch only, never
merged; every push `[skip ci]`)
**Started by:** lead, 23 Nov 2026 (owner 21:14: "a separate background maker later with procedural plants, trees,
rocks and such, also different types of building, and ocean, and have everything paintable. Also more backgrounds like
beach, road, building zone and more.") · **Model:** Opus · effort High
**Area:** findings + design only; prototype in **new files** on the branch (e.g. `tools/surroundings_proto/`). Reads
`core/surroundings.py` (`KINDS`, `build`, props), `blender/surroundings.py`, `core/sea.py`, `core/weather.py`,
`core/props_detail.py` (0155 light versions by distance), study **0286**'s report (branch
`task/0286-study-asset-libraries`: Poly Haven / ambientCG CC0 models and textures, the Fresing asset format), study
**0306** (Vehicles – its terrain, point D) if done, study **0312** (shore waves) if done. The page in
`tasks/0311_page/`. Not a code slot.

## What to find out

A. **New ready-made backgrounds** (one click, like today's 11 kinds): beach (sand, dunes, the sea meeting the shore),
   road (asphalt, markings, kerbs, lamp posts, a crossroads), building site / construction zone (fences, gravel, site
   huts, containers, a tower crane from the Lifting lane), onshore wind farm, industrial estate, harbour basin, field /
   meadow, forest edge, desert, snow. Rank them by what the owner's users need (offshore wind, cable lay, cranes,
   machines, vehicles) and cost; say which can be built from today's `core/surroundings.py` pieces as a quick first
   build task (phase 1) before the maker exists.
B. **The maker** – its own workspace or window, simple for a sales person, deep for an animator:
   - **terrain**: flat, a height map or an imported terrain (also Vehicles' speed bump / off-road track – one terrain
     for both), raise / lower / smooth by brush;
   - **paint layers** by brush: grass, gravel, sand, asphalt, concrete, rock, mud, snow, water's edge;
   - **scatter by painting**: trees, bushes, grass, rocks, stones, debris, with a density brush and an eraser;
     procedural (Geometry Nodes) or assets (0286's CC0 sources), which per kind and why;
   - **buildings**: a few procedural kinds (hall, office, house, warehouse, site hut) with size, floors, roof, facade,
     colour – the colour paintable;
   - **roads** drawn as curves (width, kind, markings and kerbs automatic, follows the terrain);
   - **water**: sea / lake / river whose shore line comes from the terrain height (a beach where water meets low
     terrain – breaking waves are study 0312's; design the hand-over).
   - **presets**: "Beach at sunset", "Building site" … one click; save your own surroundings as a preset in your own /
     department / company folder (0272's locations).
C. **Cost and speed**: instancing, light versions by camera distance, nothing outside the camera's view, memory for
   e.g. a million grass blades, Live preview cost, a 4K Cycles frame (measured on the web machine; the RTX 3090 as an
   expectation, said as such); what can go onto the 3D page (0106's surroundings) and at what size.
D. **How the materials of the surroundings should be made**: procedural (as the machine looks today, `core/
   materials_lib.py` – no UV maps on STEP parts) or scanned image textures (0286's CC0 sources: real-looking ground,
   bark, rock; box / triplanar projection, memory), or both. Measure one ground both ways (time per frame, memory,
   look) and recommend.
E. **Prototype** on the branch: one terrain with painted layers, painted scatter (a tree, a bush, grass, a rock kind),
   one procedural building and a road; pictures + 2–3 short clips; then **phases and build tasks** with lanes (who
   owns `surroundings.py` today: the Sea lane's sea part, the Scene & Render lane's world) and models / efforts; the
   page with a design sketch, pick ticks and a Copy line (`0311 pick: …`).

## Done when

- [x] Report + page on the branch → the lead publishes the page for the owner's picks → build tasks

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 23 Nov 2026. Branch `task/0311-study-surroundings-maker` (pushed with `[skip ci]`,
never merged). No existing file changed: new files only (`tools/surroundings_proto/`, `tasks/0311_page/`).

**In short.** A working prototype builds a whole building site round the Lifting lane's AT-100 crane (Working pose) in
**≈ 3 s**: hills, the crane's flat pad, painted gravel / sand / mud / rock / concrete, a road cut into the slope, a pond that
fills its own hollow and paints its own shore, three buildings from a few settings, and trees, conifers, bushes, rocks and
grass placed by painting – plants follow the ground (no grass on the road, nothing on the pad or under water). Three
findings set the design: **copies, never merged meshes** (grass as copies +9 MB render memory, merged +181 MB);
**only what the scene camera sees** (crane close-up: 7,772 grass clumps instead of 88,085); **brushes must not re-place the
plants at every dab** (0.12–0.16 s each). Ground: **the app's own by default**, photo ground from the library as an option
(scanned rendered 2 × faster on the processor but took ~100 MB more and repeats at a distance). **Phase 1**: six new
one-click backgrounds from today's pieces (P1). Then the maker (M1–M6), then M7–M10.

**Page:** `tasks/0311_page/index.html` – pictures, three clips, the design sketch, the Map view, every table, the
build tasks with pick ticks and a Copy line (`0311 pick: …`).

### A · New ready-made backgrounds (one click, like today's 11)

Ranked by what the app's users need first (offshore wind, cable lay, cranes, machines, vehicles) against the cost.
"Phase 1" = can be built now from today's `core/surroundings.py` pieces (Box, Beam, Tube, Quad, Loft, the props, the
sea, the quay) plus a few new procedural ground materials – no maker needed.

| # | Background | Who needs it | What it holds | Phase 1 from today's pieces? | Cost |
| --- | --- | --- | --- | --- | --- |
| 1 ★ | **Building site** | cranes, lifting plans, machines delivered | gravel ground, site fence (posts + mesh panels), site huts (the containers stacked), barriers, pallets, skip, stacked steel and rebar, a parked mobile crane far off (Lifting lane's AT-40 as light shapes) | yes – gravel material new | low |
| 2 ★ | **Onshore wind farm** | offshore/onshore wind, cranes (blade lift) | meadow, crane pad (gravel), access road, 4–8 turbines at real size far off (tower Loft + nacelle + blades from `demo_model/turbine.py`'s own section shapes), a blade on its transport | yes – grass + gravel + asphalt materials new; turbines as Loft shapes | medium |
| 3 ★ | **Industrial yard** (outdoor, next to a hall) | machines, vehicles, lifting | asphalt yard with lines, hall walls (today's hall shell from outside), fences, containers, pallets, lamp posts | yes | low |
| 4 | **Road & crossroads** | vehicles (0306), transport of machines | 2-lane road with markings, kerbs, pavement, lamp posts, a crossroads, grass verges | yes (straight pieces; curves need the maker's road) | low |
| 5 | **Harbour basin** | cable lay, offshore loading | today's quay on two sides of a basin, the sea between, bollards, fenders, a moored work boat as shapes | yes – extends QUAY | low |
| 6 | **Beach / landfall** | cable lay (the cable's landfall), vessels (0312) | sand sloping under today's sea, dunes (Loft), a foam line where the water is shallow | partly: sand + slope yes; breaking waves are 0312's | medium |
| 7 | **Meadow** | everything (a neutral outdoor ground) | grass ground to the horizon, a far tree line | ground yes; real grass and trees need the maker's scatter | low (ground only) |
| 8 | **Forest edge** | product shots, vehicles | trees, bushes | no – needs scatter | maker |
| 9 | **Snow** | anything in winter | = Meadow / Building site + 0109's snow weather (already makes materials snowy) | yes, via weather | none |
| 10 | **Desert** | rarely | sand + dunes | after the maker | low value |

### B · The maker

Its own window (made like the output windows and the Set-up window, `ops_setup.open_window`) with tabs **Start ·
Ground · Paint · Plants & rocks · Buildings · Roads · Water · Save as preset**, and **Simple | More** at the top right:
Simple = presets, three brush sizes, the swatches; More = numbers (metres, %, seed, density per m², detail distance,
which plant grows on which ground). The view has three modes: **3D** (the brush is a circle on the ground, drawn as
hover.py draws), **Map** (top view in the layers' colours with height lines – page picture "map", made from the same
arrays in 0.3 s) and **Through the camera**.

- **Terrain.** One height grid (prototype: 0.5 m over 260 × 260 m = 271,441 points). Brushes Raise / Lower / Smooth /
  Flatten, Hills (fractal noise), Import (height-map picture, GeoTIFF, a mesh – later). The machine's **pad** is kept
  flat at the floor and free, blending into the hills (it follows the model's box, like today's `keepout`). Brushes are
  the app's own (a modal tool on `core/terrain.py`), not Blender's Sculpt mode: no mode switch for a sales person, the
  Client view's lock stays simple, the same strokes give the same result in tests, and the layers can stay normalised.
  Pen pressure comes with Blender's mouse events.
- **Paint layers.** Grass, gravel, sand, asphalt, concrete, rock, mud, snow – weights 0 … 1 per grid point that always
  add up to 1 (painting gravel makes the others give way; Erase = back to the base layer). The brush's edge is broken by
  noise when painting, and once more in the material, so no round "stamps" show. Stored as point attributes of the
  terrain mesh: they are saved with the project, undo works, and one material reads them (Attribute nodes, no
  pictures).
- **Scatter by painting.** One Geometry Nodes tree for every kind (trees, conifers, bushes, grass, rocks): the painted
  density × **what the ground allows** (grass only on grass, trees not on asphalt, nothing on the pad, nothing under
  water, the road's corridor clear) → points → instances. A density brush and an eraser. Every kind has a **detailed**
  and a **light** version (0155's rule): the light one beyond a distance from the camera. Nothing is made outside the
  **scene camera's** view (+ a margin); grass thins out between 15 and 45 m (the ground material carries the look
  further). Turning the 3D view with the mouse costs nothing – only moving the scene's camera makes it scatter again.
  - **Procedural or assets, per kind:** grass – procedural (16 blades a clump, 96 triangles; any amount); trees and
    bushes – procedural from the app's own maker (both versions from one seed, real size, no licence question, seasons
    later by settings; CC0 tree models are scarce – ambientCG has none, Poly Haven few); rocks – procedural first, CC0
    scanned rocks (Poly Haven) as an extra through 0286's library; debris – the app's props (pallets, barriers) and
    small rocks.
- **Buildings.** Hall (cladding ribs, roller doors, a window band, roof lights), office (floors, window strips, flat roof
  with a parapet), house, warehouse, site hut (the app's containers) – width, depth, floors, roof (pitched / flat /
  saw-tooth), windows, colour. **One facade material for all** whose colour is the building's own setting (an object
  attribute read by the material): colour is a setting, not a new material. Painting a colour on part of a facade =
  a face attribute painted the same way (not tried). A building flattens its footprint and paints its concrete apron.
- **Roads.** Drawn as a line of clicks; width and kind (2-lane asphalt, 1-lane, gravel track, concrete slabs); markings
  in the material from the road's own UVs (dashed centre line, edge lines, worn); kerbs optional; the terrain is **cut
  and filled** to a smooth profile with at most 6 % grade and 4 m shoulders; the corridor clears the scatter; gravel
  shoulders painted. Crossroads later (a junction patch where two roads meet).
- **Water.** A **pond / lake**: click a point in a hollow and a level → the water fills only what connects to that
  point (flood fill), not every low spot. **Sea**: today's sea; the shore is where the terrain goes under it. **River**:
  a line with width and depth that carves a bed (later). The shore paints itself: sand just above the water line, mud
  under it. **Hand-over to 0312** (breaking waves): the water's depth per grid point (`Terrain.depth()`) and the shore
  line; waves break where the depth is about 1.3 × the wave height.
- **Presets.** A preset = terrain arrays + roads + buildings + water + scatter settings + light / weather, one file per
  preset in 0272's locations as a new kind "Surroundings" (My / Department / Company, shared in a `.frsetup`). The ready
  ones are made in code and fit the machine (the pad follows its box): Building site, Onshore wind farm, Industrial
  yard, Road & crossroads, Harbour, Beach at sunset (= Beach + 0109's sunset), Meadow, Forest edge.
- **Vehicles (0306): one terrain for both.** A speed bump is a Raise stroke or a road object; an off-road track is
  Lower + Mud paint; wheels read the height and slope from the same grid (`Terrain.sample`, bilinear, vectorised).

### C · Cost and speed (web machine: 4 cores, no graphics card; Blender 5.2.3 as a module; Cycles on the processor)

| What | Measured |
| --- | --- |
| Build the whole site (terrain 271,441 points, all strokes, road, pond, buildings) | ≈ 3 s (strokes 1.8–2.0 s on a window round the brush; 11.7 s when every dab worked on the whole grid) |
| Place every plant (Geometry Nodes) | 0.05–0.27 s |
| One dab, raise, grass in view | 0.16–0.20 s = arrays 0.3 ms + mesh written 41–58 ms + plants again 0.12–0.15 s |
| One dab painting trees | 0.14–0.18 s |
| Scene camera moved (plants follow its view) | 0.11–0.14 s |
| Site pictures 1600 × 900, 96 samples | 2 min 1 s – 4 min 8 s; render memory 247–261 MB |

Grass at eye height (960 × 540, 32 samples; 16,139 clumps × 16 = 258,224 blades in view after culling and thinning):
none 41.9 s / 181 MB render memory / 1,335 MB Blender peak; **copies** 42.9 s / 190 MB / 1,434 MB; **merged** (1.55 M
triangles) 39.9 s / 362 MB / 2,068 MB. GRASS1M_LINE

Culling and light versions (640 × 360, 16 samples): whole site – culling + light 11.6 s / 160 MB, no culling 11.6 s / 160 MB
(52 instead of 42 trees), no light versions 11.7 s / 172 MB. Crane close-up – culling + light 6.3 s / 164 MB with 7,772
grass clumps; no culling 6.9 s / 210 MB with 88,085 clumps (1.4 M blades); no light versions 6.5 s / 176 MB.

FRAME4K_LINE

WEB_LINE

Live preview (Cycles in the 3D view) was not measured: no graphics card here; EEVEE in software took 33 s for one 640 × 360
picture of a cube. The plants follow the scene camera, not the 3D view, so turning the view never re-places them.

### D · Ground materials

Same flat field, same views, 960 × 540, 64 samples. App-made: 46.1 s (eye) / 65.0 s (closer), 149 MB render memory, no
files. Scanned (ambientCG Grass004 + Gravel017, 2048 px colour / normal / roughness, CC0, from a CC0 mirror on GitHub –
ambientcg.com was refused here): 23.2 / 27.8 s, 253 MB (the 6 maps take 96 MB as Cycles holds them), 37 MB of JPEGs.
Close up the scan reads as real rounded stones, the app's gravel as flat angular pieces; far away the scan repeats every 2 m.
**Recommendation:** the app's own ground by default (no files, no repeats, any colour, every layer paintable, snow and wet
from 0109 work); photo ground per layer as an option from 0286's library with the repeats broken up (M7); a cheaper app-made
gravel (four Voronoi lookups a point made it the slowest part).

### E · Prototype and pictures

`tools/surroundings_proto/`: `terrain.py` (heights, brushes on windows, layers that add up to 1, scatter densities, what grows
where, road cut and fill, flood-filled water, shore band), `shapes.py` (tree, conifer, bush, grass clump, rock – detailed and
light; buildings: hall / office / house, pitched / flat / saw-tooth), `scene.py` (the Blender scene: ground material from the
layers, road, kerbs, water, facade material with the colour per building, the Geometry Nodes scatter with light versions,
culling and thinning), `measure.py`, `clips.py`, `sketch.py` (Map view and the design sketch). Snags found on the way:
a far-ground plane at −1 m hid the pond (now a ring from the terrain's own border); a pond level taken from a hill flooded the
site (now a flood fill from a point); the sky's own sun disc doubled the sun and washed out every picture (off); a boolean in
the culling tree was the wrong way round, so nothing was culled (found by the top-view clip).

### Phases and build tasks

| Task | Phase · lane | Model · effort | After |
| --- | --- | --- | --- |
| **P1** ★ six new backgrounds + grounds (gravel, asphalt, grass, sand, mud) | 1 · Scene & Render | Opus · Medium | – |
| P2 beach / landfall | 1 · Sea lane | Opus · Medium | 0312's picks |
| **M1** ★ maker window, terrain in tiles, brushes, 8 layers, Map view | 2 · new Surroundings maker lane | Opus · High | – |
| **M2** ★ plants and rocks (app-made, two versions), scatter with culling, density brush | 2 | Opus · High | M1 |
| **M3** ★ roads | 2 | Opus · High | M1 |
| **M4** ★ buildings | 2 | Opus · Medium | M1 |
| **M5** ★ water: pond, lake, river, sea shore; hand-over to 0312 | 2 · with the Sea lane | Opus · High | M1 |
| **M6** ★ presets + saving in 0272's folders | 2 | Opus · Medium | M1–M5 |
| M7 photo ground from the library | 3 | Opus · Medium | 0286's build tasks |
| M8 surroundings on the 3D page | 3 · Web 3D lane | Opus · Medium | M1, M2 |
| M9 import a terrain; bumps and tracks for Vehicles | 3 · with 0306 | Opus · Medium | M1 |
| M10 seasons and wind | 3 | Opus · Medium | M2 |

Every build task adds its tour stop, PC-check line, function entry and guide section (CLAUDE.md section 6).

**Tested and measured:** web machine (4 cores, no graphics card), Blender 5.2.3 as a Python module, Cycles on the
processor; models: the Lifting lane's AT-100 (`fresing_render/data/lifting/AT-100`) and the prototype's own made-up terrain.
No app code changed, so no app tests were run. Subagents: none.

**Open points / follow-up tasks:**
- Not measured: Live preview and anything on the RTX 3090; a forest-size site (thousands of trees) for the light versions;
  the brush on 32 m tiles (designed from the measured full-mesh write); Blender's own Sculpt mode for comparison.
- Culled objects cast no shadows into the picture: keep ~30 m round the camera (M2).
- The prototype's procedural gravel is slow (four Voronoi lookups); M7 / P1 make a cheaper one.
- Licences: nothing is shipped. ambientCG's maps were used only to measure (CC0); a build task that ships photo grounds
  follows 0286 and adds them to `THIRD-PARTY-NOTICES.md`.
- Hand-overs: 0306 (one terrain, `Terrain.sample`), 0312 (`Terrain.depth()` + shore line), 0286 (photo ground, scanned
  rocks), 0272 (a new kind "Surroundings"), 0155 (the two-versions rule), 0106 / 0099 (the 3D page).
