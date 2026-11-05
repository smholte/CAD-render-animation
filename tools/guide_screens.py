"""Pictures for the user guide (docs/img/), made in the real app with the generic test crane only.

Three runs; each writes its pictures to $GUIDE_OUT (default docs/img):

  panels   one picture per side-panel section, the rest of the side panel hidden:
      BLENDER_USER_RESOURCES=<user> GUIDE_SHOTS=panels xvfb-run -a -s "-screen 0 1500x7000x24" \\
          blender -p 0 0 1500 7000 --app-template fresing_render --enable-event-simulate --python tools/guide_screens.py
  window   the whole app: at start, after an import, the Help menu, joint arrows in the view:
      BLENDER_USER_RESOURCES=<user> GUIDE_SHOTS=window xvfb-run -a -s "-screen 0 1920x1200x24" \\
          blender -p 0 0 1920 1200 --app-template fresing_render --enable-event-simulate --python tools/guide_screens.py
  render   a finished render of the crane (Cycles on the processor):
      BLENDER_USER_RESOURCES=<user> GUIDE_SHOTS=render blender -b --app-template fresing_render \\
          --python tools/guide_screens.py
  looks    the crane in each of the five light looks, side by side (looks.png; Cycles on the processor):
      BLENDER_USER_RESOURCES=<user> GUIDE_SHOTS=looks blender -b --app-template fresing_render \\
          --python tools/guide_screens.py

<user> is a Blender user folder with the extension (Linux build, guide inside) and the app template
installed, see tools/ui_test_app.py. Needs xvfb-run and ImageMagick (import). A lane that changes its
panels runs "panels" again and checks the pictures of its sections before committing them.

Only the test models in tests/data may be shown: the repository is public.
"""

import math
import os
import shutil
import subprocess
import tempfile
import sys
import time
import traceback

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "tests", "data")
CRANE = os.path.join(DATA, "test_crane_a.step")
CRANE_B = os.path.join(DATA, "test_crane_b.step")
MODE = os.environ.get("GUIDE_SHOTS", "panels")
OUT = os.path.abspath(os.environ.get("GUIDE_OUT", os.path.join(HERE, "..", "docs", "img")))
os.makedirs(OUT, exist_ok=True)
SCRATCH = os.environ.get("GUIDE_SCRATCH", os.path.join(tempfile.gettempdir(), "fresing_guide_screens"))
os.makedirs(SCRATCH, exist_ok=True)
LOG = open(os.path.join(SCRATCH, f"guide_screens_{MODE}.log"), "w")


def log(*a):
    msg = " ".join(str(x) for x in a)
    print("[GUIDE]", msg, flush=True)
    LOG.write(msg + "\n")
    LOG.flush()


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def pkg():
    import addon_utils
    for m in addon_utils.modules():
        if m.__name__.endswith("fresing_render"):
            return m.__name__
    return None


def mod(name):
    import importlib
    return importlib.import_module(pkg() + "." + name)


def areas():
    win = bpy.context.window_manager.windows[0]
    area = next(a for a in win.screen.areas if a.type == "VIEW_3D")
    region = next(r for r in area.regions if r.type == "WINDOW")
    sidebar = next(r for r in area.regions if r.type == "UI")
    return win, area, region, sidebar


def override():
    win, area, region, _sb = areas()
    return bpy.context.temp_override(window=win, screen=win.screen, area=area, region=region, scene=win.scene)


def ob(name, n=0):
    hits = sorted((o for o in bpy.context.scene.objects if o.get("fr_name") == name), key=lambda o: o.get("fr_uid"))
    return hits[n]


def select_only(*objs):
    for o in bpy.context.selected_objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    if objs:
        bpy.context.view_layer.objects.active = objs[0]


def redraw_all():
    win = bpy.context.window_manager.windows[0]
    for a in win.screen.areas:
        a.tag_redraw()


def wiggle(n=20):
    """Simulated mouse moves over the side panel: panels animate into place on redraws."""
    win, area, region, sb = areas()
    for k in range(n):
        win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=region.x + 100 + k, y=region.y + 100 + 10 * k)
    redraw_all()


def grab_screen():
    """The whole virtual screen as a numpy array (height, width, 3); ImageMagick reads it."""
    import numpy as np
    full = os.path.join(SCRATCH, "screen.png")
    subprocess.run(["import", "-window", "root", full], check=True)
    w, h = (int(v) for v in subprocess.check_output(["identify", "-format", "%w %h", full]).split())
    raw = subprocess.check_output(["convert", full, "-depth", "8", "rgb:-"])
    return np.frombuffer(raw, dtype=np.uint8).reshape(h, w, 3)


def save_png(im, name: str) -> str:
    """Fewer colours (the UI is flat colours): pictures a third of the size, no visible difference."""
    path = os.path.join(OUT, name + ".png")
    h, w = im.shape[:2]
    subprocess.run(["convert", "-size", f"{w}x{h}", "-depth", "8", "rgb:-", "+dither", "-colors", "256",
                    "-strip", f"PNG8:{path}"], input=im.tobytes(), check=True)
    log("saved", name, (w, h), f"{os.path.getsize(path) // 1024} KB")
    return path


def crop_region(im, region, win_h):
    top = win_h - (region.y + region.height)          # screen y grows downwards, Blender's upwards
    return im[top:top + region.height, region.x:region.x + region.width]


def trim_sidebar(im, margin=6):
    """Cut the side panel down to the drawn panels: no tab strip, no empty space below."""
    import numpy as np
    h, w = im.shape[:2]
    bg = im[h - 3, 2].astype(int)                      # empty side-panel background, bottom left
    diff = np.abs(im.astype(int) - bg).max(axis=2) > 6
    # the tab strip ("Item", "Tool", ..., "Fresing") on the right: a column that differs all the way down
    strip = w
    for x in range(w // 2, w):
        if diff[h // 2:h - 4, x].mean() > 0.9:
            strip = x
            break
    body = diff[:h - 4, :strip]                        # (the last rows are the region's edge line)
    rows = np.nonzero(body.any(axis=1))[0]
    cols = np.nonzero(body.any(axis=0))[0]
    if not len(rows):
        return im
    return im[:min(h, rows[-1] + margin), :min(strip, cols[-1] + margin)]


# ---------------------------------------------------------------------------
# side-panel sections on their own
# ---------------------------------------------------------------------------

_ORIG = {}
_CLONES = []
_N = [0]


def _panel_names():
    return sorted(n for n in dir(bpy.types) if n.startswith("FRESING_PT_") and "__shot" not in n)


def show_only(spec):
    """Draw only these Fresing panels: [(class name, closed, top_level[, draw function])].

    Each picture gets fresh copies of the panel classes (a new name each time), so the
    open/closed state is what the picture asks for and not what an earlier picture left."""
    if not _ORIG:
        for n in _panel_names():
            _ORIG[n] = getattr(bpy.types, n)
    for cls in list(_CLONES):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
        _CLONES.remove(cls)
    for n, cls in _ORIG.items():
        if getattr(bpy.types, n, None) is cls:
            bpy.utils.unregister_class(cls)
    _N[0] += 1
    suffix = f"__shot{_N[0]}"
    for name, closed, top, *draw in spec:
        base = _ORIG[name]
        opts = set(getattr(base, "bl_options", set())) - {"DEFAULT_CLOSED"}
        if closed:
            opts.add("DEFAULT_CLOSED")
        attrs = {"bl_idname": name + suffix, "bl_options": opts}
        if draw:                                       # only part of the panel
            attrs["draw"] = draw[0]
        parent = getattr(base, "bl_parent_id", "")
        if top or not parent:
            attrs["bl_parent_id"] = ""
        else:
            attrs["bl_parent_id"] = parent + suffix
        clone = type(name + suffix, (base,), attrs)
        bpy.utils.register_class(clone)
        _CLONES.append(clone)


def restore_panels():
    for cls in list(_CLONES):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
        _CLONES.remove(cls)
    for n, cls in _ORIG.items():
        if getattr(bpy.types, n, None) is None:
            bpy.utils.register_class(cls)


def shoot_sidebar(name):
    win, area, region, sb = areas()
    im = trim_sidebar(crop_region(grab_screen(), sb, win.height))
    save_png(im, name)


# ---------------------------------------------------------------------------
# the project state shown in the pictures (test crane)
# ---------------------------------------------------------------------------


_RULE_SET_UNDO: dict = {}


def _rule_set_state(sc, undo=False):
    """Rule-set picture: the project uses 'Example Ltd' from the shared library and one group has another
    colour. The library is a folder named like a network path inside the scratch folder (Linux allows
    backslashes in a name), so the picture shows the path a Windows PC would show."""
    s = sc.fresing
    rsm, ui = mod("blender.rule_sets"), mod("blender.ui")
    if undo:
        if _RULE_SET_UNDO:
            g = s.groups[_RULE_SET_UNDO["group"]]
            g.material, g.color = _RULE_SET_UNDO["look"]
            s.rule_set, s.rule_set_data = _RULE_SET_UNDO["rule_set"]
            os.environ.pop(rsm.ENV_FOLDER, None)
            os.chdir(_RULE_SET_UNDO["cwd"])
            ui._OPEN_FOLDS = False
            rsm.forget_scan()
            _RULE_SET_UNDO.clear()
        return
    shared = "\\\\server\\Library\\Rule sets"
    _RULE_SET_UNDO.update(cwd=os.getcwd(), rule_set=(s.rule_set, s.rule_set_data))
    os.chdir(SCRATCH)
    shutil.rmtree(shared, ignore_errors=True)
    os.makedirs(shared)
    os.environ[rsm.ENV_FOLDER] = shared
    rsm.forget_scan()
    rsm.save_as(sc, "Example Ltd")
    g = next(g for g in s.groups if g.by_rules and (g.material, g.color) != ("paint_satin", "RAL 5010"))
    _RULE_SET_UNDO.update(group=g.name, look=(g.material, g.color))
    g.material, g.color = "paint_satin", "RAL 5010"
    ui._OPEN_FOLDS = True


def boom_axis():
    """The boom's pivot: the centre of BOOM.PIN, along the pin (-Y, so positive angles raise the boom)."""
    pin = ob("BOOM.PIN")
    centre = sum((pin.matrix_world @ Vector(c) for c in pin.bound_box), Vector()) / 8.0
    return pin, centre, Vector((0.0, -1.0, 0.0))


def build_state():
    """A project in the middle of the work: joints, poses, scenes, an animation, a queue."""
    sc = bpy.context.scene
    s = sc.fresing
    joints, states, queue = mod("blender.joints"), mod("blender.states"), mod("blender.queue")
    pin, origin, direction = boom_axis()
    j1 = joints.create(sc, "ROTATE", [ob("BOOM.ASM")], origin, direction, ref=pin, name="Boom luff")
    j1.use_limits = True
    j1.rot_min, j1.rot_max = math.radians(-5), math.radians(60)
    joints.create(sc, "SLIDE", [ob("TROLLEY.ASM")], Vector((0.7, 0.3, 0.45)), Vector((1, 0, 0)), name="Trolley",
                  base=ob("BOOM.ASM"))                    # "Sits on": the trolley rides on the boom
    s.joints_index = 0
    joints.set_value(j1, math.radians(20))
    states.save_pose(sc, "Working")
    joints.set_value(j1, 0.0)
    states.save_pose(sc, "Transport")
    joints.set_value(j1, math.radians(20))
    states.save_visibility(sc, "Without cover")
    cams = mod("blender.cameras")
    iso = sc.camera or cams.add_camera(sc, "ISO", 50.0)       # the import adds "Iso front-right"
    low = cams.add_camera(sc, "LOW", 35.0)
    sc.camera = iso
    states.save_shot(sc, "Overview")
    sc.camera = low
    states.save_shot(sc, "Low hero")
    sc.camera = iso
    a = s.animations.add()
    a.name = "Luff and travel"
    a.start_shot = "Overview"
    a.tail = 0.5
    b = a.blocks.add()
    b.kind, b.joint, b.start, b.duration, b.to_angle = "JOINT", j1.name, 0.0, 2.0, math.radians(45)
    b.name = "Boom up"
    b = a.blocks.add()
    b.kind, b.joint, b.start, b.duration, b.to_dist = "JOINT", "Trolley", 2.0, 3.0, 0.4
    b.name = "Trolley out"
    b = a.blocks.add()
    b.kind, b.camera_mode, b.orbit_angle, b.start, b.duration = "CAMERA", "ORBIT", math.radians(60), 0.0, 5.0
    b.name = "Camera turns"
    a.blocks_index = 0
    s.animations_index = 0
    # finished renders need a file to point at (Open / Show in folder appear only then)
    png = os.path.join(SCRATCH, "TEST_CRANE_Iso_front-right_1920x1080.png")
    subprocess.run(["convert", "-size", "16x9", "xc:#6f7f90", png], check=True)
    done = queue.add_job(sc, "STILL", shot="Low hero")
    done.status, done.message, done.output = "DONE", "Saved " + os.path.basename(png), png
    test = queue.add_job(sc, "TEST", animation=a.name)
    test.status = "DONE"
    test.message = "6.2 s per frame on GPU: about 14 min for 139 frames at 1920x1080"
    q = queue.add_job(sc, "ANIMATION", animation=a.name)
    s.queue_index = 2
    s.last_render = png
    return j1


# ---------------------------------------------------------------------------
# steps (one per timer call; "wait" = call again until done)
# ---------------------------------------------------------------------------

STEPS = []


def step(fn):
    STEPS.append(fn)
    return fn


def _start():
    win, area, region, sb = areas()
    log("mode", MODE, "ui scale", bpy.context.preferences.view.ui_scale, "window", win.width, win.height,
        "sidebar", sb.width)
    win.event_simulate(type="ESC", value="PRESS", x=700, y=500)       # close the splash screen
    win.event_simulate(type="ESC", value="RELEASE", x=700, y=500)
    return 1.5


def _import(path=CRANE, update=False):
    s = bpy.context.scene.fresing
    with override():
        if update:
            root = mod("blender.build").model_roots(bpy.context.scene)[0]
            res = bpy.ops.fresing.import_step(filepath=path, quality="normal", update_root=root.name)
        else:
            res = bpy.ops.fresing.import_step(filepath=path, quality="normal")
    log("import", os.path.basename(path), res, s.last_message)
    return 1.0


def _wait_import():
    s = bpy.context.scene.fresing
    job = mod("blender.ops_import")._ACTIVE_JOB
    if s.model_count == 0 or (job is not None and not job.done):
        return "wait"
    return 1.0


def _frame_model():
    """Zoom the view onto the model (View all would include the large floor)."""
    parts = list(mod("blender.build").iter_parts(bpy.context.scene))
    select_only(*parts)
    with override():
        bpy.ops.view3d.view_selected()
    select_only()
    return 1.0


if MODE == "panels":

    step(_start)

    @step
    def p_empty_import():
        show_only([("FRESING_PT_import", False, True)])
        wiggle()
        return 2.0

    @step
    def p_shot_empty_import():
        shoot_sidebar("panel_1_import_start")
        return 0.5

    step(_import)
    step(_wait_import)

    @step
    def p_update():
        return _import(CRANE_B, update=True)

    @step
    def p_wait_update():
        s = bpy.context.scene.fresing
        job = mod("blender.ops_import")._ACTIVE_JOB
        if (job is not None and not job.done) or not s.report_title:
            return "wait"
        return 1.0

    @step
    def p_motion_start():
        bpy.context.scene.fresing.pick_mode = "SUBASSEMBLY"
        select_only(ob("BOOM.ASM"))
        show_only([("FRESING_PT_motion", False, True)])
        wiggle()
        return 2.5

    @step
    def p_shot_motion_start():
        shoot_sidebar("panel_4_motion_start")
        return 0.5

    @step
    def p_state():
        build_state()
        sc = bpy.context.scene
        mod("blender.tree").follow_view(sc, ob("BOOM.PIN"))
        select_only(ob("BOOM.ASM"))
        sc.fresing.find_text = "boom"
        # material previews (the coloured balls in the lists) are rendered in the background
        for mat in bpy.data.materials:
            try:
                mat.preview_ensure()
            except Exception:
                pass
        return 1.0

    @step
    def p_previews():
        """Material previews render in the background: draw the lists until they are done (max ~30 s)."""
        p_previews.n = getattr(p_previews, "n", 0) + 1
        if p_previews.n == 1:
            show_only([("FRESING_PT_structure", False, True), ("FRESING_PT_looks", False, True)])
        wiggle()
        return "wait" if p_previews.n < 15 else 2.0

    SHOTS = [
        ("panel_1_import", [("FRESING_PT_import", False, True)]),
        ("panel_2_structure", [("FRESING_PT_structure", False, True)]),
        ("panel_2_cleanup", [("FRESING_PT_cleanup", False, True)]),
        ("panel_2_visibility", [("FRESING_PT_visibility", False, True)]),
        ("panel_3_looks", [("FRESING_PT_looks", False, True)]),
        # the top of 3 Looks: a rule set of the library with a change, Manage rule sets open
        ("panel_3_rule_sets", [("FRESING_PT_looks", False, True,
                                lambda self, context: mod("blender.ui").draw_rule_set(self.layout, context))]),
        ("panel_3_find", [("FRESING_PT_find", False, True)]),
        ("panel_3_rules", [("FRESING_PT_rules", False, True)]),
        ("panel_3_schemes", [("FRESING_PT_schemes", False, True)]),
        ("panel_3_faces", [("FRESING_PT_faces", False, True)]),
        ("panel_4_motion", [("FRESING_PT_motion", False, True)]),
        ("panel_4_poses", [("FRESING_PT_poses", False, True)]),
        ("panel_5_scene", [("FRESING_PT_scene", False, True)]),
        ("panel_5_surroundings", [("FRESING_PT_scene", False, True)]),
        ("panel_5_camera", [("FRESING_PT_camera", False, True)]),
        ("panel_5_props", [("FRESING_PT_props", False, True)]),
        ("panel_5_output", [("FRESING_PT_output", False, True)]),
        ("panel_5_turntable", [("FRESING_PT_turntable", False, True)]),
        ("panel_5_shots", [("FRESING_PT_shots", False, True)]),
        ("panel_6_animation", [("FRESING_PT_animation", False, True)]),
        ("panel_7_queue", [("FRESING_PT_queue", False, True)]),
        # the whole side panel with every section closed: the headers show the state of each
        ("sidebar_sections", [(n, True, False) for n in ("FRESING_PT_import", "FRESING_PT_structure",
                                                         "FRESING_PT_looks", "FRESING_PT_motion",
                                                         "FRESING_PT_scene", "FRESING_PT_animation",
                                                         "FRESING_PT_queue")]),
    ]

    def _make_shot(name, spec):
        def show():
            sc = bpy.context.scene
            if name == "panel_3_looks":                 # a part clicked: its box under the groups
                sc.fresing.pick_mode = "PART"
                select_only(ob("BOOM"))
                grp = ob("BOOM").get("fr_group", "")
                idx = next((i for i, g in enumerate(sc.fresing.groups) if g.name == grp), 0)
                sc.fresing.groups_index = idx
            elif name == "panel_3_rule_sets":
                _rule_set_state(sc)
            elif name == "panel_3_find":                # back to Standard, as before
                _rule_set_state(sc, undo=True)
            elif name == "panel_3_faces":               # one face of the boom painted by hand, boom clicked
                s = sc.fresing
                logic, faces = mod("blender.logic"), mod("blender.faces")
                logic.ensure_group(s, "Warning red")
                s.face_group = "Warning red"
                faces.paint(ob("BOOM"), [0], "Warning red")
                logic.apply_rules(sc)
                sc.fresing.pick_mode = "PART"
                select_only(ob("BOOM"))
            elif name == "panel_2_structure":
                sc.fresing.pick_mode = "SUBASSEMBLY"
                select_only(ob("BOOM.ASM"))
            elif name in ("panel_4_motion", "panel_4_poses"):
                sc.fresing.pick_mode = "SUBASSEMBLY"
                select_only(ob("BOOM.ASM"))
            elif name == "panel_5_scene":               # a light look picked: its button pressed
                with override():
                    bpy.ops.fresing.light_look(look="PRODUCT")
            elif name == "panel_5_surroundings":        # a built-in surrounding: its settings below the choice
                sc.fresing.background = "DECK"
            elif name == "panel_5_camera":              # strong blur, sharp at the trolley (picked on the model)
                cams = mod("blender.cameras")
                cam = next(c for c in cams.fr_cameras(sc) if c.name.startswith("Iso"))
                sc.camera = cam
                sc.fresing.camera_blur = "STRONG"
                trolley = ob("TROLLEY")
                cams.set_focus(cam, sc, trolley, trolley.matrix_world.translation)
            elif name == "panel_5_props":               # two props next to the machine
                sur = mod("blender.surroundings")
                if not sur.props(sc):
                    sur.add_prop(sc, "PERSON")
                    sur.add_prop(sc, "CONTAINER")
            elif name == "panel_5_output":              # back to the studio for the rest
                sc.fresing.background = "COLOR"
                sur = mod("blender.surroundings")
                sur.remove_props(sc)
            show_only(spec)
            wiggle()
            return 2.5

        def shoot():
            shoot_sidebar(name)
            return 0.5
        show.__name__, shoot.__name__ = f"show_{name}", f"shoot_{name}"
        return show, shoot

    for _name, _spec in SHOTS:
        for _fn in _make_shot(_name, _spec):
            step(_fn)

elif MODE == "window":

    step(_start)

    step(_import)
    step(_wait_import)
    step(_frame_model)

    @step
    def w_state():
        build_state()
        sc = bpy.context.scene
        select_only()
        sc.fresing.show_joints = False
        mod("blender.joints").set_value(sc.fresing.joints[0], 0.0)
        _frame_model()
        wiggle(5)
        return 3.0

    @step
    def w_shot_overview():
        save_png(grab_screen(), "app_after_import")
        return 0.5

    @step
    def w_joints():
        sc = bpy.context.scene
        sc.fresing.show_joints = True
        mod("blender.joints").set_value(sc.fresing.joints[0], math.radians(20))
        select_only(ob("BOOM.ASM"))
        wiggle(5)
        return 2.0

    @step
    def w_shot_joints():
        win, area, region, sb = areas()
        im = crop_region(grab_screen(), region, win.height)
        h, w = im.shape[:2]
        save_png(im[int(h * 0.15):int(h * 0.72), int(w * 0.28):int(w * 0.76)], "view_joints")   # the model
        return 0.5

    @step
    def w_help_menu():
        """Click "Help" in the top bar (File Edit Render Window Help: at 1920 px wide and scale 1.0 it is
        at x 235, 13 px below the top edge)."""
        win = bpy.context.window_manager.windows[0]
        scale = bpy.context.preferences.view.ui_scale
        x, y = int(235 * scale), win.height - int(13 * scale)
        win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x, y=y)
        win.event_simulate(type="LEFTMOUSE", value="PRESS", x=x, y=y)
        win.event_simulate(type="LEFTMOUSE", value="RELEASE", x=x, y=y)
        return 2.0

    @step
    def w_shot_help():
        win = bpy.context.window_manager.windows[0]
        im = grab_screen()
        scale = bpy.context.preferences.view.ui_scale
        save_png(im[:int(330 * scale), :int(560 * scale)], "help_menu")
        return 0.5

elif MODE in ("render", "looks"):
    pass


@step
def s_quit():
    LOG.close()
    bpy.ops.wm.quit_blender()
    return None


_i = [0]
_wait = [0.0]


def driver():
    if _i[0] >= len(STEPS):
        return None
    fn = STEPS[_i[0]]
    try:
        r = fn()
    except Exception:
        log("ERROR in", fn.__name__, traceback.format_exc())
        r = 0.5
    if r == "wait":
        if not _wait[0]:
            _wait[0] = time.time()
        if time.time() - _wait[0] > float(os.environ.get("GUIDE_WAIT", "120")):
            log(fn.__name__, "timeout")
            _i[0] += 1
            _wait[0] = 0.0
        return 1.0
    _wait[0] = 0.0
    _i[0] += 1
    return r if r is not None else None


def render_looks():
    """The test crane in each light look (task 0017), one small render each, side by side."""
    import addon_utils
    addon_utils.enable(pkg(), default_set=True)
    assert bpy.ops.fresing.import_step(filepath=CRANE, quality="normal") == {"FINISHED"}
    sc = bpy.context.scene
    s = sc.fresing
    studio = mod("core.studio")
    cams = mod("blender.cameras")
    sc.camera = cams.add_camera(sc, "LOW", 35.0)
    s.out_format, s.out_custom_w, s.out_custom_h, s.use_gpu, s.out_folder = "custom", 480, 270, False, SCRATCH
    tiles = []
    for look, (label, _icon, _tip) in studio.LOOKS.items():
        bpy.ops.fresing.light_look(look=look)
        t = time.time()
        path = os.path.join(SCRATCH, f"look_{look}.png")
        mod("blender.render").render_still(sc, s, "preview", filepath=path)
        log("look", look, f"{time.time() - t:.0f} s")
        tiles += ["-label", label, path]
    out = os.path.join(OUT, "looks.png")
    subprocess.run(["montage", *tiles, "-tile", "3x2", "-geometry", "+6+6", "-pointsize", "18",
                    "-background", "white", out], check=True)
    subprocess.run(["convert", out, "-strip", "-quality", "92", out], check=True)
    log("saved looks", f"{os.path.getsize(out) // 1024} KB")


def render_crane():
    """A finished render of the test crane, the way a user makes one (background mode, processor)."""
    import addon_utils
    addon_utils.enable(pkg(), default_set=True)
    assert bpy.ops.fresing.import_step(filepath=CRANE, quality="normal") == {"FINISHED"}
    sc = bpy.context.scene
    s = sc.fresing
    joints = mod("blender.joints")
    pin, origin, direction = boom_axis()
    j = joints.create(sc, "ROTATE", [ob("BOOM.ASM")], origin, direction, ref=pin, name="Boom luff")
    joints.create(sc, "SLIDE", [ob("TROLLEY.ASM")], Vector((0.7, 0.3, 0.45)), Vector((1, 0, 0)), name="Trolley",
                  base=ob("BOOM.ASM"))
    joints.set_value(j, math.radians(18))
    s.background = "SKY"
    s.floor = "VISIBLE"
    s.floor_use_own_color = True
    s.floor_color = (0.42, 0.42, 0.4)
    cams = mod("blender.cameras")
    cam = cams.add_camera(sc, "LOW", 35.0, name="Low hero")
    sc.camera = cam
    bpy.context.view_layer.update()
    cams.fit(cam, sc)                        # the raised boom too ("Fit model")
    s.out_format, s.out_resolution, s.use_gpu, s.out_folder = "presentation", "preview", False, SCRATCH
    mod("blender.render").apply_output(sc, s)
    sc.render.resolution_percentage = 100
    t = time.time()
    assert bpy.ops.fresing.render(quality="preview") == {"FINISHED"}
    log("render", s.last_render, f"{time.time() - t:.0f} s")
    path = os.path.join(OUT, "render_crane.jpg")
    subprocess.run(["convert", s.last_render, "-strip", "-quality", "88", path], check=True)
    log("saved render_crane", f"{os.path.getsize(path) // 1024} KB")


if MODE in ("render", "looks"):
    try:
        render_crane() if MODE == "render" else render_looks()
    except Exception:
        log("ERROR", traceback.format_exc())
        sys.exit(1)
else:
    bpy.context.preferences.view.ui_scale = float(os.environ.get("GUIDE_SCALE", "1.5" if MODE == "panels" else "1.0"))
    bpy.context.preferences.system.use_region_overlap = False      # side panel on a plain background
    bpy.app.timers.register(driver, first_interval=4.0, persistent=True)
