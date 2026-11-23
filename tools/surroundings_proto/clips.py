"""Study 0311: the short clips of the page.

    ~/venv/bin/python tools/surroundings_proto/clips.py --clip orbit|cull|stages --out DIR

orbit   the camera goes round the crane on the finished site (the scatter culled to each frame's view)
cull    seen from above while the shot camera turns: only what the camera sees is made, near trees detailed
stages  the maker step by step (flat → hills → pad → paint → road → buildings → water → trees → grass)
Frames are JPEGs; ffmpeg makes the MP4 (see the end of each function).
"""

from __future__ import annotations

import argparse
import math
import os
import subprocess
import sys
import time

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import scene as SC  # noqa: E402

CRANE = "/tmp/claude-0/p/crane.blend"


def _mp4(pattern, out, fps):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", pattern, "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", "-crf", "23", "-movflags", "+faststart", out], check=True)


def orbit(a):
    sc, T, terrain = SC.build(8, crane_blend=CRANE)
    w, h = (int(v) for v in a.size.split("x"))
    SC.setup_render(sc, w, h, a.samples)
    cam = SC.camera("FR shot", (40, -30, 8), (6, 0, 8), 28.0)
    SC.add_scatter(terrain, SC.make_sources(), cam)
    n = a.frames
    times = []
    for f in range(n):
        ang = math.radians(-40 + 70 * f / max(1, n - 1))
        r = 46.0
        loc = (6 + r * math.cos(ang), r * math.sin(ang), 7.0 + 3.0 * f / n)
        SC.camera("FR shot", loc, (5, 0, 9 + 2.0 * f / n), 26.0)
        bpy.context.view_layer.update()
        t = time.time()
        SC.render(os.path.join(a.out, f"orbit_{f:03d}.jpg"))
        times.append(time.time() - t)
        print("frame", f, round(times[-1], 1), SC.instance_counts(), flush=True)
    _mp4(os.path.join(a.out, "orbit_%03d.jpg"), os.path.join(a.out, "clip_orbit.mp4"), a.fps)
    print("orbit mean s/frame", sum(times) / len(times))


def cull(a):
    sc, T, terrain = SC.build(8, crane_blend=CRANE)
    SC.setup_render(sc, 640, 640, 12)
    shot = SC.camera("FR shot", (0, -20, 6), (0, 20, 2), 35.0)
    sc.render.resolution_x, sc.render.resolution_y = 1280, 720          # the shot's own frame decides the cone
    obs = SC.add_scatter(terrain, SC.make_sources(), shot, ["tree", "conifer", "bush", "rock"])
    sc.render.resolution_x, sc.render.resolution_y = 640, 640
    top = SC.camera("FR top", (0, 0, 300), (0, 0.001, 0), 50.0)
    top.data.type = "ORTHO"
    top.data.ortho_scale = 260.0
    # the shot camera as a visible marker: a thin cone of its view
    import bmesh
    me = bpy.data.meshes.new("view cone")
    bm = bmesh.new()
    tip = bm.verts.new((0, 0, 0))
    tx, ty = 0.6, 0.34
    far = [bm.verts.new((sx * tx * 120, sy * ty * 120, -120)) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    for i in range(4):
        bm.faces.new((tip, far[i], far[(i + 1) % 4]))
    bm.to_mesh(me)
    cone = SC.new_ob("view cone", me)
    cone.parent = shot
    m = bpy.data.materials.new("cone")
    m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (1.0, 0.35, 0.05, 1)
    p.inputs["Alpha"].default_value = 0.25
    me.materials.append(m)
    sc.camera = top
    n = a.frames
    for f in range(n):
        ang = 2 * math.pi * f / n
        shot.location = (25 * math.cos(ang) + 5, 25 * math.sin(ang), 6.0)
        import mathutils
        d = mathutils.Vector((math.cos(ang + 2.2), math.sin(ang + 2.2), -0.05))
        shot.rotation_mode = "QUATERNION"
        shot.rotation_quaternion = d.to_track_quat("-Z", "Y")
        bpy.context.view_layer.update()
        SC.render(os.path.join(a.out, f"cull_{f:03d}.jpg"))
        print("frame", f, SC.instance_counts(), flush=True)
    _mp4(os.path.join(a.out, "cull_%03d.jpg"), os.path.join(a.out, "clip_cull.mp4"), a.fps)


def stages(a):
    names = []
    for k, name in enumerate(SC.STAGES):
        sc, T, terrain = SC.build(k, crane_blend=CRANE)
        w, h = (int(v) for v in a.size.split("x"))
        SC.setup_render(sc, w, h, a.samples)
        cam = SC.camera("FR shot", *SC.SHOTS["overview"])
        if k >= SC.STAGES.index("trees"):
            kinds = None if k >= SC.STAGES.index("grass") else ["tree", "conifer", "bush", "rock"]
            SC.add_scatter(terrain, SC.make_sources(), cam, kinds)
        path = os.path.join(a.out, f"stage_{k}_{name}.jpg")
        SC.render(path)
        # a caption on the picture (ImageMagick)
        subprocess.run(["convert", path, "-gravity", "southwest", "-fill", "white", "-undercolor", "#000000a0",
                        "-pointsize", str(int(h / 18)), "-annotate", "+12+12", f" {k + 1}. {LABELS[name]} ", path],
                       check=True)
        names.append(path)
        print("stage", k, name, flush=True)
    # each stage held 1.5 s, cross-faded
    frames = os.path.join(a.out, "stages_frames")
    os.makedirs(frames, exist_ok=True)
    f = 0
    for i, p in enumerate(names):
        for _ in range(int(a.fps * 1.2)):
            subprocess.run(["cp", p, os.path.join(frames, f"{f:04d}.jpg")], check=True)
            f += 1
        if i + 1 < len(names):
            for s in range(1, int(a.fps * 0.4)):
                t = s / int(a.fps * 0.4)
                subprocess.run(["convert", p, names[i + 1], "-compose", "blend", "-define",
                                f"compose:args={int(t * 100)}", "-composite", os.path.join(frames, f"{f:04d}.jpg")],
                               check=True)
                f += 1
    _mp4(os.path.join(frames, "%04d.jpg"), os.path.join(a.out, "clip_stages.mp4"), a.fps)


LABELS = {"flat": "Flat ground", "hills": "Hills + raise / lower brush", "pad": "The machine's pad kept flat",
          "paint": "Painted ground: gravel, sand, mud, rock, concrete", "road": "A road drawn as a line",
          "buildings": "Buildings from a few settings", "water": "A pond: water fills the hollow",
          "trees": "Trees, bushes, rocks painted", "grass": "Grass where the ground is grass"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clip", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--size", default="640x360")
    ap.add_argument("--samples", type=int, default=16)
    ap.add_argument("--frames", type=int, default=48)
    ap.add_argument("--fps", type=int, default=24)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    {"orbit": orbit, "cull": cull, "stages": stages}[a.clip](a)


if __name__ == "__main__":
    main()
