"""Independent tests of 8 Lifting plan in the app (task 0201), written from the brief by a tester who did not write the
code: Remove, two cranes, a crane turned / travelled, the readout's cache, loads (a sub-assembly and its own child, a
scaled part, an open mesh, a crane as a load), the CoG marker by hand through save + open, the panel's words and the
first-use gate. Blender as a Python module."""

from __future__ import annotations

import math
import os
import re

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")

import fresing_render  # noqa: E402
from fresing_render.core import lifting, lifting_reach as LR  # noqa: E402
from fresing_render.lifting_model import classes as C  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "fresing_render", "data")
CRANE = os.path.join(DATA, "test_crane_a.step")
FORBIDDEN = re.compile(r"\b(" + "|".join(re.escape(w) for w in lifting.FORBIDDEN_WORDS) + r")\b", re.I)


def _mods():
    if not hasattr(bpy.types.Scene, "fresing"):
        fresing_render.register()
    from fresing_render.blender import lifting as BL
    return BL


def _new(tmp_path, step=CRANE):
    BL = _mods()
    bpy.ops.wm.read_homefile(use_empty=True)
    from fresing_render.blender import workspaces
    workspaces.use_all(bpy.context.scene)
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path / "out")
    if step:
        assert bpy.ops.fresing.import_step(filepath=step, quality="draft") == {"FINISHED"}
    BL.forget()
    return bpy.context.scene


def _item(name):
    return os.path.join(DATA, "lifting", name)


def _part(sc, name):
    from fresing_render.blender import build, logic
    root = build.model_roots(sc)[0]
    return next(o for o in logic.descendants(root) if o.get(build.PROP_NAME) == name)


# ---------------------------------------------------------------------------------------------------------------------
# Remove leaves nothing behind

def test_remove_leaves_no_groups_or_collections_behind(tmp_path):
    """Placing a crawler crane and removing it again must leave the project as it was: no empty collection named after
    the crane, no Looks groups (and their materials) that only its parts used.

    FAULT: after Remove of a CC-100, its collection 'CC-100' (empty) and 20 groups ('Pulleys', 'Bearings', 'Colour
    #EDB214' …, all empty, shown in Looks) with their materials stay in the project."""
    BL = _mods()
    sc = _new(tmp_path)
    collections = {c.name for c in bpy.data.collections}
    groups = {g.name for g in sc.fresing.groups}
    c = BL.place(bpy.context, _item("CC-100"), (30.0, 5.0, 0.0), 0.5)
    BL.remove(sc, c)
    left_c = sorted({c.name for c in bpy.data.collections} - collections)
    left_g = sorted({g.name for g in sc.fresing.groups} - groups)
    assert not left_c and not left_g, f"left behind: collections {left_c}, groups {left_g}"


# ---------------------------------------------------------------------------------------------------------------------
# a crane turned, placed off the origin, travelled

def test_hook_to_here_on_a_turned_crawler_that_has_travelled(tmp_path):
    """CC-100 placed at (30, 5, 0) turned by 0.5 rad, travelled 7 m, slewed 20°: Hook to here on a world point the
    maker's kinematics reach puts the hook block there (within 5 mm), keeps the travel, and the readout's radius is the
    maker's (from the slew axis where the crane stands)."""
    BL = _mods()
    sc = _new(tmp_path)
    c = BL.place(bpy.context, _item("CC-100"), (30.0, 5.0, 0.0), 0.5)
    BL.set_values(sc, c, {"Travel": 7000.0, "Slew": 20.0})
    lay = C.layout("CC-100")
    want_vals = {"Travel": 7000.0, "Slew": -35.0, "Luff": 8.0, "Hoist": 12000.0}
    target = BL.to_world(c, C.hook_point(lay, want_vals))
    a = BL.hook_to(sc, c, target)
    assert a.ok, a.reason
    vals = BL.values(sc, c)
    assert vals["Travel"] == pytest.approx(7000.0, abs=1e-3)
    hb = BL._hook_block_world(sc, c)
    assert np.linalg.norm(hb - np.asarray(target)) < 0.005
    ro = BL.readout(sc, c)
    r, z = C.hook_radius_height(lay, vals)
    assert ro.radius == pytest.approx(r, abs=1e-4) and ro.height == pytest.approx(z, abs=1e-4)
    # Move… (placed again elsewhere, turned the other way): the hook comes along, the readout stays the crane's own
    BL.place_at(c, (-10.0, 2.0, 0.0), -1.0)
    ro2 = BL.readout(sc, c)
    assert ro2 is not ro and ro2.radius == pytest.approx(r, abs=1e-4)
    assert np.linalg.norm(BL._hook_block_world(sc, c) - BL.hook_world(sc, c)) < 0.005


# ---------------------------------------------------------------------------------------------------------------------
# the readout's cache

def test_readout_follows_a_joint_moved_by_hand_and_the_set_up(tmp_path):
    """The readout is cached; it must follow a joint moved by hand (not through the plan), the counterweight, the
    outrigger spread typed instead of read from the pose, and the load's mass."""
    BL = _mods()
    sc = _new(tmp_path)
    from fresing_render.blender import joints
    c = BL.place(bpy.context, _item("AT-40"), (12.0, 0.0, 0.0), 0.0)
    BL.apply_pose(sc, c, "Working")
    ld = BL.new_box(sc, (1.0, 1.0, 1.0), 2.0, location=(18.0, 0.0, 0.0))
    ro = BL.readout(sc, c, ld)
    luff = joints.find(sc, "AT-40 · Luff")
    joints.set_value(luff, math.radians(40.0))
    bpy.context.view_layer.update()
    ro2 = BL.readout(sc, c, ld)
    rig = BL.rig_of(c)
    r, _z = rig.radius_height(BL.values(sc, c))
    assert ro2 is not ro and ro2.radius == pytest.approx(r) and ro2.boom_angle == pytest.approx(40.0, abs=1e-3)
    c.counterweight = 0.0
    ro3 = BL.readout(sc, c, ld)
    assert ro3.chart is not None and ro3.chart.config["counterweight"] == 0.0
    c.spread_from_pose = False
    c.outriggers = 4.6
    ro4 = BL.readout(sc, c, ld)
    assert ro4.chart.config["outriggers"] == 4.6
    ld.mass_t = 3.0
    ro5 = BL.readout(sc, c, ld)
    assert ro5.gross == pytest.approx(3000.0 + BL.hook_block_kg(c))


def test_readout_on_a_chart_row_agrees_with_hook_to_here(tmp_path):
    """AT-40 at the origin: Hook to here at exactly 9.00 m radius (the 10.8 m chart's last row). The readout of the
    pose it leaves must give the same crane use (the panel shows the readout)."""
    BL = _mods()
    sc = _new(tmp_path, step=None)
    c = BL.place(bpy.context, _item("AT-40"), (0.0, 0.0, 0.0), 0.0)
    BL.apply_pose(sc, c, "Set up")
    centre = BL.to_world(c, BL.rig_of(c).slew_centre(BL.values(sc, c)))
    ld = BL.new_box(sc, (0.5, 0.5, 0.5), 1.0, location=(centre[0] + 9.0, 0.0, 0.0))
    a = BL.hook_to(sc, c, (centre[0] + 9.0, centre[1], 3.0), ld)
    assert a.ok and a.use is not None, a.reason
    ro = BL.readout(sc, c, ld)
    assert ro.use is not None, ro.reason
    assert ro.use == pytest.approx(a.use, rel=1e-6)


# ---------------------------------------------------------------------------------------------------------------------
# two cranes, Remove, place again

def test_remove_one_of_two_cranes_and_place_again(tmp_path):
    BL = _mods()
    sc = _new(tmp_path)
    a = BL.place(bpy.context, _item("AT-40"), (12.0, 0.0, 0.0), 0.0)
    b = BL.place(bpy.context, _item("AT-40"), (-14.0, 0.0, 0.0), math.pi)
    BL.apply_pose(sc, a, "Long reach")
    old = BL.readout(sc, a)
    BL.remove(sc, sc.fresing.lifting.cranes["AT-40"])
    b = sc.fresing.lifting.cranes["AT-40 2"]
    vb = BL.values(sc, b)
    c = BL.place(bpy.context, _item("AT-40"), (0.0, 20.0, 0.0), 0.0)
    assert c.name == "AT-40"
    names = [j.name for j in sc.fresing.joints]
    assert len(names) == len(set(names))
    assert len(BL.own_joints(sc, c)) == len(BL.own_joints(sc, sc.fresing.lifting.cranes["AT-40 2"]))
    assert BL.values(sc, sc.fresing.lifting.cranes["AT-40 2"]) == vb
    # the new crane's readout is its own (not the removed crane's cached one in its Long reach pose)
    ro = BL.readout(sc, c)
    assert ro is not old
    assert ro.radius == pytest.approx(BL.rig_of(c).radius_height(BL.values(sc, c))[0])
    # its poses move it alone
    BL.apply_pose(sc, c, "Working")
    assert BL.values(sc, sc.fresing.lifting.cranes["AT-40 2"]) == vb
    pnames = [p.name for p in sc.fresing.poses]
    assert len(pnames) == len(set(pnames))


# ---------------------------------------------------------------------------------------------------------------------
# loads

def test_a_subassembly_and_its_own_child_count_once(tmp_path):
    BL = _mods()
    sc = _new(tmp_path)
    from fresing_render.blender import logic
    boom = _part(sc, "BOOM.ASM")
    ld = BL.new_load(sc, [boom], "Boom")
    v1, m1 = ld.volume, ld.volume_mass
    BL.remove_load(sc, ld)
    child = next(o for o in logic.descendants(boom) if o.type == "MESH")
    ld = BL.new_load(sc, [boom, child], "Boom and child")
    assert ld.volume == pytest.approx(v1, rel=1e-9) and ld.volume_mass == pytest.approx(m1, rel=1e-9)


def test_a_scaled_part_has_its_scaled_volume(tmp_path):
    BL = _mods()
    sc = _new(tmp_path)
    from fresing_render.blender import logic
    boom = _part(sc, "BOOM.ASM")
    part = next(o for o in logic.descendants(boom) if o.type == "MESH")
    ld = BL.new_load(sc, [part], "One part")
    v1 = ld.volume
    part.scale = part.scale * 2.0
    BL.refresh_load(sc, ld)
    assert ld.volume == pytest.approx(8.0 * v1, rel=1e-6)


def test_an_open_mesh_part_is_named_and_boxed(tmp_path):
    """A part that is not a closed solid (an open tube: a pipe drawn as a surface) falls back to its box and is named.

    FAULT: the open tube is taken for a closed solid (see test_lifting_reach_independent) – not named, and its volume
    is 2/3 of the closed tube's instead of its box."""
    BL = _mods()
    sc = _new(tmp_path)
    from fresing_render.blender import build
    n, r, h = 64, 0.2, 1.5
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    vs = [(r * math.cos(a), r * math.sin(a), 0.0) for a in t] + [(r * math.cos(a), r * math.sin(a), h) for a in t]
    fs = [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    me = bpy.data.meshes.new("open tube")
    me.from_pydata(vs, [], fs)
    me.update()
    ob = bpy.data.objects.new("OPEN TUBE", me)
    ob[build.PROP_KIND] = "part"
    ob[build.PROP_NAME] = "OPEN TUBE"
    sc.collection.objects.link(ob)
    ob.location = (40.0, 0.0, 0.0)
    ld = BL.new_load(sc, [ob], "Tube")
    assert "OPEN TUBE" in ld.open_parts
    assert ld.volume == pytest.approx((2 * r) ** 2 * h, rel=0.02)          # its box


def test_a_placed_crane_cannot_be_a_load(tmp_path):
    BL = _mods()
    sc = _new(tmp_path)
    from fresing_render.blender import build, logic
    c = BL.place(bpy.context, _item("KB-20"), (15.0, 0.0, 0.0), 0.0)
    part = next(o for o in logic.descendants(c.root) if o.get(build.PROP_KIND) == "part")
    with pytest.raises(ValueError, match="crane"):
        BL.new_load(sc, [part])
    assert len(sc.fresing.lifting.loads) == 0


def test_cog_by_hand_survives_save_and_open(tmp_path):
    BL = _mods()
    sc = _new(tmp_path)
    boom = _part(sc, "BOOM.ASM")
    ld = BL.new_load(sc, [boom], "Boom")
    c0 = BL.cog_world(ld).copy()
    bpy.ops.fresing.lifting_load_select(index=0)
    assert bpy.ops.fresing.lifting_cog_move(offset=(0.0, 0.2, 0.1)) == {"FINISHED"}
    path = str(tmp_path / "plan.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    ld = sc.fresing.lifting.loads["Boom"]
    assert BL.cog_by_hand(ld)
    assert np.linalg.norm(BL.cog_world(ld) - c0 - np.array((0.0, 0.2, 0.1))) < 1e-5
    # the marker rides with the load: move the boom's parts' parent and the marker comes along
    assert bpy.ops.fresing.lifting_cog_back() == {"FINISHED"}
    assert not BL.cog_by_hand(ld) and np.linalg.norm(BL.cog_world(ld) - c0) < 1e-5


# ---------------------------------------------------------------------------------------------------------------------
# words and the first-use gate

class _Recorder:
    """A layout that records every text it is given (label, operator, prop text, wrap's labels)."""

    def __init__(self, texts):
        self.texts = texts
        self.scale_y = 1
        self.scale_x = 1
        self.alignment = "LEFT"
        self.active = True
        self.enabled = True
        self.alert = False
        self.use_property_split = False
        self.use_property_decorate = False

    def _child(self, *a, **k):
        return _Recorder(self.texts)

    row = column = box = split = grid_flow = column_flow = _child

    def panel(self, *a, **k):
        return _Recorder(self.texts), _Recorder(self.texts)

    def label(self, *a, text="", **k):
        self.texts.append(text)

    def operator(self, idname, *a, text="", **k):
        self.texts.append(text)
        return type("Op", (), {})()

    def prop(self, data, name, *a, text="", **k):
        self.texts.append(text)

    def __getattr__(self, name):
        return lambda *a, **k: _Recorder(self.texts)


def _panel_texts(context):
    from fresing_render.blender import ui_lifting
    texts = []
    for cls in ui_lifting.CLASSES:
        fake = type("P", (), {"layout": _Recorder(texts)})()
        cls.draw(fake, context)
        if hasattr(cls, "draw_header_preset"):
            cls.draw_header_preset(fake, context)
    return " ".join(t for t in texts if t)


def test_no_forbidden_words_anywhere_the_user_reads(tmp_path):
    """Section 8: never 'safe', 'approved', 'certified', 'compliant', 'OK to lift', 'passed' – in the panels as drawn
    (with a crane, a load and a hook answer), the operators' tooltips, the settings' tooltips and the guide chapter.
    The planning-aid line (a competent person approves the plan) is the one place 'approved' may stand."""
    BL = _mods()
    sc = _new(tmp_path)
    BL.set_up_example(bpy.context)
    drawn = _panel_texts(bpy.context)
    norm = " ".join(drawn.split())
    assert " ".join(lifting.PLANNING_AID.split()) in norm or all(w in norm for w in lifting.PLANNING_AID.split()[:8])
    assert "SAMPLE" in drawn
    texts = [drawn.replace(lifting.PLANNING_AID, "")]
    from fresing_render.blender import ops_lifting
    for cls in ops_lifting.CLASSES:
        mod, op = cls.bl_idname.split(".")
        rna = getattr(getattr(bpy.ops, mod), op).get_rna_type()
        texts.append(rna.description)
        texts += [p.description for p in rna.properties]
    from fresing_render.blender import props
    for name in ("FRLiftCrane", "FRLiftDensity", "FRLiftLoad", "FRLifting"):
        cls = getattr(props, name)
        for p in cls.bl_rna.properties:
            texts.append(p.description)
            if p.type == "ENUM":
                texts += [i.description + " " + i.name for i in p.enum_items]
    guide = open(os.path.join(ROOT, "docs", "USER-GUIDE.md"), encoding="utf-8").read()
    start = guide.find('id="lifting')
    assert start >= 0
    chapter = guide[start:]
    nxt = re.search(r"\n## ", chapter[10:])
    chapter = chapter[: nxt.start() + 10] if nxt else chapter
    texts.append(chapter.replace(" ".join(lifting.PLANNING_AID.split()), ""))
    bad = [t for t in texts if t and FORBIDDEN.search(t.replace(lifting.PLANNING_AID, ""))]
    assert not bad, bad[:5]


def test_nothing_of_the_section_works_before_i_understand(tmp_path, monkeypatch):
    """First use: until the planning-aid line is accepted, none of the section's buttons work (placing, poses, loads,
    Hook to here, Remove) and the section shows only the line and its button."""
    BL = _mods()
    sc = _new(tmp_path)
    BL.set_up_example(bpy.context)
    monkeypatch.setattr(BL, "understood", lambda background=None: False)
    for op in ("lifting_place", "lifting_move", "lifting_remove", "lifting_pose", "lifting_setup_value",
               "lifting_load_selected", "lifting_box", "lifting_load_remove", "lifting_load_refresh",
               "lifting_cog_move", "lifting_hook_here", "lifting_hook_above", "lifting_pick"):
        assert not getattr(bpy.ops.fresing, op).poll(), op
    drawn = _panel_texts(bpy.context)
    assert "Hook to here" not in drawn.split("Start the Lifting plan")[0]


# ---------------------------------------------------------------------------------------------------------------------
# the crane's equipment file not where it was

def test_a_crane_whose_file_is_gone_says_so_and_hook_to_here_does_not_crash(tmp_path):
    """A crane placed from the user's library, then its folder deleted (or the project opened on a PC without it): the
    panel must name the problem ('… is gone …'), and Hook to here must refuse in words, not with a Python error.

    FAULT: the readout says "Hook to here knows mobile, crawler and knuckle-boom cranes, not ''." and Hook to here
    raises ReachError out of the operator."""
    import shutil
    BL = _mods()
    sc = _new(tmp_path, step=None)
    lib = tmp_path / "lib" / "AT-40"
    shutil.copytree(_item("AT-40"), lib)
    c = BL.place(bpy.context, str(lib), (0.0, 0.0, 0.0), 0.0)
    BL.apply_pose(sc, c, "Working")
    shutil.rmtree(tmp_path / "lib")
    BL.forget()
    assert "gone" in BL.file_changed(c)
    problems = []
    ro = BL.readout(sc, c)
    if not (isinstance(ro, str) and ("gone" in ro or "file" in ro)):
        problems.append(f"readout: {ro}")
    try:
        res = bpy.ops.fresing.lifting_hook_here(point=(8.0, 0.0, 2.0))
        if res != {"CANCELLED"}:
            problems.append(f"Hook to here: {res}")
    except RuntimeError as exc:
        lines = str(exc).strip().splitlines()
        problems.append("Hook to here raised: " + next((x for x in lines if "Error" in x), lines[0]))
    assert not problems, problems


def test_a_built_in_crane_is_found_when_the_app_lives_elsewhere(tmp_path):
    """A built-in sample crane placed on one PC; the project opened where the app is installed in another folder (a
    colleague's PC, another Windows user): the built-in item is the same, the plan must still read its charts.

    FAULT: the crane keeps the absolute path of the built-in file; elsewhere it is 'gone' and the readout has no
    chart."""
    BL = _mods()
    sc = _new(tmp_path, step=None)
    c = BL.place(bpy.context, _item("AT-40"), (0.0, 0.0, 0.0), 0.0)
    BL.apply_pose(sc, c, "Working")
    assert c.builtin
    rel = os.path.relpath(c.item_path, os.path.join(DATA, "lifting"))
    c.item_path = os.path.join(str(tmp_path), "OtherUser", "extensions", "fresing_render", "data", "lifting", rel)
    BL.forget()
    ro = BL.readout(sc, c)
    assert not isinstance(ro, str) and ro.chart is not None, ro
