"""``lightbake.bake(..., uv="UV1", sizes={object: (W, H)})`` (task 0114, for the house format's ``uv1_px``): the image
is exactly W x H (any whole numbers), objects without an entry are sized as before, and a size that stretches the UV
layout by more than 2 % gives a ``problems`` line instead of a silent rescale."""

import math

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

from fresing_render.blender import lightbake  # noqa: E402

FAST = {"samples": 4, "quality": "DRAFT"}


def _scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    w = bpy.data.worlds.new("Test sky")
    nt = w.node_tree
    nt.nodes.clear()
    sky = nt.nodes.new("ShaderNodeTexSky")
    sky.sun_elevation = math.radians(40.0)
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = 0.08
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(sky.outputs["Color"], bg.inputs["Color"])
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])
    sc.world = w
    return sc


def _plate(sc, name, sx, sy, location=(0.0, 0.0, 0.0)):
    """A flat plate sx x sy metres with a UV set 1 that covers it exactly (0 … 1 both ways, no stretch at W/H = sx/sy)."""
    me = bpy.data.meshes.new(name)
    me.from_pydata([(0, 0, 0), (sx, 0, 0), (sx, sy, 0), (0, sy, 0)], [], [(0, 1, 2, 3)])
    for layer in ("UVMap", "UVMap.001"):
        uv = me.uv_layers.new(name=layer)
        uv.data.foreach_set("uv", [0, 0, 1, 0, 1, 1, 0, 1])
    ob = bpy.data.objects.new(name, me)
    ob.location = location
    sc.collection.objects.link(ob)
    return ob


def test_sizes_are_exact_and_others_unchanged():
    sc = _scene()
    a = _plate(sc, "Plate A", 2.3, 1.2)
    b = _plate(sc, "Plate B", 1.0, 1.0, (4.0, 0.0, 0.0))
    bpy.context.view_layer.update()
    res = lightbake.bake([a, b], "ALL", uv="UV1", sizes={a: (46, 24)}, scene=sc, **FAST)
    assert res.items["Plate A"].pixels.shape == (24, 46, 3)
    assert res.items["Plate B"].pixels.shape[:2] == lightbake.Bake([b], "ALL", uv="UV1", scene=sc,
                                                                  **FAST).plan()["own"][0]["size"][::-1]
    assert not [p for p in res.problems if "does not fit" in p]
    assert np.isfinite(res.items["Plate A"].pixels).all() and res.items["Plate A"].pixels.mean() > 0
    # by name works too, and odd sizes (not powers of two) are taken as they are
    res = lightbake.bake([a], "ALL", uv="UV1", sizes={"Plate A": (37, 19)}, scene=sc, **FAST)
    assert res.items["Plate A"].pixels.shape == (19, 37, 3)


def test_a_size_that_stretches_the_layout_is_a_problem_line():
    sc = _scene()
    a = _plate(sc, "Plate A", 2.0, 1.0)
    bpy.context.view_layer.update()
    plan = lambda size: lightbake.Bake([a], "ALL", uv="UV1", sizes={a: size}, scene=sc, **FAST).plan()  # noqa: E731
    assert not plan((32, 16))["problems"]
    assert not plan((32, 16 + 0.25))["problems"]            # (whole numbers: 16 -> 16)
    assert not plan((64, 32))["problems"]                    # another density, still not stretched
    assert not plan((65, 32))["problems"]                    # 1.6 %: within 2 %
    p = plan((40, 16))["problems"]                           # 25 % wider than the layout
    assert len(p) == 1 and "Plate A" in p[0] and "40 x 16" in p[0] and "25 %" in p[0]
    assert plan((32, 20))["problems"]
    assert plan((40, 16))["own"][0]["size"] == (40, 16)     # never rescaled
