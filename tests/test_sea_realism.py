"""Task 0229, stand-in (study 0226): the two public checks of the demo's realism file
(``tests/test_demo_project_realism.py``: the cable weighs 38 kg/m and its tensions follow; the "Lay data" label shows
its numbers inside the picture) done on the public sea cable test model (tests/data/test_sea.step,
``paths_sea.set_up_test_model``: 15 m of water, layback 20 m, the cable paying out at 60 m/min for 8 s).

- a cable of 38 kg/m in water (typed, and the same from a Ø 200 mm power cable) hangs from the horn: its bottom and
  top tension, departure angle and hanging length are the touching-down catenary's in plain numbers (H = a w g,
  T = (a + h) w g, X = a acosh(1 + h/a), s = sqrt(h² + 2 a h), tan θ = s / a), worked out here by a bisection of our
  own from the layback and the height; the drawn line follows that catenary; the tensions scale with the weight and
  the shape does not;
- a 7-line "Lay data" label pointing at the touch-down, tied to the pay-out step, shows the cable's numbers at every
  second of the step and its box lies inside the picture at HD and at 4K (and is not the whole picture).
"""

import math
import os

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from mathutils import Matrix  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.join(HERE, "data", "test_sea.step")

import fresing_render  # noqa: E402
from fresing_render.blender import animation, callouts, paths, paths_sea  # noqa: E402

G = 9.81                        # m/s²
WEIGHT = 38.0                   # kg/m in water (a heavy, lead-sheathed Ø 200 mm power cable; study 0152)
STEP = "Surface lay"
LAY_DATA = ("Lay data\\nTop tension {top} kN\\nBottom tension {bottom} kN\\nLayback {layback} m\\n"
            "Departure angle {angle}°\\nLay speed {speed} m/min\\nWater depth {depth} m")


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def update(times=2):
    for _ in range(times):
        bpy.context.view_layer.update()


def cable(sc):
    return paths.find(sc, paths_sea.TEST_CABLE)


@pytest.fixture(scope="module")
def sea(tmp_path_factory):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    paths.forget()
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path_factory.mktemp("sea_realism"))
    assert bpy.ops.fresing.import_step(filepath=MODEL, quality="draft") == {"FINISHED"}
    made = paths_sea.set_up_test_model(sc)
    assert made["cable"] == paths_sea.TEST_CABLE
    return sc


def resolve(sc):
    update()
    paths.refresh(sc)
    update()
    return cable(sc)


# ---------------------------------------------------------------------------
# the touching-down catenary in plain numbers (not the app's code)
# ---------------------------------------------------------------------------

def a_for(X: float, h: float) -> float:
    """The catenary parameter a whose touching-down catenary reaches X flat over the height h: a acosh(1 + h/a) = X,
    by bisection on a (the reach grows with a)."""
    lo, hi = 1e-6, 1e6
    for _ in range(200):
        a = math.sqrt(lo * hi)
        if a * math.acosh(1.0 + h / a) < X:
            lo = a
        else:
            hi = a
    return math.sqrt(lo * hi)


def by_hand(X: float, h: float, w: float) -> dict:
    a = a_for(X, h)
    s = math.sqrt(h * h + 2.0 * a * h)
    return {"a": a, "bottom": a * w * G / 1000.0, "top": (a + h) * w * G / 1000.0, "hanging": s,
            "angle": math.degrees(math.atan2(s, a))}


def test_the_cable_weighs_38_kg_per_m_and_its_tensions_follow(sea):
    sc = sea
    it = cable(sc)
    it.sea_weight = WEIGHT                          # (as typed in the panel: its update solves again)
    it = resolve(sc)
    n = paths_sea.numbers(sc, it)
    assert n["weight"] == pytest.approx(WEIGHT)
    assert n["kind"] == 0 and n["depth"] == pytest.approx(15.0)
    assert n["layback"] == pytest.approx(20.0, abs=0.05)                # the layback as set
    h = n["height"]
    assert 15.0 < h < 20.0, h                                           # 15 m of water + the horn above it
    want = by_hand(n["layback"], h, WEIGHT)
    assert n["a"] == pytest.approx(want["a"], rel=1e-4)
    assert n["bottom"] == pytest.approx(want["bottom"], rel=1e-4)
    assert n["top"] == pytest.approx(want["top"], rel=1e-4)
    assert n["hanging"] == pytest.approx(want["hanging"], rel=1e-4)
    assert n["angle"] == pytest.approx(want["angle"], abs=0.05)
    # in numbers: about 5.2 and 11.5 kN at 38 kg/m, 15 m of water and a 20 m layback; leaving at about 63°
    assert 4.7 < n["bottom"] < 5.7 and 10.5 < n["top"] < 12.5 and 58.0 < n["angle"] < 68.0, n

    # the drawn line is that catenary: z = a (cosh(x/a) - 1) over the touch-down, x flat from it
    inv = np.linalg.inv(np.array(paths_sea.bed(sc).matrix_world))
    T, tdp = paths_sea.tdp_world(sc, it)
    to_bed = lambda p: inv[:3, :3] @ np.asarray(p, dtype=float) + inv[:3, 3]    # noqa: E731
    T, tdp = to_bed(T), to_bed(tdp)
    assert math.hypot(*(T - tdp)[:2]) == pytest.approx(n["layback"], abs=0.02)
    assert T[2] - tdp[2] == pytest.approx(h, abs=0.02)
    line = np.array([to_bed(p) for p in paths.shape_now(sc, it)])
    x = np.hypot(line[:, 0] - tdp[0], line[:, 1] - tdp[1])
    way = (T - tdp)[:2] / np.linalg.norm((T - tdp)[:2])
    hanging = ((line[:, :2] - tdp[:2]) @ way > 0.5) & (x < n["layback"] - 0.5) & (line[:, 2] > tdp[2] + 0.05)
    assert hanging.sum() > 10, hanging.sum()
    z = tdp[2] + want["a"] * (np.cosh(x[hanging] / want["a"]) - 1.0)
    assert np.abs(line[hanging, 2] - z).max() < 0.05, np.abs(line[hanging, 2] - z).max()

    # the tensions follow the weight, the shape does not; 38 kg/m is also what a Ø 200 mm power cable weighs
    it.sea_weight = WEIGHT / 2.0
    half = paths_sea.numbers(sc, resolve(sc))
    assert half["bottom"] == pytest.approx(n["bottom"] / 2.0, rel=1e-6)
    assert half["top"] == pytest.approx(n["top"] / 2.0, rel=1e-6)
    assert half["layback"] == pytest.approx(n["layback"], abs=1e-6) and half["a"] == pytest.approx(n["a"], rel=1e-6)
    it = cable(sc)
    it.sea_weight = 0.0                             # (from the diameter)
    it = cable(sc)
    it.diameter = 0.2
    it = resolve(sc)
    assert paths_sea.weight(it) == pytest.approx(WEIGHT)
    assert paths_sea.numbers(sc, it)["bottom"] == pytest.approx(
        by_hand(paths_sea.numbers(sc, it)["layback"], paths_sea.numbers(sc, it)["height"], WEIGHT)["bottom"], rel=1e-4)


def test_lay_data_shows_the_numbers_inside_the_picture(sea):
    sc = sea
    it = cable(sc)
    it.sea_weight = WEIGHT                          # (as typed in the panel: its update solves again)
    it = resolve(sc)
    a = sc.fresing.animations[paths_sea.TEST_ANIMATION]
    blk = next(b for b in a.blocks if b.joint == it.joint)
    blk.name = STEP
    # a camera as the test tour has it, the label on the cable pointing at its touch-down, tied to the pay-out step
    cam = bpy.data.objects.new("Lay camera", bpy.data.cameras.new("Lay camera"))
    sc.collection.objects.link(cam)
    cam.data.lens = 30.0
    cam.matrix_world = Matrix(paths_sea.view_matrix(sc, it))
    sc.camera = cam
    T, tdp = paths_sea.tdp_world(sc, it)
    c = callouts.add(sc, it.part, tdp, LAY_DATA, step=STEP)
    sc.fresing.callouts_on = True
    r = animation.bake(sc, a)
    assert not [w for w in r["warnings"] if "cable" in w.lower()], r["warnings"]
    w = callouts.window_for(a, c)
    assert w is not None and w[1] - w[0] >= 7.5, w
    fps = int(a.fps)
    boxes = callouts.PartBoxes(sc)
    speeds, checked = set(), 0
    for f in range(int(w[0] * fps) + 3, int(w[1] * fps) - 2, 25):
        sc.frame_set(f + 1)
        it = cable(sc)
        n = paths_sea.numbers(sc, it)
        rows = callouts.label_text(sc, c).split("\n")
        assert rows[0] == "Lay data" and len(rows) == 7, rows
        assert rows[1] == f"Top tension {n['top']:.1f} kN" and rows[2] == f"Bottom tension {n['bottom']:.1f} kN"
        assert rows[3] == f"Layback {n['layback']:.1f} m" and rows[4] == f"Departure angle {n['angle']:.0f}°"
        assert rows[6] == "Water depth 15 m"
        assert "–" not in "".join(rows), rows                     # every field has its number
        speeds.add(rows[5])
        for size in ((1920, 1080), (3840, 2160)):
            d = [x for x in callouts.draws_at(sc, size, f / fps, a, "", boxes) if x.text.startswith("Lay data")]
            assert len(d) == 1, (size, f)
            assert d[0].box.inside(size[0], size[1], 0.0), (size, f, d[0].box)
            assert d[0].box.h < 0.45 * size[1]                     # (readable, not the whole picture)
        checked += 1
    assert checked >= 7
    assert speeds == {f"Lay speed {blk.speed_mmin:.1f} m/min"}, speeds    # it pays out at 60 m/min all through
