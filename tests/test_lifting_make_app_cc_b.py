"""Task 0204: five random valid CC cranes made from numbers (sets 5 … 9 of 20), each imported and
rigged in the app (Blender as a Python module), every joint from its minimum to its maximum against the maker's
kinematics, the hook at every pose, and the clash check of the crane's own motion: clean. See
tests/lifting_make_app.py.
"""

from __future__ import annotations

import pytest

pytest.importorskip("bpy")
pytest.importorskip("OCP")

import lifting_make_app as MA  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def addon():
    import bpy
    import fresing_render
    bpy.ops.wm.read_factory_settings(use_empty=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.mark.parametrize("i", range(MA.SETS_PER_FILE))
def test_made_cc_crane_in_the_app(i, tmp_path):
    values = MA.sets("CC", 1)[i]
    MA.assert_ok(MA.check_one("CC", 1 * MA.SETS_PER_FILE + i, values, tmp_path))
