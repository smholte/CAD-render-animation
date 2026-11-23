"""The Blender side of an import, timed one by one (task 0301). Blender as a Python module (the venv's bpy).

    python tools/import_timing/time_build.py <cache dir> [--json out.json] [--variants]

Runs ``ops_import.finish_import`` step by step on a cache written by time_reader.py (or the app): build.build
(meshes: vertices / corners / faces set, edges worked out, normals; CAD face sets; objects: made, custom
properties, matrices, linked), up axis, lock, sorting rules, the structure list, bounds, the first depsgraph
update, camera, surroundings. ``--variants`` also times ways to make the meshes faster (each on the same cache,
in a fresh file): without ``calc_edges``, edges given in the same call, a .blend of the meshes read back
(``bpy.data.libraries.load``) and linked duplicates instead of copies (nothing to gain: copies already share
their mesh). First draw needs a window and a graphics card: not here (see the report).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

import bpy  # noqa: E402
import addon_utils  # noqa: E402
import numpy as np  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import build, cameras, faces, logic, ops_import, render, world  # noqa: E402


class Clock:
    def __init__(self):
        self.t: dict = {}

    def wrap(self, mod, name, key=None):
        real = getattr(mod, name)
        key = key or name
        clock = self

        def timed(*a, **k):
            t = time.perf_counter()
            try:
                return real(*a, **k)
            finally:
                clock.t[key] = clock.t.get(key, 0.0) + time.perf_counter() - t
        setattr(mod, name, timed)
        return real

    def step(self, key, fn, *a, **k):
        t = time.perf_counter()
        r = fn(*a, **k)
        self.t[key] = self.t.get(key, 0.0) + time.perf_counter() - t
        return r


_REGISTERED = [False]


def fresh():
    if _REGISTERED[0]:
        fresing_render.unregister()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    _REGISTERED[0] = True


def new_mesh_parts(name, pos, nrm, tri, clock: Clock, edges_mode="update"):
    """build._new_mesh with a clock round each piece (same calls)."""
    t = time.perf_counter
    a = t()
    me = bpy.data.meshes.new(name)
    n_v, n_t = len(pos), len(tri)
    me.vertices.add(n_v)
    me.vertices.foreach_set("co", pos.reshape(-1))
    me.loops.add(n_t * 3)
    me.loops.foreach_set("vertex_index", tri.reshape(-1))
    me.polygons.add(n_t)
    me.polygons.foreach_set("loop_start", np.arange(0, n_t * 3, 3, dtype=np.int32))
    b = t()
    if edges_mode == "update":
        me.update(calc_edges=True)
    elif edges_mode == "no_edges":
        me.update()
    c = t()
    attr = me.attributes.new("custom_normal", "FLOAT_VECTOR", "POINT")
    attr.data.foreach_set("vector", nrm.reshape(-1))
    me.materials.append(None)
    d = t()
    for k, v in (("mesh_arrays", b - a), ("mesh_edges", c - b), ("mesh_normals", d - c)):
        clock.t[k] = clock.t.get(k, 0.0) + v
    return me


def timed_import(cache_dir: str) -> dict:
    fresh()
    clock = Clock()
    clock.step("load_cache", build.load_cache, cache_dir)        # warm read of the npz (the build reads it again)
    clock.t["load_cache_again"] = 0.0
    build._new_mesh = lambda n, p, nr, tr: new_mesh_parts(n, p, nr, tr, clock)
    clock.wrap(build, "load_cache", "load_cache_again")
    clock.wrap(faces, "cad_sets")
    clock.wrap(faces, "link_slots")
    ctx = bpy.context
    scene = ctx.scene
    s = scene.fresing
    t_all = time.perf_counter()
    root = clock.step("build_total", build.build, cache_dir)
    clock.step("up_axis", logic.set_up_axis, root, "Z")
    clock.step("lock_all", logic.lock_all, scene)
    clock.step("apply_rules", logic.apply_rules, scene)
    clock.step("rebuild_tree", logic.rebuild_tree, scene)
    clock.step("update_bounds", logic.update_bounds, scene)
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.length_unit = "MILLIMETERS"
    clock.step("render_output", render.apply_output, scene, s)
    scene.render.engine = "CYCLES"
    clock.step("view_layer_update", ctx.view_layer.update)
    clock.step("camera", lambda: cameras.fr_cameras(scene) or cameras.add_camera(scene, "ISO"))
    clock.step("world", world.apply, scene, s)
    clock.t["finish_import_total"] = time.perf_counter() - t_all
    T = clock.t
    T["build_meshes"] = T.get("mesh_arrays", 0) + T.get("mesh_edges", 0) + T.get("mesh_normals", 0) + \
        T.get("cad_sets", 0)
    T["build_objects_etc"] = T["build_total"] - T["build_meshes"] - T.get("load_cache_again", 0)
    T["objects"] = len(bpy.data.objects)
    T["meshes"] = len(bpy.data.meshes)
    return T


def variants(cache_dir: str) -> dict:
    out: dict = {}
    info, arrays = build.load_cache(cache_dir)
    mids = sorted({n["mesh"] for n in info["nodes"] if n["kind"] == "part" and f"p{n['mesh']}" in arrays})
    for mode in ("update", "no_edges"):
        fresh()
        c = Clock()
        t = time.perf_counter()
        for m in mids:
            new_mesh_parts(f"P{m}", arrays[f"p{m}"], arrays[f"n{m}"], arrays[f"t{m}"], c, mode)
        out[f"meshes_{mode}"] = time.perf_counter() - t
        out[f"meshes_{mode}_parts"] = dict(c.t)
    # the meshes written to a .blend and read back (what a background Blender could hand over)
    fresh()
    c = Clock()
    made = [new_mesh_parts(f"P{m}", arrays[f"p{m}"], arrays[f"n{m}"], arrays[f"t{m}"], c) for m in mids]
    path = os.path.join(cache_dir, "meshes_test.blend")
    t = time.perf_counter()
    bpy.data.libraries.write(path, set(made), compress=False)
    out["blend_write"] = time.perf_counter() - t
    out["blend_mb"] = os.path.getsize(path) / 1e6
    fresh()
    t = time.perf_counter()
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.meshes = list(src.meshes)
    out["blend_append_meshes"] = time.perf_counter() - t
    # objects alone: how much of the object phase is Blender's own and how much our properties
    fresh()
    me = bpy.data.meshes.new("one")
    coll = bpy.data.collections.new("c")
    bpy.context.scene.collection.children.link(coll)
    n = len(info["nodes"])
    t = time.perf_counter()
    obs = []
    for i in range(n):
        ob = bpy.data.objects.new(f"O{i}", me)
        coll.objects.link(ob)
        obs.append(ob)
    out["objects_bare"] = time.perf_counter() - t
    t = time.perf_counter()
    for ob in obs:
        ob["fr_uid"] = "x/y#1"
        ob["fr_name"] = "name"
        ob["fr_kind"] = "part"
        ob["fr_color"] = "#ffffff"
        ob["fr_cad_material"] = ""
        ob["fr_instance"] = ""
        build.set_mat(ob, build.PROP_CAD_BASIS, ob.matrix_basis)
        build.set_mat(ob, build.PROP_REST_BASIS, ob.matrix_basis)
    out["objects_props"] = time.perf_counter() - t
    out["objects_n"] = n
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cache")
    ap.add_argument("--json", default="")
    ap.add_argument("--variants", action="store_true")
    a = ap.parse_args(argv)
    T = timed_import(a.cache)
    if a.variants:
        T["variants"] = variants(a.cache)
    txt = json.dumps(T, indent=1, default=float)
    if a.json:
        with open(a.json, "w") as fh:
            fh.write(txt)
    print(txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
