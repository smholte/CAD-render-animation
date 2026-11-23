"""Study 0300: the clips for the page – each station today (rigid) beside the prototype (soft); Cycles on the
processor, Blender 5.2.3 as a Python module.

    ~/venv/bin/python tools/soft_proto/render.py <out dir> [station ...]
"""

from __future__ import annotations

import math
import os
import subprocess
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(__file__))
import scene  # noqa: E402

STATIONS = {                       # target, camera offset, lens
    "spring": ((0.0, 0.0, 0.05), (0.10, -0.30, 0.10), 50),
    "buffer": ((0.30, 0.0, 0.025), (0.08, -0.22, 0.07), 50),
    "bellows": ((0.73, 0.0, 0.05), (0.06, -0.55, 0.16), 50),
    "tyre": ((1.0, 0.0, 0.22), (0.35, -1.25, 0.25), 50),
}
W, H = 400, 300
STEP = 2


def look(cam, target):
    d = Vector(target) - cam.location
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def setup(station, variant, helix=1.0):
    scene.build(variant, helix=helix)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 24
    sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = W, H
    sc.render.film_transparent = False
    world = bpy.data.worlds.new("w")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.78, 0.80, 0.83, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.8
    sc.world = world
    target, off, lens = STATIONS[station]
    cd = bpy.data.cameras.new("cam")
    cd.lens = lens
    cam = bpy.data.objects.new("cam", cd)
    sc.collection.objects.link(cam)
    cam.location = Vector(target) + Vector(off)
    look(cam, target)
    sc.camera = cam
    ld = bpy.data.lights.new("key", "AREA")
    ld.energy = 60
    ld.size = 0.6
    lo = bpy.data.objects.new("key", ld)
    sc.collection.objects.link(lo)
    lo.location = Vector(target) + Vector((-0.4, -0.5, 0.7))
    look(lo, target)
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sun.data.energy = 2.0
    sc.collection.objects.link(sun)
    sun.rotation_euler = (0.7, 0.2, 0.8)
    # a floor under everything
    fl = scene.mesh_object("Floor", scene.shapes.box(4, 4, 0.01, 0.5, 0, -0.031), sc.collection,
                           scene.material("floor", (0.55, 0.56, 0.57), 0.8))
    return sc


def render(out, station, variant, helix=1.0, frames=None):
    sc = setup(station, variant, helix)
    d = os.path.join(out, f"{station}_{variant}")
    os.makedirs(d, exist_ok=True)
    frames = frames or range(1, scene.FRAMES + 1, STEP)
    for i, fr in enumerate(frames):
        sc.frame_set(fr)
        sc.render.filepath = os.path.join(d, f"{i:03d}.png")
        bpy.ops.render.render(write_still=True)
    return d


def clip(out, station):
    a = render(out, station, "rigid")
    b = render(out, station, "soft")
    dest = os.path.join(out, f"{station}.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "12", "-i", os.path.join(a, "%03d.png"),
                    "-framerate", "12", "-i", os.path.join(b, "%03d.png"), "-filter_complex",
                    "[0]drawtext=text='today':x=10:y=10:fontsize=18:fontcolor=white:box=1:boxcolor=black@0.5[l];"
                    "[1]drawtext=text='soft (prototype)':x=10:y=10:fontsize=18:fontcolor=white:box=1:"
                    "boxcolor=black@0.5[r];[l][r]hstack", "-pix_fmt", "yuv420p", "-c:v", "libx264", "-crf", "26",
                    "-movflags", "+faststart", dest], check=True)
    return dest


if __name__ == "__main__":
    out = sys.argv[1]
    names = sys.argv[2:] or list(STATIONS)
    for n in names:
        if n == "wire":
            # the spring at 50 mm: plain stretch (the wire goes flat) vs following the wire (stays round)
            for helix, tag in ((0.0, "plain"), (1.0, "helix")):
                sc = setup("spring", "soft", helix)
                cam = sc.camera
                cam.location = Vector((0.03, -0.20, 0.06))
                cam.data.lens = 55
                look(cam, (0.0, 0.0, 0.03))
                sc.frame_set(40)
                sc.render.filepath = os.path.join(out, f"wire_{tag}.png")
                bpy.ops.render.render(write_still=True)
            continue
        print(clip(out, n))
