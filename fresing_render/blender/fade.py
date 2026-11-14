"""Fade and X-ray (task 0073): a part made see-through, per object, in Cycles and EEVEE, with scripts off.

How: every material of a faded part gets one node group ("FR fade") between its shader and the output. The group
reads four *object* attributes – custom properties of the part's object, so each copy has its own:

    fr_fade            0 = the part as it is, 1 = gone (or fully X-ray); keyed by the Fade steps
    fr_xray            1 = fade to the X-ray look instead of to nothing
    fr_xray_color      the X-ray colour (linear RGB)
    fr_xray_strength   how strongly the X-ray look shows (0 … 1)

Why per object and not per material: a material is shared by every part of its group ("FR <group>"); fading a
material would fade the whole group. An object attribute is read by both engines' shaders, can be keyed like any
custom property (no Python driver), and an object without it reads 0: the material looks exactly as before, so
other parts of the same group (and old projects) are unchanged. A material is only wrapped when one of its parts
fades or is X-rayed.

A part faded out fully (stop at 0 %, not to X-ray) is also hidden from its last fade frame on (hide keys, as Hide
does): it costs nothing in later frames and casts no shadow.
"""

from __future__ import annotations

import bpy

GROUP = "FR fade"
NODE = "FR fade"                      # the group node's name in a wrapped material
TAG = "fr_fade_wrap"                  # on a wrapped material (materials.build_nodes wraps it again after a rebuild)
FADE, XRAY, XCOLOR, XSTRENGTH = "fr_fade", "fr_xray", "fr_xray_color", "fr_xray_strength"
LOOK = "fr_xray_look"                 # on an object: the X-ray look of 3 Looks (kept when an animation is cleared)
ANIM = "fr_anim_fade"                 # on an object: the last Build set its fade (cleared with the keys)
GROUP_VERSION = 4
DEFAULT_COLOR = (0.35, 0.65, 1.0)     # light blue (linear)
DEFAULT_STRENGTH = 0.7


# ---------------------------------------------------------------------------
# the shader
# ---------------------------------------------------------------------------

def node_group() -> bpy.types.NodeTree:
    ng = bpy.data.node_groups.get(GROUP)
    if ng is not None and ng.get("fr_version") == GROUP_VERSION:
        return ng
    if ng is None:
        ng = bpy.data.node_groups.new(GROUP, "ShaderNodeTree")
    ng.nodes.clear()
    for item in list(ng.interface.items_tree):
        ng.interface.remove(item)
    ng["fr_version"] = GROUP_VERSION
    ng.interface.new_socket("Shader", in_out="INPUT", socket_type="NodeSocketShader")
    ng.interface.new_socket("Shader", in_out="OUTPUT", socket_type="NodeSocketShader")
    n, L = ng.nodes, ng.links
    gin, gout = n.new("NodeGroupInput"), n.new("NodeGroupOutput")

    def attr(name, y):
        a = n.new("ShaderNodeAttribute")
        a.attribute_type = "OBJECT"
        a.attribute_name = name
        a.location = (-800, y)
        return a

    fade, xray, col, strength = attr(FADE, 200), attr(XRAY, 0), attr(XCOLOR, -200), attr(XSTRENGTH, -400)
    clear = n.new("ShaderNodeBsdfTransparent")
    # X-ray: see-through, the edges (where the surface turns away) glow in the colour; the faces facing the camera
    # stay mostly clear, so parts behind show through
    lw = n.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.5
    edge = n.new("ShaderNodeMath")
    edge.operation = "POWER"
    edge.inputs[1].default_value = 2.0
    L.new(lw.outputs["Facing"], edge.inputs[0])
    lift = n.new("ShaderNodeMath")                  # 0.55 + 0.45 x edge^2 (x strength)
    lift.operation = "MULTIPLY_ADD"
    lift.inputs[1].default_value = 0.45
    lift.inputs[2].default_value = 0.55
    L.new(edge.outputs[0], lift.inputs[0])
    amount = n.new("ShaderNodeMath")
    amount.operation = "MULTIPLY"
    amount.use_clamp = True
    L.new(lift.outputs[0], amount.inputs[0])
    L.new(strength.outputs["Fac"], amount.inputs[1])
    glow = n.new("ShaderNodeEmission")
    glow.inputs["Strength"].default_value = 1.0
    L.new(col.outputs["Color"], glow.inputs["Color"])
    ghost = n.new("ShaderNodeMixShader")
    L.new(amount.outputs[0], ghost.inputs[0])
    L.new(clear.outputs[0], ghost.inputs[1])
    L.new(glow.outputs[0], ghost.inputs[2])
    target = n.new("ShaderNodeMixShader")           # vanish, or X-ray
    L.new(xray.outputs["Fac"], target.inputs[0])
    L.new(clear.outputs[0], target.inputs[1])
    L.new(ghost.outputs[0], target.inputs[2])
    out = n.new("ShaderNodeMixShader")              # the part as it is -> the target
    L.new(fade.outputs["Fac"], out.inputs[0])
    L.new(gin.outputs[0], out.inputs[1])
    L.new(target.outputs[0], out.inputs[2])
    L.new(out.outputs[0], gout.inputs[0])
    for k, node in enumerate((lw, edge, lift, amount, glow, clear, ghost, target, out)):
        node.location = (-600 + 140 * k, -100 - 40 * (k % 2))
    gin.location, gout.location = (-800, 400), (800, 0)
    return ng


def _no_light(mat) -> None:
    """The X-ray glow must not make the material a light Cycles samples (every frame slower, task 0071)."""
    from ..core import materials_lib
    spec = materials_lib.get(mat.get("fr_material", "")) if mat.get("fr_material") else {}
    if spec.get("emission"):
        return                                 # a lamp material keeps lighting the scene
    from . import gcode
    gcode.no_light(mat)


def wrap(mat) -> bool:
    """Put the fade group between the shader and every output of ``mat``. Returns True when it changed."""
    if mat is None or mat.node_tree is None:
        return False
    nt = mat.node_tree
    ng = node_group()
    changed = False
    for out in [n for n in nt.nodes if n.bl_idname == "ShaderNodeOutputMaterial"]:
        sock = out.inputs.get("Surface")
        if sock is None or not sock.is_linked:
            continue
        src = sock.links[0].from_node
        if src.bl_idname == "ShaderNodeGroup" and src.node_tree is ng:
            continue
        node = nt.nodes.new("ShaderNodeGroup")
        node.node_tree = ng
        node.name = node.label = NODE if not nt.nodes.get(NODE) else f"{NODE} {out.name}"
        node.location = (out.location.x, out.location.y - 220)
        from_sock = sock.links[0].from_socket
        nt.links.remove(sock.links[0])
        nt.links.new(from_sock, node.inputs[0])
        nt.links.new(node.outputs[0], sock)
        changed = True
    if hasattr(mat, "use_transparent_shadow") and not mat.use_transparent_shadow:
        mat.use_transparent_shadow = True      # EEVEE: a fading part's shadow fades with it
    if hasattr(mat, "surface_render_method") and mat.surface_render_method not in ("DITHERED", "BLENDED"):
        mat.surface_render_method = "DITHERED"
    _no_light(mat)
    if not mat.get(TAG):
        mat[TAG] = True
    return changed


def is_wrapped(mat) -> bool:
    return bool(mat is not None and mat.node_tree is not None
                and any(n.bl_idname == "ShaderNodeGroup" and n.node_tree is not None and n.node_tree.name == GROUP
                        for n in mat.node_tree.nodes))


def materials_of(ob) -> list:
    out = []
    for slot in getattr(ob, "material_slots", ()):
        if slot.material is not None and slot.material not in out:
            out.append(slot.material)
    return out


def decals_of(ob) -> list:
    from . import decals
    return [c for c in ob.children if c.get("fr_kind") == decals.KIND]


def prepare(ob) -> list:
    """Wrap the materials of ``ob`` and its decals; give them the fade property (0). Returns [ob, decals...]."""
    out = [ob] + decals_of(ob)
    for o in out:
        for mat in materials_of(o):
            wrap(mat)
        if FADE not in o:
            o[FADE] = 0.0
            _ui(o)
    return out


def _ui(ob) -> None:
    try:
        ui = ob.id_properties_ui(FADE)
        ui.update(min=0.0, max=1.0, soft_min=0.0, soft_max=1.0,
                  description="How far the part has faded (0 = as it is, 1 = gone or fully X-ray). Set by Fade steps "
                              "and the X-ray look")
    except (TypeError, KeyError):
        pass


def set_xray(ob, on: bool, color=DEFAULT_COLOR, strength: float = DEFAULT_STRENGTH) -> None:
    ob[XRAY] = 1.0 if on else 0.0
    ob[XCOLOR] = [float(c) for c in color]
    ob[XSTRENGTH] = float(strength)


# ---------------------------------------------------------------------------
# the X-ray look of 3 Looks (static)
# ---------------------------------------------------------------------------

def xray_parts(scene) -> list:
    return [o for o in scene.objects if o.get(LOOK)]


_XRAY_GEN = [0]                        # + 1 whenever this module gives or takes the X-ray look
_XRAY_COUNT: dict = {"key": None, "n": 0, "at": 0.0}
XRAY_AGE = 2.0                         # s: an undo can change the look behind our back


def xray_count(scene) -> int:
    """How many parts have the X-ray look, for the side panel (bug hunt 0118 row 18a: the panel walked every object
    twice per redraw, and it redraws every frame while playing). Kept until the look is given or taken, objects come
    or go, or ``XRAY_AGE`` seconds pass."""
    import time
    key = (scene.name, len(scene.objects), _XRAY_GEN[0])
    now = time.monotonic()
    if _XRAY_COUNT["key"] != key or now - _XRAY_COUNT["at"] > XRAY_AGE:
        _XRAY_COUNT.update(key=key, n=len(xray_parts(scene)), at=now)
    return _XRAY_COUNT["n"]


def apply_look(scene, obs, color=None, strength=None) -> int:
    """Give ``obs`` (parts; their decals go along) the X-ray look. Returns how many parts."""
    s = scene.fresing
    color = tuple(s.xray_color) if color is None else color
    strength = float(s.xray_strength) if strength is None else strength
    n = 0
    for ob in obs:
        if ob.type != "MESH":
            continue
        _XRAY_GEN[0] += 1
        for o in prepare(ob):
            o[LOOK] = 1
            o[FADE] = 1.0
            set_xray(o, True, color, strength)
            o.update_tag()
        n += 1
    return n


def remove_look(scene, obs) -> int:
    n = 0
    for ob in obs:
        if not ob.get(LOOK):
            continue
        for o in [ob] + decals_of(ob):
            _plain(o)
        n += 1
    return n


def _plain(o) -> None:
    _XRAY_GEN[0] += 1
    for k in (LOOK, XRAY, XCOLOR, XSTRENGTH):
        if k in o:
            del o[k]
    if FADE in o:
        o[FADE] = 0.0
    o.update_tag()


def restyle(scene) -> None:
    """The X-ray colour or strength of 3 Looks changed: every X-ray part follows."""
    s = scene.fresing
    for o in xray_parts(scene):
        o[XCOLOR] = [float(c) for c in s.xray_color]
        o[XSTRENGTH] = float(s.xray_strength)
        o.update_tag()


def after_clear(scene) -> None:
    """'Clear keys': parts a Build faded go back to how they look without the animation."""
    s = scene.fresing
    for o in scene.objects:
        if not o.get(ANIM):
            continue
        del o[ANIM]
        if o.get(LOOK):
            o[FADE] = 1.0
            set_xray(o, True, tuple(s.xray_color), float(s.xray_strength))
        else:
            _plain(o)
