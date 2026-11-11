"""Cutaway / section view (task 0086): plane and box cuts, cap colour, the cut as a slide joint."""

import math
import os
import subprocess
import sys

import numpy as np
import pytest

from fresing_render.core import section as core

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from mathutils import Vector  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import (animation, build, doublearm, fade, joints, materials, section,  # noqa: E402
                                    states)

HERE = os.path.dirname(__file__)
DATA = os.path.join(HERE, "data")
MACHINE = os.path.join(DATA, "test_machine.step")          # FRAME: a closed box 1000 x 600 x 50 mm at the origin
CRANE_A = os.path.join(DATA, "test_crane_a.step")
CRANE_B = os.path.join(DATA, "test_crane_b.step")
N = 40                                                     # picture size (square)


# ---------------------------------------------------------------------------
# no Blender
# ---------------------------------------------------------------------------

def test_core_places_and_words():
    c, n = core.plane_default((0, 0, 0), (1, 0.6, 0.05), (-3.0, 1.0, 2.0))
    assert c == pytest.approx((0.5, 0.3, 0.025)) and n == (-1.0, 0.0, 0.0)
    assert core.plane_default((0, 0, 0), (1, 1, 1), (0.2, 5.0, 0.0))[1] == (0.0, 1.0, 0.0)
    assert core.plane_default((0, 0, 0), (1, 1, 1), (0.0, 0.0, 9.0))[1] == (0.0, -1.0, 0.0)   # straight above
    c, size = core.box_default((0, 0, 0), (1, 0.6, 0.2), (-1.0, -1.0, 1.0), margin=0.0)
    assert c == pytest.approx((0.25, 0.15, 0.1)) and size == pytest.approx((0.5, 0.3, 0.2))
    c, size = core.box_default((0, 0, 0), (1, 1, 1), (1.0, 1.0, 0.0), margin=0.1)
    assert c[0] == pytest.approx(0.8) and size[0] == pytest.approx(0.6) and size[2] == pytest.approx(1.2)
    assert core.status(0, 0) == ""
    assert core.status(2, 1) == "2 cuts · 1 on"
    assert core.status(1, 0) == "1 cut · off"
    assert all(len(core.status(n, k)) <= 14 for n in range(1, 10) for k in range(n + 1))   # fits the header


# ---------------------------------------------------------------------------
# set-up
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def _fresh(path=MACHINE):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    assert bpy.ops.fresing.import_step(filepath=path, quality="draft") == {"FINISHED"}
    return bpy.context.scene


def ob(sc, name, n=0):
    hits = sorted((o for o in sc.objects if o.get(build.PROP_NAME) == name), key=lambda o: o.get(build.PROP_UID))
    return hits[n]


def _update():
    bpy.context.view_layer.update()
    bpy.context.view_layer.update()


def _camera(sc, loc, at, ortho):
    cd = bpy.data.cameras.new("Test")
    cam = bpy.data.objects.new("Test camera", cd)
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.location = loc
    cam.rotation_euler = (Vector(at) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    cd.type, cd.ortho_scale = "ORTHO", ortho
    return cam


def _look_side(sc):
    """From -X straight at the middle of the frame's end (the cut face of the default cut): a 150 mm window, the
    50 mm thick frame fills rows 14 … 26 of 40."""
    return _camera(sc, (-1.0, 0.3, 0.025), (0.5, 0.3, 0.025), 0.15)


def _look_down(sc):
    """From above, the whole frame: x runs left to right, y bottom to top (camera up = +Y)."""
    cam = _camera(sc, (0.5, 0.3, 2.0), (0.5, 0.3, 0.0), 1.1)
    cam.rotation_euler = (0.0, 0.0, 0.0)
    return cam


def _frame_only(sc):
    frame = ob(sc, "FRAME")
    for o in sc.objects:
        if o.get(build.PROP_KIND) == "part" and o is not frame:
            o.hide_render = True
    return frame


def _render(sc, tmp_path, name, engine="CYCLES", w=N, h=N):
    r = sc.render
    r.engine = engine
    r.resolution_x, r.resolution_y, r.resolution_percentage = w, h, 100
    if engine == "CYCLES":
        sc.cycles.samples, sc.cycles.device, sc.cycles.use_denoising, sc.cycles.seed = 16, "CPU", False, 1
    else:
        sc.eevee.taa_render_samples = 4
    r.filepath = os.path.join(str(tmp_path), name + ".png")
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(r.filepath)
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    return px.reshape(h, w, 4)[..., :3]          # row 0 = the bottom of the picture


def _red(px) -> np.ndarray:
    """The cap colour on screen (the view transform softens the strong red to about (0.7, 0.24, 0.21))."""
    return (px[..., 0] > 0.25) & (px[..., 0] > 2.0 * px[..., 1]) & (px[..., 0] > 2.0 * px[..., 2])


def _orange(px) -> np.ndarray:
    return (px[..., 0] > 0.3) & (px[..., 1] > 0.15) & (px[..., 2] < 0.6 * px[..., 0])


def _cut(sc, kind="PLANE", targets=None):
    frame = ob(sc, "FRAME")
    _look_side(sc)                               # the camera at -X: the new cut takes away x < 0.5
    return section.add(sc, targets or [("PART", frame, "")], kind)


@pytest.fixture()
def scene():
    return _fresh()


# ---------------------------------------------------------------------------
# what is cut, the shader, the objects
# ---------------------------------------------------------------------------

def test_add_cut_makes_shape_joint_and_wraps_only_its_parts(scene):
    cut = _cut(scene)
    frame = ob(scene, "FRAME")
    assert scene.fresing.floor_offset == pytest.approx(section.FLOOR_GAP)   # the floor below the cut faces
    j = section.joint_of(scene, cut)
    assert j is not None and j.kind == "SLIDE" and j.name == cut.name == "Cut 1"
    assert doublearm.app_joint(j)                                     # never taken as a CNC axis
    o, d = joints.axis_world(j)
    assert (o - Vector((0.5, 0.3, 0.025))).length < 1e-6 and (d - Vector((-1, 0, 0))).length < 1e-6
    assert not any(j.frame.lock_location) and not any(j.frame.lock_rotation)   # the handle moves
    assert cut.shape is not None and cut.shape.hide_select and cut.shape.parent is None
    assert cut.shape.constraints["FR cut"].target is j.motion
    assert [p.name for p in section.cut_parts(scene, cut)] == [frame.name]
    assert frame[section.ATTR + cut.key] == 1.0
    mat = frame.material_slots[0].material
    assert section.is_wrapped(mat)
    # other materials are not touched
    assert not any(section.is_wrapped(m) for m in bpy.data.materials if m is not mat)
    assert section.status(scene) == "1 cut · 1 on"
    assert scene.cycles.transparent_max_bounces >= section.TRANSPARENT_STEPS


def test_shape_follows_the_handle_and_the_slide(scene):
    cut = _cut(scene)
    j = section.joint_of(scene, cut)
    joints.set_value(j, 0.1)
    _update()
    # the arrow points to -X (the side taken away): +100 mm along it
    assert (cut.shape.matrix_world.translation - Vector((0.4, 0.3, 0.025))).length < 1e-6
    cut.place = (0.6, 0.3, 0.025)                   # by numbers (model coordinates)
    _update()
    assert (cut.shape.matrix_world.translation - Vector((0.5, 0.3, 0.025))).length < 1e-6
    assert tuple(cut.place) == pytest.approx((0.6, 0.3, 0.025))


def test_scripts_off_no_python_drivers(scene):
    cut = _cut(scene)
    ng = bpy.data.node_groups[section.GROUP]
    drivers = list(ng.animation_data.drivers)
    assert len(drivers) == 6                                           # scale x 3, turn x 3
    assert all(fc.driver.type == "AVERAGE" for fc in drivers)
    assert all(v.type == "TRANSFORMS" for fc in drivers for v in fc.driver.variables)
    j = section.joint_of(scene, cut)
    assert all(fc.driver.type == "AVERAGE" for fc in j.motion.animation_data.drivers)
    turn = ng.nodes[f"{cut.key} turn"]
    assert tuple(turn.inputs[i].default_value for i in range(3)) == pytest.approx(
        tuple(cut.shape.matrix_world.to_euler("XYZ")), abs=1e-5)


def test_materials_rebuilt_by_a_look_change_stay_cut_and_fade_wraps_outside(scene):
    cut = _cut(scene)
    frame = ob(scene, "FRAME")
    mat = frame.material_slots[0].material
    fade.prepare(frame)
    nt = mat.node_tree
    out = next(n for n in nt.nodes if n.bl_idname == "ShaderNodeOutputMaterial")
    first = out.inputs["Surface"].links[0].from_node
    assert first.node_tree.name == fade.GROUP                           # fade outside, the cut inside
    assert first.inputs[0].links[0].from_node.node_tree.name == section.GROUP
    materials.build_nodes(mat, mat["fr_material"], mat.get("fr_color", ""))
    out = next(n for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeOutputMaterial")
    first = out.inputs["Surface"].links[0].from_node
    assert first.node_tree.name == fade.GROUP
    assert first.inputs[0].links[0].from_node.node_tree.name == section.GROUP
    assert sum(1 for n in mat.node_tree.nodes if section._is_group(n, section.GROUP)) == 1
    assert cut is not None


def test_a_new_material_on_a_cut_part_is_wrapped(scene):
    _cut(scene)
    frame = ob(scene, "FRAME")
    new = bpy.data.materials.new("Milled faces (test)")
    frame.data.materials.append(new)
    _update()
    assert frame.name in section._PENDING
    section._wrap_pending()                                            # (the timer in the app)
    assert section.is_wrapped(new)


def test_group_part_and_model_targets(scene):
    bolt = ob(scene, "ISO 4017 M12 x 40 - 8.8 HDG")
    group = bolt[build.PROP_GROUP]
    cut = section.add(scene, [("GROUP", None, group)])
    assert len(section.cut_parts(scene, cut)) == 4
    cut2 = section.add(scene, [("MODEL", build.model_roots(scene)[0], "")], "BOX")
    assert len(section.cut_parts(scene, cut2)) == len(list(build.iter_parts(scene)))
    assert section.status(scene) == "2 cuts · 2 on"
    cut2.enabled = False
    assert section.status(scene) == "2 cuts · 1 on"
    ng = bpy.data.node_groups[section.GROUP]
    assert ng.nodes[f"{cut2.key} on"].outputs[0].default_value == 0.0
    section.remove(scene, section.find(scene, cut.key))
    assert not any(section.ATTR + "c1" in o for o in scene.objects)
    assert section.find(scene, "c1") is None and scene.fresing.joints.get("Cut 1") is None
    assert len(scene.fresing.cuts) == 1


def test_saved_scene_keeps_cuts_on_and_off(scene):
    cut = _cut(scene)
    states.save_shot(scene, "Cut open")
    cut.enabled = False
    states.save_shot(scene, "Whole")
    states.apply_shot(scene, "Cut open")
    assert section.find(scene, cut.key).enabled
    states.apply_shot(scene, "Whole")
    assert not section.find(scene, cut.key).enabled
    scene.fresing.shots["Cut open"].cuts = ""                          # saved before cuts existed: unchanged
    states.apply_shot(scene, "Cut open")
    assert not section.find(scene, cut.key).enabled


def test_old_project_without_cuts_is_unchanged(scene):
    section.sync(scene)
    assert section.GROUP not in bpy.data.node_groups
    assert not any(section.is_wrapped(m) for m in bpy.data.materials)
    assert not any(k.startswith(section.ATTR) for o in scene.objects for k in o.keys())
    assert scene.fresing.floor_offset == 0.0


# ---------------------------------------------------------------------------
# renders
# ---------------------------------------------------------------------------

def test_plane_cut_renders_the_half_and_the_cap(scene, tmp_path):
    frame = _frame_only(scene)
    cut = _cut(scene)
    _look_down(scene)
    px = _render(scene, tmp_path, "down")
    left, right = px[:, 5:17], px[:, 23:35]          # x 0.03 … 0.40 and 0.60 … 0.97 m
    rows = slice(int(N * 0.3), int(N * 0.7))
    assert _orange(right[rows]).mean() > 0.9                          # the half that stays
    assert _orange(left[rows]).mean() < 0.05                          # the half that is taken away
    _look_side(scene)
    px = _render(scene, tmp_path, "side")
    band = px[16:24]                             # the frame's end, seen through the cut
    assert _red(band).mean() > 0.9, band
    cut.flip = True                                                   # the other half stays: no cap seen from -X
    px = _render(scene, tmp_path, "side_flip")
    band = px[16:24]
    assert _red(band).mean() < 0.05 and _orange(band).mean() > 0.9
    _look_down(scene)
    px = _render(scene, tmp_path, "down_flip")
    assert _orange(px[rows, 5:17]).mean() > 0.9 and _orange(px[rows, 23:35]).mean() < 0.05
    assert frame is not None


def test_box_cut_takes_a_quarter(scene, tmp_path):
    _frame_only(scene)
    frame = ob(scene, "FRAME")
    _camera(scene, (-1.0, -1.0, 1.0), (0.5, 0.3, 0.0), 1.0)          # the camera at -X -Y: that quarter goes
    cut = section.add(scene, [("PART", frame, "")], "BOX")
    assert cut.shape_kind == "BOX"
    _look_down(scene)
    px = _render(scene, tmp_path, "box")
    # quarters of the frame in the picture (y 0 … 0.6 m spans rows ~9 … 31 of 40)
    lo_rows, hi_rows = slice(12, 18), slice(24, 29)
    assert _orange(px[lo_rows, 5:16]).mean() < 0.05                   # x < 0.5, y < 0.3: taken away
    assert _orange(px[lo_rows, 24:35]).mean() > 0.9
    assert _orange(px[hi_rows, 5:16]).mean() > 0.9
    assert _orange(px[hi_rows, 24:35]).mean() > 0.9
    cut.flip = True                                                   # only the box stays
    px = _render(scene, tmp_path, "box_flip")
    assert _orange(px[lo_rows, 5:16]).mean() > 0.9 and _orange(px[hi_rows, 24:35]).mean() < 0.05


def test_part_of_the_same_material_not_cut_renders_as_before(scene, tmp_path):
    bolts = [ob(scene, "ISO 4017 M12 x 40 - 8.8 HDG", k) for k in range(4)]
    assert len({b.material_slots[0].material.name for b in bolts}) == 1
    _look_down(scene)
    before = _render(scene, tmp_path, "before")
    _camera(scene, (-1.0, 0.0, 0.5), (0.05, 0.05, 0.05), 1.0)
    cut = section.add(scene, [("PART", bolts[0], "")])
    assert section.is_wrapped(bolts[0].material_slots[0].material)
    assert not any(section.ATTR + cut.key in b for b in bolts[1:])
    _look_down(scene)
    after = _render(scene, tmp_path, "after")
    keep = np.ones((N, N), bool)
    keep[:12, :8] = False                                             # round the cut bolt (x 0.05, y 0.05)
    diff = np.abs(after - before).sum(axis=2)[keep]
    assert diff.mean() < 0.01 and np.percentile(diff, 99) < 0.08, (diff.mean(), diff.max())


def test_cut_and_fade_together(scene, tmp_path):
    _frame_only(scene)
    _cut(scene)
    frame = ob(scene, "FRAME")
    _look_side(scene)
    px = _render(scene, tmp_path, "cut")
    assert _red(px[16:24]).mean() > 0.9
    for o in fade.prepare(frame):
        o[fade.FADE] = 1.0                                            # faded away: the cap goes with it
        o.update_tag()
    px = _render(scene, tmp_path, "faded")
    assert _red(px).mean() < 0.02 and _orange(px).mean() < 0.02


EEVEE_CHILD = """
import sys
sys.path.insert(0, {root!r})
sys.path.insert(0, {tests!r})
import test_section as T
import bpy, addon_utils, fresing_render
bpy.ops.wm.read_factory_settings(use_empty=True)
addon_utils.enable("cycles", default_set=True)
fresing_render.register()
sc = T._fresh()
T._frame_only(sc)
T._cut(sc)
T._look_side(sc)
px = T._render(sc, {out!r}, "eevee_side", "BLENDER_EEVEE")
print("RED", float(T._red(px[16:24]).mean()))
T._look_down(sc)
px = T._render(sc, {out!r}, "eevee_down", "BLENDER_EEVEE")
print("HALF", float(T._orange(px[12:28, 5:17]).mean()), float(T._orange(px[12:28, 23:35]).mean()))
"""


def test_plane_cut_in_eevee(tmp_path):
    """EEVEE needs a GL context: as the fade test, the render runs in a process of its own (skipped without one)."""
    code = EEVEE_CHILD.format(root=os.path.dirname(HERE), tests=HERE, out=str(tmp_path))
    p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=600)
    red = next((x for x in p.stdout.splitlines() if x.startswith("RED ")), None)
    if red is None and p.returncode < 0 or p.returncode in (134, -6):
        pytest.skip("EEVEE cannot start here (no GL context)")
    assert red is not None, (p.returncode, p.stdout[-2000:], p.stderr[-2000:])
    assert float(red.split()[1]) > 0.9
    half = next(x for x in p.stdout.splitlines() if x.startswith("HALF ")).split()
    assert float(half[1]) < 0.05 and float(half[2]) > 0.9


# ---------------------------------------------------------------------------
# moving the cut, the queue, saving, a model update
# ---------------------------------------------------------------------------

def _slide_animation(sc, cut, to=0.3, seconds=2.0):
    a = sc.fresing.animations.add()
    a.name, a.fps, a.tail = "Open up", "25", 0.0
    b = a.blocks.add()
    b.kind, b.joint, b.start, b.duration, b.easing = "JOINT", section.joint_of(sc, cut).name, 0.0, seconds, "LINEAR"
    b.use_from = False
    b.from_dist, b.to_dist = to, 0.0
    return a


def _shape_x(sc, f):
    sc.frame_set(f)
    return [round(sc.objects[n].matrix_world.translation.x, 7) for n in sorted(
        o.name for o in sc.objects if o.get(section.KEY) and o.type == "EMPTY" and o.constraints)]


def test_move_joint_step_moves_the_cut(scene, tmp_path):
    cut = _cut(scene)
    a = _slide_animation(scene, cut)
    animation.bake(scene, a)
    want = {1: 0.5 - 0.3, 26: 0.5 - 0.15, 51: 0.5}                    # linear from +300 mm (along -X) to 0
    for f, x in want.items():
        scene.frame_set(f)
        assert cut.shape.matrix_world.translation.x == pytest.approx(x, abs=1e-6), f
    _frame_only(scene)
    _look_down(scene)
    scene.frame_set(26)
    px = _render(scene, tmp_path, "half_way")
    # at frame 26 the plane is at x = 0.35 m: x 0.40 … 0.97 stays, x 0.03 … 0.30 is gone
    assert _orange(px[12:28, 21:35]).mean() > 0.9 and _orange(px[12:28, 5:13]).mean() < 0.05


def test_queue_copy_gives_the_same_frames_and_renders(scene, tmp_path):
    cut = _cut(scene)
    a = _slide_animation(scene, cut)
    animation.bake(scene, a)
    want = [_shape_x(scene, f) for f in (1, 13, 26, 51)]
    path = str(tmp_path / "cut.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)                            # as the queue runner: open, build, render
    sc = bpy.context.scene
    assert [_shape_x(sc, f) for f in (1, 13, 26, 51)] == want
    animation.bake(sc, sc.fresing.animations["Open up"])
    assert [_shape_x(sc, f) for f in (1, 13, 26, 51)] == want
    c = sc.fresing.cuts[0]
    assert c.shape is not None and section.joint_of(sc, c) is not None
    assert section.is_wrapped(ob(sc, "FRAME").material_slots[0].material)
    _frame_only(sc)
    sc.frame_set(51)
    _look_side(sc)
    px = _render(sc, tmp_path, "reopened")
    assert _red(px[16:24]).mean() > 0.9


def test_model_update_keeps_the_cut(tmp_path):
    sc = _fresh(CRANE_A)
    sc.fresing.out_folder = str(tmp_path)
    boom = ob(sc, "BOOM.ASM")
    cut = section.add(sc, [("PART", boom, ""), ("GROUP", None, ob(sc, "COVER")[build.PROP_GROUP])])
    j = section.joint_of(sc, cut)
    joints.set_value(j, 0.04)
    cut.color = (0.1, 0.2, 0.9)
    _update()
    where = cut.shape.matrix_world.translation.copy()
    root = build.model_roots(sc)[0]
    res = bpy.ops.fresing.import_step(filepath=CRANE_B, quality="draft", update_root=root.name)
    assert res == {"FINISHED"}
    _update()
    cut = sc.fresing.cuts[0]
    j = section.joint_of(sc, cut)
    assert j is not None and j.name == "Cut 1"
    assert joints.get_value(j) == pytest.approx(0.04, abs=1e-7)
    assert (cut.shape.matrix_world.translation - where).length < 1e-6
    new_boom = ob(sc, "BOOM.ASM")
    assert cut.targets[0].obj is new_boom and cut.targets[0].uid == new_boom[build.PROP_UID]
    names = {p.get(build.PROP_NAME) for p in section.cut_parts(sc, cut)}
    assert {"BOOM", "BOOM.PIN", "BOOM.LAMP", "COVER"} <= names            # the new revision's lamp too
    assert section.is_wrapped(ob(sc, "BOOM").material_slots[0].material)
    assert tuple(cut.color) == pytest.approx((0.1, 0.2, 0.9))
    assert len([x for x in sc.fresing.joints if section.is_cut_joint(x)]) == 1


def test_operators_and_decals_go_along():
    sc = _fresh(os.path.join(DATA, "test_decals_a.step"))
    from fresing_render.blender import decals
    panel = ob(sc, "PANEL")
    decals.add(panel, 5, (0.2, 0.15, 0.01), (0, 0, 1), "TEXT", text="CUT")      # on the panel's top face
    sticker = section._decals_of(panel)
    assert len(sticker) == 1
    bpy.ops.object.select_all(action="DESELECT")
    panel.select_set(True)
    bpy.context.view_layer.objects.active = panel
    sc.fresing.pick_mode = "PART"
    sc.fresing.cut_new_shape = "BOX"
    assert bpy.ops.fresing.cut_add(what="SELECTED") == {"FINISHED"}
    cut = section.active(sc)
    assert cut.shape_kind == "BOX" and [t.obj for t in cut.targets] == [panel]
    key = section.ATTR + cut.key
    assert panel[key] == 1.0 and sticker[0][key] == 1.0 and sticker[0][section.NOCAP] == 1.0   # no cap on a sticker
    assert section.is_wrapped(sticker[0].material_slots[0].material)
    assert bpy.ops.fresing.cut_select_handle() == {"FINISHED"}
    assert bpy.context.view_layer.objects.active is section.handle(sc, cut)
    assert bpy.ops.fresing.cut_add(what="MODEL") == {"FINISHED"}
    assert len(sc.fresing.cuts) == 2
    sc.fresing.cuts_index = 0
    assert bpy.ops.fresing.cut_target_remove(index=0) == {"FINISHED"}
    assert key not in panel and key not in sticker[0]
    assert bpy.ops.fresing.cut_remove() == {"FINISHED"}
    assert len(sc.fresing.cuts) == 1
    cut = sc.fresing.cuts[0]
    cut.name = "Housing cut"                                           # the joint follows the name
    assert section.joint_of(sc, cut).name == "Housing cut" and cut.joint == "Housing cut"
