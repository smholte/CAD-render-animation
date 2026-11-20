"""Task 0166 / 0247: the wind park round the demo's ship, in the made demo project (``blender/demo_park.py``).

- the park stands still on the seabed at every frame, never with the vessel's heave, roll and pitch;
- the power cable comes down turbine A's J-tube onto the seabed and lies on along it, right under the ship, to its
  sealed end abeam turbine B;
- the rotors turn clockwise seen from the front, all facing one wind; the lights flash together (simple-expression
  drivers: scripts off); the park is not counted in the model's size.

The demo project is made once per run and shared by the demo files (``tests/demo_made.py``, task 0145).
"""

import math
import os
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

bpy = pytest.importorskip("bpy")
pytest.importorskip("OCP")

from demo_made import _scene, made  # noqa: E402,F401
from fresing_render.blender import build, demo, demo_park, flex, paths_sea  # noqa: E402

TOL = 0.001                                   # m


def _park(sc):
    return next(r for r in build.model_roots(sc) if r.get(build.PROP_NAME, r.name).startswith("DEMO WIND PARK")
                or os.path.basename(r.get(build.PROP_SOURCE, "")) == "demo_park.step")


def _asm(root, name):
    from fresing_render.blender import logic
    return next(o for o in logic.descendants(root) if o.get(build.PROP_NAME) == name
                and o.get(build.PROP_KIND) == "assembly")


def _part(root, name, n=0):
    from fresing_render.blender import logic
    hits = sorted((o for o in logic.descendants(root) if o.get(build.PROP_NAME) == name),
                  key=lambda o: o.get(build.PROP_UID))
    return hits[n]


@pytest.fixture(scope="module")
def places(made):
    """Every frame: the park root, a hull part (name -> (frames, 4, 4))."""
    sc = _scene()
    root = _park(sc)
    hull = next(o for o in build.iter_parts(sc) if o.get(build.PROP_NAME) == "HULL")
    f0, f1 = int(sc.frame_start), int(sc.frame_end)
    got = flex.read_places(sc, [root, hull], f0, f1 - f0 + 1, keep_shown=True)
    return {"root": got[root.name], "hull": got[hull.name], "f0": f0, "f1": f1}


def test_the_park_stands_still_on_the_seabed(made, places):
    """The park root stands still at every frame (the vessel's motion taken out exactly: Still), its seabed (z -30 m
    of the park) on the sea's seabed within 1 mm, though the vessel heaves; it is left out of the clash check by its
    stored tag."""
    from fresing_render.blender import clash
    sc = _scene()
    root = _park(sc)
    R, H = places["root"], places["hull"]
    assert np.abs(R - R[0]).max() < TOL                               # no heave, no roll, no pitch
    assert np.ptp(H[:, 2, 3]) > 0.05                                  # while the vessel does heave
    depth = float(sc.fresing.sea_depth)
    assert abs(float((R[0] @ np.array([0.0, 0.0, -depth, 1.0]))[2]) - (paths_sea.waterline(sc) - depth)) < TOL
    cons = [c.name for c in root.constraints]
    assert cons == ["FR vessel motion", "FR vessel still"], cons
    assert root.get(clash.NO_CLASH) and root.get(demo_park.KEEP)


def test_the_turbines_feet_stay_on_the_seabed(made):
    """Every turbine's monopile stands 3 m in the seabed at every 25th frame."""
    sc = _scene()
    root = _park(sc)
    piles = [_part(root, "MONOPILE", k) for k in range(9)]
    depth = float(sc.fresing.sea_depth)
    for f in range(int(sc.frame_start), int(sc.frame_end) + 1, 25):
        sc.frame_set(f)
        bz = paths_sea.waterline(sc) - depth
        for o in piles:
            lo = min((o.matrix_world @ __import__("mathutils").Vector(c)).z for c in o.bound_box)
            assert abs(lo - (bz - 3.0)) < 3 * TOL, (f, o.name, lo, bz)   # the pile reaches 3 m into the seabed
            #                                     (3 mm: piles up to 1.5 km out, the Still pair's float32 matrices)


def test_the_cable_lies_on_the_seabed_under_the_ship(made):
    """The CAD cable from turbine A's J-tube meets the seabed at the park's origin; the cable on the seabed starts
    there, lies 30 % of its Ø in the seabed, runs along the ship's centre line right under her (in her model
    coordinates) and ends abeam turbine B with its sealed end."""
    from mathutils import Vector

    from fresing_render.blender import vessel_motion
    sc = _scene()
    sc.frame_set(int(sc.frame_start))
    with vessel_motion.at_rest(sc):                  # the ship and the park where they stand on a still sea
        _cable_at_rest(made, sc)


def _cable_at_rest(made, sc):
    from mathutils import Vector
    root = _park(sc)
    sheet = demo_park.sheet_of(os.path.join(made["models"], "demo_route.json"))
    first, bed = _part(root, "CABLE FIRST END"), _part(root, "CABLE ON THE SEABED")
    end = _part(root, "CABLE END")
    W = root.matrix_world
    sb = sheet["seabed_cable"]
    a0, a1 = W @ (Vector(sb["start"]) / 1000.0), W @ (Vector(sb["end"]) / 1000.0)
    piece_end = W @ (Vector(sheet["cable_piece"]["end"]) / 1000.0)
    assert (piece_end - a0).length < TOL
    depth = float(sc.fresing.sea_depth)
    r = sb["radius"] / 1000.0
    assert abs(a0.z - (paths_sea.waterline(sc) - depth + 0.2 * r * 2)) < 0.002          # 30 % of the Ø in the seabed
    ship = next(r_ for r_ in build.model_roots(sc) if r_.get(build.PROP_SOURCE, "").endswith("demo_vessel.step"))
    S = ship.matrix_world.inverted()
    p0, p1 = S @ a0, S @ a1
    assert p0.x < -100.0 and p1.x > 1000.0 and abs(p0.y) < 0.01 and abs(p1.y) < 0.01      # under the ship's keel line
    for o in (first, bed, end):
        assert o.get("fr_group_manual") == "Demo: power cable", o.name
    b = next(t for t in sheet["turbines"] if t["role"] == "B")
    assert sb["end"][0] == pytest.approx(b["xy"][0], abs=1.0)


def test_rotors_turn_clockwise_facing_one_wind(made):
    sc = _scene()
    root = _park(sc)
    from fresing_render.blender import joints
    from mathutils import Vector
    a = sc.fresing.animations[demo.ANIM]
    motors = [b for b in a.blocks if b.kind == "MOTOR" and b.joint.endswith(": Rotor")]
    assert len(motors) == 9 and all(b.speed_rpm > 0 and b.start == 0.0 for b in motors)
    dirs = []
    for k in range(9):
        j = joints.find(sc, f"WTG {k + 1:02d}: Rotor")
        o, dvec = joints.axis_world(j)
        dirs.append(np.array(dvec))
        blade = _part(root, "BLADE", 3 * k)
        sc.frame_set(100)
        tip0 = blade.matrix_world @ Vector((0.0, 0.0, 110.0))
        sc.frame_set(101)
        o, dvec = joints.axis_world(j)
        tip1 = blade.matrix_world @ Vector((0.0, 0.0, 110.0))
        r = tip0 - o
        moves = Vector(dvec).cross(r)                    # a positive turn about the downwind axis: clockwise from
        assert moves.normalized().dot((tip1 - tip0).normalized()) > 0.99   # the front (looking downwind)
    for dv in dirs:
        assert np.allclose(dv, dirs[0], atol=1e-5)      # one wind


def test_lights_flash_together_scripts_off(made):
    """One driver per kind of light, on its group material's emission (every lamp of the kind uses that material):
    simple expressions (they run with scripts off); on and off at the frames the period says, all at once."""
    sc = _scene()
    root = _park(sc)
    from fresing_render.blender import logic
    fps = float(sc.render.fps) / float(sc.render.fps_base)
    for group, (period, on, strength) in demo_park.FLASH.items():
        mats = {o.material_slots[0].material.name for o in logic.descendants(root)
                if o.get(build.PROP_GROUP) == group and o.material_slots}
        assert len(mats) == 1, (group, mats)
        mat = bpy.data.materials[mats.pop()]
        drv = [fc for fc in mat.node_tree.animation_data.drivers if "Emission Strength" in fc.data_path
               or fc.data_path.endswith("default_value")]
        assert len(drv) == 1 and drv[0].driver.is_simple_expression and drv[0].driver.is_valid
        fc = drv[0]
        node, _sock = fc.data_path.split(".inputs")

        def at(f):
            sc.frame_set(f)
            ev = mat.evaluated_get(bpy.context.evaluated_depsgraph_get())
            return float(ev.node_tree.path_resolve(fc.data_path))
        f_on = int(sc.frame_start) + int(0.2 * on * fps)
        f_off = int(sc.frame_start) + int((on + 0.4 * (period - on)) * fps)
        assert at(f_on) == pytest.approx(strength)
        assert at(f_off) == pytest.approx(0.0)
        assert at(f_on + round(period * fps * 7)) == pytest.approx(strength, rel=1e-6)
        del node


def test_the_park_is_not_the_model_size(made):
    """The park (3 km) is scenery: the model's size, the floor and vessel motion's hull measure the vessel."""
    from fresing_render.blender import logic, vessel_motion
    sc = _scene()
    mn, mx = logic.update_bounds(sc)
    assert (mx - mn)[0] < 400.0 and (mx - mn)[1] < 400.0, (mn, mx)
    length, beam = vessel_motion.size(sc)
    assert 100.0 < length < 400.0 and beam < 100.0


def test_shots(made):
    sc = _scene()
    a = sc.fresing.animations[demo.ANIM]
    for name in (demo_park.BESIDE_A, demo_park.PARK_OVERVIEW, demo_park.PARK_NIGHT):
        assert sc.objects.get(name) is not None and name in {s.name for s in sc.fresing.shots}, name
        assert any(b.kind == "CAMERA" and b.camera_mode == "CUT" and b.camera is not None and b.camera.name == name
                   for b in a.blocks), name
    night = [b for b in a.blocks if b.kind == "WEATHER"]
    assert len(night) == 1 and night[0].wx_hour == pytest.approx(23.0)
    assert not [b for b in a.blocks if b.kind == "JOINT" and b.joint == demo_park.SHIFT]       # the park stays put


def test_the_park_keeps_clear_of_the_vessel(made):
    """The park is left out of the demo's clash check (its stored tag: it made the check 3–5 x slower), so its
    clearances are checked here, every 20th frame: every part of the ship's model (her crane's boom and hook too) stays
    clear of every turbine's platform (its corners further from the tower axis than the platform's edge + 2 m) and,
    above 25 m, of every rotor's disc (2 m off the rotor plane or outside its radius + 2 m)."""
    from fresing_render.blender import clash, logic
    sc = _scene()
    root = _park(sc)
    a = sc.fresing.animations[demo.ANIM]
    assert not [o for o in clash.objects(sc) if o.get(build.PROP_SCENERY)]          # (left out of the check)
    sheet = demo_park.sheet_of(os.path.join(made["models"], "demo_route.json"))
    ship = [o for r in build.model_roots(sc) if r is not root for o in logic.descendants(r)
            if o.get(build.PROP_KIND) == "part" and o.type == "MESH"]
    park = _asm(root, "WIND PARK")
    plat = sheet["platform_r"] / 1000.0 + 2.0
    rr = sheet["rotor_r"] / 1000.0 + 2.0
    corners = np.array([[x, y, z, 1.0] for x in (0, 1) for y in (0, 1) for z in (0, 1)], float)

    def boxes(objs):
        out = []
        for o in objs:
            bb = np.array([list(c) + [1.0] for c in o.bound_box])
            out.append((np.array(o.matrix_world) @ bb.T).T[:, :3])
        return np.concatenate(out)
    del corners
    frames = range(int(sc.frame_start), int(sc.frame_end) + 1, 20)
    worst = {"platform": 1e9, "rotor": 1e9}
    for f in frames:
        sc.frame_set(f)
        P = boxes(ship)
        W = np.array(park.matrix_world)
        for t in sheet["turbines"]:
            ax = W @ np.r_[np.array(t["xy"]) / 1000.0, 0.0, 1.0]
            d = np.hypot(P[:, 0] - ax[0], P[:, 1] - ax[1])
            worst["platform"] = min(worst["platform"], float(d.min() - plat))
            hub = W @ np.r_[np.array(t["hub"]) / 1000.0, 1.0]
            dn = W[:3, :3] @ np.array(t["down"])
            hi = P[P[:, 2] > 25.0]
            if len(hi):
                v = hi - hub[:3]
                off = np.abs(v @ dn)
                rad = np.linalg.norm(v - np.outer(v @ dn, dn), axis=1)
                ok = (off > 2.0) | (rad > rr)
                worst["rotor"] = min(worst["rotor"], float(np.where(ok, 1.0, -1.0).min()))
    assert worst["platform"] > 0.0 and worst["rotor"] > 0.0, worst
