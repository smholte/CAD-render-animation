"""Task 0040: the tool library without Blender (core/tools.py) and the outline reading of fluted tools."""

import io
import json
import math
import zipfile

import numpy as np
import pytest

from fresing_render.core import gcode, machining, tools

MM = 0.001


def test_every_type_has_sizes_that_work_at_once():
    for k in tools.KINDS:
        s = tools.default(k, 3)
        assert s.kind == k and s.number == 3 and s.diameter > 0 and s.stick_out > 0
        cut = tools.cutting_tool(s)
        c = machining.Cutter(cut)
        assert c.reach >= s.diameter / 2 - 1e-9 and c.length > 0
        v, t, part = tools.tool_mesh(s)
        assert len(t) > 50 and abs(v[:, 2].min()) < 1e-12 and set(part.tolist()) == {0}
        assert tools.checks(s) == []
        assert tools.describe(s).startswith(tools.type_name(k))


@pytest.mark.parametrize("holder", ["ER", "SK40", "BT30", "BT40", "HSK63"])
def test_holders_sit_above_the_stick_out(holder):
    s = tools.default("FLAT")
    s.holder = holder
    s = tools.resolved(s)
    v, t, part = tools.tool_mesh(s)
    hv = v[np.unique(t[part == 1])]
    assert abs(hv[:, 2].min() - s.stick_out) < 1e-9
    assert tools.gauge_length(s) == pytest.approx(s.stick_out + s.holder_length)
    if holder != "ER":
        flange = {"HSK63": 31.5, "BT30": 23.0}.get(holder, 31.75) * MM
        assert np.hypot(hv[:, 0], hv[:, 1]).max() == pytest.approx(flange)


def test_bt30_holder_shape():
    """Task 0049: BT30 – flange Ø46, 7:24 taper from Ø31.75 at the gauge line, 48.4 long, a pull stud above."""
    s = tools.resolved(tools.Spec(kind="FLAT", diameter=10 * MM, stick_out=40 * MM, holder="BT30"))
    assert s.holder_length == pytest.approx(45 * MM) and s.holder_diameter == pytest.approx(32 * MM)
    rings = tools.holder_rings(s)
    a = s.holder_length
    at_gauge = [r for z, r in rings if abs(z - a) < 1e-9]
    assert 15.875 * MM in [pytest.approx(r) for r in at_gauge]
    top = max(z for z, r in rings)
    assert top == pytest.approx(a + 48.4 * MM + 23 * MM)
    small = [r for z, r in rings if abs(z - (a + 48.4 * MM)) < 1e-9]
    assert any(r == pytest.approx((31.75 - 48.4 * 7 / 24) / 2 * MM) for r in small)
    assert "BT30" in tools.HOLDERS


def test_gauge_length_is_tip_to_gauge_line():
    """Task 0049: G43 lengths from the tip to the gauge line; a typed gauge length wins."""
    arbor = tools.resolved(tools.Spec(kind="FACE", diameter=50 * MM, stick_out=40 * MM, holder="BT30",
                                      holder_length=45 * MM))
    chuck = tools.resolved(tools.Spec(kind="FLAT", diameter=8 * MM, stick_out=38 * MM, holder="BT30",
                                      holder_length=60 * MM))
    assert tools.gauge_length(arbor) == pytest.approx(85 * MM)
    assert tools.gauge_length(chuck) == pytest.approx(98 * MM)
    assert tools.gauge_length(tools.Spec(kind="FLAT", stick_out=30 * MM)) == pytest.approx(30 * MM)   # no holder
    typed = tools.Spec(kind="VEE", diameter=10 * MM, stick_out=50 * MM, holder="BT30", gauge=90 * MM)
    assert tools.gauge_length(typed) == pytest.approx(90 * MM)


def test_fusion_bt30_holder_is_read():
    doc = {"data": [{"type": "flat end mill", "description": "EM 6", "unit": "millimeters",
                     "geometry": {"DC": 6, "LCF": 12, "LB": 30, "NOF": 3}, "post-process": {"number": 1},
                     "holder": {"description": "BT30 ER25 chuck A60",
                                "segments": [{"height": 25, "lower-diameter": 42, "upper-diameter": 42},
                                             {"height": 35, "lower-diameter": 46, "upper-diameter": 46}]}}]}
    t = tools.read_fusion(json.dumps(doc)).tools[0]
    assert t.holder == "BT30" and t.holder_length == pytest.approx(60 * MM)
    assert tools.gauge_length(t) == pytest.approx(90 * MM)


def test_drawn_end_mill_outer_diameter_is_on_the_lands():
    s = tools.default("FLAT")
    v, t, _p = tools.tool_mesh(s)
    r = np.hypot(v[:, 0], v[:, 1])
    flutes = v[:, 2] < s.flute_length * 0.6
    assert r[flutes].max() == pytest.approx(s.diameter / 2, abs=1e-9)
    assert r[flutes & (v[:, 2] > 1 * MM)].min() < 0.8 * s.diameter / 2      # the flutes are cut in
    prof, _a, _b = machining.profile_from_points(v, np.zeros(3), np.array([0, 0, 1.0]), t)
    tool = machining.classify(prof)
    assert tool.kind == "FLAT" and tool.radius == pytest.approx(s.diameter / 2, abs=0.05 * MM)


def test_cutting_shapes_per_type():
    face = tools.default("FACE")
    face.lead_angle = 45
    c = tools.cutting_tool(face)
    assert c.kind == "CUSTOM" and c.profile[0] == (0.0, face.diameter / 2)
    assert c.profile[1][1] - c.profile[0][1] == pytest.approx(tools.cutting_height(face))
    face.lead_angle = 90
    assert tools.cutting_tool(face).kind == "FLAT"
    assert tools.cutting_tool(tools.default("SLOT")).length == pytest.approx(tools.default("SLOT").width)
    d = tools.cutting_tool(tools.default("DRILL"))
    assert d.kind == "DRILL" and d.angle == 118
    assert tools.chip_kind(tools.default("THREAD")) == "END" and tools.chip_kind(tools.default("FACE")) == "FACE"


def test_flat_mill_with_a_corner_chamfer_is_a_flat_mill():
    R, c = 6 * MM, 0.3 * MM
    prof = [(0.0, R - c), (c, R), (26 * MM, R), (72 * MM, R)]
    t = machining.classify(prof)
    assert t.kind == "FLAT" and t.radius == pytest.approx(R)


def test_outline_between_vertices_of_a_helix():
    """Vertices alone: at most heights only flute vertices lie there; the cross-sections give the true outline."""
    s = tools.default("FLAT")
    s.diameter = 12 * MM
    s = tools.resolved(s)
    v, t, _p = tools.tool_mesh(s, seg=36)
    # shift every ring a little in height, so no two vertices share a height (like a CAD helix mesh)
    v = v.copy()
    v[:, 2] += np.random.default_rng(1).uniform(0, 0.2 * MM, len(v)) * (v[:, 2] > 0.5 * MM)
    vonly, _a, _b = machining.profile_from_points(v, np.zeros(3), np.array([0, 0, 1.0]))
    exact, _a, _b = machining.profile_from_points(v, np.zeros(3), np.array([0, 0, 1.0]), t)
    re_ = np.array([r for z, r in exact if 2 * MM < z < 15 * MM] or [6 * MM])
    assert re_.min() > 5.95 * MM and re_.max() < 6.01 * MM
    assert machining.classify(exact).radius == pytest.approx(6 * MM, abs=0.05 * MM)
    assert min(r for z, r in vonly if 2 * MM < z < 15 * MM) < 5.5 * MM    # vertices alone: flute vertices only


def test_from_outline_finds_the_holder_and_the_type():
    prof = [(0.0, 5 * MM), (22 * MM, 5 * MM), (22 * MM, 4.8 * MM), (35 * MM, 4.8 * MM), (35 * MM, 20 * MM),
            (95 * MM, 20 * MM), (95 * MM, 31.75 * MM), (111 * MM, 31.75 * MM)]
    s = tools.from_outline(prof)
    assert s.kind == "FLAT" and s.diameter == pytest.approx(10 * MM)
    assert s.stick_out == pytest.approx(35 * MM) and s.flute_length == pytest.approx(22 * MM)
    face = tools.from_outline([(0, 25 * MM), (6 * MM, 25 * MM), (6.01 * MM, 20 * MM), (40 * MM, 20 * MM)])
    assert face.kind == "FACE" and face.insert_size == pytest.approx(12 * MM, abs=0.1 * MM)
    drill = tools.from_outline([(0, 0), (1.8 * MM, 3 * MM), (60 * MM, 3 * MM)])
    assert drill.kind == "DRILL" and drill.angle == pytest.approx(118, abs=1)


FUSION = {
    "data": [
        {"type": "flat end mill", "description": "EM D10 Z3", "unit": "millimeters", "guid": "x",
         "geometry": {"DC": 10, "LCF": 22, "LB": 40, "NOF": 3, "SFDM": 10, "OAL": 75, "unknown-field": 1},
         "post-process": {"number": 1, "comment": ""},
         "holder": {"description": "SK40 ER32 collet chuck", "segments": [
             {"height": 30, "lower-diameter": 42, "upper-diameter": 42},
             {"height": 30, "lower-diameter": 50, "upper-diameter": 50}]}},
        {"type": "face mill", "description": "FM 50", "geometry": {"DC": 50, "NOF": 5, "TA": 45},
         "post-process": {"number": 2}},
        {"type": "bull nose end mill", "geometry": {"DC": 12, "RE": 1.5}, "post-process": {"number": 3}},
        {"type": "spot drill", "geometry": {"DC": 10, "SIG": 90}, "post-process": {"number": 4}},
        {"type": "chamfer mill", "geometry": {"DC": 12, "TA": 45}, "post-process": {"number": 5}},
        {"type": "drill", "unit": "inches", "geometry": {"DC": 0.25, "SIG": 135}, "post-process": {"number": 6}},
        {"type": "thread mill", "geometry": {"DC": 8, "TP": 1.25}, "post-process": {"number": 7}},
        {"type": "slot mill", "geometry": {"DC": 30, "LCF": 5, "SFDM": 12}, "post-process": {"number": 8}},
        {"type": "lollipop mill", "geometry": {"DC": 6}, "post-process": {"number": 9}},
        {"type": "probe", "description": "Renishaw", "post-process": {"number": 99}},
        {"type": "dovetail mill", "geometry": {"DC": 20}, "post-process": {"number": 2}},
    ]}


def test_fusion_library_json_and_tools_zip():
    res = tools.read_fusion(json.dumps(FUSION))
    by = {s.number: s for s in res.tools}
    assert sorted(by) == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    assert by[1].kind == "FLAT" and by[1].diameter == pytest.approx(10 * MM) and by[1].stick_out == pytest.approx(40 * MM)
    assert by[1].holder == "SK40" and by[1].holder_length == pytest.approx(60 * MM)
    assert by[1].holder_diameter == pytest.approx(50 * MM)
    assert by[2].kind == "FACE" and by[2].inserts == 5 and by[2].lead_angle == pytest.approx(45)
    assert by[3].kind == "BULL" and by[3].corner == pytest.approx(1.5 * MM)
    assert by[4].kind == "VEE" and by[4].angle == 90
    assert by[5].kind == "VEE" and by[5].angle == 90
    assert by[6].kind == "DRILL" and by[6].diameter == pytest.approx(6.35 * MM) and by[6].angle == 135
    assert by[7].kind == "THREAD" and by[7].pitch == pytest.approx(1.25 * MM)
    assert by[8].kind == "SLOT" and by[8].width == pytest.approx(5 * MM) and by[8].neck == pytest.approx(12 * MM)
    assert by[9].kind == "BALL" and "lollipop" in by[9].note
    assert by[10].kind == "SLOT" and "numbered 10" in by[10].note       # T2 was taken
    assert any("probe" in n for n in res.notes)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("tools.json", json.dumps(FUSION))
    res2 = tools.read_fusion(buf.getvalue())
    assert [s.number for s in res2.tools] == [s.number for s in res.tools]


def test_linuxcnc_tool_table():
    text = ("T1 P1 D6.0 Z+30.0 ;6 mm end mill\n"
            "T2 P7 D8.5 Z+45.5 ;8.5 drill 135°\n"
            "T3 P3 D50 Z+40 ;face mill 50\n"
            "T4 P4 D10 Z+35 ;spot drill 90 deg\n"
            "T5 P5 D12 Z+40 ;bull nose R1.5\n"
            ";comment line\n"
            "T6 P6 Z+20 ;no diameter\n")
    res = tools.read_linuxcnc(text)
    by = {s.number: s for s in res.tools}
    assert by[1].kind == "FLAT" and by[1].stick_out == pytest.approx(30 * MM) and by[1].pocket == 1
    assert by[2].kind == "DRILL" and by[2].angle == 135 and by[2].pocket == 7
    assert by[3].kind == "FACE"
    assert by[4].kind == "VEE" and by[4].angle == 90
    assert by[5].kind == "BULL" and by[5].corner == pytest.approx(1.5 * MM)
    assert by[6].diameter == pytest.approx(6 * MM) and "no diameter" in by[6].note


def test_program_tool_comments_fill_rows():
    prog = gcode.read("(T1 D=50. CR=0. - ZMIN=-1. - face mill)\n(T2 D=8. CR=0. - flat end mill)\n"
                      "(T3 D=6.8 CR=0. TAPER=118deg - drill)\n(T4 D=8. CR=0. - thread mill)\nT1 M6\nM30\n")
    rows = {n: tools.from_info(info) for n, info in prog.tools.items()}
    assert rows[1].kind == "FACE" and rows[1].diameter == pytest.approx(50 * MM) and rows[1].name == "face mill"
    assert rows[2].kind == "FLAT"
    assert rows[3].kind == "DRILL" and rows[3].angle == 118
    assert rows[4].kind == "THREAD"


def test_type_words_in_three_languages():
    assert tools.kind_from_text("Planfräser 63") == "FACE"
    assert tools.kind_from_text("vingerfrees 10") == "FLAT"
    assert tools.kind_from_text("Kugelfräser R3") == "BALL"
    assert tools.kind_from_text("Gewindefräser M8") == "THREAD"
    assert tools.kind_from_text("T-slot cutter") == "SLOT"
    assert tools.kind_from_text("NC spot drill 90") == "VEE"
    assert tools.kind_from_text("boor 6.8") == "DRILL"
    assert tools.kind_from_text("something") == ""


def test_checks_warn_but_do_not_refuse():
    s = tools.default("FLAT")
    s.diameter = 0.4
    s.stick_out = 0.5
    w = tools.checks(s, travel=(0.5, 0.4, 0.3))
    assert any("wider than tools usually are" in x for x in w)
    assert any("half the machine's travel" in x for x in w)
    assert any("further than the machine's Z travel" in x for x in w)
    assert tools.missing([1, 2, 7], [tools.default("FLAT", 1), tools.default("FLAT", 2)]) == [7]


def test_round_trip_through_fields():
    s = tools.default("SLOT", 4)
    d = {k: getattr(s, k) for k in tools.spec_fields()}
    assert tools.resolved(tools.Spec(**d)) == s
    assert math.isclose(tools.resolved(s).diameter, s.diameter)
