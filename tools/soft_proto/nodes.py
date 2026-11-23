"""Study 0300: the Geometry Nodes deformers of soft and springy parts (prototype; Blender 5.2.3).

Every deformer works on the part's OWN mesh (the CAD part keeps its looks, selection and copies) and reads the parts
it sits between with Object Info – no driver, no Python while playing or rendering, so it works with scripts off and
in the render queue. All numbers are in the part's own (object) coordinates, metres.

* ``FR soft axial`` – coil springs and bellows: the part between two seats gets longer or shorter along its axis; the
  end pieces (closed end turns, a bellows' cuffs) keep their size, the part between them is stretched evenly. With
  "Helix" on (springs) each point moves with the wire's centre line, so the wire stays round; off (bellows) the
  folds themselves get flatter or deeper. A sideways offset of the seats shears the part. The new place of every
  point is LINEAR in the seats' places (glTF morph targets can carry it exactly).
* ``FR soft squeeze`` – rubber buffers, bump stops, mounts: squeezed along the axis by the other part once it
  touches, the volume kept by a bulge that is largest half-way and nothing at the faces held by the two parts.
* ``FR soft ground`` – a tyre on the ground: the part below the ground is pushed up flat (the contact patch) and the
  walls near it bulge out sideways by how far the tyre is pressed in; it works whatever the wheel's turn.
"""

from __future__ import annotations

import math

import bpy


class G:
    """A tiny builder: ``g.math("ADD", a, b)`` etc. take sockets or numbers and return the output socket."""

    def __init__(self, name: str):
        old = bpy.data.node_groups.get(name)
        if old is not None:
            bpy.data.node_groups.remove(old)
        self.t = bpy.data.node_groups.new(name, "GeometryNodeTree")
        self.t.is_modifier = True
        self.inp = self.t.nodes.new("NodeGroupInput")
        self.out = self.t.nodes.new("NodeGroupOutput")

    def socket(self, name, kind, default=None, out=False):
        s = self.t.interface.new_socket(name, in_out="OUTPUT" if out else "INPUT", socket_type="NodeSocket" + kind)
        if default is not None:
            s.default_value = default
        return None if out else self.inp.outputs[name]

    def node(self, kind, **props):
        n = self.t.nodes.new(kind)
        for k, v in props.items():
            setattr(n, k, v)
        return n

    def link(self, a, b):
        if a is None:
            return
        if isinstance(a, (int, float)):
            b.default_value = a
        elif isinstance(a, tuple):
            b.default_value = a
        else:
            self.t.links.new(a, b)

    def math(self, op, a, b=None, c=None):
        n = self.node("ShaderNodeMath", operation=op)
        for i, x in enumerate((a, b, c)):
            if x is not None:
                self.link(x, n.inputs[i])
        return n.outputs[0]

    def vec(self, op, a, b=None, scale=None):
        n = self.node("ShaderNodeVectorMath", operation=op)
        self.link(a, n.inputs[0])
        if b is not None:
            self.link(b, n.inputs[1])
        if scale is not None:
            self.link(scale, n.inputs["Scale"])
        return n.outputs["Value" if op in ("DOT_PRODUCT", "LENGTH", "DISTANCE") else "Vector"]

    def mapc(self, v, a, b, c, d):
        """clamped linear map v: a..b -> c..d"""
        n = self.node("ShaderNodeMapRange", clamp=True)
        for i, x in enumerate((v, a, b, c, d)):
            self.link(x, n.inputs[i])
        return n.outputs["Result"]

    def clamp(self, v, lo, hi):
        n = self.node("ShaderNodeClamp")
        self.link(v, n.inputs["Value"])
        self.link(lo, n.inputs["Min"])
        self.link(hi, n.inputs["Max"])
        return n.outputs[0]

    def xyz(self, v):
        n = self.node("ShaderNodeSeparateXYZ")
        self.link(v, n.inputs[0])
        return n.outputs

    def point_in_self(self, obj_socket, local_point):
        """A point given in another object's coordinates, in this object's coordinates (evaluated places)."""
        info = self.node("GeometryNodeObjectInfo")
        self.link(obj_socket, info.inputs["Object"])
        tp = self.node("FunctionNodeTransformPoint")
        self.link(local_point, tp.inputs["Vector"])
        self.link(info.outputs["Transform"], tp.inputs["Transform"])
        return self.to_self(tp.outputs[0])

    def _self_inv(self):
        if not hasattr(self, "_inv"):
            so = self.node("GeometryNodeSelfObject")
            info = self.node("GeometryNodeObjectInfo")
            self.link(so.outputs[0], info.inputs["Object"])
            inv = self.node("FunctionNodeInvertMatrix")
            self.link(info.outputs["Transform"], inv.inputs[0])
            self._inv = inv.outputs[0]
        return self._inv

    def to_self(self, world_point):
        tp = self.node("FunctionNodeTransformPoint")
        self.link(world_point, tp.inputs["Vector"])
        self.link(self._self_inv(), tp.inputs["Transform"])
        return tp.outputs[0]

    def dir_to_self(self, world_dir):
        td = self.node("FunctionNodeTransformDirection")
        self.link(world_dir, td.inputs[0])
        self.link(self._self_inv(), td.inputs[1])
        return td.outputs[0]

    def finish(self, geo, positions, normals="keep"):
        sp = self.node("GeometryNodeSetPosition")
        self.link(geo, sp.inputs["Geometry"])
        self.link(positions, sp.inputs["Position"])
        g = sp.outputs[0]
        if normals == "angle":
            # the import's point normals belong to the shape before: take them off and smooth by angle (30 deg)
            ea = self.node("GeometryNodeInputMeshEdgeAngle")
            sharp = self.math("GREATER_THAN", ea.outputs["Unsigned Angle"], math.radians(30))
            sn = self.node("GeometryNodeSetMeshNormal", mode="SHARPNESS")
            self.link(g, sn.inputs["Mesh"])
            sn.inputs["Remove Custom"].default_value = True
            self.link(sharp, sn.inputs["Edge Sharpness"])
            g = sn.outputs[0]
        self.link(g, self.out.inputs[0])
        return self.t


def axial(name="FR soft axial"):
    g = G(name)
    geo = g.socket("Geometry", "Geometry")
    g.socket("Geometry", "Geometry", out=True)
    seat_a = g.socket("Seat A", "Object")
    pa_l = g.socket("Seat A point", "Vector")          # the bottom seat's centre, in seat A's coordinates
    seat_b = g.socket("Seat B", "Object")
    pb_l = g.socket("Seat B point", "Vector")          # the top seat's centre, in seat B's coordinates
    org = g.socket("Origin", "Vector")                 # the bottom seat's centre at rest, in the part's coordinates
    u = g.socket("Axis", "Vector", (0.0, 0.0, 1.0))
    ref = g.socket("Ref", "Vector", (1.0, 0.0, 0.0))   # angle 0 round the axis
    side = g.socket("Side", "Vector", (0.0, 1.0, 0.0))  # angle 90 deg (the spring's hand: cross(axis, ref) or minus it)
    L0 = g.socket("Free length", "Float", 0.08)
    z1 = g.socket("Active from", "Float", 0.006)       # centre-line heights where the part that stretches starts/ends
    z2 = g.socket("Active to", "Float", 0.074)
    phi1 = g.socket("Phase", "Float", 0.0)             # the wire's angle at "Active from"
    pitch = g.socket("Pitch", "Float", 0.0085)
    wire = g.socket("Wire", "Float", 0.004)
    helix = g.socket("Helix", "Float", 1.0)            # 1 = spring (wire kept round), 0 = bellows (folds squeeze)
    solid = g.socket("Shortest", "Float", 0.0)         # the solid length: never shorter
    pos = g.node("GeometryNodeInputPosition").outputs[0]

    pa = g.point_in_self(seat_a, pa_l)
    pb = g.point_in_self(seat_b, pb_l)
    d = g.vec("SUBTRACT", pb, pa)
    L = g.math("MAXIMUM", g.vec("DOT_PRODUCT", d, u), solid)
    lat = g.vec("SUBTRACT", d, g.vec("SCALE", u, scale=g.vec("DOT_PRODUCT", d, u)))
    q = g.vec("SUBTRACT", pos, org)
    h = g.vec("DOT_PRODUCT", q, u)
    rv = g.vec("SUBTRACT", q, g.vec("SCALE", u, scale=h))
    th = g.math("ARCTAN2", g.vec("DOT_PRODUCT", rv, side), g.vec("DOT_PRODUCT", rv, ref))
    two_pi = 2 * math.pi
    span = g.math("SUBTRACT", z2, z1)
    phi2 = g.math("ADD", phi1, g.math("MULTIPLY", g.math("DIVIDE", span, pitch), two_pi))
    k_dead = g.math("DIVIDE", two_pi, wire)            # angle per metre in the closed end turns
    # the angle along the wire a point at height h would have (piecewise: dead | active | dead)
    below = g.math("MINIMUM", g.math("SUBTRACT", h, z1), 0.0)
    above = g.math("MAXIMUM", g.math("SUBTRACT", h, z2), 0.0)
    phi_est = g.math("ADD", g.math("ADD", phi1, g.mapc(h, z1, z2, 0.0, g.math("SUBTRACT", phi2, phi1))),
                     g.math("MULTIPLY", g.math("ADD", below, above), k_dead))
    # the turn it is on: the one whose angle matches the point's own angle round the axis
    kk = g.math("ROUND", g.math("DIVIDE", g.math("SUBTRACT", phi_est, th), two_pi))

    def zc_of(dk):
        phi = g.math("ADD", th, g.math("MULTIPLY", g.math("ADD", kk, dk), two_pi))
        b2 = g.math("MINIMUM", g.math("SUBTRACT", phi, phi1), 0.0)
        a2 = g.math("MAXIMUM", g.math("SUBTRACT", phi, phi2), 0.0)
        return g.math("ADD", g.math("ADD", z1, g.mapc(phi, phi1, phi2, 0.0, span)),
                      g.math("DIVIDE", g.math("ADD", b2, a2), k_dead))

    # of the turn it seems to be on and its two neighbours, the one whose centre line is nearest in height
    # (one guess alone put the top of the last closed end turn on the first free turn: up to 1.9 mm off)
    zc = zc_of(0.0)
    for dk in (-1.0, 1.0):
        other = zc_of(dk)
        nearer = g.math("LESS_THAN", g.math("ABSOLUTE", g.math("SUBTRACT", h, other)),
                        g.math("ABSOLUTE", g.math("SUBTRACT", h, zc)))
        zc = g.math("ADD", zc, g.math("MULTIPLY", nearer, g.math("SUBTRACT", other, zc)))
    zc = g.math("ADD", h, g.math("MULTIPLY", helix, g.math("SUBTRACT", zc, h)))    # helix off: the point itself
    dz = g.math("SUBTRACT", h, zc)
    grow = g.math("SUBTRACT", L, L0)
    m = g.math("ADD", zc, g.math("MULTIPLY", grow, g.mapc(zc, z1, z2, 0.0, 1.0)))
    h2 = g.math("ADD", m, dz)
    frac = g.mapc(h, 0.0, L0, 0.0, 1.0)
    p2 = g.vec("ADD", g.vec("ADD", pa, g.vec("SCALE", u, scale=h2)), rv)
    p2 = g.vec("ADD", p2, g.vec("SCALE", lat, scale=frac))
    return g.finish(geo, p2)


def squeeze(name="FR soft squeeze", subdivide=3, normals="angle"):
    g = G(name)
    geo = g.socket("Geometry", "Geometry")
    g.socket("Geometry", "Geometry", out=True)
    seat_b = g.socket("Presser", "Object")
    pb_l = g.socket("Presser point", "Vector")         # the point of the other part that presses, in its coordinates
    org = g.socket("Origin", "Vector")                 # the face that stands (its centre), the part's coordinates
    u = g.socket("Axis", "Vector", (0.0, 0.0, 1.0))
    H0 = g.socket("Free height", "Float", 0.025)
    bulge = g.socket("Bulge", "Float", 1.0)            # share of the volume kept by bulging (1 = all of it)
    pos = g.node("GeometryNodeInputPosition").outputs[0]
    pb = g.point_in_self(seat_b, pb_l)
    H = g.math("MINIMUM", g.vec("DOT_PRODUCT", g.vec("SUBTRACT", pb, org), u), H0)
    H = g.math("MAXIMUM", H, g.math("MULTIPLY", H0, 0.2))      # rubber never below a fifth of its height
    s = g.math("DIVIDE", H, H0)
    # bulge b(z) = 4 z (1 - z); volume kept: 8/15 k^2 + 4/3 k + (1 - 1/s) = 0
    c = g.math("SUBTRACT", 1.0, g.math("DIVIDE", 1.0, s))
    disc = g.math("SUBTRACT", 16.0 / 9.0, g.math("MULTIPLY", c, 32.0 / 15.0))
    k = g.math("DIVIDE", g.math("SUBTRACT", g.math("SQRT", disc), 4.0 / 3.0), 16.0 / 15.0)
    q = g.vec("SUBTRACT", pos, org)
    h = g.vec("DOT_PRODUCT", q, u)
    rv = g.vec("SUBTRACT", q, g.vec("SCALE", u, scale=h))
    z = g.math("DIVIDE", h, H0)
    b = g.math("MULTIPLY", g.math("MULTIPLY", z, g.math("SUBTRACT", 1.0, z)), 4.0)
    grow = g.math("ADD", 1.0, g.math("MULTIPLY", g.math("MULTIPLY", k, b), bulge))
    p2 = g.vec("ADD", g.vec("ADD", org, g.vec("SCALE", u, scale=g.math("MULTIPLY", h, s))),
               g.vec("SCALE", rv, scale=grow))
    if subdivide:
        sd = g.node("GeometryNodeSubdivideMesh")
        g.link(geo, sd.inputs["Mesh"])
        sd.inputs["Level"].default_value = subdivide
        geo = sd.outputs[0]
    return g.finish(geo, p2, normals=normals)


def ground(name="FR soft ground"):
    g = G(name)
    geo = g.socket("Geometry", "Geometry")
    g.socket("Geometry", "Geometry", out=True)
    gro = g.socket("Ground", "Object")                  # its z = 0 plane, normal +z, is the ground
    cen = g.socket("Centre", "Vector")
    ax = g.socket("Axle", "Vector", (0.0, 0.0, 1.0))
    R = g.socket("Radius", "Float", 0.3)
    band = g.socket("Wall band", "Float", 0.08)
    bulge = g.socket("Bulge", "Float", 0.6)
    pos = g.node("GeometryNodeInputPosition").outputs[0]
    info = g.node("GeometryNodeObjectInfo")
    g.link(gro, info.inputs["Object"])
    tp = g.node("FunctionNodeTransformPoint")
    g.link(info.outputs["Transform"], tp.inputs["Transform"])
    gp = g.to_self(tp.outputs[0])
    td = g.node("FunctionNodeTransformDirection")
    td.inputs[0].default_value = (0.0, 0.0, 1.0)
    g.link(info.outputs["Transform"], td.inputs[1])
    n = g.vec("NORMALIZE", g.dir_to_self(td.outputs[0]))
    hv = g.vec("DOT_PRODUCT", g.vec("SUBTRACT", pos, gp), n)
    low = g.math("SUBTRACT", g.vec("DOT_PRODUCT", g.vec("SUBTRACT", cen, gp), n), R)
    D = g.math("MAXIMUM", g.math("MULTIPLY", low, -1.0), 0.0)
    push = g.math("MAXIMUM", g.math("MULTIPLY", hv, -1.0), 0.0)
    p1 = g.vec("ADD", pos, g.vec("SCALE", n, scale=push))
    h1 = g.math("MAXIMUM", hv, 0.0)
    w = g.math("POWER", g.mapc(h1, 0.0, band, 1.0, 0.0), 2.0)
    a = g.vec("DOT_PRODUCT", g.vec("SUBTRACT", pos, cen), ax)
    sgn = g.math("SIGN", a)
    side = g.vec("SCALE", ax, scale=g.math("MULTIPLY", g.math("MULTIPLY", sgn, D), g.math("MULTIPLY", bulge, w)))
    return g.finish(geo, g.vec("ADD", p1, side), normals="angle")


def add(ob, group, **inputs):
    mod = ob.modifiers.new(group.name, "NODES")
    mod.node_group = group
    for item in group.interface.items_tree:
        if item.item_type != "SOCKET" or item.in_out != "INPUT" or item.socket_type == "NodeSocketGeometry":
            continue
        if item.name in inputs:
            mod[item.identifier] = inputs[item.name]
    return mod
