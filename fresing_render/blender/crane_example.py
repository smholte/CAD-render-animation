"""Set up a crane done by names (task 0203): a built-in crane's bare STEP rigged through the Set-up window's buttons
only, by part names – the names, limits and numbers a user reads off the maker's drawing (here: the built-in file of
the same class). The test tour's crane set-up set, the PC check's ``lifting.setup``, ``tests/test_setup_crane.py`` and
the real-app test ``tools/ui_test_setup_crane.py`` use it; ``compare`` checks a saved file against the built-in one.

Every press goes through ``bpy.ops.fresing.*`` the way a button does ("EXEC_DEFAULT"). The only choice a user makes by
eye – which axis of the list – is made here by the built-in axis: the list must hold it.
"""

from __future__ import annotations

import json
import math
import os

import numpy as np

def _m(name: str):
    import importlib
    return importlib.import_module(__package__.rsplit(".", 1)[0] + "." + name)


KINDS = {"mobile_crane": "CRANE_MOBILE", "crawler_crane": "CRANE_CRAWLER", "knuckle_boom_crane": "CRANE_KNUCKLE",
         "other_crane": "CRANE_OTHER"}


def _ops():
    import bpy
    return bpy.ops.fresing


def _need(ok, what) -> None:
    if not ok:
        raise RuntimeError(f"Set up a crane by names: {what}")


def press(op, **kw):
    res = op("EXEC_DEFAULT", True, **kw)
    _need("FINISHED" in res, f"{op} {kw} gave {res}")
    return res


def builtin(cls: str) -> dict:
    LL = _m("core.lifting_library")
    with open(os.path.join(LL.BUILTIN_DIR, cls, cls + ".json"), encoding="utf-8") as fh:
        return json.load(fh)


def _role(j: dict) -> str | None:
    LR = _m("core.lifting_reach")
    if hasattr(LR, "role_of"):
        return LR.role_of(j)
    if j.get("role"):
        return j["role"]
    n = j["name"]
    for pre, r in (("Slew", "slew"), ("Luff", "luff"), ("Main boom", "luff"), ("Telescope", "telescope"),
                   ("Jib", "jib"), ("Knuckle", "knuckle"), ("Extension", "extension"), ("Hoist", "hoist"),
                   ("Hook swing", "swing"), ("Outrigger", "outrigger"), ("Stabiliser", "outrigger"),
                   ("Jack", "jack"), ("Leg", "jack"), ("Travel", "travel")):
        if n.startswith(pre):
            return r
    return None


def _pick(names):
    import bpy
    press(bpy.ops.fresing.crane_pick, clear=True)
    press(bpy.ops.fresing.crane_pick, names=" | ".join(names), add=True)


def _choose_axis(scene, root, point_mm, direction, rotate: bool) -> int:
    """The list's axis nearest the built-in one (a user picks it by its label): returns its index."""
    SC = _m("blender.setup_crane")
    cs = SC.settings(scene)
    best, best_err = -1, None
    u = np.asarray(direction, float)
    u /= np.linalg.norm(u)
    c = np.asarray(point_mm, float)
    for i, a in enumerate(cs.axes):
        o = SC.to_model(root, np.array(a.origin))
        d = SC.dir_to_model(root, np.array(a.direction))
        ang = math.degrees(math.acos(min(1.0, abs(float(np.dot(d, u))))))
        off = 0.0
        if rotate:
            v = o - c
            off = float(np.linalg.norm(v - np.dot(v, u) * u))
        err = ang + off / 10.0
        if best_err is None or err < best_err:
            best, best_err = i, err
    _need(best >= 0 and best_err < 0.2, f"no axis in the list fits ({[a.label for a in cs.axes]}, {best_err})")
    press(_ops().crane_axis_use, index=best)
    return best


def _limits(scene, name: str, lim) -> None:
    joints = _m("blender.joints")
    j = joints.find(scene, name)
    if lim is None:
        j.use_limits = False
        return
    if j.kind == "ROTATE":
        j.rot_min, j.rot_max = math.radians(lim[0]), math.radians(lim[1])
    else:
        j.slide_min, j.slide_max = lim[0] / 1000.0, lim[1] / 1000.0
    j.use_limits = True


def _by_parts(scene, parts) -> str:
    """The made joint that moves exactly these parts."""
    joints, SC = _m("blender.joints"), _m("blender.setup_crane")
    want = sorted(parts)
    for j in SC.crane_joints(scene):
        if sorted(SC.name_of(m) for m in joints.members(j)) == want:
            return j.name
    raise RuntimeError(f"Set up a crane by names: no joint moves {want}")


def _sheave_name(scene, root, point_mm) -> str:
    """The part whose level round face passes through the built-in hoist point (the head sheave)."""
    SC = _m("blender.setup_crane")
    best = None
    for name, objs in SC.lookup(root).items():
        if len(objs) != 1 or objs[0].type != "MESH":
            continue
        for o, d, r, _p in SC._mesh_axes(objs[0]):
            if abs(d.z) > 0.02 or r <= 0:
                continue
            om = SC.to_model(root, np.array(o))
            dm = SC.dir_to_model(root, np.array(d))
            v = om - np.asarray(point_mm, float)
            off = float(np.linalg.norm(v - np.dot(v, dm) * dm))
            if off < 1.0 and (best is None or r > best[1]):
                best = (name, r)
    _need(best is not None, "no head sheave through the hoist point")
    return best[0]


def rig(scene, cls: str, kind_override: str = "", clash: bool = False, check: bool = True) -> dict:
    """Rig the imported bare STEP of built-in class ``cls`` through the set-up's buttons. Returns {built-in name:
    made name}."""
    import bpy
    joints, SC = _m("blender.joints"), _m("blender.setup_crane")
    data = builtin(cls)
    rig_ = data["rig"]
    kind = kind_override or KINDS[data["kind"]]
    press(bpy.ops.fresing.crane_setup, kind=kind)
    cs = SC.settings(scene)
    root = SC.model_root(scene)
    _need(root is not None, "no crane model")
    cs.name, cs.cls = f"Own {cls}" + (" other" if kind == "CRANE_OTHER" else ""), cls
    js = rig_["joints"]
    by = {j["name"]: j for j in js}
    made: dict = {}

    def one(j, role):
        _pick(j["parts"])
        if kind == "CRANE_OTHER":
            cs.free_role = role
        press(bpy.ops.fresing.crane_axes, role=role)
        _choose_axis(scene, root, j["point"], j["direction"], j["kind"] == "ROTATE")
        cs.stroke = (j["limits"][1] / 1000.0) if j["kind"] == "SLIDE" and j.get("limits") else 0.0
        press(bpy.ops.fresing.crane_make, role=role)
        name = _by_parts(scene, j["parts"])
        _limits(scene, name, j.get("limits"))
        made[j["name"]] = name

    # travel + tracks (crawler)
    for j in js:
        if _role(j) == "travel":
            one(j, "travel")
            for t in rig_.get("tracks") or []:
                _pick(t["wheels"] + [t["link"]] + t["riders"])
                press(bpy.ops.fresing.crane_track)
    order = ["slew", "luff"]
    for role in order:
        j = next(j for j in js if _role(j) == role and not j.get("follows"))
        one(j, role)
        if role == "luff":
            cs.boom_angle = math.radians(_th0(data))
    # cylinders of the boom (luff) – pendants too
    for c in rig_.get("cylinders") or []:
        carrier = c["rod_pin"]["carrier"]
        role = "luff"
        for j in js:
            if carrier in j["parts"] and _role(j) in ("jib", "knuckle"):
                role = _role(j)
        if role != "luff":
            continue
        _pick(c["barrel"] + c["rod"])
        press(bpy.ops.fresing.crane_cylinder, role=role)
    # telescope / extensions: the chain from its leader
    for role in ("telescope",):
        lead = next((j for j in js if _role(j) == role and not j.get("follows")), None)
        if lead is None:
            continue
        chain = [lead] + [j for j in js if j.get("follows") == lead["name"] and _role(j) == role]
        _pick([p for j in chain for p in j["parts"]])
        press(bpy.ops.fresing.crane_axes, role=role)
        _choose_axis(scene, root, lead["point"], lead["direction"], False)
        cs.stroke = lead["limits"][1] / 1000.0
        press(bpy.ops.fresing.crane_make, role=role, chain=True)
        for j in chain:
            made[j["name"]] = _by_parts(scene, j["parts"])
    for role in ("jib", "knuckle"):
        j = next((j for j in js if _role(j) == role and not j.get("follows")), None)
        if j is None:
            continue
        one(j, role)
        lim = data.get("limits") or {}
        rel = lim.get("jib_angle_to_boom") or lim.get("knuckle_angle")
        if rel and j.get("limits"):
            cs.second_angle = math.radians(float(rel[0]) - float(j["limits"][0]))
        for c in rig_.get("cylinders") or []:
            if c["rod_pin"]["carrier"] in j["parts"]:
                _pick(c["barrel"] + c["rod"])
                press(bpy.ops.fresing.crane_cylinder, role=role)
    for role in ("extension",):
        lead = next((j for j in js if _role(j) == role and not j.get("follows")), None)
        if lead is None:
            continue
        chain = [lead] + [j for j in js if j.get("follows") == lead["name"] and _role(j) == role]
        _pick([p for j in chain for p in j["parts"]])
        press(bpy.ops.fresing.crane_axes, role=role)
        _choose_axis(scene, root, lead["point"], lead["direction"], False)
        cs.stroke = lead["limits"][1] / 1000.0
        press(bpy.ops.fresing.crane_make, role=role, chain=True)
        for j in chain:
            made[j["name"]] = _by_parts(scene, j["parts"])
    # hoist: the head sheave, the rope, the hook block
    hoist = next(j for j in js if _role(j) == "hoist")
    _pick([_sheave_name(scene, root, hoist["point"])])
    press(bpy.ops.fresing.crane_sheave)
    for cab in rig_.get("cables") or []:
        cs.rope_part = cab["part"]
    cs.falls = 4
    _pick([rig_["hook"]["assembly"]])
    press(bpy.ops.fresing.crane_hook)
    made[hoist["name"]] = SC.first(scene, "hoist").name
    # the app's guess lies on the plumb line under the sheave, on the hook block; the maker's drawing gives the saddle
    guess = SC.to_model(root, SC.to_world(root, np.asarray(cs.hook_point) * 1000.0)) if cs.hook_set else None
    _need(guess is not None and abs(guess[0] - hoist["point"][0]) < 1.0 and abs(guess[1] - hoist["point"][1]) < 1.0,
          "the app's hook point is not under the head sheave")
    cs.hook_point = [v / 1000.0 for v in rig_["hook"]["point"]]
    _limits(scene, made[hoist["name"]], hoist.get("limits"))
    swings = [j for j in js if _role(j) == "swing"]
    mine = SC.with_role(scene, "swing")
    for j, m in zip(swings, mine):
        made[j["name"]] = m.name
    # outriggers / stabilisers: one corner at a time (beam stages from the inside out, then the jack)
    firsts = [j for j in js if _role(j) == "outrigger" and not (j.get("rides_on") and _role(by[j["rides_on"]]) ==
                                                                 "outrigger")]
    firsts.sort(key=lambda j: bool(j.get("follows")))
    for f in firsts:
        corner, cur = [f], f
        while True:
            nxt = next((j for j in js if j.get("rides_on") == cur["name"]), None)
            if nxt is None:
                break
            corner.append(nxt)
            cur = nxt
        beams = [j for j in corner if _role(j) == "outrigger"]
        jack = next(j for j in corner if _role(j) == "jack")
        cs.stroke = beams[0]["limits"][1] / 1000.0
        cs.jack_stroke = jack["limits"][1] / 1000.0
        _pick([p for j in beams for p in j["parts"]] + jack["parts"])
        press(bpy.ops.fresing.crane_corner)
        for j in corner:
            made[j["name"]] = _by_parts(scene, j["parts"])
    # the rest of the numbers a user reads off the maker's sheet
    lim = data.get("limits") or {}
    cs.model_boom = float(lim.get("model_boom") or 0.0)
    cs.model_jib = float(lim.get("model_jib") or 0.0)
    cs.jib_boom_angle = float(lim.get("jib_charts_boom_angle") or 0.0)
    cs.counterweight_steps = ", ".join(f"{v:g}" for v in lim.get("counterweight_steps") or [])
    o = data.get("outriggers") or {}
    sp = [2.0 * float(o.get("spreads", {}).get(k, 0.0)) for k in ("full", "middle", "narrow")]
    cs.spreads = sp
    hb = (data.get("hook_blocks") or [{}])[0]
    cs.hook_block_t = float(hb.get("mass", 0.0))
    # masses and CoG, typed from the data sheet
    press(bpy.ops.fresing.crane_groups)
    for key, g in rig_["groups"].items():
        it = next((x for x in cs.groups if x.key == key), None)
        if it is None:
            it = cs.groups.add()
            it.key = it.name = key
        it.parts = " | ".join(g["parts"])
        it.mass_mode = "ENTERED"
        it.mass_t = float(data["mass"][key])
        it.cog_by_hand = True
        it.cog = data["cog"][key]
    for it in cs.groups:
        if it.key not in rig_["groups"]:
            it.parts = ""
    # the chart: pasted as CSV
    press(bpy.ops.fresing.crane_chart_csv, paste=True, text=chart_csv(data))
    cs.chart_wind = float((data["charts"][0].get("wind_max") or 9.8))
    cs.chart_hook = bool(data["charts"][0].get("includes_hook_block"))
    cs.chart_source = "typed from the data sheet"
    # poses
    for p in rig_.get("poses") or []:
        vals = {made[k]: v for k, v in p["values"].items() if k in made}
        for j in SC.crane_joints(scene):
            if j.follows:
                continue
            v = vals.get(j.name, 0.0)
            joints.set_value(j, math.radians(v) if j.kind == "ROTATE" else v / 1000.0, use_limits=False)
        bpy.context.view_layer.update()
        press(bpy.ops.fresing.pose_save, name=p["name"])
    cs.start_pose = rig_.get("start_pose", "")
    for j in SC.crane_joints(scene):
        if not j.follows:
            joints.set_value(j, 0.0, use_limits=False)
    bpy.context.view_layer.update()
    if check:
        press(bpy.ops.fresing.crane_check, clash=clash)
    return made


def _th0(data) -> float:
    lim = data.get("limits") or {}
    ang = lim.get("boom_angle") or lim.get("main_boom_angle")
    luff = next(j for j in data["rig"]["joints"] if _role(j) == "luff" and not j.get("follows"))
    return float(ang[0]) - float(luff["limits"][0]) if ang and luff.get("limits") else 0.0


def chart_csv(data) -> str:
    """The built-in charts as the CSV a user pastes (t, m)."""
    lines = []
    for c in data["charts"]:
        cfg = c.get("config") or {}
        words = []
        for k, unit in (("boom", "m"), ("jib", "m"), ("counterweight", "t"), ("outriggers", "m")):
            if isinstance(cfg.get(k), (int, float)):
                words.append(f"{k} {cfg[k]:g} {unit}")
        lines.append("; ".join(words))
        for r, cap in zip(c["radius"], c["capacity"]):
            lines.append(f"{r:g};" + ("" if cap is None else f"{cap:g}"))
    return "\n".join(lines) + "\n"


def compare(cls: str, saved: dict, made: dict) -> list:
    """Differences between the saved file and the built-in one: joints (role, kind, parts, rides on, follows +
    ratio, limits, axis within 1 mm / 0.1°), hook point (1 mm), poses, masses, CoG, charts. [] = the same."""
    data = builtin(cls)
    out = []
    mine = {j["name"]: j for j in saved["rig"]["joints"]}
    back = {v: k for k, v in made.items()}
    for j in data["rig"]["joints"]:
        m = mine.get(made.get(j["name"], ""))
        if m is None:
            out.append(f"{j['name']}: not made")
            continue
        if (m.get("role") or "") != (_role(j) or ""):
            out.append(f"{j['name']}: role {m.get('role')} != {_role(j)}")
        if m["kind"] != j["kind"]:
            out.append(f"{j['name']}: kind")
        if j["parts"] and sorted(m["parts"]) != sorted(j["parts"]):
            out.append(f"{j['name']}: parts {m['parts']} != {j['parts']}")
        if back.get(m.get("rides_on") or "", None) != j.get("rides_on"):
            out.append(f"{j['name']}: rides on {m.get('rides_on')} != {j.get('rides_on')}")
        if back.get(m.get("follows") or "", None) != j.get("follows") or \
                abs(float(m.get("ratio", 1.0)) - float(j.get("ratio", 1.0))) > 1e-6:
            out.append(f"{j['name']}: follows {m.get('follows')} {m.get('ratio')} != {j.get('follows')} "
                       f"{j.get('ratio')}")
        lj, lm = j.get("limits"), m.get("limits")
        if (lj is None) != (lm is None) or (lj and max(abs(a - b) for a, b in zip(lj, lm)) > 0.01):
            out.append(f"{j['name']}: limits {lm} != {lj}")
        u, d = np.asarray(j["direction"], float), np.asarray(m["direction"], float)
        ang = math.degrees(math.acos(min(1.0, float(np.dot(u, d)) / np.linalg.norm(u) / np.linalg.norm(d))))
        if ang > 0.1:
            out.append(f"{j['name']}: direction {ang:.3f}° off")
        if j["kind"] == "ROTATE":
            v = np.asarray(m["point"], float) - np.asarray(j["point"], float)
            u = u / np.linalg.norm(u)
            off = float(np.linalg.norm(v - np.dot(v, u) * u))
            if off > 1.0:
                out.append(f"{j['name']}: axis {off:.2f} mm off")
    for extra in set(mine) - set(made.values()):
        out.append(f"{extra}: made but not in the built-in")
    hp = np.asarray(saved["rig"]["hook"]["point"]) - np.asarray(data["rig"]["hook"]["point"])
    if np.linalg.norm(hp) > 1.0:
        out.append(f"hook point {np.linalg.norm(hp):.2f} mm off")
    want = {p["name"]: p["values"] for p in data["rig"]["poses"]}
    got = {p["name"]: p["values"] for p in saved["rig"]["poses"]}
    if set(want) != set(got):
        out.append(f"poses {sorted(got)} != {sorted(want)}")
    for name, vals in want.items():
        g = {back.get(k, k): v for k, v in got.get(name, {}).items()}
        for k in set(vals) | set(g):
            if abs(float(vals.get(k, 0.0)) - float(g.get(k, 0.0))) > 0.01:
                out.append(f"pose {name}: {k} {g.get(k)} != {vals.get(k)}")
    if saved["rig"].get("start_pose") != data["rig"].get("start_pose"):
        out.append("start pose")
    for k, v in data["mass"].items():
        if abs(float(saved["mass"].get(k, -1)) - float(v)) > 1e-6:
            out.append(f"mass {k}")
        if np.linalg.norm(np.asarray(saved["cog"].get(k, (9e9, 0, 0))) - np.asarray(data["cog"][k])) > 1e-4:
            out.append(f"cog {k}")
    LL = _m("core.lifting_library")
    a = LL.charts_of(LL.from_data(data))
    b = LL.charts_of(LL.from_data(saved))
    if len(a) != len(b):
        out.append(f"{len(b)} charts != {len(a)}")
    else:
        for ca, cb in zip(a, b):
            if set(ca.config) != set(cb.config) or any(abs(float(ca.config[k]) - float(cb.config[k])) > 1e-6
                                                       for k in ca.config if isinstance(ca.config[k], (int, float))):
                out.append(f"chart config {cb.config} != {ca.config}")
            if not np.allclose(ca.radius, cb.radius) or \
                    [x is None for x in ca.capacity] != [x is None for x in cb.capacity] or \
                    not np.allclose([x or 0 for x in ca.capacity], [x or 0 for x in cb.capacity]):
                out.append(f"chart {ca.config} differs")
    return out
