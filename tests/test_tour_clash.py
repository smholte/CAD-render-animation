"""Task 0067 (split in task 0127): every animation of every test-tour project is built and checked: 0 rows, except the
clash model's own 6.0 mm. A new tour set (a new function's stop) is checked here by itself.

Until task 0127 this was one test in tests/test_clash.py that built all sets and checked them in one go: after task
0122 it took 300 of its 360 s on a 4-core machine and could time out on a busy GitHub runner. Now each set is its own
test (it builds only its own project, ``tour.build_all(only=...)``) with its own time box, and the file is its own
item for the pytest groups (``tools/ci_groups.py``). The checks are the same as before: every animation of every set,
0 rows, the clash model exactly its own pair at ``tour.CLASH_DEPTH``, at least 15 animations in all.
"""

import time

import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import animation, clash, tour  # noqa: E402
from fresing_render.core import clash as core  # noqa: E402

MM = 1e-3
SET_SECONDS = 150           # time box of one set: build + every animation built and checked (the slowest sets, the
                            # toolpath's milling program and the 4th axis, take about 40 s on the 4-core web machine)
CHECKED: dict[str, int] = {}


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.mark.parametrize("sid", list(tour.SETS))
def test_tour_set_has_no_clash(sid, tmp_path):
    t0 = time.perf_counter()
    folder = str(tmp_path / "tour")
    out = tour.build_all(folder, "9.9.9", only=(sid,))
    assert not out["errors"], out["errors"]
    tour.open_set(folder, "9.9.9", sid)
    sc = bpy.context.scene
    found, n = {}, 0
    for a in list(sc.fresing.animations):
        animation.bake(sc, a)
        rows = clash.check(sc, store=False).rows
        n += 1
        if sid == "clash":
            assert [frozenset((r.a, r.b)) for r in rows] == [frozenset(("ARM.A", "ARM.B"))], sid
            assert abs(rows[0].depth / MM - tour.CLASH_DEPTH) < 0.1
        elif rows:
            found[f"{sid} / {a.name}"] = [core.row_text(r) for r in rows[:5]]
    CHECKED[sid] = n
    assert not found, found
    took = time.perf_counter() - t0
    assert took < SET_SECONDS, f"{sid}: {took:.0f} s"


def test_every_set_was_checked():
    """(Runs after the sets above, in this file's order.) No set was left out, and as many animations as before."""
    assert set(CHECKED) == set(tour.SETS), sorted(set(tour.SETS) - set(CHECKED))
    assert sum(CHECKED.values()) >= 15
