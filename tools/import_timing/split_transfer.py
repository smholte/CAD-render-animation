"""Prototype measurement (task 0301): is turning the file into shapes worth splitting over helpers?

    python tools/import_timing/split_transfer.py model.step N [--mesh] [--quality normal]

Starts N processes at once. Each one reads (parses) the whole file itself, then turns only its share of the parts'
shape representations into shapes (every N-th ``*_BREP_SHAPE_REPRESENTATION`` / ``*_SURFACE_SHAPE_REPRESENTATION``
entity, ``STEPControl_Reader.TransferOne``) and, with ``--mesh``, meshes them with the app's settings. Prints
each process's parse / transfer / mesh seconds and the wall time until the last one is done. N = 1 is the whole
model in one process (no names, colours or tree: those stay with the reader's own XCAF transfer). Measures only;
the app does not work this way.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

SHAPE_REPS = ("StepShape_AdvancedBrepShapeRepresentation", "StepShape_ManifoldSurfaceShapeRepresentation",
              "StepShape_FacetedBrepShapeRepresentation", "StepShape_GeometricallyBoundedSurfaceShapeRepresentation",
              "StepShape_EdgeBasedWireframeShapeRepresentation")


def one(path: str, k: int, n: int, mesh: bool, quality: str) -> dict:
    from OCP.STEPControl import STEPControl_Reader
    from OCP.IFSelect import IFSelect_RetDone
    t0 = time.time()
    r = STEPControl_Reader()
    if r.ReadFile(path) != IFSelect_RetDone:
        raise RuntimeError("read failed")
    t1 = time.time()
    model = r.StepModel()
    reps = [i for i in range(1, model.NbEntities() + 1) if model.Value(i).DynamicType().Name() in SHAPE_REPS]
    share = reps[k::n]
    t2 = time.time()
    ok = 0
    for i in share:
        ok += bool(r.TransferOne(i))          # by entity number (TransferEntity of the same entity gave nothing)
    shapes = [r.Shape(j) for j in range(1, r.NbShapes() + 1)]
    t3 = time.time()
    tris = 0
    if mesh:
        from fresing_render.importer import step_reader as sr
        occ = sr._occ()
        lin, ang = sr.QUALITY[quality]
        for s in shapes:
            d, rel, a = sr.mesh_params(lin, ang, sr._part_size(occ, s), sr.FACETS[quality], False)
            occ["BRepMesh_IncrementalMesh"](s, d, rel, a, True)
            res = sr._mesh_shape(occ, s, lin, ang, None, already_meshed=True)
            tris += 0 if res is None else len(res[2])
    t4 = time.time()
    return {"k": k, "parse": t1 - t0, "find": t2 - t1, "transfer": t3 - t2, "mesh": t4 - t3, "reps": len(share),
            "transferred": ok, "shapes": len(shapes), "tris": tris, "total": t4 - t0}


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["--one"]:
        path, k, n, mesh, quality = argv[1], int(argv[2]), int(argv[3]), argv[4] == "1", argv[5]
        print("RESULT " + json.dumps(one(path, k, n, mesh, quality)), flush=True)
        return 0
    path, n = argv[0], int(argv[1])
    mesh = "--mesh" in argv
    quality = argv[argv.index("--quality") + 1] if "--quality" in argv else "normal"
    t = time.time()
    procs = [subprocess.Popen([sys.executable, __file__, "--one", path, str(k), str(n), "1" if mesh else "0", quality],
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True) for k in range(n)]
    res = []
    for p in procs:
        out, _ = p.communicate()
        res += [json.loads(line[7:]) for line in out.splitlines() if line.startswith("RESULT ")]
    wall = time.time() - t
    print(json.dumps({"model": os.path.basename(path), "n": n, "mesh": mesh, "wall": wall, "each": res}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
