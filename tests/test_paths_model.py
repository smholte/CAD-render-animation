"""Task 0078: the cable-path test model (tools/make_test_paths.py -> tests/data/test_paths_a.step / _b.step).

No Blender. The maker's numbers (``NUMBERS``, its docstring) are checked against its own maths, and against the
STEP files read the way the app reads them (the importer's cache: tree and meshes): the rope's middle – read from
its mesh with core/flex_fit – lies on the drum, in both sheaves' grooves, on both V rollers and in the chute's
trough; the round parts' axes are found where the docstring says; no part is drawn through another; revision B
is revision A with one more part and another order.
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

import make_test_paths as maker  # noqa: E402
from fresing_render.core import clash as C  # noqa: E402
from fresing_render.core.flex_fit import tube_centreline  # noqa: E402
from fresing_render.importer import step_reader  # noqa: E402

A = os.path.join(HERE, "data", "test_paths_a.step")
B = os.path.join(HERE, "data", "test_paths_b.step")
N = maker.NUMBERS
GREY, YELLOW, STEEL, CHROME = (0.3, 0.3, 0.3), (0.976, 0.659, 0.0), (0.55, 0.57, 0.6), (0.85, 0.86, 0.88)
COLOURS = {"BASE FRAME": GREY, "BEARING BLOCK": GREY, "CRADLE STAND": GREY, "CHUTE STAND": GREY, "A-FRAME": YELLOW,
           "WINCH DRUM": STEEL, "SHEAVE 1": STEEL, "SHEAVE 2": STEEL, "V ROLLER": STEEL, "CHUTE": STEEL,
           "HINGE PIN": CHROME, "SHEAVE PIN 1": CHROME, "SHEAVE PIN 2": CHROME, "WIRE ROPE": (0.13, 0.13, 0.14),
           "GUARD": (0.9, 0.35, 0.05)}
Y = np.array([0.0, 1.0, 0.0])


# ---------------------------------------------------------------------------------------------------------
# the files as the app reads them
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

    def named(self, name):
        return [i for i in self.parts if self.nodes[i]["name"] == name]

    def mesh(self, i):
        """(corners (V, 3) in mm, triangles (T, 3)) of part i where it stands."""
        mid = self.nodes[i]["mesh"]
        v = self.arrays[f"p{mid}"].astype(np.float64)
        m = self.world[i]
        return (v @ m[:3, :3].T + m[:3, 3]) * 1000.0, self.arrays[f"t{mid}"].reshape(-1, 3).astype(np.int64)

    def axes(self, i):
        """The round faces' axes the importer found on part i: [(point in mm, direction, radius in mm)]."""
        m = self.world[i]
        out = []
        for ox, oy, oz, dx, dy, dz, r in self.info["meshes"][self.nodes[i]["mesh"]]["axes"]:
            out.append(((m[:3, :3] @ (ox, oy, oz) + m[:3, 3]) * 1000.0, m[:3, :3] @ (dx, dy, dz), r * 1000.0))
        return out


@pytest.fixture(scope="module")
def model_a(tmp_path_factory):
    return Model(A, tmp_path_factory.mktemp("paths_a"))


@pytest.fixture(scope="module")
def model_b(tmp_path_factory):
    return Model(B, tmp_path_factory.mktemp("paths_b"))


@pytest.fixture(scope="module")
def rope(model_a):
    """The rope's middle read from its mesh: (the Tube, its points in the model's coordinates in mm)."""
    i = model_a.by_uid[N["rope"]["uid"]]
    mid = model_a.nodes[i]["mesh"]
    tube = tube_centreline(model_a.arrays[f"p{mid}"], model_a.arrays[f"t{mid}"].reshape(-1, 3), 2049)
    assert tube.ok, tube.problem
    m = model_a.world[i]
    return tube, (tube.points @ m[:3, :3].T + m[:3, 3]) * 1000.0


def off_line(points, point, direction):
    """How far points lie from the line through ``point`` along ``direction``."""
    d = np.asarray(direction, dtype=float)
    d = d / np.linalg.norm(d)
    rel = np.asarray(points, dtype=float) - np.asarray(point, dtype=float)
    return np.linalg.norm(rel - np.outer(rel @ d, d), axis=1)


def has_axis(axes, point, direction, tol=0.01):
    """Whether one of a part's axes is the line through ``point`` along ``direction`` (mm)."""
    d = np.asarray(direction, dtype=float)
    for p, a, _r in axes:
        if abs(abs(float(a @ d) / np.linalg.norm(d)) - 1.0) < 1e-6 and off_line([p], point, d)[0] < tol:
            return True
    return False


def angle(a, b):
    c = float(np.dot(a, b)) / float(np.linalg.norm(a) * np.linalg.norm(b))
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))


# ---------------------------------------------------------------------------------------------------------
# the maker's numbers
# ---------------------------------------------------------------------------------------------------------

def test_the_shipped_models_are_the_test_data():
    for name in ("test_paths_a.step",):               # revision B is for the model-update test only: not shipped
        with open(os.path.join(ROOT, "fresing_render", "data", name), "rb") as a, \
                open(os.path.join(HERE, "data", name), "rb") as b:
            assert a.read() == b.read(), f"{name}: copy tests/data/{name} to fresing_render/data/"
        assert os.path.getsize(os.path.join(HERE, "data", name)) < 400 * 1024


def test_the_rope_is_lines_and_arcs_without_a_kink():
    """The route's own maths: every piece starts where the one before ends, going the same way; every arc lies on
    its wheel at the seat radius (surface + the rope's radius) on the side the numbers give."""
    route = maker.Route()
    assert [s.kind for s in route.segments] == ["arc", "line"] * 4
    assert [a.name for a in route.contacts] == list(N["contacts"]) == ["WINCH DRUM", "SHEAVE 1", "SHEAVE 2", "CHUTE"]
    for a, b in zip(route.segments[:-1], route.segments[1:]):
        assert np.linalg.norm(a.end - b.start) < 1e-9
        assert angle(a.end_tangent, b.start_tangent) < 1e-5
    assert abs(sum(s.length for s in route.segments) - route.length) < 1e-9
    assert abs(sum(s["length"] for s in N["rope"]["segments"]) - N["rope"]["length"]) < 1e-3
    for arc in route.contacts:
        c = N["contacts"][arc.name]
        assert c["seat_radius"] == c["surface_radius"] + N["rope_radius"] == arc.radius
        assert c["axis_direction"] == (0.0, 1.0, 0.0)
        assert abs(arc.length - arc.radius * math.radians(c["wrap"])) < 1e-3
        for s in np.linspace(0.0, arc.length, 7):
            p, t = arc.point(s), arc.tangent(s)
            assert abs(np.linalg.norm(p - arc.centre) - arc.radius) < 1e-9
            rel = np.array([p[0] - arc.centre[0], 0.0, p[1] - arc.centre[1]])
            side = np.sign(np.cross(rel, [t[0], 0.0, t[1]]) @ Y)             # the brief's definition of a side
            assert side == c["side"] == arc.side
        assert np.allclose(c["tangent_in"], (arc.start[0], 0.0, arc.start[1]), atol=1e-3)
        assert np.allclose(c["tangent_out"], (arc.end[0], 0.0, arc.end[1]), atol=1e-3)
    assert [N["contacts"][k]["side"] for k in N["contacts"]] == [-1, 1, -1, 1]
    assert [N["contacts"][k]["turns"] for k in N["contacts"]] == [True, True, True, False]
    pts = maker.centreline(0.0, 0.5)
    assert np.all(pts[:, 1] == 0.0)
    steps = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    assert steps.max() <= 0.5 + 1e-9 and abs(steps.sum() - route.length) < 0.01


def test_the_numbers_of_the_docstring():
    """The numbers other tests and the app's set-up take from the maker's docstring."""
    doc = maker.__doc__
    r = N["rope"]
    assert N["rope_radius"] == 12.0 and N["lean"] == 20.0 and N["luff_range"] == (-15.0, 15.0)
    assert N["luff_axis"]["point"] == (1500.0, 0.0, 730.0) and N["luff_axis"]["direction"] == (0.0, 1.0, 0.0)
    assert np.allclose(r["start"], (238.0, 0.0, 450.0), atol=1e-3)
    assert np.allclose(r["end"], (3481.020, 0.0, 52.650), atol=1e-3)
    assert abs(r["length"] - 7022.212) < 1e-3 and "7022.212" in doc
    want = {"WINCH DRUM": ((450.0, 0.0, 450.0), 200.0, 212.0, 147.111),
            "SHEAVE 1": ((1910.424, 0.0, 1857.631), 238.0, 250.0, 191.749),
            "SHEAVE 2": ((1500.0, 0.0, 830.0), 168.0, 180.0, 134.638),
            "CHUTE": ((2700.0, 0.0, 50.0), 588.0, 600.0, 50.0)}
    for name, (axis, surface, seat, wrap) in want.items():
        c = N["contacts"][name]
        assert np.allclose(c["axis_point"], axis, atol=1e-3), name
        assert (c["surface_radius"], c["seat_radius"]) == (surface, seat)
        assert abs(c["wrap"] - wrap) < 1e-3 and (name == "CHUTE" or f"{wrap:.3f}" in doc)
    # a quarter turn and more on the drum, the two sheaves on different sides, the run through the cradle level
    assert N["contacts"]["WINCH DRUM"]["wrap"] >= 90.0
    assert N["contacts"]["SHEAVE 1"]["side"] == -N["contacts"]["SHEAVE 2"]["side"] == 1
    assert N["contacts"]["SHEAVE 2"]["tangent_out"][2] == N["contacts"]["CHUTE"]["tangent_in"][2] == N["level_run_z"]
    assert N["level_run_z"] == 650.0
    for k, (axis, direction, touch) in enumerate((((2400.0, 46.281, 594.845), (0.0, 0.766044, 0.642788),
                                                   (2400.0, 7.713, 640.807)),
                                                  ((2540.0, -46.281, 594.845), (0.0, -0.766044, 0.642788),
                                                   (2540.0, -7.713, 640.807)))):
        roller = N["rollers"][k]
        assert np.allclose(roller["axis_point"], axis, atol=1e-3)
        assert np.allclose(roller["axis_direction"], direction, atol=1e-6)
        assert np.allclose(roller["touch"], touch, atol=1e-3) and roller["gap"] == 0.0
        assert (roller["surface_radius"], roller["seat_radius"]) == (60.0, 72.0)
        d = np.array(roller["axis_direction"])
        assert abs(np.linalg.norm(d) - 1.0) < 1e-6 and d[0] == 0.0                # square to the rope (along X)
        assert abs(math.degrees(math.asin(d[2])) - 40.0) < 1e-4                   # 40° from the horizontal
        # the touch point is on the roller's skin and on the rope's; the rope's middle is the seat radius away
        assert abs(off_line([roller["touch"]], roller["axis_point"], d)[0] - 60.0) < 1e-3
        assert abs(np.linalg.norm(np.array(roller["touch"]) - roller["rope_middle"]) - 12.0) < 1e-3
        assert abs(off_line([roller["rope_middle"]], roller["axis_point"], d)[0] - 72.0) < 1e-3
        assert abs((np.array(roller["rope_middle"]) - roller["axis_point"]) @ d) < 1e-3


def test_the_luff_range():
    """-15° .. +15°: the rope's path stays possible (every run and wrap there), the sheaves ride on the frame,
    the run through the cradle stays on the V rollers within 0.7 mm; the numbers of the docstring's table."""
    hinge = np.array(N["luff_axis"]["point"])
    for luff in np.linspace(-15.0, 15.0, 13):
        n = maker.numbers_at(float(luff))
        route = maker.Route(float(luff))
        for a, b in zip(route.segments[:-1], route.segments[1:]):
            assert np.linalg.norm(a.end - b.start) < 1e-9 and angle(a.end_tangent, b.start_tangent) < 1e-5
        assert all(s.length > 300.0 for s in route.segments)
        assert all(40.0 < c["wrap"] < 210.0 for c in n["contacts"].values())
        assert n["contacts"]["WINCH DRUM"]["wrap"] >= 90.0
        turn = maker.RotY(float(luff), hinge)                    # + about +Y: the top goes towards +X
        for name in ("SHEAVE 1", "SHEAVE 2"):
            drawn = np.r_[N["contacts"][name]["axis_point"], 1.0]
            assert np.allclose((turn @ drawn)[:3], n["contacts"][name]["axis_point"], atol=1e-3)
        for name in ("WINCH DRUM", "CHUTE"):
            assert n["contacts"][name]["axis_point"] == N["contacts"][name]["axis_point"]
        assert n["rope"]["start"] == N["rope"]["start"] and n["rope"]["end"] == N["rope"]["end"]
        gaps = [r["gap"] for r in n["rollers"]]
        assert -0.7 < min(gaps) and max(gaps) <= 1e-9, (luff, gaps)
        # the run between the two sheaves rides on the frame: always as long
        assert abs(n["rope"]["segments"][3]["length"] - N["rope"]["segments"][3]["length"]) < 1e-3
    for luff, length, wraps, top in ((-15.0, 6849.652, (156.232, 185.870, 119.798, 50.159), (1604.587, 1925.434)),
                                     (15.0, 7162.170, (138.417, 198.055, 149.805, 50.166), (2188.292, 1712.982))):
        n = maker.numbers_at(luff)
        assert abs(n["rope"]["length"] - length) < 1e-3
        assert np.allclose([c["wrap"] for c in n["contacts"].values()], wraps, atol=1e-3)
        assert np.allclose(n["contacts"]["SHEAVE 1"]["axis_point"], (top[0], 0.0, top[1]), atol=1e-3)
    assert maker.numbers_at(15.0)["contacts"]["SHEAVE 1"]["axis_point"][0] > N["contacts"]["SHEAVE 1"]["axis_point"][0]


# ---------------------------------------------------------------------------------------------------------
# revision A through the importer
# ---------------------------------------------------------------------------------------------------------

def _solids_in(path):
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPControl import STEPControl_Reader
    reader = STEPControl_Reader()
    assert reader.ReadFile(path) == IFSelect_RetDone
    reader.TransferRoots()
    return maker.solids(reader.OneShape())


def test_parts_names_and_colours(model_a):
    nodes = model_a.nodes
    assert sorted(n["name"] for n in nodes) == sorted(maker.PARTS + maker.ASSEMBLIES)
    assert sorted(n["name"] for n in nodes if n["kind"] == "part") == sorted(maker.PARTS)
    assert model_a.info["stats"]["placed_parts"] == 17 and model_a.info["stats"]["unique_parts"] == 14
    assert _solids_in(A) == 17, "every part is one solid"
    for i in model_a.parts:
        n = nodes[i]
        assert n["color"] is not None, (n["name"], "has no colour (a part of several solids loses it)")
        assert np.allclose(n["color"], COLOURS[n["name"]], atol=2e-3), n["name"]
    for name in ("V ROLLER", "BEARING BLOCK", "HINGE PIN"):
        twice = model_a.named(name)
        assert len(twice) == 2 and len({nodes[i]["mesh"] for i in twice}) == 1, name
    for key, uid in maker.UID.items():
        assert uid in model_a.by_uid, key
    parent = {n["name"]: nodes[n["parent"]]["name"] for n in nodes if n["parent"] >= 0}
    assert {k for k, v in parent.items() if v == "A-FRAME.ASM"} == {"A-FRAME", "HINGE PIN", "SHEAVE PIN 1", "SHEAVE 1",
                                                                    "SHEAVE PIN 2", "SHEAVE 2"}
    assert {k for k, v in parent.items() if v == "V CRADLE.ASM"} == {"CRADLE STAND", "V ROLLER"}
    # the A-frame's place: its origin on the luff axis, leaning 20° towards +X (a turn about +Y)
    m = model_a.world[model_a.by_uid[maker.UID["A-FRAME.ASM"]]]
    assert np.allclose(m[:3, 3] * 1000.0, N["luff_axis"]["point"], atol=1e-6)
    assert np.allclose(m[:3, :3], maker.RotY(20.0)[:3, :3], atol=1e-9)
    for name in ("SHEAVE 1", "SHEAVE 2"):
        i = model_a.by_uid[maker.UID[name]]
        assert np.allclose(np.array(nodes[i]["matrix"])[:3, 3] * 1000.0, N["contacts"][name]["in_frame"], atol=1e-3)
        assert np.allclose(model_a.world[i][:3, 3] * 1000.0, N["contacts"][name]["axis_point"], atol=1e-3)


def test_the_rope_read_from_its_mesh(rope):
    """Ø24, as long as the numbers say, in the plane y = 0, along the maker's lines and arcs."""
    tube, pts = rope
    assert abs(tube.radius * 1000.0 - 12.0) < 0.1
    assert abs(tube.length * 1000.0 / N["rope"]["length"] - 1.0) < 0.005
    assert np.abs(pts[:, 1]).max() < 0.01
    if pts[0][0] > pts[-1][0]:
        pts = pts[::-1]
    assert np.linalg.norm(pts[0] - N["rope"]["start"]) < 1.0           # (this end is bent: on the drum)
    assert np.linalg.norm(pts[-1] - N["rope"]["end"]) < 0.1
    exact = maker.centreline(0.0, 0.5)
    off = np.array([np.sqrt(((exact - p) ** 2).sum(axis=1).min()) for p in pts])
    assert off.max() < 1.0 and off.mean() < 0.3 and np.sort(off)[int(0.99 * len(off))] < 0.5


def test_the_rope_lies_on_drum_sheaves_and_chute(rope):
    """Along each wrap the rope's middle is at the seat radius from the wheel's axis within 0.3 mm (the facets of
    a bend lie a little inside it), and never nearer anywhere."""
    _tube, pts = rope
    for name, c in N["contacts"].items():
        centre = np.array(c["axis_point"])
        r = off_line(pts, centre, c["axis_direction"])
        assert r.min() > c["seat_radius"] - 0.3, (name, r.min())
        # the points over the wrap, 2° in from the two tangent points
        a_in = math.atan2(c["tangent_in"][2] - centre[2], c["tangent_in"][0] - centre[0])
        ang = np.arctan2(pts[:, 2] - centre[2], pts[:, 0] - centre[0])
        swept = (c["side"] * (a_in - ang)) % (2.0 * math.pi)             # how far round from the tangent-in point
        on = (swept > math.radians(2.0)) & (swept < math.radians(c["wrap"] - 2.0)) & (r < c["seat_radius"] + 5.0)
        assert on.sum() > 0.9 * (c["wrap"] - 4.0) / 360.0 * 2.0 * math.pi * c["seat_radius"] / 3.5, name
        assert np.abs(r[on] - c["seat_radius"]).max() < 0.3, (name, np.abs(r[on] - c["seat_radius"]).max())


def test_the_rope_rests_on_both_v_rollers(rope, model_a):
    _tube, pts = rope
    for k, roller in enumerate(N["rollers"]):
        r = off_line(pts, roller["axis_point"], roller["axis_direction"])
        assert abs(r.min() - roller["seat_radius"]) < 0.3, (k, r.min())
        nearest = pts[int(np.argmin(r))]
        assert np.linalg.norm(nearest - roller["rope_middle"]) < 3.0           # … above the roller, no bend there
        # the roller itself: its axis where the numbers say, plain, Ø120
        i = model_a.by_uid[roller["uid"]]
        v, _t = model_a.mesh(i)
        assert abs(off_line(v, roller["axis_point"], roller["axis_direction"]).max() - 60.0) < 1e-3
        m = model_a.world[i]
        assert np.allclose(m[:3, 3] * 1000.0, roller["axis_point"], atol=1e-3)
        assert np.allclose(m[:3, 2], roller["axis_direction"], atol=1e-6)


def test_the_surfaces_under_the_rope(model_a):
    """From the meshes (their corners lie on the CAD surfaces): the drum's barrel, the sheaves' round grooves
    (radius 13, bottom and flanges where the numbers say), the chute's trough."""
    drum = N["contacts"]["WINCH DRUM"]
    v, _t = model_a.mesh(model_a.by_uid[drum["uid"]])
    r = off_line(v, drum["axis_point"], Y)
    between = np.abs(v[:, 1]) < 200.0 + 1e-3                                     # between the flanges: the barrel
    assert between.sum() > 20 and abs(r[between].min() - 200.0) < 1e-3
    assert set(np.round(r[between], 3)) == {200.0, 300.0}                        # … plain, and the flanges' rims
    assert abs(r.max() - 300.0) < 1e-3 and abs(np.abs(v[:, 1]).max() - 340.0) < 1e-3
    for name in ("SHEAVE 1", "SHEAVE 2"):
        c = N["contacts"][name]
        v, _t = model_a.mesh(model_a.by_uid[c["uid"]])
        r = off_line(v, c["axis_point"], Y)
        bottom = c["surface_radius"]
        assert abs(r.max() - (bottom + 28.0)) < 1e-3, name                       # the flanges
        groove = (np.abs(v[:, 1]) < 12.0) & (r < bottom + 8.0) & (r > bottom - 1.0)
        assert groove.sum() > 100
        assert abs(r[groove].min() - bottom) < 0.2, (name, r[groove].min())      # the groove's bottom
        round_ = np.hypot(r[groove] - (bottom + 13.0), v[groove, 1])             # a circle of radius 13 …
        assert np.abs(round_ - 13.0).max() < 1e-3, name
        assert c["seat_radius"] == bottom + 12.0                                 # … the Ø24 rope lies on its bottom
    chute = N["contacts"]["CHUTE"]
    v, _t = model_a.mesh(model_a.by_uid[chute["uid"]])
    rel = v - chute["axis_point"]
    r = np.hypot(rel[:, 0], rel[:, 2])
    section = np.hypot(r - 608.0, v[:, 1])                                       # round the U's middle
    inner = np.abs(section - 20.0) < 1e-3
    assert inner.sum() > 50 and abs(r[inner].min() - 588.0) < 0.2                # the trough's bottom
    assert abs(r.min() - 578.0) < 0.2                                            # its underside (10 thick)
    around = np.degrees(np.arctan2(rel[:, 0], rel[:, 2]))                        # from straight up towards +X
    assert abs(around.min() + 7.5) < 1e-3 and abs(around.max() - 57.5) < 1e-3, "65° of a circle: not round all the way"


def test_the_importer_finds_the_round_axes(model_a):
    """The axes of round faces in the cache (what joint picking and the cable reading use)."""
    for name, c in N["contacts"].items():
        axes = model_a.axes(model_a.by_uid[c["uid"]])
        assert len(axes) == 1, (name, axes)
        assert has_axis(axes, c["axis_point"], c["axis_direction"]), name
    for roller in N["rollers"]:
        axes = model_a.axes(model_a.by_uid[roller["uid"]])
        assert len(axes) == 1 and has_axis(axes, roller["axis_point"], roller["axis_direction"])
    # the luff axis: on both hinge pins, in the base frame's forks and in the A-frame's feet
    luff = N["luff_axis"]
    for i in model_a.named("HINGE PIN") + model_a.named("BASE FRAME") + model_a.named("A-FRAME"):
        assert has_axis(model_a.axes(i), luff["point"], luff["direction"]), model_a.nodes[i]["uid"]
    assert len(model_a.axes(model_a.named("BASE FRAME")[0])) == 1
    # each sheave's pin is on its sheave's axis; the stands of the chute has no round face at all
    for pin, name in (("SHEAVE PIN 1", "SHEAVE 1"), ("SHEAVE PIN 2", "SHEAVE 2")):
        c = N["contacts"][name]
        assert has_axis(model_a.axes(model_a.named(pin)[0]), c["axis_point"], c["axis_direction"])
    assert model_a.axes(model_a.named("CHUTE STAND")[0]) == []


# ---------------------------------------------------------------------------------------------------------
# no part is drawn through another
# ---------------------------------------------------------------------------------------------------------

def _inside(points, verts, tris):
    """Which points lie inside a closed mesh: a ray from each point (nearly straight up) crosses its skin an odd
    number of times. Two rays must agree (a ray that grazes an edge counts wrong). Only the triangles above a
    point are tried."""
    tri = verts[tris]
    reach = float(verts[:, 2].max() - verts[:, 2].min())
    lo, hi = tri[:, :, :2].min(axis=1), tri[:, :, :2].max(axis=1)
    room = 0.02 * reach + 1e-6                                           # only the triangles over these points
    over = np.all((hi >= points[:, :2].min(axis=0) - room) & (lo <= points[:, :2].max(axis=0) + room), axis=1)
    tri, lo, hi = tri[over], lo[over], hi[over]
    e1, e2 = tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]
    out = None
    for lean in ((0.0137, 0.0071), (-0.0093, 0.0119)):
        d = np.array([lean[0], lean[1], 1.0])
        pad = max(abs(lean[0]), abs(lean[1])) * reach + 1e-6            # how far the ray drifts sideways
        d = d / np.linalg.norm(d)
        h = np.cross(d, e2)
        det = np.einsum("ij,ij->i", e1, h)
        ok = np.abs(det) > 1e-12
        inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
        odd = np.zeros(len(points), dtype=bool)
        for start in range(0, len(points), 2048):
            p = points[start:start + 2048]
            near = ((p[:, None, 0] >= lo[None, :, 0] - pad) & (p[:, None, 0] <= hi[None, :, 0] + pad)
                    & (p[:, None, 1] >= lo[None, :, 1] - pad) & (p[:, None, 1] <= hi[None, :, 1] + pad) & ok[None])
            pi, ti = np.nonzero(near)
            s = p[pi] - tri[ti, 0]
            u = np.einsum("ij,ij->i", s, h[ti]) * inv[ti]
            q = np.cross(s, e1[ti])
            w = (q @ d) * inv[ti]
            t = np.einsum("ij,ij->i", q, e2[ti]) * inv[ti]
            hit = (u >= 0.0) & (w >= 0.0) & (u + w <= 1.0) & (t > 1e-9)
            odd[start:start + 2048] = np.bincount(pi[hit], minlength=len(p)) % 2 == 1
        out = odd if out is None else out & odd
    return out


def samples(mesh, spacing=20.0, most=4000):
    """At most ``most`` points spread over a mesh's faces: its corners and points about ``spacing`` mm apart along
    long thin faces (a rope's straight run is two corners long) and over wide ones (coarser when they are big)."""
    v, t = C.split_long(mesh[0], mesh[1], longest=spacing)
    pts = np.unique(np.round(C.triangle_points(v[t], spacing, max_split=6)[0], 4), axis=0)
    return pts[np.random.default_rng(78).permutation(len(pts))[:most]]


def depth_in(points, mesh, most=300):
    """How deep (mm) the deepest of ``points`` (another part's skin: ``samples``) lies inside a closed mesh:
    0 when none does."""
    v, t = mesh
    lo, hi = v.min(axis=0), v.max(axis=0)
    pts = points[np.all((points > lo) & (points < hi), axis=1)]
    if not len(pts):
        return 0.0
    pts = pts[_inside(pts, v, t)]
    if not len(pts):
        return 0.0
    tri = v[t]
    return max(float(np.linalg.norm(C.closest_on_triangles(p, tri) - p, axis=1).min()) for p in C.thin_out(pts, most))


def _box(x0, y0, z0, x1, y1, z1):
    v = np.array([(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)], dtype=float)
    t = np.array([(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1), (2, 3, 7), (2, 7, 6),
                  (0, 2, 6), (0, 6, 4), (1, 5, 7), (1, 7, 3)])
    return v, t


def test_the_check_for_parts_in_each_other():
    """The check itself: two boxes 3 mm into each other are found from either side, boxes that touch are not, a
    thin bar through the middle of a box (no corner of either in the other) is."""
    a, b = _box(0, 0, 0, 100, 100, 100), _box(97, 10, 10, 200, 90, 90)
    assert abs(depth_in(samples(a), b) - 3.0) < 1e-6 and abs(depth_in(samples(b), a) - 3.0) < 1e-6
    assert depth_in(samples(a), _box(100, 0, 0, 200, 100, 100)) < 1e-6
    assert depth_in(samples(a), _box(101, 0, 0, 200, 100, 100)) == 0.0
    bar = _box(-50, 45, 45, 150, 55, 55)
    assert depth_in(samples(bar), a) > 30.0
    assert _inside(np.array([[50.0, 50.0, 50.0], [150.0, 50.0, 50.0], [50.0, 50.0, -1.0]]), *a).tolist() == [
        True, False, False]


def test_no_part_is_drawn_through_another(model_a, model_b):
    """Meshes of parts that touch (a pin in its bore, the rope in a groove) overlap by their facets only: under
    0.6 mm at Normal detail (measured: 0.31, the rope in the chute). A part drawn through another would be in it
    by millimetres. Revision B: its one new part against the others (the rest is revision A, see below)."""
    for model in (model_a, model_b):
        meshes = {i: model.mesh(i) for i in model.parts}
        points = {i: samples(meshes[i]) for i in model.parts}
        worst = (0.0, "")
        for i in model.parts:
            for j in model.parts:
                if i != j and (model is model_a or "GUARD" in (model.nodes[i]["name"], model.nodes[j]["name"])):
                    d = depth_in(points[i], meshes[j])
                    worst = max(worst, (d, f"{model.nodes[i]['uid']} in {model.nodes[j]['uid']}"))
        assert worst[0] < 0.6, worst
    # … and the check sees it when a part does: a V roller 5 mm up into the rope, SHEAVE 2 10 mm into its cheek
    meshes = {i: model_a.mesh(i) for i in model_a.parts}
    rope_i = model_a.by_uid[N["rope"]["uid"]]
    roller = meshes[model_a.by_uid[N["rollers"][0]["uid"]]]
    assert depth_in(samples(meshes[rope_i]), (roller[0] + (0.0, 0.0, 5.0), roller[1])) > 2.5
    sheave = meshes[model_a.by_uid[N["contacts"]["SHEAVE 2"]["uid"]]]
    assert depth_in(samples((sheave[0] + (0.0, 10.0, 0.0), sheave[1])), meshes[model_a.named("A-FRAME")[0]]) > 2.5


# ---------------------------------------------------------------------------------------------------------
# revision B, and the maker against the shipped files
# ---------------------------------------------------------------------------------------------------------

def test_revision_b_is_a_with_a_guard_in_another_order(model_a, model_b):
    """Every part of A is in B under the same ID, at the same place, with the same shape; B has GUARD more."""
    assert set(model_b.by_uid) - set(model_a.by_uid) == {"TEST.PATHS#1/GUARD#1"}
    assert set(model_a.by_uid) <= set(model_b.by_uid)
    assert model_b.info["stats"]["placed_parts"] == 18 and model_b.info["stats"]["unique_parts"] == 15
    assert _solids_in(B) == 18
    for uid, i in model_a.by_uid.items():
        j = model_b.by_uid[uid]
        na, nb = model_a.nodes[i], model_b.nodes[j]
        assert (na["name"], na["kind"]) == (nb["name"], nb["kind"]), uid
        assert np.allclose(model_a.world[i], model_b.world[j], atol=1e-12), uid
        if na["kind"] != "part":
            continue
        assert np.allclose(na["color"], nb["color"]), uid
        (va, ta), (vb, tb) = model_a.mesh(i), model_b.mesh(j)
        assert len(va) == len(vb) and len(ta) == len(tb), uid       # (the triangles' order may differ: counts,
        assert np.allclose(va.min(axis=0), vb.min(axis=0), atol=1e-6)            # places and volume)
        assert np.allclose(va.max(axis=0), vb.max(axis=0), atol=1e-6)
        assert np.allclose(va.mean(axis=0), vb.mean(axis=0), atol=1e-6)
        assert abs(C.signed_volume(va, ta) - C.signed_volume(vb, tb)) < 1e-6 * max(abs(C.signed_volume(va, ta)), 1.0)

    def order(model, parent):
        p = next(i for i, n in enumerate(model.nodes) if n["name"] == parent)
        return [n["name"] for n in model.nodes if n["parent"] == p]

    for parent in ("TEST.PATHS", "A-FRAME.ASM"):
        a, b = order(model_a, parent), order(model_b, parent)
        assert sorted(a + (["GUARD"] if parent == "TEST.PATHS" else [])) == sorted(b) and a != [n for n in b
                                                                                                  if n != "GUARD"]
    guard = model_b.by_uid["TEST.PATHS#1/GUARD#1"]
    assert np.allclose(model_b.nodes[guard]["color"], COLOURS["GUARD"], atol=2e-3)
    v, _t = model_b.mesh(guard)
    assert np.allclose(v.min(axis=0), maker.GUARD[:3]) and np.allclose(v.max(axis=0), maker.GUARD[3:])
    for i in model_b.parts:                                         # it stands on the base and touches nothing else
        if i != guard and model_b.nodes[i]["name"] != "BASE FRAME":
            w, _t = model_b.mesh(i)
            apart = np.maximum(np.maximum(w.min(axis=0) - v.max(axis=0), v.min(axis=0) - w.max(axis=0)), 0.0)
            assert np.linalg.norm(apart) > 50.0, model_b.nodes[i]["uid"]


def test_the_maker_makes_what_the_files_hold(model_a):
    """The STEP file is the maker's model (someone changes the maker and forgets the files: this fails): every
    part one solid, its volume and its box the same; the rope's solid touches what it lies on."""
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib

    made = maker.placed(maker.model("A"))
    assert [name for name, _path, _shape in made] == maker.PARTS
    assert [model_a.nodes[i]["name"] for i in model_a.parts] == maker.PARTS
    shapes = {}
    for i, (name, _path, shape) in zip(model_a.parts, made):
        shapes.setdefault(name, []).append(shape)
        assert maker.solids(shape) == 1, name
        v, t = model_a.mesh(i)
        assert abs(C.signed_volume(v, t) / maker.volume(shape) - 1.0) < 0.01, name
        box = Bnd_Box()
        BRepBndLib.AddOptimal_s(shape, box, False, False)
        lo, hi = box.CornerMin(), box.CornerMax()
        assert np.allclose(v.min(axis=0), (lo.X(), lo.Y(), lo.Z()), atol=0.6), name
        assert np.allclose(v.max(axis=0), (hi.X(), hi.Y(), hi.Z()), atol=0.6), name
    rope = shapes["WIRE ROPE"][0]
    assert abs(maker.volume(rope) / (math.pi * 12.0 ** 2 * N["rope"]["length"]) - 1.0) < 1e-6
    for name in maker.ROPE_TOUCHES:
        for shape in shapes[name]:
            assert maker.gap(rope, shape) < 1e-4, (name, "the rope does not touch it")
    for name in ("A-FRAME", "CRADLE STAND", "CHUTE STAND", "BASE FRAME", "SHEAVE PIN 2"):
        assert maker.gap(rope, shapes[name][0]) > 8.0, name
