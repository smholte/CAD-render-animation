"""Task 0323: welds from the CAD file – the finder without Blender (core/weld_cad.py) on the three exports of the
CAD-weld frame (tools/make_test_weldment.py --cad), look-alikes, names, metals, pieces that join one or three parts."""

from __future__ import annotations

import math
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))

import weld_cad_models as models  # noqa: E402
from fresing_render.core import weld_cad  # noqa: E402
from fresing_render.core import welds as core  # noqa: E402

import make_test_weldment as maker  # noqa: E402

HALF_MM = 0.0005 + 1e-9


@pytest.fixture(scope="module")
def tmp(tmp_path_factory):
    return str(tmp_path_factory.mktemp("weld_cad"))


def _by_pair(found, meshes):
    out = {}
    for f in found:
        a = meshes[f.part_a].name if f.part_a else None
        b = meshes[f.part_b].name if f.part_b else None
        out.setdefault((a, b), []).append(f)
    return out


def _expected(table):
    return {(a, b): [w for w in table if (w[1], w[2]) == (a, b)] for _n, a, b, *_r in table}


def _check(found, meshes, table):
    pairs = _by_pair(found, meshes)
    exp = _expected(table)
    assert set(pairs) == set(exp), (sorted(pairs), sorted(exp))
    for pair, ws in exp.items():
        got = sorted(pairs[pair], key=lambda f: (f.intermittent is not None, f.length))
        want = sorted(ws, key=lambda w: (w[7] is not None, w[5]))
        assert len(got) == len(want), (pair, [weld_cad.describe(f) for f in got])
        for f, (_n, _a, _b, kind, size, length, closed, inter) in zip(got, want):
            what = (pair, weld_cad.describe(f))
            assert f.kind == kind, what
            assert abs(f.size * 1000 - size) <= 0.5, what
            assert f.closed == closed, what
            if inter is None:
                assert f.intermittent is None, what
                assert abs(f.length * 1000 - length) <= 0.5, what
            else:
                n, piece, pitch = f.intermittent
                assert n == inter[0] and abs(piece * 1000 - inter[1]) <= 0.5 and abs(pitch * 1000 - inter[2]) <= 0.5, what


@pytest.mark.parametrize("kind", ["inventor", "creo", "unnamed"])
def test_the_three_exports_give_the_same_welds(kind, tmp):
    found, meshes = models.detect(kind, tmp)
    _check(found, meshes, maker.CAD_WELDS)
    how = {f.how for f in found}
    assert how == ({"shape"} if kind == "unnamed" else {"name"})
    # no look-alike is in a weld, as a bead or as a part it joins
    for f in found:
        assert meshes[f.body].name not in maker.LOOK_ALIKES
        assert not {meshes[k].name for k in f.parts} & set(maker.LOOK_ALIKES), weld_cad.describe(f)


def test_the_inventor_welds_body_is_split_per_weld(tmp):
    found, meshes = models.detect("inventor", tmp)
    assert {meshes[f.body].name for f in found} == {"Welds"}
    pieces = sum(f.pieces for f in found)
    assert pieces == 9                                   # 6 welds, one of them 4 pieces
    body = next(m for m in meshes.values() if m.name == "Welds")
    assert len(weld_cad.components(body.points, body.tris)) == 9
    used = np.concatenate([f.tris for f in found])
    assert len(np.unique(used)) == len(used) == len(body.tris)      # every triangle in exactly one weld


def test_sizes_in_detail(tmp):
    found, meshes = models.detect("inventor", tmp)
    pairs = _by_pair(found, meshes)
    stiff = pairs[("BOTTOM PLATE", "STIFFENER")][0]
    assert abs(stiff.legs[0] - 0.010) <= HALF_MM and abs(stiff.legs[1] - 0.006) <= HALF_MM
    assert stiff.note == "legs 10 × 6 mm"
    assert abs(stiff.size - 0.004) <= 1e-9               # 6 · cos 45° = 4.24 -> 4.0
    fin = [f for f in pairs[("BOTTOM PLATE", "RIB")] if f.intermittent is None][0]
    assert abs(fin.legs[0] - 5 * math.sqrt(2) / 1000) < 0.0002 and fin.note == ""
    groove = pairs[("BOTTOM PLATE", "END PLATE")][0]
    assert groove.kind == "BUTT" and abs(groove.size - 0.0155) <= HALF_MM
    # the groove's line lies on the plates' faces (z = 12 mm), where the app's butt weld lies
    z = groove.seams[0].points[:, 2]
    assert np.allclose(z, 0.012, atol=0.0002)
    c = groove.seams[0].corners[0]
    assert c.theta == 180.0 and c.na[2] > 0.99 and abs(c.da[0]) > 0.99
    square = pairs[("BOTTOM PLATE", "BOX POST")][0]
    assert len(square.seams) == 4 and square.closed      # one bead round the four corners
    ring = pairs[("BOTTOM PLATE", "TUBE")][0]
    assert len(ring.seams) == 1 and ring.seams[0].closed


def test_metal_from_the_cad_material(tmp):
    found, _m = models.detect("inventor", tmp)
    assert {f.metal for f in found} == {"STEEL"}         # "Welded Steel Mild"
    found, _m = models.detect("creo", tmp)
    assert {f.metal for f in found} == {""}              # no material in the file: from the parts
    for name, metal in (("Welded Steel Mild", "STEEL"), ("Welded Aluminum-6061", "ALUMINIUM"),
                        ("Welded Stainless Steel", "STAINLESS"), ("Stainless Steel, Austenitic", "STAINLESS"),
                        ("1.4301", "STAINLESS"), ("AISI 316L", "STAINLESS"), ("AlMg3", "ALUMINIUM"),
                        ("Aluminium 6082", "ALUMINIUM"), ("S355J2", "STEEL"), ("Staal", "STEEL"), ("Stahl", "STEEL"),
                        ("Generic", ""), ("", ""), ("Rubber", "")):
        assert weld_cad.metal_of_material(name) == metal, name


@pytest.mark.parametrize("name", ["Welds", "Weld", "Weld Bead", "Weld Bead 3", "WELD_1", "Fillet Weld 2",
                                  "Groove weld", "weld-bead", "Lasnaad", "Lasnaden 2", "Hoeklasnaad", "Schweißnaht",
                                  "Schweissnaht 4", "Kehlschweißnaht", "Schweißnähte", "Soudure", "Soudures 2",
                                  "Saldatura", "Soldadura 1", "Welds:1"])
def test_weld_names(name):
    assert weld_cad.weld_name(name)


@pytest.mark.parametrize("name", ["Weld nut M8", "Schweißmutter M10", "Lasmoer M6", "Weldment1", "Weldment",
                                  "Welded frame", "Welded Assembly", "Weld-on hinge", "Weld stud M6", "Weld neck flange",
                                  "Welding table", "Bead", "Bead blasted cover", "Body 14", "Solid1", "PLATE",
                                  "Schweißkonstruktion", "Lasconstructie", "Weld plate", ""])
def test_not_weld_names(name):
    assert not weld_cad.weld_name(name)


def test_look_alikes_fail_the_full_shape_check(tmp):
    """Every part of the unnamed export put through the full check (not only those the quick look lets through): only
    the beads come out."""
    ms, _by = models.meshes("unnamed", tmp)
    found = weld_cad.find(ms, ms, set())
    names = {next(m.name for m in ms if m.key == f.body) for f in found}
    assert names == {f"BODY {k}" for k in (1, 2, 6, 7, 8, 9)}   # 2 = the first of the intermittent pieces 2 … 5
    assert sum(f.pieces for f in found) == 9


def test_quick_look_lets_only_thin_bodies_through(tmp):
    ms, _by = models.meshes("unnamed", tmp)
    passed = {m.name for m in ms if weld_cad.maybe_bead(m)}
    assert {f"BODY {k}" for k in range(1, 10)} <= passed
    assert not passed & {"BOTTOM PLATE", "END PLATE", "RIB", "TUBE", "BOX POST", "STIFFENER", "WALL", "FOOT"}


def test_revision_b_and_matching(tmp):
    old, om = models.detect("inventor", tmp)
    new, nm = models.detect("inventor_b", tmp)
    _check(new, nm, maker.CAD_WELDS_B)

    def rows(fs, ms):
        return [(ms[f.part_a].name, ms[f.part_b].name, weld_cad.line_points(f.seams)) for f in fs]
    pairs = weld_cad.match(rows(old, om), rows(new, nm))
    got = {}
    for i, j in pairs:
        got[weld_cad.describe(old[i])] = None if j is None else weld_cad.describe(new[j])
    lost = [k for k, v in got.items() if v is None]
    assert lost == ["fillet a4, 240 mm, all round"]       # the square post's weld is gone
    assert got["fillet a5, 200 mm"] == "fillet a5, 150 mm"   # the shorter fin weld is that weld again
    assert len({j for _i, j in pairs if j is not None}) == 5  # the new stiffener weld matches nothing: new


def _box(x0, y0, z0, x1, y1, z1, start=0):
    """A box as the importer gives it: every face its own 4 points, 2 triangles each."""
    c = np.array([[x, y, z] for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)], float)
    quads = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    pts, tris, face = [], [], []
    for f, q in enumerate(quads):
        b = len(pts)
        pts.extend(c[list(q)])
        tris.extend([(b, b + 1, b + 2), (b, b + 2, b + 3)])
        face.extend([f, f])
    return np.array(pts), np.array(tris), np.array(face)


def _prism(profile, x0, x1):
    """A prism along x of a (y, z) polygon (counter-clockwise seen from +x), every face its own points."""
    k = len(profile)
    a = [np.array([x0, y, z]) for y, z in profile]
    b = [np.array([x1, y, z]) for y, z in profile]
    pts, tris, face = [], [], []
    f = 0
    for i in range(k):
        j = (i + 1) % k
        base = len(pts)
        pts.extend([a[i], a[j], b[j], b[i]])
        tris.extend([(base, base + 2, base + 1), (base, base + 3, base + 2)])
        face.extend([f, f])
        f += 1
    for cap, rev in ((a, True), (b, False)):
        base = len(pts)
        pts.extend(cap)
        for i in range(1, k - 1):
            tris.append((base, base + i + 1, base + i) if rev else (base, base + i, base + i + 1))
            face.append(f)
        f += 1
    return np.array(pts), np.array(tris), np.array(face)


def _mesh(key, name, geo):
    """A convex test solid, its triangles turned to face out (away from its middle)."""
    pts, tris, face = geo
    c = pts.mean(0)
    v = pts[tris]
    n = np.cross(v[:, 1] - v[:, 0], v[:, 2] - v[:, 0])
    inward = (n * (v.mean(1) - c)).sum(1) < 0
    tris = tris.copy()
    tris[inward] = tris[inward][:, ::-1]
    return weld_cad.Mesh(key, name, pts, tris, face)


def test_a_bead_on_one_part_or_three_is_kept_and_said():
    plate = _mesh("p", "PLATE", _box(0, 0, 0, 0.4, 0.3, 0.012))
    fin = _mesh("f", "FIN", _box(0.05, 0.145, 0.012, 0.25, 0.155, 0.112))
    fin2 = _mesh("g", "FIN 2", _box(0.25, 0.145, 0.012, 0.30, 0.155, 0.112))
    z = 0.005
    lone = _mesh("w1", "Weld 1", _prism([(0.20, 0.012), (0.21, 0.012), (0.20, 0.012 + z)], 0.30, 0.35))
    three = _mesh("w2", "Weld 2", _prism([(0.145, 0.012), (0.145, 0.012 + z), (0.145 - z, 0.012)], 0.10, 0.28))
    found = weld_cad.find([lone, three], [plate, fin, fin2], {"w1", "w2"})
    by = {f.body: f for f in found}
    assert by["w1"].joins == 1 and by["w1"].note == "joins 1 part" and by["w1"].kind == "OTHER"
    assert by["w2"].joins == 3 and by["w2"].note == "joins 3 parts"
    # by shape only, the bead on one part is no weld
    assert all(f.body != "w1" for f in weld_cad.find([lone, three], [plate, fin, fin2], set()))


def test_a_square_bar_in_a_corner_is_no_weld_even_with_a_seam():
    plate = _mesh("p", "PLATE", _box(0, 0, 0, 0.4, 0.3, 0.012))
    wall = _mesh("w", "WALL", _box(0.05, 0.145, 0.012, 0.25, 0.155, 0.112))
    bar = _mesh("b", "BAR", _box(0.06, 0.135, 0.012, 0.20, 0.145, 0.022))
    tri = _mesh("t", "BODY", _prism([(0.145, 0.012), (0.145, 0.022), (0.135, 0.012)], 0.06, 0.20))
    assert weld_cad.find([bar], [plate, wall], set()) == []
    got = weld_cad.find([tri], [plate, wall], set())
    assert len(got) == 1 and got[0].kind == "FILLET" and abs(got[0].size - 0.007) <= HALF_MM   # 10 · cos 45° = 7.07
    # named, the bar is kept as a weld of its own shape (a CAD user called it a weld)
    named = weld_cad.find([bar], [plate, wall], {"b"})
    assert len(named) == 1


def test_uvs_run_along_and_across(tmp):
    found, meshes = models.detect("inventor", tmp)
    body = next(m for m in meshes.values() if m.name == "Welds")
    for f in found:
        uv = weld_cad.uvs(body.points, body.tris[f.tris], f.seams, f.kind, f.size)
        assert uv.shape == (len(f.tris), 3, 2)
        assert uv[..., 1].min() >= 0.0 and uv[..., 1].max() <= 1.0
        span = uv[..., 0].max() - uv[..., 0].min()
        total = sum(weld_cad._arc(s.points, s.closed)[-1] for s in f.seams)
        assert span <= (1.5 * total if f.closed else total) + 0.02, weld_cad.describe(f)   # (a mended wrap runs on)
        assert span >= 0.5 * f.length - 0.01, weld_cad.describe(f)
        if len(f.seams) == 1 and f.seams[0].closed:     # no triangle spans more than half the ring (the wrap is mended)
            assert (uv[..., 0].max(1) - uv[..., 0].min(1)).max() < 0.5 * total + 1e-6


def test_transform_and_pack_keep_the_seams(tmp):
    found, _m = models.detect("inventor", tmp)
    M = np.eye(4)
    M[:3, :3] = np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]], float)
    M[:3, 3] = (1.0, 2.0, 3.0)
    for f in found:
        moved = weld_cad.transform(f.seams, M)
        back = weld_cad.transform(moved, np.linalg.inv(M))
        for a, b in zip(f.seams, back):
            assert np.allclose(a.points, b.points, atol=1e-9)
        again = core.unpack_seams(core.pack_seams(moved))
        assert len(again) == len(moved)
        assert abs(sum(s.length for s in again) - sum(s.length for s in moved)) < 1e-3


@pytest.mark.parametrize("name", ["test_waycover_a", "test_waycover_b", "test_waycover_c", "test_waycover_d",
                                  "test_mill_cabinet", "test_gantry", "test_sequence_frame", "test_tracks",
                                  "test_flex_chains_a", "test_crane_a", "test_weldment"])
def test_other_test_models_have_no_welds_by_shape(name, tmp):
    """No part of the app's other test models is a weld bead (way-cover flanges, sheet covers, chain links …): a flange
    strip 3 x 40 mm lying in a corner was once taken for a groove weld."""
    found, meshes = models.detect(name, tmp, step=os.path.join(models.DATA, name + ".step"))
    assert found == [], [(meshes[f.body].name, weld_cad.describe(f)) for f in found]


def test_the_search_by_shape_has_a_time_budget(tmp):
    """At an import the search for unnamed beads stops after ``SHAPE_BUDGET`` (said); named bodies are always looked
    at; Find in CAD file (budget None) looks at all."""
    ms, _by = models.meshes("unnamed", tmp)
    bodies = [m for m in ms if weld_cad.maybe_bead(m)]
    assert weld_cad.find(bodies, ms, set(), budget=0.0) == [] and weld_cad.STOPPED[0]
    assert len(weld_cad.find(bodies, ms, set(), budget=None)) == 6 and not weld_cad.STOPPED[0]
    ms, _by = models.meshes("inventor", tmp)
    named = {m.key for m in ms if weld_cad.weld_name(m.name)}
    got = weld_cad.find([m for m in ms if m.key in named], [m for m in ms if m.key not in named], named, budget=0.0)
    assert len(got) == 6
