"""Hover highlight while picking an axis (task 0088): what lights up under the mouse is what the click then uses."""

import os
import time

import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import build, faces, hover, joints  # noqa: E402

HERE = os.path.dirname(__file__)
CRANE_A = os.path.join(HERE, "data", "test_crane_a.step")


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture(scope="module")
def scene(tmp_path_factory):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path_factory.mktemp("hover"))
    assert bpy.ops.fresing.import_step(filepath=CRANE_A, quality="draft") == {"FINISHED"}
    bpy.context.view_layer.update()
    return sc


def ob(sc, name, n=0):
    hits = sorted((o for o in sc.objects if o.get(build.PROP_NAME) == name), key=lambda o: o.get(build.PROP_UID))
    return hits[n]


def ray_at(point, normal, gap=0.002):
    """A ray that starts just outside a surface and looks at it."""
    n = Vector(normal).normalized()
    return Vector(point) + n * gap, -n


def look(sc, origin, direction, refuse=None):
    return hover.look(sc, bpy.context.evaluated_depsgraph_get(), origin, direction, refuse)


def click(sc, origin, direction):
    """What the pickers' click does with the same ray: part, polygon, axis."""
    part, index, loc, normal = hover.cast(sc, bpy.context.evaluated_depsgraph_get(), origin, direction)
    if index < 0:
        return None
    o, d, _desc = joints.axis_from_hit(part, index, loc, normal)
    return part, index, o, d


def same_as_click(sc, h, origin, direction):
    c = click(sc, origin, direction)
    assert c is not None
    part, index, o, d = c
    assert h.part == part.name
    assert h.face == faces.face_of_polygon(part.data, index)
    assert h.tris[0] <= index < h.tris[1]
    assert (h.origin - o).length < 1e-9 and (h.direction - d).length < 1e-9


def test_shaft_lights_up_with_its_axis(scene):
    pin = ob(scene, "BOOM.PIN")
    origin, direction = ray_at(pin.matrix_world @ Vector((0, -0.085, 0.02)), (0, 0, 1))
    h = look(scene, origin, direction)
    assert h.part == pin.name and h.kind == "shaft" and abs(h.diameter - 40) < 0.05, h
    assert h.tris == (0, 52), h.tris                       # the pin's whole round face (its CAD face block)
    assert abs(abs(h.direction.y) - 1) < 1e-6 and abs(h.origin.x - 0.1) < 1e-6 and abs(h.origin.z - 0.4) < 1e-6
    assert "Shaft Ø40 mm – axis through its centre" in h.text, h.text
    # the line reaches past the pin on both ends
    ys = sorted(p.y for p in h.ends)
    bb = [pin.matrix_world @ Vector(c) for c in pin.bound_box]
    assert ys[0] < min(c.y for c in bb) and ys[-1] > max(c.y for c in bb)
    same_as_click(scene, h, origin, direction)


def test_hole_lights_up_with_its_axis(scene):
    pin = ob(scene, "BOOM.PIN")
    ped = ob(scene, "PEDESTAL")
    saved = pin.matrix_world.copy()
    moved = [pin, ob(scene, "BOOM")]
    keep = [o.location.copy() for o in moved]
    for o in moved:
        o.location.z += 5.0                                 # the pin (and the boom on it) out of the hole
    bpy.context.view_layer.update()
    try:
        bb = [ped.matrix_world @ Vector(c) for c in ped.bound_box]
        y = min(c.y for c in bb) + 0.005                    # in the front lug (the boom sits between the two)
        origin, direction = Vector((0.1, y, 0.41)), Vector((0, 0, 1))      # from inside the bore, up at its wall
        h = look(scene, origin, direction)
        assert h.part == ped.name and h.kind == "hole", h
        assert h.text.endswith("Hole Ø40.4 mm – axis through its centre"), h.text
        assert h.tris in ((44, 96), (216, 268)), h.tris
        same_as_click(scene, h, origin, direction)
        fill, outline = hover.face_shape(ped.data, h.face)
        assert len(fill) == 3 * (h.tris[1] - h.tris[0]) and len(outline) % 2 == 0 and len(outline) > 0
    finally:
        for o, loc in zip(moved, keep):
            o.location = loc
        bpy.context.view_layer.update()
    assert (pin.matrix_world.translation - saved.translation).length < 1e-9


def test_flat_face_gives_an_arrow(scene):
    base = ob(scene, "BASE")
    bb = [base.matrix_world @ Vector(c) for c in base.bound_box]
    top = max(c.z for c in bb)
    origin, direction = ray_at((0.3, 0.45, top), (0, 0, 1))
    h = look(scene, origin, direction)
    assert h.part == base.name and h.kind == "flat", h
    assert (h.direction - Vector((0, 0, 1))).length < 1e-6
    assert h.text == "BASE: Flat face – axis at right angles to it"
    assert (h.ends[0] - h.origin).length < 1e-9 and h.ends[1].z > h.origin.z + 0.02     # the arrow points up
    same_as_click(scene, h, origin, direction)


def test_floor_and_empty_space_are_not_parts(scene):
    h = look(scene, Vector((3.0, 3.0, 1.0)), Vector((0, 0, -1)))
    assert not h.part and h.text.startswith("Not a part") and not h.ends, h
    assert click(scene, Vector((3.0, 3.0, 1.0)), Vector((0, 0, -1))) is None
    h = look(scene, Vector((0, 0, 10)), Vector((0, 0, 1)))
    assert not h.part and h.text == "Not a part (empty space)"


def test_copies_of_one_part_each_in_their_own_place(scene):
    w0, w1 = ob(scene, "WHEEL", 0), ob(scene, "WHEEL", 1)
    assert w0.data is w1.data
    hs = []
    for w in (w0, w1):
        c = w.matrix_world.translation
        origin, direction = ray_at(c + Vector((0, 0, 0.025)), (0, 0, 1))
        h = look(scene, origin, direction)
        assert h.part == w.name, h
        same_as_click(scene, h, origin, direction)
        hs.append(h)
    assert abs((hs[1].origin - hs[0].origin).x - (w1.matrix_world.translation - w0.matrix_world.translation).x) < 1e-6
    assert hs[0].face == hs[1].face


def test_refused_spot_says_why(scene):
    pin = ob(scene, "BOOM.PIN")
    origin, direction = ray_at(pin.matrix_world @ Vector((0, -0.085, 0.02)), (0, 0, 1))
    h = look(scene, origin, direction, refuse=lambda part, o, d: "not on the arm")
    assert h.refused == "not on the arm" and h.text == "BOOM.PIN: not on the arm"


def test_time_per_move_on_the_crane(scene):
    """The work of one mouse move: well under a frame on the test crane (numbers for the report)."""
    pin = ob(scene, "BOOM.PIN")
    origin, direction = ray_at(pin.matrix_world @ Vector((0, -0.085, 0.02)), (0, 0, 1))
    look(scene, origin, direction)
    t0 = time.perf_counter()
    for _ in range(50):
        look(scene, origin, direction)
    ms = (time.perf_counter() - t0) * 1000 / 50
    print(f"hover look on the test crane: {ms:.2f} ms per move")
    assert ms < 15


def test_overlay_leaves_the_project_alone(scene, tmp_path):
    """Only an overlay: nothing in bpy.data changes, the stored face list is not written, a render is the same."""
    def state():
        return (len(bpy.data.objects), len(bpy.data.meshes), len(bpy.data.materials), len(bpy.data.images),
                sorted((m.name, sorted(m.keys())) for m in bpy.data.meshes))

    sc = scene
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 1
    sc.cycles.use_denoising = False
    sc.render.resolution_x = sc.render.resolution_y = 24
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"

    def render(name):
        sc.render.filepath = str(tmp_path / name)
        bpy.ops.render.render(write_still=True)
        img = bpy.data.images.load(str(tmp_path / name) + ".png")
        px = np.array(img.pixels[:])
        bpy.data.images.remove(img)
        return px

    plain = render("plain")
    before = state()
    hover.start(bpy.context, object(), "Click a hole")
    pin = ob(sc, "BOOM.PIN")
    origin, direction = ray_at(pin.matrix_world @ Vector((0, -0.085, 0.02)), (0, 0, 1))
    hover._S["hover"] = look(sc, origin, direction)
    assert hover.current() is not None and hover.active()
    assert state() == before
    assert np.array_equal(render("hover"), plain)
    hover.end(None)
    assert hover.current() is None and not hover._S["handles"]


def test_highlight_gone_after_end_undo_and_file_load(scene, tmp_path):
    op = object()
    hover.start(bpy.context, op, "Click a hole")
    pin = ob(scene, "BOOM.PIN")
    origin, direction = ray_at(pin.matrix_world @ Vector((0, -0.085, 0.02)), (0, 0, 1))
    hover._S["hover"] = look(scene, origin, direction)
    hover.end(object())                                     # another pick's end does not end this one
    assert hover.current() is not None
    hover._after_undo()                                     # undo: forgotten, worked out again at the next move
    assert hover.current() is None and hover.active()
    hover.end(op)
    assert not hover.active()
    # opening another file ends a pick that is still running
    path = str(tmp_path / "other.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path, copy=True)
    hover.start(bpy.context, op, "Click a hole")
    hover._S["hover"] = hover.Hover()
    bpy.ops.wm.open_mainfile(filepath=path)
    assert not hover.active() and hover.current() is None


def test_preference_on_by_default():
    assert hover.enabled()
