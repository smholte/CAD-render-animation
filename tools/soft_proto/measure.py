"""Study 0300: what the deformers cost and how right they are (Blender 5.2.3 as a Python module).

    ~/venv/bin/python tools/soft_proto/measure.py [out.json]
"""

from __future__ import annotations

import json
import math
import os
import sys
import time

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import read  # noqa: E402
import scene  # noqa: E402
import shapes  # noqa: E402


def world(ob, v):
    M = np.array(ob.matrix_world)
    return v @ M[:3, :3].T + M[:3, 3]


def dist_to_polyline(p, line):
    best = np.full(len(p), np.inf)
    for i in range(0, len(line) - 1, 200):
        a = line[i:i + 201][:-1]
        b = line[i + 1:i + 201]
        ab = b - a
        t = np.clip(np.einsum("pkj,kj->pk", p[:, None, :] - a[None], ab) / np.einsum("kj,kj->k", ab, ab), 0, 1)
        c = a[None] + t[..., None] * ab[None]
        best = np.minimum(best, np.linalg.norm(p[:, None, :] - c, axis=2).min(1))
    return best


def wire_roundness(v, facts, length):
    """How far the surface points lie from the wire's radius round the centre line of the same spring squeezed to
    ``length`` (the exact answer): max and mean, mm."""
    sv, sf, sn, _ = shapes.spring(od=facts["od"], wire=facts["wire"], free=length, turns=facts["turns"],
                                  dead=facts["dead"], per_turn=96)
    # the centre line of that spring = the tube's ring centres
    R = (facts["od"] - facts["wire"]) / 2
    turns = facts["turns"]
    n = int(turns * 400) + 1
    phi = np.linspace(0, 2 * math.pi * turns, n)
    t = phi / (2 * math.pi)
    d = facts["wire"]
    h_dead = facts["dead"] * d
    h_act = length - d - 2 * h_dead
    zc = d / 2 + np.interp(t, [0, facts["dead"], turns - facts["dead"], turns], [0, h_dead, h_dead + h_act,
                                                                                 2 * h_dead + h_act])
    line = np.stack([R * np.cos(phi), R * np.sin(phi), zc], 1)
    v = v[:-2]                                   # the two end caps' centres lie on the centre line itself
    e = np.abs(dist_to_polyline(v, line) - d / 2) * 1000
    return float(e.max()), float(e.mean())


def accuracy():
    res = {}
    for helix in (1.0, 0.0):
        out = scene.build("soft", helix=helix)
        spr, base, top, facts = out["spring"]
        rows = []
        for fr in (1, 20, 40):
            bpy.context.scene.frame_set(fr)
            v, f = scene.evaluated(spr)
            L = float(top.location.z - 0.01)
            mx, mn = wire_roundness(v, facts, L)
            rows.append({"frame": fr, "length_mm": round(L * 1000, 2), "off_round_max_mm": round(mx, 3),
                         "off_round_mean_mm": round(mn, 3)})
        res["spring_helix" if helix else "spring_plain_stretch"] = rows
    # linear in the length: the middle shape = the mean of the two ends (one morph target is exact)
    out = scene.build("soft")
    spr, base, top, facts = out["spring"]
    shapes_at = {}
    for z in (0.09, 0.075, 0.06):
        top.animation_data_clear()
        top.location.z = z
        bpy.context.view_layer.update()
        shapes_at[z] = scene.evaluated(spr)[0]
    lin = 0.5 * (shapes_at[0.09] + shapes_at[0.06])
    res["spring_morph_error_mm"] = float(np.abs(lin - shapes_at[0.075]).max() * 1000)
    # buffer: volume kept, bulge; and one / two morph targets
    buf, car, stop = out["buffer"]
    car.animation_data_clear()
    v0, f0 = scene.evaluated(buf)
    vol0 = read.volume(v0, f0)
    rows, shp = [], {}
    for z in (0.045, 0.0365, 0.0325, 0.0285, 0.0245):
        car.location.z = z
        bpy.context.view_layer.update()
        v, f = scene.evaluated(buf)
        shp[z] = v
        rows.append({"squeeze_pct": round((0.025 - min(0.025, z - 0.012)) / 0.025 * 100, 1),
                     "volume_pct": round(read.volume(v, f) / vol0 * 100, 2),
                     "widest_mm": round(float(np.hypot(v[:, 0], v[:, 1]).max() * 2000), 2)})
    res["buffer"] = rows
    one = shp[0.045] + (shp[0.0245] - shp[0.045]) * 0.5
    res["buffer_one_morph_error_mm"] = float(np.abs(one - shp[0.0325]).max() * 1000)
    two = shp[0.0325] + (shp[0.0245] - shp[0.0325]) * 0.5
    res["buffer_two_morphs_error_mm"] = float(np.abs(two - shp[0.0285]).max() * 1000)
    # tyre: lowest point in the world stays on the ground; length of the flat
    ty, hub, gro = out["tyre"]
    rows = []
    for fr in (1, 30, 70):
        bpy.context.scene.frame_set(fr)
        v, _ = scene.evaluated(ty)
        w = world(ty, v)
        flat = w[w[:, 2] < 0.0005]
        rows.append({"frame": fr, "axle_mm": round(hub.location.z * 1000, 1),
                     "lowest_mm": round(float(w[:, 2].min() * 1000), 3),
                     "flat_length_mm": round(float(np.ptp(flat[:, 0]) * 1000) if len(flat) else 0.0, 1),
                     "width_mm": round(float(np.ptp(w[:, 1]) * 1000), 1)})
    res["tyre"] = rows
    # bellows: cuffs keep their length
    bel, barrel, rod_end, bf = out["bellows"]
    rows = []
    for fr in (1, 40, 80):
        bpy.context.scene.frame_set(fr)
        v, _ = scene.evaluated(bel)
        z = v[:, 2]
        rows.append({"frame": fr, "length_mm": round(float(np.ptp(z) * 1000), 2)})
    res["bellows"] = rows
    return res


def timing(copies=50, frames=96):
    """ms per frame for ``copies`` of each station: rigid (as today) and soft."""
    res = {}
    for variant in ("rigid", "soft"):
        out = scene.build(variant)
        sc = bpy.context.scene
        made = 0
        for kind in ("spring", "buffer", "bellows", "tyre"):
            ob = out[kind][0]
            for i in range(1, copies):
                c = ob.copy()                    # the mesh is shared, as the app's copies of one part
                c.location.y += 0.2 * i
                sc.collection.objects.link(c)
                made += 1
        sc.frame_set(1)
        sc.frame_set(2)
        per = {}
        t0 = time.perf_counter()
        for fr in range(1, frames + 1):
            sc.frame_set(fr)
        per["all"] = (time.perf_counter() - t0) / frames * 1000
        res[variant] = {k: round(v, 2) for k, v in per.items()}
    res["objects_each_kind"] = copies
    res["threads"] = os.cpu_count()
    return res


def timing_each(copies=100, frames=48):
    """ms per frame per soft part, one kind at a time: soft minus rigid."""
    out_rows = {}
    for kind in ("spring", "buffer", "bellows", "tyre"):
        row = {}
        for variant in ("rigid", "soft"):
            out = scene.build(variant)
            sc = bpy.context.scene
            # only this kind: delete the other kinds' parts
            keep = out[kind][0]
            for k in ("spring", "buffer", "bellows", "tyre"):
                if k != kind:
                    bpy.data.objects.remove(out[k][0])
            for i in range(1, copies):
                c = keep.copy()
                c.location.y += 0.2 * i
                sc.collection.objects.link(c)
            sc.frame_set(1)
            sc.frame_set(2)
            t0 = time.perf_counter()
            for fr in range(1, frames + 1):
                sc.frame_set(fr)
            row[variant] = (time.perf_counter() - t0) / frames * 1000
        me = keep.data
        row["tris_import"] = len(me.polygons)
        row["ms_per_part_frame"] = round((row["soft"] - row["rigid"]) / copies, 4)
        row["rigid"], row["soft"] = round(row["rigid"], 2), round(row["soft"], 2)
        out_rows[kind] = row
    return out_rows


def buffer_variants(copies=100, frames=48):
    """The rubber's cost: how it is made finer (in the nodes every frame, or once as a finer import) and how its
    normals are made."""
    import nodes
    rows = []
    for label, sub, rows_side, nrm in (("import mesh as it is, no refining", 0, 1, "angle"),
                                       ("refined in the nodes, level 2", 2, 1, "angle"),
                                       ("refined in the nodes, level 3", 3, 1, "angle"),
                                       ("finer import (12 rows), normals by angle", 0, 12, "angle"),
                                       ("finer import (12 rows), import normals kept", 0, 12, "keep")):
        t = {}
        for variant in ("rigid", "soft"):
            bpy.ops.wm.read_factory_settings(use_empty=True)
            sc = bpy.context.scene
            sc.frame_start, sc.frame_end = 1, frames
            v, f, n = shapes.buffer(rows=rows_side)
            buf = scene.mesh_object("Rubber buffer", (v, f, n), sc.collection)
            car = bpy.data.objects.new("Stop", None)
            sc.collection.objects.link(car)
            scene.key(car, "location", [(1, 0.033), (24, 0.0165), (48, 0.033)], index=2)
            if variant == "soft":
                g = nodes.squeeze("FR soft squeeze test", subdivide=sub, normals=nrm)
                mod = buf.modifiers.new("FR soft", "NODES")
                mod.node_group = g
                scene.set_inputs(mod, **{"Presser": car, "Presser point": (0, 0, 0), "Origin": (0, 0, 0),
                                         "Axis": (0, 0, 1), "Free height": 0.025, "Bulge": 1.0})
            for i in range(1, copies):
                c = buf.copy()
                c.location.y += 0.05 * i
                sc.collection.objects.link(c)
            sc.frame_set(1)
            sc.frame_set(2)
            t0 = time.perf_counter()
            for fr in range(1, frames + 1):
                sc.frame_set(fr)
            t[variant] = (time.perf_counter() - t0) / frames * 1000
            if variant == "soft":
                sc.frame_set(24)
                ev, ef = scene.evaluated(buf)
                widest = float(np.hypot(ev[:, 0], ev[:, 1]).max() * 2000)
                tris = len(ef)
        rows.append({"how": label, "triangles_drawn": tris, "widest_mm_at_34pct": round(widest, 2),
                     "ms_per_part_frame": round((t["soft"] - t["rigid"]) / copies, 4)})
    return rows


def shape_key_alternative(copies=100, frames=48):
    """The other way for a spring: one shape key (the shortest shape, made once) + a simple-expression driver from
    the top plate. Exact for a spring (linear), but a shape key lives on the MESH: every copy of the part squeezes
    the same unless each gets its own mesh."""
    out = scene.build("soft")
    sc = bpy.context.scene
    spr, base, top, facts = out["spring"]
    top.animation_data_clear()
    top.location.z = 0.01 + facts["solid"]
    bpy.context.view_layer.update()
    short, _ = scene.evaluated(spr)
    top.location.z = 0.09
    spr.modifiers.clear()
    for k in ("buffer", "bellows", "tyre"):
        bpy.data.objects.remove(out[k][0])
    spr.shape_key_add(name="Basis")
    sk = spr.shape_key_add(name="Shortest")
    sk.data.foreach_set("co", short.astype(np.float32).reshape(-1))
    scene.key(top, "location", [(1, 0.09), (40, 0.06), (56, 0.06), (96, 0.09)], index=2)
    fc = sk.driver_add("value")
    drv = fc.driver
    drv.type = "SCRIPTED"
    var = drv.variables.new()
    var.name = "z"
    var.type = "TRANSFORMS"
    var.targets[0].id = top
    var.targets[0].transform_type = "LOC_Z"
    drv.expression = "(0.09 - z) / %.6f" % (0.08 - facts["solid"])
    simple = drv.is_simple_expression
    for i in range(1, copies):
        c = spr.copy()
        c.location.y += 0.2 * i
        sc.collection.objects.link(c)
    sc.frame_set(1)
    sc.frame_set(2)
    t0 = time.perf_counter()
    for fr in range(1, frames + 1):
        sc.frame_set(fr)
    t = (time.perf_counter() - t0) / frames * 1000
    return {"ms_per_frame_100_springs": round(t, 2), "simple_expression": simple}


def reading():
    rows = []
    cases = [dict(), dict(od=0.03, wire=0.003, free=0.06, turns=7, dead=0.75),
             dict(od=0.12, wire=0.012, free=0.30, turns=6.5, dead=1), dict(od=0.02, wire=0.0015, free=0.05,
                                                                             turns=12.25, dead=1.5)]
    for kw in cases:
        v, f, n, fa = shapes.spring(**kw)
        a = 0.7
        Rm = np.array([[1, 0, 0], [0, math.cos(a), -math.sin(a)], [0, math.sin(a), math.cos(a)]])
        w = v @ Rm.T + [1.2, -0.4, 2.0]
        t = time.perf_counter()
        r = read.spring(w, f)
        dt = time.perf_counter() - t
        rows.append({"made": {k: round(fa[k] * 1000, 2) if k in ("od", "wire", "free", "pitch") else fa[k]
                              for k in ("od", "wire", "free", "turns", "dead", "pitch")},
                     "read": {k: round(float(r[k]) * 1000, 2) if k in ("od", "wire", "free", "pitch")
                              else round(float(r[k]), 2) for k in ("od", "wire", "free", "turns", "dead", "pitch")},
                     "triangles": int(len(f)), "seconds": round(dt, 2)})
    return rows


if __name__ == "__main__":
    dest = sys.argv[1] if len(sys.argv) > 1 else "numbers.json"
    res = {"reading": reading(), "accuracy": accuracy(), "cost_each": timing_each(),
           "cost_mix_50_each": timing(), "buffer_variants": buffer_variants(), "spring_shape_key": shape_key_alternative()}
    with open(dest, "w") as fh:
        json.dump(res, fh, indent=1)
    print(json.dumps(res, indent=1))
