"""Background renderer for the render queue (see blender/queue.py).

Started by the app as:
    blender --background --python queue_runner.py -- <queue folder> <package name>
or, with Blender as a Python module (tests):
    python queue_runner.py <queue folder> <package name>
"""

import importlib
import json
import os
import sys
import time
import traceback


def _args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    return argv[0], argv[1]


def _keep_awake() -> None:
    """Windows: no sleep while the queue renders (released automatically when the process ends)."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
    except Exception:
        pass


def main() -> int:
    qdir, package = _args()
    _keep_awake()
    import bpy

    import addon_utils
    if "cycles" not in bpy.context.preferences.addons:
        addon_utils.enable("cycles", default_set=False)
    pkg = importlib.import_module(package)
    if not hasattr(bpy.types.Scene, "fresing"):
        pkg.register()
    queue = importlib.import_module(package + ".blender.queue")

    with open(os.path.join(qdir, "queue.json"), encoding="utf-8") as fh:
        q = json.load(fh)
    status = {"pid": os.getpid(), "running": True, "started": time.time(), "jobs": {}}
    for job in q["jobs"]:
        status["jobs"][job["id"]] = {"status": "WAITING", "progress": 0.0, "message": "Waiting", "output": ""}

    def write():
        tmp = os.path.join(qdir, "status.json.tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(status, fh, indent=1)
        for _ in range(5):
            try:
                os.replace(tmp, os.path.join(qdir, "status.json"))
                return
            except PermissionError:          # Windows: the app is reading it right now
                time.sleep(0.2)

    def should_stop() -> bool:
        return os.path.exists(os.path.join(qdir, "stop"))

    write()
    for job in q["jobs"]:
        st = status["jobs"][job["id"]]
        if should_stop():
            st.update(status="STOPPED", message="Stopped")
            continue
        st.update(status="RUNNING", message="Opening project", progress=0.0)
        write()
        last = [0.0]

        def progress(pct, msg, st=st):
            st["progress"] = round(float(pct), 1)
            st["message"] = msg
            print(f"[{job['label']}] {pct:.0f}% {msg}", flush=True)
            if time.time() - last[0] > 1.0:
                last[0] = time.time()
                write()

        try:
            # every job starts from the saved project, so jobs do not affect each other
            bpy.ops.wm.open_mainfile(filepath=q["blend"], load_ui=False)
            out = queue.run_job(bpy.context.scene, job, progress, should_stop)
            st.update(status="DONE", progress=100.0, message="Saved " + os.path.basename(out), output=out)
        except queue.Stopped:
            st.update(status="STOPPED", message="Stopped (start the queue again to continue)")
        except Exception as exc:
            traceback.print_exc()
            st.update(status="FAILED", message=str(exc) or exc.__class__.__name__)
        write()
    status["running"] = False
    status["finished"] = time.time()
    write()
    try:                                     # the copy of the project is not needed any more
        bpy.ops.wm.read_homefile(use_empty=True)
        os.remove(q["blend"])
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    code = main()
    if "--" not in sys.argv:            # module mode: exit with the code; Blender exits by itself
        sys.exit(code)
