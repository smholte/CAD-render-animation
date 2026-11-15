"""Helpers for the 0141 study: snapshot of what a Build wrote, and the difference between two snapshots."""
import json
import numpy as np
import bpy


def _props(group, depth=0):
    out = {}
    for p in group.bl_rna.properties:
        k = p.identifier
        if k in ("rna_type",):
            continue
        try:
            v = getattr(group, k)
        except Exception:
            continue
        if p.type in ("FLOAT", "INT", "BOOLEAN", "STRING", "ENUM"):
            if getattr(p, "is_array", False) or (p.type in ("FLOAT", "INT") and getattr(p, "array_length", 0)):
                v = [float(x) for x in v]
            out[k] = v
        elif p.type == "POINTER":
            out[k] = getattr(v, "name", None) if v is not None else None
        elif p.type == "COLLECTION" and depth < 2:
            for i, it in enumerate(v):
                for kk, vv in _props(it, depth + 1).items():
                    out[f"{k}[{i}].{kk}"] = vv
    for k in group.keys():
        try:
            v = group[k]
            if k in group.bl_rna.properties:
                continue                        # (an RNA property: read above)
            if hasattr(v, "to_list"):
                v = v.to_list()
            if isinstance(v, (int, float, str)) or (isinstance(v, list) and all(isinstance(x, (int, float)) for x in v)):
                out["#" + k] = v
        except Exception:
            pass
    return out


import re


def _base(name):
    return re.sub(r"\.\d\d\d$", "", name)


def snapshot(scene, joints_too=True):
    s = scene.fresing
    snap = {"mesh": {}, "cable": {}, "joint": {}, "keys": {}, "obj": {}}
    groups = {}
    for me in bpy.data.meshes:
        if me.name.startswith("FR ") and me.users:
            co = np.empty(len(me.vertices) * 3, np.float32)
            me.vertices.foreach_get("co", co)
            attrs = {}
            for a in me.attributes:
                if a.name.startswith("fr_") and a.data_type == "FLOAT" and a.domain == "POINT":
                    v = np.empty(len(me.vertices), np.float32)
                    a.data.foreach_get("value", v)
                    attrs[a.name] = v
            groups.setdefault(_base(me.name), []).append((co.reshape(-1, 3).copy(), attrs))
    for base, rows in groups.items():       # several with one name (a trail per copy of a screw): ordered by content
        rows.sort(key=lambda r: (len(r[0]), r[0].tobytes()))
        for i, (co, attrs) in enumerate(rows):
            key = base if len(rows) == 1 else f"{base} #{i}"
            snap["mesh"][key] = co
            for n, v in attrs.items():
                snap["mesh"][key + "|" + n] = v
    for ob in bpy.data.objects:
        if ob.name.startswith("FR "):
            for k in ob.keys():
                v = ob[k]
                if hasattr(v, "to_list"):
                    snap["obj"][ob.name + "#" + k] = np.array(v.to_list(), dtype=float)
                elif isinstance(v, (int, float, str)):
                    snap["obj"][ob.name + "#" + k] = v
    from fresing_render.blender import paths as _p
    for ob in scene.objects:
        for idb, tag in ((ob, ""), (ob.data if ob.type == "CAMERA" else None, "data.")):
            if idb is None or idb.animation_data is None or idb.animation_data.action is None:
                continue
            for fc in _p._fcurves(idb):
                n = len(fc.keyframe_points)
                co = np.empty(2 * n, np.float32)
                fc.keyframe_points.foreach_get("co", co)
                snap["keys"][f"{_base(ob.name) if ob.get('fr_anim_camera') else ob.name}|{tag}{fc.data_path}[{fc.array_index}]"] = co.reshape(-1, 2).copy()
    for it in s.cables:
        for k, v in _props(it).items():
            snap["cable"][it.name + "." + k] = v
    from fresing_render.blender import joints
    for j in s.joints:
        snap["joint"][j.name] = float(joints.get_value(j))
        if j.motion is not None and j.motion.animation_data and j.motion.animation_data.action:
            from fresing_render.blender import paths
            for fc in paths._fcurves(j.motion):
                n = len(fc.keyframe_points)
                co = np.empty(2 * n, np.float32)
                fc.keyframe_points.foreach_get("co", co)
                snap["keys"][j.name + "|" + fc.data_path] = co.reshape(-1, 2).copy()
    return snap


def diff(a, b, tol=1e-4, show=40):
    rows = []
    for sec in a:
        for k in sorted(set(a[sec]) | set(b[sec])):
            x, y = a[sec].get(k), b[sec].get(k)
            if x is None or y is None:
                rows.append((sec, k, "only in one"))
                continue
            if isinstance(x, np.ndarray) or isinstance(y, np.ndarray):
                x, y = np.asarray(x), np.asarray(y)
                if x.shape != y.shape:
                    rows.append((sec, k, f"shape {x.shape} vs {y.shape}"))
                else:
                    d = float(np.abs(x - y).max(initial=0.0))
                    if d > tol:
                        rows.append((sec, k, f"max diff {d:.4f}"))
            elif isinstance(x, float) and isinstance(y, float):
                if abs(x - y) > tol:
                    rows.append((sec, k, f"{x:.5f} vs {y:.5f}"))
            elif isinstance(x, list) and isinstance(y, list) and all(isinstance(v, (int, float)) for v in x + y):
                if len(x) != len(y) or max((abs(p - q) for p, q in zip(x, y)), default=0.0) > tol:
                    rows.append((sec, k, f"{[round(v, 3) for v in x[:6]]} vs {[round(v, 3) for v in y[:6]]}"))
            elif x != y:
                xs, ys = str(x), str(y)
                rows.append((sec, k, f"{xs[:150]} vs {ys[:150]}"))
    for r in rows[:show]:
        print("   DIFF", *r)
    print("   differences:", len(rows))
    return rows
