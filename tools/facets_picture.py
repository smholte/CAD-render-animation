"""Task 0061 (subagent C): the pictures and numbers of the dark facets on cut faces.

Mills the test mill's block (a slot, a shallower pass across it, a ball-mill groove across both, and the slot the
flat end mill makes meanwhile), gives it a shiny metal look and renders the cut close up with Cycles on the
processor: once with the normals the app wrote, once with ``core/cut_normals.corner_normals``.

    ~/venv/bin/python tools/facets_picture.py <out dir> [numbers|before|after|both] [--dump file.npz]

``numbers`` prints how far the corner normals are from their faces (no render); ``both`` also puts the two
pictures side by side (ImageMagick ``convert``).  bpy as a Python module, no graphics card needed.
"""
from __future__ import annotations

import math
import os
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import bpy  # noqa: E402
import addon_utils  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import animation, build, joints, machining  # noqa: E402

MILL = os.path.join(ROOT, "tests", "data", "test_mill.step")
MM = 0.001
STOCK = "STOCK 200x200x40"

# (joint, start s, duration s, to mm).  Flat end mill Ø10 tip at (0, 0, 90) mm, ball Ø6 at (120, 0, 90) mm,
# the block's top at z = 70 mm.
MOVES = [
    ("Z", 0.0, 1.0, -25.0), ("X", 1.0, 2.0, 50.0), ("Z", 3.0, 0.5, 0.0),          # slot 5 mm deep, 50 mm long
    ("X", 3.5, 0.5, 25.0), ("Y", 4.0, 0.5, -30.0), ("Z", 4.5, 0.5, -22.0),        # a pass across it, 2 mm deep
    ("Y", 5.0, 2.0, 30.0), ("Z", 7.0, 0.5, 0.0),
    ("X", 7.5, 0.5, -82.0), ("Y", 8.0, 0.5, -40.0), ("Z", 8.5, 0.5, -27.0),       # the ball mill, 7 mm deep,
    ("Y", 9.0, 2.0, 40.0), ("X", 9.0, 2.0, -70.0), ("Z", 11.0, 0.5, 0.0),         # slanting across both
]


# the table ends 40 mm along +Y: the crossing of the cuts is at about (30, 40, 66) mm then
CAMERA, TARGET = (0.136, -0.072, 0.148), (0.0, 0.035, 0.068)
BANDS = 9.0                           # light bands between the horizon and straight up


def ob(sc, name):
    return next(o for o in sc.objects if o.get(build.PROP_NAME) == name)


def click(o):
    for x in bpy.context.selected_objects:
        x.select_set(False)
    o.select_set(True)
    bpy.context.view_layer.objects.active = o


def make_scene(out: str, look: str = "chrome"):
    """The milled test block at the end of the moves; returns (scene, the workpiece object)."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    machining._RUNTIME.clear()
    sc = bpy.context.scene
    sc.fresing.out_folder = out
    assert bpy.ops.fresing.import_step(filepath=MILL, quality="draft") == {"FINISHED"}
    for name, asm, d in (("Y", "TABLE.ASM", (0, 1, 0)), ("X", "X.ASM", (1, 0, 0)), ("Z", "Z.ASM", (0, 0, 1))):
        o = ob(sc, asm)
        joints.create(sc, "SLIDE", [o], o.matrix_world.translation, Vector(d), name=name)
    a = sc.fresing.animations.add()
    a.name, a.tail = "Mill", 0.0
    for j, start, dur, to in MOVES:
        b = a.blocks.add()
        b.kind, b.joint, b.start, b.duration, b.easing = "JOINT", j, start, dur, "LINEAR"
        b.use_from, b.to_dist = True, to * MM
    frames = animation.bake(sc, a)["frames"]
    wp = ob(sc, STOCK)
    sc.fresing.groups[wp[build.PROP_GROUP]].material = look
    for bit in ("END MILL D10", "BALL MILL D6"):
        click(ob(sc, bit))
        assert bpy.ops.fresing.mill_add_bit() == {"FINISHED"}
    click(wp)
    assert bpy.ops.fresing.mill_set_workpiece() == {"FINISHED"}
    machining.settings(sc).cut_look = "SAME"           # the cut as a mirror too: reflections show the normals
    machining.sample(sc)
    sc.frame_set(frames)
    machining.refresh(sc, force=True)
    return sc, wp


def tiles_of(sc) -> list:
    """The milled mesh as the app has it, tile by tile: [(verts, tris, source, the tile's box lo, hi)]."""
    rt = machining.runtime(sc)
    tl = rt["timeline"]
    T = float(sc.frame_current)
    return [tl.wp._tile_mesh(t.solid)[:3] + (t.lo, t.hi) for t in tl.at(T) if t.ntri]


def mesh_arrays(me) -> tuple:
    v = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", v)
    t = np.empty(len(me.loops), np.int32)
    me.loops.foreach_get("vertex_index", t)
    return v.reshape(-1, 3), t.reshape(-1, 3)


def blender_corner_normals(me) -> np.ndarray:
    n = np.empty(len(me.loops) * 3, np.float32)
    me.corner_normals.foreach_get("vector", n)
    return n.reshape(-1, 3)


def face_geometry(v, t) -> tuple:
    """(unit face normals, areas, longest edge) in float64."""
    p = v.astype(np.float64)[t]
    e0, e1, e2 = p[:, 1] - p[:, 0], p[:, 2] - p[:, 1], p[:, 0] - p[:, 2]
    c = np.cross(e0, -e2)
    a2 = np.linalg.norm(c, axis=1)
    longest = np.sqrt(np.maximum.reduce([(e0 ** 2).sum(1), (e1 ** 2).sum(1), (e2 ** 2).sum(1)]))
    return c / np.maximum(a2, 1e-300)[:, None], a2 * 0.5, longest


def numbers(v, t, cn, title: str) -> dict:
    """How far corner normals are from the normal of their face on the level faces (the top, the floors of the
    cuts): those meet every other face at 60 degrees or more, so each of their corners must be the face normal."""
    fn, area, longest = face_geometry(v, t)
    thin = 2.0 * area / np.maximum(longest ** 2, 1e-300) < 1e-3
    cn = cn.reshape(-1, 3, 3).astype(np.float64)
    dev = np.degrees(np.arccos(np.clip((cn * fn[:, None, :]).sum(-1), -1, 1)))      # (faces, 3)
    level = (np.abs(fn[:, 2]) > 1 - 1e-9) & ~thin & (area > 1e-12)
    worst = dev[level].max(axis=1)
    out = {
        "triangles": len(t), "thinner than 1/1000 of their length": int(thin.sum()),
        "without area": int((area == 0).sum()),
        "level faces": int(level.sum()), "level mm2": round(float(area[level].sum() * 1e6)),
        "level faces with a corner off > 0.5 deg": int((worst > 0.5).sum()),
        "their mm2": round(float(area[level][worst > 0.5].sum() * 1e6)),
        "worst deg": round(float(worst.max()), 2),
    }
    print(title, out)
    return out


def compare(v, t, before, after, cut) -> None:
    """Corners where Blender's smooth-by-angle and ``corner_normals`` disagree, on triangles one can see."""
    fn, area, longest = face_geometry(v, t)
    real = 2.0 * area / np.maximum(longest ** 2, 1e-300) >= 1e-3
    b, a = before.reshape(-1, 3, 3).astype(np.float64), after.reshape(-1, 3, 3).astype(np.float64)
    d = np.degrees(np.arccos(np.clip((a * b).sum(-1), -1, 1))).max(axis=1)
    for name, sel in (("cut faces", real & cut), ("faces of the block", real & ~cut)):
        one, five = sel & (d > 1), sel & (d > 5)
        print(f"{name}: {int(sel.sum())} triangles, {area[sel].sum() * 1e6:.0f} mm2; a corner normal changed by more "
              f"than 1 deg on {int(one.sum())} ({area[one].sum() * 1e6:.0f} mm2), more than 5 deg on "
              f"{int(five.sum())} ({area[five].sum() * 1e6:.0f} mm2), most {d[sel].max():.1f} deg")


def smooth_but_sharp(me, v, t) -> tuple:
    """(edges Blender left smooth although their two faces are more than 30 degrees apart, all edges) - by
    normals worked out in 64 bits; faces without area are left out."""
    fn, area, _l = face_geometry(v, t)
    edge = np.empty(len(me.loops), np.int32)
    me.loops.foreach_get("edge_index", edge)
    sharp = np.zeros(len(me.edges), bool)
    a = me.attributes.get("sharp_edge")
    if a is not None:
        a.data.foreach_get("value", sharp)
    order = np.argsort(edge, kind="stable")
    e, f = edge[order], order // 3
    pair = np.flatnonzero(e[1:] == e[:-1])                # closed solid: every edge has two faces
    f0, f1 = f[pair], f[pair + 1]
    ok = (area[f0] > 0) & (area[f1] > 0)
    apart = (fn[f0] * fn[f1]).sum(1) < math.cos(math.radians(30.0))
    return int((ok & apart & ~sharp[e[pair]]).sum()), len(me.edges)


def write_normals(me, n) -> None:
    """Our normals as the mesh's custom normals (one per face corner)."""
    old = me.attributes.get("custom_normal")
    if old is not None:
        me.attributes.remove(old)
    a = me.attributes.new("custom_normal", "FLOAT_VECTOR", "CORNER")
    a.data.foreach_set("vector", np.ascontiguousarray(n, np.float32).reshape(-1))
    me.update()


def our_normals(tiles) -> np.ndarray:
    """Tile by tile, as the app will do it (vertices are shared within a tile only)."""
    from fresing_render.core import cut_normals
    return np.concatenate([cut_normals.corner_normals(v, t, skip=cut_normals.seam_faces(v, t, lo, hi))
                           for v, t, _s, lo, hi in tiles])


def set_stage(sc, wp, out: str, name: str) -> str:
    """Lights, a camera close to the cut and render settings; returns the picture's path."""
    for o in sc.objects:                                # only the block: the machine would hide the cut
        if o is not wp and o.type == "MESH":
            o.hide_render = True
    # light and dark bands round the horizon (the "zebra" check of CAD programs): a flat mirror face shows
    # them as even stripes, a corner normal that leans bends or breaks them
    w = bpy.data.worlds.new("facets")
    w.use_nodes = True
    nt = w.node_tree
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = BANDS
    frac = nt.nodes.new("ShaderNodeMath")
    frac.operation = "FRACT"
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = 0.0, (0.03, 0.035, 0.05, 1)
    els[1].position, els[1].color = 1.0, (0.03, 0.035, 0.05, 1)
    for pos, col in ((0.40, (0.03, 0.035, 0.05, 1)), (0.50, (0.9, 0.9, 0.88, 1)), (0.90, (0.9, 0.9, 0.88, 1))):
        els.new(pos).color = col
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    nt.links.new(sep.outputs["Z"], mul.inputs[0])
    nt.links.new(mul.outputs[0], frac.inputs[0])
    nt.links.new(frac.outputs[0], ramp.inputs[0])
    nt.links.new(ramp.outputs[0], nt.nodes["Background"].inputs["Color"])
    nt.nodes["Background"].inputs["Strength"].default_value = 1.0
    sc.world = w
    cd = bpy.data.cameras.new("facets")
    cd.lens = 50.0
    cd.clip_start = 0.005
    cam = bpy.data.objects.new("facets", cd)
    sc.collection.objects.link(cam)
    cam.matrix_world = look_at(Vector(CAMERA), Vector(TARGET))
    sc.camera = cam
    r = sc.render
    r.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 64
    sc.cycles.use_denoising = False
    r.resolution_x, r.resolution_y, r.resolution_percentage = 480, 360, 100
    r.image_settings.file_format = "PNG"
    r.image_settings.color_depth = "8"
    r.filepath = os.path.join(out, name)
    return r.filepath


def look_at(eye: Vector, target: Vector) -> Matrix:
    q = (target - eye).to_track_quat("-Z", "Y")
    return Matrix.Translation(eye) @ q.to_matrix().to_4x4()


def main(argv) -> None:
    out = os.path.abspath(argv[0])
    mode = argv[1] if len(argv) > 1 else "both"
    os.makedirs(out, exist_ok=True)
    sc, wp = make_scene(out)
    me = wp.data
    v, t = mesh_arrays(me)
    before = blender_corner_normals(me)
    numbers(v, t, before, "before:")
    left, edges = smooth_but_sharp(me, v, t)
    print(f"before: {left} of {edges} edges are smooth although their faces are more than 30 deg apart")
    if "--dump" in argv:
        tl = tiles_of(sc)
        np.savez(argv[argv.index("--dump") + 1], v=v, t=t, cn=before,
                 **{f"{k}{i}": a[j] for i, a in enumerate(tl) for j, k in enumerate("vts")})
    if mode in ("before", "both"):
        set_stage(sc, wp, out, "0061-facets-before.png")
        bpy.ops.render.render(write_still=True)
    if mode in ("after", "both", "numbers"):
        tiles = tiles_of(sc)
        t0 = time.perf_counter()
        n = our_normals(tiles)
        print(f"corner_normals: {len(t):,} triangles in {(time.perf_counter() - t0) * 1000:.1f} ms")
        t0 = time.perf_counter()
        write_normals(me, n)
        print(f"written to the mesh in {(time.perf_counter() - t0) * 1000:.2f} ms")
        got = blender_corner_normals(me)
        print("Blender's corner normals minus what was written, largest:", float(np.abs(got - n).max()))
        numbers(v, t, got, "after:")
        compare(v, t, before, got, np.concatenate([s[2] for s in tiles]) < 0)
    if mode in ("after", "both"):
        set_stage(sc, wp, out, "0061-facets-after.png")
        bpy.ops.render.render(write_still=True)              # no frame change in between: the normals stay
    if mode == "both":
        subprocess.run(["convert", os.path.join(out, "0061-facets-before.png"),
                        os.path.join(out, "0061-facets-after.png"), "+append",
                        os.path.join(out, "0061-facets-before-after.png")], check=True)


if __name__ == "__main__":
    main(sys.argv[1:])
