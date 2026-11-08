"""Build the landing page (task 0047): https://smholte.github.io/CAD-render-animation/

    ~/venv/bin/python tools/build_site.py                      # newest release from GitHub -> dist/site/
    ~/venv/bin/python tools/build_site.py --version 0.2.34     # that version, no internet needed
    ~/venv/bin/python tools/build_site.py --check dist/site    # only check a built page

It fills site/index.html with the version, its date, the exact download address of the release's installer zip and
the newest CHANGELOG section; copies style, fonts, the Fresing logos and the pictures and video listed in
site/media/media.json; builds the user guide (tools/build_guide.py) into dist/site/guide/index.html; and checks the
result (every file there, every model credited, links only to GitHub and fresing.nl outside the credits).

Swapping in pictures (a later session, the same tool):
    tools/build_site.py --take <folder with site_pictures.json>   # the owner's renders from site/render_kit
    tools/build_site.py --hero-video <file.mp4> --start 12 --length 15 --model <id>   # cut + compress the top video
Both compress with ImageMagick / ffmpeg (JPG <= 400 KB, video <= 8 MB) and update site/media/media.json.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from html.parser import HTMLParser

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SITE = os.path.join(ROOT, "site")
MEDIA = os.path.join(SITE, "media")
MEDIA_JSON = os.path.join(MEDIA, "media.json")
DEFAULT_OUT = os.path.join(ROOT, "dist", "site")
REPO = "smholte/CAD-render-animation"
REPO_URL = f"https://github.com/{REPO}"
ALLOWED_HOSTS = ("github.com", "fresing.nl", "www.fresing.nl")
JPG_MAX = 400_000
VIDEO_MAX = 8_000_000
COPY_DIRS = ("brand", "fonts")

sys.path.insert(0, ROOT)


def asset_name(version: str) -> str:
    return f"FresingRender-{version}-windows.zip"


def download_url(version: str) -> str:
    return f"{REPO_URL}/releases/download/v{version}/{asset_name(version)}"


def manifest_version() -> str:
    text = open(os.path.join(ROOT, "fresing_render", "blender_manifest.toml"), encoding="utf-8").read()
    return re.search(r'^version\s*=\s*"([^"]+)"', text, re.M).group(1)


def blender_version() -> str:
    text = open(os.path.join(ROOT, "installer", "Install-FresingRender.ps1"), encoding="utf-8").read()
    return re.search(r'\$BlenderVersion\s*=\s*"([^"]+)"', text).group(1)


def latest_release() -> dict:
    """{"version", "size"} of the newest release ("latest") from the GitHub API."""
    req = urllib.request.Request(f"https://api.github.com/repos/{REPO}/releases/latest",
                                 headers={"Accept": "application/vnd.github+json", "User-Agent": "fresing-site"})
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    version = data["tag_name"].lstrip("v")
    size = next((a["size"] for a in data.get("assets", []) if a["name"] == asset_name(version)), 0)
    return {"version": version, "size": size}


def changelog_entry(version: str) -> dict:
    from fresing_render.core import updates
    entries = updates.parse_changelog(open(os.path.join(ROOT, "CHANGELOG.md"), encoding="utf-8").read())
    entry = next((e for e in entries if e["version"] == version), None)
    if entry is None:
        raise SystemExit(f"CHANGELOG.md has no section for {version}")
    return entry


def md_to_html(text: str) -> str:
    try:
        import markdown
    except ImportError:
        sys.exit("The page needs the Python package 'markdown': ~/venv/bin/pip install markdown")
    lines, prev = [], ""
    for line in text.splitlines():           # CHANGELOG lists often follow a line directly: Markdown needs a gap
        if re.match(r"^\s*[-*] ", line) and prev.strip() and not re.match(r"^\s*[-*] |^\s{2,}\S", prev):
            lines.append("")
        lines.append(line)
        prev = line
    return markdown.markdown("\n".join(lines))


def load_media(path: str = MEDIA_JSON) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _esc(text: str) -> str:
    return html.escape(text, quote=True)


def hero_html(media: dict) -> str:
    hero = media.get("hero") or {}
    if not hero:
        return ""
    if not hero["file"].lower().endswith(".mp4"):         # a picture until there is a video
        return (f'<img src="media/{_esc(hero["file"])}" alt="{_esc(hero.get("caption", ""))}" width="1600" '
                f'height="900">' + (f'\n      <figcaption>{_esc(hero["caption"])}</figcaption>'
                                    if hero.get("caption") else ""))
    poster = f' poster="media/{_esc(hero["poster"])}"' if hero.get("poster") else ""
    cap = f'\n      <figcaption>{_esc(hero["caption"])}</figcaption>' if hero.get("caption") else ""
    return (f'<video src="media/{_esc(hero["file"])}"{poster} autoplay muted loop playsinline controls '
            f'preload="metadata" aria-label="{_esc(hero.get("caption", "Video"))}"></video>{cap}')


def gallery_html(media: dict) -> str:
    rows = []
    for p in media.get("pictures", []):
        f = _esc(p["file"])
        if f.lower().endswith(".mp4"):
            poster = f' poster="media/{_esc(p["poster"])}"' if p.get("poster") else ""
            rows.append(f'      <figure><video src="media/{f}"{poster} muted loop playsinline controls preload="none" '
                        f'aria-label="{_esc(p["caption"])}"></video><figcaption>{_esc(p["caption"])}</figcaption>'
                        f'</figure>')
            continue
        rows.append(f'      <figure><a href="media/{f}"><img src="media/{f}" alt="{_esc(p["caption"])}" '
                    f'loading="lazy" width="1600" height="900"></a><figcaption>{_esc(p["caption"])}</figcaption>'
                    f'</figure>')
    return "\n".join(rows)


def credits_html(media: dict) -> str:
    rows = []
    for mid in used_models(media):
        m = media["models"][mid]
        text = _esc(m["credit"])
        links = []
        if m.get("link"):
            links.append(f'<a href="{_esc(m["link"])}">model</a>')
        if m.get("licence_link"):
            links.append(f'<a href="{_esc(m["licence_link"])}">licence</a>')
        rows.append(f"      <li>{text}" + (f" ({', '.join(links)})" if links else "") + "</li>")
    return "\n".join(rows)


def used_models(media: dict) -> list[str]:
    seen: list[str] = []
    items = ([media["hero"]] if media.get("hero") else []) + media.get("pictures", [])
    for it in items:
        if it.get("model") and it["model"] not in seen:
            seen.append(it["model"])
    return seen


def media_files(media: dict) -> list[str]:
    files = []
    if media.get("hero"):
        files.append(media["hero"]["file"])
        if media["hero"].get("poster"):
            files.append(media["hero"]["poster"])
    for p in media.get("pictures", []):
        files.append(p["file"])
        if p.get("poster"):
            files.append(p["poster"])
    return files


def _mb(n: int) -> str:
    return f"{n / 1e6:.0f} MB" if n else ""


def fill(template: str, values: dict) -> str:
    if not values.get("size"):
        template = template.replace(" · {{size}}", "")
    for k, v in values.items():
        template = template.replace("{{" + k + "}}", v)
    left = re.findall(r"\{\{\w+\}\}", template)
    if left:
        raise SystemExit(f"site/index.html: no value for {', '.join(sorted(set(left)))}")
    return template


def build(out: str = DEFAULT_OUT, version: str = "", size: int = 0, guide: bool = True) -> str:
    if not version:
        try:
            rel = latest_release()
            version, size = rel["version"], rel["size"]
        except Exception as exc:          # no internet: the version in the manifest
            print(f"newest release not found ({exc}); using the manifest's version")
            version = manifest_version()
    entry = changelog_entry(version)
    media = load_media()
    page = fill(open(os.path.join(SITE, "index.html"), encoding="utf-8").read(), {
        "version": _esc(version), "date": _esc(entry["date"]), "size": _mb(size),
        "download_url": download_url(version), "asset_name": asset_name(version),
        "releases_url": f"{REPO_URL}/releases", "repo_url": REPO_URL, "blender": blender_version(),
        "news_title": _esc(entry["title"][:1].upper() + entry["title"][1:]), "whats_new": md_to_html(entry["text"]),
        "hero_video": hero_html(media), "gallery": gallery_html(media), "credits": credits_html(media),
    })
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(os.path.join(out, "media"))
    with open(os.path.join(out, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(page)
    shutil.copy2(os.path.join(SITE, "style.css"), out)
    for d in COPY_DIRS:
        shutil.copytree(os.path.join(SITE, d), os.path.join(out, d))
    for f in media_files(media):
        shutil.copy2(os.path.join(MEDIA, f), os.path.join(out, "media", f))
    with open(os.path.join(out, ".nojekyll"), "w"):
        pass
    if guide:
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import build_guide
        build_guide.build(os.path.join(out, "guide", "index.html"))
    return out


# ---------------------------------------------------------------------------
# checks (also used by tests/test_site.py)
# ---------------------------------------------------------------------------

class _Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs: list[tuple[str, str, bool]] = []      # (tag, address, inside the credits list)
        self._credits = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "ul" and "credits" in (a.get("class") or "").split():
            self._credits = 1
        elif tag == "ul" and self._credits:
            self._credits += 1
        for key in ("href", "src", "poster"):
            if a.get(key):
                self.refs.append((tag, a[key], self._credits > 0))

    def handle_endtag(self, tag):
        if tag == "ul" and self._credits:
            self._credits -= 1


def check(out: str, media: dict | None = None) -> list[str]:
    """Problems of a built page ([] = fine)."""
    media = media if media is not None else load_media()
    problems = []
    page_path = os.path.join(out, "index.html")
    page = open(page_path, encoding="utf-8").read()
    p = _Links()
    p.feed(page)
    for tag, ref, in_credits in p.refs:
        if ref.startswith("#"):
            continue
        if re.match(r"^[a-z]+:", ref):
            if not ref.startswith("https://"):
                problems.append(f"not https: {ref}")
                continue
            host = ref.split("/")[2]
            if tag != "a":
                problems.append(f"loads something from another site: {ref}")
            elif not in_credits and host not in ALLOWED_HOSTS:
                problems.append(f"link to {host} outside the credits: {ref}")
            elif host == "github.com" and not in_credits and not ref.startswith(REPO_URL):
                problems.append(f"link to another GitHub project: {ref}")
            continue
        target = os.path.join(out, ref.split("#")[0].split("?")[0])
        if ref.endswith("/"):
            target = os.path.join(target, "index.html")
        if not os.path.exists(target):
            problems.append(f"missing file: {ref}")
    css = open(os.path.join(out, "style.css"), encoding="utf-8").read()
    for ref in re.findall(r"url\(([^)]+)\)", css):
        ref = ref.strip("'\"")
        if re.match(r"^[a-z]+:", ref):
            problems.append(f"style loads something from another site: {ref}")
        elif not os.path.exists(os.path.join(out, ref)):
            problems.append(f"style: missing file {ref}")
    for mid in used_models(media):
        m = media.get("models", {}).get(mid)
        if not m or not m.get("credit"):
            problems.append(f"model '{mid}' has no credit in media.json")
        elif _esc(m["credit"]) not in page:
            problems.append(f"model '{mid}' is not credited on the page")
    credits_md = open(os.path.join(SITE, "CREDITS.md"), encoding="utf-8").read()
    for mid in used_models(media):
        m = media.get("models", {}).get(mid, {})
        if m.get("credit") and m["credit"] not in credits_md:
            problems.append(f"model '{mid}' is not in site/CREDITS.md")
    for f in media_files(media):
        path = os.path.join(out, "media", f)
        if not os.path.exists(path):
            continue
        size = os.path.getsize(path)
        if f.lower().endswith((".jpg", ".jpeg")) and size > JPG_MAX * 1.1:
            problems.append(f"picture too big for the web: {f} ({size // 1000} KB, at most {JPG_MAX // 1000})")
        if f.lower().endswith(".mp4") and size > VIDEO_MAX * 1.1:
            problems.append(f"video too big for the web: {f} ({size / 1e6:.1f} MB, at most {VIDEO_MAX / 1e6:.0f})")
    if "<script" in page.lower():
        problems.append("the page has a script (none allowed)")
    return problems


# ---------------------------------------------------------------------------
# taking in new pictures and video
# ---------------------------------------------------------------------------

def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def web_jpg(src: str, dst: str, width: int = 1920) -> int:
    """A JPG at most ``width`` wide and JPG_MAX bytes (ImageMagick). Returns its size."""
    for q in (86, 82, 78, 74, 70, 64, 58):
        _run(["convert", src, "-resize", f"{width}x>", "-strip", "-interlace", "Plane",
              "-sampling-factor", "4:2:0", "-quality", str(q), dst])
        if os.path.getsize(dst) <= JPG_MAX:
            break
    return os.path.getsize(dst)


def web_mp4(src: str, dst: str, start: float = 0.0, length: float = 0.0, height: int = 1080) -> int:
    """H.264 MP4 without sound, at most ``height`` high and VIDEO_MAX bytes (ffmpeg). Returns its size."""
    cut = (["-ss", str(start)] if start else []) + (["-t", str(length)] if length else [])
    for crf in (24, 27, 30, 33):
        _run(["ffmpeg", "-y", *cut, "-i", src, "-an", "-vf", f"scale=-2:'min({height},ih)'", "-c:v", "libx264",
              "-preset", "slow", "-crf", str(crf), "-pix_fmt", "yuv420p", "-movflags", "+faststart", dst])
        if os.path.getsize(dst) <= VIDEO_MAX:
            break
    return os.path.getsize(dst)


def poster_of(video: str, dst: str) -> None:
    _run(["ffmpeg", "-y", "-i", video, "-frames:v", "1", "-q:v", "4", dst])
    web_jpg(dst, dst)


def save_media(media: dict) -> None:
    with open(MEDIA_JSON, "w", encoding="utf-8") as fh:
        json.dump(media, fh, indent=1, ensure_ascii=False)
        fh.write("\n")


def take(folder: str, keep_old: bool = False) -> dict:
    """The owner's renders (site_pictures.json from the render kit) into site/media: pictures and the video
    compressed, media.json updated (the old pictures go unless ``keep_old``)."""
    info = json.load(open(os.path.join(folder, "site_pictures.json"), encoding="utf-8"))
    media = load_media()
    pictures = media.get("pictures", []) if keep_old else []
    for it in info["items"]:
        src = os.path.join(folder, it["file"])
        if it["kind"] == "picture":
            web_jpg(src, os.path.join(MEDIA, it["file"]))
            pictures.append({"file": it["file"], "caption": it["caption"], "model": it["model"]})
        elif it["kind"] == "video":
            web_mp4(src, os.path.join(MEDIA, it["file"]))
            poster = it["file"].rsplit(".", 1)[0] + "_poster.jpg"
            poster_of(os.path.join(MEDIA, it["file"]), os.path.join(MEDIA, poster))
            item = {"file": it["file"], "poster": poster, "caption": it["caption"], "model": it["model"]}
            if (media.get("hero") or {}).get("keep"):      # the owner's own video stays at the top
                pictures.append(item)
            else:
                media["hero"] = item
    media["pictures"] = pictures
    media.setdefault("models", {}).update(info.get("models", {}))
    _tidy(media)
    save_media(media)
    return media


def _tidy(media: dict) -> None:
    """Remove media files and model entries nothing uses any more."""
    used = set(media_files(media)) | {"media.json"}
    for f in os.listdir(MEDIA):
        if f not in used:
            os.remove(os.path.join(MEDIA, f))
    keep = set(used_models(media))
    media["models"] = {k: v for k, v in media.get("models", {}).items() if k in keep}


def hero_video(src: str, start: float, length: float, model: str, caption: str, keep: bool = True) -> dict:
    media = load_media()
    name = re.sub(r"[^a-z0-9]+", "_", os.path.splitext(os.path.basename(src))[0].lower()).strip("_") + ".mp4"
    dst = os.path.join(MEDIA, name)
    web_mp4(src, dst, start, length)
    poster = name[:-4] + "_poster.jpg"
    poster_of(dst, os.path.join(MEDIA, poster))
    media["hero"] = {"file": name, "poster": poster, "caption": caption, "model": model, "keep": keep}
    _tidy(media)
    save_media(media)
    return media


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Build the landing page into dist/site")
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--version", default="", help="release version (default: the newest release on GitHub)")
    ap.add_argument("--size", type=int, default=0, help="size of the installer zip in bytes (shown on the button)")
    ap.add_argument("--no-guide", action="store_true")
    ap.add_argument("--check", metavar="DIR", help="only check a built page")
    ap.add_argument("--take", metavar="FOLDER", help="take the render kit's pictures into site/media")
    ap.add_argument("--keep-old", action="store_true", help="with --take: keep the pictures already there")
    ap.add_argument("--hero-video", metavar="FILE", help="cut and compress the video at the top of the page")
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--length", type=float, default=15.0)
    ap.add_argument("--model", default="")
    ap.add_argument("--caption", default="")
    a = ap.parse_args(argv)
    if a.take:
        take(a.take, a.keep_old)
        print("site/media updated; check site/CREDITS.md lists every model")
        return 0
    if a.hero_video:
        hero_video(a.hero_video, a.start, a.length, a.model, a.caption)
        print("site/media updated")
        return 0
    out = a.check or build(a.out, a.version, a.size, guide=not a.no_guide)
    problems = check(out)
    for p in problems:
        print("PROBLEM:", p)
    total = sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(out) for f in fs)
    print(f"{out}: {total / 1e6:.1f} MB, {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
