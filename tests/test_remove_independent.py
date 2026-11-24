"""Remove (task 0292) tried by an independent tester who did not write it: dangling references, what the window says
against what really goes, set-ups that live on a part that goes, two models, a model update after a remove, save and
reopen. Blender as a module (no undo stack: undo / redo are not tested here).

Tests marked ``# FINDING n`` failed when they were written (task 0292's independent test); the report lists them."""

import os
import types

import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import (animation, build, joints, lesson, lock, logic, ops_place, place,  # noqa: E402
                                    reimport, remove, states, workspaces)

DATA = os.path.join(os.path.dirname(__file__), "data")
CRANE = os.path.join(DATA, "test_crane_a.step")
HOSES = os.path.join(DATA, "test_flex_hoses_a.step")
LINKAGE = os.path.join(DATA, "test_linkage_a.step")
PATHS = os.path.join(DATA, "test_paths_a.step")
SPOOL = os.path.join(DATA, "test_spool.step")


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def _import(path, fresh=True):
    if fresh:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        addon_utils.enable("cycles", default_set=True)
    assert bpy.ops.fresing.import_step(filepath=path, quality="draft") == {"FINISHED"}
    return bpy.context.scene


@pytest.fixture()
def crane():
    scene = _import(CRANE)
    workspaces.switch(scene, "All functions")
    lesson.run(scene, "crane")
    yield scene


def ob(scene, name, root=None):
    return next(o for o in scene.objects if o.get(build.PROP_NAME) == name
                and (root is None or build.model_root_of(o) == root))


def _uids():
    return {str(o.get(build.PROP_UID)) for o in bpy.data.objects if o.get(build.PROP_UID)}


def dangling(scene) -> list:
    """Every part-ID field in scene.fresing (any depth) that names a part no longer there (a "gone:" ID is fine), every
    object pointer to an object in no scene, every object in no scene, every "FR removing" collection left over."""
    uids = _uids()
    in_scene = {o.name for s in bpy.data.scenes for o in s.objects}
    bad = []

    def rec(pg, path, depth=0):
        if depth > 6:
            return
        for p in pg.bl_rna.properties:
            k = p.identifier
            if k in ("rna_type", "name"):
                continue
            try:
                v = getattr(pg, k)
            except Exception:  # noqa: BLE001
                continue
            if p.type == "STRING" and k.endswith("uid") and v:
                bad.extend(f"{path}.{k}={x!r}" for x in str(v).split("\n")
                           if x and not x.startswith("gone:") and x not in uids)
            elif p.type == "POINTER":
                if isinstance(v, bpy.types.Object):
                    if v.name not in in_scene:
                        bad.append(f"{path}.{k} -> {v.name}")
                elif isinstance(v, bpy.types.PropertyGroup):
                    rec(v, f"{path}.{k}", depth + 1)
            elif p.type == "COLLECTION":
                for i, it in enumerate(v):
                    if isinstance(it, bpy.types.PropertyGroup):
                        rec(it, f"{path}.{k}[{i}]", depth + 1)

    rec(scene.fresing, "fresing")
    bad += [f"object in no scene: {o.name}" for o in bpy.data.objects if not o.users_scene]
    bad += [f"collection {c.name}" for c in bpy.data.collections if c.name.startswith("FR removing")]
    for j in scene.fresing.joints:
        if not joints.is_valid(j) or any(m.obj is None for m in j.members):
            bad.append(f"joint {j.name}")
    return bad


def reopen(tmp_path, name="r.blend"):
    path = str(tmp_path / name)
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    return bpy.context.scene


def steps_without_owner(scene) -> list:
    """Animation steps that name a joint / cylinder / mechanism that is not there any more."""
    s = scene.fresing
    have = {"JOINT": {j.name for j in s.joints}, "MOTOR": {j.name for j in s.joints},
            "CYLINDER": {c.name for c in s.cylinders}, "MECHANISM": {m.name for m in s.mechanisms}}
    field = {"JOINT": "joint", "MOTOR": "joint", "CYLINDER": "cylinder", "MECHANISM": "mechanism"}
    out = []
    for a in s.animations:
        for b in a.blocks:
            if b.kind in field:
                v = getattr(b, field[b.kind])
                if v and v not in have[b.kind]:
                    out.append((a.name, b.kind, v))
    return out


def _add_step(scene, kind, **index):
    s = scene.fresing
    s.animations_index = 0
    for k, v in index.items():
        setattr(s, k, v)
    assert bpy.ops.fresing.block_add(kind=kind) == {"FINISHED"}
    a = s.animations[0]
    return a.blocks[len(a.blocks) - 1]


def _scissor(scene):
    from fresing_render.blender import linkages
    arms = [ob(scene, f"LIFT.ARM.{s}.{i}") for i in (1, 2, 3) for s in ("IN", "OUT")]
    return linkages.create(scene, "SCISSOR", [[a] for a in arms] + [[ob(scene, "LIFT.PLATFORM.ASM")]],
                           base=ob(scene, "LIFT.BASE.ASM"))


# ---------------------------------------------------------------------------
# findings
# ---------------------------------------------------------------------------

def test_remove_a_model_with_a_slice(tmp_path):
    """FINDING 1: a Slice (section cut) on the whole model. Remove raised "A joint that moves nothing needs something to
    sit on" (section.after_model_update -> make_joint with the root gone) half way: joints and cylinders already
    dissolved, the model's 24 objects left in an "FR removing" collection in no scene, model_count still 1."""
    from fresing_render.blender import section
    scene = _import(CRANE)
    workspaces.switch(scene, "All functions")
    root = build.model_roots(scene)[0]
    section.add(scene, [("MODEL", root, "")])
    remove.remove(scene, [root])                                      # FINDING 1: raises RuntimeError
    assert not [o for o in scene.objects if o.get(build.PROP_KIND) in build.MODEL_KINDS]
    assert not dangling(scene), dangling(scene)
    assert not dangling(reopen(tmp_path))


def test_the_window_counts_a_cylinder_that_goes_with_its_pin_and_its_step_goes_too(crane):
    """FINDING 2: removing BOOM.LUFF.PIN (the part the luffing cylinder's rod pin is in; the same for BOOM.ASM) removes
    the cylinder ("Cylinder 'Luffing cylinder' removed: the part its rod's pin was in is gone"), but the plan says
    0 cylinders and nothing under "loses", and the cylinder's animation step stays, naming a cylinder that is gone."""
    scene = crane
    _add_step(scene, "CYLINDER", cylinders_index=0)
    pin = ob(scene, "BOOM.LUFF.PIN")
    p = remove.plan(scene, [pin])
    n0 = len(scene.fresing.cylinders)
    remove.remove(scene, [pin])
    gone = n0 - len(scene.fresing.cylinders)
    assert gone == 1
    assert not steps_without_owner(scene), steps_without_owner(scene)      # FINDING 2: the CYLINDER step stays
    assert p["cylinders"] == gone or any("Luffing cylinder" in x for x in p["loses"]), p   # FINDING 2: says 0


def test_a_mechanism_the_plan_lists_as_going_stays_but_loses_its_step():
    """FINDING 3: the scissor lift's platform subassembly (one of its links) goes. The plan says 1 mechanism and 1 step
    go; the rebuild keeps the mechanism ("1 part no longer in the model") – but its MECHANISM step was already taken
    off. The window says one thing, the project ends up with a mechanism whose animation step is lost."""
    scene = _import(LINKAGE)
    _scissor(scene)
    s = scene.fresing
    assert bpy.ops.fresing.anim_add() == {"FINISHED"}
    _add_step(scene, "MECHANISM", mechanisms_index=0)
    target = ob(scene, "LIFT.PLATFORM.ASM")
    p = remove.plan(scene, [target])
    remove.remove(scene, [target])
    kept = [x.name for x in s.mechanisms]
    assert p["mechanisms"] == 1 - len(kept), (p["mechanisms"], kept)          # FINDING 3: plan 1, mechanism stays
    if kept:
        assert any(b.kind == "MECHANISM" for b in s.animations[0].blocks), "the kept mechanism lost its step"


def test_a_mechanism_that_goes_takes_its_own_drive_joint():
    """FINDING 4: the scissor lift's base goes (or one arm): the mechanism cannot be rebuilt and is gone, but the drive
    joint the mechanism made for itself ('Scissor lift drive') stays and now moves LIFT.ARM.IN.1 alone. The
    mechanism's own Remove (linkages.remove) takes that joint along."""
    scene = _import(LINKAGE)
    m = _scissor(scene)
    drive = m.own_joint and joints.find(scene, "Scissor lift drive") is not None
    assert drive
    p = remove.plan(scene, [ob(scene, "LIFT.BASE.ASM")])
    assert p["mechanisms"] == 1
    remove.remove(scene, [ob(scene, "LIFT.BASE.ASM")])
    assert not len(scene.fresing.mechanisms)
    assert joints.find(scene, "Scissor lift drive") is None, [   # FINDING 4: the drive joint is left over
        (j.name, [x.name for x in joints.members(j)]) for j in scene.fresing.joints]


def test_the_window_says_what_only_loses_something(crane):
    """FINDING 5: what the plan lists under "loses" against what the rebuild then does. BOOM.ASM goes: the plan says
    nothing more, the result is "Joint 'Trolley': the part it sat on is gone; it now sits on its CAD parent" AND
    "Cylinder 'Luffing cylinder' removed" (FINDING 2's cylinder). The owner reads the window and does not learn that
    the trolley's joint moves to another part and that the cylinder goes."""
    scene = crane
    p = remove.plan(scene, [ob(scene, "BOOM.ASM")])
    text = " ".join(remove.lines(p))
    r = remove.remove(scene, [ob(scene, "BOOM.ASM")])
    assert any("Trolley" in n for n in r["notes"])
    assert "Trolley" in text, text                                    # FINDING 5
    assert "Luffing cylinder" in text or p["cylinders"] == 1, text    # FINDING 5 (and 2)


def test_a_hose_whose_end_fitting_goes_is_named_in_the_window():
    """FINDING 6: the hoses model; the fitting a hose's end sits on (FITTING VALVE C, end A of HYDRAULIC HOSE ARM) goes.
    The plan lists no hose and nothing under "loses", the result has no note, and the hose's end silently moves onto
    the model's root (a_part = TEST.FLEX.HOSES): it ends at a point no fitting holds."""
    from fresing_render.blender import flex
    scene = _import(HOSES)
    flex.set_up_test_hoses(scene)
    hose = scene.fresing.flex[0]
    end = hose.a_part
    assert end is not None and end != hose.part
    p = remove.plan(scene, [end])
    r = remove.remove(scene, [end])
    told = p["hoses"] or any(hose.name in x for x in p["loses"]) or any(hose.name in n for n in r["notes"])
    assert told, (p["hoses"], p["loses"], r["notes"],                  # FINDING 6
                  scene.fresing.flex[0].a_part and scene.fresing.flex[0].a_part.name)


def test_a_cable_over_a_sheave_that_goes_is_named_in_the_window():
    """FINDING 7 (same kind as 5): the paths model; WINCH DRUM (a contact of the cable 'Wire rope' and the member of the
    app-made joint 'WINCH DRUM rotate') goes. Plan: 0 cables and nothing under "loses" (the joint is counted). Result: the joint goes
    and the cable's first contact becomes a BEND ("the cable no longer runs over it")."""
    from fresing_render.blender import paths
    scene = _import(PATHS)
    paths.set_up_test_model(scene)
    # (task 0263: the drum holds wire now and the rope runs over WIRE ON DRUM: that is the part that goes)
    drum = ob(scene, "WIRE ON DRUM")
    p = remove.plan(scene, [drum])
    nj = len(scene.fresing.joints)
    r = remove.remove(scene, [drum])
    assert any("Wire rope" in n for n in r["notes"])
    assert not dangling(scene), dangling(scene)
    assert animation.bake(scene, scene.fresing.animations[0])["frames"] > 1
    assert p["joints"] == nj - len(scene.fresing.joints), (p["joints"], nj - len(scene.fresing.joints))
    assert any("Wire rope" in x for x in p["loses"]), p["loses"]                                         # FINDING 7


def test_a_drum_whose_coil_goes():
    """FINDING 8 (minor): the spool model; the CAD coil of the drum 'Drum' (WIRE ON DRUM) goes alone. The plan lists
    nothing, the result has no note; the spool stays with coil None and coil_uid still the removed part's ID (not
    "gone:"). The same for a Slice whose target part goes (cuts[].targets[].uid keeps the old ID)."""
    from fresing_render.blender import spool
    scene = _import(SPOOL)
    spool.set_up_test_model(scene)
    coil = scene.fresing.spools[0].coil
    assert coil is not None
    p = remove.plan(scene, [coil])
    r = remove.remove(scene, [coil])
    assert animation.bake(scene, scene.fresing.animations[0])["frames"] > 1
    assert p["spools"] or p["loses"] or r["notes"], "nothing said about the drum"     # FINDING 8
    assert not dangling(scene), dangling(scene)                                         # FINDING 8


def test_a_model_update_after_removing_a_subassembly_keeps_it_removed(crane, tmp_path):
    """FINDING 9 (a design question for the lead): TROLLEY.ASM removed, then 1 Import > Update model from the same
    cache: the trolley's 3 parts come back (17 -> 20 parts), without its joint. A Remove the owner meant is undone by
    the next model update, silently (no note)."""
    scene = crane
    remove.remove(scene, [ob(scene, "TROLLEY.ASM")])
    root = build.model_roots(scene)[0]
    assert logic.part_count(root) == 17
    out = reimport.update_model(bpy.context, root, root["fr_cache"])
    root = build.model_roots(scene)[0]
    assert not dangling(scene), dangling(scene)
    assert not dangling(reopen(tmp_path))
    scene = bpy.context.scene
    root = build.model_roots(scene)[0]
    assert logic.part_count(root) == 17 or out.get("notes"), logic.part_count(root)      # FINDING 9


def test_the_operator_with_names_that_are_no_model_says_nothing_to_remove(crane):
    """FINDING 10 (minor): fresing.remove(names=…) with an object that is not a model object (an empty in another
    scene) ran remove() with nothing chosen and FINISHED with "Removed  (0 parts). Ctrl+Z brings it back"."""
    s2 = bpy.data.scenes.new("Other")
    stranger = bpy.data.objects.new("Stranger", None)
    s2.collection.objects.link(stranger)
    assert bpy.ops.fresing.remove(names="Stranger") == {"CANCELLED"}       # FINDING 10: FINISHED


# ---------------------------------------------------------------------------
# what held (passed when written)
# ---------------------------------------------------------------------------

def test_remove_one_of_two_copies_keeps_the_other_whole(crane, tmp_path):
    """Two copies of the same STEP (shared-looking meshes, the second's part IDs scoped): the first goes, the second
    keeps every part with its mesh, and a joint across them (on copy A's boom, moving copy B's cover) stays and moves."""
    scene = crane
    _import(CRANE, fresh=False)
    a, b = build.model_roots(scene)
    cov = ob(scene, "COVER", b)
    joints.create(scene, "SLIDE", [cov], cov.matrix_world.translation.copy(), Vector((0, 0, 1)),
                  base=ob(scene, "BOOM.ASM", a), name="Across")
    p = remove.plan(scene, [a])
    assert p["joints"] == 2 and p["parts"] == 20
    remove.remove(scene, [a])
    parts = [o for o in scene.objects if o.get(build.PROP_KIND) == "part" and o.type == "MESH"]
    assert len(parts) == 20 and all(o.data is not None and len(o.data.polygons) for o in parts)
    j = joints.find(scene, "Across")
    assert j is not None and joints.is_valid(j) and [m.name for m in joints.members(j)] == [cov.name]
    w = cov.matrix_world.translation.copy()
    joints.set_value(j, 0.2)
    bpy.context.view_layer.update()
    assert abs((cov.matrix_world.translation - w).length - 0.2) < 1e-5
    assert scene.fresing.model_count == 1 and not dangling(scene)
    assert not dangling(reopen(tmp_path))


def test_removing_the_member_model_of_a_joint_across_models_takes_the_joint(crane):
    scene = crane
    _import(CRANE, fresh=False)
    a, b = build.model_roots(scene)
    cov = ob(scene, "COVER", b)
    joints.create(scene, "SLIDE", [cov], cov.matrix_world.translation.copy(), Vector((0, 0, 1)),
                  base=ob(scene, "BOOM.ASM", a), name="Across")
    p = remove.plan(scene, [b])
    remove.remove(scene, [b])
    assert "Across" in p["_joints"] and joints.find(scene, "Across") is None
    assert [j.name for j in scene.fresing.joints] == ["Boom", "Trolley"] and not dangling(scene)


def test_one_bolt_of_a_row_with_a_sticker_on_its_shared_mesh(crane, tmp_path):
    """Four bolts share one mesh with a sticker on every copy: one bolt goes with its decal object, the mesh and the
    sticker stay on the other three; save + reopen."""
    from fresing_render.blender import decals
    scene = crane
    bolts = [o for o in scene.objects if o.get(build.PROP_NAME) == "ISO 4762 M24 x 60 - 12.9"]
    assert len(bolts) == 4 and len({b.data.name for b in bolts}) == 1
    decals.add(bolts[0], 0, tuple(bolts[0].matrix_world.translation), (0, 0, 1), "STICKER", sticker="CE")
    assert len([o for o in scene.objects if o.get(build.PROP_KIND) == "decal"]) == 4
    p = remove.plan(scene, bolts[:1])
    assert p["parts"] == 1 and p["decals"] == 1
    remove.remove(scene, bolts[:1])
    left = [o for o in scene.objects if o.get(build.PROP_NAME) == "ISO 4762 M24 x 60 - 12.9"]
    assert len(left) == 3 and all(len(decals.items_of(o)) == 1 for o in left)
    assert len([o for o in scene.objects if o.get(build.PROP_KIND) == "decal"]) == 3
    assert logic.part_count(build.model_roots(scene)[0]) == 19 and not dangling(scene)
    assert not dangling(reopen(tmp_path))


def test_a_pose_and_saved_scenes_after_the_trolley_went(crane, tmp_path):
    scene = crane
    joints.set_value(joints.find(scene, "Trolley"), 0.3)
    states.save_pose(scene, "Out")
    states.reset_pose(scene)
    remove.remove(scene, [ob(scene, "TROLLEY.ASM")])
    assert states.apply_pose(scene, "Out")
    scene = reopen(tmp_path)
    assert not dangling(scene) and states.apply_pose(scene, "Out")
    assert animation.bake(scene, scene.fresing.animations[0])["frames"] > 1


def test_remove_a_built_animation_then_build_and_place(crane):
    """A built animation is taken off; Build again works; Place still moves what stays and Back to CAD puts it back."""
    scene = crane
    animation.bake(scene, scene.fresing.animations[0])
    remove.remove(scene, [ob(scene, "COVER")])
    assert not animation.has_keys(scene)
    assert animation.bake(scene, scene.fresing.animations[0])["frames"] > 1
    animation.clear_keys(scene)
    root = build.model_roots(scene)[0]
    ops_place.set_lock(root, False)
    w0 = ob(scene, "BOOM").matrix_world.copy()
    place.move(scene, [root], Matrix.Translation((1.0, 0.0, 0.0)))
    bpy.context.view_layer.update()
    assert abs(ob(scene, "BOOM").matrix_world.translation.x - w0.translation.x - 1.0) < 1e-5
    place.back_to_cad(scene, [root])
    assert not dangling(scene)


def test_remove_on_a_moving_vessel_keeps_the_other_model_on_its_place(tmp_path):
    """Vessel motion on (deck), two cranes, the frame not the first: the first goes, the second keeps its vessel
    constraint and its places at rest; save + reopen; a new import into the emptied project works."""
    from fresing_render.blender import vessel_motion as VM
    scene = _import(CRANE)
    _import(CRANE, fresh=False)
    s = scene.fresing
    s.background = "DECK"
    s.vessel.enabled = True
    bpy.context.view_layer.update()
    a, b = build.model_roots(scene)
    with VM.at_rest(scene):
        before = {o.name: o.matrix_world.translation.copy() for o in scene.objects if build.model_root_of(o) == b}
    scene.frame_set(120)
    remove.remove(scene, [a])
    assert b.constraints.get(VM.CON) is not None
    with VM.at_rest(scene):
        bpy.context.view_layer.update()
        moved = [n for n, t in before.items() if (bpy.data.objects[n].matrix_world.translation - t).length > 1e-5]
    assert not moved and not dangling(scene)
    scene = reopen(tmp_path)
    remove.remove(scene, build.model_roots(scene))
    assert not dangling(scene)
    _import(CRANE, fresh=False)
    assert len(build.model_roots(bpy.context.scene)) == 1


def test_the_client_view_refuses_remove_and_its_key(crane):
    scene = crane
    cover = ob(scene, "COVER")
    for o in scene.objects:
        o.select_set(False)
    cover.select_set(True)
    workspaces.switch(scene, "Client view")
    try:
        assert lock.ON[0]
        assert not bpy.ops.fresing.remove_key.poll() and not bpy.ops.fresing.remove.poll()
        with pytest.raises(RuntimeError):
            bpy.ops.fresing.remove(names=cover.name)
        assert cover.name in scene.objects
    finally:
        workspaces.switch(scene, "All functions")


def test_odd_selections(crane):
    """The same part twice, a camera, a joint empty, None: only the part counts; a root with its own child: the root."""
    scene = crane
    cov = ob(scene, "COVER")
    cam = next(o for o in scene.objects if o.type == "CAMERA")
    jm = joints.find(scene, "Boom").motion
    assert remove.plan(scene, [cov, cov, cam, jm, None])["objects"] == [cov.name]
    root = build.model_roots(scene)[0]
    p = remove.plan(scene, [ob(scene, "BOOM"), root])
    assert p["objects"] == [root.name] and p["models"] == 1 and p["parts"] == 20
    assert bpy.ops.fresing.remove(names="nothing\nnope") == {"CANCELLED"}
    ctx = types.SimpleNamespace(scene=scene, selected_objects=[cov, cam])
    assert remove.chosen(ctx.scene, ctx.selected_objects) == [cov]
