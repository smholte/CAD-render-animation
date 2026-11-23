# 0301 – Study (findings + measurements only): faster STEP import – more cores and other gains

**Who:** worker · **Status:** done 23 Nov (findings on this branch) · **Branch:** `task/0301-study-faster-import` (branch only, never merged;
every push `[skip ci]`)
**Started by:** lead, 23 Nov 2026 (owner's list, 23 Nov 19:39: "Multicore step import / import time improvements.")
· **Model:** Opus · effort High
**Area:** findings only; measuring scripts in new files on the branch (e.g. `tools/import_timing/`); reads
`importer/step_reader.py`, `importer/runner.py`, `blender/build.py`, `blender/ops_import.py`, `logic.py`,
`pccheck/heavy_scene.py`, `docs/DEVELOPMENT.md` (measured timings). Not a code slot.

## Background

The reader meshes on all cores but one with helper processes (task 0074); reading the file and turning it into shapes
is one process. On the owner's PC (24 cores): the EGR line (78 MB, 2,789 parts – a GrabCAD model, not in the
repository; ask the owner to attach it if needed) 50–52 s at Normal, 40 s at Draft (2 Nov). Big invented models: the
PC check's Heavy machine (`heavy_scene.py`, ~3,000 parts, written at run time).

## What to find out

A. **Time per stage** on the Heavy machine and a larger invented one, with 1 / 2 / 4 helpers on the 4-core web machine:
   read (STEP parse), transfer to shapes (names, colours, tree), meshing, cache write, Blender build (objects, meshes,
   materials, collections), sorting rules, first draw. Which stages use one core.
B. **Options**, each with the expected gain on a 24-core PC (an expectation, said as one): parallel parsing (OpenCascade's
   own parallel options; reading sub-assemblies in helpers), meshing started while reading, fewer copies between
   processes (shared memory), a faster Blender build (`foreach_set` in bulk, fewer datablocks, instancing), showing the
   model early (Draft at once, Normal swapped in the background), a model update that reads only changed parts, keeping
   OpenCascade's own binary for re-imports.
C. **Ranked proposals** (gain / risk / work), the first one to build, and a PC-check Heavy line that measures the stages
   on the owner's PC.

## Done when

- [x] Report with the measured table and the ranked proposals on the branch → the lead briefs the build task(s)

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (worker), 23 Nov 2026. Branch `task/0301-study-faster-import`, never merged,
every push `[skip ci]` (0 GitHub runs). No subagents.

**What changed:** only new files on the branch – `tools/import_timing/` (`make_models.py` invented models,
`time_reader.py` + `time_worker.py` the reader's stages with a clock, `time_build.py` the Blender side,
`split_transfer.py` + `step_hash.py` two prototypes that only measure, `README.md`, `results/` the raw JSON). No app code.

**Tested and measured** – all on the **4-core web machine** (Intel Xeon 2.1 GHz, 15 GB, no graphics card), Normal
detail unless said. Models (all invented, written at run time, nothing committed): **Heavy** = the PC check's Heavy
machine at full size (`heavy_scene.py`, 23 MB); **Heavy as B-splines** (every part turned into B-spline faces, 46 MB);
**Big** = the same maker × 4 (96 MB – about the EGR line's 78 MB); the public **demo vessel** (12 MB, lofted hull).
Check of the instrument: the app's own reader took 11.6 s on Heavy with 3 helpers, the timed copy 11.2 s, same parts
and triangles.

### A. Time per stage

Whole reader, seconds (meshing stage in brackets), by number of meshing helpers:

| Model | file | unique / placed | triangles | 0 helpers | 1 | 2 | 3 | 4 | parse + transfer (one core) |
|---|---|---|---|---|---|---|---|---|---|
| Heavy (PC check, full size) | 23 MB | 600 / 2,992 | 2.26 M | 19.3 (13.7) | 18.9 (13.6) | 12.9 (7.5) | 11.2 (5.6) | 10.9 (4.7) | 4.5 s |
| Heavy as B-splines | 46 MB | 600 / 2,992 | 3.04 M | 34.0 (24.7) | 34.3 (25.4) | 24.9 (15.1) | 20.0 (10.4) | 18.3 (8.9) | 8.0 s |
| Big (Heavy × 4) | 96 MB | 2,400 / 11,968 | 9.46 M | 81.4 (58.0) | 86.7 (61.6) | 56.8 (32.7) | 48.5 (24.4) | 43.4 (20.2) | 19.8 s |
| Demo vessel | 12 MB | 86 / 106 | 0.42 M | 4.4 (1.5) | – | 4.5 (1.4) | 4.1 (1.1) | 4.2 (1.3) | 2.1 s |

Every stage of **Big, 4 helpers** (43.4 s) and the Blender side after it (same cache, Blender as a Python module):

| Stage | s | cores | Note |
|---|---|---|---|
| Parse the file (`ReadFile`) | 6.5 | 1 | OpenCascade; no parallel option in this build (93 read parameters, none parallel) |
| Transfer to shapes + names, colours, tree (`Transfer`) | 13.8 | 1 | the shapes alone: 10.9 s (prototype) |
| Material names (file text), tree walk, face colours | 0.9 | 1 | Python |
| Copy parts out to helpers (binary BRep, 20 MB) | 0.2 | 1 | |
| Meshing | 20.2 | 4 helpers | 77 part-seconds in all (58 s on one core – the rest is 4 cores sharing memory); biggest part 0.23 s |
| Collect results, write cache (npz 393 MB + json) | 1.1 | 1 | |
| **Blender: meshes** (2,400) | 4.7 | 1 | 3.1 s of it is `foreach_set` of co / vertex_index / loop_start |
| Blender: objects, properties, parents, links (12,081) | 2.4 | 1 | |
| Blender: sorting rules (`apply_rules`) | 2.4 | 1 | 2.3 s (in a profile of the same call) is `props._group_look_changed`: an update callback that walks every part, run once per group – 38 walks |
| Blender: bounds (`update_bounds`) | 1.2 | 1 | a Python loop over every part |
| Blender: tree, camera, surroundings, rest | 1.2 | 1 | |
| **Blender side together** | **12.1** | 1 | Heavy 2.8 s, demo vessel 0.9 s |
| First draw | – | – | needs a window and a graphics card: not measurable here (PC-check line below) |

Findings:
- **Only meshing uses more than one core.** Parse, transfer and the whole Blender side run on one core: on Big that is
  35 of the 55 s (reader + Blender) with 4 helpers, and it does not get shorter with more cores.
- **On a 24-core PC (an expectation, worked out from the numbers above, in this machine's seconds):** meshing ≈ 77 / 23
  ≈ 3.5–4.5 s, so Big would take about **27 s in the reader + 12 s in Blender ≈ 39 s, of which ≈ 35 s on one core**.
  The owner's PC is likely faster per core; the shares are what count.
- **Real CAD files lean even more on parsing.** The EGR line on the 2-core test machine (task 0010's report, with
  helpers): 58.8 s, meshing only 17.9 s → ~41 s reading. Our invented models have simple faces (planes, cylinders);
  Inventor files carry more entities per face.
- OpenCascade's own threads inside one part: +9 % without helpers (Big 58 vs 63 s meshing), **no difference with
  helpers** (48.5 vs 48.5 s). Draft instead of Normal: Big 33.2 vs 48.5 s (3 helpers) – only the meshing gets shorter.
- Copies between processes (out 0.2 s, back ≈ 1 s of overhead on Big): shared memory would gain ≤ 1 s.
- The demo vessel: its hull (one part) takes 0.6–1.1 s to mesh and sets the floor; more helpers change nothing.

### B. Options, measured where possible

1. **Faster Blender build** (measured on Big's cache):
   - meshes through the attribute API (`attributes["position"]`, `attributes[".corner_vert"]` `foreach_set`):
     **0.5 s instead of 3.1 s** for the same arrays (−2.6 s); `update(calc_edges=True)` stays (0.7–0.8 s).
   - sorting: one walk over the parts instead of one per group in `_group_look_changed` (expected −2 s of 2.4 s);
   - bounds from the cache's bounding boxes × matrices in NumPy (expected −1 s of 1.2 s);
   - a .blend of the meshes read back (`libraries.load`): 1.0 s for 2,400 meshes (but a background Blender must make
     them first, 564 MB file) – not worth it after the attribute API.
   - Fewer datablocks / instancing: nothing to gain – copies already share one mesh (2,401 meshes for 12,081 objects).
2. **Split the transfer over helpers** (prototype `split_transfer.py`, Big): each process parses the whole file and
   turns only its share of the parts into shapes (`STEPControl_Reader.TransferOne` by entity number). Shapes alone:
   10.9 s in one process, **2.5–3.1 s each in 4 at once**; four parses at once took no longer than one (6.0–6.7 s
   each). Parse + transfer + mesh in 4 processes: **30.8 s against today's 43.4 s** (4 helpers) – and that is on 4
   cores. The names, colours and tree would then come from the file text (as `step_meta.py` already reads material
   names: 0.4 s on Big), not from OpenCascade's XCAF transfer. **Memory:** parsing Big takes ~0.9 GB per process
   (Heavy 0.43 GB); 23 helpers each parsing would need ~20 GB, so: a few parsing helpers (by free memory) that
   transfer and pass parts on to mesh-only helpers, as today.
   On 24 cores (expectation, this machine's seconds): reader ≈ 6.5 parse + ~1–2 transfer share + ~3.5 mesh + ~1.5
   ≈ **12–13 s instead of ~27 s**.
   A cheaper half (expectation): keep the XCAF transfer in the reader and let the helpers parse + transfer + mesh in
   parallel – meshing then hides behind the reader's transfer: ~−4 s on Big; the same matching work, less gain.
3. **Model update reads only changed parts** (prototype `step_hash.py`): a hash of each part's shape entities with
   entity numbers left out. Heavy vs the same maker with one part more (all entity numbers shifted): **600 of 601 parts
   found unchanged**, 1.8 s per file (Big: 8 s in plain Python – in a helper, beside the parse). Today it could skip the
   meshing and Blender mesh of unchanged parts (~4 s + ~1.5 s on Big); after option 2 also their transfer. **Not
   known:** whether Inventor writes an unchanged part's entities the same way in a new export – needs two revisions of
   one of the owner's models (numbers only).
4. **Show the model early** (Draft at once, Normal in the background): the read is the same; on 24 cores it would show
   the model ~2 s sooner and then build everything twice. Not worth it.
5. **OpenCascade's binary for re-imports:** an unchanged file already comes from the app's cache in seconds; for a new
   revision the old binary does not help beyond option 3. Nothing to gain.
6. **Shared memory** between reader and helpers: ≤ 1 s on Big. Not worth it.
7. **OpenCascade's own parallel options:** none for reading in this build; meshing's in-part threads already on (no
   gain with helpers, possibly a small loss with 23 helpers – measure on the PC, see the line below).

### C. Ranked proposals

| # | Proposal | Gain on Big, 24 cores (expectation) | Risk | Work | Model / effort |
|---|---|---|---|---|---|
| 1 | **Blender build**: meshes via the attribute API, one walk in `_group_look_changed`, bounds in NumPy; + the PC-check line below + stage seconds in `tree.json` stats (parse, transfer, biggest part) | −5 to −6 s of ~39 (~15 %); every import, every model update, every project with many groups | low (same mesh; existing build/sort tests) | S | Sonnet · Medium |
| 2 | **Split transfer**: parsing helpers (count by free memory) transfer and mesh their share, the tree / names / colours / face colours from the file text; today's reader kept as fallback and as the oracle – A/B test on every test model that `tree.json` and the meshes match | −14 s (reader ~27 → ~13 s, ~35 %); more on real CAD files | high (XCAF's assembly rules re-done: instances, units, colours on faces, mirrored placements, AP203 / AP214 / AP242) | L | Opus · High |
| 3 | **Model update reuses unchanged parts** (hash per part, old cache's meshes) – first measure on two of the owner's revisions | on an update with few changes: −meshing and −Blender meshes now; after #2 also −transfer | medium (a false "unchanged" keeps an old shape: the hash covers the whole shape) | M | Opus · High |
| – | Early display, OCC binary, shared memory | ≤ 2 s | – | – | not proposed |

**Build first: #1** – small, safe, and the PC-check line it adds measures every stage on the owner's 24 cores, which
tells whether #2 is worth its risk (if parse + transfer are well under half of his import time there, #2 can wait).

**PC-check Heavy line (in #1):** `heavy.import_stages` "Big machine: where the import time goes" – imports the Heavy
machine once with the normal helper count and records: parse, transfer (+ names / tree), copy, meshing (wall),
part-seconds, biggest part, helpers used, cache write, then Blender: meshes, objects, sorting, structure, bounds,
surroundings, and **first draw** (time from the build's end to the first frame a draw handler in the 3D view sees,
plus the next 3 redraws) – `expected` ≈ 60 s; `shows`: which stages use one core on his PC; `not_shown`: a model with
real CAD surfaces (the EGR line imported by hand gives that: its `seconds_*` stats). Needs the reader to write
`seconds_parse`, `seconds_transfer`, `seconds_biggest_part` into `tree.json` stats (no cache-format change: stats are
free-form).

**Open points / follow-up tasks:**
- The lead briefs #1 (build task) and decides #2 after the owner's PC-check numbers.
- For #3: two STEP revisions of one of the owner's models (attached in a chat, numbers only).
- The EGR line was not attached; the shares above come from invented models plus task 0010's EGR numbers.
- First draw not measured (no graphics card here).
- Branch `task/0301-study-faster-import` stays unmerged (findings only); the owner can delete it after the lead's review.
