"""Make the built-in materials' pictures for the material picker (task 0273).

    python tools/material_pictures.py              # the missing and changed ones (hashes.json says which)
    python tools/material_pictures.py --all        # every one again
    python tools/material_pictures.py --only paint_satin preset:paint_7035
    python tools/material_pictures.py --check      # exit 1 when one is missing or old (what the test checks)

Runs the real Blender (``--blender``, default ~/blender-5.2.3/…, or $BLENDER) in the background with
``fresing_render/material_picture_runner.py``: Cycles on the processor, 32 samples + denoise, 256 px JPEG into
``fresing_render/data/material_pictures/``; ``hashes.json`` there records what each picture was made from
(``core/material_files.picture_hash``). About 4 s a picture on a 4-core web machine.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from fresing_render.core import material_files as F  # noqa: E402

DEFAULT_BLENDER = os.environ.get("BLENDER") or os.path.expanduser("~/blender-5.2.3/blender-5.2.3-linux-x64/blender")


def hashes_path() -> str:
    return os.path.join(F.PICTURES_DIR, F.HASHES)


def read_hashes() -> dict:
    try:
        with open(hashes_path(), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def stale() -> list:
    """Keys whose picture is missing or was made from other settings."""
    h = read_hashes()
    return [k for k in F.builtin_keys()
            if h.get(k) != F.picture_hash(k) or not os.path.isfile(os.path.join(F.PICTURES_DIR, F.picture_name(k)))]


def extra() -> list:
    """Pictures in the folder that no built-in has any more."""
    want = {F.picture_name(k) for k in F.builtin_keys()}
    try:
        return sorted(n for n in os.listdir(F.PICTURES_DIR) if n.endswith(F.PICTURE_EXT) and n not in want)
    except OSError:
        return []


def item(key: str) -> dict:
    kind, _s, ident = key.partition(":")
    e = next(e for e in F.builtin_entries() if e.key == key)
    ch = dict(e.changes)
    if not ch.get("color") and F.picture_colour(key):
        ch["color"] = F.picture_colour(key)
    return {"out": os.path.join(F.PICTURES_DIR, F.picture_name(key)), "base": e.base, "changes": ch}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--blender", default=DEFAULT_BLENDER)
    a = ap.parse_args()
    if a.check:
        bad, more = stale(), extra()
        for k in bad:
            print("old or missing:", k)
        for n in more:
            print("no built-in has it any more:", n)
        return 1 if bad or more else 0
    if a.only:
        keys = [k if ":" in k else f"builtin:{k}" for k in a.only]
    else:
        keys = F.builtin_keys() if a.all else stale()
    unknown = [k for k in keys if k not in F.builtin_keys()]
    if unknown:
        print("unknown:", ", ".join(unknown))
        return 2
    for n in extra():
        os.remove(os.path.join(F.PICTURES_DIR, n))
        print("removed", n)
    if not keys:
        print("every picture is up to date")
        return 0
    os.makedirs(F.PICTURES_DIR, exist_ok=True)
    work = tempfile.mkdtemp(prefix="fr_matpics_")
    job = os.path.join(work, "job.json")
    with open(job, "w", encoding="utf-8") as fh:
        json.dump({"items": [item(k) for k in keys]}, fh)
    runner = os.path.join(ROOT, "fresing_render", "material_picture_runner.py")
    t0 = time.time()
    proc = subprocess.run([a.blender, "--background", "--factory-startup", "--python", runner, "--", job,
                           "fresing_render", ROOT], capture_output=True, text=True)
    lines = [ln for ln in proc.stdout.splitlines() if ln.startswith(("PICTURE", "FAILED"))]
    print("\n".join(lines))
    h = read_hashes()
    made = {ln.split(" ", 2)[2] for ln in lines if ln.startswith("PICTURE")}
    for k in keys:
        if item(k)["out"] in made:
            h[k] = F.picture_hash(k)
    h = {k: h[k] for k in F.builtin_keys() if k in h}
    with open(hashes_path(), "w", encoding="utf-8") as fh:
        json.dump(h, fh, indent=1, sort_keys=True)
        fh.write("\n")
    print(f"{len(made)} of {len(keys)} pictures in {time.time() - t0:.0f} s")
    if len(made) < len(keys):
        print(proc.stdout[-3000:], proc.stderr[-3000:])
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
