"""Set up a crane (task 0203) – the independent tester's cases, written from the brief (not from the author's tests).

Each test rigs a built-in crane's bare STEP (invented, public) through the set-up's own operators – the by-names
driver ``crane_example.rig`` a user's clicks stand for – and then does what a user may do next: pick a sub-assembly
together with one of its parts, make a joint twice, Remove and make it again, Flip, move the model before the set-up,
save under odd names, place the saved crane in the same project, paste odd charts, leave the chart out. Blender as a
Python module."""

from __future__ import annotations

import json
import math
import os

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")

import fresing_render  # noqa: E402
from fresing_render.core import lifting, lifting_library as LL, lifting_reach as LR  # noqa: E402
from fresing_render.core import lifting_setup as LS  # noqa: E402

from fresing_render.blender import crane_example as D  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIFT = os.path.join(ROOT, "fresing_render", "data", "lifting")
os.environ.setdefault("FRESING_LIFTING_UNDERSTOOD", "1")


@pytest.fixture(scope="module", autouse=True)
def registered():
    mine = not hasattr(bpy.types.Scene, "fresing")
    if mine:
        fresing_render.register()
    yield
    if mine:
        bpy.ops.wm.read_homefile(use_empty=True)
        fresing_render.unregister()


def _mods():
    from fresing_render.blender import joints, lifting as BL, lifting_rig_out as RO, setup_crane as SC
    return joints, BL, RO, SC


def _new(cls=None, before=None):
    from fresing_render.blender import workspaces
    bpy.ops.wm.read_homefile(use_empty=True)
    workspaces.use_all(bpy.context.scene)
    sc = bpy.context.scene
    sc.fresing.out_folder = "/tmp/fr_setup_crane_independent"
    _j, BL, _RO, SC = _mods()
    BL.forget()
    SC.forget()
    if cls:
        step = os.path.join(LIFT, cls, cls + ".step")
        assert bpy.ops.fresing.import_step(filepath=step, quality="normal") == {"FINISHED"}
        if before is not None:
            before(sc)
            bpy.context.view_layer.update()
    return sc


def _rigged(cls="AT-40", before=None, kind=""):
    sc = _new(cls, before)
    made = D.rig(sc, cls, kind_override=kind, check=False)
    return sc, made


def _press(op, **kw):
    return op("EXEC_DEFAULT", True, **kw)


def _refused(op, **kw) -> bool:
    """A button pressed that must refuse: an operator that reports an error raises in Python (the UI shows it)."""
    try:
        return op("EXEC_DEFAULT", True, **kw) == {"CANCELLED"}
    except RuntimeError:
        return True


def _red(sc, clash=False):
    _j, _BL, _RO, SC = _mods()
    assert _press(bpy.ops.fresing.crane_check, clash=clash) == {"FINISHED"}
    return [(p.step, p.text) for p in SC.settings(sc).problems if p.severity == "red"]


def _data(sc) -> dict:
    _j, _BL, RO, _SC = _mods()
    d = RO.build(sc)
    d.pop("_problems", None)
    return json.loads(json.dumps(d))


@pytest.fixture(scope="module")
def lib(tmp_path_factory):
    return str(tmp_path_factory.mktemp("own_cranes"))


# ---------------------------------------------------------------------------------------------------------------------
# picking parts

def test_a_name_that_fits_several_parts_is_refused_in_words():
    """'WINCH STAND' is the name of two parts: picking it by name says so, and Make makes nothing."""
    joints, _BL, _RO, SC = _mods()
    sc = _new("AT-40")
    _press(bpy.ops.fresing.crane_setup, kind="CRANE_MOBILE")
    n0 = len(sc.fresing.joints)
    _press(bpy.ops.fresing.crane_pick, names="WINCH STAND")
    objs, bad = SC.objects_of(sc, SC.settings(sc).pick)
    assert not objs and bad and "2 parts" in bad[0]
    SC.settings(sc).axes.add()
    SC.settings(sc).axis_index = 0
    assert _press(bpy.ops.fresing.crane_make, role="slew") == {"CANCELLED"}
    assert len(sc.fresing.joints) == n0


def test_a_subassembly_and_its_own_part_picked_together_move_as_one():
    """The superstructure and one of its own parts (the turntable) picked together for the slew: turned 30°, the part
    turns with the superstructure once – not twice – or the pick is refused."""
    joints, _BL, _RO, SC = _mods()
    sc = _new("AT-40")
    _press(bpy.ops.fresing.crane_setup, kind="CRANE_MOBILE")
    root = SC.model_root(sc)
    by = SC.lookup(root)
    tt = by["TURNTABLE"][0]
    sup = by["SUPERSTRUCTURE.ASM"][0]
    tt0 = np.array(tt.matrix_world)
    sup0 = np.array(sup.matrix_world)
    _press(bpy.ops.fresing.crane_pick, names="SUPERSTRUCTURE.ASM | TURNTABLE")
    _press(bpy.ops.fresing.crane_axes, role="slew")
    slew = next(j for j in D.builtin("AT-40")["rig"]["joints"] if j["name"] == "Slew")
    D._choose_axis(sc, root, slew["point"], slew["direction"], True)
    res = _press(bpy.ops.fresing.crane_make, role="slew")
    if res != {"FINISHED"}:
        return                                                  # refused: fine
    j = SC.first(sc, "slew")
    joints.set_value(j, math.radians(30.0))
    bpy.context.view_layer.update()
    bpy.context.view_layer.update()
    o, d = joints.axis_world(j)
    from mathutils import Matrix, Vector
    R = Matrix.Translation(Vector(o)) @ Matrix.Rotation(math.radians(30.0), 4, Vector(d)) @ \
        Matrix.Translation(-Vector(o))
    want = np.array(R) @ tt0
    got = np.array(tt.matrix_world)
    assert np.abs(got[:3, 3] - want[:3, 3]).max() < 1e-4, (got[:3, 3], want[:3, 3])
    assert np.abs(got[:3, :3] - want[:3, :3]).max() < 1e-5
    sw = np.array(sup.matrix_world)
    assert np.abs(sw[:3, 3] - (np.array(R) @ np.r_[np.array(sup0)[:3, 3], 1.0])[:3]).max() < 1e-4


# ---------------------------------------------------------------------------------------------------------------------
# making, removing, flipping

def test_making_the_slew_twice_is_refused_or_found_by_the_check():
    """A second slew joint on the same superstructure (the user pressed Make again): refused, or the Check names the
    slew step – never two slews that both turn the crane."""
    joints, _BL, _RO, SC = _mods()
    sc, _made = _rigged("AT-40")
    assert _red(sc) == []
    root = SC.model_root(sc)
    slew = next(j for j in D.builtin("AT-40")["rig"]["joints"] if j["name"] == "Slew")
    D._pick(slew["parts"])
    _press(bpy.ops.fresing.crane_axes, role="slew")
    D._choose_axis(sc, root, slew["point"], slew["direction"], True)
    res = _press(bpy.ops.fresing.crane_make, role="slew")
    if res != {"FINISHED"}:
        return
    slews = SC.with_role(sc, "slew", driven_only=True)
    if len(slews) <= 1:
        return
    got = _red(sc)
    assert any(k == "slew" for k, _t in got), (f"{len(slews)} slew joints and the Check is happy: {got}")


def test_remove_then_make_again_gives_the_same_crane():
    """Remove the slew of a finished set-up and make it again (same parts, axis, limits): the file is the built-in
    rig again – the luff (and all above it) ride on the new slew."""
    joints, _BL, _RO, SC = _mods()
    sc, made = _rigged("AT-40")
    root = SC.model_root(sc)
    assert _press(bpy.ops.fresing.crane_remove, joint=made["Slew"]) == {"FINISHED"}
    slew = next(j for j in D.builtin("AT-40")["rig"]["joints"] if j["name"] == "Slew")
    D._pick(slew["parts"])
    _press(bpy.ops.fresing.crane_axes, role="slew")
    D._choose_axis(sc, root, slew["point"], slew["direction"], True)
    assert _press(bpy.ops.fresing.crane_make, role="slew") == {"FINISHED"}
    name = D._by_parts(sc, slew["parts"])
    D._limits(sc, name, slew["limits"])
    made["Slew"] = name
    got = _data(sc)
    assert D.compare("AT-40", got, made) == []
    assert _red(sc) == []


def test_flip_against_the_role_is_found_by_the_check():
    """Flip on the luff joint makes + lower the boom (the role says + = boom up): the Check names the luff step (the
    file would give Hook to here and the chart a boom angle that runs the wrong way)."""
    joints, _BL, _RO, SC = _mods()
    sc, made = _rigged("AT-40")
    luff = joints.find(sc, made["Luff"])
    assert SC.sense_ok(sc, "luff", luff)
    assert _press(bpy.ops.fresing.crane_flip, joint=made["Luff"]) == {"FINISHED"}
    assert not SC.sense_ok(sc, "luff", joints.find(sc, made["Luff"]))
    got = _red(sc)
    assert any(k == "luff" for k, _t in got), f"the luff now lowers the boom with +, and the Check says {got}"


# ---------------------------------------------------------------------------------------------------------------------
# the model moved before the set-up

def _turn_and_move(sc):
    from mathutils import Matrix
    _j, _BL, _RO, SC = _mods()
    from fresing_render.blender import build
    root = build.model_roots(sc)[0]
    root.matrix_world = Matrix.Translation((12.0, -7.0, 0.5)) @ Matrix.Rotation(math.radians(90.0), 4, "Z") \
        @ root.matrix_world


def test_a_model_turned_and_moved_before_the_setup_gives_the_builtin_rig():
    """The crane's root turned 90° and moved 12 m before the set-up: the file is still in the STEP's own frame – the
    same joints, hook point and Check as the crane left where it was imported."""
    _j, _BL, _RO, _SC = _mods()
    sc, made = _rigged("AT-40", before=_turn_and_move)
    assert _red(sc) == []
    assert D.compare("AT-40", _data(sc), made) == []


def _y_up(sc):
    """Make the project's model as a STEP drawn with Y up would import: the root turned 90° about X (the importer's
    ``logic.set_up_axis``), the crane standing where it stood – the model frame now has Y up."""
    from mathutils import Matrix
    from fresing_render.blender import build, logic
    root = build.model_roots(sc)[0]
    Rx = Matrix.Rotation(math.radians(-90.0), 4, "X")
    for ch in list(root.children):
        w = ch.matrix_world.copy()
        ch.matrix_basis = Rx @ ch.matrix_basis
        for key in (build.PROP_CAD_BASIS, build.PROP_REST_BASIS):
            if key in ch:
                build.set_mat(ch, key, Rx @ build.get_mat(ch, key) if hasattr(build, "get_mat") else ch.matrix_basis)
        ch["_w"] = [float(x) for x in np.array(w, float).ravel()]
    logic.set_up_axis(root, "Y")
    bpy.context.view_layer.update()
    for ch in root.children:
        assert np.allclose(np.array(ch.matrix_world).ravel(), ch["_w"], atol=1e-5)
        del ch["_w"]


def test_a_crane_drawn_with_y_up_has_its_support_on_the_ground():
    """A crane STEP drawn with Y up: its outriggers' support area lies in the level plane (x, z of the file) – the
    crane's CoG at rest is inside it, as for the same crane drawn with Z up."""
    _j, _BL, RO, SC = _mods()
    sc = _new("AT-40", before=_y_up)
    assert RO.up_axis(SC.model_root(sc)) == "Y"
    # the by-names driver reads the built-in (Z up) file: rig by its numbers turned into the Y-up frame
    data = D.builtin("AT-40")
    Rm = np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]], float)      # Z-up model -> Y-up model (x, z, -y)
    for j in data["rig"]["joints"]:
        j["point"] = list(Rm @ np.asarray(j["point"], float))
        j["direction"] = list(Rm @ np.asarray(j["direction"], float))
    data["rig"]["hook"]["point"] = list(Rm @ np.asarray(data["rig"]["hook"]["point"], float))
    for k in data["cog"]:
        data["cog"][k] = list(Rm @ np.asarray(data["cog"][k], float))
    orig, need = D.builtin, D._need
    D.builtin = lambda cls: json.loads(json.dumps(data))
    # the driver's own guard reads x, y as the level plane (Z up): the hook point is typed right after it anyway
    D._need = lambda ok, what: None if "hook point" in what else need(ok, what)
    try:
        D.rig(sc, "AT-40", check=False)
    finally:
        D.builtin, D._need = orig, need
    d = _data(sc)
    assert d["rig"]["up_axis"] == "Y"
    fp = LS.footprint(d)
    area = 0.5 * abs(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(fp, fp[1:] + fp[:1])))
    ref = LS.footprint(D.builtin("AT-40"))
    ref_area = 0.5 * abs(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(ref, ref[1:] + ref[:1])))
    assert area == pytest.approx(ref_area, rel=0.05), (fp, ref)
    assert [p.text for p in LS.cog_problems(d)] == []


def test_flipping_the_telescope_is_found_by_the_check():
    """Flip on the telescope makes + slide the sections into the boom base (the role says + = out): the Check – with
    its clash check, as the button runs it – must name the telescope step."""
    joints, _BL, _RO, SC = _mods()
    sc, made = _rigged("AT-40")
    assert _press(bpy.ops.fresing.crane_flip, joint=made["Telescope"]) == {"FINISHED"}
    assert not SC.sense_ok(sc, "telescope", joints.find(sc, made["Telescope"]))
    got = _red(sc, clash=True)
    assert any(k == "telescope" for k, _t in got), f"+ now pulls the sections in, and the Check says {got}"


# ---------------------------------------------------------------------------------------------------------------------
# the set-up and other cranes in the same project; projects opened again

def test_the_setup_keeps_its_crane_when_another_is_placed(lib):
    """Save, then try it at once: Place the saved crane in the same project. The set-up still knows its own crane
    (its steps, ticks, Check and Save do not fall back to 'First the crane's model')."""
    _j, BL, RO, SC = _mods()
    sc, _made = _rigged("AT-40")
    root = SC.model_root(sc)
    path = RO.save(sc, os.path.join(lib, "same_project"))
    BL.place(bpy.context, path, location=(0.0, 40.0, 0.0), heading=0.0)
    assert SC.model_root(sc) == root, "the set-up lost its crane once a second model is in the project"
    got = _red(sc)
    assert not any(k == "model" for k, _t in got), got


def test_a_project_opened_again_finds_its_parts(tmp_path):
    """The set-up's name list is a cache: after the project is saved and opened again (another project with the same
    crane has the same names and counts) picking by name must give the opened project's parts, not removed ones."""
    _j, _BL, _RO, SC = _mods()
    sc = _new("AT-40")
    _press(bpy.ops.fresing.crane_setup, kind="CRANE_MOBILE")
    SC.objects_of(sc, "SUPERSTRUCTURE.ASM")             # fills the cache
    path = str(tmp_path / "crane setup.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    objs, bad = SC.objects_of(sc, "SUPERSTRUCTURE.ASM")  # a step's button, the Set-up window still open
    assert not bad
    try:
        name = objs[0].name
    except ReferenceError as exc:
        pytest.fail(f"the set-up handed out a removed object after the project was opened again: {exc}")
    assert objs[0] == bpy.data.objects[name]


# ---------------------------------------------------------------------------------------------------------------------
# the hook block

def _no_wrappers(sc):
    """The hook block straight under the boom head (no HOOK SWING.ASM round it), as many makers draw it."""
    from fresing_render.blender import build
    root = build.model_roots(sc)[0]
    blk = next(o for o in root.children_recursive if o.get(build.PROP_NAME) == "HOOK BLOCK.ASM")
    head = next(o for o in root.children_recursive if o.get(build.PROP_NAME) == "BOOM SECTION 4.ASM")
    w = blk.matrix_world.copy()
    blk.parent = head
    blk.matrix_parent_inverse.identity()
    blk.matrix_basis = head.matrix_world.inverted() @ w
    for key in (build.PROP_CAD_BASIS, build.PROP_REST_BASIS):
        if key in blk:
            build.set_mat(blk, key, blk.matrix_basis)
    bpy.context.view_layer.update()
    assert np.allclose(np.array(blk.matrix_world), np.array(w), atol=1e-6)


def test_a_hook_block_without_wrappers_still_hangs_plumb(lib):
    """No sub-assembly round the hook block: the hook swing joints move nothing, but the hoist rides on them – the
    file's hook hangs plumb at every boom angle, Check is happy, and the placed crane's hook block hangs plumb."""
    joints, BL, RO, SC = _mods()
    sc, made = _rigged("AT-40", before=_no_wrappers)
    swing = SC.with_role(sc, "swing")
    assert swing, "no hook swing joint"
    d = _data(sc)
    rig = LR.Rig(d)
    for luff in (0.0, 30.0, 60.0, 82.0):
        v = {rig.role["luff"]: luff, rig.role["tele"]: 3000.0}
        D_ = rig.hook_dir(v)
        assert np.degrees(np.arccos(np.clip(-D_ @ rig.up, -1, 1))) < 0.1, (luff, D_)
    assert [p.text for p in LS.sweep(d)] == []
    assert _red(sc) == []
    path = RO.save(sc, os.path.join(lib, "no_wrappers"))
    sc = _new()
    c = BL.place(bpy.context, path)
    BL.apply_pose(sc, c, "Working")
    bpy.context.view_layer.update()
    root = c.root
    blk = next(o for o in root.children_recursive if o.get("fr_name") == "HOOK BLOCK.ASM")
    R = np.array(blk.matrix_world)[:3, :3]
    assert np.abs(R - np.eye(3)).max() < 1e-3, "the placed hook block does not hang plumb"


# ---------------------------------------------------------------------------------------------------------------------
# Save

@pytest.mark.parametrize("name, folder", [("Kran 40/2: Ø \"neu\"?", "Kran 40_2_ Ø _neu__"), ("CON", "CON_"),
                                          ("  trailing dots...  ", "trailing dots")])
def test_save_with_a_name_that_is_no_folder_name(lib, name, folder):
    """Names Windows cannot use as a folder are made usable; the saved crane reads back without problems and its
    STEP sits next to it."""
    _j, _BL, RO, SC = _mods()
    sc, _made = _rigged("AT-40")
    SC.settings(sc).name = name
    lib2 = os.path.join(lib, "names")
    assert _press(bpy.ops.fresing.crane_save, library=lib2) == {"FINISHED"}, SC.settings(sc).message
    path = SC.settings(sc).saved_path
    assert os.path.basename(os.path.dirname(path)) == folder
    item = LL.read_item(path)
    assert item.ok, item.problems
    assert os.path.isfile(item.model)


def test_save_twice_overwrites_and_reads_back(lib):
    _j, _BL, RO, SC = _mods()
    sc, _made = _rigged("AT-40")
    lib2 = os.path.join(lib, "twice")
    assert _press(bpy.ops.fresing.crane_save, library=lib2) == {"FINISHED"}
    p1 = SC.settings(sc).saved_path
    SC.settings(sc).hook_block_t = 0.7
    assert _press(bpy.ops.fresing.crane_save, library=lib2) == {"FINISHED"}
    p2 = SC.settings(sc).saved_path
    assert p1 == p2
    item = LL.read_item(p2)
    assert item.ok, item.problems
    assert item.data["hook_blocks"][0]["mass"] == pytest.approx(0.7)
    assert sorted(os.listdir(os.path.dirname(p2))) == sorted(
        [os.path.basename(p2), os.path.basename(item.model)]), os.listdir(os.path.dirname(p2))


def test_save_refused_in_words(lib):
    """No hook yet, the built-in folder, a library inside the built-ins: refused with a sentence, nothing written."""
    _j, _BL, RO, SC = _mods()
    sc = _new("AT-40")
    _press(bpy.ops.fresing.crane_setup, kind="CRANE_MOBILE")
    assert _refused(bpy.ops.fresing.crane_save, library=os.path.join(lib, "no_hook"))
    assert "hook" in SC.settings(sc).message.lower()
    assert not os.path.exists(os.path.join(lib, "no_hook"))
    before = {d: sorted(os.listdir(os.path.join(LL.BUILTIN_DIR, d))) for d in os.listdir(LL.BUILTIN_DIR)}
    sc, _made = _rigged("AT-40")
    for bad in (LL.BUILTIN_DIR, os.path.join(LL.BUILTIN_DIR, "AT-40"),
                LL.BUILTIN_DIR + os.sep + ".." + os.sep + "lifting"):
        assert _refused(bpy.ops.fresing.crane_save, library=bad)
        assert SC.settings(sc).message
    after = {d: sorted(os.listdir(os.path.join(LL.BUILTIN_DIR, d))) for d in os.listdir(LL.BUILTIN_DIR)}
    assert after == before


# ---------------------------------------------------------------------------------------------------------------------
# no chart

def _no_chart(sc):
    _j, _BL, _RO, SC = _mods()
    SC.settings(sc).charts.clear()


def test_no_chart_check_says_not_checked():
    """Without a chart the Check says 'Not checked – no chart' (amber), nothing red about the chart."""
    _j, _BL, _RO, SC = _mods()
    sc, _made = _rigged("AT-40")
    _no_chart(sc)
    assert _red(sc) == []
    amb = [p.text for p in SC.settings(sc).problems if p.severity == "amber"]
    assert any("Not checked" in t and "no chart" in t for t in amb), amb


def test_no_chart_placed_crane_use_is_not_checked_grey(lib):
    """An own crane saved without its chart is placed and moved, and the crane use says 'Not checked – no chart'
    (grey) – never a red 'Over entered limit' and never 'within limits'."""
    _j, BL, RO, SC = _mods()
    sc, _made = _rigged("AT-40")
    _no_chart(sc)
    path = RO.save(sc, os.path.join(lib, "no_chart"))
    assert LL.read_item(path).ok
    sc = _new()
    c = BL.place(bpy.context, path)
    BL.apply_pose(sc, c, "Working")
    BL.forget()
    ro = BL.readout(sc, c)
    assert not isinstance(ro, str), ro
    assert ro.use is None
    assert ro.status == lifting.NOT_CHECKED, (ro.status, ro.words, ro.reason)
    assert "no chart" in (ro.words + " " + ro.reason).lower()


# ---------------------------------------------------------------------------------------------------------------------
# the chart: pasted CSV -> the typed table -> the file keeps what was pasted

CSVS = {
    "decimal commas and gaps": "boom 10,8 m; counterweight 4 t\nradius (m);capacity (t)\n3;20,5\n4,5;16\n6;-\n8;9,25\n",
    "units in cells": "boom 30 m\n3 m;12000 kg\n5 m;9 t\n7 m;6500 kg\n",
    "feet and pounds": "boom 100 ft\nradius (ft);capacity (lb)\n10;20000\n20;12000\n30;7000\n",
    "one row": "boom 12 m\n4;3\n",
    "configs that differ only by the jib": "boom 30 m\n4;10\n8;6\nboom 30 m; jib 9 m\n6;3\n10;2\n",
    "a configuration with only a jib": "boom 30 m\n4;10\n8;6\njib 9 m\n6;3\n10;2\n",
    "precise numbers": "boom 23.456 m\n3.1234567;11.234567\n7.7654321;5.4321098\n",
}


@pytest.mark.parametrize("key", list(CSVS))
def test_pasted_chart_reaches_the_file_as_pasted(key):
    """What Paste CSV accepted reaches the saved file unchanged (configurations, radii, capacities, gaps) – the
    typed table in between must not change a configuration or a number."""
    _j, _BL, _RO, SC = _mods()
    sc = _new("KB-20")
    _press(bpy.ops.fresing.crane_setup, kind="CRANE_OTHER")
    text = CSVS[key]
    want = LL.chart_csv(text, "t", "m")
    assert want.ok, want.errors
    assert _press(bpy.ops.fresing.crane_chart_csv, paste=True, text=text) == {"FINISHED"}
    got = SC.chart_dicts(sc)
    exp = want.dicts("t", "m")
    assert len(got) == len(exp), (got, exp)
    for g, e in zip(got, exp):
        assert g["config"] == pytest.approx(e["config"], rel=1e-6), (g["config"], e["config"])
        assert g["radius"] == pytest.approx(e["radius"], rel=1e-5)     # the table keeps 6 digits
        assert [x is None for x in g["capacity"]] == [x is None for x in e["capacity"]]
        assert [x or 0 for x in g["capacity"]] == pytest.approx([x or 0 for x in e["capacity"]], rel=1e-5)


def test_typed_table_with_bad_cells_is_refused_by_row():
    _j, _BL, _RO, SC = _mods()
    sc = _new("KB-20")
    _press(bpy.ops.fresing.crane_setup, kind="CRANE_OTHER")
    _press(bpy.ops.fresing.crane_chart_add)
    c = SC.settings(sc).charts[0]
    c.boom = 8.0
    c.rows[0].radius, c.rows[0].capacity = "2", "5 t"
    for r, cap in (("3,5", "4"), ("5", "zwei"), ("6", "0")):
        row = c.rows.add()
        row.radius, row.capacity = r, cap
    e = SC.chart_entry(sc)
    assert not e.ok
    assert any("Row 3" in m for m in e.errors) and any("Row 4" in m for m in e.errors), e.errors
    assert SC.chart_dicts(sc) == []


# ---------------------------------------------------------------------------------------------------------------------
# masses: the crane's centre of gravity outside its support; the support where the pads stand

def test_cog_outside_the_footprint_is_red_and_leads_to_masses():
    _j, _BL, _RO, SC = _mods()
    sc, _made = _rigged("AT-40")
    g = next(g for g in SC.settings(sc).groups if g.key == "counterweight")
    g.mass_t = 80.0
    g.cog_by_hand = True
    g.cog = (-9.0, 0.0, 2.0)
    got = _red(sc)
    assert any(k == "masses" and "outside" in t for k, t in got), got
    assert _press(bpy.ops.fresing.crane_go, key="masses") == {"FINISHED"}
    keys = [k for k, *_r in SC.STEP_LISTS[sc.fresing.setup_kind]]
    assert keys[sc.fresing.setup_step] == "masses"


def _pad_centres(sc, root, by):
    from fresing_render.blender import build
    _j, _BL, _RO, SC = _mods()
    out = {}
    for corner in ("FL", "FR", "RL", "RR"):
        mn, mx = build.world_bounds([by[f"JACK PAD {corner}"][0]])
        out[corner] = SC.to_model(root, (np.asarray(mn) + np.asarray(mx)) / 2.0)[:2] / 1000.0
    return out


def _near(fp, pads, v):
    """Each pad at a corner of the support: across (the spread) within 5 cm; along within 0.3 m (the file's 'a' is
    the jack assembly's middle, a little inside the pad – the built-in file says the same)."""
    for corner, c in pads.items():
        k = int(np.argmin(np.linalg.norm(fp - c, axis=1)))
        assert abs(fp[k][1] - c[1]) < 0.05 and abs(fp[k][0] - c[0]) < 0.3, (corner, v, c, fp)


def test_outrigger_footprint_matches_the_pads():
    """The support area the file says (outriggers: a, b_in, stages x the joint) lies where the jack pads stand, with
    the beams in, half out and out."""
    joints, _BL, _RO, SC = _mods()
    sc, made = _rigged("AT-40")
    d = _data(sc)
    root = SC.model_root(sc)
    by = SC.lookup(root)
    for v in (0.0, 0.3, 0.7725):
        joints.set_value(joints.find(sc, made["Outriggers"]), v)
        bpy.context.view_layer.update()
        bpy.context.view_layer.update()
        fp = np.array(LS.footprint(d, {made["Outriggers"]: v * 1000.0}))
        _near(fp, _pad_centres(sc, root, by), v)


def test_one_stage_corners_give_the_footprint_of_their_pads():
    """A crane whose outriggers have one beam stage per corner (the user picks one stage and the jack): the file's
    support area at full stroke lies where the pads stand."""
    joints, _BL, _RO, SC = _mods()
    sc, made = _rigged("AT-40")
    for n in ("Outriggers", "Jacks"):
        assert _press(bpy.ops.fresing.crane_remove, joint=made[n]) == {"FINISHED"}
    assert not SC.with_role(sc, "outrigger") and not SC.with_role(sc, "jack")
    cs = SC.settings(sc)
    for corner in ("FL", "FR", "RL", "RR"):
        cs.stroke, cs.jack_stroke = 1.2, 0.372
        D._pick([f"OUTRIGGER BEAM {corner}.ASM", f"JACK {corner}.ASM"])
        assert _press(bpy.ops.fresing.crane_corner) == {"FINISHED"}, cs.message
    lead = next(j for j in SC.with_role(sc, "outrigger") if not j.follows)
    d = _data(sc)
    assert d["outriggers"]["stages"] == 1
    root = SC.model_root(sc)
    by = SC.lookup(root)
    joints.set_value(lead, 1.2)
    bpy.context.view_layer.update()
    bpy.context.view_layer.update()
    fp = np.array(LS.footprint(d, {lead.name: 1200.0}))
    _near(fp, _pad_centres(sc, root, by), 1.2)


# ---------------------------------------------------------------------------------------------------------------------
# telescope sections picked outermost first

def test_telescope_sections_picked_in_the_wrong_order():
    """The sections picked 4, 3, 2 (outermost first): the made telescope still moves the boom head as the built-in's
    (sections riding on each other, sharing the stroke), or the step refuses in words."""
    joints, _BL, _RO, SC = _mods()
    sc, made = _rigged("AT-40")
    ref = LR.Rig(D.builtin("AT-40"))
    tele = joints.find(sc, made["Telescope"])
    assert _press(bpy.ops.fresing.crane_remove, joint=made["Telescope"]) == {"FINISHED"}
    lead = next(j for j in D.builtin("AT-40")["rig"]["joints"] if j["name"] == "Telescope")
    D._pick(["BOOM SECTION 4.ASM", "BOOM SECTION 3.ASM", "BOOM SECTION 2.ASM"])
    cs = SC.settings(sc)
    _press(bpy.ops.fresing.crane_axes, role="telescope")
    D._choose_axis(sc, SC.model_root(sc), lead["point"], lead["direction"], False)
    cs.stroke = lead["limits"][1] / 1000.0
    try:
        res = _press(bpy.ops.fresing.crane_make, role="telescope", chain=True)
    except RuntimeError:                                    # refused with an error the user reads: fine
        return
    if res != {"FINISHED"}:
        return
    assert tele is not None and len(SC.with_role(sc, "telescope")) == 3
    d = _data(sc)
    # the hook made again: the swing followed the luff, its frame rode on section 4 – check the reach chain only
    mine = LR.Kinematics(d)
    tn = next(j["name"] for j in d["rig"]["joints"] if j.get("role") == "telescope" and not j.get("follows"))
    head = np.array(D.builtin("AT-40")["rig"]["hook"]["point"], float)
    s4 = next(j["name"] for j in d["rig"]["joints"] if j.get("parts") == ["BOOM SECTION 4.ASM"])
    for e in (0.0, 2000.0, 7733.0):
        want = ref.moved("Telescope 4", head, {"Telescope": e, "Luff": 40.0})
        got = mine.moved(s4, head, {tn: e, made["Luff"]: 40.0})
        assert np.linalg.norm(got - want) < 1.0, (e, got, want)


# ---------------------------------------------------------------------------------------------------------------------
# removing a joint others hang on; numbers typed the European way

def test_removing_the_luff_after_the_hook_is_found_in_words():
    """The luff removed after the hook was made (its hook swing follows it and goes too; the hoist rode on that
    swing): the Check and Save say what to do in words – no traceback, nothing saved."""
    _j, _BL, RO, SC = _mods()
    sc, made = _rigged("AT-40")
    assert _press(bpy.ops.fresing.crane_remove, joint=made["Luff"]) == {"FINISHED"}
    got = _red(sc)
    assert any(k in ("luff", "hook_block") for k, _t in got), got
    with pytest.raises((RO.RigError, LL.LibraryError, RuntimeError)) as e:
        RO.save(sc, os.path.join(str(bpy.app.tempdir or "/tmp"), "fr_removed_luff_lib"))
    assert type(e.value).__name__ in ("RigError", "LibraryError") and str(e.value)


@pytest.mark.parametrize("typed, want", [("0; 4,5; 9", [0.0, 4.5, 9.0]), ("0 t, 4 t, 8 t", [0.0, 4.0, 8.0]),
                                         ("0, 4, 8", [0.0, 4.0, 8.0])])
def test_counterweight_steps_typed_as_a_user_types_them(typed, want):
    """'Steps, t' in the Counterweight step: a decimal comma (allowed everywhere else in the set-up) or a unit after
    each number must not change the steps the file gets."""
    _j, _BL, _RO, SC = _mods()
    sc, _made = _rigged("AT-40")
    SC.settings(sc).counterweight_steps = typed
    got = _data(sc)["limits"].get("counterweight_steps")
    assert got == pytest.approx(want), (typed, got)
