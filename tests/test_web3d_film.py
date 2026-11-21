"""Film on the web 3D page (task 0252), no Blender: the film data (``core/web3d_film.py``) and the page playing it
(``fr_page.js`` / ``fr_player.js``, driven in headless Chromium by ``tools/web_player_probe.js``).

A camera made up here circles a two-plate model, zooms, and cuts once; the page must show exactly what the data says
at any moment (the same blending as ``web3d_film.sample``), hold the shot before a cut, follow the time line, leave
the Film on a drag while the motion plays on, glide back on Film, open in it from a link, and show the captions,
labels and cards only while the Film is on. Without a browser (GitHub's Linux runners) the scripts are checked by
node and the page's text (``test_web_player.browser_test``).
"""

import json
import math
import os

import numpy as np

from fresing_render.core import brand
from fresing_render.core import web3d_env as env
from fresing_render.core import web3d_film as F

from test_web_player import VIEWS, browser_test, model, probe

FPS = 24
N = 97                           # 4 s, as the test model's motion
CUT = 60


def look(eye, target):
    """A Blender camera matrix at ``eye`` looking at ``target`` (z up)."""
    f = np.asarray(target, float) - np.asarray(eye, float)
    f /= np.linalg.norm(f)
    r = np.cross(f, [0, 0, 1])
    r /= np.linalg.norm(r)
    u = np.cross(r, f)
    m = np.eye(4)
    m[:3, 0], m[:3, 1], m[:3, 2], m[:3, 3] = r, u, -f, eye
    return m


def track(n=N, cut=CUT, fps=FPS):
    """The made-up camera: half a turn a second round the plates, rising; at ``cut`` it jumps (another angle, 5 m
    higher). Field of view breathing between 22° and 28°."""
    mats = []
    for k in range(n):
        a = k / fps * 0.5 + (1.0 if k >= cut else 0.0)
        eye = [1.5 + 8 * math.sin(a), -8 * math.cos(a), 2.0 + k * 0.01 + (5.0 if k >= cut else 0.0)]
        mats.append(look(eye, [1.5, 0.0, 0.3]))
    vfov = 25 + 3 * np.sin(np.arange(n) / fps)
    return np.array(mats), vfov


def film_block(extras=True):
    mats, v = track()
    pos, q = F.pose(mats)
    film = F.encode(pos, q, v, FPS, 16 / 9, 5.0, cuts=[CUT])
    if extras:
        film["captions"] = F.captions([("The plates move", 0.5, 2.0)], FPS, N)
        film["labels"] = {"size": 0.036, "box": "#1A2027", "fg": "#FFFFFF",
                          "items": [{"node": 1, "at": [0.0, 0.0, 0.0], "w": None, "text": "Moving plate"},
                                    {"node": 0, "at": [0.0, 0.0, 0.0], "w": [3.0, 4.0], "texts": [[0.0, "Still"]]}]}
        film["cards"] = {"bg": "#1A2027", "fg": "#FFFFFF", "title": {"s": 1.0, "title": "Two plates", "sub": "A test"},
                         "end": {"s": 1.0, "text": "www.example.com", "logo": ""}}
    return film, pos, q, v


def write(path, films=True, extras=True, animated=True):
    ch = dict(env.default_choice(), shadows=False, auto=True, quality="BALANCED", sea=False, haze=False, rain=False)
    st = env.settings(ch, [-1.0, -1.0, 0.0], [4.0, 1.0, 0.6], sky={"kind": "SKY", "sun": env.sun_vector(40, 30)},
                      plain=True)
    st["views"] = VIEWS
    if films:
        st["films"] = [film_block(extras)[0]]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(env.page_html("Film test", model(animated), st, animated=animated, note="Made with Fresing Render"))
    return str(path)


# ---------------------------------------------------------------------------
# the data
# ---------------------------------------------------------------------------

def test_pose_is_the_blender_camera_in_the_pages_world():
    mats, _v = track(5)
    pos, q = F.pose(mats)
    assert np.allclose(F.matrix_of(pos, q), mats, atol=1e-12)
    # Blender (x, y, z) is three's (x, z, -y); a camera looking along Blender's +y looks along three's -z
    m = look([0, -5, 0], [0, 0, 0])
    p, qq = F.pose(m[None])
    assert np.allclose(p[0], [0, 0, 5])
    assert np.allclose(np.abs(qq[0]), [0, 0, 0, 1], atol=1e-12)


def test_every_frame_within_the_tolerances_and_the_cut_is_held():
    film, pos, q, v = film_block(extras=False)
    dec = F.decode(film)
    ep, ea, ev = F.errors(dec, pos, q, v)
    assert ep <= F.pos_tol(5.0) * 1.001 and ea <= math.degrees(F.ANGLE_TOL) * 1.001 and ev <= F.FOV_TOL * 1.001
    assert ep <= 1e-3 * 5.0 and ea <= 0.05 and ev <= 0.05             # the brief's numbers
    assert film["cut"] == [CUT] and CUT in dec["keys"] and CUT - 1 in dec["keys"]
    # between the frame before the cut and the cut: the shot before holds, never a blend of the two
    for frac in (0.01, 0.5, 0.99):
        p, qq, vv = F.sample(dec, (CUT - 1 + frac) / FPS)
        assert np.linalg.norm(p[0] - pos[CUT - 1]) < F.pos_tol(5.0)
    p, _q, _v = F.sample(dec, CUT / FPS)
    assert np.linalg.norm(p[0] - pos[CUT]) < F.pos_tol(5.0)
    # in between two ordinary frames it blends (not held)
    p, _q, _v = F.sample(dec, 10.5 / FPS)
    assert np.linalg.norm(p[0] - (pos[10] + pos[11]) / 2) < 0.01


def test_a_straight_move_keeps_two_moments_and_the_block_is_small():
    n = 4481                                       # the full demo kit's length
    mats = np.array([look([10.0 + 0.01 * k, -40.0, 8.0], [10.0 + 0.01 * k, 0.0, 2.0]) for k in range(n)])
    pos, q = F.pose(mats)
    film = F.encode(pos, q, np.full(n, 30.0), 25, 16 / 9, 100.0)
    assert len(film["k"]) == 2
    # a camera that turns all the time (an orbit of the whole demo) keeps every frame: still within the aim
    mats = np.array([look([60 * math.sin(k / 400), -60 * math.cos(k / 400), 20.0], [0, 0, 5]) for k in range(n)])
    pos, q = F.pose(mats)
    film = F.encode(pos, q, 30 + np.sin(np.arange(n) / 100), 25, 16 / 9, 100.0)
    assert F.size_bytes(film) < 200_000, F.size_bytes(film)
    ep, ea, ev = F.errors(F.decode(film), pos, q, 30 + np.sin(np.arange(n) / 100))
    assert ep <= F.pos_tol(100.0) * 1.001 and ea <= 0.0201 and ev <= 0.0201


def test_cuts_found_from_the_numbers():
    film, pos, q, v = film_block(extras=False)
    assert F.find_cuts(pos, q, v, 5.0) == [CUT]
    assert F.find_cuts(pos[:CUT], q[:CUT], v[:CUT], 5.0) == []        # a smooth camera has none


def test_captions_as_the_video_shows_them():
    steps = [("One", 0.0, 0.5), ("Two", 1.0, 3.0), ("Three", 2.5, 3.0)]
    caps = F.captions(steps, 25, 76)
    want = brand.caption_list(steps, 25, 0, 76)
    assert [c["text"] for c in caps] == [c.text for c in want]
    for c, w in zip(caps, want):                 # video frame f shows from (f - 1) / fps on, for 1 / fps
        assert abs(c["a"] - (w.start - 1) / 25) < 1e-9 and abs(c["b"] - w.end / 25) < 1e-9
    assert caps[0]["b"] == 1.0                   # at least 1.5 s, but never into the next one (from 1.0 s on)


# ---------------------------------------------------------------------------
# the page
# ---------------------------------------------------------------------------

def _close(a, b, tol):
    return np.abs(np.asarray(a, float) - np.asarray(b, float)).max() <= tol


def _same_turn(a, b, tol=1e-6):
    return abs(abs(float(np.dot(a, b))) - 1.0) <= tol


@browser_test
def test_page_plays_the_film_as_the_data_says(tmp_path):
    path = write(tmp_path / "film.html", extras=False)
    film, pos, q, v = film_block(extras=False)
    dec = F.decode(film)
    times = [0.0, 0.37, 1.0, 1.51, (CUT - 1) / FPS, (CUT - 0.5) / FPS, CUT / FPS, 3.33, 4.0]
    steps = [{"eval": "frPage.setFilm(true, false), frPage.paused = true"}]
    steps += [{"eval": f"frPage.filmAt({t})"} for t in times]
    steps += [{"eval": "frPage.setTime(3.33), 0"}, {"wait": 300}, {"eval": "frPage.filmState()"}]
    out = probe(path, steps, query="soft=0")
    assert out["ok"], out
    o = out["out"]
    for t, got in zip(times, o[1:1 + len(times)]):
        p, qq, vv = F.sample(dec, t)
        assert _close(got["pos"], p[0], 1e-9), (t, got, p)
        assert _same_turn(got["quat"], qq[0]), (t, got, qq)
        assert abs(got["vfov"] - vv[0]) < 1e-9
    # the frame before the cut holds until the cut's frame
    assert _close(o[1 + times.index((CUT - 0.5) / FPS)]["pos"], pos[CUT - 1], F.pos_tol(5.0))
    st = o[-1]
    assert st["on"] and _close(st["camPos"], st["pos"], 1e-6) and _same_turn(st["camQuat"], st["quat"])
    p, _qq, _vv = F.sample(dec, 3.33)
    assert _close(st["pos"], p[0], 1e-6) and abs(st["time"] - 3.33) < 1e-6


@browser_test
def test_film_button_leave_and_back(tmp_path):
    path = write(tmp_path / "film.html", extras=False)
    out = probe(path, [
        {"eval": "!!document.querySelector('#fr-playbar .fr-film')"},                       # 0
        {"click": "#fr-playbar .fr-film"}, {"wait": 900},
        {"eval": "frPage.filmState()"},                                                      # 3
        {"eval": "frPage.time"}, {"drag": [450, 300, 560, 330]}, {"wait": 400},
        {"eval": "frPage.filmState()"},                                                      # 7
        {"eval": "frPage.time"},                                                             # 8
        {"eval": "document.querySelector('#fr-playbar .fr-film').className"},                # 9
        {"eval": "frPage.viewLink()"},                                                       # 10
        {"click": "#fr-playbar .fr-film"},
        {"eval": "frPage.filmState().gliding"},                                              # 12
        {"wait": 900}, {"eval": "frPage.filmState()"},                                       # 14
        {"eval": "frPage.viewLink()"},                                                       # 15
        {"key": "1"}, {"wait": 200}, {"eval": "frPage.filmState()"},                         # 18
        {"click": "#fr-playbar .fr-film"}, {"wait": 900}, {"key": "r"}, {"eval": "frPage.filmOn()"},   # 22
        {"click": "#fr-playbar .fr-film"}, {"wait": 900},
        {"eval": "frPage.setTime(1.0), frPage.paused = true, 0"}, {"wait": 200}, {"eval": "frPage.filmState()"},  # 27
        {"key": "ArrowRight"}, {"wait": 200}, {"eval": "frPage.filmState()"},              # 30
        {"click": "#fr-playbar [aria-label='Speed 2']"}, {"eval": "frPage.paused = false, 0"}, {"wait": 500},
        {"eval": "frPage.filmState()"},                                                      # 34
    ], query="soft=0", size="900x600")
    o = out["out"]
    assert out["ok"], out
    assert o[0] is True
    assert o[3]["on"] and not o[3]["gliding"] and _close(o[3]["camPos"], o[3]["pos"], 1e-5)
    assert not o[7]["on"] and o[7]["left"], "a drag leaves the Film"
    assert o[8] > o[4], "the motion plays on after leaving the Film"
    assert "fr-back" in o[9]
    assert "film=1" not in o[10]
    assert o[12] is True, "Film glides back"
    assert o[14]["on"] and not o[14]["gliding"] and _close(o[14]["camPos"], o[14]["pos"], 1e-5)
    assert "film=1" in o[15]
    assert not o[18]["on"], "a saved view leaves the Film"
    assert o[22] is False, "Reset view leaves the Film"
    assert abs(o[27]["time"] - 1.0) < 1e-6 and _close(o[27]["camPos"], o[27]["pos"], 1e-6)
    assert abs(o[30]["time"] - 3.0) < 1e-6 and _close(o[30]["camPos"], o[30]["pos"], 1e-6), "← → move the Film too"
    assert o[34]["on"] and _close(o[34]["camPos"], o[34]["pos"], 1e-5)
    # the link opens in the Film
    back = probe(path, [{"wait": 200}, {"eval": "frPage.filmState()"}], query="film=1&time=2.5&paused=1&soft=0")
    st = back["out"][1]
    assert st["on"] and abs(st["time"] - 2.5) < 1e-6 and _close(st["camPos"], st["pos"], 1e-6)


@browser_test
def test_no_film_no_button(tmp_path):
    path = write(tmp_path / "plain.html", films=False)
    out = probe(path, [{"eval": "!!document.querySelector('#fr-playbar .fr-film')"},
                       {"eval": "frPage.setFilm(true)"}, {"eval": "frPage.filmState()"}], query="soft=0")
    assert out["out"] == [False, False, None]


@browser_test
def test_captions_labels_and_cards_only_in_the_film(tmp_path):
    path = write(tmp_path / "film.html")
    out = probe(path, [
        {"eval": "frPage.filmOverlays()"},                                                   # 0: Film off
        {"eval": "frPage.paused = true, frPage.setTime(0), frPage.setFilm(true, false), frPage.filmCard()"},  # 1
        {"wait": 300}, {"eval": "frPage.filmOverlays()"},                                    # 3
        {"eval": "frPage.paused = false, 0"}, {"wait": 1500},                                # card over
        {"eval": "[frPage.filmCard(), frPage.time]"},                                        # 6
        {"eval": "frPage.paused = true, frPage.setTime(1.0), 0"}, {"wait": 300},
        {"eval": "frPage.filmOverlays()"},                                                   # 9
        {"eval": "frPage.setTime(3.5), 0"}, {"wait": 300}, {"eval": "frPage.filmOverlays()"},  # 12
        {"eval": "frPage.setTime(3.9), frPage.paused = false, 0"}, {"wait": 600},
        {"eval": "[frPage.filmCard(), frPage.filmOverlays()]"},                              # 15: end card
        {"eval": "frPage.setTime(0.2), 0"}, {"wait": 100}, {"eval": "frPage.filmCard()"},    # 18: skipped
        {"eval": "frPage.paused = true, frPage.setFilm(false), frPage.filmOverlays()"},      # 19
    ], query="soft=0", size="900x600")
    o = out["out"]
    assert out["ok"], out
    assert o[0]["caption"] == "" and o[0]["labels"] == [] and o[0]["card"] == ""
    assert o[1]["kind"] == "title"
    assert o[3]["card"] == "title" and "Two plates" in o[3]["cardText"] and "A test" in o[3]["cardText"]
    assert o[6][0] is None and o[6][1] > 0.05, "after its seconds the title card goes and the motion plays"
    assert o[9]["caption"] == "The plates move" and [x["text"] for x in o[9]["labels"]] == ["Moving plate"]
    assert o[12]["caption"] == "" and sorted(x["text"] for x in o[12]["labels"]) == ["Moving plate", "Still"]
    assert o[15][0] and o[15][0]["kind"] == "end" and "www.example.com" in o[15][1]["cardText"]
    assert o[18] is None, "moving the time line skips a card"
    assert o[19]["caption"] == "" and o[19]["labels"] == [] and o[19]["card"] == ""


@browser_test
def test_label_line_ends_on_the_moving_part(tmp_path):
    path = write(tmp_path / "film.html")
    steps = []
    for t in (0.8, 1.6, 2.4):
        steps += [{"eval": f"frPage.paused = true, frPage.setFilm(true, false), frPage.setTime({t}), 0"},
                  {"wait": 250},
                  {"eval": "(function(){var o=frPage.nodes[1], T=frPage.three.T, c=frPage.three.camera;"
                           "var v=new T.Vector3().setFromMatrixPosition(o.matrixWorld).project(c);"
                           "var r=frPage.three.canvas.getBoundingClientRect();"
                           "return [(v.x+1)/2*r.width, (1-v.y)/2*r.height, frPage.filmLabels]})()"}]
    out = probe(path, steps, query="soft=0", size="900x600")
    assert out["ok"], out
    for got in out["out"][2::3]:
        x, y, labels = got
        lab = next(lb for lb in labels if lb["text"] == "Moving plate")
        assert abs(lab["anchor"][0] - x) < 1.0 and abs(lab["anchor"][1] - y) < 1.0
        bx, by, bw, bh = lab["box"]
        assert not (bx <= x <= bx + bw and by <= y <= by + bh), "the box sits beside the point, not on it"


@browser_test
def test_film_button_on_a_phone_no_overlaps(tmp_path):
    path = write(tmp_path / "film.html")
    for size, mobile in (("320x568", True), ("375x667", True), ("667x375", True), ("900x600", False)):
        out = probe(path, [{"wait": 300}, {"eval": "frPage.layoutCheck()"},
                           {"eval": "frPage.paused = true, frPage.setFilm(true, false), frPage.setTime(1.0), 0"},
                           {"wait": 300}, {"eval": "frPage.layoutCheck()"}], query="soft=0", size=size, mobile=mobile)
        assert out["ok"], out
        for lc in (out["out"][1], out["out"][4]):
            assert "play: Film" in lc["items"], (size, lc["items"])
            assert lc["overlaps"] == [] and lc["outside"] == [] and lc["small"] == [], (size, lc)


@browser_test
def test_film_costs_no_frame_time(tmp_path):
    """Pictures a second with the Film on and off, the same motion, software drawing (the web machine): the Film's
    work per picture (a binary search, a slerp, a few labels) must not show."""
    path = write(tmp_path / "film.html")
    out = probe(path, [{"wait": 1500}, {"frames": 3000},
                       {"eval": "frPage.setFilm(true, false), 0"}, {"wait": 500}, {"frames": 3000},
                       {"eval": "frPage.setFilm(false), 0"}, {"wait": 500}, {"frames": 3000}],
                query="soft=0&auto=0&quality=PHONE", size="640x400")
    assert out["ok"], out
    off1, on, off2 = out["out"][1], out["out"][4], out["out"][7]
    print(f"pictures in 3 s: Film off {off1}, on {on}, off again {off2}")
    assert on >= 0.75 * min(off1, off2), (off1, on, off2)
    with open(os.path.join(str(tmp_path), "frames.json"), "w") as fh:
        json.dump([off1, on, off2], fh)
