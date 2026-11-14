# 0117 – Mesh import: glTF / OBJ / FBX models as projects the app can work with

**Who:** worker · **Status:** running · **Branch:** `ccr-8270e3a4-hwpgr0` (the web session's)
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

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
