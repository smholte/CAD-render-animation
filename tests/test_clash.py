"""Task 0065: the clash check in Blender, against hand calculations.

Generic model (tools/make_test_clash.py): arm B turns into place, then arm A comes down onto it; A's flat underside
ends exactly 6.0 mm inside B's flat side (deepest at the last frame). Arm A passes 2.0 mm above a low block (a near
miss) and, turned the other way within one frame, goes through a thin post (found only between frames). Pins turn
in their bores all the time (touching, never a clash).

The test tour's projects (crane, cylinder, mechanisms, way cover, CNC gantry, tool changes by hand and with the
changer, milling) are checked too: no false clashes; the clashes the check finds there are real faults of those
simple test models or of their set-ups, each named below with the reason.
"""

import math
import os

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from mathutils import Vector  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import animation, build, clash, joints, logic, machining, tour  # noqa: E402
from fresing_render.core import clash as core  # noqa: E402

HERE = os.path.dirname(__file__)
MODEL = os.path.join(HERE, "data", "test_clash.step")
MM = 1e-3


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def load(tmp_path, path=MODEL):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path)
    assert bpy.ops.fresing.import_step(filepath=path, quality="draft") == {"FINISHED"}
    return sc


def named(sc, name):
    return next(o for o in sc.objects if o.get(build.PROP_NAME) == name)


def arms(sc, name="Arms meet"):
    a = sc.fresing.animations.add()
    a.name, a.tail, a.fps = name, 0.0, "25"
    tour.clash_arms(sc, a)
    sc.fresing.animations_index = len(sc.fresing.animations) - 1
    return a


@pytest.fixture()
def scene(tmp_path):
    sc = load(tmp_path)
    animation.bake(sc, arms(sc))
    return sc


def overlap_by_hand(sc) -> float:
    """How far arm A's underside is inside arm B (mm), from the two arms' places and their boxes in the CAD file:
    points spread over A's underside (local x = +20 mm) tested against B's box, and B's top side (local x = +30 mm)
    against A's box; a point's depth is its distance to the nearest face of the other box."""
    A, B = named(sc, "ARM.A"), named(sc, "ARM.B")
    boxes = {"A": (np.array([-20, 14, 15]), np.array([20, 744, 55])),
             "B": (np.array([970, -30, 5]), np.array([1030, 503, 65]))}
    ys = {"A": np.linspace(14, 744, 300), "B": np.linspace(-30, 503, 300)}
    zs = {"A": np.linspace(15, 55, 9), "B": np.linspace(5, 65, 9)}
    best = 0.0
    for me, other, face_x, m_me, m_other in (("A", "B", 20.0, A, B), ("B", "A", 1030.0, B, A)):
        to_other = m_other.matrix_world.inverted() @ m_me.matrix_world
        lo, hi = boxes[other]
        for y in ys[me]:
            for z in zs[me]:
                p = np.array(to_other @ (Vector((face_x, y, z)) / 1000.0)) * 1000.0
                if np.all(p > lo) and np.all(p < hi):
                    best = max(best, float(np.min(np.minimum(p - lo, hi - p))))
    return best


# ---------------------------------------------------------------------------
# the known clash
# ---------------------------------------------------------------------------

def test_known_clash_parts_frames_and_depth(scene):
    sc = scene
    run = clash.check(sc)
    rows = [r for r in run.rows if r.kind == "CLASH"]
    assert len(rows) == 1, [core.row_text(r) for r in rows]          # pins turning in bores, block, post: none
    r = rows[0]
    assert {r.a, r.b} == {"ARM.A", "ARM.B"}
    assert abs(r.depth / MM - tour.CLASH_DEPTH) < 0.1
    assert r.frame_to == sc.frame_end and r.t_deep == sc.frame_end
    # the first frame deeper than 0.5 mm, worked out by hand from the arms' places
    first = None
    for f in range(1, sc.frame_end + 1):
        sc.frame_set(f)
        if overlap_by_hand(sc) > 0.5:
            first = f
            break
    assert first is not None and abs(r.frame_from - first) <= 1, (r.frame_from, first)
    sc.frame_set(sc.frame_end)
    assert abs(overlap_by_hand(sc) - 6.0) < 0.05
    # stored with the project, a marker at its start
    c = clash.settings(sc)
    assert c.checked and c.clashes == 1 and c.anim == "Arms meet" and len(c.rows) == 1
    marks = [m for m in sc.timeline_markers if m.name.startswith(clash.MARK)]
    assert [(m.name, m.frame) for m in marks] == [(f"{clash.MARK}ARM.A × ARM.B", r.frame_from)]
    assert clash.state(sc)["text"] == "1 clash"
    # the check leaves the frame where it was
    assert run.stats["moments"] == sc.frame_end and run.stats["bodies"] == 3


def test_a_deeper_clash_depth_setting_lets_it_pass(scene):
    clash.settings(scene).depth = 7 * MM
    run = clash.check(scene)
    assert not run.rows and clash.state(scene)["text"] == "No clashes"


def test_near_misses_when_asked(scene):
    c = clash.settings(scene)
    run = clash.check(scene)
    assert not [r for r in run.rows if r.kind == "NEAR"]
    c.use_near, c.near_distance = True, 5 * MM
    run = clash.check(scene)
    near = [r for r in run.rows if r.kind == "NEAR"]
    assert len(near) == 1 and {near[0].a, near[0].b} == {"ARM.A", "BLOCK"}, [core.row_text(r) for r in run.rows]
    assert abs(near[0].depth / MM - 2.0) < 0.1                       # arm A passes 2.0 mm above the block
    assert [r.kind for r in run.rows] == ["CLASH", "NEAR"]
    assert c.near_misses == 1 and c.clashes == 1


def test_a_fast_move_cannot_pass_through_between_two_frames(tmp_path, monkeypatch):
    sc = load(tmp_path)
    a = sc.fresing.animations.add()
    a.name, a.tail, a.fps = "Fast swing", 0.2, "25"
    joints.create(sc, "ROTATE", [named(sc, "ARM.A.ASM")], Vector((0.0, 0.044, 0.0)), Vector((0, 0, 1)), name="Arm A")
    tour._joint_step(a, "Arm A", 0.0, 0.04, math.radians(90))      # 90° within one frame
    animation.bake(sc, a)
    run = clash.check(sc)
    post = [r for r in run.rows if r.kind == "CLASH" and "POST" in (r.a, r.b)]
    assert len(post) == 1 and {post[0].a, post[0].b} == {"ARM.A", "POST"}
    assert 1.0 < post[0].t_deep < 2.0 and post[0].depth > core.DEPTH
    # on the frames themselves the arm is nowhere near the post
    A, P = named(sc, "ARM.A"), named(sc, "POST")
    ma, mp = clash._mesh_from(A.data), clash._mesh_from(P.data)
    for f in (1, 2):
        sc.frame_set(f)
        rel = np.linalg.inv(np.array(A.matrix_world, dtype=float)) @ np.array(P.matrix_world, dtype=float)
        assert clash.narrow(ma, mp, rel) == (0.0, math.inf)
    # without the moments between frames it would slip through
    monkeypatch.setattr(core, "STEP", 10.0)
    assert not [r for r in clash.check(sc, store=False).rows if "POST" in (r.a, r.b)]


def test_hidden_parts_are_skipped_while_hidden(tmp_path):
    sc = load(tmp_path)
    logic.set_hidden(named(sc, "ARM.B.ASM"), True)
    a = arms(sc)
    animation.bake(sc, a)
    assert named(sc, "ARM.B").hide_render
    assert not clash.check(sc).rows
    # shown again by a Show step after the arms met: the clash counts from then on
    logic.set_hidden(named(sc, "ARM.B.ASM"), False)
    blk = a.blocks.add()
    blk.kind, blk.start = "SHOW", 1.96
    ob = named(sc, "ARM.B.ASM")
    blk.target_name, blk.target_uid = ob.name, ob.get(build.PROP_UID, "")
    logic.set_hidden(ob, True)
    animation.bake(sc, a)
    rows = clash.check(sc).rows
    assert len(rows) == 1 and rows[0].frame_from >= 50, [core.row_text(r) for r in rows]


# ---------------------------------------------------------------------------
# a click on a row, the project, Build again, the queue note
# ---------------------------------------------------------------------------

def test_click_a_row_frame_selection_red_and_materials_untouched(scene):
    sc = scene
    clash.check(sc)
    sc.frame_set(1)
    before = {n: [m.material.name if m.material else "" for m in named(sc, n).material_slots]
              for n in ("ARM.A", "ARM.B")}
    c = clash.settings(sc)
    c.rows_index = 0                                   # what a click in the list does
    r = c.rows[0]
    assert sc.frame_current + sc.frame_subframe == pytest.approx(r.deep)
    assert {o.get(build.PROP_NAME) for o in bpy.context.selected_objects} == {"ARM.A", "ARM.B"}
    assert set(clash.red_names()) == {named(sc, "ARM.A").name, named(sc, "ARM.B").name}
    after = {n: [m.material.name if m.material else "" for m in named(sc, n).material_slots]
             for n in ("ARM.A", "ARM.B")}
    assert after == before
    assert bpy.ops.fresing.clash_red_off() == {"FINISHED"} and not clash.red_names()
    assert bpy.ops.fresing.clash_show(index=0) == {"FINISHED"} and clash.red_names()
    clash.hide_red()


def test_kept_with_the_project_and_cleared_by_another_build(scene, tmp_path):
    sc = scene
    assert bpy.ops.fresing.clash_check() == {"FINISHED"}         # the button (run at once from a script)
    path = str(tmp_path / "clash é.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    c = clash.settings(sc)
    assert c.checked and len(c.rows) == 1 and clash.state(sc)["text"] == "1 clash"
    # Build again, the same steps: the result still fits
    a = sc.fresing.animations["Arms meet"]
    animation.bake(sc, a)
    assert clash.state(sc)["text"] == "1 clash" and not clash.drop_if_stale(sc)
    # another end: not checked since the last Build; the result and its markers go
    a.blocks[1].to_angle = math.radians(-85)
    animation.bake(sc, a)
    st = clash.state(sc)
    assert st["stale"] and st["text"] == "Not checked since the last Build"
    assert clash.drop_if_stale(sc)
    assert not c.checked and not len(c.rows) and not [m for m in sc.timeline_markers if m.name.startswith(clash.MARK)]
    assert [m for m in sc.timeline_markers if m.name.startswith("▸ ")]          # the steps' own markers stay
    # Clear keys: nothing built, nothing to say
    animation.clear_keys(sc)
    assert clash.state(sc)["text"] == "Build first"
    with pytest.raises(clash.ClashError):
        clash.check(sc)
    assert bpy.ops.fresing.clash_check() == {"CANCELLED"}


def test_the_render_queue_note(scene):
    sc = scene
    s = sc.fresing
    assert bpy.ops.fresing.queue_add(kind="ANIMATION", name="Arms meet", start=False) == {"FINISHED"}
    assert s.last_message == "'Arms meet' was not checked for clashes (6 Animation > Clash check)"
    clash.check(sc)
    s.last_message = ""
    bpy.ops.fresing.queue_add(kind="ANIMATION", name="Arms meet", start=False)
    assert s.last_message.startswith("'Arms meet' has 1 clash")
    clash.settings(sc).depth = 7 * MM
    clash.check(sc)
    s.last_message = ""
    bpy.ops.fresing.queue_add(kind="ANIMATION", name="Arms meet", start=False)
    assert s.last_message == ""                       # checked, no clashes: nothing to say
    assert len(s.queue) == 3                          # the note never stops a job going in


def test_clear_the_result(scene):
    clash.check(scene)
    assert bpy.ops.fresing.clash_clear() == {"FINISHED"}
    c = clash.settings(scene)
    assert not c.checked and not len(c.rows) and clash.state(scene)["text"] == "Not checked since the last Build"


# ---------------------------------------------------------------------------
# tools: the cutting part may go through the workpiece, the holder and spindle may not
# ---------------------------------------------------------------------------

def _set(set_id, tmp_path):
    folder = str(tmp_path / "tour")
    out = tour.build_all(folder, "9.9.9", only=(set_id,))
    assert not out["errors"], out["errors"]
    tour.open_set(folder, "9.9.9", set_id)
    return bpy.context.scene


def test_milling_the_cut_is_not_a_clash(tmp_path, monkeypatch):
    sc = _set("mill", tmp_path)
    animation.clear_keys(sc)                       # (puts back what the tour's own Build saw: the finished part shown)
    machining.set_finished(sc, named(sc, "FINISHED PART"))          # the finished part is a limit, not shown
    a = sc.fresing.animations["Mill a slot"]
    a.start_shot = ""                                               # (the tour's start scene shows it)
    animation.bake(sc, a)
    assert not clash.check(sc).rows
    # proof that the rule does it: without the tools' zones the bit plunging 25 mm deep is a clash
    monkeypatch.setattr(clash, "tools_of", lambda scene: {})
    rows = clash.check(sc, store=False).rows
    assert any({r.a, r.b} == {"STOCK 200x200x40", "END MILL D10"} for r in rows)


def test_gantry_the_spindle_hits_a_block_placed_too_high(tmp_path):
    sc = _set("gantry", tmp_path)
    a = sc.fresing.animations["G-code"]
    animation.bake(sc, a)
    rows = clash.check(sc).rows
    # the test gantry's right side runs through the tool carousel's disc when the gantry moves along Y (its CAD:
    # the disc reaches x 400 … 600, the side x 390 … 410): a real fault of the test model
    assert {frozenset((r.a, r.b)) for r in rows} == {frozenset(("GANTRY SIDE R", "CAROUSEL DISC"))}
    # a clamp block put on the bed 40 mm higher than the stock under the program's path
    stock = named(sc, "STOCK 300x200x30")
    clamp = stock.copy()
    for col in stock.users_collection:
        col.objects.link(clamp)
    clamp[build.PROP_NAME] = "CLAMP"
    clamp[build.PROP_UID] = stock.get(build.PROP_UID, "") + "/clamp"
    clamp.matrix_world = Matrix_translation(0.0, 0.0, 0.040) @ stock.matrix_world
    bpy.context.view_layer.update()
    flat = [v for row in clamp.matrix_basis for v in row]
    clamp[build.PROP_CAD_BASIS] = flat                  # its own place in the CAD model (poses put parts there)
    clamp[build.PROP_REST_BASIS] = flat
    animation.bake(sc, a)
    assert clamp.matrix_world.translation.z - stock.matrix_world.translation.z == pytest.approx(0.04, abs=1e-6)
    rows = clash.check(sc).rows
    pairs = {frozenset((r.a, r.b)) for r in rows}
    assert frozenset(("SPINDLE", "CLAMP")) in pairs, [core.row_text(r) for r in rows]
    assert frozenset(("TOOL T1 FLAT D6", "CLAMP")) in pairs
    spindle = next(r for r in rows if {r.a, r.b} == {"SPINDLE", "CLAMP"})
    assert spindle.depth > 1 * MM


def Matrix_translation(x, y, z):
    from mathutils import Matrix
    return Matrix.Translation((x, y, z))


# ---------------------------------------------------------------------------
# the test tour's projects: no false clashes
# ---------------------------------------------------------------------------

def _rows(sc, anim):
    animation.bake(sc, sc.fresing.animations[anim])
    return clash.check(sc).rows


def test_no_false_clashes_crane_and_way_cover(tmp_path):
    sc = _set("crane", tmp_path)
    for a in ("Boom up", "Boom and trolley", "Finished video", "Queue video", "Turntable"):
        assert not _rows(sc, a), a
    sc = _set("waycover", tmp_path)
    assert not _rows(sc, "X axis out and back")


def test_no_false_clashes_cylinder_and_mechanisms(tmp_path):
    sc = _set("cylinder", tmp_path)
    # only the front cylinder is set up in the tour: the second one and the telescopic one stand still while the
    # arm lifts, so the arm's pin is torn through them (real). Left out, the rest has no clash.
    rows = _rows(sc, "Stroke out")
    assert rows and all("ARM.ROD.PIN" in (r.a, r.b) for r in rows)
    still = [o for o in sc.objects if o.get(build.PROP_NAME) in ("CYL.ASM", "TELE.ASM")
             and abs(o.matrix_world.translation.y - 0.08) > 0.01]
    assert len(still) == 2
    logic.exclude(still)
    assert not _rows(sc, "Stroke out")
    sc = _set("linkage", tmp_path)
    # the lifting cylinder is no part of the tour's scissor mechanism: it stands still and the arm's pin is torn
    # through its rod end (real); the slider-crank's crank pin goes through the bearing block on every turn (the
    # test model's bearing is a solid block): 10 mm, the pin's radius
    logic.exclude([named(sc, "LIFT.CYL.ASM")])
    rows = _rows(sc, "Lift and crank")
    assert [frozenset((r.a, r.b)) for r in rows] == [frozenset(("CRANK.BEARING", "CRANK.CRANK.PIN"))]
    assert abs(rows[0].depth / MM - 10.0) < 0.2


def test_no_false_clashes_tool_changes(tmp_path):
    sc = _set("tools", tmp_path)
    animation.clear_keys(sc)
    machining.set_finished(sc, named(sc, "FINISHED PART"))
    sc.fresing.animations["Three tools"].start_shot = ""
    # tool copies in the spindle, the hand, the cut: nothing
    assert not _rows(sc, "Three tools")
    sc = _set("atc", tmp_path)
    rows = _rows(sc, "Tool changer")
    # the test gantry's crude shapes: the spindle (a plain cylinder) goes down through the carousel disc to the
    # pockets, the carriage box hangs below the spindle nose when Z is up, the gantry side runs through the disc.
    # Never a tool against its own spindle or pocket.
    allowed = {frozenset(("SPINDLE", "CAROUSEL DISC")), frozenset(("GANTRY SIDE R", "CAROUSEL DISC"))}
    for r in rows:
        pair = frozenset((r.a, r.b))
        assert pair in allowed or pair == frozenset(("CARRIAGE", r.a if r.b == "CARRIAGE" else r.b)), core.row_text(r)
        tool = any(n.startswith(("FR tool", "TOOL ")) for n in (r.a, r.b))
        assert not ({r.a, r.b} & {"SPINDLE", "CAROUSEL DISC"} and tool)
