"""The quick unlock popup and the Lock it again popup (task 0338).

Here (Blender as a module, no window): who the popup unlocks, that Lock it again comes only after a confirmed move of
what the popup unlocked (not after a cancel, not for something unlocked in 2 Structure), one popup for a second move,
another unlock replaces it, Lock it again locks exactly that, the 5 seconds, where the cards sit (by the mouse, inside
the view; top left below the view's text, right of a toolbar lying over the view, at a 2x scale), the hit test, and
that a built animation, S and the Client view open no popup. The clicks in a window: tools/ui_test_move.py."""

import os
import types

import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from mathutils import Matrix  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import build, lock, ops_place, place, place_popups as pp, tour, workspaces  # noqa: E402

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
    pp.close()
    pp.PENDING["owners"] = []
    yield scene
    pp.close()
    workspaces.switch(scene, "All functions")


def ob(scene, name):
    return next(o for o in scene.objects if o.get(build.PROP_NAME) == name)


def ctx(scene, *objs):
    return types.SimpleNamespace(scene=scene, selected_objects=list(objs), active_object=objs[0] if objs else None)


def test_the_popup_unlocks_what_holds_the_move(crane):
    asm, part, trolley = ob(crane, "BOOM.ASM"), ob(crane, "BOOM"), ob(crane, "TROLLEY.ASM")
    c = ctx(crane, part)                                        # a part picked: its subassembly holds it
    assert pp.held_owners(c, "TRANSLATE") == [asm.name]
    assert pp.held_owners(ctx(crane, asm, trolley), "ROTATE") == [asm.name, trolley.name]
    assert pp.unlock(c, [asm.name], "TRANSLATE") == [asm.name]
    assert not any(asm.lock_location) and not any(asm.lock_rotation) and not any(part.lock_location)
    assert all(trolley.lock_location)                          # only what held it
    assert pp.held_owners(c, "TRANSLATE") == []
    assert "Unlock in the popup" not in place.LAST[0] and "unlocked" in place.LAST[0]


def test_lock_it_again_only_after_a_confirmed_move_of_what_it_unlocked(crane):
    asm, trolley = ob(crane, "BOOM.ASM"), ob(crane, "TROLLEY.ASM")
    c = ctx(crane, asm)
    pp.unlock(c, [asm.name], "TRANSLATE")
    assert not pp.after_move([asm.name], moved=False)          # cancelled: no popup, and none later
    assert not pp.AGAIN["on"] and not pp.after_move([asm.name])
    ops_place.set_lock(trolley, False)                         # unlocked in 2 Structure: never a popup
    assert not pp.after_move([trolley.name]) and not pp.AGAIN["on"]
    ops_place.set_lock(asm, True)
    pp.unlock(c, [asm.name], "TRANSLATE")
    assert not pp.after_move([trolley.name])                   # something else moved
    assert pp.after_move([ob(crane, "BOOM").name])             # a part of it moved (Blender moved the part)
    assert pp.AGAIN["on"] and pp.AGAIN["owners"] == [asm.name]
    shown = pp.SHOWN[1]
    assert not pp.after_move([asm.name]) and pp.SHOWN[1] == shown   # a second move: still one popup
    assert pp.lock_again() == [asm.name]
    assert all(asm.lock_location) and all(asm.lock_rotation) and asm.get(build.PROP_LOCKED)
    assert not all(trolley.lock_location)                      # exactly what the popup unlocked
    assert not pp.AGAIN["on"] and "locked in place again" in place.LAST[0]


def test_unlocking_something_else_replaces_the_popup(crane):
    asm, trolley = ob(crane, "BOOM.ASM"), ob(crane, "TROLLEY.ASM")
    pp.unlock(ctx(crane, asm), [asm.name], "TRANSLATE")
    pp.after_move([asm.name])
    assert pp.AGAIN["owners"] == [asm.name]
    pp.unlock(ctx(crane, trolley), [trolley.name], "ROTATE")
    assert not pp.AGAIN["on"]
    pp.after_move([trolley.name])
    assert pp.AGAIN["owners"] == [trolley.name]


def test_place_moves_bring_the_lock_it_again_popup(crane):
    """Move / turn… (the window) and Place's steps end in place.apply: that is where the popup comes."""
    asm = ob(crane, "BOOM.ASM")
    bpy.context.view_layer.objects.active = asm
    for o in crane.objects:
        o.select_set(o == asm)
    pp.unlock(bpy.context, [asm.name], "WINDOW")
    assert not pp.AGAIN["on"]
    place.apply(bpy.context, Matrix.Translation((0.1, 0.0, 0.0)))
    assert pp.AGAIN["on"] and pp.AGAIN["owners"] == [asm.name]


def test_five_seconds_before_a_click_closes_it(crane):
    asm = ob(crane, "BOOM.ASM")
    pp.unlock(ctx(crane, asm), [asm.name], "TRANSLATE")
    pp.after_move([asm.name])
    t = pp.AGAIN["since"]
    assert not pp.can_close_by_click(t + 4.9) and pp.can_close_by_click(t + 5.0)
    assert pp.STAY >= 5.0


def test_no_popup_for_s_a_built_animation_or_the_client_view(crane):
    asm = ob(crane, "BOOM.ASM")
    for o in crane.objects:
        o.select_set(o == asm)
    shown = pp.SHOWN[0]
    assert not place.popup(bpy.context, "RESIZE")
    lock.ON[0] = True
    try:
        assert not place.popup(bpy.context, "TRANSLATE")
    finally:
        lock.ON[0] = False
    ops_place.set_lock(asm, False)
    tour._boom_joint(crane)
    a = tour._animation(types.SimpleNamespace(s=crane.fresing), "Up")
    tour._joint_step(a, "Boom", 0, 1, 20)
    crane.fresing.animations_index = len(crane.fresing.animations) - 1
    assert bpy.ops.fresing.anim_build() == {"FINISHED"}
    ops_place.set_lock(asm, True)
    assert not place.popup(bpy.context, "TRANSLATE")
    msg, _n = place.why_not(ctx(crane, asm), "TRANSLATE")
    assert msg.startswith("The animation is built")            # its own message stays
    bpy.ops.fresing.anim_clear()
    assert pp.SHOWN[0] == shown


def test_the_status_line_says_the_popup_too(crane):
    msg, _n = place.why_not(ctx(crane, ob(crane, "BOOM.ASM")), "TRANSLATE")
    assert "click Unlock in the popup" in msg and "Unlock so it can move" in msg


# --- where the cards are --------------------------------------------------------------------------------------------

class R(types.SimpleNamespace):
    pass


def _area(header_over=False, tools_w=0, stats=False, text=True):
    win = R(type="WINDOW", x=0, y=0, width=1600, height=1000, alignment="NONE")
    regs = [win, R(type="HEADER", x=0, y=1000 if not header_over else 974, width=1600, height=26, alignment="TOP")]
    if tools_w:
        regs.append(R(type="TOOLS", x=0, y=0, width=tools_w, height=1000, alignment="LEFT"))
    ov = R(show_stats=stats, show_text=text)
    return R(regions=regs, spaces=R(active=R(overlay=ov))), win


@pytest.mark.parametrize("s", [1.0, 2.0])
def test_lock_it_again_sits_top_left_below_the_views_text(crane, s):
    names = [ob(crane, "BOOM.ASM").name]
    area, win = _area()
    c = pp.again_card(area, win, names, s)
    x, y, w, h = c["box"]
    assert x < 20 * s + 1 and y + h <= win.height - (14 + 3 * 19) * s + 1e-6      # below 3 lines of view text
    assert y > win.height / 2                                                    # still near the top
    same = pp.again_card(area, win, names, s)
    assert same["box"] == c["box"]                                               # same place every time
    area2, win2 = _area(header_over=True, tools_w=300, stats=True)
    c2 = pp.again_card(area2, win2, names, s)
    assert c2["box"][0] >= 300 and c2["box"][1] + c2["box"][3] <= 974 - (14 + 12 * 19) * s + 1e-6


@pytest.mark.parametrize("s", [1.0, 2.0])
def test_unlock_sits_by_the_mouse_inside_the_view(crane, s):
    names = [ob(crane, "BOOM.ASM").name]
    _a, win = _area()
    c = pp.unlock_card(win, (800, 500), names, s)
    x, y, w, h = c["box"]
    assert abs(x - (800 + 14 * s)) < 1e-6 and y < 500 + 60 * s and y + h > 500     # beside the pointer
    for at in ((1590, 995), (2, 2)):                                               # at the edges: inside the view
        x, y, w, h = pp.unlock_card(win, at, names, s)["box"]
        assert 0 <= x and x + w <= win.width and 0 <= y and y + h <= win.height
    assert pp.hit(c, *(c["button"][0] + 2, c["button"][1] + 2)) == "button"
    assert pp.hit(c, *(c["x"][0] + 2, c["x"][1] + 2)) == "x"
    assert pp.hit(c, c["box"][0] + c["box"][2] - 2, c["box"][1] + 2) == "card"
    assert pp.hit(c, 10, 10) == ""


def test_tooltips():
    assert pp.UNLOCK_TIP == "Unlock it so it can move. You can lock it again afterwards"
    assert bpy.ops.fresing.unlock_popup.get_rna_type().description
    assert bpy.ops.fresing.lock_again.get_rna_type().description
