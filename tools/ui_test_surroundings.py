"""Real-app test of the surroundings (task 0016), with simulated input in the real Fresing Render app.

Every surrounding is chosen as in the side panel; a live preview of a hall; props for scale added,
undone and redone; a click through the hall still selects the machine; the background queue renders
a still (Cycles) and a short video (EEVEE) of a saved scene on a vessel deck; save + reopen keeps it
all without rebuilding. Then screenshots of panel 5 Scene & Render for each kind of background
(panel5_*.png: only panel 5 is shown, at the default side-panel width).

Install the extension and the app template first (see tools/ui_test_app.py). Run:
    FRESING_UI_OPEN_FOLDS=1 xvfb-run -a -s "-screen 0 1500x3000x24" blender -p 0 0 1500 3000 \
        --app-template fresing_render --enable-event-simulate --python tools/ui_test_surroundings.py
UITEST_QUICK=1 skips the queue. Log and pictures go to $UITEST_OUT (default ~/fresing_ui_surroundings).
"""

import math
import os
import subprocess
import time
import traceback

import bpy
from bpy_extras import view3d_utils
from mathutils import Vector

OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_surroundings"))
CRANE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "data", "test_crane_a.step")
QUICK = bool(os.environ.get("UITEST_QUICK"))
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "ui_test_surroundings.log"), "w")
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


def env_objects():
    return mod("blender.surroundings")._objects(bpy.context.scene)


def write_hdr(path):
    import numpy as np
    w, h = 256, 128
    px = np.zeros((h, w, 4), np.float32)
    px[h // 2:, :, :3] = (0.9, 1.0, 1.3)
    px[: h // 2, :, :3] = (0.3, 0.27, 0.22)
    px[:, :, 3] = 1.0
    img = bpy.data.images.new("ui_test_photo", w, h, float_buffer=True)
    img.pixels.foreach_set(px.ravel())
    img.filepath_raw = path
    img.file_format = "HDR"
    img.save()
    bpy.data.images.remove(img)


def picture_stats(path):
    import numpy as np
    img = bpy.data.images.load(path)
    px = np.empty(img.size[0] * img.size[1] * 4, np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    px = px.reshape(-1, 4)
    return float(px[:, :3].std()), float(px[:, 3].min())


STEPS = []


def step(fn):
    STEPS.append(fn)
    return fn


@step
def s_start():
    check("add-on enabled", pkg() is not None and pkg() in bpy.context.preferences.addons, pkg())
    shot("00_start")                            # also gives the splash screen time to open
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
def s_every_kind():
    """Each built-in surrounding, as picked in the Background list."""
    from importlib import import_module
    env = import_module(pkg() + ".core.surroundings")
    sur = mod("blender.surroundings")
    s = bpy.context.scene.fresing
    mn, mx = mod("blender.logic").cached_bounds(bpy.context.scene)
    times = []
    ok = True
    for detail in ("SIMPLE", "DETAILED"):
        s.env_detail = detail
        for kind in env.BUILT:
            t = time.time()
            s.background = kind
            times.append(f"{kind[:4]}/{detail[0]} {time.time() - t:.2f}s")
            root = sur.root_object()
            good = (root is not None and root.get("fr_kind") == kind and env_objects()
                    and abs(root.location.z - mn[2]) < 1e-4)
            if not good:
                ok = False
                log("not built:", kind, detail)
    check("every surrounding builds in the app, machine on the floor", ok, ", ".join(times))
    s.env_detail = "SIMPLE"
    s.background = "FACTORY"
    floor = bpy.data.objects.get(mod("blender.world").FLOOR_NAME)
    check("studio floor hidden under a hall", floor is None or floor.hide_render)
    shot("01_factory_solid_view")
    return 0.5


@step
def s_live_preview():
    r = op("fresing.preview")
    check("live preview of the hall starts", r == {"FINISHED"} and ui()[1].spaces.active.shading.type == "RENDERED", r)
    return 10.0


@step
def s_live_preview_off():
    shot("02_factory_live_preview")
    op("fresing.preview")
    check("live preview off", ui()[1].spaces.active.shading.type == "SOLID")
    return 0.5


@step
def s_props():
    sur = mod("blender.surroundings")
    sc = bpy.context.scene
    r1 = op("fresing.prop_add", kind="PERSON")
    r2 = op("fresing.prop_add", kind="CONTAINER")
    props = sur.props(sc)
    z = sur.floor_height(sc)
    check("props added next to the machine, on the floor",
          r1 == r2 == {"FINISHED"} and len(props) == 2 and all(abs(p.location.z - z) < 1e-4 for p in props),
          [(p.name, round(p.location.z, 4)) for p in props])
    act = bpy.context.view_layer.objects.active
    check("the new prop is selected to move it", act is not None and act.get(sur.PROP_TAG) == "CONTAINER",
          act.name if act else None)
    STATE["env_ptrs"] = sorted(ob.as_pointer() for ob in env_objects())
    shot("03_props")
    key("Z", ctrl=True)
    return 1.0


@step
def s_after_undo():
    sur = mod("blender.surroundings")
    names = sorted(p.name for p in sur.props(bpy.context.scene))
    check("undo removes the last prop, the hall stays", len(names) == 1 and len(env_objects()) > 3, (names, len(env_objects())))
    key("Z", ctrl=True, shift=True)
    return 1.0


@step
def s_after_redo():
    sur = mod("blender.surroundings")
    n = len(sur.props(bpy.context.scene))
    check("redo brings the prop back", n == 2, n)
    # click the boom through the hall: the machine is selected, never the hall
    for o in bpy.context.selected_objects:
        o.select_set(False)
    boom = find("BOOM")
    x, y = to_window(boom.matrix_world @ Vector((1.0, 0, 0.05)))
    click(x, y)
    return 0.8


@step
def s_wiggle():
    wiggle()                                    # the app finishes a pick on the next mouse move
    return 0.8


@step
def s_after_click():
    sur = mod("blender.surroundings")
    sel = bpy.context.selected_objects
    names = {o.get("fr_name") for o in sel}
    check("click in the hall selects the machine's subassembly", {"BOOM", "BOOM.ASM"} <= names, sorted(map(str, names)))
    check("the hall itself cannot be clicked", not any(o.get(sur.TAG) for o in sel))
    s = bpy.context.scene.fresing
    s.props_visible = False
    hidden = all(p.hide_render and p.hide_viewport for p in sur.props(bpy.context.scene))
    s.props_visible = True
    shown = not any(p.hide_render for p in sur.props(bpy.context.scene))
    check("Show props hides and shows all props", hidden and shown)
    r = op("fresing.env_place")
    check("Put on the floor again", r == {"FINISHED"} and abs(sur.root_object().location.z -
                                                                 sur.floor_height(bpy.context.scene)) < 1e-6)
    return 0.5


@step
def s_queue():
    if QUICK:
        return 0.1
    sc = bpy.context.scene
    s = sc.fresing
    s.out_folder = os.path.join(OUT, "renders")
    s.background = "DECK"
    s.sea_state = "ROUGH"
    s.use_gpu = False
    with override():
        bpy.ops.fresing.shot_save(name="On deck", scheme="__current__", pose="__current__", visibility="__current__")
    s.background = "FACTORY"
    s.env_detail = "DETAILED"
    with override():
        bpy.ops.fresing.shot_save(name="In the hall", scheme="__current__", pose="__current__",
                                  visibility="__current__")
    s.env_detail = "SIMPLE"                     # the queue switches to the saved scenes itself
    s.sea_state = "CALM"
    for name, start in (("Deck video", "On deck"), ("Hall video", "In the hall")):
        a = s.animations.add()
        a.name = name
        a.start_shot = start
        a.out_resolution = "preview"
        a.out_format = "square"
        a.quality = "eevee"                     # the fast preview engine: waves, see-through walls, cut-away
        a.tail = 0.0
        b = a.blocks.add()
        b.kind, b.camera_mode, b.camera, b.start = "CAMERA", "CUT", sc.camera, 0.04   # 2 frames
    with override():
        bpy.ops.fresing.queue_add(kind="SHOT", name="On deck")
        s.queue[-1].quality = "draft"
        s.out_resolution = "preview"
        bpy.ops.fresing.queue_add(kind="ANIMATION", name="Deck video")
        bpy.ops.fresing.queue_add(kind="ANIMATION", name="Hall video")
        res = bpy.ops.fresing.queue_start()
    check("queue starts a background Blender", res == {"FINISHED"} and s.queue_pid > 0, res)
    STATE["qt0"] = time.time()
    return 2.0


@step
def s_queue_wait():
    if QUICK:
        return 0.1
    sc = bpy.context.scene
    q = mod("blender.queue")
    if q.is_running(sc) and time.time() - STATE["qt0"] < 1500:
        return "wait"
    q.sync(sc)
    jobs = [(j.label, j.status, j.message, j.output) for j in sc.fresing.queue]
    check("queue: deck still (Cycles), deck and hall videos (EEVEE) rendered",
          len(jobs) == 3 and all(j[1] == "DONE" for j in jobs), jobs)
    try:
        std, alpha = picture_stats(sc.fresing.queue[0].output)
        check("queue still shows the deck, no empty background", std > 0.02 and alpha > 0.99, (std, alpha))
        subprocess.run(["cp", sc.fresing.queue[0].output, os.path.join(OUT, "04_queue_still_deck.png")], check=False)
        for i, what in ((1, "deck"), (2, "hall")):
            frames = os.path.splitext(sc.fresing.queue[i].output)[0]
            pngs = sorted(f for f in os.listdir(frames) if f.endswith(".png"))
            std, alpha = picture_stats(os.path.join(frames, pngs[0]))
            check(f"EEVEE frame shows the {what}", len(pngs) >= 2 and std > 0.02 and alpha > 0.99,
                  (len(pngs), std, alpha))
            subprocess.run(["cp", os.path.join(frames, pngs[0]), os.path.join(OUT, f"05_queue_eevee_{what}.png")],
                           check=False)
    except Exception as exc:
        check("queue pictures readable", False, str(exc))
    check("the queue left the hall in the open project", sc.fresing.background == "FACTORY")
    return 0.5


@step
def s_save_reload():
    STATE["key"] = mod("blender.surroundings").root_object().get("fr_key")
    path = os.path.join(OUT, "surroundings_project.blend")
    with override():
        bpy.ops.wm.save_as_mainfile(filepath=path)
    with override():
        bpy.ops.wm.open_mainfile(filepath=path)
    return 1.5


@step
def s_after_reload():
    sc = bpy.context.scene
    sur = mod("blender.surroundings")
    root = sur.root_object()
    check("reopened: the hall is there", sc.fresing.background == "FACTORY" and root is not None
          and root.get("fr_key") == STATE["key"] and len(env_objects()) > 3)
    before = sorted(ob.as_pointer() for ob in env_objects())
    mod("blender.world").apply(sc, sc.fresing)
    check("reopened: not rebuilt when nothing changed", sorted(ob.as_pointer() for ob in env_objects()) == before)
    check("reopened: props kept", len(sur.props(sc)) == 2)
    shot("06_reopened")
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
    cls = getattr(bpy.types, "FRESING_PT_props", None)
    if cls is not None:            # a copy that starts open (the panel remembers that it was closed)
        attrs = {k: getattr(cls, k) for k in ("bl_label", "bl_space_type", "bl_region_type", "bl_category",
                                              "draw", "draw_header", "draw_header_preset") if hasattr(cls, k)}
        attrs.update(bl_idname="FRESING_PT_props_open", bl_parent_id="FRESING_PT_scene", bl_options=set())
        bpy.utils.unregister_class(cls)
        bpy.utils.register_class(type("FRESING_PT_props_open", (bpy.types.Panel,), attrs))
    for name in ("FRESING_PT_shots", "FRESING_PT_output"):     # closed, so panel 5 itself fits
        cls = getattr(bpy.types, name, None)
        if cls is not None:
            bpy.utils.unregister_class(cls)
            cls.bl_options = set(getattr(cls, "bl_options", set())) | {"DEFAULT_CLOSED"}
            bpy.utils.register_class(cls)
    write_hdr(os.path.join(OUT, "test_photo.hdr"))
    redraw()
    return 1.5


SCREENS = [
    ("panel5_1_colour", dict(background="COLOR")),
    ("panel5_2_photo_none", dict(background="HDRI", hdri_path="")),
    ("panel5_3_photo", dict(background="HDRI", hdri_path="__PHOTO__")),
    ("panel5_4_sea", dict(background="SEA")),
    ("panel5_5_deck", dict(background="DECK")),
    ("panel5_6_factory", dict(background="FACTORY")),
    ("panel5_7_props", dict(background="WAREHOUSE")),
]


def _screen_step(name, values):
    def set_state():
        s = bpy.context.scene.fresing
        for k, v in values.items():
            setattr(s, k, os.path.join(OUT, "test_photo.hdr") if v == "__PHOTO__" else v)
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
