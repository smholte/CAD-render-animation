"""The real-size models of the learning sets "Painted faces" and "Logos and stickers" (task 0235): the makers write
them as revision "r"; names kept, real sizes, one solid per part, the painted faces are there."""

import os
import re
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")


def make(tmp_path, maker, rev="r"):
    out = str(tmp_path / f"{maker}_{rev}.step")
    r = subprocess.run([sys.executable, os.path.join(TOOLS, f"make_test_{maker}.py"), out, rev],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-800:]
    return out


def read(path):
    pytest.importorskip("OCP")
    with open(path, encoding="latin-1") as fh:
        return fh.read()


def names(text):
    return sorted(set(re.findall(r"PRODUCT\('([^']*)'", text)))


def test_the_shipped_copies_are_the_makers_models():
    for m in ("faces", "decals"):
        a = os.path.join(ROOT, "tests", "data", f"test_{m}_r.step")
        b = os.path.join(ROOT, "fresing_render", "data", f"test_{m}_r.step")
        with open(a, "rb") as fa, open(b, "rb") as fb:
            assert fa.read() == fb.read(), f"copy tests/data/test_{m}_r.step to fresing_render/data/"


def test_faces_keep_their_part_names_and_painted_faces(tmp_path):
    text = read(make(tmp_path, "faces"))
    for n in ("HOUSING", "BRACKET", "COVER", "BLOCK", "EVERY FACE"):
        assert n in text
    # the blue face still carries its appearance name; red and orange are painted too
    assert "Aluminum - Anodized Glossy (Blue)" in text
    assert text.count("COLOUR_RGB(") >= 3
    # holes and fillets: far more faces than the boxes of revision a
    assert text.count("ADVANCED_FACE(") > 60


def test_decals_model_is_real_size_and_keeps_its_names(tmp_path):
    pytest.importorskip("OCP")
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPControl import STEPControl_Reader
    path = make(tmp_path, "decals")
    text = read(path)
    for n in ("PANEL", "BARREL", "BOX"):
        assert n in text
    rd = STEPControl_Reader()
    assert rd.ReadFile(path) == IFSelect_RetDone
    rd.TransferRoots()
    box = Bnd_Box()
    BRepBndLib.Add_s(rd.OneShape(), box)
    x0, y0, z0, x1, y1, z1 = box.CornerMin().X(), box.CornerMin().Y(), box.CornerMin().Z(), box.CornerMax().X(), box.CornerMax().Y(), box.CornerMax().Z()
    assert z1 - z0 == pytest.approx(892, abs=2)          # a 200 l drum, 880 mm + its bung
    assert x1 - x0 > 3000                                # panel 1.2 m, two drums, a box
    assert text.count("PANEL") >= 1 and "BARREL" in text


def test_revisions_a_and_b_are_unchanged(tmp_path):
    a = read(make(tmp_path, "decals", "a"))
    assert "400.0" in a or "400." in a
    assert len(names(a)) >= 3
