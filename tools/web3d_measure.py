"""Measure one web 3D export (task 0105): file size, export time, peak memory, compressed or not.

    ~/venv/bin/python tools/web3d_measure.py <model.step> [--quality normal] [--size 1024] [--compress auto|on|off]
        [--out DIR] [--page]

Runs in a process of its own (Blender as a Python module) so the peak memory belongs to this one export: it prints
one line of JSON with the size, the time, the peak memory of the whole process and the memory before the export
(after the import). Big models: the Heavy machine (``fresing_render/pccheck/heavy_scene.py out.step 600 3000``) and
the demo vessel (``python -m fresing_render.demo_model.make``).
"""

from __future__ import annotations

import argparse
import json
import os
import resource
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))


def rss_mb() -> float:
    with open("/proc/self/status") as fh:
        for line in fh:
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1024
    return 0.0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("step")
    ap.add_argument("--quality", default="normal")
    ap.add_argument("--size", type=int, default=1024)
    ap.add_argument("--compress", choices=("auto", "on", "off"), default="auto")
    ap.add_argument("--out", default="/tmp/web3d_measure")
    ap.add_argument("--page", action="store_true", help="also write the viewer page")
    a = ap.parse_args(argv)

    import bpy  # noqa: I001 (bpy first: it brings addon_utils)
    import addon_utils

    import fresing_render
    from fresing_render.blender import web3d
    from fresing_render.core import web3d as core
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    t0 = time.perf_counter()
    assert bpy.ops.fresing.import_step(filepath=os.path.abspath(a.step), quality=a.quality) == {"FINISHED"}
    t_import = time.perf_counter() - t0
    before = rss_mb()
    peak_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    os.makedirs(a.out, exist_ok=True)
    name = f"{os.path.splitext(os.path.basename(a.step))[0]}_{a.quality}_{a.size}_{a.compress}.glb"
    comp = {"auto": None, "on": True, "off": False}[a.compress]
    out = web3d.Job(bpy.context.scene, os.path.join(a.out, name), size=a.size, page=a.page, compress=comp).run()
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    with open(out["path"], "rb") as fh:
        data = fh.read()
    info = core.summary(data)
    print(json.dumps({"model": os.path.basename(a.step), "quality": a.quality, "size_px": a.size,
                      "compressed": info["compressed"], "file_mb": round(len(data) / 1e6, 2),
                      "texture_mb": round(out["texture_bytes"] / 1e6, 2), "export_s": round(out["seconds"], 1),
                      "import_s": round(t_import, 1), "rss_before_mb": round(before), "peak_before_mb": round(peak_before),
                      "peak_mb": round(peak), "triangles": info["triangles"],
                      "unique_triangles": info["unique_triangles"], "textures": info["textures"],
                      "problems": core.problems(data)[:3], "path": out["path"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
