"""Task 0130: ``sun_light`` is the sun's light at normal incidence (FORMAT 8.3, 1.0.1), measured with a probe turned to face
the sun – not an upward probe divided by sin(elevation), whose noise grows 12-fold at a 4.8° sun. Real Cycles, tiny scene."""

import math
import os

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import lightbake  # noqa: E402

FAST = {"samples": 8, "quality": "DRAFT"}


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def _scene(elevation):
    sc = bpy.context.scene
    w = bpy.data.worlds.new("Test sky")
    nt = w.node_tree
    nt.nodes.clear()
    sky = nt.nodes.new("ShaderNodeTexSky")
    sky.sun_elevation = math.radians(elevation)
    sky.sun_rotation = 0.0
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = 0.08
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(sky.outputs["Color"], bg.inputs["Color"])
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])
    sc.world = w
    me = bpy.data.meshes.new("t")
    me.from_pydata([(0, 0, 0), (0.1, 0, 0), (0, 0.1, 0)], [], [(0, 1, 2)])
    ob = bpy.data.objects.new("t", me)
    sc.collection.objects.link(ob)
    return sc, ob


def _sun(sc, ob, el, facing, seed):
    sc.cycles.seed = seed
    n = None
    if facing:                                  # sun_rotation 0 -> the sun's scene azimuth is 90° (house_bake)
        e, a = math.radians(el), math.radians(90.0)
        n = (math.cos(a) * math.cos(e), math.sin(a) * math.cos(e), math.sin(e))
    b = lightbake.Bake([ob], "ALL", sky={"sun_height": el, "sun_direction": 0.0}, occluders=[], lamps=[], uv="VERTEX",
                       scene=sc, probe_normal=n, **FAST)
    for _ in b.steps():
        pass
    r = b.result
    sun = np.maximum(np.array(r.reference) - np.array(r.reference_sky), 0.0)
    return sun if facing else sun / math.sin(math.radians(el))


def _run(el, facing, n=5):
    sc, ob = _scene(el)
    v = np.array([_sun(sc, ob, el, facing, 1 + i).mean() for i in range(n)])
    return v.mean(), v.std()


@pytest.mark.parametrize("el", [35.0, 12.0])
def test_facing_probe_agrees_with_the_upward_probe_over_sin(el):
    up, _ = _run(el, False, 3)
    fa, _ = _run(el, True, 3)
    print(f"el {el}: upward/sin {up:.3f}  facing {fa:.3f}")
    assert fa == pytest.approx(up, rel=0.12)


def test_low_sun_is_less_noisy_when_the_probe_faces_it():
    up_m, up_s = _run(4.8, False)
    fa_m, fa_s = _run(4.8, True)
    print(f"el 4.8: upward/sin {up_m:.3f} +- {up_s:.4f} ({up_s / up_m:.1%})   facing {fa_m:.3f} +- {fa_s:.4f} ({fa_s / fa_m:.1%})")
    assert fa_m > 0 and fa_s / fa_m <= 1.5 * up_s / up_m        # (measured: 1.7 % vs 2.1 % at 8 samples)
    assert fa_s / fa_m < 0.05
