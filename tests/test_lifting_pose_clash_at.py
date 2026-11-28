"""Task 0349 (Lifting makers): every built-in crane's own poses through the app's clash check – the crane moved from
its first pose through every named pose and back (``lifting_rig.pose_tour``), built and checked: no clash row. A
cylinder's own barrel and rod (a pendant's bar and rod) are left out, as the Set-up window's Check does (their inside
test in a long thin bore is the Clash lane's, 0378). Split by kind so no file sets a run's length. Blender as a
module."""

from __future__ import annotations

import pytest

pytest.importorskip("bpy")

import lifting_rig as LR  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def addon():
    import bpy
    import fresing_render
    bpy.ops.wm.read_factory_settings(use_empty=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.mark.parametrize("name", ["AT-40", "AT-100", "AT-250", "AT-500"])
def test_every_own_pose_is_clean(name, tmp_path):
    r = LR.Rigged(name, out=str(tmp_path / "cache"))
    assert LR.clash_rows(r, LR.pose_tour(r, seconds=0.6)) == []
