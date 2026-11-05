"""Build a Windows release of Fresing Render.

    python tools/build_release.py [--blender-ext PATH_TO_blender_ext.py] [--base-url URL]
                                  [--dist DIR] [--version-as X.Y.Z --template-from DIR]

Produces in dist/:
    fresing_render-<version>.zip                 the Blender extension (with OpenCascade and Manifold wheels,
                                                 the user guide, the app template and changelog.json inside)
    FresingRender-<version>-windows/             installer folder (Install.bat, app layout, extension,
                                                 "User guide.html")
    FresingRender-<version>-windows.zip          the same folder zipped, to hand out
    update-repo/                                 update listing: index.json (Blender's standard listing),
                                                 changelog.json and the extension zip. GitHub publishes
                                                 these with every release (docs/UPDATES.md)

--base-url   full address of the folder the zip will be downloaded from (the release's download
             folder on GitHub); without it index.json names the zip relative to itself.
--version-as / --template-from   build the same code as another version with another app template
             (the automatic tests install such an "old" version and update it, task 0020).
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
PKG = os.path.join(ROOT, "fresing_render")
TEMPLATE = os.path.join(ROOT, "app_template", "fresing_render")
TEMPLATE_FILES_DIR = "app_template_files"      # update_helper.TEMPLATE_FILES_DIR
DIST = os.path.join(ROOT, "dist")
WHEEL_CACHE = os.path.join(ROOT, "wheels")
WHEELS = [
    ("cadquery-ocp-novtk", "8.0.1.1.0", "cadquery_ocp_novtk-8.0.1.1.0-cp313-cp313-win_amd64.whl"),
    ("cadquery-ocp-proxy", "8.0.1.1.0", "cadquery_ocp_proxy-8.0.1.1.0-py3-none-any.whl"),
    ("manifold3d", "3.5.4", "manifold3d-3.5.4-cp313-cp313-win_amd64.whl"),      # milling (task 0027)
]


def version() -> str:
    init = open(os.path.join(PKG, "__init__.py"), encoding="utf-8").read()
    v = re.search(r'__version__\s*=\s*"([^"]+)"', init).group(1)
    manifest = open(os.path.join(PKG, "blender_manifest.toml"), encoding="utf-8").read()
    mv = re.search(r'^version\s*=\s*"([^"]+)"', manifest, re.M).group(1)
    if v != mv:
        sys.exit(f"Version mismatch: __init__.py {v} vs blender_manifest.toml {mv}")
    return v


def find_blender_ext(hint: str | None) -> str:
    if hint and os.path.isfile(hint):
        return hint
    import importlib.util
    spec = importlib.util.find_spec("bpy")
    if spec and spec.submodule_search_locations:
        base = list(spec.submodule_search_locations)[0]
        hits = glob.glob(os.path.join(base, "*", "scripts", "addons_core", "bl_pkg", "cli", "blender_ext.py"))
        if hits:
            return hits[0]
    sys.exit("blender_ext.py not found: pass --blender-ext <Blender>/<ver>/scripts/addons_core/bl_pkg/cli/blender_ext.py")


def ensure_wheels() -> None:
    os.makedirs(WHEEL_CACHE, exist_ok=True)
    for name, ver, fname in WHEELS:
        if os.path.isfile(os.path.join(WHEEL_CACHE, fname)):
            continue
        print("downloading", fname)
        subprocess.check_call([sys.executable, "-m", "pip", "download", "--only-binary=:all:", "--no-deps",
                               "--platform", "win_amd64", "--python-version", "3.13", "-d", WHEEL_CACHE,
                               f"{name}=={ver}"])


def run(cmd):
    print("$", " ".join(cmd))
    subprocess.check_call(cmd)


def changelog_json() -> dict:
    """CHANGELOG.md as data: what the app shows under "What's new"."""
    from fresing_render.core import updates
    text = open(os.path.join(ROOT, "CHANGELOG.md"), encoding="utf-8").read()
    return {"versions": updates.parse_changelog(text)}


def set_version(stage: str, version: str) -> None:
    """Give a staged extension another version number (tests: an "old" version to update from)."""
    for name, pattern, repl in (("__init__.py", r'__version__\s*=\s*"[^"]+"', f'__version__ = "{version}"'),
                                ("blender_manifest.toml", r'(?m)^version\s*=\s*"[^"]+"', f'version = "{version}"')):
        path = os.path.join(stage, name)
        text = open(path, encoding="utf-8").read()
        new, n = re.subn(pattern, repl, text, count=1)
        if n != 1:
            sys.exit(f"no version found in {path}")
        open(path, "w", encoding="utf-8").write(new)


def stage_extension(stage: str, *, template_src: str = TEMPLATE, version: str = "") -> str:
    """Copy the extension into ``stage`` with everything that ships inside it besides the code:
    the user guide (Help > Fresing Render user guide), the app template (an update copies it into
    place) and changelog.json (what's new after an update). Wheels are added by the caller."""
    shutil.copytree(PKG, stage, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    import build_guide
    build_guide.build(os.path.join(stage, "guide", build_guide.GUIDE_FILE))
    shutil.copytree(template_src, os.path.join(stage, TEMPLATE_FILES_DIR),
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    if not os.path.isfile(os.path.join(stage, TEMPLATE_FILES_DIR, "splash.png")):     # old test templates
        shutil.copy2(os.path.join(TEMPLATE, "splash.png"), os.path.join(stage, TEMPLATE_FILES_DIR))
    with open(os.path.join(stage, "changelog.json"), "w", encoding="utf-8") as fh:
        json.dump(changelog_json(), fh, indent=1, ensure_ascii=False)
    if version:
        set_version(stage, version)
    return stage


def write_update_repo(repo: str, ext_zip: str, ext_tool, base_url: str = "") -> None:
    """index.json (+ index.html) by Blender's own tool, changelog.json next to it.

    ``ext_tool``: path of blender_ext.py (bpy module), or a command list such as
    [blender, "--factory-startup", "--command", "extension"] (the real Blender program)."""
    os.makedirs(repo, exist_ok=True)
    for old in glob.glob(os.path.join(repo, "fresing_render-*.zip")):
        os.remove(old)             # one version per listing: the app offers the newest anyway
    shutil.copy2(ext_zip, repo)
    prefix = list(ext_tool) if isinstance(ext_tool, (list, tuple)) else [sys.executable, ext_tool]
    run(prefix + ["server-generate", "--repo-dir", repo, "--html"])
    index_path = os.path.join(repo, "index.json")
    if base_url:                   # full addresses: the listing stays right when it is copied or redirected
        index = json.load(open(index_path, encoding="utf-8"))
        for item in index.get("data", []):
            url = item.get("archive_url", "")
            if url.startswith("./"):
                item["archive_url"] = base_url.rstrip("/") + "/" + url[2:]
        with open(index_path, "w", encoding="utf-8") as fh:
            json.dump(index, fh, indent=2)
    with open(os.path.join(repo, "changelog.json"), "w", encoding="utf-8") as fh:
        json.dump(changelog_json(), fh, indent=1, ensure_ascii=False)


def main() -> None:
    global DIST
    ap = argparse.ArgumentParser()
    ap.add_argument("--blender-ext")
    ap.add_argument("--base-url", default="", help="download folder of the zip (GitHub release)")
    ap.add_argument("--dist", default="", help="output folder (default: dist/)")
    ap.add_argument("--version-as", default="", help="build as this version (tests)")
    ap.add_argument("--template-from", default="", help="app template folder to ship (tests)")
    args = ap.parse_args()
    if args.dist:
        DIST = os.path.abspath(args.dist)

    v = args.version_as or version()
    ext_tool = find_blender_ext(args.blender_ext)
    ensure_wheels()

    stage = os.path.join(DIST, "stage", "fresing_render")
    shutil.rmtree(os.path.join(DIST, "stage"), ignore_errors=True)
    template_src = os.path.abspath(args.template_from) if args.template_from else TEMPLATE
    # the user guide, the app template and the changelog go inside the extension, so an update
    # brings the ones of that version along
    stage_extension(stage, template_src=template_src, version=args.version_as)
    os.makedirs(os.path.join(stage, "wheels"), exist_ok=True)
    for _, _, fname in WHEELS:
        shutil.copy2(os.path.join(WHEEL_CACHE, fname), os.path.join(stage, "wheels", fname))
    guide = os.path.join(stage, "guide", "user_guide.html")

    os.makedirs(DIST, exist_ok=True)
    for old in glob.glob(os.path.join(DIST, "fresing_render-*.zip")):
        os.remove(old)
    run([sys.executable, ext_tool, "build", "--source-dir", stage, "--output-dir", DIST])
    ext_zip = sorted(glob.glob(os.path.join(DIST, "fresing_render-*.zip")))[-1]
    run([sys.executable, ext_tool, "validate", ext_zip])

    # installer folder
    rel = os.path.join(DIST, f"FresingRender-{v}-windows")
    shutil.rmtree(rel, ignore_errors=True)
    os.makedirs(rel)
    shutil.copy2(ext_zip, rel)
    for f in ("Install.bat", "Install-FresingRender.ps1", "Uninstall.bat", "Uninstall-FresingRender.ps1"):
        shutil.copy2(os.path.join(ROOT, "installer", f), rel)
    shutil.copytree(os.path.join(stage, TEMPLATE_FILES_DIR), os.path.join(rel, "app_template", "fresing_render"),
                    ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy2(os.path.join(ROOT, "docs", "README-install.txt"), os.path.join(rel, "README.txt"))
    shutil.copy2(guide, os.path.join(rel, "User guide.html"))           # to read before installing

    rel_zip = rel + ".zip"
    if os.path.exists(rel_zip):
        os.remove(rel_zip)
    with zipfile.ZipFile(rel_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for dirpath, _, files in os.walk(rel):
            for f in files:
                full = os.path.join(dirpath, f)
                zf.write(full, os.path.relpath(full, DIST))

    # update listing (GitHub publishes it with the release)
    repo = os.path.join(DIST, "update-repo")
    write_update_repo(repo, ext_zip, ext_tool, args.base_url)

    shutil.rmtree(os.path.join(DIST, "stage"), ignore_errors=True)
    print()
    print("user guide:", os.path.join(rel, "User guide.html"))
    print("extension :", ext_zip, f"({os.path.getsize(ext_zip) / 1e6:.1f} MB)")
    print("installer :", rel_zip, f"({os.path.getsize(rel_zip) / 1e6:.1f} MB)")
    print("update repo:", repo)


if __name__ == "__main__":
    main()
