"""Task 0163: the render kit's console route continues a run, Pause stays paused, English day names; House zip names
checked raw (as on Windows); the turbine converter's worn-edge check."""

import importlib.util
import io
import os
import sys
import zipfile

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KIT = os.path.join(ROOT, "site", "render_kit")


def _load(name, file):
    spec = importlib.util.spec_from_file_location(name, os.path.join(KIT, file))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --- kit: console route ------------------------------------------------------------------------------------------

def test_console_route_offers_to_continue(tmp_path):
    kr = _load("kit_run_0163", "kit_run.py")
    kit = _load("kit_0163", "make_site_pictures.py")
    out = str(tmp_path)
    assert kit.ask_resume(out, ask=lambda q: "y") is False          # no run: nothing to ask
    st = kr.RunState.new(out, [{"id": "a", "views": ["X", "Y", "Z"], "video": "none"}], {})
    st.record("a", "still:x", {"file": "a_x.jpg", "model": "a", "kind": "picture", "caption": "x"})
    st.record("a", "still:y", {"file": "a_y.jpg", "model": "a", "kind": "picture", "caption": "y"})
    asked = []
    assert kit.ask_resume(out, ask=lambda q: asked.append(q) or "") is True      # Enter = continue
    assert "Continue the run of" in asked[0] and "2 of 3" in asked[0]
    assert kit.ask_resume(out, ask=lambda q: "N") is False
    assert kit.ask_resume(out, ask=lambda q: (_ for _ in ()).throw(EOFError())) is True


def test_bat_console_route_asks():
    bat = open(os.path.join(KIT, "Make site pictures.bat"), "rb").read().decode("utf-8")
    line = [ln for ln in bat.splitlines() if "--start-at=%START%" in ln][0]
    assert "--ask-resume" in line
    assert "offers to continue" in bat


# --- kit: status window --------------------------------------------------------------------------------------------

def test_status_window_keeps_resume_while_pause_is_asked():
    ps = open(os.path.join(KIT, "kit_window.ps1"), "rb").read().decode("ascii")
    assert 'CultureInfo]::InvariantCulture' in ps and 'ToString("ddd HH\\:mm", [System' in ps
    assert '$state -eq "paused" -or $word -eq "pause"' in ps          # the button follows control.txt too
    assert '$asked -eq "pause"' in ps                                 # closing asks while pause is asked
    assert b"\n" not in ps.encode().replace(b"\r\n", b"")


# --- House: raw zip names ------------------------------------------------------------------------------------------

def _zip_with(names_and_data, patch=None):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for n, d in names_and_data:
            zf.writestr(n, d)
    data = buf.getvalue()
    if patch:
        assert data.count(patch[0]) == 2                            # local header + central directory
        data = data.replace(*patch)
    return data


def test_windows_backslash_name_refused(monkeypatch):
    from fresing_render.core import house_scene as hs
    data = _zip_with([("light\\a.png", b"x")])
    monkeypatch.setattr(os, "sep", "\\")                           # Windows: zipfile turns '\\' into '/'
    with pytest.raises(hs.FormatError, match="forward slashes"):
        hs.read_zip(data)


def test_nul_in_name_refused():
    from fresing_render.core import house_scene as hs
    data = _zip_with([("bake.json_evil", b"x")], (b"bake.json_evil", b"bake.json\0evil"))
    with pytest.raises(hs.FormatError, match="control character"):
        hs.read_zip(data)


def test_name_not_utf8_has_a_clear_message():
    from fresing_render.core import house_scene as hs
    data = _zip_with([("aåb.txt", b"x")], ("aåb.txt".encode(), b"a\xff\xfeb.txt"))
    with pytest.raises(hs.FormatError, match="not UTF-8"):
        hs.read_zip(data)


# --- turbine converter: the worn edge ------------------------------------------------------------------------------

def test_worn_edge_check():
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    bpy = pytest.importorskip("bpy")                                 # noqa: F841
    from site_projects import iea15
    iea15.check_worn_edge(np.array([-0.05, -0.998, 0.0]), 1)         # mirrored stand-in: leads on -y: fine
    iea15.check_worn_edge(np.array([0.5, -0.8, 0.0]), 1)             # within 45 degrees: fine
    with pytest.raises(RuntimeError, match="wrong edge"):
        iea15.check_worn_edge(np.array([0.0, 1.0, 0.0]), 2)          # unmirrored: leads on +y
    with pytest.raises(RuntimeError, match="wrong edge"):
        iea15.check_worn_edge(np.array([1.0, 0.0, 0.0]), 3)
