"""Lightmap UVs and baked-light numbers (task 0107, ``core/lightmap.py``): charts never overlap (also a helical ramp
that lies over itself), meshes split at sharp edges stay one chart per face, packing, the gap between charts, texel
size, encoding, dilate / smooth, vertex-or-map, image size, speed."""

import time

import numpy as np
import pytest

from fresing_render.core import lightmap as lm


# ---------------------------------------------------------------------------
# test meshes
# ---------------------------------------------------------------------------

def box(size=(1.0, 1.0, 1.0), at=(0.0, 0.0, 0.0), split=False):
    """A box with outward triangles; ``split`` = every face has its own 4 points (as a CAD mesh split at edges)."""
    sx, sy, sz = size
    c = np.array([[x, y, z] for z in (0, sz) for y in (0, sy) for x in (0, sx)], float) + at
    quads = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]
    if not split:
        tris = [t for a, b, cc, d in quads for t in ((a, b, cc), (a, cc, d))]
        return c, np.array(tris)
    pts, tris = [], []
    for q in quads:
        n = len(pts)
        pts.extend(c[list(q)])
        tris += [(n, n + 1, n + 2), (n, n + 2, n + 3)]
    return np.array(pts), np.array(tris)


def cylinder(sides=64, r=0.5, h=1.0):
    a = np.linspace(0, 2 * np.pi, sides, endpoint=False)
    ring = np.stack([r * np.cos(a), r * np.sin(a)], 1)
    pts = np.concatenate([np.c_[ring, np.zeros(sides)], np.c_[ring, np.full(sides, h)], [[0, 0, 0], [0, 0, h]]])
    tris = []
    for i in range(sides):
        j = (i + 1) % sides
        tris += [(i, j, sides + j), (i, sides + j, sides + i), (2 * sides, j, i), (2 * sides + 1, sides + i, sides + j)]
    return pts, np.array(tris)


def u_channel():
    """A U-channel (outer side) as three plates of a sheet: bottom and two walls, both faces of each."""
    meshes = [box((1.0, 0.2, 0.01)), box((1.0, 0.01, 0.3), at=(0, 0, 0)), box((1.0, 0.01, 0.3), at=(0, 0.19, 0))]
    return merge(meshes)


def merge(meshes):
    pts, tris, n = [], [], 0
    for p, t in meshes:
        pts.append(p)
        tris.append(t + n)
        n += len(p)
    return np.concatenate(pts), np.concatenate(tris)


def helix_ramp(turns=2.0, steps=96, r0=0.2, r1=0.6, pitch=0.3):
    """The top face of a helical ramp: seen from above it lies over itself after one turn."""
    n = int(steps * turns) + 1
    a = np.linspace(0, 2 * np.pi * turns, n)
    z = a / (2 * np.pi) * pitch
    inner = np.stack([r0 * np.cos(a), r0 * np.sin(a), z], 1)
    outer = np.stack([r1 * np.cos(a), r1 * np.sin(a), z], 1)
    pts = np.concatenate([inner, outer])
    tris = []
    for i in range(n - 1):
        tris += [(i, n + i, n + i + 1), (i, n + i + 1, i + 1)]
    return pts, np.array(tris)


def sphere(nu, nv, r=1.0):
    u = np.linspace(0, 2 * np.pi, nu, endpoint=False)
    v = np.linspace(0, np.pi, nv + 1)[1:-1]
    U, V = np.meshgrid(u, v)
    pts = np.stack([r * np.sin(V) * np.cos(U), r * np.sin(V) * np.sin(U), r * np.cos(V)], -1).reshape(-1, 3)
    pts = np.concatenate([pts, [[0, 0, r], [0, 0, -r]]])
    idx = np.arange(len(v) * nu).reshape(len(v), nu)
    a, b = idx[:-1], np.roll(idx, -1, 1)[:-1]
    c, d = idx[1:], np.roll(idx, -1, 1)[1:]
    tris = [np.stack([a, c, d], -1).reshape(-1, 3), np.stack([a, d, b], -1).reshape(-1, 3)]
    top, bot = len(pts) - 2, len(pts) - 1
    tris.append(np.stack([np.full(nu, top), idx[0], np.roll(idx[0], -1)], 1))
    tris.append(np.stack([np.full(nu, bot), np.roll(idx[-1], -1), idx[-1]], 1))
    return pts, np.concatenate(tris)


def check(points, tris, tpm=60.0, padding=4, copies=1):
    """Unwrap, pack ``copies`` and place them: returns (unwrap, per-copy uv, per-copy atlas index, overlaps)."""
    un = lm.unwrap(points, tris)
    sz = lm.chart_pixels(un.size, tpm, padding)
    places = lm.pack([sz] * copies)
    uvs, ais = zip(*[lm.place_uv(un, tpm, pl, padding) for pl in places])
    uv = np.concatenate(uvs)
    ai = np.concatenate(ais)
    chart = np.concatenate([un.chart + c * un.charts for c in range(copies)])
    return un, uvs, ais, lm.overlap_texels(uv, chart, ai)


def chart_area(un, tris_area):
    return np.bincount(un.chart, weights=tris_area)


# ---------------------------------------------------------------------------
# charts
# ---------------------------------------------------------------------------

def test_cube_six_charts():
    un, _, _, ov = check(*box())
    assert un.charts == 6
    assert np.allclose(un.size, 1.0)
    assert un.area == pytest.approx(6.0)
    assert ov == 0
    assert un.uv.min() >= 0 and un.uv.max() <= 1.0 + 1e-12


def test_split_box_still_one_chart_per_face():
    p, t = box((2.0, 1.0, 0.5), split=True)
    un = lm.unwrap(p, t)
    assert un.charts == 6
    for c in range(6):
        assert (un.chart == c).sum() == 2


def test_split_faces_welded_into_one_chart():
    """A flat plate cut into 4 x 4 quads, every quad with its own points: one chart, not 16."""
    pts, tris = [], []
    for i in range(4):
        for j in range(4):
            n = len(pts)
            pts += [(i, j, 0), (i + 1, j, 0), (i + 1, j + 1, 0), (i, j + 1, 0)]
            tris += [(n, n + 1, n + 2), (n, n + 2, n + 3)]
    pts = np.array(pts, float) * 0.25
    un = lm.unwrap(pts, np.array(tris))
    assert un.charts == 1
    assert np.allclose(un.size, 1.0)


def test_cylinder_64():
    p, t = cylinder(64)
    un, _, _, ov = check(p, t, tpm=100)
    assert 6 <= un.charts <= 10
    assert ov == 0
    assert un.area == pytest.approx(2 * np.pi * 0.5 * 1.0 * np.sinc(1 / 64) + 2 * 64 * 0.5 * 0.25 *
                                    np.sin(2 * np.pi / 64), rel=1e-6)


def test_u_channel():
    un, _, _, ov = check(*u_channel(), tpm=200)
    assert ov == 0
    assert un.charts >= 6


def test_helix_ramp_is_split():
    p, t = helix_ramp(turns=2.0)
    un, uvs, ais, ov = check(p, t, tpm=100)
    assert un.charts >= 2                       # two turns seen from above: at least two pieces
    assert ov == 0
    # the pieces stay big: no chart is a crumb
    assert (np.bincount(un.chart) >= 10).all()


def test_helix_fan_around_its_axis():
    """A helicoid with no hole: every triangle shares the axis point, yet the layers overlap."""
    p, t = helix_ramp(turns=1.5, r0=0.0)
    un, _, _, ov = check(p, t, tpm=100)
    assert ov == 0
    assert un.charts >= 2


def test_degenerate_triangles():
    p, t = box()
    p = np.concatenate([p, [[0.5, 0.5, 0.0], [5, 5, 5]]])
    extra = np.array([[0, 1, 1], [8, 8, 8], [0, 1, 0], [0, 3, 8], [9, 9, 9]])  # zero area
    t2 = np.concatenate([t, extra])
    un, _, _, ov = check(p, t2)
    assert len(un.chart) == len(t2)
    assert np.isfinite(un.uv).all() and np.isfinite(un.size).all()
    assert ov == 0
    assert un.area == pytest.approx(6.0)


def test_empty_mesh():
    un = lm.unwrap(np.zeros((0, 3)), np.zeros((0, 3), int))
    assert un.charts == 0 and un.area == 0.0


def test_texel_size_matches_tpm():
    """A 1 m square face at 50 texels per metre spans about 50 texels."""
    pts = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], float)
    un = lm.unwrap(pts, np.array([[0, 1, 2], [0, 2, 3]]))
    sz = lm.chart_pixels(un.size, 50.0, 4)
    assert tuple(sz[0]) == (51 + 8, 51 + 8)
    places = lm.pack([sz])
    uv, _ = lm.place_uv(un, 50.0, places[0], 4)
    span = (uv.max(0) - uv.min(0)) * lm.ATLAS
    assert np.allclose(span, 50.0, atol=1e-3)
    assert lm.overlap_texels(uv, un.chart, np.zeros(2, int)) == 0


def test_three_copies_never_share_texels():
    p, t = merge([cylinder(32), box((0.3, 0.3, 1.2), at=(1, 0, 0)), helix_ramp(1.3, 48)])
    tpm, pad = lm.texels_per_m(lm.unwrap(p, t).area * 3, lm.QUALITY["DRAFT"]["budget"] // 8), 2
    un, uvs, ais, ov = check(p, t, tpm=tpm, padding=pad, copies=3)
    assert ov == 0
    for uv in uvs:
        assert uv.min() >= 0 and uv.max() <= 1


def test_gap_between_charts():
    """The texels of two charts lie at least 2 x padding texels apart (Cycles' margin cannot reach a neighbour)."""
    p, t = merge([box(), cylinder(16), box((0.2, 0.5, 0.1), at=(3, 0, 0))])
    tpm, pad = 40.0, 3
    un = lm.unwrap(p, t)
    sz = lm.chart_pixels(un.size, tpm, pad)
    places = lm.pack([sz, sz])
    rects = []
    for pl in places:
        uv, ai = lm.place_uv(un, tpm, pl, pad)
        px = uv.reshape(-1, 3, 2).astype(float) * lm.ATLAS
        for c in range(un.charts):
            q = px[un.chart == c].reshape(-1, 2)
            # texels whose centres the chart can reach
            lo = np.ceil(q.min(0) - 0.5).astype(int)
            hi = np.floor(q.max(0) - 0.5).astype(int)
            rects.append((pl[c, 0], lo, hi))
    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            ai, lo1, hi1 = rects[i]
            aj, lo2, hi2 = rects[j]
            if ai != aj:
                continue
            gap = np.maximum(lo2 - hi1 - 1, lo1 - hi2 - 1).max()
            assert gap >= 2 * pad, (i, j, gap)


# ---------------------------------------------------------------------------
# packing
# ---------------------------------------------------------------------------

def _random_items(seed, n_items=60):
    rng = np.random.default_rng(seed)
    items = []
    for _ in range(n_items):
        k = rng.integers(1, 12)
        big = rng.random() < 0.15
        w = rng.integers(9, 400 if big else 90, k)
        h = rng.integers(9, 400 if big else 90, k)
        items.append(np.stack([w, h], 1))
    return items


def _fill(items, places, atlas=lm.ATLAS):
    n = max(int(p[:, 0].max()) for p in places if len(p)) + 1
    used = np.zeros(n)
    top = np.zeros(n)
    for s, p in zip(items, places):
        for (w, h), (a, x, y) in zip(s, p):
            used[a] += w * h
            top[a] = max(top[a], y + h)
    return used.sum() / (atlas * atlas * (n - 1) + atlas * top[-1]), n


def test_pack_no_overlap_inside_deterministic():
    items = _random_items(3, 300)
    t = time.perf_counter()
    places = lm.pack(items)
    dt = time.perf_counter() - t
    assert all(np.array_equal(a, b) for a, b in zip(places, lm.pack(items)))
    cover = {}
    for s, p in zip(items, places):
        assert len(set(p[:, 0])) <= 1                  # all charts of one copy in one atlas
        for (w, h), (a, x, y) in zip(s, p):
            assert 0 <= x and x + w <= lm.ATLAS and 0 <= y and y + h <= lm.ATLAS
            img = cover.setdefault(a, np.zeros((lm.ATLAS, lm.ATLAS), np.int8))
            img[y:y + h, x:x + w] += 1
    assert max(int(c.max()) for c in cover.values()) == 1
    fill, n = _fill(items, places)
    print(f"pack: {sum(len(s) for s in items)} charts in {n} atlases, fill {fill:.0%}, {dt:.2f} s")
    assert fill > 0.6


def test_pack_fill_realistic_mix():
    """Many copies of a few parts (as a machine has them): a good fill."""
    rng = np.random.default_rng(7)
    kinds = [np.stack([rng.integers(9, 300, k), rng.integers(9, 300, k)], 1) for k in (6, 8, 3, 12, 6)]
    items = [kinds[i % len(kinds)] for i in range(120)]
    places = lm.pack(items)
    fill, n = _fill(items, places)
    print(f"pack mix: {sum(len(s) for s in items)} charts in {n} atlases, fill {fill:.0%}")
    assert fill > 0.6


def test_pack_too_big():
    with pytest.raises(lm.TooBig) as e:
        lm.pack([np.array([[10, 10]]), np.array([[3000, 10]]), np.array([[1500, 1500], [1500, 1500]])])
    assert e.value.items == [1, 2]
    assert isinstance(e.value, ValueError)
    assert lm.fits(np.array([[2048, 2048]]))
    assert not lm.fits(np.array([[1500, 1500], [1500, 1500]]))


def test_pack_empty():
    assert lm.pack([]) == []
    out = lm.pack([np.zeros((0, 2), int), np.array([[5, 5]])])
    assert out[0].shape == (0, 3) and out[1].shape == (1, 3)


# ---------------------------------------------------------------------------
# sizes and choices
# ---------------------------------------------------------------------------

def test_texels_per_m():
    assert lm.texels_per_m(100.0, 4_000_000) == pytest.approx(200.0)
    assert lm.texels_per_m(1e6, 1_000_000) == lm.MIN_TPM
    assert lm.texels_per_m(1e-4, 1_000_000) == lm.MAX_TPM
    assert lm.texels_per_m(0.0, 1_000_000) == lm.MAX_TPM


def test_prefer_vertex():
    bolt_p, bolt_t = cylinder(12, r=0.01, h=0.08)      # an M20 bolt: 26 points, ~0.0056 m²
    area = lm.unwrap(bolt_p, bolt_t).area
    assert lm.prefer_vertex(len(bolt_p), area, 200.0)
    plate_p, plate_t = box((2.0, 1.0, 0.02))
    plate_area = lm.unwrap(plate_p, plate_t).area
    assert lm.prefer_vertex(len(plate_p), plate_area, 50.0)          # the byte rule alone: 8 points are cheap
    assert not lm.prefer_vertex(len(plate_p), plate_area, 50.0, size_m=2.0)   # but 100 texels across: a map
    assert lm.prefer_vertex(len(bolt_p), area, 200.0, size_m=0.08)
    assert not lm.prefer_vertex(5000, plate_area, 50.0)


def test_image_size():
    assert lm.image_size(1.0, 1.0, 100.0) == (128, 128)        # 100 texels across -> 128
    assert lm.image_size(1.0, 0.25, 100.0) == (256, 256)       # covers a quarter of the square
    assert lm.image_size(1e-6, 1.0, 10.0) == (16, 16)
    assert lm.image_size(1e4, 1.0, 400.0) == (2048, 2048)
    assert lm.image_size(1e4, 1.0, 400.0, max_px=512) == (512, 512)


def test_estimate():
    e = lm.estimate(1_000_000, 10_000, 64, 2, 1e8, 20.0, 0.5)
    assert e["seconds_cpu"] == pytest.approx((1e6 + 1e4) * 64 * 2 / 1e8)
    assert e["seconds_gpu"] == pytest.approx(e["seconds_cpu"] / 20)
    assert e["bytes"] == int(1e6 * 0.5 + 3e4)


# ---------------------------------------------------------------------------
# encoding and pictures
# ---------------------------------------------------------------------------

def test_encode_decode():
    f = np.linspace(0, 3.0, 3000).reshape(-1, 3)
    s = 2.5
    u8 = lm.encode(f, s)
    assert u8.dtype == np.uint8 and u8.max() == 255 and u8.min() == 0
    back = lm.decode(u8, s)
    inside = f <= s
    err = np.abs(back - f)[inside]
    # the square root keeps steps small in the dark: error <= half a step of v, times dF/dv = 2 v s
    v = np.sqrt(f[inside] / s)
    assert (err <= (v + 1 / 510) * s / 255 + 1e-6).all()
    assert np.abs(back[~inside] - s).max() < 1e-6
    assert lm.encode(np.array([0.25]), 1.0)[0] == 128


def test_scale_of():
    a = np.ones((100, 100, 3))
    assert lm.scale_of([a]) == 1.0
    b = np.full((1000, 3), 0.5)
    b[:, 0] = np.linspace(0, 4, 1000)
    assert lm.scale_of([b, np.zeros((0, 3))]) == pytest.approx(np.percentile(np.linspace(0, 4, 1000), 99.9))
    assert lm.scale_of([]) == 1.0
    assert lm.scale_of([np.full((4, 3), np.nan)]) == 1.0


def test_dilate():
    px = np.zeros((9, 9, 3), np.float32)
    mask = np.zeros((9, 9), bool)
    mask[3:6, 3:6] = True
    px[3:6, 3:6] = 1.0 + np.arange(27, dtype=np.float32).reshape(3, 3, 3)
    out = lm.dilate(px, mask, 1)
    assert np.array_equal(out[mask], px[mask])
    ring = np.zeros((9, 9), bool)
    ring[2:7, 2:7] = True
    assert (out[ring & ~mask] > 0).all()
    assert (out[~ring] == 0).all()
    assert np.allclose(out[2, 2], px[3, 3])          # the corner sees only one baked texel
    out3 = lm.dilate(px, mask, 3)
    assert (out3[:, :, 2] > 0).all()


def test_smooth_keeps_mask_apart():
    px = np.zeros((20, 20, 3), np.float32)
    mask = np.zeros((20, 20), bool)
    mask[:, :8] = True
    mask[:, 12:] = True
    px[:, :8] = 1.0
    px[:, 12:] = 5.0
    px[:, 8:12] = 100.0                              # unbaked texels: never read
    rng = np.random.default_rng(0)
    px[mask] += rng.normal(0, 0.1, (mask.sum(), 3)).astype(np.float32)
    out = lm.smooth(px, mask, radius=2)
    assert np.abs(out[:, :8] - 1.0).max() < 0.2
    assert np.abs(out[:, 12:] - 5.0).max() < 0.2
    assert np.array_equal(out[:, 8:12], px[:, 8:12])
    assert out[:, :8].std() < px[:, :8].std()


# ---------------------------------------------------------------------------
# speed
# ---------------------------------------------------------------------------

def test_unwrap_200k_triangles_fast():
    p, t = sphere(400, 251)
    assert len(t) >= 199_000
    t0 = time.perf_counter()
    un = lm.unwrap(p, t)
    dt = time.perf_counter() - t0
    print(f"unwrap sphere {len(t)} triangles: {dt:.2f} s, {un.charts} charts")
    assert dt < 5.0
    assert un.charts >= 6
    many = merge([box((0.1 + 0.01 * (i % 7), 0.2, 0.05), at=(i % 100, i // 100, 0), split=True)
                  for i in range(16_000)])
    t0 = time.perf_counter()
    un2 = lm.unwrap(*many)
    dt2 = time.perf_counter() - t0
    print(f"unwrap 16,000 boxes ({len(many[1])} triangles): {dt2:.2f} s, {un2.charts} charts")
    assert un2.charts == 6 * 16_000
    assert dt2 < 5.0


def test_sphere_and_triangle_soup_never_overlap():
    """A smooth sphere, and a soup of random triangles that cross each other everywhere: no texel baked twice."""
    un, _, _, ov = check(*sphere(80, 50), tpm=120)
    assert ov == 0
    rng = np.random.default_rng(5)
    base = rng.random((1500, 1, 3)) * 2.0
    pts = (base + rng.normal(0, 0.15, (1500, 3, 3))).reshape(-1, 3)
    tris = np.arange(len(pts)).reshape(-1, 3)
    tris[::2] = tris[::2][:, ::-1]                  # some facing each way
    shared = np.repeat(tris[1:400:3], 1, 0)          # some share points with the next one (fans)
    tris[2:401:3, 0] = shared[:, 0]
    un, _, _, ov = check(pts, tris, tpm=60, padding=2)
    assert ov == 0
    print(f"soup: {len(tris)} triangles -> {un.charts} charts")


def test_overlap_check_sees_overlaps():
    """The check itself: two copies on the same place, and a helix left whole, are found."""
    p, t = cylinder(16)
    un = lm.unwrap(p, t)
    sz = lm.chart_pixels(un.size, 80.0, 2)
    pl = lm.pack([sz])[0]
    uv, ai = lm.place_uv(un, 80.0, pl, 2)
    assert lm.overlap_texels(uv, un.chart, ai) == 0
    assert lm.overlap_texels(np.concatenate([uv, uv]), np.r_[un.chart, un.chart], np.r_[ai, ai]) > 1000
    hp, ht = helix_ramp(turns=1.5)
    whole = lm.Unwrap(lm.unwrap(hp, ht).uv, np.zeros(len(ht), np.int32), np.zeros((1, 2)), 0.0)
    flat = hp[ht].reshape(-1, 3)[:, :2]                      # seen from above, one chart
    whole.uv = flat - flat.min(0)
    whole.size = np.array([np.ptp(flat, 0)])
    uv, ai = lm.place_uv(whole, 80.0, lm.pack([lm.chart_pixels(whole.size, 80.0, 2)])[0], 2)
    assert lm.overlap_texels(uv, whole.chart, ai) > 100
