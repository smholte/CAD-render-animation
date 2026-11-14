# 0117 – Mesh import: glTF / OBJ / FBX models as projects the app can work with

**Who:** worker · **Status:** open – can start · **Branch:** `task/0117-mesh-import` (or the web session's)
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

## Done when

- [ ] glTF/GLB and OBJ import to the same cache as STEP; FBX as decided; units, up axis, names, colours, instancing
- [ ] Faces for meshes: joint picker, hover and decals work on a facetted model; axis accuracy test; speed measured
- [ ] Split by loose parts; textures "From file"; web 3D export of a textured part; model update keeps the work
- [ ] Credit line read and shown; menu + drag-and-drop; tooltips, guide, tour stop, PC-check line(s)
- [ ] Independent tester's findings fixed; full run green; CHANGELOG, version taken last

## Not in this task

Downloading or adding the Sketchfab models to the site (a later Site kit task, after the owner downloads them).
Changing the STEP reader. Mesh repair beyond what the face split needs. Decimation (later, if big scans need it).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
