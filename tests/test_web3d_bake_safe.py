"""Task 0136 (bug hunt 0131, rows 1 and 12).

Row 1: Export web 3D model crashed Blender (segfault) with a moving cable and no built animation: the bake scene is a
copy that carries the project's data, and the cables' live handler ran for it. The export runs in a process of its own,
so a crash fails the test instead of killing pytest.
Row 12: the marine growth's waterline follows the surroundings' sea (water level, Vessel deck)."""

import os
import subprocess
import sys
import textwrap

import pytest

bpy = pytest.importorskip("bpy")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

SCRIPT = textwrap.dedent("""
    import sys, os
    sys.path.insert(0, {root!r})
    import bpy, addon_utils
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    import fresing_render
    fresing_render.register()
    from fresing_render.blender import animation, paths, web3d
    sc = bpy.context.scene
    sc.fresing.out_folder = {out!r}
    assert bpy.ops.fresing.import_step(filepath={model!r}, quality="draft") == {{"FINISHED"}}
    paths.set_up_moving_model(sc)
    if {built!r}:
        animation.clear_keys(sc)
    n_before = len(bpy.app.handlers.depsgraph_update_post)
    web3d.export(sc, os.path.join({out!r}, "m.glb"), size=256)
    assert os.path.getsize(os.path.join({out!r}, "m.glb")) > 1000
    assert len(bpy.app.handlers.depsgraph_update_post) == n_before      # the handlers are back
    assert not [s for s in bpy.data.scenes if s.name.startswith("FR web3d bake")]
    print("EXPORT-OK")
""")


@pytest.mark.parametrize("cleared", [False, True])
def test_export_with_a_moving_cable_does_not_crash(tmp_path, cleared):
    code = SCRIPT.format(root=ROOT, out=str(tmp_path), model=os.path.join(HERE, "data", "test_moving.step"),
                         built=cleared)
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=900)
    assert r.returncode == 0 and "EXPORT-OK" in r.stdout, (r.returncode, r.stdout[-800:], r.stderr[-1500:])


LIGHT_SCRIPT = textwrap.dedent("""
    import sys, os
    sys.path.insert(0, {root!r})
    import bpy, addon_utils
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    import fresing_render
    fresing_render.register()
    from fresing_render.blender import animation, lightbake, paths, web3d
    from fresing_render.core.web3d import Cancelled
    sc = bpy.context.scene
    sc.fresing.out_folder = {out!r}
    assert bpy.ops.fresing.import_step(filepath={model!r}, quality="draft") == {{"FINISHED"}}
    paths.set_up_moving_model(sc)
    animation.clear_keys(sc)                       # the moving cable is not built: its live handler would run
    # the copy's tag taken off: only pausing the handlers may keep them away from it (0147 row 1)
    init = web3d.Baker.__init__
    def untagged(self, *a, **k):
        init(self, *a, **k)
        if "fr_bake" in self.scene:
            del self.scene["fr_bake"]
    web3d.Baker.__init__ = untagged
    seen = []
    def spy(scene, *rest):                         # stands for any app handler that would act on the copy
        if scene is not None and scene.name.startswith("FR web3d bake"):
            seen.append(scene.name)
    spy.__module__ = "fresing_render.blender.spy"
    bpy.app.handlers.depsgraph_update_post.append(spy)
    bpy.app.handlers.frame_change_post.append(spy)
    n_before = {{n: len(getattr(bpy.app.handlers, n)) for n in ("depsgraph_update_post", "frame_change_post")}}
    calls = []
    orig = lightbake.Bake._bake_call
    def counted(self, *a, **k):
        calls.append(1)
        return orig(self, *a, **k)
    lightbake.Bake._bake_call = counted
    out = web3d.export(sc, os.path.join({out!r}, "m.glb"), size=256, light="SOFT", light_quality="DRAFT")
    assert os.path.getsize(out["html"]) > 1000 and calls, calls
    assert not seen, ("an app handler saw the bake copy", len(seen))
    after = {{n: len(getattr(bpy.app.handlers, n)) for n in n_before}}
    assert after == n_before, (after, n_before)                     # the handlers are back
    # a Cancel in the middle of the light bake: the handlers come back too
    def cancel_in_bake(self, *a, **k):
        raise Cancelled()
    lightbake.Bake._bake_call = lambda self, *a, **k: (orig(self, *a, **k), cancel_in_bake(self))
    try:
        web3d.export(sc, os.path.join({out!r}, "c.glb"), size=256, light="SOFT", light_quality="DRAFT")
        raise AssertionError("not cancelled")
    except Cancelled:
        pass
    after = {{n: len(getattr(bpy.app.handlers, n)) for n in n_before}}
    assert after == n_before, (after, n_before)
    assert not [s for s in bpy.data.scenes if s.name.startswith("FR web3d bake")]
    print("EXPORT-OK")
""")


def test_light_bake_keeps_the_live_handlers_away_from_the_copy(tmp_path):
    """Task 0161 (0147 row 1): the light bake (Soft light / Everything baked, and the House bake) ran Cycles on the
    bake copy with every live handler on; a moving cable that is not built crashed Blender once the copy's tag was
    missing. Its own process, so a crash fails the test instead of killing pytest."""
    code = LIGHT_SCRIPT.format(root=ROOT, out=str(tmp_path), model=os.path.join(HERE, "data", "test_moving.step"))
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=900)
    assert r.returncode == 0 and "EXPORT-OK" in r.stdout, (r.returncode, r.stdout[-800:], r.stderr[-1500:])


def test_pause_live_takes_the_app_handlers_out_and_puts_them_back():
    import fresing_render
    from fresing_render.blender import handlers
    import addon_utils
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    try:
        before = {n: list(getattr(bpy.app.handlers, n)) for n in handlers._PAUSED_LISTS}
        assert any(before.values())
        with handlers.pause_live():
            for n in handlers._PAUSED_LISTS:
                assert not [f for f in getattr(bpy.app.handlers, n) if f.__module__.startswith("fresing_render")]
        assert {n: list(getattr(bpy.app.handlers, n)) for n in handlers._PAUSED_LISTS} == before
    finally:
        fresing_render.unregister()


def test_the_waterline_follows_the_sea():
    import addon_utils
    import fresing_render
    from fresing_render.blender import marine_looks, surroundings, world
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    try:
        assert bpy.ops.fresing.import_step(filepath=os.path.join(HERE, "data", "test_crane_a.step"),
                                           quality="draft") == {"FINISHED"}
        sc = bpy.context.scene
        s = sc.fresing
        s.background = "SEA"
        s.water_level = 3.0
        surroundings.ensure(sc, s)
        assert marine_looks.waterline(sc) == pytest.approx(marine_looks.sea_z(sc))
        assert marine_looks.waterline(sc) == pytest.approx(3.0, abs=0.05)
        s.water_level = -2.0
        surroundings.ensure(sc, s)
        assert marine_looks.waterline(sc) == pytest.approx(-2.0, abs=0.05)
        s.vessel.enabled = True
        world.apply(sc, s)
        assert marine_looks.waterline(sc) == pytest.approx(marine_looks.sea_z(sc))
    finally:
        fresing_render.unregister()
