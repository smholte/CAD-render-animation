"""Task 0119 (bug hunt 0118, rows 2, 3, 7, 17): a model update keeps drums, carousels, riders and tracks.

Blender as a Python module. Rows 3, 7 and 17 call the update hooks of the module under test with the lookup tables
a real update hands them (``by_uid``: old part ID -> new part, ``mapping``: old ID -> new ID or ``"gone:<id>"``)."""

import os
import sys

import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))

import fresing_render  # noqa: E402
from fresing_render.blender import build, paths, paths_riders, paths_sea, spool, tracks  # noqa: E402

DATA = os.path.join(HERE, "data")


@pytest.fixture()
def fresh(tmp_path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    paths.forget()
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path)
    yield sc
    fresing_render.unregister()


def _import(sc, name, **kw):
    assert bpy.ops.fresing.import_step(filepath=os.path.join(DATA, name), quality="draft", **kw) == {"FINISHED"}
    bpy.context.view_layer.update()


def _uid(ob):
    return ob.get(build.PROP_UID)


def test_updating_another_model_keeps_the_drums(fresh):
    sc = fresh
    _import(sc, "test_spool.step")
    spool.set_up_test_model(sc)
    before = {sp.name: (sp.enabled, sp.part_uid) for sp in sc.fresing.spools}
    assert paths.find(sc, "Wire").a_kind == "SPOOL"
    roots = set(build.model_roots(sc))
    _import(sc, "test_crane_a.step")
    crane = next(r for r in build.model_roots(sc) if r not in roots)
    _import(sc, "test_crane_b.step", update_root=crane.name)
    bpy.context.view_layer.update()
    assert {sp.name: (sp.enabled, sp.part_uid) for sp in sc.fresing.spools} == before
    for cable in ("Wire", "Power cable"):
        assert paths.find(sc, cable).a_kind == "SPOOL", cable
    assert all(spool.find(sc, n).enabled and not spool.find(sc, n).problem for n in ("Drum", "Carousel"))


def test_a_drum_whose_id_changed_is_found_again_next_time(fresh):
    sc = fresh
    _import(sc, "test_spool.step")
    spool.set_up_test_model(sc)
    sp = spool.find(sc, "Drum")
    ob, old = sp.part, sp.part_uid
    ob[build.PROP_UID] = "renamed-drum"
    assert spool.after_model_update(sc, {}, {old: "renamed-drum"}) == []
    sp = spool.find(sc, "Drum")
    assert sp.part_uid == "renamed-drum" and sp.enabled
    notes = spool.after_model_update(sc, {}, {"renamed-drum": "renamed-drum"})     # the second update
    assert notes == [] and spool.find(sc, "Drum").enabled and spool.find(sc, "Drum").part == ob


def test_a_rider_part_that_is_gone_is_dropped_with_a_note(fresh):
    sc = fresh
    _import(sc, "test_sea.step")
    paths_sea.set_up_test_model(sc)
    it = paths.find(sc, paths_sea.TEST_CABLE)
    r = it.riders[0]
    uids = [p.part_uid for p in r.parts]
    n = len(uids)
    assert n >= 3
    gone = uids[:2]
    mapping = {u: ("gone:" + u if u in gone else u) for u in uids}
    by_uid = {u: next(o for o in sc.objects if _uid(o) == u) for u in uids if u not in gone}
    notes = paths_riders.after_model_update(sc, by_uid, mapping)
    r = paths.find(sc, paths_sea.TEST_CABLE).riders[0]
    assert len(r.parts) == n - 2 and all(p.part is not None for p in r.parts)
    assert any("2 of its parts are gone" in t for t in notes), notes
    # a part of another model (in neither table) stays
    other = [p.part_uid for p in r.parts][0]
    notes = paths_riders.after_model_update(sc, {}, {})
    assert len(paths.find(sc, paths_sea.TEST_CABLE).riders[0].parts) == n - 2 and notes == []
    assert other


def test_a_track_keeps_its_coupled_wheel_and_says_what_is_gone(fresh):
    sc = fresh
    _import(sc, "test_tracks.step")
    tracks.set_up_test_model(sc)
    it = tracks.find(sc, "Bottom track")
    coupled = [w.part_uid for w in it.wheels if w.coupled][:1]
    n_coupled = len([w for w in it.wheels if w.coupled])
    assert coupled, "the test track has a coupled wheel"
    riders = [u for u in it.rider_uids.split("\n") if u]
    assert riders
    new_id = "new-" + coupled[0]
    wheel = next(o for o in sc.objects if _uid(o) == coupled[0])
    wheel[build.PROP_UID] = new_id
    keep = {u: next(o for o in sc.objects if _uid(o) == u) for u in
            [w.part_uid for w in it.wheels if w.part_uid != coupled[0]] + [it.chain_uid] + riders[1:]}
    by_uid = dict(keep)
    by_uid[coupled[0]] = wheel
    mapping = {u: u for u in by_uid}
    mapping[coupled[0]] = new_id
    mapping[riders[0]] = "gone:" + riders[0]
    by_uid.pop(riders[0], None)
    notes = tracks.after_model_update(sc, by_uid, mapping)
    it = tracks.find(sc, "Bottom track")
    assert it is not None and any("gone in the new revision" in t and "Bottom track" in t for t in notes), notes
    assert new_id in [w.part_uid for w in it.wheels if w.coupled]
    assert len([w for w in it.wheels if w.coupled]) == n_coupled
