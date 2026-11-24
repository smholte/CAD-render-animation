"""Copy and Paste (task 0293): right-click > Copy / Paste here, 2 Structure > Place > Copy / Paste, Ctrl+C / Ctrl+V
outside Full access (in Full access they stay Blender's). The rules: the top of ``copy.py``."""

from __future__ import annotations

import bpy
from bpy.props import BoolProperty, FloatVectorProperty, StringProperty

from . import build, copy, remove


def _poll(cls, context) -> bool:
    from . import lock
    if getattr(context.scene, "fresing", None) is None:
        return False
    if lock.ON[0]:
        cls.poll_message_set(lock.MESSAGE)
        return False
    return True


def clipboard(scene) -> list:
    """The objects Copy remembered that are still in this project (never the same names in another project)."""
    if copy.CLIP.get("scene") != scene.name:
        return []
    out = []
    uids = list(copy.CLIP.get("uids") or [])
    for k, n in enumerate(copy.CLIP["names"]):
        ob = scene.objects.get(n)
        u = uids[k] if k < len(uids) else ""
        if ob is None or (u and ob.get(build.PROP_UID) != u):     # replaced by a model update: by its part ID
            ob = next((o for o in scene.objects if u and o.get(build.PROP_UID) == u), None)
        if ob is not None and ob not in out:
            out.append(ob)
    return out


def can_paste(scene) -> bool:
    return bool(clipboard(scene))


OPENED = [""]                          # what opening Move / turn after a paste gave (tests)


def do_paste(op, context, at=None, open_place: bool = True) -> set:
    """Paste (the button, Paste here and Ctrl+V – each pushes its own undo step: an operator called from another one
    pushes none, CLAUDE.md 8)."""
    scene = context.scene
    objs = clipboard(scene)
    if not objs:
        _say(op, context, "Nothing to paste: copy a model, subassembly or part first", "WARNING")
        return {"CANCELLED"}
    try:
        p = copy.paste(scene, objs, at=at)
    except RuntimeError as exc:
        _say(op, context, f"Paste: {exc}", "ERROR")
        return {"CANCELLED"}
    if not p["roots"]:
        _say(op, context, "; ".join(p["left"]) or "Nothing was copied", "WARNING")
        return {"CANCELLED"}
    for o in scene.objects:
        o.select_set(False)
    tops = [bpy.data.objects[n] for n in p["roots"]]
    from . import ops_place
    for t in tops:                           # the copy can be placed at once
        ops_place.set_lock(t, False)
        t.select_set(True)
    context.view_layer.objects.active = tops[0]
    _say(op, context, copy.summary(p)[0] + ". Ctrl+Z takes it away")
    if open_place and not bpy.app.background and getattr(context, "window", None) is not None:
        try:
            OPENED[0] = str(bpy.ops.fresing.place_window("INVOKE_DEFAULT"))
        except RuntimeError as exc:          # a window opening already: the copy is made all the same
            print("Fresing Render: Paste: Move / turn not opened:", exc)
    return {"FINISHED"}


def _say(op, context, msg: str, kind: str = "INFO") -> None:
    context.scene.fresing.last_message = msg
    copy.NOTE[0] = msg
    op.report({kind}, msg)


class FRESING_OT_copy(bpy.types.Operator):
    """Remembers the selected model, subassembly or parts, to paste a copy of it (Paste, Paste here, Ctrl+V). The copy
    brings its joints, cylinders, mechanisms, way covers, hoses, labels and logos; its parts share their shapes with
    the original"""

    bl_idname = "fresing.copy"
    bl_label = "Copy"

    names: StringProperty(options={"SKIP_SAVE", "HIDDEN"})          # object names, one per line (else the selection)

    @classmethod
    def poll(cls, context):
        return _poll(cls, context)

    def execute(self, context):
        scene = context.scene
        objs = ([bpy.data.objects[n] for n in self.names.split("\n") if n in bpy.data.objects] if self.names
                else list(context.selected_objects))
        top = remove.chosen(scene, objs)
        if not top:
            _say(self, context, "Select a model, subassembly or part first: click it in the view or a row of "
                                "2 Structure", "WARNING")
            return {"CANCELLED"}
        copy.remember(scene, top)
        what = top[0].get(build.PROP_NAME, top[0].name) + (f" and {len(top) - 1} more" if len(top) > 1 else "")
        _say(self, context, f"Copied '{what}': Paste (or Ctrl+V) puts a copy beside it, right-click > Paste here "
                            "where you click")
        return {"FINISHED"}


class FRESING_OT_paste(bpy.types.Operator):
    """Pastes a copy of what you copied – with its joints, cylinders, mechanisms, way covers, hoses, labels and logos
    – beside the original (Paste here: where you right-clicked), then opens Move / turn for it. What reaches outside
    the copy is left out (the window says what): the copy moves by itself. Ctrl+Z takes it away again"""

    bl_idname = "fresing.paste"
    bl_label = "Paste"
    bl_options = {"REGISTER", "UNDO"}

    here: BoolProperty(options={"SKIP_SAVE", "HIDDEN"})              # at ``point`` (right-click > Paste here)
    point: FloatVectorProperty(size=3, options={"SKIP_SAVE", "HIDDEN"})
    open_place: BoolProperty(default=True, options={"SKIP_SAVE", "HIDDEN"})

    @classmethod
    def poll(cls, context):
        if not _poll(cls, context):
            return False
        if not can_paste(context.scene):
            cls.poll_message_set("Copy something first: select a model, subassembly or part, then Copy (or Ctrl+C)")
            return False
        return True

    def execute(self, context):
        return do_paste(self, context, tuple(self.point) if self.here else None, self.open_place)


class FRESING_OT_copy_key(bpy.types.Operator):
    """Ctrl+C in the 3D view outside Full access: Copy what is selected (in Full access the key is Blender's own)"""

    bl_idname = "fresing.copy_key"
    bl_label = "Copy (Ctrl+C)"
    bl_options = {"INTERNAL"}

    @classmethod
    def poll(cls, context):
        from . import lock
        return (lock.keys_quiet() and context.mode == "OBJECT" and not lock.ON[0]
                and getattr(context.scene, "fresing", None) is not None)

    def execute(self, context):
        return bpy.ops.fresing.copy()


class FRESING_OT_paste_key(bpy.types.Operator):
    """Ctrl+V in the 3D view outside Full access: Paste a copy of what you copied beside it (in Full access the key is
    Blender's own)"""

    bl_idname = "fresing.paste_key"
    bl_label = "Paste (Ctrl+V)"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    @classmethod
    def poll(cls, context):
        from . import lock
        return (lock.keys_quiet() and context.mode == "OBJECT" and not lock.ON[0]
                and getattr(context.scene, "fresing", None) is not None)

    def execute(self, context):
        if not can_paste(context.scene):
            self.report({"INFO"}, "Nothing to paste: select a model, subassembly or part and press Ctrl+C first")
            return {"CANCELLED"}
        return do_paste(self, context)


CLASSES = (FRESING_OT_copy, FRESING_OT_paste, FRESING_OT_copy_key, FRESING_OT_paste_key)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass

