"""The stress-test model of the PC check "Stress" (task 0315), from the command line.

    ~/venv/bin/python tools/make_test_stress.py <out folder> [--small] [--revision B] [--measure] [--zip]
    python tools/make_test_stress.py --publish <zip>          (the workflow stress.yml, with GITHUB_TOKEN)

The model itself is made by ``fresing_render/pccheck/stress_scene.py`` (shipped with the app, so the owner's PC makes it
at run time): an invented offshore substation topside of about 11,000 placed / 2,000 unique parts. It is never
committed. ``--measure`` reads it with the app's own STEP reader at Draft, Normal and Fine and prints the triangles and
times; ``--zip`` packs the STEP, its joint sheet and a README into ``FresingStressModel.zip`` for the owner;
``--publish`` puts that zip on the DRAFT release "stress-model" (only people with access to the repository see a
draft; the apps' version checks read only tags starting with "v").
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SCENE = os.path.join(ROOT, "fresing_render", "pccheck", "stress_scene.py")
READER = os.path.join(ROOT, "fresing_render", "importer", "step_reader.py")
REPO = "smholte/CAD-render-animation"
TAG = "stress-model"
ASSET = "FresingStressModel.zip"
STEP_NAME = "Fresing stress topside.step"
README = (
    "Fresing Render - stress test model (made up)\r\n\r\n"
    "An invented offshore substation topside of about 11,000 parts, made by the app's PC check (task 0315) to test\r\n"
    "how the app copes with a very big assembly. Nothing of a real design.\r\n\r\n"
    "Import it like any STEP file: open 1 Import in the side panel, leave Detail on Normal and click\r\n"
    "Import STEP... (or drag the .step file onto the 3D view). It takes a minute or two.\r\n"
    "The joints of the crane, the davit and the doors are listed in the .joints.json file (millimetres).\r\n")
NOTES = ("The stress-test model of the PC check 'Stress' (task 0315): an invented offshore substation topside, about "
         "11,000 parts. Not a release of the app: a draft only people with access to the repository see.\n\n"
         "Download FresingStressModel.zip, unzip it and import the STEP file: 1 Import > Import STEP…. "
         "Do not publish this draft.")


def make(out_dir: str, small: bool = False, revision: str = "A") -> tuple[str, dict]:
    os.makedirs(out_dir, exist_ok=True)
    step = os.path.join(out_dir, STEP_NAME if revision == "A" else STEP_NAME.replace(".step", f" rev {revision}.step"))
    info_path = os.path.splitext(step)[0] + ".info.json"
    cmd = [sys.executable, SCENE, step, "--revision", revision, "--json", info_path] + (["--small"] if small else [])
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
    with open(info_path, encoding="utf-8") as fh:
        return step, json.load(fh)


def measure(step: str, work: str) -> dict:
    """Triangles (placed and unique) and reader time at Draft, Normal and Fine, with the app's own reader."""
    out = {}
    for quality in ("draft", "normal", "fine"):
        cache = os.path.join(work, f"cache_{quality}")
        t0 = time.time()
        subprocess.run([sys.executable, READER, step, cache, "--quality", quality], check=True,
                       stdout=subprocess.DEVNULL)
        secs = time.time() - t0
        with open(os.path.join(cache, "tree.json"), encoding="utf-8") as fh:
            tree = json.load(fh)
        uses: dict = {}
        for n in tree["nodes"]:
            if n.get("kind") == "part" and n.get("mesh") is not None:
                uses[n["mesh"]] = uses.get(n["mesh"], 0) + 1
        meshes = tree["meshes"]
        out[quality] = {"seconds": round(secs, 1), "triangles_placed": sum(meshes[i]["tris"] * c for i, c in uses.items()),
                        "triangles_unique": sum(m["tris"] for m in meshes), "helpers": tree["stats"]["mesh_helpers"]}
    return out


def pack(step: str, path: str) -> str:
    joints = os.path.splitext(step)[0] + ".joints.json"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        z.write(step, os.path.basename(step))
        if os.path.isfile(joints):
            z.write(joints, os.path.basename(joints))
        z.writestr("README.txt", README)
    return path


def _api(method: str, url: str, token: str, data: bytes | None = None, ctype: str = "application/json"):
    import urllib.request
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "Content-Type": ctype,
        "User-Agent": "fresing-stress-model"})
    with urllib.request.urlopen(req, timeout=900) as r:
        body = r.read()
    return json.loads(body) if body else {}


def publish(path: str, token: str, repo: str = REPO, api=_api) -> dict:
    """Put the zip on the draft release TAG (made when missing; an older zip of the same name is replaced). Refuses a
    published release of that name: it must stay a draft."""
    base = f"https://api.github.com/repos/{repo}"
    rels = api("GET", f"{base}/releases?per_page=100", token)
    rel = next((r for r in rels if r.get("tag_name") == TAG), None)
    if rel is not None and not rel.get("draft"):
        raise SystemExit(f"the release {TAG} is published: it must stay a draft (delete or unpublish it)")
    if rel is None:
        rel = api("POST", f"{base}/releases", token, json.dumps({
            "tag_name": TAG, "name": "Stress model – a made-up 11,000-part topside for tests", "body": NOTES,
            "draft": True, "prerelease": True}).encode())
    for a in rel.get("assets", []):
        if a["name"] == ASSET:
            api("DELETE", f"{base}/releases/assets/{a['id']}", token)
    up = rel["upload_url"].split("{", 1)[0]
    with open(path, "rb") as fh:
        api("POST", f"{up}?name={ASSET}", token, fh.read(), "application/zip")
    return rel


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("out", nargs="?", default="")
    ap.add_argument("--small", action="store_true")
    ap.add_argument("--revision", default="A", choices=("A", "B"))
    ap.add_argument("--measure", action="store_true")
    ap.add_argument("--zip", action="store_true")
    ap.add_argument("--publish", default="", help="a zip made with --zip: put it on the draft release")
    a = ap.parse_args(argv)
    if a.publish:
        token = os.environ.get("GITHUB_TOKEN", "")
        if not token:
            raise SystemExit("GITHUB_TOKEN is not set")
        rel = publish(a.publish, token)
        print(f"model on the draft release {rel.get('html_url', TAG)}")
        return 0
    if not a.out:
        ap.error("give an out folder")
    t0 = time.time()
    step, info = make(a.out, a.small, a.revision)
    info["make_seconds"] = round(time.time() - t0, 1)
    if a.measure:
        info["measure"] = measure(step, a.out)
    if a.zip:
        info["zip"] = pack(step, os.path.join(a.out, ASSET))
        info["zip_mb"] = round(os.path.getsize(info["zip"]) / 1e6, 1)
    print(json.dumps(info, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
