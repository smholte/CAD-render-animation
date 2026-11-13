"""Task 0110: the clash check skips work it can prove changes nothing, and still finds every clash.

Two speed-ups, each compared here with a *thorough* run of the same scene (no gap is ever looked for, no pair is ever
checked once for a stretch: every pair whose boxes meet is worked out again whenever it moved):

- **A gap for every pair** (``Check._check_pairs``, ``Check._between``): a small part spinning far from the surface of a
  big frame whose box holds it is worked out once, then left alone until it has moved as far as the gap. Before task
  0110 only parts with more than 20,000 faces together looked for a gap.
- **Once per turn, pair by pair** (``Check._maybe_window``): a sheave turning on its pin while the head carrying both
  tips over meets the pin and the head the same way at every angle, whatever carries them.

Small scenes made here (no STEP file); the shapes come from ``tests/test_clash_turning.py``.
"""

import math

import pytest

bpy = pytest.importorskip("bpy")

from test_clash_turning import FRAMES, _fence, addon, box, built, keys, part, prism, run, sc  # noqa: E402,F401

from fresing_render.blender import clash  # noqa: E402
from fresing_render.core import clash as core  # noqa: E402

MM = 1e-3


def thorough(monkeypatch):
    """The check without the shortcuts: no gap is looked for, no pair is checked once for a stretch."""
    monkeypatch.setattr(clash.Check, "_separation", lambda self, p, q, rel, need=clash.SEP_NEED: 0.0)
    monkeypatch.setattr(clash.Check, "_maybe_window", lambda self, p, q, t: None)
    monkeypatch.setattr(clash.Check, "_still_pairs", lambda self: setattr(self, "windows", {}) or 0)


def rows_of(r):
    return sorted((x.kind, *sorted((x.a, x.b)), x.frame_from, x.frame_to, round(x.depth / MM, 1)) for x in r.rows)


def same_rows(fast, slow):
    a, b = rows_of(fast), rows_of(slow)
    assert [x[:5] for x in a] == [x[:5] for x in b], (a, b)
    for x, y in zip(a, b):
        assert abs(x[5] - y[5]) <= max(0.1, 0.05 * y[5]), (x, y)          # depth (mm)


# ---------------------------------------------------------------------------
# a gap for every pair
# ---------------------------------------------------------------------------

def _spinning_arm(scene, slide):
    """A fence of four bars (2 m square, inner faces 0.95 m from the middle; 48 faces: no "big" part) and an arm 0.3 m
    long spinning 8 times about Z in the middle of it while it slides ``slide`` m along X."""
    _fence_part = part(scene, "FENCE", _fence(1.0))
    arm = part(scene, "ARM", box((0.0, -0.02, -0.02), (0.3, 0.02, 0.02)))
    keys(arm, "location", [(0, 0, 0), (slide, 0, 0)])
    keys(arm, "rotation_euler", [(0, 0, 0.1), (0, 0, 0.1 + 16 * math.pi)])
    del _fence_part
    return built(scene)


def test_a_small_part_far_inside_a_frames_box_is_left_alone(sc, monkeypatch):
    """The arm spins 0.65 m from the fence: one gap search, then nothing (it never moves that far against it). The
    thorough check works the pair out at every frame and many times between frames."""
    r = run(_spinning_arm(sc, 0.0))
    assert not r.rows and r.stats["narrow"] == 0 and r.stats["between"] == 0
    thorough(monkeypatch)
    slow = run(sc)
    assert not slow.rows and slow.stats["narrow"] > 100


def test_the_gap_shortcut_still_finds_the_arm_reaching_the_fence(sc, monkeypatch):
    """The arm slides 0.7 m while it spins: its tip reaches the fence (0.95 m) near the end and goes 50 mm in. The
    frames left alone while it was far must not hide that: the same rows as the thorough check, far fewer tests."""
    r = run(_spinning_arm(sc, 0.7))
    rows = [x for x in r.rows if x.kind == "CLASH"]
    assert rows and all({x.a, x.b} == {"ARM", "FENCE"} for x in rows), [core.row_text(x) for x in r.rows]
    assert max(x.depth for x in rows) > 20 * MM                    # (the bar is 50 mm thick)
    assert min(x.frame_from for x in rows) >= 30
    n_fast = r.stats["narrow"]
    thorough(monkeypatch)
    slow = run(sc)
    same_rows(r, slow)
    assert n_fast * 2 < slow.stats["narrow"], (n_fast, slow.stats["narrow"])


# ---------------------------------------------------------------------------
# once per turn, pair by pair
# ---------------------------------------------------------------------------

N = 96


def _ring(r0, r1, z0, z1, n=N):
    """A closed ring about Z (inner radius r0, outer r1, from z0 to z1)."""
    v = []
    for r in (r0, r1):
        for z in (z0, z1):
            v += [(r * math.cos(2 * math.pi * i / n), r * math.sin(2 * math.pi * i / n), z) for i in range(n)]
    t = []

    def ix(k, i):
        return k * n + i % n
    for i in range(n):
        for k0, k1 in ((0, 1), (1, 3), (3, 2), (2, 0)):
            t += [(ix(k0, i), ix(k1, i + 1), ix(k0, i + 1)), (ix(k0, i), ix(k1, i), ix(k1, i + 1))]
    return v, t


def _join(*shapes):
    v, t = [], []
    for sv, st in shapes:
        t += [(a + len(v), b + len(v), c + len(v)) for a, b, c in st]
        v += list(sv)
    return v, t


def _sheave():
    """A sheave about Z: hub (bore r 30 mm, 90 mm out), four spokes, rim (r 0.30 … 0.40 m, 60 mm wide). Not round (spokes)."""
    spokes = []
    for k in range(4):
        a = k * math.pi / 2
        bv, bt = box((0.085, -0.02, -0.02), (0.305, 0.02, 0.02))
        spokes.append(([(x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a), z) for x, y, z in bv],
                       bt))
    return _join(_ring(0.03, 0.09, -0.03, 0.03), _ring(0.3, 0.4, -0.03, 0.03), *spokes)


def _pin(r=0.0301, half=0.06):
    """A round pin along Z (96 facets, lined up with the bore's): 0.1 mm into the hub."""
    sec = [(r * math.cos(2 * math.pi * i / N), r * math.sin(2 * math.pi * i / N)) for i in range(N)]
    v, t = prism(sec, -half, half)                                   # along X
    return [(z, y, x) for x, y, z in v], [(a, c, b) for a, b, c in t]  # along Z (a mirror: faces turned back)


def _tipping_head(scene, bolt=False):
    """A head (two cheeks 10 mm beside the rim, carrying the pin) tips a quarter turn about X while the sheave on its
    pin turns three times. ``bolt``: a bolt on a cheek reaches 10 mm into the room the spokes sweep."""
    head = part(scene, "HEAD", _join(box((-0.45, -0.45, 0.04), (0.45, 0.45, 0.06)),
                                     box((-0.45, -0.45, -0.06), (0.45, 0.45, -0.04))))
    part(scene, "PIN", _pin(), parent=head)
    shv = part(scene, "SHEAVE", _sheave(), parent=head)
    if bolt:
        part(scene, "BOLT", box((0.15, -0.01, 0.01), (0.2, 0.01, 0.04)), parent=head)
    keys(head, "rotation_euler", [(0, 0, 0), (math.pi / 2, 0, 0)])
    keys(shv, "rotation_euler", [(0, 0, 0.3), (0, 0, 0.3 + 6 * math.pi)])
    return built(scene)


def only_the_world_carries(monkeypatch):
    """The carriers ``_hold_still`` tries, cut to the world: the sheave (tipping and turning) has none, so it is not
    held and ``_still_pairs`` finds no stretch for it (the demo's tipping sheave: its head was not among the bodies
    tried)."""
    monkeypatch.setattr(clash, "CARRIERS_BIG", 0)
    monkeypatch.setattr(clash, "CARRIERS_NEAR", 0)


def test_a_sheave_turning_on_its_pin_while_the_head_tips_is_checked_once(sc, monkeypatch):
    """The sheave turns against the head and the pin about the pin's axis the whole time, and is round wherever they
    come (the bore, the rim's faces): each pair is worked out a couple of times, then left for the rest of the turn.
    The same (no) rows as the thorough check, which works both pairs out again and again."""
    only_the_world_carries(monkeypatch)
    r = run(_tipping_head(sc))
    assert not r.rows, [core.row_text(x) for x in r.rows]
    assert r.stats["held"] == 0 and r.stats["still_pairs"] == 0
    assert r.stats["pair_windows"] == 2
    n_fast = r.stats["narrow"]
    thorough(monkeypatch)
    slow = run(sc)
    assert not slow.rows
    assert n_fast * 5 < slow.stats["narrow"], (n_fast, slow.stats["narrow"])


def test_a_bolt_in_the_spokes_way_is_still_found(sc, monkeypatch):
    """The same with a bolt on the head 10 mm into the room the spokes sweep: the sheave is not round where the bolt
    is, so that pair keeps its full check; every pass of a spoke is found, as in the thorough check."""
    only_the_world_carries(monkeypatch)
    r = run(_tipping_head(sc, bolt=True))
    rows = [x for x in r.rows if x.kind == "CLASH"]
    assert rows and all({x.a, x.b} == {"SHEAVE", "BOLT"} for x in rows), [core.row_text(x) for x in r.rows]
    assert len(rows) >= 10                                          # 3 turns x 4 spokes
    assert max(x.depth for x in rows) > 9 * MM, [core.row_text(x) for x in rows]
    assert r.stats["pair_windows"] == 2                             # the pin and the head; never the bolt
    thorough(monkeypatch)
    same_rows(r, run(sc))



# ---------------------------------------------------------------------------
# a part that repeats after a step of angle (a carousel's rim fence of posts)
# ---------------------------------------------------------------------------

POSTS = 24


def _fence_ring(odd=0.0):
    """A turntable's rim fence about Z: a round rail (r 0.95 … 1.0 m, z 0 … 0.05) and 24 posts (40 mm square, outer
    face at r 1.0, up to z 0.4). ``odd``: the first post sticks out this much further (the fence no longer repeats)."""
    shapes = [_ring(0.95, 1.0, 0.0, 0.05, 192)]
    for k in range(POSTS):
        a = 2 * math.pi * k / POSTS
        out = 1.0 + (odd if k == 0 else 0.0)
        bv, bt = box((0.96, -0.02, 0.05), (out, 0.02, 0.4))
        shapes.append(([(x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a), z) for x, y, z in bv],
                       bt))
    return _join(*shapes)


def _carousel(scene, gap, odd=0.0, turns=2.5):
    """The fence turns ``turns`` times; a bracket stands outside it, ``gap`` m from the posts' outer faces (negative:
    into their way), between z 0.2 and 0.3 (above the rail)."""
    fence = part(scene, "RIM FENCE", _fence_ring(odd))
    part(scene, "BRACKET", box((1.0 + gap, -0.05, 0.2), (1.2, 0.05, 0.3)))
    start = math.pi / POSTS                                        # the bracket half way between two posts
    keys(fence, "rotation_euler", [(0, 0, start), (0, 0, start + turns * 2 * math.pi)])
    return built(scene)


def test_a_rim_fence_turning_past_a_bracket_is_checked_over_one_post_step(sc, monkeypatch):
    """The posts pass 2 mm from the bracket 60 times. The fence is not round, and the bracket is in the room its posts
    sweep, but turned by 1/24 turn it lands on itself: once one post step has been checked the pair is left alone. No
    rows, as in the thorough check, with far fewer tests."""
    r = run(_carousel(sc, 2 * MM))
    assert not r.rows, [core.row_text(x) for x in r.rows]
    assert r.stats["period_windows"] == 1
    n_fast = r.stats["narrow"]
    thorough(monkeypatch)
    slow = run(sc)
    assert not slow.rows
    assert n_fast * 3 < slow.stats["narrow"], (n_fast, slow.stats["narrow"])


def test_every_post_running_through_the_bracket_is_found(sc, monkeypatch):
    """The bracket 3 mm into the posts' way: every post passing it is a clash (no step without one, so no shortcut);
    the same rows as the thorough check."""
    r = run(_carousel(sc, -3 * MM, turns=0.5))
    rows = [x for x in r.rows if x.kind == "CLASH"]
    assert len(rows) >= POSTS // 2 - 1 and all({x.a, x.b} == {"RIM FENCE", "BRACKET"} for x in rows)
    assert r.stats["period_windows"] == 0
    thorough(monkeypatch)
    same_rows(r, run(sc))


def test_one_odd_post_is_found_every_turn(sc, monkeypatch):
    """One post sticks out 5 mm further and runs 3 mm into the bracket once per turn; the others pass 2 mm clear. The
    fence does not repeat where the bracket is: no shortcut, the odd post is found on each of its two passes in 2.5 turns
    (the thorough check finds the same)."""
    r = run(_carousel(sc, 2 * MM, odd=5 * MM))
    rows = [x for x in r.rows if x.kind == "CLASH"]
    assert len(rows) == 2 and all({x.a, x.b} == {"RIM FENCE", "BRACKET"} for x in rows), \
        [core.row_text(x) for x in r.rows]
    assert r.stats["period_windows"] == 0
    thorough(monkeypatch)
    same_rows(r, run(sc))
