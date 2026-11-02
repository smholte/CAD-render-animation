"""Click-to-select-subassembly behaviour (Inventor-like) via Blender's message bus.

When "Click selects: Subassembly" is on, clicking a part also selects the rest of
its subassembly. The clicked part stays the active object, so the part info in the
Looks panel and "Rule from active part" keep working.

Message-bus callbacks run after the change, also when an operator (not a click)
changes the active object. Operators that set the active object themselves call
``ignore_next(ob)`` so their selection is left alone.
"""

from __future__ import annotations

import bpy
from bpy.app.handlers import persistent

from . import build, logic

_OWNER = object()
_IGNORE: set[str] = set()


def ignore_next(ob) -> None:
    """Do not expand the selection for the next active-object change to ``ob``."""
    if ob is not None:
        _IGNORE.add(ob.name)


def _on_active_changed():
    ctx = bpy.context
    scene = getattr(ctx, "scene", None)
    view_layer = getattr(ctx, "view_layer", None)
    if scene is None or view_layer is None or not hasattr(scene, "fresing"):
        return
    ob = view_layer.objects.active
    if ob is not None and ob.name in _IGNORE:
        _IGNORE.discard(ob.name)
        return
    _IGNORE.clear()
    if ob is not None and ob.get(build.PROP_KIND) in build.JOINT_KINDS:
        s = scene.fresing                    # clicking a joint arrow selects it in the joint list
        for i, j in enumerate(s.joints):
            if ob is j.frame or ob is j.motion:
                s.joints_index = i
                break
        return
    if scene.fresing.pick_mode != "SUBASSEMBLY":
        return
    if ob is None or ob.get(build.PROP_KIND) != "part" or not ob.select_get():
        return
    tree = logic.Tree(scene)
    sub = logic.subassembly_for_pick(ob, tree)
    if sub is None or sub is ob:
        return
    for d in [sub] + logic.descendants(sub, tree):
        if d.visible_get() and not d.hide_select:
            d.select_set(True)
    s = scene.fresing
    for i, item in enumerate(s.tree):
        if item.obj is sub:
            s.tree_index = i
            break


def _subscribe():
    bpy.msgbus.clear_by_owner(_OWNER)
    bpy.msgbus.subscribe_rna(
        key=(bpy.types.LayerObjects, "active"),
        owner=_OWNER,
        args=(),
        notify=_on_active_changed,
        options={"PERSISTENT"},
    )


@persistent
def _on_load(_dummy=None):
    _IGNORE.clear()
    _subscribe()
    try:
        for sc in bpy.data.scenes:           # projects from before 0.2: store the CAD matrices once
            if hasattr(sc, "fresing") and sc.fresing.model_count:
                build.ensure_bases(sc)
    except Exception:
        pass
    try:                                     # a render queue started earlier may still be going
        scene = bpy.context.scene
        if scene is not None and hasattr(scene, "fresing") and scene.fresing.queue_dir:
            from . import queue
            queue.sync(scene)
            if scene.fresing.queue_pid:
                queue.ensure_polling()
    except Exception:
        pass


@persistent
def _after_undo(_dummy=None):
    try:
        from . import queue
        if queue._RUNTIME["pid"]:
            queue.sync(bpy.context.scene)    # put the running queue back into the restored scene
            queue.ensure_polling()
    except Exception:
        pass


@persistent
def _before_load(_dummy=None):
    from .ops_import import cancel_running_job
    cancel_running_job()


def _at_exit():
    try:
        from .ops_import import cancel_running_job
        cancel_running_job()
    except Exception:
        pass


def register():
    import atexit
    _subscribe()
    if _on_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_on_load)
    if _before_load not in bpy.app.handlers.load_pre:
        bpy.app.handlers.load_pre.append(_before_load)
    for lst in (bpy.app.handlers.undo_post, bpy.app.handlers.redo_post):
        if _after_undo not in lst:
            lst.append(_after_undo)
    atexit.register(_at_exit)


def unregister():
    import atexit
    bpy.msgbus.clear_by_owner(_OWNER)
    if _on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_load)
    if _before_load in bpy.app.handlers.load_pre:
        bpy.app.handlers.load_pre.remove(_before_load)
    for lst in (bpy.app.handlers.undo_post, bpy.app.handlers.redo_post):
        while _after_undo in lst:
            lst.remove(_after_undo)
    atexit.unregister(_at_exit)
