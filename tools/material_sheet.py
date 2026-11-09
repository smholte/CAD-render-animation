"""Render the material sheet (task 0046): every library material on a block, a disc and a shaft.

    ~/venv/bin/python tools/material_sheet.py --out dist/sheet [--engine CYCLES|EEVEE|BOTH] [--width 1200]
        [--samples 32] [--ids steel_ground,cast_iron] [--columns 6] [--wear 0.6]

Runs with Blender as a Python module (bpy). Writes sheet_cycles.png / sheet_eevee.png and prints the times.
Generic shapes only: the pictures may go in a report."""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="dist/sheet")
    ap.add_argument("--engine", default="CYCLES", choices=("CYCLES", "EEVEE", "BOTH"))
    ap.add_argument("--width", type=int, default=1200)
    ap.add_argument("--samples", type=int, default=32)
    ap.add_argument("--ids", default="")
    ap.add_argument("--columns", type=int, default=6)
    ap.add_argument("--wear", type=float, default=0.0)
    a = ap.parse_args(argv)
    import bpy
    import addon_utils
    import fresing_render
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    from fresing_render.blender import material_sheet
    ids = [x for x in a.ids.split(",") if x] or None
    engines = ("CYCLES", "EEVEE") if a.engine == "BOTH" else (a.engine,)
    for eng in engines:
        scene = material_sheet.build(ids, a.columns, a.wear)
        suffix = f"_wear{a.wear:g}" if a.wear else ""
        path = os.path.join(os.path.abspath(a.out), f"sheet_{eng.lower()}{suffix}.png")
        info = material_sheet.render(scene, path, eng, a.samples, a.width)
        print(f"{eng}: {path} in {info['seconds']} s ({info['device']}, {info['size'][0]} x {info['size'][1]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
