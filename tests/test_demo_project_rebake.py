"""Task 0160 (bug hunt 0147 rows 6 and 19): the re-bake after a sea change on the made demo project.

- row 6: the built demo, the sea changed CALM → ROUGH with the LAST frame shown: the re-bake gives exactly what a
  Build with ROUGH gives (before: "Second end" up to 8.13 m off on 3,243 of 3,806 frames; the small test model
  cannot show it, it needs the second end).
- row 19: the re-bake runs as a long job: the pass through the frames in small steps (progress), Cancel stops it and
  takes the built animation off ("Build again").

The demo project is made once per run and shared by the demo files (``tests/demo_made.py``, task 0145).
"""

import os
import sys
import time

import numpy as np
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

bpy = pytest.importorskip("bpy")
pytest.importorskip("OCP")

from demo_made import _scene, made  # noqa: E402,F401
from fresing_render.blender import animation, demo, paths, rebake  # noqa: E402


def _open(made):
    bpy.ops.wm.open_mainfile(filepath=made["out"]["path"])
    sc = _scene()
    a = sc.fresing.animations[demo.ANIM]
    a.start_shot = ""                           # (its start scene would put CALM back at Build)
    return sc, a


def _shapes(sc) -> dict:
    out = {}
    for it in sc.fresing.cables:
        sh = paths._shapes(sc, it)
        if sh is None:
            continue
        frames, per, _first = paths._layout_of(sh)
        co = np.empty(len(sh.data.vertices) * 3, np.float32)
        sh.data.vertices.foreach_get("co", co)
        out[it.name] = co.reshape(frames, per, 3).astype(float)
    return out


def test_the_rebake_at_the_last_frame_is_a_build(made):
    sc, a = _open(made)
    assert sc.fresing.sea_state == "CALM" and sc.fresing.anim_baked
    sc.fresing.sea_state = "ROUGH"
    animation.bake(sc, a)
    want = _shapes(sc)
    assert demo.SECOND_ITEM in want and demo.CABLE_ITEM in want

    sc, a = _open(made)
    if not sc.fresing.anim_baked:
        animation.bake(sc, a)
    sc.frame_set(sc.frame_end)
    t0 = time.perf_counter()
    sc.fresing.sea_state = "ROUGH"              # the background: the re-bake runs at once
    took = time.perf_counter() - t0
    assert sc.frame_current == sc.frame_end     # the frame shown comes back
    got = _shapes(sc)
    for name, w in want.items():
        g = got[name]
        assert g.shape == w.shape, (name, g.shape, w.shape)
        off = float(np.linalg.norm(g - w, axis=2).max())
        assert off < 1e-4, f"{name}: {off:.3f} m off a Build with ROUGH"
    print(f"\nre-bake in one go (background): {took:.1f} s")


def test_the_rebake_job_steps_and_cancel_takes_the_build_off(made):
    sc, a = _open(made)
    if not sc.fresing.anim_baked:
        animation.bake(sc, a)
    sc.frame_set(sc.frame_end)
    shown, hidden = sc.frame_current, [ob.name for ob in sc.objects if ob.hide_viewport]
    gen = rebake.steps(sc, {"flex": True, "paths": True})
    gaps, seen, t = [], [], time.perf_counter()
    for p in gen:
        now = time.perf_counter()
        gaps.append(now - t)
        seen.append(p)
        t = now
        if p >= 0.5 * rebake.READ_SHARE:
            break
    assert seen == sorted(seen) and len(seen) > sc.frame_end // 3, len(seen)      # a step per frame read
    assert max(gaps) < 1.0, max(gaps)
    gen.close()                                 # Cancel: the pass puts the visibility and the frame back
    assert sc.frame_current == shown and [ob.name for ob in sc.objects if ob.hide_viewport] == hidden
    rebake.cancelled(sc)
    assert not sc.fresing.anim_baked and "Build again" in sc.fresing.last_message
    print(f"\njob: {len(seen)} steps, longest {max(gaps) * 1000:.0f} ms")


def test_the_whole_job_gives_the_one_go_rebake(made):
    sc, a = _open(made)
    if not sc.fresing.anim_baked:
        animation.bake(sc, a)
    sc.fresing.sea_state = "ROUGH"              # one go (background)
    want = _shapes(sc)
    sc, a = _open(made)
    if not sc.fresing.anim_baked:
        animation.bake(sc, a)
    sc.frame_set(sc.frame_end // 2)
    real = paths.motion_changed
    paths.motion_changed = lambda scene, force=True: None              # the window's route: the job does it
    import fresing_render.blender.flex as flex
    real_f = flex.motion_changed
    flex.motion_changed = lambda scene, force=True: None
    try:
        sc.fresing.sea_state = "ROUGH"
    finally:
        paths.motion_changed, flex.motion_changed = real, real_f
    gaps, t = [], time.perf_counter()
    for _p in rebake.steps(sc, {"flex": True, "paths": True}):
        now = time.perf_counter()
        gaps.append(now - t)
        t = now
    got = _shapes(sc)
    assert sc.frame_current == sc.frame_end // 2
    for name, w in want.items():
        assert float(np.abs(got[name] - w).max()) < 1e-5, name
    print(f"\nwhole job: {len(gaps)} steps, longest step {max(gaps):.1f} s, total {sum(gaps):.1f} s")
