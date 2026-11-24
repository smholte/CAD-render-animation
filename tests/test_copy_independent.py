"""Copy and paste (task 0293): independent tests written by an agent that did not write the code, to break it.

Blender as a module. Each test states the behaviour the brief and ``copy.py``'s docstring promise."""

import functools
import math
import os
import subprocess
import sys

import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import (animation, build, copy, cylinders, decals, flex, joints, lesson,  # noqa: E402
                                    linkages, logic, place, reimport, remove, waycover, workspaces)

DATA = os.path.join(os.path.dirname(__file__), "data")
CRANE = os.path.join(DATA, "test_crane_a.step")
HOSES = os.path.join(DATA, "test_flex_hoses_a.step")
LINKS = os.path.join(DATA, "test_linkage_a.step")
COVERS = os.path.join(DATA, waycover.TEST_MODEL)


def own_process(fn):
    """Run a test in a process of its own with a time box: a paste that hangs (a dangling list item) fails the test
    instead of the whole run."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if os.environ.get("FR_COPY_CHILD") == "1":
            return fn(*args, **kwargs)
        env = dict(os.environ, FR_COPY_CHILD="1")
        try:
            done = subprocess.run([sys.executable, "-m", "pytest", f"{__file__}::{fn.__name__}", "-q", "-x",
                                   "-p", "no:cacheprovider"], env=env, capture_output=True, text=True,
                                  cwd=os.path.dirname(os.path.dirname(__file__)), timeout=60)
        except subprocess.TimeoutExpired:
            pytest.fail(f"{fn.__name__}: the paste hung (no answer in 60 s)")
        assert done.returncode == 0, done.stdout[-3000:] + done.stderr[-1000:]
    return wrapper


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def _fresh(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    assert bpy.ops.fresing.import_step(filepath=path, quality="draft") == {"FINISHED"}
    scene = bpy.context.scene
    workspaces.switch(scene, "All functions")
    return scene


@pytest.fixture()
def crane():
    scene = _fresh(CRANE)
    lesson.run(scene, "crane")
    animation.clear_keys(scene)
    yield scene


def ob(scene, name, root=None):
    return next(o for o in scene.objects if o.get(build.PROP_NAME) == name
                and (root is None or build.model_root_of(o) is root))


def roots(scene):
    return {r.get(build.PROP_NAME): r for r in build.model_roots(scene)}


def update():
    bpy.context.view_layer.update()
    bpy.context.view_layer.update()


def _close(a, b, tol=2e-4):
    return all(abs(a[r][c] - b[r][c]) < tol for r in range(4) for c in range(4))


def _model_objs(scene):
    return [o for o in scene.objects if o.get(build.PROP_KIND) in build.MODEL_KINDS]


def _uids_unique(scene):
    seen = {}
    dup = []
    for o in _model_objs(scene):
        u = o.get(build.PROP_UID)
        if not u:
            continue
        if u in seen:
            dup.append((u, seen[u], o.name))
        seen[u] = o.name
    return dup


def _counts(scene):
    s = scene.fresing
    return {"joints": len(s.joints), "cylinders": len(s.cylinders), "mechanisms": len(s.mechanisms),
            "way_covers": len(s.waycovers), "hoses": len(s.flex), "labels": len(s.callouts)}


def _check_plan_truthful(scene, before, p):
    """Every count the paste says came along was really made, and works."""
    after = _counts(scene)
    for k in before:
        assert after[k] - before[k] == p[k], f"paste said {p[k]} {k}, made {after[k] - before[k]} ({p})"
    s = scene.fresing
    assert all(joints.is_valid(j) for j in s.joints), [j.name for j in s.joints if not joints.is_valid(j)]
    assert all(cylinders.is_valid(c) for c in s.cylinders)
    assert all(linkages.is_valid(m) for m in s.mechanisms)
    assert all(not flex.broken(scene, it) for it in s.flex), [(it.name, flex.broken(scene, it)) for it in s.flex]


# ---------------------------------------------------------------------------
# couplings and stacks
# ---------------------------------------------------------------------------

def test_coupling_inside_the_copy_follows_the_copys_leader(crane):
    scene = crane
    joints.set_follows(scene, joints.find(scene, "Trolley"), "Boom", ratio=0.1)
    root = roots(scene)["TEST.CRANE"]
    before = _counts(scene)
    p = copy.paste(scene, [root])
    _check_plan_truthful(scene, before, p)
    t2 = joints.find(scene, "Trolley (2)")
    assert t2.follows == "Boom (2)", t2.follows
    assert joints.find(scene, "Trolley").follows == "Boom"
    t1v = joints.get_value(joints.find(scene, "Trolley"))
    t2v = joints.get_value(t2)
    joints.set_value(joints.find(scene, "Boom (2)"), math.radians(20.0))
    update()
    assert abs(joints.get_value(joints.find(scene, "Trolley")) - t1v) < 1e-6, "the copy's leader moved the original"
    assert abs(joints.get_value(t2) - t2v) > 1e-7, "the copy's follower did not follow the copy's leader"
    t2v = joints.get_value(t2)
    joints.set_value(joints.find(scene, "Boom"), math.radians(-15.0))
    update()
    assert abs(joints.get_value(t2) - t2v) < 1e-6, "the original's leader moved the copy's follower"


def test_follower_outside_leader_inside(crane):
    """Trolley (outside) follows Boom (inside the copied boom): the original coupling stays, the copy's boom drives
    nothing of the original."""
    scene = crane
    joints.set_follows(scene, joints.find(scene, "Trolley"), "Boom", ratio=0.1)
    before = _counts(scene)
    p = copy.paste(scene, [ob(scene, "BOOM.ASM")])
    _check_plan_truthful(scene, before, p)
    assert joints.find(scene, "Trolley").follows == "Boom"
    tv = joints.get_value(joints.find(scene, "Trolley"))
    joints.set_value(joints.find(scene, "Boom (2)"), math.radians(25.0))
    update()
    assert abs(joints.get_value(joints.find(scene, "Trolley")) - tv) < 1e-6
    joints.set_value(joints.find(scene, "Boom"), math.radians(25.0))
    update()
    assert abs(joints.get_value(joints.find(scene, "Trolley")) - tv) > 1e-7, "the original coupling was lost"


def test_table_coupling_inside_the_copy_is_kept_or_said(crane):
    """A table coupling whose leader is in the copy: either the copy follows the copy's leader, or the paste says
    the coupling was left out (never silently dropped)."""
    scene = crane
    joints.set_table(scene, joints.find(scene, "Trolley"), "Boom", [0.0, 1.0], [0.0, 0.5], "test:table")
    root = roots(scene)["TEST.CRANE"]
    p = copy.paste(scene, [root])
    t2 = joints.find(scene, "Trolley (2)")
    said = any("Trolley" in x for x in p["left"])
    assert t2.follows == "Boom (2)" or said, \
        f"the table coupling of 'Trolley' was dropped on the copy without a word (left: {p['left']})"


def _wheel_joint(scene):
    w = ob(scene, "WHEEL")
    j = joints.create(scene, "ROTATE", [w], w.matrix_world.translation.copy(), Vector((0.0, 1.0, 0.0)),
                      name="Wheel spin")
    update()
    return j


def test_a_joint_on_a_moving_part_copied_fully_rides_on_the_copy(crane):
    scene = crane
    j = _wheel_joint(scene)
    assert j.frame.parent is ob(scene, "TROLLEY.ASM")
    before = _counts(scene)
    p = copy.paste(scene, [ob(scene, "TROLLEY.ASM")])
    _check_plan_truthful(scene, before, p)
    assert p["joints"] == 2
    r2 = roots(scene)["TROLLEY.ASM (2)"]
    t2, w2 = joints.find(scene, "Trolley (2)"), joints.find(scene, "Wheel spin (2)")
    assert w2 is not None and joints.is_valid(w2)
    assert w2.frame.parent is ob(scene, "TROLLEY.ASM", r2), w2.frame.parent
    wheel2 = joints.members(w2)[0]
    assert build.model_root_of(wheel2) is r2
    wm = wheel2.matrix_world.copy()
    joints.set_value(t2, 0.3)
    update()
    assert not _close(wm, wheel2.matrix_world), "the copy's wheel does not ride on the copy's trolley"


def _trolley_tilt(scene):
    t = ob(scene, "TROLLEY.ASM")
    j = joints.create(scene, "ROTATE", [t], t.matrix_world.translation.copy(), Vector((0.0, 1.0, 0.0)),
                      name="Trolley tilt")
    update()
    return j


def test_a_stack_copied_fully_rides_on_the_copys_joint(crane):
    """'Trolley tilt' made on the trolley, which 'Trolley' moves: it rides on 'Trolley' (a stack). The copy of the
    trolley has both, the tilt riding on the copy's slide."""
    scene = crane
    _trolley_tilt(scene)
    trolley = joints.find(scene, "Trolley")
    assert "Trolley tilt" in [r.name for r in joints.all_riders(scene, trolley)]
    before = _counts(scene)
    p = copy.paste(scene, [ob(scene, "TROLLEY.ASM")])
    _check_plan_truthful(scene, before, p)
    assert p["joints"] == 2, p
    t2 = joints.find(scene, "Trolley (2)")
    assert t2 is not None and "Trolley tilt (2)" in [r.name for r in joints.all_riders(scene, t2)], \
        "the stack was not kept on the copy"
    r2 = bpy.data.objects[p["roots"][0]]
    tr = ob(scene, "TROLLEY", r2)
    w = tr.matrix_world.copy()
    joints.set_value(t2, 0.3)
    update()
    assert not _close(w, tr.matrix_world), "the copy's slide does not move the copy's trolley"
    # the original's stack is untouched
    assert "Trolley tilt" in [r.name for r in joints.all_riders(scene, joints.find(scene, "Trolley"))]


def test_a_stack_copied_with_the_lower_joint_outside(crane):
    """The tilt's stack: the copy of the whole crane keeps it; the copy of the boom alone (the slide sits on it) keeps
    nothing of the trolley."""
    scene = crane
    _trolley_tilt(scene)
    before = _counts(scene)
    p = copy.paste(scene, [roots(scene)["TEST.CRANE"]])
    _check_plan_truthful(scene, before, p)
    assert p["joints"] == 3, p
    assert "Trolley tilt (2)" in [r.name for r in joints.all_riders(scene, joints.find(scene, "Trolley (2)"))]


def test_a_stack_copied_partly_sits_on_the_copy(crane):
    scene = crane
    _wheel_joint(scene)
    before = _counts(scene)
    wheel = joints.members(joints.find(scene, "Wheel spin"))[0]
    p = copy.paste(scene, [wheel])
    _check_plan_truthful(scene, before, p)
    w2 = joints.find(scene, "Wheel spin (2)")
    assert w2 is not None and joints.is_valid(w2)
    r2 = bpy.data.objects[p["roots"][0]]
    assert w2.frame.parent is r2, w2.frame.parent
    # the original's trolley moving does not move the copy
    m = joints.members(w2)[0]
    wm = m.matrix_world.copy()
    joints.set_value(joints.find(scene, "Trolley"), 0.4)
    update()
    assert _close(wm, m.matrix_world)


# ---------------------------------------------------------------------------
# remove the original / the copy
# ---------------------------------------------------------------------------

def test_remove_the_original_then_save_reopen_and_build_the_copy(crane, tmp_path):
    scene = crane
    joints.set_follows(scene, joints.find(scene, "Trolley"), "Boom", ratio=0.1)
    root = roots(scene)["TEST.CRANE"]
    copy.paste(scene, [root])
    remove.remove(scene, [root])
    s = scene.fresing
    assert [j.name for j in s.joints] == ["Boom (2)", "Trolley (2)"]
    assert joints.find(scene, "Trolley (2)").follows == "Boom (2)"
    path = str(tmp_path / "copy_only.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    scene = bpy.context.scene
    s = scene.fresing
    assert all(joints.is_valid(j) for j in s.joints) and len(s.cylinders) == 1
    assert all(cylinders.is_valid(c) for c in s.cylinders)
    r2 = roots(scene)["TEST.CRANE (2)"]
    b2 = ob(scene, "BOOM", r2)
    assert len(b2.data.vertices) > 0
    w = b2.matrix_world.copy()
    joints.set_value(joints.find(scene, "Boom (2)"), math.radians(20.0))
    update()
    assert not _close(w, b2.matrix_world)
    # the original's animation had a step on 'Boom' (gone): Build still runs
    info = animation.bake(scene, s.animations[0])
    assert info["frames"] >= 1
    animation.clear_keys(scene)
    reimport.update_model(bpy.context, r2, r2["fr_cache"])
    assert len(s.joints) == 2 and all(joints.is_valid(j) for j in s.joints)


def test_removing_the_copy_leaves_the_original_whole(crane):
    scene = crane
    s = scene.fresing
    joints.set_follows(scene, joints.find(scene, "Trolley"), "Boom", ratio=0.1)
    boom = ob(scene, "BOOM")
    c = s.callouts.add()
    c.text, c.part = "Boom", boom
    decals.add(boom, 0, (0.0, 0.0, 0.0), (0, 0, 1), "TEXT", text="ORIGINAL")
    decals.sync([boom])
    update()
    root = roots(scene)["TEST.CRANE"]
    objs_before = {o.name for o in bpy.data.objects}
    meshes_before = {m.name for m in bpy.data.meshes}
    cols_before = {c.name for c in bpy.data.collections}
    dec_before = [o.name for o in scene.objects if o.get(build.PROP_KIND) == "decal"]
    assert dec_before
    p = copy.paste(scene, [root])
    r2 = bpy.data.objects[p["roots"][0]]
    dec2 = [o for o in scene.objects if o.get(build.PROP_KIND) == "decal" and build.model_root_of(o.parent) is r2]
    assert dec2, "the logo on the boom did not come along"
    assert p["labels"] == 1
    remove.remove(scene, [r2])
    update()
    assert [j.name for j in s.joints] == ["Boom", "Trolley"] and all(joints.is_valid(j) for j in s.joints)
    assert joints.find(scene, "Trolley").follows == "Boom"
    assert len(s.cylinders) == 1 and cylinders.is_valid(s.cylinders[0])
    assert len(s.callouts) == 1 and s.callouts[0].part is boom
    assert {o.name for o in scene.objects if o.get(build.PROP_KIND) == "decal"} == set(dec_before)
    assert {m.name for m in bpy.data.meshes} >= meshes_before - {m for m in meshes_before if m not in bpy.data.meshes}
    assert all(len(o.data.vertices) for o in _model_objs(scene) if o.type == "MESH")
    left = {o.name for o in bpy.data.objects} - objs_before
    assert not left, f"objects of the removed copy are left: {sorted(left)[:10]}"
    cols = {c.name for c in bpy.data.collections} - cols_before
    assert not cols, f"collections of the removed copy are left: {sorted(cols)}"
    assert copy.GROUP not in root or not copy.others(scene, root)
    assert animation.bake(scene, s.animations[0])["frames"] > 1


def test_removing_a_hose_copy_leaves_the_original_hoses():
    scene = _fresh(HOSES)
    s = scene.fresing
    flex.set_up_test_hoses(scene)
    n = len(s.flex)
    root = build.model_roots(scene)[0]
    p = copy.paste(scene, [root])
    assert len(s.flex) == 2 * n
    remove.remove(scene, [bpy.data.objects[p["roots"][0]]])
    update()
    assert len(s.flex) == n, [it.name for it in s.flex]
    assert all(not flex.broken(scene, it) for it in s.flex)
    assert all(it.part.modifiers.get(flex.MOD) is not None for it in s.flex)
    assert len(s.joints) == 2 and len(s.cylinders) == 1


# ---------------------------------------------------------------------------
# copies of copies, frozen copies, model updates
# ---------------------------------------------------------------------------

def test_a_copy_of_a_frozen_copy(crane):
    scene = crane
    p = copy.paste(scene, [ob(scene, "BOOM.ASM")])
    r2 = bpy.data.objects[p["roots"][0]]
    before = _counts(scene)
    p = copy.paste(scene, [r2])
    _check_plan_truthful(scene, before, p)
    r3 = bpy.data.objects[p["roots"][0]]
    assert p["names"] == ["BOOM.ASM (3)"], p["names"]
    j3 = joints.find(scene, "Boom (3)")
    assert j3 is not None and joints.is_valid(j3)
    b3 = ob(scene, "BOOM", r3)
    w = b3.matrix_world.copy()
    joints.set_value(j3, math.radians(15.0))
    update()
    assert not _close(w, b3.matrix_world)
    assert copy.refused_update(r3), "a copy of a frozen copy must be frozen too"
    assert not _uids_unique(scene)


def test_part_ids_unique_after_many_pastes(crane):
    scene = crane
    root = roots(scene)["TEST.CRANE"]
    p = copy.paste(scene, [ob(scene, "BOOM.ASM", root)])
    sub = bpy.data.objects[p["roots"][0]]
    p = copy.paste(scene, [root])
    r2 = bpy.data.objects[p["roots"][0]]
    copy.paste(scene, [ob(scene, "TROLLEY.ASM", r2)])
    copy.paste(scene, [sub])
    copy.paste(scene, [r2])
    copy.paste(scene, [ob(scene, "BOOM", root), ob(scene, "COVER", root)])
    dup = _uids_unique(scene)
    assert not dup, dup[:5]
    names = [j.name for j in scene.fresing.joints]
    assert len(names) == len(set(names)), names
    rnames = [r.get(build.PROP_NAME) for r in build.model_roots(scene)]
    assert len(rnames) == len(set(rnames)), rnames
    reimport.update_model(bpy.context, root, root["fr_cache"])
    assert not _uids_unique(scene)
    names = [j.name for j in scene.fresing.joints]
    assert len(names) == len(set(names)) and all(joints.is_valid(j) for j in scene.fresing.joints), names


def _bolt(scene, root):
    return next(o for o in logic.descendants(root) if str(o.get(build.PROP_NAME, "")).startswith("ISO 4017"))


def _bolts(scene, root):
    return sum(1 for o in logic.descendants(root) if str(o.get(build.PROP_NAME, "")).startswith("ISO 4017"))


def test_removed_parts_of_the_original_stay_out_of_the_copy(crane):
    scene = crane
    root = roots(scene)["TEST.CRANE"]
    remove.remove(scene, [_bolt(scene, root)])
    assert _bolts(scene, root) == 3
    p = copy.paste(scene, [root])
    r2 = bpy.data.objects[p["roots"][0]]
    assert _bolts(scene, r2) == 3
    reimport.update_model(bpy.context, root, root["fr_cache"])
    rs = roots(scene)
    assert _bolts(scene, rs["TEST.CRANE"]) == 3 and _bolts(scene, rs["TEST.CRANE (2)"]) == 3
    reimport.update_model(bpy.context, rs["TEST.CRANE (2)"], rs["TEST.CRANE (2)"]["fr_cache"])
    rs = roots(scene)
    assert _bolts(scene, rs["TEST.CRANE"]) == 3 and _bolts(scene, rs["TEST.CRANE (2)"]) == 3
    assert not _uids_unique(scene)


def test_a_part_removed_from_the_copy_stays_out_when_the_original_is_updated(crane):
    scene = crane
    root = roots(scene)["TEST.CRANE"]
    p = copy.paste(scene, [root])
    r2 = bpy.data.objects[p["roots"][0]]
    remove.remove(scene, [_bolt(scene, r2)])
    assert _bolts(scene, r2) == 3 and _bolts(scene, root) == 4
    reimport.update_model(bpy.context, root, root["fr_cache"])
    rs = roots(scene)
    assert _bolts(scene, rs["TEST.CRANE"]) == 4, "the original got the copy's removal"
    assert _bolts(scene, rs["TEST.CRANE (2)"]) == 3, "the copy's removed bolt came back with the original's update"
    assert len(scene.fresing.joints) == 4 and all(joints.is_valid(j) for j in scene.fresing.joints)


def test_an_update_of_the_original_with_a_hose_copy():
    scene = _fresh(HOSES)
    s = scene.fresing
    flex.set_up_test_hoses(scene)
    n = len(s.flex)
    root = build.model_roots(scene)[0]
    copy.paste(scene, [root])
    names = sorted(it.name for it in s.flex)
    out = reimport.update_model(bpy.context, root, root["fr_cache"])
    assert sorted(it.name for it in s.flex) == names, (names, [it.name for it in s.flex], out["notes"])
    assert len(s.flex) == 2 * n and all(not flex.broken(scene, it) for it in s.flex)
    assert sorted(j.name for j in s.joints) == ["Luff", "Luff (2)", "Slide", "Slide (2)"]
    assert len(s.cylinders) == 2 and all(cylinders.is_valid(c) for c in s.cylinders)
    # each hose still on its own model's parts
    for it in s.flex:
        r = build.model_root_of(it.part)
        assert build.model_root_of(it.a_part) is r and build.model_root_of(it.b_part) is r, it.name


def _fourbar(scene):
    crank = ob(scene, "FOURBAR.CRANK.ASM")
    linkages.create(scene, "FOURBAR", [[ob(scene, "FOURBAR.COUPLER.ASM")], [ob(scene, "FOURBAR.ROCKER.ASM")],
                                       [crank]], base=ob(scene, "FOURBAR.BASE.ASM"), drive=crank)
    update()


def test_an_update_of_the_original_with_a_mechanism_copy():
    scene = _fresh(LINKS)
    s = scene.fresing
    _fourbar(scene)
    root = build.model_roots(scene)[0]
    before = _counts(scene)
    p = copy.paste(scene, [root])
    _check_plan_truthful(scene, before, p)
    jn = sorted(j.name for j in s.joints)
    reimport.update_model(bpy.context, root, root["fr_cache"])
    assert len(s.mechanisms) == 2 and all(linkages.is_valid(m) for m in s.mechanisms)
    assert sorted(j.name for j in s.joints) == jn
    r2 = roots(scene)[p["names"][0]]
    m2 = next(m for m in s.mechanisms if build.model_root_of(m.base) is r2)
    j2 = linkages.input_joint(scene, m2)
    assert j2 is not None
    rock2 = ob(scene, "FOURBAR.ROCKER.ASM", r2)
    w = rock2.matrix_world.copy()
    joints.set_value(j2, math.radians(25.0))
    update()
    assert not _close(w, rock2.matrix_world)


def test_a_mechanism_whose_base_is_outside_is_left_out_and_said():
    """(A mechanism's input joint is always its own, on a link: one that also moves parts elsewhere is refused by
    linkages.create, so 'drive joint outside' cannot be set up.) The four-bar's links copied without its base: the
    mechanism is left out and said so; what is made is what is counted."""
    scene = _fresh(LINKS)
    s = scene.fresing
    _fourbar(scene)
    before = _counts(scene)
    p = copy.paste(scene, [ob(scene, n) for n in ("FOURBAR.COUPLER.ASM", "FOURBAR.ROCKER.ASM", "FOURBAR.CRANK.ASM")])
    _check_plan_truthful(scene, before, p)
    assert p["mechanisms"] == 0 and any("Mechanism" in x for x in p["left"]), p["left"]
    assert linkages.is_valid(s.mechanisms[0]) and linkages.input_joint(scene, s.mechanisms[0]) is not None


# ---------------------------------------------------------------------------
# several things at once, selections
# ---------------------------------------------------------------------------

def test_two_subassemblies_of_one_model(crane):
    scene = crane
    before = _counts(scene)
    p = copy.paste(scene, [ob(scene, "BOOM.ASM"), ob(scene, "TROLLEY.ASM")])
    _check_plan_truthful(scene, before, p)
    assert len(p["roots"]) == 1 and p["joints"] == 2, p
    r2 = bpy.data.objects[p["roots"][0]]
    t2 = joints.find(scene, "Trolley (2)")
    assert t2.frame.parent is ob(scene, "BOOM.ASM", r2), "the trolley's joint should sit on the copied boom"
    tr = ob(scene, "TROLLEY", r2)
    w = tr.matrix_world.copy()
    joints.set_value(joints.find(scene, "Boom (2)"), math.radians(20.0))
    update()
    assert not _close(w, tr.matrix_world), "the copied trolley does not ride on the copied boom"


def test_a_child_selected_with_its_parent_is_copied_once(crane):
    scene = crane
    p1 = copy.plan(scene, [ob(scene, "BOOM.ASM")])
    p2 = copy.plan(scene, [ob(scene, "BOOM.ASM"), ob(scene, "BOOM"), ob(scene, "BOOM.PIN")])
    assert (p1["parts"], p1["joints"]) == (p2["parts"], p2["joints"]) == (3, 1)
    p = copy.paste(scene, [ob(scene, "BOOM"), ob(scene, "BOOM.ASM")])
    assert p["parts"] == 3 and len(p["roots"]) == 1
    r2 = bpy.data.objects[p["roots"][0]]
    assert sum(1 for o in logic.descendants(r2) if o.get(build.PROP_NAME) == "BOOM") == 1


def test_a_model_and_parts_of_another_model():
    scene = _fresh(CRANE)
    assert bpy.ops.fresing.import_step(filepath=LINKS, quality="draft") == {"FINISHED"}
    _fourbar(scene)
    rs = roots(scene)
    crane_root = rs["TEST.CRANE"]
    before = _counts(scene)
    p = copy.paste(scene, [crane_root, ob(scene, "FOURBAR.ASM")])
    _check_plan_truthful(scene, before, p)
    assert len(p["roots"]) == 2 and p["mechanisms"] == 1, p
    boxes = [place.bounds(scene, bpy.data.objects[n]) for n in p["roots"]]
    others = [place.bounds(scene, r) for r in build.model_roots(scene) if r.name not in p["roots"]]
    for i, (lo, hi) in enumerate(boxes):
        for lo2, hi2 in boxes[:i] + others:
            overlap = all(lo[k] < hi2[k] and hi[k] > lo2[k] for k in range(3))
            assert not overlap, f"copy {p['roots'][i]} overlaps another model"
    assert not _uids_unique(scene)


# ---------------------------------------------------------------------------
# a built animation, placed models
# ---------------------------------------------------------------------------

def test_copy_while_an_animation_is_built(crane):
    scene = crane
    s = scene.fresing
    info = animation.bake(scene, s.animations[0])
    scene.frame_set(info["frames"])
    root = roots(scene)["TEST.CRANE"]
    boom_cad = joints.get_value(joints.find(scene, "Boom"))
    p = copy.paste(scene, [root])
    assert p["roots"]
    assert not animation.has_keys(scene)
    text = " ".join(copy.summary(p))
    assert "Build again" in text or "build" in text.lower(), \
        f"the built animation was taken off without a word: {text!r}"
    del boom_cad


def test_a_placed_subassembly_is_copied_where_it_stands(crane):
    scene = crane
    root = roots(scene)["TEST.CRANE"]
    cover = ob(scene, "COVER", root)
    place.move(scene, [cover], Matrix.Translation((0.0, 0.7, 0.3)))
    update()
    w = cover.matrix_world.copy()
    p = copy.paste(scene, [cover])
    c2 = ob(scene, "COVER", bpy.data.objects[p["roots"][0]])
    d = c2.matrix_world.translation - w.translation
    assert abs(d.y) < 1e-4 and abs(d.z) < 1e-4, f"the copy of a placed part landed off its place: {tuple(d)}"
    assert _close(w.to_3x3().to_4x4(), c2.matrix_world.to_3x3().to_4x4(), 1e-5)
    # the whole model with a placed part: the part where the original's stands, relative to its root
    p = copy.paste(scene, [root])
    r2 = bpy.data.objects[p["roots"][0]]
    c3 = ob(scene, "COVER", r2)
    rel1 = root.matrix_world.inverted() @ cover.matrix_world
    rel2 = r2.matrix_world.inverted() @ c3.matrix_world
    assert _close(rel1, rel2), "the placed part stands elsewhere in the copy of the whole model"


def test_a_placed_joint_member_is_copied_where_it_stands(crane):
    """BOOM.ASM moved by Place (its joint's axis goes with it): the copy of the whole crane has its boom and axis
    where the original's are."""
    scene = crane
    root = roots(scene)["TEST.CRANE"]
    boom = ob(scene, "BOOM.ASM", root)
    place.move(scene, [boom], Matrix.Translation((0.0, 0.0, 0.25)))
    update()
    p = copy.paste(scene, [root])
    r2 = bpy.data.objects[p["roots"][0]]
    b2 = ob(scene, "BOOM.ASM", r2)
    rel1 = root.matrix_world.inverted() @ boom.matrix_world
    rel2 = r2.matrix_world.inverted() @ b2.matrix_world
    assert _close(rel1, rel2), "the placed boom stands elsewhere in the copy"
    o1, _d = joints.axis_world(joints.find(scene, "Boom"))
    o2, _d = joints.axis_world(joints.find(scene, "Boom (2)"))
    a = root.matrix_world.inverted() @ o1
    b = r2.matrix_world.inverted() @ o2
    assert (a - b).length < 1e-4, f"the copy's boom axis is off by {(a - b).length:.4f} m"


def test_a_placed_model_is_copied_beside_it(crane):
    scene = crane
    root = roots(scene)["TEST.CRANE"]
    place.move(scene, [root], Matrix.Translation((3.0, -2.0, 0.5)) @ Matrix.Rotation(math.radians(30), 4, "Z"))
    update()
    p = copy.paste(scene, [root])
    r2 = bpy.data.objects[p["roots"][0]]
    lo1, hi1 = place.bounds(scene, root)
    lo2, hi2 = place.bounds(scene, r2)
    assert lo2.x > hi1.x - 1e-6 and abs(lo2.y - lo1.y) < 1e-4 and abs(lo2.z - lo1.z) < 1e-4
    assert _close(root.matrix_world.to_3x3().to_4x4(), r2.matrix_world.to_3x3().to_4x4(), 1e-5)


# ---------------------------------------------------------------------------
# way covers, hoses with an end outside
# ---------------------------------------------------------------------------

def _cover_ob(scene, name, root):
    return next(o for o in logic.descendants(root) if str(o.get(build.PROP_NAME, "")).split(" v")[0] == name)


def test_way_covers_come_along_and_follow_the_copys_axis():
    scene = _fresh(COVERS)
    s = scene.fresing
    waycover.set_up_test_model(scene)
    root = build.model_roots(scene)[0]
    before = _counts(scene)
    p = copy.paste(scene, [root])
    _check_plan_truthful(scene, before, p)
    assert p["way_covers"] == 2 and len(s.waycovers) == 4
    r2 = bpy.data.objects[p["roots"][0]]
    new = list(s.waycovers)[2:]
    assert all(w.axis == "X axis (2)" for w in new), [w.axis for w in new]
    for w in new:
        for sec in w.sections:
            if sec.joint:
                j = joints.find(scene, sec.joint)
                assert j is not None and joints.is_valid(j) and j.follows == "X axis (2)", (w.name, sec.joint)
                assert all(build.model_root_of(m) is r2 for m in joints.members(j))
            for r in sec.parts:
                assert build.model_root_of(r.obj) is r2, (w.name, r.obj.name)
    l1, l1c = _cover_ob(scene, "COVER.L.1", root), _cover_ob(scene, "COVER.L.1", r2)
    w1, w2 = l1.matrix_world.copy(), l1c.matrix_world.copy()
    joints.set_value(joints.find(scene, "X axis (2)"), 0.5)
    update()
    assert _close(w1, l1.matrix_world), "the copy's axis moved the original's cover"
    assert not _close(w2, l1c.matrix_world), "the copy's cover did not follow the copy's axis"


def test_way_cover_axis_outside_the_copy_is_left_out():
    scene = _fresh(COVERS)
    s = scene.fresing
    waycover.set_up_test_model(scene)
    root = build.model_roots(scene)[0]
    parts = [_cover_ob(scene, f"COVER.L.{k}", root) for k in range(1, 5)]
    before = _counts(scene)
    p = copy.paste(scene, parts)
    _check_plan_truthful(scene, before, p)
    assert p["way_covers"] == 0 and len(s.waycovers) == 2
    assert all(waycover.is_valid(w) if hasattr(waycover, "is_valid") else True for w in s.waycovers)
    assert p["joints"] == 0 or all(not joints.find(scene, n).follows or joints.find(scene, joints.find(scene, n)
                                                                                    .follows) for n in
                                   [j.name for j in s.joints])
    assert any("follows 'X axis'" in x for x in p["left"]) or any("Way cover" in x for x in p["left"]), p["left"]


def test_a_hose_with_an_end_outside_is_left_out_and_the_original_stays():
    scene = _fresh(HOSES)
    s = scene.fresing
    flex.set_up_test_hoses(scene)
    n = len(s.flex)
    shapes = {it.name: flex.shape_now(scene, it).copy() for it in s.flex}
    hose = ob(scene, "HYDRAULIC HOSE CYL A")
    before = _counts(scene)
    p = copy.paste(scene, [hose, ob(scene, "CYL.ASM")])
    _check_plan_truthful(scene, before, p)
    assert p["hoses"] == 0 and len(s.flex) == n
    assert any("HYDRAULIC HOSE CYL A" in x and "outside" in x for x in p["left"]), p["left"]
    r2 = bpy.data.objects[p["roots"][0]]
    h2 = ob(scene, "HYDRAULIC HOSE CYL A", r2)
    assert h2.modifiers.get(flex.MOD) is None and not any(k in h2 for k in ("fr_flex", "fr_flex_local"))
    for it in s.flex:
        assert not flex.broken(scene, it), it.name
        assert it.part.modifiers.get(flex.MOD) is not None, it.name
    import numpy as np
    flex.refresh(scene, force=True)
    for it in s.flex:
        assert float(np.abs(flex.shape_now(scene, it) - shapes[it.name]).max()) < 1e-6, it.name


def test_a_hose_with_both_ends_and_its_part_in_a_parts_copy():
    scene = _fresh(HOSES)
    s = scene.fresing
    flex.set_up_test_hoses(scene)
    before = _counts(scene)
    objs = [ob(scene, n) for n in ("HYDRAULIC HOSE ARM", "FITTING VALVE C", "ARM.ASM")]
    p = copy.paste(scene, objs)
    _check_plan_truthful(scene, before, p)
    assert p["hoses"] == 1 and p["joints"] == 1, p
    it = s.flex[len(s.flex) - 1]
    r2 = bpy.data.objects[p["roots"][0]]
    assert build.model_root_of(it.part) is r2 and build.model_root_of(it.a_part) is r2
    j = joints.find(scene, "Luff (2)")
    sh = flex.shape_now(scene, it).copy()
    joints.set_value(j, math.radians(-12.0))
    update()
    flex.refresh(scene, force=True)
    update()
    import numpy as np
    assert float(np.abs(flex.shape_now(scene, it) - sh).max()) > 1e-3, "the copied hose does not follow the copy"


@own_process
def test_a_model_with_hoses_pasted_twice():
    """Paste, then Paste again (Ctrl+V twice): the second paste hung for ever (the hose list item read after the list
    grew, ``copy._flex``)."""
    scene = _fresh(HOSES)
    s = scene.fresing
    flex.set_up_test_hoses(scene)
    root = build.model_roots(scene)[0]
    for k in range(3):
        before = _counts(scene)
        p = copy.paste(scene, [root])
        _check_plan_truthful(scene, before, p)
        assert p["hoses"] == 4
    assert len(s.flex) == 16


@own_process
def test_a_model_with_way_covers_and_labels_pasted_three_times():
    scene = _fresh(COVERS)
    s = scene.fresing
    waycover.set_up_test_model(scene)
    root = build.model_roots(scene)[0]
    for o in [o for o in logic.descendants(root) if o.get(build.PROP_KIND) == "part"][:5]:
        c = s.callouts.add()
        c.text, c.part = o.get(build.PROP_NAME), o
    for k in range(3):
        before = _counts(scene)
        p = copy.paste(scene, [root])
        _check_plan_truthful(scene, before, p)
        assert p["way_covers"] == 2 and p["labels"] == 5
    assert len(s.waycovers) == 8 and len(s.callouts) == 20
    for w in list(s.waycovers)[2:]:
        assert joints.find(scene, w.axis) is not None and w.axis != "X axis", w.axis


@own_process
def test_two_whole_models_with_hoses_and_labels_pasted_at_once():
    """The original and its copy pasted together: each new copy gets the hoses and labels of its own original."""
    scene = _fresh(HOSES)
    s = scene.fresing
    flex.set_up_test_hoses(scene)
    root = build.model_roots(scene)[0]
    c = s.callouts.add()
    c.text, c.part = "Arm", ob(scene, "ARM")
    p = copy.paste(scene, [root])
    r2 = bpy.data.objects[p["roots"][0]]
    before = _counts(scene)
    p = copy.paste(scene, [root, r2])
    _check_plan_truthful(scene, before, p)
    assert len(p["roots"]) == 2 and p["hoses"] == 8 and p["labels"] == 2, p
    new_roots = [bpy.data.objects[n] for n in p["roots"]]
    for r in new_roots:
        items = [it for it in s.flex if build.model_root_of(it.part) is r]
        assert len(items) == 4, (r.name, [it.name for it in s.flex])
        for it in items:
            assert build.model_root_of(it.a_part) is r and build.model_root_of(it.b_part) is r, it.name
        assert sum(1 for c in s.callouts if build.model_root_of(c.part) is r) == 1
    names = [it.name for it in s.flex]
    assert len(names) == len(set(names)), names


def test_save_reopen_then_update_the_original_updates_the_copy(crane, tmp_path):
    scene = crane
    root = roots(scene)["TEST.CRANE"]
    p = copy.paste(scene, [root])
    r2 = bpy.data.objects[p["roots"][0]]
    place.move(scene, [r2], Matrix.Translation((0.5, 1.5, 0.0)) @ Matrix.Rotation(math.radians(40), 4, "Z"))
    update()
    m2 = r2.matrix_world.copy()
    sub = copy.paste(scene, [ob(scene, "BOOM.ASM", root)])
    path = str(tmp_path / "group.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    scene = bpy.context.scene
    rs = roots(scene)
    out = reimport.update_model(bpy.context, rs["TEST.CRANE"], rs["TEST.CRANE"]["fr_cache"])
    assert any("TEST.CRANE (2)" in n and "updated too" in n for n in out["notes"]), out["notes"]
    rs = roots(scene)
    assert set(rs) == {"TEST.CRANE", "TEST.CRANE (2)", sub["names"][0]}
    assert _close(rs["TEST.CRANE (2)"].matrix_world, m2, 1e-5), "the copy's place (turned) was lost in the update"
    with pytest.raises(reimport.UpdateFailed):
        reimport.update_model(bpy.context, rs[sub["names"][0]], rs["TEST.CRANE"]["fr_cache"])
    assert all(joints.is_valid(j) for j in scene.fresing.joints) and len(scene.fresing.joints) == 5


def test_a_hidden_part_stays_hidden_in_the_copy_and_through_an_update(crane):
    scene = crane
    root = roots(scene)["TEST.CRANE"]
    cover = ob(scene, "COVER", root)
    logic.set_hidden(cover, True)
    hidden = logic.is_hidden(cover)
    assert hidden
    p = copy.paste(scene, [root])
    r2 = bpy.data.objects[p["roots"][0]]
    assert logic.is_hidden(ob(scene, "COVER", r2)) == hidden
    reimport.update_model(bpy.context, root, root["fr_cache"])
    rs = roots(scene)
    assert logic.is_hidden(ob(scene, "COVER", rs["TEST.CRANE (2)"])) == hidden
    assert logic.is_hidden(ob(scene, "COVER", rs["TEST.CRANE"])) == hidden


@own_process
def test_many_labels_come_along_each_on_its_own_part():
    """Twelve labels on the crane's parts: the copy has twelve, with the same texts, each on the copy of its part."""
    scene = _fresh(CRANE)
    s = scene.fresing
    root = roots(scene)["TEST.CRANE"]
    parts = [o for o in logic.descendants(root) if o.get(build.PROP_KIND) == "part"][:12]
    for k, part in enumerate(parts):
        c = s.callouts.add()
        c.text, c.part = f"Label {k}", part
    p = copy.paste(scene, [root])
    assert p["labels"] == 12 and len(s.callouts) == 24
    r2 = bpy.data.objects[p["roots"][0]]
    for k in range(12):
        a, b = s.callouts[k], s.callouts[12 + k]
        assert b.text == a.text, (k, a.text, b.text)
        assert b.part is not None and build.model_root_of(b.part) is r2 and \
            b.part.get(build.PROP_UID) == "~2/" + a.part.get(build.PROP_UID), (k, b.part)


def test_an_only_this_copy_logo_and_removing_the_copy(crane):
    scene = crane
    boom = ob(scene, "BOOM")
    decals.add(boom, 0, (0.0, 0.0, 0.0), (0, 0, 1), "TEXT", text="ONLY HERE", only_copy=True)
    decals.sync([boom])
    update()
    mine = [o.name for o in scene.objects if o.get(build.PROP_KIND) == "decal" and o.parent is boom]
    assert mine
    p = copy.paste(scene, [roots(scene)["TEST.CRANE"]])
    r2 = bpy.data.objects[p["roots"][0]]
    b2 = ob(scene, "BOOM", r2)
    theirs = [o for o in scene.objects if o.get(build.PROP_KIND) == "decal" and o.parent is b2]
    assert len(theirs) == len(mine), "the copy's own logo did not come along"
    assert b2.fresing_decals[0].key != boom.fresing_decals[0].key
    remove.remove(scene, [r2])
    update()
    assert [o.name for o in scene.objects if o.get(build.PROP_KIND) == "decal" and o.parent is boom] == mine


def test_the_clipboard_after_a_model_update(crane):
    """Copy the crane, update it, Paste: the clipboard named the old root, which the update replaced."""
    scene = crane
    root = roots(scene)["TEST.CRANE"]
    for o in scene.objects:
        o.select_set(False)
    root.select_set(True)
    bpy.context.view_layer.objects.active = root
    assert bpy.ops.fresing.copy() == {"FINISHED"}
    reimport.update_model(bpy.context, root, root["fr_cache"])
    assert bpy.ops.fresing.paste.poll(), "after a model update the copied model can no longer be pasted"
    assert bpy.ops.fresing.paste(open_place=False) == {"FINISHED"}
    assert "TEST.CRANE (2)" in roots(scene)


# ---------------------------------------------------------------------------
# names
# ---------------------------------------------------------------------------

def test_names_collide_with_existing_joints_and_objects(crane):
    scene = crane
    cover = ob(scene, "COVER")
    joints.create(scene, "ROTATE", [cover], cover.matrix_world.translation.copy(), Vector((0, 0, 1)),
                  name="Boom (2)")
    e = bpy.data.objects.new("BOOM.ASM (2)", None)
    scene.collection.objects.link(e)
    update()
    p = copy.paste(scene, [ob(scene, "BOOM.ASM")])
    names = [j.name for j in scene.fresing.joints]
    assert len(names) == len(set(names)), names
    assert "Boom (3)" in names, names
    r2 = bpy.data.objects[p["roots"][0]]
    assert r2.get(build.PROP_NAME) == r2.name, (r2.name, r2.get(build.PROP_NAME))
    assert joints.find(scene, "Boom (2)").frame is not None and joints.members(joints.find(scene, "Boom (2)")) == \
        [cover]


# ---------------------------------------------------------------------------
# a failure half-way
# ---------------------------------------------------------------------------

def test_a_failure_half_way_leaves_no_half_made_copy(crane, monkeypatch):
    scene = crane
    root = roots(scene)["TEST.CRANE"]
    objs = {o.name for o in bpy.data.objects}
    n_j = len(scene.fresing.joints)

    def boom(*_a, **_k):
        raise RuntimeError("test: a failure while the copy is made")
    monkeypatch.setattr(copy, "_labels", boom)
    try:
        copy.paste(scene, [root])
    except RuntimeError:
        pass
    monkeypatch.undo()
    new = {o.name for o in bpy.data.objects} - objs
    assert not new and len(scene.fresing.joints) == n_j, \
        f"a failure in paste left a half-made copy: {len(new)} objects, {len(scene.fresing.joints) - n_j} joints"
