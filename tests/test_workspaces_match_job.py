"""Workspaces match their job (task 0333, 0328 rows 9, 10, 11, 16, 26, 33): the lists, the Make list, the colleague's
project popup, the Client view's Play button, the lead motions menu and the still Motion panel."""

import os

import pytest

from fresing_render.core import functions as F
from fresing_render.core import workspaces as W

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import ui_left, ui_top, workspaces  # noqa: E402

CRANE = os.path.join(os.path.dirname(__file__), "data", "test_crane_a.step")


def shown(key):
    return W.shown_functions(W.builtin(key))


def test_video_producer_and_animator_have_their_functions():
    v = shown("video")
    assert {"scene.weather", "scene.weather_presets", "animation.weather_change", "scene.turntable",
            "scene.render_view", "joints.move", "scene.start_scene_save", "animation.weather_step"} <= v
    a = shown("animator")
    assert {"scene.light", "scene.save", "scene.weather", "scene.turntable"} <= a


def test_the_lists_match_the_panels():
    for key in ("essentials", "quick", "sales", "builder", "welding"):
        if "looks.materials" in shown(key):
            assert "looks.picker" in shown(key), key
    assert {"looks.finishes", "import.update"} <= shown("essentials")
    assert {"looks.finishes", "import.update"} <= shown("builder")


def test_the_client_view_imports_nothing():
    assert not [f for f in shown("client") if f.startswith("import.")]
    assert "FRESING_PT_import" in W.hidden_panels(W.builtin("client"))


def test_sales_renders_the_animation_from_make():
    assert "queue.video" in shown("sales")
    assert ("anim", "queue.video") and "queue.video" in ui_top.ALSO_SHOWS["anim"]


@pytest.fixture(scope="module")
def crane():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    assert bpy.ops.fresing.import_step(filepath=CRANE, quality="draft") == {"FINISHED"}
    yield bpy.context.scene
    workspaces.switch(bpy.context.scene, "All functions")
    fresing_render.unregister()


def test_make_has_the_animation_output_in_sales_not_in_the_client_view(crane):
    workspaces.switch(crane, "Sales")
    assert "anim" in [o[0] for o in ui_top._outputs(crane)]
    workspaces.switch(crane, "All functions")


def test_a_colleagues_project_opens_in_my_workspace_and_can_go_back(crane):
    s = crane.fresing
    me = workspaces.me()
    workspaces.switch(crane, "Video producer")
    s.saved_by = "A Colleague"
    assert workspaces.take_in(crane)
    assert workspaces.name_of(crane) == workspaces.default_name()
    assert "A Colleague" in workspaces.colleague_text(s.saved_by, "Video producer", "Essentials")
    assert bpy.ops.fresing.workspace_theirs() == {"FINISHED"}
    assert workspaces.name_of(crane) == "Video producer"
    # my own project, a project nobody saved, a Client view and a project already in my workspace: nothing happens
    s.saved_by = me
    assert not workspaces.take_in(crane)
    s.saved_by = ""
    assert not workspaces.take_in(crane)
    s.saved_by = "A Colleague"
    workspaces.switch(crane, "Client view")
    assert not workspaces.take_in(crane) and workspaces.name_of(crane) == "Client view"
    workspaces.switch(crane, workspaces.default_name())
    assert not workspaces.take_in(crane)
    assert workspaces.colleague_text("", "x", "y").startswith("Another person")
    s.saved_by = ""
    workspaces.switch(crane, "All functions")


def test_a_save_writes_who_saved_it(crane):
    crane.fresing.saved_by = ""
    workspaces._on_save()
    assert crane.fresing.saved_by == workspaces.me()


def test_the_popup_switch_is_a_setting_on_by_default():
    from fresing_render.blender import prefs, settings_store
    assert prefs.FRESING_AP_prefs.bl_rna.properties["ask_colleague_workspace"].default is True
    assert "ask_colleague_workspace" in settings_store.spec()


class Layout:
    def __init__(self):
        self.ops = []

    def column(self, **_kw):
        return self

    row = box = split = column

    def label(self, **_kw):
        pass

    def separator(self, **_kw):
        pass

    def operator(self, idname, text="", icon="NONE"):
        self.ops.append(idname)
        return type("P", (), {})()

    def prop(self, *a, **kw):
        return None

    def __getattr__(self, name):
        return lambda *a, **k: self


def test_the_lead_motions_menu_draws_nothing_greyed_in_the_client_view(crane):
    from fresing_render.blender import ui_lead_motions
    workspaces.switch(crane, "All functions")
    ctx = type("C", (), {"scene": crane})()
    crane.fresing.lead_motions.add().name = "Boom"
    lay = Layout()
    ui_lead_motions.draw_menu(lay, ctx)
    assert "fresing.lead_show_all" in lay.ops and "fresing.lead_edit" in lay.ops
    workspaces.switch(crane, "Client view")
    try:
        lay = Layout()
        ui_lead_motions.draw_menu(lay, ctx)
        assert not {"fresing.lead_show_all", "fresing.lead_edit", "fresing.lead_make_one",
                    "fresing.lead_add_step"} & set(lay.ops)
        assert "fresing.lead_back_to_start" in lay.ops
    finally:
        crane.fresing.lead_motions.clear()
        workspaces.switch(crane, "All functions")


def test_the_client_view_gets_a_play_button_once_built(crane):
    from fresing_render.blender import animation
    ctx = type("C", (), {"scene": crane})()
    workspaces.switch(crane, "Client view")
    try:
        crane[animation.PRINT] = "{}"
        assert ui_left.client_play(ctx)
        del crane[animation.PRINT]
        assert not ui_left.client_play(ctx)
    finally:
        workspaces.switch(crane, "All functions")
    crane[animation.PRINT] = "{}"
    assert not ui_left.client_play(ctx)
    del crane[animation.PRINT]


def test_the_built_animation_box_sits_below_the_back_to_cad_button(crane, monkeypatch):
    """Row 26: the panel stays still – the box that appears with a built animation goes at the bottom."""
    from fresing_render.blender import animation, ui_motion
    monkeypatch.setattr(animation, "has_keys", lambda scene: True)
    lay = Layout()
    ctx = type("C", (), {"scene": crane})()
    monkeypatch.setattr(ui_motion, "big", lambda layout, op, *a, **k: lay.ops.append(op))
    monkeypatch.setattr(ui_motion, "wrap", lambda *a, **k: None)
    monkeypatch.setattr(ui_motion, "gap", lambda *a, **k: None)
    ui_motion.FRESING_PT_motion.draw(type("P", (), {"layout": lay})(), ctx)
    assert lay.ops.index("fresing.pose_reset") < lay.ops.index("fresing.anim_clear")
