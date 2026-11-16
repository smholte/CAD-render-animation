"""Task 0166: the wind park round the demo vessel, in the made demo project (``blender/demo_park.py``).

- the park stands on the seabed and moves with it at every frame, never with the vessel's heave, roll and pitch;
- shots 1–8b: turbine A's cable piece meets the app's laid cable on the seabed at every frame; shots 9–12: the park
  has moved on, the second end lies within the planned distance of turbine B's J-tube bell-mouth;
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

from demo_made import _scene, _solved, _t9, made  # noqa: E402,F401
from fresing_render.blender import animation, build, demo, demo_park, flex, paths, paths_sea  # noqa: E402

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
    """Every frame: the park root, the seabed's motion, a hull part (name -> (frames, 4, 4))."""
    sc = _scene()
    root = _park(sc)
    hull = next(o for o in build.iter_parts(sc) if o.get(build.PROP_NAME) == "HULL")
    bed = paths_sea.bed(sc)
    f0, f1 = int(sc.frame_start), int(sc.frame_end)
    got = flex.read_places(sc, [root, bed, hull], f0, f1 - f0 + 1, keep_shown=True)
    return {"root": got[root.name], "bed": got[bed.name], "hull": got[hull.name], "f0": f0, "f1": f1}


def test_the_park_stands_on_the_seabed_at_every_frame(made, places):
    """The park root is the seabed's motion @ its own basis at every frame (the vessel's motion taken out exactly):
    its seabed (z -30 m of the park) lies on the seabed within 1 mm and never heaves, though the vessel does."""
    sc = _scene()
    root = _park(sc)
    R, B, H = places["root"], places["bed"], places["hull"]
    basis = np.array(root.matrix_basis)
    want = B @ basis
    assert np.abs(R - want).max() < TOL, np.abs(R - want).max()
    depth = float(sc.fresing.sea_depth)
    sea_bed = R @ np.array([0.0, 0.0, -depth, 1.0])
    assert np.abs(sea_bed[:, 2] - (B[:, 2, 3] - depth)).max() < TOL
    assert np.ptp(R[:, 2, 3]) < TOL                                  # no heave …
    assert np.abs(R[:, :3, :3] - basis[:3, :3]).max() < 1e-6         # … no roll, no pitch
    assert np.ptp(H[:, 2, 3]) > 0.05                                  # while the vessel does heave
    # it moves with the seabed: the seabed's x went along with the payout
    assert np.ptp(B[:, 0, 3]) > 100.0
    cons = [c.name for c in root.constraints]
    assert cons[0] == demo_park.CON and cons[1:] == ["FR vessel motion", "FR vessel still"], cons


def test_the_turbines_feet_stay_on_the_seabed(made):
    """Every turbine's monopile and the substation's legs stand in the seabed at every 25th frame and at shot 9's
    start (the park's move), within 1 mm of their place on the seabed's motion."""
    sc = _scene()
    root = _park(sc)
    a = sc.fresing.animations[demo.ANIM]
    f9 = animation.frame_of(a, _t9(a))
    piles = [_part(root, "MONOPILE", k) for k in range(9)]
    frames = sorted(set(range(int(sc.frame_start), int(sc.frame_end) + 1, 25)) | {f9 - 2, f9 - 1, f9, f9 + 1})
    bed = paths_sea.bed(sc)
    from fresing_render.blender import joints
    sj = joints.find(sc, demo_park.SHIFT)
    L = next(float(b.to_dist) for b in a.blocks if b.kind == "JOINT" and b.joint == demo_park.SHIFT)
    depth = float(sc.fresing.sea_depth)
    for f in frames:
        sc.frame_set(f)
        bz = bed.matrix_world.translation.z - depth
        for o in piles:
            lo = min((o.matrix_world @ __import__("mathutils").Vector(c)).z for c in o.bound_box)
            assert abs(lo - (bz - 3.0)) < TOL, (f, o.name, lo, bz)   # the pile reaches 3 m into the seabed
        v = joints.get_value(sj)
        assert abs(v - (0.0 if f < f9 else L)) < 1e-5, (f, v, L)


def test_the_first_end_meets_the_lay_cable(made):
    """Shots 1–8b: the end of the app's laid cable on the seabed is the park's origin – where turbine A's cable
    piece from its J-tube comes down – at every frame (to 1 mm)."""
    sc = _scene()
    root = _park(sc)
    a = sc.fresing.animations[demo.ANIM]
    f9 = animation.frame_of(a, _t9(a))
    it = paths.find(sc, demo.CABLE_ITEM)
    res, first = _solved(sc, it)
    P = np.asarray(res["points"])
    M = np.array(it.part.matrix_world)
    origin = np.array([0.0, 0.0, paths_sea.bottom_z(sc, it), 1.0])
    end_z = paths_sea.bottom_z(sc, it)
    n = 0
    bed = paths_sea.bed(sc)
    # (shot 8b hides the lay cable: the second end takes its place from shot 9)
    hide = min(animation.frame_of(a, b.start) for b in a.blocks if b.kind == "HIDE" and b.target_uid ==
               it.part.get(build.PROP_UID))
    for k in range(0, min(len(P), hide - first), 7):
        f = first + k
        sc.frame_set(f)
        M = np.array(it.part.matrix_world)                 # (the cable part rides with the vessel's motion)
        end = P[k][-1] @ M[:3, :3].T + M[:3, 3]
        o = np.array(root.matrix_world) @ np.array([0.0, 0.0, end_z, 1.0])
        assert np.linalg.norm(end - o[:3]) < TOL, (f, end, o)
        n += 1
    assert n > 100
    del origin, bed


def test_the_second_end_is_laid_beside_turbine_b(made):
    """After shot 11 the second end's end lies on the seabed within the planned distance of B's bell-mouth."""
    sc = _scene()
    root = _park(sc)
    sheet = demo_park.sheet_of(os.path.join(made["models"], "demo_cable_route.json"))
    b = next(t for t in sheet["turbines"] if t["role"] == "B")
    it = paths.find(sc, demo.SECOND_ITEM)
    res, first = _solved(sc, it)
    P = np.asarray(res["points"])
    M = np.array(it.part.matrix_world)
    f1 = int(sc.frame_end)
    sc.frame_set(f1)
    M = np.array(it.part.matrix_world)
    head = P[f1 - first][0] @ M[:3, :3].T + M[:3, 3]
    park = np.array(_asm(root, "WIND PARK").matrix_world)      # (the park's joint moved it on)
    bell = park @ np.r_[np.array(b["bell"]) / 1000.0, 1.0]
    d = float(np.linalg.norm(head[:2] - bell[:2]))
    assert d <= sheet["b_end"] / 1000.0, d
    # the end lies on the seabed, clear of B's scour rock (its edge) and of B's monopile
    centre = park @ np.r_[np.array(b["xy"]) / 1000.0, 0.0, 1.0]
    assert np.linalg.norm(head[:2] - centre[:2]) > sheet["scour_r"] / 1000.0
    assert head[2] < paths_sea.waterline(sc) - float(sc.fresing.sea_depth) + 1.0


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
    t9 = _t9(a)
    shift = [b for b in a.blocks if b.kind == "JOINT" and b.joint == demo_park.SHIFT]
    assert len(shift) == 1 and shift[0].start + shift[0].duration == pytest.approx(t9)
    assert animation.frame_of(a, shift[0].start) == animation.frame_of(a, t9) - 1


def test_the_park_keeps_clear_of_the_vessel_and_the_d(made):
    """The park is left out of the demo's clash check (``demo_park._clash_hook``: it made the check 3–5 x slower), so
    its clearances are checked here, every 20th frame and round the park's move: every part of the vessel's model stays
    clear of every turbine's platform (its corners further from the tower axis than the platform's edge + 2 m) and,
    above 25 m, of every rotor's disc (2 m off the rotor plane or outside its radius + 2 m); the parts lowered to the
    seabed in shots 10–12 stay outside turbine B's scour rock."""
    from fresing_render.blender import clash, logic
    sc = _scene()
    root = _park(sc)
    a = sc.fresing.animations[demo.ANIM]
    f9 = animation.frame_of(a, _t9(a))
    assert not [o for o in clash.objects(sc) if o.get(build.PROP_SCENERY)]          # (left out of the check)
    sheet = demo_park.sheet_of(os.path.join(made["models"], "demo_cable_route.json"))
    ship = [o for r in build.model_roots(sc) if r is not root for o in logic.descendants(r)
            if o.get(build.PROP_KIND) == "part" and o.type == "MESH"]
    low = demo.lowered_parts(sc)
    park = _asm(root, "WIND PARK")
    plat = sheet["platform_r"] / 1000.0 + 2.0
    rr = sheet["rotor_r"] / 1000.0 + 2.0
    b = next(t for t in sheet["turbines"] if t["role"] == "B")
    corners = np.array([[x, y, z, 1.0] for x in (0, 1) for y in (0, 1) for z in (0, 1)], float)

    def boxes(objs):
        out = []
        for o in objs:
            bb = np.array([list(c) + [1.0] for c in o.bound_box])
            out.append((np.array(o.matrix_world) @ bb.T).T[:, :3])
        return np.concatenate(out)
    del corners
    frames = sorted(set(range(int(sc.frame_start), int(sc.frame_end) + 1, 20)) | {f9 - 1, f9})
    worst = {"platform": 1e9, "rotor": 1e9, "scour": 1e9}
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
        if f >= f9 and low:
            Q = boxes(low)
            ax = W @ np.r_[np.array(b["xy"]) / 1000.0, 0.0, 1.0]
            deep = Q[Q[:, 2] < paths_sea.waterline(sc) - 20.0]
            if len(deep):
                d = np.hypot(deep[:, 0] - ax[0], deep[:, 1] - ax[1]) - sheet["scour_r"] / 1000.0
                worst["scour"] = min(worst["scour"], float(d.min()))
    assert worst["platform"] > 0.0 and worst["rotor"] > 0.0 and 0.0 < worst["scour"] < 1e8, worst
