"""build_site.py --take with the render kit's new result (task 0112): its zip (or folder), the clips with the kit's own
posters, a gallery clip at most CLIP_MAX, older pictures kept with --keep-old, the Fresing 400 refused.

The compression itself (ImageMagick, ffmpeg) is replaced by copies that record what they were asked; where both
programs are installed, one more run uses them for real."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import zipfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import build_site  # noqa: E402


def _media(tmp_path, monkeypatch):
    media = tmp_path / "media"
    shutil.copytree(build_site.MEDIA, media)
    monkeypatch.setattr(build_site, "MEDIA", str(media))
    monkeypatch.setattr(build_site, "MEDIA_JSON", str(media / "media.json"))
    return media


def _result(tmp_path, items, real=False) -> str:
    """A kit result zip like make_site_pictures.py writes (site_pictures.json, files, log.txt)."""
    send = tmp_path / "send"
    send.mkdir(exist_ok=True)
    for it in items:
        for key in ("file", "poster"):
            if not it.get(key):
                continue
            p = send / it[key]
            if real and p.suffix == ".mp4":
                subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=size=640x360:rate=25:duration=2",
                                "-pix_fmt", "yuv420p", str(p)], check=True, capture_output=True)
            elif real:
                subprocess.run(["convert", "-size", "800x450", "xc:#3F6E8C", str(p)], check=True, capture_output=True)
            else:
                p.write_bytes(f"{it[key]}".encode() * 50)
    info = {"made": "2026-11-14 06:30", "app": "0.2.88", "device": "GPU NVIDIA GeForce RTX 3090", "items": items,
            "models": {"thor": {"title": "Thor robot arm", "credit": "Thor robot arm by Ángel L. M. (AngelLM), "
                                "CC BY-SA 4.0", "link": "https://github.com/AngelLM/Thor", "licence": "CC BY-SA 4.0",
                                "licence_link": "https://creativecommons.org/licenses/by-sa/4.0/"}}}
    (send / "site_pictures.json").write_text(json.dumps(info), encoding="utf-8")
    z = tmp_path / "site_pictures_2026-11-14.zip"
    with zipfile.ZipFile(z, "w") as zf:
        for f in os.listdir(send):
            zf.write(send / f, f)
        zf.writestr("log.txt", "Fresing site pictures – started\n")
    return str(z)


ITEMS = [
    {"file": "thor_low.jpg", "model": "thor", "caption": "Thor in the dark studio", "kind": "picture"},
    {"file": "thor_product.mp4", "poster": "thor_product_poster.jpg", "model": "thor", "kind": "video",
     "video": "product", "loop": False, "caption": "Thor robot arm: product video"},
]


def test_take_zip_with_kit_posters(tmp_path, monkeypatch):
    media = _media(tmp_path, monkeypatch)
    calls = []

    def fake_jpg(src, dst, width=1920):
        calls.append(("jpg", os.path.basename(src), os.path.basename(dst)))
        shutil.copy2(src, dst)
        return os.path.getsize(dst)

    def fake_mp4(src, dst, start=0.0, length=0.0, height=1080, max_bytes=build_site.VIDEO_MAX):
        calls.append(("mp4", os.path.basename(src), max_bytes))
        shutil.copy2(src, dst)
        return os.path.getsize(dst)

    monkeypatch.setattr(build_site, "web_jpg", fake_jpg)
    monkeypatch.setattr(build_site, "web_mp4", fake_mp4)
    monkeypatch.setattr(build_site, "poster_of", lambda *a: pytest.fail("the kit's poster should be used"))
    before = build_site.load_media()
    m = build_site.take(_result(tmp_path, ITEMS), keep_old=True)
    assert m["hero"] == before["hero"]                               # the owner's milling video stays on top
    files = [p["file"] for p in m["pictures"]]
    assert "thor_low.jpg" in files and "thor_product.mp4" in files
    assert files.count("thor_low.jpg") == 1
    clip = next(p for p in m["pictures"] if p["file"] == "thor_product.mp4")
    assert clip["poster"] == "thor_product_poster.jpg" and (media / "thor_product_poster.jpg").exists()
    assert ("jpg", "thor_product_poster.jpg", "thor_product_poster.jpg") in calls
    assert ("mp4", "thor_product.mp4", build_site.CLIP_MAX) in calls and build_site.CLIP_MAX <= 5_000_000
    assert m["models"]["thor"]["licence_link"].startswith("https://creativecommons.org")
    on_disk = json.loads((media / "media.json").read_text(encoding="utf-8"))
    assert on_disk["pictures"] == m["pictures"]
    # taken again: no doubles
    m2 = build_site.take(_result(tmp_path, ITEMS), keep_old=True)
    assert [p["file"] for p in m2["pictures"]].count("thor_product.mp4") == 1


def test_take_refuses_the_fresing_400(tmp_path, monkeypatch):
    _media(tmp_path, monkeypatch)
    bad = [{"file": "fresing_400_iso.jpg", "model": "fresing_400", "caption": "x", "kind": "picture"}]
    with pytest.raises(SystemExit, match="Fresing 400"):
        build_site.take(_result(tmp_path, bad))


def test_take_with_the_real_tools(tmp_path, monkeypatch):
    """Where ffmpeg and ImageMagick are installed (the owner's take-in session is): a real clip and poster."""
    if not (shutil.which("ffmpeg") and shutil.which("convert")):
        return                                       # the runners' pytest jobs have neither; the logic is tested above
    media = _media(tmp_path, monkeypatch)
    m = build_site.take(_result(tmp_path, ITEMS, real=True), keep_old=True)
    assert (media / "thor_product.mp4").stat().st_size <= build_site.CLIP_MAX
    assert (media / "thor_product_poster.jpg").stat().st_size <= build_site.JPG_MAX
    assert any(p["file"] == "thor_product.mp4" for p in m["pictures"])
