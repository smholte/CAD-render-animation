"""Task 0263: the cable paths test model's winch (tests/data/test_paths_a.step, ``paths.set_up_test_model(winch=True)``).

The winch drum holds wire (WIRE ON DRUM: two full layers) and the rope comes off it: with ``winch=True`` the drum is a
winch drum of 4 Motion > Drums and carousels, so the rope starts on it and winds off and on layer by layer. Expected
values are worked out from the maker's geometry (tools/make_test_paths.py): the first layer's middle is the barrel's
radius + the rope's (200 + 12), the flanges' inner faces are 300 apart, a layer is (300 - 24) / 25.44 = 10.85 turns
(the app's pitch for a drum without a groove: 1.06 rope diameters), each layer 24 x cos 30° further out; the rope comes off at r 256.785, which is the app's layer 3 (253.569, the nearest).
"""

import math
import os
import sys

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")

import addon_utils  # noqa: E402

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))

import make_test_paths as maker  # noqa: E402
from fresing_render.blender import animation, build, flex, joints, paths, spool  # noqa: E402

MODEL_A = os.path.join(HERE, "data", "test_paths_a.step")
W = maker.NUMBERS["winch"]
MM = 0.001


@pytest.fixture(scope="module", autouse=True)
def addon():
    import fresing_render
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture(scope="module")
def folder(tmp_path_factory):
    return str(tmp_path_factory.mktemp("paths_winch"))


@pytest.fixture()
def winch(folder):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    flex.forget()
    paths.forget()
    sc = bpy.context.scene
    sc.fresing.out_folder = folder
    assert bpy.ops.fresing.import_step(filepath=MODEL_A, quality="draft") == {"FINISHED"}
    made = paths.set_up_test_model(sc, winch=True)
    return sc, made


def _ob(sc, name):
    return next(o for o in sc.objects if o.get(build.PROP_NAME) == name)


def test_the_rope_starts_on_the_winch_drum(winch):
    sc, made = winch
    assert made["spool"] == paths.TEST_DRUM and made["joints"] == ["Luff", "Drum turn", "Cable Wire rope"]
    it = paths.find(sc, made["cable"])
    sp = spool.find(sc, paths.TEST_DRUM)
    assert sp is not None and sp.kind == "DRUM" and not sp.problem and spool.of_cable(sc, it) == sp
    assert it.a_kind == "SPOOL" and [c.name for c in it.contacts] == ["SHEAVE 1", "SHEAVE 2", "V ROLLER", "V ROLLER",
                                                                       "CHUTE"]
    assert paths.status(sc, it)[1] == "OK" and spool.status(sc, sp)[1] == "CHECKMARK"
    assert sp.part == _ob(sc, "WINCH DRUM") and sp.coil == _ob(sc, "WIRE ON DRUM")
    # the drum read from the model: the first layer's middle, the flanges, how many layers fit under the flange's rim
    assert sp.r1 == pytest.approx(W["r1"] * MM, abs=0.5 * MM)
    assert (sp.a_lo, sp.a_hi) == pytest.approx((-0.150, 0.150), abs=0.5 * MM)
    assert sp.r_max == pytest.approx((W["flange_radius"] - W["d"] / 2) * MM, abs=0.5 * MM)
    # the drum turns with its wire: one joint for both
    j = joints.find(sc, sp.joint)
    assert j.name == "Drum turn" and joints.members(j) == [_ob(sc, "WINCH DRUM"), _ob(sc, "WIRE ON DRUM")]


def test_the_wire_on_it_and_its_layers(winch):
    """How much is on it: layers 1 and 2 full and layer 3 from the flange to the rope's middle at y = 0, at the pitch
    the app takes for a drum without a groove (1.06 d = 25.44 mm): 10.849 + 10.849 + 5.425 turns of a helix, plus the
    app's climb of a quarter turn from layer to layer (radius from one layer's middle to the next)."""
    sc, _made = winch
    sp = spool.find(sc, paths.TEST_DRUM)
    est = W["wound_estimate"]
    pitch, r = 1.06 * 24.0, [212.0 + k * 24 * math.cos(math.radians(30)) for k in range(3)]
    turns = [276.0 / pitch, 276.0 / pitch, 138.0 / pitch]
    want = [n * math.hypot(2 * math.pi * rk, pitch) for n, rk in zip(turns, r)]
    assert est["layers"] == pytest.approx(want, abs=1e-2) and est["total"] == pytest.approx(38968.0, abs=1.0)
    climbs = sum(0.5 * math.pi * 0.5 * (r[k] + r[k + 1]) for k in range(2))          # 731 mm
    assert float(sp.wound) == pytest.approx((est["total"] + climbs) * MM, abs=0.01)
    assert spool.status(sc, sp)[0].startswith(f"{float(sp.wound):.1f} m on it, layer 3 of 4")


def test_paying_out_turns_the_drum_as_far_as_its_layer_gives(winch):
    """1 m of rope off layer 3 (rope middle r 0.2536 m) turns the drum 1 / 0.2536 rad = 226°; built, the rope's start
    stays on the drum's layer and the sheaves turn with the rope."""
    sc, made = winch
    a = sc.fresing.animations[made["animation"]]
    animation.bake(sc, a)
    it = paths.find(sc, made["cable"])
    drum, cab = joints.find(sc, "Drum turn"), joints.find(sc, it.joint)
    sc.frame_set(sc.frame_start)
    d0, p0 = joints.get_value(drum), joints.get_value(cab)
    sc.frame_set(sc.frame_end)
    turned, pay = abs(joints.get_value(drum) - d0), joints.get_value(cab) - p0
    assert pay == pytest.approx(1.0, abs=0.01)
    assert math.degrees(turned) == pytest.approx(math.degrees(pay / 0.253569), abs=1.0)
    shape = np.asarray(paths.shape_now(sc, it), float)
    centre = np.array(W["axis_point"]) * MM
    r = np.hypot(shape[0, 0] - centre[0], shape[0, 2] - centre[2])
    assert r == pytest.approx(0.253569, abs=1 * MM)              # the rope leaves the drum from its 3rd layer
    animation.clear_keys(sc)
