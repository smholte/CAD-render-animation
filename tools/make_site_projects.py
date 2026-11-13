"""The landing page's moving models and the render kit (tasks 0112, 0116).

    ~/venv/bin/python tools/make_site_projects.py thor ceb_press --out <folder>
        clone the sources (pinned commits, only the folders needed) and write <model>.step + <model>.json there
        (iea15_offshore, iea15_onshore: the IEA 15 MW turbine from the owner's STEP on the draft release site-kit,
        see site_projects/fetch.py; FRESING_IEA15_STEP=<file> to use a copy)
    ~/venv/bin/python tools/make_site_projects.py thor --out <folder> --project [--quality draft] [--no-check]
        ... and the Fresing Render project <model>.blend (Blender as a Python module): imported, coloured as
        models.ini says, joints, cylinders, poses, the animation built and clash-checked; prints a summary
    ~/venv/bin/python tools/make_site_projects.py --kit <zip>
        the render kit for the owner: site/render_kit (scripts, models.ini, README, projects/*.json) + the moving
        models' STEP files in models/ (the sheets in the kit are written fresh from the sources)
    ~/venv/bin/python tools/make_site_projects.py --publish-kit <zip>
        (in the workflow site-kit.yml, with GITHUB_TOKEN) put the zip on the draft release "site-kit", replacing it

From Python (task 0111 builds the web model from the Thor project): ``convert(model, out)``, ``build_project(model,
out)``. The sheets the kit ships live in site/render_kit/projects/; ``--check-sheets`` says when they differ from a
fresh conversion (a test does it too).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KIT = os.path.join(ROOT, "site", "render_kit")
SHEETS = os.path.join(KIT, "projects")
sys.path.insert(0, os.path.join(ROOT, "tools"))

from site_projects import ceb, fetch, thor  # noqa: E402


class _Turbine:
    """The IEA 15 MW turbine in one of its versions (site_projects/iea15.py); the source is the owner's STEP."""

    _leaves: dict = {}                       # the STEP read once per run (32 s), shared by both versions

    def __init__(self, variant: str):
        self.variant = variant

    def convert(self, src: str, out: str, write_step: bool = True) -> dict:
        from site_projects import iea15, iea15_source
        key = os.path.realpath(src)
        if key not in self._leaves:
            self._leaves.clear()
            self._leaves[key] = iea15_source.read(src)
        return iea15.convert(src, out, write_step, self.variant, leaves=self._leaves[key])


MODELS = {"thor": thor, "ceb_press": ceb, "iea15_offshore": _Turbine("offshore"),
          "iea15_onshore": _Turbine("onshore")}
GIT_MODELS = ("thor", "ceb_press")           # sources anyone can clone; the turbine needs the owner's STEP
REPO = "smholte/CAD-render-animation"
KIT_TAG = "site-kit"
KIT_ASSET = "fresing_site_kit.zip"
KIT_FOLDER = "Fresing site kit"


def convert(model: str, out: str, cache: str = "", step: bool = True) -> dict:
    """Clone the model's source (once) and write <model>.step (unless ``step`` is False) and <model>.json into out."""
    if model not in MODELS:
        raise SystemExit(f"unknown model '{model}': use {', '.join(MODELS)}")
    src = fetch.fetch(model, cache)
    return MODELS[model].convert(src, out, write_step=step)


def same_sheet(a: dict, b: dict) -> list[str]:
    """Where two sheets differ (numbers to 1e-4), [] when they are the same."""
    out = []

    def walk(x, y, path):
        if isinstance(x, dict) and isinstance(y, dict):
            for k in sorted(set(x) | set(y)):
                if k not in x or k not in y:
                    out.append(f"{path}.{k}: only in one")
                else:
                    walk(x[k], y[k], f"{path}.{k}")
        elif isinstance(x, list) and isinstance(y, list):
            if len(x) != len(y):
                out.append(f"{path}: {len(x)} vs {len(y)} items")
            for i, (p, q) in enumerate(zip(x, y)):
                walk(p, q, f"{path}[{i}]")
        elif isinstance(x, (int, float)) and isinstance(y, (int, float)) and not isinstance(x, bool):
            if abs(float(x) - float(y)) > 1e-4:
                out.append(f"{path}: {x} vs {y}")
        elif x != y:
            out.append(f"{path}: {x!r} vs {y!r}")
    walk(a, b, "")
    return out


def check_sheets(cache: str = "", models=GIT_MODELS) -> list[str]:
    import tempfile
    problems = []
    with tempfile.TemporaryDirectory() as tmp:
        for model in models:
            fresh = convert(model, tmp, cache, step=False)
            with open(os.path.join(SHEETS, f"{model}.json"), encoding="utf-8") as fh:
                kept = json.load(fh)
            # the shipped sheet also carries what only the STEP pass works out (round faces, unique parts)
            problems += [f"{model}{p}" for p in same_sheet(_core(fresh), _core(kept))]
    return problems


def _core(sheet: dict) -> dict:
    s = json.loads(json.dumps(sheet))
    s.pop("unique_parts", None)
    for j in s.get("joints", []):
        j.pop("round_faces", None)
        j.pop("round_radius", None)
    return s


# ---------------------------------------------------------------------------
# the project (Blender as a Python module)
# ---------------------------------------------------------------------------

def _app():
    import bpy  # noqa: F401
    sys.path.insert(0, ROOT)
    sys.path.insert(0, KIT)
    import fresing_render
    if not hasattr(bpy.types.Scene, "fresing"):
        fresing_render.register()
    return fresing_render


def build_project(model: str, out: str, quality: str = "draft", check: bool = True, cache: str = "",
                  step: str = "", log=print) -> dict:
    """<out>/<model>.blend: the STEP imported with the app's importer, coloured as models.ini says, the motion made
    from the kit's sheet (site/render_kit/projects/<model>.json), the animation built and (``check``) clash-checked.
    ``step``: an already written STEP (else it is converted first). Returns the summary of ``projects.make``."""
    import bpy
    pkg = _app()
    import make_site_pictures as kit
    import projects
    os.makedirs(out, exist_ok=True)
    if not step:
        convert(model, out, cache)
        step = os.path.join(out, f"{model}.step")
    sheet = projects.load(model)
    _general, models = kit.read_settings(os.path.join(KIT, "models.ini"))
    m = next((x for x in models if x.get("project") == model), None)
    t0 = time.time()
    scene = kit.fresh_import(pkg, step, quality, "Z", out)
    log(f"imported {os.path.basename(step)} in {time.time() - t0:.0f} s")
    if m and m["colours"]:
        kit.paint(pkg, scene, m["colours"])
    res = projects.make(pkg, scene, sheet, check=check, log=log, check_extra_animation=check)
    path = os.path.join(out, f"{model}.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path, check_existing=False)
    res["path"] = path
    return res


# ---------------------------------------------------------------------------
# the kit and its draft release
# ---------------------------------------------------------------------------

KIT_FILES = ("Make site pictures.bat", "make_site_pictures.py", "projects.py", "models.ini", "README.txt")


def make_kit(path: str, cache: str = "", work: str = "") -> str:
    """The kit zip: one folder "Fresing site kit" with the scripts, models.ini, README.txt, projects/*.json and
    models/<model>.step of every moving model, written fresh from the sources (their sheets must match the kit's)."""
    import tempfile
    work = work or tempfile.mkdtemp(prefix="site_kit_")
    for model in MODELS:
        convert(model, work, cache)
        with open(os.path.join(work, f"{model}.json"), encoding="utf-8") as fh:
            fresh = json.load(fh)
        with open(os.path.join(SHEETS, f"{model}.json"), encoding="utf-8") as fh:
            kept = json.load(fh)
        diff = same_sheet(_core(fresh), _core(kept))
        if diff:
            raise SystemExit(f"site/render_kit/projects/{model}.json differs from the source: {diff[:3]} – "
                             f"write it again (make_site_projects.py {model} --out site/render_kit/projects)")
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for f in KIT_FILES:
            z.write(os.path.join(KIT, f), f"{KIT_FOLDER}/{f}")
        for model in MODELS:
            z.write(os.path.join(SHEETS, f"{model}.json"), f"{KIT_FOLDER}/projects/{model}.json")
            z.write(os.path.join(work, f"{model}.step"), f"{KIT_FOLDER}/models/{model}.step")
        z.writestr(f"{KIT_FOLDER}/models/README.txt",
                   ", ".join(f"{m}.step" for m in MODELS) + " come with this kit.\r\n"
                   "evo.step, openarm.step and farmbot.step are taken from the models folder of your first kit when\r\n"
                   "it is next to this folder (or put them here).\r\n")
    return path


def _api(method: str, url: str, token: str, data: bytes | None = None, ctype: str = "application/json"):
    import urllib.request
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "Content-Type": ctype,
        "User-Agent": "fresing-site-kit"})
    with urllib.request.urlopen(req, timeout=600) as r:
        body = r.read()
    return json.loads(body) if body else {}


KIT_NOTES = ("The render kit for the landing page's pictures and videos (task 0112). Not a release of the app: a "
             "draft only people with access to the repository see.\n\n"
             "Download fresing_site_kit.zip, follow README.txt inside it. When it is done, upload the "
             "site_pictures_<date>.zip it made here: Edit (pencil) -> drag the file onto 'Attach binaries' -> "
             "Save draft. Do not publish this draft.")


def publish_kit(path: str, token: str, repo: str = REPO, api=_api) -> dict:
    """Put the kit zip on the draft release KIT_TAG (made when missing; an older kit zip is replaced, the owner's
    uploads stay). Returns the release."""
    base = f"https://api.github.com/repos/{repo}"
    rels = api("GET", f"{base}/releases?per_page=100", token)
    rel = next((r for r in rels if r.get("tag_name") == KIT_TAG), None)
    if rel is not None and not rel.get("draft"):
        raise SystemExit(f"the release {KIT_TAG} is published: it must stay a draft (delete or unpublish it)")
    if rel is None:
        rel = api("POST", f"{base}/releases", token, json.dumps({
            "tag_name": KIT_TAG, "name": "Site kit – pictures and videos for the web page", "body": KIT_NOTES,
            "draft": True, "prerelease": True}).encode())
    for a in rel.get("assets", []):
        if a["name"] == KIT_ASSET:
            api("DELETE", f"{base}/releases/assets/{a['id']}", token)
    up = rel["upload_url"].split("{", 1)[0]
    with open(path, "rb") as fh:
        api("POST", f"{up}?name={KIT_ASSET}", token, fh.read(), "application/zip")
    return rel


# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("models", nargs="*", help=", ".join(MODELS))
    ap.add_argument("--out", default="")
    ap.add_argument("--cache", default="", help="where the sources are cloned (default ~/.cache/fresing_site_sources)")
    ap.add_argument("--sheet-only", action="store_true", help="only the sheet (no STEP)")
    ap.add_argument("--project", action="store_true", help="also the .blend project (Blender as a Python module)")
    ap.add_argument("--quality", default="draft", choices=("draft", "normal", "fine"))
    ap.add_argument("--no-check", action="store_true", help="with --project: no clash check")
    ap.add_argument("--kit", metavar="ZIP")
    ap.add_argument("--publish-kit", metavar="ZIP")
    ap.add_argument("--check-sheets", action="store_true")
    a = ap.parse_args(argv)
    if a.check_sheets:
        problems = check_sheets(a.cache)
        for p in problems:
            print("DIFFERS:", p)
        print(f"{len(problems)} differences")
        return 1 if problems else 0
    if a.kit:
        print(make_kit(a.kit, a.cache))
        return 0
    if a.publish_kit:
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if not token:
            raise SystemExit("--publish-kit needs GITHUB_TOKEN")
        rel = publish_kit(a.publish_kit, token, os.environ.get("GITHUB_REPOSITORY", REPO))
        print(f"kit on the draft release {rel.get('html_url', KIT_TAG)}")
        return 0
    if not a.models or not a.out:
        ap.error("name the models and --out")
    for model in a.models:
        if a.project:
            res = build_project(model, a.out, a.quality, not a.no_check, a.cache)
            print(json.dumps(res, indent=1))
            if res.get("clash_rows"):
                return 1
        else:
            sheet = convert(model, a.out, a.cache, step=not a.sheet_only)
            print(f"{model}: {sheet['parts']} parts, {len(sheet['joints'])} joints, "
                  f"{len(sheet['cylinders'])} cylinders -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
