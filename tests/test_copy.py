"""Copy and paste with joints and mechanisms (task 0293). Blender as a module (no window); the keys, the right-click
menu, the Place window and Ctrl+Z in a window: tools/ui_test_copy.py."""

import math
import os

import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import (animation, build, clash, context_menu, copy, cylinders, flex, joints,  # noqa: E402
                                    lesson, linkages, lock, logic, ops_copy, ops_place, place, reimport, remove,
                                    workspaces)

DATA = os.path.join(os.path.dirname(__file__), "data")
CRANE = os.path.join(DATA, "test_crane_a.step")
HOSES = os.path.join(DATA, "test_flex_hoses_a.step")
LINKS = os.path.join(DATA, "test_linkage_a.step")


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
    """The test crane as the crane lesson makes it: joints Boom and Trolley, the luffing cylinder, an animation."""
    scene = _fresh(CRANE)
    lesson.run(scene, "crane")
    animation.clear_keys(scene)
    yield scene


def ob(scene, name, root=None):
    return next(o for o in scene.objects if o.get(build.PROP_NAME) == name
                and (root is None or build.model_root_of(o) is root))


def roots(scene):
    return {r.get(build.PROP_NAME): r for r in build.model_roots(scene)}


def select(scene, *objs):
    for o in scene.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0] if objs else None


def update():
    bpy.context.view_layer.update()
    bpy.context.view_layer.update()


def _close(a, b, tol=2e-4):
    return all(abs(a[r][c] - b[r][c]) < tol for r in range(4) for c in range(4))


def test_names_count_up():
    assert copy.next_name("Boom", set()) == "Boom (2)"
    assert copy.next_name("Boom", {"Boom (2)"}) == "Boom (3)"
    assert copy.next_name("Boom (2)", {"Boom (2)", "Boom (3)"}) == "Boom (4)"
    assert copy.next_name("A (b) (7)", set()) == "A (b) (2)"


def test_the_crane_copied_with_its_joints_and_cylinder(crane):
    """The whole crane: a second crane beside it with its own joints and cylinder, shared shapes, scoped part IDs;
    the two move independently, Build moves each by its own steps, a model update updates both."""
    scene = crane
    s = scene.fresing
    root = roots(scene)["TEST.CRANE"]
    meshes = len(bpy.data.meshes)
    joints.set_value(joints.find(scene, "Boom"), math.radians(10.0))
    p = copy.paste(scene, [root])
    assert p["names"] == ["TEST.CRANE (2)"] and not p["left"] and not p["notes"], p
    assert (p["parts"], p["joints"], p["cylinders"]) == (20, 2, 1)
    assert [j.name for j in s.joints] == ["Boom", "Trolley", "Boom (2)", "Trolley (2)"]
    assert [c.name for c in s.cylinders] == ["Luffing cylinder", "Luffing cylinder (2)"]
    assert all(joints.is_valid(j) for j in s.joints) and all(cylinders.is_valid(c) for c in s.cylinders)
    assert len(bpy.data.meshes) == meshes                       # the shapes are shared
    r2 = roots(scene)["TEST.CRANE (2)"]
    assert r2.name == "TEST.CRANE (2)" and r2[build.PROP_UID].startswith("~2/") and r2[copy.GROUP] == root[copy.GROUP]
    assert r2["fr_cache"] == root["fr_cache"] and not r2.get(copy.FROZEN)
    assert s.model_count == 2
    b1, b2 = ob(scene, "BOOM", root), ob(scene, "BOOM", r2)
    assert b1.data is b2.data and b2[build.PROP_UID] == "~2/" + b1[build.PROP_UID]
    # the copy stands beside the original (no overlap), the same pose (Boom at 10°)
    lo1, hi1 = place.bounds(scene, root)
    lo2, hi2 = place.bounds(scene, r2)
    assert lo2.x > hi1.x and abs(lo2.y - lo1.y) < 1e-4 and abs(lo2.z - lo1.z) < 1e-4
    assert abs(joints.get_value(joints.find(scene, "Boom (2)")) - math.radians(10.0)) < 1e-5
    dx = r2.matrix_world.translation.x - root.matrix_world.translation.x
    assert _close(Matrix.Translation((dx, 0, 0)) @ b1.matrix_world, b2.matrix_world)
    # independent: the copy's boom up 30°, the original's stays
    w1 = b1.matrix_world.copy()
    joints.set_value(joints.find(scene, "Boom (2)"), math.radians(30.0))
    update()
    assert _close(w1, b1.matrix_world) and not _close(Matrix.Translation((dx, 0, 0)) @ w1, b2.matrix_world)
    rod = ob(scene, "HYDRAULIC CYLINDER.ROD", r2)
    assert rod.parent is not None and rod.parent.get(build.PROP_KIND) == "cyl_rod"
    # Build: the original's animation moves only the original
    a = s.animations[0]
    info = animation.bake(scene, a)
    assert info["frames"] > 1
    scene.frame_set(1)
    c0 = b2.matrix_world.copy()
    f0 = b1.matrix_world.copy()
    scene.frame_set(info["frames"])
    assert _close(c0, b2.matrix_world) and not _close(f0, b1.matrix_world)
    animation.clear_keys(scene)
    # a paste with a built animation takes it off and says so
    animation.bake(scene, a)
    p = copy.paste(scene, [b1])
    assert not animation.has_keys(scene) and "Build again" in copy.summary(p)[-1]
    remove.remove(scene, [bpy.data.objects[p["roots"][0]]])
    # a step of the copy's own joint moves the copy
    s.joints_index = [j.name for j in s.joints].index("Boom (2)")
    s.animations_index = 0
    assert bpy.ops.fresing.block_add(kind="JOINT") == {"FINISHED"}
    blk = a.blocks[len(a.blocks) - 1]
    blk.start, blk.duration, blk.use_from, blk.to_angle = 0.0, 2.0, True, math.radians(40.0)
    info = animation.bake(scene, a)
    scene.frame_set(1)
    c0 = b2.matrix_world.copy()
    scene.frame_set(info["frames"])
    assert not _close(c0, b2.matrix_world)
    animation.clear_keys(scene)


def test_clash_check_sees_both_cranes(crane):
    """Pasted onto the original (Paste here at its middle), the original's boom moving up runs through the copy:
    the clash check finds it; pasted beside it, no clash."""
    scene = crane
    s = scene.fresing
    root = roots(scene)["TEST.CRANE"]
    p = copy.paste(scene, [root])
    animation.bake(scene, s.animations[0])
    run = clash.check(scene)
    assert not [r for r in run.rows if r.kind == "CLASH"], [(r.a, r.b) for r in run.rows]
    animation.clear_keys(scene)
    lo, hi = place.bounds(scene, root)
    mid = (lo + hi) / 2.0
    remove.remove(scene, [bpy.data.objects[p["roots"][0]]])
    p = copy.paste(scene, [root], at=(mid.x, mid.y, lo.z))
    r2 = bpy.data.objects[p["roots"][0]]
    assert (r2.matrix_world.translation - root.matrix_world.translation).length < 1e-4
    animation.bake(scene, s.animations[0])
    run = clash.check(scene)
    rows = [r for r in run.rows if r.kind == "CLASH"]
    assert rows, "the original's boom runs through the copy standing on it: no clash found"
    assert all({r.a, r.b} & {"BOOM", "BOOM.PIN", "BOOM.LUFF.PIN", "TROLLEY", "WHEEL", "HYDRAULIC CYLINDER.ROD",
                             "HYDRAULIC CYLINDER.BARREL"} for r in rows), [(r.a, r.b) for r in rows]
    assert clash.settings(scene).clashes == len(rows)


def test_save_and_reopen_keeps_the_copy(crane, tmp_path):
    scene = crane
    root = roots(scene)["TEST.CRANE"]
    copy.paste(scene, [root])
    path = str(tmp_path / "copied.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    scene = bpy.context.scene
    s = scene.fresing
    assert [j.name for j in s.joints] == ["Boom", "Trolley", "Boom (2)", "Trolley (2)"]
    assert all(joints.is_valid(j) for j in s.joints) and len(s.cylinders) == 2
    r2 = roots(scene)["TEST.CRANE (2)"]
    b2 = ob(scene, "BOOM", r2)
    w = b2.matrix_world.copy()
    joints.set_value(joints.find(scene, "Boom (2)"), math.radians(25.0))
    update()
    assert not _close(w, b2.matrix_world)
    assert animation.bake(scene, s.animations[0])["frames"] > 1


def test_a_subassembly_copy_is_its_own_model_and_frozen(crane):
    """The boom alone: a model of its own ("BOOM.ASM (2)") with the boom's joint sitting on it; the cylinder, whose
    barrel is outside, is left out and said so; a model update leaves it alone and is refused for it."""
    scene = crane
    s = scene.fresing
    root = roots(scene)["TEST.CRANE"]
    boom = ob(scene, "BOOM.ASM")
    p = copy.paste(scene, [boom])
    assert p["names"] == ["BOOM.ASM (2)"] and (p["parts"], p["joints"], p["cylinders"]) == (3, 1, 0)
    assert any("Cylinder 'Luffing cylinder'" in x for x in p["left"])
    text = " ".join(copy.summary(p))
    assert "Left out" in text and "moves by itself" in text and "model of its own" in text
    r2 = roots(scene)["BOOM.ASM (2)"]
    assert r2.get(copy.FROZEN) and not r2.get("fr_cache") and r2.get(build.PROP_ROOT)
    j = joints.find(scene, "Boom (2)")
    assert joints.is_valid(j) and j.frame.parent is r2 and [m.name for m in joints.members(j)] == \
        [ob(scene, "BOOM.ASM", r2).name]
    # it stands beside the crane, as the boom stands in it (same height, turn)
    b1, b2 = ob(scene, "BOOM", root), ob(scene, "BOOM", r2)
    d = b2.matrix_world.translation - b1.matrix_world.translation
    assert abs(d.y) < 1e-4 and abs(d.z) < 1e-4 and d.x > 0.1
    assert _close(b1.matrix_world.to_3x3().to_4x4(), b2.matrix_world.to_3x3().to_4x4(), 1e-5)
    # its joint turns it about its own pin
    joints.set_value(j, math.radians(20.0))
    update()
    assert abs(b2.matrix_world.to_euler().y + math.radians(20.0)) < 1e-4
    # model updates: refused for the frozen copy, the original's leaves it as it is
    with pytest.raises(reimport.UpdateFailed, match="copy of a subassembly"):
        reimport.update_model(bpy.context, r2, root["fr_cache"])
    w = b2.matrix_world.copy()
    reimport.update_model(bpy.context, root, root["fr_cache"])
    update()
    assert roots(scene)["BOOM.ASM (2)"] is r2 and _close(w, b2.matrix_world)
    assert joints.is_valid(joints.find(scene, "Boom (2)"))


def test_a_model_update_updates_the_copy_too(crane):
    """A copy of a whole model follows a model update of the original (and the other way round), each keeping its
    own place, joints and values."""
    scene = crane
    s = scene.fresing
    root = roots(scene)["TEST.CRANE"]
    p = copy.paste(scene, [root])
    r2 = bpy.data.objects[p["roots"][0]]
    x2 = r2.matrix_world.translation.x
    joints.set_value(joints.find(scene, "Boom (2)"), math.radians(15.0))
    out = reimport.update_model(bpy.context, root, root["fr_cache"])
    assert any("TEST.CRANE (2)" in n and "updated too" in n for n in out["notes"]), out["notes"]
    rs = roots(scene)
    assert set(rs) == {"TEST.CRANE", "TEST.CRANE (2)"}
    r2 = rs["TEST.CRANE (2)"]
    assert r2.name == "TEST.CRANE (2)" and abs(r2.matrix_world.translation.x - x2) < 1e-5
    assert [j.name for j in s.joints if j.name.endswith("(2)")] == ["Boom (2)", "Trolley (2)"]
    assert abs(joints.get_value(joints.find(scene, "Boom (2)")) - math.radians(15.0)) < 1e-5
    assert all(joints.is_valid(j) for j in s.joints) and len(s.cylinders) == 2
    assert r2[copy.GROUP] == rs["TEST.CRANE"][copy.GROUP] and r2[build.PROP_UID].startswith("~2/")
    # the other way round: updating the copy updates the original
    out = reimport.update_model(bpy.context, r2, r2["fr_cache"])
    assert any("TEST.CRANE" in n and "updated too" in n for n in out["notes"]), out["notes"]
    assert set(roots(scene)) == {"TEST.CRANE", "TEST.CRANE (2)"} and len(s.joints) == 4


def test_a_coupling_to_a_joint_outside_is_left_out(crane):
    """The trolley follows the boom; the trolley alone copied: its copy moves by itself (the window says so)."""
    scene = crane
    s = scene.fresing
    joints.set_follows(scene, joints.find(scene, "Trolley"), "Boom", ratio=0.1)
    trolley = ob(scene, "TROLLEY.ASM")
    p = copy.paste(scene, [trolley])
    assert any("follows 'Boom'" in x and "by itself" in x for x in p["left"]), p["left"]
    j = joints.find(scene, "Trolley (2)")
    assert joints.is_valid(j) and not j.follows
    assert joints.find(scene, "Trolley").follows == "Boom"
    # the copy's joint sat on the boom (outside the copy): it sits on the copy itself
    assert j.frame.parent is roots(scene)["TROLLEY.ASM (2)"]


def test_copy_of_a_copy_and_removing_the_original(crane):
    scene = crane
    s = scene.fresing
    root = roots(scene)["TEST.CRANE"]
    p = copy.paste(scene, [root])
    r2 = bpy.data.objects[p["roots"][0]]
    p = copy.paste(scene, [r2])
    assert p["names"] == ["TEST.CRANE (3)"]
    r3 = bpy.data.objects[p["roots"][0]]
    assert r3[build.PROP_UID].startswith("~3/") and r3[copy.GROUP] == root[copy.GROUP]
    assert [j.name for j in s.joints][-2:] == ["Boom (3)", "Trolley (3)"]
    # three cranes in a row, none overlapping
    boxes = [place.bounds(scene, r) for r in (root, r2, r3)]
    assert boxes[0][1].x < boxes[1][0].x and boxes[1][1].x < boxes[2][0].x
    # the original removed: the copies keep their shapes, joints and cylinders and build
    remove.remove(scene, [root])
    assert set(roots(scene)) == {"TEST.CRANE (2)", "TEST.CRANE (3)"}
    assert all(joints.is_valid(j) for j in s.joints) and len(s.joints) == 4 and len(s.cylinders) == 2
    b3 = ob(scene, "BOOM", r3)
    assert b3.data is not None and len(b3.data.vertices)
    assert animation.bake(scene, s.animations[0])["frames"] >= 1
    animation.clear_keys(scene)
    # a model update of a copy still works (its own STEP and import)
    reimport.update_model(bpy.context, r3, r3["fr_cache"])
    assert set(roots(scene)) == {"TEST.CRANE (2)", "TEST.CRANE (3)"} and len(s.joints) == 4


def test_a_subassembly_with_a_mechanism():
    """The four-bar's subassembly copied: its mechanism (and the drive joint it made) come along; driving the copy
    moves the copy's rocker, not the original's."""
    scene = _fresh(LINKS)
    s = scene.fresing
    crank = ob(scene, "FOURBAR.CRANK.ASM")
    linkages.create(scene, "FOURBAR", [[ob(scene, "FOURBAR.COUPLER.ASM")], [ob(scene, "FOURBAR.ROCKER.ASM")], [crank]],
                    base=ob(scene, "FOURBAR.BASE.ASM"), drive=crank)
    update()
    asm = ob(scene, "FOURBAR.ASM")
    p = copy.paste(scene, [asm])
    assert p["mechanisms"] == 1 and p["joints"] == 1 and not p["notes"], p
    assert len(s.mechanisms) == 2 and all(linkages.is_valid(m) for m in s.mechanisms)
    m2 = s.mechanisms[1]
    r2 = roots(scene)["FOURBAR.ASM (2)"]
    j2 = linkages.input_joint(scene, m2)
    j1 = linkages.input_joint(scene, s.mechanisms[0])
    assert j2 is not None and j2.name != j1.name and j2.name.endswith("(2)")
    rock1, rock2 = ob(scene, "FOURBAR.ROCKER.ASM", roots(scene)["TEST.LINKAGES"]), ob(scene, "FOURBAR.ROCKER.ASM", r2)
    w1, w2 = rock1.matrix_world.copy(), rock2.matrix_world.copy()
    joints.set_value(j2, math.radians(30.0))
    update()
    assert _close(w1, rock1.matrix_world) and not _close(w2, rock2.matrix_world)
    joints.set_value(j1, math.radians(-20.0))
    update()
    assert not _close(w1, rock1.matrix_world)


def test_a_hose_between_two_copied_parts_follows_the_copy():
    """The hoses model copied: its hoses come along on the copied parts and bend with the copy's own joint."""
    scene = _fresh(HOSES)
    s = scene.fresing
    flex.set_up_test_hoses(scene)
    n = len(s.flex)
    root = build.model_roots(scene)[0]
    p = copy.paste(scene, [root])
    assert p["hoses"] == n and p["cylinders"] == 1 and p["joints"] == 2, p
    assert len(s.flex) == 2 * n
    r2 = bpy.data.objects[p["roots"][0]]
    names2 = {o.name for o in logic.descendants(r2)}
    new = list(s.flex)[n:]
    assert all(it.part is not None and it.part.name in names2 and it.a_part.name in names2 and it.b_part.name in names2
               for it in new)
    assert all(it.name.endswith("(2)") for it in new)
    assert all(not flex.broken(scene, it) for it in s.flex)
    assert all(it.part.modifiers.get(flex.MOD) is not None for it in new)
    old = list(s.flex)[:n]
    shapes_old = [flex.shape_now(scene, it) for it in old]
    shapes_new = [flex.shape_now(scene, it) for it in new]
    joints.set_value(joints.find(scene, "Luff (2)"), math.radians(-12.0))
    update()
    flex.refresh(scene, force=True) if "force" in flex.refresh.__code__.co_varnames else flex.refresh(scene)
    update()
    moved = [flex.shape_now(scene, it) for it in new]
    still = [flex.shape_now(scene, it) for it in old]
    import numpy as np
    assert any(float(np.abs(np.asarray(a) - np.asarray(b)).max()) > 1e-3 for a, b in zip(shapes_new, moved))
    assert all(float(np.abs(np.asarray(a) - np.asarray(b)).max()) < 1e-6 for a, b in zip(shapes_old, still))


def test_the_operators_keys_and_menu(crane):
    """Copy remembers the selection, Paste makes the copy, selects and unlocks it for Place; Ctrl+C / Ctrl+V are the
    app's outside Full access; the right-click menu lists Copy and Paste here; the Client view refuses."""
    scene = crane
    root = roots(scene)["TEST.CRANE"]
    select(scene, root)
    assert not bpy.ops.fresing.paste.poll()
    assert bpy.ops.fresing.copy() == {"FINISHED"}
    assert copy.CLIP["names"] == [root.name] and "Copied 'TEST.CRANE'" in scene.fresing.last_message
    assert copy.CLIP["scene"] == scene.name
    assert bpy.ops.fresing.paste.poll()
    assert bpy.ops.fresing.paste() == {"FINISHED"}
    r2 = roots(scene)["TEST.CRANE (2)"]
    assert bpy.context.view_layer.objects.active is r2 and r2.select_get() and not place.locked(r2)
    assert place.target(bpy.context) is r2 and not place.refused(bpy.context)
    from fresing_render.blender import ui_place
    note = ui_place.copy_note(r2)
    assert note and note[0].startswith("Copied 'TEST.CRANE (2)': 20 parts, 2 joints, 1 cylinder")
    # Place moves the copy (its joints along)
    j = joints.find(scene, "Boom (2)")
    o0, _d = joints.axis_world(j)
    place.move(scene, [r2], Matrix.Translation((0.0, 2.0, 0.0)))
    update()
    assert abs((joints.axis_world(j)[0] - o0).y - 2.0) < 1e-5
    binds = {(k, key, tuple(sorted(m.items()))): op for k, _sp, key, m, op, _p in lock.APP_KEYS}
    assert binds[("Object Mode", "C", (("ctrl", True),))] == "fresing.copy_key"
    assert binds[("Object Mode", "V", (("ctrl", True),))] == "fresing.paste_key"
    assert "Copy" in context_menu.ON_PART and "Paste here" in context_menu.ON_PART and "Paste" in context_menu.ON_EMPTY
    assert "Copy" in context_menu.CLIENT_DROPS and "Paste here" in context_menu.CLIENT_DROPS
    workspaces.switch(scene, "Client view")
    try:
        assert lock.ON[0] and not bpy.ops.fresing.copy.poll() and not bpy.ops.fresing.paste.poll()
    finally:
        workspaces.switch(scene, "All functions")
    # a new project forgets what was copied (the same names there are other objects)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    assert not copy.CLIP["names"] and not ops_copy.can_paste(bpy.context.scene)


def test_labels_and_logos_come_along(crane):
    from fresing_render.blender import decals
    scene = crane
    s = scene.fresing
    c = s.callouts.add()
    c.text, c.part = "Boom", ob(scene, "BOOM")
    root = roots(scene)["TEST.CRANE"]
    p = copy.paste(scene, [root])
    assert p["labels"] == 1 and len(s.callouts) == 2
    r2 = bpy.data.objects[p["roots"][0]]
    assert s.callouts[1].text == "Boom" and s.callouts[1].part is ob(scene, "BOOM", r2)
    assert s.callouts[0].part is ob(scene, "BOOM", root)
    assert decals.sync is not None


PATHS = os.path.join(DATA, "test_paths_a.step")


@pytest.mark.parametrize("winch", [False, True])
def test_a_cable_read_from_cad_comes_along_with_its_drum(winch):
    """Task 0374 (0293's open point): the cable paths model copied whole – its wire rope (read from CAD) comes along,
    read again on the copied parts: its own speed joint, the copy's sheaves turn with it, the original's stay with the
    original; with ``winch`` the winch drum (4 Motion > Drums and carousels) comes along too. A cable into the sea or a
    drawn one would stay and be said (``copy._cable_stays``)."""
    import numpy as np

    from fresing_render.blender import paths, spool
    scene = _fresh(PATHS)
    s = scene.fresing
    paths.set_up_test_model(scene, winch=winch)
    root = build.model_roots(scene)[0]
    orig = paths.find(scene, "Wire rope")
    n_contacts = len(orig.contacts)
    p = copy.paste(scene, [root])
    assert p["cables"] == 1 and p["drums"] == (1 if winch else 0), p
    assert not [x for x in p["left"] if "Cable" in x or "Drum" in x], p["left"]
    assert any("1 cable" in line for line in copy.summary(p))
    assert len(s.cables) == 2
    new = paths.find(scene, "Wire rope (2)")
    assert new is not None and paths.broken(scene, new) == ""
    r2 = bpy.data.objects[p["roots"][0]]
    names2 = {o.name for o in logic.descendants(r2)}
    assert new.part.name in names2 and new.joint and new.joint != orig.joint
    assert len(new.contacts) == n_contacts
    turning = [c for c in new.contacts if c.kind in ("SHEAVE", "ROLLER")]
    assert turning and all(c.part.name in names2 for c in new.contacts if c.part is not None)
    for c in turning:                               # the copy's sheaves turn with the copy's cable …
        j = joints.find(scene, c.joint)
        assert j is not None and j.follows == new.joint, (c.name, j.follows)
    for c in paths.find(scene, "Wire rope").contacts:   # … the original's with the original's
        if c.kind in ("SHEAVE", "ROLLER") and c.made_joint:
            assert joints.find(scene, c.joint).follows == orig.joint
    if winch:
        sp = [it for it in s.spools if it.cable == new.name]
        assert len(sp) == 1 and sp[0].part.name in names2
    # the copy's cable lies on the copy: as far from the original's as the copy stands from the original
    a, b = np.array(paths.shape_now(scene, paths.find(scene, "Wire rope"))), np.array(paths.shape_now(scene, new))
    shift = np.array(r2.matrix_world.translation) - np.array(root.matrix_world.translation)
    assert np.linalg.norm(shift) > 0.5
    assert abs(np.linalg.norm(b.mean(axis=0) - a.mean(axis=0)) - np.linalg.norm(shift)) < 0.05
    # paying out the copy's cable moves only the copy's
    joints.set_value(joints.find(scene, new.joint), 0.5)
    update()
    paths.refresh(scene) if hasattr(paths, "refresh") else None
    update()
    a2 = np.array(paths.shape_now(scene, paths.find(scene, "Wire rope")))
    assert float(np.abs(a2 - a).max()) < 1e-6
