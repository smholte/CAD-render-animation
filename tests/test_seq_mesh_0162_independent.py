"""Task 0162, independent tests (written by a tester who did not write the code): assembly sequence steps in other
orders (three deep, interleaved, the same subassembly twice, riders, Back to CAD), unnamed mesh groups in model
updates, the OBJ / MTL decoder and hiding after Build.

The deep model (SLIDE.UNIT with a CARRIAGE.SET inside it) is written to tmp_path with the helpers of
tools/make_test_sequence.py; nothing in tests/data is changed.
"""

from __future__ import annotations

import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, HERE)

from fresing_render.importer import mesh_reader  # noqa: E402

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import animation, build, logic, sequence, states  # noqa: E402

MM = 1e-3
TOL = 0.01 * MM


# ---------------------------------------------------------------------------
# _decode (no Blender needed)
# ---------------------------------------------------------------------------

def test_decode_bom_crlf_and_mixed_lines():
    """BOM + CRLF + one cp1252 comment line among UTF-8 lines: every line keeps its letters, the BOM is gone, the
    line ends are kept; an empty file and a file that is only a BOM read as empty."""
    raw = (b"\xef\xbb\xbf" + "o Plåt\r\n".encode() + "# för Windows\r\n".encode("cp1252")
           + "usemtl Stål\r\n".encode())
    assert mesh_reader._decode(raw) == "o Plåt\r\n# för Windows\r\nusemtl Stål\r\n"
    assert mesh_reader._decode(b"") == ""
    assert mesh_reader._decode(b"\xef\xbb\xbf") == ""
    assert mesh_reader._decode("o A\r".encode() + "# Blå\r".encode("cp1252") + "o Plåt".encode()) == \
        "o A\r# Blå\ro Plåt"                                  # old Mac line ends (CR only)
    assert mesh_reader._decode("o Plåt\nusemtl Blå\n".encode("cp1252")) == "o Plåt\nusemtl Blå\n"


@pytest.mark.parametrize("last", ["Blå", "Ä", "é", "Ü"])
def test_decode_a_cp1252_letter_at_the_very_end_of_the_file(last):
    """A cp1252 file whose last line has no line break and ends in a letter that is a UTF-8 lead byte in cp1252
    (å = E5, Ä = C4, é = E9, Ü = DC): the last letter must stay. ``_decode`` takes it for "a read cut in the
    middle of a letter" and drops it ("usemtl Bl" instead of "usemtl Blå"), so the material name changes."""
    raw = ("o Plåt\nusemtl " + last).encode("cp1252")
    assert mesh_reader._decode(raw) == "o Plåt\nusemtl " + last


def test_decode_a_utf8_file_cut_in_the_middle_of_a_letter():
    """A UTF-8 file cut inside its last letter (the credit read of a few bytes): the rest stays UTF-8."""
    raw = "o Plåt\n# Stål".encode()
    assert mesh_reader._decode(raw[:-2], cut=True) == "o Plåt\n# St"
    assert mesh_reader._decode(raw[:-3], cut=True) == "o Plåt\n# St"


# ---------------------------------------------------------------------------
# unnamed mesh groups in a model update (0147 row 3)
# ---------------------------------------------------------------------------

import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

import make_test_mesh as maker  # noqa: E402
from fresing_render.blender import joints  # noqa: E402
from test_mesh_import_fixes import fresh, parts, update  # noqa: E402

X0 = {"A": -1.0, "B": 0.0, "C": 1.0, "D": 2.0}


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def groups_glb(groups=("A", "B", "C"), sizes=None, part_names=None, nest=None, at=None) -> bytes:
    """Unnamed group nodes (the reader names them "Node k"), two boxes each: ``<G>1`` and ``<G>2``. Every group's
    first box has the same size as the other groups' first boxes (as copies of one bracket would), so only the name
    and the box's place tell them apart. ``sizes[G]``: another size for G's boxes (a changed shape);
    ``part_names[G]``: names for G's two boxes; ``nest[G]``: the group G sits inside (also unnamed); ``at[G]``: a
    translation of G's own node (the boxes are then drawn round that place)."""
    g = maker.Gltf()
    grey = g.material("Grey", (0.5, 0.5, 0.5))
    nodes = {}
    for name in groups:
        par = nodes.get((nest or {}).get(name))
        off = np.array((at or {}).get(name, (0.0, 0.0, 0.0)), float)
        m = np.eye(4)
        m[:3, 3] = off
        nodes[name] = grp = g.node("", matrix=m, parent=par)
        for k in (1, 2):
            s = maker.Shape()
            x = X0[name] + 0.3 * k
            h = (sizes or {}).get(name, 0.0)
            lo = np.array((x, 0.0, 0.0)) - off
            hi = np.array((x + 0.2, 0.2 + 0.05 * k + h, 0.2)) - off
            s.box(tuple(lo), tuple(hi))
            nm = (part_names or {}).get(name, (f"{name}1", f"{name}2"))[k - 1]
            g.node(nm, g.mesh(nm, [(s, grey)]), parent=grp)
    return g.glb()


def _cx(ob):
    return sum((ob.matrix_world @ Vector(v)).x for v in ob.bound_box) / 8


def _part(sc, name, x=None):
    """The part called ``name`` (the one nearest x when several share the name)."""
    c = [o for o in parts(sc) if o.get(build.PROP_NAME) == name]
    if x is not None:
        c.sort(key=lambda o: abs(_cx(o) - x))
    return c[0]


def _work_on(sc, grp, part):
    """Work on a group and a part: the eye in 2 Structure, a Hide step and a sequence step on the group, a slide
    joint on the part."""
    logic.set_hidden(grp, True)
    a = sc.fresing.animations.add()
    hide = a.blocks.add()
    hide.kind, hide.target_uid, hide.target_name = "HIDE", grp[build.PROP_UID], grp[build.PROP_NAME]
    seq = a.blocks.add()
    seq.kind, seq.target_uid, seq.target_name = "SEQUENCE", grp[build.PROP_UID], grp[build.PROP_NAME]
    joints.create(sc, "SLIDE", [part], Vector((0, 0, 0)), Vector((1, 0, 0)), name="Work joint")
    return hide, seq


def _check_work(sc, hide, seq, part_name, x=None):
    p = _part(sc, part_name, x)
    grp = build.logical_parent(p)
    by = states.by_uid(sc)
    got = {"hide step": by.get(hide.target_uid), "sequence step": by.get(seq.target_uid)}
    wrong = {k: (v.get(build.PROP_NAME), sorted(c.get(build.PROP_NAME, "") for c in v.children)) if v else None
             for k, v in got.items() if v != grp}
    assert not wrong, (wrong, "expected the group of", part_name)
    groups = [o for o in sc.objects if o.get(build.PROP_KIND) == "assembly"]
    hidden = sorted(o.name for o in groups if logic.is_hidden(o))
    assert hidden == [grp.name], ("eye", hidden, grp.name)
    j = sc.fresing.joints["Work joint"]
    on = [f"{o.get(build.PROP_NAME)}@{_cx(o):.2f}" for o in joints.members(j)]
    assert on == [f"{p.get(build.PROP_NAME)}@{_cx(p):.2f}"], ("joint", on)


ONE_LEFT = pytest.mark.xfail(strict=True, reason="open point of task 0162: with one group left the reader makes that "
                              "group the model's root, which is matched to the old root, not to the old group")


@pytest.mark.parametrize("after", [("A", "B"), ("B", "C"), ("A", "B", "C", "D"), ("D", "A", "B", "C"),
                                   pytest.param(("B",), marks=ONE_LEFT)],
                         ids=["C-removed", "A-removed", "D-added-last", "D-added-first", "A-and-C-removed"])
def test_unnamed_group_b_keeps_its_work(tmp_path, after):
    """Three unnamed groups at the model's origin, work on group B and its part B1 (eye, Hide step, sequence step,
    a joint); the update removes or adds other groups. All the work must stay on B and B1. The parts' "made" rule
    pairs them by shape and place only – A1, B1 and C1 have one shape and the same origin (0, 0, 0) – so old B1
    can pair with new A1 or C1 and the work moves to another group."""
    src = tmp_path / "g.glb"
    src.write_bytes(groups_glb())
    sc = fresh(tmp_path, src)
    b1 = _part(sc, "B1")
    hide, seq = _work_on(sc, build.logical_parent(b1), b1)
    src.write_bytes(groups_glb(after))
    update(sc, src)
    _check_work(sc, hide, seq, "B1")


def test_unnamed_groups_nested_in_unnamed_groups(tmp_path):
    """B sits inside A (both unnamed), C beside them; the update puts C first (every "Node k" shifts): the work on
    B (an unnamed group inside an unnamed group) stays on B."""
    src = tmp_path / "g.glb"
    src.write_bytes(groups_glb(("A", "B", "C"), nest={"B": "A"}))
    sc = fresh(tmp_path, src)
    b1 = _part(sc, "B1")
    assert build.logical_parent(build.logical_parent(b1)) == build.logical_parent(_part(sc, "A1"))
    hide, seq = _work_on(sc, build.logical_parent(b1), b1)
    src.write_bytes(groups_glb(("C", "A", "B"), nest={"B": "A"}))
    update(sc, src)
    _check_work(sc, hide, seq, "B1")


@pytest.mark.parametrize("after", [("B", "C"), ("A", "B")], ids=["A-removed", "C-removed"])
def test_equal_part_names_in_different_unnamed_groups(tmp_path, after):
    """Every group's boxes are called "Bracket" and "Plate" (equal names, equal first shapes); the groups differ only
    by where their boxes lie. Another group is removed: the work on the middle group's Bracket (x = 0.4 m) stays
    there."""
    names = {g: ("Bracket", "Plate") for g in "ABC"}
    src = tmp_path / "g.glb"
    src.write_bytes(groups_glb(part_names=names))
    sc = fresh(tmp_path, src)
    br = _part(sc, "Bracket", 0.4)
    hide, seq = _work_on(sc, build.logical_parent(br), br)
    src.write_bytes(groups_glb(after, part_names=names))
    update(sc, src)
    _check_work(sc, hide, seq, "Bracket", 0.4)


def test_a_group_whose_parts_all_changed_shape(tmp_path):
    """Group B's two boxes both get 30 mm taller (same names, same place): the work stays on B and B1."""
    src = tmp_path / "g.glb"
    src.write_bytes(groups_glb())
    sc = fresh(tmp_path, src)
    b1 = _part(sc, "B1")
    hide, seq = _work_on(sc, build.logical_parent(b1), b1)
    src.write_bytes(groups_glb(sizes={"B": 0.03}))
    update(sc, src)
    _check_work(sc, hide, seq, "B1")


@pytest.mark.parametrize("after", [("B", "C"), ("A", "B")], ids=["A-removed", "C-removed"])
def test_unnamed_groups_with_their_own_place(tmp_path, after):
    """Unnamed groups whose nodes are not at the origin (each moved to its boxes): another group removed, the work
    on B stays on B."""
    at = {"A": (-0.6, 0.0, 0.0), "B": (0.4, 0.0, 0.0), "C": (1.4, 0.0, 0.0)}
    src = tmp_path / "g.glb"
    src.write_bytes(groups_glb(at=at))
    sc = fresh(tmp_path, src)
    b1 = _part(sc, "B1")
    hide, seq = _work_on(sc, build.logical_parent(b1), b1)
    src.write_bytes(groups_glb(after, at=at))
    update(sc, src)
    _check_work(sc, hide, seq, "B1")


# ---------------------------------------------------------------------------
# assembly sequence steps in other orders (0147 rows 7, 9, 13)
# ---------------------------------------------------------------------------

from test_sequence import add_anim, named, worlds  # noqa: E402


def _jumps(sc, parts, f_from, f_to, least=0.008, ratio=3.0):
    """Frames where a part moves at once: its step in that frame is at least ``least`` and ``ratio`` times its steps
    in the frames before and after (a fast but smooth motion has neighbours of about its own size)."""
    pos = {o.name: [] for o in parts}
    for f in range(f_from, f_to + 1):
        sc.frame_set(f)
        for o in parts:
            pos[o.name].append(o.matrix_world.translation.copy())
    out = []
    for o in parts:
        p = pos[o.name]
        d = [0.0] + [(p[i] - p[i - 1]).length for i in range(1, len(p))] + [0.0]
        for i in range(1, len(p)):
            if d[i] >= least and d[i] > ratio * max(d[i - 1], d[i + 1], 1e-9):
                out.append((f_from + i, o.get(build.PROP_NAME), round(d[i] * 1000, 1),
                            round(d[i - 1] * 1000, 1), round(d[i + 1] * 1000, 1)))
    return out


def write_deep(path: str) -> None:
    """test_sequence_frame.step one level deeper, without the portal frame: SLIDE.UNIT holds CARRIAGE.SET
    (CARRIAGE + GRIPPER BLOCK). Three levels: TEST.SEQUENCE.DEEP > SLIDE.UNIT > CARRIAGE.SET."""
    import make_test_sequence as mts
    from OCP.gp import gp_Trsf, gp_Vec
    from OCP.Quantity import Quantity_Color, Quantity_TOC_sRGB
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.TDataStd import TDataStd_Name
    from OCP.TDocStd import TDocStd_Document
    from OCP.TopLoc import TopLoc_Location
    from OCP.XCAFApp import XCAFApp_Application
    from OCP.XCAFDoc import XCAFDoc_ColorType, XCAFDoc_DocumentTool
    app = XCAFApp_Application.GetApplication_s()
    doc = TDocStd_Document(TCollection_ExtendedString("XmlXCAF"))
    app.InitDocument(doc)
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    ct = XCAFDoc_DocumentTool.ColorTool_s(doc.Main())

    def name(lab, text):
        TDataStd_Name.Set_s(lab, TCollection_ExtendedString(text))

    def part(shape, text, rgb):
        lab = st.AddShape(shape, False)
        name(lab, text)
        ct.SetColor(lab, Quantity_Color(*rgb, Quantity_TOC_sRGB), XCAFDoc_ColorType.XCAFDoc_ColorSurf)
        return lab

    def place(assy, lab, trsf=None):
        st.AddComponent(assy, lab, TopLoc_Location(trsf if trsf is not None else gp_Trsf()))

    def asm(text):
        lab = st.NewShape()
        name(lab, text)
        return lab

    grey, blue, orange, steel, dark = ((0.55, 0.57, 0.6), (0.075, 0.267, 0.486), (0.95, 0.45, 0.05),
                                       (0.8, 0.8, 0.82), (0.15, 0.15, 0.17))
    base = part(mts.base_plate(), "BASE PLATE", grey)
    unit = asm("SLIDE.UNIT")
    place(unit, part(mts.rail_block(), "RAIL BLOCK", blue))
    place(unit, part(mts.slide_cover(), "COVER", steel))
    b = part(mts.g.xform(mts.socket_screw(8, 25.0), mts.g.T(0, 0, 50.0)), "ISO 4762 M8x25", dark)
    for y in (-40.0, 40.0):
        t = gp_Trsf()
        t.SetTranslation(gp_Vec(-100.0, y, 0))
        place(unit, b, t)
    cset = asm("CARRIAGE.SET")
    place(cset, part(mts.carriage(), "CARRIAGE", orange))
    place(cset, part(mts.gripper_block(), "GRIPPER BLOCK", steel))
    place(unit, cset)
    place(unit, part(mts.split_pin(), "SPLIT PIN", dark))
    root = asm("TEST.SEQUENCE.DEEP")
    place(root, base)
    place(root, unit)
    st.UpdateAssemblies()
    mts._write(doc, path)


@pytest.fixture(scope="module")
def deep_step(tmp_path_factory):
    p = str(tmp_path_factory.mktemp("deep") / "test_sequence_deep.step")
    write_deep(p)
    return p


@pytest.fixture()
def deep(tmp_path, deep_step):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path)
    assert bpy.ops.fresing.import_step(filepath=deep_step, quality="draft") == {"FINISHED"}
    logic.set_hidden(named(sc, "BASE PLATE"), True)
    return sc


ROOT_D, UNIT, CSET = "TEST.SEQUENCE.DEEP", "SLIDE.UNIT", "CARRIAGE.SET"
LEVEL = {CSET: 0, UNIT: 1, ROOT_D: 2}
A, T = "APART", "TOGETHER"


def seq(sc, a, target, start, mode="APART", **kw):
    b = a.blocks.add()
    b.kind = "SEQUENCE"
    t = named(sc, target)
    b.target_uid, b.target_name = t[build.PROP_UID], t[build.PROP_NAME]
    b.start, b.seq_mode, b.seq_id = start, mode, f"x{len(a.blocks)}"
    b.seq_direction = "UP"
    b.seq_part_time = 1.5
    for k, v in kw.items():
        setattr(b, k, v)
    sequence.count(sc, b)
    return b


def run(sc, a, steps, gap=0.2):
    """Steps as (target, mode, settings) one after the other; returns the blocks."""
    t, out = 0.0, []
    for target, mode, kw in steps:
        b = seq(sc, a, target, t, mode, **kw)
        out.append(len(a.blocks) - 1)
        t += b.duration + gap
    return [a.blocks[i] for i in out]


def _end_of(a, b):
    return animation.frame_of(a, b.start + b.duration) + 1


def _off(sc, home, parts, frame):
    """mm each part is away from home at ``frame``."""
    w = worlds(sc, parts, frame)
    return {f"{o.get(build.PROP_NAME)} [{o.name}]": round((w[o.name].translation - home[o.name].translation).length
                                                          * 1000, 2) for o in parts}


def _keys(sc, parts):
    out = {}
    for o in parts:
        cb = animation._channelbag(o, "OBJECT")
        out[o.name] = [] if cb is None else [(fc.data_path, fc.array_index,
                                              tuple(tuple(round(x, 6) for x in k.co) for k in fc.keyframe_points))
                                             for fc in cb.fcurves]
    return out


def _check_order(sc, a, steps, order, home, every):
    """After each Put together, a part every Take apart of which (by any subassembly holding it) has been put
    together again is home; at the end every part is home; no part moves at once (``_jumps``)."""
    holds = {n: {o.name for o in sequence.movers(sc, named(sc, n)).parts} for n, _m in order}
    for i, (name, mode) in enumerate(order):
        if mode != T:
            continue
        open_ = {}
        for x, m in order[:i + 1]:
            open_[x] = open_.get(x, 0) + (1 if m == A else -1)
        apart = set().union(*[holds[x] for x, c in open_.items() if c > 0])
        own = [o for o in every if o.name in holds[name] and o.name not in apart]
        bad = {n: v for n, v in _off(sc, home, own, _end_of(a, steps[i])).items() if v > 0.01}
        assert not bad, (f"after step {i + 1} (Put together {name})", bad)
        # a part an earlier Take apart moved that is home when this Put together starts stays home all through it
        moved_before = set().union(*[holds[x] for x, m in order[:i] if m == A]) if i else set()
        f0, f1 = animation.frame_of(a, steps[i].start), _end_of(a, steps[i])
        at0 = _off(sc, home, every, f0)
        stay = [o for o in every if o.name in holds[name] and o.name in moved_before
                and at0[f"{o.get(build.PROP_NAME)} [{o.name}]"] <= 0.01]
        for f in range(f0, f1 + 1, 2):
            left = {n: v for n, v in _off(sc, home, stay, f).items() if v > 0.01}
            assert not left, (f"step {i + 1} (Put together {name}) moves parts that were home, frame {f}", left)
    end = {n: v for n, v in _off(sc, home, every, sc.frame_end).items() if v > 0.01}
    assert not end, ("at the end", end)
    assert _jumps(sc, every, 1, sc.frame_end) == []


@pytest.mark.parametrize("together", [
    (ROOT_D, UNIT, CSET),        # strict reverse
    (CSET, UNIT, ROOT_D),        # the same order back (innermost first)
    (UNIT, CSET, ROOT_D),        # middle first
    (UNIT, ROOT_D, CSET),
    (CSET, ROOT_D, UNIT),
], ids=["reverse", "same-order", "middle-first", "middle-outer-inner", "inner-outer-middle"])
def test_three_deep_any_order_ends_home(deep, together):
    """Take apart CARRIAGE.SET, SLIDE.UNIT and the whole model (inside out), then put them together in another
    order: at the end every part is home, no part moves at once, and a Put together whose outer
    subassemblies are together again leaves its parts home. Built twice: the same keys."""
    sc = deep
    a = add_anim(sc, "Deep")
    order = [(CSET, A), (UNIT, A), (ROOT_D, A)] + [(n, T) for n in together]
    steps = run(sc, a, [(n, m, {}) for n, m in order])
    every = sequence.movers(sc, named(sc, ROOT_D)).parts
    home = worlds(sc, every, 1)
    info = animation.bake(sc, a)
    assert not [w for w in info["warnings"] if "found" in w or "pick" in w], info["warnings"]
    _check_order(sc, a, steps, order, home, every)
    first = _keys(sc, every)
    animation.bake(sc, a)
    assert _keys(sc, every) == first


@pytest.mark.parametrize("order", [
    [(ROOT_D, A), (UNIT, T), (ROOT_D, T)],                          # only the outer one taken apart
    [(ROOT_D, A), (CSET, T), (UNIT, T), (ROOT_D, T)],
    [(UNIT, A), (CSET, A), (UNIT, T), (CSET, T)],                   # inner taken apart after the outer one
    [(UNIT, A), (CSET, A), (CSET, T), (UNIT, T)],
    [(CSET, A), (CSET, A), (CSET, T), (CSET, T)],                   # the same subassembly twice
    [(CSET, A), (UNIT, A), (CSET, T), (ROOT_D, A), (UNIT, T), (ROOT_D, T)],   # interleaved
    [(UNIT, A), (UNIT, T), (CSET, A), (ROOT_D, A), (CSET, T), (ROOT_D, T)],
    [(UNIT, A), (ROOT_D, T)],                                       # Put together of the outer one only
], ids=["outer-only-inner-first", "outer-only-3", "inner-after-outer-a", "inner-after-outer-b", "same-twice",
        "interleaved-a", "interleaved-b", "outer-together-only"])
def test_other_orders(deep, order):
    """More orders on the three-level model: a Put together of an inner subassembly when only an outer one was taken
    apart, an inner one taken apart after its outer one, the same one twice, interleaved steps. Every part ends
    home, nothing jumps, a Put together leaves parts alone that are home already; built twice, the same keys."""
    sc = deep
    a = add_anim(sc, "Orders")
    steps = run(sc, a, [(n, m, {}) for n, m in order])
    every = sequence.movers(sc, named(sc, ROOT_D)).parts
    home = worlds(sc, every, 1)
    info = animation.bake(sc, a)
    assert not [w for w in info["warnings"] if "found" in w or "pick" in w], info["warnings"]
    _check_order(sc, a, steps, order, home, every)
    first = _keys(sc, every)
    animation.bake(sc, a)
    assert _keys(sc, every) == first


def test_a_disabled_and_a_deleted_step_in_the_middle(deep):
    """Take apart CARRIAGE.SET, Take apart SLIDE.UNIT (switched off), Put together CARRIAGE.SET: the switched-off
    step does nothing, the carriage set comes home. Then the switched-off step is deleted: the same keys."""
    sc = deep
    a = add_anim(sc, "Off")
    order = [(CSET, A), (UNIT, A), (CSET, T)]
    steps = run(sc, a, [(n, m, {}) for n, m in order])
    steps[1].enabled = False
    every = sequence.movers(sc, named(sc, ROOT_D)).parts
    home = worlds(sc, every, 1)
    animation.bake(sc, a)
    unit_only = [o for o in sequence.movers(sc, named(sc, UNIT)).parts
                 if o not in sequence.movers(sc, named(sc, CSET)).parts]
    for f in range(1, sc.frame_end + 1, 5):
        assert all(v < 0.01 for v in _off(sc, home, unit_only, f).values()), f
    assert all(v < 0.01 for v in _off(sc, home, every, sc.frame_end).values())
    assert _jumps(sc, every, 1, sc.frame_end) == []
    first = _keys(sc, every)
    a.blocks.remove(1)
    animation.bake(sc, a)
    assert _keys(sc, every) == first


def _rig(sc):
    """The carriage slides along X on the rail block; the gripper block lifts on the carriage: both ride (as
    test_sequence.rig, on the three-level model)."""
    from fresing_render.blender import joints as J
    rail, car, blk = named(sc, "RAIL BLOCK"), named(sc, "CARRIAGE"), named(sc, "GRIPPER BLOCK")
    J.create(sc, "SLIDE", [car], Vector((0, 0, 0.04)), Vector((1, 0, 0)), name="Carriage", base=rail)
    J.create(sc, "SLIDE", [blk], Vector((0, 0, 0.08)), Vector((0, 0, 1)), name="Lift", base=car)


RIDER_ORDERS = {
    "inner-differs": [(CSET, A, {"seq_distance": 0.1}), (UNIT, A, {}), (CSET, T, {"seq_direction": "CENTRE"}),
                      (UNIT, T, {})],
    "outer-differs": [(UNIT, A, {"seq_direction": "CENTRE"}), (ROOT_D, A, {}),
                      (UNIT, T, {"seq_distance": 0.05}), (ROOT_D, T, {"seq_overlap": 0.0})],
    "any-order": [(UNIT, A, {"seq_distance": 0.1}), (ROOT_D, A, {}), (UNIT, T, {"seq_direction": "CENTRE"}),
                  (ROOT_D, T, {})],
    "same-twice": [(UNIT, A, {}), (UNIT, A, {"seq_distance": 0.05}), (UNIT, T, {"seq_direction": "CENTRE"}),
                   (UNIT, T, {"seq_part_time": 2.0})],
}


@pytest.mark.parametrize("name", list(RIDER_ORDERS))
def test_riders_in_both_directions_and_both_levels(deep, name):
    """Riders (carriage on the rail block, gripper block on the carriage) in Take apart and Put together steps whose
    settings differ, in the inner and the outer step: no part moves at once, every part ends home."""
    sc = deep
    _rig(sc)
    a = add_anim(sc, "Riders")
    order = RIDER_ORDERS[name]
    run(sc, a, order)
    every = sequence.movers(sc, named(sc, ROOT_D)).parts
    home = worlds(sc, every, 1)
    info = animation.bake(sc, a)
    assert not [w for w in info["warnings"] if "found" in w or "pick" in w], info["warnings"]
    end = {n: v for n, v in _off(sc, home, every, sc.frame_end).items() if v > 0.01}
    assert not end, end
    assert _jumps(sc, every, 1, sc.frame_end) == []


def _shows(o):
    from fresing_render.blender import fade
    return not o.hide_render and float(o.get(fade.FADE, 0.0)) < 1e-6


@pytest.mark.parametrize("order", [
    [(CSET, A, {"seq_end": "HIDE"}), (UNIT, A, {}), (CSET, T, {}), (UNIT, T, {})],
    [(CSET, A, {"seq_end": "FADE"}), (UNIT, A, {"seq_end": "HIDE"}), (UNIT, T, {}), (CSET, T, {})],
    [(ROOT_D, A, {"seq_end": "HIDE"}), (UNIT, T, {}), (ROOT_D, T, {})],
    [(UNIT, A, {}), (UNIT, T, {"seq_end": "HIDE"})],
    [(UNIT, A, {"seq_end": "FADE"}), (ROOT_D, A, {}), (ROOT_D, T, {"seq_end": "HIDE"}), (UNIT, T, {})],
], ids=["hide-inner-stay", "fade-inner-hide-outer", "hide-outer-inner-first", "stay-then-hide", "fade-hide-mixed"])
def test_hide_fade_then_stay_in_other_orders(deep, order):
    """Take apart with Hide or Fade, Put together with Stay (or Hide), in other orders: every part renders, unfaded,
    at the last frame."""
    sc = deep
    a = add_anim(sc, "Show")
    run(sc, a, order)
    every = sequence.movers(sc, named(sc, ROOT_D)).parts
    animation.bake(sc, a)
    sc.frame_set(sc.frame_end)
    hidden = sorted(o.name for o in every if not _shows(o))
    assert not hidden, hidden


def _cad(a, start, whole=True, target=None):
    c = a.blocks.add()
    c.kind, c.start, c.duration, c.cad_whole = "CAD", start, 1.0, whole
    if target is not None:
        c.target_uid, c.target_name = target[build.PROP_UID], target[build.PROP_NAME]
    return c


def test_back_to_cad_after_steps_in_another_order(deep):
    """Take apart CARRIAGE.SET, Take apart SLIDE.UNIT, Put together CARRIAGE.SET, Take apart the whole model, then
    Back to CAD (whole model): every part ends home and nothing jumps."""
    sc = deep
    a = add_anim(sc, "Back")
    order = [(CSET, A, {}), (UNIT, A, {}), (CSET, T, {}), (ROOT_D, A, {})]
    steps = run(sc, a, order)
    t = steps[-1].start + steps[-1].duration + 0.2
    _cad(a, t)
    every = sequence.movers(sc, named(sc, ROOT_D)).parts
    home = worlds(sc, every, 1)
    info = animation.bake(sc, a)
    assert not info["warnings"], info["warnings"]
    end = {n: v for n, v in _off(sc, home, every, sc.frame_end).items() if v > 0.01}
    assert not end, end
    assert _jumps(sc, every, 1, sc.frame_end) == []


def test_back_to_cad_of_the_inner_one_then_put_together_the_outer_one(deep):
    """Take apart SLIDE.UNIT, Take apart CARRIAGE.SET, Back to CAD of CARRIAGE.SET only, Put together SLIDE.UNIT:
    nothing jumps and every part ends home."""
    sc = deep
    a = add_anim(sc, "Back inner")
    steps = run(sc, a, [(UNIT, A, {}), (CSET, A, {})])
    t = steps[-1].start + steps[-1].duration + 0.2
    _cad(a, t, whole=False, target=named(sc, CSET))
    seq(sc, a, UNIT, t + 1.2, T)
    every = sequence.movers(sc, named(sc, ROOT_D)).parts
    home = worlds(sc, every, 1)
    info = animation.bake(sc, a)
    assert not info["warnings"], info["warnings"]
    end = {n: v for n, v in _off(sc, home, every, sc.frame_end).items() if v > 0.01}
    assert not end, end
    assert _jumps(sc, every, 1, sc.frame_end) == []


# ---------------------------------------------------------------------------
# hiding or showing after Build (0147 row 21c)
# ---------------------------------------------------------------------------

def _built(sc):
    """The spindle unit taken apart (Hide at the end) and put together (Fade): every part of it has visibility keys."""
    from test_sequence import add_seq
    a = add_anim(sc, "Built")
    b1 = add_seq(sc, a, seq_end="HIDE")
    add_seq(sc, a, start=b1.duration + 0.5, seq_mode="TOGETHER", seq_end="FADE")
    animation.bake(sc, a)
    assert animation.has_keys(sc)
    return a


def _select(sc, *objs):
    for o in sc.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]


@pytest.fixture()
def spindle(tmp_path):
    from test_sequence import load
    return load(tmp_path)


@pytest.mark.parametrize("entry", ["toggle_hide", "hide_selected", "show_all", "tree_eye", "tree_only",
                                   "show_only_selected", "show_only_end", "show_only_group", "vis_apply"])
def test_every_hide_and_show_entry_takes_the_build_off(spindle, entry):
    """After Build, every way to hide or show parts in the side panel (2 Structure: the row's eye and Show only,
    Hide, Show only, Show all, Show everything again, Use visibility set; 3 Looks: Show only these) takes the built
    animation off with "Build again": the built keys would otherwise still show the parts it hid in the render."""
    sc = spindle
    cover = named(sc, "COVER")
    base = named(sc, "BASE PLATE")
    unit = named(sc, "SPINDLE.UNIT")
    if entry == "show_only_end":
        _select(sc, base)
        assert bpy.ops.fresing.show_only_selected() == {"FINISHED"}
    if entry == "vis_apply":
        logic.set_hidden(unit, True)
        states.save_visibility(sc, "No unit")
        logic.set_hidden(unit, False)
    _built(sc)
    if entry == "toggle_hide":
        res = bpy.ops.fresing.toggle_hide(name=cover.name)
    elif entry == "hide_selected":
        _select(sc, cover)
        res = bpy.ops.fresing.hide_selected()
    elif entry == "show_all":
        logic.set_hidden(cover, True)
        res = bpy.ops.fresing.show_all()
    elif entry in ("tree_eye", "tree_only"):
        bpy.ops.fresing.tree_refresh()
        i = next(k for k, it in enumerate(sc.fresing.tree) if it.obj == base)
        res = bpy.ops.fresing.tree_row(index=i, action="HIDE" if entry == "tree_eye" else "ONLY")
    elif entry == "show_only_selected":
        _select(sc, base)
        res = bpy.ops.fresing.show_only_selected()
    elif entry == "show_only_end":
        res = bpy.ops.fresing.show_only_end()
    elif entry == "show_only_group":
        group = base.get("fr_group") or next(iter(g.name for g in sc.fresing.groups))
        res = bpy.ops.fresing.show_only_group(group=group)
    else:
        res = bpy.ops.fresing.vis_apply(name="No unit")
    assert res == {"FINISHED"}, res
    assert not animation.has_keys(sc), f"{entry}: the built animation is still on after hiding / showing parts"
    assert "Build again" in sc.fresing.last_message


def test_show_only_after_build_does_not_render_the_hidden_parts(spindle):
    """The consequence of the row above for 2 Structure > Show only: after Build, Show only the base plate; the
    spindle unit's parts must not render at any frame (the owner sees only the base plate in the view)."""
    sc = spindle
    _built(sc)
    parts = sequence.movers(sc, named(sc, "SPINDLE.UNIT")).parts
    _select(sc, named(sc, "BASE PLATE"))
    assert bpy.ops.fresing.show_only_selected() == {"FINISHED"}
    shown = {}
    for f in range(1, sc.frame_end + 1, 10):
        sc.frame_set(f)
        n = sum(not o.hide_render for o in parts)
        if n:
            shown[f] = n
    assert not shown, f"frames where parts of the unit render: {shown} (of {len(parts)})"
