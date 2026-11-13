"""Wet and snowy looks (task 0109): one node group, "FR weather", in every material of the model and the outdoor
ground, between the look's own shader and whatever follows it (the cutaway's "FR section" group, the "FR fade"
group, or the output) – so a cut or faded part shows its wet or snowy surface.

The group reads two of the scene's weather channels (``core/weather.py``) with Attribute nodes of type **View
Layer** – they read the scene's custom properties ``fr_wx_wet`` and ``fr_wx_cover``, in Cycles and EEVEE, with
scripts off, keyed by a Weather & time step, in the render queue:

    wet     0 … 1: darker (more on porous surfaces: concrete, the deck), a clear water film that reflects
            (Fresnel, IOR 1.33), drops on every face, run-off streaks along gravity on sloped and upright faces,
            puddles on flat faces that face up
    cover   0 … 1: a white, rough snow layer with a slight bump on faces that face up – the more snow, the steeper
            the slope it still lies on – and **only under the open sky**: an Ambient Occlusion node looks straight
            up (not "only local", ``SKY_DISTANCE`` metres): a plate under a roof stays clear. Cycles traces this;
            EEVEE's AO node only sees what is on the screen (horizon scan), so in EEVEE a roof out of the picture
            does not keep the snow off what is under it.

With both channels 0 every mix is 0: the material renders as before (Cycles folds the whole group away, View Layer
attributes are constants to it). With the weather off the group is taken out again (``apply(scene, False)``): the
node tree is exactly what it was.

The patterns (drops, streaks, puddles, snow patches) use the object's own coordinates, so they stay on a part that
moves; the streaks run along the world's "down" turned into the object's coordinates.
"""

from __future__ import annotations

import bpy

GROUP = "FR weather"
NODE = "FR weather"                    # the group node's name in a wrapped material
TAG = "fr_weather_wrap"                # on a wrapped material (materials.build_nodes wraps it again after a rebuild)
GROUP_VERSION = 3
WET, COVER = "fr_wx_wet", "fr_wx_cover"
SKY_DISTANCE = 25.0                    # m: what lies within this far above a point keeps the snow off it
AO_SAMPLES = 8

# surroundings roles whose materials get the look (never the sea, lamps, the photo's dome and ground, hall shells)
ENV_ROLES = ("floor", "structure", "contents", "high")
POROUS = {"concrete": 0.55, "deck": 0.5, "floor_concrete": 0.55, "kerb": 0.55, "rubber": 0.35, "wood": 0.6,
          "asphalt": 0.6}


# ---------------------------------------------------------------------------
# the node group
# ---------------------------------------------------------------------------

class _B:
    def __init__(self, ng):
        self.ng, self.n, self.L = ng, ng.nodes, ng.links
        self.x = -1600

    def node(self, kind, x=None, y=0, **props):
        nd = self.n.new(kind)
        nd.location = (self.x if x is None else x, y)
        for k, v in props.items():
            setattr(nd, k, v)
        return nd

    def put(self, sock, v):
        if isinstance(v, bpy.types.NodeSocket):
            self.L.new(v, sock)
        elif v is not None:
            sock.default_value = v

    def math(self, op, a, b=None, c=None, x=0, y=0, clamp=False):
        m = self.node("ShaderNodeMath", x, y, operation=op, use_clamp=clamp)
        for i, v in enumerate((a, b, c)):
            if v is not None:
                self.put(m.inputs[i], v)
        return m.outputs[0]

    def ramp(self, v, a, b, x=0, y=0, lo=0.0, hi=1.0):
        """Smoothstep of v from a to b (a > b runs downwards), mapped to lo … hi."""
        m = self.node("ShaderNodeMapRange", x, y, interpolation_type="SMOOTHSTEP", clamp=True)
        self.put(m.inputs["Value"], v)
        m.inputs["From Min"].default_value = a
        m.inputs["From Max"].default_value = b
        m.inputs["To Min"].default_value = lo
        m.inputs["To Max"].default_value = hi
        return m.outputs["Result"]

    def ramp_s(self, v, a, b, x=0, y=0):
        """As ramp, with sockets for the ends."""
        m = self.node("ShaderNodeMapRange", x, y, interpolation_type="SMOOTHSTEP", clamp=True)
        self.put(m.inputs["Value"], v)
        self.put(m.inputs["From Min"], a)
        self.put(m.inputs["From Max"], b)
        return m.outputs["Result"]

    def noise(self, vec, scale, detail=2.0, x=0, y=0):
        t = self.node("ShaderNodeTexNoise", x, y, noise_dimensions="3D")
        self.put(t.inputs["Vector"], vec)
        t.inputs["Scale"].default_value = scale
        t.inputs["Detail"].default_value = detail
        return t.outputs["Fac"]

    def vmath(self, op, a, b=None, x=0, y=0, scale=None):
        m = self.node("ShaderNodeVectorMath", x, y, operation=op)
        self.put(m.inputs[0], a)
        if b is not None:
            self.put(m.inputs[1], b)
        if scale is not None:
            self.put(m.inputs["Scale"], scale)
        return m.outputs["Value"] if op in ("DOT_PRODUCT", "LENGTH", "DISTANCE") else m.outputs["Vector"]


SOCKETS = [("INPUT", "Shader", "NodeSocketShader"), ("INPUT", "Porous", "NodeSocketFloat"),
           ("INPUT", "Alpha", "NodeSocketFloat"), ("OUTPUT", "Shader", "NodeSocketShader")]


def _sockets(ng) -> None:
    """The group's sockets; kept when they are right (removing them would cut the links in every material)."""
    have = [(i.in_out, i.name, i.socket_type) for i in ng.interface.items_tree if i.item_type == "SOCKET"]
    if sorted(have) == sorted(SOCKETS):
        return
    for item in list(ng.interface.items_tree):
        ng.interface.remove(item)
    ng.interface.new_socket("Shader", in_out="INPUT", socket_type="NodeSocketShader")
    porous = ng.interface.new_socket("Porous", in_out="INPUT", socket_type="NodeSocketFloat")
    porous.default_value, porous.min_value, porous.max_value = 0.3, 0.0, 1.0
    porous.description = "How much darker the surface gets when wet: 0.1 metal, 0.3 paint, 0.55 concrete"
    alpha = ng.interface.new_socket("Alpha", in_out="INPUT", socket_type="NodeSocketFloat")
    alpha.default_value, alpha.min_value, alpha.max_value = 1.0, 0.0, 1.0
    alpha.description = "Where the look is see-through (a decal's clear parts): no wet film or snow there"
    ng.interface.new_socket("Shader", in_out="OUTPUT", socket_type="NodeSocketShader")


def _build(ng, wet_on: bool = True, snow_on: bool = True) -> None:
    """The group's nodes. Only the parts the project uses are built: Cycles does not fold a View Layer attribute
    of 0 away, and the snow's AO node cost about as much as the rest of the render (measured: 2.06 s -> 3.9 s a
    frame with the snow at 0). Neither: the group passes the shader straight through."""
    ng.nodes.clear()
    _sockets(ng)
    b = _B(ng)
    gin = b.node("NodeGroupInput", -1800, 0)
    gout = b.node("NodeGroupOutput", 1400, 0)
    if not wet_on and not snow_on:
        b.put(gout.inputs[0], gin.outputs[0])
        return

    def channel(name, y):
        a = b.node("ShaderNodeAttribute", -1600, y, attribute_type="VIEW_LAYER", attribute_name=name)
        return b.math("MAXIMUM", a.outputs["Fac"], 0.0, x=-1420, y=y, clamp=True)
    seen = b.math("MINIMUM", b.math("MAXIMUM", gin.outputs["Alpha"], 0.0, x=-1600, y=800), 1.0, x=-1420, y=800)
    wet = b.math("MULTIPLY", channel(WET, 600), seen, x=-1300, y=650)
    cover = channel(COVER, -900)

    geo = b.node("ShaderNodeNewGeometry", -1600, 200)
    tc = b.node("ShaderNodeTexCoord", -1600, 0)
    sep = b.node("ShaderNodeSeparateXYZ", -1420, 200)
    b.put(sep.inputs[0], geo.outputs["Normal"])
    up = sep.outputs["Z"]
    p = tc.outputs["Object"]

    if not wet_on:
        wetted = None
    else:
        wetted = _wet(b, gin, wet, up, p)
    if not snow_on:
        b.put(gout.inputs[0], wetted.outputs[0])
        return
    _snow(b, gin, gout, cover, seen, up, p, wetted.outputs[0] if wetted is not None else gin.outputs[0])


def _wet(b, gin, wet, up, p):
    """Darker, a clear water film, drops, run-off streaks and puddles."""
    flat = b.ramp(up, 0.96, 0.995, -1200, 400)                    # flat faces that face up: puddles
    slope = b.ramp(up, 0.97, 0.8, -1200, 300)                     # sloped and upright faces: streaks
    under = b.ramp(up, -0.2, -0.7, -1200, 200, 1.0, 0.4)          # faces turned down get less
    # world "down" in the part's coordinates: the streaks run along it
    vt = b.node("ShaderNodeVectorTransform", -1420, -100, vector_type="VECTOR", convert_from="WORLD",
                convert_to="OBJECT")
    vt.inputs[0].default_value = (0.0, 0.0, 1.0)
    d = b.vmath("NORMALIZE", vt.outputs[0], x=-1250, y=-100)
    along = b.vmath("DOT_PRODUCT", p, d, x=-1100, y=-100)
    q1 = b.vmath("SCALE", p, x=-1100, y=-200, scale=60.0)
    q2 = b.vmath("SCALE", d, x=-950, y=-150, scale=b.math("MULTIPLY", along, -57.0, x=-950, y=-250))
    q = b.vmath("ADD", q1, q2, x=-800, y=-150)                    # 60 across, 3 along gravity: long thin streaks
    sn = b.noise(q, 1.0, 1.0, x=-650, y=-150)
    streak = b.math("MULTIPLY", b.ramp(sn, 0.6, 0.68, -500, -150), slope, x=-350, y=-150)
    vor = b.node("ShaderNodeTexVoronoi", -800, 50, voronoi_dimensions="3D", feature="F1", distance="EUCLIDEAN")
    b.put(vor.inputs["Vector"], p)
    vor.inputs["Scale"].default_value = 70.0                      # cells ~14 mm: drops a few mm across
    vor.inputs["Randomness"].default_value = 1.0
    in_drop = b.ramp(vor.outputs["Distance"], 0.3, 0.18, -650, 50)
    rnd = b.node("ShaderNodeSeparateColor", -650, 150)
    b.put(rnd.inputs[0], vor.outputs["Color"])
    some = b.math("LESS_THAN", rnd.outputs[0], b.math("MULTIPLY", wet, 0.7, x=-650, y=250), x=-500, y=150)
    drops = b.math("MULTIPLY", b.math("MULTIPLY", in_drop, some, x=-400, y=100), b.math("SUBTRACT", 1.0, flat,
                                                                                          x=-500, y=300), x=-300, y=100)
    pn = b.noise(p, 0.6, 2.0, x=-800, y=450)
    t0 = b.math("MULTIPLY_ADD", wet, -0.14, 0.74, x=-800, y=600)  # wetter: more puddles (~20 % of flat ground)
    t1 = b.math("ADD", t0, 0.03, x=-650, y=600)
    puddle = b.math("MULTIPLY", b.ramp_s(pn, t0, t1, -650, 450), flat, x=-500, y=450)
    detail = b.math("MAXIMUM", b.math("MAXIMUM", drops, streak, x=-200, y=0), puddle, x=-100, y=200)
    film = b.math("MULTIPLY", b.math("MULTIPLY", wet, b.math("MULTIPLY_ADD", detail, 0.65, 0.35, x=0, y=200),
                                     x=100, y=300), under, x=200, y=300, clamp=True)
    dark = b.math("MULTIPLY", b.math("MULTIPLY", wet, gin.outputs["Porous"], x=0, y=500),
                  b.math("MULTIPLY_ADD", detail, 0.5, 0.75, x=0, y=600), x=150, y=500, clamp=True)
    black = b.node("ShaderNodeEmission", 150, 700)
    black.inputs["Color"].default_value = (0.0, 0.0, 0.0, 1.0)
    black.inputs["Strength"].default_value = 0.0
    darker = b.node("ShaderNodeMixShader", 400, 500)
    b.put(darker.inputs[0], dark)
    b.put(darker.inputs[1], gin.outputs[0])
    b.put(darker.inputs[2], black.outputs[0])
    # the water film: a clear coat that reflects by Fresnel; puddles and drops are smoother, drops bulge
    fres = b.node("ShaderNodeFresnel", 150, 150)
    fres.inputs["IOR"].default_value = 1.33
    # (puddles reflect a little more than Fresnel alone: they read as water from any height)
    shine = b.math("ADD", fres.outputs[0], b.math("MULTIPLY_ADD", puddle, 0.12, 0.02, x=150, y=100), x=300, y=150)
    coat = b.math("MULTIPLY", film, shine, x=450, y=200, clamp=True)
    smooth = b.math("MAXIMUM", puddle, drops, x=150, y=0)
    rough = b.math("MULTIPLY_ADD", smooth, -0.16, 0.18, x=300, y=0)
    bump = b.node("ShaderNodeBump", 300, -150)
    bump.inputs["Strength"].default_value = 0.5
    bump.inputs["Distance"].default_value = 0.002
    b.put(bump.inputs["Height"], drops)
    gloss = b.node("ShaderNodeBsdfGlossy", 450, 0, distribution="GGX")
    gloss.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
    b.put(gloss.inputs["Roughness"], rough)
    b.put(gloss.inputs["Normal"], bump.outputs["Normal"])
    wetted = b.node("ShaderNodeMixShader", 650, 300)
    b.put(wetted.inputs[0], coat)
    b.put(wetted.inputs[1], darker.outputs[0])
    b.put(wetted.inputs[2], gloss.outputs[0])
    return wetted


def _snow(b, gin, gout, cover, seen, up, p, shader_in):
    """A white, rough layer on faces that face up, where the sky is open above them."""
    sky = b.node("ShaderNodeAmbientOcclusion", -650, -500, inside=False, only_local=False, samples=AO_SAMPLES)
    sky.inputs["Distance"].default_value = SKY_DISTANCE
    sky.inputs["Normal"].default_value = (0.0, 0.0, 1.0)          # look straight up (unlinked: world space)
    upv = b.node("ShaderNodeCombineXYZ", -800, -600)
    upv.inputs["Z"].default_value = 1.0
    b.put(sky.inputs["Normal"], upv.outputs[0])
    open_sky = b.ramp(sky.outputs["AO"], 0.45, 0.8, -450, -500)
    sn1 = b.noise(p, 3.0, 2.0, x=-800, y=-800)
    sn2 = b.noise(p, 1.2, 2.0, x=-800, y=-1000)
    lo = b.math("MULTIPLY_ADD", cover, -0.45, 0.85, x=-650, y=-900)   # more snow: steeper slopes hold it
    hi = b.math("ADD", lo, 0.12, x=-500, y=-950)
    tilt = b.math("ADD", up, b.math("MULTIPLY_ADD", sn1, 0.16, -0.08, x=-650, y=-750), x=-500, y=-800)
    lie = b.ramp_s(tilt, lo, hi, -350, -800)
    p0 = b.math("MULTIPLY_ADD", cover, -0.75, 0.62, x=-650, y=-1100)  # patchy when there is little snow
    p1 = b.math("ADD", p0, 0.08, x=-500, y=-1100)
    patch = b.ramp_s(sn2, p0, p1, -350, -1000)
    some_snow = b.ramp(cover, 0.0, 0.08, -350, -1150)
    snow_fac = b.math("MULTIPLY", b.math("MULTIPLY", b.math("MULTIPLY", lie, open_sky, x=-200, y=-700), seen,
                                         x=-100, y=-700),
                      b.math("MULTIPLY", patch, some_snow, x=-200, y=-1000), x=-50, y=-800, clamp=True)
    sh = b.noise(p, 25.0, 3.0, x=-200, y=-450)
    sbump = b.node("ShaderNodeBump", 0, -450)
    b.put(sbump.inputs["Strength"], b.math("MULTIPLY_ADD", cover, 0.25, 0.1, x=-200, y=-550))
    sbump.inputs["Distance"].default_value = 0.004
    b.put(sbump.inputs["Height"], sh)
    snow = b.node("ShaderNodeBsdfDiffuse", 200, -450)
    snow.inputs["Color"].default_value = (0.82, 0.84, 0.88, 1.0)
    snow.inputs["Roughness"].default_value = 1.0
    b.put(snow.inputs["Normal"], sbump.outputs["Normal"])
    out = b.node("ShaderNodeMixShader", 1000, 0)
    b.put(out.inputs[0], snow_fac)
    b.put(out.inputs[1], shader_in)
    b.put(out.inputs[2], snow.outputs[0])
    b.put(gout.inputs[0], out.outputs[0])


def _sig(wet_on: bool, snow_on: bool) -> str:
    return f"{GROUP_VERSION}:{int(bool(wet_on))}{int(bool(snow_on))}"


def needed(scene) -> tuple:
    """(wet, snow): whether the project shows any wet or any snow layer – now or in a built animation."""
    from .weather_fx import peak
    return peak(scene, "wet") > 1e-4, peak(scene, "cover") > 1e-4


def node_group(wet_on: bool | None = None, snow_on: bool | None = None) -> bpy.types.NodeTree:
    """The shared group with the parts asked for (None: as it is, or what the scene needs when it is new)."""
    ng = bpy.data.node_groups.get(GROUP)
    if ng is not None and ng.bl_idname != "ShaderNodeTree":
        ng = None
    if wet_on is None or snow_on is None:
        if ng is not None and str(ng.get("fr_sig", "")).startswith(f"{GROUP_VERSION}:"):
            return ng
        scene = bpy.context.scene
        wet_on, snow_on = needed(scene) if scene is not None else (True, True)
    sig = _sig(wet_on, snow_on)
    if ng is not None and ng.get("fr_sig") == sig:
        return ng
    if ng is None:
        ng = bpy.data.node_groups.new(GROUP, "ShaderNodeTree")
    _build(ng, wet_on, snow_on)
    ng["fr_sig"] = sig
    return ng


# ---------------------------------------------------------------------------
# wrapping a material
# ---------------------------------------------------------------------------

def _is(node, name: str) -> bool:
    return node.bl_idname == "ShaderNodeGroup" and node.node_tree is not None and node.node_tree.name == name


def _outer_groups() -> tuple:
    from . import fade, section
    return fade.GROUP, section.GROUP


def porous(mat) -> float:
    """How much darker this material gets when wet (the group's Porous input)."""
    env = mat.get("fr_env")
    if isinstance(env, str):
        return POROUS.get(env, 0.3)
    mid = mat.get("fr_material", "")
    if not mid:
        return 0.3
    from ..core import materials_lib
    spec = materials_lib.get(mid) or {}
    if spec.get("transmission"):
        return 0.0                                 # glass: a wet film, no darker
    if float(spec.get("metallic", 0.0)) >= 0.5:
        return 0.12
    if float(spec.get("roughness", 0.4)) >= 0.6:
        return 0.5
    return 0.3


def wanted(mat) -> bool:
    """Lamps (an emitting look) and the water never get the group."""
    if mat is None or mat.node_tree is None:
        return False
    if mat.get("fr_env") in ("water", "photo") or mat.get("fr_weather"):
        return False
    mid = mat.get("fr_material", "")
    if mid:
        from ..core import materials_lib
        if (materials_lib.get(mid) or {}).get("emission"):
            return False
    return True


def wrap(mat) -> bool:
    """Put the weather group right after the look's shader of every output of ``mat`` (inside a cutaway or fade
    group). Returns True when it changed."""
    if mat is None or mat.node_tree is None:
        return False
    nt = mat.node_tree
    ng = node_group()
    outer = _outer_groups()
    changed = False
    for out in [n for n in nt.nodes if n.bl_idname == "ShaderNodeOutputMaterial"]:
        sock = out.inputs.get("Surface")
        if sock is None or not sock.is_linked:
            continue
        seen = 0
        while sock.is_linked and any(_is(sock.links[0].from_node, g) for g in outer) and seen < 8:
            sock = sock.links[0].from_node.inputs[0]
            seen += 1
        if not sock.is_linked or _is(sock.links[0].from_node, GROUP):
            continue
        node = nt.nodes.new("ShaderNodeGroup")
        node.node_tree = ng
        node.name = node.label = NODE if not nt.nodes.get(NODE) else f"{NODE} {out.name}"
        node.location = (out.location.x, out.location.y - 600)
        node.inputs["Porous"].default_value = porous(mat)
        node.hide = True
        from_sock = sock.links[0].from_socket
        _see_through(nt, from_sock.node, node)
        nt.links.remove(sock.links[0])
        nt.links.new(from_sock, node.inputs[0])
        nt.links.new(node.outputs[0], sock)
        changed = True
    if not mat.get(TAG):
        mat[TAG] = True
    return changed


def _see_through(nt, shader, node) -> None:
    """A look with an Alpha (a decal's Principled BSDF): its clear parts get no film or snow, or the decal would
    show as a dark, glossy or white square on the part."""
    a = shader.inputs.get("Alpha") if shader.bl_idname == "ShaderNodeBsdfPrincipled" else None
    if a is None:
        return
    if a.is_linked:
        nt.links.new(a.links[0].from_socket, node.inputs["Alpha"])
    else:
        node.inputs["Alpha"].default_value = float(a.default_value)


def unwrap(mat) -> bool:
    """Take the weather group out of ``mat`` again: the tree is as it was before ``wrap``."""
    if mat is None:
        return False
    changed = False
    nt = mat.node_tree
    if nt is not None:
        for node in [n for n in nt.nodes if _is(n, GROUP)]:
            src = node.inputs[0].links[0].from_socket if node.inputs[0].is_linked else None
            targets = [lk.to_socket for lk in node.outputs[0].links]
            nt.nodes.remove(node)
            if src is not None:
                for t in targets:
                    nt.links.new(src, t)
            changed = True
    if TAG in mat:
        del mat[TAG]
        changed = True
    return changed


def is_wrapped(mat) -> bool:
    return bool(mat is not None and mat.node_tree is not None and any(_is(n, GROUP) for n in mat.node_tree.nodes))


# ---------------------------------------------------------------------------
# the scene
# ---------------------------------------------------------------------------

def _materials(ob) -> list:
    out = []
    for slot in getattr(ob, "material_slots", ()):
        if slot.material is not None and slot.material not in out:
            out.append(slot.material)
    return out


def targets(scene) -> list:
    """The materials that get the look: the model's parts and their decals, props, drums' ropes, and the outdoor
    ground, deck and quay."""
    from . import build, surroundings
    mats, seen = [], set()
    for ob in scene.objects:
        kind = ob.get(build.PROP_KIND)
        env = ob.get(surroundings.TAG)
        if ob.get("fr_weather") is not None:
            continue
        if not (kind in ("part", "decal", "spool") or env in ENV_ROLES or ob.get(surroundings.PROP_TAG)):
            continue
        for m in _materials(ob):
            if m.name not in seen and wanted(m):
                seen.add(m.name)
                mats.append(m)
    return mats


def apply(scene, on: bool) -> int:
    """On: every target material has the group (materials that already have it are left alone: cheap when nothing
    changed). Off: the group is taken out of every material that has it. Returns how many materials changed."""
    n = 0
    if not on:
        for m in bpy.data.materials:
            if m.get(TAG) or is_wrapped(m):
                n += bool(unwrap(m))
        ng = bpy.data.node_groups.get(GROUP)
        if ng is not None and ng.users == 0:
            bpy.data.node_groups.remove(ng)
        return n
    node_group(*needed(scene))
    for m in targets(scene):
        if not m.get(TAG) or not is_wrapped(m):
            n += bool(wrap(m))
    return n


def remove(scene=None) -> None:
    """Unwrap everything and delete the group."""
    apply(scene, False)
