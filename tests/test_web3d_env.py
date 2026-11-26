"""Web 3D model with surroundings (task 0106), no Blender: the page's settings block, the sea and vessel formulas in
Python and in the page's JavaScript (run by node), the pictures and the one-file page."""

import json
import math
import os
import re
import shutil
import subprocess

import numpy as np
import pytest

from fresing_render.core import web3d, web3d_env as env

HERE = os.path.dirname(os.path.abspath(__file__))
MATH_JS = os.path.join(web3d.WEB_DIR, env.MATH_FILE)
NODE = shutil.which("node")

# a sea and a vessel as the export writes them (numbers of the app's Calm sea + a swell, rounded)
SEA = {"state": "CALM", "level": 1.5, "origin": [3.0, -2.0], "near": 40.0, "own": 2, "bump": 0.12, "foam": 0.82,
       "moving": True,
       "waves": [[0.11, 0.70, 0.71, 2 * math.pi / 55, 1.3], [0.055, 0.96, -0.28, 2 * math.pi / 38, 4.0],
                 [0.4, -0.5, 0.866, 0.0625, 2.2]]}
VESSEL = {"pivot": [1.0, 2.0, 1.5], "heave": [0.0, [[0.2, 0.8, 1.0], [0.05, 1.1, 0.3]]],
          "roll": [0.0, [[0.02, 0.57, 2.0]]], "pitch": [0.0, [[-0.008, 0.9, 0.4], [0.003, 0.7, 5.0]]],
          "ends": [[-60.0, 2.0, 1.5], [64.0, 2.0, 1.5]], "hull": [124.0, 28.0]}


def _node(expr: str):
    """Evaluate ``expr`` with FRMath loaded in node; returns the JSON it prints."""
    code = f"const FRMath = require({json.dumps(MATH_JS)}); console.log(JSON.stringify({expr}));"
    out = subprocess.run([NODE, "-e", code], capture_output=True, text=True, timeout=60, check=True)
    return json.loads(out.stdout)


# ---------------------------------------------------------------------------
# the settings block
# ---------------------------------------------------------------------------

def test_settings_block_from_the_choice():
    ch = env.default_choice()
    ch.update(sea=True, sea_state="ROUGH", haze=True, haze_strength=0.5, rain=True, rain_strength=0.8,
              clouds="SOME", quality="PHONE", auto=False, shadows=False)
    st = env.settings(ch, [0, 0, 0], [10, 4, 3], sea=dict(SEA, state="ROUGH"), vessel=VESSEL,
                      sky={"kind": "SKY", "sun": env.sun_vector(30, 90)}, time_start=2.5)
    assert st["quality"] == "PHONE" and st["auto"] is False and st["shadows"] is False
    assert set(st["levels"]) == set(env.LEVELS)
    assert "sky" not in st["levels"]["BEST"] and st["levels"]["BEST"]["shadow"] > st["levels"]["PHONE"]["shadow"]
    assert st["sea"]["radius"] == env.SEA_RADIUS and st["vessel"] is VESSEL
    assert st["sky"]["clouds"] == "SOME"
    assert st["sky"]["elevation"] == pytest.approx(30) and st["sky"]["azimuth"] == pytest.approx(90)
    assert st["haze"]["strength"] == 0.5 and st["haze"]["density"] > 0
    assert st["rain"] == {"strength": 0.8, "spray": True}           # spray only on a rough sea
    assert st["time"]["start"] == 2.5
    json.dumps(st, allow_nan=False)


def test_items_off_leave_nothing_on_the_page():
    st = env.settings(env.default_choice(), [0, 0, 0], [1, 1, 1], sea=None, vessel=VESSEL)
    assert st["sea"] is None and st["vessel"] is None             # no vessel motion without a sea
    assert st["haze"] is None and st["rain"] is None
    assert env.items_text(st) == "sky, sun shadows"
    ch = dict(env.default_choice(), rain=True)
    assert env.settings(ch, [0, 0, 0], [1, 1, 1])["rain"]["spray"] is False          # no sea: no spray
    assert env.settings(dict(ch, quality="nonsense"), [0, 0, 0], [1, 1, 1])["quality"] == "BALANCED"


def test_haze_gets_thicker_and_follows_the_model_size():
    d = [env.haze_density(s, 2.0) for s in (0.0, 0.3, 0.7, 1.0)]
    assert d == sorted(d)
    assert 3.0 / d[0] == pytest.approx(20000.0)
    assert 3.0 / d[-1] == pytest.approx(150.0)                       # a small machine: at least 150 m
    assert 3.0 / env.haze_density(1.0, 124.0) == pytest.approx(496.0)


def test_sun_vector_matches_the_app_sky():
    """Measured with Cycles (task 0106): Rotate light 0 puts the sun of the app's sky at +y, 90 at +x."""
    assert env.sun_vector(0, 0) == pytest.approx([0, 1, 0], abs=1e-12)
    assert env.sun_vector(0, 90) == pytest.approx([1, 0, 0], abs=1e-12)
    assert env.sun_vector(90, 33) == pytest.approx([0, 0, 1], abs=1e-12)
    for el, rot in ((10, 0), (45, 135), (70, 300)):
        assert env.angles_of(env.sun_vector(el, rot)) == pytest.approx((el, rot))


# ---------------------------------------------------------------------------
# the sea and the vessel: Python == JavaScript
# ---------------------------------------------------------------------------

POINTS = [(0.0, 0.0, 0.0), (12.0, -7.0, 3.3), (39.0, 5.0, 10.0), (50.0, 0.0, 7.0), (70.0, 10.0, 1.0)]


def test_sea_height_python_formula():
    # one wave by hand, inside 'near'
    one = dict(SEA, waves=[SEA["waves"][0]])
    a, dx, dy, k, ph = one["waves"][0]
    x, y, t = 5.0, 2.0, 1.7
    assert env.sea_height(one, x, y, t) == pytest.approx(a * math.sin(k * (dx * x + dy * y) + ph - math.sqrt(9.81 * k) * t))
    assert env.sea_fade(40.0, 0, 0) == 1.0 and env.sea_fade(40.0, 64.0, 0) == 0.0
    assert env.sea_fade(40.0, 52.0, 0) == pytest.approx(0.5)


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_page_sea_and_vessel_equal_python():
    js = _node(f"(() => {{ const S = {json.dumps(SEA)}, V = {json.dumps(VESSEL)}; const P = {json.dumps(POINTS)};"
               " return {h: P.map(p => FRMath.seaHeight(S, p[0], p[1], p[2])),"
               "         c: P.map(p => FRMath.crest(S, p[0], p[1], p[2])),"
               "         ch: [0, 1.5, 7.25].map(t => FRMath.channel(V.heave, t)),"
               "         m: [0, 3.3, 11].map(t => FRMath.vesselMatrix(V, t)),"
               "         lv: FRMath.vesselMatrix(V, 3.3, 'LEVEL'), st: FRMath.vesselMatrix(V, 3.3, 'STILL')}; })()")
    for (x, y, t), h in zip(POINTS, js["h"]):
        assert h == pytest.approx(float(env.sea_height(SEA, x, y, t)), abs=1e-12)
    own = SEA["waves"][:2]
    for (x, y, t), c in zip(POINTS, js["c"]):
        ref = env.sea_height(dict(SEA, waves=own), x, y, t) / sum(w[0] for w in own)
        assert c == pytest.approx(float(ref), abs=1e-12)
    for t, v in zip((0, 1.5, 7.25), js["ch"]):
        assert v == pytest.approx(float(env.channel(VESSEL["heave"], t)), abs=1e-12)
    for t, m in zip((0, 3.3, 11), js["m"]):
        ref = env.vessel_matrix(VESSEL, t)
        assert np.allclose(np.array(m).reshape(4, 4).T, ref, atol=1e-12)
    lv = np.array(js["lv"]).reshape(4, 4).T
    assert np.allclose(lv[:3, :3], np.eye(3)) and lv[2, 3] == pytest.approx(float(env.channel(VESSEL["heave"], 3.3)))
    assert np.allclose(np.array(js["st"]).reshape(4, 4), np.eye(4))


def test_vessel_matrix_keeps_the_pivot_and_heaves_it():
    for t in (0.0, 2.0, 9.5):
        m = env.vessel_matrix(VESSEL, t)
        p = np.array(VESSEL["pivot"] + [1.0])
        moved = m @ p
        assert moved[:3] == pytest.approx(np.array(VESSEL["pivot"]) + [0, 0, float(env.channel(VESSEL["heave"], t))])
        assert np.allclose(m[:3, :3] @ m[:3, :3].T, np.eye(3))


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_page_scripts_parse():
    for name in (env.MATH_FILE, env.PAGE_FILE):
        out = subprocess.run([NODE, "--check", os.path.join(web3d.WEB_DIR, name)], capture_output=True, text=True)
        assert out.returncode == 0, out.stderr


# ---------------------------------------------------------------------------
# pictures
# ---------------------------------------------------------------------------

def _blender_picture(direction, w=256, h=128):
    """A Blender-layout equirect (rows bottom-up) with one bright spot towards ``direction`` (Blender world)."""
    u = (np.arange(w) + 0.5) / w
    v = (np.arange(h) + 0.5) / h
    U, V = np.meshgrid(u, v)
    lon = (U - 0.5) * 2 * math.pi            # Blender: u = atan2(y, -x) / 2pi + 0.5
    lat = (V - 0.5) * math.pi
    x, y, z = -np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)
    d = np.array(direction, float) / np.linalg.norm(direction)
    spot = (x * d[0] + y * d[1] + z * d[2]) > math.cos(math.radians(6))
    px = np.full((h, w, 4), 0.2, np.float32)
    px[spot, :3] = 50.0
    return px


@pytest.mark.parametrize("direction,rotation", [((0, 1, 0.5), 0.0), ((1, 0, 0.6), 0.0), ((-1, -1, 1), 0.0),
                                                ((0, 1, 0.5), 90.0)])
def test_light_picture_keeps_its_directions(direction, rotation):
    page = env.equirect_for_page(_blender_picture(direction), rotation, 256)
    assert page.shape == (128, 256, 3)
    sun, share = env.brightest(page)
    d = np.array(direction, float) / np.linalg.norm(direction)
    # the app's Mapping turns the looked-up vector by +rotation: the picture appears turned by -rotation
    r = math.radians(-rotation)
    want = np.array([math.cos(r) * d[0] - math.sin(r) * d[1], math.sin(r) * d[0] + math.cos(r) * d[1], d[2]])
    assert float(np.dot(sun, want)) > math.cos(math.radians(8))
    assert share > 5


def test_hdr_round_trip_and_size():
    rng = np.random.default_rng(3)
    px = (rng.random((16, 32, 3)) * 40).astype(np.float32)
    px[0, 0] = 0.0
    data = env.hdr_bytes(px)
    assert data.startswith(b"#?RADIANCE\nFORMAT=32-bit_rle_rgbe\n\n-Y 16 +X 32\n")
    back = env.read_hdr(data)
    # RGBE: one exponent per pixel, so every channel is exact to 1/256 of the pixel's brightest
    assert np.all(np.abs(back - px) <= px.max(axis=2, keepdims=True) / 128 + 1e-6)
    assert len(data) < 32 * 16 * 4 + 64


def test_agx_three_is_three_js_agx():
    """A few values of three.js r180's AgXToneMapping (worked out by hand from its GLSL): the page's curve before
    task 0369."""
    out = env.agx_three(np.array([[0.0, 0.0, 0.0], [0.18, 0.18, 0.18], [1.0, 1.0, 1.0], [100.0, 100.0, 100.0]]))
    assert out[0] == pytest.approx([0, 0, 0], abs=2e-3)
    assert 0.12 < out[1][0] < 0.25 and out[1][0] == pytest.approx(out[1][1], abs=1e-3)
    assert out[2][0] > out[1][0] and out[3][0] > 0.95
    assert np.all(np.diff(env.agx_three(np.linspace(0, 20, 50)[:, None].repeat(3, 1))[:, 0]) >= 0)


# Blender 5.2.3's AgX view with the look "AgX - Medium High Contrast" (the app's renders), measured with save_render:
# linear sRGB -> the screen's 0 … 255
APP_AGX = [((0.30, 0.24, 0.14), (151, 134, 103)), ((0.25, 0.08, 0.03), (137, 68, 20)), ((0.12, 0.06, 0.03), (88, 55, 30)),
           ((0.04, 0.06, 0.10), (40, 59, 80)), ((0.21, 0.21, 0.21), (128, 128, 128)), ((0.70, 0.05, 0.03), (211, 58, 27)),
           ((0.80, 0.60, 0.02), (204, 179, 79)), ((0.8, 0.8, 0.8), (199, 199, 199))]


def test_page_tone_is_the_apps_agx_look():
    """Task 0369: the page's tone curve gives the app's colours – sand, rust, brown and dark blue within a few of 255;
    three.js's own AgX (the page before) made the dark warm ones greyer and lighter."""
    x = np.array([c for c, _ in APP_AGX])
    want = np.array([w for _, w in APP_AGX], float)
    got = env.tone(x, encode=True) * 255.0
    err = np.abs(got - want)
    assert err[:5].max() <= 4, np.round(got)                  # dark warm, dark cool, mid grey
    assert err.max() <= 15, np.round(got)                     # bright saturated paint: the fit's hardest
    assert err.mean() <= 4
    old = env.srgb_encode(env.agx_three(x)) * 255.0
    assert np.abs(old[1:3] - want[1:3]).max() > 20           # rust and brown: why 0143's sand looked grey
    assert env.agx(x).dtype == np.float32 and np.allclose(env.agx(x), env.tone(x), atol=1e-6)
    ramp = env.tone(np.linspace(0, 30, 200)[:, None].repeat(3, 1))
    assert np.all(np.diff(ramp, axis=0) >= -1.0 / 255) and ramp[0].max() < 2e-3 and ramp[-1].min() > 0.95
    assert np.abs(ramp[:, 0] - ramp[:, 2]).max() < 0.01      # grey stays grey


def test_page_has_the_same_tone_numbers():
    """``web/fr_page.js`` writes ``FR_TONE`` into three's custom tone mapping: the same numbers as ``env.TONE``."""
    text = open(os.path.join(web3d.WEB_DIR, "fr_page.js"), encoding="utf-8").read()
    m = re.search(r"var FR_TONE = (\{.*?\});", text)
    assert m, "fr_page.js has no FR_TONE"
    js = json.loads(m.group(1))
    for k in ("m_in", "m_out", "poly"):
        assert np.allclose(np.array(js[k]), env.TONE[k], rtol=0, atol=1e-12), k
    for k in ("lo", "span", "gamma"):
        assert js[k] == pytest.approx(env.TONE[k], abs=1e-12), k
    assert "renderer.toneMapping = T.CustomToneMapping" in text and "vec3 CustomToneMapping( vec3 color ) {" in text


def test_sky_sun_follows_the_table():
    """Task 0369: the page sun's strength and the sky's light by the sun's height (``SKY_SUN``), as the page reads
    them (``sun_table``, interpolated between rows)."""
    rows = env.SKY_SUN
    assert [r[0] for r in rows] == sorted(r[0] for r in rows) and rows[0][0] == 0.0 and rows[-1][0] == 90.0
    for e, rgb, k in rows:
        got, sky = env.sky_sun(e)
        assert got == pytest.approx(rgb) and sky == pytest.approx(k)
        assert rgb[0] >= rgb[1] >= rgb[2] >= 0.0                # the sun is never bluer than white
    a, b = rows[3], rows[4]
    mid, sky = env.sky_sun((a[0] + b[0]) / 2)
    assert mid == pytest.approx([(x + y) / 2 for x, y in zip(a[1], b[1])]) and sky == pytest.approx((a[2] + b[2]) / 2)
    assert env.sky_sun(-5.0) == env.sky_sun(0.0) and env.sky_sun(120.0)[0] == pytest.approx(rows[-1][1])
    assert env.sun_table()[2] == [rows[2][0], *rows[2][1], rows[2][2]]
    # the old page sun: 3.2 x (1, 0.96, 0.9) from 15 degrees up – about a quarter of the app's at 35 degrees
    assert env.sky_sun(35.0)[0][0] > 3.0 * 3.2


def test_brightest_colour_is_the_spot_s_own():
    page = np.full((64, 128, 3), 0.2, np.float32)
    page[20, 40] = (30.0, 20.0, 10.0)
    c = env.brightest_colour(page)
    assert c[0] > c[1] > c[2]
    assert float(np.dot(c, [0.2126, 0.7152, 0.0722])) == pytest.approx(1.0, abs=1e-3)


# ---------------------------------------------------------------------------
# the page
# ---------------------------------------------------------------------------

def test_page_is_one_offline_file():
    st = env.settings(dict(env.default_choice(), sea=True), [0, 0, 0], [2, 1, 1], sea=SEA)
    page = env.page_html("Mill </script> & co", b"glTF-bytes", st, {"light": ("image/vnd.radiance", b"#?RAD")},
                         note="Made with Fresing Render", animated=True)
    back = env.page_settings(page)
    assert back["sea"]["near"] == 40.0 and back["animated"] is True
    assert "FRTHREE" in page and "FRMath" in page and "frPage" in page
    assert 'id="fr-glb"' in page and 'id="fr-pic-light"' in page
    assert "Mill &lt;/script&gt; &amp; co" in page
    # nothing from the internet: no src/href to http(s), no import of a module by URL
    assert not re.search(r"""(src|href)=["']https?:""", page)
    assert not re.search(r"""import\s*\(?\s*["']https?:""", page)
    # every inline script is closed only by its own end tag
    assert page.count("<script") == page.count("</script>")


def test_settings_block_escapes_every_lt():
    """Task 0161 (0147 row 15): a camera name with "<!--" and then "<script" (Hide part names off) left the settings
    block open in the browser (script data double-escaped state): the page stayed at "Loading the 3D model …"."""
    st = env.settings(env.default_choice(), [0, 0, 0], [2, 1, 1])
    st["views"] = [{"name": "<!-- <script", "eye": [1, 2, 3], "target": [0, 0, 0], "vfov": 30, "hfov": 50},
                   {"name": "a </script> b <", "eye": [1, 2, 3], "target": [0, 0, 0], "vfov": 30, "hfov": 50}]
    page = env.page_html("M", b"glTF", st)
    start = page.index('id="fr-env">') + len('id="fr-env">')
    block = page[start:page.index("</script>", start)]
    assert "<" not in block
    assert [v["name"] for v in env.page_settings(page)["views"]] == ["<!-- <script", "a </script> b <"]
    assert json.loads(block)["views"][0]["name"] == "<!-- <script"      # what JSON.parse in the page reads


def test_model_viewer_page_stays_for_the_site():
    """Task 0134: the exports all use the player; model-viewer's page stays for a bare .glb on the website."""
    plain = web3d.viewer_html("M", glb=b"x", script_text="/*mv*/")
    assert "model-viewer" in plain and "FRTHREE" not in plain


def test_three_bundle_is_shipped_with_its_licence():
    for f in env.SCRIPTS + ("LICENSE-three.txt",):
        assert os.path.exists(os.path.join(web3d.WEB_DIR, f)), f
    head = open(os.path.join(web3d.WEB_DIR, env.THREE_FILE), encoding="utf-8").read(400)
    assert "three.js r180" in head and "MIT" in head
    assert env.THREE_VERSION.split(".")[1] == "180"
    readme = open(os.path.join(web3d.WEB_DIR, "README.txt"), encoding="utf-8").read()
    assert env.THREE_FILE in readme and "MIT" in readme
