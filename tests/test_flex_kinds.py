"""Task 0243: standard kinds, colours and sizes of hoses, cables and drag chains (core/flex_kinds.py,
blender/kinds.py), the four drag-chain link types (core/flex_chain.link_mesh) and the hose patterns
(blender/cable_looks.py kinds HOSE / BRAID / SLEEVE)."""

import math
import os
import sys

import numpy as np
import pytest

from fresing_render.core import flex_chain as CH
from fresing_render.core import flex_kinds as K
from fresing_render.core import materials_lib

HERE = os.path.dirname(__file__)
MM = 0.001


# ---------------------------------------------------------------------------
# core: no Blender
# ---------------------------------------------------------------------------

def test_every_owner_pick_is_there():
    assert [k.id for k in K.kinds("hose")] == ["HYDRAULIC", "BRAIDED", "PNEUMATIC", "SLEEVE"]
    assert [k.id for k in K.kinds("cable")] == ["MACHINE", "POWER", "OFFSHORE", "ROPE"]
    assert [k.id for k in K.kinds("chain")] == ["OPEN", "CLOSED", "HALF", "STEEL"]
    numbers = [k.number for k in K.KINDS]
    assert len(set(numbers)) == len(numbers) and 0 not in numbers           # 0 = "NONE" in the enums
    pneu = {c.id for c in K.get("PNEUMATIC").colours}
    assert pneu == {"BLUE", "BLACK", "CLEAR", "RED", "YELLOW", "GREEN", "SILVER"}
    assert {c.id for c in K.get("SLEEVE").colours} == {"BLACK", "ORANGE", "YELLOW"}
    assert {c.id for c in K.get("MACHINE").colours} == {"GREY", "ORANGE", "BLACK", "GREEN"}
    assert {c.id for c in K.get("POWER").colours} == {"BLACK", "GREY"}
    assert {c.id for c in K.get("ROPE").colours} == {"BRIGHT", "GALVANISED"}
    for kid in ("OPEN", "CLOSED", "HALF"):
        assert {c.id for c in K.get(kid).colours} == {"BLACK", "GREY", "ORANGE"}
    assert [c.id for c in K.get("STEEL").colours] == ["STEEL"]


def test_every_colour_has_a_library_material_and_a_valid_colour_text():
    from fresing_render.core import ral
    for k in K.KINDS:
        assert k.sizes and k.colours, k.id
        for c in k.colours:
            assert c.material in materials_lib.MATERIALS, (k.id, c.material)
            if materials_lib.needs_color(c.material):
                assert ral.parse_colour(c.text), (k.id, c.id, c.text)
            assert K.group_name(k.id, c.id)
    # the offshore cable and the rope keep the cable looks' own groups (old projects' groups are reused)
    assert K.group_name("OFFSHORE", "STRIPES") == "Power cables" and K.group_name("ROPE", "BRIGHT") == "Wire ropes"
    # one group (= one shared material) per kind and colour, no two the same
    names = [K.group_name(k.id, c.id) for k in K.KINDS for c in k.colours]
    chains = [K.group_name(k, c.id) for k in ("OPEN", "CLOSED", "HALF") for c in K.get(k).colours]
    assert len(set(names)) == len(names) and len(set(chains)) == 9


def test_hydraulic_sizes_are_en853_2sn():
    by = {s.id: s for s in K.get("HYDRAULIC").sizes}
    # EN 853 2SN, as the data sheets named in core/flex_kinds.py quote it: (outer Ø mm, smallest bend mm)
    for dn, od, bend in ((6, 15.4, 100), (10, 19.0, 130), (12, 22.6, 180), (19, 29.7, 240), (25, 38.5, 300),
                         (51, 68.2, 630)):
        s = by[f"DN{dn}"]
        assert s.od == pytest.approx(od * MM) and s.bend == pytest.approx(bend * MM)
    assert K.get("BRAIDED").sizes == K.get("HYDRAULIC").sizes
    ods = [s.od for s in K.get("HYDRAULIC").sizes]
    assert ods == sorted(ods)


def test_pneumatic_rope_and_invented_sizes():
    pu = {s.id: s for s in K.get("PNEUMATIC").sizes}
    assert [round(s.od / MM) for s in K.get("PNEUMATIC").sizes] == [4, 6, 8, 10, 12, 16]
    assert pu["OD8"].bend == pytest.approx(20 * MM) and pu["OD12"].bend == pytest.approx(35 * MM)
    for s in K.get("ROPE").sizes:                          # sheave D >= 20 d: bend to the rope's middle 10 d
        assert s.bend == pytest.approx(10 * s.od)
    for kid in ("MACHINE", "POWER", "OFFSHORE", "SLEEVE"):
        for s in K.get(kid).sizes:
            assert s.od > 0 and s.bend >= 4 * s.od - 1e-12
    for kid in ("OPEN", "STEEL"):
        for s in K.get(kid).sizes:
            assert s.width > s.height > 0 and s.pitch > 0 and s.radii and s.radii[0] >= s.pitch
            assert s.label.startswith("Chain ") and list(s.radii) == sorted(s.radii)


def test_nearest_size_and_radius():
    assert K.nearest_size("HYDRAULIC", od=0.0225).id == "DN12"
    assert K.nearest_size("PNEUMATIC", od=0.0079).id == "OD8"
    assert K.nearest_size("OPEN", width=0.066).id == "C25x50"
    assert K.nearest_size("ROPE").id == K.get("ROPE").sizes[len(K.get("ROPE").sizes) // 2].id     # no number: middle
    assert K.nearest_size("NONE") is None and K.size("HYDRAULIC", "") is None
    sz = K.size("OPEN", "C25x50")
    assert K.nearest_radius(sz, 0.11) == pytest.approx(0.1) and K.nearest_radius(sz, 0.0) == pytest.approx(0.075)
    assert K.nearest_radius(sz, 0.11, at_most=0.11) == pytest.approx(0.1)
    assert K.nearest_radius(sz, 0.06, at_most=0.06) == pytest.approx(0.06)          # none that small: kept
    assert K.colour("PNEUMATIC", "nonsense").id == "BLUE"
    assert K.matches(sz, "chain", width=sz.width, height=sz.height, pitch=sz.pitch)
    assert not K.matches(K.size("PNEUMATIC", "OD8"), "hose", od=0.008, bend=0.021)


def test_enum_items_keep_none_first_with_number_zero():
    items = K.enum_items(K.HOSE_ITEM_KINDS, "As in the CAD file", "x")
    assert items[0][0] == "NONE" and items[0][4] == 0
    assert [i[0] for i in items[1:]] == list(K.HOSE_ITEM_KINDS)


def test_pattern_look_values():
    assert K.pattern_look("PNEUMATIC", 0.008) is None and K.pattern_look("MACHINE", 0.01) is None
    h = K.pattern_look("HYDRAULIC", 0.02)
    assert h[3] == 4.0 and h[0] >= 0.12
    b = K.pattern_look("BRAIDED", 0.03)
    assert b[3] == 5.0 and b[1] == 24 and b[0] == pytest.approx(0.096)
    s = K.pattern_look("SLEEVE", 0.04)
    assert s[3] == 6.0 and s[1] == 1 and 0 < s[2] < 1


def _volume(pts, faces):
    p = np.asarray(pts, float)
    v = 0.0
    for f in faces:
        for i in range(1, len(f) - 1):
            v += np.dot(p[f[0]], np.cross(p[f[i]], p[f[i + 1]])) / 6.0
    return v


@pytest.mark.parametrize("kind", CH.LINK_TYPES)
def test_link_types_are_closed_solids_inside_their_size(kind):
    pitch, width, height = 0.035, 0.064, 0.035
    pts, faces = CH.link_mesh(kind, pitch, width, height)
    p = np.asarray(pts)
    assert _volume(pts, faces) > 0.0                       # faces look outward
    assert p[:, 2].min() >= -width / 2 - 1e-9 and p[:, 2].max() <= width / 2 + 1e-9
    assert p[:, 1].min() >= -height / 2 - 1e-9 and p[:, 1].max() <= height / 2 + 1e-9
    # every edge is used by exactly two faces: closed pieces
    edges = {}
    for f in faces:
        for a, b in zip(f, f[1:] + f[:1]):
            edges[(min(a, b), max(a, b))] = edges.get((min(a, b), max(a, b)), 0) + 1
    assert set(edges.values()) == {2}


def test_link_types_differ_where_they_should():
    pitch, width, height = 0.035, 0.064, 0.035

    def cover(kind, sign):
        """Share of the link's length covered at the top (+y, inside of the bend) or bottom (−y, outside)."""
        pts, faces = CH.link_mesh(kind, pitch, width, height)
        p = np.asarray(pts)
        t = min(max(0.06 * width, 0.0006), 0.2 * width)
        mid = np.isclose(np.abs(p[:, 2]), 0.5 * width - 1.5 * t)       # the crossbars' and lids' ends
        ys = p[mid, 1] * sign
        far = p[mid][ys > height / 2 - 0.2 * height]
        return (far[:, 0].max() - far[:, 0].min()) / pitch

    assert cover("OPEN", 1) < 0.5 and cover("OPEN", -1) < 0.5
    assert cover("CLOSED", 1) > 0.9 and cover("CLOSED", -1) > 0.9
    assert cover("HALF", -1) > 0.9 and cover("HALF", 1) < 0.5            # the lid on the outside of the bend
    steel = np.asarray(CH.link_mesh("STEEL", pitch, width, height)[0])
    assert steel[:, 0].min() < -0.05 * pitch and steel[:, 0].max() > 1.05 * pitch      # plates overlap the next
    # an unknown type (and an older project) is the open link of 0.2.180
    assert CH.link_mesh("??", pitch, width, height) == CH.link_mesh("OPEN", pitch, width, height)


def test_hose_patterns_in_plain_python():
    from fresing_render.blender import cable_looks as CL
    assert CL.kind_name(4.0) == "HOSE" and CL.kind_name(5.0) == "BRAID" and CL.kind_name(6.0) == "SLEEVE"
    assert CL.kind_name(3.0) == "SERVED" and CL.kind_name(1.0) == "POWER" and CL.kind_name(2.0) == "ROPE"
    look = K.pattern_look("HYDRAULIC", 0.02)
    s = np.linspace(0.0, 1.0, 4001)
    on_line = CL.pattern("HOSE", s, 0.0, 0.0, look)
    assert 0.2 < on_line.mean() < 0.5                     # blocks of letters along the line
    assert CL.pattern("HOSE", s, math.pi, 0.0, look).max() == 0.0          # nothing on the far side
    look = K.pattern_look("SLEEVE", 0.04)
    wrap = CL.pattern("SLEEVE", s, 0.3, 0.0, look)
    assert wrap.mean() == pytest.approx(look[2], abs=0.02)                 # the wrap covers its share
    look = K.pattern_look("BRAIDED", 0.02)
    h = CL.pattern("BRAID", s, 0.0, 0.0, look)
    assert 0.0 <= h.min() and h.max() <= 1.0 and h.std() > 0.1


# ---------------------------------------------------------------------------
# Blender
# ---------------------------------------------------------------------------

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import fresing_render  # noqa: E402
from fresing_render.blender import build, cable_looks, drawn, flex, hover, joints, kinds, logic, paths  # noqa: E402
from mathutils import Vector  # noqa: E402

HOSES_A = os.path.join(HERE, "data", "test_flex_hoses_a.step")
CHAINS = os.path.join(HERE, "data", "test_flex_chains_a.step")
PATHS_A = os.path.join(HERE, "data", "test_paths_a.step")


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture(scope="module")
def folder(tmp_path_factory):
    return str(tmp_path_factory.mktemp("kinds"))


def load(folder, path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    flex.forget()
    paths.forget()
    sc = bpy.context.scene
    sc.fresing.out_folder = folder
    assert bpy.ops.fresing.import_step(filepath=path, quality="draft") == {"FINISHED"}
    return sc


def named(sc, name):
    return next(o for o in sc.objects if o.get(build.PROP_NAME) == name)


def click(sc, origin, direction, want=None):
    ob, index, loc, normal = hover.cast(sc, bpy.context.evaluated_depsgraph_get(), Vector(origin), Vector(direction))
    assert index >= 0 and (want is None or ob.get(build.PROP_NAME) == want)
    return drawn.spot(ob, index, loc, normal)


def material_of(ob):
    return ob.material_slots[0].material if ob.material_slots else None


def test_a_hose_kind_and_size_set_the_numbers_and_the_shared_look(folder):
    sc = load(folder, HOSES_A)
    flex.set_up_test_hoses(sc)
    hoses = [it for it in sc.fresing.flex if it.kind == "HOSE"]
    assert len(hoses) >= 2
    a, b = hoses[0], hoses[1]
    look_before = material_of(a.part)
    assert a.hose_kind == "NONE" and a.size == "CUSTOM" and a.size_id == ""        # as every older project
    a.hose_kind = "PNEUMATIC"
    assert a.kind_colour == "BLUE" and a.size_id                                   # nearest standard size
    sz = K.size("PNEUMATIC", a.size_id)
    assert a.diameter == pytest.approx(sz.od, abs=1e-6) and a.min_radius == pytest.approx(sz.bend, abs=1e-6)
    assert a.part.get("fr_group_manual") == "Pneumatic tube, blue"
    m = material_of(a.part)
    assert m is not None and m is not look_before and m.get("fr_material") == "plastic_matte"
    # a size pick: the numbers at once; the tube drawn is that thick (Ø within 0.1 mm)
    a.size = "OD12"
    assert a.diameter == pytest.approx(0.012, abs=1e-6) and a.min_radius == pytest.approx(0.035, abs=1e-6)
    bpy.context.view_layer.update()
    ev = a.part.evaluated_get(bpy.context.evaluated_depsgraph_get())
    me = ev.to_mesh()
    pts = np.array([v.co[:] for v in me.vertices])
    ev.to_mesh_clear()
    line = flex.shape_now(sc, a)
    mw = np.array(a.part.matrix_world)
    world = pts @ mw[:3, :3].T + mw[:3, 3]
    k = len(line) // 2
    mid, tan = line[k], line[k + 1] - line[k - 1]
    tan = tan / np.linalg.norm(tan)
    rel = world - mid
    along = rel @ tan
    near = rel[(np.abs(along) < 0.003) & (np.linalg.norm(rel, axis=1) < 0.02)]
    radial = np.linalg.norm(near - np.outer(near @ tan, tan), axis=1)
    assert len(near) and radial.max() == pytest.approx(0.006, abs=0.0001)
    # a number by hand: Custom
    a.diameter = 0.0125
    assert a.size_id == "" and a.size == "CUSTOM"
    # the same kind and colour on another hose: the same material (shared, not one per item)
    b.hose_kind = "PNEUMATIC"
    assert material_of(b.part) is material_of(a.part)
    b.colour = "RED"
    assert material_of(b.part) is not material_of(a.part)
    assert b.part.get("fr_group_manual") == "Pneumatic tube, red"
    # a kind with a pattern writes the look numbers the material reads; the tube has the attribute
    b.hose_kind = "BRAIDED"
    assert list(b.part[cable_looks.LOOK])[3] == 5.0
    assert material_of(b.part).get("fr_material") == "hose_braided"
    bpy.context.view_layer.update()
    ev = b.part.evaluated_get(bpy.context.evaluated_depsgraph_get())
    assert cable_looks.ATTR in ev.data.attributes
    # back to "As in the CAD file": the look it had, no pattern numbers
    b.hose_kind = "NONE"
    assert cable_looks.LOOK not in b.part and b.part.get("fr_group_manual", "") != "Steel-braided hose, stainless steel"


def test_chain_types_build_roll_and_change_the_link(folder):
    sc = load(folder, CHAINS)
    flex.set_up_test_chains(sc)
    cad = next(it for it in sc.fresing.flex if it.name == "CHAIN X.ASM")
    assert not cad.made_links and not kinds.can_size(cad)          # CAD links keep their own shape
    flex.remove(sc, flex.index_of(sc, cad))
    rows = [o for o in build.iter_parts(sc) if build.logical_parent(o) == named(sc, "CHAIN X.ASM")]
    logic.exclude(rows, True)
    a = click(sc, (-0.07, -1, 0.661), (0, 1, 0), "CHAIN BRACKET X FIXED")
    b = click(sc, (-0.01, -1, 0.83), (0, 1, 0), "CHAIN BRACKET X MOVING")
    logic.exclude(rows, False)
    ch, notes = flex.draw_chain(sc, a, b, replace=rows[0])
    assert ch.made_links and ch.chain_kind == "NONE"
    length = ch.pitch * ch.count
    radius0 = ch.radius
    for kid in ("OPEN", "CLOSED", "HALF", "STEEL"):
        radius0 = ch.radius
        ch.chain_kind = kid
        sz = K.size(kid, ch.size_id)
        assert sz is not None and ch.pitch == pytest.approx(sz.pitch, abs=1e-6)
        assert ch.width == pytest.approx(sz.width, abs=1e-6) and ch.height == pytest.approx(sz.height, abs=1e-6)
        # a standard radius no bigger than the brackets allow (half their gap), else the drawn one
        assert ch.radius in [pytest.approx(r, abs=1e-6) for r in sz.radii] + [pytest.approx(radius0, abs=1e-6)]
        assert ch.radius <= radius0 + 0.001
        assert abs(ch.pitch * ch.count - length) <= ch.pitch                     # its length kept to a link
        bpy.context.view_layer.update()
        link = bpy.data.objects[ch["link_name"]]
        assert link.get("fr_flex_link") == kid
        for x in (-0.375, 0.0, 0.375):                                             # it rolls with its axis
            joints.set_value(joints.find(sc, "X"), x)
            bpy.context.view_layer.update()
            flex.refresh(sc)
            assert flex.status(sc, ch)[1] == "OK", (kid, x, flex.status(sc, ch))
            pins = flex.pins_now(sc, ch)
            gaps = np.linalg.norm(np.diff(pins, axis=0), axis=1)
            assert np.allclose(gaps, ch.pitch, atol=1e-6)                        # links one pitch apart
            end = drawn.world_spot(ch.b_part, ch.b_point, (1, 0, 0))[0]
            assert np.linalg.norm(pins[-1] - end) < 0.1 * MM
    assert ch.part.get("fr_group_manual") == "Steel chain, steel"


def test_cable_kinds_set_look_group_and_size(folder):
    sc = load(folder, PATHS_A)
    paths.set_up_test_model(sc)
    cab = sc.fresing.cables[0]
    look0 = cab.look
    cab.cable_kind = "ROPE"
    assert cab.look == "ROPE" and cab.kind_colour == "BRIGHT" and cab.size_id
    assert cab.part.get("fr_group_manual") == "Wire ropes"
    sz = K.size("ROPE", cab.size_id)
    assert cab.diameter == pytest.approx(sz.od, abs=1e-6) and cab.mbr == pytest.approx(sz.bend, abs=1e-6)
    cab.colour = "GALVANISED"
    assert cab.part.get("fr_group_manual") == "Wire ropes, galvanised"
    assert material_of(cab.part).get("fr_material") == "wire_rope_galv"
    cab.cable_kind = "MACHINE"
    assert cab.look == "PLAIN" and cab.part.get("fr_group_manual") == "Machine cable, grey"
    cab.cable_kind = "OFFSHORE"
    assert cab.look == "POWER" and cab.part.get("fr_group_manual") == "Power cables"
    cab.colour = "SERVED"
    assert cab.look == "SERVED"
    cab.mbr = 1.0
    assert cab.size_id == ""
    assert look0 in ("POWER", "ROPE", "SERVED", "PLAIN")


def test_kinds_survive_save_reopen_and_build(folder):
    from fresing_render.blender import animation
    sc = load(folder, HOSES_A)
    flex.set_up_test_hoses(sc)
    a = next(it for it in sc.fresing.flex if it.kind == "HOSE")
    a.hose_kind = "SLEEVE"
    a.colour = "ORANGE"
    a.size = "S25"
    name, look = a.name, list(a.part[cable_looks.LOOK])
    path = os.path.join(folder, "kinds.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    a = flex.find(sc, name)
    assert (a.hose_kind, a.kind_colour, a.size_id, a.size) == ("SLEEVE", "ORANGE", "S25", "S25")
    assert a.diameter == pytest.approx(0.025, abs=1e-6) and list(a.part[cable_looks.LOOK]) == pytest.approx(look)
    assert material_of(a.part).get("fr_material") == "hose_sleeve" and material_of(a.part).get("fr_color") == "#E8650E"
    # Build: the hose follows along the animation with its kind; nothing needs a Python driver (scripts off)
    anim = sc.fresing.animations.add()
    anim.name = "Kinds"
    blk = anim.blocks.add()
    blk.kind, blk.joint, blk.start, blk.duration = "JOINT", "Luff", 0.0, 1.0
    blk.use_from, blk.to_angle = True, 0.2
    animation.bake(sc, anim)
    assert flex.status(sc, a)[1] == "OK"
    ad = a.part.animation_data
    assert ad is None or all(fc.driver.type != "SCRIPTED" or fc.driver.is_simple_expression for fc in ad.drivers)


def test_a_model_update_keeps_kinds_and_their_looks(folder):
    sc = load(folder, HOSES_A)
    flex.set_up_test_hoses(sc)
    a = next(it for it in sc.fresing.flex if it.kind == "HOSE")
    a.hose_kind = "BRAIDED"
    name = a.name
    root = build.model_roots(sc)[0]
    assert bpy.ops.fresing.import_step(filepath=os.path.join(HERE, "data", "test_flex_hoses_b.step"), quality="draft",
                                       update_root=root.name) == {"FINISHED"}
    a = flex.find(sc, name)
    assert a.hose_kind == "BRAIDED" and a.size_id
    assert material_of(a.part).get("fr_material") == "hose_braided"
    assert list(a.part[cable_looks.LOOK])[3] == 5.0
