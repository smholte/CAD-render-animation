"""The Thor robot arm (AngelLM/Thor, CC BY-SA 4.0) as a model that moves (task 0112).

``convert(src, out_dir)`` reads the FreeCAD Assembly4 files of ``src`` (the repository's ``freecad-src`` folder) and
writes ``thor.step`` – the 522 parts, grouped into one sub-assembly per moving body, nested along the arm (Art1 in the
model, Art2 in Art1 ... the fingers on their links) – and ``thor.json``, the sheet the render kit's project maker
reads (``site/render_kit/projects.py``): joints, couplings, limits, poses and the animation.

Where the joints come from (nothing guessed): Assembly4 attaches each sub-assembly and each part to a coordinate
system (LCS) of the one it sits on; a revolute joint turns about the Z axis of such a frame. ``Attachments.frames``
works the frame out from both sides (the parent's LCS x the attachment offset, and the part's own LCS) and the
converter refuses a joint whose two frames differ. The joints:

    Art1   base -> Art1: AssemblyArt1's frame (Z up at the base)
    Art2   shoulder: AssemblyArt2's frame (Y, z 202 mm)            Art3   elbow: AssemblyArt3's frame (Y, z 362 mm)
    Art4   forearm: AssemblyArt4's frame (Z)
    Art5   wrist pitch: the shaft the two bevel gears of the differential turn on (their frames, Y, z 556 mm)
    Art6   wrist roll: the gear plate's frame (Z)
    gripper: the servo horn, the passive arm, the two links and the two fingers (their frames, all along X)

Gears that mesh are coupled by the tooth counts in the parts' own spreadsheets: the motor pinions of Art1 (10:50,
inside a ring gear), Art2 (two pinions 10:60, inside), Art4 (10:20, outside) turn with their joints, and the
differential's two bevel gears (15) turn against the gear plate (30) when the wrist rolls. The gripper is a pair of
parallelograms: both links turn with the servo arm, the passive arm turns the other way (equal gears), and each finger
turns back on its link so it stays upright.
"""

from __future__ import annotations

import json
import math
import os

import numpy as np

from . import a4, stepout

TOP = "THOR"
# sub-assembly link of the top file -> body name of its parts
SUBS = {"AssemblyBase": "BASE", "AssemblyArt1": "ART1", "AssemblyArt2": "ART2", "AssemblyArt3": "ART3",
        "AssemblyArt4": "ART4", "AssemblyArt56": "ART5"}
# inside a sub-assembly: an object (and what is attached to it) that moves on its own -> its body
ANCHORS = {
    "AssemblyBase": {"Art1GearMotor_Art1GearMotor": "ART1 PINION"},
    "AssemblyArt1": {"Art2MotorGear_Art2MotorGear": "ART2 PINION A", "Art2MotorGear_Art2MotorGear001": "ART2 PINION B"},
    "AssemblyArt3": {"Art4MotorGear_Art4MotorGear": "ART4 PINION"},
    "AssemblyArt56": {
        "Art56GearPlate_Art56GearPlate": "ART6",
        "Art56SmallGear_Art56SmallGear": "WRIST GEAR A", "Art56SmallGear_Art56SmallGear001": "WRIST GEAR B",
        "ServomotorWheelHorn001": "GRIPPER SERVO ARM", "Unnamed3_GripperPassiveArm": "GRIPPER PASSIVE ARM",
        "Unnamed2_GripperArm001": "GRIPPER LINK A", "Unnamed2_GripperArm": "GRIPPER LINK B",
        "Unnamed1_GripperFinger": "FINGER A", "GripperFinger_sym001": "FINGER B"},
}
# body -> the body it sits on (the nesting of the STEP)
TREE = {
    "BASE": TOP, "ART1 PINION": "BASE", "ART1": TOP, "ART2 PINION A": "ART1", "ART2 PINION B": "ART1",
    "ART2": "ART1", "ART3": "ART2", "ART4 PINION": "ART3", "ART4": "ART3", "ART5": "ART4",
    "WRIST GEAR A": "ART5", "WRIST GEAR B": "ART5", "ART6": "ART5",
    "GRIPPER SERVO ARM": "ART6", "GRIPPER PASSIVE ARM": "ART6", "GRIPPER LINK A": "ART6", "GRIPPER LINK B": "ART6",
    "FINGER A": "GRIPPER LINK A", "FINGER B": "GRIPPER LINK B",
}
# parts the clip leaves out (hidden for good in the project, the app's "excluded"), with the reason; renamed so the
# sheet can name them: (sub-assembly, object) -> name
HIDE = {
    ("AssemblyArt2", "GT2_Belt_Art3001"): ("ART3 BELT", "the elbow's toothed belt runs inside the upper arm; a "
                                           "one-piece belt cannot run round its pulleys, so the turning elbow "
                                           "pulley would cut through it"),
    ("AssemblyBase", "Screw031"): ("ART1 PINION GRUB SCREW", "the Art1 motor pinion's grub screw sticks 0.7 mm into "
                                   "the Art1 ring gear when the pinion turns (in the source model); inside the base"),
}
# gears: body -> (file whose spreadsheet holds the tooth count)
TEETH_FILES = {"ART1 PINION": "Art1GearMotor", "ART1": "Art1Bot", "ART2 PINION A": "Art2MotorGear",
               "ART2": "Art2BodyA", "ART4 PINION": "Art4MotorGear", "ART4": "Art4TransmissionColumn",
               "WRIST GEAR A": "Art56SmallGear", "ART6": "Art56GearPlate"}

# joint name -> (moving body, (sub-assembly chain, attached object, hinge axis of its attachment frame), rides on).
# Assembly4 gives the frame; which of its axes is the hinge differs between Thor's sub-assemblies (the shoulder's and
# the wrist's are Z, the elbow's is Y), so it is named here – and ``round_faces`` checks it against the geometry.
JOINTS = [
    ("Art1", "ART1", ((), "AssemblyArt1", "z"), None),
    ("Art2", "ART2", ((), "AssemblyArt2", "z"), "Art1"),
    ("Art3", "ART3", ((), "AssemblyArt3", "y"), "Art2"),
    ("Art4", "ART4", ((), "AssemblyArt4", "z"), "Art3"),
    ("Art5", "ART5", (("AssemblyArt56",), "Art56SmallGear_Art56SmallGear", "z"), "Art4"),
    ("Art6", "ART6", (("AssemblyArt56",), "Art56GearPlate_Art56GearPlate", "z"), "Art5"),
    ("Gripper", "GRIPPER SERVO ARM", (("AssemblyArt56",), "ServomotorWheelHorn001", "z"), "Art6"),
    ("Gripper passive arm", "GRIPPER PASSIVE ARM", (("AssemblyArt56",), "Unnamed3_GripperPassiveArm", "z"), "Art6"),
    ("Gripper link A", "GRIPPER LINK A", (("AssemblyArt56",), "Unnamed2_GripperArm001", "z"), "Art6"),
    ("Gripper link B", "GRIPPER LINK B", (("AssemblyArt56",), "Unnamed2_GripperArm", "z"), "Art6"),
    ("Finger A", "FINGER A", (("AssemblyArt56",), "Unnamed1_GripperFinger", "z"), "Gripper link A"),
    ("Finger B", "FINGER B", (("AssemblyArt56",), "GripperFinger_sym001", "z"), "Gripper link B"),
    ("Art1 pinion", "ART1 PINION", (("AssemblyBase",), "Art1GearMotor_Art1GearMotor", "z"), None),
    ("Art2 pinion A", "ART2 PINION A", (("AssemblyArt1",), "Art2MotorGear_Art2MotorGear", "z"), "Art1"),
    ("Art2 pinion B", "ART2 PINION B", (("AssemblyArt1",), "Art2MotorGear_Art2MotorGear001", "z"), "Art1"),
    ("Art4 pinion", "ART4 PINION", (("AssemblyArt3",), "Art4MotorGear_Art4MotorGear", "z"), "Art3"),
    ("Wrist gear A", "WRIST GEAR A", (("AssemblyArt56",), "Art56SmallGear_Art56SmallGear", "z"), "Art5"),
    ("Wrist gear B", "WRIST GEAR B", (("AssemblyArt56",), "Art56SmallGear_Art56SmallGear001", "z"), "Art5"),
]
# the joints a user moves (the rest follow): limits in degrees, safe ranges (Thor's docs give none) with 0 clashes
DRIVEN = {"Art1": (-170.0, 170.0), "Art2": (-95.0, 95.0), "Art3": (-110.0, 110.0), "Art4": (-170.0, 170.0),
          "Art5": (-100.0, 100.0), "Art6": (-170.0, 170.0), "Gripper": (0.0, 85.0)}


def teeth(src: str, stem: str) -> tuple[int, float]:
    """(teeth, module) from a part file's spreadsheet."""
    import re
    import zipfile
    path = next(os.path.join(src, f) for f in os.listdir(src) if os.path.splitext(f)[0].lower() == stem.lower())
    d = zipfile.ZipFile(path).read("Document.xml").decode("utf-8")
    vals = dict(re.findall(r'<Property name="(teeth|module)"[^>]*>\s*<\w+ value="([^"]*)"', d))
    return int(round(float(vals["teeth"]))), float(vals["module"])


def label_of(part: a4.Part) -> str:
    obj = part.path[1] if len(part.path) > 1 else part.key[1]
    hit = HIDE.get((part.path[0], obj))
    return hit[0] if hit else part.label


def body_of(part: a4.Part) -> str:
    sub = part.path[0]
    obj = part.path[1] if len(part.path) > 1 else part.key[1]
    anchors = ANCHORS.get(sub, {})
    if anchors:
        at = _attachments.get(sub)
        hit = at.anchor(obj, anchors) if at is not None else ""
        if hit:
            return anchors[hit]
    return SUBS[sub]


_attachments: dict = {}


def _axis(reader, chain, obj, letter) -> tuple[np.ndarray, np.ndarray, str]:
    at = a4.Attachments(reader, chain)
    on_parent, own = at.frames(obj)
    if not np.allclose(on_parent, own, atol=1e-4):
        raise RuntimeError(f"{obj}: its two attachment frames differ – the axis cannot be read")
    col = "xyz".index(letter)
    return (own[:3, 3].copy(), own[:3, col].copy(),
            f"{'/'.join(chain) or 'Assembly'}: {obj}'s attachment frame, {letter.upper()} axis")


def round_faces(parts: list, c, u, tol_mm: float = 0.1, tol_deg: float = 0.1) -> tuple[int, float]:
    """(number of cylindrical faces of ``parts`` whose axis is the line (c, u), the largest radius in mm): the
    geometry's own word that the parts turn about that line (bores, bearing seats, gear rims)."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS
    u = np.asarray(u, float) / np.linalg.norm(u)
    n, rmax = 0, 0.0
    cos_tol = math.cos(math.radians(tol_deg))
    for p in parts:
        shape = a4.read_brep(p.brep)
        R, t = p.matrix[:3, :3], p.matrix[:3, 3]
        ex = TopExp_Explorer(shape, TopAbs_FACE)
        while ex.More():
            a = BRepAdaptor_Surface(TopoDS.Face(ex.Current()))
            if a.GetType() == GeomAbs_Cylinder:
                cyl = a.Cylinder()
                ax = cyl.Axis()
                d = R @ np.array([ax.Direction().X(), ax.Direction().Y(), ax.Direction().Z()])
                o = R @ np.array([ax.Location().X(), ax.Location().Y(), ax.Location().Z()]) + t
                if abs(float(np.dot(d, u))) >= cos_tol:
                    off = (o - c) - np.dot(o - c, u) * u
                    if np.linalg.norm(off) <= tol_mm:
                        n += 1
                        rmax = max(rmax, cyl.Radius())
            ex.Next()
    return n, rmax


def couplings(src: str, axes: dict) -> dict:
    """follower joint -> (leader, ratio) from the tooth counts and the meshes' geometry."""
    out = {}

    def mesh(pinion: str, gear: str, leader: str, pin_body: str, gear_body: str):
        zp, mp = teeth(src, TEETH_FILES[pin_body])
        zg, mg = teeth(src, TEETH_FILES[gear_body])
        p0, pd = axes[pinion]
        g0, gd = axes[gear]
        off = (p0 - g0) - np.dot(p0 - g0, gd) * gd               # centre distance, square to the gear's axis
        d = float(np.linalg.norm(off))
        inside = abs(d - mg * (zg - zp) / 2.0) < abs(d - mg * (zg + zp) / 2.0)
        same = 1.0 if inside else -1.0                           # a ring gear turns its pinion the same way
        sign = same * float(np.sign(np.dot(pd, gd)))
        out[pinion] = (leader, sign * zg / zp, f"{zp}:{zg} teeth, {'inside a ring gear' if inside else 'outside'}, "
                                               f"centres {d:.1f} mm apart")

    mesh("Art1 pinion", "Art1", "Art1", "ART1 PINION", "ART1")
    mesh("Art2 pinion A", "Art2", "Art2", "ART2 PINION A", "ART2")
    mesh("Art2 pinion B", "Art2", "Art2", "ART2 PINION A", "ART2")
    mesh("Art4 pinion", "Art4", "Art4", "ART4 PINION", "ART4")
    # the differential: the gear plate turns on Art5; each bevel gear turns about the shaft against it
    zs, _ = teeth(src, "Art56SmallGear")
    zp, _ = teeth(src, "Art56GearPlate")
    c6, u6 = axes["Art6"]
    for g in ("Wrist gear A", "Wrist gear B"):
        c, u = axes[g]
        # where they mesh: on the gear's side of the plate's axis (r), on the plate's side of the gear's axis (up)
        r = (c - c6) - np.dot(c - c6, u6) * u6
        up = u6 * float(np.sign(np.dot(c6 - c, u6)))
        v_plate = np.cross(u6, r / np.linalg.norm(r))           # the plate's teeth there, per radian of Art6
        v_gear = np.cross(u, up)                                # the gear's teeth there, per radian of its own turn
        k = float(np.sign(np.dot(v_plate, v_gear)))             # equal speeds: angle ratio = the teeth's ratio
        out[g] = ("Art6", k * zp / zs, f"{zs}:{zp} bevel teeth (differential)")
    # the gripper's parallelograms (all axes along X; ratios on the X-ward direction of each axis)
    ux = {n: float(np.sign(axes[n][1][0])) for n in ("Gripper", "Gripper passive arm", "Gripper link A",
                                                      "Gripper link B", "Finger A", "Finger B")}
    g = ux["Gripper"]
    out["Gripper passive arm"] = ("Gripper", -g * ux["Gripper passive arm"], "equal gears: turns the other way")
    out["Gripper link A"] = ("Gripper", g * ux["Gripper link A"], "parallelogram with the servo arm")
    out["Gripper link B"] = ("Gripper", -g * ux["Gripper link B"], "parallelogram with the passive arm")
    out["Finger A"] = ("Gripper", -g * ux["Finger A"], "turns back on link A: stays upright")
    out["Finger B"] = ("Gripper", g * ux["Finger B"], "turns back on link B: stays upright")
    return out


# ---------------------------------------------------------------------------
# poses and the loop (degrees; the gripper: the servo arm's angle)
# ---------------------------------------------------------------------------

POSES = {
    "Home": {"Art1": 0, "Art2": 0, "Art3": 0, "Art4": 0, "Art5": 0, "Art6": 0, "Gripper": 0},
    "Reach down": {"Art1": -45, "Art2": 55, "Art3": 65, "Art4": 0, "Art5": 60, "Art6": 0, "Gripper": 0},
    "Grip": {"Art1": -45, "Art2": 55, "Art3": 65, "Art4": 0, "Art5": 60, "Art6": 0, "Gripper": 55},
    "Lift and turn": {"Art1": 0, "Art2": 20, "Art3": 50, "Art4": 0, "Art5": 75, "Art6": 90, "Gripper": 55},
    "Put down": {"Art1": 45, "Art2": 55, "Art3": 65, "Art4": 0, "Art5": 60, "Art6": 90, "Gripper": 55},
    "Release": {"Art1": 45, "Art2": 55, "Art3": 65, "Art4": 0, "Art5": 60, "Art6": 90, "Gripper": 0},
}
# (pose, seconds to get there): starts at Home, ends at Home – a seamless loop of 11 s
LOOP = [("Reach down", 2.2), ("Grip", 0.8), ("Lift and turn", 2.0), ("Put down", 2.0), ("Release", 0.8),
        ("Home", 2.2)]
LOOP_NAME = "Thor at work"


def convert(src: str, out_dir: str, write_step: bool = True) -> dict:
    """Write thor.step and thor.json into ``out_dir``. Returns the sheet."""
    reader = a4.Reader(os.path.join(src, "Assembly.FCStd"))
    _attachments.clear()
    for sub in ANCHORS:
        _attachments[sub] = a4.Attachments(reader, (sub,))
    parts = reader.parts(shapes=write_step)
    bodies = {}
    for p in parts:
        b = body_of(p)
        bodies.setdefault(b, 0)
        bodies[b] += 1
    missing = set(TREE) - set(bodies)
    if missing:
        raise RuntimeError(f"no parts found for {sorted(missing)}: the source changed")
    axes, sources = {}, {}
    for name, _body, (chain, obj, letter), _on in JOINTS:
        c, u, how = _axis(reader, chain, obj, letter)
        axes[name] = (c, u)
        sources[name] = how
    links = couplings(src, axes)
    body_of_joint = {name: body for name, body, _s, _on in JOINTS}
    joints = []
    for name, body, _src, on in JOINTS:
        c, u = axes[name]
        j = {"name": name, "kind": "ROTATE", "parts": [body], "point": [round(float(x), 6) for x in c],
             "direction": [round(float(x), 9) for x in u], "rides_on": on, "source": sources[name]}
        if write_step:
            # a hinge has round faces on both sides (bore and pin, bearing and seat): the turning body's and those
            # of the body it sits on. (The elbow's vertical Z axis has none on Art2: that is how the Y was found.)
            under = body_of_joint.get(on, "BASE")
            n1, r1 = round_faces([p for p in parts if body_of(p) == body], c, u)
            n2, _r2 = round_faces([p for p in parts if body_of(p) == under], c, u)
            if not (n1 and n2):
                raise RuntimeError(f"joint {name}: the axis read from the files is not the axis of round faces of "
                                   f"both {body} ({n1}) and {under} ({n2})")
            j["round_faces"], j["round_radius"] = [n1, n2], round(r1, 2)
        if name in DRIVEN:
            j["limits"] = list(DRIVEN[name])
        if name in links:
            leader, ratio, why = links[name]
            j["follows"], j["ratio"], j["why"] = leader, round(ratio, 9), why
        joints.append(j)
    t, steps = 0.0, []
    for pose, sec in LOOP:
        steps.append({"kind": "POSE", "pose": pose, "start": round(t, 3), "seconds": sec, "easing": "SMOOTH"})
        t += sec
    sheet = {
        "model": "thor", "title": "Thor robot arm", "step": "thor.step", "units": "mm", "up_axis": "Z",
        "source": "AngelLM/Thor freecad-src (Assembly4), CC BY-SA 4.0",
        "parts": len(parts), "bodies": {k: bodies[k] for k in sorted(bodies)},
        "joints": joints, "cylinders": [],
        "hide": [{"part": name, "why": why} for name, why in HIDE.values()],
        "poses": [{"name": n, "values": v} for n, v in POSES.items()],
        "start_pose": "Home",
        "animation": {"name": LOOP_NAME, "seconds": round(t, 3), "loop": True, "steps": steps},
    }
    os.makedirs(out_dir, exist_ok=True)
    if write_step:
        rows = [(label_of(p), p.key, a4.read_brep(p.brep).Located(_identity()), p.matrix, body_of(p)) for p in parts]
        counts = stepout.write(os.path.join(out_dir, "thor.step"), TOP, dict(TREE), rows)
        sheet["unique_parts"] = counts["unique"]
    with open(os.path.join(out_dir, "thor.json"), "w", encoding="utf-8") as fh:
        json.dump(sheet, fh, indent=1)
        fh.write("\n")
    return sheet


def _identity():
    from OCP.TopLoc import TopLoc_Location
    return TopLoc_Location()


def angle_between(a, b) -> float:
    """Degrees between two axis lines' directions (a line: either way round)."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    c = abs(float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))))
    return math.degrees(math.acos(min(1.0, c)))
