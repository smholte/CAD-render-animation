"""The landing page (task 0047): tools/build_site.py, site/ and the picture kit's settings."""

import importlib.util
import json
import os
import re
import subprocess
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import build_site  # noqa: E402

KIT = os.path.join(ROOT, "site", "render_kit")


def _kit():
    spec = importlib.util.spec_from_file_location("make_site_pictures", os.path.join(KIT, "make_site_pictures.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = str(tmp_path_factory.mktemp("site") / "site")
    version = build_site.manifest_version()
    build_site.build(out, version=version, size=52_000_000)
    return out, version, open(os.path.join(out, "index.html"), encoding="utf-8").read()


def test_page_has_version_date_and_download(built):
    out, version, page = built
    entry = build_site.changelog_entry(version)
    url = f"https://github.com/smholte/CAD-render-animation/releases/download/v{version}/FresingRender-{version}-windows.zip"
    assert f'href="{url}"' in page
    assert f"Version {version} · {entry['date']} · 52 MB" in page
    assert f"What's new in {version}" in page
    assert "{{" not in page


def test_page_checks_pass(built):
    out, _version, _page = built
    assert build_site.check(out) == []


def test_every_picture_video_and_guide_exists(built):
    out, _version, page = built
    media = build_site.load_media()
    assert media.get("hero"), "no picture or video at the top"
    assert len(media["pictures"]) >= 3
    for f in build_site.media_files(media):
        assert os.path.getsize(os.path.join(out, "media", f)) > 1000, f
        assert f"media/{f}" in page
    assert os.path.getsize(os.path.join(out, "guide", "index.html")) > 100_000
    assert 'href="guide/"' in page
    for logo in ("fresing-logo_compact_reversed.svg", "fresing-logo_full_reversed.svg", "fresing-app-icon.svg"):
        assert os.path.exists(os.path.join(out, "brand", logo))


def test_every_model_credited(built):
    _out, _version, page = built
    media = build_site.load_media()
    credits = open(os.path.join(ROOT, "site", "CREDITS.md"), encoding="utf-8").read()
    for mid in build_site.used_models(media):
        credit = media["models"][mid]["credit"]
        assert build_site._esc(credit) in page, mid
        assert credit in credits, mid


def test_links_only_to_github_and_fresing(built):
    _out, _version, page = built
    hosts = {h for h in re.findall(r'(?:href|src)="https://([^/"]+)', page)}
    credit_part = page[page.index('<ul class="credits">'):page.index("</ul>", page.index('<ul class="credits">'))]
    outside = page.replace(credit_part, "")
    assert {h for h in re.findall(r'(?:href|src)="https://([^/"]+)', outside)} <= {"github.com", "fresing.nl"}
    assert "fresing.nl" in hosts
    assert "<script" not in page.lower() and "fonts.googleapis" not in page


def test_check_finds_problems(built, tmp_path):
    import shutil
    out, _version, page = built
    bad = str(tmp_path / "bad")
    shutil.copytree(out, bad)
    with open(os.path.join(bad, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(page.replace("</main>", '<a href="https://example.com/x">x</a><img src="media/none.jpg"></main>'))
    problems = build_site.check(bad)
    assert any("example.com" in p for p in problems)
    assert any("none.jpg" in p for p in problems)


def test_media_small_enough_and_no_model_files():
    media = build_site.load_media()
    for f in build_site.media_files(media):
        size = os.path.getsize(os.path.join(build_site.MEDIA, f))
        limit = build_site.VIDEO_MAX if f.endswith(".mp4") else build_site.JPG_MAX
        assert size <= limit * 1.1, f
    for d, _dirs, files in os.walk(os.path.join(ROOT, "site")):
        for f in files:
            assert not f.lower().endswith((".step", ".stp", ".f3d", ".iges", ".igs", ".sldasm", ".sldprt")), f
    # media.json lists nothing that is not there, and nothing is there that it does not list
    there = set(os.listdir(build_site.MEDIA)) - {"media.json"}
    assert there == set(build_site.media_files(media))


def test_kit_settings_files_read():
    kit = _kit()
    for name in ("models.ini", "placeholders.ini"):
        general, models = kit.read_settings(os.path.join(KIT, name))
        assert models
        for m in models:
            assert m["credit"] and m["views"]
    general, models = kit.read_settings(os.path.join(KIT, "models.ini"))
    assert sum(m["video"] == "turntable" for m in models) == 1


@pytest.mark.parametrize("line,reason", [
    ("look = SHINY", "look = SHINY"),
    ("views = BELOW", "BELOW unknown"),
    ("surroundings = MOON", "surroundings = MOON"),
])
def test_kit_settings_plain_problems(tmp_path, line, reason):
    kit = _kit()
    p = tmp_path / "m.ini"
    p.write_text(f"[a]\nfile = a.step\ncredit = A by B\n{line}\n", encoding="utf-8")
    with pytest.raises(ValueError, match=reason):
        kit.read_settings(str(p))
    p.write_text("[a]\nfile = a.step\n", encoding="utf-8")
    with pytest.raises(ValueError, match="credit"):
        kit.read_settings(str(p))


def test_kit_bat_finds_installed_blender():
    bat = open(os.path.join(KIT, "Make site pictures.bat"), encoding="utf-8").read()
    assert r"%LOCALAPPDATA%\FresingRender" in bat
    assert "blender-*-windows-x64" in bat and "--background" in bat and "make_site_pictures.py" in bat
    attrs = open(os.path.join(ROOT, ".gitattributes"), encoding="utf-8").read()
    assert "*.bat text eol=crlf" in attrs


def test_kit_renders_a_test_model(tmp_path):
    """The kit end to end on a test model, small, on the processor (Blender as a Python module)."""
    pytest.importorskip("bpy")
    ini = tmp_path / "m.ini"
    ini.write_text("[gantry]\nfile = test_gantry.step\nviews = ISO\nlook = PRODUCT\n"
                   "credit = Test gantry: generic test model\n", encoding="utf-8")
    out = tmp_path / "out"
    res = subprocess.run([sys.executable, os.path.join(KIT, "make_site_pictures.py"),
                          os.path.join(ROOT, "fresing_render", "data"), str(out), str(ini), "--small"],
                         capture_output=True, text=True, timeout=600)
    assert res.returncode == 0, res.stdout[-3000:] + res.stderr[-3000:]
    info = json.load(open(out / "send" / "site_pictures.json", encoding="utf-8"))
    assert [i["file"] for i in info["items"]] == ["gantry_iso.jpg"]
    assert info["models"]["gantry"]["credit"] == "Test gantry: generic test model"
    assert (out / "send" / "gantry_iso.jpg").stat().st_size > 1000
    assert (out / "full" / "gantry.blend").exists()
    assert (out / "contact_sheet.html").exists() and (out / "Fresing site pictures.zip").exists()


def test_pages_workflow():
    """The Pages workflow: after a release (called from tests.yml), on site pushes to main, by hand; a one-line
    `run:` holding ': ' is a YAML error that silently stopped every run (found on the first push of task 0047)."""
    wf = open(os.path.join(ROOT, ".github", "workflows", "pages.yml"), encoding="utf-8").read()
    for key in ("workflow_dispatch:", "workflow_call:", "branches: [main]", '"site/**"', "pages: write",
                "id-token: write", "actions/upload-pages-artifact@", "actions/deploy-pages@", "tools/build_site.py"):
        assert key in wf, key
    for line in wf.splitlines():
        m = re.match(r"^\s*(?:- )?run: (.*)$", line)
        if m and m.group(1) not in ("|", ">-"):
            assert ": " not in m.group(1), line
    tests = open(os.path.join(ROOT, ".github", "workflows", "tests.yml"), encoding="utf-8").read()
    job = tests[tests.index("\n  pages:"):]
    assert "needs: [release-latest]" in job and "needs.release-latest.result == 'success'" in job
    assert "!cancelled()" in job and "uses: ./.github/workflows/pages.yml" in job
