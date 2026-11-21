"""Task 0258 (throw-away): line-up pictures – test models beside a 1.75 m person and one real-size prop, today (top row)
and at the proposed size (bottom row), front view, orthographic, same scale for both rows.

~/venv/bin/python study0258/lineup.py <out.png> <prop kind> <title> <cache dir>:<label>:<factor> ...
(cache dir = an importer cache, made by ``python -m fresing_render.importer.step_reader <step> <dir>``)
"""
import json
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Matrix, Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from fresing_render.core import props_detail  # noqa: E402

out, prop_kind, title = sys.argv[1], sys.argv[2], sys.argv[3]
items = [a.split(":") for a in sys.argv[4:]]

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
_mats = {}


def mat(rgb):
    key = tuple(round(c, 3) for c in rgb)
    if key not in _mats:
        m = bpy.data.materials.new(f"m{len(_mats)}")
        m.use_nodes = True
        bsdf = m.node_tree.nodes["Principled BSDF"]
        lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in key]
        bsdf.inputs["Base Color"].default_value = (*lin, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.55
        _mats[key] = m
    return _mats[key]


def mesh_obj(name, pts, tris, rgb, matrix=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(p) for p in pts], [], [tuple(t) for t in tris])
    me.materials.append(mat(rgb))
    ob = bpy.data.objects.new(name, me)
    sc.collection.objects.link(ob)
    if matrix is not None:
        ob.matrix_world = matrix
    return ob


def load_model(cache):
    if cache.endswith(".glb"):
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=cache)
        new = list(set(bpy.data.objects) - before)
        bpy.context.view_layer.update()
        for o in new:
            w = o.matrix_world.copy()
            o.parent = None
            o.matrix_world = w
        return [o for o in new if o.type == "MESH"]
    tree = json.load(open(os.path.join(cache, "tree.json")))
    z = np.load(os.path.join(cache, "meshes.npz"))
    nodes = tree["nodes"]
    world = []
    obs = []
    for i, n in enumerate(nodes):
        m = Matrix(n["matrix"]) if n.get("matrix") else Matrix.Identity(4)
        w = world[n["parent"]] @ m if n["parent"] >= 0 else m
        world.append(w)
        if n["kind"] == "part" and n["mesh"] >= 0:
            col = n.get("color") or n.get("inherited_color") or (0.6, 0.6, 0.62)
            k = n["mesh"]
            obs.append(mesh_obj(n["name"], z[f"p{k}"], z[f"t{k}"], col, w))
    return obs


def shapes_obj(name, shapes, rgb):
    from fresing_render.blender import surroundings as BS
    m = BS._Mesh()
    for sh in shapes:
        m.shape(sh, 0)
    me = m.to_mesh(name)
    me.materials.append(mat(rgb))
    ob = bpy.data.objects.new(name, me)
    sc.collection.objects.link(ob)
    return ob


def box_of(obs):
    bpy.context.view_layer.update()
    pts = [ob.matrix_world @ Vector(c) for ob in obs for c in ob.bound_box]
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    return lo, hi


def place(obs, x, z0, k):
    """Scale the group by k about its box's lower-left-front corner, put it at x, standing on z0, centred on y."""
    lo, hi = box_of(obs)
    pivot = Vector((lo.x, (lo.y + hi.y) / 2, lo.z))
    T = Matrix.Translation(Vector((x, 0.0, z0))) @ Matrix.Scale(k, 4) @ Matrix.Translation(-pivot)
    for ob in obs:
        ob.matrix_world = T @ ob.matrix_world
    bpy.context.view_layer.update()
    return box_of(obs)


def label(text, x, z, size, align="CENTER"):
    cu = bpy.data.curves.new("t", "FONT")
    cu.body = text
    cu.size = size
    cu.align_x = align
    ob = bpy.data.objects.new("label", cu)
    sc.collection.objects.link(ob)
    ob.location = (x, -5.0, z)
    ob.rotation_euler = (math.pi / 2, 0, 0)
    ob.data.materials.append(mat((0.12, 0.12, 0.12)))
    return ob


def row(z0, proposed, slots=None):
    """One row; ``slots`` = the x where each item starts (the proposed row's, so the columns line up)."""
    x = 0.0
    tops = []
    person = shapes_obj("person", props_detail.model("PERSON", "DETAILED", height=1.75), (0.95, 0.45, 0.1))
    lo, hi = place([person], x, z0, 1.0)
    tops.append(hi.z)
    x = hi.x + 0.6
    if prop_kind != "NONE":
        p = shapes_obj(prop_kind, props_detail.model(prop_kind, "DETAILED"), (0.55, 0.6, 0.68))
        lo, hi = place([p], x, z0, 1.0)
        tops.append(hi.z)
        x = hi.x + 0.8
    marks, starts = [], []
    for i, (cache, name, factor) in enumerate(items):
        k = float(factor) if proposed else 1.0
        if slots is not None:
            x = slots[i]
        starts.append(x)
        obs = load_model(os.path.expanduser(cache))
        lo, hi = place(obs, x, z0, k)
        tops.append(hi.z)
        size = hi - lo
        marks.append(((lo.x + hi.x) / 2, f"{name}{' x' + factor if proposed and k != 1 else ''}\n"
                      f"{size.x:.1f} x {size.y:.1f} x {size.z:.1f} m"))
        x = hi.x + max(1.0, 0.15 * size.x)
    return x, max(tops), marks, starts


one_row = all(float(f) == 1.0 for _, _, f in items)
if one_row:
    W, t2, m2, slots = row(0.0, False)
    t1, m1 = t2, m2
    rows = [(0.0, t1, m2, "today = proposed")]
else:
    W, t2, m2, slots = row(0.0, True)
    moved = set(sc.objects)
    fs0 = 0.016 * W
    z_low = -(t2 + 7.5 * fs0)          # room for the labels under the upper row
    for ob in moved:
        ob.location.z += z_low
    w1, t1, m1, _ = row(0.0, False, slots)
    rows = [(0.0, t1, m1, "today"), (z_low, t2, m2, "proposed")]
fs = max(0.15, 0.016 * W)
for z, top, marks, name in rows:
    for i, (xx, tx) in enumerate(marks):
        label(tx, xx, z - (1.2 + 2.4 * (i % 2)) * fs, fs)
    label(name, -0.4, z + 0.3, fs * 1.3, "RIGHT")
    f = mesh_obj("floor", [(-3, -3, z), (W + 1, -3, z), (W + 1, 3, z), (-3, 3, z)], [(0, 1, 2), (0, 2, 3)],
                 (0.35, 0.35, 0.35))
    f.location.z -= 0.01
label(title, W / 2, t1 + 1.5 * fs, fs * 1.6)
z_bottom = rows[-1][0] - 5.0 * fs

# camera: orthographic front view
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
sc.collection.objects.link(cam)
cam.data.type = "ORTHO"
x0, x1 = -0.6 - 12 * fs, W + 1.0
z0, z1 = z_bottom, t1 + 3.5 * fs
cam.data.ortho_scale = max(x1 - x0, z1 - z0)
cam.location = ((x0 + x1) / 2, -60.0, (z0 + z1) / 2)
cam.rotation_euler = (math.pi / 2, 0, 0)
cam.data.clip_end = 200
sc.camera = cam
r = sc.render
r.resolution_x = 800
r.resolution_y = max(240, min(800, int(800 * (z1 - z0) / (x1 - x0))))
if (x1 - x0) < (z1 - z0):
    r.resolution_x = int(r.resolution_y * (x1 - x0) / (z1 - z0))
r.engine = "CYCLES"
sc.cycles.samples = 24
sc.cycles.use_denoising = False
sc.cycles.device = "CPU"
world = bpy.data.worlds.new("w")
sc.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (1, 1, 1, 1)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.9
sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
sun.data.energy = 3.0
sun.rotation_euler = (math.radians(50), 0, math.radians(-30))
sc.collection.objects.link(sun)
sc.view_settings.view_transform = "Standard"
r.filepath = out
bpy.ops.render.render(write_still=True)
print("WROTE", out, r.resolution_x, r.resolution_y)
