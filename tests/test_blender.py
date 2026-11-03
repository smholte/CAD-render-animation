"""End-to-end tests inside Blender (bpy module): import, sort, looks, cameras, renders, UI.

Run with the venv that has `bpy` and `cadquery-ocp` installed:
    python -m pytest tests/test_blender.py
"""

import os
import sys

import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
import numpy as np  # noqa: E402

HERE = os.path.dirname(__file__)
STEP = os.path.join(HERE, "data", "test_machine.step")

import fresing_render  # noqa: E402
from fresing_render.blender import build, cameras, logic, materials, render, world  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture()
def scene(tmp_path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path)
    res = bpy.ops.fresing.import_step(filepath=STEP, quality="draft")
    assert res == {"FINISHED"}
    return sc


def _part(sc, name):
    return next(ob for ob in build.iter_parts(sc) if ob[build.PROP_NAME] == name)


def test_import_structure(scene):
    parts = list(build.iter_parts(scene))
    assert len(parts) == 11
    bolts = [ob for ob in parts if ob[build.PROP_NAME].startswith("ISO 4017")]
    assert len(bolts) == 4
    assert len({ob.data.name for ob in bolts}) == 1, "repeated parts must share one mesh"
    uids = {ob[build.PROP_UID] for ob in parts}
    assert len(uids) == len(parts), "stable IDs must be unique"
    assert "TEST.MACHINE#1/COVER.ASM#1/COVER.PLATE#1" in uids
    frame = _part(scene, "FRAME")
    assert frame[build.PROP_COLOR] == "#F9A800"
    mn, mx = build.world_bounds([frame])
    assert np.allclose(mx - mn, [1.0, 0.6, 0.05], atol=1e-4), "mm must become metres"
    assert "custom_normal" in frame.data.attributes
    roots = build.model_roots(scene)
    assert len(roots) == 1 and roots[0].lock_location[0]


def test_sorting_and_materials(scene):
    s = scene.fresing
    groups = {g.name: g for g in s.groups}
    assert _part(scene, "ISO 4017 M12 x 40 - 8.8 HDG")[build.PROP_GROUP] == "Fasteners galvanized"
    assert _part(scene, "DIN 912 M10x30 - 12.9")[build.PROP_GROUP] == "Fasteners black"
    assert _part(scene, "ISO 7380 M6x12")[build.PROP_GROUP] == "Fasteners black"
    assert _part(scene, "FRAME")[build.PROP_GROUP] == "Colour #F9A800"
    assert _part(scene, "SIGNAL.LAMP")[build.PROP_GROUP] == "Unsorted"
    assert groups["Colour #F9A800"].material == "paint_satin"
    assert groups["Colour #F9A800"].color == "#F9A800"
    assert groups["Fasteners galvanized"].count == 4
    mat = _part(scene, "FRAME").material_slots[0].material
    assert mat is not None and mat.name == "FR Colour #F9A800"
    # instances share mesh but have their own (object-linked) material slot
    assert _part(scene, "FRAME").material_slots[0].link == "OBJECT"


def test_group_change_updates_all_parts(scene):
    s = scene.fresing
    g = s.groups["Colour #F9A800"]
    g.material = "paint_gloss"
    g.color = "RAL 5010"
    mat = bpy.data.materials["FR Colour #F9A800"]
    assert mat["fr_material"] == "paint_gloss"
    assert mat["fr_color"] == "RAL 5010"
    assert _part(scene, "FRAME").material_slots[0].material == mat


def test_manual_assignment_wins(scene):
    s = scene.fresing
    lamp = _part(scene, "SIGNAL.LAMP")
    logic.ensure_group(s, "Lights")
    lamp["fr_group_manual"] = "Lights"
    logic.apply_rules(scene)
    assert lamp[build.PROP_GROUP] == "Lights"


def test_rule_added_on_top(scene):
    s = scene.fresing
    r = s.rules.add()
    r.target, r.field, r.op, r.value = "Lamps", "name", "contains", "LAMP"
    s.rules.move(len(s.rules) - 1, 0)
    logic.apply_rules(scene)
    assert _part(scene, "SIGNAL.LAMP")[build.PROP_GROUP] == "Lamps"
    assert s.rules[0].count == 1


def test_paint_scheme_roundtrip(scene):
    s = scene.fresing
    logic.save_scheme(s, "Yellow")
    s.groups["Colour #F9A800"].color = "RAL 5010"
    logic.save_scheme(s, "Blue")
    logic.apply_scheme(scene, "Yellow")
    assert s.groups["Colour #F9A800"].color == "#F9A800"
    logic.apply_scheme(scene, "Blue")
    assert s.groups["Colour #F9A800"].color == "RAL 5010"


def test_template_roundtrip(scene, tmp_path):
    from fresing_render.blender.ops_main import _template_from_scene, apply_template
    from fresing_render.core.template import Template
    s = scene.fresing
    s.groups["Fasteners black"].material = "chrome"
    s.background = "TRANSPARENT"
    path = str(tmp_path / "tpl.json")
    _template_from_scene(scene).save(path)
    s.groups["Fasteners black"].material = "black_oxide"
    s.background = "COLOR"
    apply_template(scene, Template.load(path))
    assert s.groups["Fasteners black"].material == "chrome"
    assert s.background == "TRANSPARENT"


def test_pick_subassembly(scene):
    plate = _part(scene, "COVER.PLATE")
    sub = logic.subassembly_for_pick(plate)
    assert sub[build.PROP_NAME] == "COVER.ASM"
    bolt = _part(scene, "ISO 4017 M12 x 40 - 8.8 HDG")
    assert logic.subassembly_for_pick(bolt) is bolt  # loose part directly under the machine


def test_tree_lock_hide_exclude(scene):
    s = scene.fresing
    names = [it.obj[build.PROP_NAME] for it in s.tree]
    assert names[0] == "TEST.MACHINE" and "COVER.ASM" in names
    cover = next(it.obj for it in s.tree if it.obj[build.PROP_NAME] == "COVER.ASM")
    logic.set_locked(cover, False)
    assert not cover.lock_location[0] and cover[build.PROP_LOCKED] is False
    logic.set_hidden(cover, True)
    assert _part(scene, "COVER.PLATE").hide_render
    logic.set_hidden(cover, False)
    assert not _part(scene, "COVER.PLATE").hide_render
    small = logic.small_parts(scene, 15.0)
    assert {ob[build.PROP_NAME] for ob in small} == {"ISO 7380 M6x12"}
    logic.exclude(small)
    assert all(ob.hide_render for ob in small)
    assert logic.restore_excluded(scene) == 2


def test_camera_fit_frames_model(scene):
    render.apply_output(scene, scene.fresing)
    cam = cameras.add_camera(scene, "FRONT")
    bpy.context.view_layer.update()
    # project all bound-box corners: they must land inside the frame
    from bpy_extras.object_utils import world_to_camera_view
    from mathutils import Vector
    us, vs = [], []
    for pt in cameras._points(scene):
        co = world_to_camera_view(scene, cam, Vector(pt.tolist()))
        assert -0.001 <= co.x <= 1.001 and -0.001 <= co.y <= 1.001 and co.z > 0
        us.append(co.x)
        vs.append(co.y)
    # the model is centred and fills the frame in at least one direction
    assert abs((min(us) + max(us)) / 2 - 0.5) < 0.03 and abs((min(vs) + max(vs)) / 2 - 0.5) < 0.03
    assert max(max(us) - min(us), max(vs) - min(vs)) > 0.85


def test_output_presets_apply(scene):
    s = scene.fresing
    s.out_format = "brochure_a4"
    s.out_dpi = "300"
    assert (scene.render.resolution_x, scene.render.resolution_y) == (2480, 3508)
    s.out_use_bleed = True
    assert scene.render.resolution_x == 2551
    s.out_format = "presentation"
    s.out_resolution = "4k"
    assert (scene.render.resolution_x, scene.render.resolution_y) == (3840, 2160)


@pytest.mark.parametrize("bg, floor", [("COLOR", "SHADOW"), ("TRANSPARENT", "SHADOW"), ("HDRI", "VISIBLE"),
                                       ("SKY", "NONE")])
def test_tiny_renders(scene, bg, floor):
    s = scene.fresing
    s.background = bg
    s.floor = floor
    s.background_color = (0.2, 0.4, 0.8)
    s.out_format = "custom"
    s.out_custom_w, s.out_custom_h = 96, 54
    s.use_gpu = False
    info = render.render_still(scene, s, "draft")
    assert os.path.isfile(info["path"])
    img = bpy.data.images.load(info["path"])
    px = np.empty(img.size[0] * img.size[1] * 4, np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(-1, 4)
    if bg == "TRANSPARENT":
        assert px[:, 3].min() < 0.05, "background must be transparent"
        assert px[:, 3].max() > 0.95, "model must be opaque"
    if bg == "COLOR":
        # bottom-left pixel (outside the soft shadow) shows the exact background colour
        corner = px[0, :3]
        expect = [render.linear_to_srgb(c) for c in (0.2, 0.4, 0.8)]
        assert np.allclose(corner, expect, atol=0.02), (corner, expect)
    bpy.data.images.remove(img)


# ---------------------------------------------------------------------------
# UI smoke test: draw every panel with a fake layout and check names exist
# ---------------------------------------------------------------------------

class FakeLayout:
    def __init__(self, errors):
        self.errors = errors
        self.scale_y = 1
        self.alignment = "LEFT"
        self.active = True

    def _child(self, *a, **k):
        return FakeLayout(self.errors)

    row = column = box = split = _child

    def label(self, *a, **k):
        pass

    def panel(self, idname, default_closed=False):
        return FakeLayout(self.errors), FakeLayout(self.errors)     # draw the folded part too

    def progress(self, *a, **k):
        pass

    def separator(self, *a, **k):
        pass

    def prop(self, data, name, *a, **k):
        if data is None:
            return
        if name not in data.bl_rna.properties:
            self.errors.append(f"missing property {type(data).__name__}.{name}")

    def operator(self, idname, *a, **k):
        mod, op = idname.split(".")
        try:
            rna = getattr(getattr(bpy.ops, mod), op).get_rna_type()
        except Exception:
            self.errors.append(f"missing operator {idname}")
            return type("OpProps", (), {})()
        errors = self.errors

        class OpProps:                       # setting an option the operator does not have is an error
            def __setattr__(self, name, value):
                if name not in rna.properties:
                    errors.append(f"operator {idname} has no option {name}")
                object.__setattr__(self, name, value)
        return OpProps()

    def operator_menu_enum(self, idname, prop, *a, **k):
        return self.operator(idname)

    def template_list(self, listtype, _id, data, prop, active_data, active_prop, *a, **k):
        if prop not in data.bl_rna.properties:
            self.errors.append(f"missing list {prop}")
        if active_prop not in active_data.bl_rna.properties:
            self.errors.append(f"missing index {active_prop}")
        if not hasattr(bpy.types, listtype):
            self.errors.append(f"missing UIList {listtype}")

    def icon(self, *a, **k):
        return 0


def test_ui_panels_draw(scene, tmp_path):
    from fresing_render.blender import ui
    errors = []
    bpy.context.view_layer.objects.active = _part(scene, "FRAME")
    last = tmp_path / "last render.png"
    last.write_bytes(b"x")
    scene.fresing.last_render = str(last)      # draws "Open image" / "Show in folder"
    for cls in ui.CLASSES:
        if not issubclass(cls, bpy.types.Panel):
            continue
        fake = type("P", (), {"layout": FakeLayout(errors)})()
        cls.draw(fake, bpy.context)
        for extra in ("draw_header", "draw_header_preset"):
            if hasattr(cls, extra):
                getattr(cls, extra)(fake, bpy.context)
    # list item drawing
    s = scene.fresing
    for cls, data, prop in ((ui.FRESING_UL_tree, s, "tree"), (ui.FRESING_UL_groups, s, "groups"),
                            (ui.FRESING_UL_rules, s, "rules")):
        for item in getattr(data, prop):
            cls.draw_item(None, bpy.context, FakeLayout(errors), data, item, 0, data, "", 0)
    assert not errors, errors


def test_renamed_group_survives_resort(scene):
    s = scene.fresing
    g = s.groups["Colour #F9A800"]
    g.name = "Frame"
    logic.apply_rules(scene)
    assert _part(scene, "FRAME")[build.PROP_GROUP] == "Frame"
    assert s.groups.get("Colour #F9A800") is None
    assert s.groups["Frame"].count == 1
    g = s.groups["Frame"]
    g.name = "Main frame"          # second rename follows the chain
    logic.apply_rules(scene)
    assert _part(scene, "FRAME")[build.PROP_GROUP] == "Main frame"


def test_tree_counts_and_bounds(scene):
    s = scene.fresing
    assert s.model_count == 1
    root_item = s.tree[0]
    assert root_item.parts == 11
    tree = logic.Tree(scene)
    cover = next(it.obj for it in s.tree if it.obj[build.PROP_NAME] == "COVER.ASM")
    assert len([d for d in tree.descendants(cover) if d.get(build.PROP_KIND) == "part"]) == 3
    assert s.bounds_valid
    assert abs((s.bounds_max[0] - s.bounds_min[0]) - 1.0) < 1e-3


def test_show_in_folder(scene, tmp_path, monkeypatch):
    from fresing_render.blender import files
    calls = []
    monkeypatch.setattr(files.subprocess, "Popen", lambda *a, **k: calls.append(a[0]))
    f = tmp_path / "My renders é" / "frame 1.png"
    f.parent.mkdir()
    f.write_bytes(b"x")
    assert bpy.ops.fresing.show_in_folder(path=str(f)) == {"FINISHED"}
    assert calls == [["xdg-open", str(f.parent)]]
    assert bpy.ops.fresing.show_in_folder(path=str(tmp_path / "gone.png")) == {"CANCELLED"}
    # Windows: Explorer opens with the file selected; the path goes in quotes after /select,
    cmd = files.explorer_select_command(r"C:\Users\Seb\Pictures\Fresing Render\a b.mp4")
    assert cmd.startswith('explorer /select,"') and cmd.endswith('a b.mp4"')


def test_animation_frame_settings(scene):
    from fresing_render.blender import render
    sc = bpy.context.scene
    render.apply_quality(sc, "preview", use_gpu=False)
    c = sc.cycles
    assert c.caustics_reflective and c.max_bounces == 12 and abs(c.adaptive_threshold - 0.03) < 1e-6
    render.apply_motion_settings(sc)
    assert not c.caustics_reflective and not c.caustics_refractive
    assert (c.max_bounces, c.diffuse_bounces, c.glossy_bounces) == (8, 3, 4)
    assert abs(c.adaptive_threshold - 0.05) < 1e-6
    render.apply_quality(sc, "preview", use_gpu=False)        # stills get their own settings back
    assert c.caustics_reflective and c.diffuse_bounces == 4 and abs(c.adaptive_threshold - 0.03) < 1e-6
    if hasattr(c, "denoising_use_gpu"):
        assert c.denoising_use_gpu is False                   # no graphics card here
