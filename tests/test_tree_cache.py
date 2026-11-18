"""Task 0210: the part tree kept for a click's selection handler, and the picker's face tables built at its start."""

import os

import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import build, handlers, hover, logic  # noqa: E402

CRANE_A = os.path.join(os.path.dirname(__file__), "data", "test_crane_a.step")


@pytest.fixture(scope="module")
def scene(tmp_path_factory):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path_factory.mktemp("treecache"))
    assert bpy.ops.fresing.import_step(filepath=CRANE_A, quality="draft") == {"FINISHED"}
    bpy.context.view_layer.update()
    yield sc
    fresing_render.unregister()


def parts(sc):
    return [o for o in sc.objects if o.get(build.PROP_KIND) == "part"]


def test_tree_is_reused_while_nothing_changes(scene):
    a = logic.cached_tree(scene)
    bpy.context.view_layer.update()
    assert logic.cached_tree(scene) is a
    assert a.kids.keys() == logic.Tree(scene).kids.keys()


def test_dropped_by_a_new_object(scene):
    a = logic.cached_tree(scene)
    ob = bpy.data.objects.new("extra", None)
    scene.collection.objects.link(ob)
    assert logic.cached_tree(scene) is not a


def test_dropped_by_a_reparent(scene):
    p = parts(scene)
    a = logic.cached_tree(scene)
    moved = p[0]
    new_parent = next(o for o in p[1:] if o is not moved.parent and o is not moved)
    moved.parent = new_parent
    bpy.context.view_layer.update()
    b = logic.cached_tree(scene)
    assert b is not a
    assert moved in b.children(new_parent)


def test_dropped_by_a_transform(scene):
    a = logic.cached_tree(scene)
    p = parts(scene)[0]
    p.location.x += 0.001
    bpy.context.view_layer.update()
    assert logic.cached_tree(scene) is not a


def test_dropped_by_undo_and_load(scene):
    a = logic.cached_tree(scene)
    handlers._after_undo()
    b = logic.cached_tree(scene)
    assert b is not a
    handlers._before_load()
    assert logic.cached_tree(scene) is not b
    c = logic.cached_tree(scene)
    handlers._on_load()
    assert logic.cached_tree(scene) is not c


def test_dropped_when_a_part_gets_a_cad_parent_mark(scene):
    """joints.ride_on writes the CAD parent mark: the kept tree is dropped there too."""
    import inspect
    from fresing_render.blender import joints
    src = inspect.getsource(joints)
    k = src.index("ob[build.PROP_CAD_PARENT] = ob.parent")
    assert "drop_tree_cache" in src[k:k + 120]


def test_first_hover_equals_a_later_one(scene):
    from mathutils import Vector
    pin = next(o for o in parts(scene) if o.get(build.PROP_NAME) == "BOOM.PIN")
    n = Vector((0, 0, 1))
    origin, direction = pin.matrix_world @ Vector((0, -0.085, 0.02)) + n * 0.002, -n
    hover._MESH.clear()
    hover._FACE.clear()
    dg = bpy.context.evaluated_depsgraph_get()
    first = hover.look(scene, dg, origin, direction)
    second = hover.look(scene, dg, origin, direction)
    assert (first.part, first.face, first.kind, first.text) == (second.part, second.face, second.kind, second.text)


def test_prewarm_reads_the_tables_before_the_first_hover(scene):
    hover._MESH.clear()
    hover._S["op"] = object()
    try:
        hover._prewarm_start(scene)
        step = hover._S["warm_step"]
        for _ in range(1000):
            if step() is None:
                break
        n_meshes = len({o.data.session_uid for o in parts(scene)})
        assert len(hover._MESH) == n_meshes
    finally:
        hover._S["op"] = None
        hover._S["warm"] = None
