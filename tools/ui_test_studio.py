"""Real-app test of light looks, camera views, background blur and the turntable (task 0017), with
simulated input in the real Fresing Render app.

Every light look as its button does it (and a live preview of one); every standard view frames the
crane, and a click on the trolley + Frame: Selection frames only the trolley; adding a camera is
undone and redone with Ctrl+Z / Ctrl+Shift+Z; background blur and the sharp spot picked with the
eyedropper and a click on the model; a render with blur; the turntable button renders a short video
in the background queue (Cycles draft: the first frame, then Stop now); a hall shows the render-time note and 'Use Simple';
save + reopen keeps it all. Then screenshots of panel 5 Scene & Render (panel5_*.png: only panel 5,
at the default side-panel width).

Install the extension and the app template first (see tools/ci_real_app.py). Run:
    xvfb-run -a -s "-screen 0 1800x2600x24" blender --app-template fresing_render \
        --enable-event-simulate --python tools/ui_test_studio.py
UITEST_QUICK=1 skips the queue. Log and pictures go to $UITEST_OUT (default ~/fresing_ui_studio).
"""

import os
import subprocess
import time
import traceback

import bpy
from bpy_extras import view3d_utils
from mathutils import Vector

OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_studio"))
CRANE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "data", "test_crane_a.step")
QUICK = bool(os.environ.get("UITEST_QUICK"))
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "ui_test_studio.log"), "w")
RESULTS = []
STATE = {}


def log(*a):
    msg = " ".join(str(x) for x in a)
    print("[UITEST]", msg, flush=True)
    LOG.write(msg + "\n")
    LOG.flush()


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    log(("PASS " if ok else "FAIL ") + name + (f" ({detail})" if detail else ""))


def pkg():
    import addon_utils
    return next((m.__name__ for m in addon_utils.modules() if m.__name__.endswith("fresing_render")), None)


def mod(name):
    import importlib
    return importlib.import_module(pkg() + "." + name)


def ui():
    win = bpy.context.window_manager.windows[0]
    area = next(a for a in win.screen.areas if a.type == "VIEW_3D")
    region = next(r for r in area.regions if r.type == "WINDOW")
    sidebar = next(r for r in area.regions if r.type == "UI")
    return win, area, region, sidebar


def override():
    win, area, region, _sb = ui()
    return bpy.context.temp_override(window=win, screen=win.screen, area=area, region=region, scene=win.scene)


def op(_idname, *args, undo=True, **kw):
    """Call an operator like a button press (EXEC, with an undo step)."""
    group, op_name = _idname.split(".")
    with override():
        return getattr(getattr(bpy.ops, group), op_name)("EXEC_DEFAULT", undo, **kw)


def shot(name):
    subprocess.run(["import", "-window", "root", os.path.join(OUT, name + ".png")], check=False)


def sidebar_shot(name, height=1500):
    """Screenshot of the top of the side panel."""
    win, area, region, sb = ui()
    full = os.path.join(OUT, "_full.png")
    subprocess.run(["import", "-window", "root", full], check=False)
    top = win.height - (sb.y + sb.height)
    h = min(height, sb.height)
    subprocess.run(["convert", full, "-crop", f"{sb.width}x{h}+{sb.x}+{top}", "+repage",
                    os.path.join(OUT, name + ".png")], check=False)


def to_window(world_pt):
    win, area, region, _sb = ui()
    co = view3d_utils.location_3d_to_region_2d(region, region.data, Vector(world_pt))
    return int(region.x + co.x), int(region.y + co.y)


def click(x, y):
    win = bpy.context.window_manager.windows[0]
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x, y=y)
    win.event_simulate(type="LEFTMOUSE", value="PRESS", x=x, y=y)
    win.event_simulate(type="LEFTMOUSE", value="RELEASE", x=x, y=y)
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x + 3, y=y + 3)


def key(k, ctrl=False, shift=False):
    win, area, region, _sb = ui()
    x, y = region.x + region.width // 2, region.y + region.height // 2
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x, y=y)
    win.event_simulate(type=k, value="PRESS", x=x, y=y, ctrl=ctrl, shift=shift)
    win.event_simulate(type=k, value="RELEASE", x=x, y=y, ctrl=ctrl, shift=shift)


def wiggle():
    win, area, region, _sb = ui()
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=region.x + 300 + int(time.time()) % 7, y=region.y + 300)


def redraw():
    win = bpy.context.window_manager.windows[0]
    for a in win.screen.areas:
        a.tag_redraw()


def find(name, n=0):
    hits = sorted((o for o in bpy.context.scene.objects if o.get("fr_name") == name), key=lambda o: o.get("fr_uid"))
    return hits[n] if len(hits) > n else None


def middle_of(ob):
    return ob.matrix_world @ (sum((Vector(c) for c in ob.bound_box), Vector()) / 8)


def corners(objs):
    pts = []
    for ob in objs:
        if ob.type == "MESH" and ob.visible_get():
            pts += [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    return pts


def in_picture(cam, pts, tol=1e-4):
    """(all inside, largest share of the picture)."""
    from bpy_extras.object_utils import world_to_camera_view
    sc = bpy.context.scene
    bpy.context.view_layer.update()
    co = [world_to_camera_view(sc, cam, p) for p in pts]
    xs, ys = [c.x for c in co], [c.y for c in co]
    inside = all(-tol <= c.x <= 1 + tol and -tol <= c.y <= 1 + tol and c.z > 0 for c in co)
    return inside, max(max(xs) - min(xs), max(ys) - min(ys))


def parts():
    return [o for o in bpy.context.scene.objects if o.get("fr_kind") == "part" and o.type == "MESH"]


STEPS = []


def step(fn):
    STEPS.append(fn)
    return fn


@step
def s_start():
    check("add-on enabled", pkg() is not None and pkg() in bpy.context.preferences.addons, pkg())
    shot("00_start")
    win, area, region, sb = ui()
    x, y = win.width // 2, win.height // 2      # close the splash (a real user's first click does that)
    win.event_simulate(type="ESC", value="PRESS", x=x, y=y)
    win.event_simulate(type="ESC", value="RELEASE", x=x, y=y)
    return 1.0


@step
def s_import():
    with override():
        bpy.ops.fresing.import_step(filepath=CRANE, quality="normal")
    return 1.0


@step
def s_wait_import():
    if bpy.context.scene.fresing.model_count == 0:
        return "wait"
    check("model imported", bpy.context.scene.fresing.model_count == 1)
    return 0.5


@step
def s_looks():
    """Every light look, as its button does it."""
    studio = mod("core.studio")
    world = mod("blender.world")
    s = bpy.context.scene.fresing
    ok, times = True, []
    for look in studio.LOOKS:
        t = time.time()
        r = op("fresing.light_look", look=look)
        times.append(f"{look} {time.time() - t:.2f}s")
        nt = bpy.context.scene.world.node_tree
        imgs = {n.image.name for n in nt.nodes if n.type == "TEX_ENVIRONMENT" and n.image}
        want = world.LOOK_IMAGES.get(look if look != "SUN" else "", (None,))[0]
        good = r == {"FINISHED"} and studio.look_matches(look, s) and (want is None or want in imgs)
        if not good:
            ok = False
            log("look not right:", look, r, imgs)
    check("every light look sets light, background and floor", ok, ", ".join(times))
    op("fresing.light_look", look="PRODUCT")
    words = studio.light_words(s.lighting, s.sky_weather, s.light_rotation, s.light_strength, s.sun_elevation)
    check("light in plain words", words.startswith("Main light from the front left"), words)
    return 0.5


@step
def s_live_preview():
    r = op("fresing.preview")
    check("live preview of the product studio starts",
          r == {"FINISHED"} and ui()[1].spaces.active.shading.type == "RENDERED", r)
    return 10.0


@step
def s_live_preview_off():
    shot("01_product_studio_live_preview")
    op("fresing.preview")
    check("live preview off", ui()[1].spaces.active.shading.type == "SOLID")
    return 0.5


@step
def s_views():
    """Every standard view frames the whole crane."""
    cams = mod("blender.cameras")
    s = bpy.context.scene.fresing
    s.view_frame = "MODEL"
    bad = []
    for view in cams.STANDARD_VIEWS + ("ISO_LEFT", "BACK"):
        r = op("fresing.camera_add", view=view)
        cam = bpy.context.scene.camera
        inside, share = in_picture(cam, corners(parts()))
        if r != {"FINISHED"} or not inside or share < 0.85:
            bad.append((view, r, inside, round(share, 3)))
    check("every standard view frames the whole crane", not bad, bad)
    STATE["n_cams"] = len(cams.fr_cameras(bpy.context.scene))
    return 0.5


@step
def s_click_trolley():
    trolley = find("TROLLEY")
    op("fresing.camera_activate", name=bpy.context.scene.camera.name)    # look through the last camera
    win, area, region, _sb = ui()
    region.data.view_perspective = "PERSP"
    with override():
        bpy.ops.view3d.view_all()
    STATE["trolley_xy"] = to_window(middle_of(trolley))
    return 1.0


@step
def s_click_trolley_2():
    x, y = to_window(middle_of(find("TROLLEY")))
    click(x, y)
    return 1.0


@step
def s_frame_selection():
    sel = {o.get("fr_name") for o in bpy.context.selected_objects}
    check("a click selects the trolley subassembly", "TROLLEY" in sel, sorted(x for x in sel if x))
    s = bpy.context.scene.fresing
    s.view_frame = "SELECTION"
    r = op("fresing.camera_add", view="LOW")
    cam = bpy.context.scene.camera
    trolley = [o for o in bpy.context.selected_objects if o.get("fr_kind") == "part"]
    inside, share = in_picture(cam, corners(trolley))
    whole, _ = in_picture(cam, corners(parts()))
    check("Frame: Selection frames only the trolley", r == {"FINISHED"} and inside and share > 0.85 and not whole
          and cam.name.endswith("(selection)"), (cam.name, inside, round(share, 3), whole))
    s.view_frame = "MODEL"
    STATE["sel_cam"] = cam.name
    return 0.5


@step
def s_undo_camera():
    key("Z", ctrl=True)
    return 1.5


@step
def s_after_undo():
    cams = mod("blender.cameras")
    names = [c.name for c in cams.fr_cameras(bpy.context.scene)]
    check("Ctrl+Z takes the new camera away", STATE["sel_cam"] not in names, names)
    key("Z", ctrl=True, shift=True)
    return 1.5


@step
def s_after_redo():
    cams = mod("blender.cameras")
    names = [c.name for c in cams.fr_cameras(bpy.context.scene)]
    check("Ctrl+Shift+Z brings it back", STATE["sel_cam"] in names, names)
    op("fresing.camera_activate", name=next(c.name for c in cams.fr_cameras(bpy.context.scene)
                                            if c.name.startswith("3/4 hero, low") and "selection" not in c.name))
    bpy.ops.object.select_all(action="DESELECT")
    return 0.5


@step
def s_blur():
    cams = mod("blender.cameras")
    studio = mod("core.studio")
    s = bpy.context.scene.fresing
    cam = bpy.context.scene.camera
    s.camera_blur = "STRONG"                     # the 'Strong' button of Background blur
    d = cam.data.dof
    want = studio.blur_fstop("STRONG", cam.data.lens, cam.data.sensor_width, d.focus_distance)
    check("background blur: strong", d.use_dof and abs(d.aperture_fstop - want) < 1e-3 and
          cams.focus_label(cam) == "Middle of the machine", (d.use_dof, d.aperture_fstop, want))
    # the eyedropper: then a click on the boom tip
    win, area, region, _sb = ui()
    region.data.view_perspective = "CAMERA"
    with override():
        res = bpy.ops.fresing.focus_pick("INVOKE_DEFAULT")
    check("sharp-spot eyedropper starts", "RUNNING_MODAL" in res, res)
    return 1.0


@step
def s_click_sharp_spot():
    boom = find("BOOM")
    tip = boom.matrix_world @ Vector((max(c[0] for c in boom.bound_box) * 0.85, 0.0,
                                      (min(c[2] for c in boom.bound_box) + max(c[2] for c in boom.bound_box)) / 2))
    STATE["tip"] = tip
    x, y = to_window(tip)
    click(x, y)
    return 1.0


@step
def s_after_sharp_spot():
    cams = mod("blender.cameras")
    cam = bpy.context.scene.camera
    marker = cams.focus_marker(cam)
    ok = marker is not None
    if ok:
        p = marker.matrix_world.translation
        fwd = cam.matrix_world.to_3x3() @ Vector((0, 0, -1))
        dist = (p - cam.matrix_world.translation).dot(fwd)
        ok = abs(cam.data.dof.focus_distance - dist) < 1e-3 and (p - STATE["tip"]).length < 0.2
    check("a click on the boom makes it the sharp spot", ok,
          (cams.focus_label(cam), round(cam.data.dof.focus_distance, 3)))
    before = cam.data.dof.aperture_fstop
    bpy.context.scene.fresing.camera_lens = 85.0
    check("a longer lens keeps the same blur look (f-stop follows)", cam.data.dof.aperture_fstop > before,
          (before, cam.data.dof.aperture_fstop))
    bpy.context.scene.fresing.camera_lens = 50.0
    op("fresing.camera_fit")
    return 0.5


@step
def s_render_blur():
    s = bpy.context.scene.fresing
    s.out_format = "custom"
    s.out_custom_w, s.out_custom_h = 320, 180
    s.quality = "draft"
    s.use_gpu = False
    r = op("fresing.render")
    STATE["render_t"] = time.time()
    check("Render image with blur starts", r in ({"FINISHED"}, {"RUNNING_MODAL"}), r)
    return 2.0


@step
def s_render_blur_wait():
    s = bpy.context.scene.fresing
    if not (s.last_render and os.path.isfile(s.last_render)) and time.time() - STATE["render_t"] < 300:
        return "wait"
    check("render with blur saved", s.last_render and os.path.isfile(s.last_render), s.last_render)
    for w in bpy.context.window_manager.windows[1:]:      # close the render window
        with bpy.context.temp_override(window=w):
            bpy.ops.wm.window_close()
    return 1.0


@step
def s_hall_note():
    turntable = mod("blender.turntable")
    s = bpy.context.scene.fresing
    s.background = "CNC"
    s.env_detail = "DETAILED"
    note = turntable.slow_note(s)
    r = op("fresing.env_simple")
    check("a hall: the turntable says it renders slower and offers Simple",
          "1.4 to 2.8" in note and r == {"FINISHED"} and s.env_detail == "SIMPLE", note)
    op("fresing.light_look", look="PRODUCT")
    return 0.5


@step
def s_turntable():
    s = bpy.context.scene.fresing
    s.turntable_seconds = 2.0
    s.turntable_height = "MIDDLE"
    s.turntable_quality = "draft"
    tt = mod("blender.turntable")
    a = tt.find_animation(bpy.context.scene)
    if a is None:                               # make it once, then a small square video for the test
        tt.make(bpy.context.scene)
        a = tt.find_animation(bpy.context.scene)
    a.out_resolution, a.out_format, a.fps = "preview", "square", "24"
    if QUICK:
        info = tt.make(bpy.context.scene)
        check("turntable made (queue skipped)", info["frames"] == 48, info["frames"])
        return 0.5
    path = os.path.join(OUT, "studio_test.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    r = op("fresing.turntable")
    q = s.queue
    check("Make turntable video puts it in the queue and starts it",
          r == {"FINISHED"} and len(q) and q[-1].animation == a.name and mod("blender.queue").is_running(
              bpy.context.scene), (r, [j.label for j in q]))
    STATE["queue_t"] = time.time()
    return 2.0


@step
def s_turntable_wait():
    """The first frame is enough to show the background render works (48 frames take minutes on a
    test machine without a graphics card); then 'Stop now'."""
    if QUICK:
        return 0.1
    import glob
    queue = mod("blender.queue")
    render = mod("blender.render")
    sc = bpy.context.scene
    s = sc.fresing
    job = s.queue[-1]
    out_dir = bpy.path.abspath(s.out_folder) if s.out_folder else render.default_output_dir()
    found = glob.glob(os.path.join(out_dir, f"*_{job.job_id}", "frame_0001.png"))
    queue.sync(sc)
    if not found and queue.is_running(sc) and time.time() - STATE["queue_t"] < 900:
        return "wait"
    secs = round(time.time() - STATE["queue_t"])
    with override():
        bpy.ops.fresing.queue_stop(now=True)
    log("queue log:", queue.log_tail(s.queue_dir, 12))
    ok = bool(found)
    if ok:
        img = bpy.data.images.load(found[0])
        ok = tuple(img.size) == (540, 540)
        bpy.data.images.remove(img)
    check("the background queue renders the turntable's frames", ok, (found[:1], secs, job.message))
    return 2.0


@step
def s_save_reload():
    s = bpy.context.scene.fresing
    s.background = "SKY"
    op("fresing.light_look", look="OVERCAST")
    path = os.path.join(OUT, "studio_test.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    STATE["cam_name"] = bpy.context.scene.camera.name
    bpy.ops.wm.open_mainfile(filepath=path)
    return 3.0


@step
def s_after_reload():
    cams = mod("blender.cameras")
    tt = mod("blender.turntable")
    sc = bpy.context.scene
    s = sc.fresing
    cam = sc.camera
    check("reopened: look, blur, sharp spot and turntable kept",
          s.sky_weather == "OVERCAST" and s.background == "SKY" and cam.name == STATE["cam_name"]
          and cams.blur_level(cam) == "STRONG" and cams.focus_marker(cam) is not None
          and tt.find_animation(sc) is not None and "Turntable" in s.shots,
          (s.sky_weather, s.background, cam.name, cams.blur_level(cam), cams.focus_label(cam)))
    return 0.5


@step
def s_panel_only():
    """For the screenshots: only panel 5 (and its sub-panels) in the side panel."""
    keep = {"FRESING_PT_scene"}
    classes = [getattr(bpy.types, n) for n in dir(bpy.types) if n.startswith("FRESING_PT_")]
    drop = [c for c in classes if c.__name__ not in keep and getattr(c, "bl_parent_id", "") not in keep]
    for cls in sorted(drop, key=lambda c: 0 if getattr(c, "bl_parent_id", "") else 1):   # sub-panels first
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            log("could not hide", cls.__name__)
    for name in ("FRESING_PT_shots", "FRESING_PT_output", "FRESING_PT_props"):    # closed: panel 5 fits
        cls = getattr(bpy.types, name, None)
        if cls is not None:
            bpy.utils.unregister_class(cls)
            cls.bl_options = set(getattr(cls, "bl_options", set())) | {"DEFAULT_CLOSED"}
            bpy.utils.register_class(cls)
    cls = getattr(bpy.types, "FRESING_PT_turntable", None)
    if cls is not None:            # a copy that starts open (the panel remembers that it was closed)
        attrs = {k: getattr(cls, k) for k in ("bl_label", "bl_space_type", "bl_region_type", "bl_category",
                                              "draw", "draw_header", "draw_header_preset") if hasattr(cls, k)}
        attrs.update(bl_idname="FRESING_PT_turntable_open", bl_parent_id="FRESING_PT_scene", bl_options=set())
        bpy.utils.unregister_class(cls)
        bpy.utils.register_class(type("FRESING_PT_turntable_open", (bpy.types.Panel,), attrs))
    redraw()
    return 1.5


SCREENS = [
    ("panel5_1_product", dict(look="PRODUCT")),
    ("panel5_2_white", dict(look="WHITE")),
    ("panel5_3_dark", dict(look="DARK")),
    ("panel5_4_sun", dict(look="SUN")),
    ("panel5_5_overcast", dict(look="OVERCAST")),
    ("panel5_6_hall", dict(look="PRODUCT", background="ASSEMBLY", env_detail="DETAILED")),
]


def _screen_step(name, values):
    def set_state():
        s = bpy.context.scene.fresing
        values2 = dict(values)
        look = values2.pop("look", None)
        if look:
            op("fresing.light_look", look=look)
        for k, v in values2.items():
            setattr(s, k, v)
        redraw()
        wiggle()
        return 2.0

    def take():
        sidebar_shot(name, 3000)
        log("screenshot", name)
        return 0.3

    set_state.__name__ = "s_set_" + name
    take.__name__ = "s_take_" + name
    STEPS.append(set_state)
    STEPS.append(take)


for _name, _values in SCREENS:
    _screen_step(_name, _values)


@step
def s_finish():
    failed = [r for r in RESULTS if not r[1]]
    log(f"RESULT {len(RESULTS) - len(failed)}/{len(RESULTS)} passed")
    LOG.close()
    bpy.ops.wm.quit_blender()
    return None


_i = [0]
_w = [0.0]


def driver():
    if _i[0] >= len(STEPS):
        return None
    fn = STEPS[_i[0]]
    try:
        r = fn()
    except Exception:
        log("ERROR in", fn.__name__, traceback.format_exc())
        check(fn.__name__, False, "exception")
        r = 0.5
    if r == "wait":
        if not _w[0]:
            _w[0] = time.time()
        if time.time() - _w[0] > 1800:
            check(fn.__name__ + " timeout", False)
            _i[0] += 1
            _w[0] = 0.0
        wiggle()
        return 1.0
    _w[0] = 0.0
    _i[0] += 1
    return r


bpy.app.timers.register(driver, first_interval=3.0, persistent=True)
