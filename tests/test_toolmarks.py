"""Tool marks on cut faces (task 0061): the formula (core/toolmarks.py) and the node group that draws it.

The Blender tests use a **test bed**: a flat plane whose faces carry the four attributes of one move, written by
hand – what ``blender/machining.py`` writes on a milled mesh. Renders are tiny (Cycles on the processor)."""

import math
import os

import numpy as np
import pytest

from fresing_render.core import machining as core_machining
from fresing_render.core import materials_lib
from fresing_render.core import toolmarks as T

MM = 0.001
R = 25 * MM                # a 50 mm face mill
SPACING = 0.4 * MM         # its feed per turn
X, Y, Z = np.eye(3)
O = np.array([0.4, 0.3, 0.05])          # coordinates far from the origin, as on a real workpiece


# ---- the formula (no Blender) -----------------------------------------------------------------------------------

def test_arcs_have_the_tools_radius_and_centres_on_the_path():
    for c in (0.01, 0.01 + SPACING, 0.01 + 7 * SPACING):
        centre = O + c * X
        phi = np.linspace(-1.4, 1.4, 15)
        arc = centre + R * (np.cos(phi)[:, None] * X + np.sin(phi)[:, None] * Y)      # the tool's leading edge
        u, ridge, groove = T.pattern(T.ARCS, arc, O, X, Z, R, SPACING)
        assert np.allclose(u, c, atol=1e-9)                     # one mark: the same number all along the arc
        assert np.allclose(ridge, ridge[0], atol=1e-6)
        along_arc = -np.sin(phi)[:, None] * X + np.cos(phi)[:, None] * Y
        assert np.allclose(np.abs((groove * along_arc).sum(1)), 1.0, atol=1e-9)   # the grooves run along the arc
        assert np.allclose(np.linalg.norm(groove, axis=1), 1.0)
    # the centre moves on by one spacing: the next mark
    u0 = T.pattern(T.ARCS, O + 0.02 * X + 0.004 * Y, O, X, Z, R, SPACING)[0]
    u1 = T.pattern(T.ARCS, O + (0.02 + SPACING) * X + 0.004 * Y, O, X, Z, R, SPACING)[0]
    assert abs((u1 - u0) - SPACING) < 1e-12


def test_one_ridge_per_spacing_times_size():
    xs = np.linspace(0.0, 0.012, 12000, endpoint=False)        # whole marks at every size below
    P = O + (R + xs)[:, None] * X                              # along the middle of the swath: u = xs
    for size in (1.0, 3.0, 10.0):
        u, ridge, _g = T.pattern(T.ARCS, P, O, X, Z, R, SPACING, size=size)
        assert np.allclose(u, xs, atol=1e-12)
        cusps = np.sum((ridge[1:-1] > ridge[:-2]) & (ridge[1:-1] >= ridge[2:]) & (ridge[1:-1] > 0.9))
        assert abs(cusps - 0.012 / (SPACING * size)) <= 1.0, (size, cusps)
        assert ridge.min() >= 0.0 and ridge.max() <= 1.0
        assert abs(ridge.mean() - T.RIDGE_MEAN) < 0.01
    ridge, tilt = T.profile(np.array([0.0, 0.5, 0.999999]) * SPACING, SPACING)
    assert np.allclose(ridge, [1.0, 0.0, 1.0], atol=1e-4)      # cusp, the middle, the next cusp
    assert np.allclose(tilt, [1.0, 0.0, -1.0], atol=1e-4)
    # the normal leans downhill: away from the cusp behind, towards the cusp ahead (a scallop)
    u = np.linspace(0.05, 0.95, 50) * SPACING
    ridge, tilt = T.profile(u, SPACING)
    assert np.all(np.sign(np.gradient(ridge, u)) == -np.sign(tilt))
    assert T.period(0.0, 2.0) == T.SPACING_MIN * 2.0           # never a zero width


def test_outside_the_swath_and_single_points():
    u, ridge, groove = T.pattern(T.ARCS, O + 0.01 * X + 2 * R * Y, O, X, Z, R, SPACING)     # one point
    assert np.shape(u) == () and np.shape(groove) == (3,)
    assert abs(u - 0.01) < 1e-12 and np.isfinite(ridge) and np.all(np.isfinite(groove))    # the square root is 0
    many = T.pattern(T.ARCS, np.zeros((4, 5, 3)) + O, O, X, Z, R, SPACING)
    assert many[0].shape == (4, 5) and many[1].shape == (4, 5) and many[2].shape == (4, 5, 3)
    u, ridge, groove = T.pattern(T.NONE, O + 0.01 * X, O, X, Z, R, SPACING)
    assert u == 0.0 and not groove.any()


def test_flank_lines_run_along_the_tool():
    P = O + 0.0123 * X + R * Y + np.linspace(-0.01, 0.0, 6)[:, None] * Z       # up a wall
    u, _ridge, groove = T.pattern(T.FLANK, P, O, X, Z, R, 0.05 * MM, n=Y)
    assert np.allclose(u, 0.0123)                                               # one line: the same number
    assert np.allclose(np.abs(groove @ Z), 1.0)
    assert np.allclose(T.across(T.FLANK, P, O, X, Z, R, n=Y), X)
    u2 = T.pattern(T.FLANK, P + 0.05 * MM * X, O, X, Z, R, 0.05 * MM, n=Y)[0]
    assert np.allclose(u2 - u, 0.05 * MM)                                       # one per tooth along the feed


def test_chamfer_lines_run_along_the_path():
    n = (Y + Z) / math.sqrt(2)
    P = O + np.linspace(0.0, 0.03, 7)[:, None] * X + 0.002 * (Y - Z)
    u, _ridge, groove = T.pattern(T.ALONG, P, O, X, Z, R, T.SPACING_ALONG, n=n)
    assert np.allclose(u, -0.002)
    assert np.allclose(np.abs(groove @ X), 1.0)


def test_rings_round_the_axis():
    phi = np.linspace(0.0, 6.0, 13)
    ring = O + 0.003 * (np.cos(phi)[:, None] * X + np.sin(phi)[:, None] * Y)
    u, ridge, groove = T.pattern(T.RINGS, ring, O, (0, 0, 0), Z, 0.004, T.SPACING_RINGS)
    assert np.allclose(u, 0.003) and np.allclose(ridge, ridge[0], atol=1e-6)
    round_it = -np.sin(phi)[:, None] * X + np.cos(phi)[:, None] * Y
    assert np.allclose(np.abs((groove * round_it).sum(1)), 1.0)
    # the wall of the hole: one ring per turn, counted along the axis
    wall = ring - 0.006 * Z
    radial = (ring - O) / 0.003
    u, ridge, groove = T.pattern(T.RINGS_WALL, wall, O, (0, 0, 0), Z, 0.003, 0.1 * MM, n=-radial)
    assert np.allclose(u, -0.006)
    assert np.allclose(np.abs((groove * round_it).sum(1)), 1.0)
    # the very centre of a floor: no direction is known, and nothing breaks
    s = T.shade(T.RINGS, O, O, (0, 0, 0), Z, 0.004, T.SPACING_RINGS)
    assert np.allclose(s["normal"], Z) and s["anisotropic"] == 0.0


def test_ball_passes_have_arcs_across_the_pass():
    n = np.array([0.0, math.sin(0.5), math.cos(0.5)])                           # the flank of a scallop
    P = O + 0.01 * X + 0.001 * Y
    u, _ridge, groove = T.pattern(T.ACROSS, P, O, X, Z, 0.003, 0.05 * MM, n=n)
    assert abs(u - 0.01) < 1e-12
    assert np.allclose(np.abs(groove @ np.cross(n, X)), 1.0)                    # n x d
    assert abs(groove @ n) < 1e-9
    # a face that looks along the feed: n x d is nothing, the grooves run along the tool
    groove = T.pattern(T.ACROSS, P, O, X, Z, 0.003, 0.05 * MM, n=X)[2]
    assert np.allclose(np.abs(groove @ Z), 1.0)
    groove = T.pattern(T.ACROSS, P, O, X, Z, 0.003, 0.05 * MM)[2]               # no normal given: a floor
    assert np.allclose(np.abs(groove @ Y), 1.0)


def test_across_and_groove_are_square_and_lie_in_the_face():
    rng = np.random.default_rng(3)
    P = O + rng.uniform(-0.02, 0.02, (50, 3))
    for kind, n in ((T.ARCS, Z), (T.FLANK, Y), (T.ALONG, (Y + Z) / math.sqrt(2)), (T.RINGS, Z), (T.RINGS_WALL, Y),
                    (T.ACROSS, (0.0, 0.6, 0.8))):
        d = (0, 0, 0) if kind in (T.RINGS, T.RINGS_WALL) else X
        e = T.across(kind, P, O, d, Z, R, n=n)
        g = T.pattern(kind, P, O, d, Z, R, SPACING, n=n)[2]
        assert np.allclose(np.linalg.norm(e, axis=1), 1.0) and np.allclose(np.linalg.norm(g, axis=1), 1.0), kind
        assert np.allclose((e * g).sum(1), 0.0, atol=1e-9) and np.allclose(e @ np.asarray(n), 0.0, atol=1e-9), kind
        # u really grows that way
        step = 1e-6
        du = T.pattern(kind, P + step * e, O, d, Z, R, SPACING, n=n)[0] - T.pattern(kind, P, O, d, Z, R, SPACING,
                                                                                     n=n)[0]
        inside = np.abs((P - O) @ Y) < 0.9 * R if kind == T.ARCS else np.ones(len(P), bool)
        assert np.all(du[inside] > 0), kind


def test_shade_leans_the_normal_and_keeps_the_mean_roughness():
    xs = np.linspace(0.0, 20 * SPACING, 20000, endpoint=False)
    P = O + (R + xs)[:, None] * X + 0.003 * Y
    lk = T.look("aluminium_machined")
    s = T.shade(T.ARCS, P, O, X, Z, R, SPACING, looks=lk, roughness=0.2)
    assert np.allclose(np.linalg.norm(s["normal"], axis=1), 1.0)
    lean = np.arccos(np.clip(s["normal"] @ Z, -1, 1))
    assert 0.8 * lk["ridge"] < lean.max() < 1.5 * lk["ridge"]            # the hatch adds a little
    assert abs(s["roughness"].mean() - 0.2) < 0.002
    assert s["roughness"].max() - s["roughness"].min() > 0.5 * lk["rough"]
    assert np.allclose(s["anisotropic"], lk["anisotropic"])
    flat = T.shade(T.ARCS, P, O, X, Z, R, SPACING, looks=lk, strength=0.0)
    assert np.allclose(flat["normal"], Z) and np.allclose(flat["roughness"], 0.2) and not flat["anisotropic"].any()
    far = T.shade(T.ARCS, P, O, X, Z, R, SPACING, looks=lk, fade_by=0.0)      # ridges gone, the sheen stays
    assert np.allclose(far["normal"], Z) and np.allclose(far["anisotropic"], lk["anisotropic"])
    assert T.shade(T.ARCS, P, O, X, Z, R, SPACING, looks=lk, strength=2.0)["anisotropic"].max() <= 1.0


def test_ridges_fade_below_two_pixels():
    assert T.fade(0.4 * MM, 1.0, 2.0) == 0.0                   # 0.4 px per mark
    assert T.fade(0.4 * MM, 10.0, 0.5) == 1.0                  # 16 px
    assert 0.4 < T.fade(0.4 * MM, 1.0, 0.4) < 0.6              # 2 px
    f = T.fade(0.4 * MM, 1.0, np.linspace(0.05, 3.0, 100))
    assert np.all(np.diff(f) <= 1e-12)                         # further away: never more
    assert T.fade(0.4 * MM, 1.0, 0.0) == 0.0
    assert abs(T.pixel_angle(1920) - 0.000375) < 1e-9 and T.pixel_angle(3840, 50) < T.PIXEL_ANGLE < T.pixel_angle(960)
    assert T.fade(0.4 * MM, 1.0, 0.4, angle=T.pixel_angle(3840)) > T.fade(0.4 * MM, 1.0, 0.4)   # 4K shows more


def test_look_for_every_cut_material():
    ids = set()
    for block in materials_lib.MATERIALS:
        cut = core_machining.cut_look(block)
        ids.add(cut[0] if cut else block)
    assert {"aluminium_machined", "steel_machined", "stainless_brushed", "brass", "pom_white"} <= ids
    for mid in sorted(ids) + ["cast_iron", "no such material"]:
        lk = T.look(mid)
        assert set(lk) == set(T.LOOK_KEYS), mid
        assert 0.01 <= lk["ridge"] <= 0.15 and 0.0 < lk["rough"] <= 0.06, mid
        assert 0.0 <= lk["anisotropic"] <= 0.8 and 0.0 <= lk["hatch"] <= 0.5, mid
    alu, steel, iron = T.look("aluminium_machined"), T.look("steel_machined"), T.look("cast_iron")
    assert alu["ridge"] > steel["ridge"] > iron["ridge"]                     # crisp, finer, dull
    assert alu["anisotropic"] > steel["anisotropic"] > iron["anisotropic"] > 0
    for mid in ("pom_white", "pom_black", "plastic_gloss", "plastic_matte"):
        assert T.look(mid)["anisotropic"] == 0.0 and T.look(mid)["ridge"] < 0.5 * alu["ridge"], mid
    assert T.look("steel_machined", T.look("cast_iron")) == iron             # cast iron is tweaked steel
    assert T.look("steel_machined", dict(ridge=0.02, other=1))["ridge"] == 0.02
    assert "other" not in T.look("steel_machined", dict(other=1))
    T.look("aluminium_machined")["ridge"] = 9.0                              # a copy: the table stays
    assert T.look("aluminium_machined")["ridge"] == alu["ridge"]


# ---- Blender: the test bed ---------------------------------------------------------------------------------------

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from mathutils import Euler, Matrix, Vector  # noqa: E402

from fresing_render.blender import materials, toolmarks  # noqa: E402

PLACE = Matrix.Translation((0.3, -0.2, 0.1)) @ Euler((0.2, -0.1, 0.5)).to_matrix().to_4x4()   # moved and turned
ALU = "aluminium_machined"


def fresh():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.use_denoising = False
    sc.cycles.pixel_filter_type = "BOX"             # a pixel = the plain mean over its square
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "OPEN_EXR"
    sc.view_settings.view_transform = "Standard"
    sc.world = bpy.data.worlds.new("bed")
    sc.world.use_nodes = True
    world_plain(0.0)
    return sc


def world_plain(grey: float) -> None:
    nt = bpy.context.scene.world.node_tree
    nt.nodes.clear()
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs[0].default_value = (grey, grey, grey, 1.0)
    nt.links.new(bg.outputs[0], nt.nodes.new("ShaderNodeOutputWorld").inputs[0])


def world_ramp(axis) -> None:
    """A sky that gets brighter towards ``axis`` (world): 0.5 + 2 x the direction's part along it, 0 … 1. A mirror
    that leans by t towards the axis then shows 0.5 + 4 t – brightness as a ruler for the normal."""
    nt = bpy.context.scene.world.node_tree
    nt.nodes.clear()
    co = nt.nodes.new("ShaderNodeTexCoord")
    dot = nt.nodes.new("ShaderNodeVectorMath")
    dot.operation = "DOT_PRODUCT"
    nt.links.new(co.outputs["Generated"], dot.inputs[0])
    dot.inputs[1].default_value = tuple(axis)
    ma = nt.nodes.new("ShaderNodeMath")
    ma.operation, ma.use_clamp = "MULTIPLY_ADD", True
    nt.links.new(dot.outputs["Value"], ma.inputs[0])
    ma.inputs[1].default_value, ma.inputs[2].default_value = 2.0, 0.5
    bg = nt.nodes.new("ShaderNodeBackground")
    nt.links.new(ma.outputs[0], bg.inputs[0])
    nt.links.new(bg.outputs[0], nt.nodes.new("ShaderNodeOutputWorld").inputs[0])


class Bed:
    """A flat plane (2 x half wide, normal ``n``) in a mesh whose coordinates lie far from its origin, on an object
    that is moved and turned. Every face carries the attributes of one move: start ``o``, feed ``d``, axis ``a``."""

    def __init__(self, kind=T.ARCS, n=Z, d=X, a=Z, o=None, half=0.02, cells=6, radius=R, spacing=SPACING,
                 swath=None, material=ALU, marks=True, size=10.0, strength=1.0, tweak=None):
        n, d, a = (np.asarray(v, float) for v in (n, d, a))
        self.kind, self.n, self.d, self.a, self.half = kind, n, d, a, half
        self.radius, self.spacing, self.size, self.strength = radius, spacing, size, strength
        ex = d - (d @ n) * n
        if np.linalg.norm(ex) < 1e-6:
            ex = np.cross(a, n) if np.linalg.norm(np.cross(a, n)) > 1e-6 else X
        self.ex = ex / np.linalg.norm(ex)
        self.ey = np.cross(n, self.ex)
        self.o = O - 0.1 * d if o is None else np.asarray(o, float)
        k = np.linspace(-half, half, cells + 1)
        verts = [O + x * self.ex + y * self.ey for y in k for x in k]
        tris = []
        for j in range(cells):
            for i in range(cells):
                p = j * (cells + 1) + i
                tris += [(p, p + 1, p + cells + 2), (p, p + cells + 2, p + cells + 1)]
        me = bpy.data.meshes.new("bed")
        me.from_pydata([tuple(v) for v in verts], [], tris)
        centres = np.array([np.mean([verts[i] for i in t], axis=0) for t in tris])
        kinds = np.full(len(tris), float(kind))
        if swath is not None:                       # only the faces the tool went over know their move
            kinds[np.abs((centres - self.o) @ np.cross(a, d)) > swath] = 0.0
        self.kinds = kinds
        rows = {T.ATTR_O: np.tile(self.o, (len(tris), 1)), T.ATTR_D: np.tile(d, (len(tris), 1)),
                T.ATTR_A: np.tile(a, (len(tris), 1)),
                T.ATTR_P: np.column_stack([kinds, np.full(len(tris), radius), np.full(len(tris), spacing)])}
        for name, values in rows.items():
            me.attributes.new(name, "FLOAT_VECTOR", "FACE").data.foreach_set(
                "vector", np.asarray(values, np.float32).ravel())
        self.mat = bpy.data.materials.new("bed")
        self.mat.use_nodes = True
        tw = dict(tweak or {})
        if marks:
            tw["toolmarks"] = dict(size=size, strength=strength)
        materials.build_nodes(self.mat, material, "", 0.0, tw)
        self.looks = T.look(material)
        me.materials.append(self.mat)
        self.ob = bpy.data.objects.new("bed", me)
        self.ob.matrix_world = PLACE
        bpy.context.scene.collection.objects.link(self.ob)
        self.turn = np.array(PLACE.to_3x3())
        self.centre = np.array(PLACE @ Vector(O))
        self.cam = None

    def world(self, v):
        return self.turn @ np.asarray(v, float)

    def camera(self, width=0.95, distance=0.5):
        """An orthographic camera straight above the plane, its picture's x along ``ex``."""
        if self.cam is None:
            self.cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
            bpy.context.scene.collection.objects.link(self.cam)
            bpy.context.scene.camera = self.cam
        self.cam.data.type = "ORTHO"
        self.cam.data.ortho_scale = 2 * self.half * width
        self.seen = self.half * width
        m = np.eye(4)
        m[:3, 0], m[:3, 1], m[:3, 2] = self.world(self.ex), self.world(self.ey), self.world(self.n)
        m[:3, 3] = self.centre + distance * self.world(self.n)
        self.cam.matrix_world = Matrix(m.tolist())

    def light(self, at, height, energy=0.02):
        """A small lamp ``height`` above the point ``at`` = (x, y) on the plane."""
        li = bpy.data.objects.new("lamp", bpy.data.lights.new("lamp", "POINT"))
        li.data.energy, li.data.shadow_soft_size = energy, 0.0005
        li.location = self.centre + self.world(at[0] * self.ex + at[1] * self.ey + height * self.n)
        bpy.context.scene.collection.objects.link(li)

    def points(self, w, h, sub=1):
        """The mesh-space points the picture's pixels look at: (h, w, sub * sub, 3), row 0 at the bottom."""
        fx = (np.arange(w * sub) + 0.5) / (w * sub) * 2 - 1
        fy = (np.arange(h * sub) + 0.5) / (h * sub) * 2 - 1
        gx, gy = np.meshgrid(fx * self.seen, fy * self.seen * h / w)
        P = O + gx[..., None] * self.ex + gy[..., None] * self.ey
        return P.reshape(h, sub, w, sub, 3).transpose(0, 2, 1, 3, 4).reshape(h, w, sub * sub, 3)

    def probe(self, output):
        """Show one output of the tool-marks node as light (a vector as 0.5 + 0.5 v): a ruler for the nodes."""
        nt = self.mat.node_tree
        g = toolmarks.group_node(self.mat)
        sock = g.outputs[output]
        if sock.type == "VECTOR":
            half = nt.nodes.new("ShaderNodeVectorMath")
            half.operation = "MULTIPLY_ADD"
            nt.links.new(sock, half.inputs[0])
            half.inputs[1].default_value = half.inputs[2].default_value = (0.5, 0.5, 0.5)
            sock = half.outputs[0]
        em = nt.nodes.get("probe") or nt.nodes.new("ShaderNodeEmission")
        em.name = "probe"
        nt.links.new(sock, em.inputs["Color"])
        out = next(n for n in nt.nodes if n.bl_idname == "ShaderNodeOutputMaterial")
        nt.links.new(em.outputs[0], out.inputs["Surface"])


def render(path, w, h, samples):
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y, sc.cycles.samples = w, h, samples
    sc.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(str(path))
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    return px.reshape(h, w, 4)[:, :, :3].astype(float)


def find_period(signal, pixel: float, lo: float, hi: float) -> float:
    """The period (in the unit of ``pixel``) a row of pixels repeats with, between lo and hi: the one whose wave
    and first two overtones together are strongest. (The overtones matter: on a floor the trailing edge's
    cross-hatch can sit just between the marks – tool diameter 50 mm, marks 4 mm – and the pattern's half period
    is then as strong as the period itself.)"""
    s = (signal - signal.mean()) * np.hanning(len(signal))
    x = (np.arange(len(s)) + 0.5) * pixel
    periods = np.exp(np.linspace(math.log(lo), math.log(hi), 4000))
    power = sum(np.abs(np.exp(-2j * math.pi * k * x[None, :] / periods[:, None]) @ s) ** 2 for k in (1, 2, 3))
    return float(periods[int(np.argmax(power))])


def measure_spacing(folder, bed=None):
    """(the period measured in a render along the feed through the middle of the swath, the expected one), m."""
    bed = bed or Bed()
    bed.camera()
    world_ramp(bed.world(bed.ex))
    w, h = 192, 12
    px = render(os.path.join(str(folder), "spacing.exr"), w, h, 16)[:, :, 0]
    row = px[h // 2 - 2:h // 2 + 2].mean(axis=0)                 # 0.8 mm either side of the tool's path
    expect = bed.spacing * bed.size
    return find_period(row, 2 * bed.seen / w, 0.3 * expect, 3.0 * expect), expect, row


@pytest.fixture()
def scene():
    return fresh()


def test_spacing_in_a_render_is_the_feed_per_turn(scene, tmp_path):
    """The task's "Done when": a face mill, 0.4 mm per turn, Mark size x10 -> one ridge every 4 mm, within 5 %."""
    got, expect, row = measure_spacing(tmp_path)
    assert row.max() - row.min() > 0.15, "no ridges in the render"
    assert abs(got - expect) < 0.05 * expect, (got, expect)
    assert abs(expect - 4 * MM) < 1e-12


def test_spacing_follows_mark_size_and_the_feed(scene, tmp_path):
    got, expect, _row = measure_spacing(tmp_path, Bed(spacing=0.25 * MM, size=8.0))       # 2 mm
    assert abs(got - expect) < 0.05 * expect, (got, expect)
    bpy.data.objects.remove(bpy.data.objects["bed"])
    got, expect, _row = measure_spacing(tmp_path, Bed(size=5.0))                          # 2 mm, 0.4 x 5
    assert abs(got - expect) < 0.05 * expect, (got, expect)


CASES = {      # kind: (the face's normal, feed, start of the move)
    "arcs": (T.ARCS, Z, X, None),
    "flank": (T.FLANK, Y, X, O - 0.1 * X - 0.0123 * Z),
    "along": (T.ALONG, (Y + Z) / math.sqrt(2), X, O - 0.1 * X - 0.0123 * Z),
    "rings": (T.RINGS, Z, (0, 0, 0), O + 0.004 * X - 0.002 * Y),
    "rings_wall": (T.RINGS_WALL, Y, (0, 0, 0), O - 0.0123 * Z + 0.004 * Y),
    "across": (T.ACROSS, np.array([0.0, math.sin(0.5), math.cos(0.5)]), X, O - 0.1 * X),
    "across, face along the feed": (T.ACROSS, X, X, O - 0.1 * X),
}


@pytest.mark.parametrize("name", list(CASES))
def test_node_group_agrees_with_the_formula(scene, tmp_path, name):
    """The nodes against the mirror, pixel by pixel: the ridge, and the normal the material is lit with."""
    kind, n, d, o = CASES[name]
    bed = Bed(kind=kind, n=n, d=d, o=o, half=0.012, spacing=0.3 * MM)             # marks 3 mm wide: 14 px
    bed.camera()
    w = 56
    P = bed.points(w, w, sub=6)
    lk = bed.looks
    s = T.shade(kind, P, bed.o, d, Z, R, bed.spacing, n=n, size=bed.size, looks=lk,
                roughness=materials_lib.MATERIALS[ALU]["roughness"])
    assert s["ridge"].std() > 0.2 or name == "across, face along the feed"         # the picture shows marks
    bed.probe("Ridge")
    got = render(tmp_path / "ridge.exr", w, w, 16)[:, :, 0]
    err = np.abs(got - s["ridge"].mean(axis=2))
    assert err.mean() < 0.02 and np.percentile(err, 99) < 0.1, (name, err.mean(), err.max())
    bed.probe("Normal")
    got = render(tmp_path / "normal.exr", w, w, 16) * 2 - 1
    want = s["normal"].mean(axis=2) @ bed.turn.T                                   # the node gives world space
    err = np.abs(got - want)
    assert err.mean() < 0.004 and np.percentile(err, 99) < 0.5 * lk["ridge"], (name, err.mean(), err.max())
    lean = np.abs(s["normal"] - np.asarray(n)).max()
    assert lean > 0.3 * lk["ridge"], name                                          # … and it does lean
    if kind != T.ARCS:
        return
    for output, key in (("Tangent", "tangent"), ("Roughness", "roughness"), ("Anisotropic", "anisotropic")):
        bed.probe(output)
        got = render(tmp_path / "probe.exr", w, w, 16)
        want = s[key].mean(axis=2)
        if key == "tangent":
            got, want = got * 2 - 1, want @ bed.turn.T
        else:
            got = got[:, :, 0]
        assert np.abs(got - want).mean() < 0.004, (output, np.abs(got - want).mean())
    bed.probe("Has marks")
    assert np.allclose(render(tmp_path / "probe.exr", w, w, 4), 1.0, atol=1e-4)
    bed.probe("Fade")
    assert np.allclose(render(tmp_path / "probe.exr", w, w, 4), 1.0, atol=1e-4)     # 3 mm at 0.5 m: 12 px


EEVEE_CHILD = """
import sys
sys.path.insert(0, {root!r})
sys.path.insert(0, {tests!r})
import numpy as np
import test_toolmarks as B
sc = B.fresh()
sc.render.engine = "BLENDER_EEVEE"
sc.eevee.taa_render_samples = 16
sc.render.filter_size = 0.5
bed = B.Bed(half=0.012, spacing=0.3 * B.MM)
bed.camera()
s = B.T.shade(B.T.ARCS, bed.points(56, 56, sub=6), bed.o, B.X, B.Z, B.R, bed.spacing, size=bed.size, looks=bed.looks)
bed.probe("Ridge")
got = B.render({out!r} + "/ridge.exr", 56, 56, 16)[:, :, 0]
print("RIDGE", float(np.abs(got - s["ridge"].mean(axis=2)).mean()))
bed.probe("Normal")
got = B.render({out!r} + "/normal.exr", 56, 56, 16) * 2 - 1
print("NORMAL", float(np.abs(got - s["normal"].mean(axis=2) @ bed.turn.T).mean()))
bed.probe("Has marks")
print("HAS", float(B.render({out!r} + "/has.exr", 56, 56, 4).mean()))
"""


CYCLES_ONLY = ("ShaderNodeBevel", "ShaderNodeScript", "ShaderNodeOutputAOV", "ShaderNodeTexIES",
               "ShaderNodeWireframe", "ShaderNodeTexPointDensity")


def _only_nodes_eevee_knows():
    from fresing_render.blender import toolmarks as TB
    nodes = TB.ensure_group().nodes
    assert len(nodes) > 20
    known = ("ShaderNode", "NodeGroupInput", "NodeGroupOutput", "NodeReroute", "NodeFrame")
    bad = sorted({n.bl_idname for n in nodes if n.bl_idname in CYCLES_ONLY or not n.bl_idname.startswith(known)})
    assert not bad, f"the tool marks group has nodes EEVEE cannot work out: {bad}"
    attrs = [n for n in nodes if n.bl_idname == "ShaderNodeAttribute"]
    assert len(attrs) == 4 and all(n.attribute_type == "GEOMETRY" for n in attrs)
    assert not any(n.bl_idname == "ShaderNodeTexImage" for n in nodes)


def test_node_group_in_eevee(tmp_path):
    """The same nodes in EEVEE (per-face attributes, the part's own space, the camera's distance). EEVEE needs a
    GL context: as the fade and section tests, the render runs in a process of its own (skipped without one)."""
    import subprocess
    import sys
    here = os.path.dirname(os.path.abspath(__file__))
    code = EEVEE_CHILD.format(root=os.path.dirname(here), tests=here, out=str(tmp_path))
    p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=600)
    got = dict(line.split() for line in p.stdout.splitlines() if line.split(" ")[0] in ("RIDGE", "NORMAL", "HAS"))
    if "RIDGE" not in got and (p.returncode < 0 or p.returncode == 134):
        # no GL context here (GitHub's test machines): EEVEE cannot draw, so at least check that the group holds
        # nothing EEVEE cannot work out – no Cycles-only nodes, attributes read from the mesh
        _only_nodes_eevee_knows()
        return
    assert len(got) == 3, (p.returncode, p.stdout[-2000:], p.stderr[-2000:])
    assert float(got["RIDGE"]) < 0.03 and float(got["NORMAL"]) < 0.008 and abs(float(got["HAS"]) - 1.0) < 1e-3, got


def test_ridges_fade_with_distance_in_the_nodes(scene, tmp_path):
    bed = Bed(size=1.0)                                # 0.4 mm marks
    bed.probe("Fade")
    for distance in (0.2, 0.4, 2.0):
        bed.camera(distance=distance)
        got = render(tmp_path / "fade.exr", 16, 16, 4)[:, :, 0]
        assert np.allclose(got, T.fade(SPACING, 1.0, distance), atol=0.01), distance
    assert toolmarks.set_inputs(bed.mat, pixel_angle=T.pixel_angle(960))          # a small picture: bigger pixels
    got = render(tmp_path / "fade.exr", 16, 16, 4)[:, :, 0]
    assert np.allclose(got, T.fade(SPACING, 1.0, 2.0, angle=36 / 50 / 960), atol=0.01)
    bed.camera(distance=0.25)
    got = render(tmp_path / "fade.exr", 16, 16, 4)[:, :, 0]
    assert 0.2 < got.mean() < 0.8 and np.allclose(got, T.fade(SPACING, 1.0, 0.25, angle=36 / 50 / 960), atol=0.01)
    toolmarks.set_inputs(bed.mat, pixel_angle=T.PIXEL_ANGLE)
    bed.ob.matrix_world = PLACE @ Matrix.Scale(3.0, 4)                 # the same mesh three times as big
    bed.centre = np.array(bed.ob.matrix_world @ Vector(O))
    bed.half *= 3
    bed.camera(distance=1.2)
    got = render(tmp_path / "fade.exr", 16, 16, 4)[:, :, 0]
    assert np.allclose(got, T.fade(SPACING, 1.0, 1.2, scale=3.0), atol=0.01)


def streak_angles(folder, d=X):
    """Two small lamps over a face-milled plane, left and right of the tool's path, seen from far above (no
    ridges, only the sheen): the angle of each bright streak against the picture's x (the feed), in degrees."""
    bed = Bed(d=d, half=0.03, size=1.0)
    bed.camera(width=1.0, distance=2.0)
    off = 0.6 * R
    for y in (off, -off):
        bed.light((0.0, y), 0.06)
    w = 96
    px = render(os.path.join(str(folder), "sheen.exr"), w, w, 24)[:, :, 0]
    ys, xs = np.mgrid[0:w, 0:w]
    angles = []
    for half in (px * (ys >= w // 2), px * (ys < w // 2)):          # the top half of the picture is +y: left
        wgt = np.where(half > 0.35 * half.max(), half, 0.0)
        wgt = wgt / wgt.sum()
        cx, cy = (wgt * xs).sum(), (wgt * ys).sum()
        cov = np.array([[(wgt * (xs - cx) ** 2).sum(), (wgt * (xs - cx) * (ys - cy)).sum()],
                        [(wgt * (xs - cx) * (ys - cy)).sum(), (wgt * (ys - cy) ** 2).sum()]])
        val, vec = np.linalg.eigh(cov)
        long_axis = vec[:, 1] * np.sign(vec[0, 1] or 1.0)
        angles.append((math.degrees(math.atan2(long_axis[1], long_axis[0])), math.sqrt(val[1] / val[0])))
    return angles, bed


def test_sheen_follows_the_arcs(scene, tmp_path):
    """The bright streak lies across the grooves. Left of the path (0.6 R) the arcs lean one way, right of it the
    other: across them is 37 degrees to either side of the feed."""
    (left, left_long), (right, right_long) = streak_angles(tmp_path)[0]
    expect = math.degrees(math.atan2(0.6, 0.8))
    assert abs(left - expect) < 12 and abs(right + expect) < 12, (left, right, expect)
    assert left_long > 1.5 and right_long > 1.5, (left_long, right_long)             # a streak, not a round spot


def test_the_look_passes_through_where_no_move_is_known(scene, tmp_path):
    """Kind 0 on every face: the material renders as it does without tool marks."""
    pictures = []
    for marks in (True, False):
        bed = Bed(kind=T.NONE, marks=marks)
        bed.camera()
        world_ramp(bed.world(bed.ex + 0.5 * bed.ey))
        pictures.append(render(tmp_path / "plain.exr", 48, 48, 16)[:, :, 0])
        assert (toolmarks.group_node(bed.mat) is not None) == marks
        bpy.data.objects.remove(bed.ob)
    with_node, without = pictures
    assert abs(with_node.mean() - without.mean()) < 0.02 * without.mean()
    assert np.abs(with_node - without).mean() < 0.02


def test_only_faces_with_a_move_get_marks(scene, tmp_path):
    bed = Bed(cells=8, swath=0.01)                    # the tool went over the middle 20 mm only
    bed.camera(width=1.0)
    bed.probe("Has marks")
    got = render(tmp_path / "has.exr", 32, 32, 4)[:, :, 0]
    assert np.allclose(got[14:18].mean(), 1.0, atol=1e-3) and np.allclose(got[:6].mean(), 0.0, atol=1e-3)
    assert np.allclose(got[-6:].mean(), 0.0, atol=1e-3)
    assert abs(got.mean() - 0.5) < 0.05


def _all_nodes(mat):
    nodes = list(mat.node_tree.nodes)
    for n in list(nodes):
        if n.bl_idname == "ShaderNodeGroup":
            nodes += list(n.node_tree.nodes)
    return nodes


def test_no_scripts_no_drivers_no_pictures_and_the_file_reopens(scene, tmp_path):
    bed = Bed()
    group = toolmarks.ensure_group()
    for block in (bed.mat, bed.mat.node_tree, group, bed.ob, bed.ob.data):
        assert block.animation_data is None
    kinds = {n.bl_idname for n in _all_nodes(bed.mat)}
    assert not kinds & {"ShaderNodeScript", "ShaderNodeTexImage", "ShaderNodeTexEnvironment"}, kinds
    assert not [n for n in group.nodes if n.bl_idname in ("ShaderNodeBump", "ShaderNodeTexImage")]
    names = {n.attribute_name for n in group.nodes if n.bl_idname == "ShaderNodeAttribute"}
    assert names == set(T.ATTRS)
    assert all(n.attribute_type == "GEOMETRY" for n in group.nodes if n.bl_idname == "ShaderNodeAttribute")
    before, expect, row = measure_spacing(tmp_path, bed)
    path = str(tmp_path / "bed.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.open_mainfile(filepath=path, use_scripts=False)
    assert not bpy.app.autoexec_fail
    sc = bpy.context.scene
    sc.cycles.device = "CPU"
    again = render(tmp_path / "again.exr", 192, 12, 16)[:, :, 0]
    row2 = again[4:8].mean(axis=0)
    assert np.abs(row2 - row).mean() < 0.01                          # the same picture
    got = find_period(row2, 2 * 0.02 * 0.95 / 192, 0.3 * expect, 3.0 * expect)
    assert abs(got - expect) < 0.05 * expect
    me = bpy.data.objects["bed"].data
    assert all(me.attributes[name].domain == "FACE" for name in T.ATTRS)


def test_build_nodes_hook_and_inputs(scene):
    plain = bpy.data.materials.new("plain")
    plain.use_nodes = True
    materials.build_nodes(plain, ALU)
    assert toolmarks.group_node(plain) is None and bpy.data.node_groups.get(toolmarks.GROUP) is None
    assert not toolmarks.set_inputs(plain, 2.0, 1.0)
    for block in materials_lib.MATERIALS:
        cut = core_machining.cut_look(block)
        mid, tweak = (cut[0], dict(cut[1])) if cut else (block, {})
        mat = bpy.data.materials.new("cut")
        mat.use_nodes = True
        materials.build_nodes(mat, mid, "RAL 5010", 0.0, {**tweak, "toolmarks": dict(size=3.0, strength=0.5)})
        g = toolmarks.group_node(mat)
        assert g is not None and g.name == toolmarks.NODE and g.node_tree.name == toolmarks.GROUP, block
        lk = T.look(mid)
        assert abs(g.inputs["Size"].default_value - 3.0) < 1e-6 and abs(g.inputs["Strength"].default_value - 0.5) < 1e-6
        for key, name in toolmarks.LOOK_INPUTS.items():
            assert abs(g.inputs[name].default_value - lk[key]) < 1e-6, (block, key)
        bsdf = next(n for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
        for name in ("Roughness", "Normal", "Tangent", "Anisotropic"):
            assert bsdf.inputs[name].is_linked, (block, name)
        assert g.inputs["Normal"].is_linked, block                    # never a zero normal where no move is known
        bpy.data.materials.remove(mat)
    assert len([g for g in bpy.data.node_groups if g.name.startswith(toolmarks.GROUP)]) == 1    # one group for all
    # a look of its own (cast iron is steel with a tweak)
    mat = bpy.data.materials.new("iron")
    mat.use_nodes = True
    materials.build_nodes(mat, "steel_machined", "", 0.0, dict(toolmarks=dict(T.look("cast_iron"), size=2.0)))
    g = toolmarks.group_node(mat)
    assert abs(g.inputs["Sheen"].default_value - T.look("cast_iron")["anisotropic"]) < 1e-6
    assert abs(g.inputs["Strength"].default_value - 1.0) < 1e-6
    # Mark size and Strength without a rebuild; an unchanged value is not written again
    assert toolmarks.set_inputs(mat, 7.0, 1.5)
    assert abs(g.inputs["Size"].default_value - 7.0) < 1e-6 and abs(g.inputs["Strength"].default_value - 1.5) < 1e-6
    assert toolmarks.set_inputs(mat, strength=0.25) and abs(g.inputs["Size"].default_value - 7.0) < 1e-6
    assert abs(g.inputs["Strength"].default_value - 0.25) < 1e-6


def test_an_older_group_is_built_again_in_place(scene):
    bed = Bed()
    group = toolmarks.ensure_group()
    assert group[toolmarks.PROP_VERSION] == toolmarks.GROUP_VERSION
    count = len(group.nodes)
    assert toolmarks.ensure_group() is group and len(group.nodes) == count
    group[toolmarks.PROP_VERSION] = 0
    group.nodes.remove(group.nodes[0])
    assert toolmarks.ensure_group() is group and len(group.nodes) == count
    g = toolmarks.group_node(bed.mat)
    bsdf = next(n for n in bed.mat.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
    assert bsdf.inputs["Normal"].links[0].from_node == g and g.inputs["Normal"].is_linked     # the links are kept
    assert [s.name for s in g.inputs] == [row[0] for row in toolmarks.INPUTS]
    assert [s.name for s in g.outputs] == [row[0] for row in toolmarks.OUTPUTS]


def picture(path, size=(400, 300), samples=64, mark_size=10.0, material=ALU):
    """The test bed as a person would look at it (for the task file): a face-milled strip, the light low behind."""
    sc = fresh()
    bed = Bed(half=0.06, cells=24, swath=R, size=mark_size, material=material)
    sc.world.node_tree.nodes["Background"].inputs[0].default_value = (0.05, 0.055, 0.06, 1.0)
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.lens = 60
    eye = bed.centre + bed.world(-0.17 * X - 0.05 * Y + 0.12 * Z)
    look_at = bed.centre + bed.world(0.005 * X)
    cam.matrix_world = (Matrix.Translation(eye) @
                        Vector(look_at - eye).to_track_quat("-Z", "Y").to_matrix().to_4x4())
    li = bpy.data.objects.new("lamp", bpy.data.lights.new("lamp", "AREA"))
    li.data.energy, li.data.size = 0.1, 0.2
    pos = bed.centre + bed.world(0.30 * X + 0.05 * Y + 0.12 * Z)
    li.matrix_world = (Matrix.Translation(pos) @
                       Vector(bed.centre - pos).to_track_quat("-Z", "Y").to_matrix().to_4x4())
    sc.collection.objects.link(li)
    sc.cycles.pixel_filter_type = "BLACKMAN_HARRIS"
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode, sc.render.image_settings.color_depth = "RGB", "8"
    sc.render.image_settings.compression = 100
    sc.render.resolution_x, sc.render.resolution_y, sc.cycles.samples = size[0], size[1], samples
    sc.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
