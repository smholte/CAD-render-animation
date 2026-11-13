"""Under the water (task 0081): the seabed, the water's clarity and the cut-away behind the stern
(``core/sea.py``, the sea part of ``blender/surroundings.py``).

Without Blender: the clarity's numbers (5 % left at the clarity's distance), the light under water, the sand
ripples. Inside Blender (as a Python module): which objects each setting makes, the plain sea's materials exactly as
before (same names, same nodes), the seabed's height and its motion with "FR seabed motion", the box from the panel
and from the sea cable (``paths_sea.cut_box``), the ring of water round the box, the settings key, and small Cycles
renders: the seabed shows inside the box, the sea outside it is unchanged, a thing behind a wall fades into the
water's colour by ``core.sea.seen_through``.
"""

import json
import math
import os

import numpy as np
import pytest

from fresing_render.core import sea

# ---------------------------------------------------------------------------
# the numbers (no Blender)
# ---------------------------------------------------------------------------


def test_clarity_leaves_five_percent_at_its_distance():
    for c in (2.0, 5.0, 10.0, 40.0):
        assert sea.absorption(c) == pytest.approx(3.0 / c)
        assert sea.transmittance(c, c) == pytest.approx(math.exp(-3.0))
        assert sea.fade(c, c) == pytest.approx(1.0 - math.exp(-3.0))
        assert 0.049 < 1.0 - sea.fade(c, c) < 0.051
    d = np.array([0.0, 1.0, 5.0, 30.0])
    assert np.allclose(sea.fade(d, 10.0), 1.0 - np.exp(-0.3 * d))
    assert sea.fade(-3.0, 10.0) == 0.0                                  # nothing in front of the wall fades
    assert np.all(np.diff(sea.fade(d, 10.0)) > 0)
    assert sea.fade(5.0, 5.0) > sea.fade(5.0, 20.0)                      # murkier water fades more
    # the ring of water round the box reaches far enough that nothing shows through it
    assert sea.transmittance(sea.CUT_GROW * 10.0, 10.0) < 1e-5


def test_seen_through_mixes_towards_the_water_colour():
    white = np.ones(3)
    near = sea.seen_through(white, 0.0, 10.0)
    assert np.allclose(near, white)
    far = sea.seen_through(white, 1000.0, 10.0)
    assert np.allclose(far, sea.UNDERWATER)
    mid = sea.seen_through(white, 10.0, 10.0)
    t = math.exp(-3.0)
    assert np.allclose(mid, t + np.array(sea.UNDERWATER) * (1 - t))


def test_light_under_water_follows_the_day():
    assert sea.light_level(1.0, 0.0) == pytest.approx(1.0 + sea.NIGHT_LIGHT)
    assert sea.light_level(0.0, 0.0) == pytest.approx(sea.NIGHT_LIGHT)          # night: dark
    assert sea.light_level(1.0, 1.0) == pytest.approx(sea.OVERCAST_LIGHT + sea.NIGHT_LIGHT)
    assert sea.light_level(2.0, -1.0) == sea.light_level(1.0, 0.0)               # clamped
    assert sea.sky_light() == pytest.approx(1.0)
    assert sea.sky_light(overcast=True) == pytest.approx(sea.OVERCAST_LIGHT)
    assert sea.sky_light(elevation_deg=10.0) < sea.sky_light(elevation_deg=60.0)
    assert sea.sky_light(strength=2.0) == pytest.approx(2.0)
    night = sea.underwater_colour(sea.light_level(0.0))
    assert max(night) < 0.01 * max(sea.UNDERWATER)
    assert sea.underwater_colour(0.5) == pytest.approx(tuple(c * 0.5 for c in sea.UNDERWATER))
    # a North Sea green-blue, lighter than the sea seen from above
    r, g, b = sea.UNDERWATER
    assert g > r and b > r and sum(sea.UNDERWATER) > sum(sea.DEEP)


def test_sand_ripples():
    x, y = np.meshgrid(np.linspace(0, 40, 400), np.linspace(0, 40, 400))
    h = sea.seabed_ripples(x, y)
    assert np.abs(h).max() < sea.RIPPLE_HEIGHT + 0.13
    # along the current the ripples come every RIPPLE_LENGTH or so
    line = sea.seabed_ripples(np.linspace(0, 20, 2001), np.zeros(2001)) - 0.0
    crossings = np.sum(np.diff(np.sign(line - np.convolve(line, np.ones(101) / 101, "same"))) != 0)
    assert 30 <= crossings <= 60
    assert sea.seabed_ripples(1.0, 2.0) == sea.seabed_ripples(1.0, 2.0)


# ---------------------------------------------------------------------------
# inside Blender
# ---------------------------------------------------------------------------

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import paths_sea, surroundings, world  # noqa: E402

L, B, D = 60.0, 14.0, 9.0          # the invented vessel: stern (transom) at x = 0, bow at +x
WATER = 4.0                        # water level above the keel


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def _hull():
    me = bpy.data.meshes.new("Hull")
    v = [(0, -B / 2, 0), (L - 8, -B / 2, 0), (L, 0, 0), (L - 8, B / 2, 0), (0, B / 2, 0)]
    v = v + [(x, y, D) for x, y, _ in v]
    f = [(4, 3, 2, 1, 0), (5, 6, 7, 8, 9)] + [(i, (i + 1) % 5, 5 + (i + 1) % 5, 5 + i) for i in range(5)]
    me.from_pydata(v, [], f)
    me.update()
    return me


@pytest.fixture()
def scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    root = bpy.data.objects.new("Invented vessel", None)
    sc.collection.objects.link(root)
    root["fr_root"] = True
    root["fr_kind"] = "assembly"
    ob = bpy.data.objects.new("Hull", _hull())
    sc.collection.objects.link(ob)
    ob.parent = root
    ob["fr_kind"] = "part"
    ob["fr_uid"] = "hull"
    bpy.context.view_layer.update()
    s = sc.fresing
    s.background = "SEA"
    s.water_level = WATER
    return sc


def _env(role):
    return [o for o in bpy.data.objects if o.get(surroundings.TAG) == role]


def _apply(sc):
    world.apply(sc, sc.fresing)
    bpy.context.view_layer.update()


def _signature(mat):
    """The node tree as plain data: node types and settings, every input's value, every link."""
    nodes = []
    for n in mat.node_tree.nodes:
        ins = []
        for sock in n.inputs:
            v = getattr(sock, "default_value", None)
            if v is not None and not isinstance(v, (int, float, str, bool)):
                try:
                    v = tuple(round(float(c), 6) for c in v)
                except TypeError:
                    v = str(v)
            elif isinstance(v, float):
                v = round(v, 6)
            ins.append((sock.identifier, v))
        extra = tuple(getattr(n, k, None) for k in ("operation", "attribute_type", "attribute_name", "data_type",
                                                    "noise_dimensions", "interpolation_type"))
        nodes.append((n.bl_idname, n.name, extra, tuple(ins)))
    links = sorted((lk.from_node.name, lk.from_socket.identifier, lk.to_node.name, lk.to_socket.identifier)
                   for lk in mat.node_tree.links)
    return sorted(nodes, key=repr), links


def test_objects_for_each_setting(scene):
    s = scene.fresing
    _apply(scene)
    assert len(_env("seabed")) == 1                       # always on the open sea
    assert not _env("stones") and not _env("sea_cut")
    sea_ob = _env("sea")[0]
    assert not any(k in sea_ob for k in surroundings.CUT_ATTRS)
    s.sea_cutaway = True
    _apply(scene)
    assert len(_env("sea_cut")) == 1 and len(_env("seabed")) == 1
    assert not _env("stones")                             # Simple: no stones
    ring = _env("sea_cut")[0]
    assert not ring.modifiers                             # Simple: a flat sea, a flat top
    assert not ring.visible_shadow and not ring.visible_diffuse and ring.visible_camera
    mat = ring.data.materials[0]
    assert mat.volume_intersection_method == "ACCURATE"
    assert mat["fr_sigma"] == pytest.approx(3.0 / s.sea_clarity)
    s.env_detail = "DETAILED"
    _apply(scene)
    assert len(_env("stones")) == 1
    ring = _env("sea_cut")[0]
    sea_ob = _env("sea")[0]
    assert ring.modifiers and ring.modifiers[0].node_group == sea_ob.modifiers[0].node_group   # the same waves
    s.sea_cutaway = False
    _apply(scene)
    assert not _env("sea_cut") and not _env("stones") and len(_env("seabed")) == 1
    for kind in ("DECK", "QUAY"):                         # only the open sea has a seabed
        s.background = kind
        s.sea_cutaway = True
        _apply(scene)
        assert _env("sea") and not _env("seabed") and not _env("sea_cut")


def test_plain_sea_is_as_before(scene):
    """Without the cut-away: the 0.2.88 names, version and nodes; the cut material is the plain one plus its cut."""
    s = scene.fresing
    s.weather.enabled = True
    s.weather.vessel_speed = 6.0                          # with the wake and the hull foam
    s.sea_state = "ROUGH"
    _apply(scene)
    assert surroundings.MAT_VERSION == 4
    sea_ob = _env("sea")[0]
    plain = sea_ob.data.materials[0]
    assert plain.name == "FR_env water rough foam moving weather wake"
    assert "fr_seacut" not in plain
    foam = _env("hull_foam")[0].data.materials[0]
    assert foam.name == "FR_env hull foam" and "fr_seacut" not in foam
    names = {n.attribute_name for n in plain.node_tree.nodes if n.type == "ATTRIBUTE"}
    assert not any(a.startswith("fr_seacut") for a in names)
    sig_plain = _signature(plain)
    sig_foam = _signature(foam)
    key = json.loads(surroundings.root_object()["fr_key"])
    assert "cut" not in key and key["depth"] == 30.0
    # the same material made again with the cut-away off is node for node the same
    fresh = surroundings._water_material(scene, "ROUGH", True, True, surroundings.sea_wind(s), (), True, wake=True)
    assert fresh == plain
    s.sea_cutaway = True
    _apply(scene)
    cut = _env("sea")[0].data.materials[0]
    assert cut.name == plain.name + " cut" and cut.get("fr_seacut")
    assert _env("hull_foam")[0].data.materials[0].name == "FR_env hull foam cut"
    assert _signature(plain) == sig_plain and _signature(foam) == sig_foam      # the plain ones are untouched
    plain_nodes = {(n[0], n[1]) for n in sig_plain[0]}
    cut_nodes = {(n[0], n[1]) for n in _signature(cut)[0]}
    assert plain_nodes < cut_nodes
    added = cut_nodes - plain_nodes
    assert len(added) < 30                                # the box test and one mix
    s.sea_cutaway = False
    _apply(scene)
    assert _env("sea")[0].data.materials[0] == plain


def test_settings_key_only_what_matters(scene):
    s = scene.fresing
    _apply(scene)
    root = surroundings.root_object()
    key = root["fr_key"]
    for name, value in (("sea_clarity", 25.0), ("sea_cut_length", 80.0), ("sea_cut_side", 3.0),
                        ("sea_cut_auto", False)):
        setattr(s, name, value)
        _apply(scene)
        assert surroundings.root_object()["fr_key"] == key, name          # off: no rebuild for nothing
    s.sea_depth = 45.0
    _apply(scene)
    assert surroundings.root_object()["fr_key"] != key                 # the seabed moved: rebuilt
    s.sea_cutaway = True
    _apply(scene)
    key = surroundings.root_object()["fr_key"]
    s.sea_clarity = 6.0
    _apply(scene)
    assert surroundings.root_object()["fr_key"] != key
    assert _env("sea_cut")[0].data.materials[0]["fr_sigma"] == pytest.approx(0.5)
    # a project of 0.2.88 (its key without the depth) is built again once: with its seabed
    s.sea_cutaway = False
    _apply(scene)
    root = surroundings.root_object()
    old = json.loads(root["fr_key"])
    del old["depth"]
    root["fr_key"] = json.dumps(old, sort_keys=True)
    for ob in _env("seabed"):
        bpy.data.objects.remove(ob)
    _apply(scene)
    assert len(_env("seabed")) == 1


def test_seabed_depth_and_motion(scene):
    s = scene.fresing
    s.sea_depth = 25.0
    s.sea_cutaway = True
    s.env_detail = "DETAILED"
    _apply(scene)
    water = surroundings.waterline(scene)
    assert water == pytest.approx(WATER)
    assert surroundings.seabed_z(scene) == pytest.approx(WATER - 25.0)
    bed, stones = _env("seabed")[0], _env("stones")[0]
    assert bed.matrix_world.translation.z == pytest.approx(WATER - 25.0)
    co = np.empty(len(bed.data.vertices) * 3)
    bed.data.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    assert co[:, 2].max() < sea.RIPPLE_HEIGHT + 0.13 and co[:, 2].min() > -0.3
    assert np.abs(co[:, :2]).max() == pytest.approx(sea.SEABED_EXTENT)
    # the patch's points lie on core.sea.seabed_ripples (away from its edge)
    inner = (co[:, 2] > -sea.SEABED_SINK + 1e-4) | (co[:, 2] < -sea.SEABED_SINK - 1e-4)
    pts = co[inner][::97]
    box = surroundings.sea_cut_box(scene)
    o = np.array(box["origin"]) - np.array(surroundings.root_object().location)[:2]
    a = (pts[:, 0] - o[0]) * -1.0
    mid = (a > 2.0) & (a < box["length"] - 2.0) & (np.abs(pts[:, 1] - o[1]) < box["width"] / 2 - 2.0)
    assert mid.sum() > 50
    assert np.allclose(pts[mid, 2], sea.seabed_ripples(pts[mid, 0], pts[mid, 1]), atol=1e-4)
    # no "FR seabed motion" yet: nothing to follow
    assert not bed.constraints and not stones.constraints
    empty = bpy.data.objects.new(surroundings.SEABED_MOTION, None)
    scene.collection.objects.link(empty)
    empty.location = (0.0, 0.0, water)
    surroundings.refresh_seabed_motion()
    bpy.context.view_layer.update()
    con = bed.constraints[surroundings.SEABED_MOTION]
    assert con.type == "COPY_LOCATION" and con.use_offset and not con.use_z and con.target == empty
    x0 = bed.matrix_world.translation.copy()
    s0 = stones.matrix_world.translation.copy()
    empty.location = (-7.5, 1.25, water + 3.0)            # the vessel advanced: the seabed moves aft
    bpy.context.view_layer.update()
    assert (bed.matrix_world.translation - x0)[:] == pytest.approx((-7.5, 1.25, 0.0), abs=1e-5)
    assert (stones.matrix_world.translation - s0)[:] == pytest.approx((-7.5, 1.25, 0.0), abs=1e-5)
    # a helper for the sea cables' own objects
    other = bpy.data.objects.new("laid cable", None)
    scene.collection.objects.link(other)
    assert surroundings.follow_seabed_motion(other)
    bpy.context.view_layer.update()
    assert other.matrix_world.translation[:] == pytest.approx((-7.5, 1.25, 0.0), abs=1e-5)
    # rebuilt: still follows
    s.sea_clarity = 20.0
    _apply(scene)
    assert _env("seabed")[0].constraints.get(surroundings.SEABED_MOTION) is not None
    bpy.data.objects.remove(empty)
    surroundings.refresh_seabed_motion()                  # the empty is gone: nothing left pointing at it
    assert not _env("seabed")[0].constraints
    assert not surroundings.follow_seabed_motion(other) and not other.constraints


def _ring_corners(ring):
    co = np.empty(len(ring.data.vertices) * 3)
    ring.data.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    m = np.array(ring.matrix_world)
    return co @ m[:3, :3].T + m[:3, 3]


def test_box_from_the_panel(scene):
    s = scene.fresing
    s.sea_cutaway = True
    s.sea_cut_auto = False
    s.sea_cut_length = 50.0
    s.sea_cut_width = 20.0
    s.sea_cut_start = 5.0
    s.sea_cut_side = -2.0
    s.sea_clarity = 8.0
    _apply(scene)
    box = surroundings.sea_cut_box(scene)
    assert box == {"origin": (pytest.approx(-5.0), pytest.approx(-2.0)), "dir": (-1.0, 0.0), "length": 50.0,
                   "width": 20.0}
    sea_ob = _env("sea")[0]
    assert tuple(sea_ob["fr_seacut_o"]) == pytest.approx((-5.0, -2.0, 0.0))
    assert tuple(sea_ob["fr_seacut_u"]) == pytest.approx((-1.0, 0.0, 0.0))
    assert tuple(sea_ob["fr_seacut_s"]) == pytest.approx((50.0, 10.0, 0.0))
    ring = _env("sea_cut")[0]
    w = _ring_corners(ring)
    g = sea.CUT_GROW * 8.0
    assert w[:, 0].min() == pytest.approx(-55.0 - g, abs=1e-3) and w[:, 0].max() == pytest.approx(-5.0 + g, abs=1e-3)
    assert w[:, 1].min() == pytest.approx(-12.0 - g, abs=1e-3) and w[:, 1].max() == pytest.approx(8.0 + g, abs=1e-3)
    assert w[:, 2].max() == pytest.approx(WATER - sea.CUT_TOP, abs=1e-4)
    assert w[:, 2].min() < surroundings.seabed_z(scene) - 1.0
    # normals out of the water: the box's walls face into the box, the outer walls away from it
    me = ring.data
    inner = np.empty(len(me.polygons))
    me.attributes["fr_inner"].data.foreach_get("value", inner)
    centre = np.array([-30.0, -2.0])
    for p, flag in zip(me.polygons, inner):
        n = np.array(p.normal)
        c = np.array(p.center)[:2] + np.array(ring.matrix_world.translation)[:2]
        if abs(n[2]) > 0.9:
            continue
        towards = np.dot(n[:2], centre - c) > 0
        assert towards == bool(flag)
    assert inner.sum() == 4


def test_box_from_the_sea_cable(scene, monkeypatch):
    s = scene.fresing
    s.sea_cutaway = True
    s.sea_clarity = 10.0
    want = {"origin": (-3.0, 4.0), "dir": (-0.8, 0.6), "length": 70.0, "width": 30.0}
    monkeypatch.setattr(paths_sea, "cut_box", lambda sc: dict(want))
    _apply(scene)
    box = surroundings.sea_cut_box(scene)
    assert box["origin"] == pytest.approx(want["origin"]) and box["dir"] == pytest.approx(want["dir"])
    key = json.loads(surroundings.root_object()["fr_key"])
    assert key["cut"]["box"] == [-3.0, 4.0, -0.8, 0.6, 70.0, 30.0]
    sea_ob = _env("sea")[0]
    assert tuple(sea_ob["fr_seacut_u"]) == pytest.approx((-0.8, 0.6, 0.0))
    w = _ring_corners(_env("sea_cut")[0])
    # the ring in the box's own frame: along the box from -g to length + g, across ±(width / 2 + g)
    u, v = np.array([-0.8, 0.6]), np.array([-0.6, -0.8])
    a = (w[:, :2] - np.array([-3.0, 4.0])) @ u
    b = (w[:, :2] - np.array([-3.0, 4.0])) @ v
    g = sea.CUT_GROW * 10.0
    assert a.min() == pytest.approx(-g, abs=1e-3) and a.max() == pytest.approx(70.0 + g, abs=1e-3)
    assert np.abs(b).max() == pytest.approx(15.0 + g, abs=1e-3)
    # the cable's box changes: rebuilt; "Place it by the cable" off: the panel's box
    want["length"] = 90.0
    _apply(scene)
    assert json.loads(surroundings.root_object()["fr_key"])["cut"]["box"][4] == 90.0
    s.sea_cut_auto = False
    _apply(scene)
    assert surroundings.sea_cut_box(scene)["dir"] == (-1.0, 0.0)
    assert "manual" in json.loads(surroundings.root_object()["fr_key"])["cut"]
    # a broken answer is ignored (the panel's box), an error never stops the surroundings
    s.sea_cut_auto = True
    monkeypatch.setattr(paths_sea, "cut_box", lambda sc: {"origin": (0, 0), "dir": (0, 0), "length": 5, "width": 5})
    _apply(scene)
    assert surroundings.sea_cut_box(scene)["dir"] == (-1.0, 0.0)

    def boom(sc):
        raise RuntimeError("no cable")
    monkeypatch.setattr(paths_sea, "cut_box", boom)
    _apply(scene)
    assert _env("sea_cut") and surroundings.sea_cut_box(scene)["length"] == s.sea_cut_length
    monkeypatch.setattr(paths_sea, "cut_box", lambda sc: None)
    _apply(scene)
    assert surroundings.sea_cut_box(scene)["length"] == s.sea_cut_length


def test_water_colour_follows_the_light(scene):
    s = scene.fresing
    s.sea_cutaway = True
    _apply(scene)
    mat = _env("sea_cut")[0].data.materials[0]
    node = mat.node_tree.nodes["fr_light"]
    assert node.outputs[0].default_value == pytest.approx(sea.sky_light(1.0, False, s.sun_elevation))
    s.sky_weather = "OVERCAST"
    s.light_strength = 0.5
    _apply(scene)
    mat = _env("sea_cut")[0].data.materials[0]
    assert mat.node_tree.nodes["fr_light"].outputs[0].default_value == pytest.approx(
        sea.sky_light(0.5, True, s.sun_elevation))
    s.weather.enabled = True                              # Weather & time: the day and cloud channels
    _apply(scene)
    mat = _env("sea_cut")[0].data.materials[0]
    names = {n.attribute_name for n in mat.node_tree.nodes if n.type == "ATTRIBUTE" and n.attribute_type == "VIEW_LAYER"}
    assert names == {"fr_wx_day", "fr_wx_clouds"}
    assert "fr_light" not in mat.node_tree.nodes
    ad = mat.node_tree.animation_data
    assert ad is None or not ad.drivers                   # nothing to run: scripts off and the queue are fine


# ---------------------------------------------------------------------------
# small renders (Cycles, CPU)
# ---------------------------------------------------------------------------


def _camera(scene, eye, at, lens=30.0):
    from mathutils import Vector
    cam = scene.camera
    if cam is None:
        cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
        scene.collection.objects.link(cam)
        scene.camera = cam
    cam.data.lens = lens
    cam.data.clip_end = 30000.0
    cam.location = eye
    cam.rotation_euler = (Vector(at) - Vector(eye)).to_track_quat("-Z", "Y").to_euler()
    return cam


def _render(scene, path, size=(96, 64), samples=8):
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = False
    scene.cycles.seed = 0
    scene.render.resolution_x, scene.render.resolution_y = size
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "OPEN_EXR"
    scene.view_settings.view_transform = "Standard"
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(str(path), check_existing=False)
    px = np.array(img.pixels[:], dtype=float).reshape(size[1], size[0], 4)[..., :3]
    bpy.data.images.remove(img)
    return px


def test_render_seabed_in_the_box_and_the_sea_outside_unchanged(scene, tmp_path):
    s = scene.fresing
    _apply(scene)
    water, bed = surroundings.waterline(scene), surroundings.seabed_z(scene)
    # straight down into the middle of the box: water without the cut-away, sand with it
    _camera(scene, (-30.0, 0.0, water + 40.0), (-30.0, 0.001, bed), lens=80.0)
    plain_down = _render(scene, tmp_path / "down_plain.exr")
    # away from the box: the open sea ahead of the bow
    _camera(scene, (70.0, -10.0, water + 10.0), (300.0, 30.0, water))
    plain_sea = _render(scene, tmp_path / "sea_plain.exr")
    # the seabed under the opaque water changes nothing
    for ob in _env("seabed"):
        ob.hide_render = True
    no_bed = _render(scene, tmp_path / "sea_nobed.exr")
    for ob in _env("seabed"):
        ob.hide_render = False
    assert np.abs(no_bed - plain_sea).max() < 1e-4
    s.sea_cutaway = True
    _apply(scene)
    cut_sea = _render(scene, tmp_path / "sea_cut.exr")
    assert np.abs(cut_sea - plain_sea).max() < 1e-4, np.abs(cut_sea - plain_sea).max()
    _camera(scene, (-30.0, 0.0, water + 40.0), (-30.0, 0.001, bed), lens=80.0)
    cut_down = _render(scene, tmp_path / "down_cut.exr")
    mid_plain = plain_down[24:40, 36:60].mean(axis=(0, 1))
    mid_cut = cut_down[24:40, 36:60].mean(axis=(0, 1))
    assert mid_plain[2] > mid_plain[0]                  # the sea: blue-green
    assert mid_cut[0] > mid_cut[2] * 1.3                # sand: warm
    assert mid_cut.sum() > 2.0 * mid_plain.sum()        # in the sun, through no water


def test_render_clarity_fades_what_is_behind_a_wall(scene, tmp_path):
    """From inside the box (in its air), 1.5 m under the water, straight at a white light panel 5 m behind the box's
    aft wall: the camera sees core.sea.seen_through(panel, 5 m, clarity)."""
    s = scene.fresing
    s.sea_cutaway = True
    s.sea_cut_auto = False
    s.sea_cut_length = 40.0
    s.sea_cut_width = 16.0
    _apply(scene)
    water = surroundings.waterline(scene)
    me = bpy.data.meshes.new("panel")
    x = -40.0 - 5.0
    me.from_pydata([(x, -15, water - 20), (x, 15, water - 20), (x, 15, water - 0.5), (x, -15, water - 0.5)], [],
                   [(0, 1, 2, 3)])
    mat = bpy.data.materials.new("panel light")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = 1.0
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    me.materials.append(mat)
    panel = bpy.data.objects.new("panel", me)
    scene.collection.objects.link(panel)
    eye = (-25.0, 0.0, water - 1.5)
    _camera(scene, eye, (-100.0, 0.0, water - 1.5), lens=200.0)
    got = {}
    for clarity in (5.0, 20.0):
        s.sea_clarity = clarity
        _apply(scene)
        light = _env("sea_cut")[0].data.materials[0].node_tree.nodes["fr_light"].outputs[0].default_value
        px = _render(scene, tmp_path / f"wall_{clarity}.exr", size=(48, 32), samples=4)
        got[clarity] = px[12:20, 20:28].mean(axis=(0, 1))
        want = sea.seen_through(np.ones(3), 5.0, clarity, light)
        assert np.allclose(got[clarity], want, atol=0.01, rtol=0.03), (clarity, got[clarity], want)
    water_colour = np.array(sea.UNDERWATER)
    assert np.abs(got[5.0] - water_colour).sum() < np.abs(got[20.0] - water_colour).sum()
