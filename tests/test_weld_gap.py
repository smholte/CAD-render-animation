"""Task 0368: a square groove with a root gap (the plates' ends a few mm apart, no common edge) is a butt weld – by
its name and by its shape; a flush filler bar in such a gap is no weld."""

from __future__ import annotations

import os
import sys

import pytest

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)

from fresing_render.core import weld_cad, weld_symbols  # noqa: E402

import weld_cad_models as models  # noqa: E402


def _gap(kind, tmp):
    models._CACHE.pop(kind, None)
    try:
        return models.detect(kind, tmp, step=os.path.join(HERE, "data", f"test_weldment_gap_{kind}.step"))
    finally:
        models._CACHE.pop(kind, None)              # (the CAD frames of the same kind are cached under this name)


@pytest.mark.parametrize("kind,how", [("inventor", "name"), ("unnamed", "shape")])
def test_square_groove_with_a_gap_is_a_butt_weld(kind, how, tmp_path):
    found, by = _gap(kind, str(tmp_path))
    assert len(found) == 1, [(f.body, f.kind, f.note) for f in found]      # the flush filler bar is no weld
    f = found[0]
    assert f.how == how and f.kind == "BUTT"
    assert {by[f.part_a].name, by[f.part_b].name} == {"PLATE A", "PLATE B"}
    assert f.gap == pytest.approx(0.003, abs=1e-4)
    assert f.size == pytest.approx(0.007, abs=0.0005)                     # the cap: 3 + 2 x 2 mm
    assert f.length == pytest.approx(0.150, abs=0.001)
    assert f.note == "square groove, gap 3 mm"
    s = f.seams[0]
    assert s.kind == "BUTT" and not s.closed
    # the seam on the plates' top face, in the middle of the gap, along the joint
    assert s.points[:, 0] == pytest.approx([0.2015, 0.2015], abs=1e-4)
    assert s.points[:, 2] == pytest.approx([0.010, 0.010], abs=1e-4)
    assert sorted(s.points[:, 1]) == pytest.approx([0.0, 0.150], abs=1e-4)
    c = s.corners[0]
    assert c.na == pytest.approx([0, 0, 1], abs=1e-6) and abs(float(c.oa[0] - c.ob[0])) == pytest.approx(0.003, abs=1e-4)
    assert "groove (butt), cap 7 mm" in weld_cad.describe(f)


def test_the_symbol_of_a_known_square_groove_is_square():
    w = weld_symbols.Weld(1, kind="BUTT", thickness=0.010, seams=[weld_symbols.Seam("BUTT", 0.15)])
    assert weld_symbols.symbol(w).glyph == weld_symbols.V_BUTT_OTHER                 # 10 mm plates: a V by default
    w.square = True
    assert weld_symbols.symbol(w).glyph == weld_symbols.SQUARE_BUTT                  # the CAD file says square
