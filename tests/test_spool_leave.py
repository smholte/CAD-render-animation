"""Task 0184: the test tour's spool stop failed on AMD EPYC 7763 runners only ("Cable 'Power cable' no longer touches
'GUIDE SHEAVE' at frame 233").

Cause: the test carousel's GUIDE SHEAVE touches the coil, so in the CAD path the straight from the coil to the sheave is
a fraction of a millimetre long or nothing. ``spool._leave_cad`` took the cable's leave direction from that straight;
its direction is rounding noise. On those runners it pointed outwards and a little sideways, the carousel was read as
wound the other way (hand +1), its turn, the arm and every leave point came out mirrored, and at frame 233 the cable
could no longer reach the sheave. Now the direction comes from the coil's own arc (``spool.leave_direction``).

Here the set-up is run with that straight given a hair's length pointing outwards and a little to either side (as on
those runners): the hand must stay -1 and the stop's Build must give no warning. Blender as a Python module."""

import os

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import animation, paths, spool  # noqa: E402

HERE = os.path.dirname(__file__)
MODEL = os.path.join(HERE, "data", "test_spool.step")


@pytest.fixture(scope="module")
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.mark.parametrize("side", [0.01, -0.01])
def test_carousel_read_the_same_whatever_the_noise_of_a_touching_guide(addon, tmp_path, monkeypatch, side):
    real = paths._cad_path

    def noisy(scene, item, memo):
        line, s, res = real(scene, item, memo)
        if item.name == "Power cable" and item.a_kind != "SPOOL" and len(line) and len(res.get("first", ())):
            line = np.array(line, dtype=float)
            i0 = int(res["first"][0]) + int(res["counts"][0]) - 1
            hair = np.array([1.0, side, 0.0])                  # outwards (+x at the leave point) and a bit sideways
            line[i0 + 1] = line[i0] + 1e-6 * hair / np.linalg.norm(hair)
        return line, s, res

    monkeypatch.setattr(paths, "_cad_path", noisy)
    bpy.ops.wm.read_homefile(use_empty=True)
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path)
    assert bpy.ops.fresing.import_step(filepath=MODEL, quality="normal") == {"FINISHED"}
    made = spool.set_up_test_model(sc)
    car = spool.find(sc, "Carousel")
    assert car is not None and not car.problem, car.problem if car else None
    assert int(car.hand) == -1
    assert int(spool.find(sc, "Drum").hand) == 1
    spool.add_full_range_steps(sc, made["animation"])
    r = animation.bake(sc, sc.fresing.animations[made["animation"]])
    assert r["warnings"] == []
