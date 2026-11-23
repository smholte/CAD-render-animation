"""Moving and turning models, subassemblies and parts in the 3D view (task 0307; the Place lane – task 0292 adds the
fields, the gizmo and Remove here).

Blender's own G / R / S move, turn and scale what is selected. In this app they did nothing for the owner: the numbers
showed in the header while moving, and on a click or Enter the part was back. The causes (task 0307's report):

* **Locked in place.** An import locks every subassembly and part (``logic.lock_all``: ``lock_location`` /
  ``lock_rotation`` / ``lock_scale``), so a subassembly moves only with the one it is in. Blender's G then runs, shows
  its numbers and moves nothing – silently. Unlocking (2 Structure > Locked in place, or the right-click menu's
  **Unlock so it can move**) lets G / R move it, and the move stays.
* **A built animation.** Build & play saves how things stood and puts that back at the next Build and at Stop: a
  move made while an animation is built is undone later, without a word.
* **Scale.** Parts keep their CAD size (``lock_scale`` is always on): S never scales them.
* **The Client view** locks everything (``lock.py``): G says so (``fresing.move_key`` is in ``lock.ALLOWED``).

So the app's own key (``fresing.move_key`` on G / R / S in Object Mode, ``lock.APP_KEYS``) looks at what would move
before Blender does: when nothing of it can move, it says why in the status bar at once and Blender's G is not
started; otherwise it passes the key on to Blender (``PASS_THROUGH``), unchanged.
"""

from __future__ import annotations

import bpy
from bpy.props import EnumProperty

from . import build

MODES = (("TRANSLATE", "Move", "G: move"), ("ROTATE", "Turn", "R: turn"), ("RESIZE", "Scale", "S: scale"))
LAST = [""]                 # the last message (tests, the PC check)
STOPPED = [0]               # keys that did not start Blender's move (tests, the PC check)


def _name(ob) -> str:
    return ob.get(build.PROP_NAME) or ob.name


def movers(context) -> list:
    """What Blender's G / R would move: the selected model objects without a selected object above them (Blender
    moves a selected child with its selected parent, not on its own)."""
    sel = [o for o in context.selected_objects]
    chosen = set(o.name for o in sel)
    out = []
    for ob in sel:
        if ob.get(build.PROP_KIND) not in build.MODEL_KINDS:
            continue
        p = ob.parent
        while p is not None and p.name not in chosen:
            p = p.parent
        if p is None:
            out.append(ob)
    return out


def lock_owner(ob):
    """The subassembly whose lock holds ``ob``: itself when it is one, else the nearest one above it."""
    p = ob
    while p is not None and p.get(build.PROP_KIND) != "assembly":
        p = build.logical_parent(p)
    return p


def _locked(ob, mode: str) -> bool:
    lk = {"TRANSLATE": ob.lock_location, "ROTATE": ob.lock_rotation, "RESIZE": ob.lock_scale}[mode]
    return all(lk)


def why_not(context, mode: str) -> tuple:
    """(message, how many of the movers cannot move) – ("", 0) when Blender's key may run as it is."""
    from ..core import places
    from . import animation, lock
    scene = context.scene
    if lock.ON[0]:                                   # the Client view: nothing can be selected, nothing moves
        return lock.MESSAGE, 1
    obs = movers(context)
    if not obs:
        return "", 0
    if animation.has_keys(scene):
        what = {"TRANSLATE": "move", "ROTATE": "turn", "RESIZE": "scale"}[mode]
        return (f"The animation is built: a {what} now would be undone at the next Build. Stop it first "
                f"({places.where('motion')} > Stop it to move joints by hand), then press the key again"), len(obs)
    held = [o for o in obs if _locked(o, mode)]
    if not held:
        return "", 0
    if mode == "RESIZE":
        return "Parts keep their size from the CAD model: S does not scale them", len(held)
    owner = lock_owner(held[0]) or held[0]
    return (f"'{_name(owner)}' is locked in place – right-click it > Unlock so it can move (or "
            f"{places.where('structure')} > Locked in place), then press the key again"), len(held)


class FRESING_OT_move_key(bpy.types.Operator):
    """G / R / S in the 3D view: move, turn or scale what is selected, as in Blender. When it cannot move (locked in
    place, or an animation is built that would undo the move), the status bar says why at once, and what to do"""

    bl_idname = "fresing.move_key"
    bl_label = "Move / turn"
    bl_options = {"INTERNAL"}

    mode: EnumProperty(items=MODES, options={"SKIP_SAVE", "HIDDEN"})

    @classmethod
    def poll(cls, context):
        scene = getattr(context, "scene", None)
        return (context.mode == "OBJECT" and scene is not None and getattr(scene, "fresing", None) is not None
                and context.area is not None and context.area.type == "VIEW_3D")

    def _check(self, context):
        msg, n = why_not(context, self.mode)
        if not msg:
            return {"PASS_THROUGH"}
        LAST[0] = msg
        self.report({"WARNING"}, msg)
        if n < len(movers(context)):                 # some of it can move: Blender moves those
            return {"PASS_THROUGH"}
        STOPPED[0] += 1
        return {"CANCELLED"}

    def invoke(self, context, event):
        return self._check(context)

    def execute(self, context):                      # scripts and tests: the check alone
        res = self._check(context)
        return {"FINISHED"} if res == {"PASS_THROUGH"} else res


class FRESING_OT_ctx_unlock(bpy.types.Operator):
    """Unlocks the subassembly you right-clicked, so G moves it and R turns it (it stays where you put it); click again
    to lock it in place. Locked, it moves only with the subassembly it is in. Same as 2 Structure > Locked in place"""

    bl_idname = "fresing.ctx_unlock"
    bl_label = "Unlock so it can move"
    bl_options = {"REGISTER", "UNDO"}

    part: bpy.props.StringProperty(options={"SKIP_SAVE", "HIDDEN"})

    def execute(self, context):
        from . import logic
        ob = bpy.data.objects.get(self.part) if self.part else None
        owner = lock_owner(ob) if ob is not None else None
        if owner is None or owner.name not in context.scene.objects:
            self.report({"WARNING"}, "Right-click a part in the 3D view first")
            return {"CANCELLED"}
        locked = not owner.get(build.PROP_LOCKED, True)
        logic.set_locked(owner, locked)
        self.report({"INFO"}, f"'{_name(owner)}' is " + ("locked in place" if locked
                                                         else "unlocked: G moves it, R turns it"))
        return {"FINISHED"}


def menu_text(ob) -> str:
    """The right-click menu's entry for the lock of ``ob``'s subassembly."""
    owner = lock_owner(ob) if ob is not None else None
    if owner is not None and not owner.get(build.PROP_LOCKED, True):
        return "Lock in place"
    return "Unlock so it can move"


CLASSES = (FRESING_OT_move_key, FRESING_OT_ctx_unlock)
