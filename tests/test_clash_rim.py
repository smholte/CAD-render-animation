"""Task 0229, stand-in for the demo vessel's size (study 0226): the clash check on a made-up rim of 200 round rollers
turning in place on a plain deck.

Proves: 200 rollers (each its own keyed turn about its own axis, 3 turns in the animation) touching nothing give 0
clash rows, every roller and its shaft are recognised as round and turning in place (held still: 400 parts), the
check stays fast; and controls: a block sliding 1 mm clear over the first row gives none, one sliding 5 mm into
their tops is found and named (rows name the block and rollers of that row). A part at rest that overlaps a held one is
not a clash by design (one body), so the controls move.

Small scene made here (no STEP file, nothing of the demo): a deck (one flat box) and a grid of 4 rows x 50 rollers.
"""

import math
import time

import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import clash  # noqa: E402
from fresing_render.core import clash as core  # noqa: E402

from test_clash_turning import _linear, box, built, part, prism, roller  # noqa: E402

MM = 1e-3
FRAMES = 12
ROWS, PER_ROW = 4, 50
R = 50 * MM
PITCH_Y = 0.16                       # roller axes 160 mm apart (100 mm across + 60 mm free)
PITCH_X = 0.5
LIMIT_S = 90.0                       # generous: the measured time is printed


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def rim(dip=None, rotors=False, post_in_rotor=False):
    """The deck and 200 rollers. ``dip``: a block slides along the first row of rollers (keyed, 0.5 m/s class motion)
    with its underside that many metres below the rollers' tops (negative: that far above them)."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 1, FRAMES
    half_y = PER_ROW * PITCH_Y / 2
    part(sc, "DECK", box((-0.3, -half_y - 0.2, -0.1), (ROWS * PITCH_X, half_y + 0.2, 0.0)))
    section = roller(R, 32)
    n = 0
    for i in range(ROWS):
        for j in range(PER_ROW):
            x, y = 0.2 + i * PITCH_X, -half_y + (j + 0.5) * PITCH_Y
            rol = part(sc, f"ROLLER {n:03d}", prism(section, -0.1, 0.1))
            rol.location = (x, y, R + 0.5 * MM)                       # 0.5 mm clear of the deck
            part(sc, f"SHAFT {n:03d}", prism(roller(10 * MM, 16), -0.14, 0.14), parent=rol)
            rol.rotation_euler = (0, 0, 0)
            rol.keyframe_insert("rotation_euler", frame=1)
            rol.rotation_euler = (6 * math.pi, 0, 0)
            rol.keyframe_insert("rotation_euler", frame=FRAMES)
            _linear(rol)
            n += 1
    if dip is not None:
        top = 2 * R + 0.5 * MM
        blk = part(sc, "BLOCK", box((0.1, -0.1, top - dip), (0.3, 0.1, top - dip + 0.1)))
        blk.location = (0, -half_y, 0)
        blk.keyframe_insert("location", frame=1)
        blk.location = (0, -half_y + 3.0, 0)                          # over 19 rollers of the first row
        blk.keyframe_insert("location", frame=FRAMES)
        _linear(blk)
    if rotors:
        big_turning_parts(sc, post_in_rotor)
    return sc


def blade(n, k, length, r0, width, thick, axis):
    """Blade k of n: a box from radius r0 to length, turned k/n of a turn about the rotor axis ('x' or 'y')."""
    a = 2 * math.pi * k / n
    v, t = box((-thick / 2, -width / 2, r0), (thick / 2, width / 2, length))
    out = []
    for x, y, z in v:                                      # turn about X by a (blade along +Z at a = 0)
        y2, z2 = y * math.cos(a) - z * math.sin(a), y * math.sin(a) + z * math.cos(a)
        out.append((x, y2, z2) if axis == "x" else (y2, x, z2))
    return out, t


def rotor(sc, name, at, n, length, axis, turns):
    """A round hub (turning, keyed) with n blades as its children: the blades are not round, so they are checked."""
    hub = part(sc, f"{name} HUB", prism(roller(0.8, 24), -0.5, 0.5) if axis == "x" else _along_y(0.8, 0.5))
    hub.location = at
    for k in range(n):
        part(sc, f"{name} BLADE {k}", blade(n, k, length, 0.8, 1.0 if length > 5 else 0.2, 0.5 if length > 5 else 0.05,
                                            axis), parent=hub)
    idx = 0 if axis == "x" else 1
    hub.rotation_euler = (0, 0, 0)
    hub.keyframe_insert("rotation_euler", frame=1)
    e = [0, 0, 0]
    e[idx] = 2 * math.pi * turns
    hub.rotation_euler = tuple(e)
    hub.keyframe_insert("rotation_euler", frame=FRAMES)
    _linear(hub)
    return hub


def _along_y(r, half):
    v, t = prism(roller(r, 24), -half, half)
    return [(y, x, z) for x, y, z in v], t


def big_turning_parts(sc, post_in_rotor):
    """3 rotors of 3 blades (40 m across, hub 25 m up, beside the rim, tower behind the rotor plane), 2 propellers of 4
    blades (3 m) under the deck. ``post_in_rotor``: a post stands in the way of rotor 0's lowest blade tip."""
    for i in range(3):
        x = -80.0 - i * 80.0
        rotor(sc, f"ROTOR {i}", (x, 40.0, 25.0), 3, 20.0, "x", 1.0)
        part(sc, f"TOWER {i}", box((x - 3.5, 39.5, 0.0), (x - 2.5, 40.5, 24.0)))
    if post_in_rotor:
        part(sc, "POST", box((-80.2, 39.8, 0.0), (-79.8, 40.2, 8.0)))            # the blade tip reaches down to 5 m
    for i in range(2):
        rotor(sc, f"PROP {i}", (0.5 + i * 4.5, -2.0, -2.8), 4, 1.5, "y", 6.0)


def timed(sc):
    t0 = time.time()
    r = clash.check(built(sc), store=False)
    return r, time.time() - t0


def test_200_turning_rollers_on_a_deck_give_no_clash_and_are_held_still():
    sc = rim()
    r, dt = timed(sc)
    print(f"\nrim of {ROWS * PER_ROW} rollers: {dt:.1f} s, stats {r.stats}")
    assert not r.rows, [core.row_text(x) for x in r.rows[:5]]
    assert r.stats["held"] == 2 * ROWS * PER_ROW                  # each roller and its shaft
    assert r.stats["narrow"] == 0 and r.stats["between"] == 0, r.stats
    assert dt < LIMIT_S, dt


def test_a_block_sliding_clear_over_the_rollers_gives_no_clash():
    sc = rim(dip=-1 * MM)                                         # 1 mm above their tops
    r, dt = timed(sc)
    print(f"\nrim + clear block: {dt:.1f} s")
    assert not r.rows, [core.row_text(x) for x in r.rows[:5]]
    assert r.stats["held"] == 2 * ROWS * PER_ROW
    assert dt < LIMIT_S


def test_a_block_pushed_5_mm_into_the_rollers_is_found_and_named():
    sc = rim(dip=5 * MM)
    r, dt = timed(sc)
    print(f"\nrim + block 5 mm into the rollers: {dt:.1f} s, {len(r.rows)} rows, stats {r.stats}")
    rows = [x for x in r.rows if x.kind == "CLASH"]
    assert rows, "the block through the rollers was not found"
    assert all("BLOCK" in {x.a, x.b} for x in rows), [core.row_text(x) for x in r.rows[:5]]
    others = {(x.b if x.a == "BLOCK" else x.a) for x in rows}
    assert all(o.startswith("ROLLER 0") for o in others) and len(others) >= 10, sorted(others)
    assert max(x.depth for x in rows) == pytest.approx(5 * MM, abs=0.5 * MM)
    assert dt < LIMIT_S


def test_big_rotors_and_propellers_are_checked_not_held_and_clear():
    sc = rim(rotors=True)
    r, dt = timed(sc)
    print(f"\nrim + 3 rotors + 2 propellers: {dt:.1f} s, stats {r.stats}")
    assert not r.rows, [core.row_text(x) for x in r.rows[:5]]
    blades = 3 * 3 + 2 * 4
    hubs = 5
    assert r.stats["held"] == 2 * ROWS * PER_ROW + hubs, r.stats          # no blade held still
    assert r.stats["parts"] >= 401 + hubs + blades
    assert dt < LIMIT_S


def test_a_blade_tip_through_a_post_is_found_and_named():
    sc = rim(rotors=True, post_in_rotor=True)
    r, dt = timed(sc)
    print(f"\nrotors + post in the way: {dt:.1f} s, {len(r.rows)} rows, stats {r.stats}")
    rows = [x for x in r.rows if x.kind == "CLASH"]
    assert rows, "the post in the rotor's way was not found"
    assert all("POST" in {x.a, x.b} for x in rows), [core.row_text(x) for x in r.rows[:5]]
    assert all((x.b if x.a == "POST" else x.a).startswith("ROTOR 0 BLADE") for x in rows)
    assert dt < LIMIT_S
