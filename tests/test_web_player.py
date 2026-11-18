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
    import gzip
    return str(path), len(gzip.compress(glb, 9, mtime=0))     # task 0175: the page holds (and the bar counts) it packed


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
    import gzip
    packed = len(gzip.compress(b"glTF-bytes", 9, mtime=0))           # task 0175: the bar counts the packed model
    assert f'id="fr-glb" data-bytes="{packed}"' in path_text and 'data-bytes="5"' in path_text   # the bar's total
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
        {"eval": "[...document.querySelectorAll('#fr-views .fr-vbtn')].map(b => b.textContent)"},
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


# ---------------------------------------------------------------------------
# task 0179: a phone – one views control, one bottom stack, nothing on top of anything, the model in the free area
# ---------------------------------------------------------------------------

LONG = ["Shot 1: the whole vessel", "Shot 2: cable from the carousel", "Shot 3: carousel and arch",
        "Shot 4: tensioners squeezing", "Shot 5: chute and the stern", "Shot 6: handling winch drum, depth of field"]
PHONES = ["360x780", "390x844", "412x915", "844x390"]          # the owner's phone first; the last one held sideways
WIDE = ["768x1024", "1366x768", "1920x1080"]


def views_of(n: int, names=None) -> list[dict]:
    names = names or [LONG[k] if k < len(LONG) else f"Shot {k + 1}: camera {k + 1} over the deck" for k in range(n)]
    return [{"name": names[k], "eye": [1.5 + 0.3 * k, -8.0, 1.0 + 0.2 * k], "target": [1.5, 0.0, 0.3], "vfov": 25.0,
             "hfov": 40.0} for k in range(n)]


CHECK = "frPage.layoutCheck()"
SAFE = ("(function () { var s = document.documentElement.style; s.setProperty('--sa-t', '28px'); "
        "s.setProperty('--sa-b', '24px'); s.setProperty('--sa-l', '0px'); s.setProperty('--sa-r', '0px'); "
        "frPage.layout(); return frPage.layoutCheck(); })()")
# the model's box and the camera's aim on the screen, against the free area
FRAME = ("(function () { var t = frPage.three, c = t.camera, b = t.box, W = innerWidth, H = innerHeight;"
         " function s(v) { v = v.clone().project(c); return [(v.x + 1) / 2 * W, (1 - v.y) / 2 * H]; }"
         " var pts = [], k; for (k = 0; k < 8; k++) pts.push(s(new t.T.Vector3(k & 1 ? b.max.x : b.min.x,"
         " k & 2 ? b.max.y : b.min.y, k & 4 ? b.max.z : b.min.z)));"
         " return { aim: s(t.controls.target), pts: pts, free: frPage.freeArea() }; })()")


def _no_overlaps(check, what):
    assert check["overlaps"] == [], (what, check["overlaps"])
    assert check["outside"] == [], (what, check["outside"], check["safe"])
    assert check["small"] == [], (what, check["small"])


@browser_test
def test_no_two_controls_overlap_at_any_size(tmp_path):
    """Every tested screen (the owner's phone 360 x 780 first, sideways, tablet, laptop, big screen) with 0, 1, 3, 9 and
    21 saved views, animated and still: no two visible controls overlap, all lie inside the screen minus the safe
    areas (also with a notch and a gesture bar), buttons are at least 40 px; the hint and a message neither."""
    for n in (0, 1, 3, 9, 21):
        for animated in (True, False):
            path, _n = write(tmp_path / f"v{n}{'a' if animated else 's'}.html", animated=animated, views=views_of(n))
            for sizes, mobile in ((PHONES, True), (WIDE, False)):
                steps = []
                for size in sizes:
                    steps += [{"size": size}, {"eval": CHECK},
                              {"eval": "frPage.notify('Quality Phone: lowered to keep it smooth', 8), frPage.layoutCheck()"},
                              {"eval": "frPage.notify(''), " + CHECK}]
                steps += [{"eval": SAFE}]
                out = probe(path, steps, size=sizes[0], mobile=mobile, query="soft=0")
                assert out["ok"], out
                for k, size in enumerate(sizes):
                    for j in (1, 2, 3):
                        c = out["out"][4 * k + j]
                        what = (n, animated, size, j)
                        _no_overlaps(c, what)
                        assert c["size"] == [int(x) for x in size.split("x")], what
                        if j == 2:
                            assert "message" in c["items"], what           # shown, and on top of nothing
                        assert ("play bar" in c["items"]) == animated, what
                        assert c["mode"] == ("none" if n == 0 else c["mode"]), what
                        if size == "360x780" and n > 3:
                            assert c["mode"] == "pill" and c["tools"] <= 5, what
                        if size in WIDE and n > 1:
                            assert c["mode"] == "row", what
                safe = out["out"][-1]
                _no_overlaps(safe, (n, animated, "safe areas"))
                assert safe["safe"]["t"] == 28 and safe["safe"]["b"] == 24


@browser_test
def test_saved_views_as_one_control_on_a_phone(tmp_path):
    """The owner's screenshot: 21 views as six rows of buttons over the model. Upright: one pill ‹ name ›, the arrows
    step, the name opens the list (current one marked; closes on a pick, a tap outside, Esc or Back); keys 1 … 9."""
    path, _n = write(tmp_path / "v21.html", views=views_of(21))
    pill = "[...document.querySelectorAll('#fr-views > button')].map(b => b.getAttribute('aria-label'))"
    name = "document.querySelector('#fr-views .fr-vname .fr-txt').textContent"
    out = probe(path, [
        {"eval": "[frPage.viewMode, " + pill + "]"},
        {"click": "#fr-views [aria-label='Next view']"}, {"eval": "[frPage.currentView(), " + name + "]"},
        {"click": "#fr-views [aria-label='Previous view']"}, {"wait": 50},
        {"eval": "[frPage.currentView(), " + name + "]"},
        {"click": "#fr-views .fr-vname"},
        {"eval": "[frPage.listOpen, document.querySelectorAll('#fr-vlist li').length, "
                 "document.querySelector('#fr-vlist [aria-current]').dataset.view]"},
        {"click": "#fr-vlist [data-view='4']"}, {"wait": 1200},
        {"eval": "[frPage.listOpen, frPage.currentView(), " + name + ", frPage.cameraState().target]"},
        {"click": "#fr-views .fr-vname"}, {"tap": [180, 100]}, {"eval": "frPage.listOpen"},
        {"click": "#fr-views .fr-vname"}, {"back": True}, {"eval": "[frPage.listOpen, location.href.indexOf('v21.html') > 0]"},
        {"click": "#fr-views .fr-vname"}, {"key": "Escape"}, {"eval": "frPage.listOpen"},
        {"key": "7"}, {"eval": "[frPage.currentView(), " + name + "]"},
        {"eval": "document.querySelector('#fr-views .fr-vname .fr-txt').scrollWidth > "
                 "document.querySelector('#fr-views .fr-vname .fr-txt').clientWidth || "
                 "document.querySelector('#fr-views .fr-vname').getBoundingClientRect().width < 360"},
    ], size="360x780", mobile=True, query="soft=0")
    assert out["ok"], out
    o = out["out"]
    assert o[0] == ["pill", ["Previous view", "Show all 21 saved views", "Next view"]]
    assert o[2] == [0, LONG[0]]
    assert o[5] == [20, "Shot 21: camera 21 over the deck"]                  # steps round
    assert o[7] == [True, 21, "20"]
    assert o[10][:3] == [False, 4, LONG[4]] and np.allclose(o[10][3], [1.5, 0.3, 0.0], atol=1e-3)
    assert o[13] is False and o[16] == [False, True] and o[19] is False
    assert o[21] == [6, "Shot 7: camera 7 over the deck"]


@browser_test
def test_saved_views_as_one_row_on_wide_screens(tmp_path):
    """Wide screens and a phone sideways: one row that never wraps; when it does not fit it scrolls sideways and All
    views opens the same list; a few short views on a phone stay buttons; one view is one button; none: nothing."""
    row = ("(function () { var b = [...document.querySelectorAll('#fr-views .fr-vbtn')], s = document.querySelector('#fr-views .fr-vscroll');"
           " var all = document.querySelector('#fr-views .fr-all');"
           " return [frPage.viewMode, b.length, new Set(b.map(x => Math.round(x.getBoundingClientRect().top))).size,"
           " s ? s.scrollWidth > s.clientWidth : null, !!all && getComputedStyle(all).display !== 'none']; })()")
    path, _n = write(tmp_path / "v21.html", views=views_of(21))
    out = probe(path, [{"eval": row}, {"click": "#fr-views .fr-all"}, {"eval": "frPage.listOpen"},
                       {"click": "#fr-vlist [data-view='12']"}, {"eval": "frPage.currentView()"},
                       {"eval": "(function () { var s = document.querySelector('#fr-views .fr-vscroll'), "
                                "b = s.children[12].getBoundingClientRect(), r = s.getBoundingClientRect();"
                                " return b.left >= r.left - 1 && b.right <= r.right + 1; })()"},
                       {"size": "844x390"}, {"eval": row}], size="1366x768", query="soft=0")
    assert out["ok"], out
    o = out["out"]
    assert o[0] == ["row", 21, 1, True, True]
    assert o[2] is True and o[4] == 12 and o[5] is True                      # the picked one scrolled into sight
    assert o[7] == ["row", 21, 1, True, True]
    short = views_of(3, ["Front", "Top", "Side"])
    for views, want in ((short, ["row", 3, 1, False, False]), (views_of(3), None), (views_of(1), ["row", 1, 1, False, False]),
                        ([], ["none", 0, 0, None, False])):
        path, _n = write(tmp_path / f"n{len(views)}.html", views=views)
        out = probe(path, [{"eval": row}], size="360x780", mobile=True, query="soft=0")
        if want is None:
            assert out["out"][0][0] == "pill"                                # three long names do not fit
        else:
            assert out["out"][0] == want, (views, out["out"][0])


@browser_test
def test_the_model_starts_in_the_free_area(tmp_path):
    """The start view is framed in the rectangle the header and the bottom stack leave free, and again after the phone
    is turned; a saved view's aim is that rectangle's middle."""
    path, _n = write(tmp_path / "v21.html", views=views_of(21))
    out = probe(path, [{"eval": FRAME}, {"eval": CHECK}, {"size": "844x390"}, {"wait": 300}, {"eval": FRAME},
                       {"key": "2"}, {"wait": 1300}, {"eval": FRAME}], size="360x780", mobile=True, query="soft=0")
    assert out["ok"], out
    o = out["out"]
    for f in (o[0], o[4]):
        fr = f["free"]
        assert abs(f["aim"][0] - (fr["left"] + fr["width"] / 2)) < 1.5
        assert abs(f["aim"][1] - (fr["top"] + fr["height"] / 2)) < 1.5
        for x, y in f["pts"]:                                                # the whole model inside it
            assert fr["left"] - 1 <= x <= fr["left"] + fr["width"] + 1, (x, fr)
            assert fr["top"] - 1 <= y <= fr["top"] + fr["height"] + 1, (y, fr)
    head = o[1]
    assert o[0]["free"]["top"] > 20 and o[0]["free"]["top"] + o[0]["free"]["height"] < 780 - 80   # header, stack
    assert abs(o[7]["aim"][1] - (o[7]["free"]["top"] + o[7]["free"]["height"] / 2)) < 1.5
    assert head["overlaps"] == []


@browser_test
def test_phone_header_hint_tools_and_long_press(tmp_path):
    """Upright: the title on one line (full in the help), the hint only on the first visit until the first touch,
    at most 5 buttons a column (the rarer ones under More tools, which work from there), a long press on a button
    names it and does not press it, the help lists every button; the quality note is a short message."""
    title = "Demo cable-lay vessel 0.2.133 web 3D with a very long name"
    path = str(tmp_path / "long.html")
    st = env.settings(dict(env.default_choice(), sea=False, haze=False, rain=False), [-1, -1, 0], [4, 1, 0.6],
                      sky={"kind": "SKY", "sun": env.sun_vector(40, 30)}, plain=True)
    st["views"] = views_of(21)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(env.page_html(title, model(True), st, animated=True, note="Made with Fresing Render"))
    h1 = ("(function () { var h = document.querySelector('header h1'), r = h.getBoundingClientRect();"
          " return [r.height < 30, h.scrollWidth > h.clientWidth]; })()")
    shown = "getComputedStyle(document.getElementById('fr-first')).display"
    folded = "[...document.querySelectorAll('#fr-tools .fr-folded')].map(b => b.getAttribute('aria-label'))"
    out = probe(path, [
        {"eval": h1}, {"eval": shown}, {"eval": folded},
        {"eval": "[...document.querySelectorAll('#fr-tools > .fr-btn')].filter(b => getComputedStyle(b).display !== 'none').length"},
        {"touchon": ["#fr-tools [aria-label='Reset view']", 700]}, {"wait": 100},
        {"eval": "[frPage.lastTip, getComputedStyle(document.getElementById('fr-tip')).display, frPage.input && 1]"},
        {"wait": 600}, {"eval": shown},
        {"click": "#fr-more-btn"},
        {"eval": "[...document.querySelectorAll('#fr-more .fr-btn span')].map(s => s.textContent)"},
        {"click": "#fr-more .fr-btn:last-child"}, {"eval": "frPage.clean"}, {"key": "h"},
        {"key": "?"}, {"eval": "document.getElementById('fr-help').textContent"}, {"key": "Escape"},
        {"eval": "frPage.notify('Quality Phone: lowered to keep it smooth', 8), "
                 "[getComputedStyle(document.getElementById('fr-toast')).display, "
                 "getComputedStyle(document.getElementById('quality')).display]"},
        {"wait": 4300}, {"eval": "getComputedStyle(document.getElementById('fr-toast')).display"},
        {"reload": True}, {"eval": shown},
    ], size="360x780", mobile=True, query="soft=0&quality=PHONE&auto=0")
    assert out["ok"], out
    o = out["out"]
    assert o[0] == [True, True]                                     # one line, cut with "…"
    assert o[1] == "block"                                          # the first visit's hint
    assert set(o[2]) <= {"Screenshot", "Copy link to this view", "Clean look: hide the controls"} and o[2]
    assert o[3] <= 5
    assert o[6][0] == "Reset view" and o[6][1] == "block"
    assert o[8] == "none"                                           # gone after the first touch
    assert o[10] == o[2]
    assert o[12] is True                                            # Clean look from the More menu
    helptext = o[15]
    assert title in helptext and "Buttons" in helptext and "Measure" in helptext and "Screenshot" in helptext
    assert o[17] == ["block", "none"] and o[19] == "none"           # ~4 s, never the old corner note
    assert o[21] == "none"                                          # not shown on the next visit


@browser_test
def test_back_closes_what_is_open_and_never_leaves_the_page(tmp_path):
    """Independent tester (task 0179): the phone's Back with the help open left the page. Back now closes the help,
    the settings, More tools and the list of views – one at a time – and the page stays; the settings close with X."""
    path, _n = write(tmp_path / "v21.html", views=views_of(21))
    alive = "[!!window.frPage && frPage.ready, !!frPage.helpOpen, !!frPage.menuOpen, !!frPage.moreOpen, !!frPage.listOpen]"
    out = probe(path, [{"click": "#fr-tools [aria-label='Help and keys']"}, {"eval": alive}, {"back": True}, {"eval": alive},
                       {"click": "#fr-tools button"}, {"eval": alive}, {"back": True}, {"eval": alive},
                       {"click": "#fr-more-btn"}, {"eval": alive}, {"back": True}, {"eval": alive},
                       {"click": "#fr-views .fr-vname"}, {"wait": 50}, {"eval": alive},
                       {"back": True}, {"eval": alive},
                       {"click": "#fr-tools button"}, {"click": "#fr-menu .fr-x"}, {"eval": alive},
                       {"wait": 300}, {"eval": "history.length"}],
                size="360x780", mobile=True, query="soft=0")
    assert out["ok"], out
    o = out["out"]
    assert o[1] == [True, True, False, False, False] and o[3] == [True, False, False, False, False]
    assert o[5] == [True, False, True, False, False] and o[7] == [True, False, False, False, False]
    assert o[9] == [True, False, False, True, False] and o[11] == [True, False, False, False, False]
    assert o[14] == [True, False, False, False, True] and o[16] == [True, False, False, False, False]
    assert o[19] == [True, False, False, False, False]


@browser_test
def test_part_tool_panel_leaves_the_bottom_stack_free(tmp_path):
    """Task 0189 (0183 row 12): a phone sideways (844 x 390, 667 x 375) with the Measure tool open – its panel covered
    "Iso front-right", "Under cam" and the time line. The panel is in the layout check now and covers nothing, also
    with the Slice list open under Measure (task 0218; was Cutaway) (a longer panel) and upright."""
    names = ["Iso front-right", "Under cam", "Top", "Side", "Deck", "Stern"]
    path, _n = write(tmp_path / "tools.html", views=views_of(6, names))
    for size, mobile in (("844x390", True), ("667x375", True), ("390x844", True), ("1366x768", False)):
        out = probe(path, [{"click": "#fr-parts [aria-label^='Measure']"}, {"wait": 600}, {"eval": CHECK},
                           {"click": "#fr-parts [aria-label^='Slice']"}, {"wait": 200}, {"eval": CHECK}],
                    size=size, mobile=mobile, query="soft=0")
        assert out["ok"], out
        for c in (out["out"][2], out["out"][5]):
            assert "part tool panel" in c["items"], (size, c["items"])
            _no_overlaps(c, size)
