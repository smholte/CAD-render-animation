"""Moving and turning with G / R / S (task 0307): why a move "jumped back" and what the app now says.

Here (Blender as a module, no window): what G / R would move, the reasons it cannot (locked in place, a built
animation, S on a part, the Client view's allow-list), the right-click menu's Unlock so it can move, and the keys bound to the
check. The keys pressed in a window (G, X, a number, Enter – the move stays; after Build the message):
tools/ui_test_move.py."""

import os
import types

import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import build, context_menu, lock, place, tour, workspaces  # noqa: E402

CRANE = os.path.join(os.path.dirname(__file__), "data", "test_crane_a.step")


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture()
def crane():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    assert bpy.ops.fresing.import_step(filepath=CRANE, quality="draft") == {"FINISHED"}
    scene = bpy.context.scene
    workspaces.switch(scene, "All functions")
    yield scene
    workspaces.switch(scene, "All functions")


def ob(scene, name):
    return next(o for o in scene.objects if o.get(build.PROP_NAME) == name)


def ctx(scene, *objs):
    return types.SimpleNamespace(scene=scene, selected_objects=list(objs))


def test_an_import_locks_everything_so_g_and_r_said_nothing_before(crane):
    """The owner's case: every subassembly and part is locked in place after an import, so Blender's G showed its
    numbers and moved nothing. Now the check names the subassembly and what to do."""
    asm, part = ob(crane, "BOOM.ASM"), ob(crane, "BOOM")
    assert all(asm.lock_location) and all(part.lock_rotation)
    for mode in ("TRANSLATE", "ROTATE"):
        msg, n = place.why_not(ctx(crane, asm, part), mode)
        assert n == 1 and "'BOOM.ASM' is locked in place" in msg and "Unlock so it can move" in msg, msg
        assert "2 Structure" in msg
    msg, _n = place.why_not(ctx(crane, part), "TRANSLATE")         # a part picked in 2 Structure: its subassembly
    assert "'BOOM.ASM'" in msg


def test_movers_are_the_top_of_the_selection(crane):
    asm, part, pin = ob(crane, "BOOM.ASM"), ob(crane, "BOOM"), ob(crane, "BOOM.PIN")
    assert place.movers(ctx(crane, asm, part, pin)) == [asm]
    assert place.movers(ctx(crane, part, pin)) == [part, pin]
    assert place.movers(ctx(crane)) == [] and place.why_not(ctx(crane), "TRANSLATE") == ("", 0)


def test_unlock_from_the_right_click_menu_lets_g_and_r_run(crane):
    part = ob(crane, "BOOM")
    asm = ob(crane, "BOOM.ASM")
    context_menu.pick(bpy.context, (part, 0, (0.0, 0.0, 1.0), (0, 0, 1)))
    assert place.menu_text(part) == "Unlock so it can move"
    assert bpy.ops.fresing.ctx_unlock(part=part.name) == {"FINISHED"}
    assert not any(asm.lock_location) and not any(part.lock_location) and not asm.get(build.PROP_LOCKED, True)
    assert place.why_not(ctx(crane, asm, part), "TRANSLATE") == ("", 0)
    assert place.why_not(ctx(crane, asm), "ROTATE") == ("", 0)
    assert place.menu_text(part) == "Lock in place"
    asm.location.x += 0.1                                   # what G does: it stays
    bpy.context.view_layer.update()
    assert abs(asm.location.x - 0.6) < 1e-6
    assert bpy.ops.fresing.ctx_unlock(part=part.name) == {"FINISHED"}      # again: locked in place
    assert all(asm.lock_location) and asm.get(build.PROP_LOCKED)
    other = ob(crane, "TROLLEY.ASM")                         # other subassemblies stay locked
    assert all(other.lock_location)


def test_s_never_scales_a_part(crane):
    bpy.ops.fresing.ctx_unlock(part="BOOM.ASM")
    msg, n = place.why_not(ctx(crane, ob(crane, "BOOM.ASM")), "RESIZE")
    assert n == 1 and "keep their size" in msg


def test_a_built_animation_says_stop_it_first(crane):
    """After Build & play a move was undone by the next Build or by Stop: G / R now say so at once."""
    bpy.ops.fresing.ctx_unlock(part="BOOM.ASM")
    tour._boom_joint(crane)
    b = types.SimpleNamespace(s=crane.fresing)
    a = tour._animation(b, "Up")
    tour._joint_step(a, "Boom", 0, 1, 20)
    crane.fresing.animations_index = len(crane.fresing.animations) - 1
    assert bpy.ops.fresing.anim_build() == {"FINISHED"}
    msg, n = place.why_not(ctx(crane, ob(crane, "BOOM.ASM")), "TRANSLATE")
    assert n == 1 and msg.startswith("The animation is built") and "4 Motion > Stop it to move joints by hand" in msg
    bpy.ops.fresing.anim_clear()
    assert place.why_not(ctx(crane, ob(crane, "BOOM.ASM")), "TRANSLATE") == ("", 0)


def test_the_client_view_keeps_g_off_its_allow_list(crane):
    """The Client view allows only viewing operators (task 0213's list); nothing can be selected there anyway."""
    assert not lock.allowed("fresing.move_key")


def test_g_r_s_are_bound_to_the_check_and_not_counted():
    from fresing_render.core import usage
    keys = {(k, kw.get("mode")) for km, _sp, k, _m, idname, kw in lock.APP_KEYS if idname == "fresing.move_key"}
    assert keys == {("G", "TRANSLATE"), ("R", "ROTATE"), ("S", "RESIZE")}
    assert "fresing.move_key" in usage.NOT_COUNTED
    assert "Unlock so it can move" in context_menu.ON_PART and "Unlock so it can move" in context_menu.CLIENT_DROPS
