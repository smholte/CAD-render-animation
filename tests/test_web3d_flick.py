"""A flick sets the web 3D page's model spinning (task 0256), driven in headless Chromium by
``tools/web_player_probe.js``: a fast, short drag let go while still moving starts a spin in its direction that eases
to the auto-turn speed (Auto-turn on: keeps turning) or to a stop (off); a slow drag, a held-still release, a pan
(Shift / right button) and a second finger never start it; a press stops it.
"""

from test_web_player import browser_test, probe, write

SIZE = "600x400"
Q = "soft=0&auto=0"
SPEED = "(frPage.spinning() || {speed: 0}).speed"          # radians a second
TURN = "frPage.three.controls.autoRotateSpeed"              # 1 = one turn a minute


def run(tmp_path, steps, turn):
    path, _n = write(tmp_path / "p.html", animated=False)
    pre = [{"eval": f"frPage.setTurn({'true' if turn else 'false'})"}, {"wait": 300}]
    out = probe(path, pre + steps, query=Q, size=SIZE)
    assert out["ok"], out
    return out["out"][len(pre):]


@browser_test
def test_a_fast_drag_sets_it_spinning_and_it_eases_to_the_auto_turn_speed(tmp_path):
    o = run(tmp_path, [{"drag": [200, 200, 330, 200, 10]}, {"eval": "[frPage.turning, " + SPEED + ", " + TURN + "]"},
                       {"wait": 3000}, {"eval": "[frPage.turning, frPage.spinning(), " + TURN + "]"}], turn=True)
    on, speed, rot = o[1]
    assert on and 2.0 < speed <= 3.2 and rot > 1.5       # in the drag's direction (right = +), fast, capped at pi
    on2, spin, rot2 = o[3]
    assert on2 and spin is None and abs(rot2 - 1.0) < 1e-9, o[3]      # one turn a minute, still turning


@browser_test
def test_a_flick_to_the_left_turns_left_and_keeps_that_way(tmp_path):
    o = run(tmp_path, [{"drag": [400, 200, 270, 200, 10]}, {"wait": 3000}, {"eval": TURN}], turn=True)
    assert abs(o[2] + 1.0) < 1e-9, o


@browser_test
def test_with_auto_turn_off_it_coasts_to_a_stop(tmp_path):
    o = run(tmp_path, [{"drag": [200, 200, 330, 200, 10]}, {"eval": "frPage.turning"}, {"wait": 3000},
                       {"eval": "[frPage.turning, frPage.spinning()]"}], turn=False)
    assert o[1] is True and o[3] == [False, None], o


@browser_test
def test_a_slow_drag_a_held_release_a_pan_and_a_right_button_do_not(tmp_path):
    o = run(tmp_path, [{"drag": [200, 200, 330, 200, 80]}, {"eval": "frPage.turning"},
                       {"drag": [200, 200, 330, 200, 10, "wait"]}, {"eval": "frPage.turning"},
                       {"drag": [200, 200, 330, 200, 10, "Shift"]}, {"eval": "frPage.turning"},
                       {"drag": [200, 200, 330, 200, 10, "right"]}, {"eval": "frPage.turning"},
                       {"drag": [200, 200, 200, 320, 10]}, {"eval": "frPage.turning"}], turn=False)
    assert [o[1], o[3], o[5], o[7], o[9]] == [False] * 5, o


@browser_test
def test_a_press_stops_it_and_two_fingers_never_start_it(tmp_path):
    two = ("(() => { const c = document.querySelector('canvas');"
           "const ev = (t, id, x) => c.dispatchEvent(new PointerEvent(t, {pointerId: id, isPrimary: id === 1, "
           "pointerType: 'touch', clientX: x, clientY: 200, bubbles: true, button: 0}));"
           "ev('pointerdown', 1, 200); ev('pointerdown', 2, 300); ev('pointermove', 1, 260); ev('pointermove', 1, 400);"
           "ev('pointerup', 2, 300); ev('pointerup', 1, 400); return frPage.turning; })()")
    o = run(tmp_path, [{"eval": two}, {"drag": [200, 200, 330, 200, 10]}, {"eval": "frPage.turning"},
                       {"tap": [300, 200]}, {"eval": "[frPage.turning, frPage.spinning()]"}], turn=False)
    assert o[0] is False and o[2] is True and o[4] == [False, None], o


@browser_test
def test_the_pages_own_check_covers_the_flick(tmp_path):
    path, _n = write(tmp_path / "p.html", animated=False)
    out = probe(path, [{"wait": 600}, {"eval": "document.documentElement.dataset.frSelftest || ''"}],
                query="soft=0&auto=0&selftest=1", size=SIZE)
    assert '"flick":true' in out["out"][1], out["out"][1]
