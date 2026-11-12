"""Cutaway / section view (task 0086): a plane or box cut through chosen parts, the cut faces filled with a cap colour.

How it renders (the shader way, no boolean on the meshes): every material of a cut part gets one node group
("FR section") between its shader and the output – inside the Fade group of task 0073 when there is one, so a part
can be cut *and* fade. For each cut the group asks:

* is this part cut by it? An *object* attribute ``fr_cut_<key>`` (a custom property of the part's object, 1 = yes):
  materials are shared by a whole group, the attribute keeps the cut per part; a part without it reads 0 and looks
  exactly as before (old projects too);
* where is the shading point in the cut's own space? Texture Coordinate > Object with the cut's shape object, so the
  cut follows that object in every frame (Cycles and EEVEE, scripts off, the render queue);
* a plane takes away the side its arrow points to (Flip: the other side), a box what is inside it (Flip: outside).

What a cut takes away is transparent for every ray (the camera, light, shadows): light falls through the hole as it
would through a real cut. Through the hole the camera sees the *inside* of the solid (its back faces): those are
drawn in the cut's cap colour, lit as if they faced out of the cut (the normal of the cut face nearest to them; the
cut's turn in the world comes from drivers on the node values – AVERAGE drivers with a transform variable, no Python).
Hatch lines are worked out on the cut face itself (the view ray meets the cut plane). Caps are right only for closed
solids: an open shell shows its inside face in the cap colour.

Moving the cut: its place is an app-made **slide joint** (the joint frame is the handle the user moves in the view;
the shape object follows the joint's motion empty by a Child Of constraint), so the Move joint step, poses, saved
scenes and the render queue move it like any joint – nothing new in the animation code. The joint's motion carries
``fr_atc`` ("cut") as the double arm's joints do (task 0064): never taken as a CNC axis.
"""

from __future__ import annotations

import bpy
from mathutils import Matrix, Vector

from ..core import section as core
from . import build

GROUP = "FR section"
NODE = "FR section"                   # the group node's name in a wrapped material
TAG = "fr_section_wrap"               # on a wrapped material (materials.build_nodes wraps it again after a rebuild)
ATTR = "fr_cut_"                      # + key: on a part's object, 1 = this cut cuts it
NOCAP = "fr_cut_nocap"                # on an object: never caps (decals: thin sheets on a part's face)
KEY = "fr_section"                    # on a cut's frame, motion and shape objects: the cut's key
APP_TAG = "fr_atc"                    # the double arm's tag (task 0064): an app-made joint, never a CNC axis
GROUP_VERSION = 1
FLOOR_GAP = 0.0001                    # the floor 0.1 mm under the model while there are cuts (else it ties with the
                                      # inside of the bottom face and shows through the cut face)
TRANSPARENT_STEPS = 128               # Cycles: a view ray through a cut passes many cut-away faces (default 8: black)
PLANE_THICK = 0.0005                  # the plane's shape object: a thin box (only drawn in the view)
CAP_ROUGHNESS = 0.55
HATCH_DARK = 0.22                     # hatch lines: the cap colour times this
HATCH_WIDTH = 0.16                    # share of the spacing that is line


# ---------------------------------------------------------------------------
# lookups
# ---------------------------------------------------------------------------

def cuts(scene):
    return scene.fresing.cuts


def active(scene):
    s = scene.fresing
    return s.cuts[s.cuts_index] if 0 <= s.cuts_index < len(s.cuts) else None


def find(scene, key: str):
    return next((c for c in scene.fresing.cuts if c.key == key), None)


def joint_of(scene, cut):
    """The cut's slide joint (found by the tag on its motion empty: the user may rename it in 4 Motion)."""
    for j in scene.fresing.joints:
        if j.motion is not None and j.motion.get(KEY) == cut.key:
            return j
    return None


def is_cut_joint(j) -> bool:
    return j.motion is not None and bool(j.motion.get(KEY))


def status(scene) -> str:
    cs = scene.fresing.cuts
    return core.status(len(cs), sum(1 for c in cs if c.enabled))


def _new_key(scene) -> str:
    keys = {c.key for c in scene.fresing.cuts}
    n = 1
    while f"c{n}" in keys:
        n += 1
    return f"c{n}"


def _unique_name(scene, base: str = "Cut") -> str:
    names = {c.name for c in scene.fresing.cuts} | {j.name for j in scene.fresing.joints}
    n = 1
    while f"{base} {n}" in names:
        n += 1
    return f"{base} {n}"


# ---------------------------------------------------------------------------
# what a cut cuts
# ---------------------------------------------------------------------------

def _parts_under(scene, ob, tree=None) -> list:
    from . import logic
    tree = tree or logic.Tree(scene)
    return [o for o in [ob] + tree.descendants(ob) if o.type == "MESH" and o.get(build.PROP_KIND) == "part"]


def _decals_of(ob) -> list:
    return [c for c in ob.children if c.get(build.PROP_KIND) == "decal"]


def target_parts(scene, cut, tree=None) -> list:
    """The parts ``cut`` cuts (each once)."""
    from . import logic
    tree = tree or logic.Tree(scene)
    out, seen = [], set()
    for t in cut.targets:
        if t.kind == "GROUP":
            parts = [o for o in build.iter_parts(scene) if o.get(build.PROP_GROUP, "") == t.name]
        elif t.obj is not None and t.obj.name in scene.objects:
            parts = _parts_under(scene, t.obj, tree)
        else:
            parts = []
        for o in parts:
            if o.name not in seen:
                seen.add(o.name)
                out.append(o)
    return out


def _root_of(ob):
    while True:
        p = build.logical_parent(ob)
        if p is None:
            return ob
        ob = p


def cut_root(scene, cut):
    """The model the cut sits on (its joint's base): the root of its first target."""
    for t in cut.targets:
        if t.kind == "GROUP":
            parts = [o for o in build.iter_parts(scene) if o.get(build.PROP_GROUP, "") == t.name]
            if parts:
                return _root_of(parts[0])
        elif t.obj is not None:
            return _root_of(t.obj)
    roots = build.model_roots(scene)
    return roots[0] if roots else None


def add_target(cut, kind: str, ob=None, name: str = "") -> None:
    for t in cut.targets:
        if t.kind == kind and ((kind == "GROUP" and t.name == name) or (kind != "GROUP" and t.obj is ob)):
            return
    t = cut.targets.add()
    t.kind = kind
    if kind == "GROUP":
        t.name = name
    else:
        t.obj = ob
        t.uid = ob.get(build.PROP_UID, "")
        t.name = ob.get(build.PROP_NAME, ob.name)


def target_label(t) -> str:
    return core.target_label(t.kind, t.name)


def bounds(objs):
    """World box (min, max) of ``objs``' shapes, or None."""
    lo = Vector((1e30,) * 3)
    hi = Vector((-1e30,) * 3)
    any_ = False
    for o in objs:
        if o.type != "MESH":
            continue
        m = o.matrix_world
        for c in o.bound_box:
            p = m @ Vector(c)
            lo = Vector(map(min, lo, p))
            hi = Vector(map(max, hi, p))
            any_ = True
    return (lo, hi) if any_ else None


# ---------------------------------------------------------------------------
# the shader
# ---------------------------------------------------------------------------

class _B:
    """Small helper for building the group's nodes."""

    def __init__(self, nt):
        self.nt = nt
        self.y = 0

    def node(self, kind, x=0.0, y=None, name=None, **values):
        n = self.nt.nodes.new(kind)
        n.location = (x, self.y if y is None else y)
        if name:
            n.name = n.label = name
        for k, v in values.items():
            setattr(n, k, v)
        return n

    def put(self, sock, v):
        if isinstance(v, bpy.types.NodeSocket):
            self.nt.links.new(v, sock)
        elif v is not None:
            sock.default_value = v

    def math(self, op, a, b=None, c=None, x=0.0):
        n = self.node("ShaderNodeMath", x, operation=op)
        for i, v in enumerate((a, b, c)):
            if v is not None:
                self.put(n.inputs[i], v)
        return n.outputs[0]

    def vmath(self, op, a, b=None, scale=None, x=0.0):
        n = self.node("ShaderNodeVectorMath", x, operation=op)
        self.put(n.inputs[0], a)
        if b is not None:
            self.put(n.inputs[1], b)
        if scale is not None:
            self.put(n.inputs["Scale"], scale)
        return n.outputs["Value" if op in ("DOT_PRODUCT", "LENGTH", "DISTANCE") else "Vector"]

    def sep(self, v, x=0.0):
        n = self.node("ShaderNodeSeparateXYZ", x)
        self.put(n.inputs[0], v)
        return n.outputs[0], n.outputs[1], n.outputs[2]

    def combine(self, a, b, c, x=0.0, name=None):
        n = self.node("ShaderNodeCombineXYZ", x, name=name)
        for i, v in enumerate((a, b, c)):
            self.put(n.inputs[i], v)
        return n.outputs[0]

    def value(self, name, v, x=0.0):
        n = self.node("ShaderNodeValue", x, name=name)
        n.outputs[0].default_value = float(v)
        return n.outputs[0]

    def mixf(self, fac, a, b, x=0.0):
        n = self.node("ShaderNodeMix", x, data_type="FLOAT")
        n.clamp_factor = True
        self.put(n.inputs[0], fac)
        self.put(n.inputs[2], a)
        self.put(n.inputs[3], b)
        return n.outputs[0]

    def mixv(self, fac, a, b, x=0.0):
        n = self.node("ShaderNodeMix", x, data_type="VECTOR")
        n.clamp_factor = True
        self.put(n.inputs[0], fac)
        self.put(n.inputs[4], a)
        self.put(n.inputs[5], b)
        return n.outputs[1]

    def mixc(self, fac, a, b, x=0.0):
        n = self.node("ShaderNodeMix", x, data_type="RGBA")
        n.clamp_factor = True
        self.put(n.inputs[0], fac)
        self.put(n.inputs[6], a)
        self.put(n.inputs[7], b)
        return n.outputs[2]


def _transform_driver(sock, ob, transform_type: str) -> None:
    """``sock`` follows a world-space transform channel of ``ob`` (AVERAGE driver: no Python, scripts off)."""
    fc = sock.driver_add("default_value")
    drv = fc.driver
    drv.type = "AVERAGE"
    for v in list(drv.variables):
        drv.variables.remove(v)
    var = drv.variables.new()
    var.name = "t"
    var.type = "TRANSFORMS"
    t = var.targets[0]
    t.id = ob
    t.transform_type = transform_type
    t.transform_space = "WORLD_SPACE"
    t.rotation_mode = "XYZ"


def _driven_xyz(b, name, ob, kind: str, x=0.0):
    out = b.combine(0.0, 0.0, 0.0, x=x, name=name)
    node = out.node
    for i, ax in enumerate("XYZ"):
        _transform_driver(node.inputs[i], ob, f"{kind}_{ax}")
    return out


def _cut_block(b, cut, incoming):
    """The nodes of one cut. Returns (taken away, active, distance to the cut face, cap normal in the world, cap
    colour)."""
    k = cut.key
    tc = b.node("ShaderNodeTexCoord", -1600, name=f"{k} space")
    tc.object = cut.shape
    p = tc.outputs["Object"]                                   # in the shape's space (its scale: 1 = its edge)
    h = _driven_xyz(b, f"{k} scale", cut.shape, "SCALE", x=-1600)
    turn = _driven_xyz(b, f"{k} turn", cut.shape, "ROT", x=-1600)
    on = b.value(f"{k} on", 1.0 if cut.enabled else 0.0, x=-1400)
    s = b.value(f"{k} flip", -1.0 if cut.flip else 1.0, x=-1400)
    box = b.value(f"{k} box", 1.0 if cut.shape_kind == "BOX" else 0.0, x=-1400)
    hatch = b.value(f"{k} hatch", 1.0 if cut.hatch else 0.0, x=-1400)
    spacing = b.value(f"{k} spacing", max(1e-4, cut.hatch_spacing), x=-1400)
    col = b.node("ShaderNodeRGB", -1400, name=f"{k} colour")
    col.outputs[0].default_value = (*cut.color, 1.0)
    member = b.node("ShaderNodeAttribute", -1400, name=f"{k} member", attribute_type="OBJECT",
                    attribute_name=ATTR + k).outputs["Fac"]
    act = b.math("MULTIPLY", on, member, x=-1200)

    m = b.vmath("MULTIPLY", p, h, x=-1200)                     # metres in the cut's own frame
    _mx, _my, mz = b.sep(m, x=-1000)
    # plane: takes away s * z > 0
    gone_p = b.math("GREATER_THAN", b.math("MULTIPLY", s, mz, x=-800), 0.0, x=-600)
    n_p = b.combine(0.0, 0.0, s, x=-600)
    dist_p = b.math("ABSOLUTE", mz, x=-600)
    # box: f_i = (|p_i| - 1) h_i, how far outside each pair of faces; F = the largest
    f = b.vmath("MULTIPLY", b.vmath("SUBTRACT", b.vmath("ABSOLUTE", p, x=-1000), (1.0, 1.0, 1.0), x=-900), h, x=-800)
    fx, fy, fz = b.sep(f, x=-700)
    big = b.math("MAXIMUM", fx, b.math("MAXIMUM", fy, fz, x=-650), x=-600)
    is_x = b.math("MULTIPLY", b.math("SUBTRACT", 1.0, b.math("GREATER_THAN", fy, fx, x=-600), x=-550),
                  b.math("SUBTRACT", 1.0, b.math("GREATER_THAN", fz, fx, x=-600), x=-550), x=-500)
    is_y = b.math("MULTIPLY", b.math("SUBTRACT", 1.0, is_x, x=-500),
                  b.math("SUBTRACT", 1.0, b.math("GREATER_THAN", fz, fy, x=-600), x=-550), x=-450)
    is_z = b.math("SUBTRACT", b.math("SUBTRACT", 1.0, is_x, x=-450), is_y, x=-400)
    sg = b.vmath("SIGN", p, x=-700)
    sx, sy, sz = b.sep(sg, x=-600)
    neg_s = b.math("MULTIPLY", s, -1.0, x=-600)
    n_b = b.combine(b.math("MULTIPLY", b.math("MULTIPLY", neg_s, sx, x=-400), is_x, x=-350),
                    b.math("MULTIPLY", b.math("MULTIPLY", neg_s, sy, x=-400), is_y, x=-350),
                    b.math("MULTIPLY", b.math("MULTIPLY", neg_s, sz, x=-400), is_z, x=-350), x=-300)
    gone_b = b.math("LESS_THAN", b.math("MULTIPLY", s, big, x=-500), 0.0, x=-400)
    dist_b = b.math("ABSOLUTE", big, x=-400)
    c_b = b.vmath("DOT_PRODUCT", n_b, b.vmath("MULTIPLY", sg, h, x=-400), x=-250)
    # the shape picks plane or box
    gone = b.mixf(box, gone_p, gone_b, x=-200)
    n_local = b.mixv(box, n_p, n_b, x=-200)
    dist = b.mixf(box, dist_p, dist_b, x=-200)
    c = b.math("MULTIPLY", box, c_b, x=-200)
    # the cap normal in the world: turned like the shape
    rot = b.node("ShaderNodeVectorRotate", -50, rotation_type="EULER_XYZ")
    b.put(rot.inputs["Vector"], n_local)
    b.put(rot.inputs["Rotation"], turn)
    n_world = rot.outputs[0]
    # hatch lines on the cut face: where the view ray meets it (q), lines across its two directions
    inv = b.node("ShaderNodeVectorRotate", -50, rotation_type="EULER_XYZ", invert=True)
    b.put(inv.inputs["Vector"], incoming)
    b.put(inv.inputs["Rotation"], turn)
    i_l = inv.outputs[0]
    t = b.math("DIVIDE", b.math("SUBTRACT", c, b.vmath("DOT_PRODUCT", m, n_local, x=-50), x=0),
               b.vmath("DOT_PRODUCT", i_l, n_local, x=0), x=50)
    q = b.vmath("ADD", m, b.vmath("SCALE", i_l, scale=t, x=100), x=150)
    qx, qy, qz = b.sep(q, x=200)
    nx, ny, nz = b.sep(n_local, x=200)
    total = b.math("ADD", b.math("ADD", qx, qy, x=250), qz, x=300)
    along = b.math("MULTIPLY", b.vmath("DOT_PRODUCT", q, n_local, x=250),
                   b.math("ADD", b.math("ADD", nx, ny, x=250), nz, x=300), x=350)
    u = b.math("DIVIDE", b.math("SUBTRACT", total, along, x=400), spacing, x=450)
    line = b.math("MULTIPLY", b.math("LESS_THAN", b.math("FRACT", u, x=500), HATCH_WIDTH, x=550), hatch, x=600)
    dark = b.node("ShaderNodeMix", 600, data_type="RGBA")
    dark.blend_type = "MULTIPLY"
    dark.clamp_factor = True
    b.put(dark.inputs[0], 1.0)
    b.put(dark.inputs[6], col.outputs[0])
    b.put(dark.inputs[7], (HATCH_DARK, HATCH_DARK, HATCH_DARK, 1.0))
    cap = b.mixc(line, col.outputs[0], dark.outputs[2], x=650)
    return b.math("MULTIPLY", gone, act, x=700), act, dist, n_world, cap


def _build(ng, scene) -> None:
    ng.animation_data_clear()
    ng.nodes.clear()
    # the sockets stay when they are right: removing them would cut the links in every wrapped material
    want = [("INPUT", "Shader", "NodeSocketShader"), ("INPUT", "Caps", "NodeSocketFloat"),
            ("OUTPUT", "Shader", "NodeSocketShader")]
    have = [(i.in_out, i.name, i.socket_type) for i in ng.interface.items_tree if i.item_type == "SOCKET"]
    if sorted(have) != sorted(want):
        for item in list(ng.interface.items_tree):
            ng.interface.remove(item)
        for in_out, name, kind in want:
            sock = ng.interface.new_socket(name, in_out=in_out, socket_type=kind)
            if name == "Caps":
                sock.default_value, sock.min_value, sock.max_value = 1.0, 0.0, 1.0
    b = _B(ng)
    gin = b.node("NodeGroupInput", -2000, 300)
    gout = b.node("NodeGroupOutput", 1600, 300)
    live = [c for c in scene.fresing.cuts if c.shape is not None]
    if not live:
        b.put(gout.inputs[0], gin.outputs[0])
        return
    geo = b.node("ShaderNodeNewGeometry", -1800, 300)
    gone_all = act_all = best_key = best_n = best_col = None
    for i, cut in enumerate(live):
        b.y = -900 * i
        gone, act, dist, n_world, cap = _cut_block(b, cut, geo.outputs["Incoming"])
        key = b.math("ADD", dist, b.math("MULTIPLY", b.math("SUBTRACT", 1.0, act, x=750), 1e9, x=800), x=850)
        if gone_all is None:
            gone_all, act_all, best_key, best_n, best_col = gone, act, key, n_world, cap
            continue
        gone_all = b.math("MAXIMUM", gone_all, gone, x=900)
        act_all = b.math("MAXIMUM", act_all, act, x=900)
        take = b.math("LESS_THAN", key, best_key, x=900)          # the nearest cut face of the cuts on this part
        best_key = b.math("MINIMUM", key, best_key, x=950)
        best_n = b.mixv(take, best_n, n_world, x=950)
        best_col = b.mixc(take, best_col, cap, x=950)
    b.y = 300
    nocap = b.node("ShaderNodeAttribute", 900, attribute_type="OBJECT", attribute_name=NOCAP).outputs["Fac"]
    caps = b.math("MULTIPLY", gin.outputs["Caps"], b.math("SUBTRACT", 1.0, nocap, x=1000), x=1050)
    kept = b.math("SUBTRACT", 1.0, gone_all, x=1000)
    zone = b.math("MULTIPLY", b.math("MULTIPLY", geo.outputs["Backfacing"], act_all, x=1050),
                  b.math("MULTIPLY", kept, caps, x=1100), x=1150)        # the inside, seen through the hole
    # the cap is drawn on the solid's far inside wall, not on the cut face itself: light and bounces from there
    # would be blocked by the solid's own walls (the cap went black). So only the camera and reflections see the
    # cap; light and bounce rays pass through the inside walls, and the cap is lit as an open cut face would be.
    path = b.node("ShaderNodeLightPath", 1000, 700)
    sees = b.math("MAXIMUM", path.outputs["Is Camera Ray"], path.outputs["Is Glossy Ray"], x=1100)
    cap_fac = b.math("MULTIPLY", zone, sees, x=1200)
    gone_all = b.math("MAXIMUM", gone_all, b.math("MULTIPLY", zone, b.math("SUBTRACT", 1.0, sees, x=1150), x=1200),
                      x=1250)
    bsdf = b.node("ShaderNodeBsdfPrincipled", 1150, -200)
    b.put(bsdf.inputs["Base Color"], best_col)
    b.put(bsdf.inputs["Roughness"], CAP_ROUGHNESS)
    b.put(bsdf.inputs["Metallic"], 0.0)
    b.put(bsdf.inputs["Normal"], b.vmath("NORMALIZE", best_n, x=1100))
    clear = b.node("ShaderNodeBsdfTransparent", 1150, 500)
    hole = b.node("ShaderNodeMixShader", 1300, 400)
    b.put(hole.inputs[0], gone_all)
    b.put(hole.inputs[1], gin.outputs[0])
    b.put(hole.inputs[2], clear.outputs[0])
    out = b.node("ShaderNodeMixShader", 1450, 300)
    b.put(out.inputs[0], cap_fac)
    b.put(out.inputs[1], hole.outputs[0])
    b.put(out.inputs[2], bsdf.outputs[0])
    b.put(gout.inputs[0], out.outputs[0])


def _signature(scene) -> str:
    return "|".join([str(GROUP_VERSION)] + [f"{c.key}:{c.shape.name}" for c in scene.fresing.cuts
                                            if c.shape is not None])


def node_group(scene, rebuild: bool = False) -> bpy.types.NodeTree:
    """The shared group, built for the project's cuts (built again when cuts come or go)."""
    ng = bpy.data.node_groups.get(GROUP)
    sig = _signature(scene)
    if ng is not None and not rebuild and ng.get("fr_sig") == sig:
        restyle(scene, ng)
        return ng
    if ng is None:
        ng = bpy.data.node_groups.new(GROUP, "ShaderNodeTree")
    _build(ng, scene)
    ng["fr_sig"] = sig
    return ng


def restyle(scene, ng=None) -> None:
    """On/off, flip, shape, colour and hatch of every cut into the group's value nodes (no rebuild)."""
    ng = ng or bpy.data.node_groups.get(GROUP)
    if ng is None:
        return
    nodes = ng.nodes

    def put(name, v):
        n = nodes.get(name)
        if n is None:
            return
        if n.bl_idname == "ShaderNodeRGB":
            v = (*v, 1.0)
            if tuple(round(x, 6) for x in n.outputs[0].default_value) != tuple(round(x, 6) for x in v):
                n.outputs[0].default_value = v
        elif abs(n.outputs[0].default_value - v) > 1e-9:
            n.outputs[0].default_value = v

    for c in scene.fresing.cuts:
        put(f"{c.key} on", 1.0 if c.enabled else 0.0)
        put(f"{c.key} flip", -1.0 if c.flip else 1.0)
        put(f"{c.key} box", 1.0 if c.shape_kind == "BOX" else 0.0)
        put(f"{c.key} hatch", 1.0 if c.hatch else 0.0)
        put(f"{c.key} spacing", max(1e-4, c.hatch_spacing))
        put(f"{c.key} colour", tuple(c.color))


def _caps_for(mat) -> float:
    """Glass shows no caps (its back faces are seen through its front anyway)."""
    from ..core import materials_lib
    mid = mat.get("fr_material", "")
    spec = materials_lib.get(mid) if mid else {}
    return 0.0 if spec.get("transmission") else 1.0


def _is_group(node, ng_name: str) -> bool:
    return node.bl_idname == "ShaderNodeGroup" and node.node_tree is not None and node.node_tree.name == ng_name


def wrap(mat, ng=None) -> bool:
    """Put the section group between the shader and every output of ``mat`` (inside a Fade group). Returns True when
    it changed."""
    if mat is None or mat.node_tree is None:
        return False
    from . import fade
    ng = ng or bpy.data.node_groups.get(GROUP) or node_group(bpy.context.scene)
    nt = mat.node_tree
    changed = False
    for out in [n for n in nt.nodes if n.bl_idname == "ShaderNodeOutputMaterial"]:
        sock = out.inputs.get("Surface")
        if sock is None or not sock.is_linked:
            continue
        src = sock.links[0].from_node
        if _is_group(src, GROUP):
            continue
        if _is_group(src, fade.GROUP):                 # cut first, then fade: a faded part's cap fades too
            sock = src.inputs[0]
            if not sock.is_linked or _is_group(sock.links[0].from_node, GROUP):
                continue
        node = nt.nodes.new("ShaderNodeGroup")
        node.node_tree = ng
        node.name = node.label = NODE if not nt.nodes.get(NODE) else f"{NODE} {out.name}"
        node.location = (out.location.x, out.location.y - 400)
        node.inputs["Caps"].default_value = _caps_for(mat)
        from_sock = sock.links[0].from_socket
        nt.links.remove(sock.links[0])
        nt.links.new(from_sock, node.inputs[0])
        nt.links.new(node.outputs[0], sock)
        changed = True
    if hasattr(mat, "use_transparent_shadow") and not mat.use_transparent_shadow:
        mat.use_transparent_shadow = True              # EEVEE: light through the hole
    if hasattr(mat, "surface_render_method") and mat.surface_render_method not in ("DITHERED", "BLENDED"):
        mat.surface_render_method = "DITHERED"
    if not mat.get(TAG):
        mat[TAG] = True
    return changed


def is_wrapped(mat) -> bool:
    return bool(mat is not None and mat.node_tree is not None
                and any(_is_group(n, GROUP) for n in mat.node_tree.nodes))


def _materials(ob) -> list:
    out = []
    for slot in getattr(ob, "material_slots", ()):
        if slot.material is not None and slot.material not in out:
            out.append(slot.material)
    return out


def _wrap_object(ob, ng) -> int:
    n = 0
    for mat in _materials(ob):
        if not is_wrapped(mat):
            wrap(mat, ng)
            n += 1
    return n


# ---------------------------------------------------------------------------
# keeping parts, materials and the group in step with the cuts
# ---------------------------------------------------------------------------

def sync(scene) -> int:
    """Members (object attributes), wrapped materials, the group and render settings for every cut. Sets only what
    differs. Returns how many parts are cut."""
    from . import logic
    s = scene.fresing
    tree = logic.Tree(scene)
    want: dict[str, set] = {}                           # object name -> keys of the cuts on it
    for c in s.cuts:
        for p in target_parts(scene, c, tree):
            for o in [p] + _decals_of(p):
                want.setdefault(o.name, set()).add(c.key)
    for ob in scene.objects:
        have = {k[len(ATTR):] for k in ob.keys() if k.startswith(ATTR) and k != NOCAP}
        need = want.get(ob.name, set())
        if have == need:
            continue
        for k in have - need:
            del ob[ATTR + k]
        for k in need - have:
            ob[ATTR + k] = 1.0
        ob.update_tag()
    ng = node_group(scene) if s.cuts or bpy.data.node_groups.get(GROUP) is not None else None
    for name in want:
        ob = scene.objects.get(name)
        if ob is None:
            continue
        if ob.get(build.PROP_KIND) == "decal" and not ob.get(NOCAP):
            ob[NOCAP] = 1.0
        _wrap_object(ob, ng)
    if any(c.enabled for c in s.cuts):
        c = getattr(scene, "cycles", None)
        if c is not None and getattr(c, "transparent_max_bounces", 999) < TRANSPARENT_STEPS:
            from . import render
            render._set(c, "transparent_max_bounces", TRANSPARENT_STEPS)
    return sum(1 for n in want if (o := scene.objects.get(n)) is not None and o.get(build.PROP_KIND) == "part")


def cut_parts(scene, cut) -> list:
    """The objects carrying ``cut``'s attribute now."""
    k = ATTR + cut.key
    return [o for o in scene.objects if k in o and o.get(build.PROP_KIND) == "part"]


# ---------------------------------------------------------------------------
# the cut's objects and its slide joint
# ---------------------------------------------------------------------------

def _model_size(scene) -> float:
    from . import joints
    return joints._model_size(scene)


VIEW: dict = {}                       # {"dir": Vector}: from the model towards the eye of the 3D view (operators)


def _view_dir(scene, centre: Vector) -> Vector:
    """From the model towards whoever looks: the 3D view the button was pressed in, else the scene's camera."""
    if VIEW.get("dir") is not None:
        return Vector(VIEW["dir"])
    cam = scene.camera
    if cam is None:
        return Vector((0.4, -1.0, 0.3))
    return cam.matrix_world.translation - centre


def view_from(context) -> None:
    """Remember the direction of the 3D view of ``context`` (or forget it when there is none)."""
    VIEW.clear()
    space = getattr(context, "space_data", None)
    r3d = getattr(space, "region_3d", None) if space is not None and space.type == "VIEW_3D" else None
    if r3d is not None and r3d.view_perspective != "CAMERA":
        VIEW["dir"] = r3d.view_rotation @ Vector((0.0, 0.0, 1.0))


def _shape_basis(cut) -> Matrix:
    """The shape object's matrix under the joint's motion empty (its size)."""
    if cut.shape_kind == "BOX":
        sx, sy, sz = (max(1e-4, v / 2.0) for v in cut.size)
    else:
        r = max(1e-3, cut.plane_size / 2.0)
        sx, sy, sz = r, r, PLANE_THICK
    return Matrix.Diagonal((sx, sy, sz, 1.0))


def _style_shape(cut) -> None:
    ob = cut.shape
    if ob is None:
        return
    m = _shape_basis(cut)
    if any(abs(a - b) > 1e-9 for ra, rb in zip(ob.matrix_basis, m) for a, b in zip(ra, rb)):
        ob.matrix_basis = m
    ob.empty_display_type = "CUBE"
    ob.empty_display_size = 1.0
    ob.hide_render = True


def _make_shape(scene, cut, collection) -> bpy.types.Object:
    ob = bpy.data.objects.new(f"{cut.name} shape", None)
    collection.objects.link(ob)
    ob[KEY] = cut.key
    ob.hide_select = True                        # the handle (the joint's arrow) is what you move
    ob.show_in_front = True
    ob.lock_location = ob.lock_rotation = ob.lock_scale = (True,) * 3
    cut.shape = ob
    _style_shape(cut)
    return ob


def _follow(shape, motion) -> None:
    """The shape follows the joint's motion empty: world = motion @ its own size (Child Of, no parent: the
    structure tree of 2 Structure does not see it)."""
    con = shape.constraints.get("FR cut")
    if con is None:
        for c in list(shape.constraints):
            shape.constraints.remove(c)
        con = shape.constraints.new("CHILD_OF")
        con.name = "FR cut"
    con.target = motion
    con.set_inverse_pending = False
    con.inverse_matrix = Matrix.Identity(4)


def make_joint(scene, cut, frame_world: Matrix, root, value: float = 0.0, limits=None) -> object:
    """The cut's slide joint, its frame (the handle) at ``frame_world``, sitting on ``root``."""
    from . import joints
    size = _model_size(scene)
    j = joints.create(scene, "SLIDE", [], None, None, name=cut.name, base=root, stack=False, allow_empty=True,
                      frame_world=frame_world)
    for ob in (j.frame, j.motion):
        ob[KEY] = cut.key
    j.motion[APP_TAG] = "cut"
    fr = j.frame
    fr.lock_location = fr.lock_rotation = (False,) * 3     # the handle: move and turn it in the view
    fr.empty_display_type = "SINGLE_ARROW"
    fr.empty_display_size = max(0.05, size * 0.12)
    fr.show_in_front = True
    j.use_limits = True
    lo, hi = limits if limits is not None else (-size, size)
    j.slide_min, j.slide_max = lo, hi
    joints.apply_limits(j, size)
    j.motion.id_properties_ui(joints.VALUE).update(
        description="How far the cut has slid along its arrow, in mm (0 = where you put it). A Move joint step with "
                    "this joint slides it in a video")
    cut.joint = j.name
    if cut.shape is not None:
        _follow(cut.shape, j.motion)
    if abs(value) > 1e-12:
        joints.set_value(j, value)
    return j


def default_place(scene, cut):
    """(handle's world matrix, box size, plane size) for ``cut`` through the middle of what it cuts, taking away the
    side that faces the camera."""
    from . import logic
    bpy.context.view_layer.update()              # a camera or a part moved just now: its world place
    root = cut_root(scene, cut)
    parts = target_parts(scene, cut, logic.Tree(scene))
    lo, hi = bounds(parts) or (Vector((-0.5,) * 3), Vector((0.5,) * 3))
    view = _view_dir(scene, (lo + hi) / 2)
    rot = root.matrix_world.to_3x3().normalized() if root is not None else Matrix.Identity(3)
    size = tuple(cut.size)
    if cut.shape_kind == "BOX":
        centre, size = core.box_default(lo, hi, view)
        frame = Matrix.Translation(Vector(centre)) @ rot.to_4x4()
    else:
        centre, normal = core.plane_default(lo, hi, view)
        frame = Matrix.Translation(Vector(centre)) @ Vector(normal).to_track_quat("Z", "Y").to_matrix().to_4x4()
    return frame, size, max(0.05, 1.3 * (hi - lo).length)


def add(scene, targets: list, shape_kind: str = "PLANE", name: str = "") -> object:
    """A new cut through ``targets`` ([(kind, object or None, group name)]). Placed through the middle of them,
    taking away the side that faces the camera. Returns the cut."""
    s = scene.fresing
    if s.floor_offset < FLOOR_GAP:
        s.floor_offset = FLOOR_GAP
    cut = s.cuts.add()
    cut["key"] = _new_key(scene)
    cut["name"] = name or _unique_name(scene)
    cut["shape_kind"] = 1 if shape_kind == "BOX" else 0
    cut["color"] = core.DEFAULT_COLOR
    cut["hatch_spacing"] = core.HATCH_SPACING
    for kind, ob, gname in targets:
        add_target(cut, kind, ob, gname)
    s.cuts_index = len(s.cuts) - 1
    root = cut_root(scene, cut)
    frame, size, plane = default_place(scene, cut)
    cut["size"] = size
    cut["plane_size"] = plane
    collection = (root.users_collection[0] if root is not None and root.users_collection
                  else scene.collection)
    _make_shape(scene, cut, collection)
    make_joint(scene, cut, frame, root)
    cut.root_uid = root.get(build.PROP_UID, "") if root is not None else ""
    sync(scene)
    node_group(scene, rebuild=True)
    return cut


def place_default(scene, cut) -> None:
    """Put ``cut`` back through the middle of what it cuts (its slide at 0)."""
    from . import joints
    ensure(scene, cut)
    frame, size, plane = default_place(scene, cut)
    j = joint_of(scene, cut)
    if cut.shape_kind == "BOX":
        cut["size"] = size
    cut["plane_size"] = plane
    joints.set_value(j, 0.0, use_limits=False)
    set_world(scene, cut, frame)
    _style_shape(cut)


def set_world(scene, cut, world: Matrix) -> None:
    """Put the cut's handle at ``world`` (a rigid matrix; local Z = the arrow)."""
    fr = handle(scene, cut)
    if fr is None:
        return
    parent = fr.parent.matrix_world if fr.parent is not None else Matrix.Identity(4)
    fr.matrix_parent_inverse = Matrix.Identity(4)
    fr.matrix_basis = parent.inverted() @ world


def remove(scene, cut) -> None:
    """Remove ``cut``: its joint, its shape; the parts look as before."""
    from . import joints
    s = scene.fresing
    key = cut.key
    j = joint_of(scene, cut)
    if j is not None:
        joints.remove(scene, j)
    cut = find(scene, key)
    if cut.shape is not None:
        bpy.data.objects.remove(cut.shape, do_unlink=True)
    idx = next(i for i, c in enumerate(s.cuts) if c.key == key)
    s.cuts.remove(idx)
    s.cuts_index = min(s.cuts_index, len(s.cuts) - 1)
    sync(scene)
    node_group(scene, rebuild=True)


def ensure(scene, cut) -> None:
    """A cut whose joint was removed in 4 Motion (or whose shape was deleted) gets them back where it was."""
    if cut.shape is None or cut.shape.name not in bpy.data.objects:
        root = cut_root(scene, cut)
        coll = root.users_collection[0] if root is not None and root.users_collection else scene.collection
        _make_shape(scene, cut, coll)
        node_group(scene, rebuild=True)
    if joint_of(scene, cut) is None:
        root = cut_root(scene, cut)
        world = cut.shape.matrix_world.normalized() if cut.shape is not None else Matrix.Identity(4)
        loc, rot, _sc = world.decompose()
        make_joint(scene, cut, Matrix.Translation(loc) @ rot.to_matrix().to_4x4(), root)


def handle(scene, cut):
    j = joint_of(scene, cut)
    return j.frame if j is not None else None


def get_place(cut, scene=None):
    """(location, rotation) of the handle in the model's coordinates (m, Euler XYZ radians)."""
    scene = scene or bpy.context.scene
    fr = handle(scene, cut)
    if fr is None:
        return (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)
    return tuple(fr.location), tuple(fr.rotation_euler)


def set_place(scene, cut, location=None, rotation=None) -> None:
    fr = handle(scene, cut)
    if fr is None:
        return
    if location is not None:
        fr.location = location
    if rotation is not None:
        fr.rotation_mode = "XYZ"
        fr.rotation_euler = rotation


def slide_value(scene, cut) -> float:
    from . import joints
    j = joint_of(scene, cut)
    return joints.get_value(j) if j is not None else 0.0


def changed(scene, cut) -> None:
    """A cut's setting changed (from its properties)."""
    _style_shape(cut)
    restyle(scene)
    if cut.enabled:
        sync(scene)


def targets_changed(scene) -> None:
    sync(scene)


# ---------------------------------------------------------------------------
# saved scenes (states.save_shot / apply_shot)
# ---------------------------------------------------------------------------

def capture(scene) -> str:
    """Which cuts are on, as text for a saved scene ('' with no cuts)."""
    import json
    cs = scene.fresing.cuts
    return json.dumps({c.key: bool(c.enabled) for c in cs}) if len(cs) else ""


def apply_saved(scene, text: str) -> None:
    """Switch the cuts on and off as a saved scene had them (a scene saved before cuts: unchanged)."""
    import json
    if not text:
        return
    try:
        data = json.loads(text)
    except ValueError:
        return
    for c in scene.fresing.cuts:
        if c.key in data and bool(c.enabled) != bool(data[c.key]):
            c.enabled = bool(data[c.key])


# ---------------------------------------------------------------------------
# model update (reimport.py)
# ---------------------------------------------------------------------------

def before_model_update(scene, root) -> None:
    """The cuts on the model under ``root`` take their joints off (kept on the cut: place, value, limits); the
    joints of the model come apart after this."""
    from . import joints
    for cut in scene.fresing.cuts:
        j = joint_of(scene, cut)
        if j is None or j.frame is None:
            continue
        seat = j.frame.parent
        if root is not None and seat is not None and _root_of(seat) is not root and seat is not root:
            continue
        local = (root.matrix_world.inverted() @ j.frame.matrix_world) if root is not None else j.frame.matrix_world
        cut["parked"] = [x for row in local for x in row]
        cut["parked_value"] = joints.get_value(j)
        cut["parked_limits"] = (j.slide_min, j.slide_max)
        cut["parked_name"] = j.name
        joints.remove(scene, j)


def after_model_update(scene, by_uid, mapping: dict) -> list[str]:
    """Rebuild the parked cuts on the new model (part targets by part ID). Returns notes for the report."""
    notes = []
    for cut in scene.fresing.cuts:
        if "parked" not in cut:
            continue
        for t in cut.targets:
            if t.kind == "GROUP":
                continue
            new = by_uid.get(t.uid) if t.uid else None
            if new is not None:
                t.obj = new
                t.uid = new.get(build.PROP_UID, t.uid)
            elif t.uid and str(mapping.get(t.uid, "")).startswith("gone:"):
                t.obj = None
                notes.append(f"Cut '{cut.name}': '{t.name}' is not in the new model, so it is not cut any more")
        root = by_uid.get(cut.root_uid) if cut.root_uid else None
        root = root or cut_root(scene, cut)
        vals = list(cut["parked"])
        local = Matrix([vals[0:4], vals[4:8], vals[8:12], vals[12:16]])
        world = (root.matrix_world @ local) if root is not None else local
        cut.joint = str(cut.get("parked_name", cut.name))
        name = cut.name
        cut["name"] = cut.joint                    # the joint keeps its name (steps and poses use it)
        try:
            make_joint(scene, cut, world, root, float(cut.get("parked_value", 0.0)),
                       tuple(cut.get("parked_limits", (-1.0, 1.0))))
        finally:
            cut["name"] = name
        cut.root_uid = root.get(build.PROP_UID, "") if root is not None else ""
        for k in ("parked", "parked_value", "parked_limits", "parked_name"):
            if k in cut:
                del cut[k]
    if len(scene.fresing.cuts):
        sync(scene)
        node_group(scene, rebuild=True)
    return notes


# ---------------------------------------------------------------------------
# materials made later (looks, machining, painted faces): wrapped as they come
# ---------------------------------------------------------------------------

_PENDING: set = set()


def _cut_objects(scene) -> list:
    return [o for o in scene.objects if any(k.startswith(ATTR) and k != NOCAP for k in o.keys())]


def _wrap_pending() -> None:
    scene = bpy.context.scene
    names = list(_PENDING)
    _PENDING.clear()
    if scene is None or not len(scene.fresing.cuts):
        return None
    ng = bpy.data.node_groups.get(GROUP)
    if ng is None:
        return None
    for n in names:
        ob = bpy.data.objects.get(n)
        if ob is not None:
            _wrap_object(ob, ng)
    return None


@bpy.app.handlers.persistent
def _on_depsgraph(scene, depsgraph):
    """An object that is cut got a new material (a look change, painted faces, the milled block's cut faces): wrap
    it in a moment (not inside the update)."""
    if not len(scene.fresing.cuts):
        return
    found = False
    for u in depsgraph.updates:
        idb = u.id
        if not isinstance(idb, bpy.types.Object):
            continue
        ob = idb.original
        if ob.type != "MESH" or not any(k.startswith(ATTR) and k != NOCAP for k in ob.keys()):
            continue
        if any(not is_wrapped(m) for m in _materials(ob)):
            _PENDING.add(ob.name)
            found = True
    if found and not bpy.app.timers.is_registered(_wrap_pending):
        bpy.app.timers.register(_wrap_pending, first_interval=0.0)


@bpy.app.handlers.persistent
def _on_render_init(scene, *_args):
    """Before a picture or video (also in the render queue's background Blender): members and materials in step."""
    try:
        if len(scene.fresing.cuts):
            sync(scene)
    except Exception:                          # never stop a render
        pass


def register() -> None:
    if _on_depsgraph not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_on_depsgraph)
    if _on_render_init not in bpy.app.handlers.render_init:
        bpy.app.handlers.render_init.append(_on_render_init)


def unregister() -> None:
    for lst, fn in ((bpy.app.handlers.depsgraph_update_post, _on_depsgraph),
                    (bpy.app.handlers.render_init, _on_render_init)):
        if fn in lst:
            lst.remove(fn)
