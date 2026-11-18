"""Task 0214 (bug hunt 0209 row 17): the built-in cranes' own poses (Travel, Set up, Working, Long reach …) and the
way between them leave no part going further into another than it already is – the clash check of a pose animation
gives no row on the crane itself, whatever pose it starts in (``lifting_rig.overlap_changes``). Before the fix the
outrigger beams ran up to 190 mm through the chassis frame, a beam 47 mm through a tyre, a knuckle crane's first
extension into its outer boom, its main cylinder into the column, a crawler's jib foot through the boom head. And one
real pose animation per kind through the app's clash check, started from the second pose. Blender as a module."""

from __future__ import annotations

import pytest

pytest.importorskip("bpy")

import lifting_rig as LR  # noqa: E402

CLASSES = ["AT-40", "AT-100", "AT-250", "AT-500", "KB-20", "KB-50", "KB-100", "KB-200",
           "CC-100", "CC-300", "CC-750", "CC-1600"]


@pytest.fixture(scope="module", autouse=True)
def addon():
    import bpy
    import fresing_render
    bpy.ops.wm.read_factory_settings(use_empty=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.mark.parametrize("name", CLASSES)
def test_own_poses_go_no_deeper(name, tmp_path):
    r = LR.Rigged(name, out=str(tmp_path / "cache"))
    assert LR.overlap_changes(r) == []


@pytest.mark.parametrize("name", ["AT-100", "KB-20"])
def test_pose_animation_from_set_up_is_clean(name, tmp_path):
    r = LR.Rigged(name, out=str(tmp_path / "cache"))
    names = [p["name"] for p in r.sheet["poses"]]
    r.sheet = dict(r.sheet, poses=r.sheet["poses"][1:] + r.sheet["poses"][:1])      # start in "Set up"
    assert [p["name"] for p in r.sheet["poses"]][0] == names[1]
    assert LR.clash_rows(r, LR.pose_tour(r, seconds=0.6)) == []
