"""Task 0080: the spooling test model (tools/make_test_spool.py -> tests/data/test_spool.step, a copy in
fresing_render/data/).

No Blender. The maker's numbers (``NUMBERS``, its docstring) are checked against plain maths, and against the STEP file
read the way the app reads it (the importer's cache: tree and meshes): names, IDs, colours, every part one solid; the
key parts' boxes; the two CAD ropes' middles – read from their meshes with core/flex_fit – where the numbers say,
with their diameter; the drum's spiral groove where GROOVE START says; the round axes the app picks joints from; the
maker makes what the file holds, and makes it the same way twice.
"""

import math
import os
import sys

import numpy as np
import pytest

pytest.importorskip("OCP")

HERE = os.path.dirname(__file__)
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import make_test_spool as maker  # noqa: E402
from fresing_render.core import clash as C  # noqa: E402
from fresing_render.core.flex_fit import tube_centreline  # noqa: E402
from fresing_render.importer import step_reader  # noqa: E402

FILE = os.path.join(HERE, "data", "test_spool.step")
N = maker.NUMBERS
W, K = N["winch"], N["carousel"]
GREY, YELLOW, STEEL = (0.3, 0.3, 0.3), (0.976, 0.659, 0.0), (0.55, 0.57, 0.6)
COLOURS = {"BASE FRAME": GREY, "BEARING BLOCK": GREY, "LEVEL WIND RAIL": GREY, "LEVEL WIND CARRIAGE": GREY,
           "CAROUSEL BASE": GREY, "SLEW POST": GREY, "CABLE CLAMP": GREY, "WINCH DRUM": YELLOW, "TURNTABLE": YELLOW,
           "INNER CORE": YELLOW, "RIM FENCE": YELLOW, "ARM": YELLOW, "SHEAVE PIN": STEEL, "FAIRLEAD SHEAVE": STEEL,
           "GUIDE PIN": STEEL, "GUIDE SHEAVE": STEEL, "WIRE ROPE": (0.13, 0.13, 0.14),
           "WIRE ON DRUM": (0.13, 0.13, 0.14), "POWER CABLE": (0.05, 0.05, 0.05), "CABLE COIL": (0.05, 0.05, 0.05),
           "WEIGHT": (0.9, 0.35, 0.05)}
# the key parts' boxes (mm), worked out from the brief's numbers by hand
BOXES = {
    "BASE FRAME": ((-400, -420, 0), (1100, 420, 300)),
    "BEARING BLOCK": ((-80, 270, 300), (80, 310, 540)),
    "WINCH DRUM": ((-300, -320, 150), (300, 320, 750)),
    "WIRE ON DRUM": ((-204.641, -200, 245.359), (204.641, 200, 654.641)),
    "LEVEL WIND RAIL": ((780, -300, 60), (820, 300, 100)),
    "LEVEL WIND CARRIAGE": ((750, -60, 80), (850, 60, 580)),
    "SHEAVE PIN": ((785, -50, 529.641), (815, 50, 559.641)),
    "FAIRLEAD SHEAVE": ((675, -20, 419.641), (925, 20, 669.641)),
    "WEIGHT": ((870, -80, 60), (930, 80, 200)),
    "WIRE ROPE": ((-204.641, -10, 200), (910, 10, 654.641)),
    "CAROUSEL BASE": ((2100, -900, 0), (3900, 900, 100)),
    "TURNTABLE": ((2000, -1000, 100), (4000, 1000, 140)),
    "INNER CORE": ((2700, -300, 140), (3300, 300, 520)),
    "RIM FENCE": ((2000, -1000, 140), (4000, 1000, 420)),
    "CABLE COIL": ((2140, -860, 140), (3860, 860, 300)),
    "SLEW POST": ((4200, -100, 0), (4400, 100, 1000)),
    "ARM": ((3540, -200, 390), (4400, 100, 1140)),
    "GUIDE PIN": ((3530, -15, 415), (3670, 15, 445)),
    "GUIDE SHEAVE": ((3575, -170, 260), (3625, 170, 600)),
    "CABLE CLAMP": ((3560, -190, 1000), (3640, -110, 1060)),
    "POWER CABLE": ((3000, -170, 260), (3620, 620, 1000)),
}


# ---------------------------------------------------------------------------------------------------------
# the file as the app reads it
# ---------------------------------------------------------------------------------------------------------

class Model:
    """A STEP file through the importer; everything here in the model's coordinates, in mm."""

    def __init__(self, path, folder, quality="normal"):
        self.info = step_reader.read_step(path, str(folder), quality)
        self.arrays = np.load(os.path.join(str(folder), "meshes.npz"))
        self.nodes = self.info["nodes"]
        self.world = []
        for n in self.nodes:
            m = np.eye(4) if n["matrix"] is None else np.array(n["matrix"], dtype=float)
            self.world.append(m if n["parent"] < 0 else self.world[n["parent"]] @ m)
        self.by_uid = {n["uid"]: i for i, n in enumerate(self.nodes)}
        self.parts = [i for i, n in enumerate(self.nodes) if n["kind"] == "part"]

    def mesh(self, i):
        """(corners (V, 3) in mm, triangles (T, 3)) of part i where it stands."""
        mid = self.nodes[i]["mesh"]
        v = self.arrays[f"p{mid}"].astype(np.float64)
        m = self.world[i]
        return (v @ m[:3, :3].T + m[:3, 3]) * 1000.0, self.arrays[f"t{mid}"].reshape(-1, 3).astype(np.int64)

    def part(self, name):
        return self.mesh(self.by_uid[maker.UID[name]])

    def axes(self, uid):
        """The round faces' axes the importer found on a part: [(point in mm, direction, radius in mm)]."""
        i = self.by_uid[uid]
        m = self.world[i]
        return [((m[:3, :3] @ (ox, oy, oz) + m[:3, 3]) * 1000.0, m[:3, :3] @ (dx, dy, dz), r * 1000.0)
                for ox, oy, oz, dx, dy, dz, r in self.info["meshes"][self.nodes[i]["mesh"]]["axes"]]


@pytest.fixture(scope="module")
def model(tmp_path_factory):
    return Model(FILE, tmp_path_factory.mktemp("spool"))


@pytest.fixture(scope="module")
def made():
    """The maker's parts, made in this process: [(name, uid, shape in the model's coordinates)]."""
    return maker.placed(maker.model())


def off_line(points, point, direction):
    """How far points lie from the line through ``point`` along ``direction``."""
    d = np.asarray(direction, dtype=float)
    d = d / np.linalg.norm(d)
    rel = np.asarray(points, dtype=float) - np.asarray(point, dtype=float)
    return np.linalg.norm(rel - np.outer(rel @ d, d), axis=1)


def has_axis(axes, point, direction, tol=0.01):
    d = np.asarray(direction, dtype=float)
    return any(abs(abs(float(a @ d) / np.linalg.norm(d)) - 1.0) < 1e-6 and off_line([p], point, d)[0] < tol
               for p, a, _r in axes)


# ---------------------------------------------------------------------------------------------------------
# the maker's numbers
# ---------------------------------------------------------------------------------------------------------

def test_the_shipped_model_is_the_test_data():
    with open(os.path.join(ROOT, "fresing_render", "data", "test_spool.step"), "rb") as a, open(FILE, "rb") as b:
        assert a.read() == b.read(), "copy tests/data/test_spool.step to fresing_render/data/"
    assert os.path.getsize(FILE) < 1024 * 1024


def test_the_spools_numbers():
    """The brief's numbers, and the ones worked out from them, by plain maths."""
    doc = maker.__doc__
    d = W["drum"]
    assert d["axis_point"] == (0.0, 0.0, 450.0) and d["axis_direction"] == (0.0, 1.0, 0.0)
    assert (d["d"], d["r1"], d["groove_bottom"], d["pitch"], d["flange_inner"]) == (20.0, 160.0, 150.0, 21.2,
                                                                                    (-200.0, 200.0))
    assert d["r1"] == d["groove_bottom"] + d["d"] / 2
    assert np.allclose(d["layer_radii"], [160.0 + k * 20.0 * math.cos(math.radians(30.0)) for k in range(3)], atol=1e-4)
    assert np.allclose(d["layer_radii"], [160.0, 177.3205, 194.641], atol=1e-4)
    assert abs(d["turns_per_layer"] - 380.0 / 21.2) < 1e-5 and abs(d["turns_layer3"] - 190.0 / 21.2) < 1e-5
    assert d["wire_outer_radii"] == (187.3205, 204.641)
    # the groove's start: the path laid back from the leave point (beta 0) with climbs of 90°
    back = 360.0 * (190.0 + 2.0 * 380.0) / 21.2 + 180.0
    assert abs(d["groove_start"] - (-back) % 360.0) < 1e-3 and "247.925" in doc
    r = W["rope"]
    assert np.allclose(r["start"], (-194.641, 0.0, 450.0), atol=1e-3)
    assert np.allclose(r["leave_point"], (0.0, 0.0, 644.641), atol=1e-3) and r["leave_direction"] == (1.0, 0.0, 0.0)
    assert np.allclose(r["end"], (900.0, 0.0, 200.0), atol=1e-3) and W["weight"]["top"] == 200.0
    assert abs(r["length"] - 1607.462) < 1e-3 and "1607.462" in doc
    f = W["fairlead"]
    assert f["axis_point"] == (800.0, 0.0, 544.641) and f["axis_direction"] == (0.0, 1.0, 0.0)
    assert (f["seat_radius"], f["surface_radius"], f["rim_radius"], f["width"]) == (100.0, 90.0, 125.0, 40.0)
    assert f["axis_point"][2] + f["seat_radius"] == r["leave_point"][2]           # its top at the rope's height
    s = K["spool"]
    assert s["axis_point"] == (3000.0, 0.0, 0.0) and s["axis_direction"] == (0.0, 0.0, 1.0)
    assert (s["d"], s["r_in"], s["r_out"], s["a_bot"], s["full_layers"], s["turns_per_layer"]) == (
        40.0, 340.0, 840.0, 140.0, 3, 12.5)
    assert s["top_layer_z"] == 140.0 + 3.5 * 40.0 == 280.0 and s["leave_radius"] == s["top_layer_from"] == 600.0
    c = K["cable"]
    assert np.allclose(c["start"], (3000.0, 600.0, 280.0), atol=1e-3)
    assert np.allclose(c["leave_point"], (3600.0, 0.0, 280.0), atol=1e-3) and c["leave_direction"] == (0.0, -1.0, 0.0)
    assert np.allclose(c["end"], (3600.0, -150.0, 1000.0), atol=1e-3)
    assert abs(c["length"] - (600.0 + 150.0) * math.pi / 2 - 570.0) < 1e-3 and "1748.097" in doc
    g = K["guide"]
    assert g["axis_point"] == (3600.0, 0.0, 430.0) and g["axis_direction"] == (1.0, 0.0, 0.0)
    assert (g["seat_radius"], g["surface_radius"], g["rim_radius"], g["width"]) == (150.0, 130.0, 170.0, 50.0)
    assert g["axis_point"][2] - g["seat_radius"] == c["leave_point"][2]           # its bottom on the top layer
    a = K["arm"]
    assert a["pivot"] == (4300.0, 0.0, 0.0) and a["axis_direction"] == (0.0, 0.0, 1.0) and a["reach"] == 700.0


def test_the_wound_estimates():
    """Worked out here another way: helix turns per drum layer; an Archimedean spiral's length in closed form."""
    def helix(r, turns):
        return turns * math.sqrt((2.0 * math.pi * r) ** 2 + 21.2 ** 2)
    radii = W["drum"]["layer_radii"]
    drum = [helix(radii[0], 380 / 21.2), helix(radii[1], 380 / 21.2), helix(radii[2], 190 / 21.2)]
    assert np.allclose(W["wound_estimate"]["layers"], drum, atol=1e-2)
    assert abs(W["wound_estimate"]["total"] - sum(drum)) < 0.05 and abs(sum(drum) - 48959.901) < 0.05

    def spiral(r0, r1, turns):                  # r = a + b phi: the length from r0 to r1
        b = abs(r1 - r0) / (2.0 * math.pi * turns)

        def f(r):
            q = math.hypot(r, b)
            return (r * q + b * b * math.log(r + q)) / (2.0 * b)
        return abs(f(r1) - f(r0))
    car = [spiral(340.0, 840.0, 12.5)] * 3 + [spiral(840.0, 600.0, 6.0)]
    assert np.allclose(K["wound_estimate"]["layers"], car, atol=1e-2)
    assert abs(K["wound_estimate"]["total"] - sum(car)) < 0.05 and abs(sum(car) - 166168.543) < 0.05
    assert abs(car[0] - 2.0 * math.pi * 12.5 * 590.0) < 5.0                     # ~ turns x 2 pi x the mean radius
    doc = maker.__doc__
    assert "48959.901" in doc and "166168.543" in doc


def test_the_ropes_are_arcs_and_lines_without_a_kink():
    """Each CAD rope's route: every piece starts where the one before ends, going the same way; the arcs lie on their
    spools and sheaves at the numbers' radii; the centreline points are at most ``step`` apart."""
    on = {"WIRE ON DRUM": (W["drum"]["axis_point"], W["drum"]["axis_direction"], W["drum"]["layer_radii"][2]),
          "FAIRLEAD SHEAVE": (W["fairlead"]["axis_point"], W["fairlead"]["axis_direction"], 100.0),
          "CABLE COIL": ((3000.0, 0.0, 280.0), K["spool"]["axis_direction"], 600.0),
          "GUIDE SHEAVE": (K["guide"]["axis_point"], K["guide"]["axis_direction"], 150.0)}
    for which, numbers, kinds in (("wire", W["rope"], ["arc", "line", "arc", "line"]),
                                  ("cable", K["cable"], ["arc", "arc", "line"])):
        route = maker.Route(which)
        assert [s.kind for s in route.segments] == kinds == [s["kind"] for s in numbers["segments"]]
        for a, b in zip(route.segments[:-1], route.segments[1:]):
            assert np.linalg.norm(a.end - b.start) < 1e-9 and np.linalg.norm(a.end_tangent - b.start_tangent) < 1e-9
        for seg in route.segments:
            if seg.kind != "arc":
                continue
            centre, axis, radius = on[seg.name]
            pts = np.array([seg.point(s) for s in np.linspace(0.0, seg.length, 9)])
            assert np.abs(off_line(pts, centre, axis) - radius).max() < 1e-4, seg.name      # (numbers: 4 decimals)
            assert np.abs((pts - centre) @ np.asarray(axis)).max() < 1e-9, seg.name        # in one plane
            assert abs(seg.length - radius * math.pi / 2) < 1e-3                          # all quarter turns
        assert np.allclose(route.segments[0].end, numbers["leave_point"], atol=1e-3)
        pts = maker.centreline(which, 0.5)
        steps = np.linalg.norm(np.diff(pts, axis=0), axis=1)
        assert steps.max() <= 0.5 + 1e-9 and abs(steps.sum() - route.length) < 0.01
        assert np.allclose(pts[0], numbers["start"], atol=1e-3) and np.allclose(pts[-1], numbers["end"], atol=1e-3)
    assert np.all(maker.centreline("wire", 2.0)[:, 1] == 0.0)                     # the wire: in the plane y = 0


# ---------------------------------------------------------------------------------------------------------
# the file through the importer
# ---------------------------------------------------------------------------------------------------------

def _solids_in(path):
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPControl import STEPControl_Reader
    reader = STEPControl_Reader()
    assert reader.ReadFile(path) == IFSelect_RetDone
    reader.TransferRoots()
    return maker.G.solids(reader.OneShape())


def test_parts_names_colours_and_assemblies(model):
    nodes = model.nodes
    assert sorted(n["name"] for n in nodes) == sorted(maker.PARTS + maker.ASSEMBLIES)
    assert [nodes[i]["name"] for i in model.parts] == maker.PARTS
    assert model.info["stats"]["placed_parts"] == 22 and model.info["stats"]["unique_parts"] == 21
    assert _solids_in(FILE) == 22, "every part is one solid"
    for i in model.parts:
        n = nodes[i]
        assert n["color"] is not None, (n["name"], "has no colour (a part of several solids loses it)")
        assert np.allclose(n["color"], COLOURS[n["name"]], atol=2e-3), n["name"]
    blocks = [i for i in model.parts if nodes[i]["name"] == "BEARING BLOCK"]
    assert len(blocks) == 2 and nodes[blocks[0]]["mesh"] == nodes[blocks[1]]["mesh"]
    for key, uid in maker.UID.items():
        assert uid in model.by_uid, key
    parent = {n["name"]: nodes[n["parent"]]["name"] for n in nodes if n["parent"] >= 0}
    groups = {"DRUM.ASM": {"WINCH DRUM", "WIRE ON DRUM"},
              "LEVEL WIND.ASM": {"LEVEL WIND CARRIAGE", "SHEAVE PIN", "FAIRLEAD SHEAVE"},
              "CAROUSEL.ASM": {"TURNTABLE", "INNER CORE", "RIM FENCE", "CABLE COIL"},
              "ARM.ASM": {"ARM", "GUIDE PIN", "GUIDE SHEAVE", "CABLE CLAMP"}}
    for asm, names in groups.items():
        assert {k for k, v in parent.items() if v == asm} == names, asm
        assert parent[asm] == "TEST.SPOOL"
    # the sub-assemblies' places: origins on their axes; DRUM.ASM's own z along the drum axis (+Y)
    world = {asm: model.world[model.by_uid[maker.UID[asm]]] for asm in groups}
    assert np.allclose(world["DRUM.ASM"][:3, 3] * 1000.0, W["drum"]["axis_point"], atol=1e-6)
    assert np.allclose(world["DRUM.ASM"][:3, 2], W["drum"]["axis_direction"], atol=1e-9)
    assert np.allclose(world["DRUM.ASM"][:3, 0], (0.0, 0.0, 1.0), atol=1e-9)
    assert np.allclose(world["CAROUSEL.ASM"][:3, 3] * 1000.0, K["spool"]["axis_point"], atol=1e-6)
    assert np.allclose(world["ARM.ASM"][:3, 3] * 1000.0, K["arm"]["pivot"], atol=1e-6)
    assert np.allclose(world["LEVEL WIND.ASM"][:3, 3] * 1000.0, (800.0, 0.0, 0.0), atol=1e-6)
    for asm in ("CAROUSEL.ASM", "ARM.ASM", "LEVEL WIND.ASM"):
        assert np.allclose(world[asm][:3, :3], np.eye(3), atol=1e-12), asm


def test_the_key_parts_boxes(made, model):
    """Each part's exact box (OpenCascade, from the maker) within 0.1 mm of the numbers; the file's meshes within
    0.6 mm of it (the facets of round faces lie a little inside)."""
    done = set()
    for (name, uid, shape), i in zip(made, model.parts):
        lo, hi = maker.bounds(shape)
        want = BOXES[name]
        if name == "BEARING BLOCK" and uid.endswith("#2"):
            want = ((-80, -310, 300), (80, -270, 540))
        assert np.allclose(lo, want[0], atol=0.1) and np.allclose(hi, want[1], atol=0.1), (uid, lo, hi)
        v, _t = model.mesh(i)
        assert np.allclose(v.min(axis=0), lo, atol=0.6) and np.allclose(v.max(axis=0), hi, atol=0.6), uid
        done.add(name)
    assert done == set(BOXES)


def test_the_ropes_read_from_their_meshes(model):
    """Each CAD rope's middle from its mesh (core/flex_fit, as the app reads a cable): its diameter, its length, its
    ends where the numbers say, along the maker's arcs and lines."""
    for which, numbers in (("wire", W["rope"]), ("cable", K["cable"])):
        i = model.by_uid[numbers["uid"]]
        mid = model.nodes[i]["mesh"]
        tube = tube_centreline(model.arrays[f"p{mid}"], model.arrays[f"t{mid}"].reshape(-1, 3), 1025)
        assert tube.ok, (which, tube.problem)
        m = model.world[i]
        pts = (tube.points @ m[:3, :3].T + m[:3, 3]) * 1000.0
        assert abs(tube.radius * 1000.0 - numbers["d"] / 2.0) < 0.1, (which, tube.radius)
        assert abs(tube.length * 1000.0 / numbers["length"] - 1.0) < 0.005, which
        if np.linalg.norm(pts[0] - numbers["start"]) > np.linalg.norm(pts[-1] - numbers["start"]):
            pts = pts[::-1]
        assert np.linalg.norm(pts[0] - numbers["start"]) < 1.0, which
        assert np.linalg.norm(pts[-1] - numbers["end"]) < 1.0, which
        exact = maker.centreline(which, 0.5)
        off = np.array([np.sqrt(((exact - p) ** 2).sum(axis=1).min()) for p in pts])
        assert off.max() < 1.0 and off.mean() < 0.3, (which, off.max(), off.mean())
        # the skin: every corner of the mesh is the rope's radius from the exact middle (facets lie on it)
        v, _t = model.mesh(i)
        near = np.array([np.sqrt(((exact - p) ** 2).sum(axis=1).min()) for p in v[::7]])
        assert np.abs(near - numbers["d"] / 2.0).max() < 0.5, which


def test_the_drum_groove_and_the_wound_solids(model):
    """From the meshes: the barrel between the flanges lies between the groove's bottom (r 150) and the lands
    (r 157); the groove's bottom follows the helix GROOVE START gives; the wire on the drum and the coil fill the
    radii and heights the numbers give."""
    d = W["drum"]
    v, _t = model.part("WINCH DRUM")
    r = off_line(v, d["axis_point"], d["axis_direction"])
    inside = np.abs(v[:, 1]) < 199.0
    assert inside.sum() > 1000
    assert r[inside].min() > 150.0 - 0.05 and abs(r[inside].max() - 157.0) < 1e-3
    assert abs(r.max() - 300.0) < 1e-3 and abs(np.abs(v[:, 1]).max() - 320.0) < 1e-3
    bottom = inside & (r < 150.5)                       # the groove's bottom: within 3.2 mm of its middle line
    assert bottom.sum() > 200
    beta = np.degrees(np.arctan2(v[bottom, 0], v[bottom, 2] - d["axis_point"][2])) % 360.0
    y = -190.0 + d["pitch"] * ((beta - d["groove_start"]) % 360.0) / 360.0           # on the helix, one turn ...
    dy = (v[bottom, 1] - y + d["pitch"] / 2.0) % d["pitch"] - d["pitch"] / 2.0       # ... or a whole number more
    # (the mesh's corners in the groove lie on its round section, either side of the bottom line: about as many each
    # side; a groove 10° of turn off would be 0.6 mm off)
    assert np.abs(dy).max() < 3.25 and abs(dy.mean()) < 0.3, (np.abs(dy).max(), dy.mean())
    # the wire on the drum: r 150 .. 187.321 over the whole width, to 204.641 from y -200 to -10
    v, _t = model.part("WIRE ON DRUM")
    r = off_line(v, d["axis_point"], d["axis_direction"])
    assert abs(r.min() - 150.0) < 1e-3 and abs(r.max() - 204.641) < 1e-3
    assert abs(v[:, 1].min() + 200.0) < 1e-3 and abs(v[:, 1].max() - 200.0) < 1e-3
    assert abs(v[r > 190.0, 1].max() - d["wire_layer3_to"]) < 1e-3 and d["wire_layer3_to"] == -10.0
    assert set(np.round(r[v[:, 1] > -9.0], 3)) <= {150.0, 187.321}
    # the coil: r 320 .. 860, z 140 .. 300; the top layer (z 260 .. 300) from r 580 out
    s = K["spool"]
    v, _t = model.part("CABLE COIL")
    r = off_line(v, s["axis_point"], s["axis_direction"])
    assert abs(r.min() - 320.0) < 1e-3 and abs(r.max() - 860.0) < 1e-3
    assert abs(v[:, 2].min() - 140.0) < 1e-3 and abs(v[:, 2].max() - 300.0) < 1e-3
    top = v[:, 2] > 260.0 + 1e-3
    assert abs(r[top].min() - 580.0) < 1e-3
    away = top & (v[:, 1] < -200.0)                         # away from the cable and the guide sheave
    assert abs(r[away].min() - 580.0) < 0.5
    # where the CAD cable lies (from +X to +Y, r 580 .. 620) the top layer is cut away
    rel = v - s["axis_point"]
    around = np.degrees(np.arctan2(rel[:, 1], rel[:, 0]))
    quarter = top & (around > 1.0) & (around < 89.0)
    assert quarter.sum() > 10 and r[quarter].min() > 620.0 - 1e-3

def test_the_importer_finds_the_round_axes(model):
    """The axes of round faces in the cache: what the app's joint and spool picking use."""
    d, f, s, g, a = W["drum"], W["fairlead"], K["spool"], K["guide"], K["arm"]
    for name in ("WINCH DRUM", "WIRE ON DRUM", "BEARING BLOCK"):
        assert has_axis(model.axes(maker.UID[name]), d["axis_point"], d["axis_direction"]), name
    assert has_axis(model.axes(maker.UID["BEARING BLOCK 2"]), d["axis_point"], d["axis_direction"])
    assert len(model.axes(maker.UID["WINCH DRUM"])) == 1
    for name in ("FAIRLEAD SHEAVE", "SHEAVE PIN", "LEVEL WIND CARRIAGE"):
        assert has_axis(model.axes(maker.UID[name]), f["axis_point"], f["axis_direction"]), name
    for name in ("CAROUSEL BASE", "TURNTABLE", "INNER CORE", "RIM FENCE", "CABLE COIL"):
        assert has_axis(model.axes(maker.UID[name]), s["axis_point"], s["axis_direction"]), name
    for name in ("GUIDE SHEAVE", "GUIDE PIN", "ARM"):
        assert has_axis(model.axes(maker.UID[name]), g["axis_point"], g["axis_direction"]), name
    for name in ("SLEW POST", "ARM"):
        assert has_axis(model.axes(maker.UID[name]), a["pivot"], a["axis_direction"]), name
    for name in ("LEVEL WIND RAIL", "WEIGHT", "CABLE CLAMP"):
        assert model.axes(maker.UID[name]) == [], name


# ---------------------------------------------------------------------------------------------------------
# the maker against the shipped file, and against itself
# ---------------------------------------------------------------------------------------------------------

def test_the_maker_makes_what_the_file_holds_and_the_same_twice(made, model):
    """Someone changes the maker and forgets the file: this fails. Every part one solid, its volume and its box the
    same as the file's; made a second time, every part's volume and box the same to 1e-6."""
    assert [name for name, _uid, _shape in made] == maker.PARTS
    for (name, uid, shape), i in zip(made, model.parts):
        assert model.nodes[i]["uid"] == uid
        assert maker.G.solids(shape) == 1, name
        v, t = model.mesh(i)
        assert abs(C.signed_volume(v, t) / maker.G.volume(shape) - 1.0) < 0.01, name
    again = maker.placed(maker.model())
    for (name, _u, a), (_n, _u2, b) in zip(made, again):
        va, vb = maker.G.volume(a), maker.G.volume(b)
        assert abs(va - vb) < 1e-6 * va, name
        (la, ha), (lb, hb) = maker.bounds(a), maker.bounds(b)
        assert np.allclose(la, lb, atol=1e-6) and np.allclose(ha, hb, atol=1e-6), name
    rope = next(s for n, _u, s in made if n == "WIRE ROPE")
    cable = next(s for n, _u, s in made if n == "POWER CABLE")
    assert abs(maker.G.volume(rope) / (math.pi * 10.0 ** 2 * W["rope"]["length"]) - 1.0) < 1e-5
    assert abs(maker.G.volume(cable) / (math.pi * 20.0 ** 2 * K["cable"]["length"]) - 1.0) < 1e-5
