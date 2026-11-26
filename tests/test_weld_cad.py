"""Task 0323: welds from the CAD file in Blender – the import makes them, the CAD bead's shape with the app's looks,
the app's bead instead, all at once, the weld list and symbols, copy, motion, model update, save + reopen, Back to the
CAD part, clash / web 3D / the Client view – on the CAD-weld frames of ``tools/make_test_weldment.py --cad``."""

import os
import sys

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from mathutils import Matrix  # noqa: E402

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
DATA = os.path.join(HERE, "data")
INVENTOR = os.path.join(DATA, "test_weldment_cad_inventor.step")
INVENTOR_B = os.path.join(DATA, "test_weldment_cad_inventor_b.step")
CREO = os.path.join(DATA, "test_weldment_cad_creo.step")
UNNAMED = os.path.join(DATA, "test_weldment_cad_unnamed.step")

import fresing_render  # noqa: E402
from fresing_render.blender import build, logic, weld_cad, weld_symbols, welds  # noqa: E402
from fresing_render.core import weld_symbols as core_symbols  # noqa: E402

import make_test_weldment as maker  # noqa: E402

SYMBOLS = ["○ a4 ◸ 189 < 135", "○ a4 ◸ 240 < 135", "Λ 300 < 135", "a4 ◸ 4 × 30 (20) < 135", "a5 ◸ 200 < 135",
           "a4 ◸ 80 < 135"]


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def fresh(path=INVENTOR):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    assert bpy.ops.fresing.import_step(filepath=path, quality="draft") == {"FINISHED"}
    return bpy.context.scene


@pytest.fixture()
def scene():
    return fresh()


def part(sc, name):
    return next(o for o in sc.objects if o.get(build.PROP_NAME) == name and o.get(build.PROP_KIND) == "part")


def beads(item):
    return [o for o in welds.objects_of(item) if o.get(build.PROP_KIND) == welds.KIND]


def heat(item):
    return [o for o in welds.objects_of(item) if o.get(build.PROP_KIND) == welds.HEAT_KIND]


def symbols(sc):
    return sorted(core_symbols.one_line(weld_symbols.symbol_of(it, i + 1)) for i, it in enumerate(welds.items(sc)))


def check_table(sc, table):
    rows = weld_cad.table(sc)
    assert len(rows) == len(table), rows
    want = sorted((kind, size, round(length, 0), closed, inter[0] if inter else 0) for _n, _a, _b, kind, size, length,
                  closed, inter in table)
    got = sorted((kind, size, round(length if inter is None else maker_len(inter), 0), closed, inter[0] if inter else 0)
                 for _name, kind, size, length, closed, inter in rows)
    for (k1, s1, l1, c1, n1), (k2, s2, l2, c2, n2) in zip(got, want):
        assert (k1, c1, n1) == (k2, c2, n2) and abs(s1 - s2) <= 0.5 and abs(l1 - l2) <= 1.0, (got, want)


def maker_len(inter):
    n, piece, pitch = inter
    return (n - 1) * pitch + piece


def test_the_import_makes_the_welds(scene):
    sc = scene
    check_table(sc, maker.CAD_WELDS)
    assert "6 welds from the CAD file" in sc.fresing.last_message
    src = part(sc, "Welds")
    assert src.get(weld_cad.SOURCE) and src.get(build.PROP_EXCLUDED) and src.hide_render
    for it in welds.items(sc):
        assert it.from_cad and it.cad_how == "name" and not it.lost
        assert len(beads(it)) == 1 and len(heat(it)) == 1
        assert beads(it)[0].parent == it.part_a
        assert it.part_a == part(sc, "BOTTOM PLATE")
        assert it.finish == "PAINTED"                    # the plate is painted (0319's rule)
        assert it.metal == "STEEL"                       # "Welded Steel Mild"
    assert symbols(sc) == sorted(SYMBOLS)
    # the look-alikes are parts as they were
    for name in maker.LOOK_ALIKES:
        assert not part(sc, name).get(build.PROP_EXCLUDED)


def test_creo_and_unnamed(tmp_path):
    sc = fresh(CREO)
    check_table(sc, maker.CAD_WELDS)
    assert all(it.metal == "AUTO" and it.cad_how == "name" for it in welds.items(sc))   # no material in the file
    assert len([o for o in sc.objects if o.get(weld_cad.SOURCE)]) == 6
    sc = fresh(UNNAMED)
    check_table(sc, maker.CAD_WELDS)
    assert "found 6 welds by their shape – check them" in sc.fresing.last_message
    assert all(it.cad_how == "shape" for it in welds.items(sc))
    assert "by its shape – check it" in weld_cad.describe(welds.items(sc)[0])
    for name in maker.LOOK_ALIKES:
        assert not part(sc, name).get(weld_cad.SOURCE)


def test_the_bead_is_the_cad_shape_with_the_looks(scene):
    sc = scene
    for it in welds.items(sc):
        ob = beads(it)[0]
        me = it.cad_mesh
        assert me is not None and len(ob.data.polygons) == len(me.polygons)
        uv = ob.data.uv_layers.get("fr_weld")
        assert uv is not None
        a = np.zeros(len(ob.data.loops) * 2, np.float32)
        uv.data.foreach_get("uv", a)
        a = a.reshape(-1, 2)
        assert a[:, 1].min() >= 0.0 and a[:, 1].max() <= 1.0 and a[:, 0].max() > 0.05
        assert ob.data.materials[0] is not None
    # the CAD bead lies where the welds body was: same points (in the first part's coordinates)
    src = part(sc, "Welds")
    p, _t, _f = welds.mesh_tables(src.data)
    pts = set(map(tuple, np.round(p * 1e5).astype(int)))
    for it in welds.items(sc):
        ob = beads(it)[0]
        co = np.array([tuple(ob.matrix_world @ v.co) for v in ob.data.vertices])
        assert {tuple(x) for x in np.round(co * 1e5).astype(int)} <= pts


def test_the_apps_bead_instead_and_back(scene):
    sc = scene
    it = next(it for it in welds.items(sc) if it.cad_kind == "FILLET" and it.cad_closed and len(it.seams) == 1)
    n_cad = len(beads(it)[0].data.polygons)
    assert bpy.ops.fresing.weld_cad_shape(key=it.key) == {"FINISHED"}
    it = welds.find_item(sc, it.key)
    assert not it.cad_shape and len(beads(it)[0].data.polygons) != n_cad
    def width(ob):
        co = np.array([v.co[:] for v in ob.data.vertices])
        return float(co[:, 0].max() - co[:, 0].min())
    it.size = 0.006                                       # the app's bead takes the size
    big = width(beads(it)[0])
    it.size = 0.003
    assert width(beads(it)[0]) < big - 0.003
    assert bpy.ops.fresing.weld_cad_shape(key=it.key) == {"FINISHED"}
    it = welds.find_item(sc, it.key)
    assert it.cad_shape and len(beads(it)[0].data.polygons) == n_cad


def test_all_at_once(scene):
    sc = scene
    assert bpy.ops.fresing.weld_cad_all(what="APP") == {"FINISHED"}
    assert not any(it.cad_shape for it in welds.items(sc))
    assert bpy.ops.fresing.weld_cad_all(what="BARE") == {"FINISHED"}
    assert all(it.finish == "AS_WELDED" for it in welds.items(sc))
    assert bpy.ops.fresing.weld_cad_all(what="PAINTED") == {"FINISHED"}
    assert all(it.finish == "PAINTED" and it.paint_from == "A" for it in welds.items(sc))
    assert bpy.ops.fresing.weld_cad_all(what="CAD") == {"FINISHED"}
    assert all(it.cad_shape for it in welds.items(sc))
    for it in welds.items(sc):
        assert len(beads(it)) == 1


def test_weld_list_csv(scene, tmp_path):
    path = weld_symbols.export_csv(scene, str(tmp_path / "list.csv"))
    with open(path, encoding="utf-8-sig") as fh:
        rows = [r for r in fh.read().splitlines() if r.strip()]
    assert len(rows) == 1 + 6


def test_copy_takes_the_cad_welds(scene):
    from fresing_render.blender import copy
    sc = scene
    root = build.model_roots(sc)[0]
    p = copy.paste(sc, [root])
    assert p["welds"] == 6
    its = list(welds.items(sc))
    assert len(its) == 12 and all(it.from_cad and len(beads(it)) == 1 for it in its)
    a, b = its[0], its[6]
    assert a.part_a != b.part_a and a.cad_mesh == b.cad_mesh
    welds.remove(sc, its[6])                              # the shared shape stays with the other weld
    assert welds.find_item(sc, a.key).cad_mesh is not None and len(beads(welds.find_item(sc, a.key))) == 1


def test_the_bead_moves_with_its_first_part(scene):
    sc = scene
    it = welds.items(sc)[0]
    ob = beads(it)[0]
    bpy.context.view_layer.update()
    before = np.array(ob.matrix_world)
    it.part_a.matrix_basis = Matrix.Translation((0.0, 0.0, 0.1)) @ it.part_a.matrix_basis
    bpy.context.view_layer.update()
    assert np.allclose(np.array(ob.matrix_world)[:3, 3] - before[:3, 3], (0, 0, 0.1), atol=1e-6)


def test_model_update_keeps_changes_says_lost_and_new(scene):
    sc = scene
    by_len = {round(r[3]): r[0] for r in weld_cad.table(sc)}
    rib = welds.find_item(sc, next(it.key for it in welds.items(sc) if it.name == by_len[200]))
    rib.name = "Rib foot"
    rib.finish = "GROUND"
    rib.rust = 0.4
    keep_key = rib.key
    root = build.model_roots(sc)[0]
    assert bpy.ops.fresing.import_step(filepath=INVENTOR_B, quality="draft", update_root=root.name) == {"FINISHED"}
    sc = bpy.context.scene
    rib = welds.find_item(sc, keep_key)
    assert rib is not None and rib.name == "Rib foot" and rib.finish == "GROUND" and abs(rib.rust - 0.4) < 1e-6
    assert abs(rib.cad_length - 0.150) < 0.001 and not rib.lost and len(beads(rib)) == 1
    lost = [it for it in welds.items(sc) if it.lost]
    assert len(lost) == 1 and "Weld lost in the new model" in lost[0].note and beads(lost[0]) == []
    assert len(welds.items(sc)) == 7                      # 6 – 0 + 1 new (the lost one stays listed)
    notes = [n.text for n in sc.fresing.report_notes]
    assert sum("lost in the new model" in n for n in notes) == 1
    assert sum(n.startswith("New weld from the CAD file") for n in notes) == 1
    assert sum("changed in the new model" in n for n in notes) == 1
    for ob in bpy.data.objects:                          # every bead rides on a part of the new model
        if welds.is_weld(ob):
            assert ob.parent is not None and ob.parent.name in sc.objects
    src = [o for o in sc.objects if o.get(weld_cad.SOURCE)]
    assert len(src) == 1 and src[0].get(build.PROP_EXCLUDED)


def test_save_and_reopen(scene, tmp_path):
    path = str(tmp_path / "cad welds ä.blend")
    n = {it.key: len(beads(it)[0].data.polygons) for it in welds.items(scene)}
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    for it in welds.items(sc):
        assert it.cad_mesh is not None
        it.rust = 0.2                                     # rebuilt after the load from what the project keeps
        assert len(beads(it)[0].data.polygons) == n[it.key]


def test_back_to_the_cad_part_and_find_again(scene):
    sc = scene
    assert bpy.ops.fresing.weld_cad_put_back() == {"FINISHED"}
    assert len(welds.items(sc)) == 0
    src = part(sc, "Welds")
    assert not src.get(build.PROP_EXCLUDED) and not src.hide_render
    assert not any(me.get("fr_weld_cad") for me in bpy.data.meshes)
    assert bpy.ops.fresing.weld_cad_find() == {"FINISHED"}
    assert len(welds.items(sc)) == 6 and part(sc, "Welds").get(build.PROP_EXCLUDED)
    assert bpy.ops.fresing.weld_cad_find() == {"FINISHED"}
    assert len(welds.items(sc)) == 6                      # beads already made are skipped


def test_show_all_excluded_keeps_the_welds_body_out(scene):
    logic.restore_excluded(scene)
    assert part(scene, "Welds").get(build.PROP_EXCLUDED)


def test_clash_web3d_and_client_view(scene):
    from fresing_render.blender import clash, lock, web3d
    objs = clash.objects(scene)
    assert objs and not any(welds.is_weld(o) for o in objs) and part(scene, "Welds") not in objs
    parts, _marks = web3d.objects(scene)
    for it in welds.items(scene):
        assert beads(it)[0] in parts and heat(it)[0] not in parts
    for op in ("fresing.weld_cad_find", "fresing.weld_cad_shape", "fresing.weld_cad_all",
               "fresing.weld_cad_put_back"):
        assert not lock.allowed(op)


def test_an_import_without_welds_says_nothing():
    sc = fresh(os.path.join(DATA, "test_weldment.step"))
    assert len(welds.items(sc)) == 0 and "from the CAD file" not in sc.fresing.last_message
    assert weld_cad.LAST["welds"] == 0


def test_placed_parts_in_a_grid(tmp_path):
    """The heavy frame's cells are placed by matrices: their welds are found where the parts stand (a new part has no
    world place until the scene is updated – the import updates it first)."""
    path = str(tmp_path / "grid.step")
    root, mats = maker.heavy_beads(4)
    maker.write_cad_step(root, path, mats)
    sc = fresh(path)
    rows = weld_cad.table(sc)
    assert len(rows) == 12, rows
    assert sorted({(r[1], r[2], round(r[3]), r[4]) for r in rows}) == [("FILLET", 3.0, 133, True),
                                                                      ("FILLET", 3.0, 150, False)]
    bpy.context.view_layer.update()
    cells = set()
    for it in welds.items(sc):                            # both parts of a weld in one cell (250 mm apart)
        a, b = it.part_a.matrix_world.translation, it.part_b.matrix_world.translation
        assert (a - b).length < 0.01
        cells.add((round(a.x, 2), round(a.y, 2)))
        bead = beads(it)[0]
        assert (bead.matrix_world.translation - a).length < 1e-6
    assert len(cells) == 4


# ---------------------------------------------------------------------------
# task 0368: the square groove with a root gap; the same welds with and without helper processes
# ---------------------------------------------------------------------------

GAP = os.path.join(DATA, "test_weldment_gap_inventor.step")
GAP_UNNAMED = os.path.join(DATA, "test_weldment_gap_unnamed.step")


@pytest.mark.parametrize("path,how", [(GAP, "name"), (GAP_UNNAMED, "shape")])
def test_square_groove_import(path, how):
    sc = fresh(path)
    its = list(welds.items(sc))
    assert len(its) == 1                                   # the flush filler bar is no weld
    it = its[0]
    assert it.from_cad and it.cad_how == how and it.cad_kind == "BUTT" and it.kind == "BUTT"
    assert it.butt_width == pytest.approx(0.007, abs=0.0005) and it.cad_gap == pytest.approx(0.003, abs=1e-4)
    assert "square groove, gap 3 mm" in weld_cad.describe(it)
    assert weld_symbols.symbol_of(it, 1).glyph == core_symbols.SQUARE_BUTT
    assert len(beads(it)) == 1 and len(heat(it)) == 1 and len(heat(it)[0].data.polygons) > 0
    weld_cad.set_shape(sc, welds.find_item(sc, it.key), False)          # the app's bead on its seam works too
    it = welds.find_item(sc, it.key)
    assert not it.lost and len(beads(it)[0].data.polygons) > 0


def _weld_meshes(sc):
    out = []
    for it in sorted(welds.items(sc), key=lambda x: x.name):
        for ob in sorted(welds.objects_of(it), key=lambda o: o.name):
            me = ob.data
            co = np.zeros(len(me.vertices) * 3)
            me.vertices.foreach_get("co", co)
            uv = np.zeros(len(me.loops) * 2)
            me.uv_layers[0].data.foreach_get("uv", uv)
            out.append((ob.name, co.tobytes(), uv.tobytes()))
    return out


def test_helpers_make_the_same_welds_as_the_master_alone(tmp_path, monkeypatch):
    """The heavy frame (12 welds) imported with helper processes and without: the same welds, bit for bit."""
    from fresing_render.core import weld_pool
    path = str(tmp_path / "grid.step")
    root, mats = maker.heavy_beads(4)
    maker.write_cad_step(root, path, mats)
    monkeypatch.setattr(weld_pool, "MIN_JOBS", 1)
    got = {}
    for n in ("0", "2"):
        monkeypatch.setenv("FRESING_WELD_HELPERS", n)
        sc = fresh(path)
        assert weld_cad.LAST["helpers"] == int(n), weld_cad.LAST
        got[n] = (weld_cad.table(sc), _weld_meshes(sc))
    assert got["0"] == got["2"] and len(got["0"][0]) == 12
