"""The web 3D player (task 0134), no Blender: every page the export writes – "no graphics card" warning, drawing only
on a change, at most 60 pictures a second, the Auto fix (a hidden tab or a frozen page is not a slow picture; Auto
steps up again), the settings menu, remembered choices, playback, saved views, the view tools, the clean look and the
loading bar – driven in headless Chromium by ``tools/web_player_probe.js``.

Headless Chromium draws with SwiftShader: the page sees no graphics card and says so; ``soft=0`` in the address makes
it test the rest as if it had one. GitHub's Linux runner cannot start Chromium (task 0106): there the scripts are
checked by node and the page's text instead (each pytest group on GitHub allows only one skipped test).
"""

import functools
import json
import os
import shutil
import subprocess

import numpy as np
import pytest

from fresing_render.core import web3d, web3d_env as env

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROBE = os.path.join(ROOT, "tools", "web_player_probe.js")
NODE = shutil.which("node")
VIEWS = [{"name": "Front", "eye": [1.5, -8.0, 1.0], "target": [1.5, 0.0, 0.3], "vfov": 25.0, "hfov": 40.0},
         {"name": "Top", "eye": [1.5, 0.0, 9.0], "target": [1.5, 0.01, 0.0], "vfov": 30.0, "hfov": 45.0}]


def model(animated=True) -> bytes:
    """Two grey quads side by side (three's y = 0); with an animation the second one bobs for 4 s."""
    g = web3d.Gltf()
    look = g.material({"pbrMetallicRoughness": {"baseColorFactor": [0.5, 0.5, 0.5, 1.0], "metallicFactor": 0.0,
                                                "roughnessFactor": 0.9}})
    pos = np.array([[-1, 0, -1], [1, 0, -1], [1, 0, 1], [-1, 0, 1]], float)
    nrm = np.tile(np.array([[0, 127, 0]], np.int8), (4, 1))
    mesh = g.mesh("part", pos, nrm, None, [(look, np.array([[0, 2, 1], [0, 3, 2]]))], quantize=False)
    g.node({"mesh": mesh, "translation": [0.0, 0.0, 0.0]})
    g.node({"mesh": mesh, "translation": [3.0, 0.0, 0.0]})
    if animated:
        times = np.linspace(0, 4, 9)
        g.animation("Anim", times, [(1, "translation", np.array([[3.0, 0.5 * np.sin(t), 0.0] for t in times]))])
    return g.glb()


SEA = {"state": "CALM", "level": -0.5, "origin": [0.0, 0.0], "near": 50.0, "waves": [[0.2, 1.0, 0.0, 0.3, 0.0]],
       "own": 1, "bump": 0.3, "foam": None, "moving": True}


def write(path, kind="plain", animated=True, light=None, views=VIEWS, shadows=False, auto=True, quality="BALANCED"):
    sea = kind == "sea"
    ch = dict(env.default_choice(), shadows=shadows, auto=auto, quality=quality, sea=sea, haze=sea, rain=sea)
    st = env.settings(ch, [-1.0, -1.0, 0.0], [4.0, 1.0, 0.6], sky={"kind": "SKY", "sun": env.sun_vector(40, 30)},
                      plain=kind == "plain", sea=SEA if sea else None, light=light)
    st["views"] = views
    glb = model(animated)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(env.page_html("Player test", glb, st, animated=animated, note="Made with Fresing Render"))
    return str(path), len(glb)


_WORKS: dict = {}


def _browser_works(tmp_dir) -> bool:
    if "ok" not in _WORKS:
        ok = False
        if NODE:
            try:
                path, _n = write(os.path.join(str(tmp_dir), "works.html"))
                ok = probe(path, [])["ok"]
            except Exception:  # noqa: BLE001 - no Playwright, no Chromium: the scripts are checked by node
                ok = False
        _WORKS["ok"] = ok
    return _WORKS["ok"]


def browser_test(fn):
    @functools.wraps(fn)
    def run(tmp_path):
        if _browser_works(tmp_path):
            return fn(tmp_path)
        for name in env.SCRIPTS[1:]:
            text = open(os.path.join(web3d.WEB_DIR, name), encoding="utf-8").read()
            assert text in env.page_html("x", b"x", env.settings(env.default_choice(), [0, 0, 0], [1, 1, 1]))
            if NODE:
                subprocess.run([NODE, "--check", os.path.join(web3d.WEB_DIR, name)], check=True)
    return run


def probe(path, steps, query="", size="900x600", mobile=False, timeout=240):
    args = [NODE, PROBE, path, json.dumps(steps), f"--size={size}"] + ([f"--query={query}"] if query else [])
    if mobile:
        args.append("--mobile")
    r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert "error" not in out, out
    return out


# ---------------------------------------------------------------------------
# the page's text (no browser)
# ---------------------------------------------------------------------------

def test_page_has_the_player_and_its_loading_bar():
    path_text = env.page_html("T", b"glTF-bytes", env.settings(env.default_choice(), [0, 0, 0], [1, 1, 1]),
                              {"light": ("image/vnd.radiance", b"#?RAD")})
    for name in env.SCRIPTS:
        assert web3d_env_inline(name) in path_text, name
    assert path_text.index("fr_page") < path_text.index("fr_player") or "frPage" in path_text
    assert 'id="fr-glb" data-bytes="10"' in path_text and 'data-bytes="5"' in path_text   # the bar's total
    assert 'id="loadbar"' in path_text and "Loading the 3D model" in path_text
    st = env.page_settings(path_text)
    assert all("pixels" in st["levels"][k] for k in env.LEVELS)
    assert st["levels"]["PHONE"]["pixels"] < st["levels"]["BALANCED"]["pixels"] < st["levels"]["BEST"]["pixels"]


def web3d_env_inline(name):
    return env._inline(env._read(name))


def test_scripts_parse():
    if not NODE:
        pytest.skip("no node")
    for name in (env.PAGE_FILE, env.PLAYER_FILE, "fr_math.js"):
        subprocess.run([NODE, "--check", os.path.join(web3d.WEB_DIR, name)], check=True)
    subprocess.run([NODE, "--check", PROBE], check=True)


# ---------------------------------------------------------------------------
# 1 the "no graphics card" warning
# ---------------------------------------------------------------------------

@browser_test
def test_software_drawing_is_named_and_the_page_goes_light(tmp_path):
    path, _n = write(tmp_path / "p.html", shadows=True)
    out = probe(path, [{"eval": "getComputedStyle(document.getElementById('fr-warn')).display"},
                       {"eval": "document.getElementById('fr-warn').textContent"},
                       {"click": "#fr-warn button"},
                       {"eval": "getComputedStyle(document.getElementById('fr-warn')).display"}])
    st = out["state"]
    assert out["ok"], out
    assert st["warned"] == "software" and "SwiftShader" in st["gpu"]
    assert st["level"] == "PHONE" and st["cap"] == 30 and st["on"]["shadows"] is False      # its lightest
    assert out["out"][0] == "flex" and "chrome://restart" in out["out"][1] and "edge://restart" in out["out"][1]
    assert out["out"][3] == "none"                                                          # Hide
    # a graphics card (soft=0: as if): no bar, the export's quality and shadows
    out = probe(path, [{"eval": "getComputedStyle(document.getElementById('fr-warn')).display"}], query="soft=0")
    assert out["state"]["warned"] == "" and out["out"][0] == "none" and out["state"]["cap"] == 60
    assert out["state"]["level"] == "BALANCED" and out["state"]["on"]["shadows"] is True
    # the link's own quality wins over the lightest settings
    assert probe(path, [], query="quality=BEST&auto=0")["state"]["level"] == "BEST"


# ---------------------------------------------------------------------------
# 2 lighter: no picture while nothing moves, at most 60 a second, pixels capped, the Auto fix
# ---------------------------------------------------------------------------

@browser_test
def test_nothing_drawn_while_nothing_moves(tmp_path):
    path, _n = write(tmp_path / "still.html", animated=False)
    out = probe(path, [{"wait": 1500}, {"frames": 2500}, {"drag": [400, 300, 520, 330]}, {"frames": 400},
                       {"wait": 2500}, {"frames": 2000}], query="soft=0")
    assert out["ok"], out
    assert out["out"][1] == 0, "a still page must draw nothing"
    assert out["out"][3] > 3, "a drag must draw"
    assert out["out"][5] == 0, "nothing again once the turn has settled"
    # an animation that is paused draws nothing either; playing draws, never above 60 a second
    path, _n = write(tmp_path / "anim.html")
    out = probe(path, [{"wait": 1500}, {"frames": 2000}, {"key": " "}, {"wait": 300}, {"frames": 2000}],
                query="soft=0", size="320x240")
    assert 30 <= out["out"][1] <= 2 * 61, out["out"]
    assert out["out"][4] == 0 and out["state"]["paused"] is True


@browser_test
def test_pixels_are_capped_by_count(tmp_path):
    path, _n = write(tmp_path / "p.html", animated=False)
    out = probe(path, [{"eval": "frPage.setQuality('PHONE')"}, {"wait": 300},
                       {"eval": "frPage.info.pixels"}, {"eval": "frPage.setQuality('BEST')"}, {"wait": 300},
                       {"eval": "frPage.info.pixels"}], query="soft=0", size="2560x1440")
    phone, best = out["out"][2], out["out"][5]
    assert phone <= env.QUALITY["PHONE"]["pixels"] * 1.01 and phone < 2560 * 1440
    assert best <= env.QUALITY["BEST"]["pixels"] * 1.01 and best >= 2560 * 1440


@browser_test
def test_a_hidden_tab_or_a_frozen_page_is_not_slow_and_auto_steps_up_again(tmp_path):
    """The owner's "Quality Phone: lowered to keep it smooth" after leaving and coming back (task 0134): the time a
    tab was hidden (or the page frozen) counted as one slow picture. Measured before the fix with this test's page:
    lowered 1, level PHONE after a 3 s hidden tab or freeze."""
    path, _n = write(tmp_path / "p.html")
    out = probe(path, [{"wait": 3500}, {"eval": "frPage.lowered"}, {"hidden": 3000}, {"wait": 3500},
                       {"freeze": 3000}, {"wait": 3500}, {"eval": "[frPage.lowered, frPage.level]"}],
                query="quality=BALANCED&soft=0", size="320x240")
    assert out["ok"], out
    assert out["out"][1] == 0, "the page is too slow here even without leaving it"
    assert out["out"][2] == 0 and out["out"][4] == 0, "pictures drawn while hidden or frozen"
    assert out["out"][6] == [0, "BALANCED"]
    # Auto comes back up when there is room again (one step at a time, never above where it started)
    out = probe(path, [{"wait": 2500}, {"eval": "frPage.setLevel('PHONE')"}, {"wait": 9000}],
                query="quality=BALANCED&soft=0", size="320x240")
    assert out["state"]["level"] == "BALANCED" and out["state"]["raised"] >= 1, out["state"]


# ---------------------------------------------------------------------------
# 3 the settings menu and remembered choices
# ---------------------------------------------------------------------------

@browser_test
def test_settings_menu(tmp_path):
    path, _n = write(tmp_path / "sea.html", kind="sea", shadows=True)
    out = probe(path, [
        {"click": "#fr-tools button"},                                                        # the gear
        {"eval": "frPage.menuOpen"},
        {"eval": "[...document.querySelectorAll('#fr-menu input[data-item]')].map(e => e.dataset.item)"},
        {"click": "#fr-menu input[data-item=sea]"},
        {"eval": "frPage.on.sea"},
        {"click": "#fr-menu [data-quality=PHONE]"},
        {"eval": "[frPage.auto, frPage.level, frPage.quality]"},
        {"wait": 4500, "eval": None},
        {"eval": "document.getElementById('fr-menu').textContent"},
        {"eval": "document.getElementById('fr-sun').disabled"},
        {"eval": "frPage.setSunHour(18, true), frPage.sunHour"},
        {"click": "#fr-turn"},
        {"eval": "frPage.turn"},
        {"reload": True},
        {"eval": "[frPage.on.sea, frPage.level, frPage.auto, frPage.turn]"},                  # remembered
        {"click": "#fr-tools button"}, {"click": "#fr-forget"},
        {"eval": "[frPage.on.sea, frPage.quality, frPage.turn]"},
        {"reload": True},
        {"eval": "[frPage.on.sea, frPage.quality]"},
    ], query="soft=0", size="480x640")
    assert out["ok"], out
    o = out["out"]
    assert o[1] is True
    assert o[2] == ["sea", "sky", "haze", "rain", "shadows"]
    assert o[4] is False
    assert o[6] == [False, "PHONE", "PHONE"]
    assert "pictures a second" in o[8] and "SwiftShader" in o[8] and "Auto-turn" in o[8]
    assert o[9] is False and o[10] == 18                                       # live light: the sun moves
    assert o[12] is True
    assert o[14] == [False, "PHONE", False, True]
    assert o[17] == [True, "AUTO", False] and o[19] == [True, "AUTO"]


@browser_test
def test_sun_is_greyed_with_baked_light_and_auto_turn_waits(tmp_path):
    path, _n = write(tmp_path / "baked.html", light={"light": "SOFT", "scale": 1.0, "curve": 2.0}, animated=False)
    out = probe(path, [{"key": "m"}, {"eval": "document.getElementById('fr-sun').disabled"},
                       {"eval": "document.getElementById('fr-menu').textContent"},
                       {"key": "Escape"},
                       {"eval": "frPage.setTurn(true)"}, {"wait": 4000}, {"eval": "frPage.turning"},
                       {"wait": 5000}, {"eval": "frPage.turning"}, {"frames": 1000},
                       {"drag": [400, 300, 450, 300]}, {"eval": "frPage.turning"}], query="soft=0", size="480x360")
    o = out["out"]
    assert out["state"]["sunLive"] is False and o[1] is True and "Light is baked into this model" in o[2]
    assert o[6] is False and o[8] is True and o[9] > 5                          # starts after ~8 s, then draws
    assert o[11] is False                                                       # the first touch stops it


# ---------------------------------------------------------------------------
# 4 playback, 5 saved views, 6 view tools, 7 clean look, 8 loading bar
# ---------------------------------------------------------------------------

@browser_test
def test_playback(tmp_path):
    path, n = write(tmp_path / "anim.html")
    out = probe(path, [{"key": " "}, {"eval": "frPage.paused"}, {"key": " "}, {"eval": "frPage.paused"},
                       {"key": " "}, {"eval": "frPage.setTime(1.25), frPage.time"},
                       {"eval": "+document.getElementById('fr-slider').value"},
                       {"key": "ArrowRight"}, {"eval": "frPage.time"},
                       {"key": " "}, {"click": "#fr-playbar [aria-label='Speed 2']"}, {"eval": "frPage.speed"},
                       {"eval": "frPage.time"}, {"wait": 1500}, {"eval": "frPage.time"},
                       {"eval": "frPage.duration"}], query="soft=0", size="480x360")
    o = out["out"]
    assert out["ok"], out
    assert o[1] is True and o[3] is False
    assert o[5] == 1.25 and abs(o[6] - 1.25) < 0.02 and abs(o[8] - 3.25) < 1e-6
    assert o[11] == 2 and o[14] - o[12] > 1.6                                  # twice as fast (1.5 s of real time)
    assert o[15] == 4


@browser_test
def test_saved_views_and_view_tools(tmp_path):
    path, _n = write(tmp_path / "anim.html", shadows=True)
    out = probe(path, [
        {"eval": "[...document.querySelectorAll('#fr-views button')].map(b => b.textContent)"},
        {"key": "1"}, {"wait": 3000}, {"eval": "frPage.cameraState()"},
        {"key": " "}, {"eval": "frPage.setTime(2.5)"}, {"eval": "frPage.setItem('shadows', false)"},
        {"key": "l"}, {"eval": "frPage.lastLink"},
        {"key": "s"}, {"eval": "frPage.lastScreenshot"},
        {"key": "?"}, {"eval": "[frPage.helpOpen, document.getElementById('fr-help').textContent]"}, {"key": "Escape"},
        {"key": "h"}, {"eval": "[getComputedStyle(document.getElementById('fr-tools')).display, "
                               "getComputedStyle(document.getElementById('fr-show')).display, "
                               "getComputedStyle(document.querySelector('header')).display]"},
        {"key": "h"}, {"eval": "getComputedStyle(document.getElementById('fr-tools')).display"},
        {"key": "r"}, {"wait": 3000}, {"eval": "frPage.cameraState()"},
        {"key": "f"}, {"wait": 300}, {"eval": "!!document.fullscreenElement"},
    ], query="soft=0", size="900x600")
    o = out["out"]
    assert out["ok"], out
    assert o[0] == ["Front", "Top"]
    cam = o[3]
    assert np.allclose(cam["pos"], [1.5, 1.0, 8.0], atol=1e-3) and np.allclose(cam["target"], [1.5, 0.3, 0.0], atol=1e-3)
    assert cam["fov"] >= 25.0 - 1e-6                                           # at least the render's frame
    link = o[8]
    assert "orbit=" in link and "at=1.500,0.300,0.000" in link and "time=2.50" in link and "paused=1" in link
    assert "off=shadows" in link
    assert o[10] > 1000                                                        # a PNG data address
    assert o[12][0] is True and "Space" in o[12][1] and "fullscreen" in o[12][1]
    assert o[15][0] == "none" and o[15][1] != "none" and o[15][2] == "none" and o[17] != "none"
    assert np.allclose(o[20]["target"], [1.5, 0.3, 0.0], atol=1e-3)            # Reset: the model's middle
    assert o[23] is True
    # the link opens the same view, moment and choices
    q = link.split("?", 1)[1]
    back = probe(path, [{"eval": "frPage.cameraState()"}], query=q + "&soft=0")
    assert np.allclose(back["out"][0]["pos"], cam["pos"], atol=2e-3)
    assert back["state"]["paused"] is True and abs(back["state"]["time"] - 2.5) < 1e-6
    assert back["state"]["on"]["shadows"] is False


@browser_test
def test_loading_bar_counts_the_model(tmp_path):
    path, n = write(tmp_path / "anim.html")
    out = probe(path, [{"eval": "getComputedStyle(document.getElementById('loading')).display"}])
    assert out["state"]["load"] == {"got": n, "all": n}
    assert out["out"][0] == "none"


@browser_test
def test_phone_sized_window(tmp_path):
    """Phone quality on a phone-sized window (390 x 844, 3 device pixels per point): loads, draws, no error."""
    path, _n = write(tmp_path / "sea.html", kind="sea", quality="PHONE")
    out = probe(path, [{"frames": 2000}, {"eval": "[frPage.info.pixels, frPage.info.pixelRatio]"}], size="390x844",
                mobile=True)
    assert out["ok"], out
    assert out["state"]["level"] == "PHONE" and out["out"][0] > 0
    assert out["out"][1][0] <= env.QUALITY["PHONE"]["pixels"] * 1.01


@browser_test
def test_selftest_for_the_pc_check(tmp_path):
    path, _n = write(tmp_path / "anim.html")
    st = env.read_page(path, query="selftest=1&soft=0")
    assert st["state"].startswith("ready")
    assert st["selftest"]["ok"] and st["selftest"]["space"] is True and st["selftest"]["menu"]
    # under software drawing the page says so
    st = env.read_page(path, query="selftest=1")
    assert st["player"]["warned"] == "software" and st["selftest"]["warned"] == "software"
