"""Task 0055: group renames, safer project load, old caches, chrome rod / shaft looks."""

import json
import os

import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import handlers  # noqa: E402
from fresing_render.core import part_types_data as PTD  # noqa: E402
from fresing_render.importer import runner, step_reader  # noqa: E402

STEP = os.path.join(os.path.dirname(__file__), "data", "test_materials.step")


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture()
def scene(tmp_path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path)
    assert bpy.ops.fresing.import_step(filepath=STEP, quality="draft") == {"FINISHED"}
    return sc


def test_group_rename_moves_schemes_and_scene_looks(scene):
    s = scene.fresing
    a = s.groups[0]
    old = a.name
    sch = s.schemes.add()
    sch.name = "S"
    look = sch.looks.add()
    look.group, look.color = old, "#FF0000"
    shot = s.shots.add()
    shot.name = "Shot"
    own = shot.own_scheme.looks.add()
    own.group = old
    a.name = "Renamed A"
    assert look.group == "Renamed A" and own.group == "Renamed A"


def test_rename_to_existing_name_is_refused(scene):
    s = scene.fresing
    assert len(s.groups) >= 2
    first, second = s.groups[0], s.groups[1]
    n1, n2 = first.name, second.name
    second.name = n1
    assert second.name == n2 and first.name == n1
    assert [g.name for g in s.groups].count(n1) == 1
    assert "already exists" in s.last_message


def test_one_failing_upgrade_step_does_not_skip_the_rest(scene, monkeypatch, capsys):
    ran = []

    def boom(sc):
        raise RuntimeError("kaput")

    monkeypatch.setattr(handlers, "_upgrade_steps",
                        lambda: (("one", boom), ("two", lambda sc: ran.append(sc.name))))
    handlers._on_load()
    assert ran == [bpy.context.scene.name]
    assert "upgrade step 'one' failed" in capsys.readouterr().out


def test_prune_old_caches_keeps_current(tmp_path):
    def make(name, version, files=True):
        d = tmp_path / name
        d.mkdir()
        if files:
            (d / "tree.json").write_text(json.dumps({"version": version}))
        return d
    old = make("old", step_reader.CACHE_VERSION - 1)
    cur = make("cur", step_reader.CACHE_VERSION)
    other = make("other", 0, files=False)
    part = make("x.partial", 0, files=False)
    assert runner.prune_old_caches(str(tmp_path)) == 1
    assert not old.exists() and cur.exists() and other.exists() and part.exists()


def test_rod_and_shaft_looks_and_old_projects_unchanged():
    assert PTD.GROUPS["Chrome rods & linear shafts"][0] == "chrome_rod"
    assert PTD.GROUPS["Shafts, pins & spacers"][0] == "steel_ground"
    assert PTD.GROUPS["Linear guides & ball screws"][0] == "steel_ground"


def test_old_project_keeps_its_looks(scene):
    from fresing_render.blender import logic
    s = scene.fresing
    s.groups[0].material = "steel_machined"
    logic.upgrade_looks(scene)
    handlers._on_load()
    assert s.groups[0].material == "steel_machined"
