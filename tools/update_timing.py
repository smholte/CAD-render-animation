"""Where a model update's time goes (task 0324), in Blender as a Python module (``~/venv/bin/python``) or in the real
app under a virtual screen (each step in its own timer call, so the app's event loop runs between them as it does
when the owner clicks: Blender clears its queue of notices there, and a model update's clean-up depends on it).

    ~/venv/bin/python tools/update_timing.py <revision A .step> <revision B .step> <work folder> [--quality normal]
        [--joints <A's .joints.json>] [--fresh] [--full] [--profile <file>]
    xvfb-run -a <blender> --factory-startup --python tools/update_timing.py -- <same arguments>

Imports revision A (a fresh read into a cache of its own under the work folder), makes the joints of the stress
model's sheet when given, then updates to revision B with the import button's own call and prints, as JSON: the
reader's wall time and its own stages (from B's ``tree.json``), the build's meshes / objects, and every stage of the
update (``reimport``'s clock). ``--fresh`` also times a fresh import of B for comparison; ``--full`` sets
FRESING_UPDATE_FULL=1 (today's full path: every part read and built again).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, ROOT)


def main(argv=None) -> int:
    if argv is None and "--" in sys.argv:
        argv = sys.argv[sys.argv.index("--") + 1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("work")
    ap.add_argument("--quality", default="normal")
    ap.add_argument("--joints", default="")
    ap.add_argument("--fresh", action="store_true")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--profile", default="", help="write a cProfile of the update's Blender part to this file")
    a = ap.parse_args(argv)
    if a.full:
        os.environ["FRESING_UPDATE_FULL"] = "1"
    import bpy
    import addon_utils

    import fresing_render
    from fresing_render.blender import build, ops_import
    from fresing_render.importer import runner
    real_app = not bpy.app.background
    if real_app:                                 # the reader runs with this Python (OpenCascade is in the venv)
        exe = os.path.join(os.path.expanduser("~"), "venv", "bin", "python")
        runner.python_executable = lambda: exe
    else:
        bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    out: dict = {}
    cache = os.path.join(a.work, "cache")
    ops_import.use_cache_root(cache)
    scene = bpy.context.scene
    scene.fresing.out_folder = a.work

    def tree_stats(root) -> dict:
        with open(os.path.join(root["fr_cache"], "tree.json"), encoding="utf-8") as fh:
            return json.load(fh)["stats"]

    steps = []

    def step(fn):
        steps.append(fn)
        return fn

    def wait(res):
        """In the real app the import runs modal (the reader in the background, the event loop going on, as after a
        click): wait for it to finish."""
        if res == {"RUNNING_MODAL"}:
            while ops_import._ACTIVE_JOB is not None and not ops_import._ACTIVE_JOB.done:
                yield
            yield                                   # the operator's last timer event builds the model
            yield
            return
        assert res == {"FINISHED"}, (res, bpy.context.scene.fresing.last_message)

    @step
    def import_a():
        t0 = time.time()
        yield from wait(bpy.ops.fresing.import_step(filepath=a.a, quality=a.quality))
        out["import A"] = round(time.time() - t0, 1)
        root = build.model_roots(scene)[0]
        out["import A reader"] = tree_stats(root)
        out["import A build"] = dict(build.LAST_TIMES)

    @step
    def make_joints():
        yield
        if a.joints:
            from fresing_render.pccheck import stress
            with open(a.joints, encoding="utf-8") as fh:
                out["joints"] = stress.make_joints(scene, json.load(fh))

    @step
    def update():
        root = build.model_roots(scene)[0]
        yield from _update(root)

    def _update(root):
        if a.profile:
            import cProfile
            from fresing_render.blender import reimport
            orig = reimport.update_model

            def profiled(*args, **kw):
                prof = cProfile.Profile()
                try:
                    return prof.runcall(orig, *args, **kw)
                finally:
                    prof.dump_stats(a.profile)
            reimport.update_model = profiled
        t0 = time.time()
        yield from wait(bpy.ops.fresing.import_step(filepath=a.b, quality=a.quality, update_root=root.name))
        out["update"] = round(time.time() - t0, 1)
        root = build.model_roots(scene)[0]
        assert root.get("fr_update_stats"), scene.fresing.last_message
        stages = json.loads(root.get("fr_update_stats", "{}"))
        out["update stages"] = stages
        out["update build"] = dict(build.LAST_TIMES)
        out["update reader"] = tree_stats(root)
        out["update reader wall"] = round(out["update"] - stages.get("total", 0.0), 1)
        out["report"] = scene.fresing.report_title
        out["parts"] = sum(1 for _ in build.iter_parts(scene))
        out["joints after"] = len(scene.fresing.joints)

    @step
    def fresh():
        yield
        if not a.fresh:
            return
        bpy.ops.wm.read_homefile(use_empty=True)
        ops_import.use_cache_root(os.path.join(a.work, "cache_fresh"))
        bpy.context.scene.fresing.out_folder = a.work
        t0 = time.time()
        yield from wait(bpy.ops.fresing.import_step(filepath=a.b, quality=a.quality))
        out["fresh import B"] = round(time.time() - t0, 1)
        out["fresh import B reader"] = tree_stats(build.model_roots(bpy.context.scene)[0])
        out["fresh import B build"] = dict(build.LAST_TIMES)

    def report():
        out["real app"] = real_app
        print("UPDATE-TIMING " + json.dumps(out), flush=True)

    if not real_app:
        for fn in steps:
            for _ in fn():
                pass
        report()
        return 0
    todo = [fn() for fn in steps]

    def tick():
        try:
            while todo:
                try:
                    next(todo[0])
                    return 0.25                # the event loop runs (and clears its notices) in between
                except StopIteration:
                    todo.pop(0)
            report()
            os._exit(0)
        except Exception:
            import traceback
            traceback.print_exc()
            os._exit(1)
    bpy.app.timers.register(tick, first_interval=1.0)
    return 0


if __name__ == "__main__":
    code = main()
    import bpy
    if bpy.app.background:
        sys.exit(code)
