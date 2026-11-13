"""Task 0104 prototype: the app side, end to end, with Blender as a Python module (no app change).

Writes the invented test assembly (make_example.py), imports its STEP with the app's own importer, finds every
occurrence of the side file among the imported parts (the model update's own matcher, ``reimport.match``), works out
the plan (motion_plan.py, round parts judged from the meshes with ``core/paths.is_round``), makes the joints, the
cylinder and the coupling with the app's own calls (``joints.create``, ``cylinders.create``, ``joints.set_follows``)
and checks that the parts then move the way the Inventor constraints let them.

    ~/venv/bin/python tools/inventor/prototype/try_in_blender.py [<scratch dir>]

Not part of the app and not run by any test.
"""
from __future__ import annotations

import math
import os
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "..")))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
import addon_utils  # noqa: E402  (after bpy)
from mathutils import Vector  # noqa: E402

import fresing_render  # noqa: E402
import make_example  # noqa: E402
import motion_plan  # noqa: E402
from fresing_render.blender import build, cylinders, joints, logic, reimport  # noqa: E402
from fresing_render.core import paths as core_paths  # noqa: E402

FAILS: list[str] = []


def check(ok: bool, what: str) -> None:
    print(("OK    " if ok else "FAIL  ") + what)
    if not ok:
        FAILS.append(what)


def side_records(model: motion_plan.Model) -> list[dict]:
    """The side file's occurrences as records of the model update's matcher (``reimport.records``)."""
    out = []
    for path, o in model.live.items():
        m = np.asarray(o["matrix"], float).reshape(4, 4)
        names = []
        for i in range(1, len(path) + 1):
            oi = model.live[path[:i]]
            names.append(reimport._norm(oi.get("part_number") or os.path.splitext(oi.get("file", ""))[0]))
        out.append({"ob": path, "kind": o["kind"], "key_a": tuple(path), "key_b": tuple(names), "leaf": names[-1],
                    "pos": Vector((m[:3, 3] * 0.001).tolist()), "matrix": m})
    return out


def match(model, root, use_names: bool = True) -> dict:
    """Occurrence path -> Blender object. ``use_names`` False: as if the STEP had no occurrence names."""
    objs = logic.descendants(root)
    recs = reimport.records(objs)
    side = side_records(model)
    # an occurrence's place: the side file gives its matrix, the importer the CAD pose; for an assembly whose own
    # origin is not a part's, compare the first part's place instead
    if not use_names:
        for r in side + recs:
            r["key_a"] = None
    pairs = reimport.match(side, recs)
    return {s["ob"]: n["ob"] for s, n in pairs}


def mesh_points(objs) -> tuple[np.ndarray, np.ndarray]:
    vs, ts, base = [], [], 0
    for ob in objs:
        for o in [ob] + [c for c in ob.children_recursive]:
            if o.type != "MESH":
                continue
            me = o.data
            v = np.empty(len(me.vertices) * 3)
            me.vertices.foreach_get("co", v)
            v = v.reshape(-1, 3)
            M = np.array(o.matrix_world)
            vs.append(v @ M[:3, :3].T + M[:3, 3])
            me.calc_loop_triangles()
            t = np.empty(len(me.loop_triangles) * 3, dtype=np.int64)
            me.loop_triangles.foreach_get("vertices", t)
            ts.append(t.reshape(-1, 3) + base)
            base += len(v)
    if not vs:
        return np.zeros((0, 3)), np.zeros((0, 3), dtype=np.int64)
    return np.vstack(vs), np.vstack(ts)


def world_point(ob, local) -> Vector:
    bpy.context.view_layer.update()
    return ob.matrix_world @ Vector(local)


def main(work: str) -> int:
    step, side = make_example.main(work)
    import json
    with open(side, encoding="utf-8") as fh:
        data = json.load(fh)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    sc = bpy.context.scene
    sc.fresing.out_folder = work
    assert bpy.ops.fresing.import_step(filepath=step, quality="draft") == {"FINISHED"}
    root = next(o for o in sc.objects if o.get(build.PROP_ROOT))
    model = motion_plan.Model(data)

    # 1. matching: by occurrence names, and again as if the STEP carried none (name path + place)
    by_path = match(model, root)
    check(len(by_path) == len(model.live), f"every live occurrence found by its name ({len(by_path)}/{len(model.live)})")
    check(all(by_path[p].get(build.PROP_INSTANCE) == p[-1] for p in by_path), "found the right ones")
    blind = match(model, root, use_names=False)
    same = sum(1 for p, ob in blind.items() if by_path.get(p) is ob)
    check(same == len(model.live), f"without occurrence names, by name path + place: {same}/{len(model.live)} "
          f"{sorted(p[-1] for p in model.live if blind.get(p) is not by_path.get(p))}")

    # 2. the plan, round parts judged from the meshes
    def is_round(nodes, point, direction):
        v, t = mesh_points([by_path[n] for n in nodes])
        return len(v) > 0 and core_paths.is_round(v, point, direction, t)
    p = motion_plan.plan(data, is_round=is_round)
    for n in p["notes"] + p["left_out"]:
        print("      ", n)
    names = {j["name"]: j for j in p["joints"]}
    check(set(names) == {"Door:1 turn", "Carriage:1 slide", "Arm assembly:1 turn", "Wheel small:1 turn",
                         "Wheel big:1 turn", "Lid:1 turn", "Gripper:1 slide"}, f"joints planned: {sorted(names)}")
    check(len(p["cylinders"]) == 1 and p["cylinders"][0]["barrel"] == [["Cylinder:1", "Barrel:1"]],
          "one hydraulic cylinder, barrel = Barrel:1")
    check([(c["joint"], c["follows"], c["ratio"]) for c in p["couplings"]] ==
          [("Wheel big:1 turn", "Wheel small:1 turn", -0.5)], "gear coupling: big wheel follows the small one x -0.5")

    # 3. the app's own calls
    M = root.matrix_world
    with joints._batch(sc):
        for j in p["joints"]:
            objs = [by_path[tuple(n)] for n in j["parts"]]
            base = joints.find(sc, j["rides_on"]).motion if j["rides_on"] else by_path[tuple(j["on"][0])]
            origin = M @ (Vector(j["axis"]["point"]) / 1000.0)
            direction = (M.to_3x3() @ Vector(j["axis"]["direction"])).normalized()
            jt = joints.create(sc, "ROTATE" if j["type"] == "rotate" else "SLIDE", objs, origin, direction,
                               name=j["name"], base=base)
            if j["limits"]:
                lo, hi = j["limits"]
                if jt.kind == "ROTATE":
                    jt.rot_min, jt.rot_max = math.radians(lo), math.radians(hi)
                else:
                    jt.slide_min, jt.slide_max = lo / 1000.0, hi / 1000.0
                jt.use_limits = True
        for c in p["couplings"]:
            joints.set_follows(sc, sc.fresing.joints[c["joint"]], c["follows"], ratio=c["ratio"])
    for c in p["cylinders"]:
        def pin(d, carrier):
            return (M @ (Vector(d["point"]) / 1000.0), (M.to_3x3() @ Vector(d["direction"])).normalized(),
                    by_path[tuple(carrier[0])])
        cy, notes = cylinders.create(sc, [by_path[tuple(n)] for n in c["barrel"]],
                                     [by_path[tuple(n)] for n in c["rod"]], pin(c["barrel_pin"], c["barrel_carrier"]),
                                     pin(c["rod_pin"], c["rod_carrier"]), name=c["name"],
                                     barrel_carrier=by_path[tuple(c["barrel_carrier"][0])],
                                     rod_carrier=by_path[tuple(c["rod_carrier"][0])])
        for n in notes:
            print("       cylinder:", n)
    check(len(sc.fresing.joints) == 7, f"{len(sc.fresing.joints)} joints in the project")
    check(len(cylinders.cylinders(sc)) == 1, "one cylinder in the project")

    J = sc.fresing.joints

    def setv(name, value):
        jt = J[name]
        joints.set_value(jt, math.radians(value) if jt.kind == "ROTATE" else value / 1000.0)
        bpy.context.view_layer.update()
        bpy.context.view_layer.update()

    def near(a, b, tol=1e-4):
        return (Vector(a) - Vector(b)).length < tol

    door, carriage, lid = by_path[("Door:1",)], by_path[("Carriage:1",)], by_path[("Lid:1",)]
    arm, grip = by_path[("Arm assembly:1", "Arm:1")], by_path[("Arm assembly:1", "Gripper:1")]
    rod, barrel = by_path[("Cylinder:1", "Rod:1")], by_path[("Cylinder:1", "Barrel:1")]
    pin_ = by_path[("Hinge pin:1",)]

    # 4. motion: the door turns about the hinge (x 30, y 200), its far edge (x 344) moves on a circle
    tip0 = world_point(door, (0.344, 0.2, 0.16))
    setv("Door:1 turn", 90)
    tip = world_point(door, (0.344, 0.2, 0.16))
    check(near(tip, (0.030, 0.2 + 0.314, 0.16), 1e-4), f"door at 90°: far edge at {tuple(round(x, 4) for x in tip)}")
    check(near(world_point(pin_, (0.03, 0.2, 0.2)), (0.03, 0.2, 0.2)), "the hinge pin turns with the door, in place")
    check(abs(math.degrees(J["Door:1 turn"].rot_max) - 100) < 1e-3, "door limits 0..100° (Angle:1)")
    setv("Door:1 turn", 0)
    check(near(world_point(door, (0.344, 0.2, 0.16)), tip0), "door back")

    setv("Carriage:1 slide", 320)
    check(near(world_point(carriage, (0.32, 0.04, 0.08)), (0.64, 0.04, 0.08)), "carriage at the end of its travel")
    check(abs(J["Carriage:1 slide"].slide_min * 1000 + 20) < 1e-3 and abs(J["Carriage:1 slide"].slide_max * 1000 - 320)
          < 1e-3, "carriage limits -20..320 mm (Mate:4 offset 20, limits 0..340)")
    setv("Lid:1 turn", -90)
    edge = world_point(lid, (0.37, 0.01, 0.1125))   # the lid's front edge goes up over the hinge at y 70
    check(near(edge, (0.69, 0.0725, 0.17)), f"lid open on the moved carriage: {tuple(round(x, 4) for x in edge)}")
    setv("Lid:1 turn", 0)
    setv("Carriage:1 slide", 0)

    # the arm: rod eye stays on the arm's pin, barrel eye on the frame's, while the arm lifts 30°
    l0 = cylinders.length_now(cylinders.cylinders(sc)[0])
    setv("Arm assembly:1 turn", 30)
    a = math.radians(30)
    x, z = -0.2, -0.022                              # the arm's rod pin from its pivot, turned +30° about +y
    want = Vector((0.670 + x * math.cos(a) + z * math.sin(a), 0.35, 0.2 - x * math.sin(a) + z * math.cos(a)))
    arm_pin = world_point(arm, (-0.2, -0.01, -0.022))       # (the arm's own coordinates: its subassembly's)
    check(near(arm_pin, want, 1e-4), f"arm lifted 30°: its rod pin at {tuple(round(v, 4) for v in arm_pin)}")
    rod_eye = world_point(rod, (0.47, 0.34, 0.178))
    check((Vector((rod_eye.x, rod_eye.z)) - Vector((arm_pin.x, arm_pin.z))).length < 1e-3,
          "rod eye on the arm's pin at 30°")
    check(near(world_point(barrel, (0.47, 0.34, 0.05)), (0.47, 0.34, 0.05)), "barrel eye stays on the frame's pin")
    l1 = cylinders.length_now(cylinders.cylinders(sc)[0])
    check(l1 > l0 + 0.03, f"cylinder longer when the arm lifts: {l0 * 1000:.1f} -> {l1 * 1000:.1f} mm")
    g0 = world_point(grip, (-0.13, 0.0, 0.02))
    setv("Gripper:1 slide", 100)
    g1 = world_point(grip, (-0.13, 0.0, 0.02))
    along = (g1 - g0).normalized()
    check(abs((g1 - g0).length - 0.1) < 1e-4 and abs(along.dot(Vector((math.cos(a), 0, -math.sin(a)))) - 1) < 1e-4,
          "gripper slides 100 mm along the lifted arm (rides on the arm's turn)")

    # gears
    setv("Wheel small:1 turn", 90)
    check(abs(math.degrees(joints.get_value(J["Wheel big:1 turn"])) + 45) < 1e-3, "big wheel turns -45° for +90°")

    # nothing moves the bolts, the type plate
    for path in (("ISO 4762 M8 x 20:1",), ("Type plate:1",)):
        check(joints.joint_of_object(sc, by_path[path]) is None, f"{path[0]}: no joint")
    print(f"\n{len(FAILS)} failed")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="fr0104_")))
