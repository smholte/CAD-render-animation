"""Task 0231: the lifting-loads test model (tools/make_test_loads.py -> tests/data/test_loads.step, copy in the
extension): real sizes, named lift points, the importer reads its tree and colours."""
import os
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import make_test_loads as maker  # noqa: E402
from fresing_render.importer import step_reader  # noqa: E402

STEP = os.path.join(HERE, "data", "test_loads.step")
N = maker.NUMBERS


def test_the_shipped_copy_is_the_test_data():
    with open(os.path.join(ROOT, "fresing_render", "data", "test_loads.step"), "rb") as a, open(STEP, "rb") as b:
        assert a.read() == b.read(), "copy tests/data/test_loads.step to fresing_render/data/"
    assert os.path.getsize(STEP) < 2500 * 1024


def test_the_maker_checks_itself():
    root = maker.model()
    maker.check(root, say=lambda *_: None)
    assert len(maker.placed(root)) == len(maker.PARTS) == 27


def test_the_numbers_are_real_sizes_for_their_equipment():
    assert N["ibc_size"][0] == 1200.0 and N["ibc_size"][1] == 1000.0 and N["ibc_size"][2] == 1150.0
    assert N["container_size"] == (6058.0, 2438.0, 2591.0)           # a 20 ft ISO container
    assert N["skid_size"][0] == 4000.0 and N["skid_size"][1] == 2000.0
    assert N["ibc_mass_t"] < N["skid_mass_t"] < N["container_mass_t"]
    assert (N["ibc_mass_t"], N["skid_mass_t"], N["container_mass_t"]) == (1.1, 6.0, 18.0)
    assert N["padeyes"] == N["ibc_eyes"] == N["top_castings"] == 4


@pytest.fixture(scope="module")
def info(tmp_path_factory):
    folder = tmp_path_factory.mktemp("loads")
    return step_reader.read_step(STEP, str(folder), "normal")


def test_the_importer_reads_the_names_colours_and_tree(info):
    nodes = info["nodes"]
    parts = [n for n in nodes if n["kind"] == "part"]
    assert sorted(n["name"] for n in parts) == sorted(maker.PARTS)
    assert sorted(n["name"] for n in nodes if n["kind"] == "assembly") == sorted(maker.ASSEMBLIES)
    for n in parts:
        assert n["color"] is not None, (n["name"], "has no colour")
        assert np.allclose(n["color"], maker.COLOURS[n["name"]], atol=2e-3), n["name"]


def test_every_load_has_its_named_lift_points(info):
    nodes = info["nodes"]
    parent = {n["name"]: nodes[n["parent"]]["name"] for n in nodes if n["kind"] == "part"}
    names = [n["name"] for n in nodes if n["kind"] == "part"]
    assert names.count("PADEYE") == 4 and parent["PADEYE"] == "PUMP SKID.ASM"
    assert names.count("LIFTING EYE") == 4 and parent["LIFTING EYE"] == "IBC ON PALLET.ASM"
    assert names.count("CORNER CASTING TOP") == 4 and parent["CORNER CASTING TOP"] == "20 FT CONTAINER.ASM"


def test_the_pump_and_motor_stand_off_the_middle_of_the_skid():
    """The skid's CoG is not in the middle of its frame: the pump and motor sit at y +350 (the tour's CoG close-up
    shows the symbol off the middle)."""
    from OCP.GProp import GProp_GProps
    from OCP.BRepGProp import BRepGProp
    mid = 0.0
    total = 0.0
    for name, _p, shape in maker.placed(maker.model()):
        if name in ("MOTOR", "PUMP"):
            pr = GProp_GProps()
            BRepGProp.VolumeProperties_s(shape, pr)
            mid += pr.Mass() * pr.CentreOfMass().Y()
            total += pr.Mass()
    assert mid / total == pytest.approx(350.0, abs=5.0)
