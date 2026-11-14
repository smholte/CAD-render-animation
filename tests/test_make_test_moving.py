"""Task 0082: the moving-part test model (tools/make_test_moving.py -> tests/data/test_moving.step, copy in the
extension)."""
import os
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import make_test_moving as maker  # noqa: E402
from fresing_render.importer import step_reader  # noqa: E402

STEP = os.path.join(HERE, "data", "test_moving.step")
N = maker.NUMBERS


def test_the_shipped_copy_is_the_test_data():
    with open(os.path.join(ROOT, "fresing_render", "data", "test_moving.step"), "rb") as a, open(STEP, "rb") as b:
        assert a.read() == b.read(), "copy tests/data/test_moving.step to fresing_render/data/"
    assert os.path.getsize(STEP) < 400 * 1024


def test_the_maker_checks_itself():
    root = maker.model()
    maker.check(root, say=lambda *_: None)
    assert maker.count_parts(root) == len(maker.PARTS) == 14


def test_the_numbers():
    assert N["sheave_centre"] == (8000.0, 0.0, 4300.0) and N["sheave_radius"] == 500.0
    assert N["horn_centre"] == (500.0, 0.0, 1200.0) and N["vertical"] == (-1500.0, 0.0, 1200.0)
    assert N["cable_start"] == (6800.0, 0.0, 4800.0) and N["pivot"] == (8000.0, 0.0, 6500.0)
    assert N["wire_start"] == (13800.0, 300.0, 7750.0) and N["wire_end"] == (7850.0, 300.0, 5250.0)
    # the routes: lines and arcs that meet without a kink, as long as their pieces
    cable, wire = maker.cable_route(), maker.wire_route()
    assert cable.length == pytest.approx(sum(s.length for s in cable.segments))
    assert np.allclose(cable.start, (6800.0, 4800.0)) and np.allclose(cable.end, (-1500.0, -1000.0))
    assert wire.length == pytest.approx(13800.0 - 8000.0 + 150.0 * np.pi / 2 + 7600.0 - 5250.0)


@pytest.fixture(scope="module")
def info(tmp_path_factory):
    folder = tmp_path_factory.mktemp("moving")
    return step_reader.read_step(STEP, str(folder), "normal")


def test_the_importer_reads_the_names_colours_and_tree(info):
    nodes = info["nodes"]
    parts = [n for n in nodes if n["kind"] == "part"]
    assert sorted(n["name"] for n in parts) == sorted(maker.PARTS)
    assert sorted(n["name"] for n in nodes if n["kind"] == "assembly") == sorted(maker.ASSEMBLIES)
    for n in parts:
        assert n["color"] is not None, (n["name"], "has no colour")
        assert np.allclose(n["color"], maker.COLOURS[n["name"]], atol=2e-3), n["name"]
    lower = {n["name"] for n in parts if nodes[n["parent"]]["name"] == "LOWER.ASM"}
    assert lower == {"BLOCK", "SHEAVE", "CLAMP"}
