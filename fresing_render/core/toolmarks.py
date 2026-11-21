"""Tool marks on cut faces (task 0061): what the milled mesh tells the cut-face material. No Blender here.

Every triangle of the milled mesh a cutter made knows **the move that made it last** (``core/machining.py`` gives
each cutter solid its own Manifold id). ``blender/machining.py`` writes that as four per-face attributes; the
material of the cut faces (``blender/toolmarks.py``, shader nodes only – it works with scripts off) reads them and
draws the marks. This file is the contract between the two, and the formula in plain Python (the mirror the tests
compare a render with).

The attributes (FACE domain, all in the milled mesh's own space, metres)
------------------------------------------------------------------------
``fr_mk_o``  FLOAT_VECTOR  a point on the tool's axis at the start of the move (the tip), moved back along the feed
                           direction by the path length the bit had already cut before this move, taken modulo the
                           spacing – so the marks of one straight move carry on into the next one
``fr_mk_d``  FLOAT_VECTOR  the feed direction: the move's direction without its part along the tool axis, unit
                           length; (0, 0, 0) for a move along the axis (a plunge, a drilled hole)
``fr_mk_a``  FLOAT_VECTOR  the tool's axis, unit length, from the tip up into the tool
``fr_mk_p``  FLOAT_VECTOR  (kind, radius, spacing): ``kind`` one of the numbers below as a float; ``radius`` the
                           radius of the tool's flat bottom (m; the circle its bottom edge runs on) – on a wall
                           (kind 2) instead **the step-down**: how much deeper this pass went than the pass above
                           it (m, 0 = none), a line shows across the wall at every multiple of it above the tip;
                           ``spacing`` the distance between two marks at Mark size Real (m)

With q = P - o (P the shaded point), w = a x d, along = q . d, side = q . w, n the face's normal:

====  ==============  =============================================  ==============================================
kind  name            the number the ridges count (u, metres)        the grooves run along (g)
====  ==============  =============================================  ==============================================
0     NONE            – (not cut, or the move is not known: the material's plain machined look)
1     ARCS            along - sqrt(max(R² - side², 0))               a x (sqrt(..) d + side w) = sqrt(..) w - side d
2     FLANK           along                                          a
3     ALONG           q . a                                          d
4     RINGS           | q - (q . a) a |                              a x q
5     RINGS_WALL      q . a                                          a x q
6     ACROSS          along                                          n x d
====  ==============  =============================================  ==============================================

1 = the bottom of a flat / bull-nose tool or face mill moving sideways (arcs of the tool's radius whose centres
move along the path; the trailing edge's faint cross-hatch uses ``along + sqrt(..)``); 2 = a wall cut with the
side of the tool (lines along the tool axis, one per tooth); 3 = a chamfer / V-bit flank (lines along the path);
4 = the bottom of a plunge or of a drilled hole (rings round the axis); 5 = the wall of a plunged or drilled hole
(rings round the axis, one per turn); 6 = a ball or corner-radius pass (fine arcs across the pass).

A ridge is one period of ``u / (spacing * size)``; ``size`` is the panel's Mark size (1 = Real … 10).

What is drawn (``pattern``, ``profile``, ``shade`` below are the node group's formula in plain Python): across one
mark the surface is a shallow scallop, so the normal leans from one side to the other (``look(...)["ridge"]`` at
the cusps) and the roughness changes a little; on a floor the back of the tool adds a faint cross-hatch; and the
highlight is stretched across the grooves (``across`` is the tangent the material gets).

**Any distance (task 0280).** Real marks are often far finer than a pixel (0.05 mm per tooth seen from half a metre:
a fifth of a pixel). Drawn as they are they turn into moiré – coarse stripes that wander over a wall – or vanish. So
the marks are drawn at a *level*: level 0 is every mark, level 1 every second one, level 2 every fourth … The level
is the one that keeps the drawn marks at least ``LOD_PX`` pixels apart on the picture, measured the way the face is
seen (a wall seen from above is squeezed: ``slant``), and between two levels the two are mixed – every mark of the
coarser level is a mark of the finer one, so nothing jumps while the camera moves (``level``, ``lod_profile``).
Marks drawn further apart than ``CAP_FROM`` fade into the plain machined look (``fade``): a shot of the whole machine
shows the sheen only. Walls (kinds FLANK, RINGS_WALL) are satin: a little rougher and partly diffuse, so they read
bright grey also where they mirror a dark room (``look(...)["satin"]``, ``satin``).
"""

from __future__ import annotations

# attribute names on the milled mesh
ATTR_O, ATTR_D, ATTR_A, ATTR_P = "fr_mk_o", "fr_mk_d", "fr_mk_a", "fr_mk_p"
ATTRS = (ATTR_O, ATTR_D, ATTR_A, ATTR_P)

# kinds (stored as floats in fr_mk_p.x)
NONE, ARCS, FLANK, ALONG, RINGS, RINGS_WALL, ACROSS = 0, 1, 2, 3, 4, 5, 6
KIND_NAMES = {NONE: "none", ARCS: "arcs", FLANK: "flank", ALONG: "along", RINGS: "rings", RINGS_WALL: "rings_wall",
              ACROSS: "across"}

MM = 0.001
# marks are never drawn closer together or further apart than this (m)
SPACING_MIN, SPACING_MAX = 0.01 * MM, 2.0 * MM
# spacing of the marks that do not come from the feed: lines along a chamfer; rings on a drill point / plunge bottom
# only when no feed per turn is known (task 0096: they follow F/S like the rest)
SPACING_ALONG = 0.06 * MM
SPACING_RINGS = 0.08 * MM
# a wall's lines are drawn this much weaker than a floor's arcs (at the same strength they read as fluting)
FLANK_TILT = 0.6
# the line where two depths of a wall meet: its width at Mark size Real (m) and how hard it leans the normal,
# against one tool mark
STEP_WIDTH = 0.08 * MM
STEP_TILT = 2.5


# ---------------------------------------------------------------------------
# the look of the marks per cut-face material
# ---------------------------------------------------------------------------

#: ``ridge``: how far the surface leans at the edge of one mark (the tangent of the angle; 0.1 = 5.7 degrees);
#: ``rough``: how much the roughness changes from the middle of a mark to its edge; ``anisotropic``: the sheen
#: across the marks (the Principled BSDF's Anisotropic, 0 = none); ``hatch``: the share of the trailing edge's
#: cross-hatch on a floor (kind ARCS), 0 … 1 of the leading edge's marks; ``satin`` (task 0280): how satin a wall
#: is, 0 … 1 – its roughness grows by ``SATIN_ROUGH`` x satin and its metal by ``SATIN_METAL`` x satin turns diffuse
#: (a side-milled wall scatters the light; as a mirror it showed the dark room: black walls).
LOOKS: dict[str, dict] = {
    "aluminium_machined": dict(ridge=0.10, rough=0.04, anisotropic=0.75, hatch=0.35, satin=1.0),  # bright, crisp
    "steel_machined": dict(ridge=0.06, rough=0.03, anisotropic=0.60, hatch=0.30, satin=0.8),      # finer
    "stainless_brushed": dict(ridge=0.06, rough=0.03, anisotropic=0.65, hatch=0.30, satin=0.8),   # = stainless
    "cast_iron": dict(ridge=0.04, rough=0.05, anisotropic=0.30, hatch=0.20, satin=0.6),           # dull, grainy
    "brass": dict(ridge=0.09, rough=0.035, anisotropic=0.70, hatch=0.35, satin=0.8),
    "bronze": dict(ridge=0.08, rough=0.035, anisotropic=0.65, hatch=0.30, satin=0.8),
    "copper": dict(ridge=0.08, rough=0.04, anisotropic=0.65, hatch=0.30, satin=0.8),
    "zinc_diecast": dict(ridge=0.07, rough=0.04, anisotropic=0.55, hatch=0.30, satin=0.8),
    # plastics: only faint lines, no sheen; not metal, so nothing to make satin
    "pom_white": dict(ridge=0.03, rough=0.02, anisotropic=0.0, hatch=0.15, satin=0.0),
    "pom_black": dict(ridge=0.03, rough=0.02, anisotropic=0.0, hatch=0.15, satin=0.0),
    "plastic_gloss": dict(ridge=0.03, rough=0.02, anisotropic=0.0, hatch=0.15, satin=0.0),
    "plastic_matte": dict(ridge=0.025, rough=0.02, anisotropic=0.0, hatch=0.10, satin=0.0),
}
#: anything else (a cut that looks like the block itself)
LOOK_DEFAULT = dict(ridge=0.05, rough=0.03, anisotropic=0.40, hatch=0.25, satin=0.6)
LOOK_KEYS = ("ridge", "rough", "anisotropic", "hatch", "satin")
#: a wall at satin 1: roughness + this, and this share of its metal turned diffuse (task 0280); any other cut face
#: (a floor) gets SATIN_FLOOR of that – a floor mirrors the room less dark than a wall, and keeps its crisp arcs
SATIN_ROUGH, SATIN_METAL, SATIN_FLOOR = 0.15, 0.3, 0.4
#: the kinds that are walls (cut with the side of the tool, or a hole's wall)
WALL_KINDS = (2, 5)


def look(material_id: str, override: dict | None = None) -> dict:
    """The strengths of the tool marks for a cut-face material id (what ``core.machining.cut_look`` returns;
    also ``"cast_iron"``, which ``cut_look`` shows as tweaked steel). ``override`` replaces single values:
    ``look("steel_machined", look("cast_iron"))`` or ``look("steel_machined", dict(anisotropic=0.3))``."""
    out = dict(LOOKS.get(material_id, LOOK_DEFAULT))
    for key, value in (override or {}).items():
        if key in LOOK_KEYS:
            out[key] = float(value)
    return out


# ---------------------------------------------------------------------------
# the formula (the mirror of the node group "FR tool marks", blender/toolmarks.py)
# ---------------------------------------------------------------------------

#: No shader node knows the size of a pixel: the node group takes the distance to the camera times this angle per
#: pixel (a 1920 px wide picture through a lens of about 50 degrees: 0.87 rad / 1920 = 0.00045). (An orthographic
#: view has no such angle: the levels then still follow the camera's distance.) The angle is an input of the node
#: group ("Pixel angle"); the app sets it from the scene's camera and picture size: ``pixel_angle``.
PIXEL_ANGLE = 0.0005
#: The level of detail (task 0280, see the top of this file): the drawn marks are at least LOD_PX pixels apart (and
#: less than twice that); marks drawn further apart than CAP_FROM (m; or than one mark at the Mark size, when that
#: is wider) fade out until CAP_TO x that, leaving the plain machined look and the sheen. The deepest level drawn.
LOD_PX = 5.0
CAP_FROM, CAP_TO = 3.0 * MM, 2.0
LEVEL_MAX = 24.0
#: the line where two depths of a wall meet is drawn at least this many pixels wide (thinner, it flickered); its
#: lean shrinks by as much as it was widened, so it does not grow louder with distance
LINE_PX = 1.5
#: a direction whose part in the face is shorter than this stands on the face: the fallback is used
TINY = 1e-3
#: the mean of the ridge profile over one mark (the roughness changes round it, so its mean stays the material's)
RIDGE_MEAN = 1.0 / 3.0


def _unit(v):
    """Unit vectors; a zero vector stays zero (as Blender's Normalize node does)."""
    import numpy as np
    v = np.asarray(v, float)
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    ok = n > 1e-12
    return np.where(ok, v / np.where(ok, n, 1.0), 0.0)


def _dot(a, b):
    import numpy as np
    return (np.asarray(a, float) * np.asarray(b, float)).sum(axis=-1)


def _frame(P, o, d, a, radius):
    """(q, w, along, side, q . a, the square root, q's part square to the axis) of the table at the top."""
    import numpy as np
    P, o, d, a = (np.asarray(v, float) for v in (P, o, d, a))
    q = P - o                                        # small numbers first: the coordinates can be a metre
    w = np.cross(a, d)
    along, side, qa = _dot(q, d), _dot(q, w), _dot(q, a)
    root = np.sqrt(np.maximum(float(radius) ** 2 - side ** 2, 0.0))      # outside the tool's swath: 0
    radial = q - qa[..., None] * a
    return q, w, along, side, qa, root, radial


def period(spacing: float, size: float = 1.0) -> float:
    """The width of one mark (m): the spacing times the Mark size; the spacing never below SPACING_MIN."""
    return max(float(spacing), SPACING_MIN) * float(size)


def profile(u, spacing: float, size: float = 1.0):
    """``(ridge, tilt)`` of the number ``u``. Across one mark the surface is a shallow scallop: a cusp where two
    passes of the tool meet (ridge 1), its lowest line in the middle (ridge 0). ``tilt`` is how far the surface's
    normal leans towards growing ``u``, as a share of the material's ``ridge``: +1 just after a cusp, 0 in the
    middle, -1 just before the next cusp (the slope of a scallop is a straight line)."""
    import numpy as np
    x = np.asarray(u, float) / period(spacing, size)
    t = 1.0 - 2.0 * (x - np.floor(x))
    return t * t, t


def level(spacing: float, size: float, distance, scale: float = 1.0, angle: float = PIXEL_ANGLE, slant=1.0):
    """The level of detail the marks are drawn at (0 = every mark, 1 = every second one, a fraction mixes two
    levels): ``log2(LOD_PX / pixels)`` of one mark, never below 0 (nor above LEVEL_MAX). ``distance``: from the
    camera (m); ``scale``: the milled object's scale; ``angle``: one pixel's angle; ``slant``: how much shorter a mark
    looks because the face is seen at a slant, 0 … 1 (``slant``)."""
    import numpy as np
    dist = np.asarray(distance, float)
    px = period(spacing, size) * scale * np.asarray(slant, float) / np.maximum(dist * angle, 1e-12)
    lev = np.log2(LOD_PX / np.maximum(px, 1e-12))
    return np.clip(lev, 0.0, LEVEL_MAX)


def slant(across_world, incoming):
    """How much shorter a mark looks on the picture than it is, 0 … 1: ``sqrt(1 - (e . I)^2)`` of the unit
    direction across the marks ``e`` and the unit direction to the camera ``I`` (both world)."""
    import numpy as np
    c = _dot(_unit(across_world), _unit(incoming))
    return np.sqrt(np.maximum(1.0 - c * c, 0.0))


def lod_profile(u, spacing: float, size: float = 1.0, lev=0.0):
    """``(ridge, tilt)`` of ``profile`` at the level ``lev``: the two levels round it, mixed by its fraction."""
    import numpy as np
    lev = np.asarray(lev, float)
    k = np.floor(lev)
    b = lev - k
    p = period(spacing, size) * np.exp2(k)
    ra, ta = profile(u, p)
    rb, tb = profile(u, 2.0 * p)
    return ra + (rb - ra) * b, ta + (tb - ta) * b


def _grow(kind, P, o, d, a, radius):
    """(u, the direction u grows in – any length)."""
    import numpy as np
    d, a = np.asarray(d, float), np.asarray(a, float)
    q, w, along, side, qa, root, radial = _frame(P, o, d, a, radius)
    kind = int(round(float(kind)))
    if kind == ARCS:
        return along - root, root[..., None] * d + side[..., None] * w
    if kind in (FLANK, ACROSS):
        return along, np.broadcast_to(d, q.shape)
    if kind in (ALONG, RINGS_WALL):
        return qa, np.broadcast_to(a, q.shape)
    if kind == RINGS:
        return np.linalg.norm(radial, axis=-1), radial
    return np.zeros(q.shape[:-1]), np.zeros(q.shape)


def _face_normal(n, a, shape):
    """The face's unit normal; without one the tool's axis (a floor)."""
    import numpy as np
    return np.broadcast_to(_unit(a if n is None else n), shape)


def _in_face(G, n, a):
    """The unit direction in the face (unit normal ``n``) that ``G`` points along; ``a x n`` when ``G`` stands
    on the face (a ball pass on a face that looks along the feed: its grooves run along the tool's axis)."""
    import numpy as np
    G = _unit(G)
    E = G - _dot(G, n)[..., None] * n
    fallback = np.cross(np.broadcast_to(np.asarray(a, float), n.shape), n)
    return _unit(np.where(_dot(E, E)[..., None] < TINY * TINY, fallback, E))


def across(kind, P, o, d, a, radius: float, n=None):
    """The unit direction in the face across the grooves (the way ``u`` grows). The node group feeds this to the
    Principled BSDF as its Tangent: Blender stretches the highlight *along* the tangent, and a milled face
    stretches it *across* its grooves. A zero vector where nothing is known (the centre of a ring on a floor)."""
    _u, G = _grow(kind, P, o, d, a, radius)
    return _in_face(G, _face_normal(n, a, G.shape), a)


def pattern(kind, P, o, d, a, radius: float, spacing: float, n=None, size: float = 1.0):
    """The marks at the point(s) ``P``: ``(u, ridge, groove)``.

    ``P``: one point or an array (..., 3), in the milled mesh's own space (m); ``o``, ``d``, ``a``, ``radius``,
    ``spacing``: the face's attributes (the top of this file); ``n``: the face's normal (kind ACROSS needs it;
    without one the tool's axis is taken: a floor); ``size``: the Mark size (1 = Real … 10).

    ``u``: the number the ridges count (m); ``ridge``: 0 … 1 across one mark of ``u / (spacing * size)``, 1 on
    the cusp between two marks and 0 in the middle (``profile``), exactly as the node group works it out;
    ``groove``: the unit direction the grooves run along, in the face (``n x across``; the table's ``g`` or its
    opposite)."""
    import numpy as np
    u, G = _grow(kind, P, o, d, a, radius)
    nn = _face_normal(n, a, G.shape)
    return u, profile(u, spacing, size)[0], _unit(np.cross(nn, _in_face(G, nn, a)))


def hatch(P, o, d, a, radius: float, spacing: float, n=None, size: float = 1.0, lev=0.0):
    """The trailing edge's faint cross-hatch on a floor (kind ARCS): ``(u, ridge, tilt, across)`` of the arcs
    the back of the tool leaves, ``u = along + sqrt(..)``, at the level ``lev``; ``across`` is zero where it is not
    known."""
    import numpy as np
    d, a = np.asarray(d, float), np.asarray(a, float)
    _q, w, along, side, _qa, root, _radial = _frame(P, o, d, a, radius)
    u = along + root
    G = _unit(root[..., None] * d - side[..., None] * w)
    nn = _face_normal(n, a, G.shape)
    ridge, tilt = lod_profile(u, spacing, size, lev)
    return u, ridge, tilt, _unit(G - _dot(G, nn)[..., None] * nn)


def pixel_angle(width_px: int, lens_mm: float = 50.0, sensor_mm: float = 36.0) -> float:
    """The angle one pixel covers (rad) in a picture ``width_px`` wide through a lens of ``lens_mm``: what the
    node group's input "Pixel angle" may be set to when the picture is not about 1920 px wide (PIXEL_ANGLE)."""
    return float(sensor_mm) / max(float(lens_mm), 1e-6) / max(int(width_px), 1)


def fade(spacing: float, size: float, distance, scale: float = 1.0, angle: float = PIXEL_ANGLE, slant=1.0):
    """How much of the ridges shows, 0 … 1: 1 while the drawn marks (``level``) lie at most CAP_FROM apart (or one
    mark at the Mark size, when that is wider), 0 from CAP_TO times that on – smoothly between. The sheen stays."""
    import numpy as np
    lev = level(spacing, size, distance, scale, angle, slant)
    p = period(spacing, size)
    lo = max(CAP_FROM, p)
    x = np.clip((p * np.exp2(lev) - lo) / ((CAP_TO - 1.0) * lo), 0.0, 1.0)
    return 1.0 - x * x * (3.0 - 2.0 * x)


def step_line(height, step: float, size: float = 1.0, pixel: float = 0.0):
    """The line where two depths of a wall meet, 0 … 1 (1 on the line): ``height`` the shaded point's height above
    the tip of the pass that owns the wall (q . a, m), ``step`` how much deeper that pass went than the one above
    (m; 0: no line). A line lies at every multiple of ``step`` above the tip – not at the floor itself –,
    ``STEP_WIDTH`` x size wide, but at least ``LINE_PX`` pixels (``pixel``: one pixel's size on the wall, m; the
    line then leans less by as much as it was widened)."""
    import numpy as np
    h = np.asarray(height, float)
    if step <= 1e-6:
        return np.zeros_like(h)
    real = STEP_WIDTH * size
    width = np.maximum(real, LINE_PX * np.asarray(pixel, float))
    g = h / step
    near = np.abs(g + 0.5 - np.floor(g + 0.5) - 0.5) * step
    return np.clip(1.0 - near / (0.5 * width), 0.0, 1.0) * (g > 0.5) * (real / width)


def satin(kind, looks: dict | None = None, roughness: float = 0.2, metallic: float = 1.0):
    """(roughness, metallic) of a cut face of ``kind`` (no move known, kind 0: the material's own): a wall is satin
    (``SATIN_ROUGH``, ``SATIN_METAL`` times the look's ``satin``), any other cut face ``SATIN_FLOOR`` of that."""
    import numpy as np
    lk = {**LOOK_DEFAULT, **(looks or {})}
    k = np.rint(np.asarray(kind, float))
    share = np.where(np.isin(k, WALL_KINDS), 1.0, SATIN_FLOOR) * (k > 0.5) * lk["satin"]
    return (np.clip(roughness + SATIN_ROUGH * share, 0.0, 1.0), metallic * (1.0 - SATIN_METAL * share))


def shade(kind, P, o, d, a, radius: float, spacing: float, n=None, size: float = 1.0, strength: float = 1.0,
          looks: dict | None = None, roughness: float = 0.2, fade_by=1.0, lev=0.0, pixel=0.0,
          metallic: float = 1.0) -> dict:
    """What the node group gives the material where there are marks: ``normal`` (unit: the face's normal leaning
    over the marks), ``roughness``, ``metallic`` (both made satin: ``satin``), ``tangent`` (= ``across``),
    ``anisotropic``, ``ridge``. ``looks``: a ``look(...)``; ``roughness``, ``metallic``: the material's own;
    ``fade_by``: a ``fade(...)``; ``lev``: a ``level(...)``; ``pixel``: one pixel's size on the face (m, the
    step-down line's width)."""
    import numpy as np
    lk = {**LOOK_DEFAULT, **(looks or {})}
    kind = int(round(float(kind)))
    u, G = _grow(kind, P, o, d, a, radius)
    nn = _face_normal(n, a, G.shape)
    e = _in_face(G, nn, a)
    known = (_dot(e, e) > 0.5).astype(float)
    ridge, tilt = lod_profile(u, spacing, size, lev)
    amount = float(strength) * np.asarray(fade_by, float) * known
    lean = tilt[..., None] * e
    wave = ridge - RIDGE_MEAN
    if kind == FLANK:                          # a wall: weaker lines, and the line where two depths meet
        P_, o_, a_ = (np.asarray(x, float) for x in (P, o, a))
        up = np.broadcast_to(a_, G.shape)
        up = up - _dot(up, nn)[..., None] * nn                # the axis, in the face
        lean = (FLANK_TILT * lean
                + (STEP_TILT * step_line(_dot(P_ - o_, a_), float(radius), size, pixel))[..., None] * up)
    if kind == ARCS:
        _u2, ridge2, tilt2, e2 = hatch(P, o, d, a, radius, spacing, n, size, lev)
        lean = lean + lk["hatch"] * tilt2[..., None] * e2
        wave = wave + lk["hatch"] * (ridge2 - RIDGE_MEAN)
    rough_s, metal_s = satin(kind, lk, roughness, metallic)
    return dict(normal=_unit(nn + (amount * lk["ridge"])[..., None] * lean),
                roughness=np.clip(rough_s + lk["rough"] * amount * wave, 0.0, 1.0), metallic=metal_s,
                tangent=e, anisotropic=np.clip(lk["anisotropic"] * float(strength), 0.0, 1.0) * known,
                ridge=ridge)
