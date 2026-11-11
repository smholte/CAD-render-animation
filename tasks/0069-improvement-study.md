# 0069 – Improvement study: what to add, and what could be done a better way (findings only, no code changes)

**Who:** worker · **Status:** done – report only (11 Nov 2026) · **Branch:** `task/0069-improvement-study` (pushed as `ccr-9a271780-u8jl9p`, the branch this web session was given)
(the report only – **do not push to `main`**: other workers fast-forward `main` tonight; the lead brings it over)
**Started by:** lead chat, 11 Nov 2026 (owner's wish) · **Lane:** none – reads code and searches the web, **changes
no app code, tests or tools**, so it runs next to every lane (tonight: 0029, 0067, 0068)
**Model:** **Opus · effort High** · **Environment:** "CAD-render-animation"

## Goal

Fresing Render has grown fast (0.2.53, ~35 sub-panels, every feature on the owner's list nearly done). Before the
next round of planning, the owner wants an outside look: **what else should the app do, and which things it already
does could be done in a better, faster or simpler way.** The result is a ranked write-up the lead turns into tasks.

## Who uses it, for what (keep the ideas aimed here)

The owner makes realistic stills and animations of large machines from Inventor STEP files (AP214/AP242, up to
~3,000 parts): offshore wind / cable-laying machines (winches, cranes, tensioners, carousels), and his startup's
CNC mill (LinuxCNC, BT30, double-arm tool changer, 4th/5th axis later), for marketing videos, the website and
customers. One Windows PC (Ryzen 9 24 cores, RTX 3090), Blender 5.2.3 under the hood. He is an engineer, not a
programmer and not a 3D artist: short paths from STEP to a good result matter more than knobs.

## What to do

1. **Know what is there first:** CLAUDE.md, `TASKS.md` (Done + Open), `CHANGELOG.md`, `docs/USER-GUIDE.md`, and the
   reports' "Open points" in `tasks/`. Do not suggest what already exists – suggest improving it, with what is weak.
2. **Look outside** (web search; name every source):
   - **Tools people use for the same job:** KeyShot (incl. its animation and CAD import), SolidWorks Visualize,
     Inventor Studio, Fusion's render/animation, Twinmotion / Unreal (Datasmith), Omniverse, Blender CAD add-ons,
     machine-builder marketing videos. Which of their functions would matter for these machines and are missing
     here (e.g. section/cutaway views, X-ray, assembly/exploded sequences, variants, interactive 3D on the website,
     AR, configurators)?
   - **CNC simulation:** CAMotics, NC Viewer, Vericut, Fusion simulation, LinuxCNC's own preview – what they show
     that our milling does not, and how they remove material (dexels/tri-dexels, voxels/SDF, GPU) vs our mesh
     boolean per straight move.
   - **Offshore/heavy-lift visualisation:** wire rope, sheaves, sea state, vessel motion, lifting sequences – what
     such videos usually show (feeds "motion paths", owner's priority 4, and later tasks).
3. **Better ways for what the app already does** – read the code of each area and compare with known methods,
   e.g.: STEP import and tessellation (OCCT settings, instancing of repeated parts, LOD), materials and looks, render
   speed and quality (Cycles/EEVEE settings, light tree, denoising, persistent data, adaptive sampling, render passes),
   video encoding, memory on big models, material removal and chips, clash check speed, the render queue, the
   installer/update path, the test run. Where a claim is cheap to check, **measure** it with a small script in a
   scratch folder outside the repository (time-box each to ~20 min) and give the numbers.
4. **Workflow from Inventor to a finished video:** what could the app read or do so the owner sets up less by hand
   (joints or constraints from CAD, STEP AP242 kinematics/PMI, Inventor or Fusion exports, templates, presets per
   machine type, batch renders of variants)?
5. **Write up** in this file (below), worst-gap or best-value first:
   - **Table:** `# · idea · what the owner gets (one sentence, in his terms) · kind (new feature / better way /
     faster / simpler / quality) · effort (S/M/L) · risk · evidence (source links, measured numbers) · lane · model`.
   - Three short lists after it: **quick wins** (S effort, clear value), **big ones worth a Fable day**, and **ideas
     looked at and dropped** (with one line why – so they are not looked at again).
   - Sources at the end. Plain language; the owner reads the top 10 rows himself.
   Helper agents may search areas in parallel (at most 4, one area each); the main session checks each idea against
   the code before it goes in the table (no "missing" feature that actually exists).

## Done when

- [x] What exists read first; every row checked against the code; every outside claim has a source or a measurement.
- [x] Table ranked, quick wins / big ones / dropped lists, sources.
- [x] No change to app code, tests or tools; the report pushed to `task/0069-improvement-study`.

## Not in this task

Building or fixing anything (that is for the tasks the lead makes from this). Bugs (0068 hunts those tonight – if you
trip over one, note it in one line). The owner's own files (the repository is public).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (Opus, effort High), 11 Nov 2026 (night). No app code, tests or tools changed;
no GitHub run needed. Four helper agents searched the web in parallel (render tools; CNC simulators; offshore videos;
Inventor routes + Cycles), each row below was checked against the code (file named in the row) by the main session.
Measurements: small scripts in a scratch folder, 4-core web machine, bpy 5.2.3 / OCP 8.0 / manifold3d 3.5.4.

### Measured tonight (M1–M5)

| # | What | Result |
| --- | --- | --- |
| M1 | Milling (`core/machining.py` Timeline, Normal) on a dense 3-axis finishing program: ball Ø6, 100 × 60 mm, wavy surface, 0.3 mm step-over, 40,401 points | merged into **13,911 segments**; 1,000 segs 8.1 s, 3,000 27 s, 6,000 58 s, 10,000 105 s (**8.1 → 10.5 ms per segment, rising**), 189,000 triangles in 12 tiles at 10,000; whole program ≈ 2.4 min. A dome at 0.5 mm step-over: 3,586 segments, 30 s, 61,500 triangles. Same 40,400 moves on a **NumPy height map** (0.1 mm grid, 1,000 × 600, plain Python loop): **2.8 s** – about 50× faster, but 3-axis only and no exact edges |
| M2 | Glowing toolpath in renders: 480,000 emission triangles (tubes like `gcode._material`), 480 × 270, 16 samples, Cycles CPU | **1.95–2.55 s per frame** with Blender's default *Emission sampling = Auto* vs **0.61–0.64 s** with *None* (`surroundings.py` already sets None for its lamps; `gcode.py` and `air.py` do not) |
| M3 | OCCT meshing at our three Detail settings (`step_reader.QUALITY`, relative deflection) – segments round a cylinder / gap between facet and true surface | bolt Ø10: Draft 29 / 0.03 mm, Normal 47 / 0.01 mm, Fine 75. Shaft Ø100: 26 / 42 / 70 (0.36 / 0.14 / 0.05 mm). Drum Ø2 m: 50 / 82 / 129 (2.0 / 0.73 / 0.30 mm). **Carousel Ø10 m: 50 / 82 / 129 (9.9 / 3.7 / 1.5 mm)**. So a small bolt gets more facets than it can ever show, a 10 m carousel shows facets on its outline in close-ups |
| M4 | glTF export (web 3D) in bpy 5.2.3 after a normal app import | works: test_machine 12 objects, 8,291 triangles → 0.15 MB GLB in 0.1 s; Draco compression gave the same size in the bpy module (not checked in real Blender) |
| M5 | What Blender 5.2.3 offers that the app does not use | motion blur (`render.use_motion_blur`), H.265 / AV1 / ProRes and 10/12-bit video, `bpy.ops.cycles.denoise_animation` (OptiX temporal denoise); light tree is on by default. Already used by the app: persistent data in the queue, OIDN on the GPU, adaptive sampling, PNG frames then H.264 |

### Findings – ranked (best value first; the owner reads the top 10)

Effort S ≈ ≤ 1 day of a worker, M ≈ one task, L ≈ a Fable day or more. Evidence numbers [n] are in the Sources list.

| # | Idea | What the owner gets | Kind | Effort | Risk | Evidence | Lane | Model |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Cutaway / section view**: a cutting plane (box) through chosen groups, cut faces filled with a cap colour, the plane can move in an animation step | Show the inside of a winch gearbox, tensioner or spindle in one click, also animated ("the housing opens up") | new feature | M | medium (cap trick needs closed solids – STEP solids are) | KeyShot cutaway with caps, animatable [1]; Twinmotion section cube [9]; CIMCO section view [21]; standard in machine-maker videos [14][15]. App: only the hall walls have a cut-away (`surroundings.py`); nothing for parts | Looks + Motion (new files, one step kind) | Opus · High |
| 2 | **Ghost / X-ray look and a Fade step**: an X-ray material for a group, and an animation step that fades a subassembly out/in (instead of the instant Show/Hide) | The housing fades away to reveal the mechanism, then comes back – the most common shot in machine videos | new feature | S–M | low | KeyShot X-ray material [2]; Inventor Studio *Fade* action [5]; "housing faded in and out" [15]. App: Show/Hide steps are instant (`animation.py`, CONSTANT keys); no X-ray look | Motion (step) + Looks (material) | Sonnet · Medium |
| 3 | **Motion paths done the offshore way** (owner's priority 4): rope over sheaves as tangent lines + arcs with a mark that runs along, tensioner track links as rigid pieces spaced along a closed path, drum spooling layer by layer (opposite hand per layer), catenary into the sea that keeps its length | The core shot of every cable-lay video: carousel → tensioner → chute → sea, everything moving at one cable speed | new feature | L | medium | Videos [30][31][32][33]; Geometry-Nodes track links [35]; rope/proximity [36]; spooling geometry [37]; length-keeping catenary node [38]. App: nothing yet (task 0006/priority 4); 0058 (hoses) builds the curve base | Flex parts (after 0058) | Fable · High |
| 4 | **Vessel motion at sea**: deck heave / pitch / roll from a sea state (sum of a few waves, worked out in Python and keyed – works with scripts off), plus a "compensated vs not" switch for one part (hook, chute, gangway stays still) | The machine really works on a moving ship; the classic "ship moves, load stays still" shot for motion-compensated equipment | new feature | M | low–medium | MacGregor / Ampelmann / Huisman videos [31][32][34]; RAO superposition [39]; Blender Ocean modifier has JONSWAP [40]. App: sea waves move (`surroundings.py`), the deck and machine do not | Scene & Render | Opus · High |
| 5 | **Toolpath and air cone stop lighting the scene** (`mat.cycles.emission_sampling = "NONE"` in `gcode._material` and `air.py`, as `surroundings.py` already does) | Renders with *Toolpath in renders* on no longer slow down with long programs (and have less noise) | faster | S | low | **M2**: 2.0–2.6 s → 0.6 s per frame on 480k glowing triangles; light-tree build blows up with many emissive triangles [26] | Machining | Sonnet · Low |
| 6 | **Motion blur** switch for videos (off / a little / real), on by default only for spindles and chips if needed | A turning spindle, flying chips and fast moves look like film, not stop-motion; the spindle could run at its real speed | quality | S–M | medium (blur needs every motion at in-between moments: drivers and keys are fine; handler-driven things – milling mesh, mechanisms – must be checked) | KeyShot animation motion blur [3]; Unreal reference motion blur [10]; M5 (Blender has it). App: not set anywhere; spindle is slowed to ≤ 1/7 turn per frame instead (USER-GUIDE 6) | Scene & Render | Opus · Medium |
| 7 | **Camera that rides along or follows a path**: camera fixed to a moving part (carriage, boom tip) or flying along a curve; "keep this part in the middle" | Fly-along the cable path, ride on the gantry while it cuts, follow a hook – without setting many cameras | new feature | M | low | KeyShot camera paths [3]; Twinmotion sequences [9]; fly-along shots in cable-lay videos [30]. App: Cut / Move to / Orbit only; just the *sharp spot* follows a part (`cameras.py` "Follows the part") | Scene & Render | Sonnet · Medium |
| 8 | **Faster material removal for dense 3-axis programs**: a height map (or dexel) cutter for 3-axis finishing passes, Manifold kept for the rest, mesh made once per frame from the map | Long CAM finishing programs (and 0029's own raster finishing) cut in seconds instead of minutes, with fewer triangles | faster | L | high (must keep 0061's "which move made this face", 5-axis stays on Manifold) | **M1**: 10.5 ms per segment and rising vs 2.8 s for the whole program on a height map; industry uses dexels / voxels [17][18][19]; Blender 5.2 has SDF grid booleans [20] | Machining (after 0029, 0061) | Fable · High |
| 9 | **Assembly sequence step**: one step that explodes / assembles a subassembly piece by piece in tree order (staggered), optional trail lines | "How it is built" videos in one click instead of many Show steps and poses | simpler | M | low | Inventor Presentations: auto explode, trails, reverse play [6]; Fusion auto-explode + trails [7]; KeyShot exploded animation [4]; Twinmotion phasing [9]. App: Explode (one pose) and Show/Hide steps exist, no staggered sequence | Motion | Opus · Medium |
| 10 | **Joints from Inventor / Fusion**: a small script for Inventor (iLogic) and Fusion that writes the assembly's joints (type, origin, axis, limits, the two occurrence names) to a JSON next to the STEP; the app reads it at import and makes the joints | Joints set up in CAD come over with the model; no clicking holes again after each revision | simpler | L | high (Inventor side can only be tested on the owner's PC; classic constraints may not be readable) | STEP from Inventor/Fusion carries **no** joints [22]; AP242 kinematics rarely implemented [23]; Fusion API `Joint.geometryOrOriginOne`, `jointMotion` [24]; Inventor `AssemblyJoint` / `AssemblyJointDefinition` [25]. App: matches occurrences by `fr_instance` ("Frame:1"), so names line up | Motion + Import | Fable · High |
| 11 | **Colour by deviation and by tool** on the milled part: blue = material left, green = on size, red = cut too deep, against the finished CAD part; and each tool's cut in its own colour | Check a CAM program before it runs on the startup's mill; a clear "this is what T2 did" picture for customers | new feature | M | low (the finished part is already in milling) | Vericut AUTO-DIFF [11]; Fusion stock comparison [12]; FeatureCAM part compare [13]; Vericut cut colour per tool [11]. App: "Finish at the CAD part" exists (`core/machining.py`), no colouring; 0061 will know each face's move | Machining (after 0061) | Opus · Medium |
| 12 | **Variants in the queue**: "Queue this animation in every paint scheme" (or chosen schemes), file names with the scheme | One evening of rendering gives the same video in every colour option for a customer | simpler | S | low | KeyShot queue "all Studios / sub-materials" [4]; Visualize configurations [8]. App: saved scenes have *Queue all* (stills), schemes exist, animations are queued one at a time | Motion (queue) | Sonnet · Medium |
| 13 | **Trail line of a part**: draw the path a chosen point (hook, tool tip, carriage) takes during the animation, in renders too | Shows a lift path or reach envelope at a glance | new feature | S–M | low | Inventor / Fusion trail lines [6][7]; hook paths in lift planners [42]. App: only the G-code toolpath has tubes (`gcode._node_group`); reuse that | Motion | Sonnet · Medium |
| 14 | **Steady videos** (no crawling noise): first a test on the owner's PC; if it flickers, an option that renders the extra passes and runs OptiX temporal denoising, or more samples for flat areas | Calm walls and floors in long videos | quality | M | medium (temporal denoise reported "helps, not fully stable" [27]) | M5: `cycles.denoise_animation` exists in 5.2.3; OIDN denoises each frame alone [27]; OIDN 3 temporal not out yet [28]. App: OIDN per frame, motion threshold 0.05 (`render.MOTION_THRESHOLD_FACTOR`) | Scene & Render | Opus · Medium |
| 15 | **Interactive 3D model for the website / customers** (glTF + Google's model-viewer on the landing page; AR on phones later) | A customer turns the machine on the website or a phone instead of watching a still | new feature | M | medium (procedural materials must become plain colours or baked textures) | KeyShot web viewer + glTF/USDZ AR [4]; model-viewer [16]; **M4**: export works in bpy 5.2.3. App: no export; `site/` exists | Quality & delivery (`site/`) + Looks | Opus · Medium |
| 16 | **Cycle time with acceleration**: use the machine's max acceleration per axis (LinuxCNC INI values typed in) for the G-code timing | "Real time" videos and the step's time match the real machine (short moves now come out too fast) | quality | M | low | G-Wizard estimate with acceleration [29]; NCSIMUL / Eureka cycle times [21]. App: "Moves are timed without acceleration" (USER-GUIDE 6) | Machining | Opus · Medium |
| 17 | **Smoother big round parts, lighter small ones**: cap the facet gap in millimetres for big parts (e.g. ≤ 0.5 mm at Normal), fewer segments for parts under ~20 mm | Carousels, drums and slewing rings have smooth outlines in close-ups; fasteners cost fewer triangles | quality | S–M | low (bump `CACHE_VERSION`) | **M3**: Ø10 m ring 3.7 mm facets at Normal, a Ø10 bolt 47 segments; OCCT deflection options [26b] | Looks (importer) | Sonnet · Medium |
| 18 | **One-click standard product video**: a template that builds title card, turntable / orbit, explode + assemble, the machine's motion steps, end card from what the project already has | A first complete video in minutes, then adjusted | simpler | M | low | Usual structure of machine videos [14][15]; Fusion / Inventor storyboards [6][7]. App: all pieces exist (turntable, explode, steps, cards) but are set up by hand | Motion | Sonnet · Medium |

### Quick wins (S, clear value)
- **#5** toolpath / air glow → *Emission sampling None* (two lines, measured 3–4× on the toy frame).
- **#2** Fade step + X-ray look (the step alone is S).
- **#12** queue an animation in every paint scheme.
- **#13** trail line of a part (reuses the toolpath tubes).
- **#17** facet gap cap for big round parts.

### Big ones worth a Fable day
- **#3** motion paths: rope over sheaves, tensioner tracks, drum spooling, catenary (owner's priority 4, after 0058).
- **#8** height-map / dexel cutter for dense 3-axis programs (after 0029 and 0061).
- **#10** joints from Inventor / Fusion through an export script (needs the owner's Inventor for testing).
- **#1** cutaway, if it should also cap thin sheet parts and work with milling.

### Looked at and dropped (one line why)
- **STEP AP242 kinematics** – Inventor and Fusion do not write it; OCCT reads it only into its low-level model [22][23].
- **Custom iProperties / user attributes through STEP** – Inventor does not export them [22b].
- **Inventor Dynamic Simulation export** – only to Inventor Studio, DWF or Excel graphs [22c]; #10 is the better route.
- **USD / Datasmith / Omniverse routes** – no joints either, and STEP already gives tree, names and colours [24b][8b].
- **Path guiding** – Cycles CPU only; the owner renders on the RTX 3090 [26].
- **Scrambling distance** – 1–5 % on OptiX only, can show patterns [26].
- **OptiX instead of OIDN denoiser** – OIDN already runs on the GPU and keeps detail better; no gain worth a task [27].
- **EEVEE for final videos** – Fast preview exists; the owner wants Cycles realism.
- **H.265 / AV1 as default** – H.264 plays everywhere (PowerPoint, Windows); keep it, maybe offer later.
- **Render passes, Cryptomatte, EXR** – for compositors; the owner finishes videos in the app.
- **Sun from place and date** – the Outdoor sun look covers it.
- **Render farm / second PC** – one PC.
- **Web configurator** – after #15, only if customers ask.
- **FLIP-fluid wakes and half-under-water shots** – one example baked 20 h and rendered 56 h [41]; fragile.
- **Full GPU dexel rewrite of milling** – the hybrid of #8 gives most of the gain without leaving Python.
- **Light tree off** – it is the default and helps with many lamps; #5 removes the actual cost.

### Notes
- **No bugs found** that belong to 0068; the toolpath glow (#5) is a speed point, not wrong output.
- "Toolpath in renders" is off by default, so #5 costs only those who tick it; with a 20,000-line program it is many
  tubes (`PATH_RADIUS` 0.4 mm).
- Helper agents could not open help.autodesk.com, developer.blender.org or youtube.com pages (blocked hosts): those
  sources rest on search-result text. Video contents in [30]–[34] are from their titles and descriptions.
- Measurement scripts were kept outside the repository (not committed).

**Sources:**

[1] KeyShot cutaway material – https://manual.keyshot.com/keyshot10/?p=4213 , https://www.engineering.com/?p=26020
[2] KeyShot X-ray material – https://manuals.keyshot.com/kss2025/manual/xray.html
[3] KeyShot animation: camera paths, depth of field, motion blur – https://manual.keyshot.com/?p=6180 , https://www.tristar.com/keyshot/animation/
[4] KeyShot exploded animation, render queue, web viewer, AR – https://www.keyshot.com/blog/creating-an-exploded-view-animation-with-keyshot , https://manuals.keyshot.com/kss2026/en-us/manual/render-dialog-queue.html , https://manuals.keyshot.com/kss2025/manual/keyshotweb.html , https://manual.keyshot.com/?p=5022
[5] Inventor Studio actions (constraint, fade, camera) – https://help.autodesk.com/cloudhelp/2025/ENU/Inventor-Help/files/GUID-BE01AA75-8B7B-4E2D-833C-0385F7A1B165.htm
[6] Inventor Presentations (auto explode, trails, reverse) – https://help.autodesk.com/cloudhelp/2021/ENU/Inventor-WhatsNew/files/GUID-95946F83-2758-45EC-A41C-93DE04D712BB.htm
[7] Fusion animation workspace – https://www.autodesk.com/products/fusion-360/blog/fusion-360-animation-deep-dive/
[8] SOLIDWORKS Visualize configurations / motion import – https://www.solidworks.com/sw/docs/SW_Visualize_Top_Professional-only_Features.pdf , https://blogs.solidworks.com/tech/2018/12/how-to-export-motion-studies-to-solidworks-visualize-professional.html
[8b] Datasmith reimport – https://dev.epicgames.com/documentation/en-us/unreal-engine/datasmith-reimport-workflow-in-unreal-engine
[9] Twinmotion section cube, sequences, phasing – https://forums.unrealengine.com/t/twinmotion-20251-1-unable-to-produce-section-cube/2465084/4 , https://dev.epicgames.com/documentation/twinmotion/sequences-in-twinmotion , https://dev.epicgames.com/documentation/twinmotion/videos?lang=ja
[10] Unreal path tracer – https://dev.epicgames.com/documentation/en-us/unreal-engine/path-tracer-in-unreal-engine
[11] Vericut AUTO-DIFF, tool use colours – https://vericut.com/products/auto-diff , https://help.vericut.com/4_vericut_help/6.04_tool_use
[12] Fusion stock comparison colours – https://help.autodesk.com/cloudhelp/ENU/Fusion-CAM/files/MFG-TOLERANCE-COLORS.htm
[13] FeatureCAM part compare – https://help.autodesk.com/cloudhelp/2018/ENU/FCAM/files/GUID-26F734E3-E574-4B16-9C80-23C59BD4EB8F.htm
[14] Industrial cutaway animation – https://maverickframe.com/success-stories/industrial-valve-animation/
[15] Machine-video examples (housing fades, cut away then explode) – https://advids.co/blog/30-3d-machine-visualization-video-examples-to-unlock-business-potential , https://advids.co/blog/30-industrial-3d-video-examples-to-inspire-advanced-product-visualizations
[16] model-viewer, AR – https://modelviewer.dev/examples/augmentedreality
[17] ModuleWorks dexel simulation, GPU – https://www.moduleworks.com/precision-meets-performance-with-gpu-accelerated-simulation/
[18] Tri-dexel (RhinoCAM), adaptive tri-dexel paper – https://mecsoftcorp.github.io/RhinoCAM-2026/WebHelp/tridexel-simulation.html , https://euspen.eu/knowledge-base/ICE24301.pdf
[19] Octree + marching cubes (cutsim, CAMotics) – https://github.com/aewallin/cutsim , https://github.com/CauldronDevelopmentLLC/CAMotics/tree/master/src/camotics/contour
[20] Blender 5.2 SDF Grid Boolean – https://docs.blender.org/manual/en/5.2/modeling/geometry_nodes/volume/operations/sdf_grid_boolean.html
[21] CIMCO machine simulation; NCSIMUL; Eureka – https://www.cimco.com/software/cimco-machine-simulation/ , https://hexagon.com/products/ncsimul-machine , https://www.goengineer.com/eureka-robot
[22] STEP has no constraints/joints (Inventor, Fusion) – https://forums.autodesk.com/t5/inventor-forum/losing-part-constraints-when-importing-step-file/m-p/12354513/highlight/true , Inventor STEP options: https://help.autodesk.com/cloudhelp/2022/ENU/Inventor-Help/files/GUID-68FCAD0E-93BD-4D90-B9FE-9CF82AA4E64D.htm
[22b] Custom iProperties not in STEP – https://forums.autodesk.com/t5/inventor-programming-forum/export-step-files-with-custom-iproperties/m-p/9745418
[22c] Dynamic Simulation publish targets – https://help.autodesk.com/cloudhelp/2026/ENU/Inventor-Help/files/GUID-839F77F4-8E63-459A-A69E-309A00FAFDCD.htm
[23] AP242 kinematics adoption; OCCT StepKinematics – https://www.mbx-if.org/home/wp-content/uploads/2025/10/rec_prac_ap242xml_kinematics_v1.3.pdf , https://dev.opencascade.org/doc/occt-7.6.0/refman/html/package_rwstepkinematics.html
[24] Fusion API joints – https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_JointGeometry_origin.htm
[24b] Fusion USD export has no joints – https://forums.autodesk.com/t5/fusion-api-and-scripts-forum/include-joints-in-usd-export/m-p/11837321
[25] Inventor API assembly joints – https://help.autodesk.com/cloudhelp/2025/ENU/Inventor-API/files/AssemblyJointDefinition.htm
[26] Cycles light tree, path guiding (CPU only), scrambling distance – https://developer.blender.org/docs/release_notes/3.5/cycles/ , https://devtalk.blender.org/t/gsoc-2022-many-lights-sampling-in-cycles-x-feedback-thread/24773?page=9 , https://docs.blender.org/manual/ja/dev/render/cycles/gpu_rendering.html , https://wiki.blender.org/release_notes/3.0/cycles/
[26b] OCCT meshing options – https://dev.opencascade.org/doc/overview/html/occt_user_guides__mesh.html
[27] OptiX temporal denoise in Cycles – https://devtalk.blender.org/t/taking-a-look-at-optix-7-3-temporal-denoising-for-cycles/18656/106 , https://projects.blender.org/blender/blender/issues/115045
[28] OIDN 3 temporal – https://www.cgchannel.com/2026/01/open-image-denoise-3-will-support-temporal-denoising/
[29] G-Wizard cycle time with acceleration – https://www.cnccookbook.com/estimating-cycle-times-with-machine-acceleration-new-g-wizard-editor-feature
[30] Cable-lay explainers – https://www.youtube.com/watch?v=JHhv5Fj9CNY , https://www.youtube.com/watch?v=JWTXtVOTQgE , https://www.youtube.com/watch?v=jsskDH_T9Vo
[31] Huisman motion-compensated cable lay – https://www.youtube.com/watch?v=ZKBw67TLoCo
[32] MacGregor 3D motion compensator – https://www.oilfieldtechnology.com/offshore-and-subsea/15112016/macgregor-introduces-3d-motion-compensator-for-offshore-cranes/
[33] Royal IHC cable lay spread; Osbit carousels – https://www.royalihc.com/offshore-energy/offshore-equipment/power-cable-lay/modular-cable-lay-spread , https://oceannews.com/news/subsea-cable/osbit-to-deliver-world-first-cable-repair-equipment-for-n-sea/
[34] Motion-compensated gangway animation – https://www.youtube.com/watch?v=EJq6ddGftTk
[35] Track links along a curve (Geometry Nodes) – https://80.lv/articles/crafting-a-warhammer-40k-inspired-tank-in-3d-with-geometry-nodes , https://blenderartists.org/t/how-do-i-wrap-the-segments-of-this-tank-track-around-this-curve/1452150
[36] Ropes in Geometry Nodes – https://80.lv/articles/a-new-geometry-nodes-set-up-for-creating-ropes
[37] Drum spooling layers – https://cadforum-net.dezignstuff.com/viewtopic.php?p=25691
[38] Length-keeping catenary node – https://higgsas-geo-nodes-manual.readthedocs.io/en/latest/curves.html
[39] Vessel motions from RAOs – https://nodynamics.com/knowledge-hub/vessel-motions-rao/
[40] Blender Ocean modifier spectra – https://docs.blender.org/api/5.1/bpy.types.OceanModifier.html
[41] FLIP wake cost – https://80.lv/articles/creating-wave-simulations-with-blenders-flip-fluids/
[42] 3D Lift Plan features – https://3dliftplan.com/Info/Features.aspx
