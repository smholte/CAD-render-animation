"""Prototype pictures and clips of study 0312 (Blender as a Python module, Cycles on the processor).

    ~/venv/bin/python tools/vessels_proto/render_scenes.py <scene> [--clip] [--small]

Scenes: ``vessels`` (a CTV driven in a turn, a tug on a drawn line glancing a floating container, a buoy and a
pallet), ``beach`` (waves breaking on a plain beach), ``under`` (the camera half under water at three clarities;
``--clip``: dipping under). The sea here is the prototype's own displaced grid from ``core/sea``'s components (the
app's sea mesh and shader are not used: findings only). Pictures go to ``tasks/0312_page/img/``.
"""

from __future__ import annotations

import math
import os
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(HERE))
import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

from fresing_render.core import sea as sea_core, vessel_work  # noqa: E402
from vessels_proto import hulls, presets as P, floaters as FL, shore as SH  # noqa: E402

IMG = os.path.join(ROOT, "tasks", "0312_page", "img")
OUT = os.path.join(HERE, "out")
os.makedirs(IMG, exist_ok=True)
FRAMES = os.path.join(OUT, "frames")


# ---------------------------------------------------------------------------
# scene basics
# ---------------------------------------------------------------------------

def reset(w=1280, h=720, samples=48):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 8
    sc.cycles.transparent_max_bounces = 16
    sc.cycles.transmission_bounces = 8
    sc.cycles.volume_bounces = 1
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.film_transparent = False
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.exposure = -1.3
    sc.render.image_settings.file_format = "JPEG"
    sc.render.image_settings.quality = 86
    world = bpy.data.worlds.new("sky")
    sc.world = world
    world.use_nodes = True
    nt = world.node_tree
    bg = nt.nodes["Background"]
    sky = nt.nodes.new("ShaderNodeTexSky")
    try:
        sky.sun_elevation = math.radians(28)
        sky.sun_rotation = math.radians(200)
    except Exception:
        pass
    nt.links.new(sky.outputs[0], bg.inputs[0])
    bg.inputs[1].default_value = 0.35
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sun.data.energy = 3.2
    sun.data.angle = math.radians(1.0)
    sun.rotation_euler = (math.radians(62), 0, math.radians(200 - 180 + 90))
    sc.collection.objects.link(sun)
    return sc


def mat(name, color, rough=0.5, metal=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    return m


def water_mat(clarity=12.0, dome=False):
    """Water: a clear surface (glass, IOR 1.333) + a volume that absorbs and scatters by the clarity (the app's
    ``core/sea.absorption``); foam from the point attribute ``foam``."""
    m = bpy.data.materials.new(f"water {clarity}")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*sea_core.DEEP, 1)
    b.inputs["Roughness"].default_value = 0.035
    b.inputs["IOR"].default_value = 1.333
    b.inputs["Transmission Weight"].default_value = 1.0
    attr = nt.nodes.new("ShaderNodeAttribute")
    attr.attribute_name = "foam"
    foam = nt.nodes.new("ShaderNodeBsdfPrincipled")
    foam.inputs["Base Color"].default_value = (*sea_core.FOAM, 1)
    foam.inputs["Roughness"].default_value = 0.7
    # foam is lacy, never a solid sheet: a noise pattern whose white grows with the foam's strength
    tex = nt.nodes.new("ShaderNodeTexNoise")
    tex.inputs["Scale"].default_value = 1.6
    tex.inputs["Detail"].default_value = 8.0
    tco = nt.nodes.new("ShaderNodeTexCoord")
    nt.links.new(tco.outputs["Object"], tex.inputs["Vector"])
    lace = nt.nodes.new("ShaderNodeMath")
    lace.operation = "MULTIPLY_ADD"                            # noise * 0.9 + foam - 0.75
    lace.inputs[1].default_value = 0.9
    nt.links.new(tex.outputs["Fac"], lace.inputs[0])
    nt.links.new(attr.outputs["Fac"], lace.inputs[2])
    ramp = nt.nodes.new("ShaderNodeMapRange")
    ramp.inputs["From Min"].default_value = 0.75
    ramp.inputs["From Max"].default_value = 1.05
    nt.links.new(lace.outputs[0], ramp.inputs["Value"])
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    nt.links.new(ramp.outputs[0], mul.inputs[0])
    nt.links.new(attr.outputs["Fac"], mul.inputs[1])
    pw = nt.nodes.new("ShaderNodeMath")
    pw.operation = "POWER"
    pw.inputs[1].default_value = 0.5
    nt.links.new(mul.outputs[0], pw.inputs[0])
    mul = pw
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(mul.outputs[0], mix.inputs[0])
    nt.links.new(b.outputs[0], mix.inputs[1])
    nt.links.new(foam.outputs[0], mix.inputs[2])
    out = nt.nodes["Material Output"]
    # light reaches under the water: shadow rays pass the surface (Cycles cannot follow sunlight through a
    # refracting surface – a caustic – so without this everything under water is black)
    lp = nt.nodes.new("ShaderNodeLightPath")
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix2 = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(lp.outputs["Is Shadow Ray"], mix2.inputs[0])
    nt.links.new(mix.outputs[0], mix2.inputs[1])
    nt.links.new(tr.outputs[0], mix2.inputs[2])
    nt.links.new(mix2.outputs[0], out.inputs["Surface"])
    sigma = sea_core.absorption(clarity)
    # absorption in the water's colour: red goes first, blue-green last (North Sea water)
    ab = nt.nodes.new("ShaderNodeVolumeAbsorption")
    ab.inputs["Color"].default_value = (0.25, 0.62, 0.55, 1)
    ab.inputs["Density"].default_value = sigma
    sc_ = nt.nodes.new("ShaderNodeVolumeScatter")
    sc_.inputs["Color"].default_value = (0.35, 0.75, 0.62, 1)
    sc_.inputs["Density"].default_value = sigma * 0.15
    add = nt.nodes.new("ShaderNodeAddShader")
    nt.links.new(ab.outputs[0], add.inputs[0])
    nt.links.new(sc_.outputs[0], add.inputs[1])
    nt.links.new(add.outputs[0], out.inputs["Volume"])
    return m


def mesh_object(name, verts, faces, material=None, smooth=False):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    me.update()
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    if material:
        me.materials.append(material)
    return ob


def far_sea(x0, x1, y0, y1, big=5000.0):
    """The sea beyond the grid: a flat frame round it (never under it – it would poke through the troughs)."""
    g = 2.0
    v = [(-big, -big), (big, -big), (big, big), (-big, big), (x0 + g, y0 + g), (x1 - g, y0 + g), (x1 - g, y1 - g),
         (x0 + g, y1 - g)]
    v = [(a, b, -0.02) for a, b in v]
    f = [(0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return mesh_object("far sea", v, f, mat("far", sea_core.DEEP, 0.08))


def box_object(name, size, loc, material):
    v, f = hulls.box(*size, z0=-size[2] / 2)
    ob = mesh_object(name, v, f, material)
    ob.location = loc
    return ob


# ---------------------------------------------------------------------------
# the sea as a closed water body: a grid on top, skirts and a bottom
# ---------------------------------------------------------------------------

class Water:
    def __init__(self, x0, x1, y0, y1, step, depth, material, comps, extra=None):
        self.xs = np.arange(x0, x1 + 1e-9, step)
        self.ys = np.arange(y0, y1 + 1e-9, step)
        X, Y = np.meshgrid(self.xs, self.ys, indexing="ij")
        self.X, self.Y = X.ravel(), Y.ravel()
        nx, ny = len(self.xs), len(self.ys)
        top = np.column_stack([self.X, self.Y, np.zeros_like(self.X)])
        idx = np.arange(nx * ny).reshape(nx, ny)
        quads = np.stack([idx[:-1, :-1], idx[1:, :-1], idx[1:, 1:], idx[:-1, 1:]], -1).reshape(-1, 4)
        # the rim of the grid, anticlockwise seen from above, and its copy at the bottom
        rim = list(idx[:, 0]) + list(idx[-1, 1:]) + list(idx[::-1, -1][1:]) + list(idx[0, ::-1][1:-1])
        bot0 = len(top)
        bottom = top[rim].copy()
        bottom[:, 2] = -depth
        verts = np.concatenate([top, bottom])
        n = len(rim)
        sides = [(rim[(i + 1) % n], rim[i], bot0 + i, bot0 + (i + 1) % n) for i in range(n)]
        faces = [tuple(q) for q in quads] + sides + [tuple(bot0 + i for i in range(n - 1, -1, -1))]
        self.ob = mesh_object("sea", verts, faces, material, smooth=True)
        self.n_top = len(top)
        self.rim = rim
        self.comps = comps
        self.extra = extra
        me = self.ob.data
        self.foam_attr = me.attributes.new("foam", "FLOAT", "POINT")
        self.shape = (nx, ny)

    def height(self, x, y, t):
        h = sea_core.height(x, y, t, self.comps) if self.comps else np.zeros_like(x)
        if self.extra is not None:
            h = h + self.extra(x, y, t)
        return h

    def update(self, t, foam=None, positions=None):
        me = self.ob.data
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        if positions is not None:
            co[:self.n_top] = positions
        else:
            co[:self.n_top, 2] = self.height(self.X, self.Y, t)
        nb = len(self.rim)
        co[self.n_top:self.n_top + nb, :2] = co[self.rim, :2]
        me.vertices.foreach_set("co", co.ravel())
        f = np.zeros(len(me.vertices))
        if foam is not None:
            f[:self.n_top] = foam
        me.attributes["foam"].data.foreach_set("value", f)
        me.update()


# ---------------------------------------------------------------------------
# vessels
# ---------------------------------------------------------------------------

def vessel(kind: str):
    p = P.BY_KEY[kind]
    if kind == "CTV":
        v, f = hulls.catamaran(p.length, p.beam, p.beam * 0.3, p.depth, p.draught + 0.3)
        body = mat("ctv hull", (0.85, 0.86, 0.88), 0.35)
        top = mat("ctv orange", (0.9, 0.32, 0.04), 0.4)
    else:
        v, f = hulls.monohull(p.length, p.beam, p.depth, p.draught + 0.6)
        body = mat(kind + " hull", (0.08, 0.1, 0.16), 0.45)
        top = mat(kind + " house", (0.92, 0.92, 0.9), 0.4)
    app = P.apply(p, v, f)
    v = v - (0, 0, app["waterline_z"])                      # waterline at z = 0 of the object
    root = bpy.data.objects.new(kind, None)
    bpy.context.scene.collection.objects.link(root)
    h = mesh_object(kind + " hull", v, f, body, smooth=False)
    h.parent = root
    deck = float(v[:, 2].max())
    red = mat("antifoul", (0.45, 0.05, 0.04), 0.6)
    if kind == "CTV":
        wd = box_object("CTV deck", (p.length * 0.9, p.beam * 0.95, 0.5), (0, 0, deck + 0.25), body)
        house = box_object("CTV house", (8.0, p.beam * 0.7, 2.6), (p.length * 0.12, 0, deck + 1.8), top)
        win = box_object("CTV windows", (8.05, p.beam * 0.6, 0.8), (p.length * 0.12, 0, deck + 2.3),
                         mat("glass", (0.02, 0.03, 0.04), 0.05))
        fender = box_object("CTV fender", (0.8, 2.2, 1.2), (p.length / 2 + 0.2, 0, deck - 0.4),
                            mat("rubber", (0.02, 0.02, 0.02), 0.8))
        parts = [wd, house, win, fender]
    else:
        house = box_object("TUG house", (8.0, 7.0, 3.0), (2.0, 0, deck + 1.5), top)
        bridge = box_object("TUG bridge", (5.0, 7.6, 2.4), (3.0, 0, deck + 4.2), top)
        win = box_object("TUG windows", (5.05, 7.65, 0.9), (3.0, 0, deck + 4.6), mat("glass", (0.02, 0.03, 0.04), 0.05))
        mast = box_object("TUG mast", (0.4, 0.4, 5.0), (3.0, 0, deck + 7.5), top)
        fender = box_object("TUG fender", (2.5, p.beam * 0.6, 1.6), (p.length / 2 - 0.4, 0, deck - 0.3),
                            mat("rubber", (0.02, 0.02, 0.02), 0.8))
        tdeck = box_object("TUG deck", (p.length * 0.86, p.beam * 0.92, 0.1), (-0.5, 0, deck + 0.05),
                           mat("deck", (0.22, 0.27, 0.22), 0.7))
        parts.append(tdeck) if False else None
        stack = box_object("TUG funnel", (2.0, 3.0, 3.0), (-3.5, 0, deck + 1.5), mat("tug yellow", (0.9, 0.6, 0.05), 0.4))
        parts = [house, bridge, win, mast, fender, stack, tdeck]
    boot = box_object(kind + " boot", (p.length * 0.002, 0.001, 0.001), (0, 0, 0), red)    # (keeps the material)
    parts.append(boot)
    for o in parts:
        o.parent = root
    root["fr_len"], root["fr_beam"] = p.length, p.beam
    return root, app


def place(root, x, y, psi, sea_h, t, along=None):
    """Put a vessel on the sea: heave, pitch, roll from the plane that fits the sea under its waterline."""
    L, B = root["fr_len"] * 0.8, root["fr_beam"] * 0.8
    u = np.linspace(-L / 2, L / 2, 9)
    v = np.linspace(-B / 2, B / 2, 5)
    U, V = np.meshgrid(u, v, indexing="ij")
    c, s = math.cos(psi), math.sin(psi)
    X = x + c * U - s * V
    Y = y + s * U + c * V
    H = sea_h(X.ravel(), Y.ravel(), t).reshape(U.shape)
    A = np.column_stack([np.ones(U.size), U.ravel(), V.ravel()])
    coef = np.linalg.lstsq(A, H.ravel(), rcond=None)[0]
    pitch = -math.atan(coef[1])
    roll = math.atan(coef[2])
    root.matrix_world = (Matrix.Translation((x, y, coef[0])) @ Matrix.Rotation(psi, 4, "Z")
                         @ Matrix.Rotation(pitch, 4, "Y") @ Matrix.Rotation(roll, 4, "X"))


def camera(loc, target, lens=35.0):
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    cam.data.lens = lens
    cam.data.clip_end = 5000
    bpy.context.scene.collection.objects.link(cam)
    cam.location = loc
    d = Vector(target) - Vector(loc)
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = cam
    return cam


def render(path):
    bpy.context.scene.render.filepath = path
    t = time.perf_counter()
    bpy.ops.render.render(write_still=True)
    return time.perf_counter() - t


# ---------------------------------------------------------------------------
# wake foam on the grid from a track
# ---------------------------------------------------------------------------

def wake_foam(water, track, t, half_beam, length, reach=220.0):
    """Foam of the turbulent wake behind a vessel along its recorded track up to time ``t`` (``core/sea.wake``,
    measured along the curved track, not a straight line)."""
    nx, ny = water.shape
    foam = np.zeros((nx, ny))
    tr = track[track[:, 0] <= t]
    if len(tr) < 2:
        return foam.ravel()
    now = tr[-1]
    # stern position now; walk back along the track
    seg = np.r_[0.0, np.cumsum(np.hypot(*np.diff(tr[:, 1:3], axis=0).T))]
    back = seg[-1] - seg - length / 2                       # metres behind the stern
    knots = now[4] / P.KNOT
    step = water.xs[1] - water.xs[0]
    for i in range(len(tr) - 1, -1, -1):
        xb = back[i]
        if xb > reach:
            break
        if xb < -length / 2:
            continue
        x, y, psi = tr[i, 1], tr[i, 2], tr[i, 3]
        w = half_beam * (1.0 + 0.012 * max(xb, 0)) + 3.0
        ix0, ix1 = np.searchsorted(water.xs, [x - w, x + w])
        iy0, iy1 = np.searchsorted(water.ys, [y - w, y + w])
        if ix1 <= ix0 or iy1 <= iy0:
            continue
        gx, gy = np.meshgrid(water.xs[ix0:ix1] - x, water.ys[iy0:iy1] - y, indexing="ij")
        lat = -math.sin(psi) * gx + math.cos(psi) * gy
        lon = math.cos(psi) * gx + math.sin(psi) * gy
        near = np.abs(lon) < step * 1.5 + 0.6
        f = sea_core.wake(np.full_like(lat, max(xb, 0.0)), lat, half_beam, max(knots, 4.0)) * near
        foam[ix0:ix1, iy0:iy1] = np.maximum(foam[ix0:ix1, iy0:iy1], f)
    # smear along the track a little (the sampling is 30 Hz)
    k = np.ones(5) / 5
    foam = np.apply_along_axis(lambda r: np.convolve(r, k, "same"), 0, foam)
    foam = np.apply_along_axis(lambda r: np.convolve(r, k, "same"), 1, foam)
    return np.clip(foam * 1.1, 0, 1).ravel()


# ---------------------------------------------------------------------------
# scenes
# ---------------------------------------------------------------------------

def scene_vessels(clip=False, small=False):
    w, h = (960, 540) if not small else (640, 360)
    sc = reset(w, h, 32 if clip else 64)
    comps = sea_core.components(4.0, 20.0)
    tug_track = np.load(os.path.join(OUT, "floaters_tug.npy"))
    fl = np.load(os.path.join(OUT, "floaters.npy"))
    rec = np.load(os.path.join(OUT, "drive_rec.npy"))
    # the CTV's drive: its turn, moved to lie beside the tug's line (x, y offset; the recorded heading kept)
    t_off = 2.0                                              # the CTV's record runs 2 s behind the scene's clock
    ctv_tr = rec.copy()
    ctv_tr[:, 0] += t_off
    i0 = np.searchsorted(ctv_tr[:, 0], 46.0)
    ctv_tr[:, 1] += -45.0 - ctv_tr[i0, 1]
    ctv_tr[:, 2] += -55.0 - ctv_tr[i0, 2]
    tug_p = P.BY_KEY["TUG"]
    ctv_p = P.BY_KEY["CTV"]

    def kelvin_all(x, y, t):
        out = np.zeros_like(x)
        for tr, p in ((tug_track, tug_p), (ctv_tr, ctv_p)):
            hl = FL.Hull(np.zeros((3, 2)), 0, tr)
            c, psi, vel, _ = hl.at(t)
            kn = float(np.hypot(*vel)) / P.KNOT
            rx, ry = x - c[0], y - c[1]
            ca, sa = math.cos(psi), math.sin(psi)
            u = ca * rx + sa * ry
            v = -sa * rx + ca * ry
            out += vessel_work.kelvin(p.length / 2 - u, v, kn)
        return out

    step = 0.6 if not small else 0.9
    water = Water(-140, 120, -70, 130, step, 25.0, water_mat(10.0), comps, extra=kelvin_all)
    bed = mesh_object("seabed", [(-400, -400, -24.8), (400, -400, -24.8), (400, 400, -24.8), (-400, 400, -24.8)],
                      [(0, 1, 2, 3)], mat("sand", (0.35, 0.3, 0.22), 0.9))
    far_sea(-140, 120, -70, 130)
    tug, _ = vessel("TUG")
    ctv, _ = vessel("CTV")
    cont = box_object("container", (6.06, 2.44, 2.59), (0, 0, 0), mat("container blue", (0.05, 0.18, 0.45), 0.5, 0.3))
    buoy = bpy.data.objects.new("buoy", bpy.data.meshes.new("buoy"))
    bpy.ops.mesh.primitive_cylinder_add(radius=0.8, depth=2.2, vertices=24)
    buoy = bpy.context.active_object
    buoy.data.materials.append(mat("buoy yellow", (0.9, 0.65, 0.02), 0.4))
    pal = box_object("pallet", (1.2, 0.8, 0.144), (0, 0, 0), mat("wood", (0.45, 0.32, 0.18), 0.8))
    floats = [(cont, 0, -0.645), (buoy, 1, 0.0), (pal, 2, 0.0)]
    cam = camera((52, 40, 15), (-6, -12, -2), 32)

    def frame(t):
        tug_hl = FL.Hull(np.zeros((3, 2)), 0, tug_track)
        ctv_hl = FL.Hull(np.zeros((3, 2)), 0, ctv_tr)
        foam = np.maximum(wake_foam(water, tug_track, t, tug_p.beam / 2, tug_p.length),
                          wake_foam(water, ctv_tr, t, ctv_p.beam / 2, ctv_p.length))
        water.update(t, foam)
        for root, hl in ((tug, tug_hl), (ctv, ctv_hl)):
            c, psi, _, _ = hl.at(t)
            place(root, c[0], c[1], psi, water.height, t)
        i = int(np.clip(np.searchsorted(fl[:, 0], t), 0, len(fl) - 1))
        for ob, j, cg in floats:
            px, py, pz, r, pch, yw = fl[i, 1 + 6 * j: 7 + 6 * j]
            M = Matrix.Translation((px, py, pz)) @ Matrix.Rotation(yw, 4, "Z") @ Matrix.Rotation(pch, 4, "Y") \
                @ Matrix.Rotation(r, 4, "X") @ Matrix.Translation((0, 0, -cg))
            ob.matrix_world = M

    if not clip:
        t = 45.4
        frame(t)
        took = render(os.path.join(IMG, "vessels.jpg"))
        print(f"vessels still {took:.1f} s")
        return took
    return clip_frames("vessels", frame, 40.0, 50.0, 12)


def clip_frames(name, frame, t0, t1, fps):
    d = os.path.join(FRAMES, name)
    os.makedirs(d, exist_ok=True)
    n = int(round((t1 - t0) * fps))
    t_start = time.perf_counter()
    for i in range(n):
        frame(t0 + i / fps)
        bpy.context.scene.render.filepath = os.path.join(d, f"{i:04d}.jpg")
        bpy.ops.render.render(write_still=True)
        print(f"{name} frame {i + 1}/{n}", flush=True)
    took = time.perf_counter() - t_start
    mp4 = os.path.join(IMG, f"{name}.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", os.path.join(d, "%04d.jpg"),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "27", "-movflags", "+faststart", mp4],
                   check=True)
    print(f"{name}: {n} frames in {took:.0f} s ({took / n:.1f} s a frame)")
    return took


def scene_beach(clip=False, small=False):
    w, h = (960, 540) if not small else (640, 360)
    sc = reset(w, h, 32 if clip else 64)
    comps = sea_core.components(5.0, 15.0)
    sh = SH.Shore(comps, h0=12.0, slope=1 / 25, x_shore=0.0, x_far=-400.0)
    tb = sh.tables()
    step = 0.45 if not small else 0.7
    water = Water(-170, 6, -120, 120, step, 13.0, water_mat(4.0), [])
    # the sea floor and the beach: a slope 1:25 up to the waterline and on to the dunes
    xs = np.linspace(-400, 60, 240)
    ys = np.linspace(-200, 200, 60)
    X, Y = np.meshgrid(xs, ys, indexing="ij")
    Z = -sh.depth(X) + np.where(X > 0, X * 0.04 + 0.3 * np.sin(Y / 7.0) * np.clip(X / 30, 0, 1), 0.0)
    Z = np.where(X > 0, np.maximum(Z, 0.04 * X), Z) - 0.05
    idx = np.arange(X.size).reshape(X.shape)
    quads = np.stack([idx[:-1, :-1], idx[1:, :-1], idx[1:, 1:], idx[:-1, 1:]], -1).reshape(-1, 4)
    beach = mesh_object("beach", np.column_stack([X.ravel(), Y.ravel(), Z.ravel()]), quads,
                        mat("sand", (0.42, 0.36, 0.26), 0.95), smooth=True)
    # wet sand where the swash reaches: darker and glossier (an attribute, as the app would write it)
    wet = beach.data.attributes.new("wet", "FLOAT", "POINT")
    wet.data.foreach_set("value", np.clip(1.0 - X.ravel() / 9.0, 0, 1) * (X.ravel() > -2))
    nt = beach.data.materials[0].node_tree
    a = nt.nodes.new("ShaderNodeAttribute")
    a.attribute_name = "wet"
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs["A"].default_value = (0.42, 0.36, 0.26, 1)
    mix.inputs["B"].default_value = (0.2, 0.16, 0.11, 1)
    nt.links.new(a.outputs["Fac"], mix.inputs["Factor"])
    bsdf = nt.nodes["Principled BSDF"]
    nt.links.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
    rr = nt.nodes.new("ShaderNodeMapRange")
    rr.inputs["To Min"].default_value = 0.95
    rr.inputs["To Max"].default_value = 0.35
    nt.links.new(a.outputs["Fac"], rr.inputs["Value"])
    nt.links.new(rr.outputs["Result"], bsdf.inputs["Roughness"])
    mesh_object("far sea", [(-5000, -5000, -0.02), (-168, -5000, -0.02), (-168, 5000, -0.02),
                            (-5000, 5000, -0.02)], [(0, 1, 2, 3)], mat("far", sea_core.DEEP, 0.08))
    cam = camera((24, -52, 13), (-75, 12, -1.0), 30)
    me = water.ob.data

    def frame(t):
        XX, YY = water.X, water.Y
        Xn, Yn, Zn, foam = sh.surface(XX, YY, t, tb)
        dry = sh.depth(XX) <= 0.03
        # the water ends at the beach: the dry points stay just under the sand (the swash is a later step)
        Zn = np.where(dry, -0.25 - 0.04 * np.maximum(XX, 0), np.maximum(Zn, -sh.depth(XX) + 0.02))
        water.update(t, foam, np.column_stack([Xn, Yn, Zn]))

    if not clip:
        frame(30.0)
        took = render(os.path.join(IMG, "beach.jpg"))
        print(f"beach still {took:.1f} s")
        return took
    return clip_frames("beach", frame, 30.0, 38.0, 12)


def scene_under(clip=False, small=False):
    w, h = (960, 540) if not small else (640, 360)
    comps = sea_core.components(3.5, 20.0)
    times = {}
    for clarity in ((4.0, 12.0, 30.0) if not clip else (12.0,)):
        sc = reset(w, h, 64 if not clip else 32)
        sc.cycles.volume_bounces = 2
        bpy.data.objects["sun"].rotation_euler = (math.radians(55), 0, math.radians(300))
        sky = sc.world.node_tree.nodes.get("Sky Texture")
        if sky is not None:
            sky.sun_rotation = math.radians(20)               # the sun behind the pile: its disc stays out of the dome
        water = Water(-60, 60, -40, 80, 0.35 if not small else 0.6, 18.0, water_mat(clarity), comps)
        mesh_object("seabed", [(-300, -300, -17.8), (300, -300, -17.8), (300, 300, -17.8), (-300, 300, -17.8)],
                    [(0, 1, 2, 3)], mat("sand", (0.5, 0.42, 0.3), 0.9))
        # a monopile with its transition piece and boat landing, and the CTV pushing on it
        bpy.ops.mesh.primitive_cylinder_add(radius=3.5, depth=40, vertices=48, location=(0, 40, 2))
        pile = bpy.context.active_object
        pile.data.materials.append(mat("pile", (0.85, 0.7, 0.05), 0.5))
        for zz, nm in ((-6, "growth"),):
            bpy.ops.mesh.primitive_cylinder_add(radius=3.56, depth=12, vertices=48, location=(0, 40, -12))
            bpy.context.active_object.data.materials.append(mat("growth", (0.12, 0.16, 0.08), 0.95))
        ctv, _ = vessel("CTV")
        ladder = box_object("boat landing", (1.2, 2.6, 14), (0, 40 - 3.9, -1.0), mat("landing", (0.85, 0.7, 0.05), 0.5))
        far_sea(-60, 60, -40, 80)
        # fish-sized specks: a few hundred small bits in the water (particles)
        rng = np.random.default_rng(3)
        pts = rng.uniform((-30, 0, -16), (30, 60, -1), (500, 3))
        v = np.concatenate([p + np.array([[0, 0, 0], [0.04, 0, 0], [0, 0.04, 0], [0, 0, 0.04]]) for p in pts])
        f = np.concatenate([np.array([(0, 1, 2), (0, 1, 3), (0, 2, 3), (1, 2, 3)]) + 4 * i for i in range(len(pts))])
        mesh_object("specks", v, f, mat("speck", (0.8, 0.85, 0.8), 0.6))

        def frame(t, cam_z=None):
            water.update(t)
            place(ctv, 0, 40 - 3.9 - 0.6 - 13.0 - 0.6, math.pi / 2, water.height, t)

        cam = camera((-9.5, 18.0, 0.0), (0.0, 33.0, -2.2), 18)
        # a lens dome: a small sphere of air round the lens, cut out of the water body (a Boolean). Rays going
        # down leave the dome into the water, rays going up into the air: the split picture of a camera half under
        # water, its waterline curved like a real dome port's.
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.35, segments=96, ring_count=48)
        dome = bpy.context.active_object
        for poly in dome.data.polygons:
            poly.use_smooth = True                            # rays from the middle meet it square: no bending
        dome.hide_render = True
        dome.parent = cam
        dome.matrix_parent_inverse = Matrix()
        dome.location = (0, 0, 0)
        mod = water.ob.modifiers.new("lens dome", "BOOLEAN")
        mod.operation = "DIFFERENCE"
        mod.object = dome
        try:
            mod.solver = "MANIFOLD"
        except Exception:
            mod.solver = "EXACT"

        def at_surface(t, below=0.0):
            z = float(water.height(np.array([cam.location.x]), np.array([cam.location.y]), t)[0])
            cam.location.z = z - below

        if not clip:
            frame(20.0)
            at_surface(20.0, 0.02)
            times[clarity] = render(os.path.join(IMG, f"under_{int(clarity)}m.jpg"))
            print(f"under {clarity} m: {times[clarity]:.1f} s")
        else:
            def fr(t):
                frame(t)
                k = (t - 20.0) / 6.0                          # 0 … 1 over the clip: from 2.5 m above to 2.5 m under
                z0 = float(water.height(np.array([cam.location.x]), np.array([cam.location.y]), t)[0])
                cam.location.z = z0 + 2.5 - 5.0 * (0.5 - 0.5 * math.cos(math.pi * min(max(k, 0), 1)))
            return clip_frames("under", fr, 20.0, 26.0, 12)
    return times


if __name__ == "__main__":
    what = sys.argv[1]
    clip = "--clip" in sys.argv
    small = "--small" in sys.argv
    {"vessels": scene_vessels, "beach": scene_beach, "under": scene_under}[what](clip, small)
