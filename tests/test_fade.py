"""Fade step, X-ray look and trail lines (task 0073)."""

import math
import os

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from mathutils import Vector  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import animation, build, cameras, fade, joints, materials, trails  # noqa: E402

HERE = os.path.dirname(__file__)
CRANE_A = os.path.join(HERE, "data", "test_crane_a.step")
DECALS_A = os.path.join(HERE, "data", "test_decals_a.step")
TOP_FACE = 5                     # the panel's top face (as tests/test_decals.py)


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def _fresh(path=CRANE_A):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    assert bpy.ops.fresing.import_step(filepath=path, quality="draft") == {"FINISHED"}
    return bpy.context.scene


@pytest.fixture()
def scene():
    return _fresh()


def ob(sc, name, n=0):
    hits = sorted((o for o in sc.objects if o.get(build.PROP_NAME) == name), key=lambda o: o.get(build.PROP_UID))
    return hits[n]


def _anim(sc, name="Fade", fps="25"):
    a = sc.fresing.animations.add()
    a.name, a.fps, a.tail = name, fps, 0.0
    return a


def _fade(a, target, kind="FADE_OUT", start=0.0, duration=2.0, **kw):
    b = a.blocks.add()
    b.kind, b.start, b.duration = kind, start, duration
    b.target_uid, b.target_name = target[build.PROP_UID], target.get(build.PROP_NAME, target.name)
    for k, v in kw.items():
        setattr(b, k, v)
    return b


def _boom(sc):
    pin = ob(sc, "BOOM.PIN")
    origin, direction, _d = joints.axis_from_hit(pin, 0, Vector((0.1, 0.3, 0.42)), Vector((0, 0, 1)))
    if direction.y > 0:
        direction = -direction
    return joints.create(sc, "ROTATE", [ob(sc, "BOOM.ASM")], origin, direction, ref=pin, name="Boom")


def _at(sc, f, o):
    sc.frame_set(f)
    return float(o[fade.FADE]), bool(o.hide_render), bool(o.hide_viewport)


# ---------------------------------------------------------------------------
# fade
# ---------------------------------------------------------------------------

def test_fade_out_timing_and_hidden_at_the_end(scene):
    cover = ob(scene, "COVER")
    a = _anim(scene)
    _fade(a, cover, start=1.0, duration=2.0, easing="LINEAR")
    info = animation.bake(scene, a)
    assert info["frames"] == 76 and not info["warnings"], info
    assert _at(scene, 1, cover) == (0.0, False, False)
    assert _at(scene, 26, cover) == (0.0, False, False)               # the step starts at 1 s = frame 26
    f, hr, hv = _at(scene, 51, cover)                                 # half way
    assert abs(f - 0.5) < 1e-4 and not hr
    f, hr, hv = _at(scene, 75, cover)
    assert f < 1.0 and not hr
    assert _at(scene, 76, cover) == (1.0, True, True)                 # gone: hidden, casts no shadow
    # its group's material is wrapped once; another part of the same group reads no fade (looks as before)
    mat = cover.material_slots[0].material
    assert fade.is_wrapped(mat)
    nodes = [n for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeGroup"]
    assert len(nodes) == 1
    others = [o for o in scene.objects if o is not cover and o.type == "MESH" and o.material_slots
              and o.material_slots[0].material is mat]
    for o in others:
        assert fade.FADE not in o
    # no drivers: works with scripts off
    assert cover.animation_data.drivers.__len__() == 0
    animation.clear_keys(scene)
    assert float(cover[fade.FADE]) == 0.0 and not cover.hide_render and not cover.hide_viewport
    assert not cover.get(fade.ANIM)


def test_smooth_easing_middle_and_stop_at(scene):
    cover = ob(scene, "COVER")
    a = _anim(scene)
    _fade(a, cover, duration=2.0, fade_stop=20.0)
    _fade(a, cover, kind="FADE_IN", start=3.0, duration=1.0, fade_stop=20.0)
    assert not animation.bake(scene, a)["warnings"]
    assert abs(_at(scene, 26, cover)[0] - 0.4) < 1e-3                 # smooth: half way in the middle (of 0 -> 0.8)
    f, hr, _hv = _at(scene, 51, cover)
    assert abs(f - 0.8) < 1e-6 and not hr                              # a 20 % ghost stays, not hidden
    assert abs(_at(scene, 70, cover)[0] - 0.8) < 1e-6
    assert abs(_at(scene, 76, cover)[0] - 0.8) < 1e-6                  # fade in starts at the ghost
    assert _at(scene, 101, cover) == (0.0, False, False)
    assert animation.block_label(a.blocks[0]) == "Fade out COVER"


def test_fade_in_of_a_shown_part_starts_hidden(scene):
    cover = ob(scene, "COVER")
    a = _anim(scene)
    _fade(a, cover, kind="FADE_IN", start=1.0, duration=1.0)
    animation.bake(scene, a)
    assert _at(scene, 1, cover) == (1.0, True, True)
    f, hr, _ = _at(scene, 26, cover)
    assert f == 1.0 and not hr
    assert _at(scene, 51, cover) == (0.0, False, False)


def test_fade_to_xray_stays_and_subassembly_fades_whole(scene):
    asm = ob(scene, "BOOM.ASM")
    a = _anim(scene)
    _fade(a, asm, duration=1.0, fade_xray=True, fade_color=(1.0, 0.2, 0.1), fade_strength=0.9)
    animation.bake(scene, a)
    parts = [o for o in scene.objects if o.type == "MESH" and o.get(fade.ANIM)]
    assert len(parts) >= 2                                             # every part under the subassembly
    for o in parts:
        f, hr, hv = _at(scene, 26, o)
        assert f == 1.0 and not hr and not hv                          # X-ray: never hidden
        assert o[fade.XRAY] == 1.0 and abs(o[fade.XSTRENGTH] - 0.9) < 1e-6
        assert abs(tuple(o[fade.XCOLOR])[1] - 0.2) < 1e-6
    assert animation.block_label(a.blocks[0]) == "Fade BOOM.ASM to X-ray"
    animation.clear_keys(scene)
    assert all(fade.XRAY not in o and o[fade.FADE] == 0.0 for o in parts)


def test_both_engines_and_rebuilt_material_keep_the_wrap(scene):
    cover = ob(scene, "COVER")
    mat = cover.material_slots[0].material
    glass = bpy.data.materials.new("FR glass test")
    glass.use_nodes = True
    materials.build_nodes(glass, "glass_clear")
    assert {n.target for n in glass.node_tree.nodes if n.bl_idname == "ShaderNodeOutputMaterial"} == {"CYCLES",
                                                                                                     "EEVEE"}
    fade.wrap(glass)
    outs = [n for n in glass.node_tree.nodes if n.bl_idname == "ShaderNodeOutputMaterial"]
    assert all(o.inputs["Surface"].links[0].from_node.node_tree.name == fade.GROUP for o in outs)   # both engines
    assert glass.use_transparent_shadow
    fade.wrap(glass)
    assert sum(n.bl_idname == "ShaderNodeGroup" for n in glass.node_tree.nodes) == 2               # not twice
    a = _anim(scene)
    _fade(a, cover)
    animation.bake(scene, a)
    materials.build_nodes(mat, mat["fr_material"], mat.get("fr_color", ""), 0.3)                    # a look change
    assert fade.is_wrapped(mat)
    assert mat.cycles.emission_sampling == "NONE"                      # the X-ray glow lights nothing


def test_old_project_and_animation_without_fade_unchanged(scene):
    j = _boom(scene)
    a = _anim(scene)
    b = a.blocks.add()
    b.kind, b.joint, b.duration, b.to_angle = "JOINT", j.name, 1.0, math.radians(20)
    animation.bake(scene, a)
    assert fade.GROUP not in bpy.data.node_groups
    assert not any(fade.is_wrapped(m) for m in bpy.data.materials)
    assert not any(fade.FADE in o for o in scene.objects)
    assert not any(o.get(trails.TAG) for o in scene.objects)


def _pixels(path, n):
    img = bpy.data.images.load(path)
    px = np.empty(n * n * 4, np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    return px.reshape(n, n, 4)[..., :3]


@pytest.mark.parametrize("engine", ["CYCLES", "BLENDER_EEVEE"])
def test_render_fades_in_both_engines(scene, tmp_path, engine):
    cover = ob(scene, "COVER")
    scene.camera = cameras.add_camera(scene, "ISO", 50.0, "T")
    a = _anim(scene)
    _fade(a, cover, duration=2.0, easing="LINEAR")
    animation.bake(scene, a)
    n = 48
    r = scene.render
    r.engine = engine
    r.resolution_x = r.resolution_y = n
    r.resolution_percentage = 100
    if engine == "CYCLES":
        scene.cycles.samples, scene.cycles.device = 16, "CPU"
        scene.cycles.use_denoising = False
        scene.cycles.seed = 1
    else:
        scene.eevee.taa_render_samples = 4
    shots = {}
    for f in (1, 26, 51):
        scene.frame_set(f)
        r.filepath = str(tmp_path / f"f{f}.png")
        bpy.ops.render.render(write_still=True)
        shots[f] = _pixels(r.filepath, n)
    full = np.abs(shots[51] - shots[1]).sum(axis=2)
    mask = full > 0.15                                                 # where the cover was
    assert mask.sum() >= 4, mask.sum()
    half = np.abs(shots[26] - shots[1]).sum(axis=2)[mask].mean() / full[mask].mean()
    assert 0.2 < half < 0.8, half                                      # half way: half see-through


def test_queue_copy_gives_the_same_frames_and_reopens(scene, tmp_path):
    cover = ob(scene, "COVER")
    j = _boom(scene)
    a = _anim(scene, "Fade and trail")
    b = a.blocks.add()
    b.kind, b.joint, b.duration, b.use_from, b.to_angle = "JOINT", j.name, 2.0, False, math.radians(30)
    _fade(a, cover, start=0.5, duration=1.0, fade_xray=True)
    boom = ob(scene, "BOOM")
    t = trails.add(scene, boom, "CLICKED", (1.5, 0.0, 0.0))
    animation.bake(scene, a)

    def frames(sc):
        c = ob(sc, "COVER")
        out = []
        for f in (1, 13, 20, 26, 38, 51):
            sc.frame_set(f)
            out.append((round(float(c[fade.FADE]), 6), c.hide_render, c.get(fade.XRAY)))
        return out

    want = frames(scene)
    fr0, pts0 = trails.frame_points(scene, t)
    path = str(tmp_path / "fade.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)                            # as the queue runner: open, build, render
    sc = bpy.context.scene
    assert frames(sc) == want                                          # the saved keys play the same
    animation.bake(sc, sc.fresing.animations["Fade and trail"])
    assert frames(sc) == want                                          # built again on the copy: the same
    fr1, pts1 = trails.frame_points(sc, sc.fresing.trails[0])
    assert np.array_equal(fr0, fr1) and np.abs(pts0 - pts1).max() < 1e-7
    t1 = sc.fresing.trails[0]
    assert t1.obj is not None and t1.obj.modifiers["Trail"].node_group is not None


# ---------------------------------------------------------------------------
# trail lines
# ---------------------------------------------------------------------------

def test_trail_follows_the_point(scene):
    j = _boom(scene)
    a = _anim(scene, "Boom up")
    b = a.blocks.add()
    b.kind, b.joint, b.duration, b.use_from, b.to_angle = "JOINT", j.name, 2.0, False, math.radians(35)
    boom = ob(scene, "BOOM")
    local = Vector((1.5, 0.0, 0.0))
    t = trails.add(scene, boom, "CLICKED", local)
    t.thickness, t.grow = 0.006, True
    info = animation.bake(scene, a)
    assert not info["warnings"]
    fr, pts = trails.frame_points(scene, t)
    assert len(fr) >= 40 and t.count == len(fr)
    for f in (1, 10, 26, 40, 51):
        k = int(np.argmin(np.abs(fr - f)))
        assert abs(fr[k] - f) < 1e-6
        scene.frame_set(f)
        want = boom.matrix_world @ local
        assert (Vector(pts[k]) - want).length < 1e-5                   # < 0.01 mm
    ob_t = t.obj
    assert ob_t.get(build.PROP_KIND) == trails.KIND and not ob_t.hide_render
    ng = ob_t.modifiers["Trail"].node_group
    assert abs(ng.nodes["radius"].inputs["Radius"].default_value - 0.003) < 1e-9
    mat = ng.nodes["material"].inputs["Material"].default_value
    assert mat.cycles.emission_sampling == "NONE"
    # draw as it goes: the evaluated tube grows with the frame
    dg = bpy.context.evaluated_depsgraph_get()
    scene.frame_set(5)
    n5 = len(ob_t.evaluated_get(dg).data.vertices)
    scene.frame_set(51)
    n51 = len(ob_t.evaluated_get(dg).data.vertices)
    assert 0 < n5 < n51
    t.grow = False
    scene.frame_set(5)
    assert len(ob_t.evaluated_get(dg).data.vertices) == n51
    t.in_render = False
    assert ob_t.hide_render and not ob_t.hide_viewport
    t.enabled = False
    assert ob_t.hide_viewport
    # another animation does not show it; a trail for every animation does
    other = _anim(scene, "Other")
    bb = other.blocks.add()
    bb.kind, bb.joint, bb.duration, bb.to_angle = "JOINT", j.name, 0.4, 0.0
    t.enabled = True
    animation.bake(scene, other)
    assert ob_t.hide_viewport
    t.animation = ""
    animation.bake(scene, other)
    assert not ob_t.hide_viewport and t.count >= 2
    # several trails, removal cleans up
    t2 = trails.add(scene, ob(scene, "TROLLEY"))
    animation.bake(scene, a)
    assert t2.obj is not None and t2.obj is not t.obj
    name = t2.obj.name
    trails.remove(scene, 1)
    assert name not in bpy.data.objects and len(scene.fresing.trails) == 1


def test_tool_tip_point_and_operators(scene):
    boom = ob(scene, "BOOM")
    boom["fr_tip"] = [1.5, 0.0, 0.0]
    assert trails.tip_of(scene, boom) == Vector((1.5, 0.0, 0.0))
    del boom["fr_tip"]
    assert trails.tip_of(scene, boom) is None
    assert bpy.ops.fresing.trail_add(part=boom.name) == {"FINISHED"}
    t = trails.active(scene)
    assert t.point == "ORIGIN" and t.part is boom
    w = boom.matrix_world @ Vector((1.0, 0.0, 0.0))
    assert bpy.ops.fresing.trail_pick_point(point=w, part=boom.name) == {"FINISHED"}
    assert t.point == "CLICKED" and (Vector(t.local) - Vector((1.0, 0.0, 0.0))).length < 1e-6
    assert bpy.ops.fresing.trail_remove() == {"FINISHED"}
    assert not scene.fresing.trails


# ---------------------------------------------------------------------------
# the X-ray look
# ---------------------------------------------------------------------------

def test_xray_look_save_reopen_and_clear(scene, tmp_path):
    cover = ob(scene, "COVER")
    s = scene.fresing
    n = fade.apply_look(scene, [cover])
    assert n == 1 and cover[fade.FADE] == 1.0 and cover[fade.XRAY] == 1.0 and cover.get(fade.LOOK)
    assert fade.is_wrapped(cover.material_slots[0].material)
    s.xray_strength = 0.25
    assert abs(cover[fade.XSTRENGTH] - 0.25) < 1e-6                    # the slider restyles every X-ray part
    # an animation built and cleared keeps the look
    a = _anim(scene)
    _fade(a, ob(scene, "BASE") if any(o.get(build.PROP_NAME) == "BASE" for o in scene.objects) else cover,
          duration=0.4)
    animation.bake(scene, a)
    animation.clear_keys(scene)
    assert cover[fade.FADE] == 1.0 and cover[fade.XRAY] == 1.0
    path = str(tmp_path / "x.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    c = ob(sc, "COVER")
    assert c[fade.FADE] == 1.0 and fade.xray_parts(sc) == [c]
    assert fade.remove_look(sc, [c]) == 1
    assert fade.XRAY not in c and c[fade.FADE] == 0.0 and not fade.xray_parts(sc)


def test_xray_operators_and_decals_go_along():
    sc = _fresh(DECALS_A)
    from fresing_render.blender import decals
    panel = ob(sc, "PANEL")
    decals.add(panel, TOP_FACE, (0.2, 0.15, 0.01), (0, 0, 1), "TEXT", text="FADE")
    sticker = fade.decals_of(panel)
    assert len(sticker) == 1
    bpy.ops.object.select_all(action="DESELECT")
    panel.select_set(True)
    bpy.context.view_layer.objects.active = panel
    sc.fresing.pick_mode = "PART"
    assert bpy.ops.fresing.xray_selected() == {"FINISHED"}
    assert panel.get(fade.LOOK) and sticker[0].get(fade.LOOK) and sticker[0][fade.FADE] == 1.0
    assert fade.is_wrapped(sticker[0].material_slots[0].material)
    assert bpy.ops.fresing.xray_clear() == {"FINISHED"}
    assert not panel.get(fade.LOOK) and not sticker[0].get(fade.LOOK)
    # a fade step fades the sticker with its part (its own keys; its visibility follows the part's)
    a = _anim(sc)
    _fade(a, panel, duration=1.0, easing="LINEAR")
    animation.bake(sc, a)
    sc.frame_set(13)
    assert abs(sticker[0][fade.FADE] - 0.48) < 1e-3
    sc.frame_set(26)
    assert sticker[0][fade.FADE] == 1.0 and panel.hide_render
    animation.clear_keys(sc)
    sc.fresing.groups_index = 0
    assert bpy.ops.fresing.xray_group() == {"FINISHED"}
    assert fade.xray_parts(sc)
    assert bpy.ops.fresing.xray_clear_all() == {"FINISHED"}
    assert not fade.xray_parts(sc)


def test_operator_adds_fade_step(scene):
    cover = ob(scene, "COVER")
    bpy.ops.object.select_all(action="DESELECT")
    cover.select_set(True)
    bpy.context.view_layer.objects.active = cover
    scene.fresing.pick_mode = "PART"
    assert bpy.ops.fresing.block_add(kind="FADE_OUT") == {"FINISHED"}
    a = animation.active(scene)
    b = a.blocks[-1]
    assert b.kind == "FADE_OUT" and b.duration == 1.0 and b.target_uid == cover[build.PROP_UID]
    assert animation.block_end(b) == 1.0
