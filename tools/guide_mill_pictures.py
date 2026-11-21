"""The user guide's pictures of air blast and coolant on the test mill (docs/img/air_blast.jpg, coolant.jpg; task 0249:
made again for the larger test mill, from the test tour's sets "air" and "coolant" with their own close-up cameras).

    ~/venv/bin/python tools/guide_mill_pictures.py [out dir]      (default docs/img; Cycles on the processor, ~5 min)

air_blast.jpg: the block at the end of the program, without air (the program's M7 not used) and with air, side by
side. coolant.jpg: the stop "coolant" (flood while it cuts). Only the test models of tests/data are shown."""

import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

import bpy  # noqa: E402
import addon_utils  # noqa: E402,I001

import fresing_render  # noqa: E402
from fresing_render.blender import animation, render, tour  # noqa: E402

OUT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "docs", "img"))
WORK = tempfile.mkdtemp(prefix="fr_mill_pictures_")


def still(sc, name):
    s = sc.fresing
    s.out_format, s.out_resolution, s.use_gpu, s.out_folder = "presentation", "preview", False, WORK
    render.apply_output(sc, s)
    sc.render.resolution_percentage = 100
    t0 = time.time()
    assert bpy.ops.fresing.render(quality="preview") == {"FINISHED"}
    print(f"[PIC] {name}: {time.time() - t0:.0f} s", flush=True)
    return s.last_render


def camera(sc, aim, off, lens=50.0):
    """A camera looking at ``aim`` (world, m) from ``aim + off``."""
    from mathutils import Matrix, Vector
    cam = bpy.data.objects.new("Guide camera", bpy.data.cameras.new("Guide camera"))
    sc.collection.objects.link(cam)
    cam.data.lens = lens
    aim, off = Vector(aim), Vector(off)
    cam.matrix_world = Matrix.Translation(aim + off) @ (-off).to_track_quat("-Z", "Y").to_matrix().to_4x4()
    sc.camera = cam
    bpy.context.view_layer.update()


def go(stop_id):
    st = tour.find(stop_id)
    tour.open_set(WORK, "9.9.9", st.set)
    sc = bpy.context.scene
    problems = tour.apply(st, sc)
    assert not problems, problems
    return sc


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    out = tour.build_all(WORK, "9.9.9", only=("air", "coolant"))
    assert not out["errors"], out["errors"]
    sc = go("coolant")
    camera(sc, (0.0, 0.0, 0.085), (0.16, -0.28, 0.12))            # the tool, the jets and the hoses close up
    flood = still(sc, "coolant")
    subprocess.run(["convert", flood, "-strip", "-quality", "86", os.path.join(OUT, "coolant.jpg")], check=True)
    sc = go("air")
    a = sc.fresing.animations[sc.fresing.animations_index]
    sc.frame_set(sc.frame_end)
    camera(sc, (0.0, 0.0, 0.07), (0.25, -0.42, 0.33))             # the block on the table, the spindle above
    with_air = still(sc, "with air")
    sc.fresing.cnc.air_on_code = 150                      # no M150 in the program: no air
    for blk in a.blocks:
        if blk.kind == "GCODE":
            blk.gcode_clean = False                        # and no blowing the part clean at the end
    animation.bake(sc, a)
    sc.frame_set(sc.frame_end)
    camera(sc, (0.0, 0.0, 0.07), (0.25, -0.42, 0.33))             # (Build put the set's own camera back)
    without = still(sc, "without air")
    subprocess.run(["convert", without, with_air, "+append", "-strip", "-quality", "86",
                    os.path.join(OUT, "air_blast.jpg")], check=True)
    print("[PIC] written to", OUT, flush=True)


main()
