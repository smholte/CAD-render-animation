"""Task 0108's clash check in windows of frames (``tests/clash_windows_child.py``): every window as strict as the whole
check. Task 0247: the big demo's check left with its equipment (a private kit); the proof on the clash test model stays.
"""

import math
import os
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

bpy = pytest.importorskip("bpy")
pytest.importorskip("OCP")

import addon_utils  # noqa: E402

import fresing_render  # noqa: E402


def windows(f0: int, f1: int, n: int) -> list:
    """n windows of frames f0 … f1 that overlap by one frame: every step k → k+1 lies inside one of them."""
    cuts = sorted({f0, f1} | {f0 + round((f1 - f0) * i / n) for i in range(1, n)})
    return [(a, b) for a, b in zip(cuts, cuts[1:])]


def test_windows_cover_every_step():
    w = windows(1, 1853, 12)
    assert w[0][0] == 1 and w[-1][1] == 1853 and len(w) == 12 and len(windows(1, 1853, 36)) == 36
    assert all(a[1] == b[0] for a, b in zip(w, w[1:]))
    assert windows(1, 3, 12) == [(1, 2), (2, 3)]


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def test_windows_find_what_the_whole_check_finds(tmp_path):
    """The proof on a small model (the clash test model, as ``tests/test_clash.py`` sets it up): the arms come down
    onto each other (6.0 mm deep from frame 49 to 51), and an arm swung through a post within one frame (found only
    between two frames). Checked in windows (as the old demo was), the rows are the whole check's (pairs, frames, depth). A
    window measured from its own first frame would miss the arms (already 6 mm in each other there): the child
    measures from the animation's first frame."""
    import clash_windows_child as child

    from fresing_render.blender import animation, build, clash, joints, tour
    from fresing_render.core import clash as core
    from mathutils import Vector

    def load():
        bpy.ops.wm.read_factory_settings(use_empty=True)
        addon_utils.enable("cycles", default_set=True)
        sc = bpy.context.scene
        sc.fresing.out_folder = str(tmp_path)
        assert bpy.ops.fresing.import_step(filepath=os.path.join(HERE, "data", "test_clash.step"),
                                           quality="draft") == {"FINISHED"}
        return sc

    def key(rows):
        return sorted((frozenset((r.a, r.b)), r.frame_from, r.frame_to, round(r.depth * 1000, 1))
                      for r in rows if r.kind == "CLASH")

    def windowed(sc, cls, lo, hi):
        times = clash.sample_times(sc)
        real = clash.sample_times
        clash.sample_times = lambda _s: [t for t in times if lo <= t <= hi]
        try:
            return _run(cls(sc))
        finally:
            clash.sample_times = real

    def base(run):
        return {(run.names[p], run.names[q]): v for (p, q), v in run.base.items()}

    def compare(sc, expect, ns):
        full = clash.check(sc, store=False)
        whole = key(full.rows)
        assert expect <= {k[0] for k in whole}, whole
        cls = child.make_class(clash)
        cls.whole = child.hold_whole(clash, cls, sc)
        cls.start = (cls.whole["mats"][0].copy(), cls.whole["times"][0])
        assert np.allclose(cls.start[0], child.global_start(sc, cls.whole["names"])[0], atol=1e-9)
        f0, f1 = int(sc.frame_start), int(sc.frame_end)
        for n in ns:
            runs = [windowed(sc, cls, lo, hi) for lo, hi in windows(f0, f1, n)]
            for run in runs:                                    # the start overlaps are the whole check's
                for pair, v in base(run).items():
                    assert v == base(full).get(pair, v), (n, pair, v, base(full).get(pair))
            got = key([r for run in runs for r in run.rows])
            assert {k[0] for k in got} == {k[0] for k in whole}, (n, got, whole)
            for k in whole:                                     # each row of the whole check: same depth, its frames
                mine = [g for g in got if g[0] == k[0]]
                assert max(g[3] for g in mine) == pytest.approx(k[3], abs=0.15), (n, k, mine)
                assert min(g[1] for g in mine) == k[1] and max(g[2] for g in mine) == k[2], (n, k, mine)
        return cls

    arms_ = frozenset(("ARM.A", "ARM.B"))
    sc = load()
    a = sc.fresing.animations.add()
    a.name, a.tail, a.fps = "Arms meet", 0.0, "25"
    tour.clash_arms(sc, a)
    animation.bake(sc, a)
    cls = compare(sc, {arms_}, (3, 7))
    # measured from a window's own first frame (the plain check), the arms would be allowed 2.9 mm more: the child
    # measures them from the animation's first frame, where they are apart
    plain, strict = base(windowed(sc, clash.Check, 50, 51)), base(windowed(sc, cls, 50, 51))
    assert plain[("ARM.A", "ARM.B")][0] > 0.002 and strict[("ARM.A", "ARM.B")][0] == 0.0, (plain, strict)

    sc = load()
    a = sc.fresing.animations.add()
    a.name, a.tail, a.fps = "Fast swing", 0.2, "25"
    post = next(o for o in sc.objects if o.get(build.PROP_NAME) == "ARM.A.ASM")
    joints.create(sc, "ROTATE", [post], Vector((0.0, 0.044, 0.0)), Vector((0, 0, 1)), name="Arm A")
    tour._joint_step(a, "Arm A", 0.0, 0.04, math.radians(90))      # 90° within one frame
    animation.bake(sc, a)
    compare(sc, {frozenset(("ARM.A", "POST"))}, (2, 3))
    assert core.DEPTH > 0


def _run(run):
    for _p in run.steps():
        pass
    return run
