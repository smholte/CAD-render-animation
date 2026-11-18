"""The lifting plan in the project (task 0201, Lifting lane L4): 8 Lifting plan.

* **Equipment.** The library (``core/lifting_library``: the built-in sample cranes and the user's own items in the
  library folder "Lifting equipment") and placing a crane: its STEP comes in as a further model of the project (the
  importer's normal path, Normal quality), is rigged from its file's ``rig`` through the app's sheet reader
  (``blender/sheet.py``: joints, cylinders, poses; crawler tracks; the hoist rope as a cable that ends on the hook
  block) and is put where the user clicks, turned by the heading. Every joint, cylinder, pose, track and cable carries
  the crane's name ("AT-100 · Slew"), so two cranes – even two of one class – never share a name. A crane's poses
  move only its own joints.
* **Load.** A load group of parts (or sub-assemblies), or a box; its mass entered (with its source) or worked out from
  the parts' solid volumes x a density per material group (``core/lifting_load``); a contingency factor; the CoG
  marker – an empty "FR CoG <load>" that rides on the load's first part, drawn as the CoG symbol on top of everything;
  moved by hand it is marked "set by hand" until Back to computed.
* **Hook & capacity.** Hook to here (``core/lifting_reach.hook_to``) and the live readout (``readout``): radius, hook
  height, boom, the chart row, capacity, gross load, crane use with the plan's status word. The readout is cached on a
  cheap key (the joints' values, the crane's place, the set-up and the load): the side panel's draw does no work.

Units: SI inside (m, kg); the panel shows t and m. The plan's words only (study 0180 section 8, ``lifting.FORBIDDEN_WORDS``).
"""

from __future__ import annotations

import math
import os
import time

import bpy
import numpy as np
from mathutils import Matrix, Vector

from ..core import lifting, lifting_library as LL, lifting_load as LD, lifting_reach as LR
from . import build, joints, logic

SEP = " · "                    # crane name + SEP + the sheet's joint name
MARKER_PREFIX = "FR CoG "
BOX_PREFIX = "FR load box "
ENV_UNDERSTOOD = "FRESING_LIFTING_UNDERSTOOD"     # tests and the app's own projects: no first-use dialog
_SKIP_FIRST_USE = [False]


# ---------------------------------------------------------------------------------------------------------------------
# first use

def understood(background: bool | None = None) -> bool:
    """The planning-aid line was accepted once (per user), or the dialog never shows here (background, tests, the PC
    check, the tour). ``background``: for tests (None = Blender's own)."""
    bg = bpy.app.background if background is None else background
    if bg or _SKIP_FIRST_USE[0] or os.environ.get(ENV_UNDERSTOOD):
        return True
    try:
        from . import tour
        if tour.is_tour(bpy.context.scene):
            return True
    except Exception:  # noqa: BLE001
        pass
    from . import prefs
    p = prefs.get()
    return True if p is None else bool(p.lifting_understood)


def set_understood(on: bool = True) -> None:
    from . import prefs
    p = prefs.get()
    if p is not None:
        p.lifting_understood = on
        try:
            if not bpy.context.preferences.use_preferences_save and not bpy.app.background:
                bpy.ops.wm.save_userpref()
        except Exception:  # noqa: BLE001 - the tick still holds for this session
            pass


# ---------------------------------------------------------------------------------------------------------------------
# the library

_LIB: dict = {"items": None, "folder": None, "at": 0.0}
_ITEM: dict = {}                 # path -> (mtime, Item)
_RIG: dict = {}                  # path -> (mtime, Rig or ReachError text)
_CHARTS: dict = {}               # path -> (mtime, charts)


def user_folder() -> str:
    from . import prefs
    try:
        return prefs.library_dir("Lifting equipment")
    except Exception:  # noqa: BLE001
        return ""


def library(force: bool = False) -> list:
    """Every item: the user's own first, then the built-ins (``list_items``), read once until Refresh."""
    folder = user_folder()
    if force or _LIB["items"] is None or _LIB["folder"] != folder:
        _LIB.update(items=LL.list_items(folder or None), folder=folder, at=time.time())
    return _LIB["items"]


def by_kind(items) -> list:
    """(heading, [items]) in the panel's order: built-ins by kind and class, then the user's own."""
    kinds = {"mobile_crane": "Mobile cranes", "crawler_crane": "Crawler cranes", "knuckle_boom_crane": "Knuckle-boom "
             "cranes"}
    out = []
    for k, title in kinds.items():
        got = [i for i in items if i.builtin and i.kind == k]
        if got:
            out.append((title + " (built-in samples)", sorted(got, key=lambda i: _class_order(i.cls))))
    other = [i for i in items if i.builtin and i.kind not in kinds]
    if other:
        out.append(("Other built-ins", other))
    own = [i for i in items if not i.builtin]
    if own:
        out.append(("Your own equipment", own))
    return out


def _class_order(cls: str):
    head, _, num = cls.partition("-")
    try:
        return (head, float(num))
    except ValueError:
        return (head, 0.0)


def _mtime(path: str) -> float:
    try:
        return os.path.getmtime(path)
    except OSError:
        return -1.0


def item_at(path: str):
    """The equipment item of a path (folder or .json), read again when its file changed."""
    key = os.path.normpath(path)
    got = _ITEM.get(key)
    if got is not None and got[0] == _mtime(got[1].path or path):
        return got[1]
    it = LL.read_item(path)
    _ITEM[key] = (_mtime(it.path or path), it)
    _RIG.pop(key, None)
    _CHARTS.pop(key, None)
    return it


def path_of(crane) -> str:
    """The crane's equipment file. A built-in found again in this app's own folder when the project was made where
    the app is installed elsewhere (another PC or user)."""
    p = crane.item_path
    if crane.builtin and not os.path.exists(p):
        parts = os.path.normpath(p).replace("\\", "/").split("/")
        for i in range(len(parts) - 1, 0, -1):
            if parts[i] == "lifting" and parts[i - 1] == "data":
                cand = os.path.join(LL.BUILTIN_DIR, *parts[i + 1:])
                if os.path.exists(cand):
                    return cand
                break
    return p


def rig_of(crane) -> LR.Rig:
    path = path_of(crane)
    key = os.path.normpath(path)
    it = item_at(path)
    if not it.ok:
        raise LR.ReachError(file_changed(crane) or it.problems[0])
    got = _RIG.get(key)
    if got is None:
        try:
            got = LR.Rig(it.data)
        except LR.ReachError as exc:
            got = str(exc)
        _RIG[key] = got
    if isinstance(got, str):
        raise LR.ReachError(got)
    return got


def charts_of(crane) -> list:
    path = path_of(crane)
    key = os.path.normpath(path)
    got = _CHARTS.get(key)
    if got is None:
        try:
            got = LL.charts_of(item_at(path))
        except LL.LibraryError:
            got = []
        _CHARTS[key] = got
    return got


def hook_block_kg(crane) -> float:
    try:
        blocks = LL.hook_blocks_of(item_at(path_of(crane)))
    except LL.LibraryError:
        return 0.0
    return float(blocks[0][1]) if blocks else 0.0


def file_changed(crane) -> str:
    """'' or the sentence that the crane's file changed since it was placed (charts) or is gone."""
    path = path_of(crane)
    if not os.path.exists(path):
        return f"The equipment file of {crane.name} is gone ({crane.item_path}): its charts cannot be read."
    it = item_at(path)
    if not it.ok:
        return f"The equipment file of {crane.name} has a problem: {it.problems[0]}"
    try:
        h = LL.chart_hash(it)
    except LL.LibraryError as exc:
        return str(exc)
    if crane.chart_hash and h != crane.chart_hash:
        return (f"The charts in {os.path.basename(it.path)} changed since {crane.name} was placed: the new charts are "
                "used. Check the plan again.")
    return ""


# ---------------------------------------------------------------------------------------------------------------------
# cranes in the project

def plan(scene):
    return scene.fresing.lifting


def active_crane(scene):
    L = plan(scene)
    if 0 <= L.crane_index < len(L.cranes):
        c = L.cranes[L.crane_index]
        return c if c.root is not None else None
    return None


def active_load(scene):
    L = plan(scene)
    if 0 <= L.load_index < len(L.loads):
        return L.loads[L.load_index]
    return None


def prefix(crane) -> str:
    return crane.name + SEP


def sheet_of(data: dict) -> dict:
    r = data["rig"]
    return {"model": data.get("class", data.get("name", "")), "step": r["step"], "joints": r["joints"],
            "cylinders": r.get("cylinders", []), "poses": r.get("poses", []), "start_pose": r.get("start_pose", "")}


def unique_name(scene, base: str) -> str:
    taken = {c.name for c in plan(scene).cranes} | {j.name.split(SEP)[0] for j in scene.fresing.joints if SEP in j.name}
    if base not in taken:
        return base
    n = 2
    while f"{base} {n}" in taken:
        n += 1
    return f"{base} {n}"


def import_model(context, step: str, quality: str = "normal"):
    """The STEP as a further model of the project (the importer's normal path), waiting for it: the model's root.
    The first model of a project also gets the camera, render settings and world of a new import."""
    from ..importer.runner import ImportJob
    from .ops_import import cache_root, finish_import
    scene = context.scene
    first = not build.model_roots(scene)
    job = ImportJob(step, quality, cache_root())
    if not job.cached:
        job.start()
        while not job.poll():
            time.sleep(0.1)
    if job.error:
        raise RuntimeError(f"The crane's model could not be read: {job.error}")
    return finish_cache(context, job.cache_dir, first)


def finish_cache(context, cache_dir: str, first: bool):
    from .ops_import import finish_import
    scene = context.scene
    before = {g.name for g in scene.fresing.groups}
    if first:
        root = finish_import(context, cache_dir, "Z")
    else:
        root = build.build(cache_dir)
        logic.set_up_axis(root, "Z")
        logic.lock_all(scene)
        logic.apply_rules(scene)
        logic.rebuild_tree(scene)
        logic.update_bounds(scene)
    root["fr_quality"] = "normal"
    root["fr_lift_groups"] = sorted({g.name for g in scene.fresing.groups} - before)   # Remove takes them again
    return root


def rig_model(context, root, item, name: str = ""):
    """Rig an imported crane model from its equipment file and add it to the plan: the crane item."""
    from . import sheet
    scene = context.scene
    data = item.data
    name = unique_name(scene, name or item.name)
    groups_before = {g.name for g in scene.fresing.groups}
    m = sheet.Model(scene, sheet_of(data), root=root, prefix=name + SEP)
    root["fr_lifting"] = name
    hb = m.by_name.get((data["rig"].get("hook") or {}).get("assembly", ""), [])
    if hb:                                     # the hook block's place in the CAD pose, in the model's frame
        _update()
        R = np.array(root.matrix_world)
        hb[0]["fr_lift_cad"] = (np.linalg.inv(R) @ np.array(hb[0].matrix_world)).ravel().tolist()
    sheet.make_joints(scene, m)
    sheet.make_cylinders(scene, m)
    _tracks(scene, m, data)
    sheet.set_values(scene, {}, m)
    sheet.make_poses(scene, m)
    try:
        _rope(scene, m, data)
    except Exception as exc:  # noqa: BLE001 - a rope that cannot follow must not stop the placing
        print("Fresing Render (lifting): the hoist rope stays as drawn:", exc)
    made = {g.name for g in scene.fresing.groups} - groups_before        # the rope's look group ("Power cables" …)
    root["fr_lift_groups"] = sorted(set(root.get("fr_lift_groups", [])) | made)
    L = plan(scene)
    c = L.cranes.add()
    c.name = name
    c.item_path = item.path or item.folder
    c.item_name = item.name
    c.builtin = bool(item.builtin)
    try:
        c.chart_hash = LL.chart_hash(item)
    except LL.LibraryError:
        c.chart_hash = ""
    c.root = root
    vals = LR.setup_values(charts_of(c))
    if vals.get("counterweight"):
        c.counterweight = lifting.tonnes(vals["counterweight"][-1])     # the models carry their largest
    c.pose = data["rig"].get("start_pose", "")
    L.crane_index = len(L.cranes) - 1
    _update()
    return c


def _tracks(scene, m, data) -> None:
    from . import tracks
    for t in data["rig"].get("tracks") or []:
        wheels = [m.by_name[w][0] for w in t["wheels"]]
        tracks.add(scene, wheels, m.by_name[t["link"]][0], [m.by_name[r][0] for r in t["riders"]],
                   joint=m.jn(t["joint"]), name=m.jn(t["name"]))


def _rope(scene, m, data) -> None:
    """The hoist rope as a cable whose end stays on the hook block (4 Motion > Cables and paths)."""
    from . import paths
    for cab in data["rig"].get("cables") or []:
        part = m.by_name.get(cab["part"], [None])[0]
        block = m.by_name.get(cab.get("end_on", ""), [None])[0]
        if part is None or block is None:
            continue
        hb = block if block.type == "MESH" else next((o for o in logic.descendants(block) if o.type == "MESH"), block)
        it = paths.add_cable(scene, m.jn(cab["name"]))
        paths.read_cad(scene, it, part)
        it = paths.find(scene, m.jn(cab["name"]))
        sh = paths.shape_now(scene, it)
        c = np.array(hb.matrix_world.translation)
        end = "a" if np.linalg.norm(sh[0] - c) < np.linalg.norm(sh[-1] - c) else "b"
        paths.set_end(scene, it, end, hb)


def place_at(crane, location, heading: float) -> None:
    """Put the crane's model with its slew axis on ``location`` (world, m), turned by ``heading`` (radians)."""
    root = crane.root
    s = float(np.linalg.norm(np.array(root.matrix_world)[:3, 0]))
    root.matrix_world = Matrix.Translation(Vector(location)) @ Matrix.Rotation(heading, 4, "Z") @ Matrix.Scale(s, 4)
    _update()
    try:
        from . import paths
        paths.refresh(bpy.context.scene, force=True)
    except Exception:  # noqa: BLE001
        pass


def heading_of(crane) -> float:
    M = np.array(crane.root.matrix_world)
    return float(math.atan2(M[1, 0], M[0, 0]))


def place(context, path: str, location=(0.0, 0.0, 0.0), heading: float = 0.0, name: str = ""):
    """Import, rig and place a library item (no window needed): the crane item."""
    item = item_at(path)
    if not item.ok:
        raise RuntimeError(item.problems[0])
    if not item.model or not item.model.lower().endswith((".step", ".stp")):
        raise RuntimeError(f"{item.name}: no STEP model next to its file.")
    try:
        LR.Rig(item.data)
    except LR.ReachError as exc:
        raise RuntimeError(f"{item.name}: {exc}") from exc
    root = import_model(context, item.model)
    c = rig_model(context, root, item, name)
    place_at(c, location, heading)
    return c


def crane_of_root(scene, root):
    for c in plan(scene).cranes:
        if c.root == root:
            return c
    return None


def own_joints(scene, crane) -> list:
    p = prefix(crane)
    return [j for j in scene.fresing.joints if j.name.startswith(p)]


def remove(scene, crane) -> dict:
    """Take a placed crane out of the project: its cables, tracks, cylinders, poses, joints, model and plan data."""
    from . import animation, cylinders, paths, tracks
    s = scene.fresing
    name, p = crane.name, prefix(crane)
    root = crane.root
    gone = {"cables": 0, "tracks": 0, "cylinders": 0, "poses": 0, "joints": 0, "objects": 0}
    if animation.has_keys(scene):
        animation.clear_keys(scene)
    for i in reversed(range(len(s.cables))):
        if s.cables[i].name.startswith(p):
            paths.remove(scene, i)
            gone["cables"] += 1
    for i in reversed(range(len(s.tracks))):
        if s.tracks[i].name.startswith(p):
            tracks.remove(scene, i)
            gone["tracks"] += 1
    for n in [c.name for c in s.cylinders if c.name.startswith(p)]:      # names: removing one changes the list
        cylinders.remove(scene, cylinders.find(scene, n))
        gone["cylinders"] += 1
    for i in reversed(range(len(s.poses))):
        if s.poses[i].name.startswith(p):
            s.poses.remove(i)
            gone["poses"] += 1
    s.poses_index = max(0, min(s.poses_index, len(s.poses) - 1))
    # the joints: their empties go with the model; riders first so nothing is moved back onto a joint that is gone
    names = [j.name for j in s.joints if j.name.startswith(p)]
    for n in sorted(names, key=lambda n: -joints.depth(scene, joints.find(scene, n))):
        j = joints.find(scene, n)
        for ob in (j.motion, j.frame):
            if ob is not None:
                bpy.data.objects.remove(ob, do_unlink=True)
        idx = next(i for i, x in enumerate(s.joints) if x.name == n)
        s.joints.remove(idx)
        gone["joints"] += 1
    s.joints_index = max(0, min(s.joints_index, len(s.joints) - 1))
    joints.refresh_couplings(scene)
    if root is not None:
        obs = [root] + list(logic.descendants(root))
        meshes = {o.data for o in obs if o.type == "MESH" and o.data is not None}
        colls = {c for o in obs for c in o.users_collection if c != scene.collection}
        mats = {m for o in obs if o.type == "MESH" for m in o.data.materials if m is not None}
        mats |= {sl.material for o in obs for sl in o.material_slots if sl.material is not None}
        added = list(root.get("fr_lift_groups", []))
        for o in obs:
            try:
                bpy.data.objects.remove(o, do_unlink=True)
                gone["objects"] += 1
            except ReferenceError:
                pass
        for me in meshes:
            try:
                if me.users == 0:
                    bpy.data.meshes.remove(me)
            except ReferenceError:
                pass
        used = {str(o.get(build.PROP_GROUP, "")) for o in scene.objects}
        for g in added:                            # the Looks groups only its parts had
            i = scene.fresing.groups.find(g)
            if i >= 0 and g not in used:
                scene.fresing.groups.remove(i)
                m = bpy.data.materials.get(g)
                if m is not None:
                    mats.add(m)
        scene.fresing.groups_index = max(0, min(scene.fresing.groups_index, len(scene.fresing.groups) - 1))
        for m in mats:
            try:
                if m.users == 0:
                    bpy.data.materials.remove(m)
            except ReferenceError:
                pass
        for coll in colls:                         # the model's own collection, when nothing else is in it
            try:
                if not coll.objects and not coll.children:
                    bpy.data.collections.remove(coll)
            except ReferenceError:
                pass
    from . import flex
    col = bpy.data.collections.get(flex.COLLECTION)     # made by the hoist rope / tracks; made again when needed
    if col is not None and not col.all_objects and not col.children:
        bpy.data.collections.remove(col)
    L = plan(scene)
    idx = next(i for i, c in enumerate(L.cranes) if c.name == name)
    L.cranes.remove(idx)
    L.crane_index = max(0, min(L.crane_index, len(L.cranes) - 1))
    logic.rebuild_tree(scene)
    logic.update_bounds(scene)
    forget()
    _update()
    return gone


def pose_names(crane) -> list:
    try:
        return [p["name"] for p in item_at(path_of(crane)).data["rig"].get("poses", [])]
    except Exception:  # noqa: BLE001
        return []


def apply_pose(scene, crane, name: str) -> bool:
    from . import sheet
    ok = sheet.apply_own_pose(scene, prefix(crane) + name)
    if ok:
        crane.pose = name
        _after_move(scene)
    return ok


def values(scene, crane) -> dict:
    """The crane's driven joints' values as its file writes them (degrees, mm), by the file's names."""
    p = prefix(crane)
    out = {}
    for j in scene.fresing.joints:
        if j.name.startswith(p) and not j.follows:
            v = joints.get_value(j)
            out[j.name[len(p):]] = math.degrees(v) if j.kind == "ROTATE" else v * 1000.0
    return out


def set_values(scene, crane, vals: dict) -> None:
    p = prefix(crane)
    for k, v in vals.items():
        j = joints.find(scene, p + k)
        if j is None or j.follows:
            continue
        joints.set_value(j, math.radians(v) if j.kind == "ROTATE" else v / 1000.0, use_limits=False)
    _after_move(scene)


def _after_move(scene) -> None:
    from . import linkages
    linkages.refresh_all(scene)
    _update()
    try:
        from . import paths
        paths.refresh(scene, force=True)
    except Exception:  # noqa: BLE001
        pass
    scene.fresing.bounds_valid = False


def to_model(crane, world) -> np.ndarray:
    """A world point (m) in the crane's model frame (mm)."""
    R = np.array(crane.root.matrix_world)
    return (np.linalg.inv(R) @ np.r_[np.asarray(world, float), 1.0])[:3] * 1000.0


def to_world(crane, p_mm) -> np.ndarray:
    R = np.array(crane.root.matrix_world)
    return (R @ np.r_[np.asarray(p_mm, float) / 1000.0, 1.0])[:3]


def hook_world(scene, crane) -> np.ndarray:
    return to_world(crane, rig_of(crane).hook(values(scene, crane)))


def setup(scene, crane) -> dict:
    """The set-up the chart is picked for: counterweight (kg) and outrigger spread (m: from the pose, or typed)."""
    out = {"counterweight": lifting.kg(crane.counterweight)}
    if crane.spread_from_pose:
        try:
            sp = LR.outrigger_spread(item_at(path_of(crane)).data, values(scene, crane))
        except Exception:  # noqa: BLE001
            sp = None
        if sp is not None:
            out["outriggers"] = sp
    else:
        out["outriggers"] = float(crane.outriggers)
    return out


def hook_to(scene, crane, world_point, load=None) -> LR.Answer:
    """Put the hook (plumb) on a world point: the answer; the crane moves only when it is ok."""
    rig = rig_of(crane)
    m = load_mass(scene, load) if load is not None else (0.0, "")
    contingency = float(load.contingency) if load is not None else 1.0
    a = LR.hook_to(rig, to_model(crane, world_point), values(scene, crane), charts_of(crane), setup(scene, crane),
                   load_kg=m[0] * contingency, hook_block_kg=hook_block_kg(crane))
    if a.ok:
        set_values(scene, crane, a.values)
        crane.pose = ""                            # no longer one of the file's poses
        msg = f"Hook to here: radius {a.radius:.2f} m, hook at {a.height:.2f} m, boom {a.boom:.2f} m"
        if a.use is not None:
            msg += f", crane use {a.use * 100:.0f} %"
        plan(scene).message = msg + "."
    else:
        plan(scene).message = a.reason
    return a


# ---------------------------------------------------------------------------------------------------------------------
# the readout (cached: the panel's draw only builds the key)

_READ: dict = {}


def _key(scene, crane, load):
    vals = tuple(sorted((k, round(v, 4)) for k, v in values(scene, crane).items()))
    R = tuple(round(x, 6) for row in crane.root.matrix_world for x in row)
    st = (round(crane.counterweight, 6), crane.spread_from_pose, round(crane.outriggers, 6), crane.item_path)
    ld = None
    if load is not None:
        ld = (load.name, load.mass_mode, round(load.mass_t, 6), round(load.contingency, 6),
              round(load.volume_mass, 3), load.source)
    return (crane.name, vals, R, st, ld, _mtime(item_at(path_of(crane)).path or path_of(crane)))


def readout(scene, crane, load=None) -> LR.Readout | str:
    """The crane's live readout, or the reason there is none (a sentence)."""
    try:
        key = _key(scene, crane, load)
    except Exception as exc:  # noqa: BLE001
        return str(exc)
    got = _READ.get(crane.name)
    if got is not None and got[0] == key:
        return got[1]
    try:
        rig = rig_of(crane)
        m = load_mass(scene, load)[0] if load is not None else 0.0
        out = LR.readout(rig, values(scene, crane), charts_of(crane), setup(scene, crane), load_kg=m,
                         contingency=float(load.contingency) if load is not None else 1.0,
                         hook_block_kg=hook_block_kg(crane))
    except LR.ReachError as exc:
        out = str(exc)
    _READ[crane.name] = (key, out)
    return out


def forget() -> None:
    _READ.clear()
    _SOLID.clear()
    _ITEM.clear()
    _RIG.clear()
    _CHARTS.clear()


# ---------------------------------------------------------------------------------------------------------------------
# loads

_SOLID: dict = {}       # mesh session uid -> (polygon count, Solid in the mesh's coordinates)


def load_parts(load) -> list:
    """The mesh parts of a load (sub-assemblies opened up), each once."""
    if load.kind == "BOX":
        return [load.box] if load.box is not None else []
    out, seen = [], set()
    for r in load.parts:
        ob = r.obj
        if ob is None:
            continue
        for o in [ob] + list(logic.descendants(ob)):
            if o.type == "MESH" and o.name not in seen and o.get(build.PROP_KIND) in ("part", None):
                seen.add(o.name)
                out.append(o)
    return out


def load_of_object(scene, ob):
    """The load a part (or sub-assembly) is in, or None."""
    names = {o.name for o in [ob] + list(logic.descendants(ob))}
    up = ob
    while up is not None:
        names.add(up.name)
        up = build.logical_parent(up)
    for ld in plan(scene).loads:
        for r in ld.parts:
            if r.obj is not None and (r.obj.name in names or any(o.name in names for o in logic.descendants(r.obj))):
                return ld
    return None


def _solid_of(ob) -> LD.Solid:
    me = ob.data
    key = getattr(me, "session_uid", id(me))
    got = _SOLID.get(key)
    if got is not None and got[0] == len(me.polygons):
        return got[1]
    me.calc_loop_triangles()
    n = len(me.loop_triangles)
    tris = np.zeros(n * 3, np.int64)
    me.loop_triangles.foreach_get("vertices", tris)
    pts = np.zeros(len(me.vertices) * 3)
    me.vertices.foreach_get("co", pts)
    sol = LD.solid(pts.reshape(-1, 3), tris.reshape(-1, 3))
    _SOLID[key] = (len(me.polygons), sol)
    return sol


def _group_material(scene, ob) -> tuple[str, str]:
    g = str(ob.get(build.PROP_GROUP, "") or "")
    grp = scene.fresing.groups.get(g) if g else None
    return (g or "(no group)"), (grp.material if grp is not None else "")


def compute(scene, load) -> dict:
    """Volume, mass by volume x density and the CoG of the load's parts (world), and which parts are not closed."""
    parts = load_parts(load)
    items, vol, open_parts = [], 0.0, []
    dens = {d.name: d.density for d in load.densities}
    for ob in parts:
        M = np.array(ob.matrix_world)
        det = abs(float(np.linalg.det(M[:3, :3])))
        if load.kind == "BOX":
            sol = _solid_of(ob)
            v, c = sol.volume * det, (M @ np.r_[sol.centroid, 1.0])[:3]
            items.append((v, c, "(box)"))
            vol += v
            continue
        sol = _solid_of(ob)
        if not sol.closed:
            open_parts.append(str(ob.get(build.PROP_NAME, ob.name)))
            corners = np.array([list(v) for v in ob.bound_box])
            lo, hi = corners.min(axis=0), corners.max(axis=0)
            sol = LD.box_solid(lo, hi)
        v = sol.volume * det
        c = (M @ np.r_[sol.centroid, 1.0])[:3]
        g, mat = _group_material(scene, ob)
        if g not in dens:
            d = load.densities.add()
            d.name = g
            d["density"] = LD.density_of(mat)
            dens[g] = d.density
        items.append((v * dens[g], c, g))
        vol += v
    if load.kind == "BOX":
        mass, cog = (lifting.kg(load.mass_t), items[0][1]) if items else (0.0, np.zeros(3))
    else:
        mass, cog = LD.combine([(m, c) for m, c, _g in items])
    return {"volume": vol, "mass": mass, "cog": cog, "open": open_parts, "parts": len(parts)}


def refresh_load(scene, load) -> None:
    """Work the load out again and put the computed CoG (a marker set by hand stays where it is)."""
    _update()                              # places of parts and boxes just made or moved
    by_hand = cog_by_hand(load)
    r = compute(scene, load)
    load.volume = r["volume"]
    load.volume_mass = r["mass"] if load.kind == "PARTS" else lifting.kg(load.mass_t)
    load.open_parts = ", ".join(r["open"][:20]) + (f" and {len(r['open']) - 20} more" if len(r["open"]) > 20 else "")
    carrier = load_parts(load)[0] if load_parts(load) else None
    load.carrier = carrier
    if carrier is not None:
        Mi = np.linalg.inv(np.array(carrier.matrix_world))
        load.cog_local = tuple((Mi @ np.r_[r["cog"], 1.0])[:3])
    mk = ensure_marker(scene, load)
    if mk is not None and not by_hand:
        mk.location = Vector(load.cog_local)
        mk["fr_cog_auto"] = list(load.cog_local)
    _READ.clear()


def ensure_marker(scene, load):
    """The CoG marker: an empty that rides on the load's first part (it moves with the load)."""
    if load.carrier is None:
        return None
    mk = load.marker
    if mk is None or mk.name not in bpy.data.objects:
        mk = bpy.data.objects.new(MARKER_PREFIX + load.name, None)
        mk.empty_display_type = "SPHERE"
        mk.empty_display_size = 0.05
        mk["fr_cog"] = load.name
        mk.hide_render = True
        coll = load.carrier.users_collection[0] if load.carrier.users_collection else scene.collection
        coll.objects.link(mk)
        load.marker = mk
    if mk.parent != load.carrier:
        mk.parent = load.carrier
        mk.matrix_parent_inverse = Matrix.Identity(4)
    return mk


def cog_by_hand(load) -> bool:
    mk = load.marker
    if mk is None or mk.name not in bpy.data.objects:
        return False
    auto = mk.get("fr_cog_auto")
    if auto is None:
        return False
    return (Vector(mk.location) - Vector(tuple(auto))).length > 1e-6


def back_to_computed(scene, load) -> None:
    mk = ensure_marker(scene, load)
    if mk is not None:
        mk.location = Vector(load.cog_local)
        mk["fr_cog_auto"] = list(load.cog_local)
    _READ.clear()


def cog_world(load):
    mk = load.marker
    if mk is not None and mk.name in bpy.data.objects:
        if mk.parent is not None:          # worked out: a marker just made or moved has no world matrix yet
            return np.array((mk.parent.matrix_world @ mk.matrix_parent_inverse @ mk.matrix_basis).translation)
        return np.array(mk.matrix_world.translation)
    if load.carrier is not None:
        return np.array(load.carrier.matrix_world @ Vector(load.cog_local))
    return None


def load_mass(scene, load) -> tuple[float, str]:
    """(mass in kg, its source in words) – entered, or volume x density ("estimate")."""
    if load is None:
        return 0.0, ""
    if load.kind == "BOX" or load.mass_mode == "ENTERED":
        return lifting.kg(load.mass_t), LD.SOURCES.get(load.source, "")
    return float(load.volume_mass), "estimate (volume x density)"


def load_top(load) -> float | None:
    """The highest point of the load (world z, m)."""
    tops = []
    for ob in load_parts(load):
        M = ob.matrix_world
        tops += [(M @ Vector(c)).z for c in ob.bound_box]
    return max(tops) if tops else None


def new_load(scene, objs, name: str = ""):
    """A load of parts or sub-assemblies. Refused (ValueError) for a part already in another load."""
    objs = [o for o in objs if o is not None and o.get(build.PROP_KIND) in ("part", "assembly")]
    if not objs:
        raise ValueError("Select parts or sub-assemblies of the model first (click them in the 3D view or the "
                         "Structure list).")
    for o in objs:
        other = load_of_object(scene, o)
        if other is not None:
            raise ValueError(f"{o.get(build.PROP_NAME, o.name)} is in the load '{other.name}' already: a part can be "
                             "in one load only.")
    if any(crane_of_root(scene, build.model_root_of(o)) is not None for o in objs):
        raise ValueError("A placed crane cannot be a load.")
    L = plan(scene)
    ld = L.loads.add()
    ld.name = _unique_load(scene, name or str(objs[0].get(build.PROP_NAME, objs[0].name)))
    ld.kind = "PARTS"
    for o in objs:
        r = ld.parts.add()
        r.obj = o
    L.load_index = len(L.loads) - 1
    refresh_load(scene, ld)
    if ld.mass_t == 0.0 and ld.volume_mass > 0:
        ld["mass_t"] = round(lifting.tonnes(ld.volume_mass), 3)
    return ld


def _unique_load(scene, base: str) -> str:
    taken = {x.name for x in plan(scene).loads}
    if base not in taken:
        return base
    n = 2
    while f"{base} {n}" in taken:
        n += 1
    return f"{base} {n}"


def new_box(scene, size, mass_t: float, location=None, name: str = ""):
    """A box load (length x width x height, m) standing on ``location`` (the 3D cursor when None)."""
    lx, wy, hz = (max(float(v), 0.001) for v in size)
    me = bpy.data.meshes.new(BOX_PREFIX + (name or "Box"))
    x, y = lx / 2, wy / 2
    vs = [(-x, -y, 0), (x, -y, 0), (x, y, 0), (-x, y, 0), (-x, -y, hz), (x, -y, hz), (x, y, hz), (-x, y, hz)]
    fs = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    me.from_pydata(vs, [], fs)
    me.update()
    L = plan(scene)
    ld = L.loads.add()
    ld.name = _unique_load(scene, name or "Box")
    ob = bpy.data.objects.new(BOX_PREFIX + ld.name, me)
    ob["fr_load_box"] = ld.name
    scene.collection.objects.link(ob)
    loc = Vector(location) if location is not None else Vector(scene.cursor.location)
    ob.location = loc
    try:
        from . import materials
        mat = materials.ensure_material("Lifting load box", "paint_satin", "RAL 1003")
        ob.data.materials.append(mat)
    except Exception:  # noqa: BLE001
        pass
    ld.kind = "BOX"
    ld.box = ob
    ld["mass_t"] = float(mass_t)
    ld.mass_mode = "ENTERED"
    L.load_index = len(L.loads) - 1
    refresh_load(scene, ld)
    return ld


def remove_load(scene, load) -> None:
    L = plan(scene)
    name = load.name
    for ob in (load.marker, load.box):
        if ob is not None and ob.name in bpy.data.objects:
            me = ob.data if ob.type == "MESH" else None
            bpy.data.objects.remove(ob, do_unlink=True)
            if me is not None and me.users == 0:
                bpy.data.meshes.remove(me)
    idx = next(i for i, x in enumerate(L.loads) if x.name == name)
    L.loads.remove(idx)
    L.load_index = max(0, min(L.load_index, len(L.loads) - 1))
    _READ.clear()


def above_load(scene, load) -> np.ndarray | None:
    """The CoG + the clearance above the load's top (world, m)."""
    c, top = cog_world(load), load_top(load)
    if c is None or top is None:
        return None
    return np.array([c[0], c[1], top + float(load.clearance)])


def load_changed(scene, recompute: bool = True) -> None:
    if scene is None:
        return
    _READ.clear()
    if recompute:
        ld = active_load(scene)
        if ld is not None:
            r = compute(scene, ld)
            ld.volume_mass = r["mass"] if ld.kind == "PARTS" else lifting.kg(ld.mass_t)


# ---------------------------------------------------------------------------------------------------------------------
# the example the tour, the PC check and the tests share: an AT-40 beside the test crane, its boom as the load

EXAMPLE_CRANE = "AT-40"
EXAMPLE_LOAD = "BOOM.ASM"
EXAMPLE_MASS = 1.2          # t, "from the drawing"


def set_up_example(context, crane: str = EXAMPLE_CRANE, load_part: str = EXAMPLE_LOAD, gap: float = 6.0):
    """In a project with the test crane: place the crane (built-in sample) ``gap`` m beside the model, its boom
    towards it, set up on its outriggers; the test crane's boom becomes the load (1.2 t from the drawing, CoG
    computed); Hook to here above the load. Returns (crane item, load item, answer)."""
    scene = context.scene
    roots = [r for r in build.model_roots(scene) if crane_of_root(scene, r) is None]
    if not roots:
        raise RuntimeError("Import the test crane first.")
    mn, mx = (np.asarray(v, float) for v in logic.update_bounds(scene))
    centre = 0.5 * (mn + mx)
    c = place(context, os.path.join(LL.BUILTIN_DIR, crane), (float(mx[0]) + gap, float(centre[1]), float(mn[2])),
              math.pi)
    apply_pose(scene, c, "Set up")
    part = next((o for o in logic.descendants(roots[0]) if o.get(build.PROP_NAME) == load_part), None)
    if part is None:
        raise RuntimeError(f"The model has no {load_part}.")
    ld = new_load(scene, [part], "Test crane boom")
    ld.mass_mode = "ENTERED"
    ld.mass_t = EXAMPLE_MASS
    ld.source = "DRAWING"
    a = hook_to(scene, c, above_load(scene, ld), ld)
    return c, ld, a


def _layout(crane):
    """The maker's layout of a placed crane: a built-in class, or a crane made from numbers (task 0204)."""
    from ..lifting_model import classes as C
    from ..lifting_model import params
    try:
        cls = params.class_of_data(item_at(path_of(crane)).data)
    except (OSError, ValueError, LL.LibraryError):
        cls = C.CLASSES.get(crane.item_name)
    return C.layout(cls) if cls is not None else None


def check_rig(scene) -> str:
    """The first crane: every pose of its file puts the hook block where the maker's kinematics say (ValueError)."""
    L = plan(scene)
    if not L.cranes or L.cranes[0].root is None:
        raise ValueError("no crane in the lifting plan")
    c = L.cranes[0]
    from ..lifting_model import classes as C
    lay = _layout(c)
    if lay is None:
        raise ValueError(f"{c.item_name} is neither a built-in class nor a crane made from numbers")
    was = values(scene, c)
    worst = 0.0
    try:
        for p in pose_names(c):
            apply_pose(scene, c, p)
            want = to_world(c, C.hook_point(lay, values(scene, c)))
            got = _hook_block_world(scene, c)
            if got is None:
                raise ValueError("the crane has no hook block")
            worst = max(worst, float(np.linalg.norm(got - want)))
    finally:
        set_values(scene, c, was)
    if worst > 0.005:
        raise ValueError(f"a pose puts the hook block {worst * 1000:.1f} mm off the crane's kinematics")
    n = len(own_joints(scene, c))
    if not all(j.name.startswith(prefix(c)) for j in own_joints(scene, c)) or n == 0:
        raise ValueError("the crane's joints do not carry its name")
    return f"{c.name}: {n} joints, {len(pose_names(c))} poses, hook block within {worst * 1000:.2f} mm"


def check_cog(scene) -> str:
    """The first load: a CoG marker inside the load's box, computed (ValueError)."""
    L = plan(scene)
    if not L.loads:
        raise ValueError("no load in the lifting plan")
    ld = L.loads[0]
    c = cog_world(ld)
    if c is None:
        raise ValueError("the load has no CoG marker")
    pts = []
    for ob in load_parts(ld):
        M = ob.matrix_world
        pts += [list(M @ Vector(v)) for v in ob.bound_box]
    pts = np.array(pts)
    if not (np.all(c >= pts.min(axis=0) - 1e-6) and np.all(c <= pts.max(axis=0) + 1e-6)):
        raise ValueError("the CoG marker lies outside the load")
    if cog_by_hand(ld):
        raise ValueError("the CoG marker was moved by hand")
    m, src = load_mass(scene, ld)
    return f"{ld.name}: {lifting.tonnes(m):.2f} t ({src}), CoG at {c[0]:.2f}, {c[1]:.2f}, {c[2]:.2f} m"


def check_example(scene) -> str:
    """The example as set up: raises ValueError with a plain reason, else a one-line summary."""
    L = plan(scene)
    if not L.cranes or not L.loads:
        raise ValueError("no crane or no load in the lifting plan")
    c, ld = L.cranes[0], L.loads[0]
    rig = rig_of(c)
    from ..lifting_model import classes as C
    lay = _layout(c)
    if lay is None:
        raise ValueError(f"{c.item_name} is neither a built-in class nor a crane made from numbers")
    vals = values(scene, c)
    want = to_world(c, C.hook_point(lay, vals))
    hook = _hook_block_world(scene, c)
    if hook is None or np.linalg.norm(hook - want) > 0.005:
        raise ValueError(f"the hook block is not where the crane's kinematics put it ({_mm(hook, want)})")
    above = above_load(scene, ld)
    if np.linalg.norm(hook - above) > 0.005:
        raise ValueError(f"the hook is not above the load ({_mm(hook, above)})")
    ro = readout(scene, c, ld)
    if isinstance(ro, str) or ro.use is None:
        raise ValueError(f"no crane use at the hook: {ro if isinstance(ro, str) else ro.reason}")
    ref = lifting.crane_use(load_mass(scene, ld)[0] * ld.contingency, ro.radius, ro.chart,
                            hook_block=hook_block_kg(c))
    if abs(ref.use - ro.use) > 1e-9:
        raise ValueError("the crane use shown is not the chart's")
    if cog_world(ld) is None:
        raise ValueError("the load has no CoG marker")
    _ = rig
    return (f"{c.name}: radius {ro.radius:.2f} m, gross {lifting.tonnes(ro.gross):.2f} t, crane use "
            f"{ro.use * 100:.0f} % – {ro.words}")


def _mm(a, b) -> str:
    return "not found" if a is None else f"{np.linalg.norm(np.asarray(a) - np.asarray(b)) * 1000:.1f} mm off"


def _hook_block_world(scene, crane):
    """Where the hook block's hook point is now, read from the block's own place (not from the kinematics)."""
    from . import sheet
    data = item_at(path_of(crane)).data
    hook = data["rig"]["hook"]
    m = sheet.Model(scene, sheet_of(data), root=crane.root, prefix=prefix(crane))
    hits = m.by_name.get(hook["assembly"], [])
    if not hits:
        return None
    ob = hits[0]
    cad = ob.get("fr_lift_cad")
    if cad is None:
        return None
    R = np.array(crane.root.matrix_world)
    C0 = np.array(cad).reshape(4, 4)                            # the block in the CAD pose, model frame
    now = np.linalg.inv(R) @ np.array(ob.matrix_world)          # the block now, model frame
    p = np.r_[np.asarray(hook["point"], float) / 1000.0, 1.0]   # the CAD hook point, model frame (m)
    return (R @ now @ np.linalg.inv(C0) @ p)[:3]


# ---------------------------------------------------------------------------------------------------------------------
# the CoG symbol (drawn on top of everything; nothing in bpy.data but the markers themselves)

_DRAW = {"handle": None}


def _draw_cog():
    ctx = bpy.context
    scene = getattr(ctx, "scene", None)
    if scene is None or not hasattr(scene, "fresing") or not scene.fresing.lifting.loads:
        return
    region, rv3d = ctx.region, ctx.region_data
    if region is None or rv3d is None:
        return
    import blf
    import gpu
    from bpy_extras.view3d_utils import location_3d_to_region_2d
    from gpu_extras.batch import batch_for_shader
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    gpu.state.blend_set("ALPHA")
    for ld in scene.fresing.lifting.loads:
        w = cog_world(ld)
        if w is None:
            continue
        p = location_3d_to_region_2d(region, rv3d, Vector(w))
        if p is None:
            continue
        r = 11.0
        for q in range(4):              # four quarters, black and white in turn: the usual CoG symbol
            a0 = q * math.pi / 2
            pts = [(p.x, p.y)] + [(p.x + r * math.cos(a0 + t * math.pi / 2 / 8), p.y + r * math.sin(a0 + t * math.pi / 2 / 8))
                                  for t in range(9)]
            tris = [(0, i, i + 1) for i in range(1, 9)]
            batch = batch_for_shader(shader, "TRIS", {"pos": pts}, indices=tris)
            shader.uniform_float("color", (0.05, 0.05, 0.05, 1.0) if q % 2 == 0 else (1.0, 1.0, 1.0, 1.0))
            batch.draw(shader)
        ring = [(p.x + (r + 1) * math.cos(t * math.pi / 16), p.y + (r + 1) * math.sin(t * math.pi / 16))
                for t in range(33)]
        batch = batch_for_shader(shader, "LINE_STRIP", {"pos": ring})
        shader.uniform_float("color", (0.05, 0.05, 0.05, 1.0))
        batch.draw(shader)
        blf.position(0, p.x + r + 5, p.y - 4, 0)
        blf.size(0, 12)
        blf.color(0, 1.0, 1.0, 1.0, 1.0)
        blf.draw(0, "CoG" + (" (by hand)" if cog_by_hand(ld) else ""))
    gpu.state.blend_set("NONE")


def register():
    if _DRAW["handle"] is None and not bpy.app.background:
        _DRAW["handle"] = bpy.types.SpaceView3D.draw_handler_add(_draw_cog, (), "WINDOW", "POST_PIXEL")
    if _load_post not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_load_post)


def unregister():
    if _DRAW["handle"] is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_DRAW["handle"], "WINDOW")
        _DRAW["handle"] = None
    if _load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_load_post)


@bpy.app.handlers.persistent
def _load_post(_dummy=None):
    forget()
    _LIB["items"] = None


def _update():
    bpy.context.view_layer.update()
