"""Task 0318, independent tests (written from the brief by a tester who did not write the code).

Without Blender: where rust is logical (every library material, every finish's Metal / Kind), ``weave_frames`` on odd
and real-life input (empty, one triangle, wrong starts, degenerate triangles, a face split in two, a mirrored part, a U
with two folds, a cone, a closed tube, a dome, a round tube whose CAD face is split in two halves), ``_sphere`` on
cylinders / cones / tori / short bands / noise, ``face_frames``' sphere sign and pole, the importer's ``_face_axis`` on
an OpenCascade sphere. In Blender (as a Python module): the group's Rust slider, Rust 0 adds nothing, one AO for Wear +
Rust, ``is_current`` / ``ensure_material`` with and without rust, the finishes test model through the app (the carbon
cup's outer / inner sphere, the cap's dome, every face attribute finite), carbon / perlage builds, the web model's
colour, welds following a group's Rust."""

from __future__ import annotations

import json
import math
import os
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..")))

from fresing_render.core import finishes as fc  # noqa: E402
from fresing_render.core import materials_lib as ml  # noqa: E402

FINISHES_STEP = os.path.join(HERE, "data", "test_finishes.step")
WELDMENT = os.path.join(HERE, "data", "test_weldment.step")


# ---------------------------------------------------------------------------------------------------------------
# rust: where it is logical (no Blender)
# ---------------------------------------------------------------------------------------------------------------

NEVER = ("stainless", "aluminium", "brass", "bronze", "copper", "titanium")


def test_every_library_material_has_a_kind_or_a_reason():
    """Every material either rusts (one of the four kinds) or says why not – never both, never neither."""
    for mid in ml.MATERIALS:
        f = fc.get(mid) or {}
        bases = f.get("bases") or ("",)
        kinds = f.get("kinds") or ("",)
        for b in bases:
            for k in kinds:
                rk = ml.rust_kind(mid, b, k)
                why = ml.no_rust_why(mid, b, k)
                assert rk in ("BARE", "PAINTED", "ZINC", "PLATED", ""), (mid, b, k, rk)
                assert bool(rk) != bool(why), (mid, b, k, rk, why)


def test_never_rusts_stainless_aluminium_brass_copper_plastics_glass():
    for mid, spec in ml.MATERIALS.items():
        low = (mid + " " + spec["label"]).lower()
        if fc.get(mid) and (fc.get(mid).get("bases") or fc.get(mid).get("kinds")):
            continue                                   # a finish: its Metal / Kind decides (below)
        if mid == "nickel_plated":
            continue                                   # its own test below
        if any(w in low for w in NEVER) or spec["category"] in ("Plastic & rubber", "Glass", "Light"):
            assert ml.rust_kind(mid) == "", (mid, ml.rust_kind(mid))
    for mid in ("glass_clear", "polycarbonate_clear", "glass_tinted", "acrylic_frosted", "rubber_black",
                "plastic_gloss", "pom_white", "carbon_fibre", "wood", "concrete", "emission_light", "zinc_diecast"):
        assert ml.rust_kind(mid) == "", mid


def test_finishes_each_metal_and_kind():
    """A finish rusts by its Metal: steel and cast iron bare, galvanized zinc; stainless, aluminium, brass, titanium
    never. Sand-cast by its Kind."""
    want = {"STEEL": "BARE", "CAST_IRON": "BARE", "GALVANIZED": "ZINC", "STAINLESS": "", "ALUMINIUM": "",
            "BRASS": "", "TITANIUM": ""}
    for fid, f in fc.FINISHES.items():
        for b in f.get("bases") or ():
            assert ml.rust_kind(fid, b) == want[b], (fid, b)
            if not want[b]:
                why = ml.no_rust_why(fid, b).lower()
                assert why and b.split("_")[0][:5].lower() in why.replace("aluminium", "alumi"), (fid, b, why)
    assert ml.rust_kind("as_cast", kind="CAST_FE") == "BARE"
    assert ml.rust_kind("as_cast", kind="CAST_AL") == ""
    assert ml.rust_kind("as_cast") == ""                            # its default kind is aluminium
    for k in ("TWILL", "PLAIN"):
        assert ml.rust_kind("carbon_fibre", kind=k) == ""
    for k in fc.FINISHES["vdi"]["kinds"]:
        assert ml.rust_kind("vdi", kind=k) == ""


def test_material_that_does_not_exist():
    for mid in ("no such material", "", "STEEL_RAW", "steel_raw ", "NoneType"):
        assert ml.rust_kind(mid) == "", mid
        assert ml.no_rust_why(mid), mid                          # always some reason, never a crash
    assert ml.rust_kind("no such material", "STEEL") == ""      # a Metal does not make a made-up material rust


def test_plain_steel_wire_rope_is_galvanised_wire():
    """'Steel wire rope' is drawn as bright galvanised wires (its library entry says so; 'Steel wire rope, galvanised'
    is the duller, heavier coat): red rust only where the zinc is worn. (The independent tester first expected BARE;
    the worker kept ZINC for this reason.)"""
    assert ml.rust_kind("wire_rope") == "ZINC" and ml.rust_kind("wire_rope_galv") == "ZINC"


def test_nickel_plated_brass_fittings_do_not_red_rust():
    """'Nickel plated (brass fittings)': brass under the nickel – worn through it turns brown, never red rust."""
    assert "brass" in ml.MATERIALS["nickel_plated"]["label"].lower()
    assert ml.rust_kind("nickel_plated") == ""


def test_rust_mask_value_edges():
    from fresing_render.blender import rust
    for p in np.linspace(0, 1, 11):
        for o in np.linspace(0, 1, 5):
            v0 = rust.mask_value(p, o, 0.0)
            prev = v0
            for a in np.linspace(0, 1, 21):
                v = rust.mask_value(p, o, a)
                assert 0.0 <= v <= 1.0 and math.isfinite(v)
                assert v >= prev - 1e-12                     # more Rust never less rusty
                prev = v
    assert rust.mask_value(1.0, 1.0, 0.0) == 1.0 or rust.mask_value(0.0, 0.0, 0.0) == 0.0


# ---------------------------------------------------------------------------------------------------------------
# meshes
# ---------------------------------------------------------------------------------------------------------------


def _grid(nu, nv, fn):
    pts = np.array([fn(i / nu, j / nv) for j in range(nv + 1) for i in range(nu + 1)], float)
    tri = []
    for j in range(nv):
        for i in range(nu):
            a = j * (nu + 1) + i
            tri += [[a, a + 1, a + nu + 2], [a, a + nu + 2, a + nu + 1]]
    return pts, np.array(tri, np.int64)


def _flip(face):
    pts, tri = face
    return pts, tri[:, ::-1].copy()


def _join(faces):
    co, tri, starts, n = [], [], [], 0
    for pts, t in faces:
        starts.append(sum(len(x) for x in tri))
        tri.append(t + n)
        co.append(pts)
        n += len(pts)
    starts.append(sum(len(x) for x in tri))
    return np.vstack(co), np.vstack(tri), starts


def _normals(co, tri):
    a, b, c = co[tri[:, 0]], co[tri[:, 1]], co[tri[:, 2]]
    n = np.cross(b - a, c - a)
    return n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-20)


def _glob(frames, t0, pts):
    """The weave (U, V) a triangle of face starting at ``t0`` gives the points (the shader's formula)."""
    o, d, r, k, a, b = frames
    n = fc._native(int(round(k[t0])), pts, o[t0], d[t0], r[t0], b[t0, 2])
    c, s, det = a[t0]
    n[:, 1] *= det
    return np.stack([c * n[:, 0] - s * n[:, 1], s * n[:, 0] + c * n[:, 1]], 1) + b[t0, :2]


def _frames(co, tri, starts, axes=(), axf=()):
    o, d, r, k = fc.face_frames(co, tri, axes, axf, starts)
    a, b = fc.weave_frames(co, tri, o, d, r, k, starts)
    return o, d, r, k, a, b


def _shared_edges(co, tri, starts):
    """{(face i, face j): points (n, 3)} of the vertices two CAD faces share (by position)."""
    key = {}
    for f in range(len(starts) - 1):
        for v in np.unique(tri[starts[f]:starts[f + 1]].ravel()):
            key.setdefault(tuple(np.round(co[v] * 1e7).astype(np.int64)), set()).add(f)
    out = {}
    for kk, fs in key.items():
        fs = sorted(fs)
        for i in range(len(fs)):
            for j in range(i + 1, len(fs)):
                out.setdefault((fs[i], fs[j]), []).append(np.array(kk, float) / 1e7)
    return {k: np.array(v) for k, v in out.items()}


def _sheet(r=0.005, mirror=False, u_shape=False):
    """The outer skin of a folded sheet (normals out): a floor (z = 0, x from -L to L, facing -z), a bend of radius r
    round the line (x = L, z = r) up into a wall (x = L + r, facing +x). ``u_shape``: the same bend and wall at
    x = -L too (a U). ``mirror``: mirrored in x (triangles turned so the normals still point out).
    Returns (co, tri, starts, axes, axis_faces); the faces: floor, bend, wall[, bend, wall]."""
    L, H, W = 0.03, 0.03, 0.04

    def bend(sign):
        return _grid(6, 3, lambda u, v: (sign * L + sign * r * math.sin(u * math.pi / 2), W * v,
                                         r - r * math.cos(u * math.pi / 2)))

    def wall(sign):
        return _grid(4, 3, lambda u, v: (sign * (L + r), W * v, r + H * u))

    faces = [_grid(6, 3, lambda u, v: (-L + 2 * L * u, W * v, 0.0)), bend(1.0), wall(1.0)]
    axes = [L, 0.0, r, 0.0, 1.0, 0.0, r]
    if u_shape:
        faces += [bend(-1.0), wall(-1.0)]
        axes += [-L, 0.0, r, 0.0, 1.0, 0.0, r]
    out = []
    for f, (pts, t) in enumerate(faces):           # turn each face so its normals point out
        n = _normals(pts, t).mean(0)
        c = pts.mean(0)
        if f == 0:
            want = np.array([0.0, 0.0, -1.0])
        elif f in (2, 4):
            want = np.array([np.sign(c[0]), 0.0, 0.0])
        else:
            want = np.array([np.sign(c[0]), 0.0, -1.0])
        if np.dot(n, want) < 0:
            t = t[:, ::-1].copy()
        out.append((pts, t))
    co, tri, starts = _join(out)
    axf = [starts[1], starts[2] - starts[1], 0]
    if u_shape:
        axf += [starts[3], starts[4] - starts[3], 1]
    if mirror:
        co = co * np.array([-1.0, 1.0, 1.0])
        tri = tri[:, ::-1].copy()
        axes = list((np.array(axes).reshape(-1, 7) * np.array([-1, 1, 1, 1, 1, 1, 1])).ravel())
    return co, tri, starts, axes, axf


def _assert_continues(frames, co, tri, starts, pairs=None, atol=2e-5):
    edges = _shared_edges(co, tri, starts)
    assert edges
    for (i, j), pts in edges.items():
        if pairs is not None and (i, j) not in pairs:
            continue
        gi, gj = _glob(frames, starts[i], pts), _glob(frames, starts[j], pts)
        assert np.allclose(gi, gj, atol=atol), ((i, j), np.abs(gi - gj).max())


# ---------------------------------------------------------------------------------------------------------------
# weave_frames on odd input
# ---------------------------------------------------------------------------------------------------------------


def _finite(*arrs):
    return all(np.all(np.isfinite(np.asarray(a))) for a in arrs)


def test_weave_frames_empty_and_one_triangle():
    z3 = np.zeros((0, 3))
    a, b = fc.weave_frames(z3, np.zeros((0, 3), np.int64), z3, z3, np.zeros(0), np.zeros(0), [])
    assert a.shape == (0, 3) and b.shape == (0, 3)
    co = np.array([[0, 0, 0], [0.01, 0, 0], [0, 0.01, 0]], float)
    tri = np.array([[0, 1, 2]])
    o, d, r, k = fc.face_frames(co, tri, [], [], [0, 1])
    a, b = fc.weave_frames(co, tri, o, d, r, k, [0, 1])
    assert a.shape == (1, 3) and b.shape == (1, 3) and _finite(a, b)
    assert np.allclose(a[0], (1, 0, 1)) and np.allclose(b[0], 0)
    # triangles but no points: no crash
    a, b = fc.weave_frames(np.zeros((0, 3)), tri, o, d, r, k, [0, 1])
    assert a.shape == (1, 3)


@pytest.mark.parametrize("starts", [[], [0], [5], [0, 3, 3, 999], [7, 0, 3], [-4, 2, 10 ** 9], [0, 100, 40]])
def test_weave_frames_wrong_starts(starts):
    co, tri, _s, axes, axf = _sheet()
    o, d, r, k = fc.face_frames(co, tri, axes, axf, _s)
    a, b = fc.weave_frames(co, tri, o, d, r, k, starts)
    assert a.shape == (len(tri), 3) and b.shape == (len(tri), 3) and _finite(a, b)
    assert np.allclose(np.hypot(a[:, 0], a[:, 1]), 1.0) and set(np.unique(a[:, 2])) <= {1.0, -1.0}


def test_weave_frames_degenerate_triangles_no_nan():
    co, tri, starts, axes, axf = _sheet()
    # a face of only zero-area triangles (all points on one line) and a sliver into the floor
    n = len(co)
    line = np.array([[0.0, -0.01, 0.0], [0.001, -0.01, 0.0], [0.002, -0.01, 0.0], [0.003, -0.01, 0.0]])
    co2 = np.vstack([co, line])
    tri2 = np.vstack([tri, [[n, n + 1, n + 2], [n + 1, n + 2, n + 3], [n, n, n + 1]]])
    starts2 = starts + [len(tri2)]
    o, d, r, k = fc.face_frames(co2, tri2, axes, axf, starts2)
    assert _finite(o, d, r, k)
    a, b = fc.weave_frames(co2, tri2, o, d, r, k, starts2)
    assert _finite(a, b)
    # a duplicated point in the middle of a face (a zero-area triangle inside it)
    tri3 = tri.copy()
    tri3[0] = (tri3[0, 0], tri3[0, 0], tri3[0, 1])
    o, d, r, k = fc.face_frames(co, tri3, axes, axf, starts)
    a, b = fc.weave_frames(co, tri3, o, d, r, k, starts)
    assert _finite(o, d, r, k, a, b)


def test_weave_frames_points_out_of_range_no_crash():
    co, tri, starts, axes, axf = _sheet()
    o, d, r, k = fc.face_frames(co, tri, axes, axf, starts)
    bad = tri.copy()
    bad[3] = (0, len(co) + 5, -1)
    a, b = fc.weave_frames(co, bad, o, d, r, k, starts)
    assert _finite(a, b)


# ---------------------------------------------------------------------------------------------------------------
# weave_frames: the weave runs on where a draped ply would
# ---------------------------------------------------------------------------------------------------------------


def test_a_face_split_in_two_coplanar_halves_continues_exactly():
    left = _grid(5, 4, lambda u, v: (-0.03 + 0.03 * u, 0.04 * v, 0.0))
    right = _grid(5, 4, lambda u, v: (0.03 * u, 0.04 * v, 0.0))
    co, tri, starts = _join([left, right])
    fr = _frames(co, tri, starts)
    # the same frame on both: a point of each half gives the plain plane coordinates, no turn, no shift difference
    all_pts = co
    assert np.allclose(_glob(fr, starts[0], all_pts), _glob(fr, starts[1], all_pts), atol=1e-12)
    # a tilted plane split along a diagonal into two triangles' worth of faces, weave the same over both
    rot = np.array([[0.8, 0.0, 0.6], [0.0, 1.0, 0.0], [-0.6, 0.0, 0.8]])
    co2 = co @ rot.T + (0.1, -0.2, 0.3)
    fr2 = _frames(co2, tri, starts)
    assert np.allclose(_glob(fr2, starts[0], co2), _glob(fr2, starts[1], co2), atol=1e-9)


def test_a_round_bend_split_in_two_continues():
    """Half a tube split into two quarter faces (one axis): the second continues the first along their shared line."""
    r = 0.02
    q1 = _grid(8, 3, lambda u, v: (r * math.cos(math.pi / 2 * u), r * math.sin(math.pi / 2 * u), 0.05 * v))
    q2 = _grid(8, 3, lambda u, v: (r * math.cos(math.pi / 2 + math.pi / 2 * u), r * math.sin(math.pi / 2 + math.pi / 2 * u),
                                   0.05 * v))
    co, tri, starts = _join([q1, q2])
    axf = [0, starts[1], 0, starts[1], starts[2] - starts[1], 0]
    fr = _frames(co, tri, starts, [0, 0, 0, 0, 0, 1, r], axf)
    _assert_continues(fr, co, tri, starts)
    # over both: U grows evenly with the angle (one unrolled sheet), V is z
    pts = np.array([(r * math.cos(t), r * math.sin(t), 0.01) for t in np.linspace(0.05, math.pi - 0.05, 9)])
    face = [starts[0] if t < math.pi / 2 else starts[1] for t in np.linspace(0.05, math.pi - 0.05, 9)]
    uv = np.array([_glob(fr, f, p[None])[0] for f, p in zip(face, pts)])
    steps = np.linalg.norm(np.diff(uv, axis=0), axis=1)
    assert np.allclose(steps, steps[0], rtol=1e-6)


def test_a_mirrored_folded_sheet_continues():
    for mirror in (False, True):
        co, tri, starts, axes, axf = _sheet(mirror=mirror)
        fr = _frames(co, tri, starts, axes, axf)
        assert set(np.unique(fr[3])) == {0.0, 1.0}, np.unique(fr[3])
        _assert_continues(fr, co, tri, starts)
        # and the weave is not folded back on itself: across the bend it runs on by the arc length
        sg = -1.0 if mirror else 1.0
        fl = co[np.unique(tri[starts[0]:starts[1]].ravel())]
        e1 = fl[np.abs(fl[:, 0] - sg * 0.03) < 1e-9]               # the floor's edge at the bend
        floor_far = fl[np.abs(fl[:, 0] + sg * 0.03) < 1e-9]        # the floor's other edge
        e2 = co[np.unique(tri[starts[2]:starts[3]].ravel())]
        e2 = e2[np.abs(e2[:, 2] - 0.005) < 1e-9]                  # the wall's foot
        assert len(e1) and len(e2) and len(floor_far)
        g1, g2 = _glob(fr, starts[0], e1), _glob(fr, starts[2], e2)
        g0 = _glob(fr, starts[0], floor_far)
        # the far edge of the floor, the bend line, the wall foot lie on one line across, in order
        a0, a1, a2 = (np.mean(x, 0) for x in (g0, g1, g2))
        d01, d12 = a1 - a0, a2 - a1
        assert np.dot(d01, d12) > 0.99 * np.linalg.norm(d01) * np.linalg.norm(d12), (mirror, d01, d12)
        assert np.linalg.norm(d12) == pytest.approx(0.005 * math.pi / 2, abs=5e-5)


def test_a_u_with_two_folds_continues_all_round():
    co, tri, starts, axes, axf = _sheet(u_shape=True)
    fr = _frames(co, tri, starts, axes, axf)
    _assert_continues(fr, co, tri, starts)
    # from one wall's top to the other's along the skin: 2 walls + 2 bends + the floor
    top1 = np.array([[0.035, 0.02, 0.035]])
    top2 = np.array([[-0.035, 0.02, 0.035]])
    d = np.linalg.norm(_glob(fr, starts[2], top1) - _glob(fr, starts[4], top2))
    assert d == pytest.approx(2 * 0.03 + 2 * 0.005 * math.pi / 2 + 0.06, abs=1e-4)


def test_a_tube_whose_round_face_is_split_in_two_has_at_most_one_seam():
    """Many CAD programs store a whole tube's round face as two half faces. A real tube has at most one ply joint:
    the weave must run on across at least one of the two shared lines."""
    r = 0.02
    h1 = _grid(12, 4, lambda u, v: (r * math.cos(math.pi * u), r * math.sin(math.pi * u), 0.05 * v))
    h2 = _grid(12, 4, lambda u, v: (r * math.cos(math.pi + math.pi * u), r * math.sin(math.pi + math.pi * u), 0.05 * v))
    co, tri, starts = _join([h1, h2])
    axf = [0, starts[1], 0, starts[1], starts[2] - starts[1], 0]
    fr = _frames(co, tri, starts, [0, 0, 0, 0, 0, 1, r], axf)
    misses = []
    for x in (-r, r):
        e = np.array([(x, 0.0, z) for z in np.linspace(0, 0.05, 5)])
        misses.append(float(np.abs(_glob(fr, starts[0], e) - _glob(fr, starts[1], e)).max()))
    assert min(misses) < 2e-5, misses


def test_closed_tube_cone_and_dome_keep_their_own_frame():
    r = 0.02
    # a closed tube: theta0 = -1, no turn, no shift
    tube = _grid(24, 3, lambda u, v: (r * math.cos(2 * math.pi * u), r * math.sin(2 * math.pi * u), 0.05 * v))
    co, tri = tube
    fr = _frames(co, tri, [0, len(tri)], [0, 0, 0, 0, 0, 1, r], [0, len(tri), 0])
    assert (fr[3] == 1).all() and (fr[5][:, 2] == -1.0).all() and np.allclose(fr[4], (1, 0, 1))
    # a closed bore (normals inwards): k = -1, also closed
    fr = _frames(co, tri[:, ::-1], [0, len(tri)], [0, 0, 0, 0, 0, 1, r], [0, len(tri), 0])
    assert (fr[3] == -1).all() and (fr[5][:, 2] == -1.0).all()
    # a closed cone
    cone = _grid(24, 4, lambda u, v: ((0.01 + 0.02 * v) * math.cos(2 * math.pi * u),
                                      (0.01 + 0.02 * v) * math.sin(2 * math.pi * u), 0.03 * v))
    co, tri = cone
    fr = _frames(co, tri, [0, len(tri)], [0, 0, 0, 0, 0, 1, 0.03], [0, len(tri), 0])
    assert set(np.unique(fr[3])) <= {1.0, -1.0} and (fr[5][:, 2] == -1.0).all() and _finite(*fr)
    # a dome (a sphere cap) with a flat rim beside it: the dome keeps its own frame; nothing is NaN
    R = 0.04
    dome = _grid(24, 6, lambda u, v: (R * math.sin(0.8 * v) * math.cos(2 * math.pi * u),
                                      R * math.sin(0.8 * v) * math.sin(2 * math.pi * u), R * math.cos(0.8 * v)))
    rim_r0 = R * math.sin(0.8)
    rim = _grid(24, 2, lambda u, v: ((rim_r0 + 0.01 * v) * math.cos(2 * math.pi * u),
                                     (rim_r0 + 0.01 * v) * math.sin(2 * math.pi * u), R * math.cos(0.8)))
    co, tri, starts = _join([_flip(dome), rim])
    fr = _frames(co, tri, starts, [0, 0, 0, 0, 0, 1, R], [0, starts[1], 0])
    k = fr[3]
    assert (k[:starts[1]] == 3).all(), np.unique(k[:starts[1]])
    assert np.allclose(fr[4][:starts[1]], (1, 0, 1)) and np.allclose(fr[5][:starts[1]], 0) and _finite(*fr)


def test_weave_frames_of_a_moved_part_are_the_same_frames():
    """The same sheet moved: the weave coordinates of each point move with it (frames are found from shape, not
    place): the pattern on the part does not change when the part is moved in its own file."""
    co, tri, starts, axes, axf = _sheet(u_shape=True)
    fr = _frames(co, tri, starts, axes, axf)
    shift = np.array([0.3, -0.1, 0.05])
    ax2 = (np.array(axes).reshape(-1, 7) + np.r_[shift, 0, 0, 0, 0]).ravel()
    fr2 = _frames(co + shift, tri, starts, ax2, axf)
    _assert_continues(fr2, co + shift, tri, starts)


# ---------------------------------------------------------------------------------------------------------------
# _sphere and face_frames' spheres
# ---------------------------------------------------------------------------------------------------------------


def test_sphere_test_on_other_round_shapes():
    o, d = np.zeros(3), np.array([0.0, 0.0, 1.0])
    rng = np.random.default_rng(3)
    # cylinders: long, short, very short, coarse, with the triangles' middles (inside the surface)
    for h in (0.05, 0.003, 0.0005):
        for n in (8, 24, 96):
            cyl = _grid(n, 1, lambda u, v: (0.04 * math.cos(2 * math.pi * u), 0.04 * math.sin(2 * math.pi * u), h * v))
            pts, tri = cyl
            cen = pts[tri].mean(1)
            assert fc._sphere(np.vstack([pts, cen]), o, d) is None, (h, n)
    # cones: long and short, steep and flat; real chamfers (1 mm x 45° on Ø20, 0.5 mm on Ø40, 3 mm on Ø100)
    for r0, h, slope in ((0.02, 0.01, 0.2), (0.02, 0.01, 1.0), (0.02, 0.01, 3.0), (0.0092, 0.0008, 1.0),
                         (0.0195, 0.0005, 1.0), (0.047, 0.003, 1.0), (0.01, 0.002, 0.58)):
        cone = np.array([((r0 + slope * z) * math.cos(t), (r0 + slope * z) * math.sin(t), z)
                         for z in np.linspace(0, h, 6) for t in np.linspace(0, 6, 16)])
        got = fc._sphere(cone, o, d)
        assert got is None, (r0, h, slope, got)
    # tori (fillets round an axis) with a ring at least as wide as the tube
    for R0, r0 in ((0.05, 0.005), (0.02, 0.01), (0.01, 0.01)):
        for span in (0.3, 1.0, math.pi):
            tor = np.array([((R0 + r0 * math.cos(p)) * math.cos(t), (R0 + r0 * math.cos(p)) * math.sin(t),
                             r0 * math.sin(p)) for p in np.linspace(-span / 2, span / 2, 7)
                            for t in np.linspace(0, 6, 16)])
            assert fc._sphere(tor, o, d) is None, (R0, r0, span)
    # noise
    for _ in range(10):
        assert fc._sphere(rng.normal(size=(40, 3)) * 0.01, o, d) is None
    # one ring of points (all one z): nothing to fit
    ring = np.array([(0.03 * math.cos(t), 0.03 * math.sin(t), 0.0) for t in np.linspace(0, 6, 12)])
    assert fc._sphere(ring, o, d) is None
    # degenerate input
    assert fc._sphere(np.zeros((5, 3)), o, d) is None


def test_sphere_found_whatever_its_place_and_axis():
    rng = np.random.default_rng(7)
    for _ in range(10):
        d = rng.normal(size=3)
        d /= np.linalg.norm(d)
        c = rng.normal(size=3) * 0.2
        R = rng.uniform(0.005, 0.5)
        u = np.cross(d, [1.0, 0, 0] if abs(d[0]) < 0.9 else [0, 1.0, 0])
        u /= np.linalg.norm(u)
        w = np.cross(d, u)
        pts = np.array([c + R * (math.cos(p) * d + math.sin(p) * (math.cos(t) * u + math.sin(t) * w))
                        for p in np.linspace(0.1, 0.7, 5) for t in np.linspace(0, 6, 12)])
        o = c - 0.37 * d                                          # any point on the axis
        got = fc._sphere(pts, o, d)
        assert got is not None
        assert np.allclose(got[0], c, atol=1e-9 + 1e-9 * R) and got[1] == pytest.approx(R, rel=1e-9)
        # with a little noise (a mesh's rounding) still a sphere
        got = fc._sphere(pts + rng.normal(size=pts.shape) * R * 1e-4, o, d)
        assert got is not None and got[1] == pytest.approx(R, rel=1e-2)


def _dome(R, top_angle, zc=0.0, n=24, m=6, inside=False, lo=0.0):
    face = _grid(n, m, lambda u, v: (R * math.sin(lo + (top_angle - lo) * v) * math.cos(2 * math.pi * u),
                                     R * math.sin(lo + (top_angle - lo) * v) * math.sin(2 * math.pi * u),
                                     zc + R * math.cos(lo + (top_angle - lo) * v)))
    pts, tri = face
    n_ = _normals(pts, tri)
    out = np.sum(np.einsum("ij,ij->i", n_, pts[tri].mean(1) - (0, 0, zc))) > 0
    if out == inside:
        tri = tri[:, ::-1].copy()
    return pts, tri


@pytest.mark.parametrize("axis_sign", [1.0, -1.0])
def test_face_frames_sphere_sign_and_pole(axis_sign):
    R, zc = 0.037, -0.012
    for inside, want in ((False, 3.0), (True, -3.0)):
        pts, tri = _dome(R, 0.9, zc, inside=inside)
        axes = [0.0, 0.0, zc + 0.5 * axis_sign, 0.0, 0.0, axis_sign, R]     # any point on the axis, either way
        o, d, r, k = fc.face_frames(pts, tri, axes, [0, len(tri), 0], [0, len(tri)])
        assert (k == want).all(), (inside, np.unique(k))
        assert np.allclose(o, (0, 0, zc), atol=0.01 * R) and np.allclose(r, R, rtol=0.01)
        assert np.allclose(d, (0, 0, 1)), d[0]                    # the pole: towards the dome's middle
    # a bowl (the dome hanging down): the pole points down
    pts, tri = _dome(R, 0.9, zc)
    pts = pts * (1, 1, -1) + (0, 0, 2 * zc)
    tri = tri[:, ::-1].copy()
    o, d, r, k = fc.face_frames(pts, tri, [0, 0, zc, 0, 0, axis_sign, R], [0, len(tri), 0], [0, len(tri)])
    assert (k == 3).all() and np.allclose(d, (0, 0, -1))


def test_face_frames_sphere_zone_and_a_cup():
    """A spherical zone (no pole in it) is a sphere too; a cup's outer dome +3, the inner -3 on the same axis."""
    R = 0.037
    zone = _dome(R, 1.0, lo=0.4)
    o, d, r, k = fc.face_frames(*zone, [0, 0, 0, 0, 0, 1, R], [0, len(zone[1]), 0], [0, len(zone[1])])
    assert (k == 3).all() and np.allclose(r, R, rtol=0.01)
    outer = _dome(R, 0.9)
    inner = _dome(R - 0.0025, 0.9, inside=True)
    co, tri, starts = _join([outer, inner])
    # one axis line for both (the importer keeps the largest radius on a line)
    axf = [0, starts[1], 0, starts[1], starts[2] - starts[1], 0]
    o, d, r, k = fc.face_frames(co, tri, [0, 0, 0, 0, 0, 1, R], axf, starts)
    assert (k[:starts[1]] == 3).all() and (k[starts[1]:] == -3).all()
    assert np.allclose(r[:starts[1]], R, rtol=0.01) and np.allclose(r[starts[1]:], R - 0.0025, rtol=0.01)


def test_face_frames_cylinder_beside_a_sphere_on_one_axis_stays_a_cylinder():
    r = 0.03
    cyl = _grid(24, 4, lambda u, v: (r * math.cos(2 * math.pi * u), r * math.sin(2 * math.pi * u), -0.03 * v))
    dome = _dome(r, math.pi / 2 - 1e-9)
    co, tri, starts = _join([cyl, dome])
    axf = [0, starts[1], 0, starts[1], starts[2] - starts[1], 0]
    o, d, rr, k = fc.face_frames(co, tri, [0, 0, 0, 0, 0, 1, r], axf, starts)
    assert set(np.unique(k[:starts[1]])) <= {1.0, -1.0}
    assert (np.abs(k[starts[1]:]) == 3).all()


# ---------------------------------------------------------------------------------------------------------------
# the importer: spheres give their axis
# ---------------------------------------------------------------------------------------------------------------


def test_importer_face_axis_on_spheres():
    pytest.importorskip("OCP")
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeSphere
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    from fresing_render.importer import step_reader as sr
    assert sr.CACHE_VERSION == 7
    occ = sr._occ()

    def sphere_face(shape):
        e = TopExp_Explorer(shape, TopAbs_FACE)
        while e.More():
            f = TopoDS.Face(e.Current())
            if occ["BRepAdaptor_Surface"](f, True).GetType() == occ["GeomAbs_SurfaceType"].GeomAbs_Sphere:
                return f
            e.Next()
        raise AssertionError("no sphere face")

    c = np.array([1.0, 2.0, 3.0])
    # a cap round the CAD's own pole: its axis = the pole axis
    cap = sphere_face(BRepPrimAPI_MakeSphere(gp_Ax2(gp_Pnt(*c), gp_Dir(0, 0, 1)), 10.0, math.radians(60),
                                             math.radians(90)).Shape())
    o, d, r = sr._face_axis(occ, cap)
    assert np.allclose(o, c) and np.allclose(np.abs(d), (0, 0, 1)) and r == pytest.approx(10.0)
    pts = np.array([c + 10 * np.array([math.cos(p) * math.cos(t), math.cos(p) * math.sin(t), math.sin(p)])
                    for p in (1.1, 1.3, 1.5) for t in np.linspace(0, 6, 8)])
    o, d, r = sr._face_axis(occ, cap, pts)
    assert np.allclose(d, (0, 0, 1), atol=1e-9)                  # near the pole: the CAD's exact axis
    # a cap whose middle lies 90° off the CAD's pole (a dome made by turning a sphere): its axis points at its middle
    side = np.array([c + 10 * np.array([math.cos(t) * math.cos(p), math.sin(t) * math.cos(p), math.sin(p)])
                     for p in np.linspace(-0.3, 0.3, 4) for t in np.linspace(-0.3, 0.3, 4)])
    o, d, r = sr._face_axis(occ, cap, side)
    assert np.allclose(o, c) and np.dot(d, (1, 0, 0)) > 0.99
    # a whole ball: its middle is its centre: the CAD's pole axis
    ball = sphere_face(BRepPrimAPI_MakeSphere(gp_Pnt(*c), 5.0).Shape())
    allpts = np.array([c + 5 * np.array([math.cos(p) * math.cos(t), math.cos(p) * math.sin(t), math.sin(p)])
                       for p in np.linspace(-1.4, 1.4, 7) for t in np.linspace(0, 2 * math.pi, 12, endpoint=False)])
    o, d, r = sr._face_axis(occ, ball, allpts)
    assert np.allclose(o, c) and abs(np.linalg.norm(d) - 1) < 1e-9 and r == pytest.approx(5.0)
    # odd points: empty / one / NaN: no crash, an axis or None
    for p in (np.zeros((0, 3)), c[None] + (0, 0, 10.0)):
        got = sr._face_axis(occ, cap, p)
        assert got is not None and _finite(*got)


# ---------------------------------------------------------------------------------------------------------------
# in Blender
# ---------------------------------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def blender():
    bpy = pytest.importorskip("bpy")
    import addon_utils

    import fresing_render
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield bpy
    fresing_render.unregister()


def _mat(bpy, name, mid, colour="", wear=0.0, rust=0.0, finish=""):
    from fresing_render.blender import materials
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    materials.build_nodes(m, mid, colour, wear, finish=finish, rust=rust)
    return m


def _count(m, kind):
    return sum(1 for n in m.node_tree.nodes if n.type == kind)


def _sig(m):
    """What a node tree is made of: node types and links (positions and names left out)."""
    types = sorted(n.bl_idname for n in m.node_tree.nodes)
    return types, len(m.node_tree.links)


def _all_cases():
    """(material, finish key) for every library material, every finish with each Metal / Kind."""
    out = []
    for mid in ml.MATERIALS:
        f = fc.get(mid)
        if not f:
            out.append((mid, ""))
            continue
        for b in f.get("bases") or (None,):
            for k in f.get("kinds") or (None,):
                out.append((mid, fc.key(mid, base=b, kind=k)))
    return out


def test_rust_in_every_material_only_where_logical(blender):
    """Every look built with Rust 0.6: the rust node only where ``rust_kind`` says so; ``fr_rust`` 0 elsewhere."""
    bpy = blender
    from fresing_render.blender import materials, rust
    for mid, fin in _all_cases():
        if mid == "from_file":
            continue
        colour = "RAL 5010" if ml.needs_color(mid) else ""
        m = _mat(bpy, "ind all", mid, colour, rust=0.6, finish=fin)
        rk = materials.rust_kind_of(mid, fc.parse(mid, fin) if fc.get(mid) else {})
        has = m.node_tree.nodes.get(rust.NODE_MASK) is not None
        if rk:
            assert has and m[rust.PROP] == pytest.approx(0.6), (mid, fin, rk)
        else:
            assert not has and m[rust.PROP] == 0.0, (mid, fin)
        for never in NEVER:
            if never in mid or never.upper() in fin:
                assert not has, (mid, fin)


def test_rust_zero_adds_no_nodes(blender):
    bpy = blender
    for mid, fin in _all_cases():
        if mid == "from_file":
            continue
        colour = "RAL 5010" if ml.needs_color(mid) else ""
        for wear in (0.0, 0.5):
            a = _sig(_mat(bpy, "ind z0", mid, colour, wear=wear, finish=fin))
            b = _sig(_mat(bpy, "ind z1", mid, colour, wear=wear, rust=0.0, finish=fin))
            assert a == b, (mid, fin, wear)
    # and on a material that never rusts, any Rust is the same as none
    for mid in ("stainless_brushed", "aluminium_machined", "brass", "copper", "rubber_black", "glass_clear"):
        assert _sig(_mat(bpy, "ind n0", mid)) == _sig(_mat(bpy, "ind n1", mid, rust=1.0)), mid


def test_wear_and_rust_share_one_ambient_occlusion(blender):
    bpy = blender
    for mid, colour in (("steel_raw", ""), ("cast_iron", ""), ("paint_satin", "RAL 3000"), ("galvanized", ""),
                        ("zinc_plated", ""), ("chrome_rod", ""), ("spangle", ""), ("shot_blasted", ""),
                        ("powder_coat", "RAL 7016")):
        for wear in (0.0, 0.3, 1.0):
            for r in (0.0, 0.01, 0.5, 1.0):
                m = _mat(bpy, "ind ao", mid, colour, wear=wear, rust=r)
                assert _count(m, "AMBIENT_OCCLUSION") <= 1, (mid, wear, r)
                assert _count(m, "BEVEL") <= 1, (mid, wear, r)
    m = _mat(bpy, "ind ao2", "steel_raw", wear=0.5, rust=0.5)
    assert _count(m, "AMBIENT_OCCLUSION") == 1


def test_rust_nodes_have_no_dangling_ends(blender):
    """Every node made for the rust feeds the output (nothing built and left unused)."""
    bpy = blender
    for mid, colour, wear in (("steel_raw", "", 0.0), ("paint_satin", "RAL 5010", 0.0), ("galvanized", "", 0.0),
                              ("chrome", "", 0.0), ("paint_satin", "RAL 5010", 0.4), ("cast_iron", "", 0.4)):
        m = _mat(bpy, "ind dangle", mid, colour, wear=wear, rust=0.5)
        nt = m.node_tree
        outs = [n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"]
        seen, todo = set(), list(outs)
        while todo:
            n = todo.pop()
            if n.name in seen:
                continue
            seen.add(n.name)
            for s in n.inputs:
                for lk in s.links:
                    todo.append(lk.from_node)
        unused = [n.name for n in nt.nodes if n.name not in seen and n.type not in ("FRAME", "REROUTE")]
        assert not unused, (mid, wear, unused)


def test_is_current_with_and_without_rust(blender):
    bpy = blender
    from fresing_render.blender import materials, rust
    m = _mat(bpy, "ind cur", "steel_raw", rust=0.0)
    assert materials.is_current(m, "steel_raw", "", 0.0, "", 0.0)
    assert not materials.is_current(m, "steel_raw", "", 0.0, "", 0.2)
    m = _mat(bpy, "ind cur", "steel_raw", rust=0.2)
    assert materials.is_current(m, "steel_raw", "", 0.0, "", 0.2)
    assert not materials.is_current(m, "steel_raw", "", 0.0, "", 0.0)
    # an older material without the property (made before the slider) is current at Rust 0, not at another value
    m = _mat(bpy, "ind old", "steel_raw")
    del m[rust.PROP]
    assert materials.is_current(m, "steel_raw", "", 0.0, "", 0.0)
    assert not materials.is_current(m, "steel_raw", "", 0.0, "", 0.5)
    m = _mat(bpy, "ind old ss", "stainless_brushed")
    del m[rust.PROP]
    assert materials.is_current(m, "stainless_brushed", "", 0.0, "", 0.0)
    assert materials.is_current(m, "stainless_brushed", "", 0.0, "", 0.5)      # never rusts: nothing to rebuild
    # a finish whose Metal decides
    fin_st = fc.key("tread", base="STEEL")
    fin_al = fc.key("tread", base="ALUMINIUM")
    m = _mat(bpy, "ind tread", "tread", rust=0.4, finish=fin_st)
    assert materials.is_current(m, "tread", "", 0.0, fin_st, 0.4)
    m = _mat(bpy, "ind tread al", "tread", rust=0.4, finish=fin_al)
    assert m[rust.PROP] == 0.0 and materials.is_current(m, "tread", "", 0.0, fin_al, 0.9)


def _marked(mat):
    n = mat.node_tree.nodes.new("NodeReroute")
    n.name = "ind marker"
    return lambda: mat.node_tree.nodes.get("ind marker") is not None


@pytest.mark.parametrize("rust_value", [0.0, 0.3, 1.0, 1.5, -0.5, 7.0])
def test_ensure_material_does_not_rebuild_the_same_look(blender, rust_value):
    """Asked again for the same look, ``ensure_material`` keeps the material (a rebuild on every redraw or every
    group refresh would be slow): also for a Rust outside 0 … 1 (a script, an old file), which it clamps."""
    from fresing_render.blender import materials
    mat = materials.ensure_material(f"ind ensure {rust_value}", "steel_raw", "", 0.0, "", rust_value)
    still = _marked(mat)
    materials.ensure_material(f"ind ensure {rust_value}", "steel_raw", "", 0.0, "", rust_value)
    assert still(), rust_value


def test_the_group_slider_through_its_values(blender):
    bpy = blender
    from fresing_render.blender import logic, materials, rust
    sc = bpy.data.scenes.new("ind rust group")
    try:
        s = sc.fresing
        g = logic.ensure_group(s, "Ind steel frame")
        g.material = "steel_raw"

        def mat():
            return bpy.data.materials[materials.material_name(g.name)]

        assert mat()[rust.PROP] == 0.0 and mat().node_tree.nodes.get(rust.NODE_MASK) is None
        for v, want in ((0.001, 0.001), (1.0, 1.0), (0.5, 0.5), (5.0, 1.0), (-1.0, 0.0)):
            g.rust = v
            assert g.rust == pytest.approx(want)
            assert mat()[rust.PROP] == pytest.approx(want, abs=1e-6), v
            assert (mat().node_tree.nodes.get(rust.NODE_MASK) is not None) == (want > 0), v
        g.rust = 0.6
        assert materials.group_rust_kind(g) == "BARE"
        # stainless and back: the slider's value is kept, the look follows
        g.material = "stainless_brushed"
        assert materials.group_rust_kind(g) == "" and materials.group_no_rust_why(g)
        assert mat()[rust.PROP] == 0.0 and mat().node_tree.nodes.get(rust.NODE_MASK) is None
        g.material = "steel_raw"
        assert mat()[rust.PROP] == pytest.approx(0.6) and mat().node_tree.nodes.get(rust.NODE_MASK) is not None
        # cast iron, painted, galvanized, chrome rod: rust; aluminium, brass, copper, glass, plastic: not
        for mid, rk in (("cast_iron", "BARE"), ("paint_satin", "PAINTED"), ("galvanized", "ZINC"),
                        ("chrome_rod", "PLATED"), ("aluminium_anodized", ""), ("brass", ""), ("copper", ""),
                        ("glass_clear", ""), ("plastic_matte", ""), ("from_file", "")):
            g.material = mid
            assert materials.group_rust_kind(g) == rk, mid
            if mid != "from_file":
                assert (mat()[rust.PROP] > 0) == bool(rk), mid
            if not rk:
                assert materials.group_no_rust_why(g), mid
        # a finish whose Metal changes
        g.material = "tread"
        for base, rk in (("STEEL", "BARE"), ("ALUMINIUM", ""), ("GALVANIZED", "ZINC"), ("STEEL", "BARE")):
            g.fin_base = base
            assert materials.group_rust_kind(g) == rk, base
            assert (mat()[rust.PROP] > 0) == bool(rk), base
            assert (mat().node_tree.nodes.get(rust.NODE_MASK) is not None) == bool(rk), base
        # sand-cast: its Kind decides
        g.material = "as_cast"
        g.fin_kind = "CAST_FE"
        assert materials.group_rust_kind(g) == "BARE" and mat()[rust.PROP] > 0
        g.fin_kind = "CAST_AL"
        assert materials.group_rust_kind(g) == "" and mat()[rust.PROP] == 0.0
        assert "alumin" in materials.group_no_rust_why(g).lower()
        # a finish with a Metal left on STEEL, then a plain stainless look: no rust from the old Metal
        g.material = "knurl_diamond"
        g.fin_base = "STEEL"
        assert materials.group_rust_kind(g) == "BARE"
        g.material = "stainless_polished"
        assert materials.group_rust_kind(g) == "" and mat()[rust.PROP] == 0.0
        assert materials.rust_kind_of("stainless_brushed", {"base": "STEEL"}) == ""
        assert materials.rust_kind_of("aluminium_machined", {"base": "CAST_IRON"}) == ""
    finally:
        bpy.data.scenes.remove(sc)


def test_draw_rust_row(blender):
    """The 3 Looks box: the slider where it rusts, the reason (in the same row) where not."""
    bpy = blender
    from fresing_render.blender import logic, ui

    class Row:
        def __init__(self, log):
            self.log, self.active = log, True

        def label(self, text="", icon="NONE"):
            self.log.append(("label", text))

    class Col:
        def __init__(self):
            self.log = []

        def prop(self, data, name, **kw):
            self.log.append(("prop", name))

        def row(self, **kw):
            return Row(self.log)

    sc = bpy.data.scenes.new("ind draw")
    try:
        g = logic.ensure_group(sc.fresing, "Ind draw")
        for mid, slider in (("steel_raw", True), ("stainless_brushed", False), ("aluminium_machined", False),
                            ("galvanized", True), ("brass", False)):
            g.material = mid
            col = Col()
            ui.draw_rust(col, g)
            assert len(col.log) == 1
            if slider:
                assert col.log[0] == ("prop", "rust"), mid
            else:
                assert col.log[0][0] == "label" and "rust" in col.log[0][1].lower(), mid
    finally:
        bpy.data.scenes.remove(sc)


def test_carbon_and_perlage_build_for_every_setting(blender):
    bpy = blender
    from fresing_render.blender import finishes
    for kind in ("TWILL", "PLAIN"):
        for gloss in (0.0, 0.25, 1.0):
            for size in (0.001, 0.002, 0.008, 0.0001, 1.0):
                fin = fc.key("carbon_fibre", kind=kind, amount=gloss, size=size)
                m = _mat(bpy, "ind carbon", "carbon_fibre", finish=fin, wear=0.3, rust=0.8)
                bsdf = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
                assert bsdf.inputs["Coat Roughness"].default_value == pytest.approx(0.03 + (1 - gloss) * 0.32)
                assert m["fr_rust"] == 0.0 and m.get(finishes.PROP_FINISH) == "carbon_fibre"
                names = {n.attribute_name for n in m.node_tree.nodes if n.type == "ATTRIBUTE"}
                assert {"fr_cw_a", "fr_cw_b", "fr_fx_k"} <= names
                assert finishes.needs_faces(m)
    for base in fc.FINISHES["perlage"]["bases"]:
        for size in (0.0015, 0.004, 0.012):
            m = _mat(bpy, "ind perlage", "perlage", finish=fc.key("perlage", base=base, size=size), rust=0.5)
            assert m["fr_rust"] == 0.0 and finishes.needs_faces(m)
            web = finishes.web_numbers(m)
            assert web["mode"] == "average" and len(web["color"]) == 3
            bsdf = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
            assert bsdf.inputs["Tangent"].is_linked


def test_old_projects_carbon_face_data_is_written_again(blender):
    """A mesh with 0274's face data (fr_fx_*, no fr_cw_*) is not taken as ready for carbon."""
    bpy = blender
    from fresing_render.blender import finishes
    me = bpy.data.meshes.new("ind old fx")
    me.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 1, 2)])
    finishes.prepare_faces(me)
    assert finishes.has_faces(me)
    me.attributes.remove(me.attributes["fr_cw_a"])
    assert not finishes.has_faces(me)
    assert finishes.ensure_faces(me) and finishes.has_faces(me)
    bpy.data.meshes.remove(me)


# ---------------------------------------------------------------------------------------------------------------
# the finishes test model through the app
# ---------------------------------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def board(blender, tmp_path_factory):
    from fresing_render.blender import tour
    sc = tour._fresh((FINISHES_STEP,), str(tmp_path_factory.mktemp("ind_finishes")))
    groups = tour.finishes_demo(sc)
    return blender, sc, groups


def _attr(me, name):
    at = me.attributes[name]
    n = len(me.polygons) * (3 if at.data_type == "FLOAT_VECTOR" else 1)
    a = np.empty(n, np.float32)
    at.data.foreach_get("vector" if at.data_type == "FLOAT_VECTOR" else "value", a)
    return a.reshape(len(me.polygons), -1) if at.data_type == "FLOAT_VECTOR" else a


def _parts(sc):
    from fresing_render.blender import build
    return {ob.get(build.PROP_NAME, ""): ob for ob in build.iter_parts(sc)}


def test_board_every_face_attribute_finite(board):
    _bpy, sc, _g = board
    from fresing_render.blender import finishes
    n = 0
    for name, ob in _parts(sc).items():
        me = ob.data
        if not finishes.has_faces(me):
            continue
        n += 1
        for a in finishes.FX_NAMES:
            v = _attr(me, a)
            assert np.all(np.isfinite(v)), (name, a)
        a = _attr(me, "fr_cw_a")
        assert np.allclose(np.hypot(a[:, 0], a[:, 1]), 1.0, atol=1e-5), name
        assert set(np.unique(a[:, 2])) <= {1.0, -1.0}, name
        k = _attr(me, "fr_fx_k")
        assert set(np.unique(k)) <= {-3.0, -1.0, 0.0, 1.0, 2.0, 3.0}, (name, np.unique(k))
    assert n >= 5


def test_board_carbon_cup_outer_and_inner_sphere(board):
    _bpy, sc, _g = board
    ob = _parts(sc)["CUP CARBON"]
    me = ob.data
    k = _attr(me, "fr_fx_k")
    r = _attr(me, "fr_fx_r")
    o = _attr(me, "fr_fx_o")
    d = _attr(me, "fr_fx_d")
    outer, inner = k == 3, k == -3
    assert outer.any() and inner.any(), np.unique(k)
    assert np.allclose(r[outer], 0.037, rtol=0.01), np.unique(r[outer])
    assert np.allclose(r[inner], 0.0345, rtol=0.01), np.unique(r[inner])
    # one centre for both, the outer sphere's normals point away from it, the inner's towards it
    assert np.allclose(o[outer], o[outer][0], atol=1e-6) and np.allclose(o[inner], o[outer][0], atol=2e-5)
    co = np.array([v.co for v in me.vertices])
    tri = np.array([p.vertices[:3] for p in me.polygons])
    nrm = _normals(co, tri)
    cen = co[tri].mean(1)
    assert np.sum(np.einsum("ij,ij->i", nrm[outer], cen[outer] - o[outer])) > 0
    assert np.sum(np.einsum("ij,ij->i", nrm[inner], cen[inner] - o[inner])) < 0
    # the pole: from the centre towards the dome's middle (the flat land's side)
    mid = cen[outer].mean(0)
    pole = d[outer][0]
    assert np.allclose(d[outer], pole, atol=1e-5) and np.dot(mid - o[outer][0], pole) > 0
    # the weave: the spheres keep their own frame
    a = _attr(me, "fr_cw_a")
    b = _attr(me, "fr_cw_b")
    assert np.allclose(a[outer | inner], (1, 0, 1)) and np.allclose(b[outer | inner], 0)


def test_board_cap_dome_is_a_sphere_with_its_axis(board):
    _bpy, sc, _g = board
    parts = _parts(sc)
    me = parts["CAP SPUN"].data
    k = _attr(me, "fr_fx_k")
    r = _attr(me, "fr_fx_r")
    d = _attr(me, "fr_fx_d")
    o = _attr(me, "fr_fx_o")
    dome = (np.abs(k) == 3) & (np.abs(r - 0.101) < 0.002)
    assert dome.any() and (k[dome] == 3).all(), np.unique(k)
    assert np.allclose(r[dome], 0.101, rtol=2e-3)
    # its axis runs along the cap's end faces' axis (the revolve axis)
    ends = k == 2
    assert ends.any()
    assert abs(float(np.dot(d[dome][0], d[ends][0]))) > 0.999
    # its centre lies on that axis, 101 mm below the dome's top
    co = np.array([v.co for v in me.vertices])
    top = co @ d[dome][0]
    assert float(top.max() - np.dot(o[dome][0], d[dome][0])) == pytest.approx(0.101, abs=2e-4)


def test_board_folded_panel_weave_runs_on_through_every_bend(board):
    """The app's own folded carbon panel (a U of sheet 2 mm thick, bends R 6 inside / R 8 outside): a real panel's
    outer and inner skins are each one ply, smooth through the bends – the weave must run on across every line where a
    bend meets a flat smoothly (tangent), on the outside AND the inside."""
    _bpy, sc, _g = board
    me = _parts(sc)["PANEL CARBON"].data
    a, b, k = _attr(me, "fr_cw_a"), _attr(me, "fr_cw_b"), _attr(me, "fr_fx_k")
    o, d, r = _attr(me, "fr_fx_o"), _attr(me, "fr_fx_d"), _attr(me, "fr_fx_r")
    co = np.array([v.co for v in me.vertices], float)
    tri = np.array([p.vertices[:3] for p in me.polygons])
    starts = list(me["fr_face_starts"])
    frames = tuple(x.astype(float) for x in (o, d, r, k, a, b))
    nrm = _normals(co, tri)
    rounds = [f for f in range(len(starts) - 1) if abs(k[starts[f]]) == 1]
    assert len(rounds) == 4, [float(k[starts[f]]) for f in range(len(starts) - 1)]

    def normal_at(f, pts):
        """The mean normal of face f's triangles that touch these points."""
        sl = slice(starts[f], starts[f + 1])
        near = np.zeros(starts[f + 1] - starts[f], bool)
        for p in pts:
            near |= (np.linalg.norm(co[tri[sl]] - p, axis=2) < 1e-7).any(1)
        n = nrm[sl][near].mean(0)
        return n / np.linalg.norm(n)

    misses, smooth = [], 0
    for (i, j), pts in _shared_edges(co, tri, starts).items():
        if len(pts) < 2 or not ((i in rounds) ^ (j in rounds)):
            continue
        if np.linalg.matrix_rank(pts - pts.mean(0), tol=1e-6) > 1:
            continue                                            # a bend's curved end against the profile face
        if np.dot(normal_at(i, pts), normal_at(j, pts)) < 0.95:
            continue                                            # a sharp edge (the sheet's thickness)
        smooth += 1
        gi, gj = _glob(frames, starts[i], pts), _glob(frames, starts[j], pts)
        miss = float(np.abs(gi - gj).max())
        if miss > 5e-5:
            misses.append(((i, j), round(miss * 1000, 2)))
    assert smooth == 8, smooth                                  # 4 bends x 2 flats each
    assert not misses, f"the weave jumps (mm) where a bend meets a flat smoothly: {misses}"


def test_board_parts_without_spheres_have_no_sphere_faces(board):
    """Parts made only of planes, cylinders and cones (chamfered) keep 0274's face kinds: no face is taken for a
    sphere (a knurled knob's chamfers stay round, the faced shaft's chamfers too, the cap has ONE sphere: its dome)."""
    _bpy, sc, _g = board
    parts = _parts(sc)
    found = {}
    for name in ("KNOB DIAMOND KNURL", "KNOB STRAIGHT KNURL", "SHAFT FACED", "BUSHING HONED", "GRIP HANDLE",
                 "TUBE CARBON", "PANEL CARBON", "DISC PERLAGE"):
        me = parts[name].data
        if "fr_fx_k" not in me.attributes:
            continue
        k = _attr(me, "fr_fx_k")
        starts = list(me["fr_face_starts"])
        n = sum(1 for f in range(len(starts) - 1) if abs(k[starts[f]]) == 3)
        if n:
            found[name] = n
    me = parts["CAP SPUN"].data
    k, starts = _attr(me, "fr_fx_k"), list(me["fr_face_starts"])
    caps = sum(1 for f in range(len(starts) - 1) if abs(k[starts[f]]) == 3)
    if caps != 1:
        found["CAP SPUN"] = caps
    assert not found, f"faces taken for spheres (cones / chamfers): {found}"


# ---------------------------------------------------------------------------------------------------------------
# the web model and welds
# ---------------------------------------------------------------------------------------------------------------


def _bake_colour(bpy, m):
    from fresing_render.blender import web3d
    sc = bpy.data.scenes.new("ind web bake")
    sc.render.engine = "CYCLES"
    lk = web3d.Look(m)
    baker = web3d.Baker(sc)
    try:
        jobs = [(key, m, sock, web3d.KIND[ch]) for key, (ch, sock) in lk.sockets().items() if ch == "color"]
        if not jobs:
            return None
        tile = baker.tiles(jobs, 32)[jobs[0][0]]
        return tile[..., :3].reshape(-1, 3).mean(0)
    finally:
        baker.close()
        bpy.data.scenes.remove(sc)


def test_web_model_keeps_the_rust_colour_on_cast_iron(blender):
    bpy = blender
    rgb = _bake_colour(bpy, _mat(bpy, "ind web ci", "cast_iron", rust=0.9))
    assert rgb is not None and rgb[0] > rgb[1] * 1.3 > 0 and rgb[1] > rgb[2], rgb
    plain = _bake_colour(bpy, _mat(bpy, "ind web ci0", "cast_iron", wear=0.0))
    assert plain is None or abs(plain[0] - plain[2]) < 0.05 * max(plain[0], 1e-6) + 0.01, plain


def _weld_scene(bpy):
    import addon_utils
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    assert bpy.ops.fresing.import_step(filepath=WELDMENT, quality="draft") == {"FINISHED"}
    return bpy.context.scene


def test_welds_follow_the_group_rust_and_stainless_welds_do_not(blender):
    bpy = blender
    from fresing_render.blender import build, weld_looks, welds
    sc = _weld_scene(bpy)

    def part(name):
        return next(o for o in build.iter_parts(sc) if o[build.PROP_NAME] == name)

    def bead_rust(it):
        ob = welds._object(it, False)
        return json.loads(ob.data.materials[0][weld_looks.TAG])

    fin, gusset = part("FIN"), part("GUSSET")
    g = sc.fresing.groups[fin[build.PROP_GROUP]]
    it = welds.make(sc, fin, [], gusset, [], whole=True)
    key = it.key
    it.finish, it.metal, it.process, it.rust = "AS_WELDED", "STEEL", "MAG", 0.0
    it = welds.find_item(sc, key)
    g.material = "steel_raw"
    g.rust = 0.0
    welds.follow_rust(sc)
    assert bead_rust(welds.find_item(sc, key))["rust"] == 0.0
    g.rust = 0.7
    assert welds.follow_rust(sc) >= 1
    got = bead_rust(welds.find_item(sc, key))
    assert got["rust"] > 0.0, got
    assert welds.follow_rust(sc) == 0                            # nothing more to do
    # the group turns stainless: its welds lose the rust again
    g.material = "stainless_brushed"
    welds.follow_rust(sc)
    assert bead_rust(welds.find_item(sc, key))["rust"] == 0.0
    # a stainless weld on a rusty steel group: no red rust on the bead or its heat zone
    g.material = "steel_raw"
    g.rust = 0.9
    it = welds.find_item(sc, key)
    it.metal, it.process = "STAINLESS", "TIG"
    welds.follow_rust(sc)
    it = welds.find_item(sc, key)
    assert bead_rust(it)["rust"] == 0.0
    heat = json.loads(welds._object(it, True).data.materials[0][weld_looks.TAG])
    assert heat["rust"] == 0.0
    # an aluminium weld: none either
    it.metal, it.process = "ALUMINIUM", "MIG"
    welds.follow_rust(sc)
    assert bead_rust(welds.find_item(sc, key))["rust"] == 0.0
