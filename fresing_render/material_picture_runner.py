"""Makes material pictures in a background Blender (task 0273; see blender/material_pictures.py).

Started as:
    blender --background --factory-startup --python material_picture_runner.py -- <job.json> <package name> [<folder>]
or, with Blender as a Python module (tests):
    python material_picture_runner.py <job.json> <package name> [<folder>]

``<folder>``: the folder that holds the package (``tools/material_pictures.py`` runs it from the repository).
job.json = {"items": [{"out", "base", "changes"} | {"out", "blend", "material"}, …]}; each finished picture is
reported on a line "PICTURE <seconds> <out>", a failed one "FAILED <out>: <reason>"; status.json next to the job
says how far it got."""

import importlib
import json
import os
import sys
import traceback


def _args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    return argv[0], argv[1], (argv[2] if len(argv) > 2 else "")


def _status(job: str, data: dict) -> None:
    path = os.path.join(os.path.dirname(os.path.abspath(job)), "status.json")
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        os.replace(tmp, path)
    except OSError:
        pass


def main() -> int:
    job, package, folder = _args()
    if folder:
        sys.path.insert(0, folder)
    import bpy

    import addon_utils
    if "cycles" not in bpy.context.preferences.addons:
        addon_utils.enable("cycles", default_set=False)
    pkg = importlib.import_module(package)
    if not hasattr(bpy.types.Scene, "fresing"):
        pkg.register()
    pictures = importlib.import_module(package + ".blender.material_pictures")
    with open(job, encoding="utf-8") as fh:
        items = json.load(fh)["items"]
    done, failed = [], []
    for item in items:
        try:
            sec = pictures.make(item)
            done.append(item["out"])
            print(f"PICTURE {sec} {item['out']}", flush=True)
        except Exception as exc:  # noqa: BLE001 - one bad material does not stop the others
            traceback.print_exc()
            failed.append({"out": item.get("out", ""), "why": " ".join(str(exc).split())[:200]})
            print(f"FAILED {item.get('out')}: {exc}", flush=True)
        _status(job, {"done": done, "failed": failed, "total": len(items)})
    _status(job, {"done": done, "failed": failed, "total": len(items), "finished": True})
    return 0 if not failed else 1


if __name__ == "__main__":
    code = main()
    if "--" in sys.argv:            # inside Blender: quit with the code
        sys.exit(code)
    sys.exit(code)
