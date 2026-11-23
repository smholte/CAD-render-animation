"""Study 0306 – the prototype in Blender (as a Python module): import an invented vehicle with the app, put it on a
ground with a speed bump and an off-road stretch, solve the ride, key every part, measure, render a few frames.

    ~/venv/bin/python tasks/0306_proto/blender_bake.py <out_dir> <car|truck> [--render] [--frames 12,40,...]

Measures (printed and written to <out_dir>/bake_<vehicle>.json):
  * rays straight down onto the ground mesh with ``scene.ray_cast`` (what people.py's ground does) vs the height grid
  * turning the ground mesh into a height grid for the strip the vehicle drives through (rays on a 5 cm grid)
  * the ride solve, the mechanism solve per frame, writing the keys
The keys here are object keys per part (a prototype shortcut); the app would key joints (section "Rig" of the page).
"""

from __future__ import annotations

import json
import math
import os
import sys
import time

import bpy
import addon_utils
import numpy as np
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for p in (ROOT, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

import fresing_render                       # noqa: E402
from fresing_render.core import linkages as LK   # noqa: E402
import ground as G                          # noqa: E402
import kin as K                             # noqa: E402
import ride as R                            # noqa: E402
from spec import VEHICLES                   # noqa: E402

out_dir = sys.argv[1]
which = sys.argv[2]
do_render = "--render" in sys.argv
frames_arg = [int(x) for x in sys.argv[sys.argv.index("--frames") + 1].split(",")] if "--frames" in sys.argv else None
os.makedirs(out_dir, exist_ok=True)
veh = VEHICLES[which]
share = 0.55 if which == "car" else 0.35
M = {}

bpy.ops.wm.read_factory_settings(use_empty=True)
addon_utils.enable("cycles", default_set=True)
fresing_render.register()
sc = bpy.context.scene
sc.fresing.out_folder = out_dir
step_file = os.path.join(out_dir, f"test_{which}.step")
t0 = time.perf_counter()
assert bpy.ops.fresing.import_step(filepath=step_file, quality="draft") == {"FINISHED"}
bpy.context.view_layer.update()
M["import_s"] = round(time.perf_counter() - t0, 2)
parts = [o for o in sc.objects if o.type == "MESH" and "Floor" not in o.name]
byname = {o.get("fr_name", o.name): o for o in parts}
print("parts", len(parts), sorted(byname)[:6])
cad = {o.name: o.matrix_world.copy() for o in parts}
bb = np.array([[o.matrix_world @ Vector(c) for c in o.bound_box] for o in parts]).reshape(-1, 3)
print("model box (m)", bb.min(0).round(3), bb.max(0).round(3))

# ---------------------------------------------------------------- ground: flat, a speed bump, then off-road
g = G.flat(-15.0, -8.0, 95.0, 8.0, 0.05)
g = G.speed_bump(g, 18.0, 0.075, 3.7, "sine")
g = G.offroad(g, seed=4, roughness=0.10, x_from=38.0)
ni, nj = g.z.shape
step = 2                                                   # the shown mesh every 10 cm
xs = g.x0 + np.arange(0, ni, step) * g.step
ys = g.y0 + np.arange(0, nj, step) * g.step
Z = g.z[::step, ::step]
X, Y = np.meshgrid(xs, ys, indexing="ij")
verts = np.column_stack([X.ravel(), Y.ravel(), Z.ravel()])
a, b = len(xs), len(ys)
ii, jj = np.meshgrid(np.arange(a - 1), np.arange(b - 1), indexing="ij")
v0 = (ii * b + jj).ravel()
faces = np.column_stack([v0, v0 + b, v0 + b + 1, v0 + 1])
me = bpy.data.meshes.new("Ground")
me.vertices.add(len(verts))
me.vertices.foreach_set("co", verts.astype(np.float32).ravel())
me.loops.add(faces.size)
me.loops.foreach_set("vertex_index", faces.astype(np.int32).ravel())
me.polygons.add(len(faces))
me.polygons.foreach_set("loop_start", (np.arange(len(faces)) * 4).astype(np.int32))
me.update()
gob = bpy.data.objects.new("Ground", me)
sc.collection.objects.link(gob)
mat = bpy.data.materials.new("Ground")
mat.use_nodes = True
bsdf = mat.node_tree.nodes.get("Principled BSDF")
bsdf.inputs["Base Color"].default_value = (0.32, 0.29, 0.25, 1)
bsdf.inputs["Roughness"].default_value = 0.95
me.materials.append(mat)
for p in me.polygons:
    p.use_smooth = True
bpy.context.view_layer.update()
M["ground_triangles"] = 2 * len(faces)

# ---------------------------------------------------------------- measure: rays vs the grid
for o in sc.objects:                                       # rays see only the ground (the app's floor and the vehicle
    if o is not gob and o.type == "MESH":                  # are hidden here; the app skips them by tag, as people.py)
        o.hide_viewport = True
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
rng = np.random.default_rng(1)
pts = np.column_stack([rng.uniform(5, 80, 4000), rng.uniform(-3, 3, 4000)])
t0 = time.perf_counter()
zr = []
for x, y in pts:
    ok, loc, *_ = sc.ray_cast(dg, Vector((x, y, 5.0)), Vector((0, 0, -1)), distance=20.0)
    zr.append(loc.z if ok else 0.0)
t_ray = (time.perf_counter() - t0) / len(pts)
t0 = time.perf_counter()
zg = g.height(pts[:, 0], pts[:, 1])
t_grid = (time.perf_counter() - t0) / len(pts)
M["ray_cast_us_per_ray"] = round(t_ray * 1e6, 1)
M["grid_us_per_point"] = round(t_grid * 1e6, 3)
M["ray_vs_grid_max_mm"] = round(float(np.abs(np.array(zr) - zg).max() * 1000), 1)
for o in sc.objects:
    if o.type == "MESH" and o is not gob:
        o.hide_viewport = False
for o in sc.objects:
    if "Floor" in o.name:
        o.hide_viewport = o.hide_render = True             # the off-road's ruts lie below the app's floor
bpy.context.view_layer.update()
# a whole drive asked by rays: frames x wheels x 39 points
# the strip the vehicle drives through, sampled by rays at 5 cm (an imported terrain -> a height grid)
strip = (100.0 / 0.05) * (8.0 / 0.05)
M["strip_100m_x_8m_rays"] = int(strip)
M["strip_100m_x_8m_s_by_rays"] = round(strip * t_ray, 1)

# ---------------------------------------------------------------- the ride
route_pts = [(-8.0, 0.0), (10.0, 0.0), (30.0, 0.0), (45.0, 1.0), (60.0, -1.5), (75.0, 1.0), (88.0, 0.0)]
t0 = time.perf_counter()
res = R.drive(veh, route_pts, g, v_want=(20 if which == "car" else 15) / 3.6, fps=25.0, front_share=share,
              slow=((14.0, 22.0, 15 / 3.6),), v_start=0.0, v_end=0.0)
M["ride_total_s"] = round(time.perf_counter() - t0, 2)
M["ride_parts_s"] = {k: round(v, 3) for k, v in res.timings.items()}
n = len(res.t)
M["frames"] = n
M["pitch_deg"] = [round(float(np.degrees(res.pitch.min())), 2), round(float(np.degrees(res.pitch.max())), 2)]
M["roll_deg"] = [round(float(np.degrees(res.roll.min())), 2), round(float(np.degrees(res.roll.max())), 2)]
M["travel_mm"] = [round(float(res.travel.min() * 1000)), round(float(res.travel.max() * 1000))]
M["airborne_frames"] = int(res.airborne.any(0).sum())
print("ride", M["ride_total_s"], "s for", n, "frames")

# ---------------------------------------------------------------- keys
whs = R.wheels_of(veh)


def side_of(name):
    return 1 if " L " in f" {name} " or name.endswith(" L") else -1 if " R " in f" {name} " else 0


def axle_of(name):
    return 0 if name.startswith("Front") else 1 if name.startswith("Rear") else None


def wheel_index(axle, side):
    for i, w in enumerate(whs):
        if w.axle == axle and w.side == side:
            return i


mech = {}
for ai, a in enumerate(veh.axles):
    if a.kind in K.KINDS:
        mech[ai] = K.KINDS[a.kind](a.points)


def link_poses(corner, travel, cache={}):
    lk, wl, wheel, _ = mech[corner[0]]
    s = cache.get(corner)
    if s is None:
        s = cache[corner] = LK.Solver(lk)
        s.reset()
    try:
        s.value_for(LK.Height(wl, wheel, (0.0, wheel[1]), (0.0, 1.0)), travel)
    except LK.Unreachable:
        pass
    return s.poses


def pose2d_to_3d(pose, plane):
    """A planar pose (theta, t1, t2) in the front view (y, z) or side view (x, z) -> a 4x4 in the vehicle frame."""
    th, t1, t2 = pose
    c, s_ = math.cos(th), math.sin(th)
    m = Matrix.Identity(4)
    if plane == "yz":       # turns about x: y' = c y - s z, z' = s y + c z
        m[1][1], m[1][2], m[2][1], m[2][2] = c, -s_, s_, c
        m[1][3], m[2][3] = t1, t2
    else:                   # side view (x, z): turns about y
        m[0][0], m[0][2], m[2][0], m[2][2] = c, -s_, s_, c
        m[0][3], m[2][3] = t1, t2
    return m


def mirror_y(m):
    S = Matrix.Diagonal((1, -1, 1, 1))
    return S @ m @ S


def body_matrix(f):
    ox, oy = res.origin[f]
    T = Matrix.Translation((ox, oy, res.body_z[f]))
    Rz = Matrix.Rotation(res.heading[f], 4, "Z")
    piv = Vector((res.xc, 0.0, 0.0))
    Rp = Matrix.Translation(piv) @ Matrix.Rotation(-res.pitch[f], 4, "Y") @ Matrix.Rotation(res.roll[f], 4, "X") \
        @ Matrix.Translation(-piv)
    return T @ Rz @ Rp


link_of = {"Lower arm": 1, "Upright": 2, "Upper arm": 3, "Trailing arm": 1}
t_mech = 0.0
t0 = time.perf_counter()
frames = range(n)
for o in parts:
    o.rotation_mode = "QUATERNION"
for f in frames:
    B = body_matrix(f)
    for o in parts:
        name = o.get("fr_name", o.name)
        Mc = cad[o.name]
        ai, sd = axle_of(name), side_of(name)
        if ai is None or sd == 0 or name.endswith("Axle") or "Track rod" in name:
            if ai is not None and veh.axles[ai].kind.startswith("SOLID") and (name.endswith("Axle") or "Track rod" in name):
                wl, wr = wheel_index(ai, 1), wheel_index(ai, -1)
                h = 0.5 * (res.travel[wl, f] + res.travel[wr, f])
                rl = (res.travel[wl, f] - res.travel[wr, f]) / veh.axles[ai].track
                c = Vector((veh.axles[ai].x, 0.0, veh.axles[ai].wheel_r))
                A = Matrix.Translation((0, 0, h)) @ Matrix.Translation(c) @ Matrix.Rotation(rl, 4, "X") \
                    @ Matrix.Translation(-c)
                o.matrix_world = B @ A @ Mc
            else:
                o.matrix_world = B @ Mc
            continue
        a = veh.axles[ai]
        wi = wheel_index(ai, sd)
        tr = float(res.travel[wi, f])
        wc = Vector(a.points["wheel"])
        wc.y *= sd
        steer = float(res.steer[wi, f])
        is_wheel = name.endswith("Tyre") or name.endswith("Rim")
        if a.kind.startswith("SOLID"):
            wl, wr = wheel_index(ai, 1), wheel_index(ai, -1)
            h = 0.5 * (res.travel[wl, f] + res.travel[wr, f])
            rl = (res.travel[wl, f] - res.travel[wr, f]) / a.track
            c = Vector((a.x, 0.0, a.wheel_r))
            A = Matrix.Translation((0, 0, h)) @ Matrix.Translation(c) @ Matrix.Rotation(rl, 4, "X") \
                @ Matrix.Translation(-c)
            if "Leaf" in name or "Shackle" in name or "hanger" in name:
                o.matrix_world = B @ (A if "Leaf" in name else Matrix.Identity(4)) @ Mc
                continue
            kp = Vector(a.points.get("kingpin", a.points["wheel"]))
            kp.y *= sd
            St = Matrix.Translation(kp) @ Matrix.Rotation(steer, 4, "Z") @ Matrix.Translation(-kp) if a.steered \
                else Matrix.Identity(4)
            Sp = Matrix.Translation(wc) @ Matrix.Rotation(res.spin[wi, f], 4, "Y") @ Matrix.Translation(-wc) \
                if is_wheel else Matrix.Identity(4)
            o.matrix_world = B @ A @ St @ Sp @ Mc
            continue
        # independent: the mechanism's link poses (the left side's mechanism; the right side mirrored), one walking
        # solver per corner so each keeps its own assembly mode
        tm = time.perf_counter()
        poses = link_poses((ai, sd), tr)
        t_mech += time.perf_counter() - tm
        plane = "yz" if a.kind != "TRAILING_ARM" else "xz"
        lk, wl_, _w, _kp = mech[ai]
        key = next((k for k in link_of if name.endswith(k)), None)
        li = link_of.get(key, wl_) if key else wl_
        if a.kind == "TRAILING_ARM":
            li = 1
        Lm = pose2d_to_3d(poses[li], plane)
        if sd < 0 and plane == "yz":
            Lm = mirror_y(Lm)
        if key in ("Lower arm", "Upper arm", "Trailing arm") or name.endswith("Damper") or name.endswith("Spring") \
                or name.endswith("Coil over") or name.endswith("Tie rod"):
            # arms turn with their link; springs / dampers / tie rods: shown riding on the lower arm (a shortcut –
            # the app stretches them between their two eyes, 0300)
            if key is None and a.kind != "TRAILING_ARM":
                Lm = pose2d_to_3d(poses[1], plane)
                Lm = mirror_y(Lm) if sd < 0 else Lm
                Lm = Matrix.Identity(4) if not name.endswith("Tie rod") else Lm
            o.matrix_world = B @ Lm @ Mc
            continue
        # upright, tyre, rim: the wheel carrier's pose, then steer about the kingpin, then spin
        Wm = pose2d_to_3d(poses[wl_], plane)
        if sd < 0 and plane == "yz":
            Wm = mirror_y(Wm)
        if a.steered:
            p0 = Vector(a.points["lca_out"])
            p1 = Vector(a.points["uca_out"])
            p0.y *= sd
            p1.y *= sd
            ax = (p1 - p0).normalized()
            St = Matrix.Translation(p0) @ Matrix.Rotation(steer, 4, ax) @ Matrix.Translation(-p0)
        else:
            St = Matrix.Identity(4)
        Sp = Matrix.Translation(wc) @ Matrix.Rotation(res.spin[wi, f], 4, "Y") @ Matrix.Translation(-wc) \
            if is_wheel else Matrix.Identity(4)
        o.matrix_world = B @ Wm @ St @ Sp @ Mc
    for o in parts:
        o.keyframe_insert("location", frame=f + 1)
        o.keyframe_insert("rotation_quaternion", frame=f + 1)
t_keys = time.perf_counter() - t0
M["mechanism_ms_per_frame"] = round(t_mech / n * 1000, 2)
M["keys_ms_per_frame_all_parts"] = round((t_keys - t_mech) / n * 1000, 2)
sc.frame_start, sc.frame_end = 1, n
sc.render.fps = 25
print(json.dumps(M, indent=1))
with open(os.path.join(out_dir, f"bake_{which}.json"), "w") as fh:
    json.dump(M, fh, indent=1)
np.savez(os.path.join(out_dir, f"ride_{which}.npz"), t=res.t, pitch=res.pitch, roll=res.roll, travel=res.travel,
         steer=res.steer, speed=res.speed, body_z=res.body_z, origin=res.origin)

# ---------------------------------------------------------------- pictures
if do_render:
    cam_d = bpy.data.cameras.new("Cam")
    cam = bpy.data.objects.new("Cam", cam_d)
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam_d.lens = 45
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
    sun.data.energy = 3.5
    sun.rotation_euler = (math.radians(50), 0, math.radians(30))
    sc.collection.objects.link(sun)
    sc.world = bpy.data.worlds.new("W")
    sc.world.use_nodes = True
    sc.world.node_tree.nodes["Background"].inputs[0].default_value = (0.75, 0.8, 0.86, 1)
    sc.world.node_tree.nodes["Background"].inputs[1].default_value = 0.8
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 24
    sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = 720, 405
    sc.render.image_settings.file_format = "JPEG"
    pick = frames_arg or [int(n * k) for k in (0.25, 0.32, 0.55, 0.75)]
    xray = "--xray" in sys.argv
    if xray:
        for o in parts:
            if o.get("fr_name", o.name) in ("Body", "Cab", "Box body"):
                o.hide_render = True
    for f in pick:
        sc.frame_set(f + 1)
        ox, oy = res.origin[f]
        h = res.heading[f]
        mid = Vector((ox + math.cos(h) * veh.rear_x / 2, oy + math.sin(h) * veh.rear_x / 2, 0.7))
        side = Vector((-math.sin(h), math.cos(h), 0))
        dist = 8.5 if which == "car" else 14.0
        pos = mid - side * dist + Vector((math.cos(h), math.sin(h), 0)) * 1.5 + Vector((0, 0, 1.6))
        if xray:                                           # low, from the front left: the arms and the wheel travel
            fwd = Vector((math.cos(h), math.sin(h), 0))
            mid = Vector((ox, oy, 0.35))                      # the front axle's middle
            pos = mid + fwd * 2.6 + side * 2.2 + Vector((0, 0, 0.75))
        d = (mid - pos).normalized()
        cam.matrix_world = Matrix.Translation(pos) @ d.to_track_quat("-Z", "Y").to_matrix().to_4x4()
        sc.render.filepath = os.path.join(out_dir, f"{which}{'_xray' if xray else ''}_f{f:04d}.jpg")
        t0 = time.perf_counter()
        bpy.ops.render.render(write_still=True)
        print("rendered", f, round(time.perf_counter() - t0, 1), "s")
