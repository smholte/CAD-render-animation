"""Show what a joint moves (task 0290, owner 23 Nov 2026).

A click on a joint in 4 Motion > Joints (or on a mechanism in 4 Motion > Mechanisms) shows, in the 3D view:

* the joint's **arrow** (its axis, drawn by this module: also when "Show joint arrows in the view" is off – the
  selected joint's only), with a ring round it for a rotate joint;
* the **parts it moves** tinted in Fresing Green; the parts of joints riding on it (a stack) in a lighter shade.

It is a picture over the view, never a selection: a following click or G acts on what the user selected. Hidden parts
stay hidden (the joint's box says "n parts hidden"). It goes away when another joint or mechanism is clicked, when the
selection in the view changes (a click elsewhere), when the list's panel is folded, while an animation plays and when
another project is opened; it never shows in renders, the web export or the PC check's timings (a draw handler of the
3D view, which draws only while the overlays are on).

Nothing runs until a joint is clicked: the draw handler is added then and removed when the show ends.
"""

from __future__ import annotations

import math

import bpy
from bpy.app.handlers import persistent
from bpy.props import StringProperty
from mathutils import Vector

from . import build

GREEN = (0.278, 0.608, 0.161)               # Fresing Green #479B29
LIGHT = (0.62, 0.85, 0.55)                  # the riders of a stack: a lighter shade
MAIN_ALPHA = 0.45
RIDER_ALPHA = 0.25
ARROW = (1.0, 0.78, 0.1, 1.0)               # the arrow: a warm yellow, seen on grey and green parts

_S: dict = {"kind": "", "name": "", "main": [], "riders": [], "sel": None, "handle": None, "obs": None}


# ---------------------------------------------------------------------------
# what a joint / mechanism moves (no drawing: tests call these)
# ---------------------------------------------------------------------------

def _meshes(objs) -> list:
    out = []
    for ob in objs:
        if ob is None:
            continue
        for d in [ob, *ob.children_recursive]:
            if d.type == "MESH" and d.get(build.PROP_KIND) in build.MODEL_KINDS:
                out.append(d)
    return list(dict.fromkeys(out))


def joint_parts(scene, j) -> tuple[list, list]:
    """(the parts ``j`` moves only by itself, the parts that also have a joint of their own: those of the joints
    riding on it – a stack – and those inside its subassembly that another joint moves): mesh objects, each once."""
    from . import joints
    above = []
    for r in joints.all_riders(scene, j):
        above += joints.members(r)
    for other in scene.fresing.joints:
        if other.name != j.name:
            above += joints.members(other)
    own = _meshes(joints.members(j))
    others = {o.name for o in _meshes(above)}
    riders_of = {o.name for r in joints.all_riders(scene, j) for o in _meshes(joints.members(r))}
    main = [o for o in own if o.name not in others]
    riders = [o for o in own if o.name in others] + [o for o in _meshes(above) if o.name in riders_of]
    return main, list(dict.fromkeys(riders))


def mechanism_parts(scene, m) -> tuple[list, list]:
    """(the parts of the mechanism's moving links, [])."""
    from . import linkages
    return _meshes(linkages.all_link_objs(m)), []


def hidden_count(scene, j) -> int:
    """How many of the parts ``j`` moves (riders too) are hidden in the view now."""
    try:
        main, riders = joint_parts(scene, j)
        return sum(1 for o in main + riders if not o.visible_get())
    except (ReferenceError, AttributeError):
        return 0


# ---------------------------------------------------------------------------
# the state
# ---------------------------------------------------------------------------

def _sel_sig(context=None) -> tuple:
    context = context or bpy.context
    try:
        act = context.view_layer.objects.active
        return (act.name if act is not None else "", len(context.selected_objects))
    except (AttributeError, ReferenceError):
        return ("", 0)


def active() -> dict:
    """What is shown now: {"kind": "joint" / "mechanism" / "", "name", "main", "riders"} (object names)."""
    return {"kind": _S["kind"], "name": _S["name"], "main": list(_S["main"]), "riders": list(_S["riders"])}


def show(scene, kind: str, name: str) -> None:
    """Show a joint ("joint") or a mechanism ("mechanism") by name; '' or a name not there clears."""
    s = scene.fresing
    if kind == "joint":
        item = s.joints.get(name)
        parts = joint_parts(scene, item) if item is not None else None
    else:
        item = s.mechanisms.get(name)
        parts = mechanism_parts(scene, item) if item is not None else None
    if parts is None:
        clear()
        return
    _S.update(kind=kind, name=name, main=[o.name for o in parts[0]], riders=[o.name for o in parts[1]],
              sel=_sel_sig(), obs=None)
    if not bpy.app.background and _S["handle"] is None:
        _S["handle"] = bpy.types.SpaceView3D.draw_handler_add(_draw, (), "WINDOW", "POST_VIEW")
    _redraw()


def clear() -> None:
    had = bool(_S["kind"])
    _S.update(kind="", name="", main=[], riders=[], sel=None, obs=None)
    if _S["handle"] is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_S["handle"], "WINDOW")
        except (ValueError, RuntimeError):
            pass
        _S["handle"] = None
    if had:
        _redraw()


def _redraw() -> None:
    wm = getattr(bpy.context, "window_manager", None)
    for win in getattr(wm, "windows", ()):
        for area in win.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


def joint_clicked(s, context) -> None:
    """``joints_index`` changed (a click on the list): show that joint."""
    if 0 <= s.joints_index < len(s.joints):
        show(context.scene, "joint", s.joints[s.joints_index].name)
    else:
        clear()


def mechanism_clicked(s, context) -> None:
    if 0 <= s.mechanisms_index < len(s.mechanisms):
        show(context.scene, "mechanism", s.mechanisms[s.mechanisms_index].name)
    else:
        clear()


def still_wanted(context=None) -> bool:
    """False once the show should end: the selection changed, the item is gone or no longer the list's own, its
    panel is folded, or the animation plays."""
    context = context or bpy.context
    if not _S["kind"]:
        return False
    scene = context.scene
    s = getattr(scene, "fresing", None)
    if s is None:
        return False
    if _sel_sig(context) != _S["sel"]:
        return False
    if _S["kind"] == "joint":
        ok = 0 <= s.joints_index < len(s.joints) and s.joints[s.joints_index].name == _S["name"]
        panel = "FRESING_PT_joints"
    else:
        ok = 0 <= s.mechanisms_index < len(s.mechanisms) and s.mechanisms[s.mechanisms_index].name == _S["name"]
        panel = "FRESING_PT_mechanisms"
    if not ok:
        return False
    from . import panels
    if not panels.is_open(panel) or not panels.is_open("FRESING_PT_motion"):
        return False
    screen = getattr(context, "screen", None)
    return not (screen is not None and screen.is_animation_playing)


# ---------------------------------------------------------------------------
# drawing
# ---------------------------------------------------------------------------

def _objects(names) -> list:
    get = bpy.data.objects.get
    return [o for o in map(get, names) if o is not None and o.type == "MESH"]


def axis_lines(origin: Vector, direction: Vector, size: float, rotate: bool) -> list:
    """The arrow as line pieces (pairs of points): the shaft through the pivot, a head of four strokes at its tip and,
    for a rotate joint, a ring of 32 pieces round the axis."""
    d = direction.normalized()
    side = d.orthogonal().normalized()
    other = d.cross(side).normalized()
    a, b = origin - d * size * 0.6, origin + d * size
    out = [a, b]
    head = size * 0.15
    for v in (side, -side, other, -other):
        out += [b, b - d * head + v * head * 0.45]
    if rotate:
        r = size * 0.3
        pts = [origin + (side * math.cos(t) + other * math.sin(t)) * r
               for t in (2 * math.pi * k / 32 for k in range(33))]
        for p, q in zip(pts, pts[1:]):
            out += [p, q]
    return out


def _arrow():
    """(origin, direction, size, rotate) of the shown joint (a mechanism: its drive joint), or None."""
    from . import joints, linkages
    scene = bpy.context.scene
    s = scene.fresing
    if _S["kind"] == "joint":
        j = s.joints.get(_S["name"])
    else:
        m = s.mechanisms.get(_S["name"])
        j = linkages.input_joint(scene, m) if m is not None else None
    if j is None or j.frame is None:
        return None
    o, d = joints.axis_world(j)
    obs = _objects(_S["main"])
    size = 0.3
    if obs:
        mn, mx = build.world_bounds(obs)
        size = max(0.05, 0.35 * (Vector(mx) - Vector(mn)).length)
    return o, d, size, j.kind == "ROTATE"


def _fill(obs, rgba) -> None:
    import gpu

    from . import highlight
    sh = gpu.shader.from_builtin("UNIFORM_COLOR")
    for ob in obs:
        batch = highlight._geo(ob, False)
        if not batch:
            continue
        gpu.matrix.push()
        gpu.matrix.multiply_matrix(ob.matrix_world)
        sh.uniform_float("color", rgba)
        batch.draw(sh)
        gpu.matrix.pop()


def _draw() -> None:
    try:
        context = bpy.context
        space = context.space_data
        if space is None or not space.overlay.show_overlays:
            return
        if not still_wanted(context):
            bpy.app.timers.register(clear, first_interval=0.0)     # not from inside a draw handler
            return
        import gpu
        from gpu_extras.batch import batch_for_shader
        gpu.state.blend_set("ALPHA")
        gpu.state.depth_test_set("LESS_EQUAL")
        gpu.state.depth_mask_set(False)
        main = [o for o in _objects(_S["main"]) if o.visible_get()]
        riders = [o for o in _objects(_S["riders"]) if o.visible_get()]
        _fill(riders, (*LIGHT, RIDER_ALPHA))
        _fill(main, (*GREEN, MAIN_ALPHA))
        arrow = _arrow()
        if arrow is not None:
            gpu.state.depth_test_set("NONE")
            sh = gpu.shader.from_builtin("POLYLINE_UNIFORM_COLOR")
            region = context.region
            sh.uniform_float("viewportSize", (region.width, region.height))
            sh.uniform_float("lineWidth", 3.0)
            sh.uniform_float("color", ARROW)
            lines = [tuple(p) for p in axis_lines(*arrow)]
            batch_for_shader(sh, "LINES", {"pos": lines}).draw(sh)
        gpu.state.depth_test_set("NONE")
        gpu.state.blend_set("NONE")
    except Exception as e:  # noqa: BLE001 - drawing must never break the view
        print("Fresing Render (joint show):", e)


# ---------------------------------------------------------------------------
# the warning on a value row (task 0290: the panel stays still)
# ---------------------------------------------------------------------------

FALLBACK = "The value is past the limits set for it now: check the ratio of the joint it follows, or the limits"


class FRESING_OT_limits_note(bpy.types.Operator):
    """The value is past the limits set for it now: check the ratio of the joint it follows, or the limits"""

    bl_idname = "fresing.limits_note"
    bl_label = "Beyond limits"
    bl_options = {"INTERNAL"}

    why: StringProperty(options={"SKIP_SAVE", "HIDDEN"})

    @classmethod
    def description(cls, context, properties):
        return properties.why or FALLBACK

    def execute(self, context):
        self.report({"WARNING"}, self.why or FALLBACK)
        return {"FINISHED"}


CLASSES = (FRESING_OT_limits_note,)


@persistent
def _on_load(_dummy=None) -> None:
    clear()


def register() -> None:
    if _on_load not in bpy.app.handlers.load_pre:
        bpy.app.handlers.load_pre.append(_on_load)


def unregister() -> None:
    clear()
    while _on_load in bpy.app.handlers.load_pre:
        bpy.app.handlers.load_pre.remove(_on_load)

