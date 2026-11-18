"""Make the built-in crane classes of the Lifting lane (task 0191) into fresing_render/data/lifting/<class>/.

    python tools/make_lifting_cranes.py                    every class: <class>.step + <class>.json
    python tools/make_lifting_cranes.py --only AT-40,CC-100
    python tools/make_lifting_cranes.py --json-only        only the equipment files (keeps the STEP files)
    python tools/make_lifting_cranes.py --pictures         <class>.png: the class imported with the app, rigged, posed
                                                           "Working", rendered small (Cycles; Blender as a module)
    python tools/make_lifting_cranes.py --check            the shipped JSON files equal a fresh make (no STEP, no
                                                           pictures); exit 1 when one differs

The makers are ``fresing_render/lifting_model/`` (mobile.py, crawler.py, knuckle.py on classes.py, charts.py,
equipment.py); everything is invented – no maker's name, model or chart. Needs OpenCascade (OCP) for the STEP files;
the pictures need ``bpy`` as well. The STEP writer is not byte-stable (time stamp): a rebuild changes every STEP file.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from fresing_render.lifting_model import classes as C  # noqa: E402
from fresing_render.lifting_model import make as M  # noqa: E402

PICTURE_SIZE = (480, 320)
PICTURE_POSE = "Working"


def check(folder: str = M.BUILTIN_DIR, names=None) -> list[str]:
    """Classes whose shipped JSON differs from a fresh make (the centres of gravity are taken from the file: they
    need OpenCascade)."""
    from fresing_render.lifting_model import equipment as E
    bad = []
    for name in names or C.CLASSES:
        path = os.path.join(folder, name, f"{name}.json")
        if not os.path.isfile(path):
            bad.append(f"{name}: no {name}.json")
            continue
        with open(path, encoding="utf-8") as fh:
            kept = fh.read()
        fresh = M.json_text(E.data(name, json.loads(kept)["cog"]))
        if fresh != kept:
            bad.append(f"{name}: {name}.json differs from a fresh make (run tools/make_lifting_cranes.py --json-only)")
    return bad


def picture(name: str, folder: str = M.BUILTIN_DIR, size=PICTURE_SIZE, samples: int = 24) -> str:
    """<class>.png: imported with the app's importer, rigged from its file (tests/lifting_rig.py), the hoist rope made a
    cable, posed, framed from the front left, rendered with Cycles on the processor."""
    import bpy
    import numpy as np
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    import lifting_rig as LR
    from fresing_render.blender import build, cameras, paths
    import tempfile
    r = LR.Rigged(name, folder=folder, out=tempfile.mkdtemp(prefix="fr_lifting_"))
    sc = r.scene
    cab = r.data["rig"]["cables"][0]
    it = paths.add_cable(sc, cab["name"])
    paths.read_cad(sc, it, r.part(cab["part"]))
    hb = r.part("HOOK BLOCK")
    it = paths.find(sc, cab["name"])
    sh = paths.shape_now(sc, it)
    c = np.array(hb.matrix_world.translation)
    paths.set_end(sc, it, "a" if np.linalg.norm(sh[0] - c) < np.linalg.norm(sh[-1] - c) else "b", hb)
    pose = next(p for p in r.sheet["poses"] if p["name"] == PICTURE_POSE)
    r.set(pose["values"])
    paths.refresh(sc, force=True)
    bpy.context.view_layer.update()
    parts = [o for o in build.iter_parts(sc) if o.type == "MESH"]
    mn, mx = build.world_bounds(parts)
    corners = np.array([[x, y, z] for x in (mn[0], mx[0]) for y in (mn[1], mx[1]) for z in (mn[2], mx[2])])
    cam = cameras.add_camera(sc, "ISO", lens=50.0, name="Picture", points=corners, margin=0.86)
    sc.camera = cam
    sun = bpy.data.objects.new("Picture sun", bpy.data.lights.new("Picture sun", "SUN"))
    sun.data.energy = 3.5
    sun.rotation_euler = (0.75, 0.15, -0.9)
    sc.collection.objects.link(sun)
    world = sc.world or bpy.data.worlds.new("Picture")
    sc.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    bg.inputs[0].default_value = (0.82, 0.85, 0.88, 1.0)
    bg.inputs[1].default_value = 0.9
    ren = sc.render
    ren.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    ren.resolution_x, ren.resolution_y = size
    ren.resolution_percentage = 100
    ren.film_transparent = False
    ren.image_settings.file_format = "PNG"
    ren.image_settings.color_mode = "RGB"
    ren.image_settings.compression = 100
    out = os.path.join(folder, name, f"{name}.png")
    ren.filepath = out
    bpy.ops.render.render(write_still=True)
    shrink(out)
    return out


def shrink(path: str) -> None:
    """The picture with a 128-colour palette (ImageMagick, when there): a fraction of the size (task 0214: 256
    colours made some 2-4 times bigger and the cranes a little over their 11.5 MB)."""
    import shutil
    import subprocess
    tool = shutil.which("magick") or shutil.which("convert")
    if tool:
        subprocess.run([tool, path, "-dither", "None", "-colors", "128", "PNG8:" + path], check=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=M.BUILTIN_DIR, help="folder (default: fresing_render/data/lifting)")
    ap.add_argument("--only", default="", help="comma-separated classes (default: all 12)")
    ap.add_argument("--json-only", action="store_true")
    ap.add_argument("--pictures", action="store_true", help="only the pictures (the STEP and JSON must be there)")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    names = [x.strip() for x in a.only.split(",") if x.strip()] or list(C.CLASSES)
    bad = [x for x in names if x not in C.CLASSES]
    if bad:
        ap.error("unknown classes: " + ", ".join(bad))
    if a.check:
        problems = check(a.out, names)
        print("\n".join(problems) or "the equipment files are up to date")
        return 1 if problems else 0
    if a.pictures:
        for n in names:
            print(picture(n, a.out), flush=True)
        return 0
    for n in names:
        print(json.dumps(M.write_class(n, a.out, step=not a.json_only)), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
