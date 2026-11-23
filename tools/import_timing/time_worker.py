"""A meshing helper with a clock (task 0301): the app's helper loop, each reply carries its part's times."""

from __future__ import annotations

import io
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from fresing_render.importer import step_reader as sr  # noqa: E402

if os.environ.get("FR_TIMING_OCC_PARALLEL") == "0":
    _real = sr._occ

    def _occ():
        d = _real()
        mesh = d["BRepMesh_IncrementalMesh"]
        d["BRepMesh_IncrementalMesh"] = lambda shape, defl, rel, ang, _par: mesh(shape, defl, rel, ang, False)
        return d
    sr._occ = _occ


def _mesh_job(occ, mid, blob, face_colours, lin_rel, ang, facets=None, standard=False):
    t0 = time.time()
    shape = occ["TopoDS_Shape"]()
    occ["BinTools"].Read_s(shape, io.BytesIO(blob))
    t1 = time.time()
    defl, rel, a = sr.mesh_params(lin_rel, ang, sr._part_size(occ, shape), facets, standard)
    occ["BRepMesh_IncrementalMesh"](shape, defl, rel, a, True)
    t2 = time.time()
    axes = sr._Axes()
    starts: list = []
    res = sr._mesh_shape(occ, shape, lin_rel, ang, face_colours, already_meshed=True, axes=axes, face_starts=starts,
                         facets=facets, standard=standard)
    t3 = time.time()
    return mid, res, axes.axes, axes.faces, None, starts, {"mid": mid, "bin_read": t1 - t0, "mesh": t2 - t1,
                                                            "arrays": t3 - t2, "total": t3 - t0}


sr._mesh_job = _mesh_job

if __name__ == "__main__":
    sys.exit(sr.main(sys.argv[1:]))
