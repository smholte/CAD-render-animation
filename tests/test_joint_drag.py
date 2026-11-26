"""Task 0326: dragging a joint on a big model. ``joints.set_value`` tells Blender only what changed (the motion's
transform and data, as Blender's own slider does): a bare ``update_tag()`` also marked the shading as changed, and Blender
then went over every object again – 82 ms per drag step on the 11,228-part stress model instead of 15 ms. Followers,
stacked joints and the parts still move as before; the app's own scene-update handlers skip their work when it is not
needed (the click handler with no kept part tree, vessel motion while it is off).
"""

import math
import os

import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

HERE = os.path.dirname(__file__)
CRANE_A = os.path.join(HERE, "data", "test_crane_a.step")
X, Y, Z = Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))
TOL = 1e-5

import fresing_render  # noqa: E402
from fresing_render.blender import build, handlers, joints, logic, vessel_motion  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture()
def scene(tmp_path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path)
    assert bpy.ops.fresing.import_step(filepath=CRANE_A, quality="draft") == {"FINISHED"}
    return sc


def ob(sc, name, n=0):
    hits = sorted((o for o in sc.objects if o.get(build.PROP_NAME) == name), key=lambda o: o.get(build.PROP_UID))
    return hits[n]


def update():
    bpy.context.view_layer.update()


def pos(o):
    return o.matrix_world.translation.copy()


def trolley_and_wheel(sc):
    tr = ob(sc, "TROLLEY.ASM")
    joints.create(sc, "SLIDE", [tr], pos(tr), X, name="Trolley")
    w = ob(sc, "WHEEL", 0)
    joints.create(sc, "ROTATE", [w], pos(w), Y, name="Wheel")
    joints.set_follows(sc, joints.find(sc, "Wheel"), "Trolley", ratio=-0.5)   # ° per mm: a rolling wheel
    update()
    return tr, w


class Updates:
    """What Blender says it updated in each scene update while the block runs."""

    def __enter__(self):
        self.seen = []
        bpy.app.handlers.depsgraph_update_post.append(self._h)
        return self

    def _h(self, _scene, dg):
        self.seen.append({u.id.name: (u.is_updated_transform, u.is_updated_geometry, u.is_updated_shading)
                          for u in dg.updates if isinstance(u.id, bpy.types.Object)})

    def __exit__(self, *_exc):
        bpy.app.handlers.depsgraph_update_post.remove(self._h)
        return False


def test_a_drag_step_tags_the_motion_not_its_shading(scene):
    tr, _w = trolley_and_wheel(scene)
    j = joints.find(scene, "Trolley")
    with Updates() as u:
        joints.set_value(j, 0.05)
        update()
    assert u.seen, "the scene update reported nothing"
    flags = u.seen[-1].get(j.motion.name)
    assert flags is not None, "the joint's motion was not updated"
    transform, _geometry, shading = flags
    assert transform
    assert not shading, "a bare update_tag(): Blender goes over every object again (82 ms a step on 11,000 parts)"
    assert joints.MOVED == {"OBJECT", "DATA"}


def test_parts_and_followers_move_with_the_narrow_tag(scene):
    tr, w = trolley_and_wheel(scene)
    for i in range(1500):                         # bystanders, as in a big model
        e = bpy.data.objects.new(f"bystander {i}", None)
        scene.collection.objects.link(e)
    p0, wp0 = pos(tr), pos(w)
    j = joints.find(scene, "Trolley")
    k = joints.find(scene, "Wheel")
    for d in (0.1, -0.2, 0.3):                    # like a drag: one value after the other, an update after each
        joints.set_value(j, d)
        update()
        assert (pos(tr) - (p0 + X * d)).length < TOL
        assert (pos(w) - (wp0 + X * d)).length < TOL, "the wheel rides on the trolley"
        want = joints.get_value(k)
        assert abs(want - math.radians(-0.5) * d * 1000.0) < 1e-4
        rot = (Matrix.Translation(-pos(w)) @ w.matrix_world).to_3x3()
        assert all(abs(rot[r][c] - Matrix.Rotation(want, 3, Y)[r][c]) < TOL for r in range(3) for c in range(3))


def test_the_click_handler_looks_at_updates_only_when_a_tree_is_kept(scene):
    class Graph:
        looked = 0

        def id_type_updated(self, _t):
            Graph.looked += 1
            return True

        @property
        def updates(self):
            Graph.looked += 1
            return []

    logic.drop_tree_cache()
    handlers._on_depsgraph(scene, Graph())
    assert Graph.looked == 0, "nothing kept: a drag step must not walk the updated objects"
    logic.cached_tree(scene)
    assert logic.tree_kept()
    handlers._on_depsgraph(scene, Graph())
    assert Graph.looked > 0
    # a moved part still drops the kept tree (a re-parent shows as a transform update)
    tr, _w = trolley_and_wheel(scene)
    logic.cached_tree(scene)
    tr.location.x += 0.01
    update()
    assert not logic.tree_kept()


def test_vessel_motion_looks_no_rig_up_while_it_is_off(scene, monkeypatch):
    calls = []
    monkeypatch.setattr(vessel_motion, "rig", lambda role="pivot": calls.append(role))
    assert not vessel_motion.effective(scene)
    vessel_motion._on_depsgraph(scene)
    assert calls == []
