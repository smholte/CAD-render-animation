"""Test tour (task 0059): the stops are complete, the tour builds, every stop's Go sets its project up and its number
check passes, OK / Problem / note and Copy results, the automatic run (PC check mode Tour) with pictures.

The whole automatic run (every stop rendered, the report) runs in the real Blender on GitHub: tools/ci_real_app.py
"tour"; here it runs for a few stops.
"""

import os

import pytest

from fresing_render.blender import tour
from fresing_render.pccheck import core

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# without Blender
# ---------------------------------------------------------------------------

def test_every_stop_is_complete():
    ids = [s.id for s in tour.STOPS]
    assert len(ids) == len(set(ids)), "two stops with the same id"
    assert 20 <= len(tour.STOPS) <= 60          # 38 after tasks 0035 + 0087, 41 after 0085 + 0077, 45 after 0058 + 0099, 51 after 0079
    assert [s.number for s in tour.STOPS] == list(range(1, len(tour.STOPS) + 1))
    for s in tour.STOPS:
        assert s.group in tour.GROUPS, s.id
        assert s.set in tour.SETS, s.id
        assert s.title and len(s.title) <= 32, s.id                       # fits the side panel
        assert len(s.see) >= 40 and s.see.rstrip().endswith((".", ")")), s.id
        assert s.where, f"{s.id}: say where in the side panel the function is"
        assert s.check is not None, f"{s.id}: every stop has a number check"
        assert s.auto in ("still", "clip", "") or callable(s.auto), s.id
        assert not s.animation or s.at >= 0 or s.id == "hand", s.id
    # the groups come in order, each with stops
    groups = [s.group for s in tour.STOPS]
    assert groups == sorted(groups, key=tour.GROUPS.index)
    assert set(groups) == set(tour.GROUPS)
    for ts in tour.SETS.values():
        assert ts.models and all(os.path.isfile(m) for m in ts.models), ts.id
        # the title names its project file: nothing Windows (or GitHub's artifacts) refuses in a file name
        assert not set(ts.title) & set(':\\/*?"<>|'), ts.title
        assert any(s.set == ts.id for s in tour.STOPS), f"set {ts.id} has no stop"
    # the owner's open list (brief): each has its stop
    for sid in ("materials", "cut_look", "decals", "faces", "sea", "looks", "joint", "stack", "cylinder", "mechanism",
                "waycover", "copies", "update", "gcode", "tools", "hand", "atc", "chips", "air", "still", "turntable",
                "finishing", "labels", "queue", "shapes"):
        assert tour.find(sid) is not None, sid


def test_marks_toggle_and_notes_are_kept(tmp_path):
    folder = str(tmp_path / "Test tour é")
    tour.mark(folder, "9.9.9", "joint", state=tour.OK_STATE)
    tour.mark(folder, "9.9.9", "cylinder", state=tour.PROBLEM)
    tour.mark(folder, "9.9.9", "cylinder", note="  the rod\n jumps at 2 s ")
    data = tour.load_results(folder, "9.9.9")
    assert data["stops"]["joint"]["state"] == "OK"
    assert data["stops"]["cylinder"] == {"state": "PROBLEM", "note": "the rod jumps at 2 s"}
    tour.mark(folder, "9.9.9", "joint", state=tour.OK_STATE)            # a second click takes it off
    assert tour.load_results(folder, "9.9.9")["stops"]["joint"]["state"] == ""
    # a damaged file starts empty, it does not stop the panel
    with open(tour.results_path(folder, "9.9.9"), "w") as fh:
        fh.write("{nonsense")
    assert tour.load_results(folder, "9.9.9")["stops"] == {}


def test_results_text_has_every_stop_with_its_mark_and_note():
    data = {"stops": {"joint": {"state": "OK", "note": ""}, "cylinder": {"state": "PROBLEM", "note": "rod jumps"}}}
    text = tour.results_text("0.2.99", data, pc="Test CPU, 4 cores, 16 GB; GPU (OPTIX): RTX")
    lines = text.splitlines()
    assert lines[0].startswith("Fresing Render test tour 0.2.99 - ")
    assert lines[1] == "PC: Test CPU, 4 cores, 16 GB; GPU (OPTIX): RTX"
    assert lines[2] == f"1 OK, 1 problem, {len(tour.STOPS) - 2} not looked at, of {len(tour.STOPS)} stops"
    j, c = tour.find("joint"), tour.find("cylinder")
    assert f"{j.number:2d}. [OK] {j.title} (joint)" in lines
    assert f"{c.number:2d}. [PROBLEM] {c.title} (cylinder) - rod jumps" in lines
    assert len(lines) == 3 + len(tour.STOPS)


def test_tour_is_a_pc_check_mode_with_its_own_lines_and_report():
    from fresing_render.pccheck import tour as auto
    assert "tour" in core.MODES and core.MODE_TITLES["tour"] == "Test tour"
    assert core.parse_args(["tour"])["mode"] == "tour"
    lines = auto.lines()
    assert lines[0].id == "tour.build" and len(lines) == len(tour.STOPS) + 1
    assert all(ln.modes == ("tour",) and ln.requires == ("tour.build",) for ln in lines[1:])
    assert lines[1].what == tour.STOPS[0].see
    run = core.Run("0.2.99", "tour", "2026-11-09 10:00", pc={"cpu": "x"})
    run.results = [core.Result("tour.joint", "7. Joint", "0.2.47", status=core.OK, what="The boom turns", note="n",
                               pictures=[core.Picture("joint", "frames", thumb_png=b"\x89PNG")])]
    run.finished = True
    page = core.html_report(run, "block")
    assert "<title>Fresing Render test tour</title>" in page and "You should see:</b> The boom turns" in page
    assert "class='card stop'" in page and "data:image/png;base64," in page


def test_documents_and_names(tmp_path):
    assert tour.default_folder().endswith(os.path.join("Fresing Render", "Test tour"))
    f = str(tmp_path)
    assert tour.hub_path(f, "0.2.99") == os.path.join(f, "Test tour 0.2.99.blend")
    assert tour.set_path(f, "0.2.99", "mill") == os.path.join(f, "Test tour 0.2.99 files", "Milling a slot.blend")
    assert tour.set_path(f, "0.2.99", tour.HUB_SET) == tour.hub_path(f, "0.2.99")


def test_claude_md_has_the_tour_rule():
    with open(os.path.join(ROOT, "CLAUDE.md"), encoding="utf-8") as fh:
        text = fh.read()
    assert "Test tour stop" in text and "blender/tour.py" in text


# ---------------------------------------------------------------------------
# in Blender: build, Go for every stop, the buttons, the automatic run for a few stops
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def built(tmp_path_factory):
    bpy = pytest.importorskip("bpy")
    import addon_utils

    import fresing_render
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    folder = str(tmp_path_factory.mktemp("tour") / "Test tour é")
    out = tour.build_all(folder, "9.9.9")
    yield bpy, folder, out
    fresing_render.unregister()


def test_the_tour_builds_every_project(built):
    bpy, folder, out = built
    assert out["errors"] == {}
    assert set(out["files"]) == set(tour.SETS)
    assert out["hub"] == tour.hub_path(folder, "9.9.9") and os.path.isfile(out["hub"])
    assert sum(out["seconds"].values()) < 240, out["seconds"]


@pytest.mark.parametrize("stop_id", [s.id for s in tour.STOPS])
def test_go_sets_the_stop_up_and_its_check_passes(built, stop_id):
    bpy, folder, _out = built
    st = tour.find(stop_id)
    tour.open_set(folder, "9.9.9", st.set)
    sc = bpy.context.scene
    assert sc[tour.TAG] == st.set and tour.tour_of_file(sc) == (folder, "9.9.9")
    assert tour.apply(st, sc) == []
    s = sc.fresing
    if st.animation:
        assert s.anim_baked == st.animation and s.animations[s.animations_index].name == st.animation
        assert sc.frame_current == tour.frame_for(sc, st)
    else:
        assert s.active_shot == tour.shot_name(st) and sc.frame_current == sc.frame_start
    if st.select:
        assert bpy.context.view_layer.objects.active is not None
        assert bpy.context.view_layer.objects.active.get("fr_name") in st.select
    assert sc.camera is not None
    assert st.check(sc)


def test_go_mark_note_and_copy_buttons(built, tmp_path):
    bpy, folder, _out = built
    tour.open_set(folder, "9.9.9", tour.HUB_SET)
    assert bpy.ops.fresing.tour_go(stop="joint") == {"FINISHED"}
    assert bpy.context.scene.fresing.anim_baked == "Boom up"
    assert bpy.ops.fresing.tour_mark(stop="joint", state="OK") == {"FINISHED"}
    assert bpy.ops.fresing.tour_mark(stop="sea", state="PROBLEM") == {"FINISHED"}
    assert bpy.ops.fresing.tour_note("EXEC_DEFAULT", stop="sea", note="waves too high") == {"FINISHED"}
    assert bpy.ops.fresing.tour_pick(stop="sea") == {"FINISHED"}
    data = tour.load_results(folder, "9.9.9")
    assert data["current"] == "sea" and data["stops"]["sea"] == {"state": "PROBLEM", "note": "waves too high"}
    assert bpy.ops.fresing.tour_copy() == {"FINISHED"}
    with open(tour.results_txt_path(folder, "9.9.9"), encoding="utf-8") as fh:
        text = fh.read()
    sea = tour.find("sea")
    assert f"[PROBLEM] {sea.title} (sea) - waves too high" in text and "[OK] Joint: the boom turns" in text
    # Go to a stop of another project opens it (in the app the stop is then set up after loading)
    assert bpy.ops.fresing.tour_go(stop="cylinder") == {"FINISHED"}
    assert bpy.context.scene[tour.TAG] == "cylinder"
    from fresing_render.blender import ops_tour
    ops_tour._PENDING.clear()


def test_the_panel_shows_only_in_a_tour_project(built):
    bpy, folder, _out = built
    from fresing_render.blender import ui_tour
    tour.open_set(folder, "9.9.9", "faces")
    assert ui_tour.FRESING_PT_tour.poll(bpy.context)
    bpy.ops.wm.read_homefile(use_empty=True)
    assert not ui_tour.FRESING_PT_tour.poll(bpy.context)


def test_automatic_run_renders_a_picture_per_stop(built, tmp_path, monkeypatch):
    bpy, _folder, _out = built
    from fresing_render.pccheck import runner
    monkeypatch.setenv("FRESING_PCCHECK_DIR", str(tmp_path / "hist"))
    monkeypatch.setenv("FRESING_SELFTEST_NO_GPU", "1")
    monkeypatch.setenv("FRESING_PCCHECK_ONLY", "tour.build,tour.faces,tour.cylinder,tour.queue,tour.shapes")
    desk = tmp_path / "Desktop"
    desk.mkdir()
    run = runner.run("tour", str(desk), open_report=False)
    by = {r.id: r for r in run.results}
    assert [r.id for r in run.results] == ["tour.build", "tour.faces", "tour.cylinder", "tour.queue", "tour.shapes"]
    assert all(r.status == core.OK for r in run.results), [(r.id, r.reason) for r in run.results]
    assert len(by["tour.faces"].pictures) == 1 and len(by["tour.shapes"].pictures) == 2
    assert by["tour.cylinder"].pictures[0].width > core.THUMB_WIDTH          # three frames side by side
    assert "MP4" in by["tour.queue"].note                                     # small frames: job["scale"] (queue.py)
    page = (desk / runner.TOUR_REPORT_NAME).read_text(encoding="utf-8")
    assert "Fresing Render test tour" in page and page.count("class='card stop'") == 5
    block = (tmp_path / "hist" / "last_run.txt").read_text(encoding="utf-8")
    assert block.startswith("Fresing Render PC check") and "Test tour" in block.splitlines()[0]


def test_three_tools_cuts_nothing_outside_the_program(built):
    """Task 0096: after the manual changes at Z10 the end mill (27.7 mm longer than the face mill) dove 17.7 mm into
    the block at X20 Y0. The milled block now has nothing cut deeper than the end mill's slot (Z-6), and at X20 Y0
    (the face mill's strip) nothing deeper than its 1 mm."""
    import manifold3d as mf
    import numpy as np

    from fresing_render.blender import animation, machining
    from fresing_render.core import machining as mcore
    bpy, folder, _out = built
    tour.open_set(folder, "9.9.9", "tools")
    sc = bpy.context.scene
    a = sc.fresing.animations["Three tools"]
    r = animation.bake(sc, a)
    assert not [w for w in r["warnings"] if "G43" in w], r["warnings"]
    wp = machining.workpiece(sc)
    assert wp is not None and machining.is_active(sc)

    def solid():
        me = wp.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
        me.calc_loop_triangles()
        v = np.empty(len(me.vertices) * 3, np.float32)
        me.vertices.foreach_get("co", v)
        t = np.empty(len(me.loop_triangles) * 3, np.int32)
        me.loop_triangles.foreach_get("vertices", t)
        mw = np.array(wp.matrix_world)
        zero = np.array(sc.fresing.cnc.zero_empty.matrix_world.inverted())
        m = zero @ mw                                 # the block in the program's coordinates (m)
        pts = v.reshape(-1, 3).astype(float) @ m[:3, :3].T + m[:3, 3]
        return mcore.solid_from_mesh(pts * 1000.0, t.reshape(-1, 3))      # mm

    sc.frame_set(sc.frame_start)
    machining.sample(sc)
    sc.frame_set(sc.frame_start)
    before = solid()
    sc.frame_set(sc.frame_end)
    after = solid()
    gone = before - after
    assert gone.volume() > 1000.0                     # it did cut (mm³)
    lo = np.array(gone.bounding_box()[:3])
    assert lo[2] >= -6.05, lo                         # the end mill's slot is the deepest cut
    probe = mf.Manifold.cube((6.0, 6.0, 30.0)).translate((17.0, -3.0, -31.05))   # X17..23 Y-3..3, below Z-1.05
    assert (gone ^ probe).volume() < 1e-3
