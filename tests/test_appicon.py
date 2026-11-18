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
    """Task 0212: the app's shortcut on the Desktop and directly in Programs, the Tools folder, the pinned icons."""
    desk, prog, app, tools = tmp_path / "Desk", tmp_path / "Prog", tmp_path / "App", tmp_path / "Inst" / "Tools"
    (prog / "Fresing Render").mkdir(parents=True)
    pinned = app / ai.PINNED
    for d in (pinned, desk, tools):
        d.mkdir(parents=True)
    for p in (desk / "Fresing Render.lnk", desk / "Other.lnk", prog / "Fresing Render.lnk", prog / "Word.lnk",
              prog / "Fresing Render" / "Fresing Render - Self test.lnk", tools / "PC check (quick).lnk",
              tools / "notes.txt", pinned / "Fresing Render.lnk", pinned / "Word.lnk"):
        p.write_text("x")
    got = [os.path.relpath(p, tmp_path) for p in ai.shortcut_paths(str(desk), str(prog), str(app), str(tools))]
    assert os.path.join("Desk", "Fresing Render.lnk") in got and os.path.join("Desk", "Other.lnk") not in got
    assert os.path.join("Prog", "Fresing Render.lnk") in got and os.path.join("Prog", "Word.lnk") not in got
    assert not any(g.startswith(os.path.join("Prog", "Fresing Render") + os.sep) for g in got)   # the old folder
    assert os.path.join("Inst", "Tools", "PC check (quick).lnk") in got
    assert not any(g.endswith(".txt") for g in got)
    assert os.path.join("App", ai.PINNED, "Word.lnk") in got          # listed; plan() leaves it by its target


def test_one_shortcut_only_names():
    """Task 0212: only "Fresing Render" on the Desktop; six extras in the Tools folder; old names are not new ones."""
    assert ai.DESKTOP_NAMES == ("Fresing Render.lnk",) and ai.APP_LNK == "Fresing Render.lnk"
    assert sorted(ai.TOOLS) == ["full", "guide", "heavy", "quick", "safe", "selftest"]
    assert ai.TOOLS["safe"] == ai.SAFE_START
    assert not set(ai.TOOLS.values()) & set(ai.OLD_DESKTOP + ai.OLD_START_MENU)
    assert ai.OLD_SAFE_START in ai.OLD_START_MENU
    assert ai.tools_dir(INST) == os.path.join(INST, "Tools") and ai.tools_dir("") == ""


def test_old_shortcuts_found_by_name(tmp_path):
    desk, prog = tmp_path / "Desk", tmp_path / "Prog"
    menu = prog / "Fresing Render"
    menu.mkdir(parents=True)
    desk.mkdir()
    for p in (desk / "Fresing Render.lnk", desk / "Fresing Render - PC check.lnk", desk / "Other.lnk",
              menu / "Fresing Render.lnk", menu / "Fresing Render - User guide.lnk", menu / "Mine.lnk"):
        p.write_text("x")
    got = [os.path.relpath(p, tmp_path) for p in ai.old_shortcuts(str(desk), str(prog))]
    assert got == [os.path.join("Desk", "Fresing Render - PC check.lnk"),
                   os.path.join("Prog", "Fresing Render", "Fresing Render - User guide.lnk"),
                   os.path.join("Prog", "Fresing Render", "Fresing Render.lnk")]      # the app's own last


def test_tidy_plan_only_touches_our_shortcuts(tmp_path):
    inst = str(tmp_path / "Ins tallé")
    prog = tmp_path / "Prog"
    prog.mkdir()
    menu = os.path.join(str(prog), "Fresing Render")
    ours = os.path.join(inst, "blender-5.2.3-windows-x64", "blender.exe")
    found = {os.path.join("D", "Fresing Render - PC check.lnk"): ours,
             os.path.join(menu, "Fresing Render - User guide.lnk"):
                 os.path.join(inst, "blender", "portable", "guide", "user_guide.html"),
             os.path.join(menu, "Fresing Render - Self test.lnk"): r"C:\Other\blender.exe",     # someone else's
             os.path.join(menu, "Fresing Render - safe start.lnk"): "",                        # unreadable
             os.path.join(menu, "Fresing Render.lnk"): ours}
    plan = ai.tidy_plan(found, inst, str(prog))
    assert ("remove", os.path.join("D", "Fresing Render - PC check.lnk"), "") in plan
    assert ("remove", os.path.join(menu, "Fresing Render - User guide.lnk"), "") in plan
    assert ("move", os.path.join(menu, "Fresing Render.lnk"), os.path.join(str(prog), "Fresing Render.lnk")) in plan
    assert len(plan) == 3                                             # someone else's and the unreadable one stay
    # the installer made the new one already: the old app shortcut goes
    (prog / "Fresing Render.lnk").write_text("x")
    assert ("remove", os.path.join(menu, "Fresing Render.lnk"), "") in ai.tidy_plan(found, inst, str(prog))
    # a folder that only starts like the install folder is not inside it
    assert ai.tidy_plan({"x.lnk": inst + "2\\blender.exe"}, inst, str(prog)) == []
    assert ai.tidy_plan(found, "", str(prog)) == []


def test_tools_specs(tmp_path):
    """The Tools folder's six shortcuts: what they start, with which arguments; a missing file leaves its one out."""
    pytest.importorskip("numpy")
    inst = tmp_path / "FresingRender é"
    bdir = inst / "blender-5.2.3-windows-x64"
    ext = bdir / "portable" / "extensions" / "user_default" / "fresing_render"
    (ext / "pccheck").mkdir(parents=True)
    (ext / "guide").mkdir()
    blender = bdir / "blender.exe"
    desk = r"C:\Users\O'Brien\Desktop"
    assert ai.tools_specs(str(inst), str(blender), desk, str(ext)) == {}
    for f in (blender, bdir / "blender-launcher.exe", inst / "selftest_launcher.py", ext / "pccheck" / "launcher.py",
              ext / "guide" / "user_guide.html"):
        f.write_text("x")
    specs = ai.tools_specs(str(inst), str(blender), desk, str(ext))
    assert sorted(specs) == sorted(ai.TOOLS)
    for kind, spec in specs.items():
        assert spec["path"] == os.path.join(str(inst), "Tools", ai.TOOLS[kind]) and spec["description"]
    assert specs["selftest"]["target"] == str(blender)
    assert specs["selftest"]["arguments"] == f'--background --python "{inst / "selftest_launcher.py"}" -- "{desk}"'
    for mode in ("quick", "full", "heavy"):
        assert specs[mode]["target"] == str(blender)
        assert specs[mode]["arguments"] == \
            f'--background --python "{ext / "pccheck" / "launcher.py"}" -- "{desk}" {mode}'
    assert specs["safe"]["target"] == str(bdir / "blender-launcher.exe") and specs["safe"]["arguments"] == ai.APP_ARGS
    assert specs["guide"]["target"] == str(ext / "guide" / "user_guide.html") and specs["guide"]["arguments"] == ""
    # the installer makes the same six with the same names
    ps = open(os.path.join(ROOT, "installer", "Install-FresingRender.ps1"), encoding="utf-8").read()
    for name in ai.TOOLS.values():
        assert f'Join-Path $Tools "{name}"' in ps, name
    assert '$Tools = Join-Path $InstallDir "Tools"' in ps


def test_installer_and_uninstall_keep_only_the_app_shortcut():
    """Task 0212: Desktop and Start menu get only "Fresing Render.lnk"; old names removed only when ours."""
    ps = open(os.path.join(ROOT, "installer", "Install-FresingRender.ps1"), encoding="utf-8").read()
    made = [line for line in ps.splitlines() if line.lstrip().startswith("MakeShortcut (Join-Path")]
    for line in made:
        place = line.split("(Join-Path ")[1].split(" ")[0]
        name = line.split('"')[1]
        assert place == "$Tools" or name == "Fresing Render.lnk", line
    assert sum(" $Desktop " in f" {line} " for line in made) == 1
    assert 'MakeShortcut (Join-Path $Programs "Fresing Render.lnk")' in ps
    for name in ai.OLD_DESKTOP + ai.OLD_START_MENU + (ai.APP_LNK,):
        assert f'"{name}"' in ps, name
    assert 'StartsWith("$InstallDir\\", [StringComparison]::OrdinalIgnoreCase)' in ps
    un = open(os.path.join(ROOT, "installer", "Uninstall-FresingRender.ps1"), encoding="utf-8").read()
    for name in ai.OLD_DESKTOP + (ai.APP_LNK,):
        assert f'"{name}"' in un, name
    assert '(Join-Path $Programs "Fresing Render.lnk")' in un and '(Join-Path $Programs "Fresing Render")' in un


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
