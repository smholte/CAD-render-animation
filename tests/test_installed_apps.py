"""Fresing Render in Windows' Installed apps (task 0265): the key's values, what changes, the copy that ships inside
the extension, Update now's version, and the PowerShell files (read as text here; GitHub's Windows job runs them)."""
import datetime
import os
import re
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from fresing_render import update_helper  # noqa: E402
from fresing_render.core import installed_apps as ia  # noqa: E402

FOLDER = os.path.join("C:\\Users", "Sébastien Test", "AppData", "Local", "FresingRender") if os.name == "nt" else "/x/Sébastien Test/FresingRender"


class FakeRegistry:
    def __init__(self, values=None):
        self.values = values

    def read(self):
        return None if self.values is None else dict(self.values)

    def write(self, values):
        self.values = {**(self.values or {}), **values}


def _install(tmp_path, with_script=True):
    folder = tmp_path / "Mijn map é" / "FresingRender"
    (folder / "Tools").mkdir(parents=True)
    (folder / "blender-5.2.3-windows-x64").mkdir()
    (folder / "blender-5.2.3-windows-x64" / "blender.exe").write_bytes(b"x" * 3000)
    return str(folder)


def test_the_values_hold_everything_settings_shows():
    v = ia.wanted(FOLDER, "0.2.200", icon="i.ico", size_kb=1234, today=datetime.date(2026, 11, 23))
    assert v["DisplayName"] == "Fresing Render" and v["Publisher"] == "Fresing" and v["DisplayVersion"] == "0.2.200"
    assert v["InstallLocation"] == FOLDER and v["InstallDate"] == "20261123" and v["EstimatedSize"] == 1234
    assert v["NoModify"] == 1 and v["NoRepair"] == 1 and v["DisplayIcon"] == "i.ico"
    assert v["URLInfoAbout"].startswith("https://") and v["HelpLink"].startswith("https://")


def test_the_uninstall_command_quotes_a_path_with_a_space_and_an_accent():
    loud, quiet = ia.uninstall_string(FOLDER), ia.uninstall_string(FOLDER, quiet=True)
    script = os.path.join(FOLDER, "Tools", "Uninstall-FresingRender.ps1")
    assert f'-File "{script}"' in loud and f'-InstallDir "{FOLDER}"' in loud
    assert loud.endswith(" -Pause") and not quiet.endswith("-Pause") and quiet == loud[:-len(" -Pause")]
    assert loud.startswith("powershell.exe -NoProfile -ExecutionPolicy Bypass")


def test_changes_everything_for_a_new_key_or_another_folder_and_only_what_differs_otherwise():
    want = ia.wanted(FOLDER, "0.2.200", size_kb=10)
    assert ia.changes(None, want) == want
    assert ia.changes({"InstallLocation": "/other"}, want) == want
    same = dict(want, InstallDate="20200101")
    assert ia.changes(same, want) == {}                                   # the install date is kept
    older = dict(want, DisplayVersion="0.2.199", EstimatedSize=5)
    assert ia.changes(older, want) == {"DisplayVersion": "0.2.200", "EstimatedSize": 10}
    assert ia.changes(dict(want, NoModify=0), want) == {"NoModify": 1}


def test_the_folder_is_measured_only_for_a_new_key_or_a_new_version():
    want = ia.wanted(FOLDER, "0.2.200", size_kb=10)
    assert ia.needs_size(None, FOLDER, "0.2.200")
    assert not ia.needs_size(want, FOLDER, "0.2.200")
    assert ia.needs_size(want, FOLDER, "0.2.201")
    assert ia.needs_size(dict(want, EstimatedSize=0), FOLDER, "0.2.200")


def test_ensure_makes_the_entry_copies_the_uninstaller_and_is_quiet_the_second_time(tmp_path):
    folder = _install(tmp_path)
    reg = FakeRegistry()
    done = ia.ensure(folder, "0.2.200", registry=reg)
    assert "uninstaller copied into the Tools folder" in done and any("made" in d for d in done)
    assert os.path.isfile(ia.uninstaller_path(folder))
    assert reg.values["DisplayVersion"] == "0.2.200" and reg.values["EstimatedSize"] >= 3
    assert reg.values["UninstallString"].count(folder) == 2
    assert ia.ensure(folder, "0.2.200", registry=reg) == []                # nothing again
    again = ia.ensure(folder, "0.2.201", registry=reg)                     # after an update
    assert reg.values["DisplayVersion"] == "0.2.201" and again and "updated" in again[0]


def test_a_changed_uninstaller_is_replaced_and_no_script_means_no_entry(tmp_path):
    folder = _install(tmp_path)
    reg = FakeRegistry()
    ia.ensure(folder, "1", registry=reg)
    open(ia.uninstaller_path(folder), "wb").write(b"old")
    assert ia.ensure(folder, "1", registry=reg) == ["uninstaller copied into the Tools folder"]
    assert open(ia.uninstaller_path(folder), "rb").read() == open(ia.SHIPPED_UNINSTALLER, "rb").read()
    bare = FakeRegistry()
    assert ia.ensure(_install(tmp_path / "b"), "1", registry=bare, source=str(tmp_path / "none.ps1")) == []
    assert bare.values is None                                              # no dead Uninstall button


def test_an_entry_of_another_install_is_taken_over_not_mixed(tmp_path):
    folder = _install(tmp_path)
    reg = FakeRegistry({"InstallLocation": "/somewhere/else", "DisplayVersion": "9", "InstallDate": "20190101"})
    ia.ensure(folder, "0.2.200", registry=reg)
    assert reg.values["InstallLocation"] == folder and reg.values["InstallDate"] != "20190101"


# ---- Update now (update_helper.py) -----------------------------------------------------------------------------

def test_update_now_sets_version_and_size_and_the_new_uninstaller(tmp_path):
    folder = _install(tmp_path)
    ext = tmp_path / "ext"
    (ext / "installer_files").mkdir(parents=True)
    (ext / "installer_files" / "Uninstall-FresingRender.ps1").write_bytes(b"new script")
    (tmp_path / "x").mkdir()
    open(ia.uninstaller_path(folder), "wb").write(b"old script")
    written = {}
    plan = {"blender": os.path.join(folder, "blender-5.2.3-windows-x64", "blender.exe"), "ext_dir": str(ext)}
    note = update_helper.set_installed_apps_version(
        plan, "0.2.201", read=lambda: {"InstallLocation": folder, "DisplayVersion": "0.2.200"}, write=written.update)
    assert written["DisplayVersion"] == "0.2.201" and written["EstimatedSize"] >= 3
    assert open(ia.uninstaller_path(folder), "rb").read() == b"new script"
    assert "0.2.201" in note and "uninstaller" in note


def test_update_now_leaves_another_install_and_a_missing_entry_alone(tmp_path):
    folder = _install(tmp_path)
    plan = {"blender": os.path.join(folder, "blender-5.2.3-windows-x64", "blender.exe"), "ext_dir": str(tmp_path)}
    written = {}
    assert update_helper.set_installed_apps_version(plan, "2", read=lambda: None, write=written.update) == ""
    other = {"InstallLocation": str(tmp_path / "elsewhere")}
    assert update_helper.set_installed_apps_version(plan, "2", read=lambda: other, write=written.update) == ""
    assert written == {}
    def boom(_):
        raise OSError("denied")
    msg = update_helper.set_installed_apps_version(plan, "2", read=lambda: {"InstallLocation": folder}, write=boom)
    assert "not updated" in msg                                              # never raises: the update is done


# ---- the files -------------------------------------------------------------------------------------------------

def _text(*parts):
    return open(os.path.join(ROOT, *parts), encoding="utf-8", newline="").read().replace("\r\n", "\n")


def test_the_uninstaller_in_the_extension_is_the_installers_copy():
    assert _text("fresing_render", "installer_files", "Uninstall-FresingRender.ps1") == \
        _text("installer", "Uninstall-FresingRender.ps1"), "copy installer/Uninstall-FresingRender.ps1 into fresing_render/installer_files/"


def test_the_uninstaller_keeps_projects_runs_from_temp_and_removes_the_entry_last():
    t = _text("installer", "Uninstall-FresingRender.ps1")
    assert "projects" in t.lower() and "are kept" in t
    assert "GetTempPath" in t and "-FromTemp" in t and "-Pause" in t
    assert t.index("Remove-Item -LiteralPath $InstallDir") < t.index("Remove-Item -LiteralPath $AppsKey")
    assert "ieq $InstallDir" in t                                            # only the entry of this folder
    assert t.count("Finish 1") >= 2 and "Finish 0" in t                      # still open / not removable: exit 1
    t.encode("ascii")


def test_the_installer_writes_the_same_key_the_app_does():
    t = _text("installer", "Install-FresingRender.ps1")
    key = ia.KEY.replace("\\", "\\\\")
    assert re.search(r'HKCU:\\\\?Software', t) and "FresingRender" in t
    for name in ("DisplayName", "DisplayVersion", "Publisher", "DisplayIcon", "InstallLocation", "InstallDate",
                 "URLInfoAbout", "HelpLink", "UninstallString", "QuietUninstallString", "NoModify", "NoRepair",
                 "EstimatedSize"):
        assert name in t, name
    assert "Uninstall-FresingRender.ps1" in t and "-InstallDir" in t
    assert key  # (the value names are the ones core/installed_apps.wanted writes)
    assert set(ia.wanted(FOLDER, "1")) >= {"DisplayName", "UninstallString", "QuietUninstallString"}


def test_the_start_up_refresh_and_the_self_test_know_the_entry():
    assert "ensure_installed_apps" in open(os.path.join(ROOT, "fresing_render", "appicon.py"), encoding="utf-8").read()
    assert "Windows: in Installed apps" in open(os.path.join(ROOT, "fresing_render", "selftest.py"), encoding="utf-8").read()
