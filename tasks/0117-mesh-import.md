# 0117 – Mesh import: glTF / OBJ / FBX models as projects the app can work with

**Who:** worker · **Status:** done (0.2.99) · **Branch:** `ccr-8270e3a4-hwpgr0` (the web session's)
**Started by:** lead chat, 14 Nov 2026 (owner's pick from study 0113, 13 Nov 22:07: "mesh import – to do")
**Area (new Import lane):** new `fresing_render/importer/mesh_reader.py` (+ helpers, e.g. `core/mesh_faces.py` for the
face split), `importer/runner.py` additively (start the mesh reader like the STEP reader), `blender/ops_import.py`
additively (a new operator + file handler; the STEP import stays as it is), `blender/build.py` and `blender/faces.py`
additively (texture materials, face starts for meshes), new `tests/test_mesh_import*.py`, a test-model maker
`tools/make_test_mesh.py`. **Do not edit:** the STEP reader's behaviour (`step_reader.py`: only shared helpers moved
out if needed, with the STEP tests unchanged and green), 0082's files (`paths*`, `demo*`), 0116's
(`tools/site_projects/`, `site/render_kit/`, `materials_lib.py` while 0116 runs), 0111's (`site/`, `web3d*`).
**Model:** **Opus · effort High** (subagents allowed; an independent tester is required) · **Place:** Claude Code on
the web, environment "CAD-render-animation"

## Goal

The owner can open a mesh model (glTF/GLB first, then OBJ and FBX) – for example a CC BY vessel or truck from
Sketchfab – and use it like an imported STEP: the explorer tree, groups and looks, joints picked by clicking round
faces, poses, animation, clash check, renders, web 3D export. Study 0113 found that vessels and trucks are only free
as meshes, so this opens the site to them later.

## Background

- **The STEP path** (CLAUDE.md section 3): `importer/step_reader.py` writes a cache – `tree.json` (one node per
  assembly / part occurrence: name, kind, colour, place) and `meshes.npz` (one triangle mesh per unique part) –
  `runner.py` starts it as its own program with Blender's Python, `build.py` builds the objects, `blender/faces.py`
  keeps `fr_face_starts` (the first triangle of every CAD face) that the joint picker (`joints.axis_from_hit`), hover
  (0088), decals and the face-based tools rely on. **Write the same cache from a mesh file**, so everything after it
  works unchanged.
- **What a mesh lacks:** CAD faces (no B-rep), exact round faces (cylinders are facetted), sometimes a sensible part
  split (one big mesh), units (OBJ/FBX), and it may bring its own textures. glTF: metres, Y up, node tree with names,
  PBR materials, `asset.copyright`/`extras` (licence text often there). OBJ: groups/objects, MTL colours, no units.
  FBX: node tree, units in the header.
- **Licences:** the importer reads the file's own credit text when there is one (glTF `asset.copyright`, Sketchfab's
  `license.txt` next to it) and shows it after import (a line in the Import panel and a note in the project), so the
  credit is not lost. Nothing downloaded in tests: test models are made by a script.
- Candidates later (not in this task): Working Vessel 03, KS-4574 crane truck (CC BY 4.0, Sketchfab; the owner
  downloads them, signed in).

## Scope

1. **Reader** for **glTF/GLB** (required), **OBJ** (required), **FBX** (if a pure-Python or bundled reader works in
   Blender's Python on Windows without new installs; otherwise read FBX through Blender's own importer in the
   background Blender and convert – say which in the report; if neither is reasonable, leave FBX out and say so).
   Node tree → assembly tree (names kept; instanced meshes stored once like repeated bolts), node transforms, colours
   from base colour factor / MTL `Kd`, units (glTF m; OBJ: ask in the import dialog, default guessed from the size with
   the guess shown; FBX: from its header), up axis to the app's Z up.
2. **Faces for meshes:** split each mesh into "faces" like a CAD model has: flat regions, cylinder-like regions (fit
   axis + radius), others – region growing by normal and curvature, robust on facetted cylinders (16–64 sides) and on
   meshes with split normals; write `fr_face_starts` (triangles reordered per face) so the joint picker, hover,
   decals and the round-face checks work. A clicked facetted cylinder gives an axis within 0.5° and 0.5 % of its
   radius (test). Cost measured on a 1 M-triangle mesh (aim < 10 s on the 4-core web machine).
3. **One big mesh** (no part split): offer **Split by loose parts** in the import dialog (on by default when the file
   has fewer than ~5 nodes), so separate pieces become parts you can move and give looks.
4. **Textures:** keep the file's base-colour texture as the part's look option **"From file"** (the app's looks still
   work and replace it); normal/roughness maps if simple. Textures packed into the project so it stays one file.
   The web 3D export (0099/0105) must still work on a textured part (test: export, glTF check passes).
5. **Model update** (0052): a new revision of the same mesh file keeps groups, looks, joints by node name (as STEP
   keeps them by part path); a renamed node is reported, not silently lost.
6. **UI:** **File > Import > Mesh model (glTF, OBJ, FBX)** and drag-and-drop (a file handler), the same progress and
   Cancel as the STEP import; the Import panel shows the source and credit line. Tooltips, guide section, **tour stop**
   (a made-up glTF: a small crane with a facetted round slewing ring → click it, make the joint, turn it),
   **PC-check line** (import + face split + joint on the test glTF), a **Heavy** line if the face split's speed
   depends on size.
7. **Tests:** `tools/make_test_mesh.py` writes the test models (glTF with nodes, instancing, a texture, a facetted
   cylinder; an OBJ with MTL; one big single-mesh model) – no downloads. Independent tester (a subagent that did not
   write the reader) tries to break it: odd files (no normals, quads/ngons in OBJ, negative scales, Y-up/Z-up,
   non-ASCII names, missing textures, 0-area triangles).

8. **Bug hunt 0118 row 14** (Import lane, fits here): two imports of the same new file started within about a second
   share one `.partial` folder – give each process its own (`.partial-<pid>`), moved into place as today; a test with
   two imports at once. Holds for STEP and mesh files.

## Done when

- [ ] glTF/GLB and OBJ import to the same cache as STEP; FBX as decided; units, up axis, names, colours, instancing
- [ ] Faces for meshes: joint picker, hover and decals work on a facetted model; axis accuracy test; speed measured
- [ ] Split by loose parts; textures "From file"; web 3D export of a textured part; model update keeps the work
- [ ] Credit line read and shown; menu + drag-and-drop; tooltips, guide, tour stop, PC-check line(s)
- [ ] Independent tester's findings fixed; full run green; CHANGELOG, version taken last

## Not in this task

Downloading or adding the Sketchfab models to the site (a later Site kit task, after the owner downloads them).
Changing the STEP reader. Mesh repair beyond what the face split needs. Decimation (later, if big scans need it).

## Design (worker, 14 Nov 2026)

**One rule:** the mesh reader writes **the same cache as the STEP reader** (`tree.json` + `meshes.npz`, CACHE_VERSION
6 keys `p/n/t/f<mid>`, `meshes[mid].axes/axis_faces`), so build, faces, joints, hover, decals, clash, rules and the
model update work unchanged. New, optional keys only: `u<mid>` (float32 (n, 2) UVs, Blender's v), `meshes[mid].
file_material` (index into `info["materials"]`), `info["materials"]` (the file's materials: name, colour, metallic,
roughness, alpha, texture files relative to the cache folder), `info["credit"]` / `info["credit_text"]`,
`info["source_kind"] = "mesh"`, `info["options"]` (units, up, split as used), `info["notes"]` (what was guessed or
left out). The cache's units are metres and Z up whatever the file had.

**Files and owners**
| File | Owner | What |
| --- | --- | --- |
| `core/mesh_faces.py` + `tests/test_mesh_faces.py` | subagent A (worktree) | face split + loose parts, pure NumPy (interface below) |
| `importer/mesh_reader.py`, `importer/convert_blender.py` | worker | glTF/GLB + OBJ/MTL reader → cache; FBX (and glTF with Draco/meshopt) converted to GLB by Blender's own importer/exporter in a background Blender, then read as glTF |
| `importer/runner.py` | worker | `ImportJob(path, quality, cache_root, options=None, converter=None)` picks the reader by extension; options in the cache key; each job its own `.partial-<pid>-<n>` folder (0118 row 14); a cache another import finished first is used, not deleted |
| `blender/ops_import.py`, `ui.py` (Import panel), `build.py`, `materials.py`, `core/materials_lib.py`, `reimport.py` | worker | `fresing.import_mesh` + file handler + File > Import menu; UVs, file materials (textures packed) and the look "From file"; credit on the root; renamed parts matched by place + shape and reported |
| `tools/make_test_mesh.py`, `tests/data/test_mesh_*`, `fresing_render/data/` copies | worker | test models (no downloads) |
| `tests/test_mesh_reader.py`, `tests/test_mesh_import.py` | worker | reader (pure Python) and app side (bpy) |
| `tests/test_mesh_independent.py` | subagent B (after the code) | independent tester: tries to break the reader + face split |
| tour, PC check, guide, CHANGELOG, TASKS | worker | |

**`core/mesh_faces.py` interface** (positions in the cache's units, metres; no bpy):
```python
MAX_AXES = 400
def weld(pos, tol=None) -> np.ndarray            # (n,) int: one id per position (within tol; default 1e-6 x bbox diagonal)
def loose_parts(pos, tri, tol=None) -> np.ndarray  # (m,) int label per triangle 0..k-1 (ordered by first triangle),
                                                 # connected through *welded* vertices (split normals / UV seams do not split)
@dataclass
class Faces:
    order: np.ndarray       # (m,) int64: new triangle k is old triangle order[k]; each face one block
    starts: np.ndarray      # (F+1,) int32: first triangle of every face in the new order, + m at the end
    kinds: np.ndarray       # (F,) uint8: 0 other, 1 flat, 2 cylinder, 3 cone
    axes: list              # [ox, oy, oz, dx, dy, dz, r] per unique axis, like step_reader._Axes (foot of the line
                            # nearest the origin, first non-zero direction component > 0, same line = one axis, r = max)
    axis_faces: list        # flat [tri_start, tri_count, axis index, ...] in the NEW order (round faces)
def split(pos, tri, normals=None) -> Faces
```
Needs: a facetted cylinder of 16–64 sides (open, capped, a boss on a box, a hole through a plate, a quarter-round
fillet between two flats) is one face with an axis within 0.5° and a radius within 0.5 %; a box gives 6 flat faces;
meshes with split normals (every triangle its own vertices) give the same faces; a sphere / free shape gives "other"
faces bounded by sharp edges, never a crash; deterministic (the same mesh gives the same faces: model update keeps
painted faces); 1 M triangles in < 10 s on the 4-core web machine.

**Reader decisions:** glTF: node tree → assembly tree (uid as STEP: `parent/name#count`); a node with one primitive
is a part, a mesh of several primitives (materials) is an assembly with one part per primitive; the same mesh +
primitive used by several nodes is stored once (instancing). Y up → Z up on the roots. Colour = baseColorFactor
(linear → sRGB), the material name goes to `material` (the rules' "CAD material"). No normals → flat normals (glTF
spec). OBJ: `o`/`g` names, `usemtl` splits a part per material, MTL `Kd`, `d`, `Ns`, `map_Kd`, `map_Bump`; units
asked in the dialog (Auto guesses mm when the biggest side is ≥ 500 units, else m, and says so); up axis Y by
default (most OBJ exporters), Z on request. Split by loose parts: Auto = on when the file has fewer than 5 meshes;
more than 1,000 pieces in one mesh: the biggest 999 are parts, the rest one part "small pieces". Credit:
`asset.copyright`, `asset.extras` (Sketchfab: title, author, license, source) and a `license.txt` / `LICENSE*` /
`README*` next to the file, one line + the full text (≤ 4,000 characters).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (worker session, branch `ccr-8270e3a4-hwpgr0`), 14 Nov 2026.

**What changed:**
- **Version 0.2.99.**
- `importer/mesh_reader.py` (new): glTF 2.0 / GLB (accessors with strides, sparse, normalised ints, strips, fans,
  data URIs, external files, TRS/matrix nodes, instancing, PBR and spec-gloss materials, textures written to the
  cache) and OBJ/MTL (o/g, usemtl → a part per material, ngons as fans, negative indices, Kd/d/Ns/map_Kd/bump) →
  **the STEP cache** (tree.json + meshes.npz, same keys) plus UVs `u<mid>`, `info["materials"]`, credit, notes.
  Metres and Z up in the cache; OBJ units Auto (≥ 500 units = mm, said in the status line), up Y by default.
  Split by loose parts (Auto when < 5 meshes; > 999 pieces: the rest one part "small pieces"). No normals → flat.
- **FBX:** read by Blender's own FBX importer in a background Blender (`importer/convert_blender.py`, `blender -b
  --factory-startup`), written as a plain GLB, then read as glTF. Same route for glTF compressed with Draco or
  meshopt. Chosen because a pure-Python FBX reader would be a large new parser; Blender's importer is on every PC
  already. Costs ~1.5 s Blender start (measured here: 1.7 s for the test crane, a path with a space and an accent).
- `core/mesh_faces.py` (new, subagent A): weld, loose parts, flat / cylinder / other faces, cylinder axes as
  `step_reader._Axes` stores them; triangles reordered per face → `fr_face_starts`. Cones are not found (they come
  out flat/other).
- `importer/runner.py`: `ImportJob` picks the reader by extension, mesh options in the cache key (STEP keys
  unchanged), **each job its own `.partial-<pid>-<n>` folder** (bug hunt 0118 row 14), a cache another import put in
  place first is used, stale half-written folders (> 6 h, and the old `.partial` name) are removed.
- App: `fresing.import_mesh` (units, up axis, split; model update), file handler (.glb .gltf .obj .fbx),
  File > Import > Mesh model (glTF, OBJ, FBX)…, **Import mesh model…** in 1 Import; under a mesh model's name the
  file, its credit line and the reader's notes. `blender/mesh_import.py` (new): the file's materials (Principled +
  base colour / normal / metallic-roughness pictures, packed), the look **"From file"** (`materials_lib` id
  `from_file`, `materials.assign` swaps in the part's own material; new groups whose parts all have one start with
  it), credit on the root + text block "Model credits". `build.py`: UV layer "UVMap", `fr_file_material`.
- `reimport.py`: a 4th match – same shape (triangles, size) in the same place = renamed, kept and named in the report.
  Also for STEP.
- `web3d.py`: a part with a file picture exports that picture as it is on its own UVs (not baked as a 0.2 m tile).
- `joints.axis_from_hit`: a mirrored part (negative scale) gave a negative radius and no Ø (found by the wheels).
- `props._group_look_changed`: the parts of the group get their material again (to and from "From file").
- Tour stop "Mesh model: joint on a ring" (set `mesh`, `test_mesh_crane.glb`, joint "Slew" made by clicking the
  48-sided ring, animation turns the turret 120°); PC check Full lines `import.mesh`, `import.mesh_fbx` (FBX through
  the background Blender – Windows covered on GitHub), Heavy `heavy.mesh` (1 M triangles in one mesh).
- `tools/make_test_mesh.py` (new): test_mesh_crane(.glb, _b.glb), test_mesh_single.glb, test_mesh_parts.obj/.mtl
  + tile.png; byte-identical at every run; the crane ships in `fresing_render/data/`.
- Guide: 1 Import > Mesh models; picture panel_1_import(_start).png. CHANGELOG.

**Tested and measured** (4-core web machine):
- Face split (`tests/test_mesh_faces.py`, 94 tests): facetted cylinders 16–64 sides (tube, capped, boss, hole,
  fillet, thin shaft, 2 m slewing ring) axis within 8.5e-7°, radius 5e-14 relative. 1 M triangles 4.7–6.6 s
  (`FR_SLOW=1`), 100k < 1 s.
- Whole reader on a 1 M-triangle glTF (500 cylinders in one mesh): 6.8 s, 500 parts, 500 round faces; the Heavy line
  in Blender (module) 11.1 s incl. building 500 objects, peak 694 MB. Scaled-down Heavy 1.7 s.
- `tests/test_mesh_reader.py` (22), `tests/test_mesh_import.py` (11): ring clicked → axis 0.00° off, Ø1600.0;
  hover lights the whole wall (96 triangles); pin and mirrored wheels; joint turns the turret; decal; OBJ units;
  split; web 3D export (glTF problems: none, the PNG on own UVs); model update A → B (BOOM renamed MAIN BOOM kept,
  HOOK BLOCK new, 0 missing, joint kept); save + reopen (packed texture). Two imports of one new file at once (glTF
  and STEP). FBX via bpy module and via the real Blender 5.2.3.
- `tests/test_tour.py` 72 passed; `test_clash.py::test_every_tour_animation_has_no_clash` passed (0 clashes);
  PC check lines import.mesh 1.5 s, import.mesh_fbx 2.6 s.

**Subagents:** A (worktree) wrote `core/mesh_faces.py` + its tests from the Design; merged as it was, then its 4
slow timing tests made FR_SLOW-only (GitHub allows one skipped test per group); later it fixed the tester's findings
11 and 14 (sent back to it). B = independent tester (`tests/test_mesh_independent.py`, 105 tests): 15 findings,
77 things that worked. Fixed by the worker: 1 Draco without Blender says "compressed"; 2 damaged glTF files (12 kinds)
say "the glTF file is broken: …" instead of a bare Python error; 3 a huge count without data is refused; 4 `/` and
`#` in names no longer make uids collide (escaped, mesh files only); 5 OBJ lines with tabs; 6 concave ngons by ear
clipping; 7 two OBJ objects with one name stay two parts; 8 exactly 999 pieces is no "small pieces"; 9 split pieces
numbered in file order (a piece keeps its name when another grows); 10 mesh cache keys use the mtime in ns; 12 a
README is a credit only when it speaks of a licence/author; 13 an MTL texture with the author's absolute path is
found next to the OBJ. Fixed by A: 11 cylinders whose facets meet in T-junctions; 14 float32 cylinders hundreds of
metres out (one face, radius within 0.5 %; the stored axis point now lies beside its face, every user treats it as a
point on the line). 15 decided: groups decide looks for every model alike – a mesh part joining a group an earlier
model made takes that group's look (guide says so; pick "From file" for the group).

**Found by GitHub (run 43588174871, the task's first):** the FBX converter's background Blender used the user's
settings folder and reset it to factory settings, so Blender's extension-wheel sync **deleted the app's OpenCascade**
(every later STEP import in that app failed, Linux and Windows PC check). Reproduced here, fixed (its own temporary
settings folder, no factory reset; test `test_the_converter_blender_never_touches_the_users_settings_folder`).

**Runs:** 3 – the first found the converter fault above (and the expected "since 0.2.96 > 0.2.95"); the second
(43590650152, main merged, 0.2.98) was green, but task 0120 took 0.2.98 on main meanwhile: main merged again, 0.2.99,
a third run.

**Open points / follow-up tasks:**
- Cones are not recognised as round faces (they come out flat/other): later if a model needs them.
- A very short cylinder (length < ~0.5 x radius) with smooth fillet rings at both ends may lose its axis.
- The STEP cache key still uses whole-second mtimes (finding 10 fixed for mesh files only, STEP caches kept valid).
- Importing one mesh file with other options (units) replaces the stored cache of the earlier options.
- A part with a file picture and faces painted by hand in a tiled look exports with its own UVs only (rare).
- Normal and metallic/roughness pictures of a file material are not in the web 3D export (plain numbers).
- glTF skins/animations and KHR_texture_transform are left out (said in the import notes).
