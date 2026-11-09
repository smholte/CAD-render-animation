"""User guide (task 0021): the page builds with every chapter and picture, the Help-menu entry of the app
template finds and opens it, and the tooltip check reads every button and setting of the side panel."""

import importlib.util
import os
import re
import sys
import types

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TOOLS = os.path.join(ROOT, "tools")
DOCS = os.path.join(ROOT, "docs")
sys.path.insert(0, TOOLS)

CHAPTERS = ["layout", "start", "import", "structure", "looks", "motion", "scene", "animation", "queue", "tour", "tips",
            "troubleshooting"]


def _markdown_or_fail():
    try:
        import markdown  # noqa: F401
    except ImportError:
        pytest.fail("The user guide needs the package 'markdown': ~/venv/bin/pip install markdown "
                    "(CLAUDE.md section 4)")


@pytest.fixture(scope="module")
def page(tmp_path_factory):
    _markdown_or_fail()
    import build_guide
    out = tmp_path_factory.mktemp("guide") / "user_guide.html"
    build_guide.build(str(out))
    return out.read_text(encoding="utf-8")


def test_guide_has_every_chapter_in_order_and_in_the_contents(page):
    found = re.findall(r'<a id="([^"]+)"></a>\s*<h2', page)
    assert found == CHAPTERS
    for anchor in CHAPTERS:
        assert f'href="#{anchor}"' in page                     # contents list on the left


def test_guide_is_one_file_with_the_pictures_inside(page):
    assert 'src="img/' not in page                            # every picture embedded
    assert page.count("data:image/") >= 20
    import build_guide
    assert f"version {build_guide.version()}" in page


def test_notes_for_the_chats_stay_out_of_the_guide(page):
    assert "TOOLTIP STYLE GUIDE" not in page and "NOTES FOR THE CHATS" not in page
    src = open(os.path.join(DOCS, "USER-GUIDE.md"), encoding="utf-8").read()
    assert src.lstrip().startswith("<!--") and "TOOLTIP STYLE GUIDE" in src     # CLAUDE.md points here


def test_every_picture_is_used_and_small():
    src = open(os.path.join(DOCS, "USER-GUIDE.md"), encoding="utf-8").read()
    used = set(re.findall(r'src="img/([^"]+)"', src))
    on_disk = set(os.listdir(os.path.join(DOCS, "img")))
    assert used <= on_disk, f"missing pictures: {used - on_disk}"
    assert on_disk <= used, f"pictures no chapter uses: {on_disk - used}"
    for name in on_disk:                                      # the guide must stay small enough to e-mail
        assert os.path.getsize(os.path.join(DOCS, "img", name)) < 250_000, name


def test_missing_picture_is_an_error(tmp_path):
    _markdown_or_fail()
    import build_guide
    md = tmp_path / "guide.md"
    md.write_text('# T\n\n<a id="x"></a>\n## X\n\n<img class="panel" src="img/nope.png" alt="">\n', encoding="utf-8")
    with pytest.raises(FileNotFoundError, match="nope.png"):
        build_guide.build(str(tmp_path / "out.html"), source=str(md))


# ---- Help > Fresing Render user guide (app template) --------------------------------------------------

bpy = pytest.importorskip("bpy")


def _template():
    path = os.path.join(ROOT, "app_template", "fresing_render", "__init__.py")
    spec = importlib.util.spec_from_file_location("fr_app_template_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_help_menu_entry_opens_the_guide_of_the_installed_extension(tmp_path, monkeypatch):
    tpl = _template()
    pkg = tmp_path / "bl_ext" / "user_default" / "fresing_render"
    (pkg / "guide").mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "guide" / "user_guide.html").write_text("<h1>Fresing Render user guide</h1>", encoding="utf-8")
    fake = types.SimpleNamespace(__name__="bl_ext.user_default.fresing_render", __file__=str(pkg / "__init__.py"))
    import addon_utils
    monkeypatch.setattr(addon_utils, "modules", lambda *a, **k: [fake])
    opened = []
    monkeypatch.setattr(tpl, "open_path", opened.append)
    tpl.register()
    try:
        assert tpl._draw_help_menu in bpy.types.TOPBAR_MT_help._dyn_ui_initialize()
        assert tpl.guide_path() == str(pkg / "guide" / "user_guide.html")
        assert bpy.ops.fresing.user_guide() == {"FINISHED"}
        assert opened == [str(pkg / "guide" / "user_guide.html")]
        tpl.register()                                         # registered twice: still one menu entry
        assert bpy.types.TOPBAR_MT_help._dyn_ui_initialize().count(tpl._draw_help_menu) == 1
    finally:
        tpl.unregister()
    assert tpl._draw_help_menu not in bpy.types.TOPBAR_MT_help._dyn_ui_initialize()


def test_help_menu_entry_without_a_guide_says_what_to_do(monkeypatch):
    tpl = _template()
    import addon_utils
    monkeypatch.setattr(addon_utils, "modules", lambda *a, **k: [])
    opened = []
    monkeypatch.setattr(tpl, "open_path", opened.append)
    tpl.register()
    try:
        assert tpl.guide_path() == ""
        with pytest.raises(RuntimeError, match="Install.bat"):
            bpy.ops.fresing.user_guide()
        assert opened == []
    finally:
        tpl.unregister()


# ---- tooltip check ------------------------------------------------------------------------------------


def test_tooltip_verdicts():
    import tooltip_report as t
    assert t.judge("Max size (mm)", "Smaller than", "Size in mm")[0] == "weak"
    assert t.judge("Open", "Open file", "Open")[0] == "weak"
    assert t.judge("Hide", "Hide", "")[0] == "missing"
    assert t.judge("", "Remove", "(undocumented operator)")[0] == "missing"
    assert t.judge("Hide", "Hide", "Hide the selected parts (also in renders). Use Show all to bring them back")[0] == "ok"


def test_tooltip_check_reads_every_section():
    import tooltip_report as t
    items = t.collect()
    panels = {i.panel for i in items}
    for p in ("1 Import", "2 Structure", "3 Looks", "4 Motion", "5 Scene & Render", "6 Animation", "7 Render queue"):
        assert p in panels
    assert len(items) > 150 and all(i.verdict in ("missing", "weak", "ok") for i in items)
    by = {i.ident: i for i in items}
    hide = by["fresing.hide_selected"]                         # a known good one
    assert hide.verdict == "ok" and "Show all" in hide.tooltip
    # one operator on two buttons with one text: weak, so the lane gives each its own text
    stops = [i for i in items if i.ident.startswith("fresing.queue_stop")]
    assert len(stops) == 2 and (all(i.verdict == "weak" for i in stops)
                                or stops[0].tooltip != stops[1].tooltip)
    text = t.report(items, show_all=False)
    assert text.startswith("Buttons and settings found:")
    # sections are listed when something is missing or weak (since 0.2.16: nothing), and always with --all
    assert ("### " in text) == any(i.verdict != "ok" for i in items)
    assert "### 4 Motion" in t.report(items, show_all=True)
