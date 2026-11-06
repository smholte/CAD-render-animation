"""Task 0028: chips without Blender (core/chips.py).

A 200 x 200 x 40 mm block (top at z = 70 mm) on a 400 x 300 mm table (top at 30 mm) on a machine bed (top at 0,
bottom - the floor - at -60 mm). A flat end mill Ø10 plunges at frame 1..25 into the block, cuts a slot along X
from frame 25 to 75 and goes up again: every number below is worked out by hand from that.
"""

import math

import numpy as np
import pytest

from fresing_render.core import chips as C
from fresing_render.core import machining as M

MM = 0.001
FPS = 25.0
FRAMES = 100
TOP, BOTTOM = 0.07, 0.03


def slot_bits(depth=5.0, kind="FLAT", family="ALU", length=50.0, y=0.0, frames=(1, 25, 75, 88), radius=5.0):
    f0, f1, f2, f3 = frames
    t = np.arange(1, FRAMES + 1, dtype=float)
    z = np.interp(t, [f0, f1, f2, f3, FRAMES], [0.09, TOP - depth * MM, TOP - depth * MM, 0.09, 0.09])
    x = np.interp(t, [f0, f1, f2, f3, FRAMES], [0, 0, length * MM, length * MM, length * MM])
    o = np.stack([x, np.full_like(x, y * MM), z], axis=1)
    tool = M.Tool(kind, radius=radius * MM, length=40 * MM)
    return C.BitIn(t, o, np.tile([0, 0, 1.0], (len(t), 1)), radius * MM, 40 * MM, M.tool_profile(tool),
                   C.presets_for(family, C.bit_kind(kind, radius * MM)))


def scene(bits, amount="REALISTIC", mist=False, carry=None, seed=28, flat_bed=False):
    top = C.grid_for((-0.1, -0.1), (0.1, 0.1), 0.5 * MM)
    top.h[:] = TOP
    work = C.WorkField(top, np.full_like(top.h, BOTTOM))
    C.stamp_paths(work, bits)
    ride = C.grid_for((-0.4, -0.4), (0.4, 0.4), 2 * MM)
    xs, ys = ride.centres()
    X, Y = np.meshgrid(xs, ys)
    ride.h[(abs(X) < 0.2) & (abs(Y) < 0.15)] = BOTTOM
    static = C.grid_for((-1, -1), (1, 1), 5 * MM)
    xs, ys = static.centres()
    X, Y = np.meshgrid(xs, ys)
    static.h[(abs(X) < 0.35) & (abs(Y) < 0.25) | flat_bed] = 0.0
    return C.SimIn(FPS, 1, FRAMES, bits, work, ride, static, -0.06, carry, amount, mist, seed)


# ---------------------------------------------------------------------------


@pytest.mark.parametrize("key", sorted(C.PRESETS) + ["MIST", "WOOD/DUST"])
def test_every_preset_builds(key):
    p = {"MIST": C.MIST, "WOOD/DUST": C.WOOD_DUST}.get(key) or C.PRESETS[key]
    assert p.shape in C.SHAPES and p.speed > 0 and p.length > 0 and 0 <= p.bounce < 1
    assert p.label and C.chip_volume(p) > 0
    for v in range(C.VARIANTS):
        verts, tris = C.shape_mesh(p, v)
        assert np.isfinite(verts).all() and len(verts) >= 4 and tris.min() >= 0 and tris.max() < len(verts)
        assert abs(float(verts[:, 2].min())) < 1e-9                    # lies on the table with its lowest point
        size = float(np.ptp(verts, axis=0).max())
        assert 0.3 * p.length < size < 1.7 * p.length, (key, v, size, p.length)
        # a closed surface: every edge belongs to exactly two triangles
        e = np.sort(np.concatenate([tris[:, [0, 1]], tris[:, [1, 2]], tris[:, [2, 0]]]), axis=1)
        _u, counts = np.unique(e, axis=0, return_counts=True)
        assert (counts == 2).all(), (key, v)
        a = np.cross(verts[tris[:, 1]] - verts[tris[:, 0]], verts[tris[:, 2]] - verts[tris[:, 0]])
        assert (np.linalg.norm(a, axis=1) > 0).mean() > 0.95
    # the same variant is the same shape every time (a project looks the same when opened again)
    assert np.array_equal(C.shape_mesh(p, 2)[0], C.shape_mesh(p, 2)[0])


def test_every_material_has_a_preset_for_every_bit():
    for fam in C.FAMILIES:
        assert fam in C.LOOKS
        for bit in C.BIT_KINDS:
            assert C.preset(fam, bit).family == fam


@pytest.mark.parametrize("names, expected", [
    (["BLOCK AlMg3"], "ALU"), (["aluplaat 10mm"], "ALU"), (["EN AW-6082"], "ALU"),
    (["Plaat RVS 316"], "STAINLESS"), (["Werkstück 1.4301"], "STAINLESS"),
    (["Messing bus"], "BRASS"), (["Bronze bush"], "BRASS"), (["GG25 huis"], "CAST_IRON"),
    (["POM blok"], "PLASTIC"), (["DELRIN BLOCK"], "PLASTIC"), (["PE1000 strip"], "PLASTIC"),
    (["MDF plaat"], "WOOD"), (["Houten kist"], "WOOD"), (["C45 as"], "STEEL"), (["Staalprofiel"], "STEEL"),
    (["STOCK 200x200x40", "Unsorted"], None), (["Pomp huis"], None), (["PIPE CLAMP"], None), (["houder"], None),
])
def test_material_from_names(names, expected):
    assert C.family_from_names(names) == expected


def test_material_from_the_group_look_and_default():
    assert C.family_for(["STOCK"], "pom_white") == ("PLASTIC", "material")
    assert C.family_for(["STOCK"], "steel_machined") == ("STEEL", "material")
    assert C.family_for(["Blok RVS"], "aluminium_machined") == ("STAINLESS", "name")   # the name says more
    assert C.family_for(["STOCK"], "paint_gloss") == ("ALU", "default")


def test_bit_types():
    assert C.bit_kind("FLAT", 5 * MM) == "END" and C.bit_kind("BULL", 5 * MM) == "END"
    assert C.bit_kind("FLAT", 25 * MM) == "FACE" and C.bit_kind("BALL", 3 * MM) == "BALL"
    assert C.bit_kind("DRILL", 5 * MM) == "DRILL" and C.bit_kind("VEE", 3 * MM) == "ENGRAVE"
    assert C.bit_kind("CUSTOM", 5 * MM) == "END"


def test_the_height_field_cuts_the_slot():
    sim = scene([slot_bits()])
    vol = sim.work.removed() * 1e9
    assert vol == pytest.approx((50 * 10 + math.pi * 25) * 5, rel=0.01)
    per = sim.work.removed_per_frame(1, FRAMES)
    cutting = np.nonzero(per > 0)[0] + 1
    # the bit (tip at 90 mm) reaches the top (70 mm) after 20 / 25 of the plunge: frame 1 + 24 * 20/25.2 ≈ 20.2
    assert cutting.min() == 21 and cutting.max() == 75


def test_chips_appear_only_while_cutting():
    sim = scene([slot_bits()])
    b = C.simulate(sim)
    per = sim.work.removed_per_frame(1, FRAMES)
    first, last = np.nonzero(per > 0)[0][[0, -1]] + 1
    assert b.count > 0
    assert b.born.min() >= first - 1 and b.born.max() <= last
    for f in range(1, first):
        assert b.alive_at(f) == 0, f
    assert b.alive_at(first) > 0
    # nothing new after the bit is out: only chips still flying and the ones lying there
    n_end = b.alive_at(last + 20)
    assert n_end == b.alive_at(FRAMES) and n_end <= b.count


def test_the_amount_follows_the_removed_volume():
    b5 = C.simulate(scene([slot_bits(depth=5.0)]))
    b10 = C.simulate(scene([slot_bits(depth=10.0)]))
    assert b10.count / b5.count == pytest.approx(2.0, rel=0.02)
    # realistic: the preset's chips per mm³
    p = C.preset("ALU", "END")
    assert b5.count == pytest.approx(b5.stats["removed_mm3"] * p.per_mm3, abs=1)
    # few: about an eighth
    few = C.simulate(scene([slot_bits(depth=5.0)], amount="FEW"))
    assert few.count == pytest.approx(b5.count * C.AMOUNTS["FEW"]["factor"], abs=1)
    # over time: chips come off as fast as material does (the cumulative counts follow each other)
    sim = scene([slot_bits(depth=5.0)])
    b = C.simulate(sim)
    vol = np.cumsum(sim.work.removed_per_frame(1, FRAMES)) * 1e9 * p.per_mm3
    born = np.array([(b.born <= f).sum() for f in range(1, FRAMES + 1)])
    assert np.abs(born - vol).max() <= 2.0 + 0.02 * vol.max()
    assert C.simulate(scene([slot_bits()], amount="NONE")).count == 0


def test_the_bake_is_the_same_every_time():
    a = C.simulate(scene([slot_bits()], mist=True))
    b = C.simulate(scene([slot_bits()], mist=True))
    for k in ("born", "rest_t", "end_t", "fade", "rest_p", "rest_q", "rest_space", "slot", "scale", "tint",
              "frame_start", "fly_id", "fly_p", "fly_q", "fly_space"):
        assert np.array_equal(getattr(a, k), getattr(b, k)), k
    # and any frame shown in any order gives the same answer
    shown = {f: a.at(f) for f in (90, 30, 60)}
    for f in (60, 90, 30):
        again = a.at(f)
        for sp in (0, 1):
            assert np.array_equal(shown[f][sp]["pos"], again[sp]["pos"])
    c = C.simulate(scene([slot_bits()], mist=True, seed=29))
    assert not np.array_equal(a.rest_p, c.rest_p)                      # the seed does matter


def test_chips_land_on_the_block_the_table_the_bed_and_the_floor():
    b = C.simulate(scene([slot_bits()]))
    a = b.at(FRAMES)
    ride, world = a[0]["pos"], a[1]["pos"]
    on_block = ride[:, 2] >= TOP - 1e-6
    on_table = np.abs(ride[:, 2] - BOTTOM) < 2 * MM
    assert on_block.sum() > 10 and on_table.sum() > 0
    assert (on_block | on_table | (ride[:, 2] < TOP)).all()
    on_bed = np.abs(world[:, 2]) < 2 * MM
    on_floor = np.abs(world[:, 2] + 0.06) < 2 * MM
    assert on_bed.sum() > 10 and (on_bed | on_floor).all()
    # nothing lies inside the slot's walls: chips in the slot lie on its floor (65 mm) or higher
    in_slot = (ride[:, 0] > 0) & (ride[:, 0] < 0.05) & (np.abs(ride[:, 1]) < 0.004)
    assert (ride[in_slot, 2] >= TOP - 5 * MM - 1e-6).all()


def test_piles_grow():
    """Chips that come to rest raise the surface for the next ones: some lie higher than the bare table."""
    b = C.simulate(scene([slot_bits(depth=15.0)]))
    ride = b.at(FRAMES)[0]["pos"]
    on_table = (ride[:, 2] < TOP - 1 * MM) & (np.abs(np.abs(ride[:, 0]) - 0.15) < 0.05)
    world = b.at(FRAMES)[1]["pos"]
    assert (world[:, 2] > 0.05 * MM).any() or (ride[on_table, 2] > BOTTOM + 0.05 * MM).any()


def test_chips_on_the_block_are_gone_when_the_bit_cuts_there():
    """A second slot 15 mm beside the first, later on: chips that landed there are taken away by the bit."""
    first = slot_bits(frames=(1, 15, 40, 45))
    second = slot_bits(y=15.0, frames=(50, 60, 90, 95))
    second.t = second.t.copy()
    bits = [first, second]
    sim = scene(bits)
    b = C.simulate(sim)
    lying = (b.rest_t < 55) & (b.rest_space == 0) & (b.rest_p[:, 2] >= TOP - 1e-6)
    p = b.rest_p
    in_second = lying & (p[:, 0] > 0.006) & (p[:, 0] < 0.044) & (np.abs(p[:, 1] - 0.015) < 0.004)
    assert in_second.sum() >= 3
    assert np.isfinite(b.end_t[in_second]).all() and (b.end_t[in_second] <= 92).all()
    away = lying & (np.abs(p[:, 1] - 0.015) > 0.02) & (np.abs(p[:, 1]) > 0.02)
    assert away.sum() > 0 and not np.isfinite(b.end_t[away]).any()


def test_chips_that_fall_off_the_table_land_where_the_table_is_now():
    """The table (with the block) stands 60 mm further along Y: chips on it are the same in its own space, chips
    that fall off it land 60 mm further along on the (flat) bed, and stay there."""
    carry = np.tile(np.eye(4), (FRAMES, 1, 1))
    carry[:, 1, 3] = 0.06
    moved = C.simulate(scene([slot_bits()], carry=carry, flat_bed=True))
    still = C.simulate(scene([slot_bits()], flat_bed=True))
    assert np.array_equal(moved.rest_space, still.rest_space)
    ride = moved.rest_space == 0
    world = moved.rest_space == 1
    assert ride.sum() > 10 and world.sum() > 10
    assert np.allclose(moved.rest_p[ride], still.rest_p[ride])
    assert np.allclose(moved.rest_p[world] - still.rest_p[world], [0.0, 0.06, 0.0], atol=1e-9)
    # a chip lying on the bed does not move when the table does
    a, b = moved.at(FRAMES - 10), moved.at(FRAMES)
    keep = np.isin(a[1]["id"], b[1]["id"]) & np.isfinite(moved.rest_t[a[1]["id"]]) & \
        (moved.rest_t[a[1]["id"]] <= FRAMES - 10)
    ids = a[1]["id"][keep]
    pa = a[1]["pos"][keep]
    pb = b[1]["pos"][np.searchsorted(b[1]["id"], ids)] if np.all(np.diff(b[1]["id"]) > 0) else \
        np.array([b[1]["pos"][list(b[1]["id"]).index(i)] for i in ids])
    assert len(ids) > 0 and np.allclose(pa, pb)


def test_too_many_chips_fade_oldest_first():
    sim = scene([slot_bits(depth=25.0, length=150.0, frames=(1, 20, 90, 95), family="BRASS")], amount="FEW")
    b = C.simulate(sim)
    cap = C.AMOUNTS["FEW"]["cap"]
    assert b.count > cap
    fade = C.RETIRE_FADE * FPS
    for f in range(1, FRAMES + 1, 3):                 # at most the cap, plus the ones shrinking away just now
        assert b.alive_at(f) <= cap * 1.02 + ((b.born > f - fade - 1) & (b.born <= f)).sum(), f
    gone = np.isfinite(b.end_t) & (b.rest_space >= 0)
    assert gone.any()
    # the ones that fade were lying there the longest
    faded = np.nonzero(gone & np.isfinite(b.rest_t))[0]
    kept = np.nonzero(~gone & np.isfinite(b.rest_t))[0]
    assert np.median(b.rest_t[faded]) < np.median(b.rest_t[kept])


def test_coolant_mist_comes_and_goes():
    b = C.simulate(scene([slot_bits()], mist=True))
    mist = np.array([C.SHAPES[C.SHAPES.index("DROP")] == b.shapes[s][0].shape for s in b.slot])
    assert b.stats["mist"] > 0 and mist.sum() == b.stats["mist"]
    assert np.isfinite(b.end_t[mist]).all() and not np.isfinite(b.rest_t[mist]).any()
    assert (b.end_t[mist] - b.born[mist] <= C.MIST.life * 1.2 * FPS + 1e-6).all()


@pytest.mark.parametrize("family, kind", [("ALU", "DRILL"), ("STEEL", "VEE"), ("WOOD", "FLAT"), ("PLASTIC", "BALL"),
                                          ("BRASS", "FLAT"), ("CAST_IRON", "FLAT"), ("STAINLESS", "BALL")])
def test_other_bits_and_materials(family, kind):
    b = C.simulate(scene([slot_bits(kind=kind, family=family)], amount="FEW"))
    assert b.count > 0
    shapes = {b.shapes[s][0].shape for s in b.slot}
    assert C.preset(family, C.bit_kind(kind, 5 * MM)).shape in shapes
    if family == "WOOD":
        assert "DUST" in shapes                                       # shavings come with dust
