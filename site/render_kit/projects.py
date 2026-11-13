"""Fresing Render – the moving models of the web page as app projects (task 0112).

A *sheet* (``projects/<model>.json``, written by ``tools/make_site_projects.py`` from the model's own source files)
says which sub-assemblies turn or slide about which axis, which joints follow others and by how much, where the
cylinders' pins are, the named poses and the animation. ``make(pkg, scene, sheet)`` does on an imported model what a
user does with the buttons, through the app's own functions: joints (4 Motion > Joints, ``joints.create`` in one
batch), couplings (``joints.set_follows``), cylinders (``cylinders.create``), poses (``states.save_pose``), the
animation of "Go to pose" steps (6 Animation), Build (``animation.bake``) and the clash check (``clash.check``).

Sheet coordinates are the STEP file's, in mm; the model root's matrix takes them into the scene (the importer's up
axis and units). Parts are found by their CAD name (sub-assembly names in the sheet are unique in the model).

Used by the render kit (``make_site_pictures.py``, models.ini ``project = <model>``) on the owner's PC, by
``tools/make_site_projects.py`` and by the tests (Blender as a Python module).
"""

from __future__ import annotations

import importlib
import json
import math
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SHEETS = os.path.join(HERE, "projects")


def sheet_path(model: str) -> str:
    return os.path.join(SHEETS, f"{model}.json")


def load(model_or_path: str) -> dict:
    path = model_or_path if model_or_path.endswith(".json") else sheet_path(model_or_path)
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _mod(pkg, name: str):
    return importlib.import_module(f"{pkg.__name__}.{name}")


class Model:
    """Lookups on the imported model: parts by CAD name, sheet points (mm) as scene points."""

    def __init__(self, pkg, scene, sheet: dict):
        build = _mod(pkg, "blender.build")
        self.pkg, self.scene, self.sheet = pkg, scene, sheet
        want = os.path.basename(sheet["step"]).lower()
        roots = [r for r in build.model_roots(scene)
                 if os.path.basename(str(r.get(build.PROP_SOURCE, ""))).lower() == want]
        if len(roots) != 1:
            raise RuntimeError(f"{sheet['step']} is not (once) in the project")
        self.root = roots[0]
        logic = _mod(pkg, "blender.logic")
        self.by_name: dict = {}
        for ob in [self.root] + list(logic.descendants(self.root)):
            self.by_name.setdefault(str(ob.get(build.PROP_NAME, ob.name)), []).append(ob)

    def one(self, name: str):
        hits = self.by_name.get(name, [])
        if len(hits) != 1:
            raise RuntimeError(f"'{name}': {len(hits)} parts or sub-assemblies of that name in the model (need 1)")
        return hits[0]

    def point(self, p):
        from mathutils import Vector
        return self.root.matrix_world @ (Vector(p) / 1000.0)

    def direction(self, d):
        from mathutils import Vector
        return (self.root.matrix_world.to_3x3() @ Vector(d)).normalized()


def _order(js: list[dict]) -> list[dict]:
    """The joints others ride on or follow come first."""
    by = {j["name"]: j for j in js}
    out, done = [], set()

    def add(j, seen=()):
        if j["name"] in done or j["name"] in seen:
            return
        for dep in (j.get("rides_on"), j.get("follows")):
            if dep and dep in by:
                add(by[dep], seen + (j["name"],))
        done.add(j["name"])
        out.append(j)
    for j in js:
        add(j)
    return out


def hide_parts(pkg, scene, m: Model) -> int:
    """Parts the sheet leaves out (hidden for good: the app's "excluded", 2 Structure); the sheet says why."""
    logic = _mod(pkg, "blender.logic")
    objs = [m.one(h["part"]) for h in m.sheet.get("hide", [])]
    return logic.exclude(objs) if objs else 0


def make_joints(pkg, scene, m: Model) -> int:
    joints = _mod(pkg, "blender.joints")
    order = _order(m.sheet.get("joints", []))
    with joints._batch(scene):
        for j in order:
            objs = [m.one(n) for n in j["parts"]]
            base = None
            if j.get("rides_on"):
                below = joints.find(scene, j["rides_on"])
                if below is None:
                    raise RuntimeError(f"joint '{j['name']}' rides on '{j['rides_on']}', which is not made")
                base = below.motion
            elif j.get("base"):
                base = m.one(j["base"])
            jt = joints.create(scene, j["kind"], objs, m.point(j["point"]), m.direction(j["direction"]),
                               name=j["name"], base=base)
            if jt.name != j["name"]:
                raise RuntimeError(f"joint '{j['name']}' got the name '{jt.name}'")
            lim = j.get("limits")
            if lim is not None:
                if j["kind"] == "ROTATE":
                    jt.rot_min, jt.rot_max = math.radians(lim[0]), math.radians(lim[1])
                else:
                    jt.slide_min, jt.slide_max = lim[0] / 1000.0, lim[1] / 1000.0
                jt.use_limits = True
        for j in order:
            if j.get("follows"):
                joints.set_follows(scene, joints.find(scene, j["name"]), j["follows"], ratio=float(j["ratio"]))
        size = joints._model_size(scene)
        for j in order:
            joints.apply_limits(joints.find(scene, j["name"]), size)
    joints.refresh_couplings(scene)
    return len(order)


def make_cylinders(pkg, scene, m: Model) -> int:
    cylinders = _mod(pkg, "blender.cylinders")
    for c in m.sheet.get("cylinders", []):
        barrel = [m.one(n) for n in c["barrel"]]
        rod = [m.one(n) for n in c["rod"]]
        bp, rp = c["barrel_pin"], c["rod_pin"]
        cylinders.create(scene, barrel, rod, (m.point(bp["point"]), m.direction(bp["axis"]), barrel[0]),
                         (m.point(rp["point"]), m.direction(rp["axis"]), rod[0]),
                         barrel_carrier=m.one(bp["carrier"]), rod_carrier=m.one(rp["carrier"]), name=c["name"])
    return len(m.sheet.get("cylinders", []))


def set_values(pkg, scene, values: dict) -> None:
    """Joint values as the sheet writes them (degrees, mm); joints not named go to 0 (their CAD place)."""
    joints = _mod(pkg, "blender.joints")
    for j in scene.fresing.joints:
        if j.follows:
            continue
        v = float(values.get(j.name, 0.0))
        joints.set_value(j, math.radians(v) if j.kind == "ROTATE" else v / 1000.0, use_limits=False)
    _mod(pkg, "blender.linkages").refresh_all(scene)
    _update()


def make_poses(pkg, scene, m: Model) -> int:
    states = _mod(pkg, "blender.states")
    for p in m.sheet.get("poses", []):
        set_values(pkg, scene, p["values"])
        states.save_pose(scene, p["name"])
    start = m.sheet.get("start_pose")
    if start:
        states.apply_pose(scene, start)
        _update()
    return len(m.sheet.get("poses", []))


def _update():
    import bpy
    bpy.context.view_layer.update()


def animation_item(scene, sheet: dict):
    a = sheet.get("animation") or {}
    return scene.fresing.animations.get(a.get("name", "")) if a else None


def make_animation(pkg, scene, m: Model):
    """The sheet's animation as 6 Animation steps; its camera frames every pose (a saved scene of the same name)."""
    spec = m.sheet.get("animation")
    if not spec:
        return None
    s = scene.fresing
    a = s.animations.add()
    a.name = spec["name"]
    a.fps = str(spec.get("fps", 25))
    a.tail = 0.0
    a.quality, a.out_resolution, a.out_format, a.video = "preview", "hd", "presentation", "MP4"
    for st in spec["steps"]:
        b = a.blocks.add()
        b.kind = st["kind"]
        b.start, b.duration = float(st["start"]), float(st["seconds"])
        b.easing = st.get("easing", "SMOOTH")
        b.name = st.get("label", st.get("pose", ""))
        if st["kind"] == "POSE":
            b.pose = st["pose"]
        elif st["kind"] in ("JOINT",):
            jt = s.joints[st["joint"]]
            b.joint = jt.name
            b.use_from = True
            if jt.kind == "ROTATE":
                b.to_angle = math.radians(st["to"])
            else:
                b.to_dist = st["to"] / 1000.0
    cam = frame_all_poses(pkg, scene, m, spec["name"])
    states = _mod(pkg, "blender.states")
    if m.sheet.get("start_pose"):
        states.apply_pose(scene, m.sheet["start_pose"])
    scene.camera = cam
    shot = states.save_shot(scene, spec["name"], camera=cam)
    a.start_shot = shot.name
    s.animations_index = list(s.animations).index(a)
    return a


def frame_all_poses(pkg, scene, m: Model, name: str, view: str = "ISO", margin: float = 1.08):
    """A camera that sees the model in every pose of the sheet (the moving clip must not leave the picture)."""
    import numpy as np
    build, cameras, states = (_mod(pkg, f"blender.{x}") for x in ("build", "cameras", "states"))
    pts = []
    parts = [o for o in build.iter_parts(scene) if o.type == "MESH"]
    for p in m.sheet.get("poses", []) or [None]:
        if p is not None:
            states.apply_pose(scene, p["name"])
            _update()
        mn, mx = build.world_bounds(parts)
        pts += [mn, mx]
    cam = cameras.add_camera(scene, view, name=name, points=np.array(pts, dtype=float), margin=margin)
    return cam


def build_animation(pkg, scene, m: Model) -> dict:
    animation = _mod(pkg, "blender.animation")
    a = animation_item(scene, m.sheet)
    if a is None:
        return {}
    s = scene.fresing
    s.animations_index = list(s.animations).index(a)
    r = animation.bake(scene, a)
    scene.frame_set(scene.frame_start)
    return r


def clash_rows(pkg, scene) -> tuple[int, list]:
    clash = _mod(pkg, "blender.clash")
    run = clash.check(scene)
    rows = [r for r in run.rows if r.kind == "CLASH"]
    return len(rows), [f"{r.a} × {r.b}: {r.depth * 1000:.1f} mm, frames {r.frame_from}–{r.frame_to}" for r in rows]


def make(pkg, scene, sheet: dict, check: bool = True, log=print) -> dict:
    """Joints, cylinders, poses, the animation (built) and its clash check on the imported model. Returns a summary."""
    t0 = time.time()
    m = Model(pkg, scene, sheet)
    out = {"model": sheet["model"]}
    out["hidden"] = hide_parts(pkg, scene, m)
    out["joints"] = make_joints(pkg, scene, m)
    out["cylinders"] = make_cylinders(pkg, scene, m)
    out["poses"] = make_poses(pkg, scene, m)
    log(f"  motion: {out['joints']} joints, {out['cylinders']} cylinders, {out['poses']} poses "
        f"({time.time() - t0:.0f} s)")
    a = make_animation(pkg, scene, m)
    if a is not None:
        t1 = time.time()
        r = build_animation(pkg, scene, m)
        out.update(animation=a.name, frames=int(r.get("frames", 0)), seconds=float(r.get("seconds", 0.0)))
        log(f"  animation '{a.name}': {out['frames']} frames, built in {time.time() - t1:.0f} s")
        if check:
            t1 = time.time()
            n, rows = clash_rows(pkg, scene)
            out["clash_rows"], out["clashes"] = n, rows[:20]
            log(f"  clash check: {n} clash rows in {time.time() - t1:.0f} s" + ("".join(f"\n    {r}" for r in rows[:10])))
    out["seconds_total"] = round(time.time() - t0, 1)
    return out
