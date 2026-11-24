"""Blender's keys outside Full access, F12 / Ctrl+F12 and the right-click menu (task 0253, study 0222 package B).

Here (Blender as a module, no window, no key presses): the key list, the polls that switch with Full access, the
swallowing operator changes nothing, the menu's entries (drawn into a stand-in layout) on a part, on empty space and in
the Client view, and every entry's operator on the test crane. The keys pressed in a window, the right-click with the
mouse: tools/ui_test_keys.py."""

import os

import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import build, context_menu, lock, workspaces  # noqa: E402

CRANE = os.path.join(os.path.dirname(__file__), "data", "test_crane_a.step")


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture(scope="module")
def crane():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    assert bpy.ops.fresing.import_step(filepath=CRANE, quality="draft") == {"FINISHED"}
    scene = bpy.context.scene
    workspaces.switch(scene, "All functions")
    yield scene
    workspaces.switch(scene, "All functions")


def boom(scene):
    return next(o for o in scene.objects if o.get(build.PROP_NAME) == "BOOM")


def state(scene):
    """What a key must never change: objects, their parents and visibility, the mode, keyframes."""
    acts = sum(len(a.layers) + sum(1 for _ in getattr(a, "fcurves", ())) for a in bpy.data.actions)
    return (sorted((o.name, o.parent.name if o.parent else "", o.hide_get(), o.hide_render) for o in scene.objects),
            bpy.context.mode, len(bpy.data.actions), acts, len(bpy.data.collections))


# --- the key list --------------------------------------------------------------------------------------------------

def _keys():
    return {(km, lock.key_label(k, m)) for km, _sp, k, m, _w in lock.BLENDER_KEYS}


def test_every_harmful_key_of_the_brief_is_swallowed():
    labels = {lab for _km, lab in _keys()}
    for want in ("Tab", "Ctrl+Tab", "Shift+D", "Alt+D", "Ctrl+J", "Ctrl+P", "Alt+P", "Ctrl+A",
                 "Shift+M", "Shift+A", "Ctrl+H", "Ctrl+0", "Ctrl+1", "Ctrl+2", "Ctrl+3", "Ctrl+4", "Ctrl+5",
                 "Ctrl+Page Up", "Ctrl+Page Down", "I", "Alt+I", "K"):
        assert want in labels, want
    # X and Delete with any modifier (Shift+X / Shift+Delete too) open the app's Remove window since task 0292: it
    # lists what goes, nothing is lost until Remove is pressed
    anys = {k for km, _sp, k, m, _w in lock.BLENDER_KEYS if km == "Object Mode" and m.get("any")}
    assert anys == set()
    app = {k: op for km, _sp, k, m, op, _p in lock.APP_KEYS if km == "Object Mode" and m.get("any")}
    assert app == {"X": "fresing.remove_key", "DEL": "fresing.remove_key"}
    # M (Blender's "move to collection", swallowed before) opens Measure since task 0322; Alt+M too, everywhere
    measure = {(k, tuple(sorted(m.items()))): op for km, _sp, k, m, op, _p in lock.APP_KEYS if k == "M"}
    assert measure == {("M", ()): "fresing.measure_key", ("M", (("alt", True),)): "fresing.measure"}


def test_the_keys_a_user_needs_stay_blenders():
    plain = {(k, tuple(sorted(m.items()))) for km, _sp, k, m, _w in lock.BLENDER_KEYS if km != "User Interface"}
    for key, mods in (("H", {}), ("H", {"alt": True}), ("H", {"shift": True}), ("A", {}), ("G", {}), ("R", {}),
                      ("S", {}), ("HOME", {}), ("Z", {}), ("SPACE", {}), ("SPACE", {"ctrl": True}),
                      ("Z", {"ctrl": True}), ("F3", {}), ("N", {}), ("F11", {}), ("S", {"ctrl": True}),
                      ("O", {"ctrl": True})):
        assert (key, tuple(sorted(mods.items()))) not in plain, (key, mods)
    assert not any(k in ("F12",) for _km, _sp, k, _m, _w in lock.BLENDER_KEYS)


def test_f12_and_the_right_mouse_are_the_apps():
    app = {(k, tuple(sorted(m.items()))): (op, p) for _km, _sp, k, m, op, p in lock.APP_KEYS}
    assert app[("F12", ())] == ("fresing.key_render", {"animation": False})
    assert app[("F12", (("ctrl", True),))] == ("fresing.key_render", {"animation": True})
    assert app[("RIGHTMOUSE", ())][0] == "fresing.view_menu"
    # the Client view's own keys are still there, unchanged (task 0227)
    assert ("Object Mode", "EMPTY", "X", {"any": True}) in lock._KEYS
    assert ("Window", "EMPTY", "S", {"ctrl": True, "shift": True}) in lock._KEYS


def test_the_keys_switch_with_full_access(crane):
    for name, quiet in (("All functions", True), ("CNC & machining", True), ("Client view", True),
                        ("Full access", False), ("All functions", True)):
        workspaces.switch(crane, name)
        assert lock.keys_quiet() is quiet, name
        assert bpy.ops.fresing.blender_key.poll() is quiet, name
        assert bpy.ops.fresing.key_render.poll() is quiet, name
    workspaces.switch(crane, "All functions")


def test_a_swallowed_key_changes_nothing_and_says_how_to_get_it(crane):
    workspaces.switch(crane, "All functions")
    b = boom(crane)
    b.select_set(True)
    bpy.context.view_layer.objects.active = b
    before, kept = state(crane), lock.KEPT[0]
    steps = len(bpy.context.window_manager.operators)
    for _km, _sp, k, m, _w in lock.BLENDER_KEYS:
        assert bpy.ops.fresing.blender_key(key=lock.key_label(k, m)) == {"FINISHED"}
    assert lock.KEPT[0] - kept == len(lock.BLENDER_KEYS)
    assert state(crane) == before
    assert len(bpy.context.window_manager.operators) == steps          # no undo / redo step
    assert "Show all of Blender" in lock.KEY_MESSAGE
    assert "UNDO" not in lock.FRESING_OT_blender_key.bl_options


def test_the_client_view_keeps_its_own_message(crane):
    workspaces.switch(crane, "Client view")
    try:
        sw, kept = lock.SWALLOWED[0], lock.KEPT[0]
        assert bpy.ops.fresing.blender_key(key="Shift+D") == {"FINISHED"}
        assert lock.SWALLOWED[0] == sw + 1 and lock.KEPT[0] == kept
        assert bpy.ops.fresing.client_locked.poll()
    finally:
        workspaces.switch(crane, "All functions")
    assert not bpy.ops.fresing.client_locked.poll()


def test_ctrl_f12_without_an_animation_says_where_to_make_one(crane):
    workspaces.switch(crane, "All functions")
    assert len(crane.fresing.animations) == 0
    assert bpy.ops.fresing.key_render(animation=True) == {"CANCELLED"}


# --- the right-click menu ------------------------------------------------------------------------------------------

class Layout:
    """Records what a menu draws."""

    def __init__(self):
        self.items, self.operator_context = [], "INVOKE_REGION_WIN"

    def label(self, text="", icon="NONE"):
        self.items.append(("label", text))

    def separator(self, **_kw):
        pass

    def operator(self, idname, text="", icon="NONE"):
        self.items.append((idname, text))
        return type("Props", (), {})()


def drawn(scene):
    lay = Layout()
    context_menu._draw(type("Menu", (), {"layout": lay})(), bpy.context)
    return [t for kind, t in lay.items if kind != "label"], lay.items


def _right_click(scene, ob, point=(0.0, 0.0, 1.0)):
    context_menu.pick(bpy.context, (ob, 0, point, (0, 0, 1)) if ob is not None else None)


def test_the_menu_on_a_part_on_empty_space_and_in_the_client_view(crane):
    workspaces.switch(crane, "All functions")
    bpy.ops.fresing.ctx_show_all()
    from fresing_render.blender import copy
    copy.CLIP["names"] = []                                       # task 0293: Paste (here) once something was copied
    _right_click(crane, boom(crane))
    texts, items = drawn(crane)
    assert texts == [t for t in context_menu.ON_PART if t not in ("Show all", "Paste here")]
    target = context_menu.target_of(crane, boom(crane))         # as a left click: its subassembly by default
    assert items[0] == ("label", target.get(build.PROP_NAME)) and context_menu.HIT["target"] == target.name
    assert boom(crane).select_get() and bpy.context.view_layer.objects.active == boom(crane)
    _right_click(crane, None)
    assert drawn(crane)[0] == [t for t in context_menu.ON_EMPTY if t != "Paste"]
    copy.remember(crane, [target])
    _right_click(crane, boom(crane))
    assert drawn(crane)[0] == [t for t in context_menu.ON_PART if t != "Show all"]
    _right_click(crane, None)
    assert drawn(crane)[0] == list(context_menu.ON_EMPTY)
    copy.CLIP["names"] = []
    workspaces.switch(crane, "Client view")
    try:
        _right_click(crane, boom(crane))
        texts = drawn(crane)[0]
        assert texts == [t for t in context_menu.ON_PART if t not in context_menu.CLIENT_DROPS + ("Show all",)]
        assert not bpy.context.selected_objects                    # the lock: nothing is selected
    finally:
        workspaces.switch(crane, "All functions")


def test_full_access_draws_blenders_own_menu(crane):
    workspaces.switch(crane, "Full access")
    try:
        assert not lock.keys_quiet()
        assert not bpy.ops.fresing.view_menu.poll()
    finally:
        workspaces.switch(crane, "All functions")


def test_hide_show_only_and_show_all_on_the_part(crane):
    workspaces.switch(crane, "All functions")
    b = boom(crane)
    assert bpy.ops.fresing.ctx_hide(part=b.name) == {"FINISHED"}
    assert b.hide_get() and b.hide_render and b.get("fr_hidden")
    assert context_menu.anything_hidden(crane)
    assert bpy.ops.fresing.ctx_show_all() == {"FINISHED"}
    assert not b.hide_get() and not b.hide_render
    assert bpy.ops.fresing.ctx_only(part=b.name) == {"FINISHED"}
    others = [o for o in crane.objects if o.get(build.PROP_KIND) == "part" and o.name != b.name
              and o not in context_menu._subtree(crane, b)]
    assert others and all(o.hide_get() for o in others) and not b.hide_get()
    assert crane.fresing.isolated
    _right_click(crane, b)
    assert "Show all" in drawn(crane)[0]
    bpy.ops.fresing.ctx_show_all()
    assert not any(o.hide_get() for o in others) and not crane.fresing.isolated


def test_the_client_view_hides_in_the_view_only_and_shows_them_when_it_is_left(crane):
    workspaces.switch(crane, "Client view")
    b = boom(crane)
    try:
        assert bpy.ops.fresing.ctx_hide(part=b.name) == {"FINISHED"}
        assert b.hide_get() and not b.hide_render and not b.get("fr_hidden")      # renders and project unchanged
        assert bpy.ops.fresing.ctx_show_all() == {"FINISHED"}
        assert not b.hide_get()
        assert bpy.ops.fresing.ctx_only(part=b.name) == {"FINISHED"}
        hidden = [o for o in crane.objects if context_menu.CV_HIDE in o]
        assert hidden and all(o.hide_get() and not o.hide_render for o in hidden)
        assert not crane.fresing.isolated
        assert not bpy.ops.fresing.ctx_label.poll()                 # not in the Client view
        assert not bpy.ops.fresing.ctx_joint.poll()
    finally:
        workspaces.switch(crane, "All functions")
    assert not any(context_menu.CV_HIDE in o or o.hide_get() for o in hidden)   # back when the Client view is left


def test_add_a_label_here_points_at_the_clicked_spot(crane):
    workspaces.switch(crane, "All functions")
    b = boom(crane)
    n = len(crane.fresing.callouts)
    spot = b.matrix_world.translation + b.matrix_world.to_3x3().col[0] * 0.01
    assert bpy.ops.fresing.ctx_label(part=b.name, point=spot) == {"FINISHED"}
    assert len(crane.fresing.callouts) == n + 1
    c = crane.fresing.callouts[-1]
    assert c.part == b
    crane.fresing.callouts.remove(len(crane.fresing.callouts) - 1)


def test_the_menu_swap_keeps_other_add_ons_items():
    from fresing_render.blender import quiet
    cls = bpy.types.VIEW3D_MT_object_context_menu

    def other(self, context):
        pass

    cls.append(other)
    try:
        own = quiet._own(cls, quiet.draw_funcs(cls))
        assert own >= 0
        assert quiet.swap(cls, context_menu._draw)
        funcs = quiet.draw_funcs(cls)
        assert context_menu._draw in funcs and other in funcs
        quiet.unswap(cls)
        assert context_menu._draw not in quiet.draw_funcs(cls) and other in quiet.draw_funcs(cls)
    finally:
        quiet.unswap(cls)
        cls.remove(other)


def test_every_entry_has_a_tooltip():
    for cls in context_menu.CLASSES + (lock.FRESING_OT_blender_key, lock.FRESING_OT_key_render):
        doc = " ".join((cls.__doc__ or "").split())
        assert len(doc) > 40, cls.__name__
