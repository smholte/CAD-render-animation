"""Self-test: checks the installation on this PC and writes a short report.

Started from the "Fresing Render - Self test" shortcut, which runs Blender
in the background. The report is saved on the Desktop; send it to
whoever maintains the app.
"""

from __future__ import annotations

import os
import platform
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
TEST_STEP = os.path.join(HERE, "data", "test_machine.step")


def _desktop() -> str:
    # The installer passes the real Desktop (OneDrive may redirect it) after "--".
    if "--" in sys.argv:
        extra = sys.argv[sys.argv.index("--") + 1:]
        if extra and os.path.isdir(extra[0]):
            return extra[0]
    for cand in (os.path.join(os.path.expanduser("~"), "Desktop"),
                 os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop"),
                 os.path.expanduser("~")):
        if os.path.isdir(cand):
            return cand
    return os.getcwd()


def main(report_path: str | None = None) -> bool:
    import bpy

    from . import __version__
    from .blender import build, render

    lines: list[str] = []
    ok = True
    report_path = report_path or os.path.join(_desktop(), "Fresing Render self-test.txt")
    try:
        report = open(report_path, "w", encoding="utf-8")
    except OSError as exc:
        print("Could not write report:", exc)
        report = None

    def log(msg: str) -> None:
        print(msg)
        lines.append(msg)
        if report is not None:               # written as we go: a crash still leaves a report
            report.write(msg + "\n")
            report.flush()

    def check(name: str, fn):
        nonlocal ok
        t0 = time.time()
        try:
            result = fn()
            log(f"[ OK ] {name} ({time.time() - t0:.1f} s){': ' + str(result) if result else ''}")
            return True
        except Exception as exc:  # report everything, keep going
            ok = False
            log(f"[FAIL] {name}: {exc}")
            log(traceback.format_exc())
            return False

    log(f"Fresing Render {__version__} self-test, {time.strftime('%Y-%m-%d %H:%M')}")
    log(f"Blender {bpy.app.version_string}, Python {sys.version.split()[0]}, {platform.platform()}")
    log(f"Computer: {platform.node()}, CPU: {platform.processor() or 'unknown'}, cores: {os.cpu_count()}")

    def _occ():
        import OCP  # noqa: F401
        from OCP.STEPCAFControl import STEPCAFControl_Reader  # noqa: F401
        return "OpenCascade loaded"

    check("STEP reader (OpenCascade)", _occ)

    def _fast_import():
        """The reader with two meshing helpers gives the same model as on one core."""
        import json as _json
        import tempfile
        from .importer import runner
        stats = {}
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            for mode in ("0", "2"):
                saved = os.environ.get("FRESING_IMPORT_WORKERS")
                os.environ["FRESING_IMPORT_WORKERS"] = mode
                try:
                    job = runner.ImportJob(TEST_STEP, "normal", os.path.join(tmp, mode))
                    job.start()
                finally:
                    if saved is None:
                        os.environ.pop("FRESING_IMPORT_WORKERS", None)
                    else:
                        os.environ["FRESING_IMPORT_WORKERS"] = saved
                end = time.time() + 180
                while not job.poll():
                    if time.time() > end:
                        job.cancel()
                        raise RuntimeError("the reader did not finish within 3 minutes")
                    time.sleep(0.1)
                if job.error:
                    raise RuntimeError(job.error)
                with open(os.path.join(job.cache_dir, "tree.json"), encoding="utf-8") as fh:
                    stats[mode] = _json.load(fh)["stats"]
        if stats["2"].get("mesh_helpers") != 2:
            raise RuntimeError(f"the meshing helpers did not start ({stats['2'].get('mesh_helpers')} of 2)")
        if stats["2"]["triangles_unique"] != stats["0"]["triangles_unique"]:
            raise RuntimeError("the helpers gave a different mesh")
        n = runner.step_reader.worker_count()
        if n == 0:
            return f"helpers work; this PC has {os.cpu_count()} cores, so big models are meshed on one"
        return f"big models are meshed on {n} cores at once ({os.cpu_count()} in this PC)"

    check("Fast import (all cores)", _fast_import)

    def _cad_materials():
        """Material and appearance names from a STEP file, and the part-type library."""
        import json as _json
        import tempfile
        from .core import rules as R
        from .importer import runner
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            job = runner.ImportJob(os.path.join(HERE, "data", "test_materials.step"), "draft", tmp)
            job.start()
            end = time.time() + 120
            while not job.poll():
                if time.time() > end:
                    job.cancel()
                    raise RuntimeError("the reader did not finish within 2 minutes")
                time.sleep(0.1)
            if job.error:
                raise RuntimeError(job.error)
            with open(os.path.join(job.cache_dir, "tree.json"), encoding="utf-8") as fh:
                nodes = _json.load(fh)["nodes"]
        names = {n["name"]: n.get("material", "") for n in nodes if n["kind"] == "part"}
        if names.get("PLATE") != "Aluminum - Satin" or names.get("SEAL RING") != "Rubber - Soft":
            raise RuntimeError(f"material names not read: {names}")
        group = R.classify_one(R.facts_for("_MGPM32-75Z_ROD"), R.default_rules())[0]
        if group != "Chrome rods & linear shafts":
            raise RuntimeError(f"part-type library gave {group!r}")
        return "names read; part-type library works"

    check("CAD material names and part types", _cad_materials)

    def _template():
        import subprocess
        exe = bpy.app.binary_path
        if not exe or not os.path.basename(exe).lower().startswith("blender"):
            return "skipped (not started from Blender)"
        code = ("import bpy\n"
                "if not any(k.endswith('fresing_render') for k in bpy.context.preferences.addons.keys()):\n"
                "    raise SystemError('not enabled')\n")
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        r = subprocess.run([exe, "--background", "--app-template", "fresing_render", "--python-exit-code", "3",
                            "--python-expr", code], capture_output=True, text=True, timeout=300, creationflags=flags)
        if r.returncode != 0:
            raise RuntimeError("the app opens without the Fresing panel: run Install.bat again "
                               f"(exit code {r.returncode})")
        return "the Fresing panel loads in the app"

    check("App start (Desktop shortcut)", _template)
    check("Graphics card", lambda: render.setup_gpu())

    def _import():
        bpy.ops.wm.read_homefile(use_empty=True)
        from .blender import prefs as fr_prefs
        p = fr_prefs.get()
        saved_template = p.default_template if p else ""
        if p:
            p.default_template = ""      # the test checks the built-in sorting
        try:
            return _import_inner()
        finally:
            if p:
                p.default_template = saved_template

    def _import_inner():
        scene = bpy.context.scene
        res = bpy.ops.fresing.import_step(filepath=TEST_STEP, quality="normal")
        if res != {"FINISHED"}:
            raise RuntimeError(f"import returned {res}: {scene.fresing.last_message}")
        parts = list(build.iter_parts(scene))
        if len(parts) != 11:
            raise RuntimeError(f"expected 11 parts, got {len(parts)}")
        groups = {g.name: g.count for g in scene.fresing.groups}
        if groups.get("Fasteners galvanized") != 4 or groups.get("Fasteners black") != 4:
            raise RuntimeError(f"fastener sorting wrong: {groups}")
        return f"{len(parts)} parts, groups {groups}"

    imported = check("Import and sort test model", _import)

    def _motion():
        import math
        from mathutils import Vector
        from .blender import animation, joints
        scene = bpy.context.scene
        cover = next(o for o in scene.objects if o.get(build.PROP_NAME) == "COVER.ASM")
        plate = next(o for o in scene.objects if o.get(build.PROP_NAME) == "COVER.PLATE")
        corner = Vector((0.4, 0.3, 0.0))          # far corner of the 400 x 300 mm plate
        before = plate.matrix_world @ corner
        j = joints.create(scene, "ROTATE", [cover], plate.matrix_world.translation, Vector((0, 0, 1)))
        a = scene.fresing.animations.add()
        a.name = "Self-test"
        b = a.blocks.add()
        b.kind, b.joint, b.duration, b.use_from, b.to_angle = "JOINT", j.name, 1.0, False, math.radians(90)
        info = animation.bake(scene, a)
        scene.frame_set(info["frames"])
        moved = (plate.matrix_world @ corner - before).length
        animation.clear_keys(scene)
        joints.remove(scene, j)
        bpy.context.view_layer.update()
        back = (plate.matrix_world @ corner - before).length
        if moved < 0.01 or back > 1e-4:
            raise RuntimeError(f"joint did not move as expected (moved {moved:.3f} m, back {back:.5f} m)")
        return f"{info['frames']} frames, cover turned and returned"

    def _video():
        import tempfile
        import numpy as np
        from .blender import queue
        folder = tempfile.mkdtemp(prefix="fresing_video_")
        for i in range(3):
            img = bpy.data.images.new(f"fr_test_{i}", 64, 36, alpha=True)
            px = np.zeros((36, 64, 4), np.float32)
            px[..., i] = 1.0
            px[..., 3] = 1.0
            img.pixels.foreach_set(px.ravel())
            img.filepath_raw = os.path.join(folder, f"frame_{i + 1:04d}.png")
            img.file_format = "PNG"
            img.save()
            bpy.data.images.remove(img)
        out = queue.encode_mp4(folder, os.path.join(folder, "test.mp4"), 64, 36, 25)
        size = os.path.getsize(out)
        if size < 200:
            raise RuntimeError("video file is empty")
        return f"{size} bytes"

    def _queue():
        import tempfile
        from .blender import queue, states
        scene = bpy.context.scene
        s = scene.fresing
        if scene.camera is None:
            raise RuntimeError("no camera")
        folder = tempfile.mkdtemp(prefix="fresing_queue_")
        s.out_folder = folder
        s.out_format, s.out_resolution, s.quality = "presentation", "preview", "draft"
        states.save_shot(scene, "Self-test")
        queue.add_job(scene, "STILL", shot="Self-test", quality="draft")
        qdir = queue.start(bpy.context)
        t0 = time.time()
        while queue.is_running(scene) and time.time() - t0 < 300:
            time.sleep(1.0)
        queue.sync(scene)
        job = s.queue[-1]
        if job.status != "DONE":
            raise RuntimeError(f"{job.status}: {job.message} | log: {queue.log_tail(qdir, 12)}")
        return f"{time.time() - t0:.0f} s -> {job.output}"

    def _time_test():
        """The Time test button of 6 Animation: two frames of an animation through the queue."""
        import math
        import tempfile
        from mathutils import Vector
        from .blender import joints, queue
        scene = bpy.context.scene
        s = scene.fresing
        cover = next(o for o in scene.objects if o.get(build.PROP_NAME) == "COVER.ASM")
        plate = next(o for o in scene.objects if o.get(build.PROP_NAME) == "COVER.PLATE")
        j = joints.create(scene, "ROTATE", [cover], plate.matrix_world.translation, Vector((0, 0, 1)),
                          name="Self-test hinge")
        a = s.animations.add()
        a.name = "Self-test time"
        a.tail = 0.0
        a.quality = "draft"
        a.out_resolution = "preview"
        b = a.blocks.add()
        b.kind, b.joint, b.duration, b.use_from, b.to_angle = "JOINT", j.name, 0.4, False, math.radians(30)
        s.out_folder = tempfile.mkdtemp(prefix="fresing_timetest_")
        queue.add_job(scene, "TEST", animation=a.name, quality="draft")
        qdir = queue.start(bpy.context)
        t0 = time.time()
        while queue.is_running(scene) and time.time() - t0 < 300:
            time.sleep(1.0)
        queue.sync(scene)
        job = s.queue[-1]
        if job.status != "DONE" or "s per frame" not in job.message:
            raise RuntimeError(f"{job.status}: {job.message} | log: {queue.log_tail(qdir, 12)}")
        return job.message

    if imported:
        def _render(gpu: bool, resolution: str, quality: str):
            scene = bpy.context.scene
            s = scene.fresing
            if gpu and not render.setup_gpu().startswith("GPU"):
                raise RuntimeError("no supported graphics card found; renders will use the processor (slow). "
                                   "Update the NVIDIA driver (535 or newer) and run the self-test again")
            s.use_gpu = gpu
            s.out_format = "presentation"
            s.out_resolution = resolution
            s.out_folder = os.path.join(_desktop(), "Fresing Render self-test")
            s.background = "COLOR"
            info = render.render_still(scene, s, quality)
            denoise = "graphics card" if getattr(scene.cycles, "denoising_use_gpu", False) else "processor"
            return (f"{info['size'][0]}x{info['size'][1]} in {info['seconds']} s on {info['device']}, "
                    f"noise removal on the {denoise} -> {info['path']}")

        check("Render HD on graphics card", lambda: _render(True, "hd", "preview"))
        check("Small render on processor (for comparison)", lambda: _render(False, "preview", "draft"))
        check("Joints and animation", _motion)
        check("Video encoder (MP4)", _video)
        check("Render queue (second Blender in the background)", _queue)
        check("Animation time test (queue)", _time_test)

    log("RESULT: " + ("ALL OK" if ok else "PROBLEMS FOUND (see above)"))
    if report is not None:
        report.close()
        print("Report written to", report_path)
    return ok


def run_installed() -> None:
    """Entry point for the installer's shortcut: find the installed extension and run main()."""
    import addon_utils
    import bpy  # noqa: F401
    for mod in addon_utils.modules():
        if mod.__name__.endswith("fresing_render"):
            addon_utils.enable(mod.__name__, default_set=True)
            st = sys.modules.get(mod.__name__ + ".selftest")
            if st is None:
                import importlib
                st = importlib.import_module(mod.__name__ + ".selftest")
            st.main()
            return
    print("Fresing Render is not installed in this Blender")
