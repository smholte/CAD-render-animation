"""Task 0318: carbon fibre on curved parts – four ways side by side (pictures for the report).

    ~/venv/bin/python tools/carbon_compare.py --step <test_finishes.step> --out dist/carbon [--samples 32] [--res 420]

Blender as a Python module, Cycles on the processor, the app's Product light. The carbon parts of the finishes test
model (cup, tube with a cone, U-shaped folded panel, free-form hood, flat plate), each close up, with the weave laid by:

  old      the study's (0270) box projection: the face's main axis per pixel – it switches at 45° (the seam)
  blend    (a) the three projections blended in the weave's own coordinates (signs lined up) in a band round 45°
  uv       (c) a UV unwrap made by Blender (points merged, seams at sharp edges, conformal), scaled to metres
  faces    (b) the shipped way: every CAD face's own weave coordinates, continued across folds (``weave_frames``)

Writes carbon_<shape>_<way>.png, a sheet ``carbon_compare.png`` and the render times (``times.json``)."""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

SHAPES = {"cup": "CUP CARBON", "tube": "TUBE CARBON", "panel": "PANEL CARBON", "hood": "HOOD CARBON",
          "plate": "PLATE CARBON"}
#: camera direction (from the part's centre) and distance factor of its size
VIEW = {"cup": ((0.9, -1.0, 0.55), 1.5), "tube": ((0.3, -1.0, 0.75), 1.15), "panel": ((0.9, -1.1, 0.8), 1.5),
        "hood": ((1.0, -0.9, 0.9), 1.35), "plate": ((0.4, -1.0, 1.2), 1.0)}
WAYS = ("old", "blend", "uv", "faces")
#: close-ups ("<shape>_close"): where to look (a share of the part's box from its low corner) and from how far (m)
CLOSE = {"panel": ((0.937, 0.5, 0.094), (-1.0, -0.6, 1.0), 0.05), "cup": ((0.5, 0.5, 0.55), (0.9, -1.0, 0.3), 0.07),
         "tube": ((0.72, 0.5, 0.5), (0.2, -1.0, 0.6), 0.07), "hood": ((0.5, 0.5, 0.9), (0.6, -0.8, 0.9), 0.08)}


def _old(b, closed_count=4.0, tow=None):
    """The study's dominant projection: the face's main object axis, per pixel."""
    ps, ns = b.sep(b.p()), b.sep(b.n())
    ax = [b.math("ABSOLUTE", ns[k]) for k in range(3)]
    is_x = b.math("MULTIPLY", b.math("GREATER_THAN", ax[0], ax[1]), b.math("GREATER_THAN", ax[0], ax[2]))
    is_y = b.math("MULTIPLY", b.math("GREATER_THAN", ax[1], ax[0]), b.math("GREATER_THAN", ax[1], ax[2]))
    u = b.mix("FLOAT", is_x, b.mix("FLOAT", is_y, ps[0], ps[0]), ps[1])
    v = b.mix("FLOAT", is_x, b.mix("FLOAT", is_y, ps[1], ps[2]), ps[2])
    du = b.mix("VECTOR", is_x, b.mix("VECTOR", is_y, (1.0, 0.0, 0.0), (1.0, 0.0, 0.0)), (0.0, 1.0, 0.0))
    dv = b.mix("VECTOR", is_x, b.mix("VECTOR", is_y, (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)), (0.0, 0.0, 1.0))
    return u, v, du, dv


def _blend(b, closed_count=4.0, tow=None):
    """(a) the three projections blended in the weave's coordinates: x faces (y, -sx z), y faces (x, sy z) … with the
    signs of the normal so that neighbouring projections run the same way; weights |n|^8."""
    ps, ns = b.sep(b.p()), b.sep(b.n())
    sg = [b.math("SIGN", ns[k]) for k in range(3)]
    # x faces: (y, -sign(nx) z); y faces: (x, sign(ny) z)?  z faces: (x, y) – u shared by two of them each time
    cand = [(ps[1], b.math("MULTIPLY", b.math("MULTIPLY", sg[0], -1.0), ps[2])),
            (ps[0], b.math("MULTIPLY", sg[1], ps[2])),
            (ps[0], ps[1])]
    dirs = [((0.0, 1.0, 0.0), (0.0, 0.0, -1.0)), ((1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
            ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0))]
    ws = [b.math("POWER", b.math("ABSOLUTE", ns[k]), 8.0) for k in range(3)]
    tot = b.math("MAXIMUM", b.math("ADD", b.math("ADD", ws[0], ws[1]), ws[2]), 1e-9)
    u = v = None
    du = dv = None
    for k in range(3):
        f = b.math("DIVIDE", ws[k], tot)
        tu, tv = b.math("MULTIPLY", cand[k][0], f), b.math("MULTIPLY", cand[k][1], f)
        u = tu if u is None else b.math("ADD", u, tu)
        v = tv if v is None else b.math("ADD", v, tv)
        a_ = b.vmath("SCALE", dirs[k][0], scale=f)
        c_ = b.vmath("SCALE", dirs[k][1], scale=f)
        du = a_ if du is None else b.vmath("ADD", du, a_)
        dv = c_ if dv is None else b.vmath("ADD", dv, c_)
    return u, v, b.vmath("NORMALIZE", du), b.vmath("NORMALIZE", dv)


def _uv(b, closed_count=4.0, tow=None):
    """(c) the UV map "FR weave" (metres), its tangent turned back into object space."""
    uvm = b.node("ShaderNodeUVMap")
    uvm.uv_map = "FR weave"
    sp = b.sep(uvm.outputs["UV"])
    tn = b.node("ShaderNodeTangent")
    tn.direction_type = "UV_MAP"
    tn.uv_map = "FR weave"
    geo = b.node("ShaderNodeNewGeometry")
    t_w = tn.outputs["Tangent"]
    b_w = b.vmath("CROSS_PRODUCT", geo.outputs["Normal"], t_w)
    out = []
    for vec in (t_w, b_w):
        vt = b.node("ShaderNodeVectorTransform")
        vt.vector_type = "VECTOR"
        vt.convert_from, vt.convert_to = "WORLD", "OBJECT"
        b.put(vt.inputs[0], vec)
        out.append(vt.outputs[0])
    return sp[0], sp[1], out[0], out[1]


def _diag(b, s):
    """--diag: the weave as black and white tows (which tow is on top), matte: a seam shows as a break in the pattern."""
    from fresing_render.blender import finishes
    t = float(s["tow"])
    U, V, du, dv = finishes.weave_coords(b, 4.0, tow=t)
    iu, iv = b.math("FLOOR", b.math("DIVIDE", U, t)), b.math("FLOOR", b.math("DIVIDE", V, t))
    warp = b.math("LESS_THAN", b.math("FLOORED_MODULO", b.math("ADD", iu, iv), 4.0), 2.0)
    stripe = b.math("LESS_THAN", b.math("FLOORED_MODULO", iv, 8.0), 1.0)          # every 8th row marked
    col = b.mix("RGBA", warp, (0.08, 0.08, 0.08, 1.0), (0.8, 0.8, 0.8, 1.0))
    col = b.mix("RGBA", b.math("MULTIPLY", stripe, 0.6), col, (0.8, 0.1, 0.05, 1.0))
    return dict(color=col, roughness=0.8, coat_roughness=0.8, coat_normal=False)


def unwrap(ob) -> float:
    """(c): a copy of the part's mesh, points merged, seams at sharp edges (> 50°), Blender's conformal unwrap, UVs
    scaled to metres; written back as the UV map "FR weave" (the importer's meshes have their points per CAD face: each
    corner takes the UV of the merged point it sits on). Returns the seconds it took."""
    import bmesh
    import bpy
    import numpy as np
    t0 = time.time()
    me = ob.data
    tmp = bpy.data.objects.new("FR unwrap", me.copy())
    bpy.context.scene.collection.objects.link(tmp)
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    bpy.context.view_layer.objects.active = tmp
    tmp.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.remove_doubles(threshold=1e-6)
    bpy.ops.mesh.select_all(action="DESELECT")
    bpy.ops.mesh.edges_select_sharp(sharpness=math.radians(50.0))
    bpy.ops.mesh.mark_seam(clear=False)
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.unwrap(method="CONFORMAL", margin=0.0)
    bpy.ops.object.mode_set(mode="OBJECT")
    tm = tmp.data
    # scale: UV area = 3-D area
    bm = bmesh.new()
    bm.from_mesh(tm)
    uvl = bm.loops.layers.uv.active
    a3 = sum(f.calc_area() for f in bm.faces)
    a2 = 0.0
    for f in bm.faces:
        uvs = [l[uvl].uv for l in f.loops]
        for i in range(1, len(uvs) - 1):
            a2 += abs((uvs[i] - uvs[0]).cross(uvs[i + 1] - uvs[0])) / 2
    k = math.sqrt(a3 / max(a2, 1e-20))
    # per merged point and face normal side: the UV (faces of one CAD face share it)
    lookup = {}
    for f in bm.faces:
        for l in f.loops:
            key = (tuple(round(c * 1e6) for c in l.vert.co), tuple(round(c, 1) for c in f.normal))
            lookup[key] = (l[uvl].uv[0] * k, l[uvl].uv[1] * k)
    bm.free()
    uv = me.uv_layers.get("FR weave") or me.uv_layers.new(name="FR weave")
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    for poly in me.polygons:
        nk = tuple(round(c, 1) for c in poly.normal)
        for li in poly.loop_indices:
            vi = me.loops[li].vertex_index
            key = (tuple(round(c * 1e6) for c in co[vi]), nk)
            uv.data[li].uv = lookup.get(key, (0.0, 0.0))
    bpy.data.objects.remove(tmp)
    return time.time() - t0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--step", default=os.path.join(ROOT, "tests", "data", "test_finishes.step"))
    ap.add_argument("--out", default="dist/carbon")
    ap.add_argument("--samples", type=int, default=32)
    ap.add_argument("--res", type=int, default=420)
    ap.add_argument("--shapes", default=",".join(SHAPES))
    ap.add_argument("--ways", default=",".join(WAYS))
    ap.add_argument("--kind", default="TWILL")
    ap.add_argument("--close", action="store_true", help="also the close-ups of the bends and curves")
    ap.add_argument("--diag", action="store_true", help="the weave in black and white, matte (seams show)")
    a = ap.parse_args(argv)
    import bpy
    import addon_utils
    from mathutils import Vector

    import fresing_render
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    from fresing_render.blender import build, finishes, logic, materials, tour
    out = os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)
    sc = tour._fresh((os.path.abspath(a.step),), out)
    tour._look("PRODUCT")
    s = sc.fresing
    parts = {ob.get(build.PROP_NAME, ""): ob for ob in build.iter_parts(sc)}
    shapes = [x for x in a.shapes.split(",") if x]
    for name in SHAPES.values():
        if name in parts:
            parts[name]["fr_group_manual"] = "Carbon"
    logic.ensure_group(s, "Carbon")
    logic.apply_rules(sc)
    g = s.groups["Carbon"]
    g.material = "carbon_fibre"
    g.fin_kind = a.kind
    unwrap_s = {}
    for key in shapes:
        unwrap_s[key] = round(unwrap(parts[SHAPES[key]]), 2)
    cam = bpy.data.objects.new("Carbon cam", bpy.data.cameras.new("Carbon cam"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.lens = 60.0
    cam.data.clip_start = 0.002
    r = sc.render
    r.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = a.samples
    r.resolution_x, r.resolution_y, r.resolution_percentage = a.res, int(a.res * 0.75), 100
    times: dict = {"unwrap_s": unwrap_s}
    keep = finishes.weave_coords
    if a.diag:
        finishes.BUILDERS["carbon"] = _diag
    variants = {"old": _old, "blend": _blend, "uv": _uv, "faces": keep}
    from fresing_render.blender import cameras
    for way in [w for w in a.ways.split(",") if w]:
        finishes.weave_coords = variants[way]
        try:
            mat = bpy.data.materials[materials.material_name("Carbon")]
            materials.build_nodes(mat, "carbon_fibre", "", 0.0, finish=materials.group_finish(g))
        finally:
            finishes.weave_coords = keep
        shots = [(k, False) for k in shapes] + [(k, True) for k in shapes if k in CLOSE and a.close]
        for key, close in shots:
            ob = parts[SHAPES[key]]
            mn, mx = build.world_bounds([ob])
            c = (Vector(mn) + Vector(mx)) / 2
            size = (Vector(mx) - Vector(mn)).length
            d, f = VIEW[key]
            eye = c + Vector(d).normalized() * size * f
            if close:
                share, d, dist = CLOSE[key]
                c = Vector([mn[i] + share[i] * (mx[i] - mn[i]) for i in range(3)])
                eye = c + Vector(d).normalized() * dist
            cam.matrix_world = tour.Matrix_look(eye, c)
            for o in build.iter_parts(sc):
                o.hide_render = o is not ob
            cameras.update_pixel_angle(sc)
            tag = f"{key}_close" if close else key
            r.filepath = os.path.join(out, f"carbon_{tag}_{way}{'_diag' if a.diag else ''}.png")
            t0 = time.time()
            bpy.ops.render.render(write_still=True)
            times[f"{tag}_{way}"] = round(time.time() - t0, 2)
            print(tag, way, times[f"{tag}_{way}"], flush=True)
    with open(os.path.join(out, "times.json"), "w") as fh:
        json.dump(times, fh, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
