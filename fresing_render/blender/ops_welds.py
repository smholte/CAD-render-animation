"""Operators of 3 Looks > Welds (task 0319).

The face picker (``fresing.weld_add``) works like Inventor's weld: 1 of 2 – click the faces of the first part (click:
this face, Shift-click: add or take away a face), Next (Enter); 2 of 2 – the faces of the second part: the seams where
the two sets meet show in the view at once (green; grey when unticked in the panel); Done (Enter) makes the weld. Esc or
right-click cancels. The picked faces light up (first part blue, second part orange); the face under the mouse in
magenta (``hover.py``). ``Picker`` holds the state – tests and the PC check drive it without a window.

The quick way (``fresing.weld_parts``): two selected parts – every line where they meet becomes a seam with a tick.
"""

from __future__ import annotations

import bpy
import numpy as np
from bpy.props import BoolProperty, EnumProperty, FloatVectorProperty, StringProperty
from mathutils import Vector

from ..core.words import plural
from . import build, hover, welds
from .ops_panels import _region_under_mouse

COL_A = (0.15, 0.55, 1.0)
COL_B = (1.0, 0.55, 0.10)
COL_SEAM = (0.20, 0.95, 0.35)
COL_OFF = (0.55, 0.55, 0.55)


class Picker:
    """The picker's state: one at a time (``P``)."""

    def __init__(self, scene, key: str = ""):
        self.scene = scene
        self.key = key                  # pick again: the weld whose faces are replaced
        self.step = "A"
        self.part_a = self.part_b = ""
        self.faces_a: set = set()
        self.faces_b: set = set()
        self.seams = []                 # found seams (core.welds.Seam, part A's coordinates)
        self.note = ""
        it = welds.find_item(scene, key) if key else None
        self.gap = it.gap if it is not None else welds.core.GAP

    # --- what the user does -------------------------------------------------
    def click(self, ob, face: int, add: bool = False) -> str:
        """A click on ``face`` of part ``ob``: '' or why it was not taken."""
        if ob is None or ob.get(build.PROP_KIND) != "part" or face < 0:
            return "Click a face of a part"
        if self.step == "A":
            if ob.name != self.part_a:
                self.part_a, self.faces_a = ob.name, set()
            self._toggle(self.faces_a, face, add)
        else:
            if ob.name == self.part_a:
                return "That is the first part: click the faces of the part it is welded to"
            if ob.name != self.part_b:
                self.part_b, self.faces_b = ob.name, set()
            self._toggle(self.faces_b, face, add)
            self.preview()
        return ""

    @staticmethod
    def _toggle(faces: set, face: int, add: bool) -> None:
        if add:
            faces.symmetric_difference_update({face})
        else:
            faces.clear()
            faces.add(face)

    def next(self) -> str:
        """Next (step 1) or Done (step 2): '' when it went on, else why not. Done makes the weld (``self.item``)."""
        if self.step == "A":
            if not self.faces_a:
                return "Click at least one face of the first part"
            self.step = "B"
            return ""
        if not self.faces_b:
            return "Click at least one face of the second part"
        if not self.seams:
            return self.note or "These faces do not meet: pick faces that touch"
        ticks = [s.enabled for s in welds.settings(self.scene).preview]
        if not any(ticks):
            return "Every seam is unticked: tick at least one"
        a, b = self.scene.objects.get(self.part_a), self.scene.objects.get(self.part_b)
        it = welds.find_item(self.scene, self.key) if self.key else None
        if it is not None:
            welds.set_faces(it, self.faces_a, self.faces_b, a, b)
            for s, on in zip(it.seams, ticks):
                s.enabled = on
            self.item = it
        else:
            self.item = welds.make(self.scene, a, sorted(self.faces_a), b, sorted(self.faces_b), ticks=ticks,
                                   gap=self.gap)
        self.step = "DONE"
        return ""

    def preview(self) -> None:
        a, b = self.scene.objects.get(self.part_a), self.scene.objects.get(self.part_b)
        prev = welds.settings(self.scene).preview
        if a is None or b is None or not self.faces_a or not self.faces_b:
            self.seams = []
            prev.clear()
            return
        seams, _sa, _sb = welds.find_raw(a, sorted(self.faces_a), b, sorted(self.faces_b), self.gap)
        self.seams = seams
        keep = [(tuple(s.mid), s.kind, s.enabled) for s in prev]
        welds.store_seams(prev, seams, keep)
        self.note = "" if seams else (f"These faces do not meet (not even with a gap of {self.gap * 1000:.1f} mm): "
                                      "pick faces that touch")

    def lines(self) -> list:
        """World polylines of the preview seams: [(points (k, 3), closed, ticked)]."""
        a = self.scene.objects.get(self.part_a)
        if a is None:
            return []
        m = np.array([list(r) for r in a.matrix_world], np.float64)
        prev = welds.settings(self.scene).preview
        out = []
        for i, s in enumerate(self.seams):
            p = s.points @ m[:3, :3].T + m[:3, 3]
            on = prev[i].enabled if i < len(prev) else True
            out.append((p, s.closed, on))
        return out

    def prompt(self) -> str:
        if self.step == "A":
            return (f"Weld 1 of 2: click the faces of the first part (Shift-click: more faces) – "
                    f"{plural(len(self.faces_a), 'face')} picked · Enter: Next · Esc: cancel")
        n = len(self.seams)
        return (f"Weld 2 of 2: click the faces of the part it is welded to (Shift-click: more) – "
                f"{plural(n, 'seam')} found · Enter: Done · Esc: cancel")


P: dict = {"picker": None, "handle": None, "go": False, "stop": False}


def picker() -> Picker | None:
    return P.get("picker")


# ---------------------------------------------------------------------------
# drawing: the picked faces and the seams
# ---------------------------------------------------------------------------

def _draw() -> None:
    pk = P.get("picker")
    if pk is None:
        return
    try:
        import gpu
        from gpu_extras.batch import batch_for_shader
        gpu.state.blend_set("ALPHA")
        gpu.state.depth_test_set("NONE")
        flat = gpu.shader.from_builtin("UNIFORM_COLOR")
        for name, faces, col in ((pk.part_a, pk.faces_a, COL_A), (pk.part_b, pk.faces_b, COL_B)):
            ob = bpy.data.objects.get(name) if name else None
            if ob is None or ob.type != "MESH":
                continue
            gpu.matrix.push()
            gpu.matrix.multiply_matrix(ob.matrix_world)
            for f in faces:
                fill, outline = hover.face_shape(ob.data, f)
                flat.uniform_float("color", (*col, 0.45))
                batch_for_shader(flat, "TRIS", {"pos": fill}).draw(flat)
                if len(outline):
                    line = gpu.shader.from_builtin("POLYLINE_UNIFORM_COLOR")
                    hover._lines(line, outline, (*col, 1.0), 2.0)
            gpu.matrix.pop()
        line = gpu.shader.from_builtin("POLYLINE_UNIFORM_COLOR")
        for pts, closed, on in pk.lines():
            if len(pts) < 2:
                continue
            seg = []
            n = len(pts)
            for i in range(n - (0 if closed else 1)):
                seg += [tuple(pts[i]), tuple(pts[(i + 1) % n])]
            hover._lines(line, seg, hover.DARK, 7.0)
            hover._lines(line, seg, (*(COL_SEAM if on else COL_OFF), 1.0), 4.0)
        gpu.state.blend_set("NONE")
    except Exception:  # noqa: BLE001 - drawing must never break the view
        pass


def _add_draw() -> None:
    if P["handle"] is None and not bpy.app.background:
        P["handle"] = bpy.types.SpaceView3D.draw_handler_add(_draw, (), "WINDOW", "POST_VIEW")


def _remove_draw() -> None:
    if P["handle"] is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(P["handle"], "WINDOW")
        except Exception:  # noqa: BLE001
            pass
        P["handle"] = None


def _redraw(context=None):
    wm = bpy.context.window_manager
    for win in wm.windows:
        for area in win.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


def start(scene, key: str = "") -> Picker:
    """A picker without a window (tests, the PC check) – the modal operator uses the same one."""
    P.update(picker=Picker(scene, key), go=False, stop=False)
    welds.settings(scene).picking = "A"
    welds.settings(scene).preview.clear()
    return P["picker"]


def finish(scene) -> None:
    P.update(picker=None, go=False, stop=False)
    s = welds.settings(scene)
    s.picking = ""
    s.preview.clear()
    _remove_draw()


def face_at(ob, polygon: int) -> int:
    from . import faces
    starts = faces.face_starts(ob.data)
    return int(np.searchsorted(starts, polygon, side="right") - 1)


# ---------------------------------------------------------------------------
# operators
# ---------------------------------------------------------------------------

def _note(ob, name, face, location, normal):
    pk = P.get("picker")
    if pk is None:
        return name
    if pk.step == "B" and ob.name == pk.part_a:
        return f"{name}: the first part"
    which = pk.faces_a if pk.step == "A" and ob.name == pk.part_a else (
        pk.faces_b if pk.step == "B" and ob.name == pk.part_b else set())
    if face in which:
        return f"{name}: picked – Shift-click takes it away"
    return f"{name}: click this face (Shift-click: add it)"


def _refuse(ob, location, normal):
    pk = P.get("picker")
    if pk is not None and pk.step == "B" and ob.name == pk.part_a:
        return "the first part – click the part it is welded to"
    return ""


class FRESING_OT_weld_add(bpy.types.Operator):
    """Adds a weld like Inventor: click the faces of the first part (Shift-click for more), Next, then the faces of the
    part it is welded to. A bead is laid on every line where the two sets meet – touching, or with a gap up to 2 mm.
    Untick seams you do not want, then Done. Esc or right-click cancels"""

    bl_idname = "fresing.weld_add"
    bl_label = "Add weld"
    bl_options = {"REGISTER", "UNDO"}

    key: StringProperty(options={"HIDDEN", "SKIP_SAVE"})          # pick again
    part: StringProperty(options={"HIDDEN", "SKIP_SAVE"})         # from the right-click menu: this part …
    point: FloatVectorProperty(size=3, options={"HIDDEN", "SKIP_SAVE"})   # … and the face at this spot

    @classmethod
    def poll(cls, context):
        return context.window is not None and context.scene.fresing.model_count > 0

    def invoke(self, context, event):
        if P.get("picker") is not None:
            P["stop"] = True                                  # pressed again: stop the running pick
            return {"CANCELLED"}
        pk = start(context.scene, self.key)
        if self.part:
            ob = context.scene.objects.get(self.part)
            if ob is not None and ob.type == "MESH":
                local = ob.matrix_world.inverted() @ Vector(self.point)
                ok, _loc, _n, poly = ob.closest_point_on_mesh(local)
                if ok and poly >= 0:
                    pk.click(ob, face_at(ob, poly))
        context.window_manager.modal_handler_add(self)
        hover.start(context, self, pk.prompt(), point=True, note=_note, refuse=_refuse)
        _add_draw()
        context.window.cursor_modal_set("CROSSHAIR")
        _redraw()
        return {"RUNNING_MODAL"}

    def _end(self, context, result):
        hover.end(self, context)
        finish(context.scene)
        try:
            context.window.cursor_modal_restore()
        except Exception:  # noqa: BLE001
            pass
        _redraw()
        return result

    def _go(self, context):
        pk = P["picker"]
        try:
            why = pk.next()
        except ValueError as exc:
            why = str(exc)
        if why:
            self.report({"WARNING"}, why)
            return {"RUNNING_MODAL"}
        if pk.step == "DONE":
            it = pk.item
            self.report({"INFO"}, f"Weld '{it.name}' added: {welds.describe(it)} – shape and look below")
            return self._end(context, {"FINISHED"})
        welds.settings(context.scene).picking = pk.step
        hover.prompt(context, pk.prompt())
        _redraw()
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        hover.on_event(self, context, event)
        pk = P.get("picker")
        if pk is None or P.get("stop"):
            return self._end(context, {"CANCELLED"})
        if P.get("go"):
            P["go"] = False
            return self._go(context)
        if event.value == "PRESS" and event.type in {"RET", "NUMPAD_ENTER"}:
            return self._go(context)
        if event.value == "PRESS" and event.type in {"ESC", "RIGHTMOUSE"}:
            region, _rv3d = _region_under_mouse(context, event)
            if event.type == "ESC" or region is not None:
                return self._end(context, {"CANCELLED"})
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            region, _rv3d = _region_under_mouse(context, event)
            if region is None:
                return {"PASS_THROUGH"}                      # the panel's buttons keep working
            hit = hover.pick(context, event)
            if hit is None:
                self.report({"WARNING"}, "Click a face of a part")
                return {"RUNNING_MODAL"}
            ob, poly, _loc, _n = hit
            why = pk.click(ob, face_at(ob, poly), add=event.shift)
            if why:
                self.report({"WARNING"}, why)
            welds.settings(context.scene).picking = pk.step
            hover.prompt(context, pk.prompt())
            _redraw()
            return {"RUNNING_MODAL"}
        return {"PASS_THROUGH"}                              # turn, pan and zoom the view as usual


class FRESING_OT_weld_next(bpy.types.Operator):
    """Next: on to the second part's faces. Done: makes the weld with the ticked seams (Enter in the view does the
    same)"""

    bl_idname = "fresing.weld_next"
    bl_label = "Next"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        P["go"] = True
        _redraw()
        return {"FINISHED"}


class FRESING_OT_weld_cancel(bpy.types.Operator):
    """Stops picking faces; no weld is made (Esc or right-click in the view does the same)"""

    bl_idname = "fresing.weld_cancel"
    bl_label = "Cancel"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        if P.get("picker") is not None:
            P["stop"] = True
        else:
            finish(context.scene)
        _redraw()
        return {"FINISHED"}


def _two_parts(context) -> list:
    sel = [o for o in context.selected_objects if o.get(build.PROP_KIND) == "part" and o.type == "MESH"]
    act = context.view_layer.objects.active
    if act in sel:
        sel.remove(act)
        sel.insert(0, act)
    return sel


class FRESING_OT_weld_parts(bpy.types.Operator):
    """The quick way: select two parts (click one, Shift-click the other) and press – every line where they meet gets a
    bead, each seam with a tick so you can leave some out. The bead moves with the part clicked last (the active one)"""

    bl_idname = "fresing.weld_parts"
    bl_label = "Weld two parts"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.scene.fresing.model_count > 0

    def execute(self, context):
        parts = _two_parts(context)
        if len(parts) != 2:
            self.report({"WARNING"}, f"Select exactly two parts ({plural(len(parts), 'part')} selected): click one, "
                                     "Shift-click the other")
            return {"CANCELLED"}
        try:
            it = welds.make(context.scene, parts[0], [], parts[1], [], whole=True)
        except ValueError as exc:
            self.report({"WARNING"}, str(exc))
            return {"CANCELLED"}
        self.report({"INFO"}, f"Weld '{it.name}' added: {welds.describe(it)} – untick seams you do not want below")
        return {"FINISHED"}


def _item(context, key):
    it = welds.find_item(context.scene, key) if key else welds.active(context.scene)
    return it


class FRESING_OT_weld_remove(bpy.types.Operator):
    """Removes this weld: its bead and heat zone go, the parts stay as they are"""

    bl_idname = "fresing.weld_remove"
    bl_label = "Remove weld"
    bl_options = {"REGISTER", "UNDO"}

    key: StringProperty(options={"HIDDEN", "SKIP_SAVE"})

    def execute(self, context):
        it = _item(context, self.key)
        if it is None:
            return {"CANCELLED"}
        name = it.name
        welds.remove(context.scene, it)
        self.report({"INFO"}, f"Weld '{name}' removed")
        return {"FINISHED"}


class FRESING_OT_weld_refind(bpy.types.Operator):
    """Finds the seams again where the parts meet now (after you moved a part or changed the gap); seams you unticked
    stay unticked"""

    bl_idname = "fresing.weld_refind"
    bl_label = "Find seams again"
    bl_options = {"REGISTER", "UNDO"}

    key: StringProperty(options={"HIDDEN", "SKIP_SAVE"})

    def execute(self, context):
        it = _item(context, self.key)
        if it is None:
            return {"CANCELLED"}
        if not welds.refind(it):
            self.report({"WARNING"}, it.note or "The seams could not be found")
            return {"CANCELLED"}
        self.report({"INFO"}, welds.describe(it))
        return {"FINISHED"}


class FRESING_OT_weld_ticks(bpy.types.Operator):
    """Ticks every seam of this weld (or none)"""

    bl_idname = "fresing.weld_ticks"
    bl_label = "Tick all seams"
    bl_options = {"REGISTER", "UNDO"}

    key: StringProperty(options={"HIDDEN", "SKIP_SAVE"})
    on: BoolProperty(default=True, options={"SKIP_SAVE"})
    preview: BoolProperty(default=False, options={"SKIP_SAVE"})

    def execute(self, context):
        if self.preview:
            for s in welds.settings(context.scene).preview:
                s.enabled = self.on
            _redraw()
            return {"FINISHED"}
        it = _item(context, self.key)
        if it is None:
            return {"CANCELLED"}
        welds._BUSY[0] = True
        try:
            for s in it.seams:
                s.enabled = self.on
        finally:
            welds._BUSY[0] = False
        welds.rebuild(it)
        return {"FINISHED"}


class FRESING_OT_weld_move_as_one(bpy.types.Operator):
    """These two parts are welded but a joint moves one of them and not the other: makes the second part move with
    the first (it joins the first part's joint, or leaves its own when the first part stands still)"""

    bl_idname = "fresing.weld_move_as_one"
    bl_label = "Make them move as one"
    bl_options = {"REGISTER", "UNDO"}

    key: StringProperty(options={"HIDDEN", "SKIP_SAVE"})

    def execute(self, context):
        it = _item(context, self.key)
        if it is None:
            return {"CANCELLED"}
        try:
            words = welds.move_as_one(context.scene, it)
        except RuntimeError as exc:
            self.report({"WARNING"}, str(exc))
            return {"CANCELLED"}
        self.report({"INFO"}, words)
        return {"FINISHED"}


class FRESING_OT_ctx_weld(bpy.types.Operator):
    """Starts a weld from the face you right-clicked: it is the first part's face; click more with Shift, press Enter,
    then click the faces of the part it is welded to"""

    bl_idname = "fresing.ctx_weld"
    bl_label = "Weld to another part…"
    bl_options = {"REGISTER"}

    part: StringProperty(options={"HIDDEN", "SKIP_SAVE"})
    point: FloatVectorProperty(size=3, options={"HIDDEN", "SKIP_SAVE"})

    def invoke(self, context, event):
        return bpy.ops.fresing.weld_add("INVOKE_DEFAULT", part=self.part, point=self.point)

    def execute(self, context):
        return {"CANCELLED"}


class FRESING_OT_weld_list(bpy.types.Operator):
    """Opens the weld list: one row per weld – its number (also on its symbol), parts, type, size, length, process
    and finish. Export CSV… there writes it as a file for a spreadsheet"""

    bl_idname = "fresing.weld_list"
    bl_label = "Weld list"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        return context.scene is not None and hasattr(context.scene, "fresing_welds")

    def invoke(self, context, event):
        from . import form_window
        return form_window.open(self, context, width=860, height=420, title="Weld list", confirm=None, icon="PRESET")

    def execute(self, context):
        return {"FINISHED"}

    def draw(self, context):
        from ..core import weld_symbols as core_symbols
        from . import weld_symbols
        layout = self.layout
        data = weld_symbols.all_data(context.scene)
        if not data:
            layout.label(text="No welds yet: add them in 3 Looks > Welds", icon="INFO")
            return
        rows = core_symbols.table(data)
        widths = (0.4, 2.2, 1.6, 1.6, 1.9, 0.6, 0.9, 1.0, 1.1, 2.2)      # the Metal column is left to the CSV
        keep = (0, 1, 2, 3, 4, 5, 6, 7, 8, 10)
        col = layout.column(align=True)
        for k, r in enumerate(rows):
            line = col.row(align=True)
            for w, i in zip(widths, keep):
                cell = line.row(align=True)
                cell.ui_units_x = w * 4
                cell.label(text=r[i], icon="NONE")
            if k == 0:
                col.separator()
        layout.separator()
        row = layout.row(align=True)
        row.operator("fresing.weld_list_csv", text="Export CSV…", icon="EXPORT")
        s = welds.settings(context.scene)
        row.prop(s, "symbols", text="Weld symbols in the view", icon="FONT_DATA")


class FRESING_OT_weld_list_csv(bpy.types.Operator):
    """Writes the weld list as a CSV file (opens in Excel or any spreadsheet): number, parts, type, size, length,
    process, finish, metal and the symbol. Pick where it goes"""

    bl_idname = "fresing.weld_list_csv"
    bl_label = "Export the weld list"
    bl_options = {"REGISTER"}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH", options={"SKIP_SAVE"})
    filter_glob: bpy.props.StringProperty(default="*.csv", options={"HIDDEN"})

    @classmethod
    def poll(cls, context):
        return context.scene is not None and len(context.scene.fresing_welds.items) > 0

    def invoke(self, context, event):
        from . import weld_symbols
        if not self.filepath:
            self.filepath = weld_symbols.default_csv_path(context.scene)
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        from . import weld_symbols
        path = self.filepath or weld_symbols.default_csv_path(context.scene)
        try:
            path = weld_symbols.export_csv(context.scene, bpy.path.abspath(path))
        except OSError as exc:
            self.report({"ERROR"}, f"The weld list could not be written: {exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"Weld list written: {path}")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# task 0323: welds from the CAD file
# ---------------------------------------------------------------------------

class FRESING_OT_weld_cad_find(bpy.types.Operator):
    """Looks for solid weld beads in the imported models (Inventor's welds body, Creo's weld bodies, parts named
    Weld …, beads by their shape) and makes each one a weld with the app's looks. Beads already made are skipped"""

    bl_idname = "fresing.weld_cad_find"
    bl_label = "Find welds in the CAD file"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return bool(build.model_roots(context.scene))

    def execute(self, context):
        from . import weld_cad
        made, by_shape = weld_cad.find_again(context.scene)
        if not made:
            self.report({"INFO"}, "No weld beads found in the CAD file (cosmetic welds are not in a STEP file)")
            return {"FINISHED"}
        s = welds.settings(context.scene)
        s.index = len(s.items) - 1
        text = f"{plural(len(made), 'weld')} from the CAD file"
        if by_shape:
            text += f"; {plural(by_shape, 'weld')} found by shape – check them"
        self.report({"INFO"}, text)
        return {"FINISHED"}


class FRESING_OT_weld_cad_shape(bpy.types.Operator):
    """Switches this weld from the CAD file between the bead's own shape from the CAD file and the app's bead laid on
    the same seam (with its size)"""

    bl_idname = "fresing.weld_cad_shape"
    bl_label = "Use the app's bead instead"
    bl_options = {"REGISTER", "UNDO"}

    key: StringProperty(options={"HIDDEN", "SKIP_SAVE"})

    def execute(self, context):
        it = _item(context, self.key)
        if it is None or not it.from_cad:
            return {"CANCELLED"}
        it.cad_shape = not it.cad_shape
        self.report({"INFO"}, f"Weld '{it.name}': " + ("the CAD shape" if it.cad_shape else "the app's bead"))
        return {"FINISHED"}


class FRESING_OT_weld_cad_all(bpy.types.Operator):
    """The same for every weld from the CAD file at once: the CAD shape or the app's bead, painted (with the paint of
    the painted part) or bare"""

    bl_idname = "fresing.weld_cad_all"
    bl_label = "All welds from the CAD file"
    bl_options = {"REGISTER", "UNDO"}

    what: EnumProperty(items=[("CAD", "CAD shape", "Every weld from the CAD file keeps its bead's own shape"),
                              ("APP", "App's bead", "Every weld from the CAD file gets the app's bead on its seam"),
                              ("PAINTED", "Painted", "Every weld from the CAD file painted over (where a part is "
                                                     "painted)"),
                              ("BARE", "Bare", "Every weld from the CAD file as welded, not painted")],
                       options={"SKIP_SAVE"})

    @classmethod
    def description(cls, context, properties):
        return {"CAD": "Every weld from the CAD file keeps its bead's own shape from the CAD file",
                "APP": "Every weld from the CAD file gets the app's bead laid on its seam instead of its CAD shape",
                "PAINTED": "Every weld from the CAD file painted over with its painted part's paint (the ripples "
                           "show through); a weld between bare parts stays bare",
                "BARE": "Every weld from the CAD file as welded: bare metal with its heat tint, not painted"}[
            properties.what]

    def execute(self, context):
        from . import weld_cad
        values = {"CAD": {"cad_shape": True}, "APP": {"cad_shape": False}, "PAINTED": {"finish": "PAINTED"},
                  "BARE": {"finish": "AS_WELDED"}}[self.what]
        n = weld_cad.set_all(context.scene, **values)
        self.report({"INFO"}, f"{plural(n, 'weld')} changed")
        return {"FINISHED"}


class FRESING_OT_weld_cad_put_back(bpy.types.Operator):
    """Removes every weld that came from the CAD file and shows the CAD part they came from again (as it was
    imported). Find welds in the CAD file makes them again"""

    bl_idname = "fresing.weld_cad_put_back"
    bl_label = "Back to the CAD part"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        from . import weld_cad
        n = weld_cad.put_back(context.scene)
        self.report({"INFO"}, f"{plural(n, 'weld')} from the CAD file removed; the CAD part shows again")
        return {"FINISHED"}


CLASSES = (FRESING_OT_weld_list, FRESING_OT_weld_list_csv, FRESING_OT_weld_add, FRESING_OT_weld_next, FRESING_OT_weld_cancel, FRESING_OT_weld_parts,
           FRESING_OT_weld_remove, FRESING_OT_weld_refind, FRESING_OT_weld_ticks, FRESING_OT_weld_move_as_one,
           FRESING_OT_ctx_weld, FRESING_OT_weld_cad_find, FRESING_OT_weld_cad_shape, FRESING_OT_weld_cad_all,
           FRESING_OT_weld_cad_put_back)
