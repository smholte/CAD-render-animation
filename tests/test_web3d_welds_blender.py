"""Task 0369, with Blender: welds on the web 3D page (each weld look baked once as a strip along the weld's own UVs –
the ripples, the finish, rust –, the heat zones as see-through strips) and the page's colours (the app's AgX look, the
sun and sky of the app's sea light, a photo's sun in the picture's colour)."""

import math
import os
import sys

import numpy as np
import pytest

from fresing_render.core import web3d as core
from fresing_render.core import web3d_env as env

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import web3d, weld_looks, welds  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WELDMENT = os.path.join(HERE, "data", "test_weldment.step")
CRANE = os.path.join(HERE, "data", "test_crane_a.step")


@pytest.fixture(scope="module")
def made(tmp_path_factory):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    assert bpy.ops.fresing.import_step(filepath=WELDMENT, quality="draft") == {"FINISHED"}
    scene = bpy.context.scene
    welds.set_up_test_model(scene)
    out = web3d.export(scene, str(tmp_path_factory.mktemp("welds") / "Weldment.glb"), size=256)
    with open(out["path"], "rb") as fh:
        data = fh.read()
    yield scene, out, data
    fresing_render.unregister()


def _weld_materials(doc, kind):
    return [(i, m) for i, m in enumerate(doc["materials"]) if (m.get("extras") or {}).get("fr_weld") == kind]


def test_each_weld_look_is_a_strip_on_the_page(made):
    scene, out, data = made
    assert not core.problems(data)
    doc, binary = core.read_glb(data)
    beads, heat = _weld_materials(doc, "bead"), _weld_materials(doc, "heat")
    assert len(beads) == len(welds.TEST_WELDS)                     # one material per weld look (each weld its own)
    # the ripples (a normal picture) on every bead but the ground-flush one
    rippled = [m for _i, m in beads if "normalTexture" in m]
    assert len(rippled) == len(welds.TEST_WELDS) - 1
    # the heat zones: see-through with their tint; the painted weld's (nothing to show) is left out
    assert len(heat) == len(welds.TEST_WELDS) - 1 and out["welds"]["left_out"] == 1
    for _i, m in heat:
        assert m["alphaMode"] == "BLEND" and "baseColorTexture" in m["pbrMetallicRoughness"]
    # a strip repeats along the weld and stops at its edges
    for _i, m in beads + heat:
        for info in (m["pbrMetallicRoughness"].get("baseColorTexture"), m.get("normalTexture")):
            if info:
                smp = doc["samplers"][doc["textures"][info["index"]]["sampler"]]
                assert (smp["wrapS"], smp["wrapT"]) == (core.REPEAT, core.CLAMP)
                assert "extensions" not in info            # its UVs are the weld's own, not the tiles' 16-bit ones
    # the weld meshes' UVs: u in strips along the seam (several on a long seam), v inside 0 … 1
    ids = {i for i, _m in beads + heat}
    us, vs = [], []
    for mesh in doc["meshes"]:
        for p in mesh["primitives"]:
            if p.get("material") in ids:
                uv = core.accessor_array(doc, binary, p["attributes"]["TEXCOORD_0"])
                us.append(uv[:, 0].max() - uv[:, 0].min())
                vs.append((uv[:, 1].min(), uv[:, 1].max()))
    assert len(us) >= 2 * len(welds.TEST_WELDS) - 1
    assert max(us) > 2.0                                    # a 200 mm seam: about three strips of 64 mm
    assert all(-1e-3 <= a and b <= 1.0 + 1e-3 for a, b in vs)
    # the file stays small: one strip per look, not a picture per weld
    assert out["welds"]["looks"] == len(beads) + len(heat)
    assert len(data) < 1_500_000


def test_heat_zone_cover_and_ripple_bump_are_found(made):
    scene, _out, _data = made
    it = next(i for i in welds.items(scene) if i.metal == "STAINLESS" and not i.pickled)
    obs = welds.objects_of(it)
    bead = next(o for o in obs if web3d.weld_kind(o) == "bead")
    heat = next(o for o in obs if web3d.weld_kind(o) == "heat")
    assert web3d.weld_bump(bead.material_slots[0].material) is not None
    cover = web3d.weld_cover(heat.material_slots[0].material)
    assert isinstance(cover, tuple)                         # fed by nodes: baked as the strip's alpha
    assert weld_looks.is_weld_material(heat.material_slots[0].material)
    assert heat in web3d.weld_heats(scene) and heat not in web3d.objects(scene)[0]


def test_ripple_normals_from_height():
    """A sawtooth ripple (the weld looks' height) gives normals that lean both ways – the gentle slope one way, the
    sharp edge the other –, average to straight up over a ripple and are unit vectors."""
    w, h, pitch = 256, 16, 0.0016
    along = 16 * pitch
    u = (np.arange(w) + 0.5) / w * along
    r = np.mod(u / pitch, 1.0)
    height = np.repeat(((1.0 - r) ** 0.6)[None, :], h, 0)
    n = web3d.height_normals(height, along, 0.008, 0.55, pitch * 0.18)
    assert n.shape == (h, w, 3)
    assert np.allclose(np.linalg.norm(n, axis=-1), 1.0, atol=1e-5)
    assert n[..., 0].min() < -0.1 and n[..., 0].max() > 0.02  # both ways
    assert abs(float(np.arctan2(n[..., 0], n[..., 2]).mean())) < 0.02   # no lean overall
    assert np.allclose(n[..., 1], 0.0, atol=1e-6)            # straight across: no slope across
    flat = web3d.height_normals(height, along, 0.008, 0.0, pitch * 0.18)
    assert np.allclose(flat, [0.0, 0.0, 1.0])


def test_page_draws_the_welds_with_the_apps_colours(made):
    _scene, out, _data = made
    browser = env.find_browser()
    if not browser:
        pytest.skip("no Chromium / Edge in this session")
    got = env.read_page(out["html"], browser, "auto=0&frames=3", seconds=120)
    if got["state"].startswith("error") and "webgl" in got["state"].lower():
        pytest.skip("no WebGL in the headless browser")
    assert got["state"].startswith("ready"), got["state"]
    pl = got["player"]
    assert pl["welds"]["beads"] >= len(welds.TEST_WELDS) and pl["welds"]["heat"] >= len(welds.TEST_WELDS) - 1
    assert pl["tone"] == "app"


# ---------------------------------------------------------------------------
# the page's colours and light
# ---------------------------------------------------------------------------

def test_page_tone_is_blenders_own_agx_look():
    """The fitted curve against Blender's own AgX + Medium High Contrast on 3,000 colours (the fit used 40,000)."""
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import fit_page_tone
    x = fit_page_tone.samples(3000, seed=7)
    want = fit_page_tone.blender_view(x)
    got = env.tone(x, encode=True)
    err = np.abs(got - want) * 255.0
    sat = (x.max(1) - x.min(1)) / np.maximum(x.max(1), 1e-9)
    assert err[sat < 0.8].mean() < 2.5 and np.percentile(err[sat < 0.8], 99) < 10
    assert err.mean() < 4.0
    old = np.abs(env.srgb_encode(env.agx_three(x)) - want) * 255.0
    assert old.mean() > 2.5 * err.mean()


def _crane(kind):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    assert bpy.ops.fresing.import_step(filepath=CRANE, quality="draft") == {"FINISHED"}
    sc = bpy.context.scene
    if kind:
        from fresing_render.blender import world
        sc.fresing.background, sc.fresing.env_detail = kind, "SIMPLE"
        sc.fresing.sun_elevation = 30.0
        world.apply(sc, sc.fresing)
    return sc


def test_sea_page_gets_the_apps_sun_and_a_studio_page_its_pictures_colour(made, tmp_path):
    from fresing_render.blender import web3d_env
    sc = _crane("SEA")
    sc.fresing.web3d.env_mode = "PROJECT"
    out = web3d.export(sc, str(tmp_path / "sea.glb"), size=256, surroundings=web3d_env.choice(sc))
    sky = env.page_settings(open(out["html"], encoding="utf-8").read())["sky"]
    assert sky["kind"] == "SKY" and sky["sun_table"] == env.sun_table()
    rgb, k = env.sky_sun(30.0)
    assert rgb[0] > 3.0 * 3.2 and 0.5 < k < 0.9
    sc = _crane("")
    out = web3d.export(sc, str(tmp_path / "plain.glb"), size=256)
    sky = env.page_settings(open(out["html"], encoding="utf-8").read())["sky"]
    assert sky["kind"] == "PHOTO" and "sun_table" not in sky
    c = sky["sun_colour"]
    assert len(c) == 3 and float(np.dot(c, [0.2126, 0.7152, 0.0722])) == pytest.approx(1.0, abs=1e-2)
    assert max(c) - min(c) < 0.15                            # the app's studio light is near white
    assert math.isfinite(sum(c))
