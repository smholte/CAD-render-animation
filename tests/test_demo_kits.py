"""Task 0228: demo kits – a demo project from a zip the user adds (core/demo_kits.py, the hook in blender/demo.py).

The made-up test kit (tests/data/demo_kit_test: a deck plate, a box that slides on it, one stage, one saved camera)
is checked, refused when broken, added, replaced, listed, removed, its maker run, and built into a project; the app's
own demo stages are untouched by a kit build.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import zipfile

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from fresing_render.core import demo_kits  # noqa: E402

KIT = os.path.join(HERE, "data", "demo_kit_test")
SHIPPED = os.path.join(ROOT, "fresing_render", "data", "demo_kit_test.zip")


def kit_json() -> dict:
    with open(os.path.join(KIT, "kit.json"), encoding="utf-8") as fh:
        return json.load(fh)


def zip_of(tmp_path, data=None, extra=(), top="kit", name="kit.zip") -> str:
    """A kit zip: the test kit's files under ``top``, kit.json replaced by ``data``, plus (name, bytes) ``extra``."""
    path = str(tmp_path / name)
    with zipfile.ZipFile(path, "w") as zf:
        for root, dirs, files in os.walk(KIT):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for f in files:
                full = os.path.join(root, f)
                arc = top + "/" + os.path.relpath(full, KIT).replace(os.sep, "/")
                if arc == f"{top}/kit.json" and data is not None:
                    zf.writestr(arc, json.dumps(data))
                else:
                    zf.write(full, arc)
        for arc, raw in extra:
            zf.writestr(arc, raw)
    return path


# ---------------------------------------------------------------------------
# kit.json and the zip
# ---------------------------------------------------------------------------

def test_the_test_kit_is_a_good_kit():
    info, top = demo_kits.check_zip(SHIPPED)
    assert (info.id, info.title, top) == ("test-kit", "Test kit box", "demo_kit_test")
    assert info.stage_module == "fr_test_kit.stages" and info.maker == "fr_test_kit.make"
    assert info.stages == ["box", "finish"]
    assert demo_kits.version_message(info, "0.2.175") == ""


def test_the_shipped_test_kit_is_the_packed_folder(tmp_path):
    """The PC check adds the copy in fresing_render/data: it must be the zip of tests/data/demo_kit_test."""
    out = demo_kits.pack(KIT, str(tmp_path / "again.zip"), top="demo_kit_test")
    with open(out, "rb") as a, open(SHIPPED, "rb") as b:
        assert a.read() == b.read(), ("pack it again: python -c \"from fresing_render.core import demo_kits; "
                                      "demo_kits.pack('tests/data/demo_kit_test', "
                                      "'fresing_render/data/demo_kit_test.zip')\"")


@pytest.mark.parametrize("change, said", [
    ({"id": "Bad Id"}, "lower-case"),
    ({"id": "1kit"}, "starting with a letter"),
    ({"id": "a" * 41}, "too long"),
    ({"id": ""}, "no 'id'"),
    ({"title": ""}, "no 'title'"),
    ({"title": "a/b"}, "names a file"),
    ({"app_min": "soon"}, "not a version"),
    ({"app_max": "x.y"}, "not a version"),
    ({"stage_module": "my kit.stages"}, "not a module path"),
    ({"maker": "../evil"}, "not a module path"),
    ({"stages": "box"}, "list of names"),
    ({"uses": ["blender/demo"]}, "not a module path"),
    ({"kit_version": 3}, "must be text"),
])
def test_kit_json_is_refused_with_a_reason(change, said):
    data = dict(kit_json(), **change)
    with pytest.raises(demo_kits.KitError) as e:
        demo_kits.info_from(data)
    assert said in str(e.value)


@pytest.mark.parametrize("extra, said", [
    ((("kit/../escape.py", b"x"),), "outside its folder"),
    ((("/abs.py", b"x"),), "outside its folder"),
    ((("kit\\win.py", b"x"),), "outside its folder"),
    ((("other/x.py", b"x"),), "ONE folder"),
    ((("loose.py", b"x"),), "one folder"),
])
def test_a_zip_that_leaves_its_folder_is_refused(tmp_path, extra, said):
    with pytest.raises(demo_kits.KitError) as e:
        demo_kits.check_zip(zip_of(tmp_path, extra=extra))
    assert said in str(e.value)


def test_not_a_kit_is_refused(tmp_path):
    p = tmp_path / "not.zip"
    p.write_bytes(b"hello")
    with pytest.raises(demo_kits.KitError, match="not a zip"):
        demo_kits.check_zip(str(p))
    p2 = tmp_path / "nokit.zip"
    with zipfile.ZipFile(p2, "w") as zf:
        zf.writestr("kit/readme.txt", "hi")
    with pytest.raises(demo_kits.KitError, match="no kit/kit.json"):
        demo_kits.check_zip(str(p2))
    with pytest.raises(demo_kits.KitError, match="no file"):
        demo_kits.check_zip(str(tmp_path / "gone.zip"))


def test_a_link_in_the_zip_is_refused(tmp_path):
    path = zip_of(tmp_path)
    with zipfile.ZipFile(path, "a") as zf:
        zi = zipfile.ZipInfo("kit/link")
        zi.external_attr = (0o120777 << 16)
        zf.writestr(zi, "/etc/passwd")
    with pytest.raises(demo_kits.KitError, match="link"):
        demo_kits.check_zip(path)


def test_versions_say_what_to_do():
    info = demo_kits.info_from(dict(kit_json(), app_min="0.2.180", app_max="0.2.199"))
    assert demo_kits.version_message(info, "0.2.185") == ""
    assert demo_kits.version_message(info, "0.2.180") == "" and demo_kits.version_message(info, "0.2.199") == ""
    assert demo_kits.version_message(info, "0.2.200") == \
        "This kit was made for 0.2.180–0.2.199. Download the kit's newer version."
    assert "Update Fresing Render" in demo_kits.version_message(info, "0.2.179")
    open_end = demo_kits.info_from(dict(kit_json(), app_min="0.2.180", app_max=""))
    assert demo_kits.version_message(open_end, "1.0.0") == ""
    assert open_end.made_for() == "0.2.180 and newer"


# ---------------------------------------------------------------------------
# the kits folder
# ---------------------------------------------------------------------------

def test_add_replace_list_remove(tmp_path):
    kits = str(tmp_path / "kits")
    assert demo_kits.list_kits(kits) == []
    info = demo_kits.add(SHIPPED, kits, "0.2.175")
    assert info.folder == os.path.join(kits, "test-kit")
    assert os.path.isfile(os.path.join(kits, "test-kit", "kit.json"))
    assert os.path.isfile(os.path.join(kits, "test-kit", "fr_test_kit", "stages.py"))
    newer = dict(kit_json(), kit_version="2", title="Test kit box (newer)")
    demo_kits.add(zip_of(tmp_path, newer, extra=(("kit/fr_test_kit/new.py", b"# new"),)), kits, "0.2.175")
    listed = demo_kits.list_kits(kits)
    assert [(k.id, k.kit_version, k.title) for k in listed] == [("test-kit", "2", "Test kit box (newer)")]
    assert os.path.isfile(os.path.join(kits, "test-kit", "fr_test_kit", "new.py"))
    assert not [n for n in os.listdir(kits) if n != "test-kit"], "nothing left over from replacing"
    other = dict(kit_json(), id="another-kit", title="A kit")
    demo_kits.add(zip_of(tmp_path, other, name="b.zip"), kits, "0.2.175")
    assert [k.id for k in demo_kits.list_kits(kits)] == ["another-kit", "test-kit"]       # by title
    os.makedirs(os.path.join(kits, "broken-kit"))
    assert len(demo_kits.list_kits(kits)) == 2                                          # a broken folder is skipped
    assert demo_kits.get(kits, "test-kit").kit_version == "2" and demo_kits.get(kits, "../x") is None
    assert demo_kits.remove(kits, "test-kit") and not demo_kits.remove(kits, "test-kit")
    assert [k.id for k in demo_kits.list_kits(kits)] == ["another-kit"]


def test_a_kit_for_another_version_is_not_added(tmp_path):
    kits = str(tmp_path / "kits")
    old = zip_of(tmp_path, dict(kit_json(), app_min="0.2.100", app_max="0.2.150"))
    with pytest.raises(demo_kits.KitError, match="0.2.100–0.2.150. Download the kit's newer version"):
        demo_kits.add(old, kits, "0.2.175")
    assert demo_kits.list_kits(kits) == []


# ---------------------------------------------------------------------------
# loading a kit's code
# ---------------------------------------------------------------------------

def test_inside_a_kit_the_app_is_fresing_app_and_forgotten_after(tmp_path):
    import fresing_render.core.words as words
    with demo_kits.loaded(KIT, "fresing_render"):
        import fresing_app.core.words as alias  # noqa: I001
        assert alias is words, "the same module, not a copy"
        from fresing_app.core import words as w2
        assert w2 is words
        import fr_test_kit
        assert fr_test_kit.JOINT == "Box slide"
    assert not [m for m in sys.modules if m.split(".")[0] in ("fresing_app", "fr_test_kit")]
    assert KIT not in sys.path


def test_a_kit_module_with_an_app_name_is_refused(tmp_path):
    bad = tmp_path / "kit"
    shutil.copytree(KIT, bad)
    (bad / "json.py").write_text("x = 1\n")                 # a module the app already uses
    with pytest.raises(demo_kits.KitError, match="'json'"):
        with demo_kits.loaded(str(bad), "fresing_render"):
            pass


def test_uses_names_what_the_app_does_not_have():
    info = demo_kits.info_from(dict(kit_json(), uses=["core.words.plural", "core.words.no_such", "core.nothing",
                                                      "demo_model.geom"]))
    assert demo_kits.missing_uses(info, "fresing_render") == ["core.words.no_such", "core.nothing"]


def test_the_kits_maker_runs_as_its_own_program(tmp_path):
    out = tmp_path / "model é"
    prog = tmp_path / "p.json"
    r = subprocess.run([sys.executable, os.path.join(ROOT, "fresing_render", "core", "demo_kit_run.py"), KIT,
                        "fr_test_kit.make", str(out), "--small", "--progress", str(prog)],
                       capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stdout + r.stderr
    assert (out / "test_kit_box.step").stat().st_size > 10000
    assert json.loads(prog.read_text())["text"] == "Writing the test box"


# ---------------------------------------------------------------------------
# a kit's demo, built (Blender as a module)
# ---------------------------------------------------------------------------

@pytest.fixture
def app(tmp_path, monkeypatch):
    import bpy  # noqa: I001
    import addon_utils

    import fresing_render
    monkeypatch.setenv(demo_kits.ENV, str(tmp_path / "kits"))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    bpy.ops.wm.read_factory_settings(use_empty=True)
    fresing_render.unregister()


def test_build_with_the_test_kit(app, tmp_path):
    import bpy

    from fresing_render.blender import demo, joints
    before = [(s.id, s.fn) for s in demo.STAGES]
    info = demo_kits.add(SHIPPED, demo.kits_dir(), "9.9.9")
    folder = demo.kit_folder(str(tmp_path / "Demo é"), info.id)
    seen = []
    out = demo.build_project(folder, "9.9.9", small=True, kit=info,
                             progress=lambda st, text, done, total: seen.append(st))
    assert [(s.id, s.fn) for s in demo.STAGES] == before, "the app's own stages are back, unchanged"
    assert list(out["seconds"]) == ["kit_model", "box", "finish"], "only the kit's maker and stages ran"
    assert out["path"] == demo.project_path(folder, "9.9.9", info.title)
    assert os.path.basename(out["path"]) == "Test kit box 9.9.9.blend"
    assert demo.exists(folder, "9.9.9", info.title) and not demo.exists(folder, "9.9.9")
    assert "The model (written)" in seen
    assert not [m for m in sys.modules if m.split(".")[0] in ("fresing_app", "fr_test_kit")]
    summary = demo.read_summary(folder, "9.9.9")
    assert summary["kit"] == "test-kit" and summary["animation"] == "Test kit" and summary["joints"] == 1

    bpy.ops.wm.open_mainfile(filepath=out["path"])
    sc = bpy.context.scene
    assert demo.is_demo(sc) and sc[demo.KIT_TAG] == "test-kit"
    jt = sc.fresing.joints.get("Box slide")
    assert jt is not None and jt.kind == "SLIDE"
    box = next(o for o in sc.objects if o.get("fr_name") == "TEST BOX")
    x0 = box.matrix_world.translation.x
    joints.set_value(jt, 2.0)
    bpy.context.view_layer.update()
    assert abs(box.matrix_world.translation.x - x0 - 2.0) < 1e-4, "the joint slides the box along the deck"
    assert any(s.name == "Box from the side" for s in sc.fresing.shots)
    a = sc.fresing.animations.get("Test kit")
    assert a is not None and len(a.blocks) == 1 and sc.frame_end > sc.frame_start


def test_a_kit_that_needs_what_the_app_lacks_leaves_nothing(app, tmp_path):
    from fresing_render.blender import demo
    before = [s.id for s in demo.STAGES]
    kits = demo.kits_dir()
    info = demo_kits.add(zip_of(tmp_path, dict(kit_json(), uses=["blender.demo.no_such_thing"])), kits, "9.9.9")
    folder = demo.kit_folder(str(tmp_path / "Demo"), info.id)
    with pytest.raises(RuntimeError, match="needs blender.demo.no_such_thing"):
        demo.build_project(folder, "9.9.9", small=True, kit=info)
    assert not os.path.exists(demo.project_dir(folder, "9.9.9"))
    assert [s.id for s in demo.STAGES] == before
    broken = dict(kit_json(), stages=["box", "finish", "never"])
    info = demo_kits.add(zip_of(tmp_path, broken, name="b.zip"), kits, "9.9.9")
    with pytest.raises(RuntimeError, match="did not register never"):
        demo.build_project(folder, "9.9.9", small=True, kit=info)
    assert [s.id for s in demo.STAGES] == before


def test_build_main_with_a_kit_that_is_not_added(app, tmp_path):
    from fresing_render.blender import demo
    folder = str(tmp_path / "k")
    assert demo.build_main(folder, small=True, kit="test-kit") == 1
    with open(demo.result_path(folder), encoding="utf-8") as fh:
        res = json.load(fh)
    assert not res["finished"] and "is not added" in res["error"]


def test_the_background_build_reads_its_kit():
    """``launcher.py -- demobuild <folder> [small] --kit <id>`` reaches build_main with the kit."""
    from unittest import mock

    from fresing_render.pccheck import runner
    with mock.patch("fresing_render.blender.demo.build_main", return_value=0) as bm:
        runner.run_from_argv(["blender", "--", "demobuild", "/tmp/x", "small", "--kit", "test-kit"])
        bm.assert_called_with("/tmp/x", small=True, kit="test-kit")
        runner.run_from_argv(["blender", "--", "demobuild", "/tmp/x"])
        bm.assert_called_with("/tmp/x", small=False, kit="")
