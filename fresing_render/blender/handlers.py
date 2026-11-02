"""Click-to-select-subassembly behaviour (Inventor-like) via Blender's message bus."""

from __future__ import annotations

import bpy
from bpy.app.handlers import persistent

from . import build, logic

_OWNER = object()
_BUSY = False


def _on_active_changed():
    global _BUSY
    if _BUSY:
        return
    ctx = bpy.context
    scene = getattr(ctx, "scene", None)
    if scene is None or not hasattr(scene, "fresing") or scene.fresing.pick_mode != "SUBASSEMBLY":
        return
    view_layer = ctx.view_layer
    ob = view_layer.objects.active
    if ob is None or ob.get(build.PROP_KIND) != "part":
        return
    sub = logic.subassembly_for_pick(ob)
    if sub is ob or sub is None:
        return
    _BUSY = True
    try:
        for d in [sub] + logic.descendants(sub):
            if d.visible_get() and not d.hide_select:
                d.select_set(True)
        try:
            sub.select_set(True)
        except RuntimeError:
            pass
        view_layer.objects.active = sub
        # highlight in the structure list
        s = scene.fresing
        for i, item in enumerate(s.tree):
            if item.obj is sub:
                s.tree_index = i
                break
    finally:
        _BUSY = False


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
    _subscribe()


def register():
    _subscribe()
    if _on_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_on_load)


def unregister():
    bpy.msgbus.clear_by_owner(_OWNER)
    if _on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_load)
