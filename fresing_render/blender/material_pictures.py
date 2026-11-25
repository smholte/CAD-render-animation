"""Material pictures (task 0273): one material on the swatch of study 0270 – a block with chamfered top edges, a knurled
knob on it and a spun cap leaning in front – rendered small (256 px) with the app's studio light.

Used by ``material_picture_runner.py`` in a background Blender: by ``tools/material_pictures.py`` for the built-ins'
pictures in ``fresing_render/data/material_pictures/`` and by the material picker for an own material's
``picture.png``. The shapes are made here as the importer makes a STEP part: triangles in blocks per CAD face, the
round faces' axes in ``fr_axes`` / ``fr_axis_faces`` and the faces' first triangles in ``fr_face_starts`` – so a
finish (knurl, spun rings, a faced end, a weave) lies on them as it lies on a real part."""

from __future__ import annotations

import math
import os
import time

import bpy

SCENE = "FR material picture"
MATERIAL = "FR picture material"
PATTERN = 2.0          # patterns judged as if the picture were 2 x as large (they fade later)
SIZE = 1.0             # the swatch: study 0270's shapes – an 80 mm block, a 20 mm knob, a 42 mm cap
FINISH_SCALE = 2.5     # a finish's pattern is drawn this much coarser in a picture: a 0.8 mm knurl is less than a
                       # pixel at 256 px (the material itself keeps its real size) …
FINE = 0.004           # … only patterns finer than this, and at most to this size


# ---------------------------------------------------------------------------------------------------------------------
# shapes: (points, triangles, axes, axis faces, face starts, smooth faces)

def _cylinder(r: float, h: float, n: int, z0: float = 0.0):
    """A round face (axis z, n x 2 triangles) and its top end face, as two CAD faces."""
    import numpy as np
    ang = np.linspace(0.0, 2.0 * math.pi, n, endpoint=False)
    ring0 = np.c_[r * np.cos(ang), r * np.sin(ang), np.full(n, z0)]
    ring1 = ring0 + [0.0, 0.0, h]
    co = np.vstack([ring0, ring1, [[0.0, 0.0, z0 + h]]])
    tri = []
    for i in range(n):
        j = (i + 1) % n
        tri += [(i, j, n + j), (i, n + j, n + i)]
    side = len(tri)
    for i in range(n):
        tri.append((2 * n, n + i, n + (i + 1) % n))
    axes = [0.0, 0.0, 0.0, 0.0, 0.0, 1.0, r]
    return co, np.array(tri, np.int64), axes, [0, side, 0], [0, side, len(tri)], [True] * side + [False] * n


def _block(w: float, d: float, h: float, c: float):
    """A block w x d x h (x, y, z; standing on z = 0) whose top edges are chamfered by c: ten flat CAD faces."""
    import numpy as np
    x, y = w / 2, d / 2
    top = [(-x + c, -y + c, h), (x - c, -y + c, h), (x - c, y - c, h), (-x + c, y - c, h)]
    mid = [(-x, -y, h - c), (x, -y, h - c), (x, y, h - c), (-x, y, h - c)]
    bot = [(-x, -y, 0.0), (x, -y, 0.0), (x, y, 0.0), (-x, y, 0.0)]
    co = np.array(top + mid + bot, float)
    quads = [(0, 1, 2, 3)]                                               # top
    for i in range(4):
        j = (i + 1) % 4
        quads.append((4 + i, 4 + j, j, i))                               # chamfer
    for i in range(4):
        j = (i + 1) % 4
        quads.append((8 + i, 8 + j, 4 + j, 4 + i))                       # side
    quads.append((8, 11, 10, 9))                                         # bottom
    tri, starts = [], []
    for q in quads:
        starts.append(len(tri))
        tri += [(q[0], q[1], q[2]), (q[0], q[2], q[3])]
    starts.append(len(tri))
    return co, np.array(tri, np.int64), [], [], starts, [False] * len(tri)


def _mesh(name: str, data) -> bpy.types.Mesh:
    import numpy as np

    from . import materials
    co, tri, axes, axf, starts, smooth = data
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(co))
    me.vertices.foreach_set("co", np.asarray(co, np.float32).ravel())
    me.loops.add(len(tri) * 3)
    me.loops.foreach_set("vertex_index", np.asarray(tri, np.int32).ravel())
    me.polygons.add(len(tri))
    me.polygons.foreach_set("loop_start", np.arange(0, len(tri) * 3, 3, dtype=np.int32))
    me.polygons.foreach_set("use_smooth", np.asarray(smooth, bool))
    me.update(calc_edges=True)
    me.validate()
    me["fr_axes"] = [float(v) for v in axes]
    me["fr_axis_faces"] = [int(v) for v in axf]
    me["fr_face_starts"] = [int(v) for v in starts]
    materials.part_axes(me)
    me.materials.append(None)
    return me


def build_scene():
    """The swatch scene (made once per Blender; made again when it was deleted)."""
    from mathutils import Matrix, Vector
    scene = bpy.data.scenes.get(SCENE)
    if scene is not None and scene.camera is not None and len(scene.objects) >= 3:
        return scene
    if scene is not None:
        bpy.data.scenes.remove(scene)
    scene = bpy.data.scenes.new(SCENE)
    scene.unit_settings.system = "METRIC"
    coll = scene.collection
    k = SIZE                                 # the swatch is drawn k x a small part, so patterns of real size show
    parts = {
        "block": (_block(0.080 * k, 0.050 * k, 0.032 * k, 0.005 * k), Matrix.Rotation(math.radians(24), 4, "Z")),
        "knob": (_cylinder(0.010 * k, 0.015 * k, 64), Matrix.Translation((0.012 * k, 0.002 * k, 0.032 * k))),
        "cap": (_cylinder(0.021 * k, 0.004 * k, 96), None),
    }
    for key, (data, mw) in parts.items():
        ob = bpy.data.objects.new(f"FR picture {key}", _mesh(f"FR picture {key}", data))
        coll.objects.link(ob)
        ob.material_slots[0].link = "OBJECT"
        if mw is not None:
            ob.matrix_world = mw
    cap = coll.objects["FR picture cap"]
    lean = Matrix.Rotation(math.radians(-20), 4, "Z") @ Matrix.Rotation(math.radians(62), 4, "X")
    # the cap stands on its rim in front of the block, its face towards the camera
    cap.matrix_world = Matrix.Translation((0.030 * k, -0.052 * k, (0.021 * math.sin(math.radians(62)) + 0.002) * k)) @ lean
    cam_data = bpy.data.cameras.new("FR picture camera")
    cam_data.lens = 70.0
    cam_data.clip_start = 0.005
    cam = bpy.data.objects.new("FR picture camera", cam_data)
    coll.objects.link(cam)
    scene.camera = cam
    centre = Vector((0.006, -0.02, 0.012)) * k
    eye = centre + Vector((0.6, -1.0, 0.9)).normalized() * 0.235 * k
    rot = (centre - eye).to_track_quat("-Z", "Y")
    cam.matrix_world = Matrix.Translation(eye) @ rot.to_matrix().to_4x4()
    r = scene.render
    r.resolution_x = r.resolution_y = 256
    r.resolution_percentage = 100
    _light(scene)
    return scene


def _light(scene) -> None:
    from . import world
    s = scene.fresing
    s.background = "COLOR"
    s.floor = "NONE"
    try:
        world.apply(scene, s)
    except Exception as exc:  # noqa: BLE001
        print("Fresing Render: material picture light:", exc)
    scene.render.film_transparent = False


def put(scene, mat) -> None:
    """Every shape of the swatch shows ``mat`` (with the face data a finish reads)."""
    from . import materials
    for ob in scene.collection.objects:
        if ob.type == "MESH":
            materials.assign(ob, mat)


def plain_material(base: str, color: str = "", wear: float = 0.0, rust: float = 0.0, finish: dict | None = None,
                   adjust: dict | None = None):
    """A library material with an entry's settings, built into "FR picture material"."""
    from ..core import finishes as fin_core
    from . import materials
    mat = bpy.data.materials.get(MATERIAL) or bpy.data.materials.new(MATERIAL)
    try:
        mat.use_nodes = True
    except Exception:  # noqa: BLE001
        pass
    key = fin_core.key(base, **(finish or {})) if fin_core.get(base) else ""
    from ..core import look_adjust as LA
    materials.build_nodes(mat, base, color, wear, finish=key, rust=rust, adjust=LA.key(adjust or {}))
    return mat


def blend_material(path: str, name: str):
    """The material ``name`` appended from ``path`` (None when it is not there)."""
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        if name not in src.materials:
            return None
        dst.materials = [name]
    return dst.materials[0] if dst.materials and dst.materials[0] is not None else None


def render(scene, out: str, samples: int = 32, size: int = 256) -> float:
    """Render the swatch to ``out`` (.png or .jpg, 8 bit RGB) on the processor. Returns the seconds it took."""
    from . import cameras
    from . import render as fr_render
    fr_render.apply_quality(scene, "preview", use_gpu=False)
    scene.cycles.samples = samples
    r = scene.render
    r.resolution_x = r.resolution_y = size
    r.resolution_percentage = 100
    jpg = out.lower().endswith((".jpg", ".jpeg"))
    r.image_settings.file_format = "JPEG" if jpg else "PNG"
    r.image_settings.color_mode = "RGB"
    if jpg:
        r.image_settings.quality = 90
    else:
        r.image_settings.color_depth = "8"
        r.image_settings.compression = 90
    from ..core import finishes as fin_core
    cameras.update_pixel_angle(scene)              # a finish too fine to see fades to its average …
    # … but a picker's picture is there to show the pattern: judged as if it were PATTERN x as large. The app's own
    # handlers would set the camera's angle again when the render starts: they are off for this render.
    scene[fin_core.PIXEL_PROP] = float(scene.get(fin_core.PIXEL_PROP, fin_core.PIXEL_ANGLE)) / PATTERN
    held = []
    for name in ("render_init", "render_pre", "frame_change_pre", "frame_change_post", "depsgraph_update_post"):
        lst = getattr(bpy.app.handlers, name)
        for fn in list(lst):
            if getattr(fn, "__name__", "") == "_pixel_angle_handler":
                lst.remove(fn)
                held.append((lst, fn))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    tmp = out + ".part" + (".jpg" if jpg else ".png")
    r.filepath = tmp
    t0 = time.time()
    try:
        bpy.ops.render.render(write_still=True, scene=scene.name)
    finally:
        for lst, fn in held:
            lst.append(fn)
    os.replace(tmp, out)
    return round(time.time() - t0, 2)


def make(item: dict) -> float:
    """One picture: ``item`` = {"out", "base", "changes"} or {"out", "blend", "material"}. Returns seconds."""
    from ..core import material_files as F
    scene = build_scene()
    if item.get("blend"):
        mat = blend_material(item["blend"], item.get("material", ""))
        if mat is None:
            raise RuntimeError(f"'{item.get('material')}' is not in {item['blend']}")
    else:
        ch = item.get("changes") or {}
        base = item.get("base", "paint_satin")
        entry = F.Entry(key="", name="", base=base, changes=ch)
        v = F.values_of(entry)
        fin = v["finish"]
        if fin and 0 < fin.get("size", 0) < FINE:
            fin = dict(fin, size=min(fin["size"] * FINISH_SCALE, FINE))       # (kept inside the finish's limits by its key)
        mat = plain_material(base, v["color"] or item.get("colour", "") or "", v["wear"], v["rust"], fin, v["adjust"])
    put(scene, mat)
    return render(scene, item["out"], int(item.get("samples", 32)), int(item.get("size", 256)))
