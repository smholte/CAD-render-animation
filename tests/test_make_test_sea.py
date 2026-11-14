"""Task 0081: the stern-horn test model (tools/make_test_sea.py -> tests/data/test_sea.step, copy in the extension)."""
import os
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import make_test_sea as maker  # noqa: E402
from fresing_render.importer import step_reader  # noqa: E402

STEP = os.path.join(HERE, "data", "test_sea.step")
N = maker.NUMBERS


def test_the_shipped_copy_is_the_test_data():
    with open(os.path.join(ROOT, "fresing_render", "data", "test_sea.step"), "rb") as a, open(STEP, "rb") as b:
        assert a.read() == b.read(), "copy tests/data/test_sea.step to fresing_render/data/"
    assert os.path.getsize(STEP) < 400 * 1024


def test_the_maker_checks_itself():
    root = maker.model()
    maker.check(root, say=lambda *_: None)
    assert maker.count_parts(root) == len(maker.PARTS) == 20


def test_the_numbers():
    assert N["horn_centre"] == (500.0, 0.0, 1200.0) and N["bend_radius"] == 2000.0
    assert N["cable_diameter"] == 120.0 and N["vertical"] == (-1500.0, 0.0, 1200.0)
    assert [r[0] for r in N["rollers"]] == [7000.0, 5000.0, 3000.0]
    assert [v[0] for v in N["vertebrae"]] == [4000.0, 4410.0, 4820.0, 5230.0, 5640.0, 6050.0]
    assert N["cps_tube"] == (6460.0, 1500.0)
    assert maker.ROLLER_Z == pytest.approx(3039.8)


@pytest.fixture(scope="module")
def info(tmp_path_factory):
    folder = tmp_path_factory.mktemp("sea")
    return step_reader.read_step(STEP, str(folder), "normal")


def test_the_importer_reads_the_names_colours_and_tree(info):
    nodes = info["nodes"]
    parts = [n for n in nodes if n["kind"] == "part"]
    assert sorted(n["name"] for n in parts) == sorted(maker.PARTS)
    assert sorted(n["name"] for n in nodes if n["kind"] == "assembly") == sorted(maker.ASSEMBLIES)
    for n in parts:
        assert n["color"] is not None, (n["name"], "has no colour")
        assert np.allclose(n["color"], maker.COLOURS[n["name"]], atol=2e-3), n["name"]
    cps = {n["name"] for n in parts if nodes[n["parent"]]["name"] == "CPS SET"}
    assert cps == {"VERTEBRA", "CPS TUBE", "CPS CHOCK"}
