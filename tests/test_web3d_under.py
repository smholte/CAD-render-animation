"""Web 3D model under the sea (task 0143), no Blender: the page's ``under`` block (the seabed, the cut-away box, the
soil section, the water's clarity), the water's stretch in plain Python (what the page's shader fades by), the seabed's
drift, and the page in headless Chromium (``tools/web_player_probe.js``): the box is open from above, "Under the sea"
off closes it, the camera dives (and stops over the seabed), crosses the surface without flicker, and a saved view
below the water or the floor stays where it was saved (0147 row 11).

GitHub's Linux runner cannot start Chromium: there the scripts are checked by node instead (``web_player`` helpers).
"""

import json
import math
import os

import numpy as np
import pytest

from fresing_render.core import sea as sea_core
from fresing_render.core import web3d_env as env

from test_web_player import NODE, browser_test, model, probe

LEVEL = -0.5
DEPTH = 10.0
BOX = {"origin": (6.0, 0.0), "dir": (1.0, 0.0), "length": 10.0, "width": 6.0}
SEA = {"state": "CALM", "level": LEVEL, "origin": [0.0, 0.0], "near": 50.0, "waves": [[0.2, 1.0, 0.0, 0.3, 0.0]],
       "own": 1, "bump": 0.3, "foam": None, "moving": False, "amp": 0.2}


def under(cut=True, ground=False, clarity=10.0):
    return env.under_settings(LEVEL - DEPTH, DEPTH, clarity, 1.0, BOX if cut else None,
                              {"depth": 6.0} if ground else None, (0.0, 0.0))


# ---------------------------------------------------------------------------
# the numbers (no browser)
# ---------------------------------------------------------------------------

def test_under_block_holds_the_apps_numbers():
    u = under(ground=True)
    assert u["bed"] == LEVEL - DEPTH and u["depth"] == DEPTH and u["clarity"] == 10.0
    assert u["sigma"] == pytest.approx(sea_core.absorption(10.0)) == pytest.approx(0.3)
    assert u["colour"] == list(sea_core.UNDERWATER)
    assert u["ripple"] == [sea_core.RIPPLE_LENGTH, sea_core.RIPPLE_HEIGHT]
    assert u["cut"]["origin"] == [6.0, 0.0] and u["cut"]["width"] == 6.0 and u["cut"]["top"] == sea_core.CUT_TOP
    assert u["cut"]["edge"] == sea_core.CUT_EDGE and u["cut"]["dark"] == list(sea_core.CUT_DARK)
    assert u["ground"]["depth"] == 6.0 and len(u["ground"]["layers"]) == len(sea_core.SOIL_LAYERS)
    assert u["motion"] is None
    # no box: no soil section either; the direction is made a unit
    assert under(cut=False, ground=True)["ground"] is None
    u2 = env.under_settings(-30, 30, 5, 1, dict(BOX, dir=(0.0, -4.0)))
    assert u2["cut"]["dir"] == [0.0, -1.0]
    for bad in (dict(BOX, width=0.0), dict(BOX, dir=(0.0, 0.0)), dict(BOX, length=float("nan"))):
        with pytest.raises(ValueError):
            env.under_settings(-30, 30, 5, 1, bad)
    with pytest.raises(ValueError):
        env.under_settings(-30, 0.0, 5, 1)
    with pytest.raises(ValueError):
        env.under_settings(-30, 30, 5, 1, BOX, {"depth": -1.0})
    json.dumps(u, allow_nan=False)                           # goes into the page as it is


def test_water_stretch_is_the_apps_seen_through():
    u = under()
    top = LEVEL
    # above the water: nothing to fade
    assert env.water_length(u, (0, -20, 5), (0, 20, 3)) == 0.0
    # straight down outside the box from the air to the seabed: the whole depth
    assert env.water_length(u, (0, -20, 5), (0, -20, top - DEPTH)) == pytest.approx(DEPTH)
    # straight down inside the box: no water at all (the box is taken away from the sky to the seabed)
    assert env.water_length(u, (11, 0, 5), (11, 0, top - DEPTH)) == pytest.approx(0.0)
    # under water, horizontally along the box's middle: only the stretches outside it count
    assert env.water_length(u, (0, 0, top - 3), (20, 0, top - 3)) == pytest.approx(10.0)
    # across the box: through its 6 m
    assert env.water_length(u, (11, -10, top - 3), (11, 10, top - 3)) == pytest.approx(14.0)
    # what the camera sees of a white thing behind it: core.sea.seen_through
    d = env.water_length(u, (11, 0, top - 3), (11, 13, top - 3))       # 3 m in the box, 10 m in water
    assert d == pytest.approx(10.0)
    seen = sea_core.seen_through(np.ones(3), d, u["clarity"])
    assert seen == pytest.approx(np.exp(-3.0) + np.array(sea_core.UNDERWATER) * (1 - np.exp(-3.0)))
    # without the box every metre under the level counts
    assert env.water_length(under(cut=False), (0, 0, top - 3), (20, 0, top - 3)) == pytest.approx(20.0)


def test_seabed_drift_is_thinned_and_repeats():
    u = under()
    t = np.linspace(0, 8, 201)
    xy = np.column_stack([5.0 - t, np.zeros_like(t)])            # 1 m/s aft
    got = env.under_motion(u, t, xy)
    assert got["motion"]["t"] == [0.0, 8.0]                       # a straight line: two moments are enough
    assert env.bed_offset(got, 2.0) == pytest.approx([3.0, 0.0])
    assert env.bed_offset(got, 10.0) == pytest.approx([3.0, 0.0])  # the animation repeats
    still = env.under_motion(u, t, np.zeros((len(t), 2)))
    assert still["motion"] is None and env.bed_offset(still, 3.0) == [0.0, 0.0]
    bend = np.column_stack([np.sin(t), np.zeros_like(t)])
    got = env.under_motion(u, t, bend)
    assert 2 < len(got["motion"]["t"]) < len(t)
    for tt in (0.3, 2.9, 6.1):
        assert env.bed_offset(got, tt)[0] == pytest.approx(math.sin(tt), abs=2e-3)


def test_items_text_names_it():
    st = env.settings(dict(env.default_choice(), sea=True), [0, 0, 0], [1, 1, 1], sea=dict(SEA))
    assert "seabed" not in env.items_text(st)
    st["under"] = under(ground=True)
    assert "the seabed and the sea cut-away with the ground" in env.items_text(st)
    st["under"] = under(cut=False)
    text = env.items_text(st)
    assert "the seabed" in text and "cut-away" not in text


# ---------------------------------------------------------------------------
# the page (headless Chromium)
# ---------------------------------------------------------------------------

UNDER_VIEW = {"name": "Seabed", "eye": [-12.0, -6.0, LEVEL - 6.0], "target": [1.5, 0.0, LEVEL - 4.0],
              "vfov": 40.0, "hfov": 60.0}
FLOOR_VIEW = {"name": "Below", "eye": [1.5, -3.0, -2.0], "target": [1.5, 0.0, 0.3], "vfov": 40.0, "hfov": 60.0}


def write(path, cut=True, ground=False, with_under=True, views=None, kind="sea", moving=False):
    if kind == "plain":
        st = env.settings(dict(env.default_choice(), shadows=False), [-1.0, -1.0, 0.0], [4.0, 1.0, 0.6],
                          sky={"kind": "SKY", "sun": env.sun_vector(40, 30)}, plain=True)
    else:
        st = env.settings(dict(env.default_choice(), sea=True, shadows=False), [-1.0, -1.0, 0.0], [4.0, 1.0, 0.6],
                          sky={"kind": "SKY", "sun": env.sun_vector(40, 30)}, sea=dict(SEA, moving=moving))
        if with_under:
            st["under"] = under(cut=cut, ground=ground)
    st["views"] = views or []
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(env.page_html("Under test", model(False), st, animated=False))
    return str(path)


def three(p):
    """Blender world -> three's coordinates (the page's b2t)."""
    return [p[0], p[2], -p[1]]


def _set(eye, target):
    return {"eval": f"frPage.setCamera({json.dumps(three(eye))}, {json.dumps(three(target))}), "
                    "frPage.wake(), new Promise(r => setTimeout(r, 400)).then(() => frPage.cameraState())"}


SETTLE = {"eval": "new Promise(r => { const t0 = Date.now(); (function w() {"
                  " if (!frPage.cameraState().flying || Date.now() - t0 > 8000) r(frPage.cameraState());"
                  " else setTimeout(w, 50); })(); })"}         # the flight to a saved view has ended
PIXEL = {"eval": "JSON.parse(document.documentElement.dataset.frProbe || 'null')"}


@browser_test
def test_box_is_open_from_above_and_the_switch_closes_it(tmp_path):
    path = write(tmp_path / "u.html")
    above = _set((11.0, 0.0, 25.0), (11.0, 0.01, LEVEL - DEPTH))     # straight down into the box
    out = probe(path, [{"wait": 300}, above, {"wait": 300}, PIXEL, {"eval": "frPage.items"},
                       {"eval": "frPage.setItem('under', false)"}, {"wait": 400}, PIXEL,
                       {"eval": "frPage.underState()"}],
                query="soft=0&auto=0&probe=0.5,0.5")
    assert out["ok"], out
    seabed, items, closed, st = out["out"][3][0], out["out"][4], out["out"][7][0], out["out"][8]
    assert "under" in items and "dive" in items
    assert seabed[0] >= seabed[2] and sum(seabed[:3]) > 200, f"the box shows no sand from above: {seabed}"
    assert closed[2] > closed[0] + 10, f"Under the sea off still shows the seabed: {closed}"   # the sea: blue
    assert sum(closed[:3]) < sum(seabed[:3]) - 60
    assert st["fog"] is None and not st["dive"]           # no water code left in any program


@browser_test
def test_camera_dives_stops_over_the_seabed_and_sees_water(tmp_path):
    path = write(tmp_path / "u.html")
    out = probe(path, [{"wait": 300},
                       _set((-15.0, -8.0, LEVEL - 4.0), (5.0, -8.0, LEVEL - 4.0)), PIXEL,   # under, outside the box
                       {"eval": "frPage.underState()"},
                       _set((-15.0, -8.0, LEVEL - 40.0), (5.0, -8.0, LEVEL - 40.0)),         # into the seabed: stopped
                       {"eval": "frPage.setItem('dive', false)"},
                       _set((-15.0, -8.0, LEVEL - 4.0), (5.0, -8.0, LEVEL - 4.0)),           # no diving: kept above
                       {"eval": "frPage.underState()"}],
                query="soft=0&auto=0&probe=0.5,0.5")
    assert out["ok"], out
    cam, water, st = out["out"][1], out["out"][2][0], out["out"][3]
    assert cam["pos"][1] == pytest.approx(LEVEL - 4.0, abs=1e-6) and st["camera"] and st["dive"]
    assert water[1] > water[0] + 10 and water[2] > water[0] + 10, f"no water colour under the sea: {water}"
    floor = out["out"][4]
    assert floor["pos"][1] == pytest.approx(LEVEL - DEPTH + 0.4, abs=1e-3)       # just over the seabed
    assert floor["target"][1] >= LEVEL - DEPTH + 0.4 - 1e-6
    dry = out["out"][6]
    assert dry["pos"][1] > LEVEL and not out["out"][7]["camera"]


@browser_test
def test_surface_crossing_never_flickers(tmp_path):
    path = write(tmp_path / "u.html")
    js = ("(async () => { const out = []; for (let i = 0; i <= 80; i++) {"
          f" const y = {LEVEL} + 0.6 - i * 0.015;"
          " frPage.setCamera([-15, y, 8], [5, y, 8]); frPage.wake();"
          " await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));"
          " out.push(frPage.underState().camera); } return out; })()")
    out = probe(path, [{"wait": 300}, {"eval": js}], query="soft=0&auto=0&t=2")
    assert out["ok"], out
    seen = out["out"][1]
    flips = sum(1 for a, b in zip(seen, seen[1:]) if a != b)
    assert not seen[0] and seen[-1] and flips == 1, seen


@browser_test
def test_saved_view_below_the_water_or_the_floor_stays(tmp_path):
    """0147 row 11: the "Seabed" camera of a sea page and a camera below the floor of a plain page are shown where
    they were saved – also with Camera under water off – until the visitor drags."""
    path = write(tmp_path / "u.html", views=[UNDER_VIEW])
    out = probe(path, [{"wait": 300}, {"eval": "frPage.setItem('dive', false)"}, {"eval": "frPage.goView(0)"},
                       {"wait": 300}, SETTLE, {"drag": [450, 300, 452, 290]},
                       {"wait": 600}, {"eval": "frPage.cameraState()"}],
                query="soft=0&auto=0")
    assert out["ok"], out
    at, dragged = out["out"][4], out["out"][7]
    assert at["pos"] == pytest.approx(three(UNDER_VIEW["eye"]), abs=1e-3) and at["onView"]
    assert not dragged["onView"] and dragged["pos"][1] > LEVEL                    # dragged: above the water again
    plain = write(tmp_path / "p.html", kind="plain", views=[FLOOR_VIEW])
    out = probe(plain, [{"wait": 300}, {"eval": "frPage.goView(0)"}, {"wait": 300}, SETTLE],
                query="soft=0&auto=0")
    assert out["ok"], out
    assert out["out"][3]["pos"] == pytest.approx(three(FLOOR_VIEW["eye"]), abs=1e-3)


@browser_test
def test_sea_without_a_seabed_stays_as_before(tmp_path):
    path = write(tmp_path / "s.html", with_under=False)
    out = probe(path, [{"wait": 300}, {"eval": "frPage.items"}, {"eval": "frPage.underState()"},
                       _set((-15.0, -8.0, LEVEL - 4.0), (5.0, -8.0, LEVEL - 4.0)),
                       {"eval": "frPage.cameraState().maxPolar"}], query="soft=0&auto=0")
    assert out["ok"], out
    assert "under" not in out["out"][1] and "dive" not in out["out"][1]
    assert not out["out"][2]["under"] and out["out"][2]["fog"] is None
    assert out["out"][3]["pos"][1] > LEVEL                                        # never under the water
    assert out["out"][4] == pytest.approx(math.pi * 0.497)


@browser_test
def test_soil_section_shows_in_the_box(tmp_path):
    path = write(tmp_path / "g.html", ground=True)
    down = _set((11.0, 0.0, 25.0), (11.0, 0.01, LEVEL - DEPTH))
    out = probe(path, [{"wait": 300}, down, {"wait": 300}, {"eval": "frPage.underState()"}, PIXEL,
                       _set((11.0, 0.0, LEVEL - DEPTH - 4.0), (14.0, 0.0, LEVEL - DEPTH - 4.0)),
                       {"eval": "frPage.underState()"}],
                query="soft=0&auto=0&probe=0.5,0.5")
    assert out["ok"], out
    assert out["out"][3]["ground"]
    pit = out["out"][5]
    assert pit["pos"][1] == pytest.approx(LEVEL - DEPTH - 4.0, abs=1e-3)          # in the pit, under the seabed


def test_page_text_without_node_has_the_switches():
    """The menu's names and the page's switches (also where no browser runs)."""
    player = env._read(env.PLAYER_FILE)
    page = env._read(env.PAGE_FILE)
    assert "under: 'Under the sea'" in player and "dive: 'Camera under water'" in player
    assert "page.items.push('under', 'dive')" in page
    if NODE:
        import subprocess
        for name in (env.PAGE_FILE, env.PLAYER_FILE):
            subprocess.run([NODE, "--check", os.path.join(env.web3d.WEB_DIR, name)], check=True)


@browser_test
def test_auto_quality_switches_it_off_at_phone_when_still_slow(tmp_path):
    """Without a graphics card the page starts at Phone; still below 27 pictures a second, Auto switches Under the sea
    off once and says so. A visitor's own choice (the link's off=…) is left alone."""
    path = write(tmp_path / "a.html", moving=True)          # the waves move: the page draws all the time
    out = probe(path, [{"wait": 6000}, {"eval": "[frPage.level, frPage.on.under, frPage.underState().fog]"},
                       {"eval": "document.getElementById('quality').textContent"}])
    assert out["ok"], out
    level, under_on, fog = out["out"][1]
    assert level == "PHONE" and under_on is False and fog is None, out["out"][1]
    assert "Under the sea switched off" in out["out"][2]
    out = probe(path, [{"wait": 6000}, {"eval": "frPage.on.under"}], query="off=haze")
    assert out["ok"] and out["out"][1] is True
