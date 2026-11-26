"""Task 0346, independent tests (written from the brief by an agent that did not write liquid.py)."""

import os

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
pytest.importorskip("manifold3d")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import chips, gcode, liquid, machining  # noqa: E402

HERE = os.path.dirname(__file__)
MILL = os.path.join(HERE, "data", "test_mill.step")
FP = {}


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def make_scene(tmp, text=liquid.TEST_PROGRAM, save=True):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    machining._RUNTIME.clear()
    chips.forget()
    liquid.forget()
    gcode._CACHE.clear()
    gcode._INFO.clear()
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp)
    assert bpy.ops.fresing.import_step(filepath=MILL, quality="draft") == {"FINISHED"}
    a, r = liquid.set_up_test_model(sc, str(tmp), text, 16.0)
    assert not r["warnings"], r["warnings"]
    if save:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(str(tmp), "liquid.blend"))
    return bpy.context.scene, a


@pytest.fixture(scope="module")
def baked(addon, tmp_path_factory):
    tmp = tmp_path_factory.mktemp("liq_ind")
    sc, a = make_scene(tmp)
    FP["base"] = liquid.fingerprint(sc)
    info = liquid.bake_now(sc, helpers=0)
    assert info
    return sc, info


def _frames(rd, step=7):
    fr = [int(f) for f in rd.frames]
    return fr[::step] + [fr[-1]]


def _co(name):
    me = bpy.data.objects[name].data
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    return co


def test_bookkeeping_at_every_sampled_frame(baked):
    sc, _ = baked
    rd, _b = liquid._open(sc)
    last = -1.0
    for f in _frames(rd, 5):
        t = rd.read(f)[3]
        parts = t["on_charts"] + t["in_flight"] + t["drained"] + t["floor"]
        assert t["poured"] == pytest.approx(parts, abs=1e-6, rel=1e-4), (f, t)
        assert t["poured"] >= last - 1e-12
        last = t["poured"]
        assert min(t[k] for k in ("on_charts", "in_flight", "drained", "floor")) >= -1e-9


def test_depths_finite_non_negative_and_drops_above_floor(baked):
    sc, _ = baked
    rd, _b = liquid._open(sc)
    st = liquid.gather(sc)
    for f in _frames(rd, 6):
        depths, drops, vols, _t = rd.read(f)
        for d in depths:
            assert np.isfinite(d).all() and (d >= 0).all(), f
        drops = np.asarray(drops)
        assert np.isfinite(drops).all()
        assert len(drops) == len(vols)
        assert (np.asarray(vols) >= 0).all()
        if len(drops):
            assert drops[:, 2].min() >= st.floor_z - 1e-3, (f, drops[:, 2].min(), st.floor_z)


def test_drawn_sheets_are_finite_and_above_the_bed(baked):
    sc, _ = baked
    rd, _b = liquid._open(sc)
    st = liquid.gather(sc)
    tray = st.charts[1]
    lo = float(np.nanmin(tray.bed[tray.bed > -0.6]))
    for f in _frames(rd, 9):
        sc.frame_set(f)
        for name in (liquid.OBJ_TABLE, liquid.OBJ_TRAY, liquid.OBJ_DROPS):
            assert np.isfinite(_co(name)).all(), (name, f)
        co = _co(liquid.OBJ_TRAY)
        if len(co):
            assert co.reshape(-1, 3)[:, 2].min() >= lo - 1e-4, (f, lo)


def test_sheet_lies_at_bed_plus_depth():
    bed = np.zeros((5, 5))
    bed[:, 2:] = 0.010
    d = np.zeros((5, 5))
    d[1:4, 1:4] = 3e-3
    v, q = liquid.sheet(d, bed, 0.004, 1.0, 2.0)
    assert len(q) > 0 and np.isfinite(v).all()
    assert v[:, 2].min() >= -1e-9
    assert v[:, 2].max() <= (bed + d).max() + liquid.LIFT + 1e-9
    assert v[:, 0].min() >= 1.0 - 1e-9 and v[:, 1].min() >= 2.0 - 1e-9
    assert v[:, 0].max() <= 1.0 + 5 * 0.004 + 1e-9


def test_fingerprint_rules(baked):
    sc, _ = baked
    s = sc.fresing.coolant
    base = liquid.fingerprint(sc)
    assert base == FP["base"]
    liquid.forget()
    assert liquid.fingerprint(sc) == base
    s.liquid_detail = "NORMAL"
    assert liquid.fingerprint(sc) != base
    s.liquid_detail = "DRAFT"
    assert liquid.fingerprint(sc) == base
    fl = s.flow
    s.flow = 0.4
    assert liquid.fingerprint(sc) != base
    s.flow = fl
    assert liquid.fingerprint(sc) == base
    assert liquid.is_baked(sc)


def test_frames_outside_the_range_do_not_break(baked):
    sc, _ = baked
    rd, _b = liquid._open(sc)
    f0, f1 = int(rd.frames[0]), int(rd.frames[-1])
    for f in (f0 - 30, f0 - 1, f1 + 1, f1 + 50):
        sc.frame_set(f)
        for o in liquid.objects():
            assert np.isfinite(_co(o.name)).all()
    assert liquid.show(sc, T=f0 - 100.0) is True
    assert liquid.show(sc, T=f1 + 100.0) is True


def test_a_frame_past_the_end_is_the_last_frame(baked):
    sc, _ = baked
    rd, _b = liquid._open(sc)
    f1 = int(rd.frames[-1])
    liquid.show(sc, T=float(f1))
    a = _co(liquid.OBJ_TRAY)
    liquid.show(sc, T=float(f1 + 40))
    assert np.array_equal(a, _co(liquid.OBJ_TRAY))


def test_cache_is_next_to_the_project(baked):
    sc, _ = baked
    p = sc[liquid.CACHE_PROP]
    assert os.path.isfile(p) and os.path.isfile(p + ".beds.npz")
    assert os.path.dirname(p).endswith("_liquid")
    assert os.path.dirname(os.path.dirname(p)) == os.path.dirname(bpy.data.filepath)


def test_the_bake_does_not_depend_on_the_frame_shown(baked):
    """A bake worked out while another frame is shown must be the same liquid (Build reads from the first frame)."""
    sc, _ = baked
    sc.frame_set(int(sc.frame_start))
    rd, _b = liquid._open(sc)
    fr = _frames(rd, 11)
    ref = {f: [d.copy() for d in rd.read(f)[0]] for f in fr}
    sc.frame_set(int(sc.frame_start) + 100)
    liquid.forget()
    for _p in liquid.steps(sc, [], helpers=0):
        pass
    liquid.forget()
    rd, _b = liquid._open(sc)
    for f in fr:
        for a, b in zip(ref[f], rd.read(f)[0]):
            assert np.array_equal(a, b), (f, float(np.abs(a - b).max()), int((a != b).sum()))
    sc.frame_set(int(sc.frame_start))


def test_helpers_give_the_same_depths_bit_for_bit(baked):
    sc, _ = baked
    sc.frame_set(int(sc.frame_start))
    liquid.forget()
    for _p in liquid.steps(sc, [], helpers=0):          # (own reference: the test before may have left a skewed bake)
        pass
    liquid.forget()
    rd, _b = liquid._open(sc)
    fr = _frames(rd, 11)
    ref = {f: [d.copy() for d in rd.read(f)[0]] for f in fr}
    tot0 = rd.read(fr[-1])[3]
    liquid.forget()
    for _p in liquid.steps(sc, [], helpers=2):
        pass
    liquid.forget()
    rd, _b = liquid._open(sc)
    assert rd is not None
    for f in fr:
        for a, b in zip(ref[f], rd.read(f)[0]):
            assert np.array_equal(a, b), (f, float(np.abs(a - b).max()), int((a != b).sum()), float(a.max()))
    assert rd.read(fr[-1])[3]["drained"] == pytest.approx(tot0["drained"], rel=1e-9, abs=1e-12)


def test_render_queue_path_bakes_when_needed(baked):
    sc, _ = baked
    path = sc[liquid.CACHE_PROP]
    liquid.forget()
    os.remove(path)
    os.remove(path + ".beds.npz")
    assert not liquid.is_baked(sc)
    machining.prepare(sc)
    assert os.path.isfile(sc[liquid.CACHE_PROP])
    assert liquid.is_baked(sc)
    assert liquid.objects()


def test_switching_off_empties_and_frames_draw_nothing(baked):
    sc, _ = baked
    s = sc.fresing.coolant
    sc.frame_set(int(sc.frame_start) + 60)
    assert liquid.objects()
    s.liquid_on = False
    assert not liquid.asked(sc) and not liquid.wanted(sc)
    for o in liquid.objects():
        assert len(o.data.vertices) == 0
    sc.frame_set(int(sc.frame_start) + 70)
    for o in liquid.objects():
        assert len(o.data.vertices) == 0
    s.liquid_on = True
    s.enabled = False                                       # coolant off with the tick on: no liquid
    sc.frame_set(int(sc.frame_start) + 80)
    assert not liquid.asked(sc)
    for o in liquid.objects():
        assert len(o.data.vertices) == 0
    s.enabled = True
    # (turning coolant off drops its spans: liquid.problem() then asks for Build again - coolant.py behaviour)


def test_unsaved_bake_moves_next_to_the_project_and_reopens(addon, tmp_path):
    sc, _a = make_scene(tmp_path, save=False)
    assert not bpy.data.filepath
    assert liquid.fingerprint(sc) == FP["base"]
    liquid.bake_now(sc, helpers=0)
    p = sc[liquid.CACHE_PROP]
    assert os.path.isfile(p)
    bpy.ops.wm.save_as_mainfile(filepath=str(tmp_path / "later.blend"))
    sc = bpy.context.scene
    p2 = sc[liquid.CACHE_PROP]
    assert p2.startswith(str(tmp_path)) and "_liquid" in p2, p2
    assert os.path.isfile(p2) and os.path.isfile(p2 + ".beds.npz")
    assert liquid.is_baked(sc)
    m = os.path.getmtime(p2)
    bpy.ops.wm.open_mainfile(filepath=str(tmp_path / "later.blend"), load_ui=False)
    sc = bpy.context.scene
    assert liquid.is_baked(sc)
    assert liquid.bake_now(sc) is not None
    assert os.path.getmtime(liquid.runtime(sc)["path"]) == m
    sc.frame_set(int(sc.frame_start) + 60)
    assert liquid.objects()
    # the stored bake path must name the file in use (the saved file still held the temp path, save_post moves the
    # file after the save; the render queue's copy reads the stored path first)
    assert os.path.isfile(sc.get(liquid.CACHE_PROP, "")), sc.get(liquid.CACHE_PROP)


def test_another_program_is_another_fingerprint(addon, tmp_path):
    sc, _a = make_scene(tmp_path, text=liquid.long_program(2), save=False)
    assert liquid.fingerprint(sc) != FP["base"]
