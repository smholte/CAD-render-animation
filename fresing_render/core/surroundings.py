"""Surroundings: where the machine stands. Pure Python (no Blender), so it can be tested alone.

A layout is a list of simple shapes in metres, in a frame centred on the machine with the floor
(deck, quay, hall floor) at z = 0. ``blender/surroundings.py`` turns the shapes into meshes and
puts the frame under the model. Everything is made in code: no photos, no downloads.

Nothing is placed inside the machine's own space (``keepout``): the machine's footprint plus a
clearance all round, from the floor up to its height plus a margin.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field, replace

# ---------------------------------------------------------------------------
# the choices (also the items of the Background setting; numbers are stored in project files)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Kind:
    id: str
    number: int          # stored in .blend files: never change or reuse
    label: str
    group: str           # studio | photo | offshore | workshop
    icon: str
    description: str


KINDS: tuple[Kind, ...] = (
    Kind("COLOR", 0, "Solid colour", "studio", "COLOR",
         "One flat colour behind the machine, with studio light. Pick the colour below"),
    Kind("TRANSPARENT", 3, "None (transparent)", "studio", "TEXTURE",
         "No background: a PNG you can put on any slide or web page. The machine keeps its light"),
    Kind("SKY", 2, "Sky", "studio", "LIGHT_SUN",
         "Open sky with a sun. Set the sun height and turn it below"),
    Kind("HDRI", 1, "360° photo", "photo", "IMAGE_BACKGROUND",
         "A 360° photo (HDRI) from your library is the background and the light. The machine stands "
         "on the photo's ground with its own shadow"),
    Kind("SEA", 4, "Open sea", "offshore", "MOD_OCEAN",
         "Sea to the horizon under a sky. The machine stands on the water line: lower or raise the water "
         "under 'Water level'"),
    Kind("DECK", 5, "Vessel deck", "offshore", "MOD_OCEAN",
         "The machine on the work deck of a vessel at sea: steel deck, railings, containers"),
    Kind("QUAY", 6, "Quayside", "offshore", "MOD_OCEAN",
         "The machine on a concrete quay with bollards, the water behind it"),
    Kind("FACTORY", 7, "Clean factory hall", "workshop", "HOME",
         "A bright, clean factory hall: epoxy floor with walkway lines, columns, roof trusses, light lines"),
    Kind("CNC", 8, "CNC machining hall", "workshop", "HOME",
         "A machining hall with rows of machine tools and racks along the walls"),
    Kind("ASSEMBLY", 9, "Assembly hall", "workshop", "HOME",
         "A tall assembly hall with an overhead crane, workbenches and frames being built"),
    Kind("WAREHOUSE", 10, "Warehouse", "workshop", "HOME",
         "A warehouse with pallet racks and pallets around the machine"),
)
KIND = {k.id: k for k in KINDS}
GROUP_LABELS = {"studio": "Studio", "photo": "Photo", "offshore": "Offshore", "workshop": "Workshop"}

BUILT = tuple(k.id for k in KINDS if k.group in ("offshore", "workshop"))   # made in 3D by the app
SEA_KINDS = ("SEA", "DECK", "QUAY")
HALL_KINDS = ("FACTORY", "CNC", "ASSEMBLY", "WAREHOUSE")

SEA_RADIUS = 20000.0      # metres: the sea reaches (almost) the horizon
SEA_RIM = 400.0           # the outer edge of the sea rises this much: no gap under the horizon


def enum_items() -> list:
    """Items for the Background setting, grouped under headings (Blender EnumProperty format)."""
    items: list = []
    group = None
    for k in KINDS:
        if k.group != group:
            if group is not None:
                items.append(None)
            items.append(("", GROUP_LABELS[k.group], ""))
            group = k.group
        items.append((k.id, k.label, k.description, k.icon, k.number))
    return items


# ---------------------------------------------------------------------------
# shapes
# ---------------------------------------------------------------------------


@dataclass
class Box:
    """Box standing on z (bottom face), centred on x/y, turned ``rot`` radians around z."""
    mat: str
    x: float
    y: float
    z: float
    sx: float
    sy: float
    sz: float
    rot: float = 0.0


@dataclass
class Beam:
    """Rectangular bar from p0 to p1; ``w`` sideways, ``h`` in the most upward direction."""
    mat: str
    p0: tuple
    p1: tuple
    w: float
    h: float


@dataclass
class Tube:
    mat: str
    p0: tuple
    p1: tuple
    r: float
    seg: int = 10


@dataclass
class Sphere:
    mat: str
    c: tuple
    r: float
    seg: int = 12


@dataclass
class Quad:
    """A flat panel; its front side (normal by the right-hand rule of p0→p1→p2) is the visible side."""
    mat: str
    pts: tuple


def _rot(x: float, y: float, a: float) -> tuple[float, float]:
    c, s = math.cos(a), math.sin(a)
    return x * c - y * s, x * s + y * c


def _move_pt(p, dx, dy, dz, a):
    x, y = _rot(p[0], p[1], a)
    return (x + dx, y + dy, p[2] + dz)


def place(shapes, dx: float = 0.0, dy: float = 0.0, dz: float = 0.0, rot: float = 0.0) -> list:
    """Copies of ``shapes`` turned by ``rot`` around z and moved by (dx, dy, dz)."""
    out = []
    for s in shapes:
        if isinstance(s, Box):
            x, y = _rot(s.x, s.y, rot)
            out.append(replace(s, x=x + dx, y=y + dy, z=s.z + dz, rot=s.rot + rot))
        elif isinstance(s, (Beam, Tube)):
            out.append(replace(s, p0=_move_pt(s.p0, dx, dy, dz, rot), p1=_move_pt(s.p1, dx, dy, dz, rot)))
        elif isinstance(s, Sphere):
            out.append(replace(s, c=_move_pt(s.c, dx, dy, dz, rot)))
        elif isinstance(s, Quad):
            out.append(replace(s, pts=tuple(_move_pt(p, dx, dy, dz, rot) for p in s.pts)))
    return out


def recolor(shapes, mapping: dict) -> list:
    return [replace(s, mat=mapping.get(s.mat, s.mat)) for s in shapes]


def footprint(shape) -> tuple[float, float, float, float, float, float]:
    """(xmin, xmax, ymin, ymax, zmin, zmax) of a shape (boxes: of their turned corners)."""
    if isinstance(shape, Box):
        pts = []
        for cx in (-shape.sx / 2, shape.sx / 2):
            for cy in (-shape.sy / 2, shape.sy / 2):
                x, y = _rot(cx, cy, shape.rot)
                pts.append((x + shape.x, y + shape.y))
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        return min(xs), max(xs), min(ys), max(ys), shape.z, shape.z + shape.sz
    if isinstance(shape, (Beam, Tube)):
        pad = shape.r if isinstance(shape, Tube) else max(shape.w, shape.h) / 2
        xs, ys, zs = zip(shape.p0, shape.p1)
        return min(xs) - pad, max(xs) + pad, min(ys) - pad, max(ys) + pad, min(zs) - pad, max(zs) + pad
    if isinstance(shape, Sphere):
        x, y, z = shape.c
        r = shape.r
        return x - r, x + r, y - r, y + r, z - r, z + r
    xs, ys, zs = zip(*shape.pts)
    return min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)


# ---------------------------------------------------------------------------
# props for scale (also used inside the surroundings)
# ---------------------------------------------------------------------------

PROPS = {
    "PERSON": ("Person", "A grey mannequin, 1.8 m tall"),
    "CONTAINER": ("20 ft container", "A 20 ft shipping container, 6.06 × 2.44 × 2.59 m"),
    "PALLET": ("Euro pallet", "A euro pallet, 1.2 × 0.8 m, with a load of boxes"),
    "BARRIER": ("Safety barrier", "A 2 m steel safety barrier"),
}


def person() -> list:
    s: list = []
    for side in (-1, 1):
        x = 0.1 * side
        s.append(Box("mannequin", x, 0.04, 0.0, 0.11, 0.27, 0.08))
        s.append(Tube("mannequin", (x, 0.0, 0.06), (x, 0.0, 0.92), 0.068, 12))
        s.append(Tube("mannequin", (0.235 * side, 0.0, 1.42), (0.27 * side, 0.02, 0.84), 0.047, 10))
        s.append(Sphere("mannequin", (0.275 * side, 0.025, 0.8), 0.05, 8))
    s.append(Box("mannequin", 0.0, 0.0, 0.84, 0.36, 0.21, 0.2))
    s.append(Box("mannequin", 0.0, 0.0, 1.0, 0.42, 0.23, 0.46))
    s.append(Tube("mannequin", (-0.17, 0.0, 1.42), (0.17, 0.0, 1.42), 0.065, 10))
    s.append(Tube("mannequin", (0.0, 0.0, 1.45), (0.0, 0.0, 1.57), 0.052, 10))
    s.append(Sphere("mannequin", (0.0, 0.0, 1.675), 0.115, 14))
    return s


CONTAINER_SIZE = (6.058, 2.438, 2.591)


def container(colour: str = "container_blue") -> list:
    """20 ft container, doors at +x."""
    L, W, H = CONTAINER_SIZE
    f = 0.16
    s: list = [Box(colour, 0.0, 0.0, 0.03, L - 0.06, W - 0.06, H - 0.06)]
    for x in (-L / 2 + f / 2, L / 2 - f / 2):
        for y in (-W / 2 + f / 2, W / 2 - f / 2):
            s.append(Box("container_frame", x, y, 0.0, f, f, H))
    for z in (0.0, H - f):
        for y in (-W / 2 + f / 2, W / 2 - f / 2):
            s.append(Box("container_frame", 0.0, y, z, L - 2 * f, f, f))
        for x in (-L / 2 + f / 2, L / 2 - f / 2):
            s.append(Box("container_frame", x, 0.0, z, f, W - 2 * f, f))
    for y in (-0.9, -0.35, 0.35, 0.9):
        s.append(Tube("galvanized", (L / 2 + 0.02, y, 0.15), (L / 2 + 0.02, y, H - 0.15), 0.022, 8))
    return s


def pallet() -> list:
    s: list = []
    for y in (-0.35, 0.0, 0.35):
        s.append(Box("wood", 0.0, y, 0.0, 1.2, 0.1, 0.022))
        s.append(Box("wood", 0.0, y, 0.1, 1.2, 0.1, 0.022))
        for x in (-0.5275, 0.0, 0.5275):
            s.append(Box("wood", x, y, 0.022, 0.145, 0.1, 0.078))
    for x in (-0.5275, -0.26, 0.0, 0.26, 0.5275):
        s.append(Box("wood", x, 0.0, 0.122, 0.145 if abs(x) > 0.5 or x == 0 else 0.1, 0.8, 0.022))
    return s


PALLET_H = 0.144


def pallet_load(rng: random.Random, max_h: float = 1.2) -> list:
    """A pallet with boxes or a wrapped load on it."""
    s = pallet()
    h = rng.uniform(0.45, max_h)
    if rng.random() < 0.5:
        s.append(Box("wrap", 0.0, 0.0, PALLET_H, 1.16, 0.78, h))
    else:
        rows = rng.choice((1, 2))
        bh = h / rows
        for k in range(rows):
            for x in (-0.3, 0.3):
                for y in (-0.2, 0.2):
                    s.append(Box("cardboard", x, y, PALLET_H + k * bh, 0.57, 0.38, bh - 0.004))
    return s


def barrier() -> list:
    s: list = []
    for x in (-0.95, 0.95):
        s.append(Box("galvanized", x, 0.0, 0.0, 0.08, 0.6, 0.04))
        s.append(Tube("barrier_frame", (x, 0.0, 0.04), (x, 0.0, 1.0), 0.024, 10))
    s.append(Tube("barrier_frame", (-0.95, 0.0, 1.0), (0.95, 0.0, 1.0), 0.024, 10))
    s.append(Tube("barrier_frame", (-0.95, 0.0, 0.25), (0.95, 0.0, 0.25), 0.02, 10))
    s.append(Box("barrier", 0.0, 0.0, 0.42, 1.8, 0.016, 0.42))
    return s


def prop_shapes(kind: str) -> list:
    if kind == "PERSON":
        return person()
    if kind == "CONTAINER":
        return container()
    if kind == "PALLET":
        return pallet_load(random.Random(7), 0.9)
    if kind == "BARRIER":
        return barrier()
    raise KeyError(kind)


def prop_size(kind: str) -> tuple[float, float, float]:
    xs, ys, zs = [], [], []
    for sh in prop_shapes(kind):
        x0, x1, y0, y1, z0, z1 = footprint(sh)
        xs += [x0, x1]
        ys += [y0, y1]
        zs += [z0, z1]
    return max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)


def prop_spot(index: int, machine: tuple, sizes: list[tuple[float, float]]) -> tuple[float, float]:
    """Where the n-th prop goes: in a row along the machine's right-hand (+x) side, front first.

    ``machine`` = (xmin, xmax, ymin, ymax) in world metres; ``sizes`` = (sx, sy) of props 0..index.
    """
    xmin, xmax, ymin, ymax = machine
    gap = 0.8
    y = ymin
    for i, (sx, sy) in enumerate(sizes):
        if i == index:
            return xmax + gap + sx / 2, y + sy / 2
        y += sy + 0.6
    raise IndexError(index)


# ---------------------------------------------------------------------------
# layouts
# ---------------------------------------------------------------------------


@dataclass
class Layout:
    kind: str
    # role -> shapes. floor; shell (walls and roof, seen from inside only); structure; high (roof
    # trusses, crane: cast no shadow on the machine); contents; lights
    parts: dict = field(default_factory=dict)
    keepout: tuple = (1.0, 1.0, 1.0)             # half sizes x, y and the height kept free
    water_level: float | None = None             # z of the sea (None = no sea)
    extent: float = 50.0                         # radius that holds everything (camera clip)
    hall: tuple | None = None                    # (half x, half y, height) of a hall
    view_radius: float = 0.0                     # the default camera's side stays open this far

    def add(self, role: str, shapes) -> None:
        self.parts.setdefault(role, []).extend(shapes)

    def put(self, role: str, shapes) -> bool:
        """Add a group of shapes (one rack bay, one machine...) only if it keeps the machine's space and
        the camera's view free. Returns whether it was added."""
        if any(overlaps_keepout(sh, self.keepout) or blocks_view(sh, self) for sh in shapes):
            return False
        self.add(role, shapes)
        return True

    def all_shapes(self):
        for shapes in self.parts.values():
            yield from shapes


def keepout_for(w: float, d: float, h: float) -> tuple[float, float, float]:
    clear = max(2.0, 0.25 * max(w, d))
    return w / 2 + clear, d / 2 + clear, h + max(1.5, 0.15 * h)


def overlaps_keepout(shape, keepout, tol: float = 1e-6) -> bool:
    kx, ky, kh = keepout
    x0, x1, y0, y1, z0, z1 = footprint(shape)
    if z1 <= 0.012 or z0 >= kh:                    # floor markings, or above the machine
        return False
    return x0 < kx - tol and x1 > -kx + tol and y0 < ky - tol and y1 > -ky + tol


def blocks_view(shape, lay: "Layout") -> bool:
    """True if the shape stands on the side the default camera looks from (front right: +x, -y),
    between the camera and the machine. Floor markings never block."""
    if lay.view_radius <= 0:
        return False
    kx, ky, _ = lay.keepout
    x0, x1, y0, y1, z0, z1 = footprint(shape)
    if z1 <= 0.012:
        return False
    if x1 < -0.3 * kx or y0 > 0.3 * ky:                # not in the front-right quarter
        return False
    nx, ny = max(x0, 0.0), min(y1, 0.0)                 # nearest point of the shape to the centre
    if x0 < 0 < x1:
        nx = 0.0
    if y0 < 0 < y1:
        ny = 0.0
    return math.hypot(nx, ny) < lay.view_radius


def _free(x, y, sx, sy, keepout, margin=0.0) -> bool:
    kx, ky, _ = keepout
    return abs(x) - sx / 2 >= kx + margin or abs(y) - sy / 2 >= ky + margin


def _steps(a: float, b: float, step: float) -> list[float]:
    n = max(1, int(round((b - a) / step)))
    return [a + (b - a) * i / n for i in range(n + 1)]


def _line(mat, x0, y0, x1, y1, width=0.1) -> Box:
    """Painted line on the floor (5 mm thick)."""
    length = math.hypot(x1 - x0, y1 - y0)
    return Box(mat, (x0 + x1) / 2, (y0 + y1) / 2, 0.0, length, width, 0.005, math.atan2(y1 - y0, x1 - x0))


def _rect_lines(mat, hx, hy, width=0.1) -> list:
    return [_line(mat, -hx, -hy, hx, -hy, width), _line(mat, -hx, hy, hx, hy, width),
            _line(mat, -hx, -hy + width / 2, -hx, hy - width / 2, width),
            _line(mat, hx, -hy + width / 2, hx, hy - width / 2, width)]


def build(kind: str, size: tuple[float, float, float], detail: str = "SIMPLE", water_level: float = 0.0) -> Layout:
    """Layout of a built-in surrounding for a machine of ``size`` = (x, y, z) metres."""
    w, d, h = (max(0.2, float(v)) for v in size)
    detailed = detail == "DETAILED"
    rng = random.Random(1234)
    lay = Layout(kind, keepout=keepout_for(w, d, h))
    lay.view_radius = max(8.0, 2.6 * max(w, d, h))
    if kind == "SEA":
        lay.water_level = water_level
        lay.extent = SEA_RADIUS
    elif kind == "DECK":
        _deck(lay, w, d, h, detailed, rng)
    elif kind == "QUAY":
        _quay(lay, w, d, h, detailed, rng)
    elif kind in HALL_KINDS:
        _hall(lay, kind, w, d, h, detailed, rng)
    else:
        raise KeyError(kind)
    return lay


# ---- offshore ----------------------------------------------------------------

FREEBOARD = 3.0      # vessel deck above the water
QUAY_HEIGHT = 3.0    # quay above the water


def _railing(mat, x0, y0, x1, y1, height=1.1, spacing=1.5) -> list:
    s: list = []
    n = max(1, int(round(math.hypot(x1 - x0, y1 - y0) / spacing)))
    for i in range(n + 1):
        t = i / n
        x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
        s.append(Tube(mat, (x, y, 0.0), (x, y, height), 0.03, 8))
    for z, r in ((height, 0.03), (height / 2, 0.022)):
        s.append(Tube(mat, (x0, y0, z), (x1, y1, z), r, 8))
    return s


def _container_stack(lay, rng, x, y, rows_x, cols_y, levels, rot=0.0) -> None:
    L, W, H = CONTAINER_SIZE
    colours = ["container_blue", "container_red", "container_green", "container_white", "container_grey"]
    for i in range(rows_x):
        for j in range(cols_y):
            for k in range(levels):
                col = rng.choice(colours)
                lx, ly = _rot(i * (L + 0.35), j * (W + 0.1), rot)
                lay.put("contents", recolor(place(container(), x + lx, y + ly, k * H, rot),
                                            {"container_blue": col}))


def _deck(lay: Layout, w, d, h, detailed, rng) -> None:
    kx, ky, kh = lay.keepout
    aft = max(10.0, kx + 6.0)              # deck behind the machine (+x, the stern)
    fwd = max(28.0, kx + 20.0)             # deck in front of it (-x), with containers
    hy = max(9.0, ky + 4.0)
    length = aft + fwd
    cx = (aft - fwd) / 2
    fb = FREEBOARD
    lay.water_level = -fb
    lay.extent = SEA_RADIUS
    lay.add("floor", [Box("deck", cx, 0.0, -0.3, length, 2 * hy, 0.3)])
    house = 12.0 if detailed else 0.0
    hull_len = length + house + 14.0
    hull_cx = cx - (house + 14.0) / 2
    lay.add("structure", [
        Box("hull", hull_cx, 0.0, -fb + 0.6, hull_len, 2 * hy + 0.3, fb - 0.9),
        Box("hull_red", hull_cx, 0.0, -fb - 5.0, hull_len, 2 * hy + 0.3, 5.6),
        Box("deck", -fwd - (house + 14.0) / 2, 0.0, -0.3, house + 14.0, 2 * hy, 0.3),
    ])
    # railings along both sides and the stern; walkway lines inside them
    xa, xf = aft, -fwd - house - 14.0
    rails = _railing("rail_yellow", xf, -hy + 0.08, xa - 0.08, -hy + 0.08)
    rails += _railing("rail_yellow", xf, hy - 0.08, xa - 0.08, hy - 0.08)
    rails += _railing("rail_yellow", xa - 0.08, -hy + 0.08, xa - 0.08, -2.5)
    rails += _railing("rail_yellow", xa - 0.08, 2.5, xa - 0.08, hy - 0.08)
    lay.add("structure", rails)
    lay.add("floor", [_line("line_yellow", xf + 1, -hy + 1.0, xa - 1, -hy + 1.0, 0.12),
                      _line("line_yellow", xf + 1, hy - 1.0, xa - 1, hy - 1.0, 0.12)])
    # containers ahead of the machine (-x)
    L, W, H = CONTAINER_SIZE
    x0 = -kx - 2.5 - L / 2
    if detailed:
        _container_stack(lay, rng, x0 - L - 0.4, -W - 0.05, 2, 2, 2)
        _container_stack(lay, rng, x0 - L - 0.4, hy - 2.5 - W, 2, 1, 1)
    else:
        _container_stack(lay, rng, x0, -W / 2 - 0.05, 1, 2, 1)
    if detailed:
        # deckhouse at the bow end, bitts along the sides
        hx0 = -fwd - house
        lay.add("structure", [Box("deckhouse", hx0 + house / 2 - 7.0, 0.0, 0.0, house, 2 * hy - 2.0, 7.5),
                              Box("deckhouse", hx0 + house / 2 - 8.0, 0.0, 7.5, house - 3.0, 2 * hy - 5.0, 3.0)])
        for z0 in (2.6, 5.3):
            lay.add("structure", [Box("glass_dark", hx0 + house / 2 - 7.0, 0.0, z0, house + 0.04, 2 * hy - 1.96, 1.1)])
        lay.add("structure", [Box("glass_dark", hx0 + house / 2 - 8.0, 0.0, 8.4, house - 2.96, 2 * hy - 4.96, 1.0)])
        for x in _steps(xf + 8, xa - 3, 9.0):
            for side in (-1, 1):
                y = side * (hy - 0.6)
                bitt = [Tube("bollard", (x - 0.35, y, 0.0), (x - 0.35, y, 0.6), 0.16, 12),
                        Tube("bollard", (x + 0.35, y, 0.0), (x + 0.35, y, 0.6), 0.16, 12),
                        Box("bollard", x, y, 0.0, 1.2, 0.5, 0.06)]
                lay.put("contents", bitt)


def _quay(lay: Layout, w, d, h, detailed, rng) -> None:
    kx, ky, kh = lay.keepout
    edge = ky + 5.0                      # the quay edge, behind the machine (+y)
    qx = max(45.0, kx + 30.0)
    land = max(40.0, ky + 30.0)
    lay.water_level = -QUAY_HEIGHT
    lay.extent = SEA_RADIUS
    lay.add("floor", [Box("concrete", 0.0, (edge - land) / 2, -9.0, 2 * qx, edge + land, 9.0)])
    lay.add("structure", [Box("kerb", 0.0, edge - 0.18, 0.0, 2 * qx, 0.36, 0.18)])
    lay.add("floor", [_line("line_yellow", -qx + 1, edge - 2.2, qx - 1, edge - 2.2, 0.15)])
    for x in _steps(-qx + 5, qx - 5, 14.0):
        b = [Tube("bollard", (x, edge - 0.9, 0.0), (x, edge - 0.9, 0.55), 0.24, 14),
             Tube("bollard", (x, edge - 0.9, 0.55), (x, edge - 0.9, 0.68), 0.34, 14)]
        lay.put("contents", b)
        lay.add("structure", [Box("rubber", x, edge + 0.2, -QUAY_HEIGHT - 0.6, 1.1, 0.4, QUAY_HEIGHT + 0.4)])
    if detailed:
        for y in (edge - 4.0, edge - 16.0):
            for xa, xb in ((-qx + 1, -kx - 0.5), (kx + 0.5, qx - 1)) if abs(y) < ky + 0.3 else ((-qx + 1, qx - 1),):
                lay.add("floor", [Box("rail_steel", (xa + xb) / 2, y, 0.0, xb - xa, 0.12, 0.005)])
        x0 = -kx - 10.0
        _container_stack(lay, rng, x0 - 12.0, -ky - 6.0, 2, 3, 3)
        _container_stack(lay, rng, x0 - 12.0, -ky - 6.0 - 3 * 2.6 - 4.0, 2, 2, 2)
        for x in (-qx + 12, qx - 12):
            lay.add("structure", [Tube("galvanized", (x, edge - 5.0, 0.0), (x, edge - 5.0, 18.0), 0.18, 10),
                                  Box("lamp_head", x, edge - 5.0, 18.0, 1.6, 0.8, 0.35)])
            lay.add("lights", [Box("light", x, edge - 5.0, 17.97, 1.4, 0.6, 0.03)])
        # a shed far behind (-y)
        lay.add("structure", [Box("wall_panel_out", -10.0, -land + 14.0, 0.0, 50.0, 18.0, 11.0)])
    else:
        _container_stack(lay, rng, -kx - 10.0 - CONTAINER_SIZE[0], -ky - 6.0, 1, 2, 2)


# ---- halls ---------------------------------------------------------------------

HALL_FLOORS = {"FACTORY": "floor_epoxy", "CNC": "floor_epoxy_green", "ASSEMBLY": "floor_concrete",
               "WAREHOUSE": "floor_concrete"}


def hall_size(kind: str, w: float, d: float, h: float) -> tuple[float, float, float]:
    kx, ky, kh = keepout_for(w, d, h)
    extra_x = {"FACTORY": 10.0, "CNC": 14.0, "ASSEMBLY": 14.0, "WAREHOUSE": 14.0}[kind]
    extra_y = {"FACTORY": 7.0, "CNC": 9.0, "ASSEMBLY": 9.0, "WAREHOUSE": 11.0}[kind]
    hx = max(18.0, kx + extra_x)
    hy = max(12.0, ky + extra_y)
    min_h = {"FACTORY": 7.0, "CNC": 7.5, "ASSEMBLY": 11.0, "WAREHOUSE": 10.0}[kind]
    return hx, hy, max(min_h, kh + 2.5)


def _hall(lay: Layout, kind: str, w, d, h, detailed, rng) -> None:
    kx, ky, kh = lay.keepout
    hx, hy, hh = hall_size(kind, w, d, h)
    lay.hall = (hx, hy, hh)
    lay.extent = max(hx, hy, hh) * 1.5
    lay.add("floor", [Box(HALL_FLOORS[kind], 0.0, 0.0, -0.2, 2 * hx, 2 * hy, 0.2)])

    # walls and roof: panels facing inwards (seen from outside they are see-through)
    def wall(x0, y0, x1, y1, z0, z1, mat, inset=0.0):
        nx, ny = -(y1 - y0), x1 - x0              # inward normal of the wall when walked anticlockwise
        n = math.hypot(nx, ny)
        ox, oy = nx / n * inset, ny / n * inset
        return Quad(mat, ((x0 + ox, y0 + oy, z0), (x1 + ox, y1 + oy, z0), (x1 + ox, y1 + oy, z1),
                          (x0 + ox, y0 + oy, z1)))

    corners = [(-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy)]
    shell = []
    for i in range(4):
        (x0, y0), (x1, y1) = corners[i], corners[(i + 1) % 4]
        shell.append(wall(x0, y0, x1, y1, 0.0, hh, "wall_panel"))
        shell.append(wall(x0, y0, x1, y1, 0.0, 1.4, "wall_dado", 0.01))
        if detailed and kind != "WAREHOUSE" and abs(x1 - x0) > 1:
            for xa in _steps(x0 + 3 * (1 if x1 > x0 else -1), x1 - 3 * (1 if x1 > x0 else -1), 6.0)[:-1]:
                xb = xa + 4.0 * (1 if x1 > x0 else -1)
                shell.append(wall(xa, y0, xb, y1, hh - 3.0, hh - 1.6, "window", 0.02))
    shell.append(Quad("roof", ((-hx, -hy, hh), (-hx, hy, hh), (hx, hy, hh), (hx, -hy, hh))))
    # roller door in the far end wall (-x)
    door_w, door_h = min(6.0, hy), min(5.5, hh - 1.5)
    shell.append(Quad("door", ((-hx + 0.03, door_w / 2 + 2, 0.0), (-hx + 0.03, -door_w / 2 + 2, 0.0),
                               (-hx + 0.03, -door_w / 2 + 2, door_h), (-hx + 0.03, door_w / 2 + 2, door_h))))
    lay.add("shell", shell)

    # columns along the long walls, trusses across
    xs = _steps(-hx, hx, 7.5 if kind != "WAREHOUSE" else 9.0)
    structure = []
    for x in xs:
        xc = max(-hx + 0.25, min(hx - 0.25, x))
        for y in (-hy + 0.25, hy - 0.25):
            structure.append(Box("steel_column", xc, y, 0.0, 0.36, 0.36, hh))
    lay.add("structure", structure)
    depth = 1.6 if detailed else 0.6
    bottom = hh - depth
    roof = []
    for x in xs[1:-1]:
        if detailed:
            roof += _truss(x, hy, hh - 0.12, bottom)
        else:
            roof.append(Beam("steel_column", (x, -hy, hh - 0.35), (x, hy, hh - 0.35), 0.22, 0.6))
    if detailed:
        for y in _steps(-hy + 2, hy - 2, 3.0):
            roof.append(Beam("steel_column", (-hx, y, hh - 0.08), (hx, y, hh - 0.08), 0.12, 0.16))
    lay.add("high", roof)

    # light lines under the roof (and skylight strips in detailed halls)
    lights = []
    z_light = max(kh + 0.3, (bottom if detailed else hh - 0.7) - 0.6)
    for y in _steps(-hy + 3.0, hy - 3.0, 5.0 if detailed else 7.0):
        lights.append(Box("light", 0.0, y, z_light, 2 * hx - 3.0, 0.12, 0.05))
        lights.append(Box("light_housing", 0.0, y, z_light + 0.05, 2 * hx - 3.0, 0.16, 0.08))
        for x in _steps(-hx + 2.0, hx - 2.0, 6.0):
            lights.append(Tube("galvanized", (x, y, z_light + 0.13), (x, y, hh - 0.1), 0.004, 4))
    if detailed:
        for y in (-hy / 2, hy / 2):
            for xa in xs[:-1]:
                xb = xa + (xs[1] - xs[0])
                lights.append(Quad("skylight", ((xa + 0.6, y - 1.0, hh - 0.02), (xa + 0.6, y + 1.0, hh - 0.02),
                                                (xb - 0.6, y + 1.0, hh - 0.02), (xb - 0.6, y - 1.0, hh - 0.02))))
    lay.add("lights", lights)

    # floor markings: the machine's area, and walkways along it
    marks = _rect_lines("line_yellow", kx, ky, 0.1)
    for y in (ky + 2.6, -(ky + 2.6)):
        if abs(y) < hy - 1.5:
            marks.append(_line("line_yellow", -hx + 1.0, y, hx - 1.0, y, 0.1))
    lay.add("floor", marks)

    {"FACTORY": _factory, "CNC": _cnc, "ASSEMBLY": _assembly, "WAREHOUSE": _warehouse}[kind](
        lay, hx, hy, hh, detailed, rng)
    if kind in ("ASSEMBLY", "CNC") or (detailed and kind == "WAREHOUSE"):
        _crane(lay, hx, hy, hh, detailed)


def _truss(x, hy, top, bottom) -> list:
    s = [Beam("steel_column", (x, -hy, top), (x, hy, top), 0.16, 0.2),
         Beam("steel_column", (x, -hy, bottom), (x, hy, bottom), 0.14, 0.16)]
    ys = _steps(-hy, hy, 2.0)
    for i, y in enumerate(ys):
        s.append(Beam("steel_column", (x, y, bottom), (x, y, top), 0.08, 0.08))
        if i + 1 < len(ys):
            a, b = (bottom, top) if i % 2 == 0 else (top, bottom)
            s.append(Beam("steel_column", (x, y, a), (x, ys[i + 1], b), 0.07, 0.07))
    return s


def _wall_slots(hx, hy, keepout, depth, length, gap, sides=("+y", "-y")) -> list[tuple[float, float, float]]:
    """Spots (x, y, rot) for things standing along the long walls, facing the hall, outside the keep-out."""
    spots = []
    for side in sides:
        sign = 1.0 if side == "+y" else -1.0
        y = sign * (hy - 0.6 - depth / 2)
        for x in _steps(-hx + 2.0 + length / 2, hx - 2.0 - length / 2, length + gap):
            if _free(x, y, length, depth, keepout, 0.3):
                spots.append((x, y, 0.0 if sign > 0 else math.pi))
    return spots


def machine_tool(rng: random.Random) -> list:
    """Generic CNC machining centre, front (door window) towards -y. About 3.4 × 2.6 × 2.8 m."""
    L = rng.choice((2.8, 3.2, 3.6))
    s = [Box("machine_dark", 0.0, 0.0, 0.0, L + 0.2, 2.4, 0.35),
         Box("machine_body", 0.0, 0.0, 0.35, L, 2.2, 2.25),
         Box("machine_body", -L / 4, 0.25, 2.6, L / 2, 1.4, 0.3),
         Box("glass_dark", -0.15, -1.105, 1.05, L * 0.45, 0.02, 0.95),
         Box("machine_blue", 0.0, -1.11, 2.3, L, 0.02, 0.18),
         Box("machine_dark", L / 2 + 0.25, -1.0, 1.1, 0.12, 0.5, 0.7),
         Tube("galvanized", (L / 2 + 0.25, -0.75, 0.35), (L / 2 + 0.25, -0.75, 1.1), 0.03, 8),
         Box("machine_dark", L / 2 - 0.4, 1.4, 0.0, 0.7, 0.6, 1.0)]
    return s


def _cnc(lay, hx, hy, hh, detailed, rng) -> None:
    spots = _wall_slots(hx, hy, lay.keepout, 3.0, 4.0, 2.0)
    if not detailed:
        spots = sorted(spots, key=lambda p: abs(p[0]))[:4]
    for x, y, rot in spots:
        lay.put("contents", place(machine_tool(rng), x, y, 0.0, rot))
    # tool cabinets and racks at the end walls
    for x in (-hx + 1.0, hx - 1.0):
        n = 6 if detailed else 3
        for i in range(n):
            y = -1.0 * n / 2 + i * 1.0
            lay.put("contents", [Box("cabinet_red" if detailed and i % 2 else "cabinet_grey", x, y, 0.0, 0.6, 0.9, 1.0)])
    if detailed:
        for x in (-hx + 3.5, hx - 3.5):
            for y in (-hy / 3, hy / 3):
                lay.put("contents", _shelf(x, y, 2.0, 0.6, 2.2, rng))


def _shelf(x, y, length, depth, height, rng, rot=math.pi / 2) -> list:
    s = []
    for dx in (-length / 2 + 0.03, length / 2 - 0.03):
        for dy in (-depth / 2 + 0.03, depth / 2 - 0.03):
            s.append(Box("rack_blue", dx, dy, 0.0, 0.05, 0.05, height))
    for z in (0.15, height * 0.4, height * 0.7, height - 0.03):
        s.append(Box("galvanized", 0.0, 0.0, z, length, depth, 0.025))
        if z < height - 0.1:
            for bx in (-length / 3, 0.0, length / 3):
                if rng.random() < 0.7:
                    s.append(Box("cardboard" if rng.random() < 0.5 else "bin_blue", bx, 0.0, z + 0.025,
                                 length / 3.5, depth * 0.8, rng.uniform(0.15, 0.4)))
    return place(s, x, y, 0.0, rot)


def _bench(rng) -> list:
    s = [Box("bench_top", 0.0, 0.0, 0.85, 2.0, 0.8, 0.05)]
    for x in (-0.95, 0.95):
        for y in (-0.35, 0.35):
            s.append(Box("machine_dark", x, y, 0.0, 0.05, 0.05, 0.85))
    s.append(Box("machine_dark", 0.0, 0.0, 0.15, 1.9, 0.7, 0.03))
    s.append(Box("machine_dark", 0.7, -0.3, 0.9, 0.18, 0.12, 0.15))       # vice
    s.append(Box("cabinet_red", -0.6, 0.0, 0.18, 0.55, 0.6, 0.6))         # drawers
    return s


def _factory(lay, hx, hy, hh, detailed, rng) -> None:
    spots = _wall_slots(hx, hy, lay.keepout, 0.7, 1.0, 0.2, sides=("+y",))
    take = spots[: (12 if detailed else 4)]
    for x, y, rot in take:
        lay.put("contents", place([Box("cabinet_grey", 0.0, 0.0, 0.0, 0.8, 0.6, 2.0),
                                   Box("machine_dark", 0.0, -0.31, 1.2, 0.25, 0.02, 0.35)], x, y, 0.0, rot))
    if detailed:
        for x, y, rot in _wall_slots(hx, hy, lay.keepout, 0.8, 2.0, 1.5, sides=("-y",))[:4]:
            lay.put("contents", place(_bench(rng), x, y, 0.0, rot))
        # cable trays along both long walls
        for y in (-hy + 0.5, hy - 0.5):
            lay.add("high", [Box("galvanized", 0.0, y, 4.0, 2 * hx - 1.0, 0.3, 0.06)])


def _assembly(lay, hx, hy, hh, detailed, rng) -> None:
    spots = _wall_slots(hx, hy, lay.keepout, 0.8, 2.0, 2.5)
    for x, y, rot in spots[: (10 if detailed else 3)]:
        lay.put("contents", place(_bench(rng), x, y, 0.0, rot))
    kx, ky, _ = lay.keepout
    # pallets with parts and (detailed) welded frames waiting for assembly, in front of the end wall
    x = -kx - 3.0
    if x - 1.0 > -hx + 1.0:
        for i, y in enumerate((-2.0, 0.0, 2.0) if detailed else (-1.0, 1.0)):
            lay.put("contents", place(pallet_load(rng), x, y))
    if detailed:
        for i, x in enumerate((kx + 4.0, kx + 9.0)):
            if x + 2 < hx - 1:
                lay.put("contents", _frame(x, 0.0, 3.2, 2.0, 1.4))
        for x, y, rot in _wall_slots(hx, hy, lay.keepout, 0.5, 0.6, 6.0)[:6]:
            lay.put("contents", place([Box("cabinet_red", 0.0, 0.0, 0.1, 0.6, 0.45, 0.9),
                                       Box("machine_dark", 0.0, 0.0, 0.0, 0.55, 0.4, 0.1)], x, y - 1.2 * (1 if y > 0 else -1),
                                      0.0, rot))


def _frame(x, y, L, W, H) -> list:
    """A welded steel frame in red primer (a machine base being built)."""
    s = []
    for z in (0.0, H - 0.16):
        for yy in (-W / 2, W / 2):
            s.append(Beam("primer", (-L / 2, yy, z + 0.08), (L / 2, yy, z + 0.08), 0.16, 0.16))
        for xx in (-L / 2, 0.0, L / 2):
            s.append(Beam("primer", (xx, -W / 2, z + 0.08), (xx, W / 2, z + 0.08), 0.16, 0.16))
    for xx in (-L / 2, L / 2):
        for yy in (-W / 2, W / 2):
            s.append(Beam("primer", (xx, yy, 0.16), (xx, yy, H - 0.16), 0.16, 0.16))
    return place(s, x, y, 0.0)


def _crane(lay, hx, hy, hh, detailed) -> None:
    kx, ky, kh = lay.keepout
    zr = hh - 1.6
    s = [Beam("crane_yellow", (-hx, y, zr), (hx, y, zr), 0.3, 0.5) for y in (-hy + 0.6, hy - 0.6)]
    xc = -kx - 3.5 if -kx - 3.5 > -hx + 2.0 else hx - 4.0
    s.append(Beam("crane_yellow", (xc, -hy + 0.6, zr + 0.65), (xc, hy - 0.6, zr + 0.65), 0.7, 0.9))
    for y in (-hy + 0.6, hy - 0.6):
        s.append(Box("crane_yellow", xc, y, zr + 0.25, 3.0, 0.5, 0.5))
    s.append(Box("machine_dark", xc, -hy / 3, zr - 0.4, 1.3, 1.1, 0.6))
    hook = max(kh * 0.5, zr - 4.5)
    s.append(Tube("galvanized", (xc, -hy / 3, hook + 0.5), (xc, -hy / 3, zr - 0.4), 0.02, 6))
    s.append(Box("crane_yellow", xc, -hy / 3, hook, 0.4, 0.25, 0.5))
    lay.add("high", s)


def _rack_row(lay, x0, x1, y, depth, levels, hh, fill, rng) -> None:
    """A row of pallet racks along x; bays that would stand in the machine's space or in the
    camera's view are left out (with their uprights)."""
    bay = 2.7
    n = max(1, int((x1 - x0) // bay))
    x0 = (x0 + x1) / 2 - n * bay / 2
    level_h = min(1.8, (hh - 1.5) / levels)
    height = level_h * levels
    fronts = (y - depth / 2 + 0.05, y + depth / 2 - 0.05)
    used = [False] * n
    for i in range(n):
        xm = x0 + (i + 0.5) * bay
        bay_shapes = []
        for k in range(1, levels + 1):
            for yy in fronts:
                bay_shapes.append(Box("rack_orange", xm, yy, k * level_h - 0.12, bay - 0.1, 0.05, 0.12))
        probe = Box("rack_blue", xm, y, 0.0, bay + 0.1, depth, height + 0.3)
        if overlaps_keepout(probe, lay.keepout) or blocks_view(probe, lay):
            continue
        used[i] = True
        for k in range(levels):
            for px in (xm - 0.65, xm + 0.65):
                if rng.random() < fill:
                    bay_shapes += place(pallet_load(rng, max(0.4, level_h - 0.35)), px, y, k * level_h, math.pi / 2)
        lay.add("contents", bay_shapes)
    for i in range(n + 1):
        if (i > 0 and used[i - 1]) or (i < n and used[i]):
            x = x0 + i * bay
            lay.add("contents", [Box("rack_blue", x, yy, 0.0, 0.09, 0.07, height + 0.3) for yy in fronts])


def _warehouse(lay, hx, hy, hh, detailed, rng) -> None:
    kx, ky, kh = lay.keepout
    depth = 1.1
    aisle = 3.4
    levels = 4 if detailed else 3
    fill = 0.8 if detailed else 0.55
    y = ky + 2.6 + 0.4 + depth / 2
    rows = 0
    while y + depth / 2 < hy - 0.8 and rows < (3 if detailed else 1):
        for sign in (1, -1):
            _rack_row(lay, -hx + 2.0, hx - 2.0, sign * y, depth, levels, hh, fill, rng)
            if detailed and y + depth * 1.5 + 0.1 < hy - 0.8:
                _rack_row(lay, -hx + 2.0, hx - 2.0, sign * (y + depth + 0.1), depth, levels, hh, fill, rng)
        y += (2 * depth + 0.1 if detailed else depth) + aisle
        rows += 1
    # pallets waiting on the floor near the machine
    for i, x in enumerate((kx + 1.5, kx + 3.0) if detailed else (kx + 1.5,)):
        if x + 0.6 < hx - 1:
            lay.put("contents", place(pallet_load(rng), -x, ky - 1.0, 0.0, math.pi / 2))
