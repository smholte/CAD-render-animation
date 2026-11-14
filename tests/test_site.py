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
    model_pages = "".join(open(os.path.join(out, "model", w["id"], "index.html"), encoding="utf-8").read()
                          for w in build_site.web_models(media))
    for f in build_site.media_files(media):
        if f.endswith(build_site.PAGE_SUFFIX):                    # an export's own page: model/<id>/index.html
            assert os.path.getsize(os.path.join(build_site.MEDIA, f)) > 1000, f
            continue
        assert os.path.getsize(os.path.join(out, "media", f)) > 1000, f
        assert f"media/{f}" in page or f"../../media/{f}" in model_pages, f
    assert os.path.getsize(os.path.join(out, "guide", "index.html")) > 100_000
    assert 'href="guide/"' in page
    for logo in ("fresing-logo_compact_reversed.svg", "fresing-logo_full_reversed.svg", "fresing-app-icon.svg"):
        assert os.path.exists(os.path.join(out, "brand", logo))


def test_pages_workflow_installs_what_the_build_imports():
    """The Pages job has a bare Python: build_site.py imports fresing_render.core.web3d (numpy) since task 0099 –
    0.2.77's landing-page job failed without it."""
    wf = open(os.path.join(ROOT, ".github", "workflows", "pages.yml"), encoding="utf-8").read()
    step = wf.split("name: Build the page")[1].split("- uses:")[0]
    assert "^markdown==" in step and "^numpy==" in step and "shell: bash" in step


def test_turn_it_yourself(built, tmp_path):
    """Tasks 0099, 0111: a card per web model on the landing page (no script, nothing of a model loaded there), each
    opening its own page with the viewer from the site itself, a Pause button, the credit and a link back; the old
    address model/ goes on to the first model."""
    out, _version, page = built
    media = build_site.load_media()
    items = build_site.web_models(media)
    assert [w["id"] for w in items] == ["test_atc", "thor"]
    assert "web_model" not in media                                        # converted to the list
    assert 'id="turn"' in page and 'href="#turn"' in page
    assert "<script" not in page.lower()                                   # the models load only when opened
    assert not re.search(r'(src|href)="[^"]*\.(glb|page\.html)"', page)
    turn = page[page.index('<section id="turn"'):page.index("</section>", page.index('<section id="turn"'))]
    assert turn.count('<li class="card">') == len(items)
    for w in items:
        assert w["model"] in media["models"] and w.get("poster") and w.get("caption")
        card = turn[turn.index(f'href="model/{w["id"]}/"'):]
        card = card[:card.index("</li>")]
        assert f'media/{w["poster"]}' in card and "Open the 3D model" in card
        assert re.search(r"\d+(\.\d)? MB", card), card
        viewer = open(os.path.join(out, "model", w["id"], "index.html"), encoding="utf-8").read()
        assert 'id="fr-play"' in viewer and 'href="../../"' in viewer
        assert build_site._esc(media["models"][w["model"]]["credit"]) in viewer
        assert not re.search(r'<script[^>]+src="https?://', viewer)
        if build_site.own_page(w):
            for f in build_site.VENDOR_PAGE:
                assert f'<script src="../../vendor/{f}"></script>' in viewer, f
            assert "three.js (MIT)" in viewer
        else:
            assert f'src="../../vendor/{build_site.web3d.MV_FILE}"' in viewer
            assert f'data-src="../../media/{w["file"]}"' in viewer
        for f in build_site.vendor_files(media):
            assert os.path.getsize(os.path.join(out, "vendor", f)) > 1000
    thor = open(os.path.join(out, "model", "thor", "index.html"), encoding="utf-8").read()
    assert 'this 3D file <a href="https://creativecommons.org/licenses/by-sa/4.0/">CC BY-SA 4.0</a>' in thor
    first = open(os.path.join(out, "model", "index.html"), encoding="utf-8").read()
    assert f'url={items[0]["id"]}/' in first and "<script" not in first.lower()
    # the checks catch a model page that loads from another site, and a model that may not be published
    w = items[0]
    bad = dict(media, web_models=[dict(w, model="fresing_400")])
    assert any("may not be published" in p for p in build_site.check_model(out, bad, "model-viewer three.js"))
    path = os.path.join(out, "model", w["id"], "index.html")
    viewer = open(path, encoding="utf-8").read()
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(viewer.replace("../../vendor/", "https://cdn.example.com/"))
    try:
        assert any("another site" in p for p in build_site.check_model(out, media, "model-viewer three.js"))
    finally:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(viewer)
    src = os.path.join(build_site.MEDIA, w["file"])
    with pytest.raises(SystemExit, match="not public"):
        build_site.web_model(src, "fresing_400", "")
    with pytest.raises(SystemExit, match="add 'nobody'"):
        build_site.web_model(_fake_glb(tmp_path), "nobody", "")


def _loop_tracks(data):
    """(seconds, [first and last key of every channel]) of a .glb's one animation."""
    import numpy as np
    doc, binary = build_site.web3d.read_glb(data)
    assert len(doc.get("animations", [])) == 1
    anim = doc["animations"][0]
    seconds = max(float(doc["accessors"][s["input"]]["max"][0]) for s in anim["samplers"])
    ends, hidden = [], set()
    for c in anim["channels"]:
        v = np.asarray(build_site.web3d.accessor_array(doc, binary, anim["samplers"][c["sampler"]]["output"]),
                       np.float64)
        ends.append((c["target"]["node"], v[0], v[-1]))
        if c["target"]["path"] == "scale" and not v[0].any() and not v[-1].any():
            hidden.add(c["target"]["node"])            # a tool copy hidden at both ends: where it is does not show
    return seconds, [(a, b) for node, a, b in ends if node not in hidden], anim


@pytest.mark.parametrize("wid,seconds,most_mb", [("test_atc", 10.1, 2.0), ("thor", 10.0, 8.0)])
def test_web_models_loop(wid, seconds, most_mb):
    """Task 0111: each model holds one animation of its loop's length whose last moment is its first (no jump when
    it starts again), small enough for a phone; the test mill's tools are shown and hidden by STEP scale keys."""
    import numpy as np
    w = next(x for x in build_site.web_models(build_site.load_media()) if x["id"] == wid)
    path = os.path.join(build_site.MEDIA, w["file"])
    data = build_site.glb_of(path)
    assert build_site.web3d.problems(data) == []
    assert len(data) <= most_mb * 1e6, f"{len(data) / 1e6:.1f} MB"
    got, ends, anim = _loop_tracks(data)
    assert abs(got - seconds) < 0.06 and abs(w["seconds"] - got) < 0.01
    for first, last in ends:
        assert np.allclose(first, last, atol=2e-4) or np.allclose(first, -last, atol=2e-4), (first, last)
    steps = [s for s in anim["samplers"] if s["interpolation"] == "STEP"]
    assert bool(steps) == (wid == "test_atc")          # the tools the arm and the pots carry
    info = build_site.web3d.summary(data)
    assert info["parts"] > 20 and all(n == "Model" or n.startswith("Part ") for n in info["names"])
    page = open(path, encoding="utf-8").read()
    st = build_site.web3d_env.page_settings(page)
    assert st.get("light", {}).get("light") == "SOFT" and st.get("animated") is True


def _fake_glb(tmp_path, seconds=2.0):
    """A one-triangle model that moves for ``seconds``."""
    import numpy as np
    g = build_site.web3d.Gltf()
    m = g.material({"name": "Look", "pbrMetallicRoughness": {"baseColorFactor": [0.5, 0.5, 0.5, 1.0]}})
    mesh = g.mesh("Mesh", np.array([[0, 0, 0], [0.1, 0, 0], [0, 0.1, 0]], float),
                  np.array([[0, 0, 127]] * 3, np.int8), None, [(m, np.array([[0, 1, 2]]))], quantize=False)
    root = g.node({"name": "Model"})
    node = g.place_mesh({"name": "Part 1"}, mesh, root)
    g.animation("Loop", np.array([0.0, seconds]), [(node, "translation", np.array([[0, 0, 0], [0, 0, 0.1]]))])
    path = tmp_path / "fake.glb"
    path.write_bytes(g.glb())
    return str(path)


def test_add_and_remove_a_web_model(tmp_path, monkeypatch):
    """Task 0111: one command adds a model (card, page, poster; a credit in media.json and CREDITS.md first) and one
    takes it out again, files and all; its place among the cards follows --order."""
    import shutil
    site = tmp_path / "site"
    shutil.copytree(os.path.join(ROOT, "site"), site, ignore=shutil.ignore_patterns("render_kit"))
    monkeypatch.setattr(build_site, "SITE", str(site))
    monkeypatch.setattr(build_site, "MEDIA", str(site / "media"))
    monkeypatch.setattr(build_site, "MEDIA_JSON", str(site / "media" / "media.json"))
    shots = []

    def poster(src, dst):
        shots.append(src)
        shutil.copy2(os.path.join(ROOT, "site", "media", "test_atc_poster.jpg"), dst)
        return True
    monkeypatch.setattr(build_site, "poster_of_model", poster)
    glb = _fake_glb(tmp_path)
    with pytest.raises(SystemExit, match="add 'gizmo'"):
        build_site.web_model(glb, "gizmo", "A gizmo")
    media = build_site.load_media()
    media["models"]["gizmo"] = {"title": "Gizmo", "credit": "Gizmo by Nobody, CC0 1.0", "licence": "CC0 1.0"}
    build_site.save_media(media)
    with pytest.raises(SystemExit, match="CREDITS.md"):
        build_site.web_model(glb, "gizmo", "A gizmo")
    with open(site / "CREDITS.md", "a", encoding="utf-8") as fh:
        fh.write("\n- Gizmo by Nobody, CC0 1.0\n")
    before = [w["id"] for w in build_site.web_models(build_site.load_media())]
    build_site.main(["--web-model", glb, "--model", "gizmo", "--caption", "A gizmo turning", "--order", "1",
                     "--title", "The gizmo"])
    media = build_site.load_media()
    items = build_site.web_models(media)
    assert [w["id"] for w in items] == ["gizmo"] + before and shots == [glb]
    g = items[0]
    assert g["file"] == "gizmo.glb" and g["poster"] == "gizmo_poster.jpg" and g["seconds"] == 2.0
    assert (site / "media" / "gizmo.glb").exists() and (site / "media" / "gizmo_poster.jpg").exists()
    out = str(tmp_path / "out")
    build_site.build(out, version=build_site.manifest_version(), guide=False)
    page = open(os.path.join(out, "index.html"), encoding="utf-8").read()
    assert 'href="model/gizmo/"' in page and "The gizmo" in page and "A gizmo turning" in page
    viewer = open(os.path.join(out, "model", "gizmo", "index.html"), encoding="utf-8").read()
    assert 'data-src="../../media/gizmo.glb"' in viewer and " autoplay" in viewer and 'id="fr-play"' in viewer
    assert "Gizmo by Nobody" in viewer
    assert "url=gizmo/" in open(os.path.join(out, "model", "index.html"), encoding="utf-8").read()
    assert [p for p in build_site.check(out) if "guide" not in p] == []
    # replacing keeps its place; a model too big is refused
    build_site.web_model(glb, "gizmo", "Again")
    assert [w["id"] for w in build_site.web_models(build_site.load_media())][0] == "gizmo"
    monkeypatch.setattr(build_site, "WEB_MODEL_MAX", 100)
    with pytest.raises(SystemExit, match="at most"):
        build_site.web_model(glb, "gizmo", "")
    build_site.main(["--remove-web-model", "gizmo"])
    media = build_site.load_media()
    assert [w["id"] for w in build_site.web_models(media)] == before
    assert not (site / "media" / "gizmo.glb").exists() and not (site / "media" / "gizmo_poster.jpg").exists()
    assert "gizmo" not in media["models"]
    with pytest.raises(SystemExit, match="no web model"):
        build_site.remove_web_model("gizmo")


def test_old_media_json_still_reads():
    """media.json before task 0111 had one "web_model": it is read as a list of one."""
    old = {"web_model": {"file": "test_atc.glb", "caption": "x", "model": "test_atc", "poster": "p.jpg"}}
    assert build_site.web_models(old) == [dict(old["web_model"], id="test_atc")]
    assert build_site.media_files(old) == ["test_atc.glb", "p.jpg"]


def test_export_folder_picks_its_own_page(tmp_path):
    """--web-model with an export folder: its three.js page (surroundings or baked light) is used, a plain
    model-viewer page is not (model-viewer shows the .glb itself)."""
    glb = _fake_glb(tmp_path)
    (tmp_path / "fake.html").write_text('<html><script id="fr-env">{}</script></html>', encoding="utf-8")
    assert build_site.export_files(str(tmp_path)) == (glb, str(tmp_path / "fake.html"))
    (tmp_path / "fake.html").write_text("<html><model-viewer></model-viewer></html>", encoding="utf-8")
    assert build_site.export_files(str(tmp_path)) == (glb, "")
    assert build_site.animation_seconds(open(glb, "rb").read()) == 2.0


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
    assert {h for h in re.findall(r'(?:href|src)="https://([^/"]+)', outside)} <= {"github.com", "fresing.nl", "www.blender.org"}
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
        limit = (build_site.VIDEO_MAX if f.endswith(".mp4") else
                 build_site.WEB_MODEL_WARN if f.endswith((".glb", ".html")) else build_site.JPG_MAX)
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
    pytest.importorskip("OCP")            # the docs-mode run has no STEP reader; the full run has
    ini = tmp_path / "m.ini"
    ini.write_text("[gantry]\nfile = test_gantry.step\nviews = ISO\nlook = PRODUCT\n"
                   "colours =\n    * = powder_coat RAL 2004\n"
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
    assert re.search(r"colours: \* \d+", (out / "log.txt").read_text(encoding="utf-8"))
    assert (out / "contact_sheet.html").exists()
    assert [f for f in os.listdir(out) if f.startswith("site_pictures_") and f.endswith(".zip")]   # task 0112


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


def test_fcstd_to_step(tmp_path):
    """tools/fcstd_to_step.py: shapes stored in a FreeCAD file become named, placed parts of a STEP assembly."""
    pytest.importorskip("OCP")
    import zipfile

    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.BRepTools import BRepTools
    from OCP.gp import gp_Trsf, gp_Vec
    from OCP.TopLoc import TopLoc_Location

    import fcstd_to_step
    box = BRepPrimAPI_MakeBox(10.0, 20.0, 30.0).Shape()
    t = gp_Trsf()
    t.SetTranslation(gp_Vec(100.0, 0.0, 0.0))
    BRepTools.Write_s(box.Located(TopLoc_Location(t)), str(tmp_path / "PartShape.brp"))
    xml = ('<Document><ObjectData><Object name="planeConstraint01"><Properties></Properties></Object>'
           '<Object name="Frame_SubAssembly_01"><Properties>'
           '<Property name="Shape" type="Part::PropertyPartShape">\n  <Part file="PartShape.brp"/>'
           '</Property></Properties></Object></ObjectData></Document>')
    src = tmp_path / "a.fcstd"
    with zipfile.ZipFile(src, "w") as z:
        z.writestr("Document.xml", xml)
        z.write(tmp_path / "PartShape.brp", "PartShape.brp")
    out = tmp_path / "a.step"
    assert fcstd_to_step.convert(str(src), str(out)) == 1
    text = out.read_text(errors="replace")
    assert "FRAME PART 1" in text and "Frame SubAssembly" in text and "PLANECONSTRAINT" not in text.upper()
    assert "100." in text                       # placed where it was


def test_a4_to_step(tmp_path):
    """tools/a4_to_step.py: an Assembly4 link to a body in another file is placed where the link says."""
    pytest.importorskip("OCP")
    import zipfile

    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.BRepTools import BRepTools
    from OCP.gp import gp_Trsf, gp_Vec
    from OCP.TopLoc import TopLoc_Location

    BRepTools.Write_s(BRepPrimAPI_MakeBox(10.0, 20.0, 30.0).Shape(), str(tmp_path / "PartShape.brp"))
    with zipfile.ZipFile(tmp_path / "Plate.FCStd", "w") as z:
        z.writestr("Document.xml", '<Document><Objects><Object type="PartDesign::Body" name="Body"/></Objects>'
                   '<ObjectData>\n        <Object name="Body">\n<Property name="Shape" type="Part::PropertyPartShape">'
                   '\n<Part file="PartShape.brp"/></Property>\n        </Object>\n</ObjectData></Document>')
        z.write(tmp_path / "PartShape.brp", "PartShape.brp")
    pl = 'Px="250" Py="0" Pz="0" Q0="0" Q1="0" Q2="0" Q3="1" A="0" Ox="0" Oy="0" Oz="1"'
    with zipfile.ZipFile(tmp_path / "Assembly.FCStd", "w") as z:
        z.writestr("Document.xml", '<Document><Objects><Object type="App::Part" name="Model"/>'
                   '<Object type="App::Link" name="Plate_Link"/></Objects><ObjectData>\n'
                   '        <Object name="Model">\n<Property name="Group" type="App::PropertyLinkList">'
                   '<LinkList count="1"><Link value="Plate_Link"/></LinkList></Property>\n        </Object>\n'
                   '        <Object name="Plate_Link">\n<Property name="LinkedObject" type="App::PropertyXLink">'
                   '<XLink file="Plate.FCStd" stamp="" name="Body"/></Property>\n'
                   f'<Property name="Placement" type="App::PropertyPlacement"><PropertyPlacement {pl}/></Property>\n'
                   '        </Object>\n</ObjectData></Document>')
    out = tmp_path / "a.step"
    # a library part inside the assembly file (as Thor's bearings and board): its piece keeps its own place (z 40)
    t = gp_Trsf()
    t.SetTranslation(gp_Vec(0.0, 0.0, 40.0))
    BRepTools.Write_s(BRepPrimAPI_MakeBox(7.0, 7.0, 7.0).Shape().Located(TopLoc_Location(t)), str(tmp_path / "Lib.brp"))
    with zipfile.ZipFile(tmp_path / "Assembly.FCStd", "a") as z:
        z.write(tmp_path / "Lib.brp", "PartShape9.brp")
    _add_library(tmp_path / "Assembly.FCStd")
    res = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "a4_to_step.py"), str(tmp_path / "Assembly.FCStd"),
                          str(out), "Test arm"], capture_output=True, text=True, timeout=120)
    assert res.returncode == 0, res.stdout[-2000:] + res.stderr[-2000:]
    assert "2 parts, 2 unique" in res.stdout
    text = out.read_text(errors="replace")
    assert "Test arm" in text and "Plate" in text and "250." in text
    assert "Piece" in text and re.search(r"\(0\.,0\.,40\.\)", text.replace(" ", "")), "the library piece lost its place"


def _add_library(path):
    """Rewrite Document.xml of the test assembly with a library App::Part 'Lib' (piece at z 40) and a link to it."""
    import zipfile
    with zipfile.ZipFile(path) as z:
        files = {n: z.read(n) for n in z.namelist()}
    d = files["Document.xml"].decode()
    d = d.replace('<Object type="App::Link" name="Plate_Link"/>', '<Object type="App::Link" name="Plate_Link"/>'
                  '<Object type="App::Link" name="Lib_Link"/><Object type="App::Part" name="Lib"/>'
                  '<Object type="Part::Feature" name="Piece"/>')
    d = d.replace('<Link value="Plate_Link"/></LinkList>', '<Link value="Plate_Link"/><Link value="Lib_Link"/></LinkList>')
    d = d.replace("</ObjectData>",
                  '        <Object name="Lib_Link">\n<Property name="LinkedObject" type="App::PropertyLink">'
                  '<Link value="Lib"/></Property>\n        </Object>\n'
                  '        <Object name="Lib">\n<Property name="Group" type="App::PropertyLinkList">'
                  '<LinkList count="1"><Link value="Piece"/></LinkList></Property>\n        </Object>\n'
                  '        <Object name="Piece">\n<Property name="Shape" type="Part::PropertyPartShape">'
                  '\n<Part file="PartShape9.brp"/></Property>\n        </Object>\n</ObjectData>')
    files["Document.xml"] = d.encode()
    with zipfile.ZipFile(path, "w") as z:
        for n, data in files.items():
            z.writestr(n, data)


def test_kit_colour_lines(tmp_path):
    kit = _kit()
    assert kit.parse_colours("\n  *screw* = black_oxide\n  art* = plastic_matte RAL 2004\n", "a") == [
        ("*screw*", "black_oxide", ""), ("art*", "plastic_matte", "RAL 2004")]
    with pytest.raises(ValueError, match="part name = material"):
        kit.parse_colours("\n  art* plastic_matte\n", "a")
    _general, models = kit.read_settings(os.path.join(KIT, "models.ini"))
    thor = next(m for m in models if m["id"] == "thor")
    assert ("art*", "plastic_matte", "RAL 2004") in thor["colours"]
    from fresing_render.core import materials_lib, ral
    for m in models:
        for _pattern, mat, colour in m["colours"]:
            assert mat in materials_lib.MATERIALS, mat
            assert not colour or ral.parse_colour(colour), colour


def test_built_on_blender_section(built):
    """The page says what it is built on and that the installer sets Blender up as a standalone app."""
    _out, _version, page = built
    sec = page[page.index('<section id="blender"'):page.index("</section>", page.index('<section id="blender"'))]
    assert "Built on Blender" in sec and 'href="https://www.blender.org"' in sec
    assert f"Blender {build_site.blender_version()} LTS" in sec and "standalone app" in sec
    assert "not made or endorsed by the Blender Foundation" in sec
    media = build_site.load_media()
    if media.get("feature"):
        assert f'media/{media["feature"]["file"]}' in sec
