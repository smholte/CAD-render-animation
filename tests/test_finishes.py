"""Task 0274: the finishes of study 0270 – knurls, spun / faced ends, honed bores, moulded textures, fabric, plate
patterns, blasted metal, paints and grains.

Without Blender: the table, the settings text, the face data (``core.finishes.face_frames``) on made-up meshes, the
far-away fade, the web model's numbers. In Blender (as a Python module): every finish builds, a group's settings
rebuild its material, the face data on the test model (copies share it, a model update writes the same numbers), the
pixel angle follows the camera, the web 3D model takes an average finish as numbers and bakes a tile finish."""

import math
import os

import numpy as np
import pytest

from fresing_render.core import finishes as fc
from fresing_render.core import materials_lib

HERE = os.path.join(os.path.dirname(__file__), "data")
FINISHES = os.path.join(HERE, "test_finishes.step")


# ---------------------------------------------------------------------------------------------------------------
# without Blender
# ---------------------------------------------------------------------------------------------------------------

def test_the_23_finishes_are_library_materials():
    with_finish = {k for k, v in materials_lib.MATERIALS.items() if v.get("finish")}
    assert with_finish == set(fc.FINISHES) and len(fc.FINISHES) == 23
    # the study's numbers that were picked for this task (0270: carbon, weld, rust and perlage go to 0318 / 0319)
    assert sorted(f["n"] for f in fc.FINISHES.values()) == sorted(
        set(range(1, 27)) - {17, 21, 23})
    numbers = list(materials_lib.UIDS.values())
    assert len(numbers) == len(set(numbers)) == len(materials_lib.MATERIALS)
    assert all(materials_lib.UIDS[k] >= 62 for k in fc.FINISHES)          # new numbers only, none reused
    for k, f in fc.FINISHES.items():
        spec = materials_lib.MATERIALS[k]
        assert spec["category"] in materials_lib.CATEGORIES
        assert f["web"] in ("average", "tile"), k
        assert not (f.get("faces") and f["web"] == "tile"), f"{k}: a face-axis pattern cannot be a 0.2 m tile"
        for b in f.get("bases", ()):
            assert b in fc.BASES, k
        for kd in f.get("kinds", ()):
            assert kd in fc.KINDS, k
        if f.get("size"):
            label, key, d, lo, hi = f["size"]
            assert lo <= d <= hi and key in f["pat"] and label, k
        assert fc.period(k) > 0, k
        assert not spec.get("marks") and not spec.get("variation") and not spec.get("bump"), k
    nums = [v[0] for v in fc.BASES.values()] + [v[0] for v in fc.KINDS.values()]
    assert len(set(v[0] for v in fc.BASES.values())) == len(fc.BASES)
    assert len(set(v[0] for v in fc.KINDS.values())) == len(fc.KINDS)
    assert 0 not in nums


def test_settings_text_round_trip_and_limits():
    k = fc.key("knurl_diamond", size=0.0012, angle=45.0, base="BRASS")
    assert k == "size=1.2;angle=45;base=BRASS"
    got = fc.parse("knurl_diamond", k)
    assert got["size"] == pytest.approx(0.0012) and got["angle"] == 45.0 and got["base"] == "BRASS"
    # out of range: kept inside the finish's limits; a metal it does not offer: its default
    c = fc.clean("knurl_diamond", size=0.5, angle=80.0, base="GALVANIZED")
    assert c["size"] == fc.FINISHES["knurl_diamond"]["size"][4] and c["angle"] == 45.0 and c["base"] == "STEEL"
    assert fc.key("paint_satin") == "" and fc.parse("paint_satin", "size=3") == {}
    assert fc.key("soft_touch") == "-"                                   # a finish without settings
    assert fc.key("vdi", kind="VDI36") == "kind=VDI36"
    assert fc.settings_of("perforated") == ["base", "kind", "size"]
    assert fc.defaults("perforated") == dict(size=0.005, angle=0.0, amount=0.0, base="GALVANIZED", kind="ROUND")
    # a size of 0 (a group that never had the finish) is the default
    assert fc.parse("tread", "size=0")["size"] == 0.025


def test_pattern_numbers_follow_the_settings():
    p = fc.pattern("perforated", {"size": 0.004, "kind": "SLOTTED"})
    assert p["hole"] == 0.004 and p["slot"] == pytest.approx(0.02) and p["pitch"] == pytest.approx(0.008)
    assert fc.pattern("perforated")["pitch"] == pytest.approx(0.008)          # Rv 5-8
    assert fc.pattern("vdi", {"kind": "VDI36"})["roughness"] == 0.64
    # box patterns that tile the web model: their period divides 0.2 m
    for k, s in (("tread", 0.023), ("scraped", 0.012)):
        per = fc.pattern(k, {"size": s})["pitch" if k == "tread" else "cell"]
        assert abs(fc.TILE / per - round(fc.TILE / per)) < 1e-9 and abs(per - s) / s < 0.1
    b = fc.base("knurl_diamond", {"base": "BRASS"})
    assert b["base_color"] == fc.BASES["BRASS"][2] and b["metallic"] == 1.0
    assert fc.base("as_cast", {"kind": "CAST_FE"})["base_color"] == (0.30, 0.30, 0.31)


def test_fade_far_away():
    a = fc.pixel_angle(1920)
    assert a == pytest.approx(fc.PIXEL_ANGLE)
    assert fc.shown(0.0008, 0.3, a) == 1.0                 # a 0.8 mm knurl at 30 cm: 4.4 px a tooth
    assert fc.shown(0.0008, 4.0, a) == 0.0                 # at 4 m: 0.3 px – its average, no moiré
    seq = [fc.shown(0.0008, d, a) for d in np.linspace(0.2, 2.0, 40)]
    assert all(x >= y for x, y in zip(seq, seq[1:]))       # fades smoothly, never comes back
    assert 0.0 < fc.shown(0.0008, 0.0008 / (2.5 * a), a) < 1.0


def test_see_through_finishes_open_share_and_far_numbers():
    for k in ("grille", "perforated", "expanded"):
        share = fc.open_share(k)
        assert 0.2 < share < 0.7, k
        assert fc.far(k)["alpha"] == pytest.approx(1.0 - share)
    assert fc.open_share("perforated") == pytest.approx(math.pi * 2.5 ** 2 / (8 ** 2 * math.sqrt(3) / 2))   # Rv 5-8: 35 %
    assert fc.open_share("tread") == 0.0 and fc.far("tread")["alpha"] == 1.0
    assert fc.far("knurl_diamond")["roughness"] > fc.base("knurl_diamond")["roughness"]   # grooves look duller far away
    assert fc.web_mode("knurl_diamond") == "average" and fc.web_mode("tread") == "tile" and fc.web_mode("chrome") == ""


def _cylinder(r=0.01, h=0.015, n=48, inside=False, cap=True):
    """A made-up CAD-like mesh: a round face (n x 2 triangles, axis z) and its top cap as a second CAD face."""
    ang = np.linspace(0, 2 * math.pi, n, endpoint=False)
    ring0 = np.c_[r * np.cos(ang), r * np.sin(ang), np.zeros(n)]
    ring1 = ring0 + [0, 0, h]
    co = np.vstack([ring0, ring1, [[0, 0, h]]])
    tri = []
    for i in range(n):
        j = (i + 1) % n
        a, b, c, d = i, j, n + j, n + i
        tri += [(a, b, c), (a, c, d)] if not inside else [(a, c, b), (a, d, c)]
    side = len(tri)
    if cap:
        for i in range(n):
            tri.append((2 * n, n + i, n + (i + 1) % n))
    axes = [0, 0, 0, 0, 0, 1, r]
    return co, np.array(tri), axes, [0, side, 0], [0, side, len(tri)]


def test_face_frames_round_face_bore_and_end_face():
    co, tri, axes, axf, starts = _cylinder()
    o, d, r, k = fc.face_frames(co, tri, axes, axf, starts)
    side = axf[1]
    assert (k[:side] == 1).all() and (k[side:] == 2).all()
    assert np.allclose(r[:side], 0.01, atol=1e-6) and np.allclose(r[side:], 0.01, atol=1e-6)
    assert np.allclose(d[:side], [0, 0, 1]) and np.allclose(d[side:], [0, 0, 1])      # the cap looks up: +z
    co, tri, axes, axf, starts = _cylinder(inside=True, cap=False)
    _o, _d, r, k = fc.face_frames(co, tri, axes, axf, starts)
    assert (k == -1).all() and np.allclose(r, 0.01, atol=1e-6)                         # a bore
    assert fc.teeth(0.01, 0.0008, 30.0) == 68


def test_face_frames_turned_and_mirrored_copy_give_the_same_pattern():
    """A turned (or mirrored) mesh: the axis turns with it, the radius and the kind stay – so the pattern sits on the
    part the same way (each copy of a part shares its mesh anyway; this is the part drawn turned in its own CAD)."""
    co, tri, axes, axf, starts = _cylinder()
    o0, d0, r0, k0 = fc.face_frames(co, tri, axes, axf, starts)
    th = 0.7
    R = np.array([[1, 0, 0], [0, math.cos(th), -math.sin(th)], [0, math.sin(th), math.cos(th)]]) @ np.diag([-1, 1, 1])
    co2 = co @ R.T + [0.1, -0.2, 0.3]
    ax2 = list(R @ axes[:3] + [0.1, -0.2, 0.3]) + list(R @ axes[3:6]) + [axes[6]]
    tri2 = tri[:, ::-1]                                       # a mirror turns the triangles' winding over
    o, d, r, k = fc.face_frames(co2, tri2, ax2, axf, starts)
    assert np.array_equal(k, k0) and np.allclose(r, r0, atol=1e-9)
    side = axf[1]
    assert np.allclose(d[:side], (R @ d0[:side].T).T, atol=1e-9)


def test_face_frames_survive_bad_input():
    o, d, r, k = fc.face_frames(np.zeros((0, 3)), np.zeros((0, 3)))
    assert len(k) == 0
    co, tri, _a, _f, _s = _cylinder()
    o, d, r, k = fc.face_frames(co, tri, axes=[], axis_faces=[], starts=[])     # no CAD data: one face, no axis
    assert (k == 0).all() and np.isfinite(o).all() and np.isfinite(d).all()
    o, d, r, k = fc.face_frames(co, tri, [0, 0, 0, 0, 0, 1, 0.01], [0, 10 ** 6, 5], [0, 7])   # axis out of range
    assert np.isfinite(r).all()


# ---------------------------------------------------------------------------------------------------------------
# in Blender
# ---------------------------------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def blender():
    bpy = pytest.importorskip("bpy")
    import addon_utils

    import fresing_render
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield bpy
    fresing_render.unregister()


@pytest.fixture(scope="module")
def board(blender, tmp_path_factory):
    from fresing_render.blender import tour
    sc = tour._fresh((FINISHES,), str(tmp_path_factory.mktemp("finishes")))
    groups = tour.finishes_demo(sc)
    return blender, sc, groups


def _attr(me, name):
    at = me.attributes[name]
    n = len(me.polygons) * (3 if at.data_type == "FLOAT_VECTOR" else 1)
    a = np.empty(n, np.float32)
    at.data.foreach_get("vector" if at.data_type == "FLOAT_VECTOR" else "value", a)
    return a


def test_every_finish_builds_into_a_material(blender):
    bpy = blender
    from fresing_render.blender import finishes, materials
    for k in fc.FINISHES:
        for settings in [{}] + [{"base": b} for b in fc.FINISHES[k].get("bases", ())[1:2]] + \
                [{"kind": kd} for kd in fc.FINISHES[k].get("kinds", ())[1:2]]:
            mat = bpy.data.materials.new(f"t {k}")
            mat.use_nodes = True
            materials.build_nodes(mat, k, "RAL 5010", 0.4, finish=fc.key(k, **settings))
            assert mat.get(finishes.PROP_FINISH) == k
            assert mat["fr_finish_set"] == fc.key(k, **settings)
            web = finishes.web_numbers(mat)
            assert web["mode"] == fc.FINISHES[k]["web"] and 0.0 <= web["roughness"] <= 1.0
            n = finishes.node_count(mat)
            assert 15 <= n <= 160, (k, n)                    # the study: 11 - 115 nodes; wear adds ~25
            bsdf = next(nd for nd in mat.node_tree.nodes if nd.type == "BSDF_PRINCIPLED")
            assert bsdf.inputs["Alpha"].is_linked == bool(fc.FINISHES[k].get("see_through")), k
            assert bsdf.inputs["Normal"].is_linked, k
            reader = next((nd for nd in mat.node_tree.nodes if nd.type == "ATTRIBUTE"
                           and nd.attribute_name == fc.PIXEL_PROP), None)
            assert reader is not None and reader.attribute_type == "VIEW_LAYER", k
            bpy.data.materials.remove(mat)
    # another look takes the finish's marks off the material again
    mat = bpy.data.materials.new("t back")
    mat.use_nodes = True
    materials.build_nodes(mat, "grille", "RAL 9005")
    materials.build_nodes(mat, "paint_satin", "RAL 9005")
    assert finishes.PROP_FINISH not in mat and finishes.web_numbers(mat) is None and mat["fr_finish_set"] == ""


def test_group_settings_rebuild_the_material(board):
    bpy, sc, groups = board
    from fresing_render.blender import materials
    g = sc.fresing.groups[groups["KNOB DIAMOND KNURL"]]
    assert g.material == "knurl_diamond"
    assert g.fin_size == pytest.approx(0.0008) and math.degrees(g.fin_angle) == pytest.approx(30.0)
    assert g.fin_base == "STEEL"
    mat = bpy.data.materials[materials.material_name(g.name)]
    assert mat["fr_finish_set"] == "size=0.8;angle=30;base=STEEL"
    g.fin_size = 0.0012
    g.fin_base = "BRASS"
    assert mat["fr_finish_set"] == "size=1.2;angle=30;base=BRASS"
    from fresing_render.core import ral
    assert tuple(mat.diffuse_color)[:3] == pytest.approx([ral.srgb_to_linear(c) for c in fc.BASES["BRASS"][2]])
    assert materials.is_current(mat, g.material, g.color, g.wear, materials.group_finish(g))
    assert not materials.is_current(mat, g.material, g.color, g.wear, "size=1.6")
    # another finish: its own defaults; back to a plain material: no settings
    g.material = "perforated"
    assert g.fin_base == "GALVANIZED" and g.fin_kind == "ROUND" and g.fin_size == pytest.approx(0.005)
    g.material = "paint_satin"
    assert materials.group_finish(g) == "" and "fr_finish" not in mat
    g.material = "knurl_diamond"


def test_face_data_on_the_test_model_copies_share_it(board):
    bpy, sc, _groups = board
    from fresing_render.blender import build, finishes
    parts = {}
    for ob in build.iter_parts(sc):
        parts.setdefault(ob.get(build.PROP_NAME), []).append(ob)
    knob = parts["KNOB DIAMOND KNURL"][0].data
    assert finishes.has_faces(knob)
    k, r = _attr(knob, "fr_fx_k"), _attr(knob, "fr_fx_r")
    assert (k == 1).any() and (k == 2).any()
    assert np.median(r[k == 1]) == pytest.approx(0.010, abs=2e-4)
    bush = parts["BUSHING HONED"][0].data
    assert (_attr(bush, "fr_fx_k") == -1).any()                  # the bore
    cups = parts["HEADSET CUP"]                                    # two copies, turned left and right
    assert len(cups) == 2 and cups[0].data is cups[1].data
    plate = parts["PLATE TREAD"][0].data                           # a box pattern needs no face data
    assert not finishes.has_faces(plate)
    # face data taken off (an older project): giving the parts their materials again writes it
    sh = parts["SHAFT FACED"][0]
    assert finishes.has_faces(sh.data)
    for name in finishes.FX_NAMES:
        sh.data.attributes.remove(sh.data.attributes[name])
    from fresing_render.blender import logic
    logic.refresh_group_materials(sc)
    assert finishes.has_faces(sh.data)


def test_model_update_writes_the_same_face_data(board):
    bpy, sc, groups = board
    from fresing_render.blender import build, finishes
    def knob():
        return next(o for o in build.iter_parts(sc) if o.get(build.PROP_NAME) == "KNOB DIAMOND KNURL")
    before = {n: _attr(knob().data, n) for n in finishes.FX_NAMES}
    root = next(r for r in build.model_roots(sc) if r.get(build.PROP_NAME) == "TEST.FINISHES")
    assert bpy.ops.fresing.import_step(filepath=FINISHES, quality="draft", update_root=root.name) == {"FINISHED"}
    me = knob().data
    assert finishes.has_faces(me)
    for n in finishes.FX_NAMES:
        assert np.allclose(_attr(me, n), before[n], atol=1e-7), n
    assert knob().active_material.get("fr_material") == "knurl_diamond"


def test_stale_face_data_is_written_again(blender):
    bpy = blender
    from fresing_render.blender import finishes
    import bmesh
    me = bpy.data.meshes.new("fx test")
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=0.01, radius2=0.01, depth=0.02)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    assert finishes.ensure_faces(me) and finishes.has_faces(me) and not finishes.ensure_faces(me)
    me.vertices[0].co.x += 0.001                                    # the part changed (a model update in place)
    assert not finishes.has_faces(me) and finishes.ensure_faces(me)


def test_pixel_angle_follows_the_camera(blender):
    bpy = blender
    from fresing_render.blender import cameras
    sc = bpy.data.scenes.new("px test")
    assert cameras.pixel_angle(sc) == fc.PIXEL_ANGLE                # no camera: the default
    cam = bpy.data.objects.new("px cam", bpy.data.cameras.new("px cam"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 1920, 1080, 100
    cam.data.lens = 50.0
    assert cameras.pixel_angle(sc) == pytest.approx(36.0 / 50.0 / 1920)
    assert cameras.update_pixel_angle(sc) and not cameras.update_pixel_angle(sc)     # set only on a change
    cam.data.lens = 85.0
    sc.render.resolution_percentage = 50
    assert cameras.update_pixel_angle(sc)
    assert sc[fc.PIXEL_PROP] == pytest.approx(36.0 / 85.0 / 960, rel=0.01)
    cam.data.type = "ORTHO"
    assert cameras.pixel_angle(sc) > 0
    bpy.data.scenes.remove(sc)


def test_web_model_takes_an_average_finish_as_numbers(blender):
    bpy = blender
    from fresing_render.blender import materials, web3d
    m1 = bpy.data.materials.new("web knurl")
    m1.use_nodes = True
    materials.build_nodes(m1, "knurl_diamond", "", 0.0)
    lk = web3d.Look(m1)
    assert lk.finish == "average" and not lk.src
    far = fc.far("knurl_diamond")
    assert lk.const["rough"] == pytest.approx(far["roughness"]) and lk.const["metal"] == 1.0
    m2 = bpy.data.materials.new("web grille")
    m2.use_nodes = True
    materials.build_nodes(m2, "grille", "RAL 9005", 0.0)
    lk = web3d.Look(m2)
    assert lk.finish == "tile" and "alpha" in lk.src and "normal" in lk.src
    m3 = bpy.data.materials.new("web chrome")
    m3.use_nodes = True
    materials.build_nodes(m3, "chrome", "", 0.0)
    assert web3d.Look(m3).finish == ""


def test_a_tile_finish_bakes_its_pattern_at_full_detail(blender):
    """In the bake scene the fade is off (``fr_pixel_angle`` tiny): the tread plate's lenses are in the tile."""
    bpy = blender
    from fresing_render.blender import materials, web3d
    sc = bpy.data.scenes.new("web bake test")
    sc.render.engine = "CYCLES"
    m = bpy.data.materials.new("web tread")
    m.use_nodes = True
    materials.build_nodes(m, "tread", "", 0.0)
    lk = web3d.Look(m)
    baker = web3d.Baker(sc)
    try:
        assert baker.scene[fc.PIXEL_PROP] < 1e-8
        jobs = [(key, m, sock, web3d.KIND[ch]) for key, (ch, sock) in lk.sockets().items() if ch == "normal"]
        got = baker.tiles(jobs, 64)
        tile = got[jobs[0][0]]
        assert float(np.ptp(tile[..., 0])) > 0.05            # the lenses tilt the normal: not a flat tile
    finally:
        baker.close()
        bpy.data.scenes.remove(sc)
