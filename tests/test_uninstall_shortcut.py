"""'Uninstall Fresing Render' in the install folder and next to Fresing Render.exe (task 0329): what the shortcut
holds (the Installed-apps entry's command), where it goes, when the app writes it again, and the PowerShell side (read
as text here; GitHub's Windows job makes, reads and runs the real shortcut)."""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from fresing_render import appicon  # noqa: E402
from fresing_render.core import installed_apps as ia  # noqa: E402

FOLDER = os.path.join(os.sep + "x", "Sébastien Test", "AppData", "Local", "FresingRender")


def _text(*parts):
    return open(os.path.join(ROOT, *parts), encoding="utf-8", newline="").read().replace("\r\n", "\n")


# ---- what the shortcut holds -----------------------------------------------------------------------------------

def test_the_entry_s_command_is_unchanged():
    script = os.path.join(FOLDER, "Tools", "Uninstall-FresingRender.ps1")
    want = f'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "{script}" -InstallDir "{FOLDER}"'
    assert ia.uninstall_string(FOLDER, quiet=True) == want
    assert ia.uninstall_string(FOLDER) == want + " -Pause"


def test_the_shortcut_runs_exactly_the_entry_s_uninstall_string():
    spec = ia.shortcut_spec(FOLDER, env={"SystemRoot": os.sep + "Win dows"})
    assert os.path.basename(spec["target"]) == "powershell.exe"
    assert spec["target"].endswith(os.path.join("System32", "WindowsPowerShell", "v1.0", "powershell.exe"))
    assert "powershell.exe " + spec["arguments"] == ia.wanted(FOLDER, "1")["UninstallString"]
    assert "-Pause" in spec["arguments"]                              # its window shows what it removed
    assert not spec["workdir"].startswith(FOLDER)                     # never holds the folder it removes
    assert spec["description"] == ("Removes Fresing Render from this PC. Your projects, renders and backups are kept")
    assert ia.powershell_exe({}).endswith("powershell.exe")          # no SystemRoot: Windows' usual folder


def test_two_places_the_install_folder_and_fresing_render_exe_s_folder():
    bdir = os.path.join(FOLDER, "blender-5.2.3-windows-x64")
    assert ia.uninstall_shortcuts(FOLDER, bdir) == [os.path.join(FOLDER, ia.UNINSTALL_LNK),
                                                     os.path.join(bdir, ia.UNINSTALL_LNK)]
    assert ia.UNINSTALL_LNK == "Uninstall Fresing Render.lnk"
    # a Blender outside the install folder, or the folder itself: only the install folder (never another folder)
    assert ia.uninstall_shortcuts(FOLDER, os.path.join(os.sep + "elsewhere", "blender")) == [os.path.join(FOLDER, ia.UNINSTALL_LNK)]
    assert ia.uninstall_shortcuts(FOLDER, FOLDER + "-other") == [os.path.join(FOLDER, ia.UNINSTALL_LNK)]
    assert ia.uninstall_shortcuts(FOLDER, FOLDER) == [os.path.join(FOLDER, ia.UNINSTALL_LNK)]
    assert ia.uninstall_shortcuts("", bdir) == []


def test_when_the_shortcut_is_written_again():
    spec = ia.shortcut_spec(FOLDER, env={"SystemRoot": os.sep + "W"})
    icon = os.path.join(FOLDER, "fresing-render.ico")
    right = {"target": spec["target"], "arguments": spec["arguments"], "icon": icon, "icon_index": 0}
    assert ia.shortcut_needs(None, spec, icon)                                       # missing / unreadable
    assert not ia.shortcut_needs(right, spec, icon)
    assert not ia.shortcut_needs({**right, "arguments": "  " + spec["arguments"].replace(" ", "  ")}, spec, icon)
    assert ia.shortcut_needs({**right, "arguments": ia.uninstall_arguments(FOLDER + "2")}, spec, icon)   # moved
    assert ia.shortcut_needs({**right, "arguments": ia.uninstall_arguments(FOLDER, quiet=True)}, spec, icon)
    assert ia.shortcut_needs({**right, "target": os.sep + "notepad.exe"}, spec, icon)
    assert ia.shortcut_needs({**right, "icon": os.sep + "blender.exe"}, spec, icon)
    assert ia.shortcut_needs({**right, "icon_index": 3}, spec, icon)
    assert not ia.shortcut_needs({**right, "icon": "other"}, spec, "")              # no icon wanted: icon not judged


# ---- the app's start: an older install gets both, a wrong one is set right ---------------------------------------

def _install(tmp_path, monkeypatch, blender="blender-5.2.3-windows-x64", script=True):
    folder = tmp_path / "Mijn map é" / "FresingRender"
    (folder / "Tools").mkdir(parents=True)
    (folder / "installed.txt").write_text("Fresing Render")
    bdir = folder / blender
    bdir.mkdir()
    (bdir / "blender.exe").write_bytes(b"x")
    (bdir / "Fresing Render.exe").write_bytes(b"x")
    if script:
        (folder / "Tools" / ia.UNINSTALLER).write_text("# uninstaller")
    win = tmp_path / "Windows"
    ps = win / "System32" / "WindowsPowerShell" / "v1.0"
    ps.mkdir(parents=True)
    (ps / "powershell.exe").write_bytes(b"x")
    monkeypatch.setenv("SystemRoot", str(win))
    links = {}

    def make(path, target, arguments, workdir, icon, description):
        links[path] = {"target": target, "arguments": arguments, "workdir": workdir, "icon": icon, "icon_index": 0,
                       "description": description}
        open(path, "wb").close()

    monkeypatch.setattr(appicon, "make_shortcut", make)
    monkeypatch.setattr(appicon, "read_shortcut", lambda path: dict(links[path]))
    return str(folder), str(bdir / "Fresing Render.exe"), links


def test_an_older_install_gets_both_shortcuts_at_its_next_start(tmp_path, monkeypatch):
    folder, exe, links = _install(tmp_path, monkeypatch)
    icon = os.path.join(folder, "fresing-render.ico")
    done = appicon.ensure_uninstall_shortcuts(folder, exe, icon)
    assert len(done) == 2 and all("made" in d for d in done), done
    want = ia.shortcut_spec(folder)
    for path in ia.uninstall_shortcuts(folder, os.path.dirname(exe)):
        assert os.path.isfile(path)
        assert links[path]["target"] == want["target"] and links[path]["arguments"] == want["arguments"]
        assert links[path]["icon"] == icon and links[path]["description"] == ia.UNINSTALL_TEXT
        assert "powershell.exe " + links[path]["arguments"] == ia.uninstall_string(folder)
    assert appicon.ensure_uninstall_shortcuts(folder, exe, icon) == []          # right: not written again


def test_a_wrong_shortcut_is_set_right_and_a_renamed_blender_folder_gets_its_own(tmp_path, monkeypatch):
    folder, exe, links = _install(tmp_path, monkeypatch)
    appicon.ensure_uninstall_shortcuts(folder, exe, "i.ico")
    first = os.path.join(folder, ia.UNINSTALL_LNK)
    links[first]["arguments"] = ia.uninstall_arguments(folder + "-old")
    done = appicon.ensure_uninstall_shortcuts(folder, exe, "i.ico")
    assert done == [f"{ia.UNINSTALL_LNK}: set right in the install folder"]
    assert links[first]["arguments"] == ia.uninstall_arguments(folder)
    # a new Blender in a folder of another name (a Blender update by Install.bat): the app makes it there too
    new = os.path.join(folder, "blender-5.3.0-windows-x64")
    os.makedirs(new)
    open(os.path.join(new, "blender.exe"), "wb").close()
    done = appicon.ensure_uninstall_shortcuts(folder, os.path.join(new, "blender.exe"), "i.ico")
    assert done == [f"{ia.UNINSTALL_LNK}: made in the Fresing Render.exe's folder"]
    assert os.path.isfile(os.path.join(new, ia.UNINSTALL_LNK))


def test_no_uninstaller_no_shortcut(tmp_path, monkeypatch):
    folder, exe, links = _install(tmp_path, monkeypatch, script=False)
    assert appicon.ensure_uninstall_shortcuts(folder, exe, "i.ico") == [] and not links


def test_the_start_up_refresh_runs_it_after_the_entry():
    t = _text("fresing_render", "appicon.py")
    assert t.index('("installed-apps entry"') < t.index('("uninstall", lambda: ensure_uninstall_shortcuts')


# ---- the PowerShell side -----------------------------------------------------------------------------------------

def test_the_installer_makes_both_with_the_entry_s_command():
    t = _text("installer", "Install-FresingRender.ps1")
    assert '$uninstallCmd = "powershell.exe $uninstallArgs"' in t
    assert 'UninstallString = "$uninstallCmd -Pause"' in t and "QuietUninstallString = $uninstallCmd" in t
    assert 'foreach ($dir in @($InstallDir, $BlenderDir))' in t and '"Uninstall Fresing Render.lnk"' in t
    assert '$lnk.Arguments = "$uninstallArgs -Pause"' in t
    assert 'System32\\WindowsPowerShell\\v1.0\\powershell.exe' in t
    assert f'$lnk.Description = "{ia.UNINSTALL_TEXT}"' in t
    assert ("To remove Fresing Render later: Settings > Apps > Installed apps, or 'Uninstall Fresing Render' in "
            "$InstallDir") in t
    t.encode("ascii")


def test_the_uninstaller_started_from_inside_the_folder_leaves_it_free():
    t = _text("installer", "Uninstall-FresingRender.ps1")
    assert "[Environment]::CurrentDirectory = [IO.Path]::GetTempPath()" in t
    gone = t.index("the folder is gone")
    assert gone < t.index("installed.txt is missing")                     # a second run says so plainly
    assert "for ($try = 0; $try -lt 4" in t
    assert "Uninstall Fresing Render" in t
    t.encode("ascii")


def test_the_self_test_the_windows_job_and_the_docs_know_it():
    assert 'check("Windows: Uninstall shortcut in the install folder"' in _text("fresing_render", "selftest.py")
    ci = _text("tools", "ci_windows_install.ps1")
    assert "Uninstall Fresing Render.lnk" in ci and "Check-UninstallLinks" in ci
    for doc in (("docs", "README-install.txt"), ("docs", "USER-GUIDE.md"), ("docs", "COMPANY-USE.md")):
        assert "Uninstall Fresing Render" in _text(*doc), doc
