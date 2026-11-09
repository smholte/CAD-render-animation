"""Task 0052: a model update keeps everything (bug hunt 0045 rows 1, 2, 6).

Row 1: joints, cylinders, mechanisms and way covers that link two models stay when either model is updated.
Row 2: labels and the camera's sharp spot follow their part to the new revision; the report names labels
whose part is gone.
Row 6: all or nothing: an update that fails (the new revision cannot be built, or a later step raises) leaves
the project as it was, with a clear message.
"""
import math
import os

import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from mathutils import Vector  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import (build, callouts, cameras, cylinders, decals, joints, linkages,  # noqa: E402
                                    reimport, states, waycover)

HERE = os.path.join(os.path.dirname(__file__), "data")
CRANE_A = os.path.join(HERE, "test_crane_a.step")
CRANE_B = os.path.join(HERE, "test_crane_b.step")
MACHINE = os.path.join(HERE, "test_machine.step")
LUFFER_A = os.path.join(HERE, "test_cylinder_a.step")
LUFFER_B = os.path.join(HERE, "test_cylinder_b.step")
LINKAGE_A = os.path.join(HERE, "test_linkage_a.step")
LINKAGE_B = os.path.join(HERE, "test_linkage_b.step")
WAYCOVER = os.path.join(HERE, "test_waycover_b.step")
TOL = 1e-5


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


def update():
    bpy.context.view_layer.update()
    bpy.context.view_layer.update()


def root_of(sc, name):
    return next(r for r in build.model_roots(sc) if r.get(build.PROP_NAME) == name)


def in_model(ob):
    return joints._root(ob).get(build.PROP_NAME)


def ob(sc, name, model=None, n=0):
    hits = [o for o in sc.objects if o.get(build.PROP_NAME) == name and (model is None or in_model(o) == model)]
    hits.sort(key=lambda o: o.get(build.PROP_UID))
    return hits[n]


def update_model(sc, path, model):
    """Like the button: the operator with ``update_root``. An error report comes back as {"CANCELLED"}."""
    try:
        res = bpy.ops.fresing.import_step(filepath=path, quality="draft", update_root=root_of(sc, model).name)
    except RuntimeError as exc:                 # bpy turns the operator's error report into an exception
        assert "Model update failed" in str(exc)
        res = {"CANCELLED"}
    update()
    return res


def notes(sc):
    return [n.text for n in sc.fresing.report_notes]


def boom_tip(sc):
    return ob(sc, "BOOM").matrix_world @ Vector((1.5, 0, 0))


# ---------------------------------------------------------------------------
# row 1: joints across two models
# ---------------------------------------------------------------------------

def crane_on_machine(tmp_path):
    """Crane A and the machine; the boom turns on the machine's frame (a joint across the two models)."""
    sc = load(tmp_path, CRANE_A, MACHINE)
    boom = ob(sc, "BOOM.ASM")
    j = joints.create(sc, "ROTATE", [boom], Vector((0.1, 0.3, 0.4)), Vector((0, 0, 1)), name="Slew",
                      base=ob(sc, "FRAME", "TEST.MACHINE"))
    joints.set_value(j, math.radians(20))
    update()
    return sc


def check_slew(sc, tip):
    j = joints.find(sc, "Slew")
    assert j is not None and joints.is_valid(j)
    assert [m.name for m in joints.members(j)] == [ob(sc, "BOOM.ASM").name]
    assert j.frame.parent is ob(sc, "FRAME", "TEST.MACHINE")
    assert math.degrees(joints.get_value(j)) == pytest.approx(20, abs=1e-6)
    assert (boom_tip(sc) - tip).length < TOL


def test_joint_across_two_models_survives_updating_its_base_model(tmp_path):
    sc = crane_on_machine(tmp_path)
    tip = boom_tip(sc).copy()
    boom = ob(sc, "BOOM.ASM")
    assert update_model(sc, MACHINE, "TEST.MACHINE") == {"FINISHED"}
    check_slew(sc, tip)
    assert ob(sc, "BOOM.ASM") is boom                      # the crane was not touched
    assert not notes(sc), notes(sc)


def test_joint_across_two_models_keeps_its_base_when_its_parts_are_updated(tmp_path):
    sc = crane_on_machine(tmp_path)
    tip = boom_tip(sc).copy()
    frame = ob(sc, "FRAME", "TEST.MACHINE")
    assert update_model(sc, CRANE_B, "TEST.CRANE") == {"FINISHED"}
    check_slew(sc, tip)
    assert ob(sc, "FRAME", "TEST.MACHINE") is frame
    assert not notes(sc), notes(sc)


def test_stack_across_two_models(tmp_path):
    """A crane joint riding on a machine joint: updating the machine rebuilds both, the crane's on top."""
    sc = load(tmp_path, CRANE_A, MACHINE)
    cover = ob(sc, "COVER.ASM")
    jm = joints.create(sc, "ROTATE", [cover], cover.matrix_world.translation, Vector((0, 0, 1)), name="Lid")
    jc = joints.create(sc, "SLIDE", [ob(sc, "BOOM.ASM")], Vector((0, 0, 0)), Vector((1, 0, 0)), name="Shift",
                       base=jm.motion)
    joints.set_value(jm, math.radians(10))
    joints.set_value(jc, 0.05)
    update()
    tip = boom_tip(sc).copy()
    assert update_model(sc, MACHINE, "TEST.MACHINE") == {"FINISHED"}
    jm, jc = joints.find(sc, "Lid"), joints.find(sc, "Shift")
    assert jm is not None and jc is not None and joints.rides_on(sc, jc).name == "Lid"
    assert math.degrees(joints.get_value(jm)) == pytest.approx(10, abs=1e-6)
    assert joints.get_value(jc) == pytest.approx(0.05, abs=1e-9)
    assert (boom_tip(sc) - tip).length < TOL
    assert not notes(sc), notes(sc)


def test_cylinder_across_two_models(tmp_path):
    """The luffer's barrel pin sits on the machine's frame."""
    sc = load(tmp_path, LUFFER_A, MACHINE)
    y = Vector((0, 1, 0))
    arm = joints.create(sc, "ROTATE", [ob(sc, "ARM.ASM")], Vector((0.1, 0.2, 0.6)), y, name="Luff")
    barrel = next(o for o in sc.objects if o.get(build.PROP_NAME) == "CYL.BARREL"
                  and (o.matrix_world.translation.y < 0.2 if o.type != "MESH" else True))
    rod = next(o for o in sc.objects if o.get(build.PROP_NAME) == "CYL.ROD" and o.parent is barrel.parent)
    frame = ob(sc, "FRAME", "TEST.MACHINE")
    c, _n = cylinders.create(sc, [barrel], [rod], (Vector((0.5, 0.0, 0.15)), y, frame),
                             (Vector((0.8, 0.4, 0.45)), -y, ob(sc, "ARM.ROD.PIN")), name="Lift")
    cylinders.set_mode(sc, c, "DRIVE")
    cylinders.set_stroke(sc, c, 0.09)
    update()
    angle = joints.get_value(arm)
    for path, model in ((MACHINE, "TEST.MACHINE"), (LUFFER_B, "TEST.LUFFER")):
        if model == "TEST.LUFFER":
            model = in_model(ob(sc, "ARM.ASM"))
        assert update_model(sc, path, model) == {"FINISHED"}
        c = cylinders.find(sc, "Lift")
        assert c is not None and cylinders.is_valid(c), notes(sc)
        assert c.frame.parent is ob(sc, "FRAME", "TEST.MACHINE")
        assert c.mode == "DRIVE"
        assert joints.get_value(joints.find(sc, "Luff")) == pytest.approx(angle, abs=1e-6)
        assert not notes(sc), notes(sc)


def test_mechanism_across_two_models(tmp_path):
    """The machine's signal lamp rides on the scissor lift's platform (part of that link)."""
    sc = load(tmp_path, LINKAGE_A, MACHINE)
    arms = [ob(sc, f"LIFT.ARM.{s}.{i}") for i in (1, 2, 3) for s in ("IN", "OUT")]
    lamp = ob(sc, "SIGNAL.LAMP")
    m = linkages.create(sc, "SCISSOR", [[a] for a in arms] + [[ob(sc, "LIFT.PLATFORM.ASM"), lamp]],
                        base=ob(sc, "LIFT.BASE.ASM"))
    name = m.name

    def lamp_z():
        return ob(sc, "SIGNAL.LAMP").matrix_world.translation.z

    def drive(deg):
        joints.set_value(linkages.input_joint(sc, linkages.find(sc, name)), math.radians(deg))
        update()

    drive(10)
    z10 = lamp_z()
    drive(20)
    z20 = lamp_z()
    assert z20 - z10 > 0.05
    for path, model in ((MACHINE, "TEST.MACHINE"), (LINKAGE_B, "TEST.LINKAGES")):
        assert update_model(sc, path, model) == {"FINISHED"}
        m = linkages.find(sc, name)
        assert m is not None and linkages.is_valid(m), notes(sc)
        assert ob(sc, "SIGNAL.LAMP") in linkages.all_link_objs(m)
        assert lamp_z() == pytest.approx(z20, abs=TOL)
        drive(10)
        assert lamp_z() == pytest.approx(z10, abs=TOL)
        drive(20)
        assert not [n for n in notes(sc) if "LAMP" not in n], notes(sc)


def test_way_cover_across_two_models(tmp_path):
    """The machine's cover rides on the way cover's carriage (the axis joint moves parts of both models)."""
    sc = load(tmp_path, WAYCOVER, MACHINE)
    carriage = next(o for o in sc.objects if o.get(build.PROP_NAME, "").split(" v")[0] == "CARRIAGE")
    j = joints.create(sc, "SLIDE", [carriage], Vector((0.1, 0.15, 0.1)), Vector((1, 0, 0)), name="X axis")
    joints.add_members(sc, j, [ob(sc, "COVER.ASM")])
    j.use_limits = True
    j.slide_min, j.slide_max = 0.0, 0.5
    c = waycover.settings(sc)
    c.axis = "X axis"
    c.total = 0.5
    groups = [["COVER.1.PLATE", "COVER.1.FLANGE"], ["COVER.2"], ["COVER.3.PLATE", "COVER.3.FLANGE"], ["COVER.4"],
              ["COVER.5"]]
    for g in groups:
        waycover.add_section(sc, [next(o for o in sc.objects if o.get(build.PROP_NAME, "").split(" v")[0] == n)
                                  for n in g])
    built, problems = waycover.make(sc)
    assert built == 5 and not problems

    def sec5_x():
        o = next(o for o in sc.objects if o.get(build.PROP_NAME, "").split(" v")[0] == "COVER.5")
        return o.matrix_world.translation.x

    joints.set_value(joints.find(sc, "X axis"), 0.0)
    update()
    x0 = sec5_x()
    cover_x0 = ob(sc, "COVER.ASM").matrix_world.translation.x
    wc_model = in_model(carriage)
    for path, model in ((MACHINE, "TEST.MACHINE"), (WAYCOVER, wc_model)):
        assert update_model(sc, path, model) == {"FINISHED"}
        assert all(waycover.is_made(sc, s) for s in c.sections), notes(sc)
        assert not notes(sc), notes(sc)
        joints.set_value(joints.find(sc, "X axis"), 0.5)
        update()
        assert sec5_x() - x0 == pytest.approx(0.5, abs=2e-5)             # the last section goes all the way
        assert ob(sc, "COVER.ASM").matrix_world.translation.x - cover_x0 == pytest.approx(0.5, abs=2e-5)
        joints.set_value(joints.find(sc, "X axis"), 0.0)
        update()


# ---------------------------------------------------------------------------
# row 2: labels and the sharp spot
# ---------------------------------------------------------------------------

def bolt_at(sc, x, y):
    return next(o for o in build.iter_parts(sc) if o[build.PROP_NAME].startswith("ISO 4017")
                and (o.matrix_world.translation - Vector((x, y, 0.1))).length < 1e-3)


def camera(sc):
    cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    sc.collection.objects.link(cam)
    cam.location = (4, -4, 3)
    return cam


def test_labels_and_sharp_spot_follow_their_parts(tmp_path):
    sc = load(tmp_path, CRANE_A)
    j = joints.create(sc, "ROTATE", [ob(sc, "BOOM.ASM")], Vector((0.1, 0.3, 0.4)), Vector((0, 0, 1)))
    joints.set_value(j, math.radians(30))
    update()
    boom = ob(sc, "BOOM")
    point = boom.matrix_world @ Vector((1.0, 0, 0.05))
    callouts.add(sc, boom, point, "Boom")
    gone = bolt_at(sc, 0.05, 0.05)                      # not in revision B
    callouts.add(sc, gone, gone.matrix_world.translation, "Bolt")
    cam = camera(sc)
    marker = cameras.set_focus(cam, sc, boom, point)
    update()
    assert update_model(sc, CRANE_B, "TEST.CRANE") == {"FINISHED"}
    s = sc.fresing
    new_boom = ob(sc, "BOOM")
    assert s.callouts[0].part is new_boom and callouts.usable(s.callouts[0])
    assert (callouts.anchor_world(s.callouts[0]) - point).length < TOL
    assert s.callouts[1].part is None
    assert [n for n in notes(sc) if n.startswith("Label 'Bolt'")], notes(sc)
    assert not [n for n in notes(sc) if "Boom" in n]
    con = marker.constraints[0]
    assert con.type == "CHILD_OF" and con.target is new_boom
    assert (marker.matrix_world.translation - point).length < TOL
    assert cameras.focus_label(cam) == "BOOM"


def test_sharp_spot_on_a_gone_part_stays_where_it_was(tmp_path):
    sc = load(tmp_path, CRANE_A)
    gone = bolt_at(sc, 0.05, 0.05)
    point = gone.matrix_world.translation + Vector((0, 0, 0.02))
    cam = camera(sc)
    marker = cameras.set_focus(cam, sc, gone, point)
    update()
    assert update_model(sc, CRANE_B, "TEST.CRANE") == {"FINISHED"}
    assert not marker.constraints
    assert (marker.matrix_world.translation - point).length < TOL
    assert cameras.focus_label(cam) == "Picked spot"
    assert [n for n in notes(sc) if n.startswith("Sharp spot")], notes(sc)


# ---------------------------------------------------------------------------
# row 6: all or nothing
# ---------------------------------------------------------------------------

def snapshot(sc):
    s = sc.fresing
    return {
        "objects": sorted(o.name for o in bpy.data.objects),
        "meshes": sorted(m.name for m in bpy.data.meshes),
        "collections": sorted(c.name for c in bpy.data.collections),
        "roots": [r.name for r in build.model_roots(sc)],
        "joints": [(j.name, round(joints.get_value(j), 9), sorted(m.name for m in joints.members(j)),
                    j.frame.parent.name if j.frame.parent else None, joints.rides_on(sc, j).name
                    if joints.rides_on(sc, j) else None) for j in s.joints],
        "cylinders": [(c.name, c.mode, round(cylinders.length_now(c), 6)) for c in s.cylinders],
        "labels": [(c.text, c.part.name if c.part else None) for c in s.callouts],
        "sharp spots": sorted((o.name, [(c.type, c.target.name if c.target else None) for c in o.constraints],
                               tuple(round(x, 6) for x in o.matrix_world.translation), o.get(cameras.PROP_FOCUS_PART))
                              for o in bpy.data.objects if o.get(cameras.PROP_FOCUS)),
        "poses": [(p.name, sorted(x.uid for x in p.places)) for p in s.poses],
    }


def crane_with_work(tmp_path):
    sc = load(tmp_path, CRANE_A)
    jb = joints.create(sc, "ROTATE", [ob(sc, "BOOM.ASM")], Vector((0.1, 0.3, 0.4)), Vector((0, 0, 1)),
                       name="Slew")
    trolley = ob(sc, "TROLLEY.ASM")
    jt = joints.create(sc, "SLIDE", [trolley], trolley.matrix_world.translation, Vector((1, 0, 0)),
                       base=ob(sc, "BOOM.ASM"), name="Trolley")
    joints.set_value(jb, math.radians(20))
    joints.set_value(jt, 0.1)
    boom = ob(sc, "BOOM")
    callouts.add(sc, boom, boom.matrix_world.translation, "Boom")
    gone = bolt_at(sc, 0.05, 0.05)                      # not in revision B
    callouts.add(sc, gone, gone.matrix_world.translation, "Bolt")
    cameras.set_focus(camera(sc), sc, gone, gone.matrix_world.translation)
    cameras.set_focus(camera(sc), sc, boom, boom.matrix_world.translation)
    states.save_pose(sc, "Work")
    update()
    return sc


@pytest.mark.parametrize("where", ["build", "decals", "rebuild", "last"])
def test_failed_update_leaves_the_project_as_it_was(tmp_path, monkeypatch, where):
    sc = crane_with_work(tmp_path)
    before = snapshot(sc)
    tip = boom_tip(sc).copy()

    def boom(*_a, **_k):
        raise MemoryError("forced for the test")

    def once(module, name):
        """The step fails the first time (the update), works after (putting the old model back)."""
        real, calls = getattr(module, name), []

        def step(*a, **k):
            calls.append(1)
            if len(calls) == 1:
                boom()
            return real(*a, **k)
        monkeypatch.setattr(module, name, step)

    if where == "build":                       # half-way through building the new revision
        real, calls = build._new_mesh, []

        def new_mesh(*a, **k):
            calls.append(1)
            if len(calls) > 3:
                boom()
            return real(*a, **k)
        monkeypatch.setattr(build, "_new_mesh", new_mesh)
    elif where == "decals":                    # after the joints came apart, before anything is rebuilt
        once(decals, "carry_over")
    elif where == "rebuild":                   # joints rebuilt on the new model, mechanisms not yet
        once(linkages, "rebuild_from_specs")
    else:                                      # everything rebuilt on the new model, the old one not yet gone
        once(states, "remap_uids")
    assert update_model(sc, CRANE_B, "TEST.CRANE") == {"CANCELLED"}
    msg = sc.fresing.last_message
    assert msg.startswith("Model update failed") and "forced for the test" in msg
    assert ("Nothing was changed" in msg) if where == "build" else ("as it was before" in msg)
    assert snapshot(sc) == before
    assert (boom_tip(sc) - tip).length < TOL
    assert not any(o.get(build.PROP_NAME) == "BOOM.LAMP" for o in sc.objects)     # nothing of revision B
    monkeypatch.undo()
    # and the next try works
    assert update_model(sc, CRANE_B, "TEST.CRANE") == {"FINISHED"}
    assert (boom_tip(sc) - tip).length < TOL
    assert sc.fresing.callouts[0].part is ob(sc, "BOOM")


def test_failed_update_gives_cylinders_back(tmp_path, monkeypatch):
    sc = load(tmp_path, LUFFER_A)
    y = Vector((0, 1, 0))
    joints.create(sc, "ROTATE", [o for o in sc.objects if o.get(build.PROP_NAME) == "ARM.ASM"],
                  Vector((0.1, 0.2, 0.6)), y, name="Luff")
    barrel = sorted((o for o in sc.objects if o.get(build.PROP_NAME) == "CYL.BARREL"),
                    key=lambda o: o.get(build.PROP_UID))[0]
    rod = next(o for o in sc.objects if o.get(build.PROP_NAME) == "CYL.ROD" and o.parent is barrel.parent)
    c, _n = cylinders.create(sc, [barrel], [rod], (Vector((0.5, 0.0, 0.15)), y, ob(sc, "BASE.PIN")),
                             (Vector((0.8, 0.4, 0.45)), -y, ob(sc, "ARM.ROD.PIN")), name="Lift")
    cylinders.set_mode(sc, c, "DRIVE")
    cylinders.set_stroke(sc, c, 0.09)
    update()
    before = snapshot(sc)

    real, calls = waycover.after_joints_rebuilt, []

    def boom(*a, **k):                      # fails during the update, works when the old model gets it back
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("forced for the test")
        return real(*a, **k)
    monkeypatch.setattr(waycover, "after_joints_rebuilt", boom)
    assert update_model(sc, LUFFER_B, in_model(barrel)) == {"CANCELLED"}
    assert snapshot(sc) == before
    c = cylinders.find(sc, "Lift")
    assert cylinders.is_valid(c) and c.mode == "DRIVE"
    assert cylinders.stroke_now(sc, c) == pytest.approx(0.09, abs=1e-6)


def test_update_model_raises_update_failed(tmp_path, monkeypatch):
    """Called directly (scripts, the PC check): a damaged cache raises UpdateFailed and changes nothing."""
    sc = crane_with_work(tmp_path)
    before = snapshot(sc)
    bad = tmp_path / "bad_cache"
    bad.mkdir()
    (bad / "tree.json").write_text("{}")
    (bad / "meshes.npz").write_bytes(b"not a zip file")
    with pytest.raises(reimport.UpdateFailed, match="Nothing was changed"):
        reimport.update_model(bpy.context, root_of(sc, "TEST.CRANE"), str(bad))
    assert snapshot(sc) == before
