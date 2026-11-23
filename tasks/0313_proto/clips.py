"""Task 0313 (study, prototype – not app code): the moves of ``moves.py`` as short clips on the test crane and the test
mill, the options of two moves side by side, a drawn path edited, and the timings of point D.

    ~/venv/bin/python tasks/0313_proto/clips.py            (Blender as a Python module, no graphics card)

Env: CLIPS_OUT (folder, default /tmp/clips0313), CLIPS_ONLY (comma list of clip names), CLIPS_FPS (default 20),
CLIPS_SECONDS (default 4). Renders with Workbench (the 3D view's own look: what a preview shows), 480 x 270, then
ffmpeg makes an MP4 and a poster per clip. ``timings.json`` holds what point D measures on these two models.
The camera is a plain camera keyed the way Build keys the Animation camera (a key per frame, ``foreach_set``).
"""
import json
import math
import os
import subprocess
import sys
import time

import bpy  # noqa: I001 (bpy first: it makes addon_utils importable)
import addon_utils
import numpy as np
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
import fresing_render  # noqa: E402
from fresing_render.blender import build, cameras, joints  # noqa: E402

import moves as M  # noqa: E402

OUT = os.environ.get("CLIPS_OUT", "/tmp/clips0313")
ONLY = {x for x in os.environ.get("CLIPS_ONLY", "").split(",") if x}
FPS = int(os.environ.get("CLIPS_FPS", "20"))
SECONDS = float(os.environ.get("CLIPS_SECONDS", "4"))
W, H = 480, 270
ASPECT = W / H
os.makedirs(OUT, exist_ok=True)
TIMES: dict = {}


def log(*a):
    print("[CLIPS]", *a, flush=True)


# ---------------------------------------------------------------------------
# set-up
# ---------------------------------------------------------------------------

def open_model(name: str):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    sc.fresing.out_folder = os.path.join(OUT, "cache")
    t = time.perf_counter()
    assert bpy.ops.fresing.import_step(filepath=os.path.join(ROOT, "fresing_render", "data", name + ".step"),
                                       quality="draft") == {"FINISHED"}
    TIMES.setdefault(name, {})["import_s"] = round(time.perf_counter() - t, 2)
    bpy.ops.fresing.light_look(look="PRODUCT")
    sc.fresing.background = "COLOR"
    sc.fresing.background_color = (0.88, 0.89, 0.9)
    r = sc.render
    r.engine = "BLENDER_WORKBENCH"
    r.resolution_x, r.resolution_y, r.resolution_percentage = W, H, 100
    r.fps = FPS
    sh = sc.display.shading
    sh.light, sh.color_type = "STUDIO", "MATERIAL"
    sh.show_shadows, sh.show_cavity = True, True
    sh.cavity_type, sh.curvature_ridge_factor, sh.curvature_valley_factor = "WORLD", 0.6, 0.8
    sh.background_type, sh.background_color = "VIEWPORT", (0.88, 0.89, 0.9)
    if sc.world is not None:
        sc.world.color = (0.62, 0.64, 0.66)              # Workbench's render background is the world colour
    sc.display.render_aa = "8"
    sc.display.shadow_focus = 0.6
    cd = bpy.data.cameras.new("Operator")
    cam = bpy.data.objects.new("Operator", cd)
    sc.collection.objects.link(cam)
    cd.sensor_fit, cd.sensor_width = "AUTO", M.SENSOR
    sc.camera = cam
    return sc, cam


def parts(sc, *names):
    out = [o for o in sc.objects if o.get(build.PROP_NAME) in names]
    assert out, names
    return out


def subject(sc, objs=None) -> M.Subject:
    if objs is None:
        return M.Subject(cameras._points(sc))
    pts = []
    for ob in objs:
        for o in [ob] + list(ob.children_recursive):
            if o.type == "MESH" and o.data is not None:
                mw = np.array(o.matrix_world)
                bb = np.array([list(c) + [1.0] for c in o.bound_box])
                pts.append((mw @ bb.T).T[:, :3])
    return M.Subject(np.concatenate(pts))


# ---------------------------------------------------------------------------
# keys and clips
# ---------------------------------------------------------------------------

def key_camera(cam, sampled: dict, start: int = 1) -> float:
    """Keys the camera on every frame (place, turn as quaternions, lens, focus), as Build does; returns ms."""
    t = time.perf_counter()
    mats = M.matrices(sampled)
    n = len(mats)
    frames = np.arange(start, start + n, dtype=float)
    if cam.animation_data and cam.animation_data.action:
        bpy.data.actions.remove(cam.animation_data.action)
    if cam.data.animation_data and cam.data.animation_data.action:
        bpy.data.actions.remove(cam.data.animation_data.action)
    cam.rotation_mode = "QUATERNION"
    loc = mats[:, :3, 3]
    quats = np.array([tuple(Matrix(m.tolist()).to_quaternion()) for m in mats])
    for i in range(1, n):                       # keep one hemisphere so the turn never flips
        if np.dot(quats[i], quats[i - 1]) < 0:
            quats[i] = -quats[i]

    def write(idb, path, idx, values):
        if idb.animation_data is None:
            idb.animation_data_create()
        if idb.animation_data.action is None:
            idb.animation_data.action = bpy.data.actions.new(idb.name + " keys")
        fc = idb.animation_data.action.fcurve_ensure_for_datablock(idb, path, index=idx)
        fc.keyframe_points.add(n)
        fc.keyframe_points.foreach_set("co", np.column_stack([frames, values]).ravel().tolist())
        fc.keyframe_points.foreach_set("interpolation", [2] * n)          # LINEAR: one key per frame
        fc.update()

    for i in range(3):
        write(cam, "location", i, loc[:, i])
    for i in range(4):
        write(cam, "rotation_quaternion", i, quats[:, i])
    write(cam.data, "lens", -1, sampled["lens"])
    write(cam.data, "dof.focus_distance", -1, sampled["focus"])
    return (time.perf_counter() - t) * 1000


def render_clip(sc, cam, name: str, sampled: dict, per_frame=None, dof=None, overlay=None, engine=None) -> None:
    if ONLY and name not in ONLY:
        return
    n = len(sampled["pos"])
    ms = key_camera(cam, sampled)
    TIMES.setdefault("clips", {})[name] = {"frames": n, "key_ms": round(ms, 1)}
    folder = os.path.join(OUT, "frames", name)
    os.makedirs(folder, exist_ok=True)
    for f in os.listdir(folder):
        os.remove(os.path.join(folder, f))
    sc.frame_start, sc.frame_end = 1, n
    cd = cam.data
    cd.dof.use_dof = dof is not None
    sc.display.shading.use_dof = dof is not None
    if dof is not None:
        cd.dof.aperture_fstop = dof
    cd.clip_start, cd.clip_end = 0.02, 500.0
    old = sc.render.engine
    if engine:                                  # Cycles for the focus pull: Workbench's blur is hard to see
        sc.render.engine = engine
        sc.cycles.samples, sc.cycles.use_denoising, sc.cycles.device = 24, True, "CPU"
    t = time.perf_counter()
    for i in range(n):
        if per_frame is not None:
            per_frame(i)
        sc.frame_set(i + 1)
        sc.render.filepath = os.path.join(folder, f"{i:04d}.png")
        bpy.ops.render.render(write_still=True)
    TIMES["clips"][name]["render_s"] = round(time.perf_counter() - t, 1)
    sc.render.engine = old
    if overlay:
        overlay(folder)
    mp4 = os.path.join(OUT, name + ".mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i",
                    os.path.join(folder, "%04d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "30",
                    "-preset", "slow", "-movflags", "+faststart", mp4], check=True)
    subprocess.run(["convert", os.path.join(folder, f"{int(n * 0.6):04d}.png"), "-quality", "82",
                    os.path.join(OUT, name + ".jpg")], check=True)
    log(name, n, "frames", TIMES["clips"][name])


def frames_n() -> int:
    return int(round(SECONDS * FPS))


def made(name, fn, *a, **kw):
    """Make a move and sample it, timed (point D: placing a move = these two)."""
    t = time.perf_counter()
    shot = fn(*a, **kw)
    s = shot.sample(frames_n()) if isinstance(shot, M.Shot) else shot
    TIMES.setdefault("place_ms", {})[name] = round((time.perf_counter() - t) * 1000, 2)
    return shot, s


# ---------------------------------------------------------------------------
# path pictures (the handles in the view, before and after an edit)
# ---------------------------------------------------------------------------

def _mat(name, rgb):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = (*rgb, 1.0)
    return m


def show_path(sc, shot: M.Shot, tag: str, colour=(0.85, 0.15, 0.1), r=0.03):
    """A tube along the move's path and a ball on each handle (drawn only for this picture)."""
    from fresing_render.core import camera_path as P
    path = P.Path(shot.handles)
    cu = bpy.data.curves.new("path " + tag, "CURVE")
    cu.dimensions, cu.bevel_depth = "3D", r
    sp = cu.splines.new("POLY")
    pts = path.dense[::6]
    sp.points.add(len(pts) - 1)
    sp.points.foreach_set("co", [c for p in pts for c in (*p, 1.0)])
    ob = bpy.data.objects.new("path " + tag, cu)
    ob.data.materials.append(_mat("path " + tag, colour))
    sc.collection.objects.link(ob)
    obs = [ob]
    for i, h in enumerate(shot.handles):
        me = bpy.data.meshes.new(f"h{i}")
        import bmesh
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=8, radius=r * 3.2)
        bm.to_mesh(me)
        bm.free()
        hb = bpy.data.objects.new(f"handle {tag} {i}", me)
        hb.location = Vector(h)
        me.materials.append(_mat("handle", (0.1, 0.35, 0.9)))
        sc.collection.objects.link(hb)
        obs.append(hb)
    return obs


def still(sc, cam, name, pos, target, lens=35.0):
    cam.animation_data_clear()
    cam.data.animation_data_clear()
    cam.matrix_world = Matrix(M.look_matrix(pos, target).tolist())
    cam.data.lens = lens
    cam.data.dof.use_dof = False
    sc.display.shading.use_dof = False
    sc.render.filepath = os.path.join(OUT, name + ".png")
    bpy.ops.render.render(write_still=True)
    subprocess.run(["convert", sc.render.filepath, "-quality", "85", os.path.join(OUT, name + ".jpg")], check=True)
    os.remove(sc.render.filepath)


def guides(folder):
    """Framing guides drawn over the frames (thirds + centre): what the view would show, never rendered."""
    for f in sorted(os.listdir(folder)):
        p = os.path.join(folder, f)
        x1, x2, y1, y2 = W // 3, 2 * W // 3, H // 3, 2 * H // 3
        subprocess.run(["convert", p, "-stroke", "rgba(255,255,255,0.75)", "-strokewidth", "1",
                        "-draw", f"line {x1},0 {x1},{H}", "-draw", f"line {x2},0 {x2},{H}",
                        "-draw", f"line 0,{y1} {W},{y1}", "-draw", f"line 0,{y2} {W},{y2}",
                        "-stroke", "rgba(255,200,0,0.9)", "-draw", f"line {W//2-8},{H//2} {W//2+8},{H//2}",
                        "-draw", f"line {W//2},{H//2-8} {W//2},{H//2+8}", p], check=True)


# ---------------------------------------------------------------------------
# the two models
# ---------------------------------------------------------------------------

def crane_clips():
    sc, cam = open_model("test_crane_a")
    S = subject(sc)
    t = time.perf_counter()
    for _ in range(20):
        S = subject(sc)
    TIMES["test_crane_a"]["subject_ms"] = round((time.perf_counter() - t) * 50, 2)
    trolley = subject(sc, parts(sc, "TROLLEY.ASM"))
    log("crane", S.lo, S.hi, "trolley", trolley.centre)

    # 1 orbit: three heights side by side (the options compared)
    for h in ("LOW", "EYE", "HIGH"):
        _, s = made(f"orbit_{h}", M.orbit, S, turn=120, height=h, aspect=ASPECT)
        render_clip(sc, cam, f"crane_orbit_{h.lower()}", s)
    # 2 crane up
    _, s = made("crane_up", M.crane, S, rise="UP", aspect=ASPECT)
    render_clip(sc, cam, "crane_crane_up", s)
    # 3 hero arc, two lenses side by side
    for lens in (24, 50):
        _, s = made(f"hero_{lens}", M.hero, S, lens=lens, aspect=ASPECT)
        render_clip(sc, cam, f"crane_hero_{lens}", s)
    # 4 slide past
    _, s = made("slide", M.slide, S, aspect=ASPECT)
    render_clip(sc, cam, "crane_slide", s)
    # 5 top-down to side
    _, s = made("top_down", M.top_down, S, aspect=ASPECT)
    render_clip(sc, cam, "crane_top_down", s)
    # 6 fly-over, then the same path edited (middle handles pulled aside, a point added)
    shot, s = made("fly_over", M.fly_over, S, aspect=ASPECT)
    render_clip(sc, cam, "crane_fly_over", s)
    t = time.perf_counter()
    ed = M.move_handle(shot, 1, shot.handles[1] + np.array([0, -2.2, -0.6]))
    ed = M.move_handle(ed, 2, ed.handles[2] + np.array([0, -2.2, -0.4]))
    ed = M.add_handle(ed, 2)
    ed.handles[3] = ed.handles[3] + np.array([0.0, 0.8, -0.9])
    s2 = ed.sample(frames_n())
    TIMES["place_ms"]["edit_path"] = round((time.perf_counter() - t) * 1000, 2)
    render_clip(sc, cam, "crane_fly_over_edited", s2)
    view_pos = S.centre + M.direction(-100, 55) * 22.0
    obs = show_path(sc, shot, "a")
    still(sc, cam, "path_before", view_pos, S.centre)
    for o in obs:
        bpy.data.objects.remove(o)
    obs = show_path(sc, ed, "b", colour=(0.1, 0.6, 0.2))
    still(sc, cam, "path_after", view_pos, S.centre)
    for o in obs:
        bpy.data.objects.remove(o)
    # 7 follow the trolley as it runs out along the boom (the path is the part's), then with handheld shake
    tro = parts(sc, "TROLLEY.ASM")[0]
    j = joints.create(sc, "SLIDE", [tro], tro.matrix_world.translation.copy(), Vector((1, 0, 0)), name="Trolley")
    n = frames_n()
    travel = [3.2 * M._smooth(i / (n - 1)) for i in range(n)]
    track = []
    for v in travel:
        joints.set_value(j, v, use_limits=False)
        bpy.context.view_layer.update()
        track.append(np.array(subject(sc, [tro]).centre))
    track = np.array(track)

    def drive(i):
        joints.set_value(j, travel[i], use_limits=False)

    t = time.perf_counter()
    s = M.follow(track, trolley, az=-60, el=22, distance=1.6, lag=0.4, fps=FPS, aspect=ASPECT)
    TIMES["place_ms"]["follow"] = round((time.perf_counter() - t) * 1000, 2)
    render_clip(sc, cam, "crane_follow", s, per_frame=drive)
    # 8 push in to the trolley, with handheld shake (the shake layer on any move) and the framing guides
    joints.set_value(j, 0.0, use_limits=False)
    bpy.context.view_layer.update()
    shot, _ = made("push_in", M.push_in, S, trolley, closeness=0.85, aspect=ASPECT)
    shot.shake = dict(kind="HANDHELD", strength=1.5, seed=3, fps=FPS)
    render_clip(sc, cam, "crane_push_in_handheld", shot.sample(frames_n()), overlay=guides)


def mill_clips():
    sc, cam = open_model("test_mill")
    S = subject(sc)
    t = time.perf_counter()
    for _ in range(20):
        S = subject(sc)
    TIMES["test_mill"]["subject_ms"] = round((time.perf_counter() - t) * 50, 2)
    tool = subject(sc, parts(sc, "END MILL D10"))
    stock = subject(sc, parts(sc, "STOCK 200x200x40"))
    spindle = subject(sc, parts(sc, "SPINDLE HOUSING"))
    log("mill", S.lo, S.hi, "tool", tool.centre, "stock", stock.centre)
    # push in: two closenesses side by side
    for c in (0.5, 0.95):
        _, s = made(f"push_{c}", M.push_in, S, stock, closeness=c, aspect=ASPECT)
        render_clip(sc, cam, f"mill_push_in_{int(c * 100)}", s)
    # pull out (a reveal) from the tool
    _, s = made("pull_out", M.push_in, S, spindle, closeness=0.9, reverse=True, aspect=ASPECT)
    render_clip(sc, cam, "mill_pull_out", s)
    # orbit 360 high (the turntable as a move)
    _, s = made("orbit_mill", M.orbit, S, turn=360, height="HIGH", aspect=ASPECT)
    render_clip(sc, cam, "mill_orbit_360", s)
    # focus pull: from the tool to the vice / stock behind it
    near = subject(sc, parts(sc, "END MILL D10", "STOCK 200x200x40"))
    far = subject(sc, parts(sc, "COLUMN"))
    _, s = made("focus_pull", M.focus_pull, S, near, far, az=-60, el=14, lens=85, aspect=ASPECT)
    render_clip(sc, cam, "mill_focus_pull", s, dof=1.4, engine="CYCLES")
    # walk-shake on a slide past
    shot, _ = made("slide_walk", M.slide, S, length=0.6, side=-80, el=8, aspect=ASPECT)
    shot.shake = dict(kind="WALK", strength=1.0, seed=5, fps=FPS)
    render_clip(sc, cam, "mill_slide_walk", shot.sample(frames_n()))


def main():
    fresing_render.register()
    try:
        crane_clips()
        mill_clips()
    finally:
        with open(os.path.join(OUT, "timings.json"), "w") as fh:
            json.dump(TIMES, fh, indent=1)
        log("timings", json.dumps(TIMES))


if __name__ == "__main__":
    main()
