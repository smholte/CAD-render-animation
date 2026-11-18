"""Fresing > Tools and checks (task 0212, ``blender/apptools.py``): the submenu, the self-test started in its own
Blender, the app's Tools folder opened, and the PC-check line ``app.tools`` (its Windows part only runs on Windows)."""

import os
import subprocess

import pytest

bpy = pytest.importorskip("bpy")
import fresing_render  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def addon():
    fresing_render.register()
    yield
    fresing_render.unregister()


def test_menu_and_its_lines():
    from fresing_render.blender import apptools, lock, ui_topbar
    assert hasattr(bpy.types, apptools.MENU)
    for idname in apptools.entries():
        assert ui_topbar._has(idname) and idname in ui_topbar.entries(), idname
        assert lock.allowed(idname), idname                    # they only start a check or open a folder
    import inspect
    assert f'"{apptools.MENU}"' in inspect.getsource(ui_topbar.TOPBAR_MT_fresing.draw)
    for idname in ("fresing.self_test", "fresing.open_app_folder"):
        desc = getattr(bpy.ops.fresing, idname.split(".")[1]).get_rna_type().description
        assert desc and "\n" not in desc, idname


def test_self_test_runs_the_extensions_own_file(monkeypatch, tmp_path):
    from fresing_render.blender import apptools
    from fresing_render.pccheck import runner
    src = open(apptools.SELFTEST, encoding="utf-8").read()
    assert 'if __name__ == "__main__":' in src and "run_installed()" in src.split('if __name__ == "__main__":')[1]
    assert apptools.selftest_command("C:/B/blender.exe", "D:/Desk top") == \
        ["C:/B/blender.exe", "--background", "--python", apptools.SELFTEST, "--", "D:/Desk top"]
    got = {}

    class FakePopen:
        def __init__(self, cmd, **kw):
            got["cmd"], got["kw"] = cmd, kw

    monkeypatch.setattr(subprocess, "Popen", FakePopen)
    monkeypatch.setattr(runner, "desktop_dir", lambda: str(tmp_path))
    from fresing_render import winexe
    monkeypatch.setattr(winexe, "console_exe", lambda binary: "")
    with pytest.raises(RuntimeError, match="not found"):           # no Blender program: a plain message
        bpy.ops.fresing.self_test()
    exe = tmp_path / "blender.exe"
    exe.write_text("x")
    monkeypatch.setattr(winexe, "console_exe", lambda binary: str(exe))
    assert bpy.ops.fresing.self_test() == {"FINISHED"}
    assert got["cmd"] == [str(exe), "--background", "--python", apptools.SELFTEST, "--", str(tmp_path)]
    assert got["kw"]["cwd"] == str(tmp_path)


def test_open_app_folder_only_in_an_installed_app(monkeypatch, tmp_path):
    from fresing_render import appicon
    from fresing_render.blender import apptools, files
    assert not bpy.ops.fresing.open_app_folder.poll()              # this Blender was not installed with Install.bat
    inst = tmp_path / "FresingRender é"
    monkeypatch.setattr(appicon, "install_dir", lambda binary: str(inst))
    opened = []
    monkeypatch.setattr(files, "open_path", opened.append)
    assert bpy.ops.fresing.open_app_folder.poll()
    assert bpy.ops.fresing.open_app_folder() == {"FINISHED"}
    assert opened == [str(inst / "Tools")] and (inst / "Tools").is_dir()


def test_pc_check_line_checks_the_menu():
    from fresing_render.pccheck import checks
    line = next(x for x in checks.LINES if x.id == "app.tools")
    assert line.since and "Tools and checks" in line.what
    note = line.fn(None)
    assert "menu checked" in note and "not checked" in note           # not an installed app on Windows here
