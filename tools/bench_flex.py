"""Hoses and drag chains (task 0058): what they cost next to a big machine.

    ~/venv/bin/python tools/bench_flex.py                    # 3,000 generated parts in 10 moving modules
    ~/venv/bin/python tools/bench_flex.py --heavy            # the PC check's Heavy machine (written and imported
                                                             # first: some minutes; --step keeps / reuses the file)
    ~/venv/bin/python tools/bench_flex.py --render           # also a small Cycles still (processor), with and without
    ~/venv/bin/python tools/bench_flex.py --hoses 20 --chains 3 --links 40 --frames 250

The scene: a machine of about 3,000 placed parts whose modules each slide on a joint (so every part moves), and an
animation that moves them all for ``--frames`` frames. The script then adds its own flex parts, made here and
tagged like model parts: hoses (a round bar drawn bent, 16 sides) from the machine's base to a part of a moving
module, and drag chains of separate link parts laid as two runs and a bend, their moving end on a module.

Measured (the bpy module, no window, so no drawing): a frame change without flex parts, the same with them built;
what "Build animation" takes more; solving and writing all of them once (live); adding them. With ``--render`` one
frame in Cycles with the flex parts drawn and with them off (their stiff CAD shapes).
The budget (task 0058): a frame change may cost 20 ms more.
"""

from __future__ import annotations

import argparse
import math
import os
import statistics
import subprocess
import sys
import tempfile
import time

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402
import addon_utils  # noqa: E402, I001 (after bpy)
from mathutils import Matrix, Vector  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import animation, build, flex, joints  # noqa: E402
from fresing_render.core import flex_chain  # noqa: E402


# ---------------------------------------------------------------------------
# parts made here, tagged like model parts
# ---------------------------------------------------------------------------

def tagged(ob, kind: str, name: str, parent, uid: str):
    ob[build.PROP_KIND], ob[build.PROP_NAME], ob[build.PROP_UID] = kind, name, uid
    if parent is not None:
        ob.parent = parent
    build.set_mat(ob, build.PROP_CAD_BASIS, ob.matrix_basis)
    build.set_mat(ob, build.PROP_REST_BASIS, ob.matrix_basis)
    return ob


def new_part(scene, name: str, mesh, parent, basis: Matrix):
    ob = bpy.data.objects.new(name, mesh)
    (parent.users_collection[0] if parent is not None else scene.collection).objects.link(ob)
    ob.matrix_basis = basis
    n = sum(1 for c in parent.children if c.get(build.PROP_NAME) == name) + 1 if parent is not None else 1
    return tagged(ob, "part", name, parent, f"{parent[build.PROP_UID]}/{name}#{n}")


def sphere_mesh(name: str, radius: float, rings: int = 8, segments: int = 16):
    """A ball of rings x segments faces, written the way the importer writes a part."""
    th = np.linspace(0.0, math.pi, rings + 1)[:, None]
    ph = np.linspace(0.0, 2.0 * math.pi, segments, endpoint=False)[None, :]
    pos = np.stack([np.sin(th) * np.cos(ph), np.sin(th) * np.sin(ph), np.cos(th) * np.ones_like(ph)], axis=2)
    pos = (pos.reshape(-1, 3) * radius).astype(np.float32)
    tri = []
    for r in range(rings):
        for s in range(segments):
            a, b = r * segments + s, r * segments + (s + 1) % segments
            c, d = a + segments, b + segments
            tri += [(a, c, b), (b, c, d)]
    nrm = pos / np.maximum(np.linalg.norm(pos, axis=1, keepdims=True), 1e-9)
    return build._new_mesh(name, pos, nrm.astype(np.float32), np.array(tri, dtype=np.int32))


def generated_machine(scene, placed: int = 3000, unique: int = 600, modules: int = 10):
    """A root, ``modules`` module assemblies in a row, ``placed`` small parts in them. Returns the modules."""
    col = bpy.data.collections.new("bench_machine")
    scene.collection.children.link(col)
    root = bpy.data.objects.new("BENCH.MACHINE", None)
    col.objects.link(root)
    tagged(root, "assembly", "BENCH.MACHINE", None, "BENCH.MACHINE#1")
    root[build.PROP_ROOT] = True
    meshes = [sphere_mesh(f"PART {i + 1:04d}", 0.02 + 0.03 * ((i * 37) % 10) / 10.0) for i in range(unique)]
    out = []
    per = placed // modules
    side = int(math.ceil(math.sqrt(per)))
    for m in range(modules):
        mod = bpy.data.objects.new(f"MODULE {m + 1:02d}", None)
        col.objects.link(mod)
        mod.matrix_basis = Matrix.Translation((m * 3.0, 0.0, 0.5))
        tagged(mod, "assembly", f"MODULE {m + 1:02d}", root, f"BENCH.MACHINE#1/MODULE {m + 1:02d}#1")
        for j in range(per):
            me = meshes[(m * 97 + j * 7) % unique]
            ob = bpy.data.objects.new(me.name, me)
            col.objects.link(ob)
            ob.matrix_basis = Matrix.Translation(((j % side) * 0.12, (j // side) * 0.12, 0.0))
            tagged(ob, "part", me.name, mod, f"{mod[build.PROP_UID]}/{me.name}#{j + 1}")
        out.append(mod)
    return out


def heavy_machine(scene, step: str, folder: str):
    """The PC check's Heavy machine: written by pccheck/heavy_scene.py (unless ``step`` is there), imported at
    Draft. Returns its modules."""
    if not os.path.isfile(step):
        script = os.path.join(ROOT, "fresing_render", "pccheck", "heavy_scene.py")
        t = time.perf_counter()
        subprocess.run([sys.executable, script, step, "600", "3000"], check=True)
        print(f"heavy machine written in {time.perf_counter() - t:.0f} s: {os.path.getsize(step) / 1e6:.0f} MB")
    scene.fresing.out_folder = folder
    t = time.perf_counter()
    assert bpy.ops.fresing.import_step(filepath=step, quality="draft") == {"FINISHED"}
    print(f"imported in {time.perf_counter() - t:.0f} s")
    return sorted((o for o in scene.objects if str(o.get(build.PROP_NAME, "")).startswith("MODULE ")),
                  key=lambda o: o.get(build.PROP_NAME))


def tube_mesh(name: str, path: np.ndarray, radius: float, sides: int = 16):
    """A round bar along ``path`` (n, 3), closed at both ends."""
    t = np.gradient(path, axis=0)
    t /= np.linalg.norm(t, axis=1, keepdims=True)
    ref = np.array([0.0, 1.0, 0.0])
    u = np.cross(t, ref)
    u /= np.linalg.norm(u, axis=1, keepdims=True)
    v = np.cross(t, u)
    ang = np.linspace(0.0, 2.0 * math.pi, sides, endpoint=False)
    ring = np.cos(ang)[None, :, None] * u[:, None, :] + np.sin(ang)[None, :, None] * v[:, None, :]
    pts = (path[:, None, :] + radius * ring).reshape(-1, 3)
    n = len(path)
    faces = [tuple(range(sides - 1, -1, -1)), tuple(range((n - 1) * sides, n * sides))]
    for k in range(n - 1):
        for s in range(sides):
            a, b = k * sides + s, k * sides + (s + 1) % sides
            faces.append((a, b, b + sides, a + sides))
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(p) for p in pts], [], faces)
    me.update()
    me.materials.append(None)
    return me


def hose_path(a: np.ndarray, b: np.ndarray, slack: float = 1.25, n: int = 48) -> np.ndarray:
    """From a (leaving upwards) to b (arriving from above) in an arc about ``slack`` times as long as straight."""
    span = float(np.linalg.norm(b - a))
    lift = 0.5 * span * math.sqrt(max(slack * slack - 1.0, 0.01))
    s = np.linspace(0.0, 1.0, n)[:, None]
    return a + s * (b - a) + np.array([0.0, 0.0, 1.0]) * lift * np.sin(math.pi * s)


def link_mesh(name: str, pitch: float, width: float, height: float):
    """A frame-shaped link: its body x 0 … 0.8 pitch, y 0 … width, z 0 … height (its origin a corner)."""
    pts, faces = [], []

    def box(x0, x1, y0, y1, z0, z1):
        k = len(pts)
        pts.extend([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                    (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)])
        for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
            faces.append(tuple(k + i for i in f))

    L, t = 0.8 * pitch, 0.08 * width
    box(0, L, 0, t, 0, height)
    box(0, L, width - t, width, 0, height)
    box(0.25 * L, 0.75 * L, t, width - t, 0, 0.15 * height)
    box(0.25 * L, 0.75 * L, t, width - t, 0.85 * height, height)
    me = bpy.data.meshes.new(name)
    me.from_pydata(pts, [], faces)
    me.update()
    me.materials.append(None)
    return me


def add_flex_parts(scene, modules, hoses: int, chains: int, links: int):
    """The hose and link parts, and their flex items. Returns the seconds the adding took."""
    root = build.model_roots(scene)[0]
    inv_root = np.array(root.matrix_world.inverted(), dtype=float)

    def in_root(p):
        return np.asarray(p, dtype=float) @ inv_root[:3, :3].T + inv_root[:3, 3]

    hose_parts, chain_parts = [], []
    for h in range(hoses):
        mod = modules[h % len(modules)]
        carrier = next(c for c in mod.children_recursive if c.type == "MESH")
        b = np.array(mod.matrix_world.translation) + (0.1 * (h // len(modules)), -0.3, 0.3)
        a = b + (-0.6, -0.8, -0.25)
        me = tube_mesh(f"BENCH HOSE {h + 1:02d}", in_root(hose_path(a, b)), 0.012)
        hose_parts.append((new_part(scene, me.name, me, root, Matrix.Identity(4)), carrier))
    pitch, radius, width, height = 0.05, 0.10, 0.06, 0.03
    link = link_mesh("BENCH CHAIN LINK", pitch, width, height)
    local = np.eye(4)
    local[:3, 3] = (0.1 * pitch, -0.5 * width, -0.5 * height)             # the body between its two pins
    turn = np.array([[1.0, 0, 0, 0], [0, 0, -1.0, 0], [0, 1.0, 0, 0], [0, 0, 0, 1.0]])   # the link's y across the chain
    spec = flex_chain.ChainSpec(pitch, links, radius)
    for c in range(chains):
        mod = modules[c % len(modules)]
        carrier = next(o for o in mod.children_recursive if o.type == "MESH")
        home = bpy.data.objects.new(f"BENCH CHAIN {c + 1}.ASM", None)
        root.users_collection[0].objects.link(home)
        tagged(home, "assembly", home.name, root, f"{root[build.PROP_UID]}/{home.name}#1")
        frame = np.eye(4)                                                 # runs along X, the moving run above
        frame[:3, :3] = np.array([[1.0, 0, 0], [0, 0, -1.0], [0, 1.0, 0]])
        frame[:3, 3] = np.array(mod.matrix_world.translation) + (-0.6, -0.6 - 0.2 * c, 0.2)
        frame = inv_root @ frame
        pins = flex_chain.chain_pins(spec, np.array([0.45 * links * pitch - 0.2, 2.0 * radius, 0.0])).pins[0]
        mats = frame @ flex_chain.pin_matrices(pins) @ turn @ local
        obs = [new_part(scene, "BENCH CHAIN LINK", link, home, Matrix(m.tolist())) for m in mats]
        chain_parts.append((obs, carrier))
    bpy.context.view_layer.update()
    t = time.perf_counter()
    for part, carrier in hose_parts:
        item, _notes = flex.add_hose(scene, part)
        flex.set_end_part(scene, flex.find(scene, item.name), "B", carrier)
    for obs, carrier in chain_parts:
        item, _notes = flex.add_chain(scene, obs)
        flex.set_end_part(scene, flex.find(scene, item.name), "B", carrier)
    return time.perf_counter() - t


# ---------------------------------------------------------------------------
# measuring
# ---------------------------------------------------------------------------

def frame_ms(scene, frames, passes: int = 3) -> float:
    """Median over ``passes`` of the mean time of a frame change, ms."""
    out = []
    for _ in range(passes):
        scene.frame_set(frames[0] - 1)
        t = time.perf_counter()
        for f in frames:
            scene.frame_set(f)
        out.append((time.perf_counter() - t) / len(frames) * 1000.0)
    return statistics.median(out)


def render_s(scene, path: str) -> float:
    scene.render.filepath = path
    t = time.perf_counter()
    bpy.ops.render.render(write_still=True)
    return time.perf_counter() - t


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--heavy", action="store_true", help="the PC check's Heavy machine instead of generated parts")
    ap.add_argument("--step", default="", help="where the Heavy machine's STEP file is (made there when missing)")
    ap.add_argument("--hoses", type=int, default=20)
    ap.add_argument("--chains", type=int, default=3)
    ap.add_argument("--links", type=int, default=40)
    ap.add_argument("--frames", type=int, default=250)
    ap.add_argument("--render", action="store_true", help="also render one frame in Cycles, with and without")
    ap.add_argument("--size", default="480x270")
    ap.add_argument("--samples", type=int, default=16)
    ap.add_argument("--out", default="", help="folder for the pictures and the import cache")
    args = ap.parse_args(argv)
    out = args.out or tempfile.mkdtemp(prefix="bench_flex_")
    os.makedirs(out, exist_ok=True)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    scene = bpy.context.scene
    scene.fresing.out_folder = out
    if args.heavy:
        modules = heavy_machine(scene, args.step or os.path.join(out, "heavy_machine.step"), out)
    else:
        modules = generated_machine(scene)
    bpy.context.view_layer.update()
    parts = sum(1 for _ in build.iter_parts(scene))
    for k, mod in enumerate(modules):
        joints.create(scene, "SLIDE", [mod], mod.matrix_world.translation.copy(), Vector((1, 0, 0)),
                      name=f"Module {k + 1}")
    bpy.context.view_layer.update()
    a = scene.fresing.animations.add()
    a.name, a.tail, a.fps = "Bench", 0.0, "25"
    seconds = (args.frames - 1) / 25.0
    for k in range(len(modules)):
        b = a.blocks.add()
        b.kind, b.joint, b.start, b.duration, b.easing = "JOINT", f"Module {k + 1}", 0.0, seconds, "SMOOTH"
        b.use_from, b.to_dist = True, 0.25 if k % 2 == 0 else -0.25
    frames = list(range(2, min(args.frames, 101)))

    t = time.perf_counter()
    r = animation.bake(scene, a)
    build_plain = time.perf_counter() - t
    plain_ms = frame_ms(scene, frames)
    animation.clear_keys(scene)
    bpy.context.view_layer.update()

    add_s = add_flex_parts(scene, modules, args.hoses, args.chains, args.links)
    n_flex = len(flex.flex_parts(scene))
    bpy.context.view_layer.update()
    # live: every module moved, every hose and chain solved and written once
    for k in range(len(modules)):
        joints.set_value(joints.find(scene, f"Module {k + 1}"), 0.1 if k % 2 == 0 else -0.1)
    t = time.perf_counter()
    bpy.context.view_layer.update()
    moved_s = time.perf_counter() - t                        # the update with the handler's solve in it
    t = time.perf_counter()
    flex.refresh(scene, force=True)
    live_s = time.perf_counter() - t
    for k in range(len(modules)):
        joints.set_value(joints.find(scene, f"Module {k + 1}"), 0.0)
    bpy.context.view_layer.update()
    t = time.perf_counter()
    for _ in range(200):
        flex._moved(scene)                                   # what the handler does when nothing moved
    idle_ms = (time.perf_counter() - t) / 200 * 1000.0

    t = time.perf_counter()
    r = animation.bake(scene, scene.fresing.animations["Bench"])
    build_flex = time.perf_counter() - t
    t = time.perf_counter()
    warnings = flex.bake(scene, scene.fresing.animations["Bench"])
    bake_s = time.perf_counter() - t
    flex_ms = frame_ms(scene, frames)
    t = time.perf_counter()
    flex.items(scene)[0].stiffness = 0.7                     # a slider moved after the Build: its frames again
    slider_s = time.perf_counter() - t
    problems = [f"{it.name}: {it.problem}" for it in flex.items(scene) if it.problem]

    rows = [("parts in the scene", f"{parts}"),
            ("flex parts", f"{args.hoses} hoses, {args.chains} chains x {args.links} links ({n_flex} parts)"),
            ("frames built", f"{r['frames']}"),
            ("frame change, no flex parts", f"{plain_ms:.1f} ms"),
            ("frame change, flex parts built", f"{flex_ms:.1f} ms  (+{flex_ms - plain_ms:.1f} ms; budget +20)"),
            ("Build animation, no flex parts", f"{build_plain:.2f} s"),
            ("Build animation, with flex parts", f"{build_flex:.2f} s  (+{build_flex - build_plain:.2f} s)"),
            ("  of that: read the frames, solve, write", f"{bake_s:.2f} s"),
            ("live: solve and write all of them once", f"{live_s * 1000:.0f} ms"),
            ("live: an update in which all of them moved", f"{moved_s * 1000:.0f} ms"),
            ("live: the look after an update in which none moved", f"{idle_ms:.2f} ms"),
            ("a slider moved after the Build (one hose)", f"{slider_s * 1000:.0f} ms"),
            ("adding them (reading the CAD shapes)", f"{add_s:.1f} s")]
    if args.render:
        from fresing_render.blender import logic
        logic.update_bounds(scene)
        if scene.camera is None:
            cam = bpy.data.objects.new("Bench camera", bpy.data.cameras.new("Bench camera"))
            scene.collection.objects.link(cam)
            scene.camera = cam
        first = np.array(modules[0].matrix_world.translation)
        scene.camera.matrix_world = Matrix.Translation(Vector(first + (-0.3, -3.5, 1.6))) @ Matrix.Rotation(
            math.radians(68), 4, "X")
        scene.camera.data.clip_end = 1000.0
        w, h = (int(x) for x in args.size.split("x"))
        rd = scene.render
        rd.engine, rd.resolution_x, rd.resolution_y, rd.resolution_percentage = "CYCLES", w, h, 100
        scene.cycles.samples, scene.cycles.use_denoising, scene.cycles.device = args.samples, False, "CPU"
        rd.image_settings.file_format = "PNG"
        scene.frame_set(r["frames"] // 2)
        render_s(scene, os.path.join(out, "warm_up.png"))
        with_s = render_s(scene, os.path.join(out, "bench_flex_with.png"))
        for it in flex.items(scene):
            it.enabled = False
        without_s = render_s(scene, os.path.join(out, "bench_flex_without.png"))
        rows.append((f"Cycles still {w} x {h}, {args.samples} samples, flex parts drawn", f"{with_s:.1f} s"))
        rows.append(("  the same with them off (stiff CAD shapes)", f"{without_s:.1f} s"))
        rows.append(("  pictures", out))
    width = max(len(k) for k, _v in rows)
    print()
    for k, v in rows:
        print(f"{k:<{width}}  {v}")
    for p in problems + list(warnings):
        print("note:", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
