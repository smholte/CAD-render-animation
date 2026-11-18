"""8 Lifting plan in the app (task 0201): placing a crane from the library, two cranes, Remove, poses, the set-up's
chart, the load with its mass and CoG, Hook to here, the readout, first use and the workspace. Blender as a Python
module."""

from __future__ import annotations

import math
import os

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")

import fresing_render  # noqa: E402
from fresing_render.core import functions as F  # noqa: E402
from fresing_render.core import lifting, lifting_load as LD, lifting_reach as LR, workspaces as W  # noqa: E402
from fresing_render.lifting_model import classes as C  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "fresing_render", "data")
CRANE = os.path.join(DATA, "test_crane_a.step")
MACHINE = os.path.join(DATA, "test_machine.step")


def _mods():
    if not hasattr(bpy.types.Scene, "fresing"):
        fresing_render.register()
    from fresing_render.blender import lifting as BL
    return BL


def _new(step=None, out=None):
    BL = _mods()
    bpy.ops.wm.read_homefile(use_empty=True)
    from fresing_render.blender import workspaces
    workspaces.use_all(bpy.context.scene)
    sc = bpy.context.scene
    sc.fresing.out_folder = out or "/tmp/fr_lifting_test"
    if step:
        assert bpy.ops.fresing.import_step(filepath=step, quality="draft") == {"FINISHED"}
    BL.forget()
    return bpy.context.scene


def _item(name):
    return os.path.join(DATA, "lifting", name)


def _counts(sc):
    s = sc.fresing
    return {"objects": len(bpy.data.objects), "meshes": len(bpy.data.meshes), "joints": len(s.joints),
            "cylinders": len(s.cylinders), "poses": len(s.poses), "cables": len(s.cables), "tracks": len(s.tracks)}


def _check_poses(BL, sc, c):
    """For every pose of the file: the hook block where the maker's kinematics put it."""
    lay = C.layout(c.item_name)
    for p in BL.pose_names(c):
        assert BL.apply_pose(sc, c, p)
        vals = BL.values(sc, c)
        want = BL.to_world(c, C.hook_point(lay, vals))
        got = BL._hook_block_world(sc, c)
        assert np.linalg.norm(got - want) < 0.005, (c.name, p)
        assert np.linalg.norm(BL.hook_world(sc, c) - want) < 1e-6


@pytest.mark.parametrize("name", ["AT-40", "KB-20"])
def test_place_rigs_the_crane_as_its_maker_says(name):
    BL = _mods()
    sc = _new(CRANE)
    c = BL.place(bpy.context, _item(name), (12.0, -3.0, 0.0), math.radians(30))
    assert c.name == name and c.builtin and c.root is not None and c.chart_hash.startswith("sha256:")
    own = BL.own_joints(sc, c)
    assert len(own) == len(BL.item_at(c.item_path).data["rig"]["joints"])
    assert all(j.name.startswith(name + " · ") for j in own)
    M = np.array(c.root.matrix_world)
    assert np.allclose(M[:3, 3], (12.0, -3.0, 0.0), atol=1e-6)
    assert abs(BL.heading_of(c) - math.radians(30)) < 1e-6
    _check_poses(BL, sc, c)


def test_two_cranes_in_one_project_and_remove_leaves_nothing():
    BL = _mods()
    sc = _new(CRANE)
    before = _counts(sc)
    a = BL.place(bpy.context, _item("AT-40"), (12.0, 0.0, 0.0), 0.0)
    mid = _counts(sc)
    b = BL.place(bpy.context, _item("AT-40"), (-14.0, 0.0, 0.0), math.pi)
    assert (a.name, b.name) == ("AT-40", "AT-40 2")
    names = [j.name for j in sc.fresing.joints]
    assert len(names) == len(set(names))
    # a pose of one crane moves only that crane
    BL.apply_pose(sc, a, "Working")
    vb = BL.values(sc, b)
    assert all(abs(v) < 1e-6 for v in vb.values())
    BL.apply_pose(sc, b, "Long reach")
    assert abs(BL.values(sc, a)["Luff"] - 60.0) < 1e-4
    _check_poses(BL, sc, b)
    # Hook to here moves the active crane only
    sc.fresing.lifting.crane_index = 0
    va = BL.values(sc, a)
    assert BL.hook_to(sc, b, (-20.0, 2.0, 3.0)).ok
    assert BL.values(sc, a) == va
    hb = BL._hook_block_world(sc, b)
    assert np.linalg.norm(hb - np.array((-20.0, 2.0, 3.0))) < 0.005
    BL.remove(sc, b)
    assert _counts(sc) == mid
    assert not any(j.name.startswith("AT-40 2") for j in sc.fresing.joints)
    BL.remove(sc, a)
    assert _counts(sc) == before
    assert len(sc.fresing.lifting.cranes) == 0


def test_hook_to_here_out_of_reach_leaves_the_crane():
    BL = _mods()
    sc = _new(CRANE)
    c = BL.place(bpy.context, _item("AT-40"), (12.0, 0.0, 0.0), 0.0)
    BL.apply_pose(sc, c, "Working")
    v0 = BL.values(sc, c)
    a = BL.hook_to(sc, c, (300.0, 0.0, 1.0))
    assert not a.ok and "further out" in a.reason and sc.fresing.lifting.message == a.reason
    assert BL.values(sc, c) == v0


def test_readout_is_crane_use_and_the_next_safer_chart():
    BL = _mods()
    sc = _new(CRANE)
    c = BL.place(bpy.context, _item("AT-40"), (12.0, 0.0, 0.0), 0.0)
    BL.apply_pose(sc, c, "Working")
    c.counterweight = 6.0                   # between the file's 4 t and 8 t
    c.spread_from_pose = True               # the Working pose has the outriggers full out: 6 m
    ld = BL.new_box(sc, (1.0, 1.0, 1.0), 2.5, location=(16.0, 0.0, 0.0))
    ld.contingency = 1.1
    ro = BL.readout(sc, c, ld)
    assert ro.chart.config["counterweight"] == 4000.0 and ro.chart.config["outriggers"] == 6.0
    assert "next safer" in ro.chart_note
    rig = BL.rig_of(c)
    r, _z = rig.radius_height(BL.values(sc, c))
    ref = lifting.crane_use(2500.0 * 1.1, r, ro.chart, hook_block=BL.hook_block_kg(c))
    assert ro.use == pytest.approx(ref.use) and ro.status == ref.status and ro.words == ref.words
    assert ro.gross == pytest.approx(2750.0 + 450.0)
    # cached: the same object until something changes
    assert BL.readout(sc, c, ld) is ro
    ld.mass_t = 3.0
    assert BL.readout(sc, c, ld) is not ro


def test_a_changed_equipment_file_is_noticed(tmp_path):
    import json
    import shutil
    BL = _mods()
    sc = _new(CRANE)
    folder = tmp_path / "AT-40"
    shutil.copytree(_item("AT-40"), folder)
    c = BL.place(bpy.context, str(folder), (12.0, 0.0, 0.0), 0.0)
    assert BL.file_changed(c) == ""
    js = folder / "AT-40.json"
    d = json.loads(js.read_text(encoding="utf-8"))
    d["charts"][0]["capacity"] = [None if x is None else round(0.9 * x, 3) for x in d["charts"][0]["capacity"]]
    js.write_text(json.dumps(d), encoding="utf-8")
    os.utime(js, (os.path.getatime(js), os.path.getmtime(js) + 5))
    assert "changed since" in BL.file_changed(c)


def _occ_volume_centroid(step):
    """The whole STEP's volume (mm³) and centre (mm) by OpenCascade."""
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPControl import STEPControl_Reader
    r = STEPControl_Reader()
    assert r.ReadFile(step) == IFSelect_RetDone
    r.TransferRoots()
    shape = r.OneShape()
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, props)
    c = props.CentreOfMass()
    return props.Mass(), np.array([c.X(), c.Y(), c.Z()])


def test_cog_of_a_test_model_is_opencascades():
    """The whole test machine as a load, one density: its volume and CoG within 1 % of OpenCascade's."""
    pytest.importorskip("OCP")
    BL = _mods()
    sc = _new(MACHINE)
    from fresing_render.blender import build
    root = build.model_roots(sc)[0]
    ld = BL.new_load(sc, [root], "Machine")
    for d in ld.densities:
        d.density = 7850.0
    BL.refresh_load(sc, ld)
    vol_mm3, c_mm = _occ_volume_centroid(MACHINE)
    vol = ld.volume
    assert vol == pytest.approx(vol_mm3 * 1e-9, rel=0.01)
    want = np.array(root.matrix_world @ __import__("mathutils").Vector(c_mm / 1000.0))
    size = float(np.linalg.norm(np.array(sc.fresing.bounds_max) - np.array(sc.fresing.bounds_min)))
    assert np.linalg.norm(BL.cog_world(ld) - want) < 0.01 * size
    assert ld.volume_mass == pytest.approx(vol * 7850.0, rel=1e-6)
    assert not ld.open_parts


def test_load_rules_box_by_hand_and_gross():
    BL = _mods()
    sc = _new(CRANE)
    from fresing_render.blender import build, logic
    root = build.model_roots(sc)[0]
    boom = next(o for o in logic.descendants(root) if o.get(build.PROP_NAME) == "BOOM.ASM")
    ld = BL.new_load(sc, [boom], "Boom")
    with pytest.raises(ValueError, match="one load only"):
        BL.new_load(sc, [boom])
    part = next(o for o in logic.descendants(boom) if o.type == "MESH")
    with pytest.raises(ValueError, match="one load only"):
        BL.new_load(sc, [part])
    with pytest.raises(ValueError):
        BL.new_load(sc, [])
    # the marker rides with the load
    c0 = BL.cog_world(ld)
    assert c0 is not None and not BL.cog_by_hand(ld)
    # by hand
    bpy.ops.fresing.lifting_load_select(index=0)
    assert bpy.ops.fresing.lifting_cog_move(offset=(0.1, 0.0, 0.0)) == {"FINISHED"}
    assert BL.cog_by_hand(ld)
    assert np.linalg.norm(BL.cog_world(ld) - c0 - np.array((0.1, 0, 0))) < 1e-6
    BL.refresh_load(sc, ld)                    # Work out again keeps a marker set by hand
    assert BL.cog_by_hand(ld)
    assert bpy.ops.fresing.lifting_cog_back() == {"FINISHED"}
    assert not BL.cog_by_hand(ld) and np.linalg.norm(BL.cog_world(ld) - c0) < 1e-6
    # mass: volume x density vs entered; contingency
    ld.mass_mode = "VOLUME"
    m, src = BL.load_mass(sc, ld)
    assert m == pytest.approx(ld.volume_mass) and "estimate" in src
    ld.mass_mode = "ENTERED"
    ld.mass_t = 2.0
    ld.source = "WEIGHED"
    assert BL.load_mass(sc, ld) == (2000.0, "weighed")
    g = LD.gross(2000.0, 1.25, 450.0)
    assert g.total == pytest.approx(2500.0 + 450.0)
    # a box
    bx = BL.new_box(sc, (2.0, 1.0, 0.5), 3.0, location=(5.0, 5.0, 0.0))
    assert bx.kind == "BOX" and BL.load_mass(sc, bx)[0] == 3000.0
    assert np.allclose(BL.cog_world(bx), (5.0, 5.0, 0.25), atol=1e-6)
    assert BL.load_top(bx) == pytest.approx(0.5)
    above = BL.above_load(sc, bx)
    assert np.allclose(above, (5.0, 5.0, 0.5 + bx.clearance))
    n = len(bpy.data.objects)
    BL.remove_load(sc, bx)
    assert len(bpy.data.objects) == n - 2          # the box and its marker


def test_example_of_tour_and_pc_check():
    BL = _mods()
    sc = _new(CRANE)
    c, ld, a = BL.set_up_example(bpy.context)
    assert a.ok, a.reason
    assert "crane use" in BL.check_example(sc)


def test_first_use_needs_the_tick(monkeypatch):
    BL = _mods()
    from fresing_render.blender import prefs
    fake = type("Prefs", (), {"lifting_understood": False})()
    monkeypatch.setattr(prefs, "get", lambda: fake)
    monkeypatch.delenv(BL.ENV_UNDERSTOOD, raising=False)
    monkeypatch.setattr(BL, "_SKIP_FIRST_USE", [False])
    assert BL.understood() is True                       # Blender as a module runs in the background
    assert BL.understood(background=False) is False
    BL.set_understood(True)
    assert fake.lifting_understood and BL.understood(background=False) is True
    fake.lifting_understood = False
    monkeypatch.setenv(BL.ENV_UNDERSTOOD, "1")           # tests and the app's own projects
    assert BL.understood(background=False) is True


def test_workspace_tab_and_client_view():
    from fresing_render.core import places
    assert list(places.SECTIONS)[-1] == "FRESING_PT_lifting" and places.number_of("FRESING_PT_lifting_hook") == 8
    lift = W.builtin("lifting")
    hidden = W.hidden_panels(lift)
    for gone in ("FRESING_PT_cnc", "FRESING_PT_milling", "FRESING_PT_cables", "FRESING_PT_vessel_motion"):
        assert gone in hidden
    for shown in ("FRESING_PT_lifting", "FRESING_PT_lifting_equipment", "FRESING_PT_lifting_load",
                  "FRESING_PT_lifting_hook", "FRESING_PT_import", "FRESING_PT_structure", "FRESING_PT_looks",
                  "FRESING_PT_scene", "FRESING_PT_animation", "FRESING_PT_queue"):
        assert shown not in hidden, shown
    for key in ("client", "cnc", "offshore", "product", "education"):
        assert "FRESING_PT_lifting" in W.hidden_panels(W.builtin(key)), key
    for key in ("all", "full"):
        assert "FRESING_PT_lifting" not in W.hidden_panels(W.builtin(key))
    assert all(f.workspaces == ("lifting",) for f in F.FUNCTIONS.values() if f.family == "lifting")


def test_an_old_project_draws_the_empty_section():
    from test_blender import FakeLayout
    BL = _mods()
    from fresing_render.blender import ui_lifting
    sc = _new(CRANE)
    assert len(sc.fresing.lifting.cranes) == 0
    for cls in ui_lifting.CLASSES:
        errors = []
        fake = type("P", (), {"layout": FakeLayout(errors)})()
        cls.draw(fake, bpy.context)
        if hasattr(cls, "draw_header_preset"):
            cls.draw_header_preset(fake, bpy.context)
        assert errors == [], cls.__name__
    BL.set_up_example(bpy.context)
    for cls in ui_lifting.CLASSES:
        errors = []
        fake = type("P", (), {"layout": FakeLayout(errors)})()
        cls.draw(fake, bpy.context)
        assert errors == [], cls.__name__


def test_no_forbidden_words_in_the_panel_and_operators():
    import inspect
    from fresing_render.blender import lifting as BL, ops_lifting, ui_lifting
    for mod in (BL, ops_lifting, ui_lifting, LR, LD):
        src = inspect.getsource(mod)
        strings = " ".join(s for s in __import__("re").findall(r'"([^"\n]*)"', src))
        for w in lifting.FORBIDDEN_WORDS:
            assert f" {w.lower()} " not in f" {strings.lower()} ", (mod.__name__, w)
