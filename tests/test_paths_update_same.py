"""Task 0192 (bug hunt 6 row 1): a model update to the SAME file changes nothing in a cable's route (``paths.read_cad``
with ``update=True`` from ``paths.after_model_update``; ``_merge`` / ``removed_of`` / ``_ends``).

- a contact read from the CAD that the user took off the list stays off (before: test_paths_a, CHUTE taken off
  "Wire rope", update with the same file -> CHUTE back, 6.490 -> 6.645 m); "From CAD cable again" still brings it back;
- a CAD-pose wrap set by hand (``wrap_user``, the demo's top pulley) is kept (before: worked out again from the CAD
  pose, by the reading and by a drum's start taken again).

The demo's case (its tipping wires' ends, the A&R wire's top pulley) is ``tests/test_demo_project_update.py``.
"""

import os
import sys

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

HERE = os.path.dirname(__file__)
MODEL_A = os.path.join(HERE, "data", "test_paths_a.step")
MODEL_B = os.path.join(HERE, "data", "test_paths_b.step")      # revision B: the same cable, a guard in another order
sys.path.insert(0, os.path.dirname(HERE))

import fresing_render  # noqa: E402
from fresing_render.blender import build, flex, paths  # noqa: E402

CABLE = "Wire rope"


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture(scope="module")
def folder(tmp_path_factory):
    return str(tmp_path_factory.mktemp("paths_same"))


@pytest.fixture()
def rope(folder):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    flex.forget()
    paths.forget()
    sc = bpy.context.scene
    sc.fresing.out_folder = folder
    assert bpy.ops.fresing.import_step(filepath=MODEL_A, quality="draft") == {"FINISHED"}
    paths.set_up_test_model(sc)
    return sc


def _update_same(sc, path=MODEL_A):
    root = next(r for r in build.model_roots(sc))
    assert bpy.ops.fresing.import_step(filepath=path, quality="draft", update_root=root.name) == {"FINISHED"}
    for _ in range(2):
        bpy.context.view_layer.update()
    return paths.find(sc, CABLE)


def _length(sc, it) -> float:
    shape = paths.shape_now(sc, it)
    return float(np.linalg.norm(np.diff(shape, axis=0), axis=1).sum())


@pytest.mark.parametrize("path", [MODEL_A, MODEL_B], ids=["same file", "revision B (read again)"])
def test_a_contact_taken_off_stays_off_after_an_update(rope, path):
    sc = rope
    it = paths.find(sc, CABLE)
    k = next(i for i, c in enumerate(it.contacts) if c.name == "CHUTE")
    paths.remove_contact(sc, it, k)
    it = paths.find(sc, CABLE)
    names = [c.name for c in it.contacts]
    assert "CHUTE" not in names
    length = _length(sc, it)
    ends = [(it.a_kind, it.b_kind, it.b_free_end)]
    it = _update_same(sc, path)
    assert [c.name for c in it.contacts] == names, [c.name for c in it.contacts]      # (before: CHUTE back)
    assert abs(_length(sc, it) - length) < (1e-4 if path == MODEL_A else 0.01), (_length(sc, it), length)   # (before:
    #                                                                          6.490 -> 6.645 m)
    assert [(it.a_kind, it.b_kind, it.b_free_end)] == ends
    assert [r["name"] for r in paths.removed_of(it)] == ["CHUTE"]
    # "From CAD cable again" (the button) brings it back, as its tooltip says
    paths.read_cad(sc, it, it.part)
    it = paths.find(sc, CABLE)
    assert "CHUTE" in [c.name for c in it.contacts] and not paths.removed_of(it)


@pytest.mark.parametrize("path", [MODEL_A, MODEL_B], ids=["same file", "revision B (read again)"])
def test_a_wrap_set_by_hand_is_kept_through_an_update(rope, path):
    sc = rope
    it = paths.find(sc, CABLE)
    k = next(i for i, c in enumerate(it.contacts) if c.name == "SHEAVE 2")
    paths.flip_contact(sc, it, k)               # (a contact the user changed: flipped twice, as it was)
    paths.flip_contact(sc, paths.find(sc, CABLE), k)
    it = paths.find(sc, CABLE)
    c = it.contacts[k]
    assert c.user and c.wrap_cad > 0.1
    c.wrap_cad = 0.05                           # (as the demo sets its top pulley's: drawn not quite touching)
    c.wrap_user = True
    wraps = [round(float(x.wrap_cad), 6) for x in it.contacts if x.kind in paths.SHAPING]
    it = _update_same(sc, path)
    assert [round(float(x.wrap_cad), 6) for x in it.contacts if x.kind in paths.SHAPING] == wraps   # (before: 0.05 lost)


def _spy_kept(monkeypatch):
    got = []
    real = paths.cable_kept
    monkeypatch.setattr(paths, "cable_kept", lambda *a: got.append(real(*a)) or got[-1])
    return got


def test_a_cable_whose_own_part_changed_is_read_again(rope, monkeypatch):
    """Task 0216 (bug hunt 7 row 8): a cable keeps its route through an update that changed other parts only; one
    whose own parts changed is read again."""
    sc = rope
    it = paths.find(sc, CABLE)
    own = it.part_uid
    real = paths.before_model_update

    def before(scene, r):                     # the cable's own CAD part was another shape before
        real(scene, r)
        paths._STATE["model_sig"][1][own] = ("another shape",)
    monkeypatch.setattr(paths, "before_model_update", before)
    got = _spy_kept(monkeypatch)
    _update_same(sc)
    assert got and not any(got)


def test_a_revision_with_a_part_changed_beside_the_cable_reads_it_again(rope, monkeypatch):
    """Revision B moves a guard next to the rope: within ``paths.ROOM`` of it, so the rope is read again."""
    got = _spy_kept(monkeypatch)
    _update_same(rope, MODEL_B)
    assert got and not any(got)


def test_kept_when_only_a_far_part_changed(rope, monkeypatch):
    sc = rope
    it = paths.find(sc, CABLE)
    want = (float(it.length), [(c.name, round(float(c.wrap_cad), 6)) for c in it.contacts])
    root = next(r for r in build.model_roots(sc))
    far = None
    for ob in build.iter_parts(sc):
        uid = ob.get(build.PROP_UID)
        if uid and uid != it.part_uid and uid not in paths._depends_on(sc, it):
            far = uid
            break
    assert far is not None
    real = paths.before_model_update

    def before(scene, r):
        real(scene, r)
        paths._STATE["model_sig"][1][far] = ("another shape",)
        held = paths._STATE["held"][CABLE]
        held["points"] = held["points"] + np.array([0.0, 0.0, 1000.0])   # (the rope far from every part)
    monkeypatch.setattr(paths, "before_model_update", before)
    got = _spy_kept(monkeypatch)
    it = _update_same(sc)
    assert got and all(got) and root is not None
    assert float(it.length) == pytest.approx(want[0], abs=1e-5)
    assert [(c.name, round(float(c.wrap_cad), 6)) for c in it.contacts] == want[1]
