"""2 Structure > Place (task 0292): X / Y / Z and turns of what is selected, steps, snap, move and turn with the mouse,
the arrows and rings (a gizmo while Place is open), Put on the floor, Back to the CAD place, Remove…. The same body
draws in the right-click menu's Move / turn… window (``draw_place(window=True)``)."""

from __future__ import annotations

import math

import bpy
from mathutils import Matrix, Vector

from ..core import place as core
from . import build, panels, place
from .ui import _Panel, gap, header_status, hint, missing, steps

PANEL = "FRESING_PT_place"


def _axis_row(col, st, prop: str, index: int, enabled: bool) -> None:
    row = col.row(align=True)
    row.enabled = enabled
    op = row.operator("fresing.place_step", text="", icon="REMOVE")
    op.index, op.sign = index, -1
    row.prop(st, prop)
    op = row.operator("fresing.place_step", text="", icon="ADD")
    op.index, op.sign = index, 1


def draw_place(layout, context, window: bool = False) -> None:
    from . import lock
    scene = context.scene
    st = scene.fresing.place
    if lock.ON[0]:
        missing(layout, context, lock.MESSAGE, icon="LOCKED")
        return
    ob = place.target(context)
    if ob is None:
        missing(layout, context, "Select a model, subassembly or part: click it in the view or a row of "
                                 "2 Structure")
        return
    objs = place.movers(context)
    is_locked = place.locked(ob)
    row = layout.row(align=True)
    name = ob.get(build.PROP_NAME, ob.name) + (f"  +{len(objs) - 1}" if len(objs) > 1 else "")
    row.label(text=name, icon="OUTLINER_COLLECTION" if place.is_root(ob) else
              ("FILE_FOLDER" if ob.get(build.PROP_KIND) == "assembly" else "MESH_CUBE"))
    row.operator("fresing.place_lock", text="Locked" if is_locked else "Free", icon="LOCKED" if is_locked
                 else "UNLOCKED", depress=is_locked).name = ob.name
    if is_locked:
        hint(layout, context, "Locked in place: click the lock to move it on its own (it still moves with "
                              "its subassembly and its joints).")
    from . import animation
    if animation.has_keys(scene):
        hint(layout, context, "The animation is built: a move takes it off (Build again after).")
    gap(layout)
    layout.row().prop(st, "space", expand=True)
    col = layout.column(align=True)
    col.label(text="Position (mm)")
    for i, p in enumerate(("x", "y", "z")):
        _axis_row(col, st, p, i, not is_locked)
    col.separator()
    col.label(text="Turn (°)")
    for i, p in enumerate(("rx", "ry", "rz")):
        _axis_row(col, st, p, 3 + i, not is_locked)
    grid = layout.grid_flow(columns=2, even_columns=True, align=True)
    grid.label(text="Step")
    grid.label(text="Snap")
    grid.prop(st, "step_move", text="")
    grid.prop(st, "snap_move", text="")
    grid.prop(st, "step_turn", text="")
    grid.prop(st, "snap_turn", text="")
    gap(layout)
    row = layout.row(align=True)
    row.enabled = not is_locked
    row.operator_context = "INVOKE_DEFAULT"
    row.operator("fresing.place_mouse", text="Move with mouse", icon="ORIENTATION_VIEW").mode = "MOVE"
    row.operator("fresing.place_mouse", text="Turn with mouse", icon="ORIENTATION_GIMBAL").mode = "TURN"
    if not window:
        layout.prop(st, "arrows", icon="EMPTY_ARROWS")
    gap(layout)
    col = layout.column(align=True)
    col.enabled = not is_locked
    col.operator("fresing.place_floor", text="Put on the floor", icon="TRIA_DOWN_BAR")
    if place.is_root(ob):
        col.operator("fresing.place_back", text="Back to where it was imported", icon="LOOP_BACK")
    else:
        col.operator("fresing.place_back", text="Back to the CAD place", icon="LOOP_BACK")
    if not window:
        gap(layout)
        layout.operator("fresing.remove", text="Remove…", icon="TRASH")


class FRESING_PT_place(_Panel, bpy.types.Panel):
    bl_label = "Place"
    bl_parent_id = "FRESING_PT_structure"
    bl_options = {"DEFAULT_CLOSED"}

    def draw_header(self, context):
        self.layout.label(icon="OBJECT_ORIGIN")

    def draw_header_preset(self, context):
        header_status(self.layout, place.state(context.scene))

    def draw(self, context):
        steps(self.layout, context, ["Select a model, subassembly or part (click it, or a row above)",
                                     "Type X / Y / Z or a turn, use – / +, or drag the arrows and rings",
                                     "It stays there: Build, poses and model updates keep it"],
              key="fr_how_place", used=any(place.is_placed(o) for o in build.model_roots(context.scene)))
        draw_place(self.layout, context)


# ---------------------------------------------------------------------------
# the arrows and rings (a gizmo while Place is open)
# ---------------------------------------------------------------------------

_DRAG = {"acc": [0.0] * 6, "busy": False, "pivot": None, "key": None, "undo": False, "scale": 1.0}
COLOURS = ((0.9, 0.25, 0.25), (0.35, 0.8, 0.3), (0.3, 0.5, 0.95))


def place_open() -> bool:
    """Is Place showing (its sub-panel open in the side panel, or the Move / turn… window open)?"""
    from . import form_window
    try:
        if form_window.is_open("fresing.place_window"):
            return True
    except Exception:  # noqa: BLE001
        pass
    return panels.is_open(PANEL) and panels.is_open("FRESING_PT_structure")


def _wanted(context) -> bool:
    from . import animation
    scene = getattr(context, "scene", None)
    if scene is None or getattr(scene, "fresing", None) is None or context.mode != "OBJECT":
        return False
    if not scene.fresing.place.arrows or not place_open():
        return False
    if animation.has_keys(scene):
        return False
    ob = place.target(context)
    return ob is not None and not place.refused(context)


def _frame(context):
    """(pivot, 3x3 axes) of what is selected – kept while nothing changes (a model's box is costly to measure)."""
    scene = context.scene
    ob = place.target(context)
    objs = place.movers(context)
    key = (tuple(o.name for o in objs), tuple(tuple(r) for o in objs for r in o.matrix_world),
           scene.fresing.place.space)
    if _DRAG["key"] != key or _DRAG["pivot"] is None:
        _DRAG["key"] = key
        _DRAG["pivot"] = place.pivot(scene, objs)
        _DRAG["axes"] = (place.axes(scene, ob) if scene.fresing.place.space != "WORLD" else Matrix.Identity(3))
        lo, hi = place.bounds(scene, ob)
        _DRAG["size"] = max(0.05, min(5.0, (hi - lo).length * 0.35)) if (hi - lo).length > 0 else 0.3
    return _DRAG["pivot"], _DRAG["axes"]


def _set(i: int):
    def setter(value):
        context = bpy.context
        scene = context.scene
        st = scene.fresing.place
        turn = i >= 3
        if turn:
            value = math.radians(core.snap(math.degrees(value), core.size_of(core.SNAP_TURN, st.snap_turn)))
        else:                       # an arrow's offset counts in its own (scaled) units
            value = core.snap(value * _DRAG["scale"] * 1000.0, core.size_of(core.SNAP_MOVE, st.snap_move)) / 1000.0
        d = value - _DRAG["acc"][i]
        if abs(d) < 1e-9:
            return
        _DRAG["acc"][i] = value
        _DRAG["undo"] = True
        a = Vector((0.0, 0.0, 0.0))
        a[i % 3] = 1.0
        a = _DRAG["axes"] @ a
        if turn:
            p = _DRAG["pivot"]
            D = Matrix.Translation(p) @ Matrix.Rotation(d, 4, a) @ Matrix.Translation(-p)
        else:
            D = Matrix.Translation(a * d)
        try:
            place.apply(context, D)
        except RuntimeError:
            return
        _watch()
    return setter


def _get(i: int):
    def getter():
        return _DRAG["acc"][i] / (_DRAG["scale"] if i < 3 else 1.0)
    return getter


def _watch() -> None:
    """After a drag: one undo step (the drag changed the project without one)."""
    if bpy.app.timers.is_registered(_after_drag):
        return
    bpy.app.timers.register(_after_drag, first_interval=0.3)


def _after_drag():
    if _DRAG["busy"]:
        return 0.3
    if _DRAG["undo"]:
        _DRAG["undo"] = False
        try:
            win = bpy.context.window_manager.windows[0]
            with bpy.context.temp_override(window=win):
                bpy.ops.ed.undo_push(message="Place")
        except Exception as exc:  # noqa: BLE001
            print("Fresing Render: Place: no undo step for the drag:", exc)
    return None


class FRESING_GGT_place(bpy.types.GizmoGroup):
    bl_idname = "FRESING_GGT_place"
    bl_label = "Place"
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"
    bl_options = {"3D", "PERSISTENT"}

    @classmethod
    def poll(cls, context):
        try:
            return _wanted(context)
        except Exception:  # noqa: BLE001 - a gizmo's poll must never fail
            return False

    def setup(self, context):
        self.items = []
        for i in range(6):
            if i < 3:
                gz = self.gizmos.new("GIZMO_GT_arrow_3d")
                gz.draw_style = "NORMAL"
                gz.length = 0.6
            else:
                gz = self.gizmos.new("GIZMO_GT_dial_3d")
                gz.draw_options = {"ANGLE_VALUE"}
                gz.line_width = 3.0
            gz.target_set_handler("offset", get=_get(i), set=_set(i))
            gz.color = COLOURS[i % 3]
            gz.alpha = 0.6
            gz.color_highlight = (1.0, 1.0, 1.0)
            gz.alpha_highlight = 1.0
            gz.use_draw_modal = True
            self.items.append(gz)

    def draw_prepare(self, context):
        busy = any(g.is_modal for g in self.items)
        _DRAG["busy"] = busy
        if busy:
            return
        _DRAG["acc"] = [0.0] * 6
        try:
            p, A = _frame(context)
        except (ReferenceError, ValueError):
            return
        size = _DRAG["size"]
        _DRAG["scale"] = size
        for i, gz in enumerate(self.items):
            a = Vector((0.0, 0.0, 0.0))
            a[i % 3] = 1.0
            a = A @ a
            rot = a.to_track_quat("Z", "Y").to_matrix().to_4x4()
            scale = Matrix.Scale(size if i < 3 else size * 0.8, 4)
            gz.matrix_basis = Matrix.Translation(p) @ rot @ scale


PANELS = (FRESING_PT_place,)
CLASSES = (FRESING_GGT_place,)
