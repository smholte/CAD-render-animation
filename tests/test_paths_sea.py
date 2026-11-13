"""Task 0081: a cable into the sea and things riding on it, in Blender (as a Python module; one check in the real
Blender with scripts off). Model: tests/data/test_sea.step (tools/make_test_sea.py), set up by
``paths_sea.set_up_test_model``: 15 m of water, layback 20 m, the CPS set passing the horn at 1 m paid out, the
cable paying out at 60 m/min for 8 s.
"""

import json
import math
import os
import subprocess
import sys

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
MODEL = os.path.join(HERE, "data", "test_sea.step")

import fresing_render  # noqa: E402
import make_test_sea as maker  # noqa: E402
from fresing_render.blender import (animation, build, cable_looks, clash, joints, paths, paths_riders,  # noqa: E402
                                    paths_sea)
from fresing_render.core import catenary as C  # noqa: E402

N = maker.NUMBERS
MM = 0.001


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture(scope="module")
def folder(tmp_path_factory):
    return str(tmp_path_factory.mktemp("sea"))


def load(folder):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    paths.forget()
    sc = bpy.context.scene
    sc.fresing.out_folder = folder
    assert bpy.ops.fresing.import_step(filepath=MODEL, quality="draft") == {"FINISHED"}
    return sc


@pytest.fixture()
def sea(folder):
    sc = load(folder)
    made = paths_sea.set_up_test_model(sc)
    assert made["cable"] == paths_sea.TEST_CABLE and made["rider"] == paths_sea.TEST_RIDER
    return sc


def update(times=2):
    for _ in range(times):
        bpy.context.view_layer.update()


def cable(sc):
    return paths.find(sc, paths_sea.TEST_CABLE)


def named(sc, name, k=0):
    return [o for o in sc.objects if o.get(build.PROP_NAME) == name][k]


def seg_dist(points, line):
    """Distance of each point to the polyline."""
    a, b = line[:-1], line[1:]
    ab = b - a
    out = []
    for p in points:
        t = np.clip(((p - a) * ab).sum(1) / np.maximum((ab * ab).sum(1), 1e-18), 0.0, 1.0)
        out.append(np.linalg.norm(a + ab * t[:, None] - p, axis=1).min())
    return np.array(out)


def mark_at(sc, it, p):
    """The cable's mark (metres along it, nothing paid out) at the world point p: s of the nearest point of the
    drawn line minus what is paid out."""
    line = paths.shape_now(sc, it)
    got = paths._arrays(sc, it)
    s = got[1][paths._moment_now(sc, it)].astype(float)
    a, b = line[:-1], line[1:]
    ab = b - a
    t = np.clip(((p - a) * ab).sum(1) / np.maximum((ab * ab).sum(1), 1e-18), 0.0, 1.0)
    d = np.linalg.norm(a + ab * t[:, None] - p, axis=1)
    k = int(np.argmin(d))
    return s[k] + t[k] * (s[k + 1] - s[k]) - paths_sea.payout(sc, it)


def test_sea_end_hangs_from_the_horn(sea):
    sc = sea
    it = cable(sc)
    assert it.b_kind == "SEA" and it.problem == "" and [c.name for c in it.contacts][-1] == "HORN"
    n = paths_sea.numbers(sc, it)
    assert n["layback"] == pytest.approx(20.0, abs=1e-4) and n["laid"] == pytest.approx(40.0, abs=1e-4)
    assert n["kind"] == C.NORMAL and 45.0 < n["angle"] < 80.0
    assert n["top"] - n["bottom"] == pytest.approx(paths_sea.weight(it) * C.G * n["height"] / 1000.0, rel=1e-6)
    line = paths.shape_now(sc, it)
    end = line[-1]
    assert end[2] == pytest.approx(-15.0 + (0.5 - paths_sea.SINK) * 0.12, abs=1e-4)      # on the seabed
    assert np.linalg.norm(np.diff(line, axis=0), axis=1).min() > 1e-6                    # no two points alike
    # the cable leaves the horn on its tangent: no kink where the arc ends and the catenary starts
    seg = np.diff(line, axis=0)
    seg /= np.linalg.norm(seg, axis=1)[:, None]
    hang = line[:, 2] < 1.2 + 2.0                                                        # below the horn's top
    k = int(np.argmax(hang[1:] & (line[1:, 0] < N["horn_centre"][0] / 1000.0)))
    turns = np.degrees(np.arccos(np.clip((seg[1:] * seg[:-1]).sum(1), -1, 1)))
    assert turns[max(k - 40, 0):k + 40].max() < 2.0                                       # (arc steps are ~1.4°)
    # Into the sea needs a contact to hang from; it refuses without one, says so and changes nothing
    it2 = paths.add_cable(sc, "Bare")
    with pytest.raises(paths.PathError):
        paths_sea.add_sea_end(sc, paths.find(sc, "Bare"))


def test_drawn_tube_equals_the_solver_and_stripes(sea):
    sc = sea
    a = sc.fresing.animations[paths_sea.TEST_ANIMATION]
    r = animation.bake(sc, a)
    assert not r["warnings"], r["warnings"]
    it = cable(sc)
    frames, per, first = paths._layout_of(it.shapes)
    assert frames == sc.frame_end - sc.frame_start + 1 and it.moving
    stored = paths._stored_places(sc, it, paths._inputs_of(it)[1])
    assert stored is not None
    rel, first = stored
    dg = bpy.context.evaluated_depsgraph_get
    radius = 0.5 * it.diameter
    for f in (sc.frame_start, (sc.frame_start + sc.frame_end) // 2, sc.frame_end):
        sc.frame_set(f)
        res = paths._solve_item(sc, it, rel[f - first:f - first + 1])
        want = paths._at(paths._world(it.part), res["points"][0])
        got = paths.shape_now(sc, it)
        assert np.abs(got - want).max() < 1e-3, f                                       # the drawn line: the solver's
        ev = it.part.evaluated_get(dg())
        W = np.array(ev.matrix_world)
        co = np.empty(len(ev.data.vertices) * 3)
        ev.data.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3) @ W[:3, :3].T + W[:3, 3]
        sample = co[:: max(1, len(co) // 1500)]
        d = seg_dist(sample, want)
        assert np.abs(d[d > 0.5 * radius] - radius).max() < 1e-3, f                    # the tube round it (caps aside)
        n = paths_sea.numbers(sc, it)
        assert n["layback"] == pytest.approx(20.0, abs=1e-3)                            # with the lay: it stays
    # stripes: a point on the seabed keeps its mark (the cable lies still), a point on the hanging part does not
    sc.frame_set(sc.frame_start)
    it = cable(sc)
    bed0 = np.array(paths_sea.bed(sc).matrix_world)
    line = paths.shape_now(sc, it)
    on_bed = line[-1] + 0.5 * (line[-2] - line[-1])                                     # halfway along the laid part
    tdp, top = paths_sea.tdp_world(sc, it)[1], paths_sea.tdp_world(sc, it)[0]
    hanging = top + 0.5 * (tdp - top)
    hanging = line[np.argmin(np.linalg.norm(line - hanging, axis=1))]
    m_bed0, m_hang0 = mark_at(sc, it, on_bed), mark_at(sc, it, hanging)
    sc.frame_set(sc.frame_end)
    bed1 = np.array(paths_sea.bed(sc).matrix_world)
    moved = bed1[:3, 3] - bed0[:3, 3]
    assert np.linalg.norm(moved) == pytest.approx(paths_sea.payout(sc, it), abs=1e-3)   # the seabed moved aft
    m_bed1 = mark_at(sc, it, on_bed + moved)                                            # the same piece of cable …
    assert m_bed1 == pytest.approx(m_bed0, abs=2e-3)                                    # … has the same mark
    assert mark_at(sc, it, hanging) == pytest.approx(m_hang0 - paths_sea.payout(sc, it), abs=0.05)
    # the look's mark: what the material draws at s is (s − paid out) / pitch – the pay driver follows the joint
    assert it.part.evaluated_get(dg())[cable_looks.PAY] == pytest.approx(paths_sea.payout(sc, it) + 2.0, abs=1e-4)


def test_vessel_speed_of_weather_moves_the_touch_down(sea):
    sc = sea
    it = cable(sc)
    s = sc.fresing
    s.weather.enabled = True
    s.weather.vessel_speed = 1.0                           # 0.514 m/s: slower than the lay (1 m/s)
    it.sea_speed = "WEATHER"
    a = s.animations[paths_sea.TEST_ANIMATION]
    animation.bake(sc, a)
    it = cable(sc)
    fc = paths_sea.bed(sc).animation_data.drivers.find("location", index=0)
    assert fc is not None and fc.driver.is_simple_expression and "frame" in fc.driver.expression
    sc.frame_set(sc.frame_start)
    lay0 = paths_sea.numbers(sc, it)["layback"]
    sc.frame_set(sc.frame_end)
    lay1 = paths_sea.numbers(sc, it)["layback"]
    adv = np.linalg.norm(np.array(paths_sea.bed(sc).matrix_world)[:2, 3])
    assert adv == pytest.approx(0.514444 * (sc.frame_end - sc.frame_start) / 25.0, rel=1e-3)
    assert lay1 < lay0 - 0.5                               # more paid out than sailed: the touch-down comes nearer


def test_cps_rides_down_the_catenary(sea):
    sc = sea
    a = sc.fresing.animations[paths_sea.TEST_ANIMATION]
    animation.bake(sc, a)
    it = cable(sc)
    r = it.riders[paths_sea.TEST_RIDER]
    rings = [p for p in r.parts if p.part.get(build.PROP_NAME) == "VERTEBRA"]
    assert len(rings) == 6 and len(r.parts) == 9
    run = paths_riders.run_object(sc, it)
    fc = run.animation_data.drivers[0]
    assert fc.driver.is_simple_expression
    sc.frame_set(sc.frame_end)                           # 8 m paid out: the set is past the horn, in the sea
    update()
    line = paths.shape_now(sc, it)
    dg = bpy.context.evaluated_depsgraph_get()
    below = 0
    for p in rings:
        ev = p.part.evaluated_get(dg)
        W = np.array(ev.matrix_world)
        co = np.empty(len(ev.data.vertices) * 3)
        ev.data.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3) @ W[:3, :3].T + W[:3, 3]
        mid = 0.5 * (co.min(0) + co.max(0))
        d = float(seg_dist([mid], line)[0])
        if mid[2] < 0.0:
            below += 1
            assert d < 2e-3, (p.part.name, d)            # on the catenary: on the cable's line within 2 mm
        # none through the cable: the cable's line stays inside the ring's bore (ID 150, cable Ø 120)
        M = paths_riders.matrix_now(sc, it, p.part)
        axis = M[:3, :3] @ np.array(r.axis)
        axis /= np.linalg.norm(axis)
        near = line[np.abs((line - mid) @ axis) < 0.15]
        if len(near):
            rel = near - mid
            off = np.linalg.norm(rel - np.outer(rel @ axis, axis), axis=1)
            assert off.max() < 0.075 - 0.06 + 2e-3, p.part.name
    assert below >= 4
    # the clash check leaves them out, as it does the cable
    assert paths._clash_hook in clash.HOOKS
    left = {o.name for o in paths._clash_hook(sc)[1]}
    assert {p.part.name for p in r.parts} <= left and it.part.name in left


def test_scripts_off_in_real_blender(sea, tmp_path):
    """The saved project in the real Blender with "Auto Run Python Scripts" off: the seabed moves with the cable
    joint and the CPS rides."""
    blender = os.path.expanduser("~/blender-5.2.3/blender-5.2.3-linux-x64/blender")
    if not os.path.exists(blender):
        pytest.skip("no real Blender here")
    sc = sea
    it = cable(sc)
    cj = joints.find(sc, it.joint)
    ring = [p.part for p in it.riders[0].parts if p.part.get(build.PROP_NAME) == "VERTEBRA"][0]
    want = []
    for v in (0.0, 3.0):
        joints.set_value(cj, v, use_limits=False)
        update()
        paths.refresh(sc)
        update()
        ev = ring.evaluated_get(bpy.context.evaluated_depsgraph_get())
        want.append((list(paths_sea.bed(sc).matrix_world.translation), list(ev.data.vertices[0].co)))
    joints.set_value(cj, 0.0, use_limits=False)
    update()
    path = str(tmp_path / "sea.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    script = tmp_path / "check.py"
    script.write_text(
        "import bpy, sys, json\n"
        "a = sys.argv[sys.argv.index('--') + 1:]\n"
        "ob = bpy.data.objects\n"
        "res = []\n"
        "for v in (0.0, 3.0):\n"
        f"    ob[a[0]][{joints.VALUE!r}] = v\n"
        "    ob[a[0]].update_tag()\n"
        "    bpy.context.view_layer.update(); bpy.context.view_layer.update()\n"
        "    dg = bpy.context.evaluated_depsgraph_get()\n"
        "    ev = ob[a[2]].evaluated_get(dg)\n"
        "    res.append((list(ob[a[1]].matrix_world.translation), list(ev.data.vertices[0].co)))\n"
        "print('RESULT' + json.dumps(res))\n")
    r = subprocess.run([blender, "-b", "-Y", "--factory-startup", path, "--python", str(script), "--",
                        cj.motion.name, paths_sea.BED, ring.name], capture_output=True, text=True, timeout=180)
    line = next((x for x in r.stdout.splitlines() if x.startswith("RESULT")), None)
    assert line is not None, r.stdout[-2000:] + r.stderr[-2000:]
    got = json.loads(line[len("RESULT"):])
    # (the cable's shape is not solved again without the extension, but the seabed and the CPS follow the joint)
    for (bed_g, v_g), (bed_w, v_w) in zip(got, want):
        assert np.allclose(bed_g, bed_w, atol=1e-5)
    assert np.linalg.norm(np.subtract(got[1][1], got[0][1])) > 1.0                      # the ring moved along


def test_model_update_keeps_the_sea_end_and_the_rider(sea):
    sc = sea
    it = cable(sc)
    it.sea_layback = 18.0
    r = it.riders[0]
    r.at = 2.0
    root = next(iter(build.model_roots(sc)))
    assert bpy.ops.fresing.import_step(filepath=MODEL, quality="draft", update_root=root.name) == {"FINISHED"}
    update()
    it = cable(sc)
    assert it.b_kind == "SEA" and it.sea_layback == pytest.approx(18.0) and it.problem == ""
    assert paths_sea.numbers(sc, it)["layback"] == pytest.approx(18.0, abs=1e-3)
    r = it.riders[0]
    assert r.at == pytest.approx(2.0) and len(r.parts) == 9 and all(p.part.name in sc.objects for p in r.parts)
    assert all(p.part.modifiers.get(paths_riders.MOD) is not None for p in r.parts)


def test_remove_puts_things_back(sea):
    sc = sea
    it = cable(sc)
    parts = [p.part for p in it.riders[0].parts]
    paths_riders.remove(sc, it, 0)
    assert all(p.modifiers.get(paths_riders.MOD) is None for p in parts)
    assert paths_riders.run_object(sc, cable(sc)) is None
    paths_sea.remove_sea_end(sc, cable(sc))
    it = cable(sc)
    assert it.b_kind == "FIXED"
    line = paths.shape_now(sc, it)
    assert line[:, 2].min() > -1.1                     # as drawn in CAD: down to 1 m under the water


def test_the_queue_copy_builds_and_renders_the_same(sea, tmp_path):
    """The render queue's background Blender opens a copy of the project, builds the animation again and renders:
    the copy draws the same catenary at every frame, and a render sees the cable hanging (not the CAD cable)."""
    from fresing_render.blender import cameras
    sc = sea
    a = sc.fresing.animations[paths_sea.TEST_ANIMATION]
    animation.bake(sc, a)
    frames = (1, 77, 201)

    def shapes(scene):
        out = []
        for f in frames:
            scene.frame_set(f)
            out.append(paths.shape_now(scene, cable(scene)))
        return np.array(out)

    want = shapes(sc)
    path = str(tmp_path / "queue copy.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path, copy=True)
    bpy.ops.wm.open_mainfile(filepath=path)
    paths.forget()
    sc = bpy.context.scene
    assert np.abs(shapes(sc) - want).max() < 1e-6
    r = animation.bake(sc, sc.fresing.animations[paths_sea.TEST_ANIMATION])
    assert not r["warnings"], r["warnings"]
    assert np.abs(shapes(sc) - want).max() < 1e-5
    top, tdp = paths_sea.tdp_world(sc, cable(sc))
    pts = np.array([(12.0, -3.0, 3.5), tuple(top), tuple(tdp)])
    sc.camera = cameras.add_camera(sc, "ISO", 35.0, "Queue view", points=pts)
    sc.render.engine = "CYCLES"
    sc.cycles.samples, sc.cycles.use_denoising = 1, False
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 96, 54, 100
    sc.render.image_settings.file_format = "PNG"
    sc.frame_set(201)

    def picture(name):
        sc.render.filepath = str(tmp_path / name)
        bpy.ops.render.render(write_still=True)
        img = bpy.data.images.load(sc.render.filepath)
        px = np.array(img.pixels[:]).reshape(-1, 4)[:, :3]
        bpy.data.images.remove(img)
        return px

    hanging = picture("hanging.png")
    again = picture("again.png")
    cable(sc).enabled = False
    stiff = picture("stiff.png")
    noise = float(np.abs(hanging - again).mean())
    assert float(np.abs(hanging - stiff).mean()) > 5.0 * noise + 1e-4
