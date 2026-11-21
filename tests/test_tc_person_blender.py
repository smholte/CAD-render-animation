"""Task 0156 in Blender: the operator changes the tool on the test mill in its enclosure (tour set "operator",
tests/data/test_mill_cabinet.step), and the gloved hand of the "Three tools" set closes round the holder.

The posed person (the evaluated mesh, arms and all) is checked against every machine part at the frames of the change:
the clash check itself moves the operator's body without its arms (``clash.CLASH_MESH``), so the arms are checked
here. The hand may touch the door's handle bar while it holds it (the door's moves)."""

import math

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import animation, build, clash, gcode, tc_person, toolchange, tour  # noqa: E402
from fresing_render.core import gcode as gcore  # noqa: E402
from fresing_render.core import toolchange as TC  # noqa: E402


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    folder = str(tmp_path_factory.mktemp("tour"))
    out = tour.build_all(folder, "9.9.9", only=("operator",))
    assert not out["errors"], out["errors"]
    tour.open_set(folder, "9.9.9", "operator")
    sc = bpy.context.scene
    a = sc.fresing.animations[tour.OPERATOR_ANIM]
    r = animation.bake(sc, a)
    yield sc, a, r
    fresing_render.unregister()


def change_of(sc, a):
    sc.frame_set(1)                       # the schedule is read as the Build reads it: from the first frame
    b = a.blocks[0]
    mach = gcode.Machine(sc)
    sch = gcore.Schedule(gcode.read_program(sc, b, mach, start=gcode.start_point(mach))[0],
                         gcode.timing(sc, a, b, mach))
    cs = [c for c in sch.changes if c.person]
    assert len(cs) == 1
    return cs[0], animation.frame_of(a, b.start)


def tree(ob, dg):
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    M = ev.matrix_world
    t = BVHTree.FromPolygons([M @ v.co for v in me.vertices], [tuple(p.vertices) for p in me.polygons])
    ev.to_mesh_clear()
    return t


def test_build_has_the_operator(built):
    sc, a, r = built
    assert not r["warnings"], r["warnings"]
    ob = tc_person.operator(sc)
    assert ob is not None and tc_person._built(ob) and not ob.hide_render
    c, _f0 = change_of(sc, a)
    need = TC.person_min(c.door)
    assert c.door > 0 and c.hand[1] == pytest.approx(need, abs=1e-6)       # the 1 s pause grew to what it needs
    assert "per change" in tc_person.words(sc)
    door = sc.fresing.joints["Door"]
    vals = []
    for f in range(1, sc.frame_end + 1, 5):
        sc.frame_set(f)
        vals.append(door.frame.matrix_world.translation.x if door.frame else 0.0)
    trol = tc_person.trolley(sc)
    assert trol is not None and not trol.hide_render


def test_the_hands_never_go_into_the_machine(built):
    sc, a, _r = built
    c, f0 = change_of(sc, a)
    op = tc_person.operator(sc)
    keys = TC.person_keys(*c.hand, c.door)
    door_span = [(f0 + x * 25, f0 + y * 25) for x, y, n in keys if n in tc_person.core.DOOR_MOVES]
    door = next(o for o in sc.objects if o.get(build.PROP_NAME) == "SLIDING DOOR")      # the right one (task 0249)
    first, last = int(f0 + keys[0][0] * 25) - 25, int(f0 + keys[-1][1] * 25) + 25
    parts = [o for o in sc.objects if o.type == "MESH" and o is not op and not o.get(tc_person.TAG)
             and o.get(gcode.TAG) != "tool" and not o.name.startswith("FR ") and len(o.data.polygons)]
    hits = {}
    for f in range(first, last, 3):
        sc.frame_set(f)
        dg = bpy.context.evaluated_depsgraph_get()
        tp = tree(op, dg)
        holding_door = any(x <= f <= y for x, y in door_span)
        holding_t1 = f0 + keys[1][0] * 25 <= f <= f0 + TC.person_events(*c.hand, c.door)[0] * 25 + 2
        for o in parts:
            if o.hide_render or (holding_door and o is door) or (holding_t1 and o.name.startswith("END MILL")):
                continue
            if tp.overlap(tree(o, dg)):
                hits.setdefault(o.name, []).append(f)
    assert not hits, hits


def test_the_tools_go_where_the_hand_takes_them(built):
    sc, a, _r = built
    c, f0 = change_of(sc, a)
    out_t, in_t = TC.person_events(*c.hand, c.door)
    keys = {n: (x, y) for x, y, n in TC.person_keys(*c.hand, c.door)}
    carried = {o[tc_person.CARRY]: o for o in sc.objects if tc_person.CARRY in o}
    lying = {o[tc_person.ON_TROLLEY]: o for o in sc.objects if tc_person.ON_TROLLEY in o}
    assert set(carried) == set(lying) == {1, 2}
    sc.frame_set(int(f0 + keys["release"][0] * 25))
    in_spindle = bpy.data.objects[carried[1]["fr_cnc_src"]]          # the model's own T1 in its holder
    assert not in_spindle.hide_render
    spindle_place = np.array(tc_person._world(in_spindle))
    f = int(math.ceil(f0 + out_t * 25))
    sc.frame_set(f)
    assert not carried[1].hide_render and lying[1].hide_render
    assert np.allclose(np.array(carried[1].matrix_world), spindle_place, atol=0.004)   # out of the spindle
    sc.frame_set(int(math.ceil(f0 + keys["set"][1] * 25)) + 1)
    assert carried[1].hide_render and not lying[1].hide_render                   # laid on the trolley
    sc.frame_set(int(f0 + keys["take"][0] * 25))
    assert not lying[2].hide_render
    sc.frame_set(int(math.ceil(f0 + in_t * 25)) + 1)
    assert carried[2].hide_render and lying[2].hide_render
    trolley = tc_person.trolley(sc)
    top = tc_person._trolley_top(sc, trolley, 0.0)
    for o in lying.values():
        v = np.array([tuple(o.matrix_world @ p.co) for p in o.data.vertices])
        assert v[:, 2].min() > top + tc_person.core.CRADLE - 0.002            # on its cradles, not in the top


def test_clash_check_and_hiding(built):
    sc, a, _r = built
    rows = clash.check(sc, store=False).rows
    assert not rows, [clash.core.row_text(r) for r in rows[:3]]
    op = tc_person.operator(sc)
    assert op.get(clash.CLASH_MESH) is not None
    sc.fresing.operator_visible = False
    c, f0 = change_of(sc, a)
    sc.frame_set(int(f0 + (c.hand[0] + 2.0) * 25))
    shown = [o.name for o in sc.objects if (o is op or o is tc_person.trolley(sc) or tc_person.CARRY in o or
                                            tc_person.ON_TROLLEY in o) and not o.hide_render]
    assert not shown, shown
    sc.fresing.operator_visible = True
    sc.frame_set(int(f0 + (c.hand[0] + 2.0) * 25))
    assert not op.hide_render


def test_clear_keys_and_the_hand_instead(built):
    sc, a, _r = built
    op = tc_person.operator(sc)
    animation.clear_keys(sc)
    assert not [o for o in sc.objects if tc_person.CARRY in o]
    assert op.get(tc_person.HOME) is None
    b = a.blocks[0]
    b.gcode_operator = "HAND"
    assert b.gcode_hand and not b.gcode_person
    r = animation.bake(sc, a)
    assert not [w for w in r["warnings"] if "operator" in w.lower()]
    assert op.hide_render                                    # not used in this Build
    hand = bpy.data.objects.get(toolchange.HAND_NAME)
    assert hand is not None and hand.data.shape_keys.key_blocks.get("Open") is not None
    c, f0 = change_of_hand(sc, a)
    out_t, _in = TC.hand_events(*c.hand)
    sc.frame_set(int(f0 + c.hand[0] * 25) + 1)
    open_v = hand.data.shape_keys.key_blocks["Open"].value
    sc.frame_set(int(math.ceil(f0 + out_t * 25)) + 1)
    assert open_v > 0.8 and hand.data.shape_keys.key_blocks["Open"].value < 0.05
    b.gcode_operator = "PERSON"


def change_of_hand(sc, a):
    sc.frame_set(1)
    b = a.blocks[0]
    mach = gcode.Machine(sc)
    sch = gcore.Schedule(gcode.read_program(sc, b, mach, start=gcode.start_point(mach))[0],
                         gcode.timing(sc, a, b, mach))
    return next(c for c in sch.changes if c.hand is not None), animation.frame_of(a, b.start)
