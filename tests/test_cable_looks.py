"""Cable looks whose pattern moves along the cable (task 0078): the formula (plain Python in ``cable_looks``)
and the shader nodes that draw it.

The Blender tests use a **straight tube** made by hand: a mesh with the point attribute ``fr_cable`` =
(cos φ, sin φ, s) that the app's cable tube carries, on an object that is moved and turned, with the two custom
properties ``fr_cable_pay`` and ``fr_cable_look``. The material comes the app's own way (``materials.ensure_material``
+ ``materials.assign``). Renders are tiny (200 x 40 px, Cycles on the processor, an orthographic camera square to
the cable); a pixel of the picture is compared with ``cable_looks.pattern`` at the point of the cable it shows."""

import math
import os

import numpy as np
import pytest

from fresing_render.core import materials_lib

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from mathutils import Euler, Matrix  # noqa: E402

from fresing_render.blender import cable_looks as CL  # noqa: E402
from fresing_render.blender import materials  # noqa: E402

PI = math.pi
MM = 0.001


# ---- the formula and the library (nothing rendered) -------------------------------------------------------------

def test_library_entries():
    m = materials_lib.MATERIALS
    assert m["cable_power"]["label"] == "Power cable, black with yellow stripes"
    assert m["cable_power"]["category"] == "Plastic & rubber" and m["cable_power"]["cable"]["kind"] == "POWER"
    assert m["wire_rope"]["label"] == "Steel wire rope"
    assert m["wire_rope"]["category"] == "Metal" and m["wire_rope"]["cable"]["kind"] == "ROPE"
    assert materials_lib.UIDS["pom_black"] == 48                     # the last number before this task
    assert materials_lib.UIDS["cable_power"] == 49 and materials_lib.UIDS["wire_rope"] == 50
    assert CL.MATERIALS == {"POWER": "cable_power", "ROPE": "wire_rope"} and CL.KINDS == {"POWER": 1.0, "ROPE": 2.0}
    assert (CL.PAY, CL.LOOK, CL.ATTR, CL.PAY_BIAS) == ("fr_cable_pay", "fr_cable_look", "fr_cable", 2.0)
    # the sheath is the plain black cable's, the rope's base a grey metal
    black = m["cable_black"]
    for key in ("base_color", "roughness", "sheen", "sheen_roughness"):
        assert m["cable_power"][key] == black[key], key
    assert m["wire_rope"]["metallic"] == 1.0 and 0.35 <= m["wire_rope"]["roughness"] <= 0.45
    for kind in CL.KINDS:
        assert set(materials_lib.MATERIALS[CL.MATERIALS[kind]]["cable"]) - {"kind"} <= set(CL.DEFAULTS[kind]), kind
        assert CL.defaults(kind)["pitch"] > 0


def test_look_values():
    assert CL.look_values("POWER", 0.2, 0.5, math.radians(45), 0.3) == [0.5, 1.0, 0.3, 1.0]     # π·0.2/0.5 = 1.26
    assert CL.look_values("POWER", 0.2, 0.1, math.radians(45), 0.3)[1] == 6.0                   # 6.28
    assert CL.look_values("POWER", 0.2, 0.1, math.radians(60), 0.3)[1] == 4.0                   # 3.63
    assert CL.look_values("POWER", 0.2, 0.5, math.radians(90), 0.3)[1] == 0.0                   # rings
    assert CL.look_values("POWER", 0.2, 0.5, math.radians(-45), 0.3)[1] == -1.0                 # the other hand
    assert CL.look_values("POWER", 0.2, 0.5, math.radians(80), 0.3)[1] == 0.0                   # 0.22: may be 0
    assert CL.look_values("POWER", 0.5, 0.5, 0.0, 0.3)[1] == CL.STARTS_MAX                      # along the cable
    assert CL.look_values("POWER", 0.5, 0.5, 1e-4, 0.3)[1] == CL.STARTS_MAX
    assert CL.look_values("POWER", 0.2, 0.5, 0.7, 1.7)[2] == 1.0 and CL.look_values("POWER", 0.2, 0.5, 0.7, -1)[2] == 0
    assert CL.look_values("POWER", 0.2, 0.0, 0.7, 0.3)[0] == CL.defaults("POWER")["pitch"]      # no pitch: library's
    assert CL.look_values("POWER", 0.2, 0.5)[2] == CL.defaults("POWER")["width"]
    for d, pitch, deg in ((0.05, 0.1, 30), (0.5, 0.8, 45), (0.3, 0.25, 70), (0.12, 0.4, -50)):
        n = CL.look_values("POWER", d, pitch, math.radians(deg), 0.3)[1]
        assert n == math.floor(PI * d / (pitch * math.tan(math.radians(deg))) + 0.5) and n == CL.stripes(
            d, pitch, math.radians(deg))
    assert CL.look_values("ROPE", 0.024, 0.16, math.radians(45), 0.3) == [0.16, 6.0, 0.3, 2.0]
    assert CL.look_values("ROPE", 0.024, 0.16) == [0.16, 6.0, 0.0, 2.0]
    assert CL.look_values("ROPE", 0.024, 0.16, -1.0)[1] == -6.0                                 # left-hand lay
    assert CL.look_values(2.0, 0.024, 0.2)[3] == 2.0 and CL.look_values(1, 0.2, 0.5)[3] == 1.0
    assert all(isinstance(v, float) for v in CL.look_values("POWER", 0.2, 0.5, 0.7, 0.3))
    with pytest.raises(ValueError):
        CL.look_values("CHAIN", 0.1, 0.1)


def test_power_pattern_is_the_contracts_formula():
    rng = np.random.default_rng(3)
    s, phi = rng.uniform(0, 300, 2000), rng.uniform(-PI, PI, 2000)
    for look, paid in (([0.5, 1, 0.3, 1], 0.0), ([0.5, 1, 0.3, 1], 0.123), ([0.07, 3, 0.6, 1], 41.7),
                       ([0.2, 0, 0.5, 1], -12.0), ([0.3, -2, 0.1, 1], 0.47)):
        ph = (s - paid) / look[0] + look[1] * phi / (2 * PI)
        want = ((ph - np.floor(ph)) < look[2]).astype(float)
        assert np.array_equal(CL.pattern("POWER", s, phi, paid, look), want)
        assert np.array_equal(CL.pattern(1.0, s, phi, paid, look), want)
        # a mark moves by exactly the paid-out length
        assert np.allclose(CL.phase("POWER", s + 7.25, phi, paid + 7.25, look), ph, atol=1e-9)
        # it closes round the cable: φ and φ + 2π are the same place
        assert np.allclose(CL.phase("POWER", s, phi + 2 * PI, paid, look) - ph, look[1], atol=1e-9)
    assert CL.pattern("POWER", 0.01, 0.0, 0.0, [0.5, 1, 0.3, 1]) == 1.0                # a float in, a float out
    assert CL.pattern("POWER", 0.2, 0.0, 0.0, [0.5, 1, 0.3, 1]) == 0.0
    assert CL.pattern("POWER", 0.2, 0.0, 0.0, [0.5, 1.4, 0.3, 1]) == 0.0               # starts is rounded: 1
    assert CL.pattern("POWER", 0.2 - 0.25, PI, 0.0, [0.5, 1.4, 0.3, 1]) == 0.0
    # the softened edge the nodes draw: 50 % exactly where the hard edge is, 1 % of a period wide
    look = [0.5, 1, 0.3, 1]
    for edge_at in (0.0, 0.15, 0.5, 0.65):                                             # fract 0 and 0.3
        assert abs(CL.pattern("POWER", edge_at, 0.0, 0.0, look, edge=0.01) - 0.5) < 1e-9
    assert CL.pattern("POWER", 0.15 - 0.0026, 0.0, 0.0, look, edge=0.01) == 1.0
    assert CL.pattern("POWER", 0.15 + 0.0026, 0.0, 0.0, look, edge=0.01) == 0.0
    x = np.linspace(0, 1, 100001)
    assert abs(CL.pattern("POWER", x, 0.3, 0.1, look, edge=0.01).mean() - 0.3) < 1e-4  # as much yellow as before
    assert CL.pattern("POWER", x, 0.3, 0.1, [0.5, 1, 0.0, 1], edge=0.01).max() < 1e-3  # width 0: no yellow at all
    assert CL.pattern("POWER", x, 0.3, 0.1, [0.5, 1, 1.0, 1], edge=0.01).min() > 1 - 1e-3
    # no look (zeros, as an object without the property gives): the library's own
    d = CL.defaults("POWER")
    lib = [d["pitch"], d["starts"], d["width"], 1.0]
    for no in (None, [0.0, 0.0, 0.0, 0.0], [0.0, 3.0, 0.9, 1.0]):
        assert np.array_equal(CL.pattern("POWER", s, phi, 0.3, no), CL.pattern("POWER", s, phi, 0.3, lib))


def test_rope_pattern():
    look = CL.look_values("ROPE", 0.024, 0.16)
    lay = look[0]
    phi = np.linspace(-PI, PI, 3601)[:-1]
    for s, paid in ((0.0, 0.0), (0.731, 0.0), (5.2, 3.9)):
        h = CL.pattern("ROPE", s, phi, paid, look)
        assert 0.0 <= h.min() < 0.12 and 0.999 < h.max() <= 1.0
        crowns = np.sum((h > np.roll(h, 1)) & (h >= np.roll(h, -1)) & (h > 0.9))
        assert crowns == 6                                                # 6 strands round the rope
    # one strand makes one full turn in one lay length: follow a crown
    at = np.linspace(0.0, lay, 81)
    crown = -2 * PI * (at / lay - 0.5 / 6)                                # phase = 6 u + 6 θ = 0.5
    assert np.allclose(CL.pattern("ROPE", at, crown, 0.0, look), 1.0)
    assert abs(crown[-1] - crown[0]) == pytest.approx(2 * PI)
    # … and along the rope there are 6 crowns per lay length
    along = CL.pattern("ROPE", np.linspace(0, lay, 6001)[:-1], 0.4, 0.0, look)
    assert np.sum((along > np.roll(along, 1)) & (along >= np.roll(along, -1)) & (along > 0.9)) == 6
    # moves by the paid-out length; the other hand is the mirror picture
    s = np.linspace(0, 1, 500)
    assert np.allclose(CL.pattern("ROPE", s + 0.47, 1.1, 0.47, look), CL.pattern("ROPE", s, 1.1, 0.0, look))
    left = [lay, -6.0, 0.0, 2.0]
    assert np.allclose(CL.pattern("ROPE", s, -1.1, 0.0, left), CL.pattern("ROPE", s, 1.1, 0.0, look))
    assert np.abs(CL.pattern("ROPE", s, 1.1, 0.0, left) - CL.pattern("ROPE", s, 1.1, 0.0, look)).mean() > 0.1
    assert np.array_equal(CL.pattern(2.0, s, 1.1, 0.0, look), CL.pattern("ROPE", s, 1.1, 0.0, look))
    assert np.array_equal(CL.pattern("ROPE", s, 1.1, 0.0, None),
                          CL.pattern("ROPE", s, 1.1, 0.0, [CL.defaults("ROPE")["pitch"], 6, 0, 2]))
    assert np.isfinite(CL.pattern("ROPE", s, 1.1, 0.0, [0.2, 0.0, 0.0, 2.0])).all()      # no strands: rings


def test_the_wires_of_a_strand_lean_the_other_way():
    """Regular lay: along a strand's crown φ falls as s grows (starts > 0); along a wire it grows, more slowly."""
    look = CL.look_values("ROPE", 0.024, 0.16)
    d = CL.defaults("ROPE")
    lay, slant, count = look[0], d["slant"], d["wires"]
    assert 0.0 < slant < 1.0 and count >= 3
    s = np.linspace(0.0, 0.02, 41)
    phi0 = 0.2
    strand = -2 * PI / lay                                    # dφ/ds along a strand
    wire = +slant * 2 * PI / lay                              # … along a wire: the other sign
    w0 = CL.wires(s[0], phi0, 0.0, look)
    assert np.allclose(CL.wires(s, phi0 + wire * s, 0.0, look), w0, atol=1e-6)            # constant along a wire
    assert np.ptp(CL.wires(s, phi0 + strand * s, 0.0, look)) > 0.5                        # not along the strand
    h0 = CL.pattern("ROPE", s[0], phi0, 0.0, look)
    assert np.allclose(CL.pattern("ROPE", s, phi0 + strand * s, 0.0, look), h0, atol=1e-9)
    # the wires move with the rope too
    assert np.allclose(CL.wires(s + 0.3, phi0, 0.3, look), CL.wires(s, phi0, 0.0, look), atol=1e-6)
    # about ``count`` wires across one strand
    across = CL.wires(0.0, np.linspace(0, 2 * PI / 6, 2001)[1:-1] - 2 * PI * 0.0, 0.0, look)
    assert np.sum((across < np.roll(across, 1)) & (across <= np.roll(across, -1)) & (across < 0.1)) in (
        count - 1, count, count + 1)
    # the other hand: the mirror picture
    left = [lay, -6.0, 0.0, 2.0]
    assert np.allclose(CL.wires(s, -phi0 - wire * s, 0.0, left), w0, atol=1e-6)


# ---- Blender: the test tube -------------------------------------------------------------------------------------

PLACE = Matrix.Translation((0.3, -0.2, 0.1)) @ Euler((0.2, -0.1, 0.5)).to_matrix().to_4x4()   # moved and turned
S0 = 3.2            # the tube's first ring is 3.2 m along its "path": s is not the mesh's x
W, H = 200, 40


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
    sc.world = bpy.data.worlds.new("tube")
    sc.world.use_nodes = True
    nt = sc.world.node_tree
    nt.nodes.clear()
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs[0].default_value = (1.0, 1.0, 1.0, 1.0)             # white light from everywhere
    nt.links.new(bg.outputs[0], nt.nodes.new("ShaderNodeOutputWorld").inputs[0])
    return sc


class Tube:
    """A straight tube along its own +x, ``length`` long, with (or without) the cable attribute:
    φ = 0 at +y, 90° at +z; s = x + S0. ``look``: the 4 numbers (None: no property), ``pay``: metres paid out
    (None: no property)."""

    def __init__(self, material, look=None, pay=0.0, length=0.6, radius=0.06, seg=96, rings=7, attr=True,
                 name="tube", group=None):
        self.length, self.radius = length, radius
        phi = 2 * PI * np.arange(seg) / seg
        xs = np.linspace(0.0, length, rings)
        co = np.empty((rings, seg, 3))
        co[:, :, 0] = xs[:, None]
        co[:, :, 1] = radius * np.cos(phi)[None, :]
        co[:, :, 2] = radius * np.sin(phi)[None, :]
        faces = [(j * seg + i, (j + 1) * seg + i, (j + 1) * seg + (i + 1) % seg, j * seg + (i + 1) % seg)
                 for j in range(rings - 1) for i in range(seg)]
        me = bpy.data.meshes.new(name)
        me.from_pydata(co.reshape(-1, 3).tolist(), [], faces)
        me.polygons.foreach_set("use_smooth", [True] * len(faces))
        if attr:
            a = np.empty((rings, seg, 3), np.float32)
            a[:, :, 0], a[:, :, 1], a[:, :, 2] = np.cos(phi)[None, :], np.sin(phi)[None, :], (xs + S0)[:, None]
            me.attributes.new(CL.ATTR, "FLOAT_VECTOR", "POINT").data.foreach_set("vector", a.ravel())
        self.ob = bpy.data.objects.new(name, me)
        self.ob.matrix_world = PLACE
        bpy.context.scene.collection.objects.link(self.ob)
        if look is not None:
            self.ob[CL.LOOK] = [float(v) for v in look]
        if pay is not None:
            self.ob[CL.PAY] = float(pay) + CL.PAY_BIAS
        self.mat = materials.ensure_material(group or f"Group {material}", material)       # the app's own path
        materials.assign(self.ob, self.mat)
        self.cam = None
        self.view = PI / 2

    def pay(self, metres: float) -> None:
        self.ob[CL.PAY] = float(metres) + CL.PAY_BIAS

    def look(self, values) -> None:
        self.ob[CL.LOOK] = [float(v) for v in values]

    def camera(self, view=PI / 2, width=0.4, centre=None):
        """An orthographic camera square to the tube, looking at the side where φ = ``view``; the picture is
        ``width`` metres wide, its x along the tube. (view = π: the side where atan2 jumps.)"""
        if self.cam is None:
            self.cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
            bpy.context.scene.collection.objects.link(self.cam)
            bpy.context.scene.camera = self.cam
        self.view, self.width = view, width
        self.centre = self.length / 2 if centre is None else centre
        self.cam.data.type = "ORTHO"
        self.cam.data.ortho_scale = width
        c, s = math.cos(view), math.sin(view)
        m = np.eye(4)
        m[:3, 0], m[:3, 1], m[:3, 2] = (1, 0, 0), (0, s, -c), (0, c, s)             # right, up, towards the camera
        m[:3, 3] = (self.centre, 2.0 * c, 2.0 * s)
        self.cam.matrix_world = PLACE @ Matrix(m.tolist())

    def seen(self, sub=6, w=W, h=H):
        """(s, φ) of the cable at the picture's pixels, ``sub`` x ``sub`` points per pixel: two arrays
        (h, w, sub²), row 0 at the bottom."""
        fx = ((np.arange(w * sub) + 0.5) / (w * sub) - 0.5) * self.width
        fy = ((np.arange(h * sub) + 0.5) / (h * sub) - 0.5) * self.width * h / w
        gx, gy = np.meshgrid(fx, fy)
        assert np.abs(fy).max() < self.radius, "the picture must show the tube only"
        depth = np.sqrt(self.radius ** 2 - gy ** 2)
        c, s = math.cos(self.view), math.sin(self.view)
        phi = np.arctan2(-gy * c + depth * s, gy * s + depth * c)
        pack = lambda a: a.reshape(h, sub, w, sub).transpose(0, 2, 1, 3).reshape(h, w, sub * sub)   # noqa: E731
        return pack(gx + self.centre + S0), pack(phi)

    def metres(self, pixel, w=W):
        """s (m) of a place along the picture's x, given in pixel-centre numbers (0 = the first pixel's middle)."""
        return ((np.asarray(pixel, float) + 0.5) / w - 0.5) * self.width + self.centre + S0

    def probe(self, name=CL.NODE_PATTERN):
        """Show one of the look's nodes as light: a ruler for the nodes."""
        nt = self.mat.node_tree
        em = nt.nodes.get("probe") or nt.nodes.new("ShaderNodeEmission")
        em.name = "probe"
        nt.links.new(nt.nodes[name].outputs[0], em.inputs["Color"])
        out = next(n for n in nt.nodes if n.bl_idname == "ShaderNodeOutputMaterial")
        nt.links.new(em.outputs[0], out.inputs["Surface"])


def render(path, samples=8, w=W, h=H):
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = w, h
    if sc.render.engine == "CYCLES":
        sc.cycles.samples = samples
    sc.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(str(path))
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    return px.reshape(h, w, 4)[:, :, :3].astype(float)


def yellow(px):
    """How yellow each pixel is, 0 … 1: red minus blue (the sheath is grey: 0), against the brightest stripe."""
    q = px[:, :, 0] - px[:, :, 2]
    return q / np.percentile(q, 98)


def edges(row):
    """Where a row of ``yellow`` crosses 0.5, in pixel-centre numbers: (rising, falling)."""
    up, down = [], []
    for i in range(len(row) - 1):
        a, b = row[i], row[i + 1]
        if (a - 0.5) * (b - 0.5) < 0:
            (up if b > a else down).append(i + (0.5 - a) / (b - a))
    return np.array(up), np.array(down)


def expected_edges(tube, look, paid):
    """Where the formula puts the edges along the middle row of the picture (φ = the camera's side), m."""
    pitch, starts, width = look[0], round(look[1]), look[2]
    lo, hi = tube.metres(-0.5), tube.metres(W - 0.5)
    k = np.arange(math.floor((lo - paid) / pitch) - 2, math.ceil((hi - paid) / pitch) + 3)
    base = paid + pitch * (k - starts * tube.view / (2 * PI))                 # fract(phase) = 0: yellow begins
    inside = lambda a: a[(a > lo + 2 * tube.width / W) & (a < hi - 2 * tube.width / W)]      # noqa: E731
    return inside(base), inside(base + pitch * width)


def edge_error(tube, px, look, paid):
    """The largest distance (m) between the yellow / black edges along the picture's middle and the formula's
    (every edge the formula puts in the picture, against the nearest edge of the same kind in the render)."""
    row = yellow(px)[H // 2 - 1:H // 2 + 1].mean(axis=0)
    got = [tube.metres(e) for e in edges(row)]
    want = expected_edges(tube, look, paid)
    worst = 0.0
    for g, w in zip(got, want):
        assert len(w) >= 1 and len(w) <= len(g) <= len(w) + 2, (g, w)       # + one at each end of the picture
        worst = max(worst, float(np.abs(g[None, :] - w[:, None]).min(axis=1).max()))
    return worst


@pytest.fixture()
def scene():
    return fresh()


def test_material_is_built_by_the_apps_own_path(scene):
    for kind, mid in CL.MATERIALS.items():
        t = Tube(mid, CL.look_values(kind, 0.12, 0.1))
        mat = t.mat
        assert mat.name == materials.material_name(f"Group {mid}") and materials.is_current(mat, mid)
        assert t.ob.material_slots[0].material is mat
        nodes = CL.nodes_of(mat)
        want = {CL.NODE_ATTR, CL.NODE_PAY, CL.NODE_LOOK, CL.NODE_PATTERN, CL.NODE_HAS}
        assert set(nodes) == want | ({CL.NODE_WIRES} if kind == "ROPE" else set())
        a, p, lk = nodes[CL.NODE_ATTR], nodes[CL.NODE_PAY], nodes[CL.NODE_LOOK]
        assert (a.attribute_type, a.attribute_name) == ("GEOMETRY", "fr_cable")
        assert (p.attribute_type, p.attribute_name) == ("OBJECT", "fr_cable_pay")
        assert (lk.attribute_type, lk.attribute_name) == ("OBJECT", "fr_cable_look")
        _only_nodes_both_engines_know(mat)
        bsdf = next(n for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
        assert bsdf.inputs["Base Color"].is_linked and bsdf.inputs["Roughness"].is_linked
        assert bsdf.inputs["Normal"].is_linked == (kind == "ROPE")                 # a bump for the strands only
        assert bsdf.inputs["Metallic"].is_linked == (kind == "ROPE")
        # no cable look: the hook leaves a material alone
        plain = bpy.data.materials.new("plain")
        plain.use_nodes = True
        materials.build_nodes(plain, "cable_black")
        assert not CL.nodes_of(plain)
        materials.build_nodes(plain, mid, "", 0.6)                                 # … and wear goes on top
        assert set(CL.nodes_of(plain)) >= want


CYCLES_ONLY = ("ShaderNodeBevel", "ShaderNodeScript", "ShaderNodeOutputAOV", "ShaderNodeTexIES",
               "ShaderNodeWireframe", "ShaderNodeTexPointDensity", "ShaderNodeAmbientOcclusion")


def _only_nodes_both_engines_know(mat):
    """Shader nodes only: no picture, no script, nothing only Cycles can work out."""
    nodes = mat.node_tree.nodes
    assert len(nodes) > 20
    bad = sorted({n.bl_idname for n in nodes if n.bl_idname in CYCLES_ONLY or not n.bl_idname.startswith(
        ("ShaderNode", "NodeReroute", "NodeFrame"))})
    assert not bad, f"the cable look has nodes EEVEE cannot work out: {bad}"
    assert not any(n.bl_idname in ("ShaderNodeTexImage", "ShaderNodeTexEnvironment", "ShaderNodeGroup")
                   for n in nodes)
    assert mat.node_tree.animation_data is None                                   # no drivers inside the material
    assert sum(n.bl_idname == "ShaderNodeAttribute" for n in nodes) == 3


def test_stripes_move_by_exactly_the_paid_out_length(scene, tmp_path):
    """The owner's wish: the pattern runs along the cable. The yellow / black edges in a Cycles render of the
    real material are where ``pattern`` says within 1 pixel (2 mm), for three paid-out lengths."""
    look = [0.15, 1.0, 0.4, 1.0]
    t = Tube("cable_power", look)
    t.camera()
    pixel = t.width / W
    rows = {}
    worst = 0.0
    for paid in (0.0, 0.123, 0.47):
        t.pay(paid)
        px = render(tmp_path / "pay.exr")
        assert np.isfinite(px).all()
        err = edge_error(t, px, look, paid)
        worst = max(worst, err)
        assert err < 1.0 * pixel, (paid, err / pixel)
        rows[paid] = yellow(px)
        # … and the whole picture: yellow where the formula says (the tube's sides have other angles φ)
        s, phi = t.seen()
        want = CL.pattern("POWER", s, phi, paid, look, edge=CL.defaults("POWER")["edge"]).mean(axis=2)
        assert np.abs(np.clip(rows[paid], 0, 1) - want).mean() < 0.05, paid
    print(f"\nedge error, three paid-out lengths: {worst / MM:.2f} mm = {worst / pixel:.2f} px")
    assert worst < 0.5 * pixel
    # 0.47 m is 235 pixels: the picture of 0.123 m shifted by 61.5 px is the picture of 0 (same stripes, moved)
    up0, up1 = edges(rows[0.0][H // 2]), edges(rows[0.123][H // 2])
    shift = (t.metres(up1[0][0]) - t.metres(up0[0][0])) % look[0]
    assert abs(shift - 0.123) < 0.5 * pixel, shift
    # the colours: traffic yellow next to a black sheath
    px = render(tmp_path / "pay.exr")
    s, phi = t.seen(sub=2)
    want = CL.pattern("POWER", s, phi, 0.47, look, edge=0.01).mean(axis=2)
    stripe, sheath = px[want == 1.0].mean(axis=0), px[want == 0.0].mean(axis=0)
    assert stripe[0] > 0.6 and stripe[1] > 0.3 and stripe[2] < 0.15 and stripe[0] > stripe[1] > 4 * stripe[2]
    assert sheath.max() < 0.12 and sheath.max() - sheath.min() < 0.02


def test_offset_at_frame_1000_with_a_simple_expression_driver(scene, tmp_path):
    """The cable's pay property is driven from the cable joint's value by ``a * k + 2.0``: no Python runs, and
    after 1,000 frames at 10 m/min the stripes sit within 1 mm of where the formula puts them."""
    look = [0.08, 1.0, 0.35, 1.0]
    t = Tube("cable_power", look, length=0.4)
    t.camera(width=0.2)                                        # 1 mm per pixel
    joint = bpy.data.objects.new("Cable travel", None)         # stands for the joint's motion empty
    bpy.context.scene.collection.objects.link(joint)
    joint["fr_value"] = 0.0
    scene.render.fps = 25                                      # the app's
    speed = 10.0 / 60.0 / 25                                   # 10 m/min, metres per frame
    for frame in (1, 1000):
        joint["fr_value"] = (frame - 1) * speed
        joint.keyframe_insert('["fr_value"]', frame=frame)
    curves = _fcurves(joint)
    assert len(curves) == 1
    for k in curves[0].keyframe_points:
        k.interpolation = "LINEAR"
    fc = t.ob.driver_add(f'["{CL.PAY}"]')
    drv = fc.driver
    drv.type = "SCRIPTED"
    var = drv.variables.new()
    var.name, var.type = "a", "SINGLE_PROP"
    var.targets[0].id, var.targets[0].data_path = joint, '["fr_value"]'
    drv.expression = f"a * 1.0 + {CL.PAY_BIAS}"
    assert drv.is_simple_expression and drv.is_valid
    worst = 0.0
    for frame in (1, 500, 1000):
        scene.frame_set(frame)
        paid = (frame - 1) * speed
        assert abs(curves[0].evaluate(frame) - paid) < 1e-5
        px = render(tmp_path / "frame.exr")
        err = edge_error(t, px, look, paid)
        worst = max(worst, err)
        assert err < 1.0 * MM, (frame, err / MM)
    assert abs((1000 - 1) * speed - 6.66) < 1e-9               # 6.66 m paid out at frame 1,000 (25 fps)
    print(f"\noffset error up to frame 1,000 (6.66 m paid out): {worst / MM:.2f} mm")
    # the other direction: k = -1
    drv.expression = f"a * -1.0 + {CL.PAY_BIAS}"
    assert drv.is_simple_expression
    scene.frame_set(999)
    scene.frame_set(1000)
    assert edge_error(t, render(tmp_path / "frame.exr"), look, -999 * speed) < 1.0 * MM


def _fcurves(ob):
    """The F-curves of an object's action (Blender 5: they live in the action's layers)."""
    act = ob.animation_data.action
    if hasattr(act, "fcurves"):
        return list(act.fcurves)
    out = []
    for layer in act.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                out.extend(bag.fcurves)
    return out


LOOKS = {      # name: (pitch, starts, width)
    "rings": (0.1, 0, 0.5),
    "one start": (0.1, 1, 0.3),
    "three starts, fine": (0.05, 3, 0.3),
    "the other hand": (0.1, -2, 0.6),
    "thin stripes": (0.2, 2, 0.08),
    "starts not whole: rounded, so it closes": (0.1, 1.4, 0.3),
}


@pytest.mark.parametrize("name", list(LOOKS))
def test_stripes_follow_pitch_starts_and_width(scene, tmp_path, name):
    """The nodes against the formula, pixel by pixel, from two sides – one of them the side where the angle
    round the cable jumps from +180° to −180°: no seam there."""
    look = [*LOOKS[name], 1.0]
    t = Tube("cable_power", look, pay=0.2)
    t.probe()
    edge = CL.defaults("POWER")["edge"]
    for view in (PI / 2, PI, -0.7):
        t.camera(view)
        s, phi = t.seen()
        if view == PI:
            assert phi.min() < -3.0 and phi.max() > 3.0                    # the jump is in the picture
        want = CL.pattern("POWER", s, phi, 0.2, look, edge=edge).mean(axis=2)
        got = render(tmp_path / "probe.exr", samples=16)[:, :, 0]
        err = np.abs(got - want)
        assert err.mean() < 0.02, (name, view, err.mean(), err.max())
        assert abs(got.mean() - look[2]) < 0.03, name                      # the yellow share is the width
        clear = (want == 0.0) | (want == 1.0)                              # pixels no edge runs through
        assert clear.mean() > 0.5 and err[clear].max() < 0.06, (name, view, err[clear].max())
        if view == PI:
            # the rows either side of the jump: nothing there but the stripes themselves
            mid = slice(H // 2 - 2, H // 2 + 2)
            assert err[mid].mean() < 0.02 and err[mid][clear[mid]].max() < 0.06, name
    if LOOKS[name][1] == 0:
        assert got.std(axis=0).max() < 0.02                                # rings: the same all round


def test_no_seam_in_the_real_material(scene, tmp_path):
    """The same from the side where atan2 jumps, with the material as the app builds it (Cycles)."""
    pixel = 0.4 / W
    for starts in (0, 1, 3, -2):
        look = [0.12, float(starts), 0.4, 1.0]
        t = Tube("cable_power", look, pay=0.31, name=f"tube {starts}")
        t.camera(PI)
        px = render(tmp_path / "seam.exr")
        assert edge_error(t, px, look, 0.31) < 1.0 * pixel, starts
        s, phi = t.seen()
        hard = CL.pattern("POWER", s, phi, 0.31, look).mean(axis=2)
        q = np.clip(yellow(px), 0, 1)
        clear = (hard == 0.0) | (hard == 1.0)
        mid = slice(H // 2 - 2, H // 2 + 2)
        assert np.abs(q - hard)[mid][clear[mid]].max() < 0.25, starts      # no line along the jump
        assert np.abs(q - hard).mean() < 0.03, starts
        bpy.data.objects.remove(t.ob)


def test_rope_six_strands_where_the_formula_says(scene, tmp_path):
    lay = 0.3
    look = CL.look_values("ROPE", 0.12, lay)
    assert look[1] == 6.0
    t = Tube("wire_rope", look, pay=0.0)
    t.probe()
    round_phi, round_h = [], []
    for paid in (0.0, 0.123):
        t.pay(paid)
        for k in range(5):                                                   # five sides: all the way round
            view = PI / 2 + k * 2 * PI / 5
            t.camera(view)
            s, phi = t.seen()
            want = CL.pattern("ROPE", s, phi, paid, look).mean(axis=2)
            got = render(tmp_path / "rope.exr", samples=16)[:, :, 0]
            err = np.abs(got - want)
            assert err.mean() < 0.01 and np.percentile(err, 99) < 0.1, (paid, view, err.mean(), err.max())
            if paid == 0.0:
                # one column of the picture = a cut across the rope: its height against the angle round it
                rel = np.arctan2(np.sin(phi[:, 0, :] - view), np.cos(phi[:, 0, :] - view)).mean(axis=1)
                keep = np.abs(rel) <= PI / 5
                round_phi.extend((view + rel[keep]) % (2 * PI))
                round_h.extend(got[:, 7][keep])
    h = np.array(round_h)[np.argsort(round_phi)]
    assert np.ptp(np.sort(round_phi)) > 6.0 and np.diff(np.sort(round_phi)).max() < 0.08    # all the way round
    assert int(np.sum((h < 0.5) & (np.roll(h, -1) >= 0.5))) == 6             # 6 strands, 6 valleys between them
    # it moves with the rope: 0.123 m paid out = 61.5 pixels
    t.camera(PI / 2)
    t.pay(0.0)
    a = render(tmp_path / "rope.exr")[:, :, 0]
    t.pay(0.124)                                                                   # 62 whole pixels
    b = render(tmp_path / "rope.exr")[:, :, 0]
    assert np.abs(b[:, 62:] - a[:, :-62]).mean() < 0.01 and np.abs(b - a).mean() > 0.1
    # the other hand is another picture: the mirror one
    t.look([lay, -6.0, 0.0, 2.0])
    c = render(tmp_path / "rope.exr")[:, :, 0]
    assert np.abs(c - b).mean() > 0.1 and np.abs(c[::-1] - b).mean() < 0.01
    # the wires on the strands
    t.look(look)
    t.probe(CL.NODE_WIRES)
    s, phi = t.seen()
    got = render(tmp_path / "rope.exr")[:, :, 0]
    err = np.abs(got - CL.wires(s, phi, 0.124, look).mean(axis=2))
    assert err.mean() < 0.02, err.mean()


def test_rope_in_the_real_material(scene, tmp_path):
    """Cycles, the material as the app builds it: steel crowns brighter than the greasy valleys, moving with
    the paid-out length, the other hand another picture; the strands' relief shows in the light."""
    lay = 0.3
    look = CL.look_values("ROPE", 0.12, lay)
    t = Tube("wire_rope", look, pay=0.05)
    t.camera()
    px = render(tmp_path / "rope.exr", samples=16)
    assert np.isfinite(px).all() and px.min() >= 0.0
    s, phi = t.seen()
    h = CL.pattern("ROPE", s, phi, 0.05, look).mean(axis=2)
    grey = px.mean(axis=2)
    crown, valley = grey[h > 0.9].mean(), grey[h < 0.3].mean()
    print(f"\nrope: crowns {crown:.3f}, valleys {valley:.3f}")
    assert crown > 1.5 * valley and crown > 0.3
    assert np.corrcoef(grey.ravel(), h.ravel())[0, 1] > 0.6
    t.pay(0.05 + 0.124)
    moved = render(tmp_path / "rope.exr", samples=16).mean(axis=2)
    assert np.abs(moved[:, 62:] - grey[:, :-62]).mean() < 0.04 < np.abs(moved - grey).mean()
    t.look([lay, -6.0, 0.0, 2.0])
    other = render(tmp_path / "rope.exr", samples=16).mean(axis=2)
    assert np.abs(other - moved).mean() > 0.04 and np.abs(other[::-1] - moved).mean() < 0.04
    # the relief: light from one end of the rope makes the strands' sides differ; without the bump they do not
    t.look(look)
    li = bpy.data.objects.new("lamp", bpy.data.lights.new("lamp", "SUN"))
    li.data.energy = 6.0
    li.matrix_world = PLACE @ Euler((0.0, math.radians(60), 0.0)).to_matrix().to_4x4()     # from +x, 30° up
    scene.collection.objects.link(li)
    scene.world.node_tree.nodes["Background"].inputs[0].default_value = (0.05, 0.05, 0.05, 1.0)
    f = (CL.phase("ROPE", s, phi, 0.174, look) % 1.0).mean(axis=2)
    lit = render(tmp_path / "rope.exr", samples=16).mean(axis=2)
    one, two = lit[(f > 0.2) & (f < 0.4)].mean(), lit[(f > 0.6) & (f < 0.8)].mean()
    assert max(one, two) > 1.3 * min(one, two), (one, two)
    bump = next(n for n in t.mat.node_tree.nodes if n.bl_idname == "ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.0
    flat = render(tmp_path / "rope.exr", samples=16).mean(axis=2)
    one, two = flat[(f > 0.2) & (f < 0.4)].mean(), flat[(f > 0.6) & (f < 0.8)].mean()
    assert max(one, two) < 1.1 * min(one, two), (one, two)


def test_a_part_without_the_attribute_shows_the_plain_base(scene, tmp_path):
    """The look may be given to a whole group: a part that is no cable (no attribute, no properties) is plain
    black / plain steel – no yellow at all, no NaN, no black frame."""
    def mean(material, tweak=None, **kw):
        t = Tube(material, None, None, attr=False, name=f"plain {material} {bool(tweak)}",
                 group=f"{material} {bool(tweak)}", **kw)
        if tweak:
            materials.build_nodes(t.mat, material, "", 0.0, tweak)
        t.camera()
        px = render(tmp_path / "plain.exr", samples=16)
        bpy.data.objects.remove(t.ob)
        assert np.isfinite(px).all()
        return px

    power, black = mean("cable_power"), mean("cable_black")
    assert (power[:, :, 0] - power[:, :, 2]).max() < 0.02                    # no yellow anywhere
    assert abs(power.mean() - black.mean()) < 0.05 * black.mean() and black.mean() > 0.02
    assert np.abs(power - black).max() < 0.03
    rope, steel = mean("wire_rope"), mean("wire_rope", {"cable": None})      # the same entry without its look
    assert abs(rope.mean() - steel.mean()) < 0.03 * steel.mean() and steel.mean() > 0.2
    assert np.abs(rope - steel).mean() < 0.02 and rope.std(axis=1).max() < 0.03      # no strands

    # a cable (the attribute) whose object has no properties: zeros -> the library's own look, 2 m "taken back"
    for kind, mid in CL.MATERIALS.items():
        t = Tube(mid, None, None, name=f"bare {kind}")
        assert CL.LOOK not in t.ob and CL.PAY not in t.ob
        t.probe()
        t.camera()
        s, phi = t.seen()
        got = render(tmp_path / "bare.exr")[:, :, 0]
        want = CL.pattern(kind, s, phi, -CL.PAY_BIAS, None, **({"edge": 0.01} if kind == "POWER" else {}))
        assert np.isfinite(got).all() and np.abs(got - want.mean(axis=2)).mean() < 0.01, kind
        t.probe(CL.NODE_HAS)
        assert np.allclose(render(tmp_path / "bare.exr", samples=2), 1.0, atol=1e-4)
        # a pitch of 0 with other numbers set, a width beyond 1: still nothing breaks
        t.look([0.0, 5.0, 3.0, 1.0])
        t.probe()
        assert np.abs(render(tmp_path / "bare.exr")[:, :, 0] - want.mean(axis=2)).mean() < 0.01, kind
        bpy.data.objects.remove(t.ob)


def test_look_survives_fade_and_cutaway_wraps(scene):
    """Fades and cutaways wrap the material's output (and wrap again after a rebuild): the look stays wired."""
    import fresing_render
    from fresing_render.blender import fade, section

    def feeds_output(mat, node):
        out = next(n for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeOutputMaterial")
        seen, todo = set(), [out]
        while todo:
            n = todo.pop()
            if n.name in seen:
                continue
            seen.add(n.name)
            todo.extend(link.from_node for sock in n.inputs for link in sock.links)
        return node.name in seen

    fresing_render.register()
    try:
        for mid in CL.MATERIALS.values():
            mat = materials.ensure_material(f"Wrapped {mid}", mid)
            assert section.wrap(mat) and fade.wrap(mat)
            assert section.is_wrapped(mat) and fade.is_wrapped(mat)
            for name in (CL.NODE_ATTR, CL.NODE_PAY, CL.NODE_LOOK):
                assert feeds_output(mat, mat.node_tree.nodes[name]), (mid, name)
            materials.build_nodes(mat, mid, "", 0.3)                       # a look change rebuilds the nodes
            assert section.is_wrapped(mat) and fade.is_wrapped(mat)
            nodes = CL.nodes_of(mat)
            assert all(feeds_output(mat, nodes[name]) for name in (CL.NODE_ATTR, CL.NODE_PAY, CL.NODE_LOOK)), mid
    finally:
        fresing_render.unregister()


EEVEE_CHILD = """
import sys
sys.path.insert(0, {root!r})
sys.path.insert(0, {tests!r})
import numpy as np
import test_cable_looks as B
sc = B.fresh()
sc.render.engine = "BLENDER_EEVEE"
sc.eevee.taa_render_samples = 16
sc.render.filter_size = 0.5
CL = B.CL
look = [0.1, 3.0, 0.3, 1.0]
t = B.Tube("cable_power", look, pay=0.123)
t.camera(B.PI)
px = B.render({out!r} + "/power.exr")
print("EDGE", B.edge_error(t, px, look, 0.123) / (t.width / B.W))
t.probe()
s, phi = t.seen()
got = B.render({out!r} + "/power.exr")[:, :, 0]
print("POWER", float(np.abs(got - CL.pattern("POWER", s, phi, 0.123, look, edge=0.01).mean(axis=2)).mean()))
look = CL.look_values("ROPE", 0.12, 0.3)
r = B.Tube("wire_rope", look, pay=0.123, name="rope")
B.bpy.data.objects.remove(t.ob)
r.camera()
grey = B.render({out!r} + "/rope.exr").mean(axis=2)
s, phi = r.seen()
h = CL.pattern("ROPE", s, phi, 0.123, look).mean(axis=2)
print("CROWN", float(grey[h > 0.9].mean() / grey[h < 0.3].mean()))
r.probe()
got = B.render({out!r} + "/rope.exr")[:, :, 0]
print("ROPE", float(np.abs(got - h).mean()))
B.bpy.data.objects.remove(r.ob)
p = B.Tube("cable_power", None, None, attr=False, name="plain")       # no attribute: the plain black sheath
p.camera()
px = B.render({out!r} + "/plain.exr")
print("PLAIN", float((px[:, :, 0] - px[:, :, 2]).max()))
"""


def test_both_looks_in_eevee(tmp_path):
    """The same nodes in EEVEE (a point attribute, two object properties, a bump). EEVEE needs a GL context: as
    the tool-marks, fade and section tests, the render runs in a process of its own; where it cannot start
    (GitHub's test machines) the nodes are checked instead: nothing in them that EEVEE cannot work out."""
    import subprocess
    import sys
    here = os.path.dirname(os.path.abspath(__file__))
    code = EEVEE_CHILD.format(root=os.path.dirname(here), tests=here, out=str(tmp_path))
    p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=600)
    names = ("EDGE", "POWER", "CROWN", "ROPE", "PLAIN")
    got = dict(line.split() for line in p.stdout.splitlines() if line.split(" ")[0] in names)
    if "EDGE" not in got and (p.returncode < 0 or p.returncode == 134):
        fresh()
        for mid in CL.MATERIALS.values():
            _only_nodes_both_engines_know(materials.ensure_material(f"EEVEE {mid}", mid))
        return
    assert len(got) == 5, (p.returncode, p.stdout[-2000:], p.stderr[-2000:])
    print("\nEEVEE:", got)
    assert float(got["EDGE"]) < 1.0 and float(got["POWER"]) < 0.03, got            # EDGE in pixels
    assert float(got["ROPE"]) < 0.03 and float(got["CROWN"]) > 1.3, got
    assert float(got["PLAIN"]) < 0.02, got
