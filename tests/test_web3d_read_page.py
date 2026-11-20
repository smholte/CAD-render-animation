"""Task 0242: ``web3d_env.read_page`` opens a page that is still "loading" once more with a longer clock, and a page
that never becomes ready still reads "loading" (the PC-check lines then fail). A fake browser (a small Python
program) stands in for Edge / Chrome: it says what a real one would write out for each clock."""
from __future__ import annotations

import os
import stat
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fresing_render.core import web3d_env as env  # noqa: E402

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="the fake browser is a script with a #! line")

FAKE = '''#!{python}
import os, sys
budget = next(int(a.split("=")[1]) for a in sys.argv if a.startswith("--virtual-time-budget="))
with open(os.environ["FAKE_LOG"], "a") as fh:
    fh.write(str(budget) + "\\n")
mode = os.environ["FAKE_MODE"]
ready = mode == "ready" or (mode == "slow" and budget >= 60000)
state = "ready PHONE frames 2" if ready else "loading"
places = ' data-fr-places="{{&quot;1&quot;: [0, 0, 0, 0, 0, 0, 1, 1, 1, 1]}}"' if ready else ""
print('<html data-fr-state="' + state + '"' + places + '><body></body></html>')
'''


@pytest.fixture
def fake(tmp_path, monkeypatch):
    path = tmp_path / "fake-browser"
    path.write_text(FAKE.format(python=sys.executable))
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    log = tmp_path / "budgets.txt"
    monkeypatch.setenv("FAKE_LOG", str(log))
    page = tmp_path / "page.html"
    page.write_text("<html></html>")

    def run(mode, **kw):
        monkeypatch.setenv("FAKE_MODE", mode)
        if log.exists():
            log.unlink()
        got = env.read_page(str(page), str(path), "auto=0&frames=2&places=1", seconds=30, **kw)
        return got, [int(x) for x in log.read_text().split()]
    return run


def test_a_ready_page_is_opened_once(fake):
    got, budgets = fake("ready")
    assert got["state"].startswith("ready") and got["tries"] == 1 and budgets == [20000]
    assert got["places"] == {"1": [0, 0, 0, 0, 0, 0, 1, 1, 1, 1]}
    assert env.tries_note(got) == ""


def test_a_slow_page_gets_a_second_longer_opening(fake):
    got, budgets = fake("slow")
    assert budgets == [20000, 60000]
    assert got["state"].startswith("ready") and got["tries"] == 2 and got["first"] == "loading"
    assert got["places"]
    assert "second" in env.tries_note(got)


def test_a_page_that_never_gets_ready_still_reads_loading(fake):
    got, budgets = fake("never")
    assert budgets == [20000, 60000]
    assert got["state"] == "loading" and got["tries"] == 2 and got["places"] is None


def test_no_second_opening_when_asked_for_none(fake):
    got, budgets = fake("never", again=0)
    assert budgets == [20000] and got["state"] == "loading" and got["tries"] == 1


def test_the_check_lines_fail_on_a_page_still_loading():
    """The two Windows web lines refuse "loading" in plain words (never 'not counted')."""
    import inspect
    from fresing_render.pccheck import checks
    src = inspect.getsource(checks)
    for name in ("web3d_small", "web3d_under"):
        body = inspect.getsource(getattr(checks, name))
        assert 'got["state"] != "loading"' in body and "tries_note(got)" in body
    assert src.count('got["state"] != "loading"') >= 2


# ---------------------------------------------------------------- a real browser (skipped when there is none)


def _page(path, hang=False):
    import numpy as np
    from fresing_render.core import web3d
    g = web3d.Gltf()
    look = g.material({"pbrMetallicRoughness": {"baseColorFactor": [0.5, 0.5, 0.5, 1.0]}})
    pos = np.array([[-1, 0, -1], [1, 0, -1], [1, 0, 1], [-1, 0, 1]], float)
    mesh = g.mesh("p", pos, np.tile(np.array([[0, 127, 0]], np.int8), (4, 1)), None,
                  [(look, np.array([[0, 2, 1], [0, 3, 2]]))], quantize=False)
    g.node({"mesh": mesh})
    t = np.linspace(0, 2, 5)
    g.animation("A", t, [(0, "translation", np.array([[0.0, 0.3 * np.sin(x), 0.0] for x in t]))])
    st = env.settings(env.default_choice(), [-1, -1, 0], [1, 1, 0.5], plain=True)
    text = env.page_html("Read page test", g.glb(), st, animated=True)
    if hang:   # the model's bytes never come: the page waits for ever, without an error and without a read under way
        text = text.replace("<head>", "<head><script>Response.prototype.arrayBuffer = function () { return new "
                            "Promise(function () {}); };</script>", 1)
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_the_clock_is_held_from_the_page_s_first_script():
    """Task 0242: the hold is the page's first script (it was at the end of fr_page.js: Windows lost 0.5-3.7 s of the
    clock before it started), and fr_page.js no longer starts one of its own."""
    page = env.page_html("x", b"glTF", env.settings(env.default_choice(), [0, 0, 0], [1, 1, 1], plain=True))
    head = page[:page.index("</head>")]
    assert head.index("<script>") < head.index("<meta") and "frHeld" in head.split("</script>")[0]
    with open(os.path.join(os.path.dirname(env.__file__), "..", "web", "fr_page.js"), encoding="utf-8") as fh:
        assert "createObjectURL(new Blob(['x']))" not in fh.read()


def test_a_real_browser_reads_a_good_page_at_once_and_a_stuck_page_as_loading(tmp_path):
    """In this machine's Chromium (Edge on the owner's PC: the Windows job's PC check): a good page is ready at the first
    opening; a page that waits for ever reads "loading" after two openings, without a time-out ("not counted").
    Where no browser starts (GitHub's Linux machines: it aborts), the page's own hold is checked by the test above."""
    import time
    try:
        got = env.read_page(_page(tmp_path / "ok.html"), query="auto=0&frames=2&t=0.5&places=1", seconds=90, again=0)
    except RuntimeError:
        return
    assert got["state"].startswith("ready") and got["tries"] == 1 and got["places"], got["state"]
    t0 = time.time()
    got = env.read_page(_page(tmp_path / "hang.html", hang=True), query="auto=0&frames=2&places=1", seconds=90)
    assert got["state"] == "loading" and got["tries"] == 2 and not got["places"]
    assert time.time() - t0 < 60         # the clock still runs out: no time-out (that would be "not counted")
