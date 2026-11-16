"""Task 0174, the independent tester's checks (written from the brief, not from the author's tests): every layer of a
drum or carousel drawn as cable – the full layers as static objects shown by a driver, the layer being paid out as the
moving rope.

What is checked against what (expectations derived here, not copied):
- core: each piece of the wound path lies in the stretch of the layer it belongs to (a climb in the layer it climbs
  into); a one-layer spool has no full layers; far past both ends nothing / everything is shown;
- Blender, read back from what Blender evaluates: at a payout p (on the spool: W0 - p, clipped) a full layer whose
  turns the moving rope has left (on the spool past the climb out of it) MUST be shown, one not yet wound to its end
  MUST NOT; the stretches drawn cover the cable from the anchor to the leave point without a gap and meet point on
  point; every drawn ring is the cable's radius and lies on the wound path (radius about the joint's axis, height
  along it); at payout 0 the full layers lie inside the CAD coil (WIRE ON DRUM, CABLE COIL: tools/make_test_spool.py);
- set-up changes: groove, first-layer radius (layer count), cable diameter, the length typed, on/off, part hidden, the
  look; save + open, the load handler run again (undo), an old project with a solid, a model update, a carousel whose
  joint axis points down, the web export's stand-in solid.
"""

from __future__ import annotations

import math
import os

import numpy as np
import pytest

from fresing_render.core import spool as S

HERE = os.path.dirname(__file__)
MODEL = os.path.join(HERE, "data", "test_spool.step")
CASES = (("Drum", "Wire"), ("Carousel", "Power cable"))
COILS = {"Drum": "WIRE ON DRUM", "Carousel": "CABLE COIL"}
GAP_TOL = 2e-4          # m along the cable (fr_L is stored in 32 bits)
SEAM_TOL = 3e-4         # m: two stretches that meet: the same point
PLACE_TOL = 1.5e-3      # m: a drawn ring centre off the true wound path (the drawing's sag is 0.5-0.7 mm)


# ---------------------------------------------------------------------------------------------------------------------
# core
# ---------------------------------------------------------------------------------------------------------------------

def _carousel(layers, d=0.03, start=1):
    return S.Spool(kind="CAROUSEL", d=d, r_in=0.25, r_out=0.5, a_bot=0.0, a_top=layers * d + 1e-6, start=start)


def _drum(layers=4, groove="SPIRAL", d=0.016, climb=math.pi / 2):
    return S.Spool(kind="DRUM", d=d, r1=0.12, a_lo=-0.15, a_hi=0.15, pitch=1.08 * d, layers=layers, groove=groove,
                   climb=climb)


SPOOLS = {"carousel 1": lambda: _carousel(1), "carousel 2": lambda: _carousel(2), "carousel 5": lambda: _carousel(5),
          "carousel 3 rim": lambda: _carousel(3, start=-1), "drum 1": lambda: _drum(layers=1),
          "drum spiral 4": lambda: _drum(), "drum Lebus 4": lambda: _drum(groove="LEBUS"),
          "drum Lebus no climb": lambda: _drum(groove="LEBUS", climb=0.0)}


@pytest.mark.parametrize("name", list(SPOOLS))
def test_core_every_piece_lies_in_its_layers_stretch(name):
    """A piece labelled layer k lies in layer k's stretch; a climb labelled k (from k to k + 1) in layer k + 1's."""
    path = S.wind(SPOOLS[name]())
    spans = S.layer_spans(path)
    n = path.layer_count
    assert spans.shape == (n, 2)
    owner = np.where(path.kind == S.CLIMB, path.layer + 1, path.layer)
    assert owner.max() <= n - 1
    lo, hi = spans[owner, 0], spans[owner, 1]
    assert np.all(path.L0 >= lo - 1e-9) and np.all(path.L1 <= hi + 1e-9), name
    # the switches lie inside the next layer's stretch, after its climb: on its own pieces' start
    sw = S.layer_switches(path)
    for k in range(n - 1):
        assert spans[k + 1, 0] <= sw[k] < spans[k + 1, 1], (name, k)
        first = np.nonzero((path.layer == k + 1) & (path.kind != S.CLIMB))[0][0]
        assert sw[k] == pytest.approx(path.L0[first], abs=1e-9), (name, k)


@pytest.mark.parametrize("name", list(SPOOLS))
def test_core_shown_layers_far_past_both_ends_and_one_layer(name):
    """Far past either end (a joint typed kilometres off): nothing / every full layer; a one-layer spool has no full
    layer at all and its rope always starts at the anchor."""
    path = S.wind(SPOOLS[name]())
    n = path.layer_count
    W0 = 0.5 * path.total
    p = np.array([W0 + 1e6, W0 + 1.0, W0, W0 - path.total, W0 - path.total - 1.0, W0 - path.total - 1e6])
    shown = S.shown_layers(path, W0, p)
    start = S.drawn_from(path, W0, p)
    assert shown.shape == (len(p), n - 1)
    assert not shown[:3].any() and np.all(start[:3] == 0.0)
    assert shown[3:].all()
    spans = S.layer_spans(path)
    assert np.allclose(start[3:], spans[-1, 0])
    if n == 1:
        assert len(S.layer_switches(path)) == 0 and len(S.layer_shows(path)) == 0
        assert np.all(S.drawn_from(path, W0, np.linspace(-10, 10, 101)) == 0.0)


@pytest.mark.parametrize("name", list(SPOOLS))
def test_core_my_rule_for_what_must_and_must_not_show(name):
    """At every amount on the spool: a full layer the rope has left (on > its switch) is shown; a layer not yet wound
    to its end (on < its stretch's end) is not; the moving rope starts at or below the end of what the shown layers
    cover; it never starts below the stretch of the layer it is on."""
    path = S.wind(SPOOLS[name]())
    spans = S.layer_spans(path)
    sw = S.layer_switches(path)
    W0 = path.total
    on = np.linspace(0.0, path.total, 20001)
    on = np.unique(np.concatenate([on, sw, sw + 1e-6, sw - 1e-6, spans[:, 1], spans[:, 1] - 1e-6]))
    on = on[(on >= 0) & (on <= path.total)]
    p = W0 - on
    shown = S.shown_layers(path, W0, p)
    start = S.drawn_from(path, W0, p)
    for k in range(path.layer_count - 1):
        must = on > sw[k] + 1e-7
        must_not = on < spans[k, 1] - 1e-7
        assert shown[must, k].all(), (name, k)
        assert not shown[must_not, k].any(), (name, k)
    covered = np.where(shown.any(axis=1), spans[np.maximum(shown.sum(axis=1) - 1, 0), 1], 0.0)
    assert np.all(start <= covered + 1e-9), name
    _phi, _a, _r, layer = S.at(path, np.clip(on - 1e-9, 0.0, None))
    assert np.all(start >= spans[np.maximum(np.asarray(layer) - 1, 0), 0] - 1e-9)   # at most one layer + climb back


def test_core_carousel_spiral_turns_one_cable_apart():
    """A one-layer carousel: neighbouring turns of the spiral one cable apart (they touch, no overlap)."""
    path = S.wind(_carousel(1))
    d = path.spool.d
    _L, gap = S.turn_gaps(path)
    assert gap.min() >= 0.999 * d
    assert np.median(gap) <= 1.01 * d


# ---------------------------------------------------------------------------------------------------------------------
# Blender
# ---------------------------------------------------------------------------------------------------------------------

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import build, cable_looks, joints, paths, spool, web3d, web3d_drawn  # noqa: E402

_DIRTY = [True]
_SEEN = {}              # what the normal set-up drew (for the down-pointing carousel)


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture(scope="module")
def folder(tmp_path_factory):
    return str(tmp_path_factory.mktemp("spool_full_independent"))


def _build_scene(folder, carousel_down=False):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    sc.fresing.out_folder = folder
    assert bpy.ops.fresing.import_step(filepath=MODEL, quality="normal") == {"FINISHED"}
    create = joints.create

    def flipped(scene, kind, members, origin, direction, *a, **kw):
        if kw.get("name") == "Carousel turn":
            direction = -direction
        return create(scene, kind, members, origin, direction, *a, **kw)
    if carousel_down:
        joints.create = flipped
    try:
        spool.set_up_test_model(sc)
    finally:
        joints.create = create
    update()
    return bpy.context.scene


@pytest.fixture()
def made(folder):
    if _DIRTY[0] or spool.find(bpy.context.scene, "Drum") is None:
        _build_scene(folder)
        _DIRTY[0] = False
    sc = bpy.context.scene
    yield sc
    sc = bpy.context.scene
    try:
        for _n, cable in CASES:
            if paths.find(sc, cable) is not None:
                pay(sc, cable, 0.0)
    except Exception:
        _DIRTY[0] = True


def update():
    bpy.context.view_layer.update()
    bpy.context.view_layer.update()


def pay(sc, cable, metres):
    it = paths.find(sc, cable)
    joints.set_value(joints.find(sc, it.joint), -metres if it.reverse else metres, use_limits=False)
    update()
    paths.refresh(sc)
    update()


def rings(ob):
    """(L keys sorted, ring centres in world (m, 3), largest |ring radius - mean ring radius|, mean ring radius) of a
    drawn object as Blender evaluates it."""
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.data
    n = len(me.vertices)
    if n == 0 or spool.S_ATTR not in me.attributes:
        return np.zeros(0), np.zeros((0, 3)), 0.0, 0.0
    co = np.empty(3 * n, np.float32)
    me.vertices.foreach_get("co", co)
    m = np.array(ev.matrix_world)
    co = co.reshape(-1, 3).astype(float) @ m[:3, :3].T + m[:3, 3]
    L = np.empty(n, np.float32)
    me.attributes[spool.S_ATTR].data.foreach_get("value", L)
    keys, inv = np.unique(L, return_inverse=True)
    c = np.zeros((len(keys), 3))
    np.add.at(c, inv, co)
    cnt = np.bincount(inv)
    c /= cnt[:, None]
    rad = np.linalg.norm(co - c[inv], axis=1)
    big = cnt[inv] > 2                                  # (a ring: not a cap's centre point)
    mean = float(rad[big].mean()) if big.any() else 0.0
    dev = float(np.abs(rad[big] - mean).max()) if big.any() else 0.0
    return keys.astype(float), c, dev, mean


def axis_of(sc, sp):
    """(origin, unit z of the spool frame (layers grow along it on a carousel)) in world."""
    fr = joints.find(sc, sp.joint).frame
    m = np.array(fr.matrix_world)
    z = m[:3, 2] / np.linalg.norm(m[:3, 2])
    return m[:3, 3], z * float(sp.zsign)


def drawn(sc, sp):
    """[(kind, L, centres, dev, radius)] of what is shown now, sorted by where it starts."""
    out = []
    for ob in spool.layer_objects(sc, sp):
        assert bool(ob.hide_viewport) == bool(ob.hide_render), ob.name
        if not ob.hide_viewport:
            out.append(("layer " + str(ob.get("fr_spool_layer")),) + rings(ob))
    if sp.owner is not None and not sp.owner.hide_viewport:
        out.append(("rope",) + rings(sp.owner))
    return sorted([x for x in out if len(x[1]) > 1], key=lambda x: x[1][0])


def check(sc, name, p=None, where=""):
    """What is drawn now for spool ``name`` against the brief: see the module's docstring."""
    sp = spool.find(sc, name)
    path = spool.path_of(sc, sp)
    W0 = float(sp.wound)
    p = spool.payout(sc, sp) if p is None else p
    on = min(max(W0 - p, 0.0), float(path.total))
    tag = (name, where, round(p, 4), round(on, 4))
    spans = S.layer_spans(path)
    sw = S.layer_switches(path)
    layers = spool.layer_objects(sc, sp)
    assert len(layers) == path.layer_count - 1, tag + (len(layers), path.layer_count)
    assert sorted(int(ob["fr_spool_layer"]) for ob in layers) == list(range(path.layer_count - 1)), tag
    for ob in layers:
        k = int(ob["fr_spool_layer"])
        if on > sw[k] + 1e-5:
            assert not ob.hide_viewport, tag + (f"layer {k + 1} must show: on {on} > switch {sw[k]}",)
        if on < spans[k, 1] - 1e-5:
            assert ob.hide_viewport, tag + (f"layer {k + 1} must not show: on {on} < its end {spans[k, 1]}",)
    parts = drawn(sc, sp)
    d = spool.diameter(sc, sp)
    if on < 1e-3:
        assert not parts or max(x[1].max() for x in parts) < 2e-3, tag
        return parts
    assert parts, tag
    assert parts[0][1][0] <= GAP_TOL, tag + ("not from the anchor", parts[0][0], parts[0][1][0])
    cover = 0.0
    for i, (kind, L, c, dev, rad) in enumerate(parts):
        assert L[0] <= cover + GAP_TOL, tag + (f"gap before {kind}: {cover} .. {L[0]}",)
        if i:                                            # its first point on the stretch drawn before it
            prev = [x for x in parts[:i] if x[1][0] - 1e-6 <= L[0] <= x[1][-1] + 1e-6]
            if prev:
                q = np.array([np.interp(L[0], prev[-1][1], prev[-1][2][:, j]) for j in range(3)])
                assert float(np.linalg.norm(q - c[0])) < SEAM_TOL, tag + (kind, "seam", float(np.linalg.norm(q - c[0])))
        cover = max(cover, L[-1])
        assert L[-1] <= on + 1e-3, tag + (kind, "drawn past what is on the spool", L[-1])
        assert abs(rad - d / 2) < 0.03 * d and dev < 0.03 * d, tag + (kind, "ring radius", rad, d / 2, dev)
        # on the wound path: radius about the axis and height along it
        o, z = axis_of(sc, sp)
        _phi, a, r, _k = S.at(path, L)
        v = c - o
        h = v @ z
        rr = np.linalg.norm(v - h[:, None] * z, axis=1)
        assert float(np.abs(rr - r).max()) < PLACE_TOL, tag + (kind, "radius off", float(np.abs(rr - r).max()))
        assert float(np.abs(h - a).max()) < PLACE_TOL, tag + (kind, "height off", float(np.abs(h - a).max()))
    assert cover == pytest.approx(on, abs=1e-3), tag + ("not to the leave point",)
    return parts


def probe_payouts(path, W0):
    """Payouts round every layer change (the switch, where the layer shows, its stretch's end), both ends, past them."""
    sw, sh, spans = S.layer_switches(path), S.layer_shows(path), S.layer_spans(path)
    on = [0.0, 0.004, 0.5 * spans[0, 1], path.total - 0.004, path.total]
    for k in range(len(sw)):
        for x in (sw[k], sh[k], spans[k, 1]):
            on += [x - 0.002, x - 0.0002, x + 0.0002, x + 0.002]
        on.append(0.5 * (spans[k + 1, 0] + spans[k + 1, 1]))
    p = [W0 - x for x in on if 0.0 <= x <= path.total] + [W0 + 3.0, W0 - path.total - 3.0]
    return sorted(p)


@pytest.mark.parametrize("name,cable", CASES)
def test_every_layer_change_meets_point_on_point(made, name, cable):
    """Payouts round every layer change and past both ends: the right layers shown, one cable without gaps."""
    sc = made
    sp = spool.find(sc, name)
    path = spool.path_of(sc, sp)
    W0 = float(sp.wound)
    for p in probe_payouts(path, W0):
        pay(sc, cable, p)
        check(sc, name, where="sweep")
    pay(sc, cable, 0.0)


@pytest.mark.parametrize("name,cable", CASES)
def test_full_layers_lie_in_the_cad_coil(made, name, cable):
    """At payout 0 the full layers shown lie inside the CAD coil they replace (layers 1-2 of the drum, 1-3 of the
    carousel: tools/make_test_spool.py), and the moving rope starts above them."""
    sc = made
    pay(sc, cable, 0.0)
    sp = spool.find(sc, name)
    parts = check(sc, name, where="cad")
    coil = sc.objects.get(sp.coil.name) if sp.coil else None
    assert coil is not None
    v = np.array([coil.matrix_world @ c.co for c in coil.data.vertices])
    lo, hi = v.min(axis=0), v.max(axis=0)
    d = spool.diameter(sc, sp)
    layers = [x for x in parts if x[0].startswith("layer")]
    assert len(layers) == {"Drum": 2, "Carousel": 3}[name], [x[0] for x in parts]
    for kind, _L, c, _dev, _r in layers:
        assert np.all(c >= lo + d / 2 - PLACE_TOL) and np.all(c <= hi - d / 2 + PLACE_TOL), (name, kind, lo, hi,
                                                                                            c.min(0), c.max(0))
    _SEEN[name] = (np.min([x[2].min(0) for x in parts], axis=0), np.max([x[2].max(0) for x in parts], axis=0))


def test_where_both_draw_a_layer_they_draw_the_same_tube(made):
    """Up the climb out of a full layer, the layer object and the moving rope both draw it (by design: a moment of
    overlap rather than a gap). Two tubes in one place must be the same tube, or they flicker through each other.
    Measured: the rings of the two differ by up to 0.11 mm on the drum's 20 mm wire (a turn of the ring) – below a
    visible size; pinned at 0.5 mm."""
    sc = made
    sp = spool.find(sc, "Drum")
    path = spool.path_of(sc, sp)
    W0 = float(sp.wound)
    k = 0
    left = 0.5 * (S.layer_shows(path)[k] + S.layer_switches(path)[k])
    pay(sc, "Wire", W0 - left)
    sp = spool.find(sc, "Drum")
    lay = spool.layer_objects(sc, sp)[k]
    assert not lay.hide_viewport

    def verts(ob):
        ev = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
        me = ev.data
        co = np.empty(3 * len(me.vertices), np.float32)
        me.vertices.foreach_get("co", co)
        L = np.empty(len(me.vertices), np.float32)
        me.attributes[spool.S_ATTR].data.foreach_get("value", L)
        m = np.array(ev.matrix_world)
        return co.reshape(-1, 3) @ m[:3, :3].T + m[:3, 3], L
    a, La = verts(lay)
    b, Lb = verts(sp.owner)
    common = np.intersect1d(np.unique(La), np.unique(Lb))
    assert len(common) > 100
    worst = 0.0
    for L in common[:: max(1, len(common) // 150)]:
        x, y = a[La == L], b[Lb == L]
        worst = max(worst, float(np.linalg.norm(x[:, None] - y[None], axis=-1).min(axis=1).max()))
    print(f"\nboth draw layer 1 of the drum: rings differ by up to {worst * 1000:.3f} mm")
    assert worst < 5e-4


def test_every_driver_runs_with_scripts_off_and_points_somewhere(made):
    """Every driver on every object a spool made: plain types or simple expressions, every variable's target set."""
    sc = made
    n = 0
    for ob in bpy.data.objects:
        if not ob.get(spool.TAG):
            continue
        ad = ob.animation_data
        for fc in (ad.drivers if ad else []):
            drv = fc.driver
            n += 1
            if drv.type == "SCRIPTED":
                assert drv.is_simple_expression, (ob.name, fc.data_path, drv.expression)
            for var in drv.variables:
                for t in var.targets[: (2 if var.type in ("LOC_DIFF", "ROTATION_DIFF") else 1)]:
                    assert t.id is not None, (ob.name, fc.data_path, var.name)
            assert drv.is_valid, (ob.name, fc.data_path)
    assert n >= 2 * (7 + 8)


def test_part_hidden_spool_off_and_on(made):
    """The clicked part hidden in renders hides its layers; the spool off takes them away and shows the CAD coil;
    on again they come back with the right ones shown at the payout set meanwhile."""
    sc = made
    sp = spool.find(sc, "Carousel")
    path = spool.path_of(sc, sp)
    W0 = float(sp.wound)
    pay(sc, "Power cable", W0 - 0.5 * (S.layer_spans(path)[2, 0] + S.layer_spans(path)[2, 1]))   # (on layer 3)
    check(sc, "Carousel", where="before")
    part = sp.part
    part.hide_render = True
    update()
    try:
        for ob in spool.layer_objects(sc, spool.find(sc, "Carousel")):
            assert ob.hide_viewport and ob.hide_render, ob.name
    finally:
        part.hide_render = False
        update()
    check(sc, "Carousel", where="part shown again")
    spool.find(sc, "Carousel").enabled = False
    update()
    sp = spool.find(sc, "Carousel")
    assert not spool.layer_objects(sc, sp)
    assert not [o for o in bpy.data.objects if o.get(spool.TAG) == "Carousel" and o.get("fr_spool_role") == "layer"]
    assert sp.coil.modifiers.get(spool.HIDE) is None
    pay(sc, "Power cable", W0 - 0.5 * (S.layer_spans(path)[1, 0] + S.layer_spans(path)[1, 1]))   # (on layer 2)
    spool.find(sc, "Carousel").enabled = True
    update()
    paths.refresh(sc)
    update()
    check(sc, "Carousel", where="on again")
    assert spool.find(sc, "Carousel").coil.modifiers.get(spool.HIDE) is not None


def test_the_look_reaches_every_layer(made):
    """A new look of the cable: every layer object has the cable part's material and look values at once."""
    sc = made
    it = paths.find(sc, "Wire")
    was = it.look
    try:
        it.look = "POWER"
        update()
        it = paths.find(sc, "Wire")
        mat = it.part.material_slots[0].material
        for ob in spool.layer_objects(sc, spool.find(sc, "Drum")) + [spool.find(sc, "Drum").owner]:
            assert ob.material_slots[0].material == mat, ob.name
            for key in cable_looks.PROPS:
                if key in it.part:
                    assert key in ob and np.allclose(np.asarray(ob[key], float), np.asarray(it.part[key], float)), \
                        (ob.name, key)
    finally:
        paths.find(sc, "Wire").look = was
        update()


def test_lebus_drum_several_layers(made):
    """The drum on a Lebus groove: layer objects for its layers, every layer change meets."""
    sc = made
    sp = spool.find(sc, "Drum")
    try:
        sp.groove = "LEBUS"
        update()
        sp = spool.find(sc, "Drum")
        assert not sp.problem, sp.problem
        path = spool.path_of(sc, sp)
        assert path.layer_count >= 4 and (path.kind == S.CROSSOVER).any()
        W0 = float(sp.wound)
        ps = probe_payouts(path, W0)
        for p in ps[:: 3] + [ps[-1]]:
            pay(sc, "Wire", p)
            check(sc, "Drum", where="lebus")
    finally:
        _DIRTY[0] = True


def test_first_layer_radius_changes_the_layer_count(made):
    """Fewer layers (a bigger first-layer radius), then one layer only, then back: no stale layer object left, none
    missing, each one's stretch the new path's."""
    sc = made
    sp = spool.find(sc, "Drum")
    r1 = float(sp.r1)
    n0 = spool.path_of(sc, sp).layer_count
    try:
        for r in (r1 + 0.06, float(sp.r_max) - 0.012, r1):
            sp = spool.find(sc, "Drum")
            sp.r1 = r
            update()
            sp = spool.find(sc, "Drum")
            path = spool.path_of(sc, sp)
            assert not sp.problem or "overfills" in sp.problem, (r, sp.problem)     # (49.6 m on a smaller coil)
            objs = [o for o in bpy.data.objects if o.get(spool.TAG) == "Drum" and o.get("fr_spool_role") == "layer"]
            assert len(objs) == path.layer_count - 1, (r, len(objs), path.layer_count)
            spans = S.layer_spans(path)
            for ob in objs:
                k = int(ob["fr_spool_layer"])
                L = np.empty(len(ob.data.vertices), np.float32)
                ob.data.attributes[spool.S_ATTR].data.foreach_get("value", L)
                assert L.min() == pytest.approx(spans[k, 0], abs=1e-4) and L.max() == pytest.approx(spans[k, 1],
                                                                                                   abs=1e-4), (r, k)
            W0 = float(sp.wound)
            for p in (0.0, W0 - 0.3 * path.total, W0 - path.total + 0.01):
                pay(sc, "Wire", p)
                check(sc, "Drum", where=f"r1 {r:.3f}")
            if r == float(sp.r_max) - 0.012:
                assert path.layer_count == 1 and not objs
        assert spool.path_of(sc, spool.find(sc, "Drum")).layer_count == n0
    finally:
        _DIRTY[0] = True


def test_cable_diameter_changes_the_layers(made):
    """A thicker wire: fewer layers on the same drum; the layer objects follow (count, stretches, tube radius)."""
    sc = made
    it = paths.find(sc, "Wire")
    d0 = float(it.diameter)
    n0 = spool.path_of(sc, spool.find(sc, "Drum")).layer_count
    try:
        it.diameter = 1.5 * d0
        update()
        sp = spool.find(sc, "Drum")
        path = spool.path_of(sc, sp)
        assert path.layer_count != n0
        # FAULT (fixed by the worker: spool.after_draw draws the spool again when its numbers changed): the cable's Diameter (4 Motion > Cables and paths) goes through paths.changed -> paths._rebuild, which
        # never calls spool.changed / spool._draw: the layer objects keep the old count, stretches and tube radius
        # (and the moving rope's Start steps and radius stay the old diameter's) until something else redraws the spool.
        # Measured: Ø20 -> Ø30 mm wire: 7 layer objects for a 5-layer path, rings still 10 mm, layer 1 drawn 0-18.06 m
        # where the new path's layer 1 is 0-11.73 m.
        objs = spool.layer_objects(sc, sp)
        assert len(objs) == path.layer_count - 1, (len(objs), path.layer_count)
        pay(sc, "Wire", 0.0)
        check(sc, "Drum", where="thicker wire")
    finally:
        paths.find(sc, "Wire").diameter = d0
        _DIRTY[0] = True


def test_a_new_length_on_it_at_start(made):
    """'On it at start' typed (more, then less): the layers shown at payout 0 follow it, the rope meets them."""
    sc = made
    sp = spool.find(sc, "Carousel")
    W0 = float(sp.wound)
    path = spool.path_of(sc, sp)
    try:
        for w in (0.9 * float(path.total), 0.05 * float(path.total), W0):
            spool.find(sc, "Carousel").wound = w
            update()
            pay(sc, "Power cable", 0.0)
            check(sc, "Carousel", where=f"wound {w:.1f}")
            pay(sc, "Power cable", 1.0)
            check(sc, "Carousel", where=f"wound {w:.1f} +1")
    finally:
        _DIRTY[0] = True


def test_web_export_stand_in_solid(made):
    """During a web 3D export the full layers are one solid (the layer objects are not in the export); the solid is
    as big as the full layers; afterwards it is hidden and goes at the next drawing."""
    sc = made
    sp = spool.find(sc, "Drum")
    path = spool.path_of(sc, sp)
    W0 = float(sp.wound)
    spans = S.layer_spans(path)
    pay(sc, "Wire", W0 - 0.5 * (spans[3, 0] + spans[3, 1]))         # (on layer 4: layers 1-3 full)
    made_ = spool.web_begin(sc)
    try:
        assert len(made_) == 2, made_
        parts, _marks = web3d.objects(sc)
        assert not [o for o in parts if o.get("fr_spool_role") == "layer"]
        exported = web3d_drawn.spool_objects(sc)
        assert {o.get("fr_spool_role") for o in exported} == {"rope", "solid"}
        sp = spool.find(sc, "Drum")
        solid = spool._made(sc, sp, "solid")
        ev = solid.evaluated_get(bpy.context.evaluated_depsgraph_get())
        v = np.array([ev.matrix_world @ x.co for x in ev.data.vertices])
        o, z = axis_of(sc, sp)
        w = v - o
        rr = np.linalg.norm(w - np.outer(w @ z, z), axis=1)
        lay = [x for x in drawn(sc, sp) if x[0].startswith("layer")]
        assert len(lay) == 3
        c = np.concatenate([x[2] for x in lay])
        wc = c - o
        rc = np.linalg.norm(wc - np.outer(wc @ z, z), axis=1)
        d = spool.diameter(sc, sp)
        assert float(rr.max()) == pytest.approx(float(rc.max()) + d / 2, abs=2e-3), (rr.max(), rc.max())
    finally:
        spool.web_end(sc, made_)
    for name in made_:
        ob = bpy.data.objects.get(name)
        assert ob is None or (ob.hide_viewport and ob.hide_render)
    spool.changed(sc, spool.find(sc, "Drum"))
    spool.changed(sc, spool.find(sc, "Carousel"))
    assert not [o for o in bpy.data.objects if o.get(spool.TAG) and o.get("fr_spool_role") == "solid"]
    check(sc, "Drum", where="after web")


def test_renamed_spool_leaves_no_second_drawing(made):
    """The spool renamed (double-click in the list), then a setting changed: one rope and one set of layer objects,
    none left over from the old name; taking it off the list then leaves nothing of it."""
    sc = made
    _DIRTY[0] = True
    sp = spool.find(sc, "Drum")
    n = len(spool.layer_objects(sc, sp))
    sp.name = "Winch drum"
    update()
    sp = spool.find(sc, "Winch drum")
    sp.groove = "LEBUS"                                  # (any setting: the spool is drawn again)
    update()
    sp = spool.find(sc, "Winch drum")
    names = {s.name for s in sc.fresing.spools}
    orphans = [o.name for o in bpy.data.objects if o.get(spool.TAG) and o.get(spool.TAG) not in names]
    # FAULT (fixed by the worker: FRSpool.name has an update, spool.renamed): a spool's objects are found by the spool's name (spool.TAG == sp.name: _made, layer_objects) and nothing
    # follows a rename (FRSpool.name has no update callback, unlike the cable's since task 0160): the next drawing makes
    # a new rope and new layer objects, the old name's stay – with their drivers still live, so every full layer is
    # drawn twice (and on remove they are left for good). The rope had this before 0174; the layer objects add n more.
    shown = [o.name for o in bpy.data.objects if o.name in orphans and not o.hide_viewport]
    assert not orphans, (orphans, "shown:", shown)
    assert len(spool.layer_objects(sc, sp)) == spool.path_of(sc, sp).layer_count - 1
    spool.remove(sc, spool.index_of(sc, sp))
    assert not [o.name for o in bpy.data.objects if o.get(spool.TAG) and o.get(spool.TAG) not in
                {s.name for s in sc.fresing.spools}]
    assert n > 0


def test_removing_a_spool_leaves_nothing(made):
    """Taking a drum off the list: its rope, shapes and every layer object go, the CAD coil shows again."""
    sc = made
    _DIRTY[0] = True
    sp = spool.find(sc, "Carousel")
    coil = sp.coil
    assert spool.layer_objects(sc, sp)
    spool.remove(sc, spool.index_of(sc, sp))
    update()
    assert not [o.name for o in bpy.data.objects if o.get(spool.TAG) == "Carousel"]
    assert coil.modifiers.get(spool.HIDE) is None
    assert not [m.name for m in bpy.data.meshes if m.users == 0 and m.name.startswith("FR spool")]


def test_load_handler_again_changes_nothing(made):
    """The load / undo handler run on a project already drawn the new way: no layer object added, removed or
    renamed, the mesh of each kept."""
    sc = made
    before = sorted((o.name, o.data.name) for o in bpy.data.objects if o.get(spool.TAG))
    spool._on_load()
    spool._on_load()
    update()
    after = sorted((o.name, o.data.name) for o in bpy.data.objects if o.get(spool.TAG))
    assert before == after
    for name, _c in CASES:
        assert not spool.needs_upgrade(sc, spool.find(sc, name))


def test_save_and_open_keeps_layers_and_drivers(made, tmp_path):
    """Saved and opened again: the layer objects, their drivers (still simple, still reading the cable joint) and the
    picture at a payout set before and after opening."""
    sc = made
    sp = spool.find(sc, "Drum")
    W0 = float(sp.wound)
    pay(sc, "Wire", 25.0)
    check(sc, "Drum", where="before save")
    names = sorted(o.name for o in bpy.data.objects if o.get(spool.TAG))
    f = str(tmp_path / "saved.blend")
    bpy.ops.wm.save_as_mainfile(filepath=f, copy=True)
    bpy.ops.wm.open_mainfile(filepath=f)
    _DIRTY[0] = True
    sc = bpy.context.scene
    update()
    assert sorted(o.name for o in bpy.data.objects if o.get(spool.TAG)) == names
    check(sc, "Drum", where="opened")
    for ob in spool.layer_objects(sc, spool.find(sc, "Drum")):
        for fc in ob.animation_data.drivers:
            assert fc.driver.is_simple_expression and fc.driver.is_valid, ob.name
    for p in (W0 - 0.01, W0 - 150.0, -2.0):
        pay(sc, "Wire", p)
        check(sc, "Drum", where="opened, paid")


def test_old_project_with_solid_and_old_draw_number(made, tmp_path):
    """An old project: the drum with a solid, no layer objects and the rope marked as drawn the old way (1); the
    carousel with a solid and a stale layer object from somewhere. Opened: both drawn the new way, nothing old left."""
    sc = made
    pay(sc, "Wire", 12.0)
    pay(sc, "Power cable", 60.0)
    for name, _c in CASES:
        sp = spool.find(sc, name)
        layers = spool.layer_objects(sc, sp)
        for ob in (layers if name == "Drum" else layers[1:]):
            spool._remove_object(ob)
        spool._new_made(sc, sp, "solid", sp.part, bpy.data.meshes.new("old solid " + name))
        sp.owner["fr_spool_draw"] = 1
    f = str(tmp_path / "old.blend")
    bpy.ops.wm.save_as_mainfile(filepath=f, copy=True)
    bpy.ops.wm.open_mainfile(filepath=f)
    _DIRTY[0] = True
    sc = bpy.context.scene
    update()
    for name, _c in CASES:
        sp = spool.find(sc, name)
        assert not [o for o in bpy.data.objects if o.get(spool.TAG) == name and o.get("fr_spool_role") == "solid"]
        assert not spool.needs_upgrade(sc, sp)
        check(sc, name, where="old opened")
    pay(sc, "Wire", 0.0)
    check(sc, "Drum", where="old opened, paid back")


def test_model_update_keeps_every_layer(folder):
    """A model update to the same STEP: every spool's layer objects on the new part, the right count, none left on
    the old parts, the picture whole."""
    sc = _build_scene(folder)
    _DIRTY[0] = True
    pay(sc, "Wire", 5.0)
    pay(sc, "Power cable", 5.0)
    root = build.model_roots(sc)[0]
    assert bpy.ops.fresing.import_step(filepath=MODEL, quality="normal", update_root=root.name) == {"FINISHED"}
    update()
    sc = bpy.context.scene
    for name, cable in CASES:
        sp = spool.find(sc, name)
        assert sp is not None and sp.enabled, (name, sp and sp.problem)
        made_ = [o for o in bpy.data.objects if o.get(spool.TAG) == name]
        assert all(o.name in sc.objects for o in made_), name
        lay = [o for o in made_ if o.get("fr_spool_role") == "layer"]
        assert lay and all(o.parent == sp.part for o in lay), (name, [(o.name, o.parent) for o in lay])
        pay(sc, cable, 5.0)
        check(sc, name, where="model update")


def test_carousel_whose_axis_points_down(folder):
    """The carousel's joint made with its arrow pointing down (away from where the layers grow): the spool frame is
    turned over, the full layers lie in the CAD coil as with the arrow up, the picture is whole when paying out."""
    sc = _build_scene(folder, carousel_down=True)
    _DIRTY[0] = True
    sp = spool.find(sc, "Carousel")
    fr = joints.find(sc, sp.joint).frame
    assert np.array(fr.matrix_world)[2, 2] < -0.99           # (the arrow points down)
    assert int(sp.zsign) == -1 and not sp.problem, (sp.zsign, sp.problem)
    pay(sc, "Power cable", 0.0)
    parts = check(sc, "Carousel", where="down")
    coil = sp.coil
    v = np.array([coil.matrix_world @ c.co for c in coil.data.vertices])
    lo, hi = v.min(axis=0), v.max(axis=0)
    d = spool.diameter(sc, sp)
    layers = [x for x in parts if x[0].startswith("layer")]
    assert len(layers) == 3
    for kind, _L, c, _dev, _r in layers:
        assert np.all(c >= lo + d / 2 - PLACE_TOL) and np.all(c <= hi - d / 2 + PLACE_TOL), (kind, c.min(0), c.max(0))
    if "Carousel" in _SEEN:
        a = (np.min([x[2].min(0) for x in parts], axis=0), np.max([x[2].max(0) for x in parts], axis=0))
        assert np.allclose(a[0], _SEEN["Carousel"][0], atol=d) and np.allclose(a[1], _SEEN["Carousel"][1], atol=d)
    path = spool.path_of(sc, sp)
    W0 = float(sp.wound)
    ps = probe_payouts(path, W0)
    for p in ps[:: 4] + [ps[-1]]:
        pay(sc, "Power cable", p)
        check(sc, "Carousel", where="down sweep")


def test_cable_joint_that_follows_a_leader(made):
    """The cable's speed joint made to follow another joint at 2 metres per metre (as the demo's tipping winches'
    wires do): paying out by the leader, the layers and the rope follow the leader's value (their drivers must read
    the top of the chain, never the follower's copy)."""
    sc = made
    _DIRTY[0] = True
    from mathutils import Vector
    base = build.model_roots(sc)[0]
    lead = joints.create(sc, "SLIDE", [], Vector((0.0, 0.0, 0.0)), Vector((1.0, 0.0, 0.0)), name="Winch speed",
                         base=base, allow_empty=True)
    lead_name = lead.name
    it = paths.find(sc, "Wire")
    cj = joints.find(sc, it.joint)
    joints.set_follows(sc, cj, lead_name, ratio=2.0)
    update()
    sp = spool.find(sc, "Drum")
    top, k, _c, _sign = spool._pay_map(sc, sp)
    assert top is not None and top.name == lead_name and k == pytest.approx(2.0), (top and top.name, k)
    path = spool.path_of(sc, sp)
    W0 = float(sp.wound)
    spans = S.layer_spans(path)
    for left in (0.5 * (spans[0, 0] + spans[0, 1]), 0.5 * (spans[3, 0] + spans[3, 1]), W0, 0.97 * path.total):
        joints.set_value(joints.find(sc, lead_name), 0.5 * (W0 - left), use_limits=False)
        update()
        paths.refresh(sc)
        update()
        assert spool.payout(sc, spool.find(sc, "Drum")) == pytest.approx(W0 - left, abs=1e-4)
        check(sc, "Drum", where=f"leader, on {left:.2f}")


def test_built_animation_across_a_layer_change_frame_by_frame(made):
    """A built animation that pays the drum's wire out slowly across the change from layer 2 to layer 1 (through the
    climb): at every frame the right layers, no gap, the seams point on point (keyed values played as frames)."""
    from fresing_render.blender import animation
    sc = made
    _DIRTY[0] = True
    s = sc.fresing
    sp = spool.find(sc, "Drum")
    path = spool.path_of(sc, sp)
    W0 = float(sp.wound)
    sw, spans = S.layer_switches(path), S.layer_spans(path)
    it = paths.find(sc, "Wire")
    sign = -1.0 if it.reverse else 1.0
    a = s.animations.add()
    a.name, a.tail, a.fps = "Across a layer", 0.0, "25"
    b = a.blocks.add()
    b.kind, b.joint, b.start, b.duration, b.easing = "JOINT", it.joint, 0.0, 2.0, "LINEAR"
    b.use_from, b.from_dist, b.to_dist = False, sign * (W0 - (sw[0] + 0.3)), sign * (W0 - (spans[0, 1] - 0.3))
    s.animations_index = len(s.animations) - 1
    info = animation.bake(sc, a)
    try:
        assert not [w for w in info["warnings"] if "Drum" in w], info["warnings"]
        shown = set()
        for f in range(int(sc.frame_start), int(sc.frame_end) + 1):
            sc.frame_set(f)
            update()
            check(sc, "Drum", where=f"frame {f}")
            shown.add(tuple(not o.hide_viewport for o in spool.layer_objects(sc, spool.find(sc, "Drum"))))
        assert len(shown) >= 2, shown                       # (layer 1 did hide on the way)
    finally:
        animation.clear_keys(sc)
        s.animations.remove(len(s.animations) - 1)
        s.animations_index = 0
        sc.frame_set(1)


def test_drawing_again_leaves_no_meshes_behind(made):
    """Drawn again and again (the groove changed back and forth): as many spool meshes as before, none without a
    user, as many layer objects as layers."""
    sc = made
    _DIRTY[0] = True

    def count():
        return len([m for m in bpy.data.meshes if m.name.startswith("FR spool")]), \
            len([m for m in bpy.data.meshes if m.name.startswith("FR spool") and m.users == 0])
    before = count()
    for g in ("LEBUS", "SPIRAL", "LEBUS", "SPIRAL"):
        spool.find(sc, "Drum").groove = g
        update()
    assert count() == before and before[1] == 0, (before, count())
    sp = spool.find(sc, "Drum")
    assert len(spool.layer_objects(sc, sp)) == spool.path_of(sc, sp).layer_count - 1
