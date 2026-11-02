"""Build a Windows release of Fresing Render.

    python tools/build_release.py [--blender-ext PATH_TO_blender_ext.py]

Produces in dist/:
    fresing_render-<version>.zip                 the Blender extension (with OpenCascade wheels)
    FresingRender-<version>-windows/             installer folder (Install.bat, app layout, extension)
    FresingRender-<version>-windows.zip          the same folder zipped, to hand out
    update-repo/                                 static update repository (index.json + zips)
                                                 -> upload this folder to the update server or share
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import shutil
import subprocess
import sys
import zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PKG = os.path.join(ROOT, "fresing_render")
DIST = os.path.join(ROOT, "dist")
WHEEL_CACHE = os.path.join(ROOT, "wheels")
WHEELS = [
    ("cadquery-ocp-novtk", "8.0.1.1.0", "cadquery_ocp_novtk-8.0.1.1.0-cp313-cp313-win_amd64.whl"),
    ("cadquery-ocp-proxy", "8.0.1.1.0", "cadquery_ocp_proxy-8.0.1.1.0-py3-none-any.whl"),
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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--blender-ext")
    args = ap.parse_args()

    v = version()
    ext_tool = find_blender_ext(args.blender_ext)
    ensure_wheels()

    stage = os.path.join(DIST, "stage", "fresing_render")
    shutil.rmtree(os.path.join(DIST, "stage"), ignore_errors=True)
    shutil.copytree(PKG, stage, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    os.makedirs(os.path.join(stage, "wheels"), exist_ok=True)
    for _, _, fname in WHEELS:
        shutil.copy2(os.path.join(WHEEL_CACHE, fname), os.path.join(stage, "wheels", fname))

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
    shutil.copytree(os.path.join(ROOT, "app_template"), os.path.join(rel, "app_template"),
                    ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy2(os.path.join(ROOT, "docs", "README-install.txt"), os.path.join(rel, "README.txt"))

    rel_zip = rel + ".zip"
    if os.path.exists(rel_zip):
        os.remove(rel_zip)
    with zipfile.ZipFile(rel_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for dirpath, _, files in os.walk(rel):
            for f in files:
                full = os.path.join(dirpath, f)
                zf.write(full, os.path.relpath(full, DIST))

    # static update repository
    repo = os.path.join(DIST, "update-repo")
    os.makedirs(repo, exist_ok=True)
    shutil.copy2(ext_zip, repo)
    run([sys.executable, ext_tool, "server-generate", "--repo-dir", repo, "--html"])

    shutil.rmtree(os.path.join(DIST, "stage"), ignore_errors=True)
    print()
    print("extension :", ext_zip, f"({os.path.getsize(ext_zip) / 1e6:.1f} MB)")
    print("installer :", rel_zip, f"({os.path.getsize(rel_zip) / 1e6:.1f} MB)")
    print("update repo:", repo)


if __name__ == "__main__":
    main()
