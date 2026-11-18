"""About Fresing Render and the licence files (task 0206): the files are in the extension and in both release zips,
the installer prints the licence line and switches Blender's extension sync off, the texts are the real ones."""

import filecmp
import os
import re
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PKG = os.path.join(ROOT, "fresing_render")
LIC = os.path.join(PKG, "licenses")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from fresing_render.core import about  # noqa: E402


def test_the_package_carries_the_licence_files():
    assert about.missing(PKG) == []
    assert about.folder(PKG) == LIC


def test_copies_are_the_repository_files():
    """The package copies are byte for byte the ones at the repository's root (change both, or the test says so)."""
    for name, src in (("LICENSE", "LICENSE"), ("THIRD-PARTY-NOTICES.md", "THIRD-PARTY-NOTICES.md"),
                      ("COMPANY-USE.md", os.path.join("docs", "COMPANY-USE.md"))):
        assert filecmp.cmp(os.path.join(LIC, name), os.path.join(ROOT, src), shallow=False), \
            f"fresing_render/licenses/{name} differs from {src}: copy it again"


def test_licence_is_the_gpl_3():
    text = open(os.path.join(LIC, "LICENSE"), encoding="utf-8").read()
    assert "GNU GENERAL PUBLIC LICENSE" in text and "Version 3, 29 June 2007" in text


def test_every_library_text_is_listed_and_every_listed_text_is_there():
    folder = os.path.join(LIC, "third-party")
    sources = open(os.path.join(folder, "SOURCES.txt"), encoding="utf-8").read()
    texts = sorted(f for f in os.listdir(folder) if f != "SOURCES.txt")
    assert len(texts) >= 25
    for f in texts:
        assert f in sources, f"{f} is not named in third-party/SOURCES.txt"
        assert os.path.getsize(os.path.join(folder, f)) > 200, f"{f} is empty or a stub"
    listed = set(re.findall(r"^([\w.\-]+\.(?:txt|md))\b", sources, re.M)) - {"SOURCES.txt"}
    assert listed <= set(texts), f"listed but missing: {sorted(listed - set(texts))}"


def test_the_libraries_of_the_opencascade_wheel_have_their_text():
    """Every library the wheel brings (THIRD-PARTY-NOTICES.md section 2.1) has a text here, the ones task 0205 found
    missing included: FreeImage, LibRaw, OpenEXR, FreeType, libpng, libjpeg, libtiff, libwebp, Lerc, OpenJPEG, OpenJPH,
    Little CMS, xz, libdeflate, zlib, zstd, Imath, and meshoptimizer."""
    names = " ".join(os.listdir(os.path.join(LIC, "third-party"))).lower()
    for lib in ("opencascade", "openexr", "imath", "freetype", "freeimage", "libpng", "libjpeg", "libtiff", "libwebp",
                "lerc", "openjpeg", "openjph", "lcms2", "xz", "libdeflate", "zlib", "zstd", "libraw", "meshoptimizer",
                "manifold3d", "cadquery-ocp"):
        assert lib in names, f"no licence text for {lib}"


def test_a_checkout_without_the_package_folder_finds_the_root_files(tmp_path):
    pkg = tmp_path / "fresing_render"
    pkg.mkdir()
    (tmp_path / "LICENSE").write_text("x")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "COMPANY-USE.md").write_text("x")
    assert about.folder(str(pkg)) == str(tmp_path)
    assert about.find(str(pkg), about.COMPANY).endswith("COMPANY-USE.md")
    assert about.find(str(pkg), about.NOTICES) == ""
    assert set(about.missing(str(pkg))) == {about.NOTICES, "third-party/SOURCES.txt"}


def test_the_about_words_are_plain():
    lines = about.lines("0.2.162", "5.2.3 LTS")
    text = " ".join(lines)
    assert "0.2.162" in text and "5.2.3 LTS" in text and "GPL-3.0-or-later" in text and "no warranty" in text
    assert "© 2026 Fresing" in text


def test_the_release_builds_carry_the_files(tmp_path):
    """The extension's stage and the installer folder hold the licence files (the zips are made from them)."""
    pytest.importorskip("markdown")
    import build_release
    stage = str(tmp_path / "stage")
    build_release.stage_extension(stage)
    assert about.missing(stage) == []
    rel = tmp_path / "rel"
    rel.mkdir()
    build_release.add_licence_files(os.path.join(stage, "licenses"), str(rel))
    for name in ("LICENSE", "THIRD-PARTY-NOTICES.md", "COMPANY-USE.md", os.path.join("licenses", "third-party", "SOURCES.txt"),
                 os.path.join("licenses", "third-party", "libraw-LGPL-2.1.txt")):
        assert (rel / name).is_file(), name


def _ps1(name):
    return open(os.path.join(ROOT, name), "rb").read().decode("utf-8")


def test_the_installer_prints_the_licence_line_first_and_asks_nothing():
    text = _ps1("installer/Install-FresingRender.ps1")
    line = text.index("GPL-3.0-or-later, no warranty. Licence:")
    assert line < text.index("function Step")            # before anything is done
    assert "Read-Host" not in text and "PromptForChoice" not in text


def test_the_installer_switches_blender_extension_sync_off_and_keeps_online_access():
    text = _ps1("installer/Install-FresingRender.ps1")
    assert "p.system.use_online_access = True" in text
    assert "repo.use_sync_on_startup = False" in text and "repo.use_remote_url" in text


def test_the_installer_copies_the_licence_files():
    text = _ps1("installer/Install-FresingRender.ps1")
    for needle in ('"LICENSE"', "THIRD-PARTY-NOTICES.md", "third-party", '"license"'):
        assert needle in text


def test_the_windows_job_checks_licences_and_sync():
    text = _ps1("tools/ci_windows_install.ps1")
    for needle in ("Licence files next to the app", "Licence files inside the extension", "Blender's own license folder",
                   "extension sync off", "licence files arrived"):
        assert needle in text
