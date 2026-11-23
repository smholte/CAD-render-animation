"""Study 0303: the look sheet – today's person, the low-poly mannequin and the realistic body, side by side, at three
camera distances, a walk clip, and per look: triangles, render time, file size.

Run with the bpy module (web machine): ``HBM=<folder with W_male.npz …> ~/venv/bin/python render_sheet.py <out dir>``
(``--quick``: small pictures, few samples, for trying). Every look stands on the same 17-bone rig: the walk comes from
``core/people.plan`` exactly as the app's Build makes it, and each look's armature gets the same pose per frame.
"""

from __future__ import annotations

import json
import math
import os
import sys
import time

import bpy
import bmesh
import numpy as np
from mathutils import Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", ".."))

from fresing_render.blender import person_rig as PR          # noqa: E402
from fresing_render.blender import props_scale as PS         # noqa: E402
from fresing_render.blender import surroundings as SUR       # noqa: E402
from fresing_render.core import people as PE                 # noqa: E402
from fresing_render.core import person_rig as R              # noqa: E402
from fresing_render.core import props_detail as P            # noqa: E402

import lowpoly as LP        # noqa: E402
import realistic as RL      # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "/tmp/sheet"
QUICK = "--quick" in sys.argv
HBM = os.environ.get("HBM", "")
os.makedirs(OUT, exist_ok=True)

LP_COLOURS = {"lp_navy": (0.13, 0.17, 0.27), "lp_orange": (0.95, 0.4, 0.07), "lp_trousers": (0.2, 0.2, 0.22),
              "lp_hivis": (0.85, 0.95, 0.1), "lp_skin": (0.78, 0.62, 0.5), "lp_boots": (0.05, 0.05, 0.055),
              "lp_helmet_white": (0.92, 0.92, 0.9), "lp_helmet_yellow": (0.98, 0.78, 0.06),
              "lp_plain": (0.72, 0.7, 0.66)}


def lin(c):
    return tuple(((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c)


def simple_mat(name, rgb, rough=0.6, emit=0.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*lin(rgb), 1.0)
    b.inputs["Roughness"].default_value = rough
    if emit:
        b.inputs["Emission Color"].default_value = (*lin(rgb), 1.0)
        b.inputs["Emission Strength"].default_value = emit
    return m


def mat_of(key):
    if key in LP_COLOURS:
        return simple_mat(key, LP_COLOURS[key], 0.55)
    if key == "rl_sclera":
        return simple_mat(key, (0.85, 0.83, 0.8), 0.15)
    if key == "rl_iris":
        return simple_mat(key, (0.12, 0.08, 0.05), 0.1)
    return PS.material(key)


# ---------------------------------------------------------------------------
# the three looks as (mesh, weights)
# ---------------------------------------------------------------------------


def mesh_from(name, verts, polys, mats, names, smooth):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(map(float, v)) for v in verts], [], [tuple(p) for p in polys])
    for k in names:
        me.materials.append(mat_of(k))
    me.polygons.foreach_set("material_index", np.asarray(mats, np.int32))
    me.polygons.foreach_set("use_smooth", np.full(len(polys), bool(smooth)))
    me.update()
    return me


def today(lod, outfit="OFFSHORE", height=1.75):
    settings = dict(P.PERSON_DEFAULTS, height=height, outfit=outfit, helmet=True)
    m, lods, _mats, W, _verts, _keys = PR._arrays(settings)
    me = PR.make_mesh(f"today {lod}", settings)
    keep = 1 if lod == "DETAILED" else 2
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[f for f, lv in zip(bm.faces, lods) if lv != keep], context="FACES")
    used = np.zeros(len(W), bool)
    for v in bm.verts:
        if v.link_faces:
            used[v.index] = True
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bm.to_mesh(me)
    bm.free()
    return me, W[used], R.Figure(height)


def lowpoly(outfit="OFFSHORE", height=1.75, plain=False):
    d = LP.mannequin(height, outfit, True, plain)
    me = mesh_from("low poly", d["verts"], d["faces"], d["mat"], d["materials"], smooth=False)
    return me, d["W"], R.Figure(height)


def realistic(body="male", outfit="OFFSHORE", skin="skin_2", level=0):
    w = np.load(os.path.join(HBM, f"rest_{body}.npz"))
    rest, W = w["rest"], w["W"]
    src = np.load(os.path.join(HBM, f"GEO-body_{body}_realistic_L0.npz"))
    polys = RL.polys_of(src)
    fig = R.Figure(float(np.load(os.path.join(HBM, f"W_{body}.npz"))["co"][:, 2].max()))
    bi = R.BONES.index("head")
    # the face without the scan's likeness: smoothed in front of the head
    hh, _Rh, ht = fig.rest_fk["head"]
    nb = RL.neighbours(len(rest), polys)
    face = (W[:, bi] > 0.5) & (rest[:, 1] < hh[1] - 0.035) & (rest[:, 2] > hh[2] + 0.02) & (rest[:, 2] < ht[2] - 0.05)
    rest = RL.smooth(rest, face, nb, rounds=6, amount=0.5)
    pts, mats, names = RL.dress(rest, polys, W, fig, outfit, skin, nb)
    verts, faces, fmat, Wl = [pts], list(polys), list(mats), [W]
    n0 = len(pts)
    # eyes (rigid on the head)
    oneh = np.zeros(len(R.BONES))
    oneh[bi] = 1.0
    raw = np.load(os.path.join(HBM, f"W_{body}.npz"))["co"]
    shift = np.array((np.load(os.path.join(HBM, f"GEO-body_{body}_realistic_L0.npz"))["co"][:, 0].mean(), 0, 0))
    for side in "LR":
        e = np.load(os.path.join(HBM, f"GEO-body_{body}_realistic.eye.{side}.npz"))
        co = e["co"] - shift
        ec = RL.to_rest(co, np.tile(oneh, (len(co), 1)), body, fig)
        cen = ec.mean(axis=0)
        ep = RL.polys_of(e)
        for nm in ("rl_sclera", "rl_iris"):
            if nm not in names:
                names.append(nm)
        for p in ep:
            c = ec[list(p)].mean(axis=0)
            faces.append(tuple(i + n0 for i in p))
            fmat.append(names.index("rl_iris" if c[1] < cen[1] - 0.009 else "rl_sclera"))
        verts.append(ec)
        Wl.append(np.tile(oneh, (len(ec), 1)))
        n0 += len(ec)
    # the hard hat
    top = rest[W[:, bi] > 0.5]
    hat = RL.hard_hat(fig, RL.OUTFITS[outfit]["hat"], float(top[:, 2].max()), top.mean(axis=0))
    m = SUR._Mesh()
    hk = RL.OUTFITS[outfit]["hat"]
    if hk not in names:
        names.append(hk)
    for sh in hat:
        m.shape(sh, names.index(hk))
    hv = np.concatenate(m.verts)
    for f in m.faces:
        ff = f if not isinstance(f, np.ndarray) else None
        if ff is None:
            for row in f:
                faces.append(tuple(int(i) + n0 for i in row))
                fmat.append(names.index(hk))
        else:
            faces.append(tuple(int(i) + n0 for i in ff))
            fmat.append(names.index(hk))
    verts.append(hv)
    Wl.append(np.tile(oneh, (len(hv), 1)))
    me = mesh_from(f"realistic {body}", np.concatenate(verts), faces, fmat, names, smooth=True)
    return me, np.concatenate(Wl), fig


# ---------------------------------------------------------------------------
# objects, armatures, poses
# ---------------------------------------------------------------------------


def person_object(name, me, W, fig, subsurf=0):
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    for j, b in enumerate(R.BONES):
        vg = ob.vertex_groups.new(name=b)
        col = W[:, j]
        idx = np.nonzero(col > 1e-4)[0]
        vals = np.round(col[idx], 3)
        for v in np.unique(vals):
            vg.add([int(i) for i in idx[vals == v]], float(v), "REPLACE")
    ad = bpy.data.armatures.new("rig " + name)
    arm = bpy.data.objects.new("rig " + name, ad)
    bpy.context.scene.collection.objects.link(arm)
    arm.parent = ob
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    for b in R.BONES:
        head, B, ln = fig.rest_matrix(b)
        e = ad.edit_bones.new(b)
        e.head = tuple(head)
        e.tail = tuple(head + B[:, 1] * ln)
        e.align_roll(tuple(B[:, 2]))
    for b in R.BONES:
        if R.PARENT[b]:
            ad.edit_bones[b].parent = ad.edit_bones[R.PARENT[b]]
    bpy.ops.object.mode_set(mode="OBJECT")
    for pb in arm.pose.bones:
        pb.rotation_mode = "QUATERNION"
    mod = ob.modifiers.new("rig", "ARMATURE")
    mod.object = arm
    if subsurf:
        s = ob.modifiers.new("smooth", "SUBSURF")
        s.levels, s.render_levels = 0, subsurf
    arm.hide_render = True
    ob["fig_h"] = fig.height
    return ob, arm


def set_pose(arm, fig, pose):
    for b in R.BONES:
        arm.pose.bones[b].rotation_quaternion = fig.blender_quaternion(pose, b)
    arm.pose.bones["pelvis"].location = fig.blender_location(pose)


# ---------------------------------------------------------------------------
# scene
# ---------------------------------------------------------------------------


def stage():
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 16 if QUICK else 64
    sc.cycles.use_denoising = True
    sc.render.film_transparent = False
    sc.view_settings.view_transform = "AgX"
    w = bpy.data.worlds.new("w")
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.55, 0.62, 0.72, 1)
    bg.inputs[1].default_value = 0.9
    sc.world = w
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sun.data.energy = 3.2
    sun.data.angle = math.radians(3)
    sun.rotation_euler = (math.radians(50), 0, math.radians(-35))
    sc.collection.objects.link(sun)
    bpy.ops.mesh.primitive_plane_add(size=400)
    fl = bpy.context.active_object
    fl.data.materials.append(simple_mat("floor", (0.55, 0.55, 0.53), 0.8))
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    cam.data.lens = 50
    sc.collection.objects.link(cam)
    sc.camera = cam
    return sc, cam


def aim(cam, eye, target):
    from mathutils import Vector
    d = Vector(target) - Vector(eye)
    cam.location = eye
    cam.rotation_mode = "QUATERNION"
    cam.rotation_quaternion = d.to_track_quat("-Z", "Y")


def tris(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    me.calc_loop_triangles()
    n = len(me.loop_triangles)
    ev.to_mesh_clear()
    return n


def render(path, w, h):
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.resolution_percentage = 100
    sc.render.filepath = path
    t = time.perf_counter()
    bpy.ops.render.render(write_still=True)
    return time.perf_counter() - t


def crowd(kind, n=40):
    """``n`` people of one look in a block 8 x 5 at 1.4 m, the camera 25 m away: render time and memory."""
    import resource
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc, cam = stage()
    t0 = time.perf_counter()
    if kind == "none":
        n = 0
    for i in range(n):
        me, W, fig = {"today": lambda: today("DETAILED"), "today_light": lambda: today("LIGHT"),
                      "lowpoly": lowpoly, "realistic": lambda: realistic("male"),
                      "realistic0": lambda: realistic("male")}[kind]()
        ob, arm = person_object(f"p{i}", me, W, fig, subsurf=1 if kind == "realistic" else 0)
        set_pose(arm, fig, fig.from_angles(("STANDING", "WALKING", "POINTING", "PANEL")[i % 4]))
        ob.location = ((i % 8 - 3.5) * 1.4, (i // 8) * 1.4, 0.0)
        ob.rotation_euler.z = 0.3 * i
    made = time.perf_counter() - t0
    aim(cam, (6.0, -24.0, 6.0), (0.0, 3.0, 0.9))
    render(os.path.join(OUT, f"crowd_{kind}.png"), 64, 36)
    t = render(os.path.join(OUT, f"crowd_{kind}.png"), 960, 540)
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    row = dict(people=n, make_s=round(made, 1), render_s=round(t, 1), peak_mb=round(rss))
    print("CROWD", kind, row, flush=True)
    with open(os.path.join(OUT, f"crowd_{kind}.json"), "w") as f:
        json.dump(row, f)


def variety():
    """Body, skin and clothes variety of the realistic route, and the two low-poly looks."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc, cam = stage()
    rows = (("realistic", dict(body="male", outfit="OFFICE", skin="skin_1")),
            ("realistic", dict(body="female", outfit="WORKSHOP", skin="skin_3")),
            ("realistic", dict(body="male", outfit="OFFSHORE", skin="skin_4")),
            ("realistic", dict(body="female", outfit="OFFSHORE", skin="skin_2")),
            ("lowpoly", dict(outfit="WORKSHOP")), ("lowpoly", dict(outfit="OFFICE")), ("lowpoly", dict(plain=True)))
    for i, (kind, kw) in enumerate(rows):
        me, W, fig = (realistic if kind == "realistic" else lowpoly)(**kw)
        ob, arm = person_object(f"v{i}", me, W, fig, subsurf=1 if kind == "realistic" else 0)
        set_pose(arm, fig, fig.from_angles(("STANDING", "PANEL", "POINTING", "STANDING", "WALKING", "OPERATOR",
                                            "STANDING")[i]))
        ob.location = ((i - 3) * 0.95, 0.0, 0.0)
        ob.rotation_euler.z = math.radians(-12)
    aim(cam, (0.0, -9.4, 1.5), (0.0, 0.0, 0.88))
    render(os.path.join(OUT, "variety.png"), *((480, 220) if QUICK else (1600, 720)))


def main():
    if "--crowd" in sys.argv:
        crowd(sys.argv[sys.argv.index("--crowd") + 1])
        return
    if "--variety" in sys.argv:
        variety()
        return
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc, cam = stage()
    looks = {}
    # today: both levels (the app keeps one by the camera distance: light beyond 30 m)
    me, W, fig = today("DETAILED")
    looks["today"] = person_object("today", me, W, fig)
    me, W, fig = today("LIGHT")
    looks["today_light"] = person_object("today light", me, W, fig)
    me, W, fig = lowpoly()
    looks["lowpoly"] = person_object("low poly", me, W, fig)
    me, W, fig = realistic("male")
    looks["realistic"] = person_object("realistic", me, W, fig, subsurf=1)
    figs = {k: R.Figure(ob["fig_h"]) for k, (ob, _a) in looks.items()}
    rest = {k: figs[k].from_angles("STANDING") for k in looks}
    for k, (ob, arm) in looks.items():
        set_pose(arm, figs[k], rest[k])
    xs = {"today": -1.1, "today_light": -1.1, "lowpoly": 0.0, "realistic": 1.1}
    for k, (ob, _a) in looks.items():
        ob.location = (xs[k], 0.0, 0.0)
        ob.rotation_euler.z = math.radians(-15)
    info = {}
    # 1. per look alone, close: triangles, render time, file size
    W1, H1 = (320, 400) if QUICK else (640, 800)
    for k, (ob, _a) in looks.items():
        for o, _ in looks.values():
            o.hide_render = o is not ob
        aim(cam, (ob.location.x, -3.2, 1.25), (ob.location.x, 0, 0.95))
        render(os.path.join(OUT, f"_warm_{k}.png"), 64, 80)       # first render pays for the kernels
        t = render(os.path.join(OUT, f"close_{k}.png"), W1, H1)
        bpy.data.libraries.write(os.path.join(OUT, f"_{k}.blend"), {ob, ob.data, _a, _a.data}, compress=True)
        info[k] = dict(triangles=tris(ob), base_triangles=sum(len(p.vertices) - 2 for p in ob.data.polygons),
                       render_s=round(t, 2), blend_mb=round(os.path.getsize(os.path.join(OUT, f"_{k}.blend")) / 1e6, 3))
        print(k, info[k], flush=True)
    # 2. side by side at three distances (today switches to its light level beyond 30 m, as in the app)
    W2, H2 = (480, 270) if QUICK else (1280, 720)
    for dist in (5.0, 15.0, 45.0):
        far = dist > 30
        looks["today"][0].hide_render = far
        looks["today_light"][0].hide_render = not far
        looks["lowpoly"][0].hide_render = False
        looks["realistic"][0].hide_render = False
        aim(cam, (0.0, -dist, 1.5 + dist * 0.03), (0.0, 0.0, 0.9))
        t = render(os.path.join(OUT, f"row_{int(dist)}m.png"), W2, H2)
        info[f"row_{int(dist)}m_s"] = round(t, 1)
    with open(os.path.join(OUT, "numbers.json"), "w") as f:
        json.dump(info, f, indent=1)
    if "--no-walk" in sys.argv:
        return
    # 3. the walk clip: three people walk the same gait side by side (core/people's plan, 25 fps)
    fps = 25
    specs = []
    order = ("today", "lowpoly", "realistic")
    for i, k in enumerate(order):
        x = (i - 1) * 1.2
        specs.append(PE.PersonSpec(k, figs[k].height, (x, 3.0, 0.0), math.pi, path=((x, -2.5),),
                                   actions=(PE.Action("WALK", "END", gait="WALK"),)))
    pl = PE.plan(specs, [])
    rows = pl.sample(fps)
    n = min(len(r) for r in rows.values())
    looks["today_light"][0].hide_render = True
    looks["today"][0].hide_render = False
    aim(cam, (4.2, -5.2, 1.7), (0.0, 0.0, 0.9))
    W3, H3 = (320, 180) if QUICK else (800, 450)
    sc.cycles.samples = 8 if QUICK else 24
    step = 3 if QUICK else 1
    times = []
    os.makedirs(os.path.join(OUT, "walk"), exist_ok=True)
    for f in range(0, n, step):
        for k in order:
            ob, arm = looks[k]
            root, pose = rows[k][f]
            ob.location = root[:3]
            ob.rotation_euler.z = root[3]
            set_pose(arm, figs[k], pose)
        times.append(render(os.path.join(OUT, "walk", f"{f:04d}.png"), W3, H3))
    info["walk_frames"] = len(times)
    info["walk_frame_s"] = round(float(np.mean(times)), 2)
    with open(os.path.join(OUT, "numbers.json"), "w") as f:
        json.dump(info, f, indent=1)


main()
