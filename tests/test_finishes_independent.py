"""Task 0274, independent tests (written by a tester who did not write the finishes): try to break the finishes.

Without Blender: the settings text with odd input, every finish x metal x kind x size limit, the face data with bad
importer data, the fade at odd distances. In Blender (as a Python module): every finish built with every metal, kind,
size / angle / strength limit and wear; odd meshes through ``prepare_faces``; the pixel angle with odd cameras; a group
switched between finishes; a saved and reopened project; the web 3D model's numbers; small Cycles renders of the
see-through finishes and of a sheet at 45° (96 px, 4 samples, well under a second each).

The tester found six faults (round holes doubled, a sheet at 45° striped, NaN settings, the pixel aspect, a negative
start in the importer's data, odd array lengths); all are fixed and these tests now guard them."""

import math
import os
import random
import sys

import numpy as np
import pytest

from fresing_render.core import finishes as fc

HERE = os.path.join(os.path.dirname(__file__), "data")
FINISHES = os.path.join(HERE, "test_finishes.step")
NAN, INF = float("nan"), float("inf")


def _combos(k, limits=True):
    f = fc.FINISHES[k]
    out = [{}]
    out += [{"base": b} for b in f.get("bases", ())]
    out += [{"kind": kd} for kd in f.get("kinds", ())]
    if limits and f.get("size"):
        out += [{"size": f["size"][3]}, {"size": f["size"][4]}]
    if limits and f.get("angle"):
        out += [{"angle": f["angle"][2]}, {"angle": f["angle"][3]}]
    if limits and f.get("amount"):
        out += [{"amount": 0.0}, {"amount": 1.0}]
    return out


# ---------------------------------------------------------------------------------------------------------------
# without Blender
# ---------------------------------------------------------------------------------------------------------------

def test_settings_text_with_odd_input_gives_the_defaults():
    d = fc.clean("knurl_diamond")
    for text in ("", None, "===;;size;angle=;base=é;kind=x", "size=abc;angle=1,5", ";;;", "size=-3", "size=0",
                 "base=steel", "base=BRASS ;", "kind=FINE"):
        got = fc.parse("knurl_diamond", text)
        for n in ("size", "angle"):
            assert math.isfinite(got[n]), (text, got)
        assert got["base"] in fc.FINISHES["knurl_diamond"]["bases"], text
    assert fc.parse("knurl_diamond", "size=abc")["size"] == d["size"]
    assert fc.parse("knurl_diamond", " size = 1.2 ; angle = 40 ; base = BRASS ") == \
        dict(d, size=pytest.approx(0.0012), angle=40.0, base="BRASS")
    # huge numbers are held at the limits
    assert fc.parse("knurl_diamond", "size=1e400")["size"] == fc.FINISHES["knurl_diamond"]["size"][4]
    assert fc.parse("knurl_diamond", "angle=-1e400")["angle"] == fc.FINISHES["knurl_diamond"]["angle"][2]
    assert fc.clean("knurl_diamond", size=INF)["size"] == fc.FINISHES["knurl_diamond"]["size"][4]
    assert fc.clean("knurl_diamond", size=NAN)["size"] == d["size"]
    # not a finish: nothing
    for mid in ("nope", "", "paint_satin"):
        assert fc.parse(mid, "size=1") == {} and fc.key(mid) == "" and fc.pattern(mid) == {} and fc.far(mid) == {}
        assert fc.period(mid) == 0.0 and fc.open_share(mid) == 0.0 and fc.web_mode(mid) == ""


def test_nan_angle_and_strength_are_replaced_by_the_defaults():
    assert math.isfinite(fc.clean("knurl_diamond", angle=NAN)["angle"])
    assert math.isfinite(fc.clean("spun", amount=NAN)["amount"])
    assert "nan" not in fc.key("knurl_diamond", angle=NAN)
    assert math.isfinite(fc.parse("knurl_diamond", "angle=nan")["angle"])


def test_every_finish_metal_kind_and_limit_gives_sane_numbers():
    for k in fc.FINISHES:
        for c in _combos(k):
            far = fc.far(k, c)
            share = fc.open_share(k, c)
            per = fc.period(k, c)
            assert 0.0 <= share < 1.0, (k, c)
            assert 0.0 <= far["roughness"] <= 1.0 and 0.0 <= far["metallic"] <= 1.0, (k, c)
            assert 0.0 < far["alpha"] <= 1.0 and all(0.0 <= x <= 1.0 for x in far["color"]), (k, c)
            assert per > 0 and math.isfinite(per), (k, c)
            p = fc.pattern(k, c)
            assert all(math.isfinite(v) for v in p.values() if isinstance(v, float)), (k, c, p)
            kk = fc.key(k, **c)
            assert fc.key(k, **fc.parse(k, kk)) == kk, (k, c)          # the text is stable
            if fc.FINISHES[k].get("see_through"):
                assert fc.far(k, c)["alpha"] == pytest.approx(1.0 - share)


def test_settings_text_round_trip_with_random_values():
    rnd = random.Random(274)
    for k, f in fc.FINISHES.items():
        for _ in range(200):
            c = {}
            if f.get("size"):
                c["size"] = rnd.uniform(f["size"][3] * 0.3, f["size"][4] * 3)
            if f.get("angle"):
                c["angle"] = rnd.uniform(-20, 120)
            if f.get("amount"):
                c["amount"] = rnd.uniform(-1, 2)
            k1 = fc.key(k, **c)
            s1 = fc.parse(k, k1)
            assert fc.key(k, **s1) == k1 and fc.parse(k, fc.key(k, **s1)) == s1, (k, c)
            cl = fc.clean(k, **c)
            for n in ("size", "angle", "amount"):
                if n in c:
                    assert s1[n] == pytest.approx(cl[n], rel=1e-3, abs=1e-9), (k, n)


def test_fade_at_odd_distances():
    assert fc.shown(0.001, 0.0) == 1.0 and fc.shown(0.001, -5.0) == 1.0     # at / behind the camera: all of it
    assert fc.shown(0.001, 1e300) == 0.0 and fc.shown(0.001, 1.0, 0.0) == 1.0
    assert fc.pixel_angle(0) > 0 and fc.pixel_angle(1920, 0.0) > 0


def _cylinder(r=0.01, h=0.015, n=48):
    sys.path.insert(0, os.path.dirname(__file__))
    from test_finishes import _cylinder as cyl
    return cyl(r=r, h=h, n=n)


def test_face_frames_with_odd_importer_data_does_not_crash():
    co, tri, axes, axf, starts = _cylinder()
    side, P = axf[1], len(tri)
    cases = [
        dict(axis_faces=axf, starts=[0, side, P + 50]),                  # starts past the end
        dict(axis_faces=axf, starts=[0, side + 10, side, P]),            # not sorted
        dict(axis_faces=axf, starts=[0, 0, side, side, P]),              # empty faces
        dict(axis_faces=[0, side, 0, side // 2, side, 0], starts=starts),  # overlapping round faces
        dict(axis_faces=[0, 2 ** 62, 0], starts=starts),                 # a count far too big
        dict(axis_faces=[0, side, 0.0], starts=np.array(starts)),        # floats, a numpy array
        dict(axis_faces=[0, side, 9], starts=starts),                    # an axis that is not there
    ]
    for kw in cases:
        o, d, r, k = fc.face_frames(co, tri, axes, **kw)
        assert len(k) == P and all(np.isfinite(x).all() for x in (o, d, r, k)), kw
        assert set(np.unique(k)) <= {-1.0, 0.0, 1.0, 2.0}, kw
    # an axis of length 0, a cap of zero-area triangles: finite numbers
    o, d, r, k = fc.face_frames(co, tri, [0, 0, 0, 0, 0, 0, 0.01], axf, starts)
    assert np.isfinite(d).all()
    tri2 = tri.copy()
    tri2[side:] = 0
    o, d, r, k = fc.face_frames(co, tri2, axes, axf, starts)
    assert np.isfinite(o).all() and np.isfinite(d).all() and (k[:side] == 1).all()
    # a turned copy of the part's own box axis (``part_round``) finds the cap as an end face
    _o, _d, _r, k = fc.face_frames(co, tri, [], [], starts, part_centre=[0, 0, 0.0075], part_round=[0, 0, 1])
    assert (k[side:] == 2).all()


def test_face_frames_negative_start_is_skipped():
    co, tri, axes, _axf, _starts = _cylinder()
    P = len(tri)
    _o, _d, _r, k = fc.face_frames(co, tri, axes, [-10, 4, 0], [0, P])
    assert not (k[-10:-6] == 1).any()


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


def _new_mat(bpy, name):
    mat = bpy.data.materials.new(name)
    if mat.node_tree is None:
        mat.use_nodes = True
    return mat


def test_every_finish_with_every_metal_kind_limit_and_wear_builds_clean(blender):
    bpy = blender
    from fresing_render.blender import finishes, materials
    bad = []
    for k, f in fc.FINISHES.items():
        for c in _combos(k):
            for wear in (0.0, 1.0):
                mat = _new_mat(bpy, f"ind {k}")
                key = fc.key(k, **c)
                materials.build_nodes(mat, k, "RAL 5010", wear, finish=key)
                for nd in mat.node_tree.nodes:
                    for s in nd.inputs:
                        if s.is_linked or not hasattr(s, "default_value"):
                            continue
                        try:
                            vals = list(s.default_value)
                        except TypeError:
                            vals = [s.default_value]
                        if any(isinstance(x, float) and not math.isfinite(x) for x in vals):
                            bad.append((k, c, wear, nd.name, s.name))
                if any(not ln.is_valid for ln in mat.node_tree.links):
                    bad.append((k, c, wear, "invalid link"))
                bsdf = next(nd for nd in mat.node_tree.nodes if nd.type == "BSDF_PRINCIPLED")
                if bsdf.inputs["Alpha"].is_linked != bool(f.get("see_through")):
                    bad.append((k, c, wear, "alpha"))
                if mat.get("fr_finish_set") != key or not materials.is_current(mat, k, "RAL 5010", wear, key):
                    bad.append((k, c, wear, "key", mat.get("fr_finish_set")))
                web = finishes.web_numbers(mat)
                if not (web and 0 <= web["roughness"] <= 1 and 0 < web["alpha"] <= 1):
                    bad.append((k, c, wear, "web", web))
                bpy.data.materials.remove(mat)
    assert bad == []


def test_a_stale_or_odd_key_rebuilds_and_a_finish_on_garbage_settings_builds(blender):
    bpy = blender
    from fresing_render.blender import materials
    mat = _new_mat(bpy, "ind stale")
    materials.build_nodes(mat, "tread", "", 0.0, finish="size=12")
    assert mat["fr_finish_set"] == fc.key("tread", size=0.012)
    assert materials.is_current(mat, "tread", "", 0.0, "size=12")
    assert materials.is_current(mat, "tread", "", 0.0, "size=12.0;junk=1")      # the same settings in other words
    assert not materials.is_current(mat, "tread", "", 0.0, "size=30")
    mat["fr_finish_set"] = "garbage"
    assert not materials.is_current(mat, "tread", "", 0.0, "size=12")
    del mat["fr_finish_set"]                                                     # built by an older version
    assert not materials.is_current(mat, "tread", "", 0.0, "")
    materials.build_nodes(mat, "knurl_diamond", "", 0.0, finish="é=é;size=;;=")
    assert mat["fr_finish_set"] == fc.key("knurl_diamond")
    materials.build_nodes(mat, "paint_satin", "RAL 3000", 0.0, finish="size=3")   # not a finish: settings ignored
    assert mat["fr_finish_set"] == "" and "fr_finish" not in mat
    bpy.data.materials.remove(mat)


def test_odd_meshes_through_the_face_data(blender):
    bpy = blender
    from fresing_render.blender import finishes, materials
    me = bpy.data.meshes.new("ind ngon")
    me.from_pydata([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0), (0.5, 1.5, 0)], [], [(0, 1, 2, 4, 3)])
    assert finishes.ensure_faces(me) and finishes.has_faces(me)
    empty = bpy.data.meshes.new("ind empty")
    assert finishes.prepare_faces(empty) == {"round": 0, "bore": 0, "end": 0, "other": 0}
    assert finishes.has_faces(empty)
    edges = bpy.data.meshes.new("ind edges")
    edges.from_pydata([(0, 0, 0), (1, 0, 0)], [(0, 1)], [])
    finishes.prepare_faces(edges)
    assert finishes.has_faces(edges)
    clash = bpy.data.meshes.new("ind attr")
    clash.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 1, 2)])
    clash.attributes.new("fr_fx_k", "INT", "POINT")                             # a name taken by another kind
    finishes.prepare_faces(clash)
    at = clash.attributes["fr_fx_k"]
    assert at.domain == "FACE" and at.data_type == "FLOAT" and finishes.has_faces(clash)
    # a mesh with no faces data at all, given a finish material through assign; a non-mesh object
    ob = bpy.data.objects.new("ind ob", me)
    mat = _new_mat(bpy, "ind knurl")
    materials.build_nodes(mat, "knurl_diamond", "", 0.0)
    for name in finishes.FX_NAMES:
        me.attributes.remove(me.attributes[name])
    materials.assign(ob, mat)
    assert finishes.has_faces(me) and ob.active_material is mat
    empty_ob = bpy.data.objects.new("ind empty ob", None)
    materials.assign(empty_ob, mat)                                              # nothing happens
    bpy.data.objects.remove(ob)
    bpy.data.objects.remove(empty_ob)
    bpy.data.materials.remove(mat)


def test_pixel_angle_with_odd_cameras(blender):
    bpy = blender
    from fresing_render.blender import cameras
    sc = bpy.data.scenes.new("ind px")
    try:
        cam = bpy.data.objects.new("ind cam", bpy.data.cameras.new("ind cam"))
        sc.collection.objects.link(cam)
        lamp = bpy.data.objects.new("ind lamp", bpy.data.lights.new("ind lamp", "POINT"))
        sc.collection.objects.link(lamp)
        sc.camera = lamp                                       # a light as the scene camera
        assert cameras.pixel_angle(sc) == fc.PIXEL_ANGLE
        sc.camera = cam
        sc.render.resolution_x, sc.render.resolution_y = 1080, 1920      # portrait, sensor fit Auto
        assert cameras.pixel_angle(sc) == pytest.approx(36.0 / 50.0 / 1920)
        cam.data.sensor_fit, cam.data.sensor_height = "VERTICAL", 24.0
        assert cameras.pixel_angle(sc) == pytest.approx(24.0 / 50.0 / 1920)
        sc.render.resolution_x, sc.render.resolution_y = 1920, 1080
        assert cameras.pixel_angle(sc) == pytest.approx(24.0 / 50.0 / 1080)
        cam.data.sensor_fit = "HORIZONTAL"
        sc.render.resolution_percentage = 1
        assert 0 < cameras.pixel_angle(sc) < 0.1 and math.isfinite(cameras.pixel_angle(sc))
        sc.render.resolution_percentage = 100
        for typ in ("ORTHO", "PANO"):
            cam.data.type = typ
            a = cameras.pixel_angle(sc)
            assert a > 0 and math.isfinite(a), typ
        cam.location = (0.0, 0.0, 0.0)
        cam.data.type = "ORTHO"
        assert math.isfinite(cameras.pixel_angle(sc))
        for junk in ("junk", -1.0, 0):
            sc[fc.PIXEL_PROP] = junk                           # a broken stored value is written again
            assert cameras.update_pixel_angle(sc) and sc[fc.PIXEL_PROP] > 0
        assert cameras.update_pixel_angle(None) is False
    finally:
        bpy.data.scenes.remove(sc)


def test_pixel_angle_with_a_pixel_aspect(blender):
    bpy = blender
    from fresing_render.blender import cameras
    sc = bpy.data.scenes.new("ind aspect")
    try:
        cam = bpy.data.objects.new("ind cam2", bpy.data.cameras.new("ind cam2"))
        sc.collection.objects.link(cam)
        sc.camera = cam
        cam.data.sensor_fit = "HORIZONTAL"
        sc.render.resolution_x, sc.render.resolution_y = 1920, 1080
        sc.render.pixel_aspect_x = 2.0
        # 1920 pixels still span the 36 mm sensor: each is 36/50/1920 rad wide (the vertical one is half that)
        assert cameras.pixel_angle(sc) >= 36.0 / 50.0 / 1920 * 0.99
    finally:
        bpy.data.scenes.remove(sc)


@pytest.fixture(scope="module")
def board(blender, tmp_path_factory):
    """The tour set "finishes" built, saved and opened again (as the Learning hub does)."""
    bpy = blender
    from fresing_render.blender import tour
    folder = str(tmp_path_factory.mktemp("ind finishes") / "Tour é")
    out = tour.build_all(folder, "9.9.9", only=("finishes",))
    assert out["errors"] == {}
    bpy.ops.wm.open_mainfile(filepath=out["files"]["finishes"])
    return bpy, out, tmp_path_factory.mktemp("ind saved")


def test_the_tour_set_reopened_passes_its_check_and_needs_no_rebuild(board):
    bpy, _out, _tmp = board
    from fresing_render.blender import cameras, logic, tour
    sc = bpy.context.scene
    st = tour.find("finishes")
    assert tour.apply(st, sc) == []
    assert "23 finishes" in st.check(sc)
    assert logic.upgrade_looks(sc) == 0                       # every material still current after the reopen
    assert sc[fc.PIXEL_PROP] == pytest.approx(cameras.pixel_angle(sc), rel=0.011)


def test_a_group_switched_between_finishes_keeps_sane_settings(board):
    bpy, _out, _tmp = board
    from fresing_render.blender import materials
    sc = bpy.context.scene
    g = next(g for g in sc.fresing.groups if g.material == "knurl_diamond")
    mat = bpy.data.materials[materials.material_name(g.name)]
    g.fin_size, g.fin_base = 0.0012, "BRASS"
    g.material = "paint_satin"
    assert "fr_finish" not in mat and mat["fr_finish_set"] == ""
    g.material = "knurl_diamond"                                     # back: its own settings are kept
    assert mat["fr_finish_set"] == "size=1.2;angle=30;base=BRASS"
    for mid in ("bead_blasted", "vdi", "perforated", "honed", "tread", "spun", "as_cast", "knurl_diamond"):
        g.material = mid
        want = fc.key(mid)                                           # a new finish starts with its own defaults
        assert mat["fr_finish_set"] == want, mid
        assert mat["fr_finish"] == mid
        d = fc.defaults(mid)
        if d["base"]:
            assert g.fin_base == d["base"], mid
        if d["kind"]:
            assert g.fin_kind == d["kind"], mid
        for name in fc.settings_of(mid):
            assert name in materials.group_finish(g), mid
    g.material = "perforated"
    g.fin_kind, g.fin_size = "SLOTTED", 0.5                          # past the finish's limit: held at it
    assert mat["fr_finish_set"] == "size=30;base=GALVANIZED;kind=SLOTTED"
    g.material = "knurl_diamond"


def test_finish_settings_survive_save_and_reopen(board):
    bpy, _out, tmp = board
    from fresing_render.blender import logic, materials
    sc = bpy.context.scene
    g = next(g for g in sc.fresing.groups if g.material == "honed")
    g.fin_angle, g.fin_base = math.radians(70.0), "CAST_IRON"
    name = g.name
    key = bpy.data.materials[materials.material_name(name)]["fr_finish_set"]
    assert key == "angle=70;base=CAST_IRON"
    path = str(tmp / "saved é.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    g = sc.fresing.groups[name]
    assert g.fin_base == "CAST_IRON" and math.degrees(g.fin_angle) == pytest.approx(70.0)
    mat = bpy.data.materials[materials.material_name(name)]
    assert mat["fr_finish_set"] == key == materials.group_finish(g)
    assert logic.upgrade_looks(sc) == 0
    assert sc.get(fc.PIXEL_PROP, 0) > 0


def test_web_model_numbers_for_every_board_material(board):
    bpy, _out, _tmp = board
    from fresing_render.blender import materials, web3d
    sc = bpy.context.scene
    seen = set()
    for g in sc.fresing.groups:
        mat = bpy.data.materials.get(materials.material_name(g.name))
        if mat is None or not mat.get("fr_finish"):
            continue
        fid = mat["fr_finish"]
        seen.add(fid)
        lk = web3d.Look(mat)
        assert lk.finish == fc.FINISHES[fid]["web"], fid
        if lk.finish == "average":
            assert not lk.src and 0 <= lk.const["rough"] <= 1 and lk.const["alpha"] == 1.0, fid
        if fc.FINISHES[fid].get("see_through"):
            assert "alpha" in lk.src, fid
        assert web3d.Look(mat, decal=True).finish == "", fid        # a decal is never read as a finish
    assert seen == set(fc.FINISHES)


# ---- small renders of see-through sheets ------------------------------------------------------------------------

def _render_sheet(bpy, tmp, mat, deg: float, scale: float, name: str):
    """A flat sheet turned ``deg`` about z in its own (object) space, seen square on through an orthographic camera
    ``scale`` wide; 96 px, 4 samples, film transparent. Returns the alpha of the middle (64 x 64)."""
    from mathutils import Matrix, Vector
    sc = bpy.data.scenes.new(f"ind sheet {name}")
    try:
        sc.render.engine = "CYCLES"
        sc.cycles.samples, sc.cycles.device, sc.cycles.use_denoising = 4, "CPU", False
        sc.render.resolution_x = sc.render.resolution_y = 96
        sc.render.resolution_percentage = 100
        sc.render.film_transparent = True
        sc.render.image_settings.file_format, sc.render.image_settings.color_mode = "PNG", "RGBA"
        sc.world = bpy.data.worlds.new("ind w")
        a = math.radians(deg)
        t = Vector((math.cos(a), -math.sin(a), 0.0))
        n = Vector((math.sin(a), math.cos(a), 0.0))
        s, h = 0.2, 0.2
        vs = [tuple(-s * t - Vector((0, 0, h))), tuple(s * t - Vector((0, 0, h))), tuple(s * t + Vector((0, 0, h))),
              tuple(-s * t + Vector((0, 0, h)))]
        me = bpy.data.meshes.new(f"ind sheet {name}")
        me.from_pydata(vs, [], [(0, 1, 2), (0, 2, 3)])
        me.materials.append(mat)
        ob = bpy.data.objects.new(f"ind sheet {name}", me)
        sc.collection.objects.link(ob)
        cam = bpy.data.objects.new(f"ind sheet cam {name}", bpy.data.cameras.new(f"ind sheet cam {name}"))
        sc.collection.objects.link(cam)
        sc.camera = cam
        cam.data.type, cam.data.ortho_scale = "ORTHO", scale
        cam.matrix_world = Matrix.Translation(n * 2.0) @ (-n).to_track_quat("-Z", "Y").to_matrix().to_4x4()
        path = str(tmp / f"{name}.png")
        sc.render.filepath = path
        with bpy.context.temp_override(scene=sc):
            bpy.ops.render.render(write_still=True, scene=sc.name)
        img = bpy.data.images.load(path)
        px = np.array(img.pixels[:], np.float32).reshape(96, 96, 4)
        bpy.data.images.remove(img)
        return px[16:80, 16:80, 3]
    finally:
        bpy.data.scenes.remove(sc)


@pytest.fixture(scope="module")
def renders(blender, tmp_path_factory):
    return blender, tmp_path_factory.mktemp("ind renders")


def test_expanded_metal_close_up_is_as_open_as_far_away(renders):
    """The control case of the two below: the expanded metal's open share up close matches its far-away alpha."""
    bpy, tmp = renders
    from fresing_render.blender import materials
    mat = _new_mat(bpy, "ind expanded")
    materials.build_nodes(mat, "expanded", "", 0.0, finish=fc.key("expanded", size=0.1))
    alpha = _render_sheet(bpy, tmp, mat, 0.0, 0.3, "expanded")
    assert float(alpha.mean()) == pytest.approx(fc.far("expanded", {"size": 0.1})["alpha"], abs=0.08)


@pytest.mark.parametrize("mid, size, scale", [("perforated", 0.03, 0.3), ("grille", 0.004, 0.03)])
def test_round_holes_up_close_are_as_open_as_far_away(renders, mid, size, scale):
    bpy, tmp = renders
    from fresing_render.blender import materials
    mat = _new_mat(bpy, f"ind {mid}")
    materials.build_nodes(mat, mid, "RAL 9005", 0.0, finish=fc.key(mid, size=size))
    alpha = _render_sheet(bpy, tmp, mat, 0.0, scale, mid)
    far = fc.far(mid, {"size": size})["alpha"]
    assert float(alpha.mean()) == pytest.approx(far, abs=0.08), (float(alpha.mean()), far)


def test_slotted_holes_up_close_are_as_open_as_far_away(renders):
    bpy, tmp = renders
    from fresing_render.blender import materials
    mat = _new_mat(bpy, "ind slotted")
    materials.build_nodes(mat, "perforated", "", 0.0, finish=fc.key("perforated", size=0.012, kind="SLOTTED"))
    alpha = _render_sheet(bpy, tmp, mat, 0.0, 0.3, "slotted")
    far = fc.far("perforated", {"size": 0.012, "kind": "SLOTTED"})["alpha"]
    assert float(alpha.mean()) == pytest.approx(far, abs=0.08), (float(alpha.mean()), far)


def test_a_perforated_sheet_at_45_degrees_has_holes_not_stripes(renders):
    bpy, tmp = renders
    from fresing_render.blender import materials
    mat = _new_mat(bpy, "ind perf 45")
    materials.build_nodes(mat, "perforated", "", 0.0, finish=fc.key("perforated", size=0.03))
    for deg in (30.0, 45.0):
        alpha = _render_sheet(bpy, tmp, mat, deg, 0.3, f"perf{int(deg)}")
        down = float(alpha.var(axis=0).mean())                       # how much it changes down a column
        assert down > 0.05, (deg, down)
