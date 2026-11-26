"""Task 0352: the compatibility test projects. The maker (tools/make_compat_project.py) covers every function family
that stores data; its result – made in this version – opens again with the same stored choices and the same picture;
and every kept project in tests/data/compat/format_<n>/ (from the baseline on, one per format number) opens in this
version, goes through the chain and still has its choices and its look."""

import glob
import json
import os
import shutil
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import make_compat_project as maker  # noqa: E402

KEPT = os.path.join(HERE, "data", "compat")


def test_the_maker_covers_every_family_that_stores_data():
    from fresing_render.core import compat as core
    from fresing_render.core import functions
    covered = maker.covered_families()
    assert core.family_problems(functions.FAMILIES, covered) == []
    from fresing_render.blender import tour
    assert set(maker.COMPAT_SETS) <= set(tour.SETS)


def test_a_maker_without_a_set_is_caught():
    from fresing_render.core import compat as core
    from fresing_render.core import functions
    fewer = maker.covered_families(tuple(s for s in maker.COMPAT_SETS if s != "mill"))
    assert any("'milling'" in p for p in core.family_problems(functions.FAMILIES, fewer))


def test_the_kept_folder_is_explained():
    with open(os.path.join(KEPT, "README.md"), encoding="utf-8") as fh:
        text = fh.read()
    assert "make_compat_project.py" in text and "format_" in text


bpy = None


@pytest.fixture(scope="module")
def app():
    global bpy
    bpy = pytest.importorskip("bpy")
    import addon_utils

    import fresing_render
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    from fresing_render.blender import prefs
    if prefs.get() is None:
        entry = bpy.context.preferences.addons.new()
        entry.module = prefs.ADDON_ID
    yield
    fresing_render.unregister()


@pytest.fixture(scope="module")
def made(app, tmp_path_factory):
    out = str(tmp_path_factory.mktemp("compat"))
    res = maker.make(out)
    assert res["errors"] == {}, res["errors"]
    return res


def _open_and_check(folder: str, tmp: str) -> list:
    """Open every project of a format folder in this version: its choices (allowing what the chain's steps change)
    and its picture against what was kept. Returns the problems."""
    from fresing_render.blender import compat
    from fresing_render.core import compat as core
    with open(os.path.join(folder, "summary.json"), encoding="utf-8") as fh:
        kept = json.load(fh)
    allowed = tuple(p for s in core.plan(kept["format"]) for p in s.changes)
    problems = []
    for name, want in kept["projects"].items():
        src = os.path.join(folder, f"{name}.blend")
        path = os.path.join(tmp, f"{name}.blend")
        shutil.copy(src, path)                    # never open the kept file itself: a load handler may write
        bpy.ops.wm.open_mainfile(filepath=path)
        assert compat.newer() is None, f"{name}: this app says it is newer"
        got = compat.summary()
        diff = core.compare(want, got, allowed)
        problems += [f"{name}: {d}" for d in diff[:20]]
        pic = os.path.join(folder, f"{name}.png")
        if os.path.isfile(pic):
            now = os.path.join(tmp, f"{name}.png")
            assert compat.picture(bpy.context.scene, now), f"{name}: no camera any more"
            d = core.picture_difference(compat.read_picture(pic), compat.read_picture(now))
            if d > core.PICTURE_TOLERANCE:
                problems.append(f"{name}: the picture differs by {d:.4f} (allowed {core.PICTURE_TOLERANCE})")
    return problems


def test_the_project_made_now_opens_the_same(made, tmp_path):
    from fresing_render.core import compat as core
    folder = made["folder"]
    assert os.path.basename(folder) == f"format_{core.FORMAT}"
    assert sorted(made["files"]) == sorted(maker.COMPAT_SETS)
    for path in made["files"].values():
        size = os.path.getsize(path)
        assert size < 1.2e6, f"{os.path.basename(path)} is {size // 1024} KB: keep a test project small"
        assert os.path.isfile(path[:-len(".blend")] + ".png")
    with open(os.path.join(folder, "summary.json"), encoding="utf-8") as fh:
        kept = json.load(fh)
    assert kept["format"] == core.FORMAT
    crane = kept["projects"]["crane"]["scenes"]
    sc = next(iter(crane.values()))
    assert sc["settings"]["fresing"]["animations"] and sc["settings"]["fresing"]["joints"]
    assert _open_and_check(folder, str(tmp_path)) == []


KEPT_FOLDERS = sorted(glob.glob(os.path.join(KEPT, "format_*")))


@pytest.mark.parametrize("folder", KEPT_FOLDERS, ids=[os.path.basename(f) for f in KEPT_FOLDERS])
def test_a_kept_project_opens_in_this_version(app, folder, tmp_path):
    assert _open_and_check(folder, str(tmp_path)) == []


def test_kept_projects_match_the_baseline_rule():
    """From the baseline on, every format number from the baseline to FORMAT has its project (the precheck says the
    same before a push)."""
    from fresing_render.core import compat as core
    have = {os.path.basename(f) for f in KEPT_FOLDERS}
    if core.BASELINE_FORMAT is None:
        assert have == set(), "before the baseline nothing is kept (CLAUDE.md section 6)"
        return
    for n in range(core.BASELINE_FORMAT, core.FORMAT + 1):
        assert f"format_{n}" in have


def test_the_check_sees_a_changed_choice_and_a_changed_look(made, tmp_path):
    """The comparison is not blind: a joint's limit, an animation step and the background changed after the save
    are found, the picture too."""
    from fresing_render.blender import compat
    from fresing_render.core import compat as core
    folder = made["folder"]
    with open(os.path.join(folder, "summary.json"), encoding="utf-8") as fh:
        want = json.load(fh)["projects"]["crane"]
    path = str(tmp_path / "crane.blend")
    shutil.copy(os.path.join(folder, "crane.blend"), path)
    bpy.ops.wm.open_mainfile(filepath=path)
    s = bpy.context.scene.fresing
    s.joints[0].rot_max = s.joints[0].rot_max - 0.25
    s.animations[0].blocks[0].duration += 1.0
    diff = core.compare(want, compat.summary())
    assert any(".joints[0].rot_max" in d for d in diff), diff
    assert any(".animations[0].blocks[0].duration" in d for d in diff), diff
    assert core.compare(want, compat.summary(), allowed=("scenes",)) == []      # a step's own change is allowed
    sc = bpy.context.scene
    world = sc.world
    world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (1.0, 0.0, 1.0, 1.0)
    bg.inputs["Strength"].default_value = 5.0
    sc.fresing.exposure = sc.fresing.exposure + 2.0
    now = str(tmp_path / "crane.png")
    assert compat.picture(sc, now)
    d = core.picture_difference(compat.read_picture(os.path.join(folder, "crane.png")), compat.read_picture(now))
    assert d > core.PICTURE_TOLERANCE, d
