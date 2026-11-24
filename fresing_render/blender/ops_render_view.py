"""Render this view (task 0308): a picture of exactly what the 3D view shows, without adding or picking a camera.

The button sits under Make (and in the 3D view header's Make list). It renders like Render image – Cycles, the
Picture's format, size, quality, file type, background and folder, the result shown the same way – through a camera
made for this one render:

- **a normal view** (perspective or orthographic): a temporary camera at the view's eye, looking the same way, as wide
  as the view (``core/view_camera.fit``: the picture's shape is fitted round the view, so nothing it shows is cut
  off);
- **camera view** (Numpad 0): the camera the view looks through (the view's own local camera, else the scene's).

The scene's active camera is put back afterwards and the temporary camera deleted with its data – after the render,
when it is cancelled, when it fails and when the operator is stopped (``cancel``). Nothing else changes: the saved
cameras, the animations and their cameras are not touched. The file is called ``<project>_View_<date>_<time>``.

Refused, with one plain line, while a render, the render queue or a long job (House bake, web 3D export, clash check,
cable re-bake) runs.
"""

from __future__ import annotations

import bpy
from bpy.app.handlers import persistent
from mathutils import Matrix, Vector

from ..core import view_camera
from . import ops_main, ops_setup, render

TEMP_NAME = "FR view camera (temporary)"
VIEW_MARK = "fr_view_camera"            # on the temporary camera object: a leftover is found and removed


def busy_line(scene) -> str:
    """Why Render this view cannot start now ("" when it can)."""
    from . import queue
    if bpy.app.is_job_running("RENDER"):
        return "A render is already running: wait for it, then press Render this view again"
    job = queue.busy_job(scene)
    if job:
        return f"The {job} is running: Render this view when it is done (or Cancel it first)"
    try:
        if queue.is_running(scene):
            return "The render queue is running: Render this view when it is done (or stop the queue first)"
    except Exception:  # noqa: BLE001
        pass
    return ""


def the_view(context):
    """(area, region, RegionView3D) of the 3D view the user looks at: the main window's biggest 3D view – also when the
    button was pressed in an output window or the header's Make list. (None, None, None) without one."""
    _win, area, region = ops_setup.main_view(context)
    if area is None or area.type != "VIEW_3D":
        return None, None, None
    rv3d = area.spaces.active.region_3d
    if region is None or region.type != "WINDOW":
        region = next((r for r in area.regions if r.type == "WINDOW"), None)
    return area, region, rv3d


def picture_size(scene) -> tuple:
    r = scene.render
    return max(1, r.resolution_x * r.resolution_percentage // 100), max(1, r.resolution_y * r.resolution_percentage // 100)


def place_camera(cam_ob, space, rv3d, width: int, height: int) -> dict:
    """Put ``cam_ob`` (a camera object) where the view's eye is, as wide as the view (the picture fitted round it)."""
    eye = rv3d.view_matrix.inverted()
    loc, rot, _scale = eye.decompose()
    persp = rv3d.is_perspective
    spec = view_camera.fit([list(row) for row in rv3d.window_matrix], persp, width, height)
    cam = cam_ob.data
    cam.sensor_fit = "HORIZONTAL"
    cam.sensor_width = view_camera.SENSOR
    cam.shift_x = cam.shift_y = 0.0
    if persp:
        cam.type = "PERSP"
        cam.lens = spec["lens"]
        cam.clip_start = space.clip_start
        cam.clip_end = space.clip_end
    else:
        cam.type = "ORTHO"
        cam.ortho_scale = spec["ortho_scale"]
        back = view_camera.ortho_back(space.clip_end)
        loc = loc + rot @ Vector((0.0, 0.0, back))          # the camera looks along its -Z: back = +Z
        cam.clip_start = 0.001
        cam.clip_end = 2.0 * back
    cam_ob.matrix_world = Matrix.LocRotScale(loc, rot, None)
    return spec


def stand_in(cam_ob, aspect: float):
    """(area, rv3d) – a stand-in for a 3D view that looks exactly as perspective camera ``cam_ob`` (its sensor fitted to
    the width, as the app's cameras of a wide picture are) does, with the matrices Blender gives a real view (the PC check and the tests compare Render this view with Render image through it)."""
    from types import SimpleNamespace
    data = cam_ob.data
    tx = data.sensor_width / 2 / data.lens
    ty = tx / aspect
    n, f = data.clip_start, data.clip_end
    win = Matrix(((1 / tx, 0, 0, 0), (0, 1 / ty, 0, 0), (0, 0, -(f + n) / (f - n), -2 * f * n / (f - n)),
                  (0, 0, -1, 0)))
    rv3d = SimpleNamespace(view_matrix=cam_ob.matrix_world.inverted(), window_matrix=win, is_perspective=True,
                           view_perspective="PERSP")
    space = SimpleNamespace(clip_start=n, clip_end=f, camera=None, use_local_camera=False, region_3d=rv3d)
    return SimpleNamespace(type="VIEW_3D", spaces=SimpleNamespace(active=space), regions=()), rv3d


def setup(scene, context, view=None) -> dict:
    """Make the scene render what the view shows (``view`` = (area, rv3d), else the main 3D view). Returns what
    ``undo`` needs; raises RuntimeError with a plain line."""
    if view is not None:
        area, rv3d = view
    else:
        area, _region, rv3d = the_view(context)
    if rv3d is None:
        raise RuntimeError("Render this view needs a 3D view in the main window")
    space = area.spaces.active
    state = {"camera": scene.camera.name if scene.camera else "", "made": ""}
    if rv3d.view_perspective == "CAMERA":
        cam = space.camera if (space.use_local_camera and space.camera) else scene.camera
        if cam is None or cam.type != "CAMERA":
            raise RuntimeError("The view looks through no camera: leave camera view (View > Cameras) and press again")
        if scene.camera != cam:
            scene.camera = cam
        state["kind"] = "camera " + cam.name
        return state
    remove_leftovers(scene)
    data = bpy.data.cameras.new(TEMP_NAME)
    ob = bpy.data.objects.new(TEMP_NAME, data)
    ob[VIEW_MARK] = 1
    ob.hide_select = True
    scene.collection.objects.link(ob)
    state["made"] = ob.name
    try:
        spec = place_camera(ob, space, rv3d, *picture_size(scene))
    except Exception:
        undo(scene, state)
        raise
    state["kind"] = "perspective" if spec["type"] == "PERSP" else "orthographic"
    scene.camera = ob
    return state


def undo(scene, state: dict) -> None:
    """The scene's camera back, the temporary camera gone (safe to call twice)."""
    if not state:
        return
    old = bpy.data.objects.get(state.get("camera", "")) if state.get("camera") else None
    try:
        if scene.camera != old:
            scene.camera = old
    except ReferenceError:
        pass
    made = state.get("made")
    if made:
        ob = bpy.data.objects.get(made)
        if ob is not None and ob.get(VIEW_MARK):
            data = ob.data
            bpy.data.objects.remove(ob, do_unlink=True)
            if data is not None and data.users == 0:
                bpy.data.cameras.remove(data)
    state.clear()


def remove_leftovers(scene=None) -> int:
    """Temporary view cameras left by a crash: removed (at a load, and before a new one is made)."""
    n = 0
    for ob in [o for o in bpy.data.objects if o.get(VIEW_MARK)]:
        data = ob.data
        if scene is not None and scene.camera == ob:
            scene.camera = None
        bpy.data.objects.remove(ob, do_unlink=True)
        if data is not None and data.users == 0:
            bpy.data.cameras.remove(data)
        n += 1
    return n


@persistent
def _on_load(_dummy=None):
    try:
        remove_leftovers(bpy.context.scene)
    except Exception as exc:  # noqa: BLE001
        print("Fresing Render: a temporary view camera was left:", exc)


class FRESING_OT_render_view(ops_main.RenderStill, bpy.types.Operator):
    """Renders exactly what the 3D view shows now – its angle and zoom – without adding or picking a camera. Uses the
    Picture's size, shape, quality and file type and saves it like Render image (its name ends in _View and the date
    and time). In camera view it renders that camera"""

    bl_idname = "fresing.render_view"
    bl_label = "Render this view"

    _view_path = ""
    _state = None

    @classmethod
    def register(cls):
        if _on_load not in bpy.app.handlers.load_post:
            bpy.app.handlers.load_post.append(_on_load)

    @classmethod
    def unregister(cls):
        while _on_load in bpy.app.handlers.load_post:
            bpy.app.handlers.load_post.remove(_on_load)

    def _file(self, scene, s):
        if not self._view_path:
            self._view_path = render.view_output_path(scene, s)
        return self._view_path

    def _done(self, context) -> None:
        undo(context.scene, self._state or {})
        self._state = None

    def execute(self, context):
        scene = context.scene
        line = busy_line(scene)
        if line:
            self.report({"WARNING"}, line)
            return {"CANCELLED"}
        try:
            self._state = setup(scene, context)
        except RuntimeError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        self._view_path = ""
        try:
            result = super().execute(context)
        except Exception:
            self._done(context)
            raise
        if "RUNNING_MODAL" not in result:
            self._done(context)
        return result

    def modal(self, context, event):
        try:
            result = super().modal(context, event)
        except Exception:
            self._done(context)
            raise
        if "FINISHED" in result or "CANCELLED" in result:
            self._done(context)
        return result

    def cancel(self, context):
        self._done(context)


CLASSES = (FRESING_OT_render_view,)
