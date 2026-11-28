"""Task 0347 D: the coolant liquid's six checks (study 0251's T1–T6) in Blender – ``blender/liquid_lab.py`` builds the
six rigs side by side, bakes their liquid next to the project and draws it from the bakes; each case's number is
within its limit, the same frame gives the same picture, and a saved project opened again draws the same."""

import json
import os

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import liquid_lab  # noqa: E402
from fresing_render.core import liquid_lab as core  # noqa: E402


@pytest.fixture(scope="module")
def lab(tmp_path_factory):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    folder = str(tmp_path_factory.mktemp("lab") / "Lab é")
    os.makedirs(folder)
    sc = bpy.context.scene
    out = liquid_lab.build(sc, folder)
    yield sc, folder, out
    fresing_render.unregister()


def _faces(cid, chart):
    ob = bpy.data.objects.get(liquid_lab.sheet_name(cid, chart))
    return np.array([v.co[:] for v in ob.data.vertices]), len(ob.data.polygons)


def _picture():
    out = {}
    for ob in bpy.data.objects:
        if ob.get(liquid_lab.TAG) in ("sheet", "drops"):
            co = np.zeros(len(ob.data.vertices) * 3, np.float32)
            ob.data.vertices.foreach_get("co", co)
            out[ob.name] = co
    return out


def test_the_six_numbers_are_within_their_limits(lab):
    sc, folder, out = lab
    assert set(out) - {"seconds"} == set(core.IDS)
    for cid in core.IDS:
        row = out[cid]
        assert row["ok"], (cid, row["text"])
        assert os.path.isfile(os.path.join(folder, liquid_lab.FOLDER, row["file"]))
    r = {cid: out[cid]["result"] for cid in core.IDS}
    assert abs(r["pocket"]["error_pct"]) <= 2.0
    assert r["slot"]["left_pct"] < 15.0 and r["slot"]["half_s"] < 1.0
    assert abs(r["tilt"]["error_deg"]) <= 1.5
    assert r["tray"]["empty_95pct_s_after_stop"] <= 30.0
    assert abs(r["slosh"]["period_s"] - r["slosh"]["expected_period_s"]) < 0.1
    assert r["wall"]["worst_behind_wall_cm3"] == 0.0
    # kept in the scene for the tour's checks
    assert liquid_lab.case_row(sc, "wall")["text"] == out["wall"]["text"]
    assert sc.frame_end == sc.frame_start + max(c.frames for c in core.lab())
    assert out["seconds"] < 120, out["seconds"]


def test_the_rigs_stand_side_by_side_on_the_floor(lab):
    sc, _, _ = lab
    boxes = [liquid_lab.case_row(sc, cid)["box"] for cid in core.IDS]
    for (lo, hi), (lo2, _hi2) in zip(boxes, boxes[1:]):
        assert lo2[0] - hi[0] >= core.GAP - 1e-9                 # one beside the other along x, apart
    for lo, _hi in boxes:
        assert lo[2] > 0.0                                        # over the floor
    for cid in core.IDS:
        for name in liquid_lab.case_row(sc, cid)["charts"]:
            rig = bpy.data.objects[liquid_lab.bed_name(cid, name)]
            assert len(rig.data.polygons) > 0 and rig.data.materials[0].name == liquid_lab.MAT_BED
            assert bpy.data.objects[liquid_lab.sheet_name(cid, name)].parent is rig
    tray = bpy.data.objects[liquid_lab.bed_name("tray", "tray")]
    idx = np.zeros(len(tray.data.polygons), np.int32)
    tray.data.polygons.foreach_get("material_index", idx)
    assert 0 < int((idx == 1).sum()) < 100                        # the drain: a few dark cells


def test_the_moving_rigs_follow_their_motion(lab):
    sc, _, _ = lab
    s0 = sc.frame_start
    tilt = bpy.data.objects[liquid_lab.bed_name("tilt", "plate")]
    sc.frame_set(s0 + core.Tilt.frames)
    assert abs(tilt.matrix_world.to_euler().y - np.radians(30.0)) < 1e-3
    box = bpy.data.objects[liquid_lab.bed_name("slosh", "box")]
    x0 = liquid_lab.case_row(sc, "slosh")["offset"][0]
    assert abs(box.matrix_world.translation.x - (x0 + 0.125)) < 1e-4
    sc.frame_set(s0)
    assert abs(tilt.matrix_world.to_euler().y) < 1e-6
    assert abs(box.matrix_world.translation.x - x0) < 1e-6


def test_the_liquid_is_drawn_where_it_should_be(lab):
    sc, _, _ = lab
    s0 = sc.frame_start
    sc.frame_set(s0)
    assert _faces("pocket", "plate")[1] == 0                      # nothing poured yet
    assert _faces("slosh", "box")[1] > 0 and _faces("tilt", "plate")[1] > 0 and _faces("wall", "tank")[1] > 0
    sc.frame_set(s0 + core.Pocket.frames)                         # the end: the pocket full
    v, n = _faces("pocket", "plate")
    assert n >= 40 * 40
    assert np.all(np.abs(v[:, 0]) <= 0.051) and np.all(np.abs(v[:, 1]) <= 0.051)
    sc.frame_set(liquid_lab.case_frame(sc, "slot"))               # the slot full at the end of the pour
    assert _faces("slot", "plate")[1] >= 10 * 80
    sc.frame_set(liquid_lab.case_frame(sc, "tray"))
    assert _faces("tray", "tray")[1] > 100
    wall_v, _ = _faces("wall", "tank")
    assert np.all(wall_v[:, 0] <= 0.0605)                          # none behind the wall (x > 60.5 mm)
    sc.frame_set(s0 + 30)
    drops = bpy.data.objects[liquid_lab.OBJ_DROPS]
    assert len(drops.data.vertices) > 0                           # the pour into the pocket falls as drops


def test_the_same_frame_gives_the_same_picture(lab):
    sc, _, _ = lab
    f = sc.frame_start + 50
    sc.frame_set(f)
    a = _picture()
    sc.frame_set(f + 200)
    b = _picture()
    sc.frame_set(f)
    c = _picture()
    assert a.keys() == c.keys()
    assert any(len(a[k]) != len(b[k]) or not np.array_equal(a[k], b[k]) for k in a)
    for k in a:
        assert np.array_equal(a[k], c[k]), k


def test_saved_and_opened_again_draws_the_same(lab):
    sc, folder, _ = lab
    f = sc.frame_start + 60
    sc.frame_set(f)
    a = _picture()
    path = os.path.join(folder, "lab.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    for ob in bpy.data.objects:                                   # nothing drawn: the handler draws it again
        if ob.get(liquid_lab.TAG) == "sheet":
            ob.data.clear_geometry()
    sc.frame_set(f)
    b = _picture()
    assert a.keys() == b.keys()
    for k in a:
        assert np.array_equal(a[k], b[k]), k
    # the bakes found next to the project when the folder moved
    d = liquid_lab.data(sc)
    for row in d["cases"].values():
        row["path"] = os.path.join(folder, "gone", row["file"])
    sc[liquid_lab.PROP] = json.dumps(d)
    liquid_lab.forget()
    sc.frame_set(f)
    c = _picture()
    for k in a:
        assert np.array_equal(a[k], c[k]), k
