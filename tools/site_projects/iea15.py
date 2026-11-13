"""The IEA 15 MW reference turbine as a model that moves, onshore and offshore (task 0116).

``convert(step, out, variant)`` reads the owner's STEP (``iea15_source``: the IEA's SolidWorks model exported from
Fusion), moves it into the turbine frame (tower axis = z, sea level z 0, rotor upwind towards -y; onshore 14 m lower so
the ground is z 0), splits the one tower solid into tower and monopile, adds the parts Fresing invented
(``turbine_parts``: nacelle cover, door, platforms, transition piece, ...), and writes

    iea15_<variant>.step   the parts nested by what moves them: TURBINE FIXED > NACELLE YAW > ROTOR TURNING >
                           BLADE n PITCH (+ DOOR SWING, DAVIT SLEW on the fixed part)
    iea15_<variant>.json   the sheet the render kit's project maker reads (``site/render_kit/projects.py``): joints,
                           poses, the loop, decals, cameras, the scene's water level, the parts it hides and why

Every joint axis is read from round faces on both sides (``iea15_source.measure``): yaw = the tower's top cone and the
yaw bearing (fixed) + the drum on the bedplate (turning); rotor = the hollow shaft (turning) + the nose it turns on
(fixed), the hub's centre on that line; pitch = each blade's own z axis, the hub's ring face centred on it.
"""

from __future__ import annotations

import json
import math
import os

import numpy as np

from . import iea15_source as S
from . import occ, stepout

TITLE = {"offshore": "IEA 15 MW wind turbine on a monopile", "onshore": "IEA 15 MW wind turbine on land"}
SOURCE = ("IEA Wind TCP Task 37, IEA-15-240-RWT v1.0 (github.com/IEAWindSystems/IEA-15-240-RWT, Apache-2.0): its "
          "SolidWorks model (CAD/deprecated/IEA-15-240-RWT_Solidworks.zip), exported to STEP in Fusion")

FIXED, YAW, ROTOR = "TURBINE FIXED", "NACELLE YAW", "ROTOR TURNING"
DOOR, DAVIT = "DOOR SWING", "DAVIT SLEW"


def pitch_body(i: int) -> str:
    return f"BLADE {i} PITCH"


# body of turbine_parts -> sub-assembly of the STEP
BODY_OF = {"TOWER": FIXED, "NACELLE": YAW, "DOOR": DOOR, "DAVIT": DAVIT}

RATED_RPM = S.value("rated_rpm")
LOOP_THIRDS = 4                   # the loop turns the rotor 4/3 of a turn: 10.6 s at rated speed (seamless: 3 blades)
YAW_SWING = 4.0                   # degrees the nacelle yaws and back during the loop


def _hidden_notes(variant: str) -> list[dict]:
    out = [
        {"part": "MAIN BEARING SRB", "why": "SRB_mock_bearing of the source: a plain ring standing in for the main "
                                             "bearing inside the shaft (a modelling aid, never seen)"},
        {"part": "MAIN BEARING TDO", "why": "TDO_mock_bearing of the source: as the SRB ring"},
        {"part": "HUB CENTRE MARK", "why": "a ball 0.2 m across at the hub's centre in the source (a modelling aid)"},
    ] + [{"part": f"BLADE {i} ROOT DISC", "why": "a disc 2 m across and 10 mm thick at the blade root in the source "
                                                 "(a modelling aid, no part of a turbine)"} for i in (1, 2, 3)]
    if variant == "offshore":
        out.append({"part": "MONOPILE BELOW SEABED",
                    "why": "the 45 m of the monopile in the ground below the 30 m deep seabed; the app has no seabed "
                           "yet (task 0081), so it would hang in the water"})
    return out


# ---------------------------------------------------------------------------
# the source's parts in the variant's frame
# ---------------------------------------------------------------------------

def _shift(variant: str) -> np.ndarray:
    return occ.translate((0.0, 0.0, S.ONSHORE_SHIFT if variant == "onshore" else 0.0))


def _by_size(shape) -> list:
    return sorted(occ.solids(shape), key=occ.volume, reverse=True)


def source_parts(leaves, T: S.TFrame, variant: str, door_cut=None) -> tuple[list, list[str]]:
    """[(name, key, shape, M, body)] of the owner's parts for stepout.write, and notes on what was changed."""
    W0 = _shift(variant) @ T.M
    notes = []
    out = []

    def place(lf):
        return W0 @ lf.M

    # the tower: one solid from the pile tip to the tower top -> tower | monopile (| below the seabed)
    tw = S.one(leaves, "tower")
    solid = occ.moved(tw.shape, place(tw))
    zb = S.SPLIT_Z + (S.ONSHORE_SHIFT if variant == "onshore" else 0.0)
    big = 30000.0

    def slab(z0, z1):
        return occ.box((-big, -big, z0), (big, big, z1))
    tower = occ.one_solid(occ.common(solid, slab(zb, 400000.0)), "tower")
    if door_cut is not None:
        tower = occ.one_solid(occ.cut(tower, door_cut), "tower with its door opening")
        notes.append("A door opening is cut into the tower (invented, as the door).")
    out.append(("TOWER", "tower", tower, np.eye(4), FIXED))
    notes.append("The source's one tower solid (pile tip -75 m to the tower top) is cut at +15 m (the IEA's tower "
                 "base / transition piece height) into the tower and the monopile.")
    if variant == "offshore":
        sb = -1000.0 * S.value("water_depth_m")
        out.append(("MONOPILE", "monopile", occ.one_solid(occ.common(solid, slab(sb, zb)), "monopile"),
                    np.eye(4), FIXED))
        out.append(("MONOPILE BELOW SEABED", "monopile below", occ.one_solid(occ.common(solid, slab(-big * 10, sb)),
                                                                             "monopile below"), np.eye(4), FIXED))
    else:
        notes.append("Onshore: the monopile is left out; the tower stands on an invented concrete pedestal, 14 m "
                     "lower than offshore (hub 136.5 m above the ground).")

    single = {"newyaw_bearing": ("YAW BEARING", FIXED), "misc_equipment": ("NACELLE DRUM", YAW),
              "newNosePiece": ("NOSE", YAW), "stator": ("STATOR", YAW), "newRotor": ("GENERATOR ROTOR", ROTOR),
              "shaft": ("SHAFT", ROTOR), "SRB_mock_bearing": ("MAIN BEARING SRB", YAW),
              "TDO_mock_bearing": ("MAIN BEARING TDO", YAW)}
    for proto, (name, body) in single.items():
        lf = S.one(leaves, proto)
        out.append((name, proto, occ.one_solid(lf.shape, name), place(lf), body))
    for i, lf in enumerate(S.by_proto(leaves, "flange_2"), start=1):
        out.append((f"NOSE FLANGE {i}", "flange_2", occ.one_solid(lf.shape, "flange"), place(lf), YAW, "NOSE FLANGE"))
    bp = S.one(leaves, "bedplate")
    parts = _by_size(bp.shape)
    out.append(("BEDPLATE", "bedplate", parts[0], place(bp), YAW))
    if len(parts) > 1:
        notes.append(f"The bedplate's {len(parts) - 1} extra solids of the source (slivers of no volume at its front) "
                     "are left out.")
    hub = S.one(leaves, "Hub")
    parts = _by_size(hub.shape)
    out.append(("HUB", "hub", parts[0], place(hub), ROTOR))
    for k, extra in enumerate(parts[1:]):
        out.append(("HUB CENTRE MARK" + (f" {k + 1}" if k else ""), f"hub extra {k}", extra, place(hub), ROTOR))
    for i, (skin, disc) in enumerate(S.blades(leaves), start=1):
        out.append((f"BLADE {i}", "blade skin", _mirrored(skin.shape), place(skin), pitch_body(i), "BLADE"))
        out.append((f"BLADE {i} ROOT DISC", "blade disc", occ.one_solid(disc.shape, "disc"), place(disc),
                    pitch_body(i), "BLADE ROOT DISC"))
    return out, notes


_MIRRORED: list = []


def _mirrored(skin_shape):
    """One mirrored copy per source blade shape (the three blades share one shape, as in the source)."""
    for shape, mirrored in _MIRRORED:
        if shape.IsSame(skin_shape):
            return mirrored
    light, dev = light_blade(skin_shape, mirror=True)
    LIGHT_DEVIATION[0] = dev
    _MIRRORED[:] = [(skin_shape, light)] + _MIRRORED[:3]
    return _MIRRORED[0][1]


LIGHT_DEVIATION = [0.0]


def bodies(variant: str, top: str) -> dict:
    b = {FIXED: top, YAW: FIXED, ROTOR: YAW, DOOR: FIXED}
    for i in (1, 2, 3):
        b[pitch_body(i)] = ROTOR
    if variant == "offshore":
        b[DAVIT] = FIXED
    return b


# ---------------------------------------------------------------------------
# joints, poses, the loop
# ---------------------------------------------------------------------------

def _r(v, n=4):
    return [round(float(x), n) for x in v]


def leading_edge_side(skin_shape) -> np.ndarray:
    """Unit vector (blade coordinates, square to its z) from the chord's middle towards the leading edge, at
    mid-span: the round nose is many times thicker near its end of the chord than the sharp trailing edge."""
    big = max(occ.faces(skin_shape), key=lambda f: occ.surface(f)["area"])
    pts = occ.surface_points(big, 300)
    s = pts[np.abs(pts[:, 2] - 60000.0) < 1500.0][:, :2]           # the skin around mid-span
    if len(s) < 20:
        raise RuntimeError("the blade's mid-span section was not found")
    c = s.mean(axis=0)
    _u, _sv, vt = np.linalg.svd(s - c)
    chord, across = vt[0], vt[1]
    t, n = (s - c) @ chord, (s - c) @ across
    lo, hi = t.min(), t.max()
    near_lo, near_hi = t < lo + 0.08 * (hi - lo), t > hi - 0.08 * (hi - lo)
    side = -chord if np.ptp(n[near_lo]) > np.ptp(n[near_hi]) else chord
    return np.array([side[0], side[1], 0.0])


LIGHT_GRID = (121, 161)          # points round the airfoil x along the span sampled from the source blade
LIGHT_TOL = 3.0                 # mm: the light blade's surface stays this close to the sampled points


def _spans(n: int) -> np.ndarray:
    """Span parameters 0 … 1: even, with more near the tip where the chord narrows fast."""
    return np.unique(np.round(np.concatenate([np.linspace(0.0, 1.0, n - 24), np.linspace(0.94, 1.0, 25)]), 9))


def light_blade(skin_shape, mirror: bool = True):
    """The blade's skin as a light surface: the source's one B-spline has 4,343 x 203 control points, which
    OpenCascade meshes in minutes into a few dozen triangles (the blades were all but invisible in the app). A grid
    of points (``LIGHT_GRID``) sampled from it – mirrored in the blade's x-z plane (``mirror``, see
    ``mirrored_blade``) – is approximated by a B-spline within ``LIGHT_TOL``; the face keeps the source's outward
    side. Returns (shell, deviation in mm measured at points between the grid's)."""
    from OCP.BRep import BRep_Builder
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.GeomAbs import GeomAbs_C2
    from OCP.GeomAPI import GeomAPI_PointsToBSplineSurface, GeomAPI_ProjectPointOnSurf
    from OCP.gp import gp_Pnt
    from OCP.collections import Array2_gp_Pnt as TColgp_Array2OfPnt
    from OCP.TopoDS import TopoDS_Shell

    big = max(occ.faces(skin_shape), key=lambda f: occ.surface(f)["area"])
    src = BRepAdaptor_Surface(big)
    u0, u1, v0, v1 = src.FirstUParameter(), src.LastUParameter(), src.FirstVParameter(), src.LastVParameter()
    nu, _nv = LIGHT_GRID
    us = np.linspace(u0, u1, nu)
    vs = v0 + (v1 - v0) * _spans(LIGHT_GRID[1])
    sign = -1.0 if mirror else 1.0
    if mirror:
        us = us[::-1]                                   # mirrored, walked the other way round: the same outer side
    arr = TColgp_Array2OfPnt(1, len(us), 1, len(vs))
    for i, u in enumerate(us):
        for j, v in enumerate(vs):
            p = src.Value(float(u), float(v))
            arr.SetValue(i + 1, j + 1, gp_Pnt(p.X(), sign * p.Y(), p.Z()))
    fit = GeomAPI_PointsToBSplineSurface(arr, 3, 8, GeomAbs_C2, LIGHT_TOL)
    if not fit.IsDone():
        raise RuntimeError("the light blade surface could not be fitted")
    surf = fit.Surface()
    face = BRepBuilderAPI_MakeFace(surf, 1e-3).Face()
    # deviation at points half way between the grid's
    worst = 0.0
    for u in (us[:-1] + us[1:])[::6] / 2:
        for v in (vs[:-1] + vs[1:])[::8] / 2:
            p = src.Value(float(u), float(v))
            q = gp_Pnt(p.X(), sign * p.Y(), p.Z())
            proj = GeomAPI_ProjectPointOnSurf(q, surf)
            if proj.NbPoints():
                worst = max(worst, float(proj.LowerDistance()))
    shell = TopoDS_Shell()
    b = BRep_Builder()
    b.MakeShell(shell)
    b.Add(shell, face)
    return shell, worst


def mirrored_blade(skin_shape):
    """The blade mirrored in its own x-z plane (the plane through its pitch axis and, at the CAD pose, the shaft):
    the source's blades are drawn for a rotor that turns anticlockwise seen from the front; mirrored they turn
    clockwise like the IEA's turbine. Root, length, pre-bend (along x) and twist stay; the leading edge changes side."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt, gp_Trsf
    t = gp_Trsf()
    t.SetMirror(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 1, 0)))
    return BRepBuilderAPI_Transform(skin_shape, t, True).Shape()


def joints(fit: dict, leaves, T: S.TFrame, variant: str, extra: list[dict]) -> list[dict]:
    """The sheet's joints (mm, the variant's frame). Positive rotor values turn it clockwise seen from the front
    (as wind turbines turn); positive pitch turns a blade's leading edge into the wind (towards feather)."""
    rot = fit["rotor"]
    down = -np.array(rot["direction"])                      # downwind along the shaft
    out = [
        {"name": "Yaw", "kind": "ROTATE", "parts": [YAW], "point": [0.0, 0.0, round(fit["tower_top_z"], 3)],
         "direction": [0.0, 0.0, 1.0], "rides_on": None, "limits": [-180.0, 180.0],
         "source": "yaw axis: the tower's top cone and the yaw bearing (fixed) and the drum on the bedplate (turning) "
                   f"share it within {max(fit['yaw']['bearing_off_mm'], fit['yaw']['nacelle_off_mm']):.3f} mm"},
        {"name": "Rotor", "kind": "ROTATE", "parts": [ROTOR], "point": _r(rot["point"], 3), "direction": _r(down, 6),
         "rides_on": "Yaw", "limits": None,
         "source": f"shaft axis: the hollow shaft (r {rot['shaft_radii']}) and the nose it turns on (r "
                   f"{rot['nose_radii']}) are one line ({rot['nose_off_mm']:.3f} mm, {rot['nose_angle_deg']:.4f}°); "
                   f"the hub's centre lies on it ({rot['hub_off_mm']:.3f} mm); tilt {fit['shaft_tilt_deg']:.3f}°"},
    ]
    W = _shift(variant) @ T.M
    for (skin, _disc), b in zip(S.blades(leaves), fit["blades"]):
        G = W @ skin.M
        le = G[:3, :3] @ leading_edge_side(_mirrored(skin.shape))      # leading edge, in the frame
        z = np.array(b["direction"])
        motion = np.cross(down, np.array(b["point"]) - np.array(rot["point"]))   # clockwise from the front
        if float(le @ motion) < 0:
            raise RuntimeError(f"blade {b['index']}: its leading edge does not lead the rotor's turn")
        # +90 about the axis must bring the leading edge to face upwind (-down)
        turned = np.cross(z, le)                              # le turned +90° about z
        axis = z if float(turned @ -down) > 0 else -z
        out.append({"name": f"Pitch {b['index']}", "kind": "ROTATE", "parts": [pitch_body(b["index"])],
                    "point": _r(b["point"], 3), "direction": _r(axis, 6), "rides_on": "Rotor",
                    "limits": [-5.0, 95.0],
                    "source": f"blade {b['index']}'s own z axis (its pitch axis); the hub's ring face is centred on "
                              f"it ({b['ring_off_mm']:.3f} mm, {b['ring_normal_deg']:.4f}°), the root's edge "
                              f"{b['root_off_axis_mm']:.0f} mm off it (the root is not quite round)"})
    for j in extra:
        out.append({"name": j["name"], "kind": j["kind"], "parts": [BODY_OF[j["body"]]], "point": _r(j["point"], 3),
                    "direction": _r(j["direction"], 6), "rides_on": None, "limits": list(j["limits"]),
                    "source": "invented part (turbine_parts): " + j.get("source", "its hinge")})
    return out


def rotor_up_angle(fit: dict) -> float:
    """Rotor value (deg, clockwise from the front) that puts the blade nearest the top straight up."""
    rot = fit["rotor"]
    a = np.array(rot["direction"])                           # upwind
    up = np.array([0.0, 0.0, 1.0]) - a[2] * a
    up /= np.linalg.norm(up)
    right = np.cross(up, a)                                  # seen from the front (looking downwind): right
    best = None
    for b in fit["blades"]:
        d = np.array(b["direction"]) - (np.array(b["direction"]) @ a) * a
        ang = math.degrees(math.atan2(float(d @ right), float(d @ up)))   # clockwise from the top
        if best is None or abs(ang) < abs(best):
            best = ang
    return -best


def poses_and_loop(fit: dict, variant: str, extra: list[dict]) -> tuple[list, dict]:
    r0 = round(rotor_up_angle(fit), 3)
    door = next((j for j in extra if j["name"] == "Door"), None)
    davit = next((j for j in extra if j["name"] == "Davit"), None)
    running = {"Yaw": 0.0, "Rotor": r0, "Pitch 1": 0.0, "Pitch 2": 0.0, "Pitch 3": 0.0}
    poses = [
        {"name": "Running", "values": dict(running)},
        {"name": "Feathered", "values": {**running, "Pitch 1": 90.0, "Pitch 2": 90.0, "Pitch 3": 90.0}},
    ]
    if door:
        opened = {**running, "Pitch 1": 90.0, "Pitch 2": 90.0, "Pitch 3": 90.0,
                  "Door": float(door["open"] if "open" in door else door["limits"][1])}
        if davit:
            opened["Davit"] = float(davit.get("out", davit["limits"][1]))
        poses.append({"name": "Door open", "values": opened})
    turn = 120.0 * LOOP_THIRDS
    secs = round(turn / (RATED_RPM * 6.0), 4)
    loop = {"name": "Turbine running", "seconds": secs, "loop": True, "periods": {"Rotor": 120.0},
            "camera": "Whole turbine" if variant == "offshore" else "From the field",
            "note": f"the rotor at the IEA's rated {RATED_RPM} rpm turns {LOOP_THIRDS}/3 of a turn: with three blades "
                    "the last frame looks like the first",
            "steps": [
                {"kind": "JOINT", "joint": "Rotor", "to": r0 + turn, "start": 0.0, "seconds": secs,
                 "easing": "LINEAR", "label": "Rotor at rated speed"},
                {"kind": "JOINT", "joint": "Yaw", "to": YAW_SWING, "start": 0.0, "seconds": round(secs / 2, 4),
                 "easing": "SMOOTH", "label": "Yaw a little"},
                {"kind": "JOINT", "joint": "Yaw", "to": 0.0, "start": round(secs / 2, 4),
                 "seconds": round(secs - round(secs / 2, 4), 4), "easing": "SMOOTH", "label": "Yaw back"},
            ]}
    return poses, loop


def check_animation(poses: list, js: list[dict]) -> dict:
    """Built only by the clash check of tools/make_site_projects.py: the poses, then every joint but the rotor
    through its whole range (both limits) and back, the nacelle yawing ±10° last."""
    names = [p["name"] for p in poses]
    steps, t = [], 0.0
    for p in ["Feathered"] + (["Door open"] if "Door open" in names else []) + ["Running"]:
        steps.append({"kind": "POSE", "pose": p, "start": t, "seconds": 2.0, "easing": "SMOOTH"})
        t += 2.0
    start = next(p for p in poses if p["name"] == "Running")["values"]
    for j in js:
        if j["name"] in ("Rotor", "Yaw") or not j.get("limits"):
            continue
        back = float(start.get(j["name"], 0.0))
        for to in (j["limits"][0], j["limits"][1], back):
            steps.append({"kind": "JOINT", "joint": j["name"], "to": float(to), "start": t, "seconds": 1.0,
                          "easing": "SMOOTH", "label": f"{j['name']} {float(to):+.0f}"})
            t += 1.0
    for yaw in (-10.0, 10.0, 0.0):
        steps.append({"kind": "JOINT", "joint": "Yaw", "to": yaw, "start": t, "seconds": 1.0, "easing": "SMOOTH",
                      "label": f"Yaw {yaw:+.0f}"})
        t += 1.0
    return {"name": "Check every joint", "seconds": t, "loop": False, "steps": steps}


# ---------------------------------------------------------------------------
# the whole conversion
# ---------------------------------------------------------------------------

NOTICE = ("Modified copy of the IEA-15-240-RWT v1.0 reference turbine (IEA Wind TCP Task 37, Apache-2.0, "
          "github.com/IEAWindSystems/IEA-15-240-RWT): moved to the turbine frame, tower cut into tower and monopile, "
          "parts invented and added by Fresing (nacelle cover, doors, platforms, monopile details); see site/CREDITS.md "
          "of github.com/smholte/CAD-render-animation")


def stamp(path: str, variant: str) -> None:
    """Apache-2.0 4(b): the written STEP says in its header that it is a changed copy and of what."""
    import re
    with open(path, encoding="latin-1") as fh:
        text = fh.read()
    desc = f"FILE_DESCRIPTION(('{NOTICE} ({variant})'),'2;1');"
    new, n = re.subn(r"FILE_DESCRIPTION\s*\(.*?\)\s*;", lambda _m: desc, text, count=1, flags=re.S)
    if n != 1:
        raise RuntimeError(f"{path}: no FILE_DESCRIPTION in its header")
    with open(path, "w", encoding="latin-1", newline="") as fh:
        fh.write(new)


def _lowest(parts: list, hidden: set) -> float:
    """The lowest point (z, mm) of the parts left visible: the app puts its floor there, less the floor gap. On land
    the slab and gravel reach below the ground (z 0), so the gap is that depth, negative: the ground at z 0."""
    return min(float((occ.bbox(occ.moved(p[2], p[3])) if not np.allclose(p[3], np.eye(4))
                      else occ.bbox(p[2]))[0][2]) for p in parts if p[0] not in hidden)


def _parts_module():
    from . import turbine_parts
    return turbine_parts


def convert(step: str, out_dir: str, write_step: bool = True, variant: str = "offshore", leaves=None) -> dict:
    """``iea15_<variant>.step`` (unless ``write_step`` is False) and ``iea15_<variant>.json`` into ``out_dir``."""
    if variant not in S.VARIANTS:
        raise ValueError(variant)
    os.makedirs(out_dir, exist_ok=True)
    leaves = leaves if leaves is not None else S.read(step)
    T = S.TFrame(leaves)
    measured = S.measure(leaves, T)
    fit = S.fit(leaves, variant, T, measured)
    tp = _parts_module()
    made = tp.make(fit, variant)
    extra = tp.joints(fit, variant)
    src, notes = source_parts(leaves, T, variant, tp.door_cut(fit, variant))
    notes.append("The source's blades are drawn for a rotor that turns anticlockwise seen from the front (their "
                 "leading edges point that way at 30, 60 and 90 m); the IEA's turbine, like every big one, turns "
                 "clockwise. Each blade is mirrored in its own plane through the pitch axis and the shaft: root, "
                 "length, pre-bend and twist stay, the leading edge leads the clockwise turn.")
    parts = list(src)
    for p in made:
        occ.one_solid(p.shape, p.name)
        parts.append((p.name, p.name, p.shape, np.eye(4), BODY_OF[p.body]))
    names = [p[0] for p in parts]
    dup = {n for n in names if names.count(n) > 1}
    if dup:
        raise RuntimeError(f"part names used twice: {sorted(dup)}")
    model = f"iea15_{variant}"
    step_name = f"{model}.step"
    counts = {}
    if write_step:
        counts = stepout.write(os.path.join(out_dir, step_name), model.upper(), bodies(variant, model.upper()),
                               parts)
    if write_step:
        stamp(os.path.join(out_dir, step_name), variant)
    js = joints(fit, leaves, T, variant, extra)
    sheet_hidden = {h["part"] for h in _hidden_notes(variant)}
    poses, loop = poses_and_loop(fit, variant, extra)
    by_body: dict = {}
    for p in parts:
        by_body[p[4]] = by_body.get(p[4], 0) + 1
    numbers = {
        "hub_height_m": (round(measured["hub_height_m"] + fit["z_shift"] / 1000.0, 3),
                         "measured: the hub's centre above the sea (offshore) / the ground (onshore)"),
        "rotor_diameter_m": (round(measured["rotor_diameter_m"], 3), "measured: twice the farthest blade point "
                                                                     "from the rotor axis"),
        "shaft_tilt_deg": (round(measured["shaft_tilt_deg"], 4), "measured: the shaft's axis"),
        "precone_deg": (round(measured["precone_deg"], 4), "measured: blade axes against the rotor plane (the CAD "
                                                           "has none; IEA 4°)"),
        "overhang_m": (round(measured["overhang_m"], 3), "measured: the hub's centre from the tower axis, level"),
        "tower_top_m": (round(measured["tower_top_z"] / 1000.0, 3), "measured: top of the tower solid (offshore "
                                                                    "frame, above the sea)"),
        "blade_length_m": (round(measured["blade_length_m"], 3), "measured: the blade skin along its own z"),
        "prebend_m": (round(measured["prebend_m"], 3), "measured: the blade tip off its own z axis"),
    }
    sheet = {
        "model": model, "title": TITLE[variant], "step": step_name, "units": "mm", "up_axis": "Z",
        "source": SOURCE, "iea_commit": S.IEA_COMMIT,
        "iea": {k: {"value": v, "source": s} for k, (v, s) in S.IEA.items()},
        "measured": {k: {"value": v, "source": s} for k, (v, s) in numbers.items()},
        "frame": {"turn_deg": measured["turn_deg"], "z_shift_mm": fit["z_shift"],
                  "note": "turbine frame: tower axis = z, sea level z 0 (onshore: ground z 0, 14 m lower), rotor "
                          "upwind towards -y (+y = north)"},
        "parts": len(parts), "bodies": dict(sorted(by_body.items())),
        "invented": sorted(p.name for p in made),
        "joints": js, "cylinders": [], "hide": _hidden_notes(variant),
        "poses": poses, "start_pose": "Running", "animation": loop,
        "check_animation": check_animation(poses, js),
        "decals": tp.anchors(fit, variant), "cameras": tp.cameras(fit, variant),
        "scene": ({"water_level_m": round(-(fit["seabed_z"]) / 1000.0, 3)} if variant == "offshore"
                  else {"floor_offset_m": round(_lowest(parts, sheet_hidden) / 1000.0, 4)}),
        "notes": notes,
    }
    if counts:
        sheet["unique_parts"] = counts.get("unique")
    with open(os.path.join(out_dir, f"{model}.json"), "w", encoding="utf-8") as fh:
        json.dump(sheet, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    return sheet
