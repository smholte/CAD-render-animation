"""Task 0305 point E: each part's free ways out, measured on the test models (Blender as a Python module, no UI).

    ~/venv/bin/python tasks/0305_proto/freeways.py <model.step> [<subassembly name>] [--json out.json]

For every part of the subassembly (the whole model without a name): which of these ways out are free – the six axes
of the world and both ends of each round axis the importer found on the part (its largest radius first) – while every
other part still stands. A way is free when rays from the part's points (the Assembly sequence's own ``Rays``: up to
48 points, drawn 0.1 mm inside the part) hit no other part along it. Only parts whose box meets the box the part
sweeps are tested. Then the parts are taken out in layers: in each round every part with a free way leaves (fasteners
first, in a round of their own); a part with no free way while others are left is "stuck". Prints a table and the
times.
"""
from __future__ import annotations

import json
import math
import os
import sys
import time

import bpy  # noqa: I001 (bpy first: it makes addon_utils importable)
import addon_utils
import numpy as np
from mathutils import Vector

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
import fresing_render  # noqa: E402
from fresing_render.blender import build, logic, sequence  # noqa: E402

KEEP_BASE = "--keep-base" in sys.argv
AXES = {"+X": (1, 0, 0), "-X": (-1, 0, 0), "+Y": (0, 1, 0), "-Y": (0, -1, 0), "+Z": (0, 0, 1), "-Z": (0, 0, -1)}
SAME = math.cos(math.radians(5))


def load(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    sc = bpy.context.scene
    sc.fresing.out_folder = "/tmp/fw0305"
    t = time.perf_counter()
    assert bpy.ops.fresing.import_step(filepath=path, quality="draft") == {"FINISHED"}
    return sc, time.perf_counter() - t


def round_axes(ob):
    """The part's round axes in the world, largest radius first: [(origin, direction, radius)]."""
    a = ob.data.get("fr_axes")
    if not a:
        return []
    a = np.array(list(a), float).reshape(-1, 7)
    mw = ob.matrix_world
    out = []
    for o, d, r in sorted(((row[:3], row[3:6], row[6]) for row in a), key=lambda t: -t[2]):
        out.append((mw @ Vector(o), (mw.to_3x3() @ Vector(d)).normalized(), r))
    return out


def ways_of(ob):
    """The part's own round axis first (both ends), then the world axes not already along it."""
    ways = []
    for _o, d, _r in round_axes(ob)[:1]:
        for s in (1, -1):
            u = d * s
            name = next((k for k, v in AXES.items() if u.dot(Vector(v)) > SAME), f"axis{'+' if s > 0 else '-'}")
            ways.append((name, u))
    for k, v in AXES.items():
        if all(Vector(v).dot(w) <= SAME for _k, w in ways):
            ways.append((k, Vector(v)))
    return ways


def head_way(ob):
    """A fastener's way out, head first: along its round axis, towards the end whose points lie furthest from the
    axis (the head; a nut has none: None)."""
    ax = round_axes(ob)
    if not ax:
        return None
    o, d, _r = ax[0]
    mw = np.array(ob.matrix_world)
    co = np.array([v.co[:] for v in ob.data.vertices])
    pts = co @ mw[:3, :3].T + mw[:3, 3]
    o, d = np.array(o), np.array(d)
    t = (pts - o) @ d
    rad = np.linalg.norm((pts - o) - np.outer(t, d), axis=1)
    lo, hi = t.min(), t.max()
    band = 0.15 * (hi - lo)
    r_lo, r_hi = rad[t < lo + band].max(), rad[t > hi - band].max()
    if abs(r_lo - r_hi) < 0.15 * max(r_lo, r_hi):
        return None
    return d if r_hi > r_lo else -d


def boxes(parts):
    out = []
    for p in parts:
        pts = np.array([p.matrix_world @ Vector(c) for c in p.bound_box])
        out.append((pts.min(axis=0), pts.max(axis=0)))
    return out


def swept_meets(bi, bj, u, far):
    lo, hi = bi
    u = np.array(u)
    lo2 = np.minimum(lo, lo + u * far)
    hi2 = np.maximum(hi, hi + u * far)
    return bool(np.all(lo2 <= bj[1] + 1e-6) and np.all(bj[0] <= hi2 + 1e-6))


def main():
    args = [a for a in sys.argv[1:] if a != "--keep-base"]
    out_json = None
    if "--json" in args:
        k = args.index("--json")
        out_json = args[k + 1]
        del args[k:k + 2]
    path = args[0]
    sub_name = args[1] if len(args) > 1 else None
    sc, t_import = load(path)
    tree = logic.Tree(sc)
    if sub_name:
        sub = next(o for o in sc.objects if o.get(build.PROP_NAME) == sub_name)
    else:
        sub = build.model_roots(sc)[0]
    parts = [d for d in tree.descendants(sub) if d.get(build.PROP_KIND) == "part"
             and not d.get(build.PROP_EXCLUDED) and len(d.data.polygons)]
    n = len(parts)
    bxs = boxes(parts)
    far = float(np.linalg.norm(np.max([b[1] for b in bxs], axis=0) - np.min([b[0] for b in bxs], axis=0)))
    rays = sequence.Rays(parts)
    fast = [sequence.is_fastener(p) for p in parts]
    ways = [ways_of(p) for p in parts]
    tests = {"pair": 0, "skipped": 0}
    t0 = time.perf_counter()

    LO = np.array([b[0] for b in bxs])
    HI = np.array([b[1] for b in bxs])
    blockers = {}                       # (i, way) -> parts found in the way (a part in the way stays in the way)

    def free(i, u, left, key=None):
        uu = np.array(u)
        lo2 = np.minimum(LO[i], LO[i] + uu * far)
        hi2 = np.maximum(HI[i], HI[i] + uu * far)
        meets = np.all(lo2 <= HI + 1e-6, axis=1) & np.all(LO <= hi2 + 1e-6, axis=1)
        meets[i] = False
        cand = [j for j in np.nonzero(meets)[0] if j in left]
        tests["skipped"] += len(left) - 1 - len(cand)
        known = blockers.setdefault(key, set()) if key is not None else set()
        if known & left:
            return False
        for j in cand:
            tests["pair"] += 1
            if rays.hit(i, j, u, far):
                known.add(j)
                return False
        return True

    vol = [float(np.prod(b[1] - b[0])) for b in bxs]
    base = int(np.argmax(vol)) if KEEP_BASE else None     # the biggest part stays where it is
    everyone = set(range(n))
    first = {}
    for i in range(n):
        first[i] = [k for k, u in ways[i] if free(i, u, everyone, (i, k))]
    t_first = time.perf_counter() - t0
    # layers
    left, layers, chosen = set(range(n)), [], {}
    while left - ({base} if base is not None else set()):
        ready = {}
        for i in sorted(left):
            if i == base:
                continue
            for k, u in ways[i]:
                if free(i, u, left, (i, k)):
                    ready[i] = k
                    break
        if not ready:
            break
        fs = {i: k for i, k in ready.items() if fast[i]}
        take = fs or ready
        layers.append(sorted(take))
        chosen.update(take)
        left -= set(take)
    t_all = time.perf_counter() - t0
    stuck = sorted(left - ({base} if base is not None else set()))
    rows = []
    way_vec = {i: next(u for k, u in ways[i] if k == chosen[i]) for i in chosen}
    heads = {"fasteners": 0, "head_found": 0, "leaves_head_first": 0}
    for i, p in enumerate(parts):
        if not fast[i]:
            continue
        heads["fasteners"] += 1
        h = head_way(p)
        if h is not None:
            heads["head_found"] += 1
            if i in way_vec and float(np.dot(np.array(way_vec[i]), h)) > SAME:
                heads["leaves_head_first"] += 1
    for i, p in enumerate(parts):
        ax = round_axes(p)
        rows.append({"part": p.get(build.PROP_NAME, p.name), "fastener": fast[i], "free_alone": first[i],
                     "layer": next((k for k, L in enumerate(layers) if i in L), None), "way": chosen.get(i),
                     "round_axis": [round(c, 3) for c in ax[0][1]] if ax else None, "tris": len(p.data.polygons)})
    for r in rows:
        print(f"{r['part'][:34]:34s} {'F' if r['fastener'] else ' '} layer {str(r['layer']):>4s} "
              f"way {str(r['way']):6s} free alone: {','.join(r['free_alone']) or '-'}")
    tris = sum(r["tris"] for r in rows)
    summary = {"model": os.path.basename(path), "sub": sub.get(build.PROP_NAME, sub.name), "parts": n,
               "triangles": tris, "import_s": round(t_import, 1), "free_ways_s": round(t_first, 2),
               "layers_s": round(t_all, 2), "pair_tests": tests["pair"], "box_skipped": tests["skipped"],
               "layers": len(layers), "stuck": [rows[i]["part"] for i in stuck],
               "free_alone_none": sum(1 for r in rows if not r["free_alone"]),
               "base": rows[base]["part"] if base is not None else None, **heads}
    print(json.dumps(summary))
    if out_json:
        with open(out_json, "w") as fh:
            json.dump({"summary": summary, "rows": rows}, fh, indent=1)


main()
