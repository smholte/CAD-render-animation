"""Task 0347: the coolant liquid on the 4th axis (tests/data/test_4axis.step) and the trunnion (test_5axis.step).

4th axis: the bar Ø50 turns about X (the A axis at y 0, z 210) on the X table. The liquid's charts: four round the bar
(their z out from the axis at 0, 90, 180, 270 deg), the X table, the tray. The program floods while it cuts a pocket on
the bar's top and a groove wrapped round it, M9, then the bar turns slowly by 90 deg and on to upside down.
Trunnion: the block on the C table, on the cradle (A), on the X table: charts table (C), carrier 1 (the cradle),
carrier 2 (the X table), the tray. The program floods while it cuts two tilted pockets, M9, the cradle tilts to
A-35 and back. Detail Draft, no helpers.
"""

import os

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
mf = pytest.importorskip("manifold3d")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import chips, coolant, gcode, joints, liquid, machining  # noqa: E402

HERE = os.path.dirname(__file__)
MM = 0.001


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def make(tmp, five):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    machining._RUNTIME.clear()
    chips.forget()
    liquid.forget()
    gcode._CACHE.clear()
    gcode._INFO.clear()
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp)
    model = os.path.join(HERE, "data", "test_5axis.step" if five else "test_4axis.step")
    assert bpy.ops.fresing.import_step(filepath=model, quality="draft") == {"FINISHED"}
    _a, r = liquid.set_up_test_rotary(sc, str(tmp), five=five)
    assert not r["warnings"], r["warnings"]
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(str(tmp), "liquid.blend"))
    sc = bpy.context.scene
    assert liquid.problem(sc) == ""
    info = liquid.bake_now(sc, helpers=0)
    assert info is not None and info["frames"] > 100
    return sc, info


def volumes(sc):
    """cm^3 per chart at every frame of the bake: (frames, (n, charts))."""
    rd, beds = liquid._open(sc)
    fr = [int(f) for f in rd.frames]
    v = np.array([[float(d.sum()) * g[0] ** 2 * 1e6 for d, g in zip(rd.read(f)[0], beds.geom)] for f in fr])
    return np.array(fr), v


def flood_end(sc):
    sp = coolant.spans()
    assert len(sp) == 1
    return int(round(sp[0, 1]))


@pytest.fixture(scope="module")
def four(addon, tmp_path_factory):
    sc, info = make(tmp_path_factory.mktemp("liquid4"), five=False)
    return sc, info


@pytest.fixture(scope="module")
def five(addon, tmp_path_factory):
    sc, info = make(tmp_path_factory.mktemp("liquid5"), five=True)
    return sc, info


# --- the 4th axis ---------------------------------------------------------------------------------------------------

def test_4th_axis_charts_round_the_bar(four):
    sc, info = four
    st = liquid.gather(sc)
    assert st.roles == ["bar 1", "bar 2", "bar 3", "bar 4", "carrier 1", "tray"]
    o, u = st.bar
    assert abs(abs(u[0]) - 1.0) < 1e-4                           # along X …
    assert abs(o[1]) < 1e-4 and abs(o[2] - 0.21) < 1e-4           # … through the A axis' point
    # the four charts' z: out from the axis, 90 deg apart, the first one up
    zs = [pl.C[:3, 2] for pl in st.plans[:4]]
    assert zs[0][2] > 0.999
    for a in range(4):
        assert abs(float(np.dot(zs[a], zs[(a + 1) % 4]))) < 1e-6 and abs(float(np.dot(zs[a], u))) < 1e-6
    # their beds are the bar's surface: the distance from the axis, 25 mm (less where it is cut)
    rd, beds = liquid._open(sc)
    for c in range(4):
        b = beds.at(c, int(rd.frames[-1]))
        fin = b[np.isfinite(b)]
        assert len(fin) > 100 and fin.max() <= 25 * MM + 1e-4 and np.median(fin) > 20 * MM
    names = str(machining.settings(sc)["fr_chain"]).split("\n")
    assert beds.follow[:4] == ["@workpiece"] * 4 and beds.follow[4] == names[1] and beds.follow[5] == ""
    assert info["totals"]["poured"] > 1.0
    t = info["totals"]
    assert abs(t["poured"] - t["on_charts"] - t["in_flight"] - t["drained"] - t["floor"]) < 1e-9


def test_4th_axis_sheet_lies_on_the_bar(four):
    """Drawn where it lies: the sheet of the top chart, at a frame the bar has turned, is on the bar's surface (its
    world points 22 … 37 mm from the A axis, as the bar is in the world at that frame)."""
    sc, _info = four
    st = liquid.gather(sc)
    fr, v = volumes(sc)
    m9 = flood_end(sc)
    k = int(np.argmax(np.where((fr > st.f0 + 20) & (fr < m9), v[:, 0], -1)))
    f = int(fr[k])
    assert v[k, 0] > 1.0
    sc.frame_set(f)
    ob = bpy.data.objects[liquid.chart_object("bar 1")]
    assert len(ob.data.polygons) > 20
    W = np.array(ob.matrix_world)
    co = np.array([vv.co for vv in ob.data.vertices], np.float64)
    w = co @ W[:3, :3].T + W[:3, 3]
    o, u = st.bar
    M = st.carry[f - st.f0]
    ow, uw = M[:3, :3] @ o + M[:3, 3], M[:3, :3] @ u
    rel = w - ow
    r = np.linalg.norm(rel - (rel @ uw)[:, None] * uw[None], axis=1)
    # (the flood stands a few mm on the bar: the height field carries a film at critical depth, ~5 mm at 14 l/min)
    assert r.min() > 21.5 * MM and r.max() < 37 * MM and np.percentile(r, 90) < 33 * MM, (r.min(), r.max())
    # the bar has turned by then: the chart's own up is not the world's up
    a = joints.get_value(sc.fresing.joints["Rotary A"])
    assert abs(a) > 0.1


def test_4th_axis_liquid_runs_off_as_the_bar_turns(four):
    sc, _info = four
    fr, v = volumes(sc)
    m9 = flood_end(sc)
    bars = v[:, :4].sum(axis=1)
    held = bars[fr == m9 + 6][0]                                  # the pocket still up, the bar still
    assert held > 1.0, held
    assert bars[-1] < 0.05 * held and bars[-1] < 0.5, (held, bars[-1])
    # it went to the table and the tray (nothing lost, nothing made)
    assert v[-1, 4] > 50.0 and v[-1, 5] > 10.0


def test_4th_axis_same_frame_same_liquid(four):
    sc, _info = four
    f = flood_end(sc) - 10
    sc.frame_set(f)
    a = {o.name: len(o.data.vertices) for o in liquid.objects()}
    sc.frame_set(sc.frame_start)
    sc.frame_set(f)
    assert {o.name: len(o.data.vertices) for o in liquid.objects()} == a
    assert a[liquid.chart_object("carrier 1")] > 0


# --- the trunnion ---------------------------------------------------------------------------------------------------

def test_trunnion_charts_ride_on_c_a_and_x(five):
    sc, info = five
    st = liquid.gather(sc)
    assert st.roles == ["table", "carrier 1", "carrier 2", "tray"] and st.bar is None
    names = str(machining.settings(sc)["fr_chain"]).split("\n")
    rd, beds = liquid._open(sc)
    assert beds.follow == ["@workpiece", names[1], names[2], ""]
    assert "Trunnion A" in names[1] and "X" in names[2]
    t = info["totals"]
    assert abs(t["poured"] - t["on_charts"] - t["in_flight"] - t["drained"] - t["floor"]) < 1e-9


def test_trunnion_tilt_spills_the_pools_to_the_low_side(five):
    sc, _info = five
    st = liquid.gather(sc)
    fr, v = volumes(sc)
    m9 = flood_end(sc)
    j = sc.fresing.joints["Trunnion A"]
    ang = {}
    for f in fr[fr >= m9]:
        sc.frame_set(int(f))
        ang[int(f)] = joints.get_value(sc.fresing.joints["Trunnion A"])
    tilt = max(ang, key=lambda f: abs(ang[f]))                       # (program A-35 = the joint at +35 deg)
    assert abs(np.degrees(ang[tilt])) > 30.0, np.degrees(ang[tilt])
    before = v[fr == m9 + 6][0]
    k = int(np.nonzero(fr == tilt)[0][0])
    after = v[k]
    assert after[0] < 0.5 * before[0], (before, after)                 # the C table spilled …
    assert v[m9 - st.f0: k + 1, 1].max() > before[1] + 5.0              # … onto the cradle
    # what is left on the table moved to its low side (most of it lies in the T-slots, which hold it)
    rd, beds = liquid._open(sc)
    cell, x0, y0 = beds.geom[0]

    def ymean(f):
        d = rd.read(int(f))[0][0]
        ys = y0 + np.arange(d.shape[0]) * cell
        return float((d.sum(axis=1) * ys).sum() / max(float(d.sum()), 1e-12))
    M = st.mats[0][tilt - st.f0]
    low = -1.0 if (M[:3, :3] @ np.array([0.0, 1.0, 0.0]))[2] > 0 else 1.0       # the chart's y side that is lower
    assert (ymean(tilt) - ymean(m9 + 6)) * low > 0.002, (ymean(m9 + 6), ymean(tilt), low)
