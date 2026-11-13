"""The CEB brick press (goscommons/CEB-Press, Open Source Ecology, CC BY-SA 4.0) as a model that moves (task 0112).

``convert(src, out_dir)`` reads ``CEB CAD Assembly.fcstd`` of ``src`` (the repository's ``01_Hardware/CAD`` folder)
like ``tools/fcstd_to_step.py`` (each stored sub-assembly shape -> its shells as parts "<PREFIX> PART n") and writes
``ceb_press.step`` + ``ceb_press.json`` (the sheet of ``site/render_kit/projects.py``). What it changes, all said in the
sheet's ``notes``:

* Both hydraulic cylinders are one solid each in the source (barrel and rod fused). They are split along the rod: the
  rod is what lies within a cylinder round the rod's own axis (between the rod and the barrel's gland), the barrel is
  the rest. So the rod can slide, it goes on inside the barrel as far as its stroke, in a bore cut for it.
* The main cylinder sub-assembly sits ~11 mm off the compression chamber in the source (its press plate cuts 11 mm
  into the chamber's end plate, its clevis into the lugs): it is moved onto the chamber's middle.
* Moving bodies become sub-assemblies: PRESS PLATE (on the main cylinder's rod), MAIN CYLINDER BARREL / ROD, DRAWER,
  DRAWER CYLINDER BARREL / ROD; the pins and bushings stay with the frame.

Motion: two slide joints ("Press plate" along the main cylinder, "Drawer" along the drawer cylinder, + = rod out) and
two app cylinders in follow mode (barrel pinned to the frame, rod eye on the plate / the drawer). The loop: the
compression chamber fills through the drawer, the drawer closes it, the plate presses, the drawer opens, the plate
lifts the brick, the drawer pushes it out, everything goes back – 10 s.
"""

from __future__ import annotations

import json
import math
import os
import re
import zipfile

import numpy as np

from . import a4, stepout

TOP = "CEB PRESS"
SRC_FILE = "CEB CAD Assembly.fcstd"
SHAPE_RE = re.compile(r'<Object name="([^"]+)"[^>]*>(?:(?!</Object>).)*?<Property name="Shape" '
                      r'type="Part::PropertyPartShape"[^>]*>\s*<Part file="([^"]+\.brp)"', re.S)

MAIN = "Cylinder_SubAssembly_01"
SECOND = "Cylinder_secondary_Subassembly_01"
DRAWER = "Drawer_SubAssembly_01"
FRAME = "Frame_SubAssembly_01"

PLATE_TRAVEL = 200.0          # mm the plate goes down from the CAD place (the brick pushed out, level with the table)
DRAWER_OUT, DRAWER_IN = 100.0, 140.0      # mm the drawer cylinder's rod goes out / in from the CAD place (its guides
#                                           meet the frame's posts at ~120 mm out)


# ---------------------------------------------------------------------------
# geometry helpers (OpenCascade)
# ---------------------------------------------------------------------------

def _shells(shape):
    from OCP.TopAbs import TopAbs_SHELL, TopAbs_SOLID
    from OCP.TopExp import TopExp_Explorer
    kind = TopAbs_SOLID if TopExp_Explorer(shape, TopAbs_SOLID).More() else TopAbs_SHELL
    ex = TopExp_Explorer(shape, kind)
    out = []
    while ex.More():
        out.append(ex.Current())
        ex.Next()
    return out


def bbox(shape) -> tuple[np.ndarray, np.ndarray]:
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    b = Bnd_Box()
    BRepBndLib.Add_s(shape, b)
    lo, hi = b.CornerMin(), b.CornerMax()
    return np.array([lo.X(), lo.Y(), lo.Z()]), np.array([hi.X(), hi.Y(), hi.Z()])


def volume(shape) -> float:
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    g = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, g)
    return abs(g.Mass())


def cylinders_of(shape) -> list[tuple[float, np.ndarray, np.ndarray, float, float]]:
    """(radius, point on the axis, direction, from, to along the axis) of every cylindrical face."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS
    from OCP.BRep import BRep_Tool
    from OCP.TopAbs import TopAbs_VERTEX
    out = []
    ex = TopExp_Explorer(shape, TopAbs_FACE)
    while ex.More():
        f = TopoDS.Face(ex.Current())
        a = BRepAdaptor_Surface(f)
        if a.GetType() == GeomAbs_Cylinder:
            c = a.Cylinder()
            ax = c.Axis()
            o = np.array([ax.Location().X(), ax.Location().Y(), ax.Location().Z()])
            d = np.array([ax.Direction().X(), ax.Direction().Y(), ax.Direction().Z()])
            ts = []
            vx = TopExp_Explorer(f, TopAbs_VERTEX)
            while vx.More():
                p = BRep_Tool.Pnt_s(TopoDS.Vertex(vx.Current()))
                ts.append(float(np.dot(np.array([p.X(), p.Y(), p.Z()]) - o, d)))
                vx.Next()
            if ts:
                out.append((c.Radius(), o, d, min(ts), max(ts)))
        ex.Next()
    return out


def _solid(shell):
    """A closed shell as a solid (the source keeps the sub-assemblies as shells)."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeSolid
    from OCP.ShapeFix import ShapeFix_Solid
    from OCP.TopAbs import TopAbs_SOLID
    from OCP.TopoDS import TopoDS
    if shell.ShapeType() == TopAbs_SOLID:
        return shell
    s = BRepBuilderAPI_MakeSolid(TopoDS.Shell(shell)).Solid()
    fix = ShapeFix_Solid(s)
    fix.Perform()
    return fix.Solid()


def _tube(o, d, r: float, t0: float, t1: float):
    """A solid cylinder of radius r round the line (o, d) from t0 to t1 along it."""
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
    p = o + d * t0
    return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(*map(float, p)), gp_Dir(*map(float, d))), r, t1 - t0).Shape()


def _one(shape):
    """The biggest solid of a boolean's result."""
    from OCP.TopAbs import TopAbs_SOLID
    from OCP.TopExp import TopExp_Explorer
    ex = TopExp_Explorer(shape, TopAbs_SOLID)
    best, vol = None, -1.0
    while ex.More():
        v = volume(ex.Current())
        if v > vol:
            best, vol = ex.Current(), v
        ex.Next()
    if best is None:
        raise RuntimeError("a cylinder split left no solid")
    return best


def split_cylinder(shell, rod_r: float, stroke_out: float, bore: float, end_r: float = 30.0):
    """Barrel and rod of a cylinder made as one solid. The rod: what lies within the rod's radius (+0.3 mm) along the
    rod's long round face, and within ``end_r`` beyond its end (the eye or clevis at the tip); the barrel: the rest.
    So the rod can slide out, it goes on ``stroke_out`` mm behind its root, in a bore of ``bore`` mm cut into the
    barrel. Returns (barrel, rod, a point on the axis, the direction barrel -> tip, root t, tip t)."""
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common, BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
    solid = _solid(shell)
    faces = [c for c in cylinders_of(solid) if abs(c[0] - rod_r) < 0.05]
    if not faces:
        raise RuntimeError(f"no rod of radius {rod_r} mm in the cylinder")
    _r, o, d, t0, t1 = max(faces, key=lambda c: c[4] - c[3])          # the rod's long face
    lo, hi = bbox(solid)
    if np.dot((lo + hi) / 2.0 - o, d) > (t0 + t1) / 2.0:                # point d from the barrel to the rod's tip
        d, t0, t1 = -d, -t1, -t0
    span = float(np.dot(hi - lo, np.abs(d)))
    tool = BRepAlgoAPI_Fuse(_tube(o, d, rod_r + 0.3, t0, t1 + 0.01), _tube(o, d, end_r, t1, t1 + span)).Shape()
    rod = _one(BRepAlgoAPI_Common(solid, tool).Shape())
    barrel = _one(BRepAlgoAPI_Cut(solid, tool).Shape())
    if stroke_out > 0:
        rod = _one(BRepAlgoAPI_Fuse(rod, _tube(o, d, rod_r, t0 - stroke_out, t0 + 0.5)).Shape())
    barrel = _one(BRepAlgoAPI_Cut(barrel, _tube(o, d, rod_r + 0.5, t0 - bore, t0 + 0.5)).Shape())
    tip = max(float(np.dot(np.array(c) - o, d)) for c in _corners(rod))
    return barrel, rod, o, d, t0, tip


def _corners(shape):
    lo, hi = bbox(shape)
    return [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]


def _translated(shape, v):
    from OCP.gp import gp_Trsf, gp_Vec
    from OCP.TopLoc import TopLoc_Location
    t = gp_Trsf()
    t.SetTranslation(gp_Vec(*map(float, v)))
    return shape.Moved(TopLoc_Location(t))


# ---------------------------------------------------------------------------
# the conversion
# ---------------------------------------------------------------------------

def read(src: str) -> dict:
    """{sub-assembly object name: [shapes]} of the source assembly."""
    z = zipfile.ZipFile(os.path.join(src, SRC_FILE))
    out = {}
    for name, fn in SHAPE_RE.findall(z.read("Document.xml").decode("utf-8")):
        out[name] = _shells(a4.read_brep(z.read(fn)))
    return out


def _name(obj: str) -> tuple[str, str]:
    """(sub-assembly name, part prefix) as fcstd_to_step names them."""
    return re.sub(r"_0\d$", "", obj).replace("_", " "), obj.split("_")[0].upper()


def chamber_shift(subs: dict) -> np.ndarray:
    """How far the main cylinder sub-assembly must move so its press plate (its widest piece) sits in the middle of the
    compression chamber, between the chamber's two end plates: the frame's plates thinner than 15 mm in y that span
    the press plate's width and height."""
    plate = max(subs[MAIN], key=lambda sh: float(np.prod((bbox(sh)[1] - bbox(sh)[0])[:2])))
    plo, phi = bbox(plate)
    mid = (plo + phi) / 2.0
    below, above = -1e9, 1e9
    for sh in subs[FRAME]:
        lo, hi = bbox(sh)
        if hi[1] - lo[1] > 15.0 or lo[0] > plo[0] or hi[0] < phi[0] or lo[2] > plo[2] or hi[2] < phi[2]:
            continue
        if hi[1] <= mid[1]:
            below = max(below, hi[1])
        elif lo[1] >= mid[1]:
            above = min(above, lo[1])
    if below < -1e8 or above > 1e8:
        raise RuntimeError("the compression chamber's end plates were not found")
    return np.array([0.0, (below + above) / 2.0 - mid[1], 0.0])


def clear_drawer_way(subs: dict, travel: tuple[float, float]) -> tuple[dict, list]:
    """The drawer does not quite fit its way through the frame in the source: the plates above it reach 3.4 mm down
    into it, and it is 1.6 mm wider than the gap between the two posts at the chamber (and 1.9 mm off their middle).
    Its height is right (the rails on top fit the frame's slots). So cut from the frame what lies in the box the
    drawer's body (its plates and walls) sweeps along its travel. Returns ({frame shell index: trimmed solid},
    [(index, deepest cut in mm)])."""
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Pnt
    body = [sh for sh in subs[DRAWER] if (bbox(sh)[1] - bbox(sh)[0])[0] > 300.0]       # its plates and walls
    dlo = np.array([bbox(sh)[0] for sh in body]).min(axis=0)
    dhi = np.array([bbox(sh)[1] for sh in body]).max(axis=0)
    lo_box = np.array([dlo[0] - 0.05, dlo[1] + min(travel), dlo[2] + 0.05])
    hi_box = np.array([dhi[0] + 0.05, dhi[1] + max(travel), dhi[2] + 0.05])
    out, cut = {}, []
    for i, sh in enumerate(subs[FRAME]):
        lo, hi = bbox(sh)
        inner_lo, inner_hi = np.maximum(lo, lo_box), np.minimum(hi, hi_box)
        if np.any(inner_hi - inner_lo <= 0.01):
            continue
        box = BRepPrimAPI_MakeBox(gp_Pnt(*map(float, lo_box)), gp_Pnt(*map(float, hi_box))).Shape()
        out[i] = _one(BRepAlgoAPI_Cut(_solid(sh), box).Shape())
        cut.append((i, float(min(inner_hi - inner_lo))))
    return out, cut


def convert(src: str, out_dir: str, write_step: bool = True) -> dict:
    subs = read(src)
    shift = chamber_shift(subs)
    # the drawer moves along y (its cylinder's axis): from DRAWER_IN towards +y to DRAWER_OUT towards -y
    trimmed, cut = clear_drawer_way(subs, (-DRAWER_OUT, DRAWER_IN))
    if not 5.0 < abs(shift[1]) < 15.0:
        raise RuntimeError(f"the main cylinder is {shift[1]:.1f} mm off the chamber – expected about 11 mm")
    rows, bodies = [], {}

    def add(body, parent, pname, shape):
        from OCP.TopLoc import TopLoc_Location
        t = shape.Location().Transformation()
        M = np.eye(4)
        for i in range(3):
            for j in range(4):
                M[i, j] = t.Value(i + 1, j + 1)
        bodies.setdefault(body, parent)
        rows.append((pname, ("ceb", body, len(rows)), shape.Located(TopLoc_Location()), M, body))

    notes = []
    # main cylinder: plate (top pieces), barrel+clevis, rod; pin and bushings with the frame
    main = [_translated(s, shift) for s in subs[MAIN]]
    body = max(main, key=lambda s: bbox(s)[1][2] - bbox(s)[0][2])                 # the long one: barrel + rod
    blo, bhi = bbox(body)
    barrel, rod, mo, md, mroot, mtip = split_cylinder(body, 34.92, 0.0, PLATE_TRAVEL + 20.0)
    notes.append(f"main cylinder moved {shift[1]:+.2f} mm along y onto the compression chamber's middle")
    notes.append("main cylinder split into barrel and rod (rod Ø69.85 mm), a bore of "
                 f"{PLATE_TRAVEL + 20:.0f} mm in the barrel for the rod's stroke")
    pin_main = None
    n_plate = n_mount = 0
    for s in main:
        if s is body:
            continue
        lo, hi = bbox(s)
        if lo[2] >= bhi[2] - 40.0:                                                   # the plate and its adapter
            n_plate += 1
            add("PRESS PLATE", TOP, f"PLATE PART {n_plate}", s)
        elif hi[2] <= blo[2] + 1.0 and (hi - lo)[1] > 2.5 * (hi - lo)[0]:             # the bottom pin (along y)
            n_mount += 1
            add("MAIN CYLINDER MOUNT", TOP, "PIN OF MAIN CYLINDER", s)
            pin_main = s
        elif hi[2] <= blo[2] + 1.0 and abs((hi + lo)[0] / 2 - (bhi + blo)[0] / 2) < 80 and (hi - lo)[1] > 120:
            add("MAIN CYLINDER BARREL", TOP, "CLEVIS OF MAIN CYLINDER", s)              # the clevis turns with the barrel
        else:
            n_mount += 1
            add("MAIN CYLINDER MOUNT", TOP, f"BUSHING {n_mount} OF MAIN CYLINDER", s)
    add("MAIN CYLINDER BARREL", TOP, "BARREL OF MAIN CYLINDER", barrel)
    add("MAIN CYLINDER ROD", TOP, "ROD OF MAIN CYLINDER", rod)
    if pin_main is None:
        raise RuntimeError("the main cylinder's bottom pin was not found")

    # drawer cylinder: the pin with the frame, barrel and rod
    sec = subs[SECOND]
    cyl = max(sec, key=volume)
    pin2 = next(s for s in sec if s is not cyl)
    barrel2, rod2, so, sd, sroot, stip = split_cylinder(cyl, 14.29, DRAWER_OUT + 10.0, DRAWER_OUT + DRAWER_IN + 30.0)
    add("DRAWER CYLINDER MOUNT", TOP, "PIN OF DRAWER CYLINDER", pin2)
    add("DRAWER CYLINDER BARREL", TOP, "BARREL OF DRAWER CYLINDER", barrel2)
    add("DRAWER CYLINDER ROD", TOP, "ROD OF DRAWER CYLINDER", rod2)
    notes.append("drawer cylinder split into barrel and rod (rod Ø28.6 mm); the rod goes on "
                 f"{DRAWER_OUT + 10:.0f} mm inside the barrel, in a bore")

    # the drawer and the rest, as fcstd_to_step names them
    for obj, shapes in subs.items():
        if obj in (MAIN, SECOND):
            continue
        sub, prefix = _name(obj)
        target = "DRAWER" if obj == DRAWER else sub.upper()
        for n, s in enumerate(shapes, 1):
            add(target, TOP, f"{prefix} PART {n}", trimmed.get(n - 1, s) if obj == FRAME else s)
    if cut:
        notes.append(f"the drawer's way cleared: {len(cut)} frame parts trimmed by at most {max(c[1] for c in cut):.1f} mm "
                     "where they reach into the drawer's path (the source's drawer does not quite fit its way)")

    # pins: the barrel pins' axes from their round faces, the rod pins on the rods' axes at their eyes
    def pin_axis(shape, near):
        cs = sorted(cylinders_of(shape), key=lambda c: -(c[4] - c[3]))
        r, o, d, t0, t1 = cs[0]
        p = o + d * float(np.dot(near - o, d))
        return p, d

    main_tip = mo + md * mtip
    bp, bd = pin_axis(pin_main, mo + md * (mroot - 1e3))
    # the bottom pin crosses the cylinder's axis: the barrel pin is where they meet
    bp = bp + bd * float(np.dot((mo - bp), bd))
    eye = _eye(rod, md, mo)
    rp = mo + md * float(np.dot(eye - mo, md))
    sp, sdir = pin_axis(pin2, so)
    sp = sp + sdir * float(np.dot(so - sp, sdir))
    s_tip = so + sd * stip
    s_eye = _eye(rod2, sd, so, end=True)
    srp = so + sd * float(np.dot(s_eye - so, sd))

    def r3(v):
        return [round(float(x), 4) for x in v]

    plate_dir = md
    rails = _rails(subs[DRAWER], sd)
    joints = [
        {"name": "Press plate", "kind": "SLIDE", "parts": ["PRESS PLATE"], "point": r3(main_tip),
         "direction": r3(plate_dir), "base": "FRAME SUBASSEMBLY", "limits": [-PLATE_TRAVEL, 0.0],
         "source": "along the main cylinder's rod (its axis from the rod's round face)"},
        {"name": "Drawer", "kind": "SLIDE", "parts": ["DRAWER"], "point": r3(s_tip), "direction": r3(rails),
         "base": "FRAME SUBASSEMBLY", "limits": [-DRAWER_IN, DRAWER_OUT],
         "source": "along the drawer's rails (its longest parts), the way its cylinder's rod goes out; the cylinder "
                   "itself is 1° off level and pivots on its pins"},
    ]
    cylinders = [
        {"name": "Main cylinder", "barrel": ["MAIN CYLINDER BARREL"], "rod": ["MAIN CYLINDER ROD"],
         "barrel_pin": {"point": r3(bp), "axis": r3(bd), "carrier": "MAIN CYLINDER MOUNT"},
         "rod_pin": {"point": r3(rp), "axis": r3(bd), "carrier": "PRESS PLATE"}},
        {"name": "Drawer cylinder", "barrel": ["DRAWER CYLINDER BARREL"], "rod": ["DRAWER CYLINDER ROD"],
         "barrel_pin": {"point": r3(sp), "axis": r3(sdir), "carrier": "DRAWER CYLINDER MOUNT"},
         "rod_pin": {"point": r3(srp), "axis": r3(sdir), "carrier": "DRAWER"}},
    ]
    sheet = {
        "model": "ceb_press", "title": "CEB brick press", "step": "ceb_press.step", "units": "mm", "up_axis": "Z",
        "source": "goscommons/CEB-Press 01_Hardware/CAD/CEB CAD Assembly.fcstd, CC BY-SA 4.0",
        "parts": len(rows), "notes": notes, "joints": joints, "cylinders": cylinders, "hide": [],
        "poses": [{"name": n, "values": v} for n, v in POSES.items()], "start_pose": "Fill",
        "animation": _loop(),
    }
    os.makedirs(out_dir, exist_ok=True)
    if write_step:
        stepout.write(os.path.join(out_dir, "ceb_press.step"), TOP, bodies, rows)
    with open(os.path.join(out_dir, "ceb_press.json"), "w", encoding="utf-8") as fh:
        json.dump(sheet, fh, indent=1)
        fh.write("\n")
    return sheet


def _rails(drawer: list, towards) -> np.ndarray:
    """The direction of the drawer's longest parts (its rails), pointing the way ``towards`` points."""
    longest = max(drawer, key=lambda sh: float(np.max(bbox(sh)[1] - bbox(sh)[0])))
    lo, hi = bbox(longest)
    axis = int(np.argmax(hi - lo))
    d = np.zeros(3)
    d[axis] = 1.0 if towards[axis] >= 0 else -1.0
    return d


def _eye(rod, d, o, end: bool = True) -> np.ndarray:
    """The middle of the rod's eye: the round hole across the rod nearest its tip (else the tip itself)."""
    best, bt = None, -1e18
    for r, co, cd, _t0, _t1 in cylinders_of(rod):
        if abs(float(np.dot(cd, d))) > 0.2 or r > 20.0:
            continue
        t = float(np.dot(co - o, d))
        if t > bt:
            best, bt = co, t
    if best is None:
        lo, hi = bbox(rod)
        tip = max(float(np.dot(np.array(c) - o, d)) for c in _corners(rod))
        return o + d * (tip - 10.0)
    return best


# the press cycle (mm: Press plate 0 = level with the table, - = down; Drawer + = rod out, towards the hopper side)
POSES = {
    "Fill": {"Press plate": -200.0, "Drawer": 32.0},          # the drawer's open box over the chamber
    "Closed": {"Press plate": -200.0, "Drawer": -132.0},      # the drawer's floor over the chamber
    "Pressed": {"Press plate": -120.0, "Drawer": -132.0},
    "Opened": {"Press plate": -120.0, "Drawer": 32.0},
    "Brick up": {"Press plate": 0.0, "Drawer": 32.0},         # the plate level with the table, the brick in the box
    "Brick out": {"Press plate": 0.0, "Drawer": -125.0},      # the box's back wall pushes the brick off the chamber
}
LOOP = [("Closed", 1.3), ("Pressed", 1.6), ("Opened", 1.1), ("Brick up", 1.4), ("Brick out", 1.6),
        ("Fill", 2.5)]
LOOP_NAME = "Press cycle"


def _loop() -> dict:
    t, steps = 0.0, []
    for pose, sec in LOOP:
        steps.append({"kind": "POSE", "pose": pose, "start": round(t, 3), "seconds": sec, "easing": "SMOOTH"})
        t += sec
    return {"name": LOOP_NAME, "seconds": round(t, 3), "loop": True, "steps": steps}
