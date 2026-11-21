"""Task 0234: the workboat test model (tools/make_test_thrusters.py -> tests/data/test_thrusters.step, copy in the
extension; task 0154 made it, 0234 gave it a hull shape). The hull itself: tests/test_workboat_hull.py."""
import os
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import make_test_thrusters as maker  # noqa: E402
from fresing_render.importer import step_reader  # noqa: E402

STEP = os.path.join(HERE, "data", "test_thrusters.step")
PARTS = ["HULL", "WHEELHOUSE"] + ["THRUSTER HOUSING", "THRUSTER POD", "THRUSTER NOZZLE", "PROPELLER"] * 2 + [
    "TUNNEL LINING", "PROPELLER"]
ASSEMBLIES = ["TEST.THRUSTERS", "AZIMUTH PS", "AZIMUTH SB", "STEERING UNIT", "STEERING UNIT", "BOW THRUSTER"]


def test_the_shipped_copy_is_the_test_data():
    with open(os.path.join(ROOT, "fresing_render", "data", "test_thrusters.step"), "rb") as a, open(STEP, "rb") as b:
        assert a.read() == b.read(), "copy tests/data/test_thrusters.step to fresing_render/data/"
    assert os.path.getsize(STEP) < 400 * 1024


@pytest.fixture(scope="module")
def info(tmp_path_factory):
    return step_reader.read_step(STEP, str(tmp_path_factory.mktemp("thrusters")), "normal")


def test_the_importer_reads_the_names_colours_and_tree(info):
    nodes = info["nodes"]
    parts = [n for n in nodes if n["kind"] == "part"]
    assert sorted(n["name"] for n in parts) == sorted(PARTS)
    assert sorted(n["name"] for n in nodes if n["kind"] == "assembly") == sorted(ASSEMBLIES)
    colour = {"HULL": maker.HULL_BLUE, "WHEELHOUSE": maker.WHITE, "PROPELLER": maker.BRONZE}
    for n in parts:
        assert n["color"] is not None, n["name"]
        assert np.allclose(n["color"], colour.get(n["name"], maker.RED), atol=2e-3), n["name"]
