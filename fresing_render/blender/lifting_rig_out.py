"""The scene's crane → an equipment file's ``rig`` (task 0203): the reverse of ``blender/sheet.py``.

``build(scene)`` reads the crane that Set up a crane made (its joints with their roles, cylinders, tracks, the rope,
poses, the hook, the groups' masses and CoG, the chart) and writes it the way the built-in cranes' files are written
(``fresing_render/data/lifting/<class>/<class>.json``): parts by their CAD names, points in mm and directions in the
STEP file's own frame, read in the CAD pose (every joint at 0), angles in degrees. ``save(scene, library)`` puts it
into the user's library through ``lifting_library.write_item`` (never into the built-ins) with a copy of the STEP and
a small picture, so it places in any project exactly as a built-in does.
"""

from __future__ import annotations

import math
import os
import shutil

import bpy
import numpy as np
from mathutils import Vector

from ..core import lifting_library as LL
from . import build as bld, cylinders, joints, setup_crane as SC


class RigError(RuntimeError):
    """The crane cannot be written yet (the message says why; ``step`` = the step that fixes it)."""

    def __init__(self, text: str, step: str = ""):
        super().__init__(text)
        self.step = step


def _r(v, n: int = 4) -> list:
    return [round(float(x), n) for x in v]


def _unique_name(scene, ob, problems: list) -> str:
    """The object's CAD name, which must name one object in the model (the file finds parts by name)."""
    n = SC.name_of(ob)
    hits = SC.lookup(SC.model_root(scene)).get(n, [])
    if len(hits) != 1:
        problems.append((f"'{n}' is the name of {len(hits)} parts: the file finds parts by name – rename one in the "
                         "CAD, or pick the sub-assembly above them", ""))
    return n


def up_axis(root) -> str:
    """'Y' when the model was imported with Y up (its root turned 90° about X), else 'Z'."""
    M = np.array(root.matrix_world)[:3, :3]
    y_world = M @ np.array([0.0, 1.0, 0.0])
    return "Y" if y_world[2] > 0.9 * np.linalg.norm(y_world) else "Z"


def _value(j, v: float) -> float:
    return math.degrees(v) if j.kind == "ROTATE" else v * 1000.0


def joints_out(scene, root, problems: list) -> list:
    """The crane's joints in the file's form, joints others ride on first."""
    out = []
    own = SC.crane_joints(scene)
    names = {j.name for j in own}
    for j in own:
        w = joints.world_of(scene, j.frame)
        o = np.array(w.translation)
        d = np.array(w.to_3x3() @ Vector((0.0, 0.0, 1.0)))
        below = joints.rides_on(scene, j)
        if below is None and j.frame is not None and j.frame.parent is not None:
            below = SC._carrier_of(scene, j.frame.parent)      # a frame on a sub-assembly another joint moves
        lim = None
        if j.use_limits:
            lo, hi = joints.limits(j)
            lim = [round(_value(j, lo), 4), round(_value(j, hi), 4)]
        d_out = {"name": j.name, "kind": j.kind, "role": j.role if j.role != "NONE" else None,
                 "parts": [_unique_name(scene, m, problems) for m in joints.members(j)],
                 "point": _r(SC.to_model(root, o)), "direction": _r(SC.dir_to_model(root, d), 6),
                 "rides_on": below.name if below is not None and below.name in names else None,
                 "limits": lim}
        if j.follows:
            d_out["follows"] = j.follows
            d_out["ratio"] = round(float(j.couple_ratio), 6)
        out.append(d_out)
    return out


def cylinders_out(scene, root, problems: list) -> list:
    """The crane's cylinders: barrel and rod by name, each pin's point and axis (the cylinder frame's z, the pin axis:
    ``core/cylinders.axis_frame``) and the part it is pinned to."""
    from mathutils import Vector
    out = []
    inside = set(id(o) for objs in SC.lookup(root).values() for o in objs)
    for c in scene.fresing.cylinders:
        if not cylinders.is_valid(c) or not any(id(o) in inside for o in cylinders.barrel_objs(c)):
            continue
        z = np.array(c.frame.matrix_world.to_3x3() @ Vector((0.0, 0.0, 1.0)))
        pins = {}
        for key, emp in (("barrel_pin", c.frame), ("rod_pin", c.pin)):
            carrier = bld.logical_parent(emp) or emp.parent
            pins[key] = {"point": _r(SC.to_model(root, np.array(emp.matrix_world.translation))),
                         "axis": _r(SC.dir_to_model(root, z), 6),
                         "carrier": _unique_name(scene, carrier, problems)}
        out.append({"name": c.name,
                    "barrel": [_unique_name(scene, o, problems) for o in cylinders.barrel_objs(c)],
                    "rod": [_unique_name(scene, o, problems) for o in cylinders.rod_objs(c)], **pins})
    return out


def poses_out(scene, own_names: set) -> list:
    out = []
    by = {j.name: j for j in scene.fresing.joints}
    for p in scene.fresing.poses:
        vals = {}
        for pj in p.joints:
            j = by.get(pj.joint)
            if j is None or j.name not in own_names or j.follows:
                continue
            v = _value(j, pj.value)
            if abs(v) > 1e-6:
                vals[j.name] = round(v, 4)
        if any(pj.joint in own_names for pj in p.joints):
            out.append({"name": p.name, "values": vals})
    return out


def tracks_out(scene, root, problems: list) -> list:
    out = []
    for t in scene.fresing.tracks:
        rec = t.get("fr_crane")
        wheels = [w.part for w in t.wheels if w.part is not None]
        if not wheels or rec is None:
            continue
        rec = dict(rec)
        out.append({"name": t.name, "wheels": [_unique_name(scene, w, problems) for w in wheels[:2]],
                    "link": rec.get("link", ""), "riders": list(rec.get("riders", [])), "joint": t.joint})
    return out


def _box(scene, root, objs) -> tuple:
    mn, mx = bld.world_bounds(SC.parts_of(objs))
    corners = [SC.to_model(root, (x, y, z)) / 1000.0 for x in (mn[0], mx[0]) for y in (mn[1], mx[1])
               for z in (mn[2], mx[2])]
    c = np.array(corners)
    return c.min(axis=0), c.max(axis=0)


def level(root) -> list:
    """The model's two level axes (along, across): (x, y) for a model drawn with Z up, (x, z) with Y up."""
    return [0, 2] if up_axis(root) == "Y" else [0, 1]


def outriggers_out(scene, root, cs) -> dict | None:
    """The outrigger (stabiliser) block for the checks: jacks' places in the CAD pose (b_in, a, centre), the beam
    stages, the pads, the spreads typed in the step (full / middle / narrow, as half spreads b)."""
    beams = SC.with_role(scene, "outrigger")
    jacks = SC.with_role(scene, "jack")
    if not beams or not jacks:
        return None
    lead = next((j for j in beams if not j.follows), beams[0])
    lead_jack = next((j for j in jacks if not j.follows), jacks[0])
    pts = []
    pads = []
    for j in jacks:
        lo, hi = _box(scene, root, joints.members(j))
        pts.append(((lo + hi) / 2.0)[level(root)])
        pads.append((hi - lo)[level(root)])
    P = np.array(pts)
    centre = (P.min(axis=0) + P.max(axis=0)) / 2.0
    stages = max(1, round(len(beams) / max(1, len(jacks))))
    names = {"full": cs.spreads[0], "middle": cs.spreads[1], "narrow": cs.spreads[2]}
    spreads = {k: round(v / 2.0, 4) for k, v in names.items() if v > 0}
    return {"centre": _r(centre), "a": round(float(np.mean(np.abs(P[:, 0] - centre[0]))), 4),
            "spreads": spreads, "spread_meaning": "b = half the spread across (pad centre to the crane's middle line)",
            "stages": stages, "b_in": round(float(np.mean(np.abs(P[:, 1] - centre[1]))), 4),
            "joint_meaning": f"each of the {stages} beam stages moves the joint's value: b = b_in + {stages} x value",
            "pad": _r(np.mean(np.array(pads), axis=0), 3), "joint": lead.name, "jack_joint": lead_jack.name}


def tracks_block(scene, root) -> dict | None:
    travel = SC.first(scene, "travel")
    ts = [t for t in scene.fresing.tracks if t.get("fr_crane") is not None]
    if travel is None or len(ts) < 2:
        return None
    boxes = []
    for t in ts:
        wheels = [w.part for w in t.wheels if w.part is not None]
        boxes.append(_box(scene, root, wheels))
    lo = np.min([b[0] for b in boxes], axis=0)
    hi = np.max([b[1] for b in boxes], axis=0)
    H = level(root)
    mids = sorted(((b[0] + b[1]) / 2.0)[H[1]] for b in boxes)
    width = float(np.mean([b[1][H[1]] - b[0][H[1]] for b in boxes]))
    return {"gauge": round(mids[-1] - mids[0], 4), "length": round(float(hi[0] - lo[0]), 4),
            "width": round(width, 4), "centre": _r(((lo + hi) / 2.0)[H]), "joint": travel.name}


def build(scene) -> dict:
    """The equipment file's data for the crane in the project (not written). RigError when it cannot be written."""
    root = SC.model_root(scene)
    if root is None:
        raise RigError("No crane model in the project: import its STEP first.", "model")
    cs = SC.settings(scene)
    kind = SC.kind_of(scene) or "other_crane"
    problems: list = []
    with joints.cad_pose(scene):
        bpy.context.view_layer.update()
        js = joints_out(scene, root, problems)
        cyls = cylinders_out(scene, root, problems)
        tracks = tracks_out(scene, root, problems)
        outr = outriggers_out(scene, root, cs)
        tblock = tracks_block(scene, root)
        footprint = None
        if outr is None and tblock is None:
            base = next((g for g in cs.groups if g.key in ("carrier", "lower", "truck", "base") and g.parts), None)
            objs = SC.objects_of(scene, base.parts)[0] if base is not None else [root]
            lo, hi = _box(scene, root, objs or [root])
            a, b = level(root)
            footprint = [[round(float(x[a]), 4), round(float(y[b]), 4)] for x, y in ((lo, lo), (hi, lo), (hi, hi),
                                                                                       (lo, hi))]
    own = {j["name"] for j in js}
    hoist = SC.first(scene, "hoist")
    if hoist is None or not cs.hook_set:
        raise RigError("The hook is not made yet: Hoist and Hook block steps.", "hook_block")
    step = str(root.get(bld.PROP_SOURCE, "") or "")
    rig = {"step": os.path.basename(step) or (cs.name or SC.name_of(root)) + ".step", "units": "mm",
           "angles": "deg", "up_axis": up_axis(root),
           "frame": "the STEP file's own frame; joint values 0 = the CAD pose",
           "joints": js, "cylinders": cyls, "poses": poses_out(scene, own),
           "start_pose": cs.start_pose or "", "groups": {}, "hook": {}}
    if not rig["start_pose"] and rig["poses"]:
        rig["start_pose"] = rig["poses"][0]["name"]
    rig["hook"] = {"assembly": cs.hook_part, "point": _r(np.asarray(cs.hook_point) * 1000.0), "joint": hoist.name,
                   "falls": int(cs.falls),
                   "plumb": "the hook swing joints follow the boom's turns (ratio -1): the block hangs plumb"}
    if cs.rope_part:
        rig["cables"] = [{"name": "Hoist rope", "part": cs.rope_part, "end_on": cs.hook_part, "look": "ROPE"}]
    if tracks:
        rig["tracks"] = tracks
    mass, cog = {}, {}
    for g in cs.groups:
        if not g.parts:
            continue
        objs, bad = SC.objects_of(scene, g.parts)
        problems += [(b, "masses") for b in bad]
        role = SC.GROUP_ROLE.get(g.key)
        mover = SC.first(scene, role) if role else None
        if mover is None and objs:
            jj = SC._carrier_of(scene, objs[0])
            mover = jj
        rig["groups"][g.key] = {"parts": [SC.name_of(o) for o in objs],
                                "moves_with": mover.name if mover is not None and mover.name in own else None}
        mass[g.key] = round(SC.group_mass_t(g), 4)
        cog[g.key] = _r(g.cog)
    limits = {}
    for role in ("slew",):
        j = next((d for d in js if d.get("role") == role and not d.get("follows")), None)
        if j and j.get("limits"):
            limits["slew"] = j["limits"]
    hj = next((d for d in js if d["name"] == hoist.name), None)
    if hj and hj.get("limits"):
        limits["hoist"] = [round(v / 1000.0, 4) for v in hj["limits"]]
    luff = next((d for d in js if d.get("role") == "luff" and not d.get("follows")), None)
    th0 = math.degrees(cs.boom_angle)
    if luff and luff.get("limits"):
        key = "main_boom_angle" if kind == "knuckle_boom_crane" else "boom_angle"
        limits[key] = [round(th0 + luff["limits"][0], 4), round(th0 + luff["limits"][1], 4)]
    second = next((d for d in js if d.get("role") in ("jib", "knuckle") and not d.get("follows")), None)
    if second and second.get("limits"):
        key = "knuckle_angle" if second["role"] == "knuckle" else "jib_angle_to_boom"
        s0 = math.degrees(cs.second_angle)
        limits[key] = [round(s0 + second["limits"][0], 4), round(s0 + second["limits"][1], 4)]
    if cs.model_boom > 0:
        limits["model_boom"] = round(cs.model_boom, 4)
    if cs.model_jib > 0:
        limits["model_jib"] = round(cs.model_jib, 4)
    if cs.jib_boom_angle > 0:
        limits["jib_charts_boom_angle"] = round(cs.jib_boom_angle, 4)
    steps, bad = counterweight_steps(cs.counterweight_steps)
    problems += [(f"Counterweight steps: cannot read '{b}' (type them like 0, 40, 80 or 0; 4,5; 9)",
                  "counterweight") for b in bad]
    if steps:
        limits["counterweight_steps"] = steps
    if any(v > 0 for v in cs.spreads):
        limits["outrigger_spreads"] = [round(v, 4) for v in cs.spreads if v > 0]
    data = LL.new_item(kind, cs.cls or cs.name or SC.name_of(root), cs.name or SC.name_of(root), "t", "m",
                       mass=mass, cog=cog, rig=rig, limits=limits, charts=SC.chart_dicts(scene),
                       source=cs.chart_source or "Own crane, set up in Fresing Render")
    if cs.hook_block_t > 0:
        data["hook_blocks"] = [{"name": "main", "mass": round(cs.hook_block_t, 4), "sheaves": int(cs.falls)}]
    if outr is not None:
        data["outriggers"] = outr
    if tblock is not None:
        data["tracks"] = tblock
    if footprint is not None:
        data["footprint"] = footprint
    data["_problems"] = problems
    return data


def counterweight_steps(text: str) -> tuple[list, list]:
    """([t], [cells not read]) from what a user types: '0, 40, 80', '0; 4,5; 9' (with ';' a comma is a decimal
    comma), '0 t, 4 t, 8 t', '4500 kg'."""
    from ..core import lifting
    text = (text or "").strip()
    if not text:
        return [], []
    dec_comma = ";" in text
    cells = [c.strip() for c in (text.split(";") if dec_comma else text.split(","))]
    out, bad = [], []
    for c in cells:
        if not c:
            continue
        try:
            v, unit = LL._parse_number(c, dec_comma)
        except ValueError:
            bad.append(c)
            continue
        if v is None or unit in lifting.LENGTH_UNITS:
            bad.append(c)
            continue
        out.append(round(v * lifting.MASS_UNITS[unit] / 1000.0, 6) if unit else v)
    return out, bad


def scene_problems(scene) -> list:
    """(step, text) problems only the project can show: names that fit several parts, joints whose value now lies
    past their limits."""
    out = []
    try:
        data = build(scene)
    except RigError as exc:
        return [(exc.step, str(exc))]
    for text, step in data.get("_problems", []):
        out.append((step, text))
    with joints.cad_pose(scene):
        for j in SC.crane_joints(scene):
            if j.role in SC.SENSE and j.role not in ("swing", "track", "travel") and not j.follows \
                    and not SC.sense_ok(scene, j.role, j):
                out.append((j.role, f"{j.name} moves the wrong way for a {SC.ROLE_WORDS[j.role].lower()} "
                                    f"({SC.SENSE[j.role]}): press Flip"))
    for j in SC.crane_joints(scene):
        if j.follows or not j.use_limits:
            continue
        v = joints.get_value(j)
        if joints.outside_limits(j, v):
            out.append((j.role if j.role != "NONE" else "joints",
                        f"{j.name} stands at {_value(j, v):.1f} {'°' if j.kind == 'ROTATE' else 'mm'}, past its "
                        "limits"))
    return out


def picture(scene, path: str) -> bool:
    """A small picture of the main window's 3D view (no picture in a background run)."""
    if bpy.app.background:
        return False
    try:
        from . import ops_setup
        win, area, region = ops_setup.main_view(bpy.context)
        if area is None:
            return False
        with bpy.context.temp_override(window=win, screen=win.screen, area=area, region=region):
            bpy.ops.screen.screenshot_area(filepath=path)
        return os.path.isfile(path)
    except Exception:  # noqa: BLE001 - a picture is a nicety
        return False


def save(scene, library: str) -> str:
    """Write the crane into the library (``<library>/<name>/<name>.json`` + the STEP + a picture). Returns the file's
    path; RigError / LibraryError in plain words. Never into the built-ins."""
    from . import lifting
    from ..core import lifting_reach as LR
    if not library:
        raise RigError("No library folder: set the library folder in Preferences first (Lifting equipment goes into "
                       "it).", "save")
    data = build(scene)
    bad = data.pop("_problems", [])
    if bad:
        raise RigError(bad[0][0], bad[0][1])
    try:
        LR.Rig(data)
    except LR.ReachError as exc:
        raise RigError(f"Not saved: {exc}", "hook_block") from exc
    root = SC.model_root(scene)
    src = bpy.path.abspath(str(root.get(bld.PROP_SOURCE, "") or ""))
    name = LL.folder_name(data["name"])
    folder = os.path.join(library, name)
    for b in (LL.BUILTIN_DIR,):
        if os.path.normcase(os.path.abspath(folder)).startswith(os.path.normcase(os.path.abspath(b))):
            raise RigError("The built-in equipment cannot be changed: pick your own library folder.", "save")
    if not os.path.isfile(src):
        raise RigError(f"The crane's STEP is gone ({src}): it is copied next to the file.", "model")
    data["rig"]["step"] = name + os.path.splitext(src)[1].lower()
    written = LL.write_item(data, library)
    dst = os.path.join(os.path.dirname(written.path), data["rig"]["step"])
    if os.path.abspath(src) != os.path.abspath(dst):
        shutil.copyfile(src, dst)
    picture(scene, os.path.join(os.path.dirname(written.path), name + ".png"))
    lifting.forget()
    return written.path
