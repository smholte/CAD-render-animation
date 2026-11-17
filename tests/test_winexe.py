"""'Fresing Render.exe' (task 0177): the byte work in plain Python. The Windows part (resources written with
UpdateResource, the copy started, Task Manager's name read from the running process) runs on GitHub's Windows job
(tools/appicon_test.py, tools/ci_windows_install.ps1)."""

from __future__ import annotations

import json
import os
import struct
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from fresing_render import appicon as ai  # noqa: E402
from fresing_render import winexe as w  # noqa: E402

BLENDER_RES = os.path.join(ROOT, "tests", "data", "blender_5.2.3_version.res")   # blender.exe's own, 636 bytes


def test_blender_version_resource_is_rebuilt_byte_for_byte():
    data = open(BLENDER_RES, "rb").read()
    root = w.parse_version(data)
    assert w.write_node(root) == data
    s = w.strings(root)
    assert s["FileDescription"] == "Blender" and s["ProductName"] == "Blender" and s["OriginalFilename"] == "blender.exe"


def test_rebranded_names_fresing_render_and_keeps_the_rest():
    data = open(BLENDER_RES, "rb").read()
    new = w.rebranded(data, "5.2")
    root = w.parse_version(new)
    s = w.strings(root)
    assert s["FileDescription"] == "Fresing Render" and s["ProductName"] == "Fresing Render"
    assert s["CompanyName"] == "Fresing" and "Blender 5.2" in s["Comments"]
    assert s["LegalCopyright"] == "GPLv3 (Blender Foundation)" and s["OriginalFilename"] == "blender.exe"
    old = w.parse_version(data)
    assert root.value == old.value                     # VS_FIXEDFILEINFO (version numbers) unchanged
    assert root.find("VarFileInfo").children[0].value == old.find("VarFileInfo").children[0].value
    assert struct.unpack_from("<H", new, 0)[0] == len(new)
    assert w.write_node(w.parse_version(new)) == new   # what we write reads back the same


def test_icon_resources_from_the_app_icon():
    ico = open(ai.SHIPPED_ICON, "rb").read()
    group, images = w.icon_resources(ico)
    n = struct.unpack_from("<H", group, 4)[0]
    assert n == 8 and len(group) == 6 + 14 * n
    for i, (rid, img) in enumerate(images):
        wd, h, _, _, planes, bpp, size, gid = struct.unpack_from("<BBBBHHIH", group, 6 + 14 * i)
        assert gid == rid >= w.ICON_IDS_FROM and size == len(img) and bpp == 32
    assert images[-1][1][:8] == b"\x89PNG\r\n\x1a\n"     # 256 px stays PNG
    with pytest.raises(ValueError):
        w.icon_resources(b"\0\0\2\0\1\0" + b"\0" * 16)


def fake_pe(signed=True, magic=0x20B) -> bytearray:
    """A made-up program file: MZ, PE header, optional header with the data directories, a body, a certificate."""
    lfanew = 0x80
    opt_size = 240 if magic == 0x20B else 224
    b = bytearray(0x400)
    b[0:2] = b"MZ"
    struct.pack_into("<I", b, 0x3C, lfanew)
    b[lfanew:lfanew + 4] = b"PE\0\0"
    struct.pack_into("<HH", b, lfanew + 4, 0x8664, 0)
    struct.pack_into("<H", b, lfanew + 20, opt_size)
    opt = lfanew + 24
    struct.pack_into("<H", b, opt, magic)
    struct.pack_into("<I", b, opt + 64, 0x1234)                      # checksum
    struct.pack_into("<H", b, opt + 68, 3)                           # console
    b += b"\xAB" * 0x200                                             # the program's sections
    if signed:
        dirs = opt + (112 if magic == 0x20B else 96)
        struct.pack_into("<II", b, dirs + 32, len(b), 0x40)
        b += b"\xCE" * 0x40
    return b


@pytest.mark.parametrize("magic", [0x20B, 0x10B])
def test_signature_off_and_gui_subsystem(magic):
    pe = fake_pe(magic=magic)
    assert w.subsystem(pe) == 3 and w.signature(pe)[1] == 0x40
    body = bytes(pe[:0x600])
    out = w.unsigned_gui(pe)
    assert w.subsystem(out) == 2 and w.signature(out) == (0, 0)
    assert len(out) == 0x600 and bytes(out[0x400:]) == body[0x400:]   # only the certificate is cut
    opt, _ = w._optional_header(out)
    assert struct.unpack_from("<I", out, opt + 64)[0] == 0


def test_unsigned_program_stays_whole():
    pe = fake_pe(signed=False)
    n = len(pe)
    w.unsigned_gui(pe)
    assert len(pe) == n and w.subsystem(pe) == 2


def test_not_a_program_is_refused():
    with pytest.raises(ValueError):
        w.unsigned_gui(bytearray(b"PK\3\4" + b"\0" * 100))


def test_signature_in_the_middle_is_refused():
    pe = fake_pe()
    _, dirs = w._optional_header(pe)
    struct.pack_into("<II", pe, dirs + 32, 0x300, 0x40)             # not at the end: we would cut the program
    with pytest.raises(ValueError):
        w.unsigned_gui(pe)


def test_paths_and_console_exe(tmp_path):
    (tmp_path / "blender.exe").write_bytes(b"x")
    copy = tmp_path / w.COPY_NAME
    assert w.copy_path(str(tmp_path / "blender.exe")) == str(copy)
    assert w.is_copy(str(copy)) and w.is_copy(str(copy).upper()) and not w.is_copy(str(tmp_path / "blender.exe"))
    assert w.console_exe(str(copy)) == str(tmp_path / "blender.exe")
    assert w.console_exe(str(tmp_path / "blender.exe")) == str(tmp_path / "blender.exe")
    assert w.blender_exe_of(str(copy)) == str(tmp_path / "blender.exe")


def test_usable_needs_a_checked_stamp_of_this_blender(tmp_path):
    exe = tmp_path / "blender.exe"
    exe.write_bytes(b"blender")
    icon = tmp_path / "i.ico"
    icon.write_bytes(b"icon")
    assert not w.usable(str(exe))
    (tmp_path / w.COPY_NAME).write_bytes(b"copy")
    stamp = dict(w.stamp_for(str(exe), str(icon)), ok=True)
    (tmp_path / w.STAMP_NAME).write_text(json.dumps(stamp))
    assert w.usable(str(exe))
    exe.write_bytes(b"a newer blender")                 # another size: made for another Blender
    assert not w.usable(str(exe))


def test_smart_app_control_state_can_be_set_for_tests(monkeypatch):
    monkeypatch.setenv("FRESING_SAC", "1")
    assert w.sac_state() == 1
    monkeypatch.delenv("FRESING_SAC")
    if sys.platform != "win32":
        assert w.sac_state() == 0


def test_ensure_does_nothing_off_windows(tmp_path):
    if sys.platform == "win32":
        pytest.skip("Windows: tools/appicon_test.py")
    assert w.ensure(str(tmp_path / "blender.exe"), ai.SHIPPED_ICON) == ""
    assert w.app_exe(str(tmp_path / "blender.exe")) == str(tmp_path / "blender.exe")


# ---------------------------------------------------------------------------
# The shortcuts start the copy (appicon.plan)
# ---------------------------------------------------------------------------

INST = os.path.join(os.sep, "x", "FresingRender")
BDIR = os.path.join(INST, "blender-5.2.3-windows-x64")
COPY = os.path.join(BDIR, w.COPY_NAME)
LAUNCHER = os.path.join(BDIR, "blender-launcher.exe")
ICON = os.path.join(INST, ai.ICON_FILE)


def link(**kw):
    base = {"target": LAUNCHER, "arguments": "--app-template fresing_render", "icon": ICON, "icon_index": 0,
            "app_id": ai.APP_ID}
    base.update(kw)
    return base


def test_app_shortcut_is_pointed_at_the_copy():
    assert ai.plan(link(), INST, ICON, app_target=COPY) == {"icon": False, "app_id": "", "target": COPY}
    assert ai.plan(link(target=COPY), INST, ICON, app_target=COPY)["target"] == ""


def test_back_to_the_launcher_when_the_copy_cannot_be_used():
    assert ai.plan(link(target=COPY), INST, ICON, app_target=LAUNCHER)["target"] == LAUNCHER


def test_console_shortcuts_keep_blender_exe():
    pc = link(target=os.path.join(BDIR, "blender.exe"), arguments='--background --python "x" -- "D" quick', app_id="")
    assert ai.plan(pc, INST, ICON, app_target=COPY)["target"] == ""


def test_a_target_outside_the_install_is_never_set():
    assert ai.plan(link(), INST, ICON, app_target=os.path.join(os.sep, "elsewhere", w.COPY_NAME))["target"] == ""


def test_restart_after_update_keeps_the_copy(tmp_path):
    pytest.importorskip("bpy")
    from fresing_render.blender import updates
    copy = tmp_path / w.COPY_NAME
    for f in ("blender.exe", "blender-launcher.exe", w.COPY_NAME):
        (tmp_path / f).write_bytes(b"x")
    assert updates.build_restart(str(copy), "fresing_render", "", windows=True)[0] == str(copy)
    # started as blender.exe: the copy only when its stamp says it was checked for this blender.exe
    assert updates.build_restart(str(tmp_path / "blender.exe"), "", "", windows=True) == \
        [str(tmp_path / "blender-launcher.exe")]
    icon = tmp_path / "i.ico"
    icon.write_bytes(b"i")
    (tmp_path / w.STAMP_NAME).write_text(json.dumps(dict(w.stamp_for(str(tmp_path / "blender.exe"), str(icon)), ok=True)))
    assert updates.build_restart(str(tmp_path / "blender.exe"), "", "", windows=True) == [str(copy)]
