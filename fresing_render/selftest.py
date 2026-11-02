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

    def log(msg: str) -> None:
        print(msg)
        lines.append(msg)

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
            return f"{info['size'][0]}x{info['size'][1]} in {info['seconds']} s on {info['device']} -> {info['path']}"

        check("Render HD on graphics card", lambda: _render(True, "hd", "preview"))
        check("Small render on processor (for comparison)", lambda: _render(False, "preview", "draft"))

    log("RESULT: " + ("ALL OK" if ok else "PROBLEMS FOUND (see above)"))
    report_path = report_path or os.path.join(_desktop(), "Fresing Render self-test.txt")
    try:
        with open(report_path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        print("Report written to", report_path)
    except OSError as exc:
        print("Could not write report:", exc)
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
