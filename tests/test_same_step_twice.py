"""Task 0056 (bug hunt 0045 row 11): the same STEP imported twice gets its own part IDs.

Two cranes from the same file act as two cranes: hiding, visibility sets, poses, show/hide steps and model updates
of one never touch the other. The first copy, and every project with one copy per model, keep their IDs; projects
made before with two copies are repaired when they are opened.
"""
import os

import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from mathutils import Matrix  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import animation, build, handlers, joints, logic, states  # noqa: E402

HERE = os.path.join(os.path.dirname(__file__), "data")
CRANE_A = os.path.join(HERE, "test_crane_a.step")
CRANE_B = os.path.join(HERE, "test_crane_b.step")
MACHINE = os.path.join(HERE, "test_machine.step")


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def load(tmp_path, *paths):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path)
    for p in paths:
        assert bpy.ops.fresing.import_step(filepath=p, quality="draft") == {"FINISHED"}
    return sc


def roots(sc):
    """The model roots, first copy first (by scope: '' before '~2/')."""
    return sorted(build.model_roots(sc), key=lambda r: (len(build.uid_scope(r)), build.uid_scope(r)))


def part(sc, name, root):
    memo = {}
    hits = [o for o in sc.objects if o.get(build.PROP_NAME) == name and build.model_root_of(o, memo) == root]
    assert len(hits) == 1, (name, root.name, len(hits))
    return hits[0]


def update_model(sc, path, root):
    res = bpy.ops.fresing.import_step(filepath=path, quality="draft", update_root=root.name)
    bpy.context.view_layer.update()
    return res


def uids_of(sc, root):
    memo = {}
    return sorted(o.get(build.PROP_UID) for o in sc.objects
                  if o.get(build.PROP_KIND) in build.MODEL_KINDS and build.model_root_of(o, memo) == root)


# ---------------------------------------------------------------------------
# IDs
# ---------------------------------------------------------------------------

def test_second_copy_gets_its_own_ids_first_keeps_its_own(tmp_path):
    sc = load(tmp_path, CRANE_A, CRANE_A)
    one, two = roots(sc)
    assert build.uid_scope(one) == "" and build.uid_scope(two) == "~2/"
    assert one.get(build.PROP_UID) == "TEST.CRANE#1"
    assert two.get(build.PROP_UID) == "~2/TEST.CRANE#1"
    assert not two.get(build.PROP_UID).startswith("@")      # "@<name>" means "another model" in joint specs
    assert part(sc, "COVER", one).get(build.PROP_UID) == "TEST.CRANE#1/COVER#1"
    assert part(sc, "COVER", two).get(build.PROP_UID) == "~2/TEST.CRANE#1/COVER#1"
    every = [o.get(build.PROP_UID) for o in sc.objects if o.get(build.PROP_KIND) in build.MODEL_KINDS]
    assert len(every) == len(set(every))
    assert [u for u in uids_of(sc, two)] == sorted("~2/" + u for u in uids_of(sc, one))
    # rules see the path in the CAD file: the same for both copies
    assert build.path_of(part(sc, "COVER", two)) == build.path_of(part(sc, "COVER", one)) == "TEST.CRANE#1/COVER#1"
    assert part(sc, "COVER", two).get("fr_group") == part(sc, "COVER", one).get("fr_group")


def test_third_copy_and_other_models(tmp_path):
    sc = load(tmp_path, CRANE_A, MACHINE, CRANE_A, CRANE_A)
    scopes = sorted(build.uid_scope(r) for r in build.model_roots(sc))
    assert scopes == ["", "", "~2/", "~3/"]       # the machine and the first crane: none
    every = [o.get(build.PROP_UID) for o in sc.objects if o.get(build.PROP_KIND) in build.MODEL_KINDS]
    assert len(every) == len(set(every))


def test_scope_helpers():
    assert build.scoped("A#1/B#1", "") == "A#1/B#1"
    assert build.scoped("A#1/B#1", "~2/") == "~2/A#1/B#1"
    assert build.unscoped("~2/A#1/B#1") == "A#1/B#1"
    assert build.unscoped("~3/~2/A#1") == "A#1"
    assert build.unscoped("A#1/~2/B#1") == "A#1/~2/B#1"
    assert build.free_scope(["A#1", "A#1/B#1"], {"X#1"}) == ""
    assert build.free_scope(["A#1", "A#1/B#1"], {"A#1"}) == "~2/"
    assert build.free_scope(["A#1"], {"A#1", "~2/A#1"}) == "~3/"


# ---------------------------------------------------------------------------
# the row's proof: hiding, visibility sets, poses, show/hide steps
# ---------------------------------------------------------------------------

def test_visibility_set_hides_the_second_cover_not_the_first(tmp_path):
    sc = load(tmp_path, CRANE_A, CRANE_A)
    one, two = roots(sc)
    c1, c2 = part(sc, "COVER", one), part(sc, "COVER", two)
    logic.set_hidden(c2, True)
    states.save_visibility(sc, "Second cover off")
    states.show_all(sc)
    assert not logic.is_hidden(c1) and not logic.is_hidden(c2)
    assert states.apply_visibility(sc, "Second cover off")
    assert logic.is_hidden(c2), "the second cover must be hidden"
    assert not logic.is_hidden(c1), "the first cover must stay shown"


def test_pose_moves_the_second_copy_only(tmp_path):
    sc = load(tmp_path, CRANE_A, CRANE_A)
    one, two = roots(sc)
    b1, b2 = part(sc, "TROLLEY.ASM", one), part(sc, "TROLLEY.ASM", two)
    b2.matrix_basis = build.rest_basis(b2) @ Matrix.Translation((0.2, 0, 0))
    states.save_pose(sc, "Moved")
    states.reset_pose(sc)
    _values, deltas = states.pose_targets(sc, sc.fresing.poses["Moved"])
    assert list(deltas) == [b2.name]
    states.apply_pose(sc, "Moved")
    assert (b2.matrix_basis.translation - build.rest_basis(b2).translation).length == pytest.approx(0.2)
    assert (b1.matrix_basis.translation - build.rest_basis(b1).translation).length < 1e-9


def test_hide_step_targets_the_second_copy(tmp_path):
    sc = load(tmp_path, CRANE_A, CRANE_A)
    one, two = roots(sc)
    c1, c2 = part(sc, "COVER", one), part(sc, "COVER", two)
    a = sc.fresing.animations.add()
    a.name, a.fps, a.tail = "Hide", "25", 0.0
    b = a.blocks.add()
    b.kind, b.start, b.target_uid, b.target_name = "HIDE", 1.0, c2.get(build.PROP_UID), "COVER"
    c = a.blocks.add()                    # something that lasts 2 s
    c.kind, c.camera_mode, c.start, c.duration = "CAMERA", "ORBIT", 0.0, 2.0
    info = animation.bake(sc, a)
    assert not info["warnings"], info
    sc.frame_set(sc.frame_end)
    assert c2.hide_render and not c1.hide_render
    animation.clear_keys(sc)


# ---------------------------------------------------------------------------
# model updates
# ---------------------------------------------------------------------------

def test_updating_one_copy_leaves_the_other_alone(tmp_path):
    sc = load(tmp_path, CRANE_A, CRANE_A)
    one, two = roots(sc)
    c1 = part(sc, "COVER", one)
    logic.set_hidden(c1, True)
    states.save_visibility(sc, "First cover off")
    logic.set_hidden(c1, False)
    logic.set_hidden(part(sc, "COVER", two), True)
    states.save_visibility(sc, "Second cover off")
    ids_one = uids_of(sc, one)
    one_name = one.name
    assert update_model(sc, CRANE_B, two) == {"FINISHED"}
    one = bpy.data.objects[one_name]
    two = next(r for r in build.model_roots(sc) if r is not one)
    assert build.uid_scope(two) == "~2/", "the updated copy keeps its own IDs"
    assert uids_of(sc, one) == ids_one, "the other copy is untouched"
    assert part(sc, "BOOM.LAMP", two).get(build.PROP_UID).startswith("~2/")   # new in revision B
    assert not [o for o in sc.objects if o.get(build.PROP_NAME) == "BOOM.LAMP"
                and build.model_root_of(o) == one]
    # each set still hides its own copy's cover
    states.apply_visibility(sc, "First cover off")
    assert logic.is_hidden(part(sc, "COVER", one)) and not logic.is_hidden(part(sc, "COVER", two))
    states.apply_visibility(sc, "Second cover off")
    assert logic.is_hidden(part(sc, "COVER", two)) and not logic.is_hidden(part(sc, "COVER", one))
    # and the first copy can be updated too, still apart from the second
    ids_two = uids_of(sc, two)
    two_name = two.name
    assert update_model(sc, CRANE_B, one) == {"FINISHED"}
    two = bpy.data.objects[two_name]
    one = next(r for r in build.model_roots(sc) if r is not two)
    assert build.uid_scope(one) == "" and uids_of(sc, two) == ids_two
    states.apply_visibility(sc, "Second cover off")
    assert logic.is_hidden(part(sc, "COVER", two)) and not logic.is_hidden(part(sc, "COVER", one))


def test_joint_on_the_second_copy_survives_its_update(tmp_path):
    sc = load(tmp_path, CRANE_A, CRANE_A)
    one, two = roots(sc)
    boom2 = part(sc, "BOOM.ASM", two)
    j = joints.create(sc, "ROTATE", [boom2], boom2.matrix_world.translation, (0, 1, 0), name="Luff 2")
    assert update_model(sc, CRANE_B, two) == {"FINISHED"}
    two = next(r for r in build.model_roots(sc) if build.uid_scope(r) == "~2/")
    j = joints.find(sc, "Luff 2")
    assert j is not None and joints.is_valid(j)
    assert [m.name for m in joints.members(j)] == [part(sc, "BOOM.ASM", two).name]


def test_one_copy_update_keeps_plain_ids(tmp_path):
    sc = load(tmp_path, CRANE_A)
    (root,) = roots(sc)
    before = uids_of(sc, root)
    assert all(not u.startswith("~") for u in before)
    assert update_model(sc, CRANE_B, root) == {"FINISHED"}
    (root,) = roots(sc)
    after = uids_of(sc, root)
    assert build.uid_scope(root) == "" and all(not u.startswith("~") for u in after)
    assert "TEST.CRANE#1/COVER#1" in after and "TEST.CRANE#1" in after


# ---------------------------------------------------------------------------
# projects made before 0056
# ---------------------------------------------------------------------------

def _make_old(sc):
    """Make the project look like one made before 0056: both copies with the same IDs, no scope."""
    for ob in sc.objects:
        if ob.get(build.PROP_UID):
            ob[build.PROP_UID] = build.unscoped(ob[build.PROP_UID])
        if build.PROP_UID_SCOPE in ob:
            del ob[build.PROP_UID_SCOPE]


def test_old_project_with_two_copies_is_repaired_on_open(tmp_path):
    sc = load(tmp_path, CRANE_A, CRANE_A)
    _make_old(sc)
    first_cover = states.by_uid(sc)["TEST.CRANE#1/COVER#1"]      # the copy old lookups landed on
    first_name = first_cover.name
    logic.set_hidden(first_cover, True)
    states.save_visibility(sc, "Old set")
    states.show_all(sc)
    path = str(tmp_path / "old.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    every = [o.get(build.PROP_UID) for o in sc.objects if o.get(build.PROP_KIND) in build.MODEL_KINDS]
    assert len(every) == len(set(every)), "opened: every part has its own ID"
    one, two = roots(sc)
    assert part(sc, "COVER", one).name == first_name, "the copy old lookups found keeps its IDs"
    assert build.uid_scope(two) == "~2/"
    states.apply_visibility(sc, "Old set")                        # still hides what it hid before
    assert logic.is_hidden(part(sc, "COVER", one)) and not logic.is_hidden(part(sc, "COVER", two))
    assert build.repair_uids(sc) == 0                             # once only


def test_repair_leaves_unique_ids_alone(tmp_path):
    sc = load(tmp_path, CRANE_A, MACHINE)
    before = {o.name: o.get(build.PROP_UID) for o in sc.objects}
    assert build.repair_uids(sc) == 0
    for _step, fn in handlers._upgrade_steps():
        fn(sc)
    assert {o.name: o.get(build.PROP_UID) for o in sc.objects} == before
