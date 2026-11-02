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
3. It writes `tree.json` (nodes with stable IDs `Parent#1/Child#2`) and `meshes.npz`
   into the cache (`<extension user dir>/cache/<name>_<hash>`). The hash covers path, size,
   modified time, quality and cache version, so a changed STEP is re-read.
4. `blender/build.py` creates one mesh per unique part (shared by its copies), empties for
   assemblies, and stores `fr_uid`, `fr_name`, `fr_color` on each object.
5. Rules run (`blender/logic.py` -> `core/rules.py`), materials are built
   (`blender/materials.py` from `core/materials_lib.py`).

Units: STEP millimetres become Blender metres; the scene shows millimetres.

## Measured (test machine: 2 slow cores, no GPU)

EGR cooler inspection line, 78 MB AP203 STEP, 2,789 placed parts, 584 unique, 4.2 M
unique triangles (17 M placed): read 42 s, tessellate 43 s, build objects 3 s.
A normal 8-16 core workstation is several times faster.

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
