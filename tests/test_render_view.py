"""Task 0308: Make – the large icons, the outputs strip of the output windows (switching), Blender's tabs hidden there,
and Render this view (the same picture as Render image from a camera at the same place; nothing left behind after a
render, an error or a cancel).

The fitting rule and the icon drawings are checked without Blender; the rest in Blender as a Python module (a 3D view
does not exist there: the view is a stand-in with the same matrices a real one has – the real app's test is
``tools/ui_test_left.py`` and the PC check's ``scene.render_view``).
"""

import math
import os
from types import SimpleNamespace

import numpy as np
import pytest

from fresing_render.core import make_icons, view_camera

HERE = os.path.dirname(__file__)
CRANE = os.path.join(HERE, "data", "test_crane_a.step")


# ---------------------------------------------------------------------------
# pure Python
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("view, aspect, want", [
    ((0.6, 0.3375), 16 / 9, (0.6, 0.3375)),        # the picture has the view's shape: exactly the view
    ((0.6, 0.45), 16 / 9, (0.8, 0.45)),            # a 4:3 view into a 16:9 picture: more at the sides
    ((0.6, 0.45), 1.0, (0.6, 0.6)),                # … into a square picture: more above and below
    ((0.6, 0.3375), 3 / 4, (0.6, 0.8)),            # a wide view into an upright picture: the width is kept
])
def test_the_picture_is_fitted_round_the_view(view, aspect, want):
    x, y = view_camera.fit_halves(*view, aspect)
    assert x == pytest.approx(want[0]) and y == pytest.approx(want[1])
    assert x >= view[0] - 1e-12 and y >= view[1] - 1e-12           # nothing of the view is cut off
    assert x / y == pytest.approx(aspect)


def test_the_camera_from_a_projection():
    tx, ty = math.tan(math.radians(30)), math.tan(math.radians(30)) * 9 / 16
    persp = view_camera.fit([[1 / tx, 0, 0, 0], [0, 1 / ty, 0, 0], [0, 0, -1, -0.2], [0, 0, -1, 0]], True, 1920, 1080)
    assert persp["type"] == "PERSP"
    assert persp["lens"] == pytest.approx(18 / tx)                  # 60° across a 36 mm sensor
    ortho = view_camera.fit([[2 / 8.0, 0, 0, 0], [0, 2 / 4.5, 0, 0], [0, 0, -0.01, 0], [0, 0, 0, 1]], False, 1920, 1080)
    assert ortho == {"type": "ORTHO", "ortho_scale": pytest.approx(8.0), "half": (pytest.approx(4.0),
                                                                                   pytest.approx(2.25))}
    with pytest.raises(ValueError):
        view_camera.fit([[0, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]], True, 10, 10)


@pytest.mark.parametrize("key", make_icons.KEYS)
def test_each_output_has_a_large_icon(key):
    coords, cols = make_icons.icon(key)
    n = len(coords) // 6
    assert n >= 4 and len(coords) == 6 * n and len(cols) == 12 * n
    for a, b, c, _col in make_icons.triangles(key):                  # the drawing stays on its grid: nothing clipped
        for x, y in (a, b, c):
            assert -0.5 <= x <= make_icons.SIZE + 0.5 and -0.5 <= y <= make_icons.SIZE + 0.5, (key, x, y)


def test_every_make_output_has_its_icon():
    from fresing_render.blender import ui_top
    assert [o[0] for o in ui_top.OUTPUTS] == list(make_icons.KEYS)


# ---------------------------------------------------------------------------
# Blender
# ---------------------------------------------------------------------------

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import ops_make, ops_render_view, ops_settings, ops_setup  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture()
def crane(tmp_path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path)
    assert bpy.ops.fresing.import_step(filepath=CRANE, quality="draft") == {"FINISHED"}
    s = sc.fresing
    s.out_format = "custom"
    s.out_custom_w, s.out_custom_h = 64, 36
    s.use_gpu = False
    s.quality = "draft"
    return sc


def _shot_camera(scene, lens=30.0):
    """A camera looking at the crane from the front corner – the 'Render image' side of the comparison."""
    data = bpy.data.cameras.new("Shot")
    data.sensor_fit, data.sensor_width, data.lens = "HORIZONTAL", 36.0, lens
    ob = bpy.data.objects.new("Shot", data)
    scene.collection.objects.link(ob)
    target = Vector((0.0, 0.0, 1.0))
    eye = Vector((9.0, -11.0, 6.0))
    rot = (target - eye).to_track_quat("-Z", "Y")
    ob.matrix_world = Matrix.LocRotScale(eye, rot, None)
    bpy.context.view_layer.update()
    return ob


def _view_like(cam, aspect, perspective=True, view_perspective="PERSP"):
    """A stand-in for a 3D view that looks exactly as ``cam`` does: its matrices as Blender gives them."""
    tx = cam.data.sensor_width / 2 / cam.data.lens
    ty = tx / aspect
    n, f = cam.data.clip_start, cam.data.clip_end
    if perspective:
        win = Matrix(((1 / tx, 0, 0, 0), (0, 1 / ty, 0, 0), (0, 0, -(f + n) / (f - n), -2 * f * n / (f - n)),
                      (0, 0, -1, 0)))
    else:
        win = Matrix(((2 / 8.0, 0, 0, 0), (0, 2 / (8.0 / aspect), 0, 0), (0, 0, -1 / f, 0), (0, 0, 0, 1)))
    rv3d = SimpleNamespace(view_matrix=cam.matrix_world.inverted(), window_matrix=win, is_perspective=perspective,
                           view_perspective=view_perspective)
    space = SimpleNamespace(clip_start=n, clip_end=f, camera=None, use_local_camera=False, region_3d=rv3d)
    area = SimpleNamespace(type="VIEW_3D", spaces=SimpleNamespace(active=space), regions=())
    return area, rv3d


@pytest.fixture()
def view(monkeypatch):
    holder = {}
    monkeypatch.setattr(ops_render_view, "the_view", lambda context: (holder["area"], None, holder["rv3d"]))
    return holder


def _pixels(path):
    img = bpy.data.images.load(path)
    px = np.empty(img.size[0] * img.size[1] * 4, np.float32)
    img.pixels.foreach_get(px)
    size = tuple(img.size)
    bpy.data.images.remove(img)
    return px.reshape(size[1], size[0], 4), size


def _things(scene):
    return (scene.camera, sorted(o.name for o in bpy.data.objects), sorted(c.name for c in bpy.data.cameras))


def test_render_this_view_gives_the_picture_of_a_camera_at_the_same_place(crane, view):
    scene, s = crane, crane.fresing
    shot = _shot_camera(scene)
    scene.camera = shot
    assert bpy.ops.fresing.render() == {"FINISHED"}
    by_camera = s.last_render
    other = bpy.data.objects.new("Other camera", bpy.data.cameras.new("Other camera"))
    scene.collection.objects.link(other)
    scene.camera = other                                     # the active camera is another one: it must stay so
    view["area"], view["rv3d"] = _view_like(shot, 64 / 36)
    before = _things(scene)
    assert bpy.ops.fresing.render_view() == {"FINISHED"}
    assert "_View_" in os.path.basename(s.last_render) and s.last_render != by_camera
    assert _things(scene) == before                          # the camera back, no camera made is left
    a, size = _pixels(by_camera)
    b, size_b = _pixels(s.last_render)
    assert size == size_b == (32, 18)                        # the Picture's size (draft: half)
    assert a[:, :, :3].std() > 0.02, "the crane must be in the picture"
    assert np.abs(a - b).max() < 0.02, np.abs(a - b).max()


def test_a_wider_picture_shows_more_at_the_sides(crane, view):
    """A 4:3 view into the 16:9 Picture: the camera is wider than the view – nothing it shows is cut off."""
    shot = _shot_camera(crane)
    area, rv3d = _view_like(shot, 4 / 3)
    ob = bpy.data.objects.new("probe", bpy.data.cameras.new("probe"))
    crane.collection.objects.link(ob)
    spec = ops_render_view.place_camera(ob, area.spaces.active, rv3d, 64, 36)
    tx_view = 18 / 30
    assert spec["tan"][0] == pytest.approx(tx_view * (16 / 9) / (4 / 3))
    assert spec["tan"][1] == pytest.approx(tx_view / (4 / 3))
    assert ob.data.lens == pytest.approx(18 / spec["tan"][0])
    assert (ob.matrix_world.translation - shot.matrix_world.translation).length < 1e-5


def test_an_orthographic_view_stands_back_by_half_the_clip(crane):
    shot = _shot_camera(crane)
    area, rv3d = _view_like(shot, 64 / 36, perspective=False)
    ob = bpy.data.objects.new("probe", bpy.data.cameras.new("probe"))
    crane.collection.objects.link(ob)
    spec = ops_render_view.place_camera(ob, area.spaces.active, rv3d, 64, 36)
    assert ob.data.type == "ORTHO" and ob.data.ortho_scale == pytest.approx(8.0) and spec["type"] == "ORTHO"
    back = ob.matrix_world.translation - shot.matrix_world.translation
    fwd = shot.matrix_world.to_quaternion() @ Vector((0, 0, -1))
    assert back.length == pytest.approx(shot.data.clip_end / 2, rel=1e-4)
    assert back.normalized().dot(fwd) == pytest.approx(-1.0, abs=1e-5)
    assert ob.data.clip_end == pytest.approx(shot.data.clip_end)


def test_camera_view_renders_that_camera_and_makes_none(crane, view):
    shot = _shot_camera(crane)
    other = bpy.data.objects.new("Other camera", bpy.data.cameras.new("Other camera"))
    crane.collection.objects.link(other)
    crane.camera = other
    area, rv3d = _view_like(shot, 64 / 36, view_perspective="CAMERA")
    area.spaces.active.use_local_camera, area.spaces.active.camera = True, shot
    view["area"], view["rv3d"] = area, rv3d
    before = _things(crane)
    assert bpy.ops.fresing.render_view() == {"FINISHED"}
    assert _things(crane) == before


def test_an_error_leaves_nothing_behind(crane, view, monkeypatch):
    shot = _shot_camera(crane)
    crane.camera = shot
    view["area"], view["rv3d"] = _view_like(shot, 64 / 36)
    before = _things(crane)

    def fails(*_a, **_k):
        raise RuntimeError("the render broke")

    from fresing_render.blender import render
    monkeypatch.setattr(render, "render_still", fails)
    with pytest.raises(RuntimeError):
        bpy.ops.fresing.render_view()
    assert _things(crane) == before
    monkeypatch.setattr(ops_render_view, "place_camera", fails)       # … and while the camera is placed
    with pytest.raises(RuntimeError):
        ops_render_view.setup(crane, bpy.context)
    assert _things(crane) == before


def test_cancel_leaves_nothing_behind(crane, view):
    """What the operator's cancel (and a cancelled render) does: the camera made is gone, the scene's is back."""
    shot = _shot_camera(crane)
    crane.camera = shot
    view["area"], view["rv3d"] = _view_like(shot, 64 / 36)
    before = _things(crane)
    state = ops_render_view.setup(crane, bpy.context)
    assert crane.camera.name.startswith(ops_render_view.TEMP_NAME) and crane.camera.get(ops_render_view.VIEW_MARK)
    op = SimpleNamespace(_state=state)
    ops_render_view.FRESING_OT_render_view._done(op, SimpleNamespace(scene=crane))
    assert _things(crane) == before
    ops_render_view.undo(crane, state)                                 # twice is harmless
    assert _things(crane) == before


def test_a_leftover_view_camera_is_removed(crane):
    data = bpy.data.cameras.new(ops_render_view.TEMP_NAME)
    ob = bpy.data.objects.new(ops_render_view.TEMP_NAME, data)
    ob[ops_render_view.VIEW_MARK] = 1
    crane.collection.objects.link(ob)
    crane.camera = ob
    assert ops_render_view.remove_leftovers(crane) == 1
    assert crane.camera is None and not [o for o in bpy.data.objects if o.get(ops_render_view.VIEW_MARK)]


def test_refused_while_a_long_job_or_the_queue_runs(crane, view, monkeypatch):
    from fresing_render.blender import queue
    shot = _shot_camera(crane)
    crane.camera = shot
    view["area"], view["rv3d"] = _view_like(shot, 64 / 36)
    before = _things(crane)
    monkeypatch.setattr(queue, "busy_job", lambda scene: "Clash check")
    assert "Clash check is running" in ops_render_view.busy_line(crane)
    assert bpy.ops.fresing.render_view() == {"CANCELLED"}
    monkeypatch.setattr(queue, "busy_job", lambda scene: "")
    monkeypatch.setattr(queue, "is_running", lambda scene: True)
    assert "render queue is running" in ops_render_view.busy_line(crane)
    assert _things(crane) == before


def test_without_a_3d_view_it_says_so(crane, monkeypatch):
    shot = _shot_camera(crane)
    crane.camera = shot
    monkeypatch.setattr(ops_setup, "main_view", lambda context=None: (None, None, None))
    before = _things(crane)
    with pytest.raises(RuntimeError, match="needs a 3D view"):        # the plain line the user sees
        bpy.ops.fresing.render_view()
    assert _things(crane) == before


# ----- the outputs strip -----

class _Screen(dict):
    areas = ()


def _window(key):
    return SimpleNamespace(screen=_Screen({ops_setup.OUTPUT_MARK: key}), width=340, height=560)


def test_the_strip_switches_its_window(monkeypatch):
    win, other = _window("still"), _window("queue")
    monkeypatch.setattr(ops_make, "output_windows", lambda key=None: [w for w in (win, other)
                                                                        if key is None or w.screen[ops_setup.OUTPUT_MARK] == key])
    monkeypatch.setattr(ops_make, "remember", lambda w: None)
    assert ops_make.switch(win, "web") == ""
    assert win.screen[ops_setup.OUTPUT_MARK] == "web"
    assert ops_make.switch(win, "web") == ""                           # already showing it
    assert "open already" in ops_make.switch(win, "queue")            # another window shows it: that one comes up
    assert win.screen[ops_setup.OUTPUT_MARK] == "web"
    assert "No output" in ops_make.switch(win, "nothing")
    assert "no output window" in ops_make.switch(SimpleNamespace(screen=_Screen()), "still")


def test_the_window_handle_follows_the_output():
    from fresing_render import winplace
    winplace._HWND.clear()
    winplace._HWND["still"] = 1234
    winplace.rekey("still", "web")
    assert winplace._HWND == {"web": 1234}
    winplace.rekey("anim", "turn")                                     # no handle kept: nothing happens
    assert winplace._HWND == {"web": 1234}
    winplace._HWND.clear()


def test_the_strip_panel_shows_only_in_output_windows():
    strip = bpy.types.FRESING_PT_make_strip
    assert strip.poll(SimpleNamespace(window=_window("still")))
    assert not strip.poll(SimpleNamespace(window=SimpleNamespace(screen=_Screen())))
    assert not strip.poll(SimpleNamespace(window=None))


def test_blenders_tabs_and_tools_hide_in_output_windows():
    """Blender's own panels of the tabs Item, Tool, View, Animation (and its tool buttons) do not show in an output
    window; their sub-panels are registered again under them; elsewhere they ask their own poll as before."""
    tabs = ops_settings.tab_panels()
    assert {c.bl_category for c in tabs} >= {"Tool", "View"}
    out = SimpleNamespace(window=_window("still"))
    for cls in tabs + [bpy.types.VIEW3D_PT_tools_active]:
        assert cls.__name__ in ops_settings._QUIET, cls.__name__
        assert cls.poll(out) is False, cls.__name__
        for kid in ops_settings._QUIET[cls.__name__][2]:
            assert kid.is_registered, kid.__name__
    props = bpy.types.VIEW3D_PT_view3d_properties             # no poll of its own: shows anywhere else
    assert props.poll(SimpleNamespace(window=None)) is True


def test_the_large_icons_are_made():
    from fresing_render.blender import make_icons as icons
    assert all(icons.icon_id(k) > 0 for k in make_icons.KEYS)
    assert icons.icon_id("nothing") == 0
