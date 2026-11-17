"""Task 0173: a label on a cable that hangs into the sea shows its live numbers – ``{top}``, ``{bottom}``,
``{layback}``, ``{angle}``, ``{depth}``, ``{speed}`` … in its words – and a label may have several lines (the demo's
"Lay data" box in shot 8). Model: tests/data/test_sea.step set up by ``paths_sea.set_up_test_model``."""

import functools
import os
import subprocess
import sys

import numpy as np
import pytest

from fresing_render.core import callouts as C

HERE = os.path.dirname(__file__)
MODEL = os.path.join(HERE, "data", "test_sea.step")
TEXT = "Lay data\\nTop tension {top} kN\\nBottom tension {bottom} kN\\nLayback {layback} m\\nAngle {angle}°\\n" \
       "Speed {speed} m/min\\nWater depth {depth} m"


# ---------------------------------------------------------------------------
# no Blender
# ---------------------------------------------------------------------------

def test_fields_are_filled_rounded_and_unknown_ones_kept():
    v = {"top": 18.94, "bottom": 7.66, "layback": 32.04, "angle": 65.6, "depth": 30.0, "speed": 10.0}
    assert C.fill("Top {top} kN, {angle}°, {speed} m/min, {depth} m", v) == "Top 18.9 kN, 66°, 10.0 m/min, 30 m"
    assert C.fill("{bottom} {layback}", v) == "7.7 32.0"
    assert C.fill("{top} {nothing} {Top}", {}) == f"{C.MISSING} {{nothing}} {{Top}}"     # no number: a dash
    assert C.fill("{top}", {"top": float("nan")}) == C.MISSING and C.fill("{speed}", {"speed": -0.01}) == "0.0"
    assert C.fields_in(TEXT) == ["top", "bottom", "layback", "angle", "speed", "depth"]
    assert C.fill("no fields", v) == "no fields"
    assert C.lines(TEXT)[:2] == ["Lay data", "Top tension {top} kN"] and len(C.lines(TEXT)) == 7
    assert C.lines("one\ntwo") == ["one", "two"]


# ---------------------------------------------------------------------------
# Blender
# ---------------------------------------------------------------------------

def fresh_process(fn):
    """Text strips are drawn only in a process of its own (see tests/test_video_labels.py)."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if os.environ.get("FR_FRESH_PROCESS") == "1":
            return fn(*args, **kwargs)
        env = dict(os.environ, FR_FRESH_PROCESS="1")
        done = subprocess.run([sys.executable, "-m", "pytest", f"{__file__}::{fn.__name__}", "-q", "-x",
                               "-p", "no:cacheprovider"], env=env, capture_output=True, text=True,
                              cwd=os.path.dirname(HERE), timeout=1500)
        assert done.returncode == 0, done.stdout[-4000:] + done.stderr[-1500:]
    return wrapper


def _scene(tmp_path):
    bpy = pytest.importorskip("bpy")
    import addon_utils

    import fresing_render
    from fresing_render.blender import paths, paths_sea
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    paths.forget()
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path)
    assert bpy.ops.fresing.import_step(filepath=MODEL, quality="draft") == {"FINISHED"}
    paths_sea.set_up_test_model(sc)
    return sc


def test_a_label_on_a_sea_cable_shows_its_numbers_at_every_frame(tmp_path):
    pytest.importorskip("bpy")
    from fresing_render.blender import animation, callouts, paths, paths_sea
    sc = _scene(tmp_path)
    it = paths.find(sc, paths_sea.TEST_CABLE)
    c = callouts.add(sc, it.part, it.part.matrix_world.translation, TEXT)
    other = callouts.add(sc, it.a_part, it.a_part.matrix_world.translation, "Clamp {top}")
    n = paths_sea.numbers(sc, it)
    got = callouts.label_text(sc, c)
    assert got.split("\n")[1] == f"Top tension {n['top']:.1f} kN" and f"Layback {n['layback']:.1f} m" in got
    assert f"Water depth {n['depth']:.0f} m" in got and "Speed 0.0 m/min" in got           # nothing keyed: stands
    assert callouts.label_text(sc, other) == f"Clamp {C.MISSING}"                           # not a sea cable
    r = animation.bake(sc, sc.fresing.animations[paths_sea.TEST_ANIMATION])
    assert not [w for w in r["warnings"] if "cable" in w.lower()], r["warnings"]
    blk = next(b for b in sc.fresing.animations[paths_sea.TEST_ANIMATION].blocks if b.joint == it.joint)
    fps = sc.render.fps
    mid = int(sc.frame_start + (blk.start + blk.duration / 2) * fps)
    seen = set()
    for f in (sc.frame_start + 2, mid, sc.frame_end):
        sc.frame_set(f)
        it = paths.find(sc, paths_sea.TEST_CABLE)
        n = paths_sea.numbers(sc, it)
        rows = callouts.label_text(sc, c).split("\n")
        assert rows[1] == f"Top tension {n['top']:.1f} kN" and rows[3] == f"Layback {n['layback']:.1f} m", f
        seen.add(rows[5])
        if f == mid:
            assert float(rows[5].split()[1]) == pytest.approx(blk.speed_mmin, rel=0.02)
    assert len(seen) > 1                                    # the speed changes from running to standing
    # several lines: the box is as high as its lines
    w1, h1 = callouts.measure("Top tension 18.9 kN", 40)
    w7, h7 = callouts.measure(callouts.label_text(sc, c), 40)
    assert h7 == pytest.approx(40 * (1 + callouts.LINE_SPACE * 6)) and w7 >= w1 * 0.9


@fresh_process
def test_a_label_of_several_lines_is_drawn_in_its_box(tmp_path):
    bpy = pytest.importorskip("bpy")
    from fresing_render.blender import callouts, paths, paths_sea, video
    from fresing_render.core import brand
    sc = _scene(tmp_path)
    it = paths.find(sc, paths_sea.TEST_CABLE)
    sc.fresing.callouts_on = True
    pts = paths.shape_now(sc, it)
    callouts.add(sc, it.part, pts[len(pts) // 2], TEXT)             # (the scene's camera sees the cable)
    W, H = callouts.picture_size(sc)
    fin = video.finishing_for_still(sc)
    draws = fin.label_track[1]
    assert len(draws) == 1 and draws[0].text.count("\n") == 6
    img = bpy.data.images.new("grey", W, H, alpha=True)
    px = np.full((H, W, 4), 0.5, np.float32)
    px[:, :, 3] = 1.0
    img.pixels.foreach_set(px.ravel())
    path = str(tmp_path / "still.png")
    img.filepath_raw, img.file_format = path, "PNG"
    img.save()
    bpy.data.images.remove(img)
    video.finish_picture(path, fin)
    out = bpy.data.images.load(path, check_existing=False)
    out.colorspace_settings.is_data = True
    got = np.empty(W * H * 4, np.float32)
    out.pixels.foreach_get(got)
    got = got.reshape(H, W, 4)[:, :, :3] * 255.0                 # rows from the bottom, as the boxes
    b = draws[0].box
    x0, x1, y0, y1 = int(b.x) + 3, int(b.x + b.w) - 3, int(b.y) + 3, int(b.y + b.h) - 3
    patch = got[y0:y1, x0:x1]
    box_rgb = np.array(brand.hex_to_rgb(brand.DEFAULT_COLOR_1)) * 255.0
    light = patch.mean(axis=2) > 170                              # the text (light on the dark box)
    assert light.any()
    rows = light.any(axis=1)
    bands = int(np.count_nonzero(np.diff(rows.astype(int)) == 1)) + int(rows[0])
    assert bands >= 6, f"{bands} lines of text drawn"            # 7 lines (some letters may touch)
    # the lines start inside the box's left edge (left-aligned in it, none cut off by the picture's edge)
    wide = got[y0:y1, max(0, int(b.x) - 30):int(b.x + b.w) + 5].mean(axis=2) > 170
    first = int(np.nonzero(wide.any(axis=0))[0][0]) + max(0, int(b.x) - 30)
    assert b.x + 2 <= first <= b.x + 0.1 * b.w, (first, b.x, b.w)
    # all of the text is inside the box: nothing light just outside it
    outside = got[int(b.y + b.h) + 2:int(b.y + b.h) + 8, x0:x1].mean(axis=2)
    assert (outside < 170).all()
    assert np.abs(patch[light == 0].mean(axis=0) - box_rgb).max() < 60   # the box is the kit's colour
