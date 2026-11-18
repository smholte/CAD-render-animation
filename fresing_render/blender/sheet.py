"""The sheet reader (task 0112; moved into the app by task 0201): joints, cylinders, poses and the rest of a *sheet* on an
imported model, through the app's own functions – what a user does with the buttons.

A *sheet* says which sub-assemblies turn or slide about which axis, which joints follow others and by how much, where
the cylinders' pins are, the named poses and the animation: the render kit's ``projects/<model>.json`` (written by
``tools/make_site_projects.py``) and the ``rig`` of a lifting equipment file (task 0191). ``make(scene, sheet)`` does
on an imported model: joints (4 Motion > Joints, ``joints.create`` in one batch), couplings (``joints.set_follows``),
cylinders (``cylinders.create``), poses (``states.save_pose``), the animation of "Go to pose" steps (6 Animation),
Build (``animation.bake``) and the clash check (``clash.check``).

Sheet coordinates are the STEP file's, in mm; the model root's matrix takes them into the scene (the importer's up
axis and units). Parts are found by their CAD name (sub-assembly names in the sheet are unique in the model).

Task 0116 (the wind turbine) adds to a sheet: ``scene`` (the sea's water level, the floor), ``decals`` (texts and
signs on parts, 3 Looks > Decals), ``cameras`` (named cameras: a saved scene each, models.ini ``views`` may name them),
an animation ``camera``, JOINT steps that run side by side (constant speed: easing LINEAR), ``periods`` (a joint
whose value may differ by whole periods between the loop's ends: the rotor of a three-bladed turbine, 120°) and a
``check_animation`` that only the clash check of ``tools/make_site_projects.py --project`` builds.

Task 0201 (Lifting L4) places cranes as further models of a project: ``Model(scene, sheet, root=…, prefix="AT-100 · ")``
reads only that model's parts, and every joint, cylinder and pose it makes carries the prefix, so two cranes (even
two of one class) never share a name; ``set_values`` and poses then touch only that crane's joints.

The render kit (``site/render_kit/projects.py``) calls this module; so do the Lifting plan and the tests.
"""

from __future__ import annotations

import importlib
import json
import math
import os
import time

import numpy as np


def load(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _mod(name: str):
    """A module of this package by its name below the package ("blender.joints")."""
    return importlib.import_module(f"{__package__.rsplit('.', 1)[0]}.{name}")


class Model:
    """Lookups on the imported model: parts by CAD name, sheet points (mm) as scene points.

    ``root``: the model's root (several copies of one STEP in a project: name the one); else the one model whose file
    is the sheet's ``step``. ``prefix``: put before every joint, cylinder and pose name the sheet makes."""

    def __init__(self, scene, sheet: dict, root=None, prefix: str = ""):
        build = _mod("blender.build")
        self.scene, self.sheet, self.prefix = scene, sheet, prefix
        if root is None:
            want = os.path.basename(sheet["step"]).lower()
            roots = [r for r in build.model_roots(scene)
                     if os.path.basename(str(r.get(build.PROP_SOURCE, ""))).lower() == want]
            if len(roots) != 1:
                raise RuntimeError(f"{sheet['step']} is not (once) in the project")
            root = roots[0]
        self.root = root
        logic = _mod("blender.logic")
        self.by_name: dict = {}
        for ob in [self.root] + list(logic.descendants(self.root)):
            name = str(ob.get(build.PROP_NAME, ob.name))
            self.by_name.setdefault(name, []).append(ob)
            inst = str(ob.get(build.PROP_INSTANCE, "") or "")
            if inst and inst != name:            # task 0116: copies of one shape told apart by their occurrence
                self.by_name.setdefault(inst, []).append(ob)

    def jn(self, name: str | None) -> str | None:
        """The name a sheet's joint, cylinder or pose gets in the project."""
        return None if not name else self.prefix + name

    def joint_names(self) -> list:
        return [self.jn(j["name"]) for j in self.sheet.get("joints", [])]

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


def hide_parts(scene, m: Model) -> int:
    """Parts the sheet leaves out (hidden for good: the app's "excluded", 2 Structure); the sheet says why."""
    logic = _mod("blender.logic")
    objs = [m.one(h["part"]) for h in m.sheet.get("hide", [])]
    return logic.exclude(objs) if objs else 0


def make_joints(scene, m: Model) -> int:
    joints = _mod("blender.joints")
    order = _order(m.sheet.get("joints", []))
    with joints._batch(scene):
        for j in order:
            objs = [m.one(n) for n in j["parts"]]
            base = None
            if j.get("rides_on"):
                below = joints.find(scene, m.jn(j["rides_on"]))
                if below is None:
                    raise RuntimeError(f"joint '{j['name']}' rides on '{j['rides_on']}', which is not made")
                base = below.motion
            elif j.get("base"):
                base = m.one(j["base"])
            jt = joints.create(scene, j["kind"], objs, m.point(j["point"]), m.direction(j["direction"]),
                               name=m.jn(j["name"]), base=base, allow_empty=not objs)
            if j.get("role") and hasattr(jt, "role"):     # task 0203: an own crane's roles
                jt.role = j["role"]
            if jt.name != m.jn(j["name"]):
                raise RuntimeError(f"joint '{m.jn(j['name'])}' got the name '{jt.name}'")
            lim = j.get("limits")
            if lim is not None:
                if j["kind"] == "ROTATE":
                    jt.rot_min, jt.rot_max = math.radians(lim[0]), math.radians(lim[1])
                else:
                    jt.slide_min, jt.slide_max = lim[0] / 1000.0, lim[1] / 1000.0
                jt.use_limits = True
        for j in order:
            if j.get("follows"):
                joints.set_follows(scene, joints.find(scene, m.jn(j["name"])), m.jn(j["follows"]),
                                   ratio=float(j["ratio"]))
        size = joints._model_size(scene)
        for j in order:
            joints.apply_limits(joints.find(scene, m.jn(j["name"])), size)
    joints.refresh_couplings(scene)
    return len(order)


def make_cylinders(scene, m: Model) -> int:
    cylinders = _mod("blender.cylinders")
    for c in m.sheet.get("cylinders", []):
        barrel = [m.one(n) for n in c["barrel"]]
        rod = [m.one(n) for n in c["rod"]]
        bp, rp = c["barrel_pin"], c["rod_pin"]
        cylinders.create(scene, barrel, rod, (m.point(bp["point"]), m.direction(bp["axis"]), barrel[0]),
                         (m.point(rp["point"]), m.direction(rp["axis"]), rod[0]),
                         barrel_carrier=m.one(bp["carrier"]), rod_carrier=m.one(rp["carrier"]), name=m.jn(c["name"]))
    return len(m.sheet.get("cylinders", []))


def set_values(scene, values: dict, m: Model | None = None) -> None:
    """Joint values as the sheet writes them (degrees, mm); joints not named go to 0 (their CAD place). With a model
    that has a prefix: only that model's joints (``values`` by the sheet's names)."""
    joints = _mod("blender.joints")
    own = None
    if m is not None and m.prefix:
        own = {m.jn(j["name"]): j["name"] for j in m.sheet.get("joints", [])}
    for j in scene.fresing.joints:
        if j.follows:
            continue
        if own is not None:
            if j.name not in own:
                continue
            v = float(values.get(own[j.name], 0.0))
        else:
            v = float(values.get(j.name, 0.0))
        joints.set_value(j, math.radians(v) if j.kind == "ROTATE" else v / 1000.0, use_limits=False)
    _mod("blender.linkages").refresh_all(scene)
    _update()


def make_poses(scene, m: Model) -> int:
    """The sheet's poses. With a prefix each pose holds only that model's joints (no free moves): a crane's pose never
    moves another crane, and it is put back with ``apply_own_pose``."""
    states = _mod("blender.states")
    own = set(m.joint_names()) if m.prefix else None
    for p in m.sheet.get("poses", []):
        set_values(scene, p["values"], m)
        pose = states.save_pose(scene, m.jn(p["name"]))
        if own is not None:
            for i in reversed(range(len(pose.joints))):
                if pose.joints[i].joint not in own:
                    pose.joints.remove(i)
            pose.places.clear()
            pose.joints_only = True          # used from 4 Motion > Poses too, it leaves free moves (0209 row 12)
    start = m.sheet.get("start_pose")
    if start:
        if own is not None:
            apply_own_pose(scene, m.jn(start))
        else:
            states.apply_pose(scene, start)
        _update()
    return len(m.sheet.get("poses", []))


def apply_own_pose(scene, name: str) -> bool:
    """A model's own pose: its joints only, nothing else of the project moves (free moves stay)."""
    states = _mod("blender.states")
    pose = scene.fresing.poses.get(name)
    if pose is None:
        return False
    states.apply_pose_data(scene, pose, joints_only=True)
    _update()
    return True


def _update():
    import bpy
    bpy.context.view_layer.update()


def animation_item(scene, sheet: dict):
    a = sheet.get("animation") or {}
    return scene.fresing.animations.get(a.get("name", "")) if a else None


def make_animation(scene, m: Model, spec: dict | None = None):
    """The sheet's animation as 6 Animation steps; its camera frames every pose (a saved scene of the same name), or
    is the sheet camera the animation names."""
    spec = spec if spec is not None else m.sheet.get("animation")
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
    named = spec.get("camera")
    cam = sheet_camera(scene, m, named) if named else frame_all_poses(scene, m, spec["name"])
    states = _mod("blender.states")
    if m.sheet.get("start_pose"):
        states.apply_pose(scene, m.sheet["start_pose"])
    scene.camera = cam
    shot = states.save_shot(scene, spec["name"], camera=cam)
    a.start_shot = shot.name
    s.animations_index = list(s.animations).index(a)
    return a


def frame_all_poses(scene, m: Model, name: str, view: str = "ISO", margin: float = 1.15):
    """A camera that sees the model in every pose of the sheet (the moving clip must not leave the picture)."""
    import numpy as np
    build, cameras, states = (_mod(f"blender.{x}") for x in ("build", "cameras", "states"))
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


def build_animation(scene, m: Model) -> dict:
    animation = _mod("blender.animation")
    a = animation_item(scene, m.sheet)
    if a is None:
        return {}
    s = scene.fresing
    s.animations_index = list(s.animations).index(a)
    r = animation.bake(scene, a)
    scene.frame_set(scene.frame_start)
    return r


def axis_errors(scene, m: Model) -> tuple[float, float]:
    """(largest angle in degrees, largest offset in mm) between the built joints' axes and the sheet's (CAD pose)."""
    from mathutils import Vector
    joints = _mod("blender.joints")
    worst_a = worst_d = 0.0
    for j in m.sheet.get("joints", []):
        jt = joints.find(scene, m.jn(j["name"]))
        if jt is None or jt.frame is None:
            raise RuntimeError(f"joint '{j['name']}' was not made")
        w = joints.world_of(scene, jt.frame)
        z, o = (w.to_3x3() @ Vector((0.0, 0.0, 1.0))).normalized(), w.translation
        u, c = m.direction(j["direction"]), m.point(j["point"])
        worst_a = max(worst_a, math.degrees(math.acos(min(1.0, abs(z.dot(u))))))
        off = (o - c) - (o - c).dot(u) * u
        worst_d = max(worst_d, off.length * 1000.0)
    return worst_a, worst_d


def loop_gap(scene, periods: dict | None = None) -> float:
    """The largest difference of a joint's value between the first and the last frame (a loop closes: 0). A joint in
    ``periods`` (degrees or mm, as the sheet) may differ by whole periods."""
    joints = _mod("blender.joints")
    periods = periods or {}
    first, last = {}, {}
    for f, store in ((scene.frame_start, first), (scene.frame_end, last)):
        scene.frame_set(f)
        for j in scene.fresing.joints:
            store[j.name] = joints.get_value(j)
    scene.frame_set(scene.frame_start)

    def gap(k):
        d = abs(first[k] - last[k])
        jt = scene.fresing.joints[k]
        if k in periods:
            p = math.radians(periods[k]) if jt.kind == "ROTATE" else periods[k] / 1000.0
            d = abs(d - round(d / p) * p)
        return d
    return max((gap(k) for k in first), default=0.0)


def clash_rows(scene) -> tuple[int, list]:
    clash = _mod("blender.clash")
    run = clash.check(scene)
    rows = [r for r in run.rows if r.kind == "CLASH"]
    return len(rows), [f"{r.a} × {r.b}: {r.depth * 1000:.1f} mm, frames {r.frame_from}–{r.frame_to}" for r in rows]


def apply_scene(scene, m: Model) -> dict:
    """The sheet's scene settings: the sea's water level above the model's lowest point, the floor's gap."""
    s = scene.fresing
    sc = m.sheet.get("scene") or {}
    if "water_level_m" in sc:
        s.water_level = float(sc["water_level_m"])
    if "floor_offset_m" in sc:
        s.floor_offset = float(sc["floor_offset_m"])
    if "sea_depth_m" in sc:                      # task 0128: the app's seabed under the sea (0081)
        s.sea_depth = float(sc["sea_depth_m"])
    cut = sc.get("cutaway")
    if cut:                                      # the cut-away box over the seabed round a point, not behind a stern
        mn, mx = (np.asarray(v, float) for v in _mod("blender.surroundings")._model_box(scene))
        cx, cy = (float(v) for v in cut["centre_m"])
        length, width = float(cut["length_m"]), float(cut["width_m"])
        s.sea_cutaway, s.sea_cut_auto = True, False
        s.sea_cut_length, s.sea_cut_width = length, width
        # the box starts at the model's lowest x minus "from the stern" and runs towards -x: its front at cx + length/2
        s.sea_cut_start = float(mn[0]) - (cx + length / 2.0)
        s.sea_cut_side = cy - float(mn[1] + mx[1]) / 2.0
        if "ground" in cut:                      # task 0148: the cut goes on into the ground (a pile below the seabed)
            s.sea_cut_ground = bool(cut["ground"])
    return dict(sc)


def _look_at(eye, target):
    from mathutils import Matrix, Vector
    eye, target = Vector(eye), Vector(target)
    fwd = (target - eye).normalized()
    up = Vector((0.0, 0.0, 1.0))
    right = fwd.cross(up)
    if right.length < 1e-6:
        right = Vector((1.0, 0.0, 0.0))
    right.normalize()
    cam_up = right.cross(fwd)
    M = Matrix.Identity(4)
    for i in range(3):
        M[i][0], M[i][1], M[i][2], M[i][3] = right[i], cam_up[i], -fwd[i], eye[i]
    return M


def sheet_camera(scene, m: Model, name: str):
    """The sheet's camera of that name (made once): a camera of the app (5 Scene & Render) and a saved scene."""
    import bpy
    cameras, states = _mod("blender.cameras"), _mod("blender.states")
    spec = next((c for c in m.sheet.get("cameras", []) if c["name"] == name), None)
    if spec is None:
        raise RuntimeError(f"the sheet has no camera '{name}'")
    ob = bpy.data.objects.get(name)
    if ob is None or ob.type != "CAMERA":
        data = bpy.data.cameras.new(name)
        data.lens = float(spec.get("lens", 35.0))
        data.display_size = cameras.display_size(scene)
        ob = bpy.data.objects.new(name, data)
        ob["fr_camera"] = True
        ob[cameras.PROP_BLUR] = "NONE"
        cameras.collection(scene).objects.link(ob)
        ob.matrix_world = _look_at(m.point(spec["eye"]), m.point(spec["target"]))
        _update()
        cameras._see_far_enough(scene)
    scene.camera = ob
    if name not in scene.fresing.shots:
        states.save_shot(scene, name, camera=ob)
    return ob


def make_cameras(scene, m: Model) -> int:
    for c in m.sheet.get("cameras", []):
        sheet_camera(scene, m, c["name"])
    return len(m.sheet.get("cameras", []))


def _nearest_face(ob, point_world, normal_world):
    """(face index, point and normal in the object's coordinates) of the object's surface nearest the point."""
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    inv = ob.matrix_world.inverted()
    p = inv @ Vector(point_world)
    n = (ob.matrix_world.to_3x3().transposed() @ Vector(normal_world)).normalized()      # a normal, world -> object
    tree = BVHTree.FromObject(ob, _depsgraph(), deform=False)
    loc, nrm, face, dist = tree.find_nearest(p)
    if face is None:
        raise RuntimeError(f"no surface on '{ob.name}'")
    return face, loc, n, dist


def _depsgraph():
    import bpy
    return bpy.context.evaluated_depsgraph_get()


def make_decals(scene, m: Model) -> int:
    """Texts and signs of the sheet on its parts (3 Looks > Decals), each where the sheet says, upright."""
    decals = _mod("blender.decals")
    made = 0
    for d in m.sheet.get("decals", []):
        ob = m.one(d["part"])
        face, loc, n, dist = _nearest_face(ob, m.point(d["point"]), m.direction(d["normal"]))
        if dist > 0.05:
            raise RuntimeError(f"decal '{d.get('text') or d.get('sticker')}': {dist * 1000:.0f} mm off '{d['part']}'")
        up = m.direction(d["up"]) if d.get("up") else None
        it = decals.add(ob, face, loc, n, d["kind"], text=d.get("text", ""), sticker=d.get("sticker", "CE"),
                        only_copy=True, view_up=up)
        w = float(d.get("width_mm", 0.0)) / 1000.0
        if w > 0:
            it.width = w
        for attr in ("ink_color", "field_color"):
            if d.get(attr):
                setattr(it, attr, d[attr])
        decals.rebuild(it)
        made += 1
    return made


def check_extra(scene, m: Model, log=print) -> tuple[int, list]:
    """The sheet's check animation (every joint through its range) built and clash-checked, then taken away."""
    spec = m.sheet.get("check_animation")
    if not spec:
        return 0, []
    s = scene.fresing
    animation = _mod("blender.animation")
    a = make_animation(scene, m, {**spec, "camera": spec.get("camera") or (m.sheet.get("animation") or {})
                                       .get("camera")})
    s.animations_index = list(s.animations).index(a)
    animation.bake(scene, a)
    scene.frame_set(scene.frame_start)
    n, rows = clash_rows(scene)
    log(f"  check animation '{a.name}': {n} clash rows" + "".join(f"\n    {r}" for r in rows[:10]))
    animation.clear_keys(scene)
    s.animations.remove(list(s.animations).index(a))
    shot = s.shots.find(spec["name"])
    if shot >= 0:
        s.shots.remove(shot)
    return n, rows


def make(scene, sheet: dict, check: bool = True, log=print, check_extra_animation: bool = False) -> dict:
    """Joints, cylinders, poses, the animation (built) and its clash check on the imported model. Returns a summary."""
    t0 = time.time()
    m = Model(scene, sheet)
    out = {"model": sheet["model"]}
    out["hidden"] = hide_parts(scene, m)
    out["joints"] = make_joints(scene, m)
    out["axis_error_deg"], out["axis_error_mm"] = (round(x, 4) for x in axis_errors(scene, m))
    out["cylinders"] = make_cylinders(scene, m)
    out["poses"] = make_poses(scene, m)
    log(f"  motion: {out['joints']} joints, {out['cylinders']} cylinders, {out['poses']} poses "
        f"({time.time() - t0:.0f} s)")
    if sheet.get("scene"):
        out["scene"] = apply_scene(scene, m)
    if sheet.get("decals"):
        out["decals"] = make_decals(scene, m)
    if sheet.get("cameras"):
        out["cameras"] = make_cameras(scene, m)
    if check and check_extra_animation and sheet.get("check_animation"):
        t1 = time.time()
        out["check_clash_rows"], rows = check_extra(scene, m, log)
        out["check_clashes"] = rows[:20]
        log(f"  (check animation in {time.time() - t1:.0f} s)")
        states = _mod("blender.states")
        if sheet.get("start_pose"):
            states.apply_pose(scene, sheet["start_pose"])
            _update()
    a = make_animation(scene, m)
    if a is not None:
        t1 = time.time()
        r = build_animation(scene, m)
        out.update(animation=a.name, frames=int(r.get("frames", 0)), seconds=float(r.get("seconds", 0.0)))
        if (m.sheet.get("animation") or {}).get("loop"):
            out["loop_gap"] = round(loop_gap(scene, (m.sheet.get("animation") or {}).get("periods")), 6)
        log(f"  animation '{a.name}': {out['frames']} frames, built in {time.time() - t1:.0f} s")
        if check:
            t1 = time.time()
            n, rows = clash_rows(scene)
            out["clash_rows"], out["clashes"] = n, rows[:20]
            log(f"  clash check: {n} clash rows in {time.time() - t1:.0f} s" + ("".join(f"\n    {r}" for r in rows[:10])))
    out["seconds_total"] = round(time.time() - t0, 1)
    return out
