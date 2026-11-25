"""Task 0320: copies take their welds along (0293's Copy / Paste), the weld symbols' switch, the symbols in renders
and the weld list – on the invented test weldment (``tools/make_test_weldment.py``)."""

import os

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

HERE = os.path.dirname(__file__)
WELDMENT = os.path.join(HERE, "data", "test_weldment.step")

import fresing_render  # noqa: E402
from fresing_render.blender import build, callouts, copy, reimport, weld_symbols, welds  # noqa: E402
from fresing_render.core import weld_symbols as core_symbols  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture()
def scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    assert bpy.ops.fresing.import_step(filepath=WELDMENT, quality="draft") == {"FINISHED"}
    sc = bpy.context.scene
    welds.set_up_test_model(sc)
    return sc


def root(sc):
    return build.model_roots(sc)[0]


def beads_of(it):
    return [o for o in welds.objects_of(it) if o.get(build.PROP_KIND) == welds.KIND]


def centre(ob):
    bpy.context.view_layer.update()
    m = ob.matrix_world
    pts = np.array([tuple(m @ Vector(c)) for c in ob.bound_box])
    return pts.mean(axis=0)


def test_a_whole_model_copy_takes_every_weld(scene):
    sc = scene
    n = welds.count(sc)
    before = {it.key: centre(beads_of(it)[0]) for it in welds.items(sc)}
    p = copy.paste(sc, [root(sc)])
    assert p["welds"] == n and any(f"{n} welds" in line for line in copy.summary(p))
    assert welds.count(sc) == 2 * n
    top = bpy.data.objects[p["roots"][0]]
    move = top.matrix_world.translation - root(sc).matrix_world.translation
    originals = {o.name for o in build.iter_parts(sc) if build.model_root_of(o) is root(sc)}
    for it, src in zip(list(welds.items(sc))[n:], list(welds.items(sc))[:n]):
        assert it.name == src.name + " (2)" and it.key != src.key
        assert it.part_a.name not in originals and it.part_b.name not in originals
        assert build.model_root_of(it.part_a) is top and build.model_root_of(it.part_b) is top
        assert [s.enabled for s in it.seams] == [s.enabled for s in src.seams]
        assert (it.size, it.finish, it.metal, it.rust) == (src.size, src.finish, src.metal, src.rust)
        obs = welds.objects_of(it)
        assert len(obs) == 2 and all(o.parent is it.part_a for o in obs)
        # the copied bead lies where the copy stands: the original's bead moved as the copy was
        assert np.allclose(centre(beads_of(it)[0]), before[src.key] + np.array(move), atol=1e-4)
        assert not it.lost


def test_a_parts_copy_leaves_out_welds_with_one_part_outside(scene):
    sc = scene
    parts = [welds.part_named(sc, n) for n in ("BASE PLATE", "FIN", "GUSSET")]
    p = copy.paste(sc, parts)
    assert p["welds"] == 3                       # plate–fin, plate–gusset, fin–gusset
    left = [line for line in p["left"] if line.startswith("Weld ")]
    assert len(left) == 3 and any("'POST' is outside the copy" in line for line in left)
    assert any("Weld 'BASE PLATE – POST'" in line for line in copy.summary(p)[1:])
    assert welds.count(sc) == 7 + 3


def test_a_failed_paste_takes_its_welds_back(scene, monkeypatch):
    sc = scene
    n, objs = welds.count(sc), set(bpy.data.objects.keys())

    def boom(*_a, **_k):
        raise RuntimeError("test")
    monkeypatch.setattr(copy, "_tidy", boom)
    with pytest.raises(RuntimeError):
        copy.paste(sc, [root(sc)])
    assert welds.count(sc) == n and set(bpy.data.objects.keys()) == objs


def test_a_model_update_of_the_original_updates_the_copys_welds(scene):
    sc = scene
    n = welds.count(sc)
    copy.paste(sc, [root(sc)])
    r = root(sc)
    out = reimport.update_model(bpy.context, r, r["fr_cache"])
    assert any("updated too" in line for line in out["notes"]), out["notes"]
    assert welds.count(sc) == 2 * n
    assert all(not it.lost and len(welds.objects_of(it)) == 2 for it in welds.items(sc))
    parts = set(build.iter_parts(sc))
    assert all(it.part_a in parts and it.part_b in parts for it in welds.items(sc))


def test_a_model_update_leaves_another_models_welds_alone(scene):
    """Found in 0320: 0319's carry-over marked every weld that was not on the updated model 'lost' – here a frozen
    parts copy (a model of its own) lost its welds when the original was updated."""
    sc = scene
    copy.paste(sc, [welds.part_named(sc, n) for n in ("BASE PLATE", "FIN")])
    mine = [it.key for it in welds.items(sc) if it.name.endswith("(2)")]
    assert len(mine) == 1
    r = root(sc)
    reimport.update_model(bpy.context, r, r["fr_cache"])
    it = welds.find_item(sc, mine[0])
    assert not it.lost and len(welds.objects_of(it)) == 2 and it.note == ""
    assert all(not w.lost for w in welds.items(sc))


def test_copied_welds_are_saved(scene, tmp_path):
    sc = scene
    copy.paste(sc, [root(sc)])
    path = str(tmp_path / "copy.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    assert welds.count(sc) == 14 and sum(it.name.endswith("(2)") for it in welds.items(sc)) == 7
    it = welds.items(sc)[8]
    it.size = 0.006                                # rebuilt from the kept seams on the copied parts
    assert not it.lost and len(welds.objects_of(it)) == 2


def test_symbols_off_by_default_and_saved(scene, tmp_path):
    sc = scene
    s = welds.settings(sc)
    assert not s.symbols and not s.symbols_render
    assert not weld_symbols.on(sc) and not weld_symbols.in_renders(sc)
    s.symbols = True
    assert weld_symbols.on(sc) and not weld_symbols.in_renders(sc)
    path = str(tmp_path / "symbols.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    assert welds.settings(bpy.context.scene).symbols


def test_the_test_welds_symbols(scene):
    texts = [core_symbols.one_line(weld_symbols.symbol_of(it, i + 1)) for i, it in enumerate(welds.items(scene))]
    assert texts[0] == "a5 ◺/◸ 200 < 135"             # the fin: fillets on both sides, steel MAG
    assert texts[3].startswith("○ ") and texts[3].endswith("< 141")       # the stainless post, all round, TIG
    assert texts[5].startswith("○ ") and texts[5].endswith("< 131")       # the aluminium saddle, MIG
    assert texts[6] == "‾V/Λ 300 < 135"               # the ground-flush butt from both faces (12 mm plate: V)
    it = welds.items(scene)[0]
    it.intermittent, it.length, it.pitch = True, 0.04, 0.09
    assert weld_symbols.symbol_of(it, 1).length == "2 × 40 (50)"


def test_symbols_in_renders_only_when_ticked(scene):
    sc = scene
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.matrix_world = Matrix.LocRotScale(Vector((0.2, -0.9, 0.7)), (Vector((0.2, -0.9, 0.7)) - Vector((0.2, 0.15, 0.0)))
                                          .to_track_quat("Z", "Y"), None)
    sc.render.resolution_x, sc.render.resolution_y = 800, 600
    sc.fresing.callouts_on = True
    size = callouts.picture_size(sc)
    assert callouts.draws_at(sc, size) == [] and not callouts.any_labels(sc)
    s = welds.settings(sc)
    s.symbols = True
    assert callouts.draws_at(sc, size) == []           # in the view only
    s.symbols_render = True
    assert callouts.any_labels(sc)
    draws = callouts.draws_at(sc, size)
    assert 5 <= len(draws) <= 7 and any(d.text.startswith("1  a5 ◺ 200") for d in draws)
    welds.items(sc)[0].hidden = True                   # a hidden weld has no symbol
    assert not any(d.text.startswith("1  ") for d in callouts.draws_at(sc, size))
    sc.fresing.callouts_on = False                     # labels off: the weld symbols still come (their own tick)
    assert callouts.draws_at(sc, size)


def test_the_weld_list_and_csv(scene, tmp_path):
    sc = scene
    rows = core_symbols.table(weld_symbols.all_data(sc))
    assert rows[0] == list(core_symbols.COLUMNS) and len(rows) == 8
    assert rows[1][:5] == ["1", "BASE PLATE – FIN", "BASE PLATE", "FIN", "Fillet, both sides"]
    assert rows[4][4] == "Fillet, both sides, all round" and rows[5][4] == "Fillet, all round"
    assert rows[7][4] == "Double-V butt"
    path = weld_symbols.export_csv(sc, str(tmp_path / "list"))
    assert path.endswith(".csv") and open(path, encoding="utf-8-sig").read().count("\n") == 8
    assert bpy.ops.fresing.weld_list_csv(filepath=str(tmp_path / "b.csv")) == {"FINISHED"}
    assert os.path.isfile(tmp_path / "b.csv")
    assert bpy.ops.fresing.weld_list.poll()
