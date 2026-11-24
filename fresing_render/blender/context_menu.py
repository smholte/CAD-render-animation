"""The right-click menu in the 3D view (task 0253, study 0222 package B).

Outside Full access (every workspace but Full access, the same switch as the quiet window: ``lock.blender_ui``) a
right-click in the 3D view does not open Blender's object menu (Delete, Duplicate, Join, Parent …) but a short
**Fresing** menu:

* on a part: the part becomes the selected one, as a left click would make it (in the pick mode "Subassembly" its
  subassembly), then **Zoom to it**, **Show in 2 Structure**, **Hide**, **Show only this**, **Show all** (when something
  is hidden or shown only), **Add a label here** (pointing at the clicked spot) and **Add joint here…** (the Motion
  panel's Add joint with this part: the axis pick starts);
* on empty space: **Zoom to all**, **Show all**;
* in the **Client view** only the viewing entries – and its Hide / Show only / Show all only hide in the view (as
  Blender's H does): nothing in the project, its renders or its built animation changes, and leaving the Client view
  shows those parts again.

How: an add-on key (right mouse and the Menu key in "Object Mode", ``lock._add_keys``) runs ``fresing.view_menu``,
whose ``poll`` is the quiet window, so in Full access Blender's own key opens Blender's menu. It picks the part under
the mouse (``HIT``) and opens Blender's ``VIEW3D_MT_object_context_menu`` – whose own draw is swapped for ours by
``quiet.swap``, so items other add-ons appended stay. In another mode than Object Mode (Full access only) Blender's
own draw. A Blender user who chose right-click select keeps Blender's (``poll``).
"""

from __future__ import annotations

import math

import bpy
from bpy.props import FloatVectorProperty, StringProperty
from mathutils import Vector

from . import build, logic

MENU = "VIEW3D_MT_object_context_menu"
HIT = {"part": "", "target": "", "point": (0.0, 0.0, 0.0), "hidden": False, "client": False}
DRAWN = [0]                  # the Fresing menu drawn (tests, the PC check)
OPENED = [0]                 # fresing.view_menu ran (tests)
CV_HIDE = "fr_cv_hide"       # per object: hidden in the view by the Client view's menu (not in the project)
ON = [False]                 # Blender's menu drawing is swapped for ours

# what the menu shows (tests, the guide, the PC check)
ON_PART = ("Zoom to it", "Show in 2 Structure", "Hide", "Show only this", "Show all", "Add a label here",
           "Add joint here…", "Unlock so it can move",          # "Lock in place" once unlocked (task 0307)
           "Move / turn…", "Remove…",                            # task 0292
           "Copy", "Paste here")                                 # task 0293 (Paste here once something was copied)
ON_EMPTY = ("Zoom to all", "Show all", "Paste")
CLIENT_DROPS = ("Add a label here", "Add joint here…", "Unlock so it can move", "Move / turn…", "Remove…", "Copy",
                "Paste here", "Paste")


def _quiet() -> bool:
    from . import lock
    return lock.tabs_hidden()


def client(scene) -> bool:
    if scene is None or getattr(scene, "fresing", None) is None:
        return False
    from . import workspaces
    return workspaces.locked(scene)


def _model(ob):
    """The model object (part or assembly) for a hit: a sticker or other child counts as the part under it."""
    while ob is not None and ob.get(build.PROP_KIND) not in build.MODEL_KINDS:
        ob = ob.parent
    return ob


def _subtree(scene, ob) -> list:
    return [ob] + logic.descendants(ob, logic.cached_tree(scene))


def anything_hidden(scene) -> bool:
    """Is there something Show all would bring back?"""
    if client(scene):
        return any(CV_HIDE in o for o in scene.objects)
    if scene.fresing.isolated:
        return True
    return any(o.get("fr_hidden") and not o.get(build.PROP_EXCLUDED) for o in scene.objects
               if o.get(build.PROP_KIND) in build.MODEL_KINDS)


def target_of(scene, ob):
    """What a left click on ``ob`` selects: the part, or its subassembly in the pick mode "Subassembly"."""
    if scene.fresing.pick_mode == "SUBASSEMBLY" and ob.get(build.PROP_KIND) == "part":
        sub = logic.subassembly_for_pick(ob, logic.cached_tree(scene))
        if sub is not None:
            return sub
    return ob


def select(context, target, active) -> None:
    """Select ``target`` (and what is under it) as a left click does; ``active`` becomes the active object."""
    from . import handlers
    from . import tree as tree_mod
    scene = context.scene
    for o in list(context.selected_objects):
        o.select_set(False)
    for o in _subtree(scene, target):
        if o.visible_get() and not o.hide_select:
            try:
                o.select_set(True)
            except RuntimeError:
                pass
    if active is not None and active.visible_get() and not active.hide_select:
        handlers.ignore_next(active)           # keep exactly this selection (the handler would make the same)
        context.view_layer.objects.active = active
    tree_mod.follow_view(scene, target)


def pick(context, hit) -> None:
    """Remember what a right-click landed on (``hit`` = (object, polygon, location, normal) or None) and select it
    outside the Client view."""
    scene = context.scene
    ob = _model(hit[0]) if hit else None
    is_client = client(scene)
    HIT.update(part="", target="", point=(0.0, 0.0, 0.0), client=is_client)
    if ob is not None:
        target = target_of(scene, ob)
        HIT.update(part=ob.name, target=target.name, point=tuple(hit[2]))
        if not is_client:
            select(context, target, ob)
    HIT["hidden"] = anything_hidden(scene)


# ---------------------------------------------------------------------------
# the menu
# ---------------------------------------------------------------------------

def _draw(self, context):
    """The Fresing menu in place of Blender's own object menu (outside Full access, Object Mode)."""
    if context.mode != "OBJECT" or not _quiet():
        from . import quiet
        orig = quiet.blender_draw(getattr(bpy.types, MENU))
        if orig is not None:
            return orig(self, context)
        return None
    DRAWN[0] += 1
    layout = self.layout
    layout.operator_context = "EXEC_DEFAULT"
    ob = bpy.data.objects.get(HIT["target"]) if HIT["target"] else None
    if ob is None:
        layout.operator("fresing.ctx_zoom", text="Zoom to all", icon="VIEWZOOM").part = ""
        layout.operator("fresing.ctx_show_all", text="Show all", icon="HIDE_OFF")
        from . import ops_copy                   # task 0293: a copy beside the original
        if not HIT["client"] and ops_copy.can_paste(context.scene):
            layout.separator()
            layout.operator("fresing.paste", text="Paste", icon="PASTEDOWN")
        return None
    layout.label(text=ob.get(build.PROP_NAME, ob.name), icon="OBJECT_DATA")
    layout.separator()
    layout.operator("fresing.ctx_zoom", text="Zoom to it", icon="ZOOM_SELECTED").part = ob.name
    layout.operator("fresing.ctx_tree", text="Show in 2 Structure", icon="OUTLINER").part = ob.name
    layout.separator()
    layout.operator("fresing.ctx_hide", text="Hide", icon="HIDE_ON").part = ob.name
    layout.operator("fresing.ctx_only", text="Show only this", icon="SOLO_ON").part = ob.name
    if HIT["hidden"]:
        layout.operator("fresing.ctx_show_all", text="Show all", icon="HIDE_OFF")
    if HIT["client"]:
        return None
    layout.separator()
    op = layout.operator("fresing.ctx_label", text="Add a label here", icon="FONT_DATA")
    op.part, op.point = HIT["part"], HIT["point"]
    layout.operator_context = "INVOKE_DEFAULT"
    layout.operator("fresing.ctx_joint", text="Add joint here…", icon="CON_PIVOT").part = ob.name
    from . import place                          # task 0307: G / R move it once it is unlocked
    layout.operator_context = "EXEC_DEFAULT"
    text = place.menu_text(ob)
    layout.operator("fresing.ctx_unlock", text=text, icon="UNLOCKED" if text.startswith("Unlock") else "LOCKED"
                    ).part = ob.name
    layout.operator_context = "INVOKE_DEFAULT"     # task 0292: Place in a window of its own, Remove… (lists what goes)
    layout.operator("fresing.place_window", text="Move / turn…", icon="OBJECT_ORIGIN")
    layout.operator_context = "EXEC_DEFAULT"     # task 0293: Copy, Paste here (where the right-click was)
    layout.operator("fresing.copy", text="Copy", icon="COPYDOWN")
    from . import ops_copy
    if ops_copy.can_paste(context.scene):
        op = layout.operator("fresing.paste", text="Paste here", icon="PASTEDOWN")
        op.here, op.point = True, HIT["point"]
    layout.operator_context = "INVOKE_DEFAULT"
    layout.separator()
    layout.operator("fresing.remove", text="Remove…", icon="TRASH")
    return None


def apply(quiet_on: bool) -> None:
    """Swap Blender's own object-menu drawing for the Fresing menu (``quiet_on``) or put it back."""
    if bpy.app.background:
        return
    cls = getattr(bpy.types, MENU, None)
    if cls is None:
        return
    from . import quiet
    if quiet_on:
        ON[0] = quiet.swap(cls, _draw)
    else:
        quiet.unswap(cls)
        ON[0] = False


def unhide_client(scene=None) -> int:
    """Show again what the Client view's menu hid in the view (the Client view is left). Returns how many."""
    n = 0
    for o in (scene.objects if scene is not None else bpy.data.objects):
        if CV_HIDE in o:
            del o[CV_HIDE]
            try:
                if o.hide_get():
                    o.hide_set(False)
            except RuntimeError:
                pass
            n += 1
    return n


# ---------------------------------------------------------------------------
# the operators
# ---------------------------------------------------------------------------

def _view(context):
    """(area, region, region_3d) of the 3D view the menu was opened in (else the first one)."""
    areas = [context.area] if context.area is not None and context.area.type == "VIEW_3D" else []
    screen = context.screen
    areas += [a for a in (screen.areas if screen is not None else ()) if a.type == "VIEW_3D"]
    for area in areas:
        region = next((r for r in area.regions if r.type == "WINDOW"), None)
        if region is not None and region.data is not None:
            return area, region, region.data
    return None, None, None


def frame(context, objs) -> bool:
    """Zoom the 3D view onto these objects (their boxes). Works where they cannot be selected (the Client view)."""
    area, _region, rv3d = _view(context)
    if rv3d is None:
        return False
    pts = []
    for o in objs:
        if o.type == "MESH" and o.visible_get():
            m = o.matrix_world
            pts += [m @ Vector(c) for c in o.bound_box]
    if not pts:
        return False
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    radius = max((hi - lo).length / 2, 0.005)
    if rv3d.view_perspective == "CAMERA":
        rv3d.view_perspective = "PERSP"
    lens = getattr(area.spaces.active, "lens", 50.0) or 50.0
    half = math.atan(36.0 / (2 * lens))                    # half the view's angle (a 36 mm frame)
    rv3d.view_location = (lo + hi) / 2
    rv3d.view_distance = radius / math.sin(half) * 1.05
    area.tag_redraw()
    return True


def _model_objects(scene) -> list:
    return [o for o in scene.objects if o.get(build.PROP_KIND) in build.MODEL_KINDS]


class _OnPart:
    part: StringProperty(name="Part", options={"SKIP_SAVE", "HIDDEN"})

    def _ob(self, context):
        ob = bpy.data.objects.get(self.part) if self.part else None
        if ob is None or ob.name not in context.scene.objects:
            self.report({"WARNING"}, "Right-click a part in the 3D view first")
            return None
        return ob


class FRESING_OT_view_menu(bpy.types.Operator):
    """Right-click in the 3D view: makes the part under the mouse the selected one and opens a short Fresing menu – zoom
    to it, show it in 2 Structure, hide it, show only it, put a label on it or add a joint. On empty space: Zoom to all
    and Show all. Fresing > Show all of Blender gives you Blender's own right-click menu"""

    bl_idname = "fresing.view_menu"
    bl_label = "Fresing menu"
    bl_options = {"INTERNAL"}

    @classmethod
    def poll(cls, context):
        if not _quiet() or context.area is None or context.area.type != "VIEW_3D" or context.mode != "OBJECT":
            return False
        scene = context.scene
        if scene is None or getattr(scene, "fresing", None) is None:
            return False
        try:                                    # a Blender user who chose right-click select keeps Blender's
            kc = context.window_manager.keyconfigs.active
            if kc.preferences is not None and getattr(kc.preferences, "select_mouse", "LEFT") == "RIGHT":
                return False
        except AttributeError:
            pass
        return True

    def invoke(self, context, event):
        from .ops_motion import _raycast, over_panel
        OPENED[0] += 1
        hit = None if over_panel(context, event) else _raycast(context, event)
        pick(context, hit)
        bpy.ops.wm.call_menu(name=MENU)
        return {"FINISHED"}

    def execute(self, context):             # scripts and tests: the menu on what was picked last
        bpy.ops.wm.call_menu(name=MENU)
        return {"FINISHED"}


class FRESING_OT_ctx_zoom(_OnPart, bpy.types.Operator):
    """Zooms the 3D view onto this part (or, on empty space, onto the whole model). The camera does not move: it only
    changes how you look at the model"""

    bl_idname = "fresing.ctx_zoom"
    bl_label = "Zoom to it"

    @classmethod
    def description(cls, context, props):
        if props is not None and not props.part:
            return "Zooms the 3D view out to the whole model. The camera does not move: it only changes how you look at it"
        return "Zooms the 3D view onto this part. The camera does not move: it only changes how you look at the model"

    def execute(self, context):
        if not self.part:
            area, region, rv3d = _view(context)
            if region is None:
                return {"CANCELLED"}
            if rv3d.view_perspective == "CAMERA":
                rv3d.view_perspective = "PERSP"
            with context.temp_override(area=area, region=region):
                bpy.ops.view3d.view_all(center=False)
            return {"FINISHED"}
        ob = self._ob(context)
        if ob is None or not frame(context, _subtree(context.scene, ob)):
            return {"CANCELLED"}
        return {"FINISHED"}


class FRESING_OT_ctx_tree(_OnPart, bpy.types.Operator):
    """Shows this part in 2 Structure: its row is opened, picked and scrolled into view in the side panel"""

    bl_idname = "fresing.ctx_tree"
    bl_label = "Show in 2 Structure"

    def execute(self, context):
        from . import panels
        from . import tree as tree_mod
        ob = self._ob(context)
        if ob is None:
            return {"CANCELLED"}
        scene = context.scene
        row = tree_mod.row_of(scene, ob)
        if row is None:
            tree_mod.rebuild(scene)
            row = tree_mod.row_of(scene, ob)
        if row is None:
            self.report({"WARNING"}, "This part has no row in 2 Structure")
            return {"CANCELLED"}
        tree_mod.reveal(scene.fresing, row)
        tree_mod._set_index_quietly(scene.fresing, row)
        panels.open_to("FRESING_PT_structure")
        area, _region, _rv3d = _view(context)
        if area is not None:
            sp = area.spaces.active
            if not sp.show_region_ui:
                sp.show_region_ui = True
            for r in area.regions:
                if r.type == "UI":
                    try:
                        if r.active_panel_category != "Fresing":
                            r.active_panel_category = "Fresing"
                    except (AttributeError, TypeError):
                        pass
                    r.tag_redraw()
        self.report({"INFO"}, f"{ob.get(build.PROP_NAME, ob.name)}: picked in 2 Structure")
        return {"FINISHED"}


def _take_build_off(op, context) -> None:
    from .ops_main import _take_build_off as off
    off(op, context)


class FRESING_OT_ctx_hide(_OnPart, bpy.types.Operator):
    """Hides this part (also in renders), as Hide selected does; Show all brings it back. After Build it takes the built
    animation off: Build again. In the Client view it only hides it in the view"""

    bl_idname = "fresing.ctx_hide"
    bl_label = "Hide"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        ob = self._ob(context)
        if ob is None:
            return {"CANCELLED"}
        scene = context.scene
        if client(scene):
            for o in _subtree(scene, ob):
                if not o.hide_get():
                    o.hide_set(True)
                    o[CV_HIDE] = True
            return {"FINISHED"}
        _take_build_off(self, context)
        logic.set_hidden(ob, True, logic.Tree(scene))
        scene.fresing.bounds_valid = False
        return {"FINISHED"}


class FRESING_OT_ctx_only(_OnPart, bpy.types.Operator):
    """Shows only this part (or subassembly), as Show only selected does; Show all brings everything back. After Build
    it takes the built animation off: Build again. In the Client view it only hides the rest in the view"""

    bl_idname = "fresing.ctx_only"
    bl_label = "Show only this"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        from . import tree as tree_mod
        ob = self._ob(context)
        if ob is None:
            return {"CANCELLED"}
        scene = context.scene
        keep = _subtree(scene, ob)
        if client(scene):
            names = {o.name for o in keep}
            p = build.logical_parent(ob)
            while p is not None:
                names.add(p.name)
                p = build.logical_parent(p)
            for o in _model_objects(scene):
                if o.name not in names and not o.hide_get():
                    o.hide_set(True)
                    o[CV_HIDE] = True
            return {"FINISHED"}
        _take_build_off(self, context)
        tree_mod.show_only(scene, keep, ob.get(build.PROP_NAME, ob.name))
        return {"FINISHED"}


class FRESING_OT_ctx_show_all(bpy.types.Operator):
    """Shows every hidden part again and ends Show only (parts removed with Clean-up stay hidden). After Build it takes
    the built animation off: Build again. In the Client view it shows what this menu hid"""

    bl_idname = "fresing.ctx_show_all"
    bl_label = "Show all"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        from .tree import ISO_HIDDEN
        scene = context.scene
        if client(scene):
            unhide_client(scene)
            return {"FINISHED"}
        _take_build_off(self, context)
        for ob in scene.objects:                 # as 2 Structure's Show all (ops_main.FRESING_OT_show_all)
            if ob.get(build.PROP_KIND) in build.MODEL_KINDS and not ob.get(build.PROP_EXCLUDED):
                logic.set_visible_flags(ob, False)
                if ob.get("fr_hidden"):
                    ob["fr_hidden"] = False
            if ISO_HIDDEN in ob:
                del ob[ISO_HIDDEN]
        scene.fresing.isolated = ""
        scene.fresing.bounds_valid = False
        return {"FINISHED"}


class FRESING_OT_ctx_label(_OnPart, bpy.types.Operator):
    """Adds a label pointing at the spot you right-clicked on this part. Type its words in 6 Animation > Labels, which
    opens"""

    bl_idname = "fresing.ctx_label"
    bl_label = "Add a label here"
    bl_options = {"REGISTER", "UNDO"}

    point: FloatVectorProperty(size=3, subtype="XYZ", options={"SKIP_SAVE", "HIDDEN"})

    @classmethod
    def poll(cls, context):
        return context.scene is not None and context.scene.fresing.model_count > 0

    def execute(self, context):
        from . import callouts, panels
        ob = self._ob(context)
        if ob is None:
            return {"CANCELLED"}
        point = Vector(self.point) if any(self.point) else ob.matrix_world.translation
        callouts.add(context.scene, ob, point, "Label")
        context.scene.fresing.last_message = f"Label added on '{ob.name}'"
        panels.open_to("FRESING_PT_labels")
        self.report({"INFO"}, "Label added: type its words in 6 Animation > Labels")
        return {"FINISHED"}


class FRESING_OT_ctx_joint(_OnPart, bpy.types.Operator):
    """Adds a joint that moves this part (or its subassembly): it is selected and Add joint starts – then click its
    pivot on the model (a hole or shaft, or a flat face). Esc cancels"""

    bl_idname = "fresing.ctx_joint"
    bl_label = "Add joint here…"

    def invoke(self, context, event):
        ob = self._ob(context)
        if ob is None:
            return {"CANCELLED"}
        select(context, ob, ob)
        bpy.ops.fresing.joint_add("INVOKE_DEFAULT")
        return {"FINISHED"}

    def execute(self, context):
        return self.invoke(context, None)


CLASSES = (FRESING_OT_view_menu, FRESING_OT_ctx_zoom, FRESING_OT_ctx_tree, FRESING_OT_ctx_hide, FRESING_OT_ctx_only,
           FRESING_OT_ctx_show_all, FRESING_OT_ctx_label, FRESING_OT_ctx_joint)


def register() -> None:
    pass


def unregister() -> None:
    cls = getattr(bpy.types, MENU, None)
    if cls is not None:
        from . import quiet
        quiet.unswap(cls)
    ON[0] = False
