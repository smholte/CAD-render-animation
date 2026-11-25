"""Task 0337 (0328 rows 22, 24): Remove on a placed crane takes all of it; a load with no parts left says so."""

from __future__ import annotations

import os

import pytest

bpy = pytest.importorskip("bpy")

import fresing_render  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRANE = os.path.join(ROOT, "fresing_render", "data", "test_crane_a.step")


@pytest.fixture(scope="module", autouse=True)
def registered():
    mine = not hasattr(bpy.types.Scene, "fresing")
    if mine:
        fresing_render.register()
    yield
    if mine:
        bpy.ops.wm.read_homefile(use_empty=True)
        fresing_render.unregister()


def _example():
    from fresing_render.blender import lifting as BL, workspaces
    bpy.ops.wm.read_homefile(use_empty=True)
    workspaces.use_all(bpy.context.scene)
    sc = bpy.context.scene
    sc.fresing.out_folder = "/tmp/fr_lifting_remove_test"
    assert bpy.ops.fresing.import_step(filepath=CRANE, quality="draft") == {"FINISHED"}
    BL.forget()
    c, ld, a = BL.set_up_example(bpy.context)
    assert a.ok, a.reason
    return BL, sc, c, ld


def test_remove_of_a_crane_takes_all_of_it():
    from fresing_render.blender import remove
    BL, sc, c, ld = _example()
    root = c.root
    p = remove.plan(sc, [root])
    assert p["_cranes"] == [c.name]
    assert any("lifting crane" in t for t in p["loses"])
    remove.remove(sc, [root])
    assert len(sc.fresing.lifting.cranes) == 0
    assert not any(j.name.startswith(c.name) for j in sc.fresing.joints)
    assert not any(po.name.startswith(c.name) for po in sc.fresing.poses)
    assert not [o for o in bpy.data.objects if o.name.startswith("FR rope " + c.name)]


def test_a_load_with_no_parts_left_has_a_red_line_and_no_use():
    from fresing_render.blender import remove
    BL, sc, c, ld = _example()
    ro = BL.readout(sc, c, ld)
    assert not isinstance(ro, str)
    load_root = next(r for r in {o for o in (rf.obj for rf in ld.parts)} if r is not None)
    from fresing_render.blender import build
    remove.remove(sc, [build.model_root_of(load_root)])
    ld = BL.plan(sc).loads[0]
    assert not BL.load_parts(ld)
    ro = BL.readout(sc, c, ld)
    assert isinstance(ro, str) and "no parts left" in ro
