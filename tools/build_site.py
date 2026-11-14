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
    tools/build_site.py --web-model <file.glb or export folder> --model <id> --caption "…" [--title …] [--order N]
    tools/build_site.py --remove-web-model <id>                # a model of "Turn it yourself" in or out
Both compress with ImageMagick / ffmpeg (JPG <= 400 KB, video <= 8 MB) and update site/media/media.json.

"Turn it yourself" (tasks 0099, 0111): the landing page itself has no script. Its section shows one card per model of
media.json "web_models" (poster, title, a line, the size) and each card opens that model's own page model/<id>/:
  - a .glb the app exported: a small page with the vendored model-viewer (fresing_render/web/, copied to vendor/)
    that loads media/<id>.glb only when it is opened;
  - an export folder whose page has surroundings or baked light (the three.js page of tasks 0106/0107): that page,
    its three.js scripts loaded from vendor/ (the model stays inside the page).
Every model page loops its animation, has a Pause/Play button, the credit and licence line and a link back. The old
address model/ goes to the first model. --web-model makes the poster picture with headless Chromium
(tools/web3d_shot.js / web3d_env_shot.js). Only openly licensed or invented models – never the Fresing 400.
tools/make_site_web_models.py makes the page's two models (test mill, Thor) and adds them with this.
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
ALLOWED_HOSTS = ("github.com", "fresing.nl", "www.fresing.nl", "www.blender.org")
JPG_MAX = 400_000
VIDEO_MAX = 8_000_000
CLIP_MAX = 5_000_000                        # a gallery clip (task 0112): the page stays light
WEB_MODEL_WARN = 10_000_000                # a web model (its .glb or its page): a phone on a slow line must get it
WEB_MODEL_MAX = 25_000_000                 # ... refused above this (export again with the Phone quality / 512 textures)
FORBIDDEN_MODELS = ("fresing_400", "fresing400", "f400")   # not public (owner, 12 Nov 2026)
COPY_DIRS = ("brand", "fonts")

sys.path.insert(0, ROOT)
from fresing_render.core import web3d  # noqa: E402
from fresing_render.core import web3d_env  # noqa: E402

PAGE_SUFFIX = ".page.html"                  # an export's own page in site/media (built into model/<id>/index.html)
VENDOR_PAGE = (web3d_env.THREE_FILE, web3d_env.MATH_FILE, web3d_env.PAGE_FILE)   # the three.js page's scripts


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


def load_media(path: str = "") -> dict:
    with open(path or MEDIA_JSON, encoding="utf-8") as fh:
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


def feature_html(media: dict) -> str:
    """The picture next to "Built on Blender" (media.json "feature")."""
    f = media.get("feature") or {}
    if not f:
        return ""
    cap = f'\n      <figcaption>{_esc(f["caption"])}</figcaption>' if f.get("caption") else ""
    return (f'<a href="media/{_esc(f["file"])}"><img src="media/{_esc(f["file"])}" alt="{_esc(f.get("caption", ""))}" '
            f'loading="lazy" width="1000" height="1350"></a>{cap}')


def web_models(media: dict) -> list[dict]:
    """The models of "Turn it yourself" in their order (media.json "web_models"; the first is the default)."""
    items = list(media.get("web_models") or [])
    if not items and media.get("web_model"):              # media.json before task 0111: one model
        w = media["web_model"]
        items = [dict(w, id=re.sub(r"[^a-z0-9]+", "_", w.get("model", "model").lower()).strip("_"))]
    return sorted(items, key=lambda w: (w.get("order", 0), items.index(w)))


def own_page(w: dict) -> bool:
    """True when the model shows on the export's own page (surroundings or baked light), not in model-viewer."""
    return w["file"].endswith(PAGE_SUFFIX)


def _title(media: dict, w: dict) -> str:
    return w.get("title") or media.get("models", {}).get(w.get("model", ""), {}).get("title") or "3D model"


def turn_html(media: dict) -> str:
    """The "Turn it yourself" section: one card per web model, '' without one. No script: each card is a link."""
    items = web_models(media)
    if not items:
        return ""
    cards = []
    for w in items:
        size = download_size(media, w)
        title = _esc(_title(media, w))
        pic = (f'<img src="media/{_esc(w["poster"])}" alt="{title}" loading="lazy" width="1200" height="800">'
               if w.get("poster") else "")
        moves = " · moves by itself" if w.get("seconds") else ""
        cards.append(f"""      <li class="card">
        <a class="card-pic" href="model/{_esc(w["id"])}/">{pic}</a>
        <h3>{title}</h3>
        <p>{_esc(w.get("caption", ""))}</p>
        <p class="small">{_esc(web3d.mb(size))} to download{moves}</p>
        <a class="button" href="model/{_esc(w["id"])}/">Open the 3D model</a>
      </li>""")
    many = len(items) > 1
    return f"""<section id="turn" class="turn">
  <div class="wrap">
    <h2>Turn it yourself</h2>
    <p>Fresing Render also saves a machine as one 3D file with its looks and its motion, and a page that shows it in any web browser: drag to turn it, scroll to zoom. E-mail it to a customer or put it on your website.</p>
    <p class="small">{"Pick a model: each" if many else "The model"} loads only when you open it. Made with 5 Scene &amp; Render &gt; Web 3D model.</p>
    <ul class="cards">
{chr(10).join(cards)}
    </ul>
  </div>
</section>
"""


def download_size(media: dict, w: dict) -> int:
    """Bytes a visitor's browser fetches for the model's page: the page, the model and the viewer's scripts."""
    path = os.path.join(MEDIA, w["file"])
    if not os.path.exists(path):
        return 0
    if own_page(w):
        n = len(model_page(media, w).encode("utf-8"))
        return n + sum(os.path.getsize(os.path.join(web3d.WEB_DIR, f)) for f in VENDOR_PAGE)
    return os.path.getsize(path) + os.path.getsize(os.path.join(web3d.WEB_DIR, web3d.MV_FILE))


def _note(media: dict, w: dict, viewer: str) -> str:
    """The line at the bottom of a model page: back to the landing page, the model's credit, the 3D file's licence."""
    m = media.get("models", {}).get(w.get("model", ""), {})
    parts = ['<a href="../../">← Fresing Render</a>']
    if m.get("credit"):
        parts.append(_esc(m["credit"]) + (f' (<a href="{_esc(m["link"])}">model</a>)' if m.get("link") else ""))
    if m.get("licence"):
        lic = _esc(m["licence"])
        if m.get("licence_link"):
            lic = f'<a href="{_esc(m["licence_link"])}">{lic}</a>'
        parts.append(f"this 3D file {lic}")
    parts.append(viewer)
    return " · ".join(parts)


SITE_UI = """<div id="fr-site"><button id="fr-play" type="button" aria-pressed="false">Pause</button></div>
<style>
  #fr-site {{ position: absolute; right: 14px; bottom: 34px; z-index: 2; }}
  #fr-play {{ font: 600 14px "IBM Plex Sans", "Segoe UI", system-ui, sans-serif; padding: 8px 16px; border-radius: 4px;
             border: 0; background: #2F6A1B; color: #fff; cursor: pointer; min-width: 84px; min-height: 40px; }}
  #fr-play:focus-visible {{ outline: 3px solid #F2A900; outline-offset: 2px; }}
  .note {{ right: 120px; }}
  .note a {{ color: #2F6A1B; }}
  @media (max-width: 600px) {{ .note {{ font-size: 11px; }} }}
</style>
<script>
(function () {{
  var b = document.getElementById('fr-play'), mv = document.querySelector('model-viewer');
  if (!{animated}) {{ b.style.display = 'none'; return; }}
  function paused() {{ return mv ? mv.paused : !!(window.frPage && window.frPage.paused); }}
  function show() {{ var p = paused(); b.textContent = p ? 'Play' : 'Pause'; b.setAttribute('aria-pressed', p ? 'true' : 'false'); }}
  b.addEventListener('click', function () {{
    if (mv) {{ if (mv.paused) mv.play(); else mv.pause(); }}
    else if (window.frPage) window.frPage.paused = !window.frPage.paused;
    show();
  }});
  if (mv) {{ mv.addEventListener('play', show); mv.addEventListener('pause', show); }}
}})();
</script>
"""


def _with_site_ui(page: str, title: str, note: str, animated: bool) -> str:
    """A model page with the site's parts: its title, the note line, the Pause/Play button (task 0111)."""
    t = _esc(title)
    page = re.sub(r"<title>.*?</title>", f"<title>{t} – Fresing Render</title>", page, count=1, flags=re.S)
    page = re.sub(r"<h1>.*?</h1>", f"<h1>{t}</h1>", page, count=1, flags=re.S)
    page = re.sub(r'<div class="note">.*?</div>', lambda _m: f'<div class="note">{note}</div>', page, count=1,
                  flags=re.S)
    ui = SITE_UI.format(animated="true" if animated else "false")
    i = page.rindex("</body>")
    return page[:i] + ui + page[i:]


def model_page(media: dict, w: dict) -> str:
    """model/<id>/index.html: the viewer page of one web model."""
    title = _title(media, w)
    animated = bool(w.get("seconds"))
    if own_page(w):
        page = open(os.path.join(MEDIA, w["file"]), encoding="utf-8").read()
        for name in VENDOR_PAGE:             # the scripts from vendor/ (cached between the models), not inline
            inline = web3d_env._inline(web3d_env._read(name))
            if inline in page:
                page = page.replace(inline, f'<script src="../../vendor/{name}"></script>', 1)
        note = _note(media, w, "three.js (MIT)")
    else:
        note = _note(media, w, "model-viewer by Google (Apache-2.0)")
        page = web3d.viewer_html(title, src="../../media/" + w["file"], script_src="../../vendor/" + web3d.MV_FILE,
                                 note=note, animated=animated)
    return _with_site_ui(page, title, note, animated)


def redirect_page(first: str) -> str:
    """model/index.html: the address of task 0099 goes on to the first model (no script)."""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="0; url={first}/">
<title>3D model – Fresing Render</title>
<link rel="canonical" href="{first}/">
</head>
<body>
<p><a href="{first}/">Open the 3D model</a> · <a href="../#turn">All models</a></p>
</body>
</html>
"""


def glb_of(path: str) -> bytes:
    """The model file of a web model: the .glb itself, or the one inside an export's own page."""
    if not path.endswith(".html"):
        return open(path, "rb").read()
    import base64
    page = open(path, encoding="utf-8").read()
    m = re.search(r'id="fr-glb">([^<]*)</script>', page)
    if not m:
        raise ValueError(f"{os.path.basename(path)} holds no 3D model")
    return base64.b64decode(m.group(1).strip())


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
    items = ([media["hero"]] if media.get("hero") else []) + media.get("pictures", []) + \
        ([media["feature"]] if media.get("feature") else []) + web_models(media)
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
    if media.get("feature"):
        files.append(media["feature"]["file"])
    for p in media.get("pictures", []):
        files.append(p["file"])
        if p.get("poster"):
            files.append(p["poster"])
    for w in web_models(media):
        files.append(w["file"])
        if w.get("poster"):
            files.append(w["poster"])
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
        "hero_video": hero_html(media), "gallery": gallery_html(media), "feature": feature_html(media), "credits": credits_html(media),
        "turn_section": turn_html(media), "turn_nav": '\n      <a href="#turn">Turn it</a>' if web_models(media) else "",
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
        if not f.endswith(PAGE_SUFFIX):            # an export's own page goes to model/<id>/ only
            shutil.copy2(os.path.join(MEDIA, f), os.path.join(out, "media", f))
    items = web_models(media)
    if items:
        for w in items:
            os.makedirs(os.path.join(out, "model", w["id"]))
            with open(os.path.join(out, "model", w["id"], "index.html"), "w", encoding="utf-8") as fh:
                fh.write(model_page(media, w))
        with open(os.path.join(out, "model", "index.html"), "w", encoding="utf-8") as fh:
            fh.write(redirect_page(items[0]["id"]))
        os.makedirs(os.path.join(out, "vendor"))
        for f in vendor_files(media):
            shutil.copy2(os.path.join(web3d.WEB_DIR, f), os.path.join(out, "vendor", f))
    with open(os.path.join(out, ".nojekyll"), "w"):
        pass
    if guide:
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import build_guide
        build_guide.build(os.path.join(out, "guide", "index.html"))
    return out


def vendor_files(media: dict) -> list[str]:
    """The viewer scripts and their licences the model pages need (vendor/)."""
    items = web_models(media)
    out = []
    if any(not own_page(w) for w in items):
        out += [web3d.MV_FILE, "LICENSE-model-viewer.txt"]
    if any(own_page(w) for w in items):
        out += list(VENDOR_PAGE) + ["LICENSE-three.txt"]
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
        for key in ("href", "src", "data-src", "poster"):
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
    problems += check_model(out, media, credits_md)
    return problems


def check_model(out: str, media: dict, credits_md: str) -> list[str]:
    """The model pages: everything from the site itself, the viewers and their licences there, each model a valid
    glTF small enough for the web, the viewers credited, the old address model/ going on to the first model."""
    items = web_models(media)
    if not items:
        return []
    problems = []
    ids = [w.get("id", "") for w in items]
    if len(set(ids)) != len(ids) or not all(re.fullmatch(r"[a-z0-9_]+", i) for i in ids):
        problems.append(f"web model ids must be different words of a-z, 0-9 and _: {ids}")
    for w in items:
        problems += _check_one(out, media, w)
    for f in vendor_files(media):
        if not os.path.exists(os.path.join(out, "vendor", f)):
            problems.append(f"missing file: vendor/{f}")
    if any(not own_page(w) for w in items) and "model-viewer" not in credits_md:
        problems.append("model-viewer is not in site/CREDITS.md")
    if any(own_page(w) for w in items) and "three.js" not in credits_md:
        problems.append("three.js is not in site/CREDITS.md")
    red = os.path.join(out, "model", "index.html")
    if not os.path.exists(red):
        problems.append("missing file: model/index.html")
    elif f'url={items[0]["id"]}/' not in open(red, encoding="utf-8").read():
        problems.append("model/index.html does not go on to the first model")
    return problems


def _check_one(out: str, media: dict, w: dict) -> list[str]:
    problems = []
    wid = w.get("id", "")
    if any(f in (w.get("model", "") + w["file"] + wid).lower() for f in FORBIDDEN_MODELS):
        problems.append(f"the web model '{w.get('model')}' may not be published (not public)")
    if not w.get("poster"):
        problems.append(f"web model '{wid}' has no poster picture")
    page_path = os.path.join(out, "model", wid, "index.html")
    if not os.path.exists(page_path):
        return problems + [f"missing file: model/{wid}/index.html"]
    page = open(page_path, encoding="utf-8").read()
    p = _Links()
    p.feed(page)
    for tag, ref, _ in p.refs:
        if re.match(r"^[a-z]+:", ref):
            if tag != "a":
                problems.append(f"model page {wid} loads something from another site: {ref}")
            continue
        target = os.path.join(out, "model", wid, ref.split("#")[0])
        if ref.endswith("/"):
            target = os.path.join(target, "index.html")
        if not os.path.exists(target):
            problems.append(f"model page {wid}: missing file {ref}")
    if 'id="fr-play"' not in page or 'href="../../"' not in page:
        problems.append(f"model page {wid}: no Pause button or no link back")
    m = media.get("models", {}).get(w.get("model", ""), {})
    if m.get("credit") and _esc(m["credit"]) not in page:
        problems.append(f"model page {wid}: the model is not credited")
    src = page_path if own_page(w) else os.path.join(out, "media", w["file"])
    if os.path.exists(src):
        size = os.path.getsize(src)
        if size > WEB_MODEL_MAX:
            problems.append(f"web model too big: {w['file']} ({size / 1e6:.1f} MB, at most {WEB_MODEL_MAX / 1e6:.0f})")
        try:
            problems += [f"web model {wid}: {x}" for x in web3d.problems(glb_of(src))]
        except ValueError as exc:
            problems.append(f"web model {wid}: {exc}")
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


def web_mp4(src: str, dst: str, start: float = 0.0, length: float = 0.0, height: int = 1080,
            max_bytes: int = VIDEO_MAX) -> int:
    """H.264 MP4 without sound, at most ``height`` high and ``max_bytes`` (ffmpeg; 720 high when 1080 does not fit).
    Returns its size."""
    cut = (["-ss", str(start)] if start else []) + (["-t", str(length)] if length else [])
    for h in (height, 720) if height > 720 else (height,):
        for crf in (24, 27, 30, 33):
            _run(["ffmpeg", "-y", *cut, "-i", src, "-an", "-vf", f"scale=-2:'min({h},ih)'", "-c:v", "libx264",
                  "-preset", "slow", "-crf", str(crf), "-pix_fmt", "yuv420p", "-movflags", "+faststart", dst])
            if os.path.getsize(dst) <= max_bytes:
                return os.path.getsize(dst)
    return os.path.getsize(dst)


def poster_of(video: str, dst: str) -> None:
    _run(["ffmpeg", "-y", "-i", video, "-frames:v", "1", "-q:v", "4", dst])
    web_jpg(dst, dst)


def save_media(media: dict) -> None:
    with open(MEDIA_JSON, "w", encoding="utf-8") as fh:
        json.dump(media, fh, indent=1, ensure_ascii=False)
        fh.write("\n")


def take(folder: str, keep_old: bool = False) -> dict:
    """The owner's renders (site_pictures.json from the render kit, a folder or the kit's site_pictures_<date>.zip)
    into site/media: pictures and videos compressed (a gallery clip at most CLIP_MAX), the kit's posters used,
    media.json updated (the old pictures go unless ``keep_old``)."""
    if folder.lower().endswith(".zip"):
        import tempfile
        import zipfile
        tmp = tempfile.mkdtemp(prefix="site_take_")
        with zipfile.ZipFile(folder) as z:
            z.extractall(tmp)
        hits = [d for d, _s, fs in os.walk(tmp) if "site_pictures.json" in fs]
        if not hits:
            raise SystemExit(f"{folder} has no site_pictures.json")
        folder = hits[0]
    info = json.load(open(os.path.join(folder, "site_pictures.json"), encoding="utf-8"))
    for it in info["items"]:
        if any(f in (it.get("model", "") + it["file"]).lower() for f in FORBIDDEN_MODELS):
            raise SystemExit(f"{it['file']} may not go on the site: the Fresing 400 is not public")
    media = load_media()
    pictures = media.get("pictures", []) if keep_old else []
    if keep_old:
        new = {it["file"] for it in info["items"]}
        pictures = [p for p in pictures if p["file"] not in new]
    for it in info["items"]:
        src = os.path.join(folder, it["file"])
        if it["kind"] == "picture":
            web_jpg(src, os.path.join(MEDIA, it["file"]))
            pictures.append({"file": it["file"], "caption": it["caption"], "model": it["model"]})
        elif it["kind"] == "video":
            gallery = bool((media.get("hero") or {}).get("keep"))      # the owner's own video stays at the top
            web_mp4(src, os.path.join(MEDIA, it["file"]), max_bytes=CLIP_MAX if gallery else VIDEO_MAX)
            poster = it["file"].rsplit(".", 1)[0] + "_poster.jpg"
            kit_poster = os.path.join(folder, it.get("poster", "")) if it.get("poster") else ""
            if kit_poster and os.path.isfile(kit_poster):
                web_jpg(kit_poster, os.path.join(MEDIA, poster))
            else:
                poster_of(os.path.join(MEDIA, it["file"]), os.path.join(MEDIA, poster))
            item = {"file": it["file"], "poster": poster, "caption": it["caption"], "model": it["model"]}
            if gallery:
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


def _shoot(cmd: list[str], png: str, dst: str) -> bool:
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300)
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"no poster picture ({exc})")
        return False
    if not os.path.exists(png):
        return False
    web_jpg(png, dst, 1200)
    return True


def poster_of_model(src: str, dst: str) -> bool:
    """A poster picture of a web model as its page shows it at its first moment (headless Chromium:
    tools/web3d_shot.js for a .glb, tools/web3d_env_shot.js for an export's own page). False when Node with
    Playwright is not there."""
    import tempfile
    tmp = tempfile.mkdtemp()
    png = os.path.join(tmp, "shot.png")
    try:
        if src.endswith(".html"):
            page = os.path.join(tmp, "page.html")
            shutil.copy2(src, page)
            return _shoot(["node", os.path.join(ROOT, "tools", "web3d_env_shot.js"), page, png, "1200", "800",
                           "--query=auto=0&t=0&quality=BEST", "--hide-ui", "--wait=2500"], png, dst)
        page = os.path.join(tmp, "page.html")
        with open(page, "w", encoding="utf-8") as fh:
            fh.write(web3d.viewer_html("", glb=open(src, "rb").read()))
        return _shoot(["node", os.path.join(ROOT, "tools", "web3d_shot.js"), page, png, "1200", "800", "",
                       "--hide-ui"], png, dst)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def export_files(src: str) -> tuple[str, str]:
    """(the .glb, its own page or '') of what --web-model got: a .glb, or an export folder / its .html. The page is
    used when it is the three.js page (surroundings or baked light): model-viewer cannot show those."""
    if os.path.isdir(src):
        glbs = sorted(f for f in os.listdir(src) if f.lower().endswith(".glb"))
        if len(glbs) != 1:
            raise SystemExit(f"{src}: put exactly one exported .glb (and its .html) in the folder, found {len(glbs)}")
        src = os.path.join(src, glbs[0])
    stem, ext = os.path.splitext(src)
    if ext.lower() == ".html":
        src = stem + ".glb"
    if not os.path.isfile(src):
        raise SystemExit(f"{src} not found")
    page = stem + ".html"
    if os.path.isfile(page) and 'id="fr-env"' in open(page, encoding="utf-8").read():
        return src, page
    return src, ""


def animation_seconds(data: bytes) -> float:
    """How long the model's (first) animation lasts, 0 without one."""
    doc, binary = web3d.read_glb(data)
    anims = doc.get("animations") or []
    if not anims:
        return 0.0
    longest = 0.0
    for smp in anims[0]["samplers"]:
        longest = max(longest, float(doc["accessors"][smp["input"]].get("max", [0.0])[0]))
    return round(longest, 2)


def web_model(src: str, model: str, caption: str, title: str = "", order: int = 0) -> dict:
    """Add or replace one model of "Turn it yourself": its .glb (or its export's own page) into site/media, its
    poster, its card in media.json "web_models" (``order``: 1 = first; 0 = where it was, or last)."""
    if not model:
        raise SystemExit("--web-model needs --model <id> (an entry of media.json 'models', with its credit)")
    if any(f in (model + os.path.basename(src)).lower() for f in FORBIDDEN_MODELS):
        raise SystemExit(f"'{model}' may not go on the site: the Fresing 400 is not public")
    glb, page = export_files(src)
    data = open(glb, "rb").read()
    bad = web3d.problems(data)
    if bad:
        raise SystemExit(f"{glb} is not a valid glTF file: {bad[0]}")
    size = os.path.getsize(page) if page else len(data)
    if size > WEB_MODEL_MAX:
        raise SystemExit(f"{os.path.basename(page or glb)} is {size / 1e6:.1f} MB; at most {WEB_MODEL_MAX / 1e6:.0f} MB "
                         "for the web (export it again with the Phone quality or Texture size 512)")
    if size > WEB_MODEL_WARN:
        print(f"warning: {os.path.basename(page or glb)} is {size / 1e6:.1f} MB – slow on a phone "
              f"(aim below {WEB_MODEL_WARN / 1e6:.0f} MB)")
    media = load_media()
    m = media.get("models", {}).get(model)
    if not m or not m.get("credit"):
        raise SystemExit(f"add '{model}' to 'models' in site/media/media.json (title, credit, licence) and to "
                         "site/CREDITS.md first")
    if m["credit"] not in open(os.path.join(SITE, "CREDITS.md"), encoding="utf-8").read():
        raise SystemExit(f"add the credit of '{model}' to site/CREDITS.md first: {m['credit']}")
    wid = re.sub(r"[^a-z0-9]+", "_", model.lower()).strip("_")
    name = wid + (PAGE_SUFFIX if page else ".glb")
    poster = wid + "_poster.jpg"
    if not poster_of_model(page or glb, os.path.join(MEDIA, poster)):
        raise SystemExit("no poster picture could be made: needs Node with Playwright (the web sessions have it)")
    shutil.copy2(page or glb, os.path.join(MEDIA, name))
    item = {"id": wid, "file": name, "poster": poster, "model": model,
            "caption": caption or m.get("title", ""), "seconds": animation_seconds(data)}
    if title:
        item["title"] = title
    items = [w for w in web_models(media)]
    at = next((i for i, w in enumerate(items) if w["id"] == wid), len(items))
    items = [w for w in items if w["id"] != wid]
    at = min(max(order - 1, 0), len(items)) if order else min(at, len(items))
    items.insert(at, item)
    for i, w in enumerate(items):
        w["order"] = i + 1
    media.pop("web_model", None)
    media["web_models"] = items
    _tidy(media)
    save_media(media)
    return media


def remove_web_model(wid: str) -> dict:
    """Take one model out of "Turn it yourself" (its files go with it)."""
    media = load_media()
    items = web_models(media)
    if not any(w["id"] == wid for w in items):
        raise SystemExit(f"no web model '{wid}' (there are: {', '.join(w['id'] for w in items) or 'none'})")
    items = [w for w in items if w["id"] != wid]
    for i, w in enumerate(items):
        w["order"] = i + 1
    media.pop("web_model", None)
    media["web_models"] = items
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
    ap.add_argument("--take", metavar="FOLDER_OR_ZIP",
                    help="take the render kit's pictures and videos into site/media (its folder or its zip)")
    ap.add_argument("--keep-old", action="store_true", help="with --take: keep the pictures already there")
    ap.add_argument("--hero-video", metavar="FILE", help="cut and compress the video at the top of the page")
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--length", type=float, default=15.0)
    ap.add_argument("--model", default="")
    ap.add_argument("--caption", default="")
    ap.add_argument("--web-model", metavar="FILE_OR_FOLDER",
                    help="add or replace a model of 'Turn it yourself': an exported .glb or export folder (with --model)")
    ap.add_argument("--title", default="", help="with --web-model: the card's title (default: the model's title)")
    ap.add_argument("--order", type=int, default=0, help="with --web-model: its place among the cards (1 = first)")
    ap.add_argument("--remove-web-model", metavar="ID", help="take a model out of 'Turn it yourself'")
    a = ap.parse_args(argv)
    if a.web_model:
        web_model(a.web_model, a.model, a.caption, a.title, a.order)
        print("site/media updated")
        return 0
    if a.remove_web_model:
        remove_web_model(a.remove_web_model)
        print("site/media updated")
        return 0
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
