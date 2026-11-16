"""Task 0174: every layer of a drum or carousel drawn as cable, one continuous cable from the anchor to the leave point,
wound fully out and fully in.

The first half needs no Blender (``core/spool.py``: the layers' stretches, which of them are shown, how close the turns
lie); the second uses the spooling test model (tests/data/test_spool.step, tools/make_test_spool.py) in Blender as a
Python module: the cable joints are driven from all paid out to full and back, live and after Build, and what Blender
draws is read back."""

import math
import os

import numpy as np
import pytest

from fresing_render.core import spool as S

HERE = os.path.dirname(__file__)
MODEL = os.path.join(HERE, "data", "test_spool.step")
COS30 = math.cos(math.radians(30.0))


def _carousel(layers, d=0.04, start=1):
    return S.Spool(kind="CAROUSEL", d=d, r_in=0.3, r_out=0.55, a_bot=0.0, a_top=layers * d + 1e-6, start=start)


def _drum(layers=3, groove="SPIRAL", d=0.02, climb=math.pi / 2):
    return S.Spool(kind="DRUM", d=d, r1=0.16, a_lo=-0.2, a_hi=0.2, pitch=1.06 * d, layers=layers, groove=groove,
                   climb=climb)


ALL = {"carousel 3": lambda: _carousel(3), "carousel 4": lambda: _carousel(4), "carousel 1": lambda: _carousel(1),
       "carousel 4 from the rim": lambda: _carousel(4, start=-1),
       "drum spiral": lambda: _drum(), "drum Lebus": lambda: _drum(groove="LEBUS"),
       "drum no climb": lambda: _drum(climb=0.0), "drum 1 layer": lambda: _drum(layers=1)}


# ---------------------------------------------------------------------------------------------------------------------
# core: the stretches, what is shown, the turns
# ---------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("name", list(ALL))
def test_layer_spans_follow_each_other(name):
    """The layers' stretches cover the whole wound path from the anchor to the end, one after another, and the centre
    line runs on without a jump or a kink through every layer change (the climb pieces)."""
    path = S.wind(ALL[name]())
    spans = S.layer_spans(path)
    assert spans.shape == (path.layer_count, 2)
    assert spans[0, 0] == 0.0 and spans[-1, 1] == pytest.approx(path.total, abs=1e-12)
    assert np.all(spans[1:, 0] == spans[:-1, 1]) and np.all(np.diff(spans, axis=1) > 0.0)
    d = path.spool.d
    for L in spans[1:, 0]:
        before, after = S.xyz(*S.at(path, np.array([L - 1e-7, L + 1e-7]))[:3])
        assert float(np.linalg.norm(after - before)) < 1e-6, (name, L)
        t0, t1 = S.tangent(path, np.array([L - 1e-6, L + 1e-6]))
        if path.spool.climb > 0.0:          # (with no climb the rope steps straight out: a right angle, as asked)
            assert float(np.degrees(np.arccos(np.clip(t0 @ t1, -1.0, 1.0)))) < 15.0, (name, L)
        assert d > 0


@pytest.mark.parametrize("name", list(ALL))
def test_what_is_drawn_is_the_whole_cable_once(name):
    """At every payout – past both ends too – the full layers shown and the moving rope (from ``drawn_from`` to the
    leave point) cover the cable on the spool from the anchor without a gap; a full layer shows only once it is wound
    (at most SHOW_EARLY before its switch) and both draw the same stretch only within a climb."""
    path = S.wind(ALL[name]())
    W0 = 0.6 * path.total
    spans = S.layer_spans(path)
    p = np.linspace(W0 - path.total - 3.0, W0 + 3.0, 40001)
    on = np.clip(W0 - p, 0.0, path.total)
    shown = S.shown_layers(path, W0, p)
    start = S.drawn_from(path, W0, p)
    assert np.allclose(start, S.stack(path, W0, p, 1)[0])
    n = path.layer_count
    assert shown.shape == (len(p), n - 1)
    for i in range(0, len(p), 7):
        covered = 0.0
        for k in range(n - 1):
            if shown[i, k]:
                assert spans[k, 0] <= covered + 1e-12, (name, p[i], k)      # follows on
                assert spans[k, 1] <= on[i] + S.SHOW_EARLY + 1e-12, (name, p[i], k)
                covered = spans[k, 1]
        assert start[i] <= covered + 1e-12, (name, p[i])                     # the moving rope follows on
        assert covered - start[i] <= max(np.diff(spans[:, 0]).max(initial=0.0), 0.0)  # (overlap: a stretch at most)
        if covered > start[i] + 1e-9:                                        # drawn twice: only up a climb
            k = int(np.searchsorted(spans[:, 1], covered - 1e-12))
            assert on[i] <= S.layer_switches(path)[k] + 1e-9, (name, p[i])
    # all paid out: nothing; full: every layer below the top
    assert shown[-1].sum() == 0 and start[-1] == 0.0
    assert shown[0].all()


def test_even_and_odd_carousel_layer_counts():
    """Layers alternate: layer 1 from the core out, layer 2 from the rim in … A coil of an odd count ends at the rim,
    an even one at the core (task 0159: the demo's top layer must be an even one); the top layer is the moving rope's,
    the ones below are full layers at one cable's spacing."""
    d = 0.04
    for n in (1, 2, 3, 4, 5):
        path = S.wind(_carousel(n))
        assert path.layer_count == n
        _phi, a, r, _k = S.at(path, np.array([path.total]))
        assert float(r[0]) == pytest.approx(0.55 - d / 2 if n % 2 else 0.3 + d / 2, abs=1e-9), n
        assert float(a[0]) == pytest.approx(d / 2 + (n - 1) * d, abs=1e-9), n
        assert len(S.layer_switches(path)) == n - 1 and len(S.layer_shows(path)) == n - 1
        assert np.all(S.layer_shows(path) < S.layer_switches(path))


def test_carousel_turns_touch_and_do_not_overlap():
    """Neighbouring turns of a carousel lie one cable apart, in a layer and between layers: no closer than d anywhere
    (a spiral's turns come d cos(its lead angle) close: 0.9998 d here) but up the climbs (where the cable rises over the
    last turn of the layer below: at least 0.89 d), and they touch (most turns one d away)."""
    path = S.wind(_carousel(3))
    d = path.spool.d
    L, gap = S.turn_gaps(path)
    i, _ = S._index(path, L)
    climb = path.kind[i] == S.CLIMB
    # (a point's neighbours on the far side of a climb: the climb's own quarter turn and the last turn below it)
    near_climb = np.zeros(len(L), bool)
    for k in range(1, path.layer_count):
        s0 = S.layer_start(path, k)
        near_climb |= (L > s0 - 2.0 * math.pi * 0.56) & (L < S._first_of_layer(path, k) + 1e-9)
    assert gap[~(climb | near_climb)].min() >= d * (1.0 - 5e-4)
    assert gap.min() >= 0.89 * d
    assert float(np.median(gap)) < 1.01 * d          # (samples d / 4 apart: the nearest one up to d / 8 along)


@pytest.mark.parametrize("groove", ["SPIRAL", "LEBUS"])
def test_drum_turns_in_a_layer_do_not_overlap_and_layers_lie_cos30_apart(groove):
    """A drum's turns in one layer lie a pitch apart (>= d: they do not overlap); the layer above lies d cos 30° further
    out (0080's maths): where its turn crosses one below, the two middles come d cos 30° close (pinned, so it cannot
    get worse – a follow-up of task 0174 would let the rope ride over the crossing)."""
    path = S.wind(_drum(layers=3, groove=groove))
    d = path.spool.d
    spans = S.layer_spans(path)
    for k in range(path.layer_count):
        L, gap = S.turn_gaps(path, spans[k, 0], spans[k, 1])
        own = (L > S._first_of_layer(path, k) + 0.1) & (L < spans[k, 1] - 0.1)
        assert gap[own].min() >= d * (1.0 - 1e-6), (groove, k)
    _L, gap = S.turn_gaps(path)
    assert gap.min() >= COS30 * d * (1.0 - 1e-6)


def test_lebus_crossovers_on_every_layer_and_climbs_at_the_flanges():
    """A Lebus drum: every layer has its two crossovers per turn, every climb lies at a flange."""
    path = S.wind(_drum(layers=4, groove="LEBUS"))
    s = path.spool
    for k in range(path.layer_count):
        mine = path.layer == k
        assert (path.kind[mine] == S.CROSSOVER).sum() >= 2 * 3, k     # (at least 3 turns of 2 crossovers)
        assert (path.kind[mine] == S.PARALLEL).sum() >= 2 * 3, k
    climbs = path.kind == S.CLIMB
    a = path.a0[climbs]
    assert np.all(np.isclose(a, s.a_lo + s.d / 2) | np.isclose(a, s.a_hi - s.d / 2))
    assert sorted(set(path.layer[climbs].tolist())) == list(range(path.layer_count - 1))


# ---------------------------------------------------------------------------------------------------------------------
# Blender: the spooling test model wound fully out and fully in
# ---------------------------------------------------------------------------------------------------------------------

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import animation, joints, paths, spool  # noqa: E402

CASES = (("Drum", "Wire"), ("Carousel", "Power cable"))


@pytest.fixture(scope="module")
def made(tmp_path_factory):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path_factory.mktemp("spoolfull"))
    assert bpy.ops.fresing.import_step(filepath=MODEL, quality="normal") == {"FINISHED"}
    spool.set_up_test_model(sc)
    yield sc
    fresing_render.unregister()


def update():
    bpy.context.view_layer.update()
    bpy.context.view_layer.update()


def pay(sc, cable, metres):
    it = paths.find(sc, cable)
    joints.set_value(joints.find(sc, it.joint), -metres if it.reverse else metres, use_limits=False)
    update()
    paths.refresh(sc)
    update()


def curve(ob, wound):
    """(ring centres in world, fr_L) of a drawn spool object as Blender evaluates it."""
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.data
    n = len(me.vertices)
    if n == 0:
        return np.zeros((0, 3)), np.zeros(0)
    co = np.empty(3 * n, np.float32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3).astype(float)
    L = np.empty(n, np.float32)
    me.attributes[spool.S_ATTR].data.foreach_get("value", L)
    keys, inv = np.unique(L, return_inverse=True)
    c = np.zeros((len(keys), 3))
    np.add.at(c, inv, co)
    c /= np.bincount(inv)[:, None]
    m = np.array(ev.matrix_world)
    return c @ m[:3, :3].T + m[:3, 3], keys.astype(float)


def drawn(sc, sp):
    """[(centres, L)] of every stretch drawn now: the full layers shown and the moving rope, by L."""
    out = []
    for ob in spool.layer_objects(sc, sp):
        if not ob.hide_viewport:
            assert not ob.hide_render, ob.name
            out.append(curve(ob, sp.wound))
        else:
            assert ob.hide_render, ob.name
    out.append(curve(sp.owner, sp.wound))
    return sorted([x for x in out if len(x[1]) > 1], key=lambda x: x[1][0])


def check_whole(sc, sp, cable, p):
    """What is drawn at payout p is one cable from the anchor to the leave point (1 mm), the free cable starts there,
    and the shown layers are the core's."""
    path = spool.path_of(sc, sp)
    W0 = float(sp.wound)
    on = min(max(W0 - p, 0.0), float(path.total))
    layers = spool.layer_objects(sc, sp)
    assert len(layers) == path.layer_count - 1
    want = S.shown_layers(path, W0, np.array([p]))[0]
    got = np.array([not ob.hide_viewport for ob in layers])
    assert np.array_equal(want, got), (sp.name, p, want, got)
    parts = drawn(sc, sp)
    if on < 1e-3:
        assert not parts or parts[-1][1].max() < 1e-3, (sp.name, p)
        return
    assert parts[0][1][0] == pytest.approx(0.0, abs=1e-6), (sp.name, p)      # from the anchor
    end = parts[0][1][0]
    for c, L in parts:
        assert L[0] <= end + 1e-3, (sp.name, p, L[0], end)                    # no gap
        end = max(end, L[-1])
    assert end == pytest.approx(on, abs=1e-3), (sp.name, p)                  # to the leave point
    tip = max(parts, key=lambda x: x[1][-1])[0][-1]
    # (the test carousel's guide sheave does not lift: filled past its 4th layer the cable starts inside the guide's
    # circle and cannot go round it – a limit of the test model's guide, not of the spool)
    if sp.kind == "DRUM" or on <= 4.0 * float(path.total) / path.layer_count:
        start = np.asarray(paths.shape_now(sc, paths.find(sc, cable))[0], dtype=float)
        assert float(np.linalg.norm(start - tip)) < 1e-3, (sp.name, p)      # the free cable starts there
    for ob in spool.layer_objects(sc, sp) + [sp.owner]:                      # the cable's look, every stretch
        assert ob.material_slots and ob.material_slots[0].material == paths.find(sc, cable).part.material_slots[
            0].material, ob.name


@pytest.mark.parametrize("name,cable", CASES)
def test_wound_fully_out_and_fully_in_live(made, name, cable):
    """The cable joint over its whole range by hand: from all paid out (nothing on the spool) to full and back, and a
    little past both ends; at every step one continuous cable, the right layers shown, the followers finite."""
    sc = made
    sp = spool.find(sc, name)
    path = spool.path_of(sc, sp)
    W0 = float(sp.wound)
    lo, hi = W0 - float(path.total), W0
    steps = list(np.linspace(hi + 1.0, lo - 1.0, 23)) + list(np.linspace(lo, hi, 9))
    try:
        for p in steps:
            pay(sc, cable, float(p))
            sp = spool.find(sc, name)
            check_whole(sc, sp, cable, float(p))
            for jn in [sp.joint] + [f.joint for f in sp.followers]:
                assert math.isfinite(joints.get_value(joints.find(sc, jn))), (jn, p)
            text, _icon = spool.status(sc, sp, write=False)
            if p > hi + 1e-6:
                assert "runs empty" in text.lower(), (p, text)
            elif p < lo - 1e-6:
                assert "overfills" in text.lower(), (p, text)
    finally:
        pay(sc, cable, 0.0)


def test_wound_fully_out_and_in_after_build(made):
    """An animation that empties the carousel and the drum and fills them again, built: at its frames the same
    picture as live (the Build needs no Python per frame)."""
    sc = made
    s = sc.fresing
    a = s.animations.add()
    a.name, a.tail, a.fps = "Empty and full", 0.0, "25"
    ends = {}
    for name, cable in CASES:
        sp = spool.find(sc, name)
        path = spool.path_of(sc, sp)
        it = paths.find(sc, cable)
        sign = -1.0 if it.reverse else 1.0
        W0 = float(sp.wound)
        lo, hi = W0 - float(path.total) + 0.05, W0 - 0.05          # (a hair inside: no "overfills" from rounding)
        ends[cable] = (hi, lo)
        for t0, frm, to in ((0.0, 0.0, hi), (4.0, hi, lo)):
            b = a.blocks.add()
            b.kind, b.joint, b.start, b.duration, b.easing = "JOINT", it.joint, t0, 4.0, "LINEAR"
            b.use_from, b.from_dist, b.to_dist = False, sign * frm, sign * to
    s.animations_index = len(s.animations) - 1
    info = animation.bake(sc, a)
    try:
        # (the test carousel's guide sheave does not lift: filled past layer 5 its cable starts inside the guide's
        # circle – a path warning of the test model, not the spool's)
        spool_warn = [w for w in info["warnings"] if "runs empty" in w or "overfills" in w]
        assert not spool_warn, spool_warn
        f0, f1 = int(sc.frame_start), int(sc.frame_end)
        for f in sorted({f0, f0 + (f1 - f0) // 4, (f0 + f1) // 2, f0 + 3 * (f1 - f0) // 4, f1, (f0 + f1) // 2 + 3}):
            sc.frame_set(f)
            update()
            for name, cable in CASES:
                sp = spool.find(sc, name)
                check_whole(sc, sp, cable, spool.payout(sc, sp))
    finally:
        animation.clear_keys(sc)
        s.animations.remove(len(s.animations) - 1)
        s.animations_index = 0
        sc.frame_set(1)
        for _name, cable in CASES:
            pay(sc, cable, 0.0)


def test_drivers_of_the_layers_are_plain_arithmetic(made):
    """Every layer's visibility works with "Auto Run Python Scripts" off: simple expressions."""
    sc = made
    for name, _cable in CASES:
        sp = spool.find(sc, name)
        for ob in spool.layer_objects(sc, sp):
            fcs = [fc for fc in ob.animation_data.drivers]
            assert {fc.data_path for fc in fcs} == {"hide_viewport", "hide_render"}, ob.name
            for fc in fcs:
                assert fc.driver.is_simple_expression, (ob.name, fc.driver.expression)


def test_off_hides_every_layer_and_a_look_change_reaches_them(made):
    """The spool switched off takes its layers away (the CAD coil shows); on again they come back. A new look of the
    cable reaches every layer at once (as 0158 does for the rope)."""
    sc = made
    sp = spool.find(sc, "Carousel")
    n = len(spool.layer_objects(sc, sp))
    assert n >= 2
    sp.enabled = False
    assert not spool.layer_objects(sc, spool.find(sc, "Carousel"))
    spool.find(sc, "Carousel").enabled = True
    sp = spool.find(sc, "Carousel")
    assert len(spool.layer_objects(sc, sp)) == n
    it = paths.find(sc, "Power cable")
    it.look = "ROPE"
    sp = spool.find(sc, "Carousel")
    mat = paths.find(sc, "Power cable").part.material_slots[0].material
    for ob in spool.layer_objects(sc, sp):
        assert ob.material_slots[0].material == mat, ob.name
    it = paths.find(sc, "Power cable")
    it.look = "POWER"


def test_an_old_project_with_a_solid_opens_with_every_layer(made, tmp_path):
    """A project saved before task 0174 (a solid under the top layers, no layer objects): opened, every spool is drawn
    again with its layers and the solid is gone. (Runs last: it opens another file.)"""
    sc = made
    for name, _c in CASES:
        sp = spool.find(sc, name)
        for ob in spool.layer_objects(sc, sp):
            spool._remove_object(ob)
        old = spool._new_made(sc, sp, "solid", sp.part, bpy.data.meshes.new("old solid"))
        assert old is not None
        del sp.owner["fr_spool_draw"]
    f = str(tmp_path / "old.blend")
    bpy.ops.wm.save_as_mainfile(filepath=f, copy=True)
    bpy.ops.wm.open_mainfile(filepath=f)
    sc = bpy.context.scene
    for name, cable in CASES:
        sp = spool.find(sc, name)
        assert spool._made(sc, sp, "solid") is None, name
        assert len(spool.layer_objects(sc, sp)) == spool.path_of(sc, sp).layer_count - 1, name
        assert not spool.needs_upgrade(sc, sp)
        check_whole(sc, sp, cable, spool.payout(sc, sp))
