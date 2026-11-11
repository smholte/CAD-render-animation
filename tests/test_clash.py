"""Task 0065: the clash check in Blender, against hand calculations.

Generic model (tools/make_test_clash.py): arm B turns into place, then arm A comes down onto it; A's flat underside
ends exactly 6.0 mm inside B's flat side (deepest at the last frame). Arm A passes 2.0 mm above a low block (a near
miss) and, turned the other way within one frame, goes through a thin post (found only between frames). Pins turn
in their bores all the time (touching, never a clash).

Task 0067: every animation of every test-tour project is built and checked: 0 rows (the clash model keeps its 6.0 mm).
The faults the check found there were fixed in the test models (double arm, carousel gantry, slider-crank) and the
tour's set-ups (the scissor lift's cylinder), and one in the check itself (points beside a sharp outer edge).
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


def test_a_build_while_the_check_runs_drops_its_result(scene):
    """0068 row 12: the animation built again while the check reads frames (it lets clicks through): the result is
    not stored as up to date (it belongs to the earlier build, or to a mix of both)."""
    sc = scene
    run = clash.Check(sc)
    gen = run.steps()
    next(gen)                                                       # the set-up
    next(gen)                                                       # reading frames
    a = arms(sc, "Other")                                           # the user builds another animation
    a.blocks[1].to_angle = math.radians(-85)
    animation.bake(sc, a)
    for _p in gen:
        pass
    assert not clash.save(sc, run)
    c = clash.settings(sc)
    assert not c.checked and not len(c.rows) and clash.state(sc)["text"] == "Not checked since the last Build"
    # the same through the whole check: stored, up to date
    run = clash.check(sc)
    assert run.stored and c.checked and clash.state(sc)["checked"]


def test_milling_and_coolant_follow_a_scrub_while_the_check_reads(scene, monkeypatch):
    """0068 row 19d: the guard (milling and coolant skip their per-frame work) is let go between two ticks, and a
    frame the user goes to meanwhile is where the time line ends up."""
    from fresing_render.blender import coolant
    monkeypatch.setattr(clash, "READ_BATCH", 3)
    sc = scene
    sc.frame_set(2)
    run = clash.Check(sc)
    gen = run.steps()
    next(gen)
    seen = 0
    for p in gen:
        if p >= 0.4:
            break
        assert machining._STATE["guard"] == 0 and coolant._STATE["guard"] == 0
        assert sc.frame_current == (2 if seen < 2 else 7)
        seen += 1
        if seen == 2:
            sc.frame_set(7)                                         # the user scrubs between two ticks
    for _p in gen:
        pass
    assert seen > 3 and sc.frame_current == 7
    assert machining._STATE["guard"] == 0 and coolant._STATE["guard"] == 0
    assert clash.save(sc, run) and len(run.rows) == 1               # the same result as without the scrub


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
    assert not clash.check(sc).rows             # (0067: the carousel's disc is clear of the gantry's side)
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
# the test tour's projects: no false clashes (task 0067)
# ---------------------------------------------------------------------------

TOUR_SECONDS = 360          # time box of the whole check below (build ~40 s, checks ~70 s on a 4-core machine; the
                            # toolpath set's milling program adds ~2 min, task 0029)


def test_every_tour_animation_has_no_clash(tmp_path):
    """Every animation of every test-tour project is built and checked: 0 rows, except the clash model's own 6.0 mm.
    A new tour set (a new function's stop) is checked here by itself."""
    import time
    t0 = time.perf_counter()
    folder = str(tmp_path / "tour")
    out = tour.build_all(folder, "9.9.9")
    assert not out["errors"], out["errors"]
    found, checked = {}, 0
    for sid in tour.SETS:
        tour.open_set(folder, "9.9.9", sid)
        sc = bpy.context.scene
        for a in list(sc.fresing.animations):
            animation.bake(sc, a)
            rows = clash.check(sc, store=False).rows
            checked += 1
            if sid == "clash":
                assert [frozenset((r.a, r.b)) for r in rows] == [frozenset(("ARM.A", "ARM.B"))], sid
                assert abs(rows[0].depth / MM - tour.CLASH_DEPTH) < 0.1
            elif rows:
                found[f"{sid} / {a.name}"] = [core.row_text(r) for r in rows[:5]]
    assert not found, found
    assert checked >= 15
    assert time.perf_counter() - t0 < TOUR_SECONDS


# ---------------------------------------------------------------------------
# the inside test beside sharp edges, the double arm's hand-overs (task 0067)
# ---------------------------------------------------------------------------

def _wedge(deg):
    """A prism along Y (100 mm) whose cross-section is a triangle with a ``deg``° knife edge on the Y axis."""
    L = 0.1
    h = L * math.tan(math.radians(deg))
    sec = [(0.0, 0.0), (L, 0.0), (L, h)]
    v = [(x, y, z) for y in (-0.05, 0.05) for x, z in sec]
    t = [(0, 1, 2), (3, 5, 4), (0, 3, 4), (0, 4, 1), (1, 4, 5), (1, 5, 2), (2, 5, 3), (2, 3, 0)]
    return clash.Mesh(np.array(v, dtype=float), np.array(t))


@pytest.mark.parametrize("deg", [10, 20, 45])
def test_points_beside_a_sharp_outer_edge_are_outside(deg, monkeypatch):
    # 2 mm round the knife edge, all the way round outside it: none inside (the U claw's cut end, task 0067: points
    # 15 mm outside the arm read 15 … 60 mm inside it, because the face whose edge was nearest pointed away)
    m = _wedge(deg)
    out = [(0.002 * math.cos(math.radians(k + 0.5)), 0.0, 0.002 * math.sin(math.radians(k + 0.5)))
           for k in range(360) if not 0 <= k + 0.5 <= deg]
    d, _g = m.depths(np.array(out))
    assert not np.any(d > 0), int(np.count_nonzero(d > 0))
    # inside, near the same edge: inside, as deep as the nearer face is away
    a = math.radians(deg / 2)
    p = np.array([[0.02 * math.cos(a), 0.0, 0.02 * math.sin(a)]])
    assert abs(m.depths(p)[0][0] - 0.02 * math.sin(a)) < 1e-6
    # the rule before 0.2.54 ("below the nearest face by half the distance") called some of them inside
    monkeypatch.setattr(clash, "FACING", 0.5)
    assert np.any(m.depths(np.array(out))[0] > 0)


def test_double_arm_held_tools_are_skipped_and_reported_when_left_behind(tmp_path):
    """The tools the arm holds are copies on the arm (one body with it), the ones in the pots copies on the pots, the
    spindle's tool sits in the spindle: none is a clash. Left in the spindle (the spindle's tool kept showing after
    the arm took it), the claw's closed side turns through it: reported."""
    sc = _set("doublearm", tmp_path)
    a = sc.fresing.animations["Double-arm changer"]
    animation.bake(sc, a)
    assert not clash.check(sc, store=False).rows
    t1 = named(sc, "TOOL T1 BT30 FLAT D10")
    held = [o for o in sc.objects if o.get("fr_cnc_carry") == 1]
    assert held and all(o.parent is not None and o.parent.get("fr_atc") for o in held)     # on the arm's turn
    sc.frame_set(260)                                       # mid-swap: T1 is on the arm, its spindle part hidden
    assert t1.hide_render and any(not o.hide_render for o in held)
    t1.animation_data_clear()
    t1.hide_render = t1.hide_viewport = False
    rows = clash.check(sc, store=False).rows
    pairs = {frozenset((r.a, r.b)) for r in rows}
    assert frozenset(("TOOL T1 BT30 FLAT D10", "CHANGER ARM")) in pairs, [core.row_text(r) for r in rows]


def test_cut_workpiece_meshes_need_no_turning(tmp_path):
    # the check takes Manifold's cut workpiece as it is (task 0067: turning its faces took 85 % of the 4th-axis
    # tour's check): every face already points outwards, the full turning pass changes nothing
    sc = _set("mill", tmp_path)
    animation.bake(sc, sc.fresing.animations["Mill a slot"])
    machining.update_if_needed(sc)
    tl = machining._timeline(sc)
    v, t, _src = tl.mesh_at(float(clash.sample_times(sc)[-1]))         # the slot cut, as the check reads it
    v, t = np.asarray(v, dtype=np.float64), np.asarray(t, dtype=np.int64)
    m = clash.Mesh(v, t)
    assert m.closed and m.sign == 1.0
    assert np.array_equal(m.t, t)


# ---------------------------------------------------------------------------
# a 45° face mill: its inserts are wider at the top than its diameter (task 0072)
# ---------------------------------------------------------------------------

def _frustum(r0, r1, h, n=48):
    ang = np.linspace(0, 2 * math.pi, n, endpoint=False)
    ring = lambda r, z: [(r * math.cos(t), r * math.sin(t), z) for t in ang]          # noqa: E731
    v = ring(r0, 0.0) + ring(r1, h) + [(0.0, 0.0, 0.0), (0.0, 0.0, h)]
    t = []
    for i in range(n):
        j = (i + 1) % n
        t += [(i, j, n + j), (i, n + j, n + i), (2 * n, j, i), (2 * n + 1, n + i, n + j)]
    return clash.Mesh(np.array(v), np.array(t))


def _box(lo, hi):
    (x0, y0, z0), (x1, y1, z1) = lo, hi
    v = [(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
    t = [(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1), (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4),
         (1, 5, 7), (1, 7, 3)]
    return clash.Mesh(np.array(v, dtype=float), np.array(t))


def test_a_45_degree_face_mill_cutting_is_not_a_clash():
    from fresing_render.core import tools as tcore
    tool = tcore.cutting_tool(tcore.default("FACE"))                # Ø50, inserts 6 mm high, 45°: Ø62 at their top
    t = clash.Tool((0.0, 0.0, 0.0), (0.0, 0.0, 1.0), tool)
    assert abs(t.cut[2] - 31 * MM) < 1e-6 and abs(t.follow[2] - 31 * MM) < 1e-6
    cutter = _frustum(25 * MM, 31 * MM, 6 * MM)
    block = _box((-0.1, -0.1, -0.04), (0.1, 0.1, 4 * MM))           # the inserts 4 mm deep in the block
    assert narrow(block, cutter, (), (t.cut,)) == 0.0
    # the zone as wide as the tool's diameter (before 0.2.57): the top of the inserts counted as a clash
    old = core.zone((0.0, 0.0, 0.0), (0.0, 0.0, 1.0), tool.radius, -math.inf, tool.length)
    assert narrow(block, cutter, (), (old,)) > 1 * MM


def narrow(a, b, za, zb):
    return clash.narrow(a, b, np.eye(4), za, zb)[0]
