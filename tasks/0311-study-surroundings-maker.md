# 0311 – Study + prototype (findings only): a surroundings maker – terrain, paint, plants, trees, rocks, buildings, roads, water – and new ready-made backgrounds (beach, road, building site …)

**Who:** worker · **Status:** done 23 Nov (findings on the branch, waits for the owner's picks) · **Branch:** `task/0311-study-surroundings-maker` (branch only, never
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

- [ ] Report + page on the branch → the lead publishes the page for the owner's picks → build tasks

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
