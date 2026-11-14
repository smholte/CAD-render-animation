"""Task 0123 study – PROTOTYPE tests (branch task/0123-learning-study only).

* the crane lesson: every step's ``do`` (the tour build's own call) makes its ``done`` check true, the check is false
  before, and "where the lesson is" follows the scene (first step not done) – also after undo-like removal;
* the function list (core/functions.py) against the guide's anchors, the tour's stops, the PC check's lines and the
  lesson: the problems it finds today are exactly the guide anchors the build task must add;
* the text card never covers the part.
"""

import os
import re

import pytest

from fresing_render.core import functions

HERE = os.path.dirname(__file__)
ROOT = os.path.dirname(HERE)
CRANE_A = os.path.join(HERE, "data", "test_crane_a.step")


def test_card_never_covers_the_part():
    from itertools import product
    region = (1200, 800)
    size = (320, 120)
    for x0, y0, w, h in product((0, 100, 500, 900, 1100), (0, 300, 700), (50, 400, 1150), (40, 500, 790)):
        box = (x0, y0, min(1200, x0 + w), min(800, y0 + h))
        cx, cy = _place(box, size, region)
        overlap = cx < box[2] and cx + size[0] > box[0] and cy < box[3] and cy + size[1] > box[1]
        fits = box[2] - box[0] < region[0] - size[0] - 100 or box[3] - box[1] < region[1] - size[1] - 100
        assert not overlap or not fits, (box, (cx, cy))


def _place(box, size, region):
    # the same rule as lesson.place_card, without bpy (that module needs Blender)
    import importlib.util
    import sys
    import types
    if "bpy" not in sys.modules:
        pytest.importorskip("bpy")
    from fresing_render.blender import lesson
    return lesson.place_card(box, size, region)


def test_function_list_is_in_step_with_guide_tour_and_pc_check():
    guide = open(os.path.join(ROOT, "docs", "USER-GUIDE.md"), encoding="utf-8").read()
    anchors = functions.guide_anchors(guide)
    tour_src = open(os.path.join(ROOT, "fresing_render", "blender", "tour.py"), encoding="utf-8").read()
    stops = set(re.findall(r'^stop\("([a-z0-9_]+)"', tour_src, re.M))
    checks = open(os.path.join(ROOT, "fresing_render", "pccheck", "checks.py"), encoding="utf-8").read()
    lines = set(re.findall(r'@line\("([a-z0-9_.]+)"', checks))
    assert len(stops) >= 50 and len(lines) >= 70
    found = functions.problems(anchors=anchors, stops=stops, lessons={"crane": 11}, lines=lines)
    # what the prototype finds today: guide sections without an anchor (the registry task adds them)
    missing = sorted({re.search(r"anchor '([a-z0-9-]+)'", p).group(1) for p in found if "anchor" in p})
    others = [p for p in found if "anchor" not in p]
    assert others == []
    assert missing == ["camera", "light-look", "poses", "saved-scenes"]


def test_an_entry_out_of_step_is_named():
    bad = {"x.y": functions.Function(id="x.y", title="X", family="nope", panel="FRESING_PT_x", guide="zzz",
                                     tour=("nostop",), lesson="crane:99")}
    found = functions.problems(bad, anchors={"a"}, stops={"s"}, lessons={"crane": 11}, lines=set())
    text = " | ".join(found)
    for part in ("family 'nope'", "no button", "anchor 'zzz'", "no tour stop 'nostop'", "'crane:99' does not exist"):
        assert part in text


@pytest.fixture(scope="module")
def blender():
    bpy = pytest.importorskip("bpy")
    import addon_utils

    import fresing_render
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    from fresing_render.blender import lesson
    lesson.register()
    yield bpy
    lesson.unregister()
    fresing_render.unregister()


def test_crane_lesson_do_makes_done_true_step_by_step(blender):
    bpy = blender
    from fresing_render.blender import lesson
    bpy.ops.wm.read_factory_settings(use_empty=True)
    import addon_utils
    addon_utils.enable("cycles", default_set=True)
    les = lesson.LESSONS["crane"]
    sc = bpy.context.scene
    assert lesson.first_not_done(sc, les) == 0
    assert bpy.ops.fresing.import_step(filepath=CRANE_A, quality="draft") == {"FINISHED"}
    sc = bpy.context.scene
    bpy.ops.fresing.light_look(look="WHITE")            # so "Product studio" is not already the look
    assert lesson.first_not_done(sc, les) == 1
    for k, st in enumerate(les.steps[1:], 1):
        assert not st.done(sc), f"step {k + 1} '{st.title}' counts as done before it was done"
        st.do(sc)
        bpy.context.view_layer.update()
        assert st.done(sc), f"step {k + 1} '{st.title}': done() is false after do()"
        assert lesson.first_not_done(sc, les) == k + 1
        assert functions.FUNCTIONS[st.function].lesson == f"crane:{k + 1}"
    # taking a step back in the scene moves the lesson back (undo does this in the app)
    sc.fresing.queue.clear()
    assert lesson.first_not_done(sc, les) == len(les.steps) - 1
