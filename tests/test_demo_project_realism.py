"""Task 0173 (study 0152): the demo reads like a real, controlled lay – in the made demo project.

- shot 8: the "Lay data" label points at the touch-down and shows the cable's numbers at every frame (top and bottom
  tension, layback, departure angle, lay speed, water depth), inside the picture at HD and 4K; the caption says
  "surface lay"; the cable weighs 38 kg/m in water: bottom ≈ 7.3 kN, top ≈ 19.5 kN at the demo's 32 m layback;
- the ROV: shown in shots 1–8b, hidden from shot 9; Still (no heave); beside the touch-down and looking at it; clear
  of the lay cable and the seabed at every frame it is shown; its tether a hose from its restrictor to the transom;
  left out of the clash check; its lights glow;
- captions: the handler's tilt in shots 9 and 12 has its "x N"; shot 5 names the tensioner class and the cable;
- the tipping winches' drums hold their wire in layers: the drum wire's payout follows the tipping wire's within a
  few cm along the quadrant operation, their fleet angle is under 2°.

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

from demo_made import _scene, _t9, made  # noqa: E402,F401
from fresing_render.blender import animation, build, demo, demo_rov, flex, paths, paths_sea  # noqa: E402


@pytest.fixture(scope="module")
def built(made):
    sc = _scene()
    a = sc.fresing.animations[demo.ANIM]
    animation.bake(sc, a)
    return sc, a


def _window(a, name):
    b = next(b for b in a.blocks if b.name == name)
    return float(b.start), float(b.start + b.duration)


# ---------------------------------------------------------------------------
# shot 8: the lay data
# ---------------------------------------------------------------------------

def test_the_cable_weighs_38_kg_per_m_and_its_tensions_follow(built):
    sc, _a = built
    it = paths.find(sc, demo.CABLE_ITEM)
    sc.frame_set(sc.frame_start)
    n = paths_sea.numbers(sc, it)
    assert n["weight"] == pytest.approx(38.0)                          # 0152: public cables 22–39 kg/m at Ø 200
    assert n["layback"] == pytest.approx(demo.SEA_LAYBACK, abs=0.05)   # the lead's choice: the layback kept
    assert 6.8 < n["bottom"] < 7.8 and 18.5 < n["top"] < 20.5, n       # (51 kg/m: 9.8 and 26.1 kN)
    assert 64.0 < n["angle"] < 72.0, n


def test_lay_data_in_shot_8_shows_the_numbers_inside_the_picture(built):
    from fresing_render.blender import callouts
    sc, a = built
    assert demo.SEA_CAPTION in [b.name for b in a.blocks] and "surface lay" in demo.SEA_CAPTION
    c = next(c for c in sc.fresing.callouts if c.text == demo.LAY_DATA)
    assert c.step == demo.SEA_CAPTION and c.part == paths.find(sc, demo.CABLE_ITEM).part
    w = callouts.window_for(a, c)
    fps = int(a.fps)
    boxes = callouts.PartBoxes(sc)
    speeds = set()
    for f in range(int(w[0] * fps) + 3, int(w[1] * fps) - 2, 25):
        sc.frame_set(f + 1)
        it = paths.find(sc, demo.CABLE_ITEM)
        n = paths_sea.numbers(sc, it)
        rows = callouts.label_text(sc, c).split("\n")
        assert rows[0] == "Lay data" and len(rows) == 7
        assert rows[1] == f"Top tension {n['top']:.1f} kN" and rows[2] == f"Bottom tension {n['bottom']:.1f} kN"
        assert rows[3] == f"Layback {n['layback']:.1f} m" and rows[4] == f"Departure angle {n['angle']:.0f}°"
        assert rows[6] == f"Water depth {demo.SEA_DEPTH:.0f} m"
        speeds.add(rows[5])
        for size in ((1920, 1080), (3840, 2160)):
            d = [x for x in callouts.draws_at(sc, size, f / fps, a, "", boxes) if x.text.startswith("Lay data")]
            assert len(d) == 1, (size, f)
            assert d[0].box.inside(size[0], size[1], 0.0), (size, f, d[0].box)
            assert d[0].box.h < 0.45 * size[1]                          # (readable, not the whole picture)
    assert speeds == {f"Lay speed {demo.SPEED:.1f} m/min"}, speeds       # the cable runs at 10 m/min all through


# ---------------------------------------------------------------------------
# captions
# ---------------------------------------------------------------------------

def test_captions_say_time_lapse_and_name_the_tensioner_and_cable(built):
    from fresing_render.demo_model.params import Params
    _sc, a = built
    tilts = [b for b in a.blocks if b.joint == demo.TILT and b.duration == pytest.approx(demo.TILT_SECONDS)]
    assert len(tilts) == 2 and all(f"(x {demo.TILT_LAPSE})" in b.name for b in tilts)
    assert demo.TILT_LAPSE == round(demo.TILT_REAL_SECONDS / demo.TILT_SECONDS) and 15 <= demo.TILT_LAPSE <= 45
    p = Params()
    assert demo.SHOT5_CAPTION in [b.name for b in a.blocks]
    assert f"Ø {p.cable_d:.0f} mm" in demo.SHOT5_CAPTION and f"MBR {p.mbr / 1000.0:.1f} m" in demo.SHOT5_CAPTION
    assert "15–20 t tensioner" in demo.SHOT5_CAPTION


# ---------------------------------------------------------------------------
# the ROV
# ---------------------------------------------------------------------------

def _rov(sc):
    r = demo_rov.rov_root(sc)
    assert r is not None
    return r


def test_the_rov_is_still_beside_the_touch_down_and_shown_only_while_laying(built):
    sc, a = built
    r = _rov(sc)
    t9 = _t9(a)
    fps = int(a.fps)
    it = paths.find(sc, demo.CABLE_ITEM)
    hull = next(o for o in build.iter_parts(sc) if o.get(build.PROP_NAME) == "HULL")
    places, hulls = [], []
    worst_cable, lowest = 1e9, 1e9
    f9 = int(round(t9 * fps)) + 1
    for f in list(range(sc.frame_start, f9 - 1, 37)) + [f9 - 2]:
        sc.frame_set(f)
        places.append(np.array(r.matrix_world))
        hulls.append(np.array(hull.matrix_world)[2, 3])
        c = demo_rov.clearances(sc)
        worst_cable = min(worst_cable, c["cable"])
        _T, tdp = paths_sea.tdp_world(sc, paths.find(sc, demo.CABLE_ITEM))
        lowest = min(lowest, c["low"] - (tdp[2] - float(it.diameter) / 2.0))
        # beside the touch-down: level with it along the lay, 6–10 m to its side, looking at it
        M = places[-1]
        off = M[:3, 3] - np.array(tdp)
        assert abs(off[0]) < 3.0 and 6.0 < abs(off[1]) < 10.0, (f, off)
        fwd = M[:3, :3] @ np.array([1.0, 0.0, 0.0])
        to = -off[:2] / np.linalg.norm(off[:2])
        assert float(fwd[:2] @ to) > 0.98, f
        assert not demo_rov.rov_parts(sc)[0].hide_render, f
    spread = max(float(np.abs(p - places[0]).max()) for p in places)
    assert spread < 1e-4, spread                                      # Still: no heave, roll or pitch
    assert max(hulls) - min(hulls) > 0.05                              # (while the vessel does heave)
    assert worst_cable > 3.0, worst_cable                              # clear of the lay cable
    assert 1.5 < lowest < 4.0, lowest                                  # over the seabed, near it
    sc.frame_set(f9 + 2)
    assert all(o.hide_render for o in demo_rov.rov_parts(sc))           # hidden from shot 9 on
    sc.frame_set(sc.frame_start)


def test_the_rov_tether_is_a_hose_to_the_transom_and_out_of_the_clash_check(built):
    from fresing_render.blender import clash
    sc, a = built
    item = flex.find(sc, demo_rov.TETHER_ITEM)
    assert item is not None and item.kind == "HOSE" and not flex.broken(sc, item)
    names = {item.a_part.get(build.PROP_NAME), item.b_part.get(build.PROP_NAME)}
    assert "ROV TETHER TERMINATION" in names and names & {"HULL BOTTOM", "HULL"}
    leave = set()
    for fn in clash.HOOKS:
        _add, out = fn(sc)
        leave |= {o.name for o in out}
    assert {o.name for o in demo_rov.rov_parts(sc)} <= leave
    # the drawn tether follows the transom: its end there moves with the vessel, its ROV end stays put
    t9 = _t9(a)
    f9 = int(round(t9 * int(a.fps)))
    ends = []
    for f in (sc.frame_start, f9 // 2, f9 - 5):
        sc.frame_set(f)
        line = np.asarray(flex.shape_now(sc, item), dtype=float)
        ends.append((line[0], line[-1]))
        assert line[:, 2].min() > paths_sea.tdp_world(sc, paths.find(sc, demo.CABLE_ITEM))[1][2] + 0.5, f
    sc.frame_set(sc.frame_start)


def test_the_rov_lights_glow(built):
    sc, _a = built
    lenses = [o for o in demo_rov.rov_parts(sc) if o.get(build.PROP_NAME) == "ROV LIGHT LENS"]
    assert len(lenses) == 2
    for o in lenses:
        mat = o.material_slots[0].material if o.material_slots else None
        assert mat is not None
        bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        assert bsdf.inputs["Emission Strength"].default_value > 1.0


# ---------------------------------------------------------------------------
# the tipping winches' drums
# ---------------------------------------------------------------------------

def test_the_tipping_drums_pay_out_what_the_tipping_wires_take(built):
    from fresing_render.blender import joints, spool
    sc, a = built
    t9 = _t9(a)
    f9 = int(round(t9 * int(a.fps)))
    for key, tip_name in demo.TIP_ITEMS:
        wire = paths.find(sc, demo.TIP_DRUM_WIRE.format(key=key))
        sp = spool.find(sc, demo.TIP_SPOOL.format(key=key))
        assert wire.moving and sp is not None and not sp.problem
        lo, hi = spool.fleet(sc, sp)
        assert math.degrees(max(lo, hi)) < demo.TIP_FLEET_MAX                  # the narrow drum: ≤ 2° (was 6.5°)
        travel = joints.find(sc, wire.joint)
        assert travel.follows == paths.find(sc, tip_name).joint
        drum = joints.find(sc, sp.joint)
        seen = set()
        for f in range(f9, sc.frame_end + 1, 60):
            sc.frame_set(f)
            tip = paths.find(sc, tip_name)
            pay_tip = paths.tight_payout(sc, tip)
            pay_drum = joints.get_value(joints.find(sc, wire.joint))
            ratio = travel.couple_ratio
            assert pay_drum == pytest.approx(ratio * joints.get_value(joints.find(sc, tip.joint)), abs=0.03), f
            seen.add(round(abs(pay_tip), 1))
            # the drum turns by its spool's table with that payout (layer by layer)
            _top, fmap = joints.chain_map(sc, drum)
            assert joints.get_value(drum) == pytest.approx(
                float(fmap(joints.get_value(joints.find(sc, paths.find(sc, tip_name).joint)))), abs=1e-4)
            assert len(paths.shape_now(sc, paths.find(sc, demo.TIP_DRUM_WIRE.format(key=key)))) > 2
        assert max(seen) > 20.0, seen                                    # the tipping pays out tens of metres
    sc.frame_set(sc.frame_start)
