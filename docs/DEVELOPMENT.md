# Development notes

## Design rule

Define things once, save combinations as configurations. The model, subassemblies,
material groups and joints live once per project; paint schemes, poses and visibility
sets are light configurations.

## How an import works

1. `blender/ops_import.py` starts `importer/step_reader.py` in a child process with
   Blender's own Python (`sys.executable`) and the same `sys.path`, so the OpenCascade wheel
   installed with the extension is found.
2. The reader walks the XCAF document: assemblies, components (with placement), parts.
   Each unique part is tessellated once (`BRepMesh_IncrementalMesh`, relative deflection),
   normals from OpenCascade are kept for smooth CAD shading.
   For files over 3 MB the reader starts helper processes (all cores but one, at most 24,
   as free memory allows) right at the start, so they load OpenCascade while the file is
   read. Each unique part goes to a helper as OpenCascade binary BRep (`BinTools`, in
   memory), biggest first; the helper meshes it and returns the arrays (length-prefixed
   pickles over stdin/stdout). Helpers run below normal priority without a console
   window and stop when the reader stops (Cancel kills only the reader). A part a helper
   dies on is reported as "Could not mesh" and skipped; parts no helper could take are
   meshed in the reader. `FRESING_IMPORT_WORKERS=0` turns helpers off (any number sets it).
   A part meshed from its binary copy can get a different triangle order (OpenCascade walks
   some maps in memory order) - same counts, colours and axes, and the same result each run.
3. It writes `tree.json` (nodes with stable IDs `Parent#1/Child#2`) and `meshes.npz`
   into the cache (`<extension user dir>/cache/<name>_<hash>`). The hash covers path, size,
   modified time, quality and cache version, so a changed STEP is re-read.
4. `blender/build.py` creates one mesh per unique part (shared by its copies), empties for
   assemblies, and stores `fr_uid`, `fr_name`, `fr_color` on each object.
5. Rules run (`blender/logic.py` -> `core/rules.py`), materials are built
   (`blender/materials.py` from `core/materials_lib.py`).

Per unique part the cache holds `p`/`n`/`t` (positions, normals, triangles), `c` (palette index
of every triangle, only for parts with individually coloured faces; `palette` and, from
Autodesk styles on single faces, `palette_names` in `tree.json`) and `f` (cache version 5: the
first triangle of every CAD face plus the total; a face's triangles are one block).

**Painted faces** (`blender/faces.py`, task 0010): a face set is a list of CAD face numbers with
its own material slot (slot k+1, polygon `material_index`); stored as JSON on the mesh
(`fr_face_sets`, shared by every copy) with per-copy choices on the object (`fr_face_copy`).
Every slot is object-linked, so copies can differ. Faces painted in CAD become sets at build
time (colours equal to the part colour are skipped) and are sorted by the rules with
`rules.face_facts` (colour and CAD material only, no name rules). Meshes made before 0.2.9 have
no face list: faces are found as connected pieces (two CAD faces never share vertices).
A model update keeps sets of parts whose per-face triangle counts are unchanged.

**Rule sets** (task 0015, `core/rule_sets.py` file format and library, `blender/rule_sets.py`
project side, `blender/ops_rule_sets.py` operators): a rule set = name + rules + group looks
(group -> material, colour) + group renames (rule name -> shown name). Files: one JSON per rule
set in `<shared library>/Rule sets/` (marker `fresing_render_rule_set`; the name inside the file
counts, the file name is only a safe version of it); without a shared library
`Documents\Fresing Render\Rule sets` on the PC (`FRESING_RULE_SETS_DIR` overrides both, for tests).
"Standard" is built in (`rule_sets.standard()`: the default rules, no own looks). The project
keeps `scene.fresing.rule_set` (name) and `rule_set_data` (the set as last loaded or saved =
its own copy); the working state stays in `rules`, `group_aliases` and `groups`. "Changed" =
`current(s)` differs from the saved copy, where looks only count when they differ from
`rules.default_material_for_group` (so Standard has none) and only for groups the rules fill
(`group.by_rules`; a group holding only hand-picked parts belongs to the project). A new group
starts with the saved copy's look for its name, else the built-in one (`logic.start_look`).
Switching (`rule_sets.switch`): load rules/renames, sort, set looks (the set's, else built-in for
rule-filled groups, hand-only groups keep theirs), remove groups left empty; `preview` runs the
same sort without writing (`logic.sort_plan`, `faces.plan`). Projects saved before 0.2.13 get
their rule set on open (`rule_sets.on_load` -> `adopt`: "Standard" when the rules are the
untouched defaults, else "From this project"; nothing is re-sorted). Templates carry
`rule_set` (name + copy): the library version wins, the copy is the fallback; templates without
it load as before (rule set "From template '<name>'").
Files: a new file never replaces another (`free_path`: 'A/B' and 'A_B' both want `A_B.json`, the
second gets `A_B (2).json`); of two files with the same rule set inside, the one with its own file
name counts (an Explorer copy does not take over). A damaged file is skipped. Drawing never waits on
the network more than once per 15 s (`folder()` caches whether the shared library is reachable,
`library()` the scan); Save, Rename and Delete check afresh. Menus of rule sets number the items by
a hash of the name (Blender stores the number of the picked item: numbers by position would point at
another rule set once the list changes while a dialog is open).

Units: STEP millimetres become Blender metres; the scene shows millimetres.

## Measured (test machine: 2 slow cores, no GPU)

EGR cooler inspection line, 78 MB AP203 STEP, 2,789 placed parts, 584 unique, 4.2 M
unique triangles (17 M placed): read 42 s, tessellate 43 s, build objects 3 s.
A normal 8-16 core workstation is several times faster. Fresing's 24-core PC (0.2.2, one
core meshing): import 50-52 s Normal, 40 s Draft. 0.2.3 meshes on all cores; on the 2-core
test machine 2 helpers take tessellation from 40 s to 30 s. The biggest EGR part
("COMPOUND", 8,600 faces, 39 % of all triangles) needs 5.7 s meshing + 5.6 s arrays there
and sets the floor on many cores.

0.2.6: the arrays come from OpenCascade in one block (`BinTools_ShapeSet.WriteTriangulation`,
one bare face per triangulation so the records keep the face order; parsed with numpy)
instead of one Python call per node. Biggest EGR part: 2.6 s -> 0.3 s. Whole EGR line,
same 2-core machine (a faster one than above): meshing 24.0 -> 17.7 s on one core,
17.7 -> 14.8 s with 2 helpers; caches identical to the last bit. If the block does not match
the faces, the part is read node by node as before.

Animation frames (0.2.4): 2560x1440 "Preview" on the RTX 3090 took about 15 s per frame
(236 frames in about an hour). Changes: OpenImageDenoise on the graphics card (Blender's
default is the processor); for animation frames no caustics, fewer bounces (8/3/4/8) and
adaptive threshold x5/3 - measured on an EGR interior close-up (CPU, 480x270): 36.9 s ->
20.8 s per frame, mean difference 1.3/255. Fast GI was tried: 27 s but 7.7/255 darker,
rejected. Colour-background compositing costs ~0.5 s per 1440p frame (kept). The log
prints "frame N: render X s, save Y s" per frame.

Rule sets (0.2.13), synthetic 2,800-part scene (test model copied with generic names, 70 parts
put in a group by hand), 2-core test machine: preview of a switch 0.02-0.03 s, switch 0.04-0.06 s,
the "changed" check the panel makes at every redraw 0.12 ms.

## Surroundings (task 0016)

Owner's guide: `docs/SURROUNDINGS.md`.

* `core/surroundings.py` (no Blender) makes a **layout**: simple shapes (box, beam, tube,
  sphere, flat panel) in metres around a machine of a given size, floor at z = 0, grouped by
  role: floor, shell (walls, roof), structure, high (trusses, crane), contents, lights. Nothing
  is placed in the machine's keep-out box (footprint + clearance, height + margin), and in the
  default camera's quarter (front right) no contents stand within the view radius. Layouts
  are the same every time (fixed random seed). The kinds are stored by number in project
  files: never change or reuse a number.
* `blender/surroundings.py` turns each role into one mesh object under the empty
  "FR Surroundings" (collection of the same name), placed under the machine: lowest point of
  all parts that are not excluded (hidden parts count), centred. The model is never moved.
  It rebuilds only when the settings key or the models (`fr_stats`) change; floor gap, photo
  turn and strength are live. Props for scale are ordinary objects in "FR Props".
* Materials are procedural (`FR_env <key>`, version in `MAT_VERSION`). Hall walls, roof,
  door, windows and skylights are one-sided (seen from behind: transparent), do not light the
  scene and cast no shadow. Light lines glow but are not sampled as lights.
* **Cut-away (halls):** materials of things that can stand in the way (columns, trusses,
  racks, machines, cabinets, lights) leave a surface out of the picture for camera rays when it
  lies in a cone from the camera around the machine and nearer than the machine, or when it is
  roof structure and the camera is above the light lines. Per object: `fr_cut_c` (machine
  centre), `fr_cut_r` (radius; absent = never cut), `fr_roof` (height). The camera position
  is found from the shading point: P + Incoming × View Distance (Camera Data), which also works
  after see-through walls. Floors and walls get no cut-away nodes (cost ~13% render time).
  Halls set `transparent_max_bounces` to 128.
* Sea: a disc of rings out to 20 km whose rim rises 400 m (no gap under the horizon).
  Detailed: a fine centre with geometry-nodes swell (sum of travelling sine waves, deep-water
  speed, fading out at 5× the machine), crest attribute for foam; everywhere: 4D-noise
  ripples in the material, animated with a driver on frame / fps.
* 360° photo with ground: a dome (part of a sphere around the photo's camera point, at the
  "photo taken at" height) shows the photo; a disc on the floor projects the photo from that
  point as a matte surface with albedo photo × π / E, where E is the irradiance of the photo's
  upper half on flat ground, so where no shadow falls the ground looks exactly like the photo.

Render time: see `docs/SURROUNDINGS.md` (measured on the 2-core test machine).

## Light looks, camera views, blur, turntable (task 0017)

* `core/studio.py` (no Blender): the light designs, the five one-click looks, light in plain
  words, background blur and turntable numbers. Directions are azimuths seen from above: 0° =
  from the right (+X), 90° = from the back (+Y), -90° = from the front (-Y, where the Front
  camera stands). Blender shows column `lon` of a 360° picture at azimuth `-lon` and turns it
  clockwise (seen from above) by "Turn light"; its sky puts the sun at the back (+Y) at turn 0
  (both measured with a panoramic render). The Light choices are stored by number: Studio 0,
  360° photo 1, Sky 2 stay; Product 3, White 4, Dark 5 are new. Soft studio is the old picture
  (`world._studio_pixels`, unchanged).
* The new light pictures (`world.LOOK_IMAGES`) are made once, packed into the project (EXR,
  the bright softboxes survive saving). Overcast is a CIE overcast sky (zenith 3 × horizon),
  used for the sky wherever the sky lights the machine (`sky_weather`).
* A look sets settings only (`studio.look_settings`); the button stays pressed while
  `studio.look_matches`. Exposures were calibrated on the test crane: sun -1 EV.
* Views (`cameras.VIEWS`): Isometric is orthographic along (1, -1, 1). `cameras.fit` takes the
  points to frame (whole model or selection) and the space (`SPACE`); an orthographic camera in
  a portrait picture now gets its scale from the height (it cut the sides off before).
* Blur: per camera `fr_blur` (NONE/LITTLE/STRONG). The f-stop is worked out so that a point far
  behind the sharp spot blurs to 0.4 % / 1.2 % of the picture width, whatever the machine's size
  (thin lens: N = f² / (share × sensor × (S − f))). `cameras.update_blur` runs after a fit, a
  lens change (the Lens field is a get/set setting on the camera), a new sharp spot and before
  every still. Cameras made before task 0017 (no `fr_blur`) keep their own f-stop. The sharp
  spot is an empty with a Child Of constraint on the clicked part (it follows joints), used as
  the camera's focus object; `focus_distance` is kept in step for animations, whose camera
  copies the distance, not the object.
* Turntable (`blender/turntable.py`): camera "Turntable camera" aimed at a point on the upright
  axis through the middle of the visible machine (the axis the Orbit step of `animation.py`
  turns around), fitted for the video's shape on the model turned in 15° steps; the saved
  scene "Turntable" and the animation "Turntable" (tagged `fr_turntable`) with one linear
  Orbit step of 360 × (N−1)/N degrees over N frames, so frame N+1 would be frame 1 (seamless
  loop). In a turntable the middle of the machine is sharp (the same distance all round).

## Tests

* `tests/test_fasteners.py`, `tests/test_core.py`: pure Python.
* `tests/test_blender.py`: full pipeline in the `bpy` module with a generated test STEP
  (`tools/make_test_step.py`): import, sorting, materials, schemes, templates, structure,
  camera framing, output sizes, tiny renders for every background mode, and a UI smoke test
  that draws every panel with a fake layout and checks property and operator names.
* `tools/test_install_linux.py`: builds a Linux variant of the extension zip, installs it
  into a clean Blender the way users get it, and runs the self-test.

## Roadmap (from the plan)

* Phase 2: joints (rotate, slide), poses, exploded views, visibility sets, scenes,
  animation timeline, render queue, re-import keeping all work.
* Phase 3: path joints (single parts, link loops, shape-changing paths), multiple machines,
  props, clash warning, project templates library.
