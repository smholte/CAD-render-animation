"""Workspaces round 3 (task 0321): Welding, Machine builder, Video producer, Houses – each exactly its functions, an
icon, a tooltip, a star – and Sales may move joints (owner 24 Nov 2026) while adding them stays hidden."""

import os

import pytest

from fresing_render.core import first_setup as FS
from fresing_render.core import functions as F
from fresing_render.core import workspaces as W

NEW = ("welding", "builder", "video", "houses")


def _hidden(key):
    return W.hidden_panels(W.builtin(key))


def test_the_four_are_in_the_list_with_a_name_a_tooltip_and_an_icon():
    for key, name in zip(NEW, ("Welding", "Machine builder", "Video producer", "Houses")):
        assert W.NAMES[key] == name and W.key_of(name) == key
        assert len(W.BUILTIN[key][1]) > 60 and not W.BUILTIN[key][2] and not W.BUILTIN[key][3]
        assert key in F.WORKSPACE_KEYS and key in F.TASK_WORKSPACES
    assert set(W.ICONS) == set(W.BUILTIN), "every workspace has an icon"
    assert len(set(W.ICONS.values())) == len(W.ICONS), "two workspaces with the same icon"
    assert list(W.BUILTIN)[0] == "essentials" and list(W.BUILTIN)[-1] == "full"


@pytest.mark.parametrize("key", NEW)
def test_a_new_workspace_shows_exactly_its_functions(key):
    ws = W.builtin(key)
    assert W.shown_functions(ws) == frozenset(F.TASK_WORKSPACES[key])
    assert len(set(F.TASK_WORKSPACES[key])) == len(F.TASK_WORKSPACES[key]), "a function named twice"
    assert "FRESING_PT_workspace" not in W.hidden_panels(ws)


def test_welding_is_welds_and_the_render_options():
    shown = W.shown_functions(W.builtin("welding"))
    assert {"import.step", "structure.tree", "looks.materials", "looks.welds", "looks.weld_symbols", "looks.weld_list", "looks.rust", "looks.light_look",
            "scene.surroundings", "scene.light", "scene.camera", "scene.still", "scene.render_view"} <= shown
    for gone in ("joints.rotate", "animation.add", "animation.labels", "queue.still", "cnc.machine", "web.export",
                 "looks.cutaway", "looks.xray", "poses.explode"):          # proposals, not added (report)
        assert gone not in shown, gone
    hidden = _hidden("welding")
    for p in ("welds", "looks", "import", "scene", "camera", "output"):
        assert "FRESING_PT_" + p not in hidden, p
    for p in ("motion", "animation", "queue", "cnc", "cables", "web3d", "cutaway"):
        assert "FRESING_PT_" + p in hidden, p


def test_machine_builder_makes_machines_move():
    shown = W.shown_functions(W.builtin("builder"))
    assert {"import.step", "structure.place", "joints.rotate", "joints.slide", "machines.cylinder",
            "machines.mechanism", "machines.waycover", "machines.hoses", "machines.chains", "machines.tracks",
            "panel.setup_window", "animation.clash"} <= shown
    for gone in ("animation.labels", "animation.music", "web.export", "queue.video", "cnc.gcode", "offshore.cables"):
        assert gone not in shown, gone
    hidden = _hidden("builder")
    for p in ("structure", "joints", "cylinders", "mechanisms", "waycover", "flex", "tracks"):
        assert "FRESING_PT_" + p not in hidden, p
    assert "FRESING_PT_web3d" in hidden


def test_video_producer_is_the_video():
    shown = W.shown_functions(W.builtin("video"))
    assert {"animation.add", "animation.camera_path", "animation.labels", "animation.cards", "animation.music",
            "animation.brand", "animation.watermark", "animation.finishing", "queue.video"} <= shown
    for gone in ("import.step", "structure.tree", "joints.rotate", "machines.cylinder", "cnc.machine"):
        assert gone not in shown, gone
    hidden = _hidden("video")
    for p in ("animation", "queue", "camera"):
        assert "FRESING_PT_" + p not in hidden, p
    for p in ("import", "structure", "cylinders"):
        assert "FRESING_PT_" + p in hidden, p


def test_houses_is_a_house_in_its_place():
    shown = W.shown_functions(W.builtin("houses"))
    assert {"house.import", "house.toolbox", "scene.surroundings", "scene.weather", "scene.light", "scene.camera",
            "scene.still", "scene.turntable", "web.export"} <= shown
    for gone in ("joints.rotate", "machines.cylinder", "cnc.machine", "offshore.cables", "animation.labels"):
        assert gone not in shown, gone
    assert "FRESING_PT_web3d" not in _hidden("houses") and "FRESING_PT_cylinders" in _hidden("houses")


def test_sales_moves_joints_but_does_not_make_them():
    shown = W.shown_functions(W.builtin("sales"))
    assert {"joints.move", "joints.cad_position", "poses.pose", "motion.lead_motions"} <= shown
    for gone in ("joints.rotate", "joints.slide", "joints.stack", "joints.couplings", "machines.cylinder",
                 "structure.tree", "structure.place", "import.step", "poses.explode"):
        assert gone not in shown, gone
    hidden = _hidden("sales")
    for p in ("motion", "joints", "poses"):
        assert "FRESING_PT_" + p not in hidden, p
    for p in ("structure", "import", "cylinders", "mechanisms"):
        assert "FRESING_PT_" + p in hidden, p
    assert not W.builtin("sales").lock


def test_moving_joints_shows_wherever_adding_them_does():
    for key in F.WORKSPACE_KEYS:
        if F.FUNCTIONS["joints.rotate"].shown_in(key):
            assert F.FUNCTIONS["joints.move"].shown_in(key), key


def test_the_first_setup_maps_its_ticks_to_the_new_workspaces():
    for tick, key in (("welding", "welding"), ("builder", "builder"), ("video", "video"), ("houses", "houses")):
        assert FS.workspace_for([tick])[0] == W.NAMES[key]
        assert FS.ticks_for(W.NAMES[key]) == [tick]
        assert FS.chapter_for([tick])
    assert len(FS.WORK_KEYS) == len(set(FS.WORK_KEYS)) == 13


def test_an_own_workspace_based_on_a_new_one_reads_back():
    base = W.builtin("welding")
    own = W.make_own("My welds", base)
    back = W.from_json(own.to_json())
    assert back.based_on == "welding"
    assert W.shown_functions(back) == W.shown_functions(base)


# ---------------------------------------------------------------------------------------------------------------
# in Blender (as a Python module)
# ---------------------------------------------------------------------------------------------------------------

bpy = pytest.importorskip("bpy")


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    import fresing_render
    d = tmp_path_factory.mktemp("ws3")
    keep = {k: os.environ.get(k) for k in ("FRESING_WORKSPACES_DIR", "FRESING_SETTINGS_FILE")}
    os.environ["FRESING_WORKSPACES_DIR"] = str(d / "Workspaces")
    os.environ["FRESING_SETTINGS_FILE"] = str(d / "fresing_settings.json")
    fresing_render.register()
    yield d
    fresing_render.unregister()
    for k, v in keep.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


class _Rec:
    """A layout that records every operator and template_list it is asked to draw."""

    def __init__(self, calls):
        self.calls = calls

    def operator(self, idname, **k):
        self.calls.append(("op", idname, k.get("text")))
        return type("O", (), {})()

    def template_list(self, *a, **k):
        self.calls.append(("list", a[0], None))

    def __getattr__(self, name):
        return lambda *a, **k: self

    def __setattr__(self, name, value):
        object.__setattr__(self, name, value)


def _draw_joints(scene):
    from fresing_render.blender import ui_motion
    calls = []
    panel = type("P", (), {"layout": _Rec(calls)})()
    ui_motion.FRESING_PT_joints.draw(panel, bpy.context)
    return calls


def test_sales_draws_the_joint_sliders_without_add_remove_or_set_up(app):
    from mathutils import Vector

    from fresing_render.blender import build, joints, ui_motion, workspaces
    bpy.ops.wm.read_homefile(use_empty=True)
    scene = bpy.context.scene
    scene.fresing.out_folder = str(app)
    crane = os.path.join(os.path.dirname(__file__), "data", "test_crane_a.step")
    assert bpy.ops.fresing.import_step(filepath=crane, quality="draft") == {"FINISHED"}
    boom = next(o for o in scene.objects if o.get(build.PROP_NAME) == "BOOM")
    j = joints.create(scene, "ROTATE", [boom], boom.matrix_world.translation.copy(), Vector((0, 1, 0)), name="Arm")
    workspaces.switch(scene, "Sales")
    assert not ui_motion.can_edit_joints(bpy.context)
    calls = _draw_joints(scene)
    ops = [(c[1], c[2]) for c in calls if c[0] == "op"]
    assert ("fresing.joint_value", "CAD (0)") in ops and ("fresing.joint_value", "Max") in ops
    assert ("list", "FRESING_UL_joints", None) in calls
    for gone in ("fresing.joint_pick_axis", "fresing.joint_remove", "fresing.joint_members", "fresing.joint_follow",
                 "fresing.joint_flip", "fresing.joint_kind"):
        assert gone not in [o[0] for o in ops], gone
    # the joint still moves (no lock)
    joints.set_value(j, 0.3)
    assert abs(joints.get_value(j) - 0.3) < 1e-5
    # Machine builder (and All functions) draw the whole fold again
    for name in ("Machine builder", W.DEFAULT, "Animator", "Essentials"):
        workspaces.switch(scene, name)
        assert ui_motion.can_edit_joints(bpy.context), name
    workspaces.switch(scene, W.DEFAULT)


def test_the_drop_down_gives_each_workspace_its_icon(app):
    from fresing_render.blender import ops_workspace, workspaces
    bpy.ops.wm.read_homefile(use_empty=True)
    scene = bpy.context.scene
    workspaces.switch(scene, "Houses")
    calls = []

    class Rec:
        def __getattr__(self, name):
            if name == "operator":
                def op(idname, **k):
                    calls.append((idname, k.get("text", ""), k.get("icon")))
                    return type("O", (), {})()
                return op
            return lambda *a, **k: self

    menu = type("M", (), {"layout": Rec()})()
    ops_workspace.FRESING_MT_workspaces.draw(menu, bpy.context)
    picks = {t.split("  ")[0]: icon for idname, t, icon in calls if idname == "fresing.workspace_pick"}
    assert picks["Houses"] == "CHECKMARK"                     # the one in use
    for key in ("welding", "builder", "video", "client", "sales"):
        assert picks[W.NAMES[key]] == W.ICONS[key], key
    workspaces.switch(scene, W.DEFAULT)
