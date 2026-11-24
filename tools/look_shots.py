"""Task 0318: close-ups of parts of the finishes test model in their tour looks (``tour.finishes_demo``), for the report
and for checking a look by eye.

    ~/venv/bin/python tools/look_shots.py --parts "PLATE RUST BARE STEEL,DISC PERLAGE" --out dist/shots
        [--step tests/data/test_finishes.step] [--samples 32] [--res 400] [--set "PLATE RUST PAINTED:rust=0.3"]
        [--sheet name.jpg]

Blender as a Python module, Cycles on the processor, the app's Product light. ``--set`` changes a group setting of a
part's group first (rust, wear, fin_kind, fin_amount, fin_size, material). Writes <part>.png per part (+ a sheet)."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--step", default=os.path.join(ROOT, "tests", "data", "test_finishes.step"))
    ap.add_argument("--parts", required=True)
    ap.add_argument("--out", default="dist/shots")
    ap.add_argument("--samples", type=int, default=32)
    ap.add_argument("--res", type=int, default=400)
    ap.add_argument("--set", action="append", default=[])
    ap.add_argument("--dist", type=float, default=1.3)
    ap.add_argument("--dir", default="0.6,-1.0,0.8")
    ap.add_argument("--sheet", default="")
    ap.add_argument("--suffix", default="")
    ap.add_argument("--show-node", default="", help="draw this node's first output as light (checking a mask)")
    a = ap.parse_args(argv)
    import bpy
    import addon_utils
    from mathutils import Vector

    import fresing_render
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    from fresing_render.blender import build, cameras, logic, tour
    out = os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)
    sc = tour._fresh((os.path.abspath(a.step),), out)
    tour._look("PRODUCT")
    groups = tour.finishes_demo(sc)
    s = sc.fresing
    for item in a.set:
        name, _, kv = item.partition(":")
        g = s.groups[groups[name]]
        for pair in kv.split(","):
            k, v = pair.split("=")
            cur = getattr(g, k)
            setattr(g, k, type(cur)(v) if not isinstance(cur, str) else v)
    logic.refresh_group_materials(sc)
    parts = {ob.get(build.PROP_NAME, ""): ob for ob in build.iter_parts(sc)}
    if a.show_node:
        for name in [p for p in a.parts.split(",") if p]:
            mat = parts[name].active_material
            nt = mat.node_tree
            nd = nt.nodes.get(a.show_node)
            if nd is None:
                continue
            em = nt.nodes.new("ShaderNodeEmission")
            nt.links.new(nd.outputs[0], em.inputs["Color"])
            for mo in nt.nodes:
                if mo.type == "OUTPUT_MATERIAL":
                    nt.links.new(em.outputs[0], mo.inputs["Surface"])
    cam = bpy.data.objects.new("Shot cam", bpy.data.cameras.new("Shot cam"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.lens = 60.0
    cam.data.clip_start = 0.002
    r = sc.render
    r.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = a.samples
    r.resolution_x, r.resolution_y, r.resolution_percentage = a.res, int(a.res * 0.75), 100
    d = Vector([float(x) for x in a.dir.split(",")]).normalized()
    files = []
    for name in [p for p in a.parts.split(",") if p]:
        ob = parts[name]
        mn, mx = build.world_bounds([ob])
        c = (Vector(mn) + Vector(mx)) / 2
        size = (Vector(mx) - Vector(mn)).length
        cam.matrix_world = tour.Matrix_look(c + d * size * a.dist, c)
        for o in build.iter_parts(sc):
            o.hide_render = o is not ob
        cameras.update_pixel_angle(sc)
        path = os.path.join(out, name.lower().replace(" ", "_") + a.suffix + ".png")
        r.filepath = path
        t0 = time.time()
        bpy.ops.render.render(write_still=True)
        print(f"{name}: {time.time() - t0:.1f} s", flush=True)
        files.append(path)
    if a.sheet:
        subprocess.run(["convert", *files, "+append", os.path.join(out, a.sheet)], check=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
