"""Build the user guide: docs/USER-GUIDE.md -> one self-contained HTML page (pictures inside).

    ~/venv/bin/python tools/build_guide.py [--out dist/guide/user_guide.html]

The page works offline, can be e-mailed or copied anywhere, and prints well (browser > Print >
Save as PDF). tools/build_release.py puts it inside the extension (fresing_render/guide/) – the
Help menu opens it from there – and next to Install.bat as "User guide.html".

Needs the Python package "markdown" (pip install markdown).
Pictures: docs/img/*.png, made with tools/guide_screens.py from the test models only.
"""

from __future__ import annotations

import argparse
import base64
import datetime
import html
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SOURCE = os.path.join(ROOT, "docs", "USER-GUIDE.md")
GUIDE_FILE = "user_guide.html"        # the app template's Help menu looks for <extension>/guide/user_guide.html
DEFAULT_OUT = os.path.join(ROOT, "dist", "guide", GUIDE_FILE)


def version() -> str:
    init = open(os.path.join(ROOT, "fresing_render", "__init__.py"), encoding="utf-8").read()
    return re.search(r'__version__\s*=\s*"([^"]+)"', init).group(1)


def _embed_images(body: str, base_dir: str) -> tuple[str, list[str]]:
    """src="img/x.png" -> data URI, so the page is one file. Returns the page and the files used."""
    used = []

    def repl(m):
        src = m.group(2)
        if src.startswith(("data:", "http:", "https:")):
            return m.group(0)
        path = os.path.normpath(os.path.join(base_dir, src))
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Picture not found: {src} (looked for {path})")
        used.append(path)
        ext = os.path.splitext(path)[1].lower().lstrip(".")
        mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "svg": "image/svg+xml"}[ext]
        data = base64.b64encode(open(path, "rb").read()).decode("ascii")
        return f'{m.group(1)}"data:{mime};base64,{data}"'

    return re.sub(r'(<img\b[^>]*?\bsrc=)"([^"]+)"', repl, body), used


def _toc(body: str) -> str:
    """Chapters (h2) with their anchors, for the contents list."""
    items = []
    for m in re.finditer(r'<a id="([^"]+)"></a>\s*<h2[^>]*>(.*?)</h2>', body, re.S):
        anchor, title = m.group(1), re.sub(r"<[^>]+>", "", m.group(2)).strip()
        items.append(f'<li><a href="#{anchor}">{title}</a></li>')
    return "<ol class=\"toc\">" + "".join(items) + "</ol>" if items else ""


def render(md_text: str, base_dir: str, ver: str, date: str) -> tuple[str, list[str]]:
    import markdown
    md_text = re.sub(r"<!--.*?-->", "", md_text, flags=re.S)        # notes for the chats stay in the source
    # the title line becomes the page header
    title_m = re.match(r"\s*#\s+(.+)\n", md_text)
    title = title_m.group(1).strip() if title_m else "Fresing Render user guide"
    if title_m:
        md_text = md_text[title_m.end():]
    body = markdown.markdown(md_text, extensions=["tables", "sane_lists", "md_in_html"], output_format="html")
    # anchors written as <a id="x"></a> on their own line come out wrapped in <p>
    body = re.sub(r'<p>(<a id="[^"]+"></a>)</p>', r"\1", body)
    body, used = _embed_images(body, base_dir)
    page = PAGE.format(title=html.escape(title), version=html.escape(ver), date=html.escape(date),
                       toc=_toc(body), body=body)
    return page, used


def build(out_path: str = DEFAULT_OUT, source: str = SOURCE) -> str:
    try:
        import markdown  # noqa: F401
    except ImportError:
        sys.exit("The user guide needs the Python package 'markdown': ~/venv/bin/pip install markdown")
    text = open(source, encoding="utf-8").read()
    today = datetime.date.today()
    date = f"{today.day} {today:%B %Y}"
    page, _used = render(text, os.path.dirname(source), version(), date)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(page)
    return out_path


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
:root {{
  --bg: #ffffff; --text: #1f2328; --muted: #59636e; --line: #d8dee4; --accent: #2f6fc0;
  --tip: #eef5fd; --tip-line: #2f6fc0; --warn: #fdf4e3; --warn-line: #c27c0e; --code: #f2f4f7;
}}
@media (prefers-color-scheme: dark) {{
  :root {{ --bg: #17191c; --text: #e6e8eb; --muted: #a0a8b2; --line: #33383f; --accent: #6aa5ef;
          --tip: #1b2735; --tip-line: #6aa5ef; --warn: #2e2618; --warn-line: #d9a24a; --code: #24282e; }}
}}
* {{ box-sizing: border-box; }}
html {{ scroll-padding-top: 16px; }}
body {{ margin: 0; background: var(--bg); color: var(--text);
       font: 16px/1.55 "Segoe UI", system-ui, -apple-system, Roboto, Helvetica, Arial, sans-serif; }}
.wrap {{ display: grid; grid-template-columns: 250px minmax(0, 1fr); gap: 40px; max-width: 1180px;
        margin: 0 auto; padding: 32px 24px 80px; }}
nav {{ position: sticky; top: 24px; align-self: start; max-height: calc(100vh - 48px); overflow: auto; }}
nav .brand {{ font-weight: 700; font-size: 18px; margin: 0 0 2px; }}
nav .meta {{ color: var(--muted); font-size: 13px; margin: 0 0 18px; }}
.toc {{ list-style: none; padding: 0; margin: 0; border-left: 2px solid var(--line); }}
.toc li a {{ display: block; padding: 5px 0 5px 14px; color: var(--muted); text-decoration: none; font-size: 15px; }}
.toc li a:hover {{ color: var(--accent); }}
main {{ min-width: 0; }}
h1 {{ font-size: 34px; line-height: 1.2; margin: 0 0 6px; }}
.sub {{ color: var(--muted); margin: 0 0 28px; }}
h2 {{ font-size: 26px; margin: 56px 0 14px; padding-top: 18px; border-top: 1px solid var(--line); clear: both; }}
h3 {{ font-size: 19px; margin: 30px 0 10px; clear: both; }}
p, li {{ max-width: 70ch; }}
a {{ color: var(--accent); }}
ol, ul {{ padding-left: 1.4em; }}
li {{ margin: 4px 0; }}
li > ul, li > ol {{ margin-top: 4px; }}
kbd {{ font: 13px/1 ui-monospace, Consolas, monospace; padding: 2px 6px; border: 1px solid var(--line);
       border-bottom-width: 2px; border-radius: 4px; background: var(--code); white-space: nowrap; }}
code {{ font: 14px ui-monospace, Consolas, monospace; background: var(--code); padding: 1px 5px; border-radius: 4px;
        white-space: nowrap; }}
b, strong {{ font-weight: 650; }}
img {{ max-width: 100%; height: auto; border-radius: 6px; }}
img.panel {{ float: right; width: 330px; margin: 4px 0 20px 28px; box-shadow: 0 1px 6px rgba(0,0,0,.25); }}
img.wide {{ display: block; width: 100%; margin: 14px 0 22px; box-shadow: 0 1px 6px rgba(0,0,0,.25); }}
img.small {{ display: block; width: 440px; margin: 10px 0 18px; box-shadow: 0 1px 6px rgba(0,0,0,.25); }}
main img {{ cursor: zoom-in; }}
#zoom {{ position: fixed; inset: 0; z-index: 10; display: flex; align-items: flex-start; justify-content: center;
        overflow: auto; padding: 24px; background: rgba(0, 0, 0, .86); cursor: zoom-out; }}
#zoom[hidden] {{ display: none; }}
#zoom img {{ max-width: none; width: auto; float: none; margin: auto; box-shadow: none; cursor: zoom-out; }}
blockquote {{ margin: 16px 0; padding: 10px 16px; background: var(--tip); border-left: 4px solid var(--tip-line);
             border-radius: 0 6px 6px 0; max-width: 70ch; }}
blockquote p {{ margin: 6px 0; }}
blockquote.warn {{ background: var(--warn); border-left-color: var(--warn-line); }}
table {{ border-collapse: collapse; margin: 14px 0 22px; font-size: 15px; }}
th, td {{ border: 1px solid var(--line); padding: 6px 10px; text-align: left; vertical-align: top; }}
th {{ background: var(--code); }}
@media (max-width: 900px) {{
  .wrap {{ grid-template-columns: 1fr; gap: 0; padding: 20px 16px 60px; }}
  nav {{ position: static; max-height: none; margin-bottom: 18px; }}
  img.panel {{ float: none; display: block; width: 100%; max-width: 360px; margin: 10px 0 18px; }}
}}
@media print {{
  :root {{ --bg: #fff; --text: #000; }}
  .wrap {{ display: block; padding: 0; max-width: none; }}
  nav {{ position: static; }}
  #zoom {{ display: none; }}
  h2 {{ break-before: page; border-top: none; }}
  img {{ break-inside: avoid; box-shadow: none; }}
  a {{ color: inherit; text-decoration: none; }}
}}
</style>
</head>
<body>
<div class="wrap">
<nav>
<p class="brand">Fresing Render</p>
<p class="meta">User guide · version {version}</p>
{toc}
</nav>
<main>
<h1>{title}</h1>
<p class="sub">For Fresing Render {version} · made {date}</p>
{body}
</main>
</div>
<div id="zoom" hidden><img alt=""></div>
<script>
// a click on a picture shows it at full size; a click or Esc closes it
(function () {{
  var zoom = document.getElementById("zoom"), big = zoom.querySelector("img");
  document.querySelectorAll("main img").forEach(function (img) {{
    img.title = "Click to enlarge";
    img.addEventListener("click", function () {{ big.src = img.src; big.alt = img.alt; zoom.hidden = false; }});
  }});
  zoom.addEventListener("click", function () {{ zoom.hidden = true; }});
  document.addEventListener("keydown", function (e) {{ if (e.key === "Escape") zoom.hidden = true; }});
}})();
</script>
</body>
</html>
"""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Build the user guide (one HTML page with the pictures inside)")
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args(argv)
    path = build(args.out)
    print("user guide:", path, f"({os.path.getsize(path) / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
