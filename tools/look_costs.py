"""The render cost of every look (task 0314): each library material on the picker's swatch (a block, a knob, a disc),
rendered with Cycles on the processor at fixed samples, timed, divided by plain satin paint's time.

    ~/venv/bin/python tools/look_costs.py [--samples 32] [--size 256] [--repeat 2] [--ids a,b] [--write]

Each look is rendered ``--repeat`` times (the fastest counts, after one warm-up render of plain paint). ``--write``
writes ``fresing_render/data/look_costs.json``, which the picker's "slower" badge reads
(``core/look_adjust.SLOWER``). Also prints plain paint with Wear and with the Adjust sliders moved (for the report).
Runs with Blender as a Python module (bpy); generic shapes only."""

from __future__ import annotations

import argparse
import datetime
import json
import os
import platform
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def machine() -> str:
    cpu = platform.processor() or ""
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("model name"):
                    cpu = line.split(":", 1)[1].strip()
                    break
    except OSError:
        pass
    return f"{cpu} ({os.cpu_count()} threads), {platform.system()}, Cycles on the processor"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=32)
    ap.add_argument("--size", type=int, default=256)
    ap.add_argument("--repeat", type=int, default=2)
    ap.add_argument("--ids", default="")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args(argv)
    import bpy
    import addon_utils

    import fresing_render
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    from fresing_render.blender import material_pictures as MPic
    from fresing_render.core import finishes as fin_core
    from fresing_render.core import look_adjust as LA
    from fresing_render.core import material_files as F
    from fresing_render.core import materials_lib as ML

    scene = MPic.build_scene()
    out = os.path.join(tempfile.mkdtemp(prefix="fr_costs_"), "x.png")

    def time_of(mid: str, wear: float = 0.0, adjust: dict | None = None) -> float:
        colour = F.PICTURE_COLOURS.get(mid, F.DEFAULT_PICTURE_COLOUR) if ML.needs_color(mid) else ""
        fin = fin_core.defaults(mid) if fin_core.get(mid) else None
        mat = MPic.plain_material(mid, colour, wear, 0.0, fin, adjust)
        MPic.put(scene, mat)
        return min(MPic.render(scene, out, a.samples, a.size) for _ in range(max(1, a.repeat)))

    time_of("paint_satin")                                   # warm-up
    base = time_of("paint_satin")
    ids = [x for x in a.ids.split(",") if x] or [m for m in ML.MATERIALS if m != "blender_material"]
    looks = {}
    for mid in ids:
        try:
            t = time_of(mid)
        except Exception as exc:  # noqa: BLE001
            print(f"{mid}: not rendered ({exc})")
            continue
        looks[mid] = round(t / base, 2)
        flag = "  SLOWER" if looks[mid] >= LA.SLOWER else ""
        print(f"{mid:32s} {t:6.2f} s  {looks[mid]:5.2f} x{flag}", flush=True)
    looks["paint_satin"] = 1.0
    extra = {"paint_satin + Wear 0.6": round(time_of("paint_satin", 0.6) / base, 2),
             "paint_satin + Adjust (shine 0.3, dirt 0.5, coat 0.5)":
                 round(time_of("paint_satin", 0.0, {"shine": 0.3, "dirt": 0.5, "coat": 0.5}) / base, 2)}
    for k, v in extra.items():
        print(f"{k}: {v} x")
    data = {"measured": datetime.date.today().isoformat(), "machine": machine(), "samples": a.samples,
            "size": a.size, "repeat": a.repeat, "base_seconds": base, "slower_at": LA.SLOWER,
            "extra": extra, "looks": dict(sorted(looks.items()))}
    print(f"plain satin paint: {base} s; {sum(v >= LA.SLOWER for v in looks.values())} of {len(looks)} looks "
          f"at {LA.SLOWER} x or more")
    if a.write:
        with open(LA.COSTS, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=1, sort_keys=False)
            fh.write("\n")
        print("written:", LA.COSTS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
