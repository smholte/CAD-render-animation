"""Study 0270: render the prototype finishes (``fresing_render/blender/finishes_proto.py``) on the study shapes.

    ~/venv/bin/python tools/finish_sheet.py --out dist/f/img [--only knurl_diamond,spun] [--shots close,product]
        [--res 960] [--samples 64] [--cost] [--far] [--headset] [--thumbs] [--eevee]

Blender as a Python module, Cycles on the processor, the app's Product studio light (its own studio picture as the
one HDRI). Shapes from ``tools/finish_shapes.py`` through the app's own STEP importer. Writes PNGs and ``times.json``.
Branch-only prototype of study 0270."""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

AZ, EL = math.radians(-38.0), math.radians(28.0)
# where each shape stands on the floor (metres; z rotation in degrees) and its close-up: (target, distance)
POSE = {"knob": ((0, 0, 0), 0), "cap": ((0, 0, 0.008), 0), "cup": ((0, 0, 0), 0), "block": ((0, 0, 0), 28),
        "shaft": ((0, 0, 0.011), -8), "plate": ((0, 0, 0), 12), "bushing": ((0, 0, 0.0), 160),
        "way": ((0, 0, 0), 8), "grip": ((0, 0, 0.015), -20), "grille": ((0, 0, 0), 0), "band": ((0, 0, 0), 0),
        "cushion": ((0, 0, 0.008), 0), "yoke": ((0, 0, 0), 0), "weld": ((0, 0, 0), 20)}
CLOSE = {"knob": ((0.0, 0.0, 0.0085), 0.055), "cap": ((0.0, 0.0, 0.006), 0.075), "cup": ((0.0, 0.0, 0.016), 0.09),
         "block": ((0.0, 0.0, 0.033), 0.10), "shaft": ((0.055, 0.0, 0.011), 0.085), "plate": ((0.0, 0.0, 0.0), 0.16),
         "bushing": ((0.0, 0.0, 0.02), 0.10), "way": ((0.0, 0.0, 0.028), 0.10), "grip": ((0.055, 0.0, 0.015), 0.085),
         "grille": ((0.0, 0.0, 0.0), 0.06), "band": ((0.0, 0.0, 0.09), 0.12), "cushion": ((0.0, 0.0, 0.008), 0.075),
         "yoke": ((0.0, 0.0, 0.042), 0.09), "weld": ((0.0, -0.006, 0.009), 0.09)}
LEAN = {"cap": 40.0, "grille": 50.0, "cushion": 40.0}     # degrees about x, towards the camera
PART = {"knob": "KNOB", "cap": "CAP", "cup": "CUP", "block": "BLOCK", "shaft": "SHAFT", "plate": "PLATE",
        "bushing": "BUSHING", "way": "WAY", "grip": "GRIP", "grille": "GRILLE", "band": "BAND",
        "cushion": "CUSHION", "yoke": "YOKE"}


def setup(step_path: str):
    import addon_utils
    import bpy
    import fresing_render
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    sc = bpy.context.scene
    sc.fresing.out_folder = os.path.join(os.path.dirname(step_path), "out")
    t = time.time()
    assert bpy.ops.fresing.import_step(filepath=step_path, quality="normal") == {"FINISHED"}
    print(f"import {time.time() - t:.1f} s", flush=True)
    from fresing_render.blender import finishes_proto as fp
    from fresing_render.blender import world
    from fresing_render.core import studio
    s = sc.fresing
    for k, v in studio.look_settings("PRODUCT", s.background).items():
        setattr(s, k, v)
    s.background_color = (0.80, 0.80, 0.80)
    world.apply(sc, s)
    meshes = set()
    kinds = {}
    for ob in sc.objects:
        if ob.type == "MESH" and ob.data and "fr_axes" in ob.data.keys() or (ob.type == "MESH" and ob.data and
                                                                               "fr_face_starts" in ob.data.keys()):
            if ob.data.name not in meshes:
                meshes.add(ob.data.name)
                kinds[ob.data.name] = fp.prepare_faces(ob.data)
    print("faces:", json.dumps(kinds), flush=True)
    return sc


def pieces(sc):
    """name -> the stand-alone object of that part (first level of the study), and the headset's objects."""
    single, head = {}, []
    for ob in sc.objects:
        if ob.type != "MESH" or not ob.data or "fr_face_starts" not in ob.data.keys():
            continue
        chain = []
        p = ob.parent
        while p is not None:
            chain.append(p.name)
            p = p.parent
        if any(n.startswith("HEADSET") for n in chain):
            head.append(ob)
        elif ob.data.name not in single.values():
            single.setdefault(ob.data.name.split(".")[0], ob)
    return single, head


def weld_set(sc, single):
    """The T-joint and a bead along its seam (both sides of the web)."""
    import bpy
    from mathutils import Matrix, Vector
    base, web = single.get("WELD BASE"), single.get("WELD WEB")
    bead = bpy.data.objects.get("FR study weld bead")
    if bead is None:
        bm_me = bpy.data.meshes.new("FR study weld bead")
        import bmesh
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=0.0045, radius2=0.0045, depth=0.148)
        for v in bm.verts:                      # along x
            v.co.x, v.co.z = v.co.z, v.co.x
        bm.to_mesh(bm_me)
        bm.free()
        for f in bm_me.polygons:
            f.use_smooth = True
        bead = bpy.data.objects.new("FR study weld bead", bm_me)
        sc.collection.objects.link(bead)
        bead.data.materials.append(None)
    return base, web, bead


def stage(sc, fid, single, head, weld):
    """Show only the shapes of ``fid`` in a row on the floor; return the objects in order (first = close-up)."""
    import bpy
    from mathutils import Matrix, Vector
    from fresing_render.blender import finishes_proto as fp
    spec = fp.FINISHES[fid]
    for ob in sc.objects:
        if ob.type == "MESH" and ob.name != "FR Floor" and not ob.name.startswith("FR Floor"):
            ob.hide_render = True
            ob.hide_viewport = True
    shown, x = [], 0.0
    placed = []
    for key in spec["shapes"]:
        if key == "weld":
            base, web, bead = weld
            obs = [base, web, bead]
        else:
            obs = [single[PART[key]]]
        # footprint: the mesh's box
        lo = Vector((1e9,) * 3)
        hi = Vector((-1e9,) * 3)
        for ob in obs[:2] if key == "weld" else obs:
            for c in ob.bound_box:
                lo = Vector(map(min, lo, c))
                hi = Vector(map(max, hi, c))
        size = (hi - lo)
        (dx, dy, dz), rz = POSE[key]
        rot = Matrix.Rotation(math.radians(rz), 4, "Z")
        lean = LEAN.get(key, 0.0)
        if key == "plate" and spec.get("see_through"):
            lean = 50.0                         # stood up, so the background shows through the holes
        if key == "bushing":                    # on its back: the bore is a trough seen from above
            rot = rot @ Matrix.Rotation(math.radians(180), 4, "Y")
        if lean:
            rot = rot @ Matrix.Rotation(math.radians(lean), 4, "X")
        centre = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))
        M = rot @ Matrix.Translation(-centre)
        pts = [M @ Vector(c) for ob in (obs[:2] if key == "weld" else obs) for c in ob.bound_box]
        xs = [q.x for q in pts]
        zmin = min(q.z for q in pts)
        M = Matrix.Translation((x - min(xs) + dx, dy, -zmin)) @ M     # its left side at x, resting on the floor
        half = (max(xs) - min(xs)) / 2
        x += half
        for ob in obs:
            ob.parent = None
            ob.matrix_world = M if ob.name != "FR study weld bead" else M @ Matrix.Translation((0, -0.0055, 0.0095))
            ob.hide_render = ob.hide_viewport = False
            shown.append(ob)
        placed.append((key, M, size))
        x += half + 0.02
    # centre the row on the origin
    shift = Matrix.Translation((-(x - 0.02) / 2, 0, 0))
    for ob in shown:
        ob.matrix_world = shift @ ob.matrix_world
    placed = [(k, shift @ M, s) for k, M, s in placed]
    bpy.context.view_layer.update()
    return shown, placed


def assign(objs, mat):
    for ob in objs:
        if not ob.material_slots:
            ob.data.materials.append(None)
        ob.material_slots[0].link = "OBJECT"
        ob.material_slots[0].material = mat


def camera(sc, target, dist, lens=50.0, name="FR study cam"):
    import bpy
    from mathutils import Vector
    cam = bpy.data.objects.get(name)
    if cam is None:
        cam = bpy.data.objects.new(name, bpy.data.cameras.new(name))
        sc.collection.objects.link(cam)
    cam.data.lens = lens
    cam.data.sensor_width = 36.0
    cam.data.clip_start = 0.002
    cam.data.clip_end = 200.0
    d = Vector((math.cos(EL) * math.sin(-AZ) * -1, -math.cos(EL) * math.cos(AZ), math.sin(EL)))
    t = Vector(target)
    cam.location = t + d * dist
    cam.rotation_mode = "QUATERNION"
    cam.rotation_quaternion = (t - cam.location).to_track_quat("-Z", "Y")
    sc.camera = cam
    return cam


def frame_all(sc, objs, margin=1.12, aspect=16 / 9):
    """Camera along the fixed view direction, just far enough that every box corner is in the picture."""
    from mathutils import Vector
    pts = [ob.matrix_world @ Vector(c) for ob in objs for c in ob.bound_box]
    lo = Vector(map(min, *pts))
    hi = Vector(map(max, *pts))
    c = (lo + hi) / 2
    cam = camera(sc, c, 1.0)
    d = (cam.location - c).normalized()
    R = cam.matrix_world.to_3x3()
    right, up = R.col[0], R.col[1]
    th, tv = 18.0 / 50.0, 18.0 / 50.0 / aspect
    D = 0.0
    for p in pts:
        q = p - c
        D = max(D, q.dot(d) + abs(q.dot(right)) * margin / th, q.dot(d) + abs(q.dot(up)) * margin / tv)
    return camera(sc, c, D)


def render(sc, path, res, samples, engine="CYCLES", square=False, pixel=True):
    import bpy
    from fresing_render.blender import finishes_proto as fp
    from fresing_render.blender import render as fr
    fr.apply_quality(sc, "preview", False)
    r = sc.render
    r.resolution_x, r.resolution_y = res, (res if square else int(res * 9 / 16))
    r.resolution_percentage = 100
    if engine == "EEVEE":
        r.engine = "BLENDER_EEVEE"
        sc.eevee.taa_render_samples = samples
    else:
        r.engine = "CYCLES"
        sc.cycles.samples = samples
        sc.cycles.use_adaptive_sampling = True
        sc.cycles.device = "CPU"
    r.image_settings.file_format = "PNG"
    r.image_settings.color_mode = "RGB"
    r.filepath = path
    if pixel:
        fp.set_pixel_angle(sc)
    else:                                   # the fade switched off (a pixel angle of nothing): to show what it prevents
        for m in bpy.data.materials:
            n = m.node_tree.nodes.get(fp.PIX) if m.node_tree else None
            if n is not None:
                n.outputs[0].default_value = 1e-9
    t = time.time()
    bpy.ops.render.render(write_still=True)
    return round(time.time() - t, 2)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="dist/f/img")
    ap.add_argument("--step", default="dist/f/finish_study.step")
    ap.add_argument("--only", default="")
    ap.add_argument("--shots", default="close,product")
    ap.add_argument("--res", type=int, default=960)
    ap.add_argument("--samples", type=int, default=64)
    ap.add_argument("--cost", action="store_true", help="1920 x 1080 product shot with and without the pattern")
    ap.add_argument("--far", action="store_true")
    ap.add_argument("--headset", action="store_true")
    ap.add_argument("--thumbs", action="store_true")
    ap.add_argument("--eevee", action="store_true")
    ap.add_argument("--copies", action="store_true")
    ap.add_argument("--cost-res", type=int, default=1920)
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    step = os.path.abspath(a.step)
    if not os.path.exists(step):
        import finish_shapes
        finish_shapes.make(step)
    import bpy
    sc = setup(step)
    from fresing_render.blender import finishes_proto as fp
    single, head = pieces(sc)
    weld = weld_set(sc, single)
    times_path = os.path.join(a.out, "times.json")
    times = json.load(open(times_path)) if os.path.exists(times_path) else {}
    ids = [x for x in a.only.split(",") if x] or list(fp.FINISHES)
    shots = [x for x in a.shots.split(",") if x]
    for fid in ids if (shots or a.cost) else []:
        spec = fp.FINISHES[fid]
        variants = list(spec.get("variants", {})) or [""]
        for var in variants:
            tag = fid + (("_" + var.replace(" ", "")) if var else "")
            mat = bpy.data.materials.get("FR study " + tag) or bpy.data.materials.new("FR study " + tag)
            nodes = fp.build(mat, fid, var)
            shown, placed = stage(sc, fid, single, head, weld)
            if fid == "weld":
                base, web, bead = weld
                for ob in (base, web):
                    from mathutils import Vector
                    inv = ob.matrix_world.inverted()
                    a_w = bead.matrix_world @ Vector((-0.074, 0, 0))
                    b_w = bead.matrix_world @ Vector((0.074, 0, 0))
                    ob["fr_weld_a"] = list(inv @ a_w)
                    ob["fr_weld_b"] = list(inv @ b_w)
                bm = bpy.data.materials.get("FR study weld bead") or bpy.data.materials.new("FR study weld bead")
                fp.FINISHES["weld_bead"] = dict(fn=fp.weld_bead, base=dict(color=(0.3, 0.3, 0.3), metallic=1.0,
                                                                          roughness=0.35), pat=dict(ripple=0.0016))
                fp.build(bm, "weld_bead")
                assign([base, web], mat)
                assign([bead], bm)
            else:
                assign(shown, mat)
            row = times.setdefault(tag, {})
            row["nodes"] = nodes
            key0, M0, _s = placed[0]
            from mathutils import Vector
            tgt, dist = CLOSE[key0]
            if "close" in shots:
                camera(sc, M0 @ Vector(tgt), dist)
                row["close_s"] = render(sc, os.path.join(a.out, f"{tag}_close.png"), a.res, a.samples)
            if "product" in shots:
                frame_all(sc, shown)
                row["product_s"] = render(sc, os.path.join(a.out, f"{tag}_product.png"), a.res, a.samples)
            if a.eevee:
                frame_all(sc, shown)
                try:
                    row["eevee_s"] = render(sc, os.path.join(a.out, f"{tag}_eevee.png"), a.res, a.samples, "EEVEE")
                except Exception as exc:
                    row["eevee_s"] = f"failed: {exc}"
            if a.cost:
                frame_all(sc, shown)
                ck = "" if a.cost_res == 1920 else f"_{a.cost_res}"
                row["cost_pattern_s" + ck] = render(sc, os.path.join(a.out, f"cost_{tag}{ck}.png"), a.cost_res, 64)
                fp.build(mat, fid, var, pattern=False)
                row["cost_plain_s" + ck] = render(sc, os.path.join(a.out, f"cost_{tag}{ck}_plain.png"), a.cost_res, 64)
                fp.build(mat, fid, var)
            print(tag, json.dumps(row), flush=True)
            json.dump(times, open(times_path, "w"), indent=1)
    if a.copies:
        copies(sc, single, a.out, times, step)
    if a.far:
        far(sc, single, a.out, times)
    if a.headset:
        headset(sc, head, a.out, times)
    if a.thumbs:
        thumbs(sc, single, a.out, times, a.eevee)
    json.dump(times, open(times_path, "w"), indent=1)
    return 0


def copies(sc, single, out, times, step):
    """A knurled knob and a tread-plate block as imported, turned, scaled x1.5 and mirrored: the pattern must sit the
    same on every copy (scaled: it grows with the part). Then the same STEP imported again: the face data must be the
    same, number for number."""
    import bpy
    import numpy as np
    from mathutils import Matrix
    from fresing_render.blender import finishes_proto as fp
    _hide_all(sc)
    row = times.setdefault("_copies", {})
    mk = bpy.data.materials.get("FR study copies knurl") or bpy.data.materials.new("FR study copies knurl")
    fp.build(mk, "knurl_diamond")
    mt = bpy.data.materials.get("FR study copies tread") or bpy.data.materials.new("FR study copies tread")
    fp.build(mt, "scraped")
    obs = []
    looks = [("as imported", Matrix()), ("turned", Matrix.Rotation(math.radians(70), 4, "Z") @
                                         Matrix.Rotation(math.radians(180), 4, "X")),
             ("scaled 1.5", Matrix.Diagonal((1.5, 1.5, 1.5, 1))), ("mirrored", Matrix.Diagonal((-1, 1, 1, 1)))]
    for i, (name, M) in enumerate(looks):
        for src, mat, y in ((single["KNOB"], mk, 0.03), (single["BLOCK"], mt, -0.06)):
            ob = src.copy()
            ob.name = f"FR study copy {name} {src.data.name}"
            sc.collection.objects.link(ob)
            ob.parent = None
            lift = 0.0
            if name == "turned":
                lift = 0.015 * 1.0 if src is single["KNOB"] else 0.04
            sz = 1.5 if name == "scaled 1.5" else 1.0
            ob.matrix_world = Matrix.Translation(((i - 1.5) * 0.11, y, lift)) @ M
            ob.hide_render = ob.hide_viewport = False
            assign([ob], mat)
            obs.append(ob)
    bpy.context.view_layer.update()
    global AZ, EL
    az0, el0 = AZ, EL
    AZ, EL = math.radians(-20.0), math.radians(35.0)
    frame_all(sc, obs, 1.04)
    row["copies.png"] = render(sc, os.path.join(out, "copies.png"), 1920, 64)
    AZ, EL = az0, el0
    for ob in obs:
        ob.hide_render = ob.hide_viewport = True
    # a model update: the same file again -> the same face data
    before = {}
    for key in ("KNOB", "BUSHING", "CAP"):
        me = single[key].data
        before[key] = [np.array([v for d in me.attributes[n].data for v in (d.vector if n in ("fr_fx_o", "fr_fx_d")
                                                                          else (d.value,))]) for n in
                       ("fr_fx_o", "fr_fx_d", "fr_fx_r", "fr_fx_k")]
    n0 = set(bpy.data.meshes.keys())
    assert bpy.ops.fresing.import_step(filepath=step, quality="normal") == {"FINISHED"}
    same = {}
    for me in bpy.data.meshes:
        if me.name in n0:
            continue
        key = me.name.split(".")[0]
        if key in before:
            fp.prepare_faces(me)
            now = [np.array([v for d in me.attributes[n].data for v in (d.vector if n in ("fr_fx_o", "fr_fx_d")
                                                                       else (d.value,))]) for n in
                   ("fr_fx_o", "fr_fx_d", "fr_fx_r", "fr_fx_k")]
            same[key] = all(len(x) == len(y) and float(np.max(np.abs(x - y))) < 1e-7 for x, y in zip(before[key], now))
    row["reimport_same"] = same
    print("reimport same:", same, flush=True)


PLATES = ["tread", "perforated", "expanded", "antiskid", "hammertone", "spangle", "carbon", "shot_blasted",
          ("rust", "heavy"), "scraped", "perlage", "grille", ("vdi", "VDI 36"), "bead_blasted", "crosshatch", "fabric"]


def _hide_all(sc):
    for ob in sc.objects:
        if ob.type == "MESH" and not ob.name.startswith("FR Floor"):
            ob.hide_render = ob.hide_viewport = True


def far(sc, single, out, times):
    """The plate finishes side by side at 'whole machine' (4 m) and 'far' (15 m) distance, with and without the fade."""
    import bpy
    from mathutils import Matrix, Vector
    from fresing_render.blender import finishes_proto as fp
    _hide_all(sc)
    src = single["PLATE"]
    obs = []
    cols = 4
    for i, item in enumerate(PLATES):
        fid, var = (item if isinstance(item, tuple) else (item, ""))
        name = f"FR study plate {i}"
        ob = bpy.data.objects.get(name) or src.copy()
        if ob.name not in sc.collection.objects:
            ob.name = name
            sc.collection.objects.link(ob)
        ob.parent = None
        r, c = divmod(i, cols)
        ob.matrix_world = Matrix.Translation(((c - 1.5) * 0.34, (1.5 - r) * 0.34, 0)) @ \
            Matrix.Translation((0.15, 0.15, 0))      # the plate's corner is its origin? keep its box centred below
        lo = Vector(map(min, *[Vector(v) for v in src.bound_box]))
        hi = Vector(map(max, *[Vector(v) for v in src.bound_box]))
        ob.matrix_world = Matrix.Translation(((c - 1.5) * 0.34, (1.5 - r) * 0.34, 0)) @ \
            Matrix.Translation(-(lo + hi) / 2 + Vector((0, 0, (hi.z - lo.z) / 2)))
        ob.hide_render = ob.hide_viewport = False
        tag = fid + (("_" + var.replace(" ", "")) if var else "")
        mat = bpy.data.materials.get("FR study " + tag) or bpy.data.materials.new("FR study " + tag)
        fp.build(mat, fid, var)
        assign([ob], mat)
        obs.append(ob)
    bpy.context.view_layer.update()
    c = Vector((0, 0, 0))
    row = times.setdefault("_far", {})
    for dist, tag in ((4.0, "machine"), (15.0, "far")):
        for fade in (True, False):
            camera(sc, c, dist)
            nm = f"far_{tag}{'' if fade else '_nofade'}.png"
            row[nm] = render(sc, os.path.join(out, nm), 1920, 64, pixel=fade)
            print(nm, row[nm], flush=True)
    for ob in obs:
        ob.hide_render = ob.hide_viewport = True


HEAD = {"KNOB": ("knurl_diamond", ""), "CAP": ("spun", ""), "CUP": ("crosshatch", ""), "BAND": ("soft_touch", ""),
        "YOKE": ("bead_blasted", ""), "CUSHION": ("leather", ""), "GRILLE": ("fabric", "")}


def headset(sc, head, out, times):
    import bpy
    from mathutils import Matrix, Vector
    from fresing_render.blender import finishes_proto as fp
    _hide_all(sc)
    mats = {}
    for ob in head:
        key = ob.data.name.split(".")[0]
        fid, var = HEAD.get(key, ("soft_touch", ""))
        if key not in mats:
            m = bpy.data.materials.get("FR study head " + key) or bpy.data.materials.new("FR study head " + key)
            fp.build(m, fid, var)
            mats[key] = m
        assign([ob], mats[key])
        ob.hide_render = ob.hide_viewport = False
    # stand it up on the floor: the model root sits wherever the import put it
    root = head[0]
    while root.parent is not None and root.parent.name.startswith("HEADSET") is False and root.parent.parent:
        root = root.parent
    pts = [ob.matrix_world @ Vector(c) for ob in head for c in ob.bound_box]
    lo = Vector(map(min, *pts))
    hs = next(o for o in bpy.data.objects if o.name.startswith("HEADSET"))
    hs.matrix_world = Matrix.Translation((0, 0, -lo.z)) @ hs.matrix_world
    bpy.context.view_layer.update()
    row = times.setdefault("_headset", {})
    global AZ, EL
    az0, el0 = AZ, EL
    AZ, EL = math.radians(38.0), math.radians(12.0)          # from the front right: the knob's side
    frame_all(sc, head, 1.02)
    row["headset.png"] = render(sc, os.path.join(out, "headset.png"), 1920, 96)
    knob = next(ob for ob in head if ob.data.name.startswith("KNOB"))
    cup = next(ob for ob in head if ob.data.name.startswith("CUP") and (ob.matrix_world.translation - knob.matrix_world.translation).length < 0.05)
    AZ, EL = math.radians(62.0), math.radians(16.0)
    camera(sc, knob.matrix_world.translation + Vector((-0.006, 0, -0.012)), 0.13)
    row["headset_close.png"] = render(sc, os.path.join(out, "headset_close.png"), 1920, 96)
    AZ, EL = az0, el0


def thumbs(sc, single, out, times, eevee=False):
    """Material picker swatch (0273): a block with a knurled knob on it and a spun cap leaning in front, 256 px."""
    import bpy
    from mathutils import Matrix, Vector
    from fresing_render.blender import finishes_proto as fp
    _hide_all(sc)
    blk, knob, cap = single["BLOCK"], single["KNOB"], single["CAP"]
    blk.parent = knob.parent = cap.parent = None
    blk.matrix_world = Matrix.Rotation(math.radians(24), 4, "Z") @ Matrix.Translation((0, 0, 0))
    knob.matrix_world = Matrix.Translation((0.012, 0.004, 0.040))
    cap.matrix_world = Matrix.Translation((0.035, -0.05, 0.0)) @ Matrix.Rotation(math.radians(-20), 4, "Z") @ \
        Matrix.Rotation(math.radians(58), 4, "X")
    for ob in (blk, knob, cap):
        ob.hide_render = ob.hide_viewport = False
    bpy.context.view_layer.update()
    row = times.setdefault("_thumbs", {})
    bpy.context.view_layer.update()
    zmin = min((cap.matrix_world @ Vector(c)).z for c in cap.bound_box)
    cap.matrix_world = Matrix.Translation((0, 0, -zmin)) @ cap.matrix_world
    for fid in ("plain", "knurl_diamond", "spun", "perforated", "carbon", "hammertone", "crosshatch", "rust"):
        m = bpy.data.materials.get("FR study thumb") or bpy.data.materials.new("FR study thumb")
        if fid == "plain":
            fp.build(m, "knurl_diamond", pattern=False)
        else:
            fp.build(m, fid, "heavy" if fid == "rust" else "")
        assign([blk, knob, cap], m)
        frame_all(sc, [blk, knob, cap], 1.04, 1.0)
        for smp in (16, 32):
            t0 = time.time()
            row[f"{fid}_{smp}"] = render(sc, os.path.join(out, f"thumb_{fid}_{smp}.png"), 256, smp, square=True)
            row[f"{fid}_{smp}_wall"] = round(time.time() - t0, 2)
        if eevee:
            try:
                row[f"{fid}_eevee"] = render(sc, os.path.join(out, f"thumb_{fid}_eevee.png"), 256, 16, "EEVEE", True)
            except Exception as exc:
                row[f"{fid}_eevee"] = f"failed: {exc}"
        print("thumb", fid, {k: v for k, v in row.items() if k.startswith(fid)}, flush=True)


if __name__ == "__main__":
    sys.exit(main())
