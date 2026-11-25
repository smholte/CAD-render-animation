"""The CAD-weld test frames (task 0323) read without Blender: the importer's cache -> ``core.weld_cad.Mesh`` per part.

``meshes(kind, tmp)`` reads tests/data/test_weldment_cad_<kind>.step (``kind`` inventor / creo / unnamed /
inventor_b) once per test session and gives ([Mesh], {key: node}); ``detect(kind, tmp)`` runs the finder as the import
does (named bodies + shape candidates)."""

from __future__ import annotations

import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
_CACHE: dict = {}


def path(kind: str) -> str:
    return os.path.join(DATA, f"test_weldment_cad_{kind}.step")


def meshes(kind: str, tmp: str, step: str | None = None):
    from fresing_render.core import web3d_faces
    from fresing_render.core.weld_cad import Mesh
    from fresing_render.importer import step_reader
    if kind in _CACHE:
        return _CACHE[kind]
    out = os.path.join(tmp, f"cache_{kind}")
    step_reader.read_step(step or path(kind), out, "normal")
    with open(os.path.join(out, "tree.json"), encoding="utf-8") as fh:
        info = json.load(fh)
    arrays = np.load(os.path.join(out, "meshes.npz"))
    nodes = info["nodes"]
    world = []
    for n in nodes:
        m = np.array(n["matrix"], float) if n.get("matrix") else np.eye(4)
        world.append(world[n["parent"]] @ m if n["parent"] >= 0 else m)
    res, by = [], {}
    for i, n in enumerate(nodes):
        if n["kind"] != "part" or n["mesh"] < 0 or f"p{n['mesh']}" not in arrays:
            continue
        mid = n["mesh"]
        p = np.asarray(arrays[f"p{mid}"], float)
        t = np.asarray(arrays[f"t{mid}"], np.int64)
        face = web3d_faces.face_of_triangles(len(t), arrays[f"f{mid}"]) if f"f{mid}" in arrays else None
        W = world[i]
        res.append(Mesh(f"{n['name']}#{i}", n["name"], p @ W[:3, :3].T + W[:3, 3], t, face,
                        n.get("material_name") or n.get("material") or ""))
        by[res[-1].key] = n
    _CACHE[kind] = (res, by)
    return res, by


def detect(kind: str, tmp: str, by_shape: bool = True, step: str | None = None):
    from fresing_render.core import weld_cad
    ms, _by = meshes(kind, tmp, step)
    named = {m.key for m in ms if weld_cad.weld_name(m.name)}
    bodies = [m for m in ms if m.key in named or (by_shape and weld_cad.maybe_bead(m))]
    parts = [m for m in ms if m.key not in named]
    return weld_cad.find(bodies, parts, named), {m.key: m for m in ms}
