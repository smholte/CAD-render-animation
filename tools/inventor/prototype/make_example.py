"""Task 0104 prototype: an invented test assembly "FR motion test" as STEP + the side file an Inventor export would
write for it (no Inventor here: this file writes both from the same numbers, so they agree).

Not part of the app and not run by any test. Run with the dev venv (needs OpenCascade):

    ~/venv/bin/python tools/inventor/prototype/make_example.py <out dir>

writes <out dir>/FR motion test.step and <out dir>/FR motion test.fresing.json. The committed
``example.fresing.json`` next to this file is that side file.

What is in it (mm, Z up; every pattern the owner named in the brief):
- Frame:1        grounded; base plate, hinge lug, rail with an end stop, arm post, cylinder lug, two shafts, two bolts
- Door:1         on the hinge lug: Mate axis-axis + Mate plane (= a turn), Angle 0..100 deg with limits
- Hinge pin:1    Insert into the door's eye only: a round part that only spins -> rides with the door
- Carriage:1     on the rail: Mate + Flush (= a slide), Mate offset 20 mm with limits 0..340 (the travel)
- Lid:1          on the carriage by an Inventor *assembly joint* (Rotational, limits -90..0 deg)
- Arm assembly:1 a RIGID subassembly (placed at 670, 360, 200): Arm:1 grounded inside it, Gripper:1 slides on the
                 arm (its own constraints, with limits); at the top: Mate axis-axis + Mate plane + Angle with limits
- Cylinder:1     a FLEXIBLE subassembly: Barrel:1 + Rod:1 (Mate axis-axis inside), Insert of the barrel's eye on the
                 frame lug and of the rod's eye on the arm: a hydraulic cylinder in a closed loop with the arm
- Wheel small:1, Wheel big:1  Insert on the frame's shafts + a Rotate-Rotate motion constraint (gears 1:2, reverse)
- ISO 4762 M8 x 20:1, :2      bolts inserted into the plate: round, only spin -> no joint
- Type plate:1   no constraints at all (only a suppressed one) -> stays where it is
- Tangent:1      a cam-like contact: listed as left out
- Spare wheel:1  a suppressed occurrence (not in the STEP)
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "..")))

NAME = "FR motion test"
ARM_AT = (670.0, 360.0, 200.0)          # the arm subassembly's place in the top assembly (its pivot)


def shapes():
    """The parts as OpenCascade solids (top-assembly mm; the arm's parts in the arm subassembly's own mm)."""
    from fresing_render.demo_model import geom as g
    box, cyl, fuse = g.box, g.cyl, g.fuse
    Y, Z = (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)
    frame = fuse(
        box(0, 0, 0, 800, 400, 20),                                   # base plate
        box(0, 185, 20, 16, 30, 280), box(16, 190, 20, 14, 20, 25),   # hinge post + arm of the lug
        cyl(14, 25, (30, 200, 20), Z),                                # hinge lug z 20..45
        box(300, 20, 20, 460, 40, 30), box(280, 20, 20, 20, 40, 60),  # rail x 300..760, end stop x 280..300
        box(650, 300, 20, 40, 40, 200), cyl(15, 10, (670, 340, 200), Y),   # arm post + lug y 340..350
        box(455, 350, 20, 30, 15, 45),                                # cylinder lug y 350..365
        cyl(5, 40, (130, 320, 20), Z), cyl(5, 40, (220, 320, 20), Z),  # wheel shafts
    )
    door = fuse(box(44, 196, 45, 300, 8, 230), box(30, 196, 45, 14, 8, 230), cyl(12, 235, (30, 200, 45), Z))
    pin = fuse(cyl(6, 255, (30, 200, 25), Z), cyl(9, 5, (30, 200, 280), Z))
    carriage = box(320, 10, 50, 100, 60, 60)
    lid = box(320, 10, 110, 100, 60, 5)
    arm = fuse(cyl(15, 20, (0, -10, 0), Y), box(-330, -10, -10, 330, 20, 20), box(-212, -10, -32, 24, 20, 22))
    gripper = box(-150, -15, 10, 40, 30, 20)
    barrel = fuse(cyl(12, 20, (470, 330, 50), Y), cyl(20, 70, (470, 340, 60), Z))
    rod = fuse(cyl(8, 82, (470, 340, 90), Z), cyl(10, 20, (470, 330, 178), Y))
    small = fuse(cyl(30, 15, (130, 320, 20), Z), cyl(10, 25, (130, 320, 20), Z))
    big = fuse(cyl(60, 15, (220, 320, 20), Z), cyl(12, 25, (220, 320, 20), Z))

    bolt = fuse(cyl(6.5, 8, (0, 0, 20), Z), cyl(4, 20, (0, 0, 0), Z))     # one part file, placed twice
    plate = box(500, -2, 5, 80, 2, 12)
    return dict(frame=frame, door=door, pin=pin, carriage=carriage, lid=lid, arm=arm, gripper=gripper,
                barrel=barrel, rod=rod, small=small, big=big, bolt=bolt,
                plate=plate)


def write_step(path: str) -> None:
    from fresing_render.demo_model import geom as g
    s = shapes()
    grey, blue, yellow, steel = (0.5, 0.5, 0.52), (0.1, 0.3, 0.7), (0.95, 0.75, 0.1), (0.7, 0.7, 0.72)
    top = g.Asm(NAME)
    top.add(g.Part("Frame", s["frame"], grey), instance="Frame:1")
    top.add(g.Part("Door", s["door"], blue), instance="Door:1")
    top.add(g.Part("Hinge pin", s["pin"], steel), instance="Hinge pin:1")
    top.add(g.Part("Carriage", s["carriage"], yellow), instance="Carriage:1")
    top.add(g.Part("Lid", s["lid"], blue), instance="Lid:1")
    arm = g.Asm("Arm assembly")
    arm.add(g.Part("Arm", s["arm"], yellow), instance="Arm:1")
    arm.add(g.Part("Gripper", s["gripper"], blue), instance="Gripper:1")
    top.add(arm, g.T(*ARM_AT), instance="Arm assembly:1")
    cyl_asm = g.Asm("Cylinder")
    cyl_asm.add(g.Part("Barrel", s["barrel"], steel), instance="Barrel:1")
    cyl_asm.add(g.Part("Rod", s["rod"], steel), instance="Rod:1")
    top.add(cyl_asm, instance="Cylinder:1")
    top.add(g.Part("Wheel small", s["small"], steel), instance="Wheel small:1")
    top.add(g.Part("Wheel big", s["big"], steel), instance="Wheel big:1")
    bolt = g.Part("ISO 4762 M8 x 20", s["bolt"], steel)
    top.add(bolt, g.T(100, 50, 0), instance="ISO 4762 M8 x 20:1")
    top.add(bolt, g.T(100, 350, 0), instance="ISO 4762 M8 x 20:2")
    top.add(g.Part("Type plate", s["plate"], (0.9, 0.9, 0.9)), instance="Type plate:1")
    g.write_step(top, path)


# ---------------------------------------------------------------------------------------------------------------
# the side file, as the Inventor script writes it: top-assembly coordinates, mm and degrees
# ---------------------------------------------------------------------------------------------------------------

def _r(v):
    return [round(float(x), 4) for x in v]


def plane(p, n):
    return {"type": "plane", "point": _r(p), "direction": _r(n)}


def cylinder(p, d, r):
    return {"type": "cylinder", "point": _r(p), "direction": _r(d), "radius": r}


def circle(p, n, r):
    return {"type": "circle", "point": _r(p), "direction": _r(n), "radius": r}


def arm(p):
    """A point of the arm subassembly in top coordinates (the script transforms with the occurrence's matrix)."""
    return np.asarray(p, float) + np.asarray(ARM_AT)


def side(occ, geometry, inferred=""):
    d = {"occurrence": occ, "geometry": geometry}
    if inferred:
        d["inferred"] = inferred
    return d


def con(name, kind, one, two, assembly=(), value=0.0, limits=None, **extra):
    d = {"name": name, "type": kind, "assembly": list(assembly), "suppressed": False, "healthy": True,
         "one": one, "two": two, "value": value, "limits": limits}
    d.update(extra)
    return d


def matrix(t=(0.0, 0.0, 0.0)):
    m = np.eye(4)
    m[:3, 3] = t
    return _r(m.reshape(-1))


def occ(path, kind, file, number, grounded=False, t=(0.0, 0.0, 0.0), **extra):
    d = {"path": path, "kind": kind, "file": file, "part_number": number, "grounded": grounded,
         "suppressed": False, "visible": True, "flexible": False, "pattern": False, "matrix": matrix(t)}
    d.update(extra)
    return d


def side_file() -> dict:
    X, Y, Z = (1, 0, 0), (0, 1, 0), (0, 0, 1)
    nX, nY, nZ = (-1, 0, 0), (0, -1, 0), (0, 0, -1)
    F, D, P, C, L = ["Frame:1"], ["Door:1"], ["Hinge pin:1"], ["Carriage:1"], ["Lid:1"]
    AA, A, G = ["Arm assembly:1"], ["Arm assembly:1", "Arm:1"], ["Arm assembly:1", "Gripper:1"]
    CY, B, R = ["Cylinder:1"], ["Cylinder:1", "Barrel:1"], ["Cylinder:1", "Rod:1"]
    WS, WB = ["Wheel small:1"], ["Wheel big:1"]
    occurrences = [
        occ(F, "part", "Frame.ipt", "Frame", grounded=True, dof={"translations": [], "rotations": []}),
        occ(D, "part", "Door.ipt", "Door", dof={"translations": [], "rotations": []}),
        occ(P, "part", "Hinge pin.ipt", "Hinge pin",
            dof={"translations": [], "rotations": [[0, 0, 1]], "centre": [30, 200, 152.5]}),
        occ(C, "part", "Carriage.ipt", "Carriage", dof={"translations": [], "rotations": []}),
        occ(L, "part", "Lid.ipt", "Lid", dof={"translations": [], "rotations": [[1, 0, 0]], "centre": [370, 70, 110]}),
        occ(AA, "assembly", "Arm assembly.iam", "Arm assembly", t=ARM_AT),
        occ(A, "part", "Arm.ipt", "Arm", grounded=True, t=ARM_AT),
        occ(G, "part", "Gripper.ipt", "Gripper", t=ARM_AT),
        occ(CY, "assembly", "Cylinder.iam", "Cylinder", flexible=True),
        occ(B, "part", "Barrel.ipt", "Barrel"),
        occ(R, "part", "Rod.ipt", "Rod"),
        occ(WS, "part", "Wheel small.ipt", "Wheel small"),
        occ(WB, "part", "Wheel big.ipt", "Wheel big"),
        occ(["ISO 4762 M8 x 20:1"], "part", "ISO 4762 M8 x 20.ipt", "ISO 4762 M8 x 20", t=(100, 50, 0)),
        occ(["ISO 4762 M8 x 20:2"], "part", "ISO 4762 M8 x 20.ipt", "ISO 4762 M8 x 20", t=(100, 350, 0)),
        occ(["Type plate:1"], "part", "Type plate.ipt", "Type plate"),
        dict(occ(["Spare wheel:1"], "part", "Wheel small.ipt", "Wheel small"), suppressed=True),
    ]
    constraints = [
        # door on the hinge lug: axis-axis + plane = a turn; the angle with limits is the door's travel
        con("Mate:1", "mate", side(D, cylinder((30, 200, 45), Z, 6), "line"),
            side(F, cylinder((30, 200, 20), Z, 6), "line"), solution="aligned"),
        con("Mate:2", "mate", side(F, plane((30, 200, 45), Z)), side(D, plane((30, 200, 45), nZ)),
            solution="opposed"),
        con("Angle:1", "angle", side(F, plane((400, 0, 10), nY)), side(D, plane((194, 196, 160), nY)),
            value=0.0, limits={"min": 0.0, "max": 100.0}, solution="reference", reference=[0, 0, 1]),
        # the pin in the door's eye only (spins)
        con("Insert:1", "insert", side(D, circle((30, 200, 280), Z, 6)), side(P, circle((30, 200, 280), nZ, 6)),
            opposed=True, lock_rotation=False),
        # carriage on the rail: plane on plane, flush side, end face 20 mm from the stop with limits = travel
        con("Mate:3", "mate", side(F, plane((530, 40, 50), Z)), side(C, plane((370, 40, 50), nZ)),
            solution="opposed"),
        con("Flush:1", "flush", side(F, plane((400, 0, 10), nY)), side(C, plane((370, 10, 80), nY)), value=-10.0),
        con("Mate:4", "mate", side(F, plane((300, 40, 65), X)), side(C, plane((320, 40, 80), nX)),
            value=20.0, limits={"min": 0.0, "max": 340.0}, solution="opposed"),
        # the arm subassembly on the post: axis-axis + plane, angle with limits
        con("Mate:5", "mate", side(A, cylinder(arm((0, -10, 0)), Y, 8), "line"),
            side(F, cylinder((670, 340, 200), Y, 8), "line"), solution="aligned"),
        con("Mate:6", "mate", side(F, plane((670, 350, 200), Y)), side(A, plane(arm((0, -10, 0)), nY)),
            solution="opposed"),
        con("Angle:2", "angle", side(F, plane((400, 200, 20), Z)), side(A, plane(arm((-165, 0, 10)), Z)),
            value=0.0, limits={"min": -5.0, "max": 60.0}, solution="reference", reference=[0, 1, 0]),
        # inside the arm subassembly: the gripper slides along the arm, its travel by a flush with limits
        con("Mate:1", "mate", side(A, plane(arm((-165, 0, 10)), Z)), side(G, plane(arm((-130, 0, 10)), nZ)),
            assembly=AA, solution="opposed"),
        con("Flush:1", "flush", side(A, plane(arm((-165, -10, 0)), nY)), side(G, plane(arm((-130, -15, 20)), nY)),
            assembly=AA, value=5.0),
        con("Flush:2", "flush", side(A, plane(arm((-330, 0, 0)), nX)), side(G, plane(arm((-150, 0, 20)), nX)),
            assembly=AA, value=-180.0, limits={"min": -300.0, "max": -40.0}),
        # the cylinder: rod in the barrel inside its (flexible) subassembly, the two eyes inserted on their pins
        con("Mate:1", "mate", side(B, cylinder((470, 340, 60), Z, 8), "line"),
            side(R, cylinder((470, 340, 90), Z, 8), "line"), assembly=CY, solution="aligned"),
        con("Insert:2", "insert", side(F, circle((470, 350, 50), nY, 6)), side(B, circle((470, 350, 50), Y, 6)),
            opposed=True, lock_rotation=False),
        con("Insert:3", "insert", side(A, circle(arm((-200, -10, -22)), nY, 5)),
            side(R, circle((470, 350, 178), Y, 5)), opposed=True, lock_rotation=False),
        # gears: both wheels on their shafts, turned 1 : 2 the other way round by a motion constraint
        con("Insert:4", "insert", side(F, circle((130, 320, 20), Z, 5)), side(WS, circle((130, 320, 20), nZ, 5)),
            opposed=True, lock_rotation=False),
        con("Insert:5", "insert", side(F, circle((220, 320, 20), Z, 5)), side(WB, circle((220, 320, 20), nZ, 5)),
            opposed=True, lock_rotation=False),
        con("Rotate:1", "rotate_rotate", side(WS, circle((130, 320, 20), Z, 30)),
            side(WB, circle((220, 320, 20), Z, 60)), ratio=0.5, forward=False),
        # bolts: inserted, only spin
        con("Insert:6", "insert", side(F, circle((100, 50, 20), Z, 4)),
            side(["ISO 4762 M8 x 20:1"], circle((100, 50, 20), nZ, 4)), opposed=True, lock_rotation=False),
        con("Insert:7", "insert", side(F, circle((100, 350, 20), Z, 4)),
            side(["ISO 4762 M8 x 20:2"], circle((100, 350, 20), nZ, 4)), opposed=True, lock_rotation=False),
        # a cam-like contact and a switched-off constraint
        con("Tangent:1", "tangent", side(D, plane((194, 204, 160), Y)), side(WB, cylinder((220, 320, 20), Z, 60))),
        dict(con("Mate:9", "mate", side(["Type plate:1"], plane((540, 0, 11), Y)), side(F, plane((400, 0, 10), nY))),
             suppressed=True),
    ]
    joints = [
        {"name": "Rotational:1", "type": "rotational", "assembly": [], "suppressed": False, "locked": False,
         "one": {"occurrence": C, "origin": {"point": [370, 70, 110], "z": [1, 0, 0], "x": [0, 1, 0]}},
         "two": {"occurrence": L, "origin": {"point": [370, 70, 110], "z": [1, 0, 0], "x": [0, 1, 0]}},
         "angle": 0.0, "angle_limits": {"min": -90.0, "max": 0.0}, "linear": 0.0, "linear_limits": None},
    ]
    return {
        "format": "fresing-cad-motion", "version": 1,
        "written_by": {"app": "Inventor", "app_version": "invented (task 0104 prototype)",
                       "script": "make_example.py", "time": "2026-11-13T12:00:00"},
        "document": {"name": NAME + ".iam", "model_state": "[Primary]", "step_file": NAME + ".step"},
        "units": {"length": "mm", "angle": "deg"},
        "frame": "top assembly (= the STEP file's coordinates)",
        "occurrences": occurrences, "constraints": constraints, "joints": joints,
    }


def main(out_dir: str) -> tuple[str, str]:
    os.makedirs(out_dir, exist_ok=True)
    step = os.path.join(out_dir, NAME + ".step")
    js = os.path.join(out_dir, NAME + ".fresing.json")
    write_step(step)
    with open(js, "w", encoding="utf-8") as fh:
        json.dump(side_file(), fh, indent=1)
    return step, js


if __name__ == "__main__":
    print(main(sys.argv[1] if len(sys.argv) > 1 else "."))
