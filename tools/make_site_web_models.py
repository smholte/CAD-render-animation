"""The moving 3D models of the landing page's "Turn it yourself" (task 0111).

    ~/venv/bin/python tools/make_site_web_models.py test_atc        # the test mill doing tool changes
    ~/venv/bin/python tools/make_site_web_models.py thor            # the Thor robot arm (clones its source once)
    ~/venv/bin/python tools/make_site_web_models.py all [--out <folder>] [--no-site] [--light SOFT|LIVE]

Each model is made the way a user would with the app (Blender as a Python module): the project built, its animation
built, then 5 Scene & Render > Web 3D model with "Animation in the file" and the light chosen below, into
<out>/<id>/<id>.glb + .html. Unless --no-site, tools/build_site.py --web-model then puts it on the page (poster, card,
its own page model/<id>/). Running it again gives the same model (same program, same sheet, same export settings).

Light (task 0111, looked at both on the test mill): "Soft light baked, sun live" – the sky's soft light and the
contact shadows baked, the sun and its shadow live, so a part that moves still casts its shadow where it is. "Live
only" looked flat next to it; "Everything baked" leaves the shadows where they were at the first frame.

A later model (the cable-lay vessel at sea, models of study 0113) is one more entry in MODELS with its make function;
the page needs no change.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
DEFAULT_OUT = os.path.join(ROOT, "dist", "web_models")
LIGHT = "SOFT"
FPS = 25

# the test mill's loop: four double-arm changes. T3 and T1 at pot 5, T2 and T1 at pot 2: every tool ends where it
# started (T1 in the spindle, T2 in pot 2, T3 in pot 5) and the magazine turns 2 -> 5 -> 2, so the loop has no seam
ATC_PROGRAM = """%
(FRESING RENDER LANDING PAGE: FOUR TOOL CHANGES THAT END WHERE THEY STARTED)
(T1 D=10. CR=0. - flat end mill)
(T2 D=8. CR=4. - ball end mill)
(T3 D=6. CR=0. TAPER=118deg - drill)
G21 G90 G54
T3 M6
T1 M6
T2 M6
T1 M6
M30
%
"""
THOR_HIDE = re.compile(r"(Screw|Nut)\d*$")     # Thor's fasteners: left out of the web model (size)
ATC_SPEED = 1.25            # the changer a little quicker than its defaults: the loop is about 10 s


def _app():
    import addon_utils
    import bpy
    sys.path.insert(0, ROOT)
    import fresing_render
    if not hasattr(bpy.types.Scene, "fresing"):
        addon_utils.enable("cycles", default_set=True)
        fresing_render.register()
    return fresing_render


def make_test_atc(work: str, log=print):
    """The invented test mill (tools/make_test_atc.py) with its double-arm changer doing ATC_PROGRAM; returns the
    scene, its animation built."""
    import bpy
    _app()
    from fresing_render.blender import animation, doublearm, gcode, joints, toolchange
    bpy.ops.wm.read_factory_settings(use_empty=True)
    _app()
    gcode._CACHE.clear()
    gcode._INFO.clear()
    sc = bpy.context.scene
    sc.fresing.out_folder = work
    step = os.path.join(ROOT, "fresing_render", "data", "test_atc.step")
    if bpy.ops.fresing.import_step(filepath=step, quality="normal") != {"FINISHED"}:
        raise SystemExit("the test mill did not import")
    path = os.path.join(work, "site_tool_change.ngc")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(ATC_PROGRAM)
    a = sc.fresing.animations.add()
    a.name, a.tail, a.fps = "Tool change", 0.0, str(FPS)
    b = a.blocks.add()
    b.kind = "GCODE"
    b.gcode_file = path
    b.gcode_tc_time = 0.0
    b.gcode_changer_speed = ATC_SPEED
    gcode.step_changed(sc, b)
    doublearm.set_up_test_model(sc, b)
    bad = [t for ok, t in doublearm.check(sc) if not ok]
    if bad:
        raise SystemExit("the changer is not set up: " + "; ".join(bad))
    _st, values, _n = toolchange.stations(sc, gcode.Machine(sc))
    joints.set_value(toolchange.carousel(sc), values[2])     # starts where the loop ends: pot 2 at the arm
    r = animation.bake(sc, a)
    if r["warnings"]:
        raise SystemExit("; ".join(r["warnings"]))
    log(f"test_atc: {sc.frame_end - sc.frame_start + 1} frames ({(sc.frame_end - sc.frame_start) / FPS:.1f} s loop)")
    return sc


def make_thor(work: str, log=print, cache: str = ""):
    """Thor from task 0112's project (tools/make_site_projects.py): its sheet's joints, poses and loop, clash-checked."""
    import bpy
    import make_site_projects as msp
    _app()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    _app()
    res = msp.build_project("thor", work, quality="draft", check=True, cache=cache, log=log)
    rows = res.get("clash_rows", 0)
    if rows:
        raise SystemExit(f"Thor's animation has {rows} clash rows")
    sc = bpy.context.scene
    from fresing_render.blender import build, logic
    hidden = 0
    for ob in list(build.iter_parts(sc)):     # as a user hides them in 2 Structure: 372 threaded screws and nuts are
        if THOR_HIDE.match(ob.get(build.PROP_NAME) or ""):   # 619,000 of 1,021,000 triangles, 12 MB -> 4.8 MB
            logic.set_hidden(ob, True)
            hidden += 1
    log(f"thor: {hidden} screws and nuts hidden for the web")
    return sc


MODELS = {
    "test_atc": {"make": make_test_atc, "order": 1,
                 "caption": "An invented test mill: the double-arm changer swaps tools from its 12-pot magazine, "
                            "four changes in a loop"},
    "thor": {"make": make_thor, "order": 2,
             "caption": "The open-source Thor robot arm: six joints and its gripper at work, in a loop"},
}


def export(sc, path: str, light: str = LIGHT, log=print) -> dict:
    from fresing_render.blender import web3d
    sc.frame_set(sc.frame_start)
    t0 = time.time()
    out = web3d.export(sc, path, animation=True, light=light, page=True)
    log(f"exported in {time.time() - t0:.0f} s: {out['text']}")
    if not out.get("animated"):
        raise SystemExit("the export has no animation")
    return out


def make(model: str, out: str = DEFAULT_OUT, site: bool = True, light: str = LIGHT, cache: str = "",
         log=print) -> dict:
    """One model: project, export into <out>/<model>/, and (``site``) onto the landing page."""
    if model not in MODELS:
        raise SystemExit(f"unknown model '{model}': use {', '.join(MODELS)} or all")
    spec = MODELS[model]
    folder = os.path.join(out, model)
    work = os.path.join(out, "_work_" + model)
    os.makedirs(folder, exist_ok=True)
    os.makedirs(work, exist_ok=True)
    for f in os.listdir(folder):
        os.remove(os.path.join(folder, f))
    kw = {"cache": cache} if model == "thor" else {}
    sc = spec["make"](work, log=log, **kw)
    res = export(sc, os.path.join(folder, model + ".glb"), light, log)
    if site:
        import build_site
        build_site.web_model(folder, model, spec["caption"], order=spec["order"])
        log(f"{model}: on the page (site/media)")
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Make the moving 3D models of 'Turn it yourself'")
    ap.add_argument("models", nargs="+", help=f"{', '.join(MODELS)} or all")
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--no-site", action="store_true", help="only export, do not put it on the page")
    ap.add_argument("--light", default=LIGHT, choices=("LIVE", "SOFT"))
    ap.add_argument("--cache", default="", help="where the sources are cloned (tools/make_site_projects.py)")
    a = ap.parse_args(argv)
    names = list(MODELS) if a.models == ["all"] else a.models
    for m in names:
        make(m, a.out, site=not a.no_site, light=a.light, cache=a.cache)
    return 0


if __name__ == "__main__":
    sys.exit(main())
