"""Task 0346: the coolant liquid on the 3-axis VMC (tests/data/test_mill.step) – charts from the machine, the bake at
Build, the drawing, the cache.

The block (200 x 200 x 40 mm, top at z = 70 mm) is clamped on the table (1200 x 500, three T-slots open at both ends)
that moves in X on the saddle (Y). The chip tray under it falls to the front and to a valley at the Ø50 drain (front
right). The program floods while it cuts a closed pocket (60 x 70 x 10 mm with the tool) and an open slot that runs
out at the block's +x side, lifts the tool over the pocket, floods on for a moment, M9, waits.
Detail Draft (4 mm cells on the table, 10 mm in the tray), no helpers: quick and the same as with helpers (task 0255).
"""

import os

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
mf = pytest.importorskip("manifold3d")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import animation, build, chips, coolant, gcode, liquid, machining  # noqa: E402
from fresing_render.core import liquid as lcore  # noqa: E402

HERE = os.path.dirname(__file__)
MILL = os.path.join(HERE, "data", "test_mill.step")
OLD = os.path.join(HERE, "data", "old_project_0_2_195.blend")
STOCK = "STOCK 200x200x40"
TOOL = "END MILL D10"
MM = 0.001


PROGRAM = liquid.TEST_PROGRAM


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def ob(sc, name):
    return next(o for o in sc.objects if o.get(build.PROP_NAME) == name)


def click(o):
    for x in bpy.context.selected_objects:
        x.select_set(False)
    o.select_set(True)
    bpy.context.view_layer.objects.active = o


def make_scene(tmp, liquid_on=True, text=PROGRAM, fit=16.0):
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
    a, r = liquid.set_up_test_model(sc, str(tmp), text, fit)
    sc.fresing.coolant.liquid_on = liquid_on
    assert not r["warnings"], r["warnings"]
    sc["fr_test_frames"] = r["frames"]
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(str(tmp), "liquid.blend"))   # the bake goes next to it
    sc = bpy.context.scene
    return sc, a


@pytest.fixture(scope="module")
def baked(addon, tmp_path_factory):
    tmp = tmp_path_factory.mktemp("liquid")
    sc, a = make_scene(tmp)
    assert liquid.problem(sc) == ""
    info = liquid.bake_now(sc, helpers=0)
    assert info and info["frames"] == sc.frame_end - sc.frame_start + 1
    return sc, info


def _reader(sc):
    rd, beds = liquid._open(sc)
    assert rd is not None, "no bake for the project as it is"
    return rd, beds


def _flood_end(sc):
    sp = coolant.spans()
    return float(sp[-1, 1])


def test_off_by_default_and_old_projects_stay_off(addon, tmp_path):
    """A new project and a project of an older version: the tick is off, Build makes nothing of the liquid."""
    sc, a = make_scene(tmp_path, liquid_on=False)
    frames = sc["fr_test_frames"]
    assert liquid.problem(sc) == "" and not liquid.wanted(sc)
    assert liquid.bake_now(sc) is None
    sc.frame_set(40)
    assert not liquid.objects()
    assert not os.path.exists(liquid.cache_path(sc))
    sc.fresing.coolant.liquid_on = True               # ticked and off again: the same Build, nothing left
    sc.fresing.coolant.liquid_on = False
    assert animation.bake(sc, a)["frames"] == frames
    assert not liquid.objects()
    # an old project (0.2.195): opens with the tick off and nothing of the liquid
    bpy.ops.wm.open_mainfile(filepath=OLD, load_ui=False)
    sc = bpy.context.scene
    assert sc.fresing.coolant.liquid_on is False
    assert sc.fresing.coolant.liquid_detail == "NORMAL"
    for an in sc.fresing.animations:
        animation.bake(sc, an)
        break
    sc.frame_set(sc.frame_start + 5)
    assert not liquid.objects()


def test_the_charts_come_from_the_machine(baked):
    sc, _info = baked
    st = liquid.gather(sc)
    assert st.roles == ["table", "tray"]
    table, tray = st.charts
    assert table.cell == pytest.approx(4 * MM) and tray.cell == pytest.approx(10 * MM)
    # the table chart: the table's top at z 30 mm with T-slots below it, the block's top at 70 mm
    b = table.bed[np.isfinite(table.bed)]
    assert np.isclose(b, 0.030, atol=1e-4).mean() > 0.3
    assert (b < 0.020).sum() > 200                         # the T-slots
    assert b.max() == pytest.approx(0.060, abs=1e-4)          # the bolts' heads (the block is read per frame)
    rd, beds = _reader(sc)
    assert np.nanmax(beds.at(0, rd.frames[0])) == pytest.approx(0.070, abs=1e-4)
    # the tray: falls to the drain, the drain's cells are orifices at its lowest point
    assert st.drain_cells > 5
    drain = tray.drain > 0
    assert tray.bed[drain].max() < np.nanmin(tray.bed[(tray.bed > -0.6) & ~drain])
    # the table moves (the program moves X and Y), the tray stands still
    assert np.abs(st.mats[0][:, :3, 3] - st.mats[0][0, :3, 3]).max() > 0.02
    assert np.abs(st.mats[1] - np.eye(4)).max() == 0.0


def test_the_pocket_fills_and_holds(baked):
    """The closed pocket fills while the flood pours into it (full, spilling over its rim), and after M9 it holds
    its liquid to the end (± 2 %). (The heap over its rim runs off when the flood stops and the pocket sloshes for a
    while: it keeps 80 … 100 % of what it holds.)"""
    sc, _info = baked
    rd, beds = _reader(sc)
    cell, x0, y0 = beds.geom[0]
    f1 = rd.frames[-1]
    bed = beds.at(0, f1)
    top = 0.070
    X, Y = np.meshgrid(x0 + np.arange(bed.shape[1]) * cell, y0 + np.arange(bed.shape[0]) * cell)
    on_block = (np.abs(X) < 0.095) & (np.abs(Y) < 0.095)        # (the bolts' heads stand 10 mm under its top too)
    pocket = on_block & np.isfinite(bed) & (bed < top - 0.008) & (bed > top - 0.0125)
    capacity = float(np.where(pocket, top - bed, 0.0).sum()) * cell * cell
    assert capacity == pytest.approx(60e-3 * 66e-3 * 10e-3, rel=0.15)        # 60 x 66 x 10 mm (the tool's path)

    def held(f):
        return float(np.where(pocket, rd.read(f)[0][0], 0.0).sum()) * cell * cell

    m9 = int(round(_flood_end(sc)))
    during = max(held(f) for f in range(m9 - 24, m9))
    assert during >= capacity, (during, capacity)                 # full and spilling over
    after, end = held(m9 + 24), held(f1)
    assert end == pytest.approx(after, rel=0.02), (after, end)
    assert 0.8 * capacity <= end <= 1.0 * capacity + 1e-9, (end, capacity)


def test_liquid_leaves_the_table_and_reaches_the_tray_and_the_drain(baked):
    sc, info = baked
    rd, beds = _reader(sc)
    _d, _p, _v, tot = rd.read(rd.frames[-1])
    on_tray = float(rd.read(rd.frames[-1])[0][1].sum()) * beds.geom[1][0] ** 2 * 1e3
    assert on_tray > 0.05, f"only {on_tray:.3f} l in the tray"
    assert tot["drained"] > 0.0
    # the liquid in the tray lies beyond the table's ends too (it ran off along the T-slots), not only under it
    cell, x0, y0 = beds.geom[1]
    d = rd.read(rd.frames[-1])[0][1]
    js, is_ = np.nonzero(d > liquid.SHOW)
    xs = x0 + is_ * cell
    assert (np.abs(xs) > 0.62).any(), "no liquid in the tray beyond the table's ends"
    # bookkeeping: everything poured is somewhere
    assert tot["poured"] == pytest.approx(tot["on_charts"] + tot["in_flight"] + tot["drained"] + tot["floor"],
                                          abs=1e-6)
    assert tot["poured"] == pytest.approx(liquid.rate(sc) * (_flood_end(sc) - coolant.spans()[0, 0]) / 24.0 / 60.0,
                                          rel=0.05)


def test_the_tray_empties_down_the_drain(baked):
    """The VMC's own tray: a 20 s flood (the program's 14 l/min) falling off the table's two ends is 95 % down the
    drain within 30 s after it stops (a thin film stays and creeps on)."""
    sc, _info = baked
    st = liquid.gather(sc)
    tray = st.charts[1]
    fps = 24
    flood, after = 20 * fps, 30 * fps
    sim = lcore.Liquid([tray], [lcore.still(flood + after + 1)], fps, st.floor_z)
    for k in range(flood + after):
        pours = [lcore.Pour((x, 0.05), 7.0, chart=0) for x in (-0.75, 0.75)] if k < flood else None
        t = sim.step(k, pours).totals
    assert t["poured"] == pytest.approx(14.0 * 20 / 60, rel=1e-6)
    assert t["drained"] >= 0.95 * t["poured"], t
    assert t["floor"] < 1e-9


def test_same_frame_same_liquid(baked):
    sc, _info = baked
    f = int(round(_flood_end(sc))) - 10

    def drawn(before):
        sc.frame_set(before)
        sc.frame_set(f)
        out = []
        for name in (liquid.OBJ_TABLE, liquid.OBJ_TRAY, liquid.OBJ_DROPS):
            me = bpy.data.objects[name].data
            co = np.empty(len(me.vertices) * 3, np.float32)
            me.vertices.foreach_get("co", co)
            out.append(co)
        return out

    a = drawn(sc.frame_start)
    b = drawn(sc.frame_end)
    assert len(a[0]) > 300 and len(a[1]) > 0
    for x, y in zip(a, b):
        assert np.array_equal(x, y)
    # the sheet on the table rides with the block, the material has a Cycles and an EEVEE output
    assert bpy.data.objects[liquid.OBJ_TABLE].constraints[0].target == machining.workpiece(sc)
    mat = bpy.data.materials[liquid.MAT]
    targets = sorted(n.target for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeOutputMaterial")
    assert targets == ["CYCLES", "EEVEE"]


def test_eevee_looks_and_the_cache_is_reused(baked):
    sc, _info = baked
    s = sc.fresing.coolant
    for look, method in (("CLEAR", "DITHERED"), ("BLENDED", "BLENDED"), ("MILKY", "DITHERED")):
        s.liquid_eevee = look
        mat = liquid.material(sc)
        assert mat.surface_render_method == method
        assert mat.use_raytrace_refraction == (look == "CLEAR")
    assert liquid.is_baked(sc)                            # a look is no reason to work it out again
    before = os.path.getmtime(liquid.runtime(sc)["path"])
    liquid.forget()
    info = liquid.bake_now(sc)
    assert info is not None and os.path.getmtime(liquid.runtime(sc)["path"]) == before
    # a changed flow is a new bake
    s.flow = 0.5
    assert not liquid.is_baked(sc)
    s.flow = 0.7
    assert liquid.is_baked(sc)


def test_beds_round_trip(tmp_path):
    base = [np.arange(12, dtype=float).reshape(3, 4), np.full((2, 2), np.nan)]
    ch = [(5, 0, 1, 1, np.array([[100.0, 101.0]])), (9, 0, 0, 0, np.array([[7.0]]))]
    b = liquid.Beds(base, ch, "fp", [(0.002, 0.1, 0.2), (0.005, 0.0, 0.0)])
    p = str(tmp_path / "x.npz")
    b.save(p)
    c = liquid.Beds.load(p, "fp")
    assert liquid.Beds.load(p, "other") is None
    assert c.at(0, 4)[1, 1] == 5.0
    assert c.at(0, 6)[1, 1] == 100.0 and c.at(0, 6)[0, 0] == 0.0
    assert c.at(0, 9)[0, 0] == 7.0
    assert c.at(0, 3)[0, 0] == 0.0                        # going back starts again from the first bed
    assert np.isnan(c.at(1, 9)).all()
    assert c.geom[0] == pytest.approx((0.002, 0.1, 0.2))


def test_sheet_mesh():
    d = np.zeros((3, 3))
    d[1, 1] = 2e-3
    d[1, 2] = 1e-3
    bed = np.zeros((3, 3))
    v, q = liquid.sheet(d, bed, 0.01, 0.0, 0.0)
    assert q.shape == (2, 4) and len(v) == 6
    assert v[:, 2].max() == pytest.approx(2e-3 + liquid.LIFT, abs=1e-6)
    v, q = liquid.sheet(np.full((2, 2), 0.05e-3), bed[:2, :2], 0.01, 0.0, 0.0)
    assert len(q) == 0                                    # a film shows as the wet sheen, not as a sheet
