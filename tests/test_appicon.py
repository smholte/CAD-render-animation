"""The Fresing icon (task 0169): the icon file, the splash, which shortcuts get what, the installer's shortcuts.

The ctypes/COM part runs only on Windows: tools/appicon_test.py on GitHub's Windows job (tools/ci_windows_install.ps1).
"""

from __future__ import annotations

import os
import struct
import subprocess
import sys

import numpy as np
import pytest
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from fresing_render import appicon as ai  # noqa: E402

ICO = os.path.join(ROOT, "fresing_render", "brand", "fresing-render.ico")
SPLASH = os.path.join(ROOT, "app_template", "fresing_render", "splash.png")
GREEN = (0x47, 0x9B, 0x29)


def _entries():
    data = open(ICO, "rb").read()
    _, kind, n = struct.unpack_from("<HHH", data, 0)
    assert kind == 1
    out = {}
    for i in range(n):
        w, h, _, _, _, bpp, size, off = struct.unpack_from("<BBBBHHII", data, 6 + 16 * i)
        out[w or 256] = (bpp, data[off:off + size])
    return out


def test_ico_has_every_size_256_as_png():
    e = _entries()
    assert sorted(e) == [16, 20, 24, 32, 40, 48, 64, 256]
    assert e[256][1][:8] == b"\x89PNG\r\n\x1a\n"
    for s in (16, 20, 24, 32, 40, 48, 64):
        bpp, blob = e[s]
        assert bpp == 32 and blob[:4] == struct.pack("<I", 40)            # a 32-bit bitmap, not PNG


def _image(size):
    im = Image.open(ICO)
    im.size = (size, size)
    im.load()
    return np.asarray(im.convert("RGBA")).astype(int)


@pytest.mark.parametrize("size", [16, 20, 24])
def test_small_sizes_keep_a_sharp_f(size):
    """The F's stem, its swoosh and the gap under it (the r beside it: test_small_sizes_show_two_letters)."""
    a = _image(size)
    white = (a[..., :3] == 255).all(-1) & (a[..., 3] == 255)
    green = (np.abs(a[..., :3] - GREEN).sum(-1) == 0) & (a[..., 3] == 255)
    cols = np.where(white.any(0))[0]
    stem = white[:, cols[0]].sum()
    assert stem >= size * 0.3                          # the stem is a solid white column, not blurred grey
    assert white[:, cols[0]:cols[0] + 2].all(1).sum() == stem      # and at least 2 px wide
    assert green.sum() >= 2 * (size // 3)              # the green bar in pure Fresing Green
    g_rows = np.where(green.any(1))[0]
    w_rows = np.where(white.any(1))[0]
    assert g_rows.max() + 1 < w_rows.min()             # a gap of at least 1 px between bar and stem
    assert a[0, 0, 3] < 128 and a[size // 2, size // 2, 3] == 255    # rounded corners, solid middle


def test_big_size_is_fr_from_the_logo():
    """The icon is "Fr" (owner, 16 Nov 2026): the F with its green swoosh, then the r - two white letters."""
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import make_app_icon as m
    want = np.asarray(m.master_icon().resize((256, 256), Image.BOX)).astype(int)
    a = _image(256)
    assert np.abs(a - want).max() <= 1
    white = (a[..., :3] > 240).all(-1) & (a[..., 3] == 255)     # see-through corner pixels have no colour
    cols = white.any(0)
    starts = np.flatnonzero(cols[1:] & ~cols[:-1]) + 1
    assert len(starts) == 2                            # F and r: two separate white letters
    green = (np.abs(a[..., :3] - GREEN).sum(-1) <= 6)
    assert np.flatnonzero(green.any(1)).max() < np.flatnonzero(white.any(1)).min()   # the swoosh above them


@pytest.mark.parametrize("size", [16, 20, 24])
def test_small_sizes_show_two_letters(size):
    white = (_image(size)[..., :3] == 255).all(-1)
    cols = white.any(0)
    assert (cols[1:] & ~cols[:-1]).sum() == 2          # F and r start apart: a gap column between them


def test_splash_has_the_logo_in_fresing_green():
    im = Image.open(SPLASH)
    assert im.size == (1000, 500)                       # Blender 5.2.3 reads only splash.png (no _2x)
    a = np.asarray(im.convert("RGB")).astype(int)
    green = (np.abs(a - GREEN).sum(-1) <= 6)
    assert green.sum() > 1000                           # the logo's bar and line
    amber = (a[..., 0] > 200) & (a[..., 1] > 140) & (a[..., 1] < 200) & (a[..., 2] < 60)
    assert amber.sum() == 0                             # the old amber bar is gone


def test_made_files_are_up_to_date():
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "make_app_icon.py"), "--check"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


# ---------------------------------------------------------------------------
# Which shortcuts get what
# ---------------------------------------------------------------------------

INST = os.path.join(os.sep, "x", "FresingRender")
EXE = os.path.join(INST, "blender-5.2.3-windows-x64", "blender.exe")
ICON = os.path.join(INST, ai.ICON_FILE)


def info(**kw):
    base = {"target": os.path.join(INST, "blender-5.2.3-windows-x64", "blender-launcher.exe"),
            "arguments": "--app-template fresing_render", "icon": EXE, "icon_index": 0, "app_id": ""}
    base.update(kw)
    return base


def test_plan_an_old_app_shortcut_gets_icon_and_id():
    assert ai.plan(info(), INST, ICON) == {"icon": True, "app_id": ai.APP_ID, "target": ""}


def test_plan_a_right_shortcut_needs_nothing():
    assert ai.plan(info(icon=ICON, app_id=ai.APP_ID), INST, ICON) == {"icon": False, "app_id": "", "target": ""}
    assert ai.plan(info(icon=ICON.upper(), app_id=ai.APP_ID), INST, ICON)["icon"] is (os.path.normcase("A") == "A")


def test_plan_other_shortcuts_get_the_icon_but_no_id():
    pc = info(target=EXE, arguments='--background --python "x\\launcher.py" -- "D" quick')
    assert ai.plan(pc, INST, ICON) == {"icon": True, "app_id": "", "target": ""}
    assert ai.plan(info(icon=ICON, icon_index=3, app_id=ai.APP_ID), INST, ICON)["icon"]


def test_plan_never_touches_a_shortcut_outside_the_install():
    other = info(target=os.path.join(os.sep, "x", "FresingRenderOld", "blender.exe"))
    assert ai.plan(other, INST, ICON) == {"icon": False, "app_id": "", "target": ""}
    assert ai.plan(info(target=""), INST, ICON) == {"icon": False, "app_id": "", "target": ""}


def test_install_dir_needs_installed_txt(tmp_path):
    blender = tmp_path / "FresingRender" / "blender-5.2.3-windows-x64"
    blender.mkdir(parents=True)
    exe = str(blender / "blender.exe")
    assert ai.install_dir(exe) == ""
    (tmp_path / "FresingRender" / "installed.txt").write_text("x")
    assert ai.install_dir(exe) == str(tmp_path / "FresingRender")
    assert ai.install_dir("") == ""


def test_ensure_icon_copies_and_replaces(tmp_path):
    dst = ai.ensure_icon(str(tmp_path))
    assert open(dst, "rb").read() == open(ai.SHIPPED_ICON, "rb").read()
    open(dst, "wb").write(b"old")
    ai.ensure_icon(str(tmp_path))
    assert open(dst, "rb").read() == open(ai.SHIPPED_ICON, "rb").read()
    assert ai.ensure_icon(str(tmp_path / "missing")) == ""


def test_shortcut_paths(tmp_path):
    desk, prog, app = tmp_path / "Desk", tmp_path / "Prog", tmp_path / "App"
    (prog / "Fresing Render").mkdir(parents=True)
    pinned = app / ai.PINNED
    pinned.mkdir(parents=True)
    desk.mkdir()
    for p in (desk / "Fresing Render.lnk", desk / "Other.lnk", prog / "Fresing Render" / "Fresing Render.lnk",
              prog / "Fresing Render" / "notes.txt", pinned / "Fresing Render.lnk", pinned / "Word.lnk"):
        p.write_text("x")
    got = [os.path.relpath(p, tmp_path) for p in ai.shortcut_paths(str(desk), str(prog), str(app))]
    assert os.path.join("Desk", "Fresing Render.lnk") in got and os.path.join("Desk", "Other.lnk") not in got
    assert os.path.join("Prog", "Fresing Render", "Fresing Render.lnk") in got
    assert not any(g.endswith(".txt") for g in got)
    assert os.path.join("App", ai.PINNED, "Word.lnk") in got          # listed; plan() leaves it by its target


def test_wanted_only_for_the_app_on_windows():
    assert ai.wanted("win32", False, "fresing_render", {})
    assert not ai.wanted("win32", True, "fresing_render", {})
    assert not ai.wanted("win32", False, "", {})
    assert not ai.wanted("linux", False, "fresing_render", {})
    assert not ai.wanted("win32", False, "fresing_render", {"FRESING_NO_APPICON": "1"})


def test_relaunch_command_prefers_the_launcher(tmp_path):
    exe = tmp_path / "blender.exe"
    assert ai.relaunch_command(str(exe)) == f'"{exe}" --app-template fresing_render'
    (tmp_path / "blender-launcher.exe").write_text("x")
    assert ai.relaunch_command(str(exe)) == f'"{tmp_path / "blender-launcher.exe"}" --app-template fresing_render'


# ---------------------------------------------------------------------------
# The installer and the app's own shortcut maker
# ---------------------------------------------------------------------------

def test_installer_shortcuts_use_the_fresing_icon():
    ps = open(os.path.join(ROOT, "installer", "Install-FresingRender.ps1"), encoding="utf-8").read()
    assert ps.count("IconLocation = $IconLoc") == 2                  # MakeShortcut + the user guide
    assert '"$BlenderExe,0"' in ps.split("$IconLoc =")[1].split("\n")[0]     # only as the fallback
    assert ps.count("IconLocation") == 2
    assert "brand\\fresing-render.ico" in ps and "set_shortcuts.py" in ps and ".appicon" in ps


def test_pc_check_shortcuts_use_the_icon_when_given():
    pytest.importorskip("bpy")
    from fresing_render.pccheck import ops
    s = ops.shortcut_script("S", r"C:\B\blender.exe", r"C:\D", ["quick"], r"C:\F\fresing-render.ico")
    assert r"$l.IconLocation = 'C:\F\fresing-render.ico,0'" in s
    assert r"$l.IconLocation = 'C:\B\blender.exe,0'" in ops.shortcut_script("S", r"C:\B\blender.exe", r"C:\D", ["quick"])


def test_the_icon_ships_inside_the_extension():
    init = open(os.path.join(ROOT, "fresing_render", "__init__.py"), encoding="utf-8").read()
    assert "appicon.startup()" in init
    assert os.path.isfile(ai.SHIPPED_ICON)


def test_a_pinned_plain_blender_keeps_its_icon():
    plain = info(target=EXE, arguments="")
    assert ai.plan(plain, INST, ICON, pinned=True) == {"icon": False, "app_id": "", "target": ""}
    assert ai.plan(info(), INST, ICON, pinned=True) == {"icon": True, "app_id": ai.APP_ID, "target": ""}
    assert ai.is_pinned(os.path.join("C:", "AppData", ai.PINNED, "Fresing Render.lnk"))
    assert not ai.is_pinned(os.path.join("C:", "Desktop", "Fresing Render.lnk"))


def test_no_icon_file_writes_nothing(tmp_path):
    assert ai.refresh_shortcuts(str(tmp_path), "", ["x.lnk"]) == []
    assert ai.refresh_shortcuts(str(tmp_path), str(tmp_path / "missing.ico"), ["x.lnk"]) == []


def test_ensure_icon_leaves_no_temp_file(tmp_path):
    ai.ensure_icon(str(tmp_path))
    assert os.listdir(tmp_path) == [ai.ICON_FILE]


def test_a_replaced_icon_file_is_flagged_for_a_redraw(tmp_path):
    ai.STATE.pop("icon_changed", None)
    ai.ensure_icon(str(tmp_path))
    assert ai.STATE.pop("icon_changed", False)
    ai.ensure_icon(str(tmp_path))                                  # the same again: nothing to redraw
    assert not ai.STATE.pop("icon_changed", False)
