# 0195 – Study: the cable-lay demo project running smoothly in the app – every function measured, ranked proposals

**Who:** worker · **Status:** done (findings only) · **Branch:** `claude/cool-thompson-esiw6v` (the web session's branch)
**Started by:** lead chat, 17 Nov 2026 (owner: "look through the entire model of the cable-lay demo project and all the
functions on how to optimise it, to get it to run smoothly in the app") · **Model:** Opus · effort High · **Place:**
Claude Code on the web, environment "CAD-render-animation"
**Area:** findings + measurements only: a report, a measuring tool `tools/measure_demo.py` (new, not app code) and its
small test. **No change to the app** – the lead turns the findings into fix tasks. Does not count as a code task.

## Goal

The owner works in the demo project (Help > Make demo project: ~2,400 parts, ~3,130 objects, ~3.6 M triangles,
4,481 frames, wind park, sea, cables, spools, tracks, people) and it should feel smooth: play, scrub, orbit the view,
select, open panels, change a setting. Find **where the time goes** in every function the demo uses, measured, and
propose fixes ranked by gain / effort / risk – so the lead can brief them as tasks.

## Background

- Known numbers (progress note, 17 Nov): playback ~39–45 ms a frame on the 4-core web machine (unloaded, Blender as a
  module); project ~226 MB; Make demo ~290 s+; Build 221 s on the small demo, the background re-bake 606 s (0183 row
  10 → **0192, running – do not re-measure that one**); web export ~23× too slow (0183 row 9 → **0189, running**).
- Earlier measuring work to build on, not repeat: `tools/measure_cables.py` (0159: Build by module, playback, live
  posing, memory for cables / spools / tracks), CLAUDE.md section 8 (frame pass ~7 ms a frame of Blender's own update,
  Geometry Nodes ~0.007 ms per object per frame, NumPy per-call cost, `logic.Tree` once per operation), 0149 (web size
  ranks), 0151 (render speed study), 0118 (speed per frame and per redraw), 0174 (+3.1 ms a frame after Build).
- No chat machine has a graphics card: drawing cost (triangles, draw calls, Material Preview, EEVEE) can only be
  measured on the owner's PC (RTX 3090, Ryzen 9 9900X, 24 cores).

## What to do

1. **Measure on the web machine** (real Blender 5.2.3 under xvfb where a window matters, Blender as a module where not;
   the made demo of `tests/demo_made.py`), each number with machine, model and how often repeated:
   - per frame while playing and scrubbing: split into Blender's depsgraph (drivers, constraints, Child Of to the
     vessel rig, modifiers per kind: FR flex / FR cable / spool trims / FR track / FR prop detail / decals / sea /
     marine looks …) and the app's Python handlers (`frame_change_*`, `depsgraph_update_post`: flex, paths, clash
     overlay, machining, labels, coolant, vessel work, …) – which run although the demo has nothing for them?
   - per UI action: redraw of each Fresing panel (the tree with 2,400 parts, joints list with ~445 joints, cables, the
     function list), select a part, hover, change a joint value live, a light look, a sea state, Undo / Redo, save,
     open, autosave.
   - memory and file size per kind of data (meshes, the shapes meshes of cables / flex, ID-property arrays, images).
   - the scene's make-up: objects, unique meshes vs copies (instancing), triangles per part group (vessel, park,
     quay, deck machines, people, props), modifiers per object, drivers count, constraints count.
2. **The model itself:** where the demo is heavier than it needs (parts nobody sees from the saved cameras, park
   turbines at full detail 2 km away, duplicated meshes not instanced, very fine round faces, the carousel's layers,
   marine pictures). Compare with what the importer's Draft / Normal give.
3. **What the owner measures on his PC:** `tools/measure_demo.py` – opened in the demo project, run from the app
   (write the steps click by click: Scripting tab → Open → Run, or a Help-menu-free way), it plays a fixed range in
   Solid and in Material Preview, orbits the view, times each panel redraw and writes one text block he pastes back
   (fps, ms per frame split, GPU memory, the top 10 costs). Test the tool here headless (a small test that it runs and
   writes its block); say which numbers are only real on his PC.
4. **Proposals:** a ranked table (gain in ms a frame / seconds per action, effort, risk, lane, model · effort), split
   into: app-wide (benefit every big project – the owner's own assemblies too), demo-model only, and settings the owner
   can switch himself today (e.g. Simplify, viewport detail of the park, hide surroundings in view). Mark any proposal
   that changes what a render shows.

## Rules for this task

- Findings only: no app code changed; the measuring tool and its test may be merged (tools/ only, with `[full run]`
  if the precheck wants it), the report goes to `main`.
- Numbers measured, never guessed (CLAUDE.md section 6); an expectation is called one.
- Up to 3 subagents for separate measuring areas (CLAUDE.md "Subagents"); real-Blender runs one at a time.
- Do not touch the files of running tasks (0189 Web 3D, 0192 cables, 0193 view clip, 0196 sea cut-away view).

## Done when

- [x] Report below: the scene's make-up, the per-frame split, per-action costs, memory, the model's heavy spots, the
      ranked proposals with lanes, and the owner's steps for `measure_demo.py`.
- [x] `tools/measure_demo.py` + its test on `main`; TASKS.md row moved to Done ("findings only").

## Not in this task

Fixing anything; the web export (0189); the background re-bake (0192); render speed on the GPU (study 0151).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (worker), 17 Nov 2026. Branch `claude/cool-thompson-esiw6v` (the session's
branch, not `task/0195-…`). No subagents (one measuring machine: real-Blender runs must not overlap).

**What changed:** new `tools/measure_demo.py` (the measuring tool, also for the owner's PC) and its test
`tests/test_measure_demo.py` (6 tests, ~6 s: a test-crane project with one of each kind the tool measures). No app code.

**Where and how it was measured.** The web machine: 4 cores, 15 GB, no graphics card. The **full** demo as the owner gets
it (`demo.build_project(small=False)`, app 0.2.146 on `main`): made here in 450 s (model 165 s = write 142 + import 23;
the final Build 127 s), 258 MB. Blender 5.2.3 as a Python module ("headless", 2 full runs of the tool) and the real app
under xvfb with Mesa llvmpipe ("app", 3 quick runs). The app's drawing numbers are software drawing and **not** the PC's;
everything marked "PC only" can only be measured with `measure_demo.py` on the owner's PC.
Repeats: per frame 5 runs × 40 consecutive frames (playing) and 80 frames far apart (scrubbing); switch-offs: each kind
off vs on before and after, 30 pairs, and the main ones again 4 × each (`focus`).
**Noise:** "all on" varied 51–70 ms a frame between measurements on this machine; only effects ≥ ~5 ms are firm.

### 1. Make-up of the scene (active scene, frame 1)

| What | Number |
| --- | --- |
| Objects | 3,696: 2,513 meshes, 1,156 empties, 22 cameras, 5 lights |
| Meshes | 527 unique; 2,180 objects share a mesh (instancing already used). Identical meshes not shared: 101 copies, 0.09 M triangles – negligible |
| Triangles drawn (shown objects, after modifiers) | **6.10 M** at frame 1 (6.65 M counting all that show in some shot) |
| … by collection | spools 2.51 M (49 objects; the carousel's 24 full layers 24 × 86 k = 2.06 M) · vessel 1.89 M (1,400) · park 1.46 M (762) · surroundings 0.22 M (the hull foam alone 217 k) · ROV 0.03 M; the quay (427 objects, 0.40 M) is hidden in this scene |
| Biggest objects | HULL BOTTOM 252 k · hull foam 217 k · RIM FENCE 140 k · 2 × WINCH DRUM 118 k · CABLE END 98 k · each carousel layer 86 k |
| Modifiers | 587, all Geometry Nodes: FR track 432, FR ride 68, FR spool layer 54, FR cable 11, FR spool 7 + hides 7, track run 4, ride run 2, On the water (hull foam) 1, FR flex 1 |
| Constraints | 22 (Copy Location 7, Locked Track 6, Child Of to the vessel rig 7, …) |
| Drivers | 1,020, **none needs Python** (476 transform, 340 custom property, 150 visibility, 24 shader, 20 modifier input) |
| Keys | 65,533 on 306 F-curves |
| Materials / images | 80 / 14 (10 MB of pixels) |

### 2. Per frame (no drawing)

| | headless (2 runs) | app (3 quick runs) |
| --- | --- | --- |
| Playing (consecutive frames) | **55 ms** (18 fps before drawing) | 42–48 ms |
| Scrubbing (frames far apart) | 65–69 ms | 54 ms |
| The app's Python handlers | **0.13 ms** of it | 0.15 ms |

- **Handlers:** five run on every frame although the demo has nothing for them (`flex._on_frame` 0.04 ms, `coolant._on_frame`
  0.03, `machining._on_frame` 0.03, `paths._on_frame` 0.02, `coolant._on_frame_pre` 0.01). Together 0.13 ms: **not worth
  a task.** No `depsgraph_update_post` handler runs while playing.
- **Blender's own update is all of it.** Switched off (focus, 4 repeats each): all 587 Geometry Nodes modifiers **30 ms**
  (27–32); the 432 **FR track** modifiers alone **15 ms** (13–18; both full runs 16–17); all 1,020 drivers 2 ms (−0.5–3.6);
  all 22 constraints nothing measurable. The vessel's collection left out: 20–34 ms (its parts' moves + its track
  parts). Smaller kinds (FR spool 4.6, FR cable 1–6, FR ride + run 0–7, hull foam's "On the water" 2.6–4.6, Locked Track
  0–3 ms) are inside the noise of single measurements; their sum is in the 30 ms above.
- So of ~50 ms: ~30 ms Geometry Nodes (half of it the track parts), ~2 ms drivers, the rest (~15–20 ms) Blender moving
  3,700 objects (keys, parents, the vessel rig). Earlier note (CLAUDE.md, task 0079): 0.007 ms per pass-through modifier
  per object; measured here on the full demo **0.035 ms per FR track part**.
- Drawing a frame (Solid, Material Preview), turning the view, playing with drawing, graphics-card memory: **PC only**.
  (llvmpipe: 286 ms a still picture, 430 ms a frame playing – meaningless for the RTX 3090.)

### 3. Per action

| Action | Measured | Where the time goes |
| --- | --- | --- |
| Select a part | **150–180 ms** (app, update + side panel; headless 180–260) | the app's part: 13–19 ms (`handlers._on_active_changed` builds `logic.Tree` once); the rest is Blender's own selection update – it stays 160–190 ms with all modifiers, drivers or constraints switched off; one object's move tagged = 27 ms |
| Hover of the axis pickers (one mouse move) | 4 ms again; first time on a part 12–18 ms median, 69–115 ms worst | the face table of a big part is built at the first hover |
| A joint moved live (one step) | 7–13 ms median, 19–34 ms worst | Blender's update |
| Side panel, the panels' own Python | **81 ms per redraw with every Fresing panel open**; Web 3D panel **39 ms**, Cables 11 ms, Weather 5.5, Motion 3.2, Import 3.1, Tracks 1.7, Structure 1.5 | Web 3D's draw works out its estimates every redraw (`light_estimate` / `marine_estimate` go over the parts and their polygon counts) |
| Light look (Overcast) | 0.4–0.6 s | `world.apply` |
| Sea state Calm ↔ Rough | **5.8–6.4 s** for the sea itself + the re-bake of cables and hoses (headless at once: **178 s** in two passes through 4,481 frames, `flex.read_steps`) | sea: `surroundings._water_material` 4.4 s (724 shader nodes made again, 3.4 s in `math`); re-bake = **0192**, not measured further |
| Undo step (after every change) | 0.12 s | Blender's memfile |
| Undo / Redo | 0.72 / 0.71 s | |
| Save a copy | 5.2–5.8 s in the app (compressed), 1.1 s headless | 258 MB |
| Open the project | 1.8–2.2 s | |
| Make demo | 450 s here (owner's PC ~290 s, progress note) | model write 142 s, Build 127 s |

### 4. Memory and file size

- Blender with the demo open: 2.2 GB (headless), 3.0–3.2 GB (app, software drawing).
- Mesh data (positions, corners, faces, attributes) **387 MB**, of which the cables' hidden **shapes meshes 236 MB**:
  "FR cable shapes Second end" 178 MB, "… Power cable" 58 MB (frames × points of the built cable). CAD parts: vessel 68 MB,
  ROV 20 MB (its tether 19 MB), park 15 MB, quay 14 MB, surroundings 9 MB, spools 4 MB.
- ID-property arrays 11 MB (`fr_cable_places` 8 MB). Images 10 MB.
- The project file is 258 MB, so the shapes meshes are most of it; they also go into every undo step and every save.

### 5. The model's heavy spots (what the shots see; 18 camera shots × 5 moments, frustum and on-screen size at 1920 ×
1080, **hiding behind other parts not counted**)

- **Carousel:** 24 full layers × 86 k = **2.06 M triangles (a third of all)**. From outside only the top layer and each
  layer's outermost turn can be seen (expectation from the geometry; not measured with occlusion).
- **Park:** 1.46 M triangles; 237 objects (0.45 M) never inside any shot, 234 more (0.29 M) never bigger than 4 px, 0.61 M
  never bigger than 20 px.
- **Draft vs Normal** (the importer's reader on the demo's STEP files): vessel 2.12 M → **0.87 M** placed triangles
  (−59 %), park 1.46 M → **0.87 M** (−40 %); reading time the same (12–14 s).
- **Hull foam** 217 k triangles + 2.6–4.6 ms a frame for its "On the water" modifier.
- Single parts: HULL BOTTOM 252 k, RIM FENCE 140 k (seen full-screen), WINCH DRUM 2 × 118 k, CABLE END 98 k.
- Not heavy: duplicated meshes (0.09 M), drivers (all simple expressions), the app's frame handlers.

### 6. Proposals, ranked (gain / effort / risk; lane; model · effort)

**App-wide (every big project, the owner's own assemblies too):**

| # | Proposal | Gain (measured basis) | Effort | Risk | Lane | Model |
| --- | --- | --- | --- | --- | --- | --- |
| A1 | Track parts without one modifier each: the track's run object draws all its parts (instances of each part's mesh on its points), the part objects hidden but kept for looks/selection; or modifiers only on parts that are shown | up to **15 ms a frame** (of ~50) on the demo; ~0.035 ms per part on any track | medium | medium: 0079 chose per-part modifiers so looks, hiding and selection stay the part's own | Flex parts | Opus · High |
| A2 | Smaller cable shapes meshes: keep a frame only where the shape changes (or every n-th frame + interpolation in the nodes), store float16 offsets from a base line | file ~258 → ~80–100 MB (expectation), save 5–6 s → ~2 s, less memory, faster undo | medium | low–medium (a cable must not jump between kept frames: test against the full table) | Flex parts | Opus · High |
| A3 | Side panel: no work in `draw` – Web 3D's estimates (39 ms a redraw) and Cables (11 ms) cached and refreshed on change, not walked per redraw; a test that times every panel's draw on a big project (this tool's panel step) | ~50 ms off every redraw of the side panel while those panels are open (mouse moves over the panel redraw it) | small | low | Web 3D + Flex | Sonnet · Medium |
| A4 | Sea / light change: keep the sea's water material and node groups and change only their numbers instead of making 724 nodes again | ~4–5 s of 6 s per sea-state / weather change | small–medium | low (render must stay the same: compare a render) | Sea | Sonnet · Medium |
| A5 | Viewport detail for big CAD parts by distance (as "FR prop detail" does for props): far parts drawn as a lighter mesh (Draft-like) or a box in the 3D view only, never in renders | drawing only (**PC only** to measure): on the demo the park's 1.46 M and the far vessel parts | large | medium | Looks / Import | Opus · High |
| A6 | Selecting: the part tree (`logic.Tree`, 13–19 ms) not rebuilt on every selection change when nothing else changed | 13–19 ms of 150–180 ms per click; the rest is Blender's (fewer objects would help: 1,156 empties) | small | low | Motion / tree | Sonnet · Medium |
| A7 | Hover: build the face table of the parts under the mouse when the picker starts, not at the first hover | first hover over a big part 70–115 ms → ~4 ms | small | low | Pick & hover | Sonnet · Low |

Not proposed: the five idle frame handlers (0.13 ms together), drivers (2 ms, all simple), instancing of the 101 duplicate
meshes (0.09 M triangles), constraints (not measurable).

**Demo model only (Demo models lane; each changes what the 3D view shows; renders should look the same – check the shots):**

| # | Proposal | Gain | Effort | Risk | Model |
| --- | --- | --- | --- | --- | --- |
| D1 | Carousel: full layers drawn only where they can be seen (top layer whole, lower layers their outer turn) | **−1.9 M triangles** (−30 % of all; drawing, PC only) | medium | low–medium (changes the render only if a camera looks into the coil) | Opus · Medium |
| D2 | Park imported at Draft (or its parts that no shot sees left out of the demo) | −0.6 M triangles (Draft) / −0.45 M (never seen) | small | low (Draft facets on turbines 1–2 km away) | Sonnet · Medium |
| D3 | Hull foam lighter (217 k triangles) | −0.2 M triangles, ~3 ms a frame | small | low (render: check shot 8 and the sea shots) | Sonnet · Medium |
| D4 | The few heavy single parts (HULL BOTTOM 252 k, RIM FENCE 140 k, WINCH DRUMs 2 × 118 k, CABLE END 98 k) made with fewer facets in the model maker | −0.4 M triangles (expectation) | small | low | Sonnet · Medium |
| D5 | Vessel at Draft: −1.25 M triangles, but the close-up shots would show facets – **not proposed** unless A5 comes |

**Settings the owner can switch today (no task):**

1. **Play in Solid**, use Material Preview only to look at a still frame (Material Preview's cost: PC only – the tool measures it).
2. **Hide what you don't work on**: in the Outliner click the eye of `demo_park` and `FR spools` (2.5 M + 1.5 M triangles
   less to draw; per frame barely changes: their update is small). Show them again before rendering – renders use the
   camera icon, not the eye, so a render still shows them only if their camera icon is on.
3. Timeline > Playback > **Sync: Frame Dropping**: the animation keeps real time and skips frames instead of slowing down.
4. Close the Web 3D model and Cables folds in the side panel while working (50 ms less per side-panel redraw).
5. Change the sea state only when needed: each change makes the sea again (~6 s) and starts the cables' re-bake (minutes).

### 7. The owner's measurement on his PC (`tools/measure_demo.py`)

1. Open the demo project (Help > Make demo project, or File > Open). If it has unsaved changes, save it (Ctrl+S).
2. At the top of the window click the tab **Scripting**.
3. In the text editor in the middle click **Open**, pick `measure_demo.py` (download it from
   https://github.com/smholte/CAD-render-animation/blob/main/tools/measure_demo.py – button "Download raw file") and click
   **Open Text**.
4. Click **Run Script** (▶). The window stands still and flickers for about 3–10 minutes: don't click. At the end the project
   is opened again by itself (everything the tool changed is put back).
5. The text editor shows "Fresing measure": click in it, Ctrl+A, Ctrl+C, paste it into the lead chat. The same text is in
   the project folder as `<project name> - measure.txt` (written after every part, so if Blender closes during the run,
   open that file in Notepad and paste what it holds).
   What it says on his PC that cannot be measured here: drawing a frame in Solid and Material Preview, turning the view,
   playing with drawing (fps), the graphics card's memory (`nvidia-smi`), the side panel's real redraw time; and all the
   CPU numbers above on 24 cores.

**Tested and measured:** see "Where and how" above. `tests/test_measure_demo.py`: 6 passed (6 s). The tool ran on the full
demo headless twice (669 s / ~12 min each, all sections) and in the app under xvfb three times (quick, 142–412 s, all
sections, project opened again at the end, Blender closed normally). **Material Preview crashed Blender under llvmpipe**
(segmentation fault in drawing): the tool now skips it on software drawing, runs it last on a real card and writes its text
file after every section. Whether it runs on the RTX 3090 is not tested (no card here).

**Open points / follow-up tasks:**
- The lead turns A1–A7 and D1–D4 into tasks (A2 next to 0192 in the Flex lane). All numbers are of app 0.2.146; 0189 (Web 3D
  export, done meanwhile) may have changed the Web 3D panel's 39 ms – measure again with the tool before briefing A3.
- The owner runs `measure_demo.py` once on his PC (steps above) so the drawing side (GPU) gets numbers; proposals A5 and D1–D4
  are sized by triangle counts until then.
- The sea-state re-bake (178 s headless here, two passes through the frames) is 0192's.
- GitHub runs: 1 full run, green (run 44179290745, 23.4 min – several jobs SLOW while other tasks' runs shared GitHub);
  then a docs run after merging `main` (it had moved by documents only).
