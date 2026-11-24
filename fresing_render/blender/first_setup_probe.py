"""Step 3 of the first-start set-up (task 0276), run as a script in a background Blender:

    blender --background --python first_setup_probe.py -- <result.json> [line ids, comma separated]

It switches the extension on (as the PC check's launcher does) and runs the PC check's Quick lines that say what the
PC can do (``core/first_setup.PROBE_LINES``: test models there, the graphics card, which card draws and renders, the
test crane's import and an HD picture on the card) – no video, no report on the Desktop, no browser, and a history
folder of its own, so the PC check's own runs keep comparing with each other. The result file:

    {"pc": {...}, "seconds": 18.2, "results": [{"id", "status", "note", "reason", "metrics"}], "error": ""}
"""

import importlib
import json
import os
import shutil
import sys
import tempfile
import traceback


def _args() -> tuple:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = argv[0] if argv else os.path.join(tempfile.gettempdir(), "fresing_setup_probe.json")
    lines = argv[1] if len(argv) > 1 else ""
    return out, lines


def _write(path: str, data: dict) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1, default=str)
    os.replace(tmp, path)


def main() -> None:
    out, lines = _args()
    data = {"pc": {}, "seconds": 0.0, "results": [], "error": ""}
    work = tempfile.mkdtemp(prefix="fresing_setup_probe_")
    try:
        import addon_utils
        name = next((m.__name__ for m in addon_utils.modules()
                     if m.__name__ == "fresing_render" or m.__name__.endswith(".fresing_render")), "")
        if not name:
            raise RuntimeError("Fresing Render is not installed in this Blender: run Install.bat again")
        addon_utils.enable(name, default_set=True)
        fs = importlib.import_module(name + ".core.first_setup")
        runner = importlib.import_module(name + ".pccheck.runner")
        ids = lines or os.environ.get(fs.PROBE_ENV, "") or ",".join(fs.PROBE_LINES)
        os.environ[runner.ONLY_ENV] = ids
        os.environ[runner.NO_OPEN_ENV] = "1"
        os.environ["FRESING_PCCHECK_DIR"] = os.path.join(work, "history")
        run = runner.run("quick", desktop=work, open_report=False)
        data["pc"] = {k: v for k, v in (run.pc or {}).items() if k in ("cpu", "cores", "ram_gb", "gpu", "draws")}
        data["seconds"] = round(run.seconds, 1)
        data["results"] = [{"id": r.id, "status": r.status, "note": r.note, "reason": r.reason,
                            "metrics": {k: list(v) for k, v in r.metrics.items()}} for r in run.results]
    except Exception as exc:  # noqa: BLE001 - the set-up says it in plain words
        traceback.print_exc()
        data["error"] = str(exc) or type(exc).__name__
    finally:
        shutil.rmtree(work, ignore_errors=True)
    _write(out, data)


if __name__ == "__main__":
    main()
