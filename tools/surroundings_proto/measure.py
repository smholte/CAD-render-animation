"""Study 0311: the measurements of the report (one experiment per process, so memory numbers are clean).

    ~/venv/bin/python tools/surroundings_proto/measure.py --exp NAME --out DIR [options]

ground   procedural vs scanned (ambientCG CC0, 2K) ground: grass + gravel, the same views, time and memory
grass    a million grass blades: none / instanced clumps / one merged mesh (Realize Instances)
cull     camera culling and the light versions on / off: instances, evaluation, render time, memory
dab      one brush dab while the scene is open: the terrain's arrays, the mesh, the scatter evaluated again
frame4k  the whole scene at 3840 x 2160 (Cycles CPU, the app's "preview" 128 samples unless --samples)
web      what the 3D page would carry: terrain grids, light trees as GPU instances, sizes of the .glb
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import scene as SC  # noqa: E402
import terrain as TR  # noqa: E402

CRANE = "/tmp/claude-0/p/crane.blend"


def ground_test(a):
    """A flat field: grass with a painted gravel patch (noisy edge), two views. PROC and SCAN in turn."""
    res = {}
    for mode in ("PROC", "SCAN"):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        SC._MATS.clear()
        for im in list(bpy.data.images):
            bpy.data.images.remove(im)
        T = TR.Terrain(half=60.0, step=0.25)
        T.stroke(lambda x, y: T.paint("gravel", x, y, 5.0, 1.0, seed=11), [(-3, 0), (6, 8), (14, 10), (22, 26)], 2.0)
        attrs = {SC.LAYER_ATTR + k: v for k, v in T.layers.items() if v.max() > 0.01}
        me = SC.grid_mesh("FR terrain", T.verts(), T.grid_faces(), attrs, T.verts()[:, :2])
        tex = SC.scanned(a.tex) if mode == "SCAN" else None
        me.materials.append(SC.ground_material(["grass", "gravel"], mode, tex))
        SC.new_ob("FR terrain", me)
        sc = bpy.context.scene
        SC.setup_render(sc, 960, 540, a.samples or 64)
        out = {}
        for view, (loc, tgt, lens) in {"eye": ((-6.0, -6.0, 1.7), (6.0, 8.0, 0.0), 30.0),
                                       "close": ((2.0, 1.0, 1.2), (3.0, 2.5, 0.0), 35.0)}.items():
            SC.camera("cam", loc, tgt, lens)
            tm = {}
            SC.render(os.path.join(a.out, f"ground_{mode.lower()}_{view}.jpg"), tm, "r")
            out[view] = {"s": tm["r"], "mem": tm["r_mem"], "peak_mb": tm["r_peak_mb"], "first": tm["r_first"]}
        imgs = [im for im in bpy.data.images if im.size[0] > 0]
        out["images"] = [(os.path.basename(im.filepath), tuple(im.size), im.channels) for im in imgs]
        out["image_mb_as_bytes"] = round(sum(im.size[0] * im.size[1] * 4 for im in imgs) / 2 ** 20, 1)
        out["files_mb"] = round(sum(os.path.getsize(bpy.path.abspath(im.filepath)) for im in imgs) / 2 ** 20, 1)
        res[mode] = out
        print(mode, json.dumps(out), flush=True)
    return res


def full_scene(a, kinds=None, cull=True, lod=True, density=1.0, shot="ground", realize=()):
    tm = {}
    sc, T, terrain = SC.build(8, crane_blend=CRANE if os.path.exists(CRANE) else None, timings=tm)
    w, h = (int(v) for v in a.size.split("x"))
    SC.setup_render(sc, w, h, a.samples or 32)
    cam = SC.camera("FR shot", *SC.SHOTS[shot])
    src = SC.make_sources()
    obs = SC.add_scatter(terrain, src, cam, kinds, cull=cull, lod=lod, density_scale=density)
    for kind in realize:
        mod = obs[kind].modifiers[0]
        ng = mod.node_group.copy()
        mod.node_group = ng
        out = next(n for n in ng.nodes if n.bl_idname == "NodeGroupOutput")
        link = out.inputs[0].links[0]
        real = ng.nodes.new("GeometryNodeRealizeInstances")
        ng.links.new(link.from_socket, real.inputs[0])
        ng.links.new(real.outputs[0], out.inputs[0])
    t = time.time()
    bpy.context.view_layer.update()
    tm["eval"] = round(time.time() - t, 2)
    tm["instances"] = SC.instance_counts()
    dg = bpy.context.evaluated_depsgraph_get()
    tris = 0
    for ob in obs.values():
        ev = ob.evaluated_get(dg)
        try:
            me = ev.to_mesh()
            tris += sum(len(p.vertices) - 2 for p in me.polygons) if len(me.polygons) < 3_000_000 else len(me.polygons)
            ev.to_mesh_clear()
        except RuntimeError:
            pass
    tm["realized_tris"] = tris
    tm["rss_after_eval_mb"] = round(SC.rss_mb())
    return sc, T, terrain, obs, tm


def grass_test(a):
    res = {}
    for label, kinds, realize in (("none", ["tree", "conifer", "bush", "rock"], ()),
                                  ("instanced", None, ()), ("merged", None, ("grass",))):
        if a.only and label != a.only:
            continue
        sc, T, terrain, obs, tm = full_scene(a, kinds, realize=realize, shot="ground")
        SC.render(os.path.join(a.out, f"grass_{label}.jpg"), tm, "r")
        tm["rss_end_mb"] = round(SC.rss_mb())
        tm["peak_mb"] = round(SC.peak_mb())
        res[label] = tm
        print(label, json.dumps(tm, default=str), flush=True)
    return res


def cull_test(a):
    res = {}
    for label, cull, lod in (("cull+light", True, True), ("no cull", False, True), ("no light versions", True, False)):
        if a.only and label != a.only:
            continue
        sc, T, terrain, obs, tm = full_scene(a, None, cull=cull, lod=lod, shot=a.shot)
        SC.render(os.path.join(a.out, f"cull_{label.replace(' ', '_').replace('+', '_')}_{a.shot}.jpg"), tm, "r")
        tm["peak_mb"] = round(SC.peak_mb())
        res[label] = tm
        print(label, json.dumps(tm, default=str), flush=True)
    return res


def dab_test(a):
    sc, T, terrain, obs, tm = full_scene(a, None, shot=a.shot)
    me = terrain.data
    out = {"setup": tm}
    rows = []
    for k in range(6):
        x, y = -30.0 + 6 * k, 40.0
        t0 = time.time()
        T.dab("raise", x, y, 8.0, 0.4)
        t1 = time.time()
        me.vertices.foreach_set("co", T.verts().astype(np.float32).ravel())
        me.update()
        t2 = time.time()
        bpy.context.view_layer.update()
        t3 = time.time()
        rows.append({"numpy": round(t1 - t0, 4), "mesh": round(t2 - t1, 4), "eval": round(t3 - t2, 4)})
    out["raise"] = rows
    rows = []
    for k in range(6):
        x, y = -30.0 + 6 * k, 30.0
        t0 = time.time()
        T.paint_scatter("tree", x, y, 8.0, 1.0)
        dens = T.density("tree")
        t1 = time.time()
        me.attributes[SC.SCATTER_ATTR + "tree"].data.foreach_set("value", dens.astype(np.float32).ravel())
        me.update()
        t2 = time.time()
        bpy.context.view_layer.update()
        t3 = time.time()
        rows.append({"numpy": round(t1 - t0, 4), "mesh": round(t2 - t1, 4), "eval": round(t3 - t2, 4)})
    out["scatter"] = rows
    # the camera moves: culling makes the scatter evaluate again
    rows = []
    cam = sc.camera
    for k in range(6):
        cam.location.x += 2.0
        t0 = time.time()
        bpy.context.view_layer.update()
        rows.append(round(time.time() - t0, 4))
    out["camera_move_eval"] = rows
    print(json.dumps(out), flush=True)
    return out


def frame4k(a):
    a.size = "3840x2160"
    sc, T, terrain, obs, tm = full_scene(a, None, shot=a.shot)
    sc.cycles.samples = a.samples or 128
    sc.cycles.adaptive_threshold = 0.03
    SC.render(os.path.join(a.out, f"frame4k_{a.shot}.jpg"), tm, "r")
    tm["peak_mb"] = round(SC.peak_mb())
    print(json.dumps(tm, default=str), flush=True)
    return tm


def web_test(a):
    res = {}
    for step in (1.0, 2.0, 4.0):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        T, line = SC.make_terrain(8)
        k = int(round(step / T.step))
        n = (T.n - 1) // k + 1
        sub = TR.Terrain(half=T.half, step=step, h=T.h[::k, ::k].copy())
        me = SC.grid_mesh("terrain", sub.verts(), sub.grid_faces(), {}, sub.verts()[:, :2] / (2 * T.half) + 0.5)
        ob = SC.new_ob("terrain", me)
        path = os.path.join(a.out, f"web_terrain_{step:g}m.glb")
        bpy.ops.object.select_all(action="DESELECT")
        ob.select_set(True)
        bpy.context.view_layer.objects.active = ob
        bpy.ops.export_scene.gltf(filepath=path, use_selection=True, export_format="GLB", export_draco_mesh_compression_enable=False)
        res[f"terrain_{step:g}m"] = {"verts": len(me.vertices), "kb": round(os.path.getsize(path) / 1024)}
    # trees: light versions as GPU instances (one mesh, N matrices)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    SC._MATS.clear()
    T, line = SC.make_terrain(8)
    mats = SC.scene_mats()
    import shapes as SH
    me = SC.mesh_from("tree light", SH.tree(1, lod="LIGHT"), mats)
    dens = T.density("tree")
    rng = np.random.default_rng(1)
    cells = np.argwhere(rng.random(dens.shape) < dens * 0.012 * T.step ** 2)
    for i, j in cells:
        ob = SC.new_ob("tree", me)
        ob.location = (T.X[i, j], T.Y[i, j], T.h[i, j])
        ob.rotation_euler.z = rng.uniform(0, 6.28)
    path = os.path.join(a.out, "web_trees.glb")
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", export_gpu_instances=True)
    res["trees"] = {"count": len(cells), "tris_each": sum(len(p.vertices) - 2 for p in me.polygons),
                    "kb": round(os.path.getsize(path) / 1024)}
    print(json.dumps(res), flush=True)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tex", default=os.path.expanduser("~/dl"))
    ap.add_argument("--samples", type=int, default=0)
    ap.add_argument("--size", default="960x540")
    ap.add_argument("--shot", default="overview")
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    fn = {"ground": ground_test, "grass": grass_test, "cull": cull_test, "dab": dab_test, "frame4k": frame4k,
          "web": web_test}[a.exp]
    res = fn(a)
    tag = a.exp + (f"_{a.only}" if a.only else "") + (f"_{a.shot}" if a.exp in ("cull", "frame4k", "dab") else "")
    with open(os.path.join(a.out, f"m_{tag}.json"), "w") as f:
        json.dump(res, f, indent=1, default=str)


if __name__ == "__main__":
    main()
