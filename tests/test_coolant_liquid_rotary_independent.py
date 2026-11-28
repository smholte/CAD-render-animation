"""Task 0347, independent tests of the coolant liquid on the 4th axis and the trunnion (written from the brief by an agent
that did not write liquid.py). Draft detail, no helpers (except the one test that compares them)."""

import os

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
pytest.importorskip("manifold3d")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import animation, chips, coolant, gcode, joints, liquid, machining  # noqa: E402

HERE = os.path.dirname(__file__)
KEEP = {}


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    machining._RUNTIME.clear()
    chips.forget()
    liquid.forget()
    gcode._CACHE.clear()
    gcode._INFO.clear()


def make(tmp, five, text=None, bake=True, rotate_z=0.0, name="liquid.blend"):
    reset()
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp)
    model = os.path.join(HERE, "data", "test_5axis.step" if five else "test_4axis.step")
    assert bpy.ops.fresing.import_step(filepath=model, quality="draft") == {"FINISHED"}
    if rotate_z:
        import math
        for ob in bpy.data.objects:
            if ob.parent is None and ob.type == "EMPTY":
                ob.rotation_euler[2] = math.radians(rotate_z)
        bpy.context.view_layer.update()
    _a, r = liquid.set_up_test_rotary(sc, str(tmp), five=five, text=text)
    assert not r["warnings"], r["warnings"]
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(str(tmp), name))
    sc = bpy.context.scene
    info = None
    if bake:
        assert liquid.problem(sc) == ""
        info = liquid.bake_now(sc, helpers=0)
        assert info is not None
    return sc, info


def spans(sc):
    return liquid._open(sc)


def check_books(sc, step=5):
    rd, _b = liquid._open(sc)
    assert rd is not None
    fr = [int(f) for f in rd.frames]
    worst = 0.0
    for f in fr[::step] + [fr[-1]]:
        d, drops, vols, t = rd.read(f)
        # volumes drawn in the cache must match its own totals bookkeeping
        lhs = t["poured"]
        rhs = t["on_charts"] + t["in_flight"] + t["drained"] + t["floor"]
        worst = max(worst, abs(lhs - rhs))
        assert all(np.isfinite(x).all() and (x >= 0).all() for x in d), f
        assert np.isfinite(drops).all(), f
        assert abs(float(np.sum(vols)) - t["in_flight"]) < 1e-6 + 1e-3 * t["in_flight"], (f, vols.sum(), t["in_flight"])
    assert worst < 1e-9, worst
    return fr


def verts(name):
    ob = bpy.data.objects[name]
    co = np.empty(len(ob.data.vertices) * 3, np.float64)
    ob.data.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    W = np.array(ob.matrix_world)
    return co @ W[:3, :3].T + W[:3, 3], co


def snapshot():
    out = {}
    for ob in liquid.objects():
        w, co = verts(ob.name)
        out[ob.name] = (co.copy(), w.copy())
    return out


def same(a, b, tol=1e-9):
    assert a.keys() == b.keys()
    for k in a:
        assert a[k][0].shape == b[k][0].shape, k
        if len(a[k][0]):
            assert np.abs(a[k][0] - b[k][0]).max() <= tol, k
            assert np.abs(a[k][1] - b[k][1]).max() <= 1e-6, k


def a_deg(sc):
    import math
    return round(math.degrees(joints.get_value(sc.fresing.joints['Rotary A'])), 1)


def vols_per_chart(sc):
    rd, beds = liquid._open(sc)
    fr = np.array([int(f) for f in rd.frames])
    v = np.array([[float(d.sum()) * g[0] ** 2 * 1e6 for d, g in zip(rd.read(int(f))[0], beds.geom)] for f in fr])
    return fr, v


@pytest.fixture(scope="module")
def four(addon, tmp_path_factory):
    tmp = tmp_path_factory.mktemp("ind4")
    KEEP["four"] = tmp
    return make(tmp, False)


@pytest.fixture(scope="module")
def five(addon, tmp_path_factory):
    tmp = tmp_path_factory.mktemp("ind5")
    KEEP["five"] = tmp
    return make(tmp, True)


# ---- 4th axis (the order matters: the module scene is the 4th axis until test_reopen) -------------------------------

def test_4_bookkeeping_exact(four):
    sc, info = four
    check_books(sc)
    assert info["totals"]["poured"] > 1.0


def test_4_same_frame_twice_and_from_another_frame(four):
    sc, _ = four
    fr, v = vols_per_chart(sc)
    sc.frame_set(int(fr[len(fr) // 3]))
    f = int(fr[int(np.argmax(v[:, :4].sum(axis=1)))])
    sc.frame_set(f)
    a = snapshot()
    assert any(len(x[0]) for x in a.values())
    sc.frame_set(f)
    same(a, snapshot(), 0.0)
    for other in (int(fr[-1]), int(fr[0]), f + 17, f):
        sc.frame_set(other)
    same(a, snapshot(), 0.0)
    # jumping back and forth through the beds (changes are applied incrementally): a late frame before and after
    late = int(fr[-3])
    sc.frame_set(late)
    b = snapshot()
    sc.frame_set(int(fr[1]))
    sc.frame_set(late)
    same(b, snapshot(), 0.0)


def test_4_x_table_sheet_sits_on_the_table_wherever_the_table_is(four):
    """The X-table chart ("carrier 1") rides on the X table: at frames spread over the program, the table at a
    different X each time, every sampled sheet point has a real surface 18 .. 70 mm below it (ray from 20 mm above the
    point straight down, liquid and tool hidden)."""
    import mathutils
    sc, _ = four
    st = liquid.gather(sc)
    c = st.roles.index("carrier 1")
    rd, beds = liquid._open(sc)
    table = bpy.data.objects[beds.follow[c]]
    fr, v = vols_per_chart(sc)
    wet = [int(f) for f, x in zip(fr, v[:, c]) if x > 0.5]
    assert len(wet) > 20
    tool_like = {ob.name for _it, ob in machining.bits(sc)}
    for ob in liquid.objects():
        ob.hide_viewport = True
    xs, bad = set(), []
    try:
        for f in wet[:: max(1, len(wet) // 10)]:
            sc.frame_set(f)
            xs.add(round(float(np.array(table.matrix_world)[0, 3]), 3))
            for ob in liquid.objects():
                ob.hide_viewport = False
            w, _co = verts(liquid.chart_object("carrier 1"))
            for ob in liquid.objects():
                ob.hide_viewport = True
            bpy.context.view_layer.update()
            dg = bpy.context.evaluated_depsgraph_get()
            idx = np.linspace(0, len(w) - 1, min(80, len(w))).astype(int)
            good = 0
            for i in idx:
                hit, loc, _n, _fi, hob, _m = sc.ray_cast(dg, mathutils.Vector((w[i, 0], w[i, 1], w[i, 2] + 0.02)),
                                                         mathutils.Vector((0, 0, -1)))
                dist = (w[i, 2] + 0.02) - loc.z if hit else 9.9
                good += 0.018 <= dist <= 0.07
            if good < 0.8 * len(idx):
                bad.append((f, good, len(idx)))
    finally:
        for ob in liquid.objects():
            ob.hide_viewport = False
    assert len(xs) >= 3, ("the X table hardly moves over the wet frames", xs)
    assert not bad, bad


def test_4_bar_sheets_stay_in_a_skin_round_the_bar(four):
    """Every sheet point of a bar chart is, in the world at its frame, outside the bar (radius 25 mm from the A axis,
    minus the cut) and not more than 20 mm above it: the liquid cannot float 28 mm off the bar or lie inside it."""
    sc, _ = four
    st = liquid.gather(sc)
    fr, v = vols_per_chart(sc)
    o, u = st.bar
    bad_out, bad_in, seen = [], [], 0
    for c in range(4):
        wet = [int(f) for f, x in zip(fr, v[:, c]) if x > 0.5]
        for f in wet[:: max(1, len(wet) // 14)]:
            sc.frame_set(f)
            w, _co = verts(liquid.chart_object(f"bar {c + 1}"))
            M = st.carry[f - st.f0]
            ow, uw = M[:3, :3] @ o + M[:3, 3], M[:3, :3] @ u
            rel = w - ow
            r = np.linalg.norm(rel - (rel @ uw)[:, None] * uw[None], axis=1)
            seen += 1
            if r.max() > 0.045:
                bad_out.append((f"bar {c + 1}", f, a_deg(sc), round(float(r.max()) * 1000, 1)))
            if r.min() < 0.020:
                bad_in.append((f"bar {c + 1}", f, a_deg(sc), round(float(r.min()) * 1000, 1)))
    assert seen >= 20
    assert not bad_out, ("liquid floating more than 20 mm off the bar", bad_out)
    assert not bad_in, ("liquid drawn inside the bar", bad_in)


def test_4_helpers_and_frame_shown_do_not_change_the_bake(four):
    """The fixture's bake (helpers=0, first frame shown) against one worked out with helpers=2 while a frame in the
    middle is shown: the same depths bit for bit (a combined check: one bake saves a minute)."""
    sc, _ = four
    rd, _b = liquid._open(sc)
    fr = [int(f) for f in rd.frames]
    pick = fr[::9] + [fr[-1]]
    ref = {f: [d.copy() for d in rd.read(f)[0]] for f in pick}
    tot = rd.read(fr[-1])[3]
    sc.frame_set(int(sc.frame_start) + 70)
    liquid.forget()
    for _p in liquid.steps(sc, [], helpers=2):
        pass
    liquid.forget()
    rd, _b = liquid._open(sc)
    for f in pick:
        for a, b in zip(ref[f], rd.read(f)[0]):
            assert np.array_equal(a, b), (f, float(np.abs(a - b).max()), int((a != b).sum()))
    assert rd.read(fr[-1])[3]["drained"] == pytest.approx(tot["drained"], rel=1e-9, abs=1e-12)
    sc.frame_set(int(sc.frame_start))


def test_4_reopen_draws_the_same_and_follows_the_right_objects(four):
    sc, _ = four
    fr, v = vols_per_chart(sc)
    f = int(fr[int(np.argmax(v[:, :4].sum(axis=1)))])
    sc.frame_set(f)
    liquid.show(sc)
    a = snapshot()
    rd, beds = liquid._open(sc)
    want = {liquid.chart_object(n): fol for n, fol in zip(rd.names, beds.follow)}
    follow_before = {}
    for ob in liquid.objects():
        con = ob.constraints.get("Follow the workpiece")
        follow_before[ob.name] = con.target.name if con is not None and con.target else ""
    bpy.ops.wm.save_as_mainfile(filepath=str(KEEP["four"] / "liquid2.blend"))
    bpy.ops.wm.open_mainfile(filepath=str(KEEP["four"] / "liquid2.blend"), load_ui=False)
    sc = bpy.context.scene
    assert liquid.is_baked(sc)
    assert liquid.bake_now(sc) is not None
    sc.frame_set(f)
    liquid.show(sc)
    same(a, snapshot(), 1e-6)
    for ob in liquid.objects():
        con = ob.constraints.get("Follow the workpiece")
        tgt = con.target.name if con is not None and con.target else ""
        assert tgt == follow_before[ob.name], (ob.name, tgt, follow_before[ob.name])
    wp = machining.workpiece(sc)
    for nm, fol in want.items():
        con = bpy.data.objects[nm].constraints.get("Follow the workpiece")
        exp = wp.name if fol == "@workpiece" else fol
        assert (con.target.name if con is not None and con.target else "") == exp, (nm, fol)


# ---- trunnion -------------------------------------------------------------------------------------------------------

def test_5_bookkeeping_exact(five):
    sc, info = five
    check_books(sc)


def test_5_same_frame_twice(five):
    sc, _ = five
    fr, v = vols_per_chart(sc)
    f = int(fr[int(np.argmax(v[:, :3].sum(axis=1)))])
    sc.frame_set(f)
    a = snapshot()
    sc.frame_set(int(fr[-1]))
    sc.frame_set(int(fr[2]))
    sc.frame_set(f)
    same(a, snapshot(), 0.0)


def test_5_table_sheet_tilts_with_the_cradle(five):
    """The C-table chart's liquid lies on the table top: its plane's normal turns with the cradle's tilt A."""
    sc, _ = five
    fr, v = vols_per_chart(sc)
    st = liquid.gather(sc)
    rows = []
    for k in range(len(fr)):
        if v[k, 0] > 1.0:
            sc.frame_set(int(fr[k]))
            a = joints.get_value(sc.fresing.joints["Trunnion A"])
            rows.append((int(fr[k]), a))
    assert len(rows) > 3, "the table never holds liquid"
    f_lo = min(rows, key=lambda r: r[1])
    f_hi = max(rows, key=lambda r: r[1])
    da = f_hi[1] - f_lo[1]
    assert abs(da) > 0.15, ("A is the same whenever the table is wet; cannot compare", rows[:3])

    def normal(f):
        sc.frame_set(f)
        w, _c = verts(liquid.chart_object("table"))
        # points on the liquid's top: fit a plane through the upper half
        w = w[w[:, 2] > np.percentile(w[:, 2], 0)]
        c = w - w.mean(axis=0)
        n = np.linalg.svd(c, full_matrices=False)[2][-1]
        return n * (1 if n[2] >= 0 else -1) if abs(n[2]) > 0.2 else n

    n1, n2 = normal(f_lo[0]), normal(f_hi[0])
    ang = float(np.arccos(np.clip(abs(float(np.dot(n1, n2))), -1, 1)))
    assert abs(ang - abs(da)) < np.radians(12), (np.degrees(ang), np.degrees(da))


def test_5_trunnion_sheet_over_the_rotary_table_top(five):
    """Where the C table's liquid is drawn in the world, it is close to the plane through the cradle-turned table."""
    sc, _ = five
    fr, v = vols_per_chart(sc)
    rd, beds = liquid._open(sc)
    k = int(np.argmax(v[:, 0]))
    f = int(fr[k])
    sc.frame_set(f)
    liquid.show(sc)
    w, _c = verts(liquid.chart_object("table"))
    assert len(w) > 20
    wp = machining.workpiece(sc)
    # the sheet lies over the workpiece (the block on the table): inside its world box, a little above
    bb = np.array([wp.matrix_world @ __import__("mathutils").Vector(c) for c in wp.bound_box])
    lo, hi = bb.min(axis=0) - 0.15, bb.max(axis=0) + 0.15
    assert (w >= lo - 1e-6).all() and (w <= hi + 1e-6).all(), (w.min(axis=0), w.max(axis=0), lo, hi)


# ---- special programs, damage, cancel -------------------------------------------------------------------------------

NO_TURN_4 = "\n".join([
    "%", "(T1 D=6 CR=0 - ZMIN=-3 - flat end mill)", "G21 G90 G94 G17 G54", "T1 M6", "S10000 M3", "G0 Z10",
    "G0 X-60 Y-4 A0", "M8", "G1 Z-2 F300", "G1 X-20 F600", "G1 Y4", "G1 X-60", "G0 Z10", "G4 P2", "M9", "G4 P2",
    "M5", "M30", "%"]) + "\n"

NO_TILT_5 = "\n".join([
    "%", "(T1 D=6 CR=0 - ZMIN=-3 - flat end mill)", "G21 G90 G94 G17 G54", "T1 M6", "S10000 M3", "G0 Z20", "M8",
    "G0 X-10 Y-10", "G1 Z-2 F300", "G1 X10 F600", "G1 Y10", "G1 X-10", "G0 Z40", "G4 P2", "M9", "G4 P2", "M5", "M30",
    "%"]) + "\n"


@pytest.mark.parametrize("five,text", [(False, NO_TURN_4), (True, NO_TILT_5)])
def test_program_without_the_rotary_axis_moving(addon, tmp_path, five, text):
    sc, info = make(tmp_path, five, text=text)
    fr = check_books(sc, step=3)
    st = liquid.gather(sc)
    assert st.roles[-1] == "tray" and len(set(st.roles)) == len(st.roles)
    for f in fr[::10]:
        sc.frame_set(f)
        for ob in liquid.objects():
            assert np.isfinite(verts(ob.name)[0]).all()


def test_old_project_without_chain_asks_for_build(addon, tmp_path):
    reset()
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path)
    assert bpy.ops.fresing.import_step(filepath=os.path.join(HERE, "data", "test_mill.step"), quality="draft") == {
        "FINISHED"}
    a, r = liquid.set_up_test_model(sc, str(tmp_path), liquid.TEST_PROGRAM, 16.0)
    m = machining.settings(sc)
    assert "fr_chain" in m, "3-axis Build must store fr_chain too"
    saved = str(m["fr_chain"])
    del m["fr_chain"]
    assert "Build" in liquid.problem(sc)
    assert not liquid.wanted(sc)
    assert liquid.bake_now(sc, helpers=0) is None
    liquid.prepare(sc)
    sc.frame_set(int(sc.frame_start) + 5)
    assert liquid.show(sc) is False
    assert not liquid.is_baked(sc)
    # Build again fixes it
    animation.bake(sc, a)
    machining.sample(sc)
    assert "fr_chain" in machining.settings(sc)
    assert liquid.problem(sc) == ""
    info = liquid.bake_now(sc, helpers=0)
    assert info is not None
    check_books(sc, step=7)
    assert saved is not None


def test_cancel_half_way_leaves_nothing_whole(addon, tmp_path):
    sc, _ = make(tmp_path, False, bake=False)
    path = liquid.cache_path(sc)
    assert not os.path.exists(path)
    gen = liquid.steps(sc, [], helpers=0)
    p = 0.0
    for p in gen:
        if p > 0.4:
            break
    assert 0.4 < p < 1.0
    gen.close()
    liquid.forget()
    assert liquid._open(sc) == (None, None)
    assert not os.path.exists(path + ".beds.npz")
    assert not liquid.is_baked(sc)
