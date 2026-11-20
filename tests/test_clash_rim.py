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


def rim(dip=None):
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
    return sc


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
