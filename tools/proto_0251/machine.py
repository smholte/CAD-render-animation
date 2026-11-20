"""Prototype 0251: the height-field liquid on the app's test mills (3-, 4- and 5-axis), rendered with the app's own cut,
jets and motion. Blender as a Python module (~/venv). Not app code.

    PYTHONPATH=. ~/venv/bin/python tools/proto_0251/machine.py 3|4|5 <out dir> [frames: all|N,N,..] [engine]

Steps: set the test model up as the tests do (joints, G-code step, milling, coolant on), Build; one pass through the
frames reads every carrier's place, the tool's tip, the coolant spans and (every few frames) the cut part's top; the
charts are height maps made by rays in the carriers' frames; the liquid is baked (liquid.py); then frames are rendered
with the liquid's grids put in place per frame.
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
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
import bl  # noqa: E402
import liquid as L  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import animation, build, coolant, gcode, joints, machining, rotary  # noqa: E402

MM = 1e-3
FLOW = float(os.environ.get("P251_FLOW", "3.0")) / 1000 / 60      # l/min -> m^3/s
RES = tuple(int(x) for x in os.environ.get("P251_RES", "640x360").split("x"))
SAMPLES = int(os.environ.get("P251_SAMPLES", "24"))
STEP = int(os.environ.get("P251_STEP", "1"))
EVERY = 4                       # the cut part's top is read again every so many frames

PROGRAM_3 = """%
(LIQUID TEST: A POCKET AND AN OPEN SLOT, THEN THE TABLE MOVES)
(T1 D=10. CR=0. - flat end mill)
G21 G90 G94 G17
S9000 M3
G0 X-60 Y-30 Z5
M8
G1 Z-5 F900
{pocket5}
G1 Z-10 F900
{pocket10}
G0 Z5
G0 X20 Y0
G1 Z-6 F900
G1 X112 F1800
G0 Z30
G0 Y70
G0 Y-70
G0 Y0
M9
G4 P4
M5
M30
%
"""


def _zigzag(x0, x1, y0, y1, step):
    out, y, k = [], y0, 0
    while True:
        out.append(f"G1 X{(x1 if k % 2 == 0 else x0):g} Y{y:g} F2400")
        k += 1
        if y + step > y1 + 1e-9:
            break
        y += step
        out.append(f"G1 Y{y:g}")
    out.append(f"G1 X{x0:g} Y{y0:g}")
    return "\n".join(out)


def ob(sc, name):
    return next(o for o in sc.objects if o.get(build.PROP_NAME) == name)


def click(o):
    for x in bpy.context.selected_objects:
        x.select_set(False)
    o.select_set(True)
    bpy.context.view_layer.objects.active = o


def setup(kind, tmp):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    sc.fresing.out_folder = tmp
    data = os.path.join(ROOT, "tests", "data")
    if kind == 3:
        assert bpy.ops.fresing.import_step(filepath=os.path.join(data, "test_mill.step"), quality="draft") == {"FINISHED"}
        for name, asm, d in (("Y", "TABLE.ASM", (0, 1, 0)), ("X", "X.ASM", (1, 0, 0)), ("Z", "Z.ASM", (0, 0, 1))):
            o = ob(sc, asm)
            joints.create(sc, "SLIDE", [o], o.matrix_world.translation, Vector(d), name=name)
        assert bpy.ops.fresing.cnc_find_axes() == {"FINISHED"}
        click(ob(sc, "END MILL D10"))
        assert bpy.ops.fresing.cnc_use_tool() == {"FINISHED"}
        click(ob(sc, "STOCK 200x200x40"))
        assert bpy.ops.fresing.cnc_use_workpiece() == {"FINISHED"}
        m = machining.settings(sc)
        m.enabled = True
        machining.add_bit(sc, ob(sc, "END MILL D10"))
        machining.set_workpiece(sc, ob(sc, "STOCK 200x200x40"))
        text = PROGRAM_3.format(pocket5=_zigzag(-60, -10, -30, 30, 8), pocket10=_zigzag(-60, -10, -30, 30, 8))
        path = os.path.join(tmp, "liquid3.ngc")
        open(path, "w").write(text)
        a = sc.fresing.animations.add()
        a.name, a.tail, a.fps = "Program", 0.0, "24"
        b = a.blocks.add()
        b.kind = "GCODE"
        b.gcode_speed, b.gcode_fit, b.gcode_path = "FIT", 12.0, False
        b.gcode_file = path
        sc.fresing.coolant.enabled = True
    else:
        five = kind == 5
        assert bpy.ops.fresing.import_step(filepath=os.path.join(data, "test_5axis.step" if five else "test_4axis.step"),
                                           quality="draft") == {"FINISHED"}
        path = os.path.join(tmp, "prog.ngc")
        open(path, "w").write(rotary.TEST_PROGRAM_5AXIS if five else rotary.TEST_PROGRAM_4AXIS)
        a = sc.fresing.animations.add()
        a.name, a.tail, a.fps = "Program", 0.0, "24"
        b = a.blocks.add()
        b.kind = "GCODE"
        b.gcode_file = path
        b.gcode_speed, b.gcode_fit = "FIT", 12.0
        b.gcode_coolant = "FLOOD"
        rotary.set_up_test_model(sc, b, five=five, milling=True)
        sc.fresing.coolant.enabled = True
    t0 = time.perf_counter()
    r = animation.bake(sc, a)
    machining.sample(sc)
    build_s = time.perf_counter() - t0
    print("Build", round(build_s, 1), "s, frames", sc.frame_start, sc.frame_end, r.get("warnings"))
    return sc, build_s


# ---------------------------------------------------------------------------------------------------------------
# height maps by rays
# ---------------------------------------------------------------------------------------------------------------

def bvh_world(objs, cut_local=None, cut_matrix=None):
    """One BVH of the objects' evaluated meshes in world space (as they are now) + the cut mesh (local verts)."""
    dg = bpy.context.evaluated_depsgraph_get()
    V, F, n = [], [], 0
    for o in objs:
        e = o.evaluated_get(dg)
        me = e.to_mesh()
        me.calc_loop_triangles()
        v = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get("co", v)
        v = v.reshape(-1, 3)
        t = np.empty(len(me.loop_triangles) * 3, np.int64)
        me.loop_triangles.foreach_get("vertices", t)
        M = np.array(o.matrix_world)
        V.append(v @ M[:3, :3].T + M[:3, 3])
        F.append(t.reshape(-1, 3) + n)
        n += len(v)
        e.to_mesh_clear()
    if cut_local is not None:
        v, t = cut_local
        M = cut_matrix
        V.append(v @ M[:3, :3].T + M[:3, 3])
        F.append(t + n)
    if not V:
        return None
    return BVHTree.FromPolygons(np.vstack(V).tolist(), np.vstack(F).tolist())


def heights(bvh, C, xs, ys, z_start):
    """Rays along -z of frame C (4x4 world-from-chart) from z_start over the grid: chart-z of the first hit (NaN: miss)."""
    Cm = Matrix(C.tolist())
    d = (Cm.to_3x3() @ Vector((0, 0, -1))).normalized()
    Ci = np.linalg.inv(C)
    out = np.full((len(ys), len(xs)), np.nan)
    for j, y in enumerate(ys):
        for i, x in enumerate(xs):
            p = Cm @ Vector((x, y, z_start))
            hit, _n, _i, _d = bvh.ray_cast(p, d)
            if hit is not None:
                out[j, i] = Ci[2, :3] @ np.array(hit) + Ci[2, 3]
    return out


def cut_mesh_local(sc):
    m = machining.settings(sc)
    me = m.cut_mesh
    me.calc_loop_triangles()
    v = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", v)
    t = np.empty(len(me.loop_triangles) * 3, np.int64)
    me.loop_triangles.foreach_get("vertices", t)
    return v.reshape(-1, 3), t.reshape(-1, 3)


class ChartDef:
    """A chart: its carrier object (None: still), its frame at the first frame (world), the grid, the objects its
    surface is made of, whether the cut workpiece is part of it, a mask (cells to drop), tray settings."""

    def __init__(self, name, carrier, C0, x0, x1, y0, y1, cell, objs, with_cut, z_start, open_edges=True,
                 drain=None, mask=None):
        self.name, self.carrier, self.C0 = name, carrier, np.asarray(C0, float)
        self.xs = np.arange(x0 + cell / 2, x1, cell)
        self.ys = np.arange(y0 + cell / 2, y1, cell)
        self.cell, self.objs, self.with_cut, self.z_start = cell, objs, with_cut, z_start
        self.open_edges, self.drain_at, self.mask = open_edges, drain, mask
        self.mats = []


def frame_world(origin, z, x):
    z = np.asarray(z, float) / np.linalg.norm(z)
    x = np.asarray(x, float) - np.dot(x, z) * z
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    M = np.eye(4)
    M[:3, 0], M[:3, 1], M[:3, 2], M[:3, 3] = x, y, z, origin
    return M


def charts_for(kind, sc):
    wp = machining.workpiece(sc)
    if kind == 3:
        riders = [o for o in sc.objects if o.type == "MESH" and o.parent is not None
                  and o.parent.get(build.PROP_NAME) == "TABLE.ASM" and o is not wp
                  and o.get(build.PROP_NAME) not in ("FINISHED PART",)]
        table = ob(sc, "TABLE.ASM")
        c1 = ChartDef("table", table, np.eye(4), -0.2, 0.2, -0.15, 0.15, 2 * MM, riders, True, 0.2)
        bed = ob(sc, "BED")
        c2 = ChartDef("tray", None, np.eye(4), -0.35, 0.35, -0.25, 0.25, 5 * MM, [bed], False, 0.1,
                      open_edges=False, drain=(-0.32, -0.22, 15 * MM))
        return [c1, c2]
    if kind == 4:
        bar = wp
        carrier = ob(sc, "A.ASM")
        R = 25 * MM
        axis_z = 0.15
        charts = []
        for k, n in enumerate(((0, 0, 1), (0, 1, 0), (0, 0, -1), (0, -1, 0))):
            # outward direction in the world at A = 0: +Z, +Y, -Z, -Y
            C0 = frame_world((0.0, 0.0, axis_z), n, (1, 0, 0))
            half = R * math.sin(math.radians(45)) + 1 * MM
            charts.append(ChartDef(f"bar {k}", carrier, C0, -0.12, 0.12, -half, half, 1.5 * MM, [], True, 0.06))
        bedo = ob(sc, "BED")
        charts.append(ChartDef("tray", None, np.eye(4), -0.25, 0.25, -0.15, 0.15, 5 * MM, [bedo], False, 0.3,
                               open_edges=False, drain=(-0.22, -0.12, 15 * MM)))
        return charts
    # five
    ctab = ob(sc, "C.ASM")
    rt = ob(sc, "ROTARY TABLE")
    c1 = ChartDef("table C", ctab, np.eye(4), -0.07, 0.07, -0.07, 0.07, 1.5 * MM, [rt], True, 0.3)
    cradle = ob(sc, "CRADLE")
    c2 = ChartDef("cradle", ob(sc, "A.ASM"), np.eye(4), -0.13, 0.13, -0.09, 0.09, 3 * MM, [cradle], False, 0.3)
    bedo = ob(sc, "BED")
    c3 = ChartDef("tray", None, np.eye(4), -0.25, 0.25, -0.15, 0.15, 5 * MM, [bedo], False, 0.3, open_edges=False,
                  drain=(-0.22, -0.12, 15 * MM))
    return [c1, c2, c3]


# ---------------------------------------------------------------------------------------------------------------
# the pass through the frames, the bake
# ---------------------------------------------------------------------------------------------------------------

def run(kind, out, frames_arg="all", eng="CYCLES"):
    os.makedirs(out, exist_ok=True)
    sc, build_s = setup(kind, out)
    f0, f1 = sc.frame_start, sc.frame_end
    n = f1 - f0 + 1
    defs = charts_for(kind, sc)
    sc.frame_set(f0)
    wp = machining.workpiece(sc)
    t0 = time.perf_counter()
    # still parts of each chart's surface: rays at the first frame
    static = []
    for c in defs:
        bvh = bvh_world(c.objs) if c.objs else None
        static.append(heights(bvh, c.C0, c.xs, c.ys, c.z_start) if bvh else np.full((len(c.ys), len(c.xs)), np.nan))
    rays_s = time.perf_counter() - t0
    carriers0 = {c.name: np.array(c.carrier.matrix_world) if c.carrier is not None else np.eye(4) for c in defs}
    wp0 = np.array(wp.matrix_world)
    tips, beds, spans = [], [], coolant.spans()
    tpass = time.perf_counter()
    cut_s = 0.0
    for f in range(f0, f1 + 1):
        sc.frame_set(f)
        for c in defs:
            M = np.array(c.carrier.matrix_world) if c.carrier is not None else np.eye(4)
            c.mats.append(M @ np.linalg.inv(carriers0[c.name]) @ c.C0)
        r = coolant.root()
        tips.append(np.array(r.matrix_world.translation) if r is not None else np.zeros(3))
        if (f - f0) % EVERY == 0:
            a = time.perf_counter()
            v, t = cut_mesh_local(sc)
            # the cut part in the world at the first frame (where the charts' rays were cast)
            bvh = bvh_world([], (v, t), wp0)
            row = []
            for c, st in zip(defs, static):
                if c.with_cut:
                    h = heights(bvh, c.C0, c.xs, c.ys, c.z_start)
                    row.append(np.fmax(st, h))
                else:
                    row.append(st)
            beds.append((f - f0, row))
            cut_s += time.perf_counter() - a
    pass_s = time.perf_counter() - tpass
    for c in defs:
        c.mats.append(c.mats[-1])
        c.mats.insert(0, c.mats[0])
    # charts
    chs = []
    for k, c in enumerate(defs):
        b = beds[0][1][k].copy()
        if c.mask is not None:
            b[c.mask] = np.nan
        drain = None
        if c.drain_at is not None:
            X, Y = np.meshgrid(c.xs, c.ys)
            dx, dy, r = c.drain_at
            hole = (X - dx) ** 2 + (Y - dy) ** 2 <= (r + c.cell / 2) ** 2
            drain = np.zeros_like(b)
            drain[hole] = math.pi * r * r / max(hole.sum(), 1)
            b = np.nan_to_num(b, nan=0.0)
        chs.append(L.Chart(c.name, b, c.cell, c.xs[0], c.ys[0], open_edges=c.open_edges, drain=drain))
    # matrices are indexed from 0 = the frame before f0 (World.gravity uses f-1, f, f+1): shift by one
    mats = [np.array(c.mats) for c in defs]

    def flow_at(f):
        fr = f0 + f
        on = any(a <= fr < b and k == 1 for a, b, k in spans)
        return on

    def sources(fi):
        f = min(fi, n - 1)
        if not flow_at(f):
            return []
        return [(tips[f] + np.array([0.0, 0.0, 0.004]), FLOW)]
    w = L.World(chs, mats, float(sc.render.fps), floor_z=-0.07, sources=sources)
    tb = time.perf_counter()
    store = {c.name: [] for c in chs}
    drops, counts, tot = [], [], []
    bi = 0
    w._vols = []
    bed_at = {c.name: [] for c in chs}
    for fi in range(n):
        while bi + 1 < len(beds) and beds[bi + 1][0] <= fi:
            bi += 1
            for k, c in enumerate(defs):
                if c.with_cut:
                    nb = beds[bi][1][k].copy()
                    if c.mask is not None:
                        nb[c.mask] = np.nan
                    chs[k].set_bed(nb)
        w.run_frame(fi)
        for c in chs:
            store[c.name].append(c.depth.astype(np.float16))
            bed_at[c.name].append(bi)
        drops.append(w.P.astype(np.float32))
        counts.append(len(w.vol))
        tot.append(w.totals())
        w._vols.append(w.vol.astype(np.float32))
    bake_s = time.perf_counter() - tb
    npz = os.path.join(out, "liquid.npz")
    np.savez_compressed(npz, **{f"d_{c.name}": np.array(store[c.name]) for c in chs},
                        drops=np.concatenate(drops), vols=np.concatenate(w._vols), counts=np.array(counts))
    info = dict(kind=kind, frames=n, build_s=build_s, rays_first_s=rays_s, frame_pass_s=pass_s, cut_rays_s=cut_s,
                liquid_bake_s=bake_s, liquid_ms_per_frame=1000 * bake_s / n, cache_bytes=os.path.getsize(npz),
                cells=int(sum(c.bed.size for c in chs)), totals_end={k: v * 1e6 for k, v in tot[-1].items()},
                charts={c.name: list(c.bed.shape) for c in chs}, flow_l_min=FLOW * 60000)
    print(json.dumps(info))
    # ------------------------------------------------------------------ render
    liq = bl.liquid_material("Liquid")
    dm = bl.drop_material("Drops")
    objs = []
    for k, c in enumerate(chs):
        e = bpy.data.objects.new(f"FR liquid frame {c.name}", None)
        sc.collection.objects.link(e)
        g = bl.liquid_grid(f"FR liquid {c.name}", c.bed, c.cell, c.x0, c.y0, liq, e)
        objs.append((e, g, k))
    drops_ob = bl.drops_object("FR liquid drops", dm)
    off = np.concatenate([[0], np.cumsum(counts)])
    D = {c.name: np.array(store[c.name]) for c in chs}
    V = np.concatenate(w._vols)
    P = np.concatenate(drops)

    def update(f):
        i = min(max(f - f0, 0), n - 1)
        for e, g, k in objs:
            e.matrix_world = Matrix(mats[k][i + 1].tolist())
            bb = beds[bed_at[chs[k].name][i]][1][k] if defs[k].with_cut else None
            if bb is not None and defs[k].mask is not None:
                bb = np.where(defs[k].mask, np.nan, bb)
            bl.set_liquid(g, D[chs[k].name][i].astype(np.float32), bed=bb)
        Pd = P[off[i]:off[i + 1]]
        Vd = V[off[i]:off[i + 1]]
        keep = Vd > 2e-10
        a, b = bl.split_drops(Pd[keep], Vd[keep])
        bl.set_drops(drops_ob, a, b)

    # camera
    bb = np.array([wp.matrix_world @ Vector(c) for c in wp.bound_box])
    target = 0.5 * (bb.min(0) + bb.max(0))
    cam_cfg = {3: dict(dist=0.95, elev=38, azim=-60, lens=40), 4: dict(dist=0.62, elev=30, azim=-62, lens=40),
               5: dict(dist=0.55, elev=38, azim=-58, lens=40)}[kind]
    bl.studio(tuple(target - np.array([0, 0, 0.05 if kind != 3 else 0.03])), res=RES, **cam_cfg)
    # the app's world is replaced by the studio's; the machine keeps its own materials
    bl.engine(eng, SAMPLES if eng == "CYCLES" else 32)
    fr = list(range(f0, f1 + 1, STEP)) if frames_arg == "all" else [f0 + int(x) for x in frames_arg.split(",")]
    ups = []
    for f in fr[:30]:
        sc.frame_set(f)
        a = time.perf_counter()
        update(f)
        bpy.context.view_layer.update()
        ups.append(time.perf_counter() - a)
    times = bl.render_frames(fr, os.path.join(out, "frames"), update)
    info.update(render_s_per_frame=float(np.median(times)), update_ms=1000 * float(np.median(ups)), engine=eng)
    if len(fr) > 30:
        info["mp4_bytes"] = bl.mp4(os.path.join(out, "frames"), os.path.join(out, f"m{kind}_{eng.lower()}.mp4"), fps=24 // STEP)
    json.dump(info, open(os.path.join(out, "info.json"), "w"), indent=1, default=float)
    print(json.dumps(info, default=float))


if __name__ == "__main__":
    run(int(sys.argv[1]), sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "all",
        sys.argv[4] if len(sys.argv) > 4 else "CYCLES")
