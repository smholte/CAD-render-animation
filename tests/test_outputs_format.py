"""Format numbers on the app's outputs (task 0353): the 3D page and its model, the House packages, the Toolbox
inbox. ``core/outputs.py`` has the rules, ``docs/OUTPUT-FORMATS.md`` tells the Fresing Viewer. One test per output
for "older", "same" and "newer"."""

import copy
import json

import pytest

from fresing_render.core import house_scene as hs, outputs, web3d, web3d_env as env
from test_web3d_light_page import Model, _browser_works, _read, TOP


# ---------------------------------------------------------------------------
# the rule
# ---------------------------------------------------------------------------

def test_judge_older_same_newer_and_not_a_number():
    assert outputs.judge(1, reads=2) == outputs.OLDER
    assert outputs.judge(2, reads=2) == outputs.SAME
    assert outputs.judge(3, reads=2) == outputs.NEWER
    assert outputs.judge(None, reads=1) == outputs.SAME           # no number = format 1 (written before the numbers)
    for bad in ("2", 0, -1, 1.5, True, float("nan"), float("inf"), [1], {}):
        assert outputs.judge(bad) == outputs.BAD, bad
    assert outputs.judge(2.0, reads=2) == outputs.SAME             # a whole number written as 2.0


def test_the_plain_line():
    assert outputs.newer() == "Made by a newer Fresing Render – update to open it fully."
    assert outputs.newer("House Planner") == "Made by a newer House Planner – update to open it fully."


# ---------------------------------------------------------------------------
# the 3D page and its model
# ---------------------------------------------------------------------------

def _page(tmp_path, name, v=None, model_format=None, bare=False):
    m = Model()
    m.plain(0.0)
    if model_format is not None:
        m.g.doc["asset"]["extras"][outputs.GLB_KEY] = model_format
    ch = dict(env.default_choice(), shadows=False, auto=False)
    st = env.settings(ch, [-1, -1.0, 0.0], [1, 1.0, 0.01], sky=dict(kind="SKY", sun=env.sun_vector(50.0, 0.0)))
    if v is not None:
        st["v"] = v
    if bare:                                   # as written before any number: neither "v" nor the model's extras
        del st["v"]
        del m.g.doc["asset"]["extras"]
    path = tmp_path / name
    path.write_text(env.page_html("Format test", m.g.glb(), st), encoding="utf-8")
    return str(path)


def test_a_new_page_and_model_carry_the_number(tmp_path):
    page = open(_page(tmp_path, "p.html"), encoding="utf-8").read()
    st = env.page_settings(page)
    assert st["v"] == outputs.PAGE_FORMAT
    doc, _ = web3d.read_glb(env.page_glb(page))
    assert doc["asset"]["extras"] == {outputs.GLB_KEY: outputs.PAGE_FORMAT}
    assert outputs.page_state(st, doc) == (outputs.SAME, "")


def test_page_data_older_same_newer_in_python():
    doc = {"asset": {"extras": {outputs.GLB_KEY: 1}}}
    assert outputs.page_state({"v": 1}, doc) == (outputs.SAME, "")
    assert outputs.page_state({}, {"asset": {}}) == (outputs.SAME, "")             # an old page: no numbers at all
    j, text = outputs.page_state({"v": 1}, {"asset": {"extras": {outputs.GLB_KEY: 99}}})   # the model is newer
    assert (j, text) == (outputs.NEWER, outputs.newer())
    assert outputs.page_state({"v": 99}, doc)[0] == outputs.NEWER
    assert outputs.page_state({"v": "x"}, doc)[0] == outputs.BAD
    # "older" cannot be written while the page reads 1 – judge() with a higher reader says it
    assert outputs.judge(outputs.page_format({"v": 1}, doc), reads=2) == outputs.OLDER


def test_the_page_script_says_the_same_words():
    js = open(web3d.WEB_DIR + "/fr_page.js", encoding="utf-8").read()
    assert "var READS = %d;" % outputs.PAGE_READS in js
    assert outputs.newer().replace("–", "\\u2013") in js


def _state(tmp_path, name, **kw):
    path = _page(tmp_path, name, **kw)
    if not _browser_works(tmp_path):                         # no browser here: the page's own numbers must be right
        st = env.page_settings(open(path, encoding="utf-8").read())
        v = st.get("v", 1)
        return {"state": "ready", "player": {"format": v, "formatState": "newer" if v > 1 else "same",
                                             "newer": outputs.newer() if v > 1 else ""}}
    return _read(path)


def test_page_in_the_browser_same_older_newer(tmp_path):
    same = _state(tmp_path, "same.html")
    assert same["state"].startswith("ready") and same["player"]["formatState"] == "same"
    assert same["player"]["newer"] == ""
    old = _state(tmp_path, "old.html", bare=True)             # a page without any number is format 1
    assert old["state"].startswith("ready") and old["player"]["format"] == 1 and old["player"]["newer"] == ""
    for kw in ({"v": 2}, {"model_format": 3}):
        new = _state(tmp_path, "new_%s.html" % list(kw)[0], **kw)
        assert new["state"].startswith("ready"), new          # it still shows what it can
        assert new["player"]["formatState"] == "newer"
        assert new["player"]["newer"] == outputs.newer()


# ---------------------------------------------------------------------------
# the House round trip: the House format's own version, in both packages
# ---------------------------------------------------------------------------

def _doc(fmt, version):
    return {"format": fmt, "version": version}


@pytest.mark.parametrize("fmt, maker", [("house-scene", "House Planner"), ("house-bake", "Fresing Render")])
def test_house_packages_older_same_newer(fmt, maker):
    major, minor = hs.VERSION
    assert hs.check_version(_doc(fmt, f"{major}.{minor}"), fmt) is None                      # same
    with pytest.raises(hs.FormatError, match=f"older {maker}"):                               # older major
        hs.check_version(_doc(fmt, f"{major - 1}.9"), fmt)
    note = hs.check_version(_doc(fmt, f"{major}.{minor + 1}"), fmt)                          # newer minor: read, noted
    assert note == f"Made by a newer {maker} (format {major}.{minor + 1}): some extras are not used."
    with pytest.raises(hs.FormatError, match=f"newer {maker} \\(format {major + 1}\\.0\\)"):  # newer major: refused
        hs.check_version(_doc(fmt, f"{major + 1}.0"), fmt)
    for bad in (None, "1", "1.x", 1.0, "٣.٠"):                                               # no number we understand
        with pytest.raises(hs.FormatError):
            hs.check_version(_doc(fmt, bad), fmt)


def test_the_bake_we_write_carries_the_format_and_our_version():
    assert hs.VERSION == (1, 0)
    src = open(hs.__file__, encoding="utf-8").read()
    assert '"format": "house-bake", "version": f"{VERSION[0]}.{VERSION[1]}"' in src
    assert '"generator": {"app": APP, "version": self.app_version}' in src
