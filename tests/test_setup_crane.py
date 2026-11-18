"""Set up a crane (task 0203): the AT-40, the CC-750 with its luffing jib and the KB-50 rigged from their bare STEP
through the Set-up window's buttons only (``tests/crane_setup_drive.py``), compared with the built-in rig of the same
class; Save into a library (never the built-ins) → Place in a new project → the same joints, poses, hook point, masses
and chart, and Hook to here gives the class solver's answer; the Check finds a planted fault of each kind and names
its step; masses by volume x density, the chart typed and pasted; "Other crane" with roles by hand. Blender as a
Python module."""

from __future__ import annotations

import json
import math
import os

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")

import fresing_render  # noqa: E402
from fresing_render.core import lifting_library as LL, lifting_reach as LR  # noqa: E402

import crane_setup_drive as D  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIFT = os.path.join(ROOT, "fresing_render", "data", "lifting")
os.environ.setdefault("FRESING_LIFTING_UNDERSTOOD", "1")


@pytest.fixture(scope="module", autouse=True)
def registered():
    mine = not hasattr(bpy.types.Scene, "fresing")
    if mine:
        fresing_render.register()
    yield
    if mine:
        bpy.ops.wm.read_homefile(use_empty=True)
        fresing_render.unregister()


def _mods():
    from fresing_render.blender import joints, lifting, lifting_rig_out, setup_crane
    return joints, lifting, lifting_rig_out, setup_crane


def _new(cls=None):
    from fresing_render.blender import workspaces
    bpy.ops.wm.read_homefile(use_empty=True)
    workspaces.use_all(bpy.context.scene)
    sc = bpy.context.scene
    sc.fresing.out_folder = "/tmp/fr_setup_crane_test"
    _j, BL, _ro, SC = _mods()
    BL.forget()
    SC.forget()
    if cls:
        step = os.path.join(LIFT, cls, cls + ".step")
        assert bpy.ops.fresing.import_step(filepath=step, quality="normal") == {"FINISHED"}
    return sc


def _class_answer(data, target, current, setup=None, hook_block_kg=0.0):
    """0201's class solver on the built-in file (the reference, kept in the tests only)."""
    import lifting_reach_class as RC
    return RC.class_hook_to(data, target, current, LL.charts_of(LL.from_data(data)), setup, 0.0, hook_block_kg)


_SAVED: dict = {}


def _rig_and_save(cls, tmp, kind=""):
    key = (cls, kind)
    if key in _SAVED and os.path.exists(_SAVED[key][0]):
        return _SAVED[key]
    _j, _BL, RO, SC = _mods()
    sc = _new(cls)
    made = D.rig(sc, cls, kind_override=kind, check=True, clash=False)
    red = [p.text for p in SC.settings(sc).problems if p.severity == "red"]
    assert not red, red
    lib = os.path.join(str(tmp), "library")
    os.makedirs(lib, exist_ok=True)
    path = RO.save(sc, lib)
    _SAVED[key] = (path, made)
    return path, made


@pytest.fixture(scope="module")
def lib_tmp(tmp_path_factory):
    return tmp_path_factory.mktemp("setup_crane")


@pytest.mark.parametrize("cls", ["AT-40", "CC-750", "KB-50"])
def test_rigged_through_the_steps_is_the_builtin_rig(cls, lib_tmp):
    path, made = _rig_and_save(cls, lib_tmp)
    with open(path, encoding="utf-8") as fh:
        saved = json.load(fh)
    assert D.compare(cls, saved, made) == []
    assert os.path.isfile(os.path.join(os.path.dirname(path), saved["rig"]["step"]))      # the STEP copied
    assert saved["sample"] is False and saved["kind"] == D.builtin(cls)["kind"]
    item = LL.read_item(path)
    assert item.ok and not item.builtin, item.problems


@pytest.mark.parametrize("cls", ["AT-40", "CC-750", "KB-50"])
def test_round_trip_places_and_hooks_as_the_class(cls, lib_tmp):
    """Save → Place in a new project beside the built-in of the class: the same joints, poses, hook point, masses and
    chart; Hook to here on the own crane = the built-in crane's answer = 0201's class solver's."""
    path, _made = _rig_and_save(cls, lib_tmp)
    joints, BL, _RO, _SC = _mods()
    sc = _new()
    own = BL.place(bpy.context, path, location=(0.0, 0.0, 0.0), heading=0.0)
    ref = BL.place(bpy.context, os.path.join(LIFT, cls), location=(0.0, 500.0, 0.0), heading=0.0)
    with open(path, encoding="utf-8") as fh:
        saved = json.load(fh)
    assert {j.name for j in BL.own_joints(sc, own)} == {BL.prefix(own) + j["name"] for j in saved["rig"]["joints"]}
    assert set(BL.pose_names(own)) == {p["name"] for p in saved["rig"]["poses"]}
    rig = BL.rig_of(own)
    assert np.allclose(rig.hook_cad, saved["rig"]["hook"]["point"])
    assert len(BL.charts_of(own)) == len(BL.charts_of(ref))
    for p in BL.pose_names(ref):           # every pose: the same readout (chart, capacity, use)
        BL.apply_pose(sc, own, p)
        BL.apply_pose(sc, ref, p)
        BL.forget()
        a, b = BL.readout(sc, own), BL.readout(sc, ref)
        assert (a.chart is None) == (b.chart is None), p                # the same chart (its name is only a label)
        if a.chart is not None:
            assert a.chart.config == pytest.approx(b.chart.config), p
        assert (a.capacity, a.radius, a.height) == pytest.approx((b.capacity, b.radius, b.height)), p
    BL.apply_pose(sc, own, BL.pose_names(ref)[-1])
    BL.apply_pose(sc, ref, BL.pose_names(ref)[-1])
    data = D.builtin(cls)
    ref_rig = LR.Rig(data)
    rng = np.random.default_rng(7)
    tried = 0
    for _k in range(40):
        vals = {jj["name"]: float(rng.uniform(*jj["limits"])) for jj in ref_rig.driven() if jj.get("limits")}
        target = ref_rig.hook(vals)
        want = BL.hook_to(sc, ref, BL.to_world(ref, target))
        if not want.ok:
            continue
        got = BL.hook_to(sc, own, BL.to_world(own, target))
        assert got.ok, got.reason
        assert np.linalg.norm(rig.hook({**BL.values(sc, own), **got.values}) - target) < 5.0
        assert abs(got.boom - want.boom) < 0.002
        assert (got.use is None) == (want.use is None)
        if want.use is not None:
            assert got.use == pytest.approx(want.use, rel=1e-6, abs=1e-9)
        cl = _class_answer(data, target, BL.values(sc, ref), BL.setup(sc, ref), BL.hook_block_kg(ref))
        if cl.ok:
            assert abs(got.boom - cl.boom) < 0.002
            if cl.use is not None:
                assert got.use == pytest.approx(cl.use, rel=1e-6, abs=1e-9)
        tried += 1
    assert tried >= 10


def test_never_into_the_builtins(lib_tmp):
    _j, _BL, RO, _SC = _mods()
    sc = _new("KB-20")
    D.rig(sc, "KB-20", check=False)
    for bad in (LL.BUILTIN_DIR, os.path.join(LL.BUILTIN_DIR, "x")):
        with pytest.raises((RO.RigError, LL.LibraryError)):
            RO.save(sc, bad)
    with pytest.raises(RO.RigError):
        RO.save(sc, "")
    assert sorted(os.listdir(LL.BUILTIN_DIR)) == sorted(
        ["AT-100", "AT-250", "AT-40", "AT-500", "CC-100", "CC-1600", "CC-300", "CC-750", "KB-100", "KB-20", "KB-200",
         "KB-50"])


def _rigged(cls="AT-40"):
    sc = _new(cls)
    D.rig(sc, cls, check=False)
    return sc


def _problems(sc, clash=False):
    _j, _BL, _RO, SC = _mods()
    assert bpy.ops.fresing.crane_check("EXEC_DEFAULT", True, clash=clash) == {"FINISHED"}
    return [(p.step, p.text) for p in SC.settings(sc).problems if p.severity == "red"]


def _goes_to(sc, key):
    _j, _BL, _RO, SC = _mods()
    assert bpy.ops.fresing.crane_go("EXEC_DEFAULT", True, key=key) == {"FINISHED"}
    keys = [k for k, *_r in SC.STEP_LISTS[sc.fresing.setup_kind]]
    return keys[sc.fresing.setup_step]


def test_check_finds_each_planted_fault():
    joints, _BL, _RO, SC = _mods()
    sc = _rigged("AT-40")
    assert _problems(sc) == []
    # a pose past a joint's limit
    pose = sc.fresing.poses["Working"]
    luff = SC.first(sc, "luff")
    for pj in pose.joints:
        if pj.joint == luff.name:
            pj.value = math.radians(95.0)
    got = _problems(sc)
    assert any(k == "luff" or k == "poses" for k, _t in got), got
    step = next(k for k, _t in got if k in ("luff", "poses"))
    assert _goes_to(sc, step) in ("luff", "poses")
    for pj in pose.joints:
        if pj.joint == luff.name:
            pj.value = math.radians(60.0)
    assert _problems(sc) == []
    # the hook not plumb: a swing that follows at the wrong ratio
    sw = SC.first(sc, "swing")
    joints.set_follows(sc, sw, sw.follows, ratio=-0.5)
    got = _problems(sc)
    assert any(k in ("hook_block", "swing", "hoist") for k, _t in got), got
    assert _goes_to(sc, "swing") == "hook_block"
    joints.set_follows(sc, SC.first(sc, "swing"), luff.name, ratio=-1.0)
    # a mass missing
    g = next(g for g in SC.settings(sc).groups if g.key == "boom")
    keep = g.mass_t
    g.mass_t = 0.0
    got = _problems(sc)
    assert any(k == "masses" for k, _t in got), got
    assert _goes_to(sc, "masses") == "masses"
    g.mass_t = keep
    # a chart refused: a capacity that rises with the radius
    c = SC.settings(sc).charts[0]
    keep = c.rows[2].capacity
    c.rows[2].capacity = str(float(c.rows[0].capacity) * 2.0)
    got = _problems(sc)
    assert any(k == "chart" for k, _t in got), got
    assert _goes_to(sc, "chart") == "chart"
    c.rows[2].capacity = keep
    assert _problems(sc) == []


def test_check_finds_a_clash_and_its_step():
    """The boom let down below level runs into the carrier: the clash check of the crane's own motion finds it."""
    joints, _BL, _RO, SC = _mods()
    sc = _rigged("KB-20")
    for j in SC.crane_joints(sc):
        if j.role not in ("luff",) or j.follows:
            continue
        j.rot_min = math.radians(-60.0)
    got = _problems(sc, clash=True)
    assert any(k == "luff" and "clash" in t for k, t in got), got


def test_chart_typed_and_pasted_with_refusals_by_row():
    _j, _BL, _RO, SC = _mods()
    sc = _new("KB-20")
    cs = SC.settings(sc)
    assert bpy.ops.fresing.crane_chart_add("EXEC_DEFAULT", True) == {"FINISHED"}
    c = cs.charts[0]
    c.boom = 8.0
    for r, cap in (("2", "5"), ("4", "3,5"), ("6", "")):
        row = c.rows[-1] if not c.rows[-1].radius else c.rows.add()
        row.radius, row.capacity = r, cap
    e = SC.chart_entry(sc)
    assert e.ok and len(e.charts) == 1 and e.charts[0].capacity[2] is None
    assert SC.chart_dicts(sc)[0]["config"]["boom"] == 8.0
    c.rows[1].radius = "1"
    e = SC.chart_entry(sc)
    assert not e.ok and any("Row 2" in m for m in e.errors), e.errors
    text = "boom 8 m; counterweight 2 t\nradius (m);capacity (t)\n2;5\n4;3,5\n"
    assert bpy.ops.fresing.crane_chart_csv("EXEC_DEFAULT", True, paste=True, text=text) == {"FINISHED"}
    assert len(cs.charts) == 1 and cs.charts[0].counterweight == pytest.approx(2.0)
    assert bpy.ops.fresing.crane_chart_csv("EXEC_DEFAULT", True, paste=True, text="2;5\n1;6\n") == {"CANCELLED"}
    assert "Line 2" in cs.message


def test_masses_by_volume_and_markers():
    _j, _BL, _RO, SC = _mods()
    sc = _rigged("KB-20")
    cs = SC.settings(sc)
    g = next(g for g in cs.groups if g.key == "outer_boom")
    g.mass_mode = "VOLUME"
    g.cog_by_hand = False
    g.density = 7850.0
    assert bpy.ops.fresing.crane_group_work("EXEC_DEFAULT", True, key=g.key) == {"FINISHED"}
    assert g.volume_mass > 10.0
    objs, _bad = SC.objects_of(sc, g.parts)
    mn, mx = _BL_bounds(objs)
    root = SC.model_root(sc)
    c = SC.to_world(root, np.asarray(g.cog) * 1000.0)
    assert all(mn[i] - 1e-3 <= c[i] <= mx[i] + 1e-3 for i in range(3))
    assert g.marker is not None and (np.array(g.marker.matrix_world.translation) - np.array(c)).max() < 1e-3


def _BL_bounds(objs):
    from fresing_render.blender import build
    _j, _BL, _RO, SC = _mods()
    return build.world_bounds(SC.parts_of(objs))


def test_other_crane_with_roles_by_hand(lib_tmp):
    """KB-50 set up as 'Other crane' (each joint's role picked by hand) saves a file Hook to here solves."""
    path, made = _rig_and_save("KB-50", lib_tmp, kind="CRANE_OTHER")
    with open(path, encoding="utf-8") as fh:
        saved = json.load(fh)
    assert saved["kind"] == "other_crane"
    roles = {j["role"] for j in saved["rig"]["joints"]}
    assert {"slew", "luff", "knuckle", "extension", "hoist", "swing", "outrigger", "jack"} <= roles
    rig = LR.Rig(saved)
    ref = LR.Rig(D.builtin("KB-50"))
    t = ref.hook({"Main boom": 30.0, "Knuckle": -10.0, "Extension": 800.0, "Hoist": 3000.0})
    a = LR.hook_to(rig, t, {})
    assert a.ok, a.reason
    assert np.linalg.norm(rig.hook(a.values) - t) < 1.0


def test_steps_draw_for_every_kind():
    """Every step of every kind draws without an error (no model, then the AT-40 rigged)."""
    _j, _BL, _RO, SC = _mods()
    from fresing_render.blender import ui_setup

    class Lay:
        def __getattr__(self, name):
            return lambda *a, **k: self

    class Ctx:
        scene = None
        region = None
        window = None
        view_layer = None

    for cls in (None, "AT-40"):
        sc = _rigged(cls) if cls else _new()
        Ctx.scene = sc
        Ctx.view_layer = bpy.context.view_layer
        for kind in SC.STEP_LISTS:
            for _key, _title, draw, done in SC.STEP_LISTS[kind]:
                draw(Lay(), Ctx)
                if done is not None:
                    done(Ctx)
        assert "CRANE_MOBILE" in ui_setup.SETUPS and "CRANE_OTHER" in ui_setup.CHECKS
