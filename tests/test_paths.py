"""Task 0078: cables and paths – the Blender side (blender/paths.py).

The test model (tools/make_test_paths.py, whose numbers these tests use): a wire rope from a winch drum over a
sheave at the top of a luffing A-frame, under a second sheave at its foot, through a V-roller cradle and over a
chute. "The drawn cable" is what Blender evaluates for the cable part (its modifier applied), in world
coordinates: rings of ``paths.SIDES`` points; a ring's middle is a point of the path. The last test reads the
demo vessel's power cable (the small form of the demo project, built up to its joints).
"""

import math
import os
import sys
import time

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from mathutils import Vector  # noqa: E402

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
MODEL_A = os.path.join(HERE, "data", "test_paths_a.step")
MODEL_B = os.path.join(HERE, "data", "test_paths_b.step")
CRANE = os.path.join(HERE, "data", "test_crane_a.step")
MM = 0.001

import fresing_render  # noqa: E402
import make_test_paths as maker  # noqa: E402
from fresing_render.blender import animation, build, cable_looks, clash, flex, joints, logic, paths  # noqa: E402
from fresing_render.core import paths as P  # noqa: E402

N = maker.NUMBERS
CABLE = "Wire rope"
SPEED = "Cable Wire rope"
ORDER = ["WINCH DRUM", "SHEAVE 1", "SHEAVE 2", "V ROLLER", "V ROLLER", "CHUTE"]
KINDS = ["SHEAVE", "SHEAVE", "SHEAVE", "ROLLER", "ROLLER", "CHUTE"]


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture(scope="module")
def folder(tmp_path_factory):
    """One output folder for the whole file: the second import of a model comes from its cache."""
    return str(tmp_path_factory.mktemp("paths"))


def load(folder, path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    flex.forget()
    paths.forget()
    sc = bpy.context.scene
    sc.fresing.out_folder = folder
    assert bpy.ops.fresing.import_step(filepath=path, quality="draft") == {"FINISHED"}
    return sc


@pytest.fixture()
def rope(folder):
    sc = load(folder, MODEL_A)
    made = paths.set_up_test_model(sc)
    assert made["cable"] == CABLE and made["joints"] == ["Luff", SPEED] and made["contacts"] == ORDER
    assert made["animation"] == paths.TEST_ANIMATION and not sc.fresing.anim_baked
    return sc


def update(times=2):
    for _ in range(times):
        bpy.context.view_layer.update()


def ob(sc, name, k=0):
    return [o for o in sc.objects if o.get(build.PROP_NAME) == name][k]


def cable(sc):
    return paths.find(sc, CABLE)


def contact(sc, name, k=0):
    return [c for c in cable(sc).contacts if c.name == name][k]


def index(sc, name, k=0):
    return [i for i, c in enumerate(cable(sc).contacts) if c.name == name][k]


def drawn(part):
    """The part as Blender draws it: (world points (V, 3), its ``fr_cable`` attribute (V, 3) or None)."""
    e = part.evaluated_get(bpy.context.evaluated_depsgraph_get())
    me = e.data
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    w = np.array(e.matrix_world, dtype=float)
    att = None
    if cable_looks.ATTR in me.attributes:
        att = np.empty(len(me.vertices) * 3, np.float32)
        me.attributes[cable_looks.ATTR].data.foreach_get("vector", att)
        att = att.reshape(-1, 3).astype(float)
    return co.reshape(-1, 3).astype(float) @ w[:3, :3].T + w[:3, 3], att


def rings(part):
    """The middles of the drawn tube's rings (n, 3), world; and the largest a ring's radius is off the cable's."""
    co, _att = drawn(part)
    assert len(co) and len(co) % paths.SIDES == 0, f"{part.name}: {len(co)} points is no tube"
    r = co.reshape(-1, paths.SIDES, 3)
    c = r.mean(axis=1)
    return c, np.linalg.norm(r - c[:, None], axis=2)


def to_line(points, line) -> np.ndarray:
    """The distance of every point (P, 3) to the polyline (L, 3)."""
    a, b = line[:-1], line[1:]
    seg = b - a
    t = np.einsum("pli,li->pl", points[:, None] - a[None], seg) / np.maximum(np.einsum("li,li->l", seg, seg), 1e-30)
    foot = a[None] + np.clip(t, 0.0, 1.0)[..., None] * seg[None]
    return np.linalg.norm(points[:, None] - foot, axis=2).min(axis=1)


def exact(luff=0.0) -> np.ndarray:
    """The rope's middle as the maker's formulas give it with the A-frame luffed (m)."""
    return maker.centreline(luff, 2.0) * MM


def luff_deg(sc) -> float:
    return math.degrees(joints.get_value(joints.find(sc, "Luff")))


def off_path(sc, luff) -> float:
    """The furthest a ring's middle of the drawn cable is from the maker's centreline (m)."""
    c, _r = rings(cable(sc).part)
    return float(to_line(c, exact(luff)).max())


def arcs(sc, luff):
    """Per wheel of the maker's numbers: (name, the drawn ring middles on its circle, centre, seat radius)."""
    c, _r = rings(cable(sc).part)
    out = []
    for name, w in maker.numbers_at(luff)["contacts"].items():
        centre, seat = np.array(w["axis_point"]) * MM, w["seat_radius"] * MM
        d = np.linalg.norm(c - centre, axis=1)
        on = np.flatnonzero(d < seat + 1.0 * MM)
        assert len(on) >= 3 and np.all(np.diff(on) == 1), (name, on)
        out.append((name, on, centre, seat, d[on]))
    return out


def check_on_seats(sc, luff, tol=0.5 * MM):
    for name, on, _centre, seat, d in arcs(sc, luff):
        assert np.abs(d - seat).max() < tol, (name, luff, np.abs(d - seat).max() / MM)
    assert off_path(sc, luff) < tol, (luff, off_path(sc, luff) / MM)


def steps(sc, rows, name="Move"):
    """An animation of joint steps: rows of (joint, start s, seconds, to)."""
    a = sc.fresing.animations.add()
    a.name, a.tail, a.fps = name, 0.0, "25"
    for joint, start, seconds, to in rows:
        b = a.blocks.add()
        b.kind, b.joint, b.start, b.duration, b.easing = "JOINT", joint, start, seconds, "LINEAR"
        b.use_from = True
        if joints.find(sc, joint).kind == "SLIDE":
            b.to_dist = to
        else:
            b.to_angle = to
    return a


def run_step(sc, metres, mmin=10.0, name="Run"):
    """An animation with one Run motor step on the cable's joint: ``metres`` at ``mmin`` m/min."""
    a = sc.fresing.animations.add()
    a.name, a.tail, a.fps = name, 0.0, "25"
    b = a.blocks.add()
    b.kind, b.joint, b.start, b.duration, b.easing = "MOTOR", SPEED, 0.0, metres / mmin * 60.0, "LINEAR"
    b.speed_mmin = mmin
    return a


def built(sc, a):
    r = animation.bake(sc, a)
    assert not r["warnings"], r["warnings"]
    return r


class Evaluations:
    """Counts how often Blender works the cable part's shape out again at a frame change."""

    def __init__(self, part):
        self.part, self.count = part, 0

    def __call__(self, scene, depsgraph=None):
        if depsgraph is not None:
            self.count += sum(1 for u in depsgraph.updates if u.id.original == self.part and u.is_updated_geometry)

    def __enter__(self):
        bpy.app.handlers.frame_change_post.append(self)
        return self

    def __exit__(self, *exc):
        bpy.app.handlers.frame_change_post.remove(self)


# ---------------------------------------------------------------------------
# reading the CAD cable
# ---------------------------------------------------------------------------

def test_the_cable_is_read_from_its_cad_shape(rope):
    sc = rope
    it = cable(sc)
    assert [c.name for c in it.contacts] == ORDER and [c.kind for c in it.contacts] == KINDS
    assert it.part == ob(sc, "WIRE ROPE") and it.joint == SPEED and it.made_joint
    assert it.diameter == pytest.approx(24 * MM, abs=0.1 * MM) and it.cad_diameter == pytest.approx(it.diameter)
    assert it.length == pytest.approx(N["rope"]["length"] * MM, rel=1e-3)
    for c in it.contacts:
        if c.kind == "ROLLER":
            k = 0 if c == contact(sc, "V ROLLER", 0) else 1
            want = N["rollers"][k]
            assert c.radius == pytest.approx(want["seat_radius"] * MM, abs=0.2 * MM)
            assert c.surface == pytest.approx(want["surface_radius"] * MM, abs=0.2 * MM)
            assert c.wrap == 0.0 and c.full and c.part == ob(sc, "V ROLLER", k)
            continue
        want = N["contacts"][c.name]
        assert c.radius == pytest.approx(want["seat_radius"] * MM, abs=0.2 * MM), c.name
        assert c.surface == pytest.approx(want["surface_radius"] * MM, abs=0.2 * MM), c.name
        assert math.degrees(c.wrap) == pytest.approx(want["wrap"], abs=0.2), c.name
        assert c.side == want["side"], c.name               # the maker's axis is +Y, as the parts' round faces are
        assert c.full == (c.name != "CHUTE") and c.part == ob(sc, c.name)
        assert abs(c.gap) < 1.0 * MM and not c.note          # (the facets of a Draft mesh)
    # where each contact is along the rope
    assert [c.s for c in it.contacts] == sorted(c.s for c in it.contacts)
    # the wheels in world coordinates
    for w, c in zip(paths.wheels_now(sc, it), [c for c in it.contacts if c.kind in paths.SHAPING]):
        want = N["contacts"][c.name]
        assert np.linalg.norm(w.centre - np.array(want["axis_point"]) * MM) < 0.05 * MM, c.name
        assert abs(abs(w.axis[1]) - 1.0) < 1e-6 and w.side * np.sign(w.axis[1]) == want["side"]
    # the start lies on the drum, the other end is free and stays with the chute
    assert it.a_kind == "WHEEL" and it.a_part == contact(sc, "WINCH DRUM").carrier and not it.a_free_end
    assert it.b_kind == "FIXED" and it.b_free_end and it.b_part == ob(sc, "CHUTE")
    assert it["b_cad_free"] == pytest.approx(N["rope"]["free"] * MM, abs=0.5 * MM)
    shape = paths.shape_now(sc, it)
    assert np.linalg.norm(shape[0] - np.array(N["rope"]["start"]) * MM) < 0.2 * MM
    assert np.linalg.norm(shape[-1] - np.array(N["rope"]["end"]) * MM) < 0.2 * MM
    assert paths.status(sc, it) == ("7.02 m over 6 contacts", "OK") and not it.problem
    assert paths.parts_of(sc, it) == [it.part] and paths.active(sc) == it and paths.index_of(sc, it) == 0
    assert paths.label(it) == CABLE and list(paths.items(sc)) == [it]


def test_the_notes_say_what_was_found(folder):
    sc = load(folder, MODEL_A)
    it = paths.add_cable(sc, "Rope")
    assert it.joint == "Cable Rope" and joints.find(sc, "Cable Rope").kind == "SLIDE"
    assert not joints.members(joints.find(sc, "Cable Rope")) and not joints.find(sc, "Cable Rope").use_limits
    notes = paths.read_cad(sc, it, ob(sc, "WIRE ROPE"))
    assert notes[0].startswith("Cable 'Rope': 3 sheaves, 2 rollers, 1 chute; Ø 24 mm, 7.02 m; the path is at most ")
    assert notes[1] == "Cable 'Rope': 5 new joints so that what it touches turns with it" and len(notes) == 2
    off = float(notes[0].split("at most ")[1].split(" mm")[0])
    print(f"\ntest rope at Draft: the path is at most {off} mm off the CAD centreline as the importer's mesh gives it")
    assert off < 1.5
    # a default name, a second cable, taking a joint that is there
    assert paths.add_cable(sc).name == "Cable" and paths.find(sc, "Cable").joint == "Cable"
    with pytest.raises(paths.PathError, match="rotate joint"):
        paths.add_cable(sc, "x", joint="WINCH DRUM rotate")
    with pytest.raises(paths.PathError, match="no joint called"):
        paths.add_cable(sc, "x", joint="Nothing")
    with pytest.raises(paths.PathError, match="the speed of cable 'Rope' already"):
        paths.add_cable(sc, "x", joint="Cable Rope")
    assert [c.name for c in paths.items(sc)] == ["Rope", "Cable"]


def test_parts_that_are_no_cable_are_refused(rope):
    sc = rope
    it = cable(sc)
    before = [c.name for c in it.contacts]
    with pytest.raises(paths.PathError, match="This part is not a cable"):
        paths.read_cad(sc, it, ob(sc, "BASE FRAME"))
    with pytest.raises(paths.PathError, match="This part is not a cable"):
        paths.read_cad(sc, it, ob(sc, "SHEAVE 1"))
    with pytest.raises(paths.PathError, match="it has no shape to read"):
        paths.read_cad(sc, it, ob(sc, "A-FRAME.ASM"))
    other = paths.add_cable(sc, "Second")
    with pytest.raises(paths.PathError, match="is cable 'Wire rope' already"):
        paths.read_cad(sc, other, ob(sc, "WIRE ROPE"))
    assert paths.status(sc, other) == ("no path yet: use 'From CAD cable'", "ERROR")
    it = cable(sc)
    assert [c.name for c in it.contacts] == before and it.part == ob(sc, "WIRE ROPE")
    assert len(sc.fresing.joints) == 8                      # Luff, two cable joints, five wheels: nothing new


def test_a_cable_that_touches_nothing_is_refused(folder):
    """A round bar in the air beside the model: a cable by its shape, but it lies on nothing."""
    sc = load(folder, MODEL_A)
    rope_ob = ob(sc, "WIRE ROPE")
    bar = rope_ob.copy()
    bar.data = rope_ob.data.copy()
    k, n = 24, 20
    ring = [(0.02 * math.cos(2 * math.pi * i / k), 0.02 * math.sin(2 * math.pi * i / k)) for i in range(k)]
    verts = [(x * 0.1, 5.0 + y, 3.0 + z) for x in range(n + 1) for y, z in ring] + [(0, 5, 3), (n * 0.1, 5, 3)]
    faces = [(i * k + j, i * k + (j + 1) % k, (i + 1) * k + (j + 1) % k, (i + 1) * k + j)
             for i in range(n) for j in range(k)]
    faces += [(len(verts) - 2, (j + 1) % k, j) for j in range(k)]
    faces += [(len(verts) - 1, n * k + j, n * k + (j + 1) % k) for j in range(k)]
    bar.data.clear_geometry()
    bar.data.from_pydata(verts, [], faces)
    bar.data.update()
    for key in ("fr_axes", "fr_axis_faces"):
        if key in bar.data:
            del bar.data[key]
    bar[build.PROP_NAME], bar[build.PROP_UID] = "LOOSE CABLE", "TEST.PATHS#1/LOOSE CABLE#1"
    bar.matrix_basis = rope_ob.matrix_basis
    bar.parent = rope_ob.parent
    sc.collection.objects.link(bar)
    update()
    it = paths.add_cable(sc, "Loose")
    with pytest.raises(paths.PathError, match="The cable touches nothing"):
        paths.read_cad(sc, it, bar)
    assert paths.find(sc, "Loose").part is None and len(sc.fresing.joints) == 1
    assert paths.MOD not in bar.modifiers and cable_looks.PAY not in bar


def test_a_reading_far_off_the_cad_cable_is_refused(folder, monkeypatch):
    """The reader can say "ok" with its path beside the cable: the app measures that itself and refuses in plain
    words – where, and how far. (Here the limit is set far below the facets of the Draft mesh.)"""
    sc = load(folder, MODEL_A)
    it = paths.add_cable(sc, CABLE)
    monkeypatch.setattr(paths, "OFF_PATH", (0.00002, 0.0))
    with pytest.raises(paths.PathError) as err:
        paths.read_cad(sc, it, ob(sc, "WIRE ROPE"))
    text = str(err.value)
    assert text.startswith("The path of 'WIRE ROPE' cannot be read: ")
    assert " m from its start the cable as drawn lies " in text
    assert " mm beside the straight runs and round bends" in text
    it = cable(sc)
    assert it.part is None and not len(it.contacts) and len(sc.fresing.joints) == 1
    assert paths.MOD not in ob(sc, "WIRE ROPE").modifiers
    monkeypatch.undo()
    paths.read_cad(sc, it, ob(sc, "WIRE ROPE"))
    assert [c.name for c in cable(sc).contacts] == ORDER


def test_reading_in_another_pose_reads_the_same(folder):
    """The model luffed and the cable paid out when 'From CAD cable' is used: the same contacts as in the CAD pose
    (the CAD shape is read in the CAD pose) and the cable drawn for the pose the model is in."""
    sc = load(folder, MODEL_A)
    frame = ob(sc, "A-FRAME.ASM")
    luff = joints.create(sc, "ROTATE", [frame], Vector((1.5, 0.0, 0.73)), Vector((0.0, 1.0, 0.0)), name="Luff")
    joints.set_value(luff, math.radians(9.0))
    update()
    it = paths.add_cable(sc, CABLE)
    paths.read_cad(sc, it, ob(sc, "WIRE ROPE"))
    it = cable(sc)
    for c in it.contacts:
        if c.kind != "ROLLER":
            want = N["contacts"][c.name]
            assert c.radius == pytest.approx(want["seat_radius"] * MM, abs=0.2 * MM) and c.side == want["side"]
    update()
    assert luff_deg(sc) == pytest.approx(9.0, abs=1e-4)
    check_on_seats(sc, 9.0)
    joints.set_value(joints.find(sc, "Luff"), 0.0)
    update()
    check_on_seats(sc, 0.0)


# ---------------------------------------------------------------------------
# the cable drawn on its path
# ---------------------------------------------------------------------------

def test_the_drawn_cable_lies_on_its_wheels(rope):
    sc = rope
    it = cable(sc)
    update()
    c, radii = rings(it.part)
    assert np.abs(radii - 0.5 * it.diameter).max() < 1e-5
    assert np.abs(c - paths.shape_now(sc, it)).max() < 1e-5            # the rings' middles are the path's points
    check_on_seats(sc, 0.0)
    worst = max(float(np.abs(d - seat).max()) for _n, _on, _c, seat, d in arcs(sc, 0.0))
    print(f"\ntest rope, as drawn: {len(c)} rings; middle at most {worst / MM:.3f} mm off a wheel's seat circle, "
          f"{off_path(sc, 0.0) / MM:.3f} mm off the maker's centreline")
    # no kink where a straight run meets a wheel: its direction is the circle's tangent there
    shaping = [x for x in it.contacts if x.kind in paths.SHAPING]
    wheels = {w.name: paths.wheels_now(sc, it)[k] for k, w in enumerate(shaping)}
    worst = 0.0
    for name, on, _centre, _seat, _d in arcs(sc, 0.0):
        w = wheels[name]
        for i, j in ((on[0], on[0] - 1), (on[-1], on[-1] + 1)):
            if not 0 <= j < len(c):
                continue                                               # the rope starts on the drum
            run = (c[i] - c[j]) if j < i else (c[j] - c[i])
            tangent = w.side * np.cross(w.axis, c[i] - w.centre)
            cos = float(run @ tangent) / (np.linalg.norm(run) * np.linalg.norm(tangent))
            worst = max(worst, math.degrees(math.acos(min(1.0, cos))))
    print(f"test rope: direction change at a tangent point at most {worst:.4f}°")
    assert worst < 0.1
    # arcs are drawn as points 4° apart or less, straight runs as two
    step = np.linalg.norm(np.diff(c, axis=0), axis=1)
    assert len(c) < 200 and (step > 0.4).sum() == 4
    # the attribute the looks read: (cos, sin) of the angle round the cable, the metres along it
    co, att = drawn(it.part)
    assert att is not None
    assert np.abs(np.linalg.norm(att[:, :2], axis=1) - 1.0).max() < 1e-5
    s = att[:, 2].reshape(-1, paths.SIDES)
    assert np.abs(s - s[:, :1]).max() < 1e-6 and s[0, 0] == 0.0 and s[-1, 0] == pytest.approx(it.length, abs=1e-5)
    assert np.all(np.diff(s[:, 0]) > 0.0)
    assert np.abs(np.diff(s[:, 0]) - np.where(step > 0.4, step, np.diff(s[:, 0]))).max() < 1e-5   # straight: its length
    assert np.abs(paths.lengths_now(sc, it) - s[:, 0]).max() < 1e-6
    # the part's own look, its modifier first; nothing new in the model
    mod = it.part.modifiers[0]
    assert mod.name == paths.MOD and mod.node_group.name == paths.TREES[False] and mod.show_viewport and mod.show_render
    assert it.shapes is not None and it.shapes.name == f"{paths.SHAPES} {CABLE}" and it.shapes.hide_render
    assert it.shapes.users_collection[0].name == flex.COLLECTION
    assert [o.get(build.PROP_NAME) for o in build.iter_parts(sc)].count("WIRE ROPE") == 1


def test_off_shows_the_cad_shape_again(rope):
    sc = rope
    it = cable(sc)
    part = it.part
    me = part.data
    cad = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", cad)
    w = np.array(part.matrix_world, dtype=float)
    cad = cad.reshape(-1, 3).astype(float) @ w[:3, :3].T + w[:3, 3]
    update()
    tube, _att = drawn(part)
    assert len(tube) != len(cad)
    it.enabled = False
    update()
    off, att = drawn(part)
    assert off.shape == cad.shape and np.array_equal(off, cad) and att is None        # vertex for vertex
    assert paths.status(sc, it) == ("off", "OFF")
    for c in it.contacts:                                   # and nothing turns with it
        if c.joint:
            assert not joints.find(sc, c.joint).follows
    it = cable(sc)
    it.enabled = True
    update()
    again, _att = drawn(it.part)
    assert np.array_equal(again, tube)
    assert all(joints.find(sc, c.joint).follows == SPEED for c in it.contacts if c.joint)


def test_a_thicker_cable_lies_higher(rope):
    sc = rope
    it = cable(sc)
    it.diameter = 0.040
    update()
    it = cable(sc)
    _c, radii = rings(it.part)
    assert np.abs(radii - 0.020).max() < 1e-5
    c, _r = rings(it.part)
    for name, w in N["contacts"].items():
        centre = np.array(w["axis_point"]) * MM
        d = np.linalg.norm(c - centre, axis=1)
        on = d < w["seat_radius"] * MM + 9 * MM
        assert on.sum() >= 3 and np.abs(d[on] - (w["seat_radius"] * MM + 8 * MM)).max() < 0.5 * MM, name
    # a sheave turns with the cable's middle, which is further out now; a roller with the skin CAD drew
    s1, r1 = contact(sc, "SHEAVE 1"), contact(sc, "V ROLLER")
    assert abs(s1.ratio) == pytest.approx(360.0 / (2 * math.pi * 258.09), rel=1e-3)
    assert abs(r1.ratio) == pytest.approx(360.0 / (2 * math.pi * 60.0), rel=1e-3)
    assert joints.find(sc, s1.joint).couple_ratio == pytest.approx(s1.ratio, rel=1e-5)
    # read again: the typed diameter stays
    paths.read_cad(sc, it, it.part)
    assert cable(sc).diameter == pytest.approx(0.040) and cable(sc).cad_diameter == pytest.approx(0.024, abs=1e-4)


# ---------------------------------------------------------------------------
# the look
# ---------------------------------------------------------------------------

def test_the_look_and_the_ropes_hand(rope):
    sc = rope
    it = cable(sc)
    part = it.part
    look = list(part[cable_looks.LOOK])
    assert look == pytest.approx(cable_looks.look_values("ROPE", it.diameter, it.pitch, -it.angle, it.stripe))
    assert look[0] == pytest.approx(paths.ROPE_LAY * it.diameter) and look[1] == -6.0 and look[3] == 2.0
    assert paths.look_of(it) == pytest.approx(look)
    # the manual group with the look's material
    assert part["fr_group_manual"] == "Wire ropes" and part[build.PROP_GROUP] == "Wire ropes"
    assert sc.fresing.groups["Wire ropes"].material == "wire_rope"
    update()
    e = part.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mat = e.material_slots[0].material
    assert mat is not None and cable_looks.nodes_of(mat) and len(e.data.materials) == 1
    # the hand. Along a strand the look's phase stays the same; phi turns about the direction s grows in:
    co, att = drawn(part)
    r = co.reshape(-1, paths.SIDES, 3)
    a = att.reshape(-1, paths.SIDES, 3)
    k = int(np.argmin(np.abs(a[:, 0, 2] - 2.0)))                          # on the straight run up to sheave 1
    centre = r.mean(axis=1)
    along = centre[k + 1] - centre[k]
    assert a[k + 1, 0, 2] > a[k, 0, 2]
    phi = np.arctan2(a[k, :, 1], a[k, :, 0])
    turn = float(np.cross(r[k, 0] - centre[k], r[k, 1] - centre[k]) @ along)
    turn *= float(np.sign(np.unwrap(phi)[1] - phi[0]))
    assert turn > 0.0                                                     # phi turns right-handed about +s
    # … and where a strand's crest is a little further on: at a larger phi, so the strands are a right-hand screw
    s0, ds = 2.0, 0.002
    here = cable_looks.phase("ROPE", s0, 0.0, 0.0, look)
    on, on2 = (cable_looks.phase("ROPE", s0 + ds, x, 0.0, look) for x in (0.0, 0.01))
    there = (here - on) / ((on2 - on) / 0.01)                             # the phi with the same phase at s0 + ds
    assert there > 0.0, "a wire rope is laid right-handed (Z lay)"
    assert there == pytest.approx(2 * math.pi * ds / look[0], rel=1e-6)   # one turn per lay length
    # power cable: its group; plain: back where it was
    it.look = "POWER"
    it = cable(sc)
    assert part["fr_group_manual"] == "Power cables" and sc.fresing.groups["Power cables"].material == "cable_power"
    assert list(part[cable_looks.LOOK])[3] == 1.0 and part[build.PROP_GROUP] == "Power cables"
    assert it.pitch == pytest.approx(0.1)                                 # the usual stripe distance for Ø 24
    it.pitch, it.angle, it.stripe = 0.2, math.radians(30.0), 0.4
    look = list(part[cable_looks.LOOK])
    assert look == pytest.approx(cable_looks.look_values("POWER", it.diameter, 0.2, -math.radians(30.0), 0.4))
    assert look[1] < 0 and look[2] == pytest.approx(0.4)
    it.look = "PLAIN"
    assert cable_looks.LOOK not in part and "fr_group_manual" not in part
    assert part[build.PROP_GROUP] not in ("Power cables", "Wire ropes")
    it.look = "ROPE"
    assert part["fr_group_manual"] == "Wire ropes" and cable(sc).pitch == pytest.approx(0.2)    # a typed pitch stays
    # a group the user put the part in by hand comes back with Plain; one he chose afterwards stays
    cable(sc).look = "PLAIN"
    part["fr_group_manual"] = "My ropes"
    logic.ensure_group(sc.fresing, "My ropes")
    logic.apply_rules(sc)
    cable(sc).look = "POWER"
    assert part["fr_group_manual"] == "Power cables"
    cable(sc).look = "PLAIN"
    assert part["fr_group_manual"] == "My ropes" and part[build.PROP_GROUP] == "My ropes"


# ---------------------------------------------------------------------------
# everything it touches turns
# ---------------------------------------------------------------------------

def rim_runs_with_the_cable(sc, c, metres=0.004) -> float:
    """Pay out a little and see where a point of the wheel's rim under the cable goes: returns how far it went
    along the cable's direction there, as a share of the metres paid out (1.0 = it runs with the cable)."""
    it = cable(sc)
    j = joints.find(sc, c.joint)
    m = np.array(c.carrier.matrix_world, dtype=float)
    centre, axis = m[:3, :3] @ np.array(c.centre) + m[:3, 3], m[:3, :3] @ np.array(c.axis)
    shape = paths.shape_now(sc, it)
    seg = shape[1:] - shape[:-1]                            # the point of the path nearest the wheel's middle
    t = np.clip(np.einsum("li,li->l", centre - shape[:-1], seg) / np.einsum("li,li->l", seg, seg), 0.0, 1.0)
    foot = shape[:-1] + seg * t[:, None]
    i = int(np.argmin(np.linalg.norm(foot - centre, axis=1)))
    heading = seg[i] / np.linalg.norm(seg[i])
    flat = foot[i] - centre
    flat = flat - axis * float(flat @ axis)
    radius = paths.radius_of(it, c) if c.kind == "SHEAVE" else c.radius - 0.5 * it.cad_diameter
    rim = centre + flat / np.linalg.norm(flat) * radius
    part = joints.members(j)[0]
    local = np.linalg.inv(np.array(part.matrix_world, dtype=float)) @ np.append(rim, 1.0)
    lead = joints.find(sc, it.joint)
    v0 = joints.get_value(lead)
    joints.set_value(lead, v0 + metres)
    update()
    moved = (np.array(part.matrix_world, dtype=float) @ local)[:3] - rim
    joints.set_value(lead, v0)
    update()
    return float(moved @ heading) / metres


def test_everything_it_touches_turns_at_the_cables_speed(rope):
    sc = rope
    it = cable(sc)
    turning = [c for c in it.contacts if c.kind in paths.TURNING]
    assert len(turning) == 5 and not contact(sc, "CHUTE").joint and contact(sc, "CHUTE").ratio == 0.0
    for c in turning:
        j = joints.find(sc, c.joint)
        assert j is not None and c.made_joint and c.coupled and c.turns and j.kind == "ROTATE"
        assert j.follows == SPEED and j.motion[paths.TAG] == CABLE and joints.members(j) == [c.part]
        assert c.carrier == j.frame and j.couple_ratio == pytest.approx(c.ratio, rel=1e-6)
        radius = c.radius if c.kind == "SHEAVE" else c.radius - 0.5 * it.cad_diameter
        assert abs(c.ratio) == pytest.approx(360.0 / (2 * math.pi * radius * 1000.0), rel=1e-6)
        assert paths.ratio_of(sc, it, c) == pytest.approx(c.ratio)
        share = rim_runs_with_the_cable(sc, c)
        assert share == pytest.approx(1.0, abs=0.01), (c.name, share)       # the right way round, at its speed
    # the luff joint was there: sheaves on the A-frame ride on it
    for name in ("SHEAVE 1", "SHEAVE 2"):
        assert joints.find(sc, contact(sc, name).joint).frame.parent == ob(sc, "A-FRAME.ASM")
    assert paths.is_cable_joint(sc, joints.find(sc, SPEED)) and paths.cable_of_joint(sc, joints.find(sc, SPEED)) == it
    assert not paths.is_cable_joint(sc, joints.find(sc, "Luff")) and paths.cable_of_joint(sc, None) is None
    # 100 m at 10 m/min, built: every wheel's rim has run 100 m
    a = run_step(sc, 100.0)
    b = a.blocks[0]
    assert b.speed_mmin == pytest.approx(10.0) and b.speed_mms == pytest.approx(166.667, abs=1e-3)
    b.speed_mms = 200.0
    assert b.speed_mmin == pytest.approx(12.0)
    b.speed_mmin = 10.0
    r = built(sc, a)
    assert r["frames"] == 15001
    it = cable(sc)
    assert not it.moving                                    # nothing that carries a wheel moves in this animation
    part = it.part
    sc.frame_set(1000)
    paid = joints.get_value(joints.find(sc, SPEED))
    assert paid == pytest.approx(999 / 25.0 * 10.0 / 60.0, abs=1e-3)
    pay = part.evaluated_get(bpy.context.evaluated_depsgraph_get())[cable_looks.PAY]
    assert pay - cable_looks.PAY_BIAS == pytest.approx(paid, abs=1e-3)       # the look has moved with the cable
    sc.frame_set(15001)
    paid = joints.get_value(joints.find(sc, SPEED))
    assert paid == pytest.approx(100.0, abs=0.01)
    for c in [c for c in it.contacts if c.kind in paths.TURNING]:
        j = joints.find(sc, c.joint)
        radius = c.radius if c.kind == "SHEAVE" else c.radius - 0.5 * it.cad_diameter
        run = joints.get_value(j) * radius
        assert abs(run) == pytest.approx(100.0, rel=1e-3), c.name
        assert np.sign(run) == np.sign(c.ratio)
        m = j.motion.matrix_basis.to_euler("XYZ")
        assert math.remainder(m.z - joints.get_value(j), 2 * math.pi) == pytest.approx(0.0, abs=2e-3), c.name
    # every driver works with scripts off
    n = 0
    for o in sc.objects:
        for fc in (o.animation_data.drivers if o.animation_data else ()):
            if fc.driver.type == "SCRIPTED":
                assert fc.driver.is_simple_expression, (o.name, fc.data_path, fc.driver.expression)
                n += 1
    assert n >= 11 and joints.couplings_simple(sc)          # 5 followers x 2 + the look's
    fc = part.animation_data.drivers.find(f'["{cable_looks.PAY}"]')
    assert fc.driver.expression == "a * 1.0 + 2.0"
    assert fc.driver.variables[0].targets[0].id == joints.find(sc, SPEED).motion


def test_turns_off_and_runs_the_other_way(rope):
    sc = rope
    it = cable(sc)
    lead = joints.find(sc, SPEED)
    c = contact(sc, "SHEAVE 2")
    name, ratio = c.joint, c.ratio
    c.turns = False
    assert not joints.find(sc, name).follows and joints.find(sc, name) is not None     # it stays, and stands still
    joints.set_value(joints.find(sc, SPEED), 1.0)
    update()
    assert joints.get_value(joints.find(sc, name)) == 0.0
    assert joints.get_value(joints.find(sc, contact(sc, "SHEAVE 1").joint)) == pytest.approx(
        math.radians(contact(sc, "SHEAVE 1").ratio) * 1000.0, rel=1e-5)
    contact(sc, "SHEAVE 2").turns = True
    j = joints.find(sc, name)
    assert j.follows == SPEED and j.couple_ratio == pytest.approx(ratio, rel=1e-6)
    update()
    assert joints.get_value(j) == pytest.approx(math.radians(ratio) * 1000.0, rel=1e-5)
    # the other way: every ratio and the look
    part = it.part
    before = {c.joint: c.ratio for c in it.contacts if c.joint}
    assert part.evaluated_get(bpy.context.evaluated_depsgraph_get())[cable_looks.PAY] == pytest.approx(3.0)
    it.reverse = True
    it = cable(sc)
    for c in it.contacts:
        if c.joint:
            assert c.ratio == pytest.approx(-before[c.joint], rel=1e-6)
            assert joints.find(sc, c.joint).couple_ratio == pytest.approx(c.ratio, rel=1e-6)
    update()
    fc = part.animation_data.drivers.find(f'["{cable_looks.PAY}"]')
    assert fc.driver.expression == "a * -1.0 + 2.0" and fc.driver.is_simple_expression
    assert part.evaluated_get(bpy.context.evaluated_depsgraph_get())[cable_looks.PAY] == pytest.approx(1.0)
    it.reverse = False
    update()
    assert rim_runs_with_the_cable(sc, contact(sc, "WINCH DRUM")) == pytest.approx(1.0, abs=0.01)
    del lead


def test_a_joint_the_user_made_is_kept_and_remove_takes_only_the_apps(folder):
    sc = load(folder, MODEL_A)
    want = N["contacts"]["SHEAVE 1"]
    mine = joints.create(sc, "ROTATE", [ob(sc, "SHEAVE 1")], Vector(np.array(want["axis_point"]) * MM),
                         Vector((0.0, -1.0, 0.0)), name="My sheave")       # (the other way round than the app's)
    assert mine.name == "My sheave"
    roller = N["rollers"][0]
    joints.create(sc, "ROTATE", [ob(sc, "V ROLLER", 0)], Vector(np.array(roller["axis_point"]) * MM),
                  Vector(roller["axis_direction"]), name="My roller")
    joints.create(sc, "ROTATE", [ob(sc, "A-FRAME.ASM")], Vector((1.5, 0.0, 0.73)), Vector((0.0, 1.0, 0.0)), name="Luff")
    joints.set_follows(sc, joints.find(sc, "My roller"), "Luff", ratio=2.0)
    part = ob(sc, "WIRE ROPE")
    me = part.data
    cad = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", cad)
    groups = {g.name for g in sc.fresing.groups}
    group = part[build.PROP_GROUP]
    it = paths.add_cable(sc, CABLE)
    it.look = "ROPE"
    notes = paths.read_cad(sc, it, part)
    it = cable(sc)
    s1, r1 = contact(sc, "SHEAVE 1"), contact(sc, "V ROLLER", 0)
    assert s1.joint == "My sheave" and not s1.made_joint and s1.coupled and not s1.note
    j = joints.find(sc, "My sheave")
    assert j.follows == SPEED and j.couple_ratio == pytest.approx(s1.ratio, rel=1e-6) and paths.TAG not in j.motion
    assert s1.ratio == pytest.approx(-360.0 / (2 * math.pi * s1.radius * 1000.0), rel=1e-6)   # its arrow points to -Y
    assert rim_runs_with_the_cable(sc, s1) == pytest.approx(1.0, abs=0.01)
    assert r1.joint == "My roller" and not r1.made_joint and not r1.coupled
    assert r1.note == "its joint 'My roller' follows 'Luff', not this cable: left as it is"
    j = joints.find(sc, "My roller")
    assert j.follows == "Luff" and j.couple_ratio == pytest.approx(2.0)
    assert "Cable 'Wire rope': 3 new joints so that what it touches turns with it" in notes
    assert "Cable 'Wire rope': 1 joint you had made now follows the cable" in notes
    assert "Cable 'Wire rope': 1 part already had a joint that follows something else: left as it is" in notes
    assert "Cable 'Wire rope', 'V ROLLER': its joint 'My roller' follows 'Luff', not this cable: left as it is" in notes
    assert len(sc.fresing.joints) == 3 + 1 + 3
    check_on_seats(sc, 0.0)
    # remove: only what the app made goes
    shapes = it.shapes.name
    paths.remove(sc, 0)
    update()
    assert len(paths.items(sc)) == 0
    assert sorted(j.name for j in sc.fresing.joints) == ["Luff", "My roller", "My sheave"]
    assert not joints.find(sc, "My sheave").follows                 # released, and it stays
    assert joints.find(sc, "My roller").follows == "Luff"
    assert paths.MOD not in part.modifiers and shapes not in bpy.data.objects
    assert not [o for o in bpy.data.objects if o.name.startswith(paths.SHAPES)]
    assert not [m for m in bpy.data.meshes if m.name.startswith(paths.SHAPES)]
    assert not [g for g in bpy.data.node_groups if g.name.startswith("FR cable")]
    assert flex.COLLECTION not in bpy.data.collections
    for key in (cable_looks.PAY, cable_looks.LOOK, paths.PART, "fr_group_manual"):
        assert key not in part, key
    assert part.animation_data is None or not len(part.animation_data.drivers)
    assert not [o for o in sc.objects if paths.TAG in o]
    assert part[build.PROP_GROUP] == group and {g.name for g in sc.fresing.groups} >= groups
    now, att = drawn(part)
    w = np.array(part.matrix_world, dtype=float)
    assert att is None and np.array_equal(now, cad.reshape(-1, 3).astype(float) @ w[:3, :3].T + w[:3, 3])
    # the sheaves and rollers the app turned are back in the CAD tree
    for name in ("WINCH DRUM", "SHEAVE 2"):
        assert ob(sc, name).parent.get(build.PROP_KIND) == "assembly"
    assert paths.bake(sc, None) == [] and paths.after_model_update(sc, {}, {}) == []


# ---------------------------------------------------------------------------
# sheaves that move
# ---------------------------------------------------------------------------

def tangent_points(sc, luff):
    """The ends of every arc of the drawn cable and its two ends: what fixes its shape."""
    c, _r = rings(cable(sc).part)
    out = [c[0], c[-1]]
    for _name, on, _centre, _seat, _d in arcs(sc, luff):
        out += [c[on[0]], c[on[-1]]]
    return np.array(out)


def test_the_cable_follows_the_luffing_frame_live(rope):
    sc = rope
    it = cable(sc)
    assert it.moving
    solves = paths._STATE["solves"]
    lengths = {}
    for luff in (-15.0, -10.0, -5.0, 0.0, 5.0, 10.0, 15.0):
        joints.set_value(joints.find(sc, "Luff"), math.radians(luff))
        update()
        check_on_seats(sc, luff)
        lengths[luff] = cable(sc).length
        want = maker.numbers_at(luff)
        assert cable(sc).length == pytest.approx(want["rope"]["length"] * MM, rel=1e-3)
        for c in cable(sc).contacts:
            if c.kind != "ROLLER":
                assert math.degrees(c.wrap) == pytest.approx(want["contacts"][c.name]["wrap"], abs=0.2), (luff, c.name)
    assert lengths[-15.0] < lengths[0.0] < lengths[15.0]
    assert paths._STATE["solves"] == solves + 7             # once per pose
    update()
    sc.frame_set(5)
    assert paths._STATE["solves"] == solves + 7             # nothing moved: nothing solved
    joints.set_value(joints.find(sc, SPEED), 3.0)           # paying out moves no wheel's place
    update()
    assert paths._STATE["solves"] == solves + 7
    # a pose applied by a script, with no update in between
    joints.set_value(joints.find(sc, "Luff"), math.radians(-12.0))
    paths.refresh(sc)
    check_on_seats(sc, -12.0)


def test_a_built_animation_has_a_shape_for_every_frame(rope):
    sc = rope
    it = cable(sc)
    a = steps(sc, (("Luff", 0.0, 0.4, math.radians(-15.0)), ("Luff", 0.4, 3.6, math.radians(15.0))))
    stepped, solves = paths._STATE["steps"], paths._STATE["solves"]
    r = built(sc, a)
    it = cable(sc)
    frames = r["frames"]
    assert frames == 101 and it.moving and paths._STATE["steps"] == stepped + frames
    assert paths._STATE["solves"] <= solves + 2 * frames
    mod = it.part.modifiers[paths.MOD]
    assert mod.node_group.name == paths.TREES[True] and len(it.shapes.data.vertices) % frames == 0
    assert paths.status(sc, it)[0].endswith("a shape per frame")
    solves = paths._STATE["solves"]
    worst, kept = 0.0, {}
    for f in list(range(1, frames + 1, 5)) + [frames]:
        sc.frame_set(f)
        luff = luff_deg(sc)
        check_on_seats(sc, luff)
        worst = max(worst, off_path(sc, luff))
        if f in (11, 51, 91):
            kept[f] = (luff, tangent_points(sc, luff), drawn(it.part)[0])
    assert paths._STATE["solves"] == solves                 # nothing is solved while the frames are shown
    print(f"\ntest rope, luffing -15° … +15° built: at most {worst / MM:.3f} mm off the maker's centreline "
          "at every 5th frame")
    assert kept[11][0] < -9.0 and kept[91][0] > 9.0
    # any frame in any order gives the same shape
    sc.frame_set(11)
    sc.frame_set(51)
    one = drawn(it.part)[0]
    sc.frame_set(91)
    sc.frame_set(51)
    assert np.array_equal(drawn(it.part)[0], one) and np.array_equal(one, kept[51][2])
    # a setting changed after Build: every frame again, from the places read at Build (no stepping)
    stepped = paths._STATE["steps"]
    it.diameter = 0.03
    assert paths._STATE["steps"] == stepped and paths._STATE["solves"] >= solves + frames and cable(sc).moving
    sc.frame_set(91)
    _c, radii = rings(it.part)
    assert np.abs(radii - 0.015).max() < 1e-5
    cable(sc).diameter = cable(sc).cad_diameter
    # live, in the same poses: the same shape
    animation.clear_keys(sc)
    it = cable(sc)
    assert not sc.fresing.anim_baked and it.moving
    assert it.part.modifiers[paths.MOD].node_group.name == paths.TREES[False]
    worst = 0.0
    for f, (luff, points, _co) in kept.items():
        joints.set_value(joints.find(sc, "Luff"), math.radians(luff))
        update()
        worst = max(worst, float(np.linalg.norm(tangent_points(sc, luff) - points, axis=1).max()))
    print(f"test rope: the live shape and the built one of the same pose differ by at most {worst / MM:.4f} mm "
          "(where its arcs begin and end)")
    assert worst < 0.01 * MM


def test_a_cable_whose_wheels_stand_still_costs_nothing_per_frame(rope):
    sc = rope
    it = cable(sc)
    part = it.part
    # the luff joint is there but does not move in this animation: one shape, the still tree
    a = run_step(sc, 2.0)
    stepped = paths._STATE["steps"]
    built(sc, a)
    it = cable(sc)
    assert not it.moving and paths._STATE["steps"] <= stepped + 1
    assert part.modifiers[paths.MOD].node_group.name == paths.TREES[False]
    assert len(it.shapes.data.vertices) == len(paths.shape_now(sc, it))
    assert "GeometryNodeInputSceneTime" not in {n.bl_idname for n in bpy.data.node_groups[paths.TREES[False]].nodes}
    solves = paths._STATE["solves"]
    with Evaluations(part) as seen:
        for f in range(1, 61):
            sc.frame_set(f)
    assert seen.count == 0 and paths._STATE["solves"] == solves             # the tube is not worked out again
    assert part.evaluated_get(bpy.context.evaluated_depsgraph_get())[cable_looks.PAY] > 2.3    # … but its look moves
    check_on_seats(sc, 0.0)
    # the test animation luffs: a shape per frame, worked out by nodes only
    built(sc, sc.fresing.animations[paths.TEST_ANIMATION])
    it = cable(sc)
    assert it.moving and part.modifiers[paths.MOD].node_group.name == paths.TREES[True]
    assert "GeometryNodeInputSceneTime" in {n.bl_idname for n in bpy.data.node_groups[paths.TREES[True]].nodes}
    solves = paths._STATE["solves"]
    with Evaluations(part) as seen:
        for f in range(1, 61):
            sc.frame_set(f)
    assert seen.count == 60 and paths._STATE["solves"] == solves
    sc.frame_set(76)
    assert luff_deg(sc) == pytest.approx(12.0, abs=1e-3)
    check_on_seats(sc, 12.0)
    assert joints.get_value(joints.find(sc, SPEED)) == pytest.approx(0.5, abs=1e-4)


def test_cost_per_frame_with_a_thousand_parts(rope):
    sc = rope
    it = cable(sc)
    src = ob(sc, "V ROLLER")
    for k in range(1000):                                   # a bigger scene: parts that do nothing
        o = bpy.data.objects.new(f"Dummy {k}", src.data)
        o.location = (0.3 * (k % 40), 3.0 + 0.3 * (k // 40), 0.0)
        sc.collection.objects.link(o)
    update()

    def per_frame(n=60, rounds=3):
        best = math.inf
        for _ in range(rounds):
            t0 = time.perf_counter()
            for f in range(1, n + 1):
                sc.frame_set(f)
            best = min(best, (time.perf_counter() - t0) / n)
        return best * 1000.0

    def in_turns():                                         # (ms with the cable drawn, ms with its modifier off)
        mod, on, off = cable(sc).part.modifiers[paths.MOD], [], []
        for _ in range(3):
            on.append(per_frame(40, 1))
            mod.show_viewport = False
            per_frame(2, 1)
            off.append(per_frame(40, 1))
            mod.show_viewport = True
            per_frame(2, 1)
        return min(on), min(off)

    built(sc, run_step(sc, 2.0))
    assert not cable(sc).moving
    still, off = in_turns()
    built(sc, sc.fresing.animations[paths.TEST_ANIMATION])
    assert cable(sc).moving
    moving, off2 = in_turns()
    print(f"\ncost per frame, test model + 1,000 parts (this machine): cable off {off:.2f} ms, still cable "
          f"{still:.2f} ms "
          f"({still - off:+.2f}); luffing animation: cable off {off2:.2f} ms, moving cable {moving:.2f} ms "
          f"({moving - off2:+.2f})")
    assert still - off < 1.0 and moving - off2 < 5.0


# ---------------------------------------------------------------------------
# the smallest bend, and paths that cannot be
# ---------------------------------------------------------------------------

def test_a_bend_tighter_than_the_smallest_bend_warns(rope):
    sc = rope
    it = cable(sc)
    it.mbr = 0.3
    text = "bends tighter than its smallest bend (MBR 300 mm) at 'SHEAVE 2': 180 mm"
    assert paths.status(sc, cable(sc)) == (text, "WARN")
    r = animation.bake(sc, run_step(sc, 1.0))
    assert r["warnings"] == [f"Cable 'Wire rope' {text}"]
    cable(sc).mbr = 0.19
    assert "'SHEAVE 2'" in paths.status(sc, cable(sc))[0]
    cable(sc).mbr = 0.17
    assert paths.status(sc, cable(sc))[1] == "OK"
    cable(sc).mbr = 0.0
    assert paths.status(sc, cable(sc))[1] == "OK"
    # only a bend the cable really goes round counts: with the chute's bend too tight it is named, not a roller
    cable(sc).mbr = 0.65
    assert "'SHEAVE 2': 180 mm" in paths.status(sc, cable(sc))[0]
    animation.clear_keys(sc)


def test_a_pose_without_a_path_keeps_the_last_shape(rope):
    sc = rope
    it = cable(sc)
    update()
    good = drawn(it.part)[0]
    luff = joints.find(sc, "Luff")
    luff.use_limits = False
    joints.set_value(joints.find(sc, "Luff"), math.radians(-110.0))       # sheave 1 lies in the drum
    update()
    it = cable(sc)
    text, level = paths.status(sc, it)
    assert level == "WARN" and text.startswith("cannot go round 'SHEAVE 1' in this pose: ")
    assert "'WINCH DRUM' and 'SHEAVE 1' overlap" in text and "contact" not in text.lower()
    now = drawn(it.part)[0]
    assert np.isfinite(now).all() and now.shape == good.shape and np.abs(now - good).max() < 1e-6
    joints.set_value(joints.find(sc, "Luff"), 0.0)
    update()
    assert paths.status(sc, cable(sc))[1] == "OK"
    # along a built animation: a warning with the first frame, the frames without a path keep the last good one
    a = steps(sc, (("Luff", 0.0, 2.0, math.radians(-110.0)),))
    r = animation.bake(sc, a)
    it = cable(sc)
    assert len(r["warnings"]) == 1 and it.problem_frame > 1
    assert r["warnings"][0].startswith(f"Cable 'Wire rope' cannot go round 'SHEAVE 1' at frame {it.problem_frame}: ")
    sc.frame_set(it.problem_frame - 1)
    last = drawn(it.part)[0]
    check_on_seats(sc, luff_deg(sc))
    for f in (it.problem_frame, it.problem_frame + 3, sc.frame_end):
        sc.frame_set(f)
        now = drawn(it.part)[0]
        assert np.isfinite(now).all() and np.array_equal(now, last), f
    animation.clear_keys(sc)


def test_a_wheel_the_cable_lifts_off_is_a_bad_frame():
    """A wrap that jumps from next to nothing to a loop round the wheel (or the solver's own ``lifted``): the
    cable has left that wheel. Those frames keep the last good shape and the warning names the wheel."""
    wrap = np.array([[1.0, 0.5], [0.9, 0.4], [0.8, 0.01], [0.8, 5.9], [0.8, 5.8], [0.7, 0.02]])
    F = len(wrap)

    def result():
        return {"ok": np.ones(F, dtype=bool), "wrap": wrap.copy(), "bad": -np.ones(F, dtype=int), "problems": {},
                "points": np.arange(F * 6, dtype=float).reshape(F, 2, 3),
                "s": np.arange(F * 2, dtype=float).reshape(F, 2),
                "length": np.arange(F, dtype=float)}

    res = result()
    paths._lifted(res, ["SHEAVE 1", "SHEAVE 2"])
    assert list(res["ok"]) == [True, True, True, False, False, True] and res["off"] == {3: 1, 4: 1}
    assert res["problems"][3] == "the cable no longer touches 'SHEAVE 2' (it has lifted off)"
    for f in (3, 4):
        assert np.array_equal(res["points"][f], res["points"][2]) and res["length"][f] == 2.0 and res["bad"][f] == 1
    res = result()
    res["wrap"][3:5, 1] = 0.0
    res["lifted"] = np.zeros((F, 2), dtype=bool)
    res["lifted"][3:5, 1] = True
    paths._lifted(res, ["SHEAVE 1", "SHEAVE 2"])
    assert list(res["ok"]) == [True, True, True, False, False, True] and res["off"] == {3: 1, 4: 1}
    res = result()
    res["wrap"][3:5, 1] = 0.3                                # a wrap that only grows and shrinks: nothing lifted
    paths._lifted(res, ["SHEAVE 1", "SHEAVE 2"])
    assert res["ok"].all() and not res["off"]


def test_a_cable_that_stays_as_drawn(rope):
    sc = rope
    it = cable(sc)
    assert it.moving and not it.still
    update()
    before = rings(it.part)[0]
    it.still = True
    assert not cable(sc).moving and paths.status(sc, cable(sc))[1] == "OK"
    update()
    assert np.abs(rings(cable(sc).part)[0] - before).max() < 1e-6
    before = rings(cable(sc).part)[0]
    solves = paths._STATE["solves"]
    joints.set_value(joints.find(sc, "Luff"), math.radians(10.0))
    joints.set_value(joints.find(sc, SPEED), 2.0)
    update()
    assert paths._STATE["solves"] == solves and np.array_equal(rings(cable(sc).part)[0], before)
    assert joints.get_value(joints.find(sc, contact(sc, "SHEAVE 1").joint)) != 0.0       # it still turns its wheels
    cable(sc).mbr = 0.3                                     # a setting: solved for the CAD pose, not for this one
    update()
    assert np.array_equal(rings(cable(sc).part)[0], before) and "'SHEAVE 2'" in paths.status(sc, cable(sc))[0]
    # Build does not step through the frames for it
    stepped = paths._STATE["steps"]
    r = animation.bake(sc, sc.fresing.animations[paths.TEST_ANIMATION])
    it = cable(sc)
    assert paths._STATE["steps"] == stepped and not it.moving and len(r["warnings"]) == 1
    assert it.part.modifiers[paths.MOD].node_group.name == paths.TREES[False]
    sc.frame_set(76)
    update()
    assert np.array_equal(rings(it.part)[0], before)
    animation.clear_keys(sc)
    cable(sc).still = False
    assert cable(sc).moving
    joints.set_value(joints.find(sc, "Luff"), math.radians(10.0))
    update()
    check_on_seats(sc, 10.0)


def test_flip_a_contact_and_flip_it_back(rope):
    sc = rope
    it = cable(sc)
    update()
    before = rings(it.part)[0]
    k = index(sc, "SHEAVE 2")
    ratio = it.contacts[k].ratio
    paths.flip_contact(sc, it, k)
    it = cable(sc)
    update()
    c = it.contacts[k]
    assert c.side == 1 and c.user and c.ratio == pytest.approx(-ratio, rel=1e-6)
    assert joints.find(sc, c.joint).couple_ratio == pytest.approx(c.ratio, rel=1e-6)
    over = rings(it.part)[0]
    assert np.isfinite(over).all() and paths.status(sc, it)[1] == "OK"
    centre = np.array(N["contacts"]["SHEAVE 2"]["axis_point"]) * MM
    on = np.linalg.norm(over - centre, axis=1) < c.radius + 1 * MM
    assert on.sum() >= 3 and over[on][:, 2].max() > centre[2] + 0.9 * c.radius     # over its top now
    assert math.degrees(c.wrap) > 180.0 and it.length > N["rope"]["length"] * MM
    paths.flip_contact(sc, it, k)
    update()
    again = rings(cable(sc).part)[0]
    assert again.shape == before.shape and np.abs(again - before).max() < 1e-6
    assert cable(sc).contacts[k].ratio == pytest.approx(ratio, rel=1e-6)
    # a roller only turns the other way
    k = index(sc, "V ROLLER")
    ratio = cable(sc).contacts[k].ratio
    paths.flip_contact(sc, cable(sc), k)
    assert cable(sc).contacts[k].ratio == pytest.approx(-ratio, rel=1e-6)
    assert np.abs(rings(cable(sc).part)[0] - before).max() < 1e-6
    paths.flip_contact(sc, cable(sc), k)
    # a side the cable cannot take: refused in plain words, nothing changed. With the A-frame laid back over the
    # drum, sheave 1 lies in the drum's circle: no rope can cross over between them …
    joints.find(sc, "Luff").use_limits = False
    joints.set_value(joints.find(sc, "Luff"), math.radians(-110.0))
    update()
    assert paths.status(sc, cable(sc))[1] == "WARN"
    k = index(sc, "SHEAVE 2")
    with pytest.raises(paths.PathError) as err:
        paths.flip_contact(sc, cable(sc), k)
    assert str(err.value).startswith("The cable cannot go round the other side of 'SHEAVE 2': 'WINCH DRUM' and "
                                     "'SHEAVE 1' overlap")
    assert "contact" not in str(err.value).lower() and cable(sc).contacts[k].side == -1
    # … but it can go round both the same way
    paths.flip_contact(sc, cable(sc), index(sc, "SHEAVE 1"))
    update()
    assert paths.status(sc, cable(sc))[1] == "OK" and np.isfinite(rings(cable(sc).part)[0]).all()
    assert contact(sc, "SHEAVE 1").side == -1


# ---------------------------------------------------------------------------
# by hand
# ---------------------------------------------------------------------------

def test_remove_a_contact_and_add_it_again(rope):
    sc = rope
    it = cable(sc)
    update()
    before = rings(it.part)[0]
    length = it.length
    # without sheave 2 the rope would have to come onto the chute from behind: refused, nothing changed
    count = len(sc.fresing.joints)
    with pytest.raises(paths.PathError) as err:
        paths.remove_contact(sc, it, index(sc, "SHEAVE 2"))
    assert str(err.value).startswith("Without 'SHEAVE 2' the cable has no path: ") and "'CHUTE'" in str(err.value)
    it = cable(sc)
    assert [c.name for c in it.contacts] == ORDER and len(sc.fresing.joints) == count
    assert joints.find(sc, contact(sc, "SHEAVE 2").joint).follows == SPEED
    # sheave 1 can go: the rope then runs from the drum straight to sheave 2
    k = index(sc, "SHEAVE 1")
    c = it.contacts[k]
    joint, ratio, radius = c.joint, c.ratio, c.radius
    centre = np.array(N["contacts"]["SHEAVE 1"]["axis_point"]) * MM
    middle = before[np.linalg.norm(before - centre, axis=1) < radius + 1 * MM]
    middle = middle[len(middle) // 2]
    hit = centre + (middle - centre) * (c.surface / radius)              # on the groove's bottom, under the rope
    paths.remove_contact(sc, it, k)
    it = cable(sc)
    update()
    assert [c.name for c in it.contacts] == ORDER[:1] + ORDER[2:] and joints.find(sc, joint) is None
    assert ob(sc, "SHEAVE 1").parent == ob(sc, "A-FRAME.ASM")            # back in the CAD tree
    without = rings(it.part)[0]
    assert np.isfinite(without).all() and it.length < length - 0.5 and paths.status(sc, it)[1] == "OK"
    assert np.linalg.norm(without - centre, axis=1).min() > radius + 0.1
    # click the sheave where the rope lay: it is back where it was
    at = paths.add_contact(sc, it, ob(sc, "SHEAVE 1"), hit=hit)
    it = cable(sc)
    update()
    c = it.contacts[at]
    assert at == k and [x.name for x in it.contacts] == ORDER and c.kind == "SHEAVE" and c.side == 1 and c.user
    assert c.radius == pytest.approx(radius, abs=0.02 * MM) and c.made_joint and c.coupled
    assert c.ratio == pytest.approx(ratio, rel=1e-4) and joints.find(sc, c.joint).follows == SPEED
    again = rings(it.part)[0]
    assert again.shape == before.shape and np.abs(again - before).max() < 0.05 * MM
    assert it.length == pytest.approx(length, abs=0.05 * MM)
    with pytest.raises(paths.PathError, match="'SHEAVE 1' is in the cable's list already"):
        paths.add_contact(sc, it, ob(sc, "SHEAVE 1"), hit=hit)
    # a roller the cable runs over: found as a roller, in its place, turning as before
    k = index(sc, "V ROLLER", 1)
    ratio = it.contacts[k].ratio
    roller = it.contacts[k].part
    paths.remove_contact(sc, it, k)
    assert len(cable(sc).contacts) == 5
    assert np.abs(rings(cable(sc).part)[0] - again).max() < 1e-6          # a roller does not shape the path
    at = paths.add_contact(sc, cable(sc), roller)
    c = cable(sc).contacts[at]
    assert at == k and c.kind == "ROLLER" and c.part == roller and c.user and c.ratio == pytest.approx(ratio, rel=1e-4)
    assert rim_runs_with_the_cable(sc, c) == pytest.approx(1.0, abs=0.01)
    # contacts added by hand stay when the cable is read again; no joint twice
    count = len(sc.fresing.joints)
    paths.read_cad(sc, cable(sc), cable(sc).part)
    it = cable(sc)
    assert [x.name for x in it.contacts] == ORDER and len(sc.fresing.joints) == count
    assert [x.user for x in it.contacts] == [False, True, False, False, True, False]
    update()
    assert np.abs(rings(it.part)[0] - again).max() < 0.05 * MM
    # parts the cable cannot use
    for name, why in (("BASE FRAME", "does not reach|would not lie on"),
                      ("WIRE ROPE", "not a part the cable can run over"), ("CHUTE STAND", "has no round face"),
                      ("A-FRAME.ASM", "not a part the cable can run over")):
        with pytest.raises(paths.PathError, match=why):
            paths.add_contact(sc, cable(sc), ob(sc, name))
    assert [x.name for x in cable(sc).contacts] == ORDER and len(sc.fresing.joints) == count
    update()
    assert np.abs(rings(cable(sc).part)[0] - again).max() < 0.05 * MM
    # without the drum the rope would start in the air: it starts on its first wheel, sheave 1, then
    paths.remove_contact(sc, cable(sc), 0)
    it = cable(sc)
    update()
    assert it.a_kind == "WHEEL" and it.a_part == contact(sc, "SHEAVE 1").carrier
    assert np.isfinite(rings(it.part)[0]).all() and paths.status(sc, it)[1] == "OK"


def test_an_end_on_a_part_and_a_free_end(rope):
    sc = rope
    it = cable(sc)
    update()
    before = rings(it.part)[0]
    stand = ob(sc, "CHUTE STAND")
    paths.set_end(sc, it, "B", stand)
    it = cable(sc)
    update()
    assert it.b_part == stand and it.b_kind == "FIXED" and not it.b_free_end and it["b_user"]
    assert np.abs(rings(it.part)[0] - before).max() < 0.01 * MM          # it stays where it is
    # … and from now on goes with that part
    stand.matrix_basis = stand.matrix_basis @ __import__("mathutils").Matrix.Translation((0.0, 0.0, -0.05))
    update()
    paths.refresh(sc, force=True)
    update()
    moved = rings(cable(sc).part)[0]
    assert moved[-1][2] == pytest.approx(before[-1][2] - 0.05, abs=1e-5) and np.abs(moved[0] - before[0]).max() < 1e-6
    stand.matrix_basis = build.rest_basis(stand)
    update()
    paths.set_end(sc, cable(sc), "B", None)
    it = cable(sc)
    update()
    assert it.b_free_end and it.b_part == ob(sc, "CHUTE") and "b_user" not in it
    assert np.abs(rings(it.part)[0] - before).max() < 0.01 * MM
    # the free length: straight on along the same line
    it.b_free = 0.8
    update()
    longer = rings(cable(sc).part)[0]
    assert np.abs(longer[:-1] - before[:-1]).max() < 0.01 * MM
    assert np.linalg.norm(longer[-1] - longer[-2]) == pytest.approx(0.8, abs=0.05 * MM)
    run = (before[-1] - before[-2]) / np.linalg.norm(before[-1] - before[-2])
    assert np.linalg.norm(np.cross(longer[-1] - before[-2], run)) < 0.01 * MM
    assert cable(sc).length == pytest.approx(N["rope"]["length"] * MM + 0.3, abs=1 * MM)
    cable(sc).b_free = 0.0                                               # as drawn in CAD again
    update()
    assert np.abs(rings(cable(sc).part)[0] - before).max() < 0.05 * MM
    with pytest.raises(paths.PathError, match="Pick end A or end B"):
        paths.set_end(sc, cable(sc), "C", stand)
    with pytest.raises(paths.PathError, match="not a part of the model"):
        paths.set_end(sc, cable(sc), "B", cable(sc).shapes)


def test_candidates_are_found_by_name(rope, folder):
    sc = rope
    assert paths.candidates(sc) == []                       # the rope is a cable already
    paths.remove(sc, 0)
    assert [o.get(build.PROP_NAME) for o in paths.candidates(sc)] == ["WIRE ROPE"]
    names = {"POWER CABLE 3x240": True, "Staalkabel 24": True, "DRAHTSEIL": True, "TROS": True, "UMBILICAL": True,
             "CABLE ROLLER": False, "CABLE DRUM": False, "WIRE ROPE SHEAVE": False, "CABLE TRAY": False,
             "CABLEWAY": False, "ROPER": False, "CABLE GLAND M20": False, "Kabelschelle": False}
    src = ob(sc, "CHUTE STAND")
    for k, name in enumerate(names):
        o = src.copy()
        o[build.PROP_NAME], o[build.PROP_UID] = name, f"TEST.PATHS#1/X{k}#1"
        sc.collection.objects.link(o)
    found = {o.get(build.PROP_NAME) for o in paths.candidates(sc)}
    assert found == {n for n, yes in names.items() if yes} | {"WIRE ROPE"}


# ---------------------------------------------------------------------------
# the rest of the app
# ---------------------------------------------------------------------------

def test_save_and_open_again(rope, tmp_path):
    sc = rope
    it = cable(sc)
    it.mbr = 0.1
    joints.set_value(joints.find(sc, "Luff"), math.radians(7.0))
    joints.set_value(joints.find(sc, SPEED), 1.5)
    update()
    before = rings(it.part)[0]
    path = str(tmp_path / "rope.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    it = cable(sc)
    assert [c.name for c in it.contacts] == ORDER and it.mbr == pytest.approx(0.1) and it.look == "ROPE"
    mod = it.part.modifiers.get(paths.MOD)
    assert mod is not None and mod.node_group.name == paths.TREES[False] and mod.show_viewport and mod.show_render
    update()
    assert np.array_equal(rings(it.part)[0], before) and luff_deg(sc) == pytest.approx(7.0, abs=1e-3)   # as saved
    check_on_seats(sc, 7.0)
    part = it.part
    assert part.evaluated_get(bpy.context.evaluated_depsgraph_get())[cable_looks.PAY] == pytest.approx(3.5)
    joints.set_value(joints.find(sc, SPEED), 2.5)
    joints.set_value(joints.find(sc, "Luff"), math.radians(-9.0))
    update()
    assert part.evaluated_get(bpy.context.evaluated_depsgraph_get())[cable_looks.PAY] == pytest.approx(4.5)
    check_on_seats(sc, -9.0)                                # live again after loading
    assert joints.get_value(joints.find(sc, contact(sc, "SHEAVE 1").joint)) == pytest.approx(
        math.radians(contact(sc, "SHEAVE 1").ratio) * 2500.0, rel=1e-5)
    # a built animation: saved, opened, its frames show; a setting changed then solves every frame again
    built(sc, sc.fresing.animations[paths.TEST_ANIMATION])
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    it = cable(sc)
    assert sc.fresing.anim_baked == paths.TEST_ANIMATION and it.moving
    solves, stepped = paths._STATE["solves"], paths._STATE["steps"]
    for f in (1, 60, 76, 151):
        sc.frame_set(f)
        check_on_seats(sc, luff_deg(sc))
    assert paths._STATE["solves"] == solves
    it.mbr = 0.2
    assert paths._STATE["steps"] == stepped and paths._STATE["solves"] >= solves + 151
    assert "'SHEAVE 2'" in paths.status(sc, cable(sc))[0]
    sc.frame_set(76)
    check_on_seats(sc, 12.0)


def test_undo_steps_and_the_handlers_keep_nothing(rope):
    """Undo itself cannot run with Blender as a module (``ed.undo`` has no window to work in); the real-app test
    does that. Here: an undo step around 'From CAD cable' can be made, and what undo and redo call leaves the
    module with nothing that points at old data."""
    sc = rope
    it = cable(sc)
    assert bpy.ops.ed.undo_push(message="Before") == {"FINISHED"}
    paths.read_cad(sc, it, it.part)
    assert bpy.ops.ed.undo_push(message="From CAD cable") == {"FINISHED"}
    update()
    assert paths._STATE["arrays"]
    for fn in (paths._on_undo, paths._on_load):
        paths.shape_now(sc, cable(sc))
        fn()
        assert not paths._STATE["last"] and not paths._STATE["arrays"] and not paths._STATE["inputs"]
    joints.set_value(joints.find(sc, "Luff"), math.radians(6.0))
    update()
    check_on_seats(sc, 6.0)                                 # and everything is found again


def test_model_update_keeps_the_cable(rope):
    sc = rope
    it = cable(sc)
    it.mbr, it.pitch = 0.15, 0.2
    contact(sc, "V ROLLER", 1).turns = False
    it = cable(sc)
    update()
    before = rings(it.part)[0]
    ratios = [c.ratio for c in it.contacts]
    old_part = it.part.name
    joints_before = sorted(j.name for j in sc.fresing.joints)
    root = next(r for r in build.model_roots(sc))
    assert bpy.ops.fresing.import_step(filepath=MODEL_B, quality="draft", update_root=root.name) == {"FINISHED"}
    update()
    notes = [n.text for n in sc.fresing.report_notes]
    print("\nmodel update, notes about the cable:", [n for n in notes if "able" in n or "oint" in n])
    it = cable(sc)
    assert len(paths.items(sc)) == 1 and it.part is not None and it.part.name != old_part
    assert it.part.get(build.PROP_NAME) == "WIRE ROPE" and it.part.name in sc.objects
    assert [c.name for c in it.contacts] == ORDER and [c.kind for c in it.contacts] == KINDS
    assert sorted(j.name for j in sc.fresing.joints) == joints_before
    assert it.mbr == pytest.approx(0.15) and it.pitch == pytest.approx(0.2) and it.look == "ROPE" and it.joint == SPEED
    assert it.part["fr_group_manual"] == "Wire ropes" and list(it.part[cable_looks.LOOK])[1] == -6.0
    assert it[paths.WAS] == ""                              # … and Plain still knows it was in no group by hand
    for c, ratio in zip(it.contacts, ratios):
        assert c.ratio == pytest.approx(ratio, rel=1e-6), c.name
        if c.kind in paths.TURNING:
            j = joints.find(sc, c.joint)
            assert j is not None and c.made_joint and c.carrier == j.frame and j.motion[paths.TAG] == CABLE
            assert c.part.name in sc.objects and joints.members(j) == [c.part]
            assert j.follows == (SPEED if c.turns else ""), c.name
    assert [c.turns for c in it.contacts] == [True, True, True, True, False, True]
    assert joints.find(sc, SPEED).motion[paths.TAG] == CABLE and it.made_joint
    assert paths.status(sc, it)[1] == "OK" and it.a_kind == "WHEEL" and it.b_part.get(build.PROP_NAME) == "CHUTE"
    after = rings(it.part)[0]
    assert after.shape == before.shape and np.abs(after - before).max() < 0.01 * MM
    fc = it.part.animation_data.drivers.find(f'["{cable_looks.PAY}"]')
    assert fc is not None and fc.driver.variables[0].targets[0].id == joints.find(sc, SPEED).motion
    joints.set_value(joints.find(sc, "Luff"), math.radians(11.0))
    joints.set_value(joints.find(sc, SPEED), 0.5)
    update()
    check_on_seats(sc, 11.0)
    assert joints.get_value(joints.find(sc, contact(sc, "SHEAVE 2").joint)) == pytest.approx(
        math.radians(contact(sc, "SHEAVE 2").ratio) * 500.0, rel=1e-5)
    assert not [n for n in notes if n.startswith("Cable 'Wire rope'")]       # nothing to report about the cable


def test_a_cable_gone_in_the_new_revision(rope):
    """Updating to another model altogether: the cable stays in the list, says what is missing, nothing breaks."""
    sc = rope
    root = next(r for r in build.model_roots(sc))
    assert bpy.ops.fresing.import_step(filepath=CRANE, quality="draft", update_root=root.name) == {"FINISHED"}
    update()
    notes = [n.text for n in sc.fresing.report_notes]
    assert "Cable 'Wire rope': its part is gone in the new revision" in notes
    it = cable(sc)
    assert it.part is None and paths.status(sc, it) == ("its part is gone", "ERROR")
    a = steps(sc, ())
    assert any("its part is gone" in w for w in paths.bake(sc, a))
    paths.refresh(sc, force=True)
    paths.after_clear(sc)
    sc.frame_set(3)
    update()
    paths.remove(sc, 0)
    assert len(paths.items(sc)) == 0


def test_the_clash_check_leaves_the_cable_out_and_finds_nothing(rope):
    sc = rope
    it = cable(sc)
    assert it.part.name not in {o.name for o in clash.objects(sc)}
    assert "SHEAVE 1" in {o.get(build.PROP_NAME) for o in clash.objects(sc)}
    built(sc, sc.fresing.animations[paths.TEST_ANIMATION])
    run = clash.check(sc)
    assert not run.rows, [(r.a, r.b, r.depth) for r in run.rows]
    assert clash.state(sc)["text"] == "No clashes"
    paths.remove(sc, 0)
    assert "WIRE ROPE" in {o.get(build.PROP_NAME) for o in clash.objects(sc)}


def test_a_project_without_cables_gets_nothing(folder):
    sc = load(folder, MODEL_A)
    joints.create(sc, "ROTATE", [ob(sc, "A-FRAME.ASM")], Vector((1.5, 0.0, 0.73)), Vector((0, 1, 0)), name="Luff")
    solves = paths._STATE["solves"]
    a = steps(sc, (("Luff", 0.0, 1.0, math.radians(10)),))
    built(sc, a)
    assert paths.bake(sc, a) == [] and paths.after_model_update(sc, {}, {}) == []
    paths.refresh(sc)
    paths.refresh(sc, force=True)
    paths.after_clear(sc)
    sc.frame_set(10)
    update()
    assert flex.COLLECTION not in bpy.data.collections
    assert not [o for o in bpy.data.objects if o.name.startswith(paths.SHAPES)]
    assert not [g for g in bpy.data.node_groups if g.name.startswith("FR cable")]
    assert not [o for o in sc.objects if o.modifiers.get(paths.MOD) or paths.PART in o or cable_looks.PAY in o]
    assert paths._STATE["solves"] == solves and paths.candidates(sc) and clash.objects(sc)
    assert "Power cables" not in sc.fresing.groups and "Wire ropes" not in sc.fresing.groups


def test_an_older_node_tree_is_made_again(rope):
    sc = rope
    it = cable(sc)
    old = bpy.data.node_groups[paths.TREES[False]]
    old[paths.PART] = paths.VERSION - 1
    paths.forget()
    paths.refresh(sc, force=True)
    update()
    new = it.part.modifiers[paths.MOD].node_group
    assert new != old and new.name == paths.TREES[False] and new[paths.PART] == paths.VERSION
    assert paths.TREES[False] + " old" not in bpy.data.node_groups       # the unused old one is gone
    check_on_seats(sc, 0.0)


# ---------------------------------------------------------------------------
# the demo vessel's power cable
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def vessel(tmp_path_factory):
    """The small form of the demo project (Draft meshes, no quay), built up to its joints: the model, the looks
    and every joint of the sheet with the rollers following "Cable travel" – what the cable stage finds. The
    stages after that (cylinders, wires, surroundings, cameras, the shots) are left out: the cable does not need
    them and they take as long again."""
    pytest.importorskip("OCP")
    from fresing_render.blender import demo
    folder = str(tmp_path_factory.mktemp("demo_cable"))
    t0 = time.perf_counter()
    out = demo.build_project(folder, "9.9.9", small=True, only=("model", "looks", "joints"))
    bpy.ops.wm.open_mainfile(filepath=out["path"])
    paths.forget()
    flex.forget()
    return {"demo": demo, "seconds": time.perf_counter() - t0}


def test_the_demo_vessels_power_cable(vessel):
    demo = vessel["demo"]
    sc = bpy.context.scene
    parts = len(list(build.iter_parts(sc)))
    n_joints = len(sc.fresing.joints)
    part = next(o for o in build.iter_parts(sc) if o.get(build.PROP_NAME) == "CABLE")
    followers = {j.name: j.couple_ratio for j in sc.fresing.joints if j.follows == demo.CABLE}
    a = sc.fresing.animations.add()
    a.name, a.tail, a.fps = "Lay", 0.0, "25"
    b = a.blocks.add()
    b.kind, b.joint, b.start, b.duration, b.easing = "MOTOR", demo.CABLE, 0.0, 4.0, "LINEAR"
    b.speed_mmin = 10.0
    built(sc, a)

    def per_frame(n=60):
        t0 = time.perf_counter()
        for f in range(1, n + 1):
            sc.frame_set(f)
        return (time.perf_counter() - t0) / n * 1000.0

    per_frame(10)
    before = min(per_frame(), per_frame())
    animation.clear_keys(sc)
    # the CAD centreline, for comparing
    verts, tris = flex._mesh_arrays(part.data)
    w = np.array(part.matrix_world, dtype=float)
    line = P.centreline(verts @ w[:3, :3].T + w[:3, 3], tris, 0.025).points      # (a point every 25 mm)

    it = paths.add_cable(sc, "Power cable", joint=demo.CABLE)
    assert it.joint == demo.CABLE and not it.made_joint and len(sc.fresing.joints) == n_joints
    t0 = time.perf_counter()
    notes = paths.read_cad(sc, it, part)
    took = time.perf_counter() - t0
    it = paths.find(sc, "Power cable")
    kinds = {}
    for c in it.contacts:
        kinds[c.kind] = kinds.get(c.kind, 0) + 1
    rollers = [c for c in it.contacts if c.kind == "ROLLER"]
    bends = [c for c in it.contacts if c.kind in paths.SHAPING]
    print(f"\ndemo vessel (small form: Draft meshes, {parts} parts, {n_joints} joints; built up to its joints in "
          f"{vessel['seconds']:.0f} s): 'From CAD cable' took {took:.1f} s: {kinds}, Ø {it.diameter * 1000:.0f} mm, "
          f"{it.length:.2f} m")
    for n in notes[:6]:
        print("   ", n)
    assert len(rollers) == 218 and len(bends) == 14 and not kinds.get("SHEAVE")
    assert it.diameter == pytest.approx(0.2, abs=0.002) and it.length == pytest.approx(188.06, abs=0.2)
    # every roller keeps its own joint, which follows "Cable travel" already: no new joint, no coupling changed
    assert len(sc.fresing.joints) == n_joints
    assert {j.name: j.couple_ratio for j in sc.fresing.joints if j.follows == demo.CABLE} == followers
    off, other_way = [], 0
    for c in rollers:
        j = joints.find(sc, c.joint)
        assert j is not None and not c.made_joint and not c.coupled and j.follows == demo.CABLE, c.name
        assert c.carrier == j.frame
        other_way += int(c.ratio * j.couple_ratio < 0.0)
        off.append(abs(abs(j.couple_ratio) / abs(c.ratio) - 1.0))
    off = np.array(off)
    noted = [c for c in rollers if c.note]
    print(f"    rollers: {len(rollers)} keep their own joint; their ratio against the app's (cable skin as drawn): "
          f"at most {off.max() * 100:.2f} % off, {int((off > paths.RATIO_TOL).sum())} more than 0.5 % off; "
          f"{other_way} turn the other way; {len(noted)} with a note")
    assert other_way == 0 and off.max() < 0.02 and np.median(off) < 0.005   # (Draft facets: about 1 mm on a roller)
    # the bends: which lie on a part, which are carried by the cable's parent
    print("    bends:", [(c.name, c.kind, round(c.radius, 3), round(math.degrees(c.wrap), 1)) for c in bends])
    # what it lies on that can move against the vessel: the D-quadrant's gutter (it travels and tilts). The coil
    # turns on the carousel about the bend's own axis: that bend stays on the carousel joint's arrow.
    movers = sorted({c.name for c in bends if flex._movers(c.carrier) != flex._movers(part)})
    coil = next(c for c in bends if c.name == "CABLE COIL")
    print(f"    can move against the cable part: {movers}; the coil's bend is carried by '{coil.carrier.name}'")
    assert movers == ["QUADRANT GUTTER"] and it.moving and coil.carrier.get(build.PROP_KIND) == "joint_frame"
    assert any("follows what it lies on when that moves ('QUADRANT GUTTER')" in n for n in notes)
    assert paths.status(sc, it)[1] == "OK"
    update()
    c_, radii = rings(part)
    assert np.abs(radii - 0.1).max() < 1e-4
    worst = float(to_line(c_, line).max())
    back = float(to_line(line[::4], c_).max())
    print(f"    the drawn cable ({len(c_)} rings): its rings' middles at most {worst * 1000:.2f} mm off the CAD "
          f"centreline; the CAD centreline at most {back * 1000:.2f} mm off the drawn path (chords of its arcs)")
    assert worst < 0.0015                                   # (Draft meshes: the facets of the cable's bends)
    _co, att = drawn(part)
    assert att[:, 2].max() == pytest.approx(it.length, abs=1e-3)
    assert part["fr_group_manual"] == "Power cables" and sc.fresing.groups["Power cables"].material == "cable_power"
    # an animation in which the quadrant stands still: one shape, read at one frame, nothing per frame
    stepped = paths._STATE["steps"]
    built(sc, a)
    it = paths.find(sc, "Power cable")
    assert not it.moving and part.modifiers[paths.MOD].node_group.name == paths.TREES[False]
    assert paths._STATE["steps"] == stepped + 1
    solves = paths._STATE["solves"]
    with Evaluations(part) as seen:
        per_frame(10)
        after = min(per_frame(), per_frame())
    assert seen.count == 0 and paths._STATE["solves"] == solves     # the hard facts: nothing is worked out again
    sc.frame_set(51)
    pay = part.evaluated_get(bpy.context.evaluated_depsgraph_get())[cable_looks.PAY]
    assert pay - 2.0 == pytest.approx(2.0 * 10.0 / 60.0, abs=1e-3)
    # … and the time, taken in turns with the cable's modifier off (other work on the machine moves both alike)
    mod, on, off = part.modifiers[paths.MOD], [], []
    for _ in range(3):
        on.append(per_frame(30))
        mod.show_viewport = False
        per_frame(2)
        off.append(per_frame(30))
        mod.show_viewport = True
        per_frame(2)
    print(f"    cost of a frame change (this machine, best of the runs): {before:.2f} ms before the cable was made, "
          f"{after:.2f} ms with it on its path; in turns: {min(on):.2f} ms with the cable drawn, {min(off):.2f} ms "
          f"with its modifier off ({min(on) - min(off):+.2f} ms)")
    assert min(on) - min(off) < 1.0
    # an animation in which the quadrant travels: a shape per frame – unless the cable is told to stay as drawn
    travel = next(j.name for j in sc.fresing.joints if j.kind == "SLIDE" and not j.follows and j.name != demo.CABLE
                  and any(o.get(build.PROP_NAME) == "QUADRANT GUTTER" or
                          any(k.get(build.PROP_NAME) == "QUADRANT GUTTER" for k in o.children_recursive)
                          for o in joints.moved_objects(sc, j)))
    lo, hi = joints.limits(joints.find(sc, travel))
    b2 = a.blocks.add()
    b2.kind, b2.joint, b2.start, b2.duration, b2.easing = "JOINT", travel, 0.0, 2.0, "LINEAR"
    b2.use_from, b2.to_dist = True, (0.3 if hi >= 0.3 else -0.3)
    t0 = time.perf_counter()
    r = animation.bake(sc, a)
    took = time.perf_counter() - t0
    it = paths.find(sc, "Power cable")
    print(f"    '{travel}' moved 0.3 m in the animation: moving {it.moving}, Build {took:.1f} s for {r['frames']} "
          f"frames, "
          f"{len(it.shapes.data.vertices)} points kept, warnings {r['warnings']}; a frame change: "
          f"{min(per_frame(), per_frame()):.2f} ms")
    assert it.moving and part.modifiers[paths.MOD].node_group.name == paths.TREES[True]
    it.still = True
    it = paths.find(sc, "Power cable")
    assert not it.moving and part.modifiers[paths.MOD].node_group.name == paths.TREES[False]
    per_frame(2)                                            # (the new tube is worked out once)
    with Evaluations(part) as seen:
        fixed = min(per_frame(), per_frame())
    assert seen.count == 0
    print(f"    … and with 'Stays as drawn': {fixed:.2f} ms")
    update()
    assert float(to_line(rings(part)[0], line).max()) < 0.0015
    animation.clear_keys(sc)
    assert not paths.find(sc, "Power cable").moving
    # and off again
    paths.remove(sc, 0)
    assert len(sc.fresing.joints) == n_joints and joints.find(sc, demo.CABLE) is not None
    assert {j.name: j.couple_ratio for j in sc.fresing.joints if j.follows == demo.CABLE} == followers
    assert part["fr_group_manual"] == "Demo: power cable" and paths.MOD not in part.modifiers
