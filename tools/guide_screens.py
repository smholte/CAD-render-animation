"""Pictures for the user guide (docs/img/), made in the real app with the generic test crane only.

Three runs; each writes its pictures to $GUIDE_OUT (default docs/img):

  panels   one picture per side-panel section, the rest of the side panel hidden:
      BLENDER_USER_RESOURCES=<user> GUIDE_SHOTS=panels xvfb-run -a -s "-screen 0 1500x7000x24" \\
          blender -p 0 0 1500 7000 --app-template fresing_render --enable-event-simulate --python tools/guide_screens.py
  window   the whole app: at start, after an import, the Help menu, joint arrows in the view:
      BLENDER_USER_RESOURCES=<user> GUIDE_SHOTS=window xvfb-run -a -s "-screen 0 1920x1200x24" \\
          blender -p 0 0 1920 1200 --app-template fresing_render --enable-event-simulate --python tools/guide_screens.py
  update   the update notice at the top of the Fresing tab, and the Help menu (task 0020; no model needed):
      BLENDER_USER_RESOURCES=<user> GUIDE_SHOTS=update FRESING_UPDATE_URL=file:///nothing/index.json \\
          xvfb-run -a -s "-screen 0 1920x1200x24" blender -p 0 0 1920 1200 --app-template fresing_render \\
          --enable-event-simulate --python tools/guide_screens.py
  hover    Add rotate joint with the mouse on the pedestal's bore: the bore lit up with its axis line (task 0088,
      view_hover.png; as "window").
  render   a finished render of the crane (Cycles on the processor):
      BLENDER_USER_RESOURCES=<user> GUIDE_SHOTS=render blender -b --app-template fresing_render \\
          --python tools/guide_screens.py
  looks    the crane in each of the five light looks, side by side (looks.jpg; Cycles on the processor):
      BLENDER_USER_RESOURCES=<user> GUIDE_SHOTS=looks blender -b --app-template fresing_render \\
          --python tools/guide_screens.py
  decals   the crane with a type plate, a warning sticker, a CE mark and text on it (decals.jpg, task 0024):
      BLENDER_USER_RESOURCES=<user> GUIDE_SHOTS=decals blender -b --app-template fresing_render \\
          --python tools/guide_screens.py

  cutaway  the crane with a hatched cut through its pedestal and boom (cutaway.jpg, task 0086; as "decals").

  tour   the Test tour panel (task 0059): the tour made and opened, a few stops marked (as "panels").

  clash  6 Animation > Clash check (task 0065) on the clash test model, checked and its row clicked, and the two
      arms drawn red in the view (as "panels").

  toolchange / toolchange_view   Tool changes (task 0041) on the test gantry: the panels (as "panels") and the
      carousel and the hand in the view (as "window").

  doublearm / doublearm_view   the double-arm tool changer (task 0064) on the test mill with an arm (test_atc.step):
      the Tool changes panel (as "panels") and the arm at its half turn in the view (as "window").

  toolpath / toolpath_view   Milling > Make a toolpath (task 0029) on test_toolpath.step after Make toolpath (as
      "panels"), and the block cut to the end by that program (as "window").

  rotary / rotary_view   the rotary axes (task 0066): the Rotary axes panel on the trunnion (test_5axis.step, as
      "panels") and the 4th axis turning the bar with its wrapped slot cut (test_4axis.step, as "window").

  flex   the hoses (task 0058): the "on" half of view_flex_before_after.jpg (arm up 15 degrees, slide out), view_flex_off.jpg (the same with the
      items switched off = stiff CAD hoses), view_flex_before_after.jpg (those two side by side) and view_flex_chains.jpg
      (the gantry with X, Y, Z moved); Cycles on the processor, as "render".
  flex_panels   the panels of 4 Motion > Hoses and drag chains (panel_4_flex_empty / panel_4_flex / panel_4_flex_chain; as
      "panels", on the hoses model, then the chains model).

GUIDE_ONLY=panel_3_decals,panel_3_faces (comma-separated) makes only those pictures in the "panels" run.

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


def face_facing(o, world_dir):
    """(CAD face, its centre, its normal) – part coordinates – of the biggest face of a part that looks
    along ``world_dir``."""
    import numpy as np
    dec, fm = mod("blender.decals"), mod("blender.faces")
    pos, nrm = dec._mesh_arrays(o.data)
    st = fm.face_starts(o.data)
    rot = o.matrix_world.to_3x3()
    best = None
    for f in range(len(st) - 1):
        p = pos[st[f]:st[f + 1]]
        area = float((0.5 * np.linalg.norm(np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]), axis=1)).sum())
        n = nrm[st[f]:st[f + 1]].reshape(-1, 3).mean(axis=0)
        if (rot @ Vector(n)).normalized().dot(Vector(world_dir)) > 0.9 and (best is None or area > best[0]):
            best = (area, f, p.reshape(-1, 3).mean(axis=0), n / np.linalg.norm(n))
    return best[1], tuple(best[2]), tuple(best[3])


def add_decals():
    """The decals of the guide pictures: text on the boom, a type plate on the base, a warning sign on
    the pedestal, a CE mark on the trolley. Returns the type plate."""
    dec = mod("blender.decals")
    f, c, n = face_facing(ob("BOOM"), (0, -1, 0))
    text = dec.add(ob("BOOM"), f, c, n, "TEXT", text="FRESING")
    text.ink_color = (1.0, 1.0, 1.0)
    dec.fit(text)
    f, c, n = face_facing(ob("BASE"), (0, -1, 0))
    plate = dec.add(ob("BASE"), f, (0.62, c[1], c[2]), n, "STICKER", sticker="TYPE_PLATE")
    plate.plate_company, plate.plate_type, plate.plate_serial = "FRESING", "Test crane TC-1", "SN 0001"
    plate.plate_weight = "350 kg"
    plate.width = 0.16
    f, c, n = face_facing(ob("PEDESTAL"), (0, -1, 0))
    warn = dec.add(ob("PEDESTAL"), f, (c[0], c[1], c[2] + 0.04), n, "STICKER", sticker="WARN_LOAD")
    warn.width = 0.1
    f, c, n = face_facing(ob("TROLLEY"), (0, -1, 0))
    ce = dec.add(ob("TROLLEY"), f, c, n, "STICKER", sticker="CE")
    ce.ink_color = (1.0, 1.0, 1.0)                    # white on the black trolley
    ce.width = 0.07
    return plate


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
    todo = [cls for n, cls in _ORIG.items() if getattr(bpy.types, n, None) is None]
    todo.sort(key=lambda c: bool(getattr(c, "bl_parent_id", "")))      # parents before their sub-panels
    for cls in todo:
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
STATE_TOUR = {}


def step(fn):
    STEPS.append(fn)
    return fn


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


def w_shot_help():
    im = grab_screen()
    scale = bpy.context.preferences.view.ui_scale
    save_png(im[:int(350 * scale), :int(560 * scale)], "help_menu")
    return 0.5


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
        ("panel_3_decals", [("FRESING_PT_decals", False, True)]),
        ("panel_3_xray", [("FRESING_PT_xray", False, True)]),             # the cover in X-ray (task 0073)
        ("panel_4_motion", [("FRESING_PT_motion", False, True)]),
        ("panel_4_poses", [("FRESING_PT_poses", False, True)]),
        ("panel_4_coupling", [("FRESING_PT_motion", False, True)]),     # a wheel follows the trolley
        ("panel_5_scene", [("FRESING_PT_scene", False, True)]),
        ("panel_5_surroundings", [("FRESING_PT_scene", False, True)]),
        ("panel_5_camera", [("FRESING_PT_camera", False, True)]),
        ("panel_5_props", [("FRESING_PT_props", False, True)]),
        ("panel_5_vessel_motion", [("FRESING_PT_vessel_motion", False, True)]),   # task 0085, on the vessel deck
        ("panel_5_output", [("FRESING_PT_output", False, True)]),
        ("panel_5_turntable", [("FRESING_PT_turntable", False, True)]),
        ("panel_5_web3d", [("FRESING_PT_web3d", False, True)]),        # task 0099, after one export
        ("panel_5_shots", [("FRESING_PT_shots", False, True)]),
        ("panel_6_animation", [("FRESING_PT_animation", False, True)]),
        ("panel_6_motor", [("FRESING_PT_animation", False, True)]),     # a Run motor step
        ("panel_6_fade", [("FRESING_PT_animation", False, True)]),      # a Fade out step to X-ray (task 0073)
        ("panel_6_camera_ride", [("FRESING_PT_animation", False, True)]),   # a Ride along camera step (task 0087)
        ("panel_6_sequence", [("FRESING_PT_animation", False, True)]),      # an Assembly sequence step (task 0100)
        ("panel_6_camera_path", [("FRESING_PT_animation", False, True)]),   # a Fly a path camera step (task 0087)
        ("panel_6_trails", [("FRESING_PT_trails", False, True)]),       # a trail line on the trolley, built
        ("panel_7_queue", [("FRESING_PT_queue", False, True)]),
        # the whole side panel with every section closed: the headers show the state of each
        ("sidebar_sections", [(n, True, False) for n in ("FRESING_PT_import", "FRESING_PT_structure",
                                                         "FRESING_PT_looks", "FRESING_PT_motion",
                                                         "FRESING_PT_scene", "FRESING_PT_animation",
                                                         "FRESING_PT_queue")]),
        ("panel_3_cutaway", [("FRESING_PT_cutaway", False, True)]),     # last: its cut joint (task 0086)
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
            elif name == "panel_3_decals":              # decals on the crane, the base (type plate) clicked
                plate = add_decals()
                sc.fresing_decal.active = plate.key
                sc.fresing.pick_mode = "PART"
                select_only(ob("BASE"))
            elif name == "panel_2_structure":
                sc.fresing.pick_mode = "SUBASSEMBLY"
                select_only(ob("BOOM.ASM"))
            elif name in ("panel_4_motion", "panel_4_poses"):
                sc.fresing.pick_mode = "SUBASSEMBLY"
                select_only(ob("BOOM.ASM"))
            elif name == "panel_5_scene":               # a light look picked: its button pressed
                with override():
                    bpy.ops.fresing.light_look(look="PRODUCT")
            elif name == "panel_4_coupling":            # a Ø50 mm wheel rolls along with the trolley
                joints = mod("blender.joints")
                w = ob("WHEEL")
                jw = joints.create(sc, "ROTATE", [w], w.matrix_world.translation, Vector((0, 1, 0)), name="Wheel")
                joints.set_follows(sc, jw, "Trolley", ratio=360.0 / (math.pi * 50))
                joints.set_value(joints.find(sc, "Trolley"), 0.25)
                sc.fresing.joints_index = len(sc.fresing.joints) - 1
                sc.fresing.pick_mode = "SUBASSEMBLY"
                select_only(ob("BOOM.ASM"))
            elif name == "panel_6_motor":               # the cover as a winch drum: a motor, run at 12 rpm
                joints = mod("blender.joints")
                c = ob("COVER")
                centre = sum((c.matrix_world @ Vector(v) for v in c.bound_box), Vector()) / 8.0
                jm = joints.create(sc, "ROTATE", [c], centre, Vector((1, 0, 0)), name="Winch drum")
                joints.set_motor(sc, jm, True)
                a = sc.fresing.animations[0]
                b = a.blocks.add()
                b.kind, b.joint, b.start, b.duration, b.speed_rpm = "MOTOR", "Winch drum", 5.0, 5.0, 12.0
                b.easing, b.ramp = "SMOOTH", 0.5
                a.blocks_index = len(a.blocks) - 1
            elif name == "panel_3_cutaway":             # a hatched plane cut through the pedestal and the boom
                fade = mod("blender.fade")
                fade.remove_look(sc, fade.xray_parts(sc))
                mod("blender.tour").cutaway(sc)
                sc.fresing.pick_mode = "SUBASSEMBLY"
                select_only(ob("PEDESTAL"))
            elif name == "panel_3_xray":                # the cover in X-ray, the cover clicked
                mod("blender.fade").apply_look(sc, [ob("COVER")])
                sc.fresing.pick_mode = "PART"
                select_only(ob("COVER"))
            elif name in ("panel_6_camera_ride", "panel_6_camera_path"):     # task 0087
                a = sc.fresing.animations[0]
                b = a.blocks.add()
                b.kind, b.start, b.duration = "CAMERA", 0.0, 2.0
                if name == "panel_6_camera_ride":
                    boom = ob("BOOM")
                    b.camera_mode, b.ride_level = "RIDE", True
                    b.target_uid, b.target_name = boom["fr_uid"], "BOOM"
                else:
                    cp = mod("blender.camera_path")
                    b.camera_mode, b.path_look, b.duration, b.easing, b.ramp = "PATH", "PART", 5.0, "SMOOTH", 1.0
                    for p in cp.from_cameras(sc):
                        b.path_points.add().co = p
                    cp.show_path(sc, b)
                    trolley = ob("TROLLEY")
                    b.aim_uid, b.aim_name = trolley["fr_uid"], "TROLLEY"
                a.blocks_index = len(a.blocks) - 1
            elif name == "panel_6_sequence":            # Take apart the boom, outside in, along its +Z, trail lines
                if not sc.fresing.animations:
                    sc.fresing.animations.add().name = "Animation"
                a = sc.fresing.animations[0]
                b = a.blocks.add()
                boom = ob("BOOM.ASM")
                b.kind, b.start, b.seq_id = "SEQUENCE", 0.0, "guide"
                b.target_uid, b.target_name = boom["fr_uid"], "BOOM.ASM"
                b.seq_trails = True
                mod("blender.sequence").count(sc, b)
                a.blocks_index = len(a.blocks) - 1
            elif name in ("panel_6_fade", "panel_6_trails"):
                fade = mod("blender.fade")
                fade.remove_look(sc, fade.xray_parts(sc))
                if not sc.fresing.animations:
                    a = sc.fresing.animations.add()
                    a.name = "Animation"
                a = sc.fresing.animations[0]
                c = ob("COVER")
                if name == "panel_6_fade":
                    b = a.blocks.add()
                    b.kind, b.start, b.duration = "FADE_OUT", 1.0, 1.5
                    b.target_uid, b.target_name = c["fr_uid"], "COVER"
                    b.fade_xray = True
                    a.blocks_index = len(a.blocks) - 1
                else:
                    trails = mod("blender.trails")
                    t = trails.add(sc, ob("TROLLEY"))
                    t.animation = a.name
                    mod("blender.animation").bake(sc, a)
                    sc.frame_set(1)
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
            elif name == "panel_5_vessel_motion":       # on, a beam sea, the trolley kept still
                sc.fresing.env_detail = "DETAILED"
                sc.fresing.background = "DECK"
                v = sc.fresing.vessel
                v.heading = "BEAM"
                v.enabled = True
                mod("blender.vessel_motion").add_marks(sc, [ob("TROLLEY.ASM")], "STILL")
                sc.frame_set(60)
            elif name == "panel_5_web3d":               # exported once: the result line and its buttons show
                mod("blender.web3d").export(sc, os.path.join(tempfile.mkdtemp(), "Crane web 3D.glb"))
            elif name == "panel_5_output":              # back to the studio for the rest
                sc.fresing.vessel.enabled = False
                sc.frame_set(1)
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

    _only = [n.strip() for n in os.environ.get("GUIDE_ONLY", "").split(",") if n.strip()]
    for _name, _spec in SHOTS:
        if _only and _name not in _only:
            continue
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

    step(w_help_menu)
    step(w_shot_help)

elif MODE == "hover":
    # the hover highlight (task 0088): Add rotate joint, the mouse on the pedestal's bore (the boom and its pin
    # hidden), the bore lit up with its axis line

    step(_start)
    step(_import)
    step(_wait_import)

    @step
    def h_view():
        sc = bpy.context.scene
        for o in [ob("BOOM.ASM")] + list(ob("BOOM.ASM").children_recursive):
            o.hide_set(True)
        select_only(ob("PEDESTAL"))
        with override():
            bpy.ops.view3d.view_selected()
        win, area, region, sb = areas()
        region.data.view_distance *= 1.6
        select_only()
        sc.fresing.show_joints = False
        return 1.5

    _HOVER_SPOT = []

    @step
    def h_pick():
        from bpy_extras import view3d_utils
        win, area, region, sb = areas()
        with override():
            res = bpy.ops.fresing.joint_pick_axis("INVOKE_DEFAULT", mode="NEW", kind="ROTATE",
                                                  movers=ob("BOOM.ASM").name)
        log("pick", res)
        # a spot on the far wall of the front lug's bore (axis x 0.1, z 0.4, along Y, Ø40.4)
        ped = ob("PEDESTAL")
        y0 = min((ped.matrix_world @ Vector(c)).y for c in ped.bound_box)
        view = region.data.view_rotation @ Vector((0, 0, -1))
        r = Vector((view.x, 0, view.z)).normalized()
        best = None
        for dy in (0.004, 0.008, 0.012, 0.016):
            p = Vector((0.1, y0 + dy, 0.4)) + r * 0.0195
            co = view3d_utils.location_3d_to_region_2d(region, region.data, p)
            if co is None:
                continue
            x, y = int(region.x + co.x), int(region.y + co.y)
            o = view3d_utils.region_2d_to_origin_3d(region, region.data, (x - region.x, y - region.y))
            d = view3d_utils.region_2d_to_vector_3d(region, region.data, (x - region.x, y - region.y))
            h = mod("blender.hover").look(bpy.context.scene, bpy.context.evaluated_depsgraph_get(), o, d)
            log("try", dy, h.kind, h.text)
            if h.kind == "hole":
                best = (x, y)
                break
        if best is None:
            w = ob("WHEEL")
            best = tuple(int(v) for v in to_window_xy(region, w.matrix_world.translation + Vector((0, 0, 0.024))))
        _HOVER_SPOT[:] = [best]
        win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=best[0], y=best[1])
        return 1.5

    def to_window_xy(region, pt):
        from bpy_extras import view3d_utils
        co = view3d_utils.location_3d_to_region_2d(region, region.data, pt)
        return region.x + co.x, region.y + co.y

    @step
    def h_shot():
        win, area, region, sb = areas()
        log("hover", mod("blender.hover").current())
        im = grab_screen()
        x, y = _HOVER_SPOT[0]
        hgt, wid = im.shape[:2]
        top = hgt - y                                   # screen rows from the top
        y0, y1 = max(0, top - 190), min(hgt, top + 210)
        x0, x1 = max(0, x - 330), min(wid, x + 470)
        save_png(im[y0:y1, x0:x1], "view_hover")
        # a flat face too (the top of the front lug): only for checking, not in the guide
        ped = ob("PEDESTAL")
        bb = [ped.matrix_world @ Vector(c) for c in ped.bound_box]
        top_pt = Vector((0.1, min(c.y for c in bb) + 0.01, max(c.z for c in bb)))
        fx, fy = (int(v) for v in to_window_xy(region, top_pt))
        _HOVER_SPOT.append((fx, fy))
        win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=fx, y=fy)
        return 1.0

    @step
    def h_shot_flat():
        win, area, region, sb = areas()
        log("hover flat", mod("blender.hover").current())
        im = grab_screen()
        x, y = _HOVER_SPOT[1]
        top = im.shape[0] - y
        path = os.path.join(SCRATCH, "hover_flat.png")
        sub = im[max(0, top - 200):top + 200, max(0, x - 330):x + 470]
        subprocess.run(["convert", "-size", f"{sub.shape[1]}x{sub.shape[0]}", "-depth", "8", "rgb:-", path],
                       input=sub.tobytes(), check=True)
        log("saved (not for the guide)", path)
        win.event_simulate(type="ESC", value="PRESS", x=x, y=y)
        win.event_simulate(type="ESC", value="RELEASE", x=x, y=y)
        return 0.5

elif MODE == "update":

    step(_start)

    def _update_state(kind):
        upd = mod("blender.updates")
        upd.INSTALLED = "0.2.15"                   # the picture shows a plausible pair of versions
        upd._check.clear()
        upd._status.clear()
        if kind == "available":
            upd._check.update(state="available", version="0.2.16", date="12 Nov 2026", size=48_700_000,
                              release_page=mod("core.updates").RELEASES_PAGE, changes=[])
        else:
            upd._check.update(state="none", version="0.2.16")
            upd._status.update(ok=True, message="Updated to 0.2.16.", **{"from": "0.2.15"}, to="0.2.16", changes=[
                {"version": "0.2.16", "title": "an example", "text": "- What changed in this version, in plain "
                                                                     "words, as in the changelog."}])

    @step
    def u_available():
        _update_state("available")
        show_only([("FRESING_PT_update", False, True), ("FRESING_PT_import", True, True)])
        wiggle()
        return 2.5

    @step
    def u_shot_available():
        shoot_sidebar("panel_update")
        return 0.5

    @step
    def u_done():
        _update_state("done")
        show_only([("FRESING_PT_update", False, True), ("FRESING_PT_import", True, True)])
        wiggle()
        return 2.5

    @step
    def u_shot_done():
        shoot_sidebar("panel_update_done")
        return 0.5

    @step
    def u_menu_scale():
        restore_panels()
        mod("blender.updates")._status.clear()
        bpy.context.preferences.view.ui_scale = 1.0        # as the help_menu picture of the "window" run
        redraw_all()
        return 2.0

    step(w_help_menu)
    step(w_shot_help)

elif MODE in ("waycover", "air", "labels", "coolant", "flex_panels", "flex_chains_panel"):
    # task 0044: panels that had no picture yet. Each run uses its own generic test model.
    #   waycover: Way covers panel with two covers + the covers in the view (test_waycover_c.step, task 0035)
    #   air:      CNC machine with Air blast open, and the G-code step with "Blow the part clean" (test_gantry.step)
    #   labels:   Labels, Pictures and Music folds (test crane)
    #   coolant:  CNC machine > Coolant (task 0042) and the G-code step with its coolant line (test_gantry.step)
    # Same command as "panels" (xvfb 1500x7000), with GUIDE_SHOTS=waycover / air / labels.
    MILL = os.path.join(DATA, "test_gantry.step")
    WCOVER = os.path.join(DATA, "test_waycover_c.step")
    mod_name = {"waycover": WCOVER, "air": MILL, "labels": CRANE, "coolant": MILL,
                "flex_panels": os.path.join(DATA, "test_flex_hoses_a.step"),
                "flex_chains_panel": os.path.join(DATA, "test_flex_chains_a.step")}[MODE]

    step(_start)
    step(lambda: _import(mod_name))
    step(_wait_import)

    def _grab(name, spec, extra=None):
        def show():
            if extra:
                extra()
            show_only(spec)
            wiggle()
            return 2.5

        def shoot():
            shoot_sidebar(name)
            return 0.5
        show.__name__, shoot.__name__ = f"show_{name}", f"shoot_{name}"
        step(show)
        step(shoot)

    def _named(n):
        return next(o for o in bpy.data.objects if o.get("fr_name") == n)

    if MODE == "waycover":
        def _wc_setup():
            sc = bpy.context.scene
            with override():
                mod("blender.waycover").set_up_test_model(sc, carriage=True)   # 'X left' + 'X right', carriage sections
            sc.fresing.waycovers_index = 0
            select_only()
            mod("blender.joints").set_value(sc.fresing.joints.get("X axis"), 0.3)
            bpy.context.view_layer.update()
        step(lambda: (_wc_setup(), 1.0)[1])
        _grab("panel_4_waycover", [("FRESING_PT_waycover", False, True)])

        def _view():
            areas()[1].spaces.active.overlay.show_overlays = False       # like the app's own view: no grid, axes, cursor
            _frame_model()
            wiggle(5)
            return 2.0
        step(_view)

        def _view_shot():
            win, area, region, sb = areas()
            im = crop_region(grab_screen(), region, win.height)
            h, w = im.shape[:2]
            save_png(im[int(h * 0.463):int(h * 0.545), int(w * 0.2):int(w * 0.8)], "view_waycover")   # the model
            return 0.5
        step(_view_shot)

    elif MODE in ("flex_panels", "flex_chains_panel"):
        # task 0058: 4 Motion > Hoses and drag chains: empty, with the four hoses (the first one chosen), a chain chosen
        def _flex_empty():
            select_only()
            return 1.0
        def _flex_setup():
            sc = bpy.context.scene
            fx = mod("blender.flex")
            with override():
                if MODE == "flex_panels":
                    fx.set_up_test_hoses(sc)
                else:
                    fx.set_up_test_chains(sc)
            sc.fresing.flex_index = 0
            select_only()
            mod("blender.ui")._OPEN_FOLDS = True
            return 1.0
        if MODE == "flex_panels":
            step(_flex_empty)
            _grab("panel_4_flex_empty", [("FRESING_PT_flex", False, True)])
        step(_flex_setup)
        _grab("panel_4_flex" if MODE == "flex_panels" else "panel_4_flex_chain", [("FRESING_PT_flex", False, True)])

    elif MODE == "coolant":
        def _cool_setup():
            sc = bpy.context.scene
            joints = mod("blender.joints")
            for name, asm, d in (("Y", "Y.ASM", (0, 1, 0)), ("X", "X.ASM", (1, 0, 0)), ("Z", "Z.ASM", (0, 0, 1))):
                o = _named(asm)
                joints.create(sc, "SLIDE", [o], o.matrix_world.translation, Vector(d), name=name)
            with override():
                bpy.ops.fresing.cnc_find_axes()
                select_only(_named("TOOL T1 FLAT D6"))
                bpy.ops.fresing.cnc_use_tool()
                select_only(_named("STOCK 300x200x30"))
                bpy.ops.fresing.cnc_use_workpiece()
            select_only()
            sc.fresing.coolant.enabled = True
            mod("blender.ui")._OPEN_FOLDS = True
        step(lambda: (_cool_setup(), 1.0)[1])
        _grab("panel_4_coolant", [("FRESING_PT_cnc_coolant", False, True)])

        def _gcode_step():
            sc = bpy.context.scene
            os.chdir(SCRATCH)                    # plain file names in the picture
            path = "pocket.ngc"
            with open(path, "w") as fh:
                fh.write("%\nG21 G90 G54\nS9000 M3\nG0 X20 Y20 Z5\nM8\nG1 Z-2 F600\nG1 X120 F1500\nM9\nM30\n%\n")
            with override():
                bpy.ops.fresing.anim_add()
                bpy.ops.fresing.block_add(kind="GCODE")
            a = mod("blender.animation").active(sc)
            b = a.blocks[a.blocks_index]
            b.gcode_file = path
        _grab("panel_6_gcode_coolant", [("FRESING_PT_animation", False, True)], _gcode_step)

    elif MODE == "air":
        def _cnc_setup():
            sc = bpy.context.scene
            joints = mod("blender.joints")
            for name, asm, d in (("Y", "Y.ASM", (0, 1, 0)), ("X", "X.ASM", (1, 0, 0)), ("Z", "Z.ASM", (0, 0, 1))):
                o = _named(asm)
                joints.create(sc, "SLIDE", [o], o.matrix_world.translation, Vector(d), name=name)
            with override():
                bpy.ops.fresing.cnc_find_axes()
                select_only(_named("TOOL T1 FLAT D6"))
                bpy.ops.fresing.cnc_use_tool()
                select_only(_named("STOCK 300x200x30"))
                bpy.ops.fresing.cnc_use_workpiece()
            select_only()
            cnc = sc.fresing.cnc
            cnc.air_on_code, cnc.air_off_code = 7, 9
            mod("blender.ui")._OPEN_FOLDS = True
        step(lambda: (_cnc_setup(), 1.0)[1])
        _grab("panel_4_air", [("FRESING_PT_cnc", False, True)])

        def _gcode_step():
            sc = bpy.context.scene
            os.chdir(SCRATCH)                    # plain file names in the picture
            path = "pocket.ngc"
            with open(path, "w") as fh:
                fh.write("%\nG21 G90 G54\nS9000 M3 M7\nG0 X20 Y20 Z5\nG1 Z-2 F600\nG1 X120 F1500\nM9\nM30\n%\n")
            with override():
                bpy.ops.fresing.anim_add()
                bpy.ops.fresing.block_add(kind="GCODE")
            a = mod("blender.animation").active(sc)
            b = a.blocks[a.blocks_index]
            b.gcode_file = path
            b.gcode_clean = True
        _grab("panel_6_gcode_air", [("FRESING_PT_animation", False, True)], _gcode_step)

    else:
        def _label_setup():
            sc = bpy.context.scene
            s = sc.fresing
            with override():
                bpy.ops.fresing.callout_add(part=_named("BOOM").name, text="Boom, Ø40")
                bpy.ops.fresing.callout_add(part=_named("TROLLEY").name, text="Trolley")
                bpy.ops.fresing.anim_add()
            a = s.animations[s.animations_index]
            os.chdir(SCRATCH)                    # plain file names in the pictures
            logo = "logo.png"
            subprocess.run(["convert", "-size", "160x80", "xc:#2c7fb8", logo], check=True)
            wav = "music.wav"
            import wave
            with wave.open(wav, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(22050)
                w.writeframes(b"\0\0" * 22050)
            with override():
                bpy.ops.fresing.card_add(filepath=logo)
            c = a.cards[0]
            c.mode, c.corner, c.start, c.duration, c.caption = "CORNER", "BL", 0.0, 3.0, "Hydraulics"
            a.music_on, a.music_file = True, wav
            a.music_fade_in, a.music_fade_out = 1.0, 2.0
        step(lambda: (_label_setup(), 1.0)[1])
        _grab("panel_5_labels", [("FRESING_PT_labels", False, True)])
        _grab("panel_6_cards", [("FRESING_PT_cards", False, True)])
        _grab("panel_6_music", [("FRESING_PT_music", False, True)])

elif MODE in ("toolchange", "toolchange_view"):
    # task 0041: Tool changes (manual and ATC) on the test gantry; "toolchange" = the panels (xvfb 1500x7000),
    # "toolchange_view" = the carousel and the hand in the view (xvfb 1920x1200, as "window").
    TC_PROGRAM = ("(T1 D=6. CR=0. - flat end mill)\n(T2 D=4. CR=2. - ball end mill)\n"
                  "(T3 D=5. CR=0. TAPER=118deg - drill)\n(T4 D=8. CR=1. - bullnose end mill)\n"
                  "G21 G90\nG0 X10 Y0 Z5\nT2 M6\nG1 X20 F600\nT3 M6\nG0 X30 Y10 Z5\nT4 M6\nG0 X40 Y20 Z5\n"
                  "T1 M6\nG0 X0 Y0 Z5\nM30\n")
    step(_start)
    step(lambda: _import(os.path.join(DATA, "test_gantry.step")))
    step(_wait_import)

    def _named(n):
        return next(o for o in bpy.data.objects if o.get("fr_name") == n)

    def _tc_setup():
        sc = bpy.context.scene
        joints, tools = mod("blender.joints"), mod("blender.tools")
        for name, asm, d in (("Y", "Y.ASM", (0, 1, 0)), ("X", "X.ASM", (1, 0, 0)), ("Z", "Z.ASM", (0, 0, 1))):
            o = _named(asm)
            joints.create(sc, "SLIDE", [o], o.matrix_world.translation, Vector(d), name=name)
        joints.create(sc, "ROTATE", [_named("CAROUSEL.ASM")], Vector((0.5, 0, 0)), Vector((0, 0, 1)),
                      name="Carousel")
        with override():
            bpy.ops.fresing.cnc_find_axes()
            select_only(_named("TOOL T1 FLAT D6"))
            bpy.ops.fresing.cnc_use_tool()
            select_only(_named("STOCK 300x200x30"))
            bpy.ops.fresing.cnc_use_workpiece()
        select_only()
        os.chdir(SCRATCH)                    # plain file names in the pictures
        with open("parts.ngc", "w") as fh:
            fh.write(TC_PROGRAM)
        with override():
            bpy.ops.fresing.anim_add()
            bpy.ops.fresing.block_add(kind="GCODE")
        a = mod("blender.animation").active(sc)
        b = a.blocks[a.blocks_index]
        b.gcode_file = "parts.ngc"
        mod("blender.gcode").tools_from_program(sc, b)
        for n, part, length in ((1, "TOOL T1 FLAT D6", 30), (2, "TOOL T2 BALL D4", 30), (3, "TOOL T3 DRILL D5", 40),
                                (4, None, 30)):
            row = tools.row_of(sc, n)
            if part:
                tools.use_part(sc, row, _named(part))
            row.length = length * 0.001
        tools.row_of(sc, 1).pocket = 7
        cnc = sc.fresing.cnc
        cnc.change_mode = "Z"
        cnc.change_pos = (0.0, 0.0, 0.06)
        b.gcode_hand = True
        b.gcode_tc_caption = True
        mod("blender.ui")._OPEN_FOLDS = True

    def _atc():
        sc = bpy.context.scene
        tc = mod("blender.toolchange")
        cnc = sc.fresing.cnc
        cnc.changer = "ATC"
        cnc.carousel_joint = "Carousel"
        tc.add_pocket(sc, _named("CAROUSEL DISC"), Vector((0.56, 0, 0.14)))
        cnc.pocket_count = 8
        tc.fill_carousel(sc)
        cnc.pockets_index = 3

    def _grab(name, spec, extra=None):
        def show():
            if extra:
                extra()
            show_only(spec)
            wiggle()
            return 2.5

        def shoot():
            shoot_sidebar(name)
            return 0.5
        show.__name__, shoot.__name__ = f"show_{name}", f"shoot_{name}"
        step(show)
        step(shoot)

    step(lambda: (_tc_setup(), 1.0)[1])
    if MODE == "toolchange":
        _grab("panel_4_toolchange_manual", [("FRESING_PT_cnc_changes", False, True)])
        _grab("panel_6_gcode_toolchange", [("FRESING_PT_animation", False, True)])
        step(lambda: (_atc(), 1.0)[1])
        _grab("panel_4_toolchange_atc", [("FRESING_PT_cnc_changes", False, True)])
    else:
        def _look(at, dist, rot):
            win, area, region, _sb = areas()
            sp = area.spaces.active
            sp.overlay.show_overlays = False
            r3d = sp.region_3d
            r3d.view_perspective = "PERSP"
            r3d.view_location = Vector(at)
            r3d.view_distance = dist
            from mathutils import Euler
            r3d.view_rotation = Euler([math.radians(x) for x in rot]).to_quaternion()
            wiggle(5)

        def _view_shot(name):
            def shot():
                win, area, region, _sb = areas()
                im = crop_region(grab_screen(), region, win.height)
                h, w = im.shape[:2]
                save_png(im[int(h * 0.12):int(h * 0.88), int(w * 0.18):int(w * 0.82)], name)
                return 0.5
            shot.__name__ = f"shot_{name}"
            return shot

        def _hand_frame():
            sc = bpy.context.scene
            for o in list(bpy.context.view_layer.objects):
                o.select_set(False)
            animation, gcode, core = mod("blender.animation"), mod("blender.gcode"), mod("core.gcode")
            a = animation.active(sc)
            animation.bake(sc, a)
            b = a.blocks[0]
            mach = gcode.Machine(sc)
            sch = core.Schedule(gcode.read_program(sc, b, mach, start=gcode.start_point(mach))[0],
                                gcode.timing(sc, a, b, mach))
            c = sch.changes[0]
            keys = mod("core.toolchange").hand_keys(*c.hand)
            t = next(t for t, p in keys if p == "grip") + 0.25        # pulling the old tool out
            sc.frame_set(int(1 + t * int(a.fps)))
            tip = _named("TOOL T1 FLAT D6").matrix_world.translation
            _look((tip.x, tip.y - 0.05, 0.11), 0.75, (68, 0, 28))
            return 2.0

        def _atc_frame():
            sc = bpy.context.scene
            animation, gcode, core = mod("blender.animation"), mod("blender.gcode"), mod("core.gcode")
            animation.clear_keys(sc)
            _atc()
            a = animation.active(sc)
            animation.bake(sc, a)
            b = a.blocks[0]
            mach = gcode.Machine(sc)
            sch = core.Schedule(gcode.read_program(sc, b, mach, start=gcode.start_point(mach))[0],
                                gcode.timing(sc, a, b, mach))
            c = sch.changes[1]
            turn = c.turns()[-1]
            t = (turn[0] + turn[1]) / 2                                 # the carousel turning to the new pocket
            sc.frame_set(int(1 + t * int(a.fps)))
            _look((0.53, 0.0, 0.13), 0.42, (86, 0, 28))
            return 2.0

        step(_hand_frame)
        step(_view_shot("view_toolchange_hand"))
        step(_atc_frame)
        step(_view_shot("view_toolchange_atc"))

elif MODE in ("doublearm", "doublearm_view"):
    # task 0064: the double-arm changer on the test mill with an arm; "doublearm" = the Tool changes panel (xvfb
    # 1500x7000), "doublearm_view" = the arm at its half turn in the view (xvfb 1920x1200, as "window").
    step(_start)
    step(lambda: _import(os.path.join(DATA, "test_atc.step")))
    step(_wait_import)

    def _arm_setup():
        sc = bpy.context.scene
        os.chdir(SCRATCH)                    # plain file names in the pictures
        dbl = mod("blender.doublearm")
        with open("parts.ngc", "w") as fh:
            fh.write(dbl.TEST_PROGRAM)
        with override():
            bpy.ops.fresing.anim_add()
            bpy.ops.fresing.block_add(kind="GCODE")
        a = mod("blender.animation").active(sc)
        b = a.blocks[a.blocks_index]
        b.gcode_file = "parts.ngc"
        dbl.set_up_test_model(sc, b)
        dbl.LAST_CHECK[:] = dbl.check(sc)
        sc.fresing.cnc.pockets_index = 1
        select_only()

    step(lambda: (_arm_setup(), 1.0)[1])
    if MODE == "doublearm":
        def _show_arm():
            show_only([("FRESING_PT_cnc_changes", False, True)])
            wiggle()
            return 2.5

        def _shoot_arm():
            shoot_sidebar("panel_4_toolchange_arm")
            return 0.5
        step(_show_arm)
        step(_shoot_arm)
    else:
        def _arm_frame():
            sc = bpy.context.scene
            animation, gcode, core = mod("blender.animation"), mod("blender.gcode"), mod("core.gcode")
            a = animation.active(sc)
            animation.bake(sc, a)
            b = a.blocks[0]
            mach = gcode.Machine(sc)
            sch = core.Schedule(gcode.read_program(sc, b, mach, start=gcode.start_point(mach))[0],
                                gcode.timing(sc, a, b, mach))
            c = next(x for x in sch.changes if x.kind == "arm")
            t = c.arm_times()
            f = 1 + (t["swap"][0] + (t["swap"][1] - t["swap"][0]) * 0.4) * int(a.fps)
            sc.frame_set(int(f), subframe=f - int(f))
            win, area, region, _sb = areas()
            sp = area.spaces.active
            sp.overlay.show_overlays = False
            r3d = sp.region_3d
            r3d.view_perspective = "PERSP"
            r3d.view_location = Vector((-0.15, 0.0, 0.27))
            r3d.view_distance = 0.75
            from mathutils import Euler
            r3d.view_rotation = Euler([math.radians(x) for x in (72, 0, 24)]).to_quaternion()
            wiggle(5)
            return 2.0

        def _arm_shot():
            win, area, region, _sb = areas()
            im = crop_region(grab_screen(), region, win.height)
            h, w = im.shape[:2]
            save_png(im[int(h * 0.12):int(h * 0.88), int(w * 0.18):int(w * 0.82)], "view_toolchange_arm")
            return 0.5
        step(_arm_frame)
        step(_arm_shot)

elif MODE in ("rotary", "rotary_view"):
    # task 0066: "rotary" = 4 Motion > CNC machine > Rotary axes on the trunnion after Check (xvfb 1500x7000);
    # "rotary_view" = the 4th axis turning the bar, the wrapped slot cut and the toolpath on it (xvfb 1920x1200)
    five = MODE == "rotary"
    step(_start)
    step(lambda: _import(os.path.join(DATA, "test_5axis.step" if five else "test_4axis.step")))
    step(_wait_import)

    def _rot_setup():
        sc = bpy.context.scene
        os.chdir(SCRATCH)
        rot = mod("blender.rotary")
        with open("parts.ngc", "w") as fh:
            fh.write(rot.TEST_PROGRAM_5AXIS if five else rot.TEST_PROGRAM_4AXIS)
        with override():
            bpy.ops.fresing.anim_add()
            bpy.ops.fresing.block_add(kind="GCODE")
        a = mod("blender.animation").active(sc)
        b = a.blocks[a.blocks_index]
        b.gcode_file = "parts.ngc"
        b.gcode_speed, b.gcode_fit = "FIT", 12.0
        b.gcode_path = True
        rot.set_up_test_model(sc, b, five=five, milling=not five)
        rot.check(sc)
        select_only()

    step(lambda: (_rot_setup(), 1.0)[1])
    if five:
        def _show_rot():
            show_only([("FRESING_PT_cnc_rotary", False, True)])
            wiggle()
            return 2.5

        def _shoot_rot():
            shoot_sidebar("panel_4_rotary")
            return 0.5
        step(_show_rot)
        step(_shoot_rot)
    else:
        def _rot_frame():
            sc = bpy.context.scene
            animation, machining = mod("blender.animation"), mod("blender.machining")
            gcode, core = mod("blender.gcode"), mod("core.gcode")
            a = animation.active(sc)
            animation.bake(sc, a)
            machining.sample(sc)
            b = a.blocks[0]
            mach = gcode.Machine(sc)
            sch = core.Schedule(gcode.read_program(sc, b, mach, start=gcode.start_point(mach))[0],
                                gcode.timing(sc, a, b, mach))
            # halfway through G0 A180: the slot wrapped round, the first flat cut, the bar turned 90°
            p = next(p for p in sch.pieces if p.move.kind == "RAPID" and abs(p.move.rb[0] - 180.0) < 1e-6
                     and abs(p.move.ra[0]) < 1e-6)
            f = int(1 + (p.v0 + p.vd * 0.5) * int(a.fps))
            sc.frame_set(f)
            machining.refresh(sc, frame=f, force=True)
            win, area, region, _sb = areas()
            sp = area.spaces.active
            sp.overlay.show_overlays = False
            sp.shading.type = "SOLID"
            r3d = sp.region_3d
            r3d.view_perspective = "PERSP"
            r3d.view_location = Vector((-0.04, 0.0, 0.155))
            r3d.view_distance = 0.30
            from mathutils import Euler
            r3d.view_rotation = Euler([math.radians(x) for x in (66, 0, 28)]).to_quaternion()
            wiggle(5)
            return 2.0

        def _rot_shot():
            win, area, region, _sb = areas()
            im = crop_region(grab_screen(), region, win.height)
            h, w = im.shape[:2]
            save_png(im[int(h * 0.12):int(h * 0.88), int(w * 0.18):int(w * 0.82)], "view_rotary")
            return 0.5
        step(_rot_frame)
        step(_rot_shot)

elif MODE == "tour":
    # task 0059: the Test tour panel (Help > Make test tour project, then open it). Same command as "panels"
    # (xvfb 1500x7000), with GUIDE_SHOTS=tour. The tour is made in the scratch folder; two stops marked, stop 7 picked.
    step(_start)

    def _tour_make():
        folder = os.path.join(SCRATCH, "Test tour")
        STATE_TOUR["folder"] = folder
        with override():
            res = bpy.ops.fresing.tour_make(folder=folder, in_place=True)
        log("tour made", res)
        tour = mod("blender.tour")
        version = __import__("importlib").import_module(pkg()).__version__
        STATE_TOUR["version"] = version
        for p in (tour.results_path(folder, version),):
            if os.path.isfile(p):
                os.remove(p)
        with override():
            bpy.ops.fresing.tour_open(filepath=tour.hub_path(folder, version))
        return 3.0
    step(_tour_make)

    def _tour_marks():
        tour = mod("blender.tour")
        folder, version = STATE_TOUR["folder"], STATE_TOUR["version"]
        for sid in ("materials", "faces", "decals", "cut_look", "sea", "looks"):
            tour.mark(folder, version, sid, state=tour.OK_STATE)
        tour.mark(folder, version, "stack", state=tour.PROBLEM)
        tour.mark(folder, version, "stack", note="the trolley stops 1 frame late")
        data = tour.load_results(folder, version)
        data["current"] = "stack"
        tour.save_results(folder, version, data)
        show_only([("FRESING_PT_tour", False, True)])
        wiggle()
        return 2.5
    step(_tour_marks)
    step(lambda: (shoot_sidebar("panel_tour"), 0.5)[1])

elif MODE == "clash":
    # task 0065: 6 Animation > Clash check on the clash test model (test_clash.step): built, checked, the row clicked;
    # and the two arms drawn red in the view. Same command as "panels" (xvfb 1500x7000), with GUIDE_SHOTS=clash.
    step(_start)
    step(lambda: _import(os.path.join(DATA, "test_clash.step")))
    step(_wait_import)

    def _clash_setup():
        sc = bpy.context.scene
        a = sc.fresing.animations.add()
        a.name, a.tail, a.fps = "Arms meet", 0.0, "25"
        mod("blender.tour").clash_arms(sc, a)
        sc.fresing.animations_index = len(sc.fresing.animations) - 1
        with override():
            bpy.ops.fresing.anim_build()
            bpy.ops.fresing.clash_check()
        sc.fresing.clash.use_near = True
        with override():
            bpy.ops.fresing.clash_check()
        sc.fresing.clash.rows_index = 0                  # a click on the row: frame, selection, red
        show_only([("FRESING_PT_clash", False, True)])
        wiggle()
        return 2.5
    step(_clash_setup)
    step(lambda: (shoot_sidebar("panel_6_clash"), 0.5)[1])

    def _clash_view():
        restore_panels()
        areas()[1].spaces.active.overlay.show_overlays = False
        with override():
            bpy.ops.view3d.view_selected()
        wiggle(5)
        return 2.0
    step(_clash_view)

    def _clash_view_shot():
        win, area, region, sb = areas()
        im = crop_region(grab_screen(), region, win.height)
        h, w = im.shape[:2]
        save_png(im[int(h * 0.455):int(h * 0.535), int(w * 0.15):int(w * 0.80)], "view_clash")
        return 0.5
    step(_clash_view_shot)

elif MODE in ("toolpath", "toolpath_view"):
    # task 0029: 4 Motion > Milling > Make a toolpath on the toolpath test model, made (as "panels", xvfb 1500x7000);
    # "toolpath_view" = the block cut to the end by the program the app made (xvfb 1920x1200)
    step(_start)
    step(lambda: _import(os.path.join(DATA, "test_toolpath.step")))
    step(_wait_import)

    def _tp_setup():
        sc = bpy.context.scene
        tp = mod("blender.toolpath")
        tp.set_up_test_model(sc)
        with override():
            bpy.ops.fresing.anim_add()
        tp.make(sc, os.path.join(SCRATCH, "toolpath.ngc"))
        select_only()
        return 1.0
    step(_tp_setup)
    if MODE == "toolpath":
        def _show_tp():
            show_only([("FRESING_PT_milling_toolpath", False, True)])
            wiggle()
            return 2.5
        step(_show_tp)
        step(lambda: (shoot_sidebar("panel_4_toolpath"), 0.5)[1])
    else:
        def _tp_frame():
            sc = bpy.context.scene
            animation, machining = mod("blender.animation"), mod("blender.machining")
            a = animation.active(sc)
            animation.bake(sc, a)
            machining.sample(sc)
            sc.frame_set(sc.frame_end)
            machining.refresh(sc, frame=sc.frame_end, force=True)
            p = mod("blender.gcode").path_object()
            if p is not None:
                p.hide_viewport = True
            for o in sc.objects:
                if o.get("fr_name") in ("SPINDLE", "END MILL D10", "CARRIAGE", "COLUMN") or o.get("fr_cnc") == "tool":
                    o.hide_viewport = True
            win, area, region, _sb = areas()
            sp = area.spaces.active
            sp.overlay.show_overlays = False
            sp.shading.type = "SOLID"
            r3d = sp.region_3d
            r3d.view_perspective = "PERSP"
            wp = machining.settings(sc).workpiece
            r3d.view_location = wp.matrix_world @ Vector((0.0, 0.0, 0.055))
            r3d.view_distance = 0.26
            from mathutils import Euler
            r3d.view_rotation = Euler([math.radians(x) for x in (55, 0, 30)]).to_quaternion()
            wiggle(5)
            return 2.0

        def _tp_shot():
            win, area, region, _sb = areas()
            im = crop_region(grab_screen(), region, win.height)
            h, w = im.shape[:2]
            save_png(im[int(h * 0.15):int(h * 0.85), int(w * 0.2):int(w * 0.8)], "view_toolpath")
            return 0.5
        step(_tp_frame)
        step(_tp_shot)

elif MODE in ("render", "looks", "decals"):
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
    sheet = os.path.join(SCRATCH, "looks.png")
    subprocess.run(["montage", *tiles, "-tile", "3x2", "-geometry", "+6+6", "-pointsize", "18",
                    "-background", "white", sheet], check=True)
    out = os.path.join(OUT, "looks.jpg")
    subprocess.run(["convert", sheet, "-strip", "-quality", "86", out], check=True)
    log("saved looks", f"{os.path.getsize(out) // 1024} KB")


def render_crane(with_decals: bool = False, with_cut: bool = False):
    """A finished render of the test crane, the way a user makes one (background mode, processor);
    with decals on it for the picture of 3 Looks > Logos & stickers; with a hatched cut through the pedestal and the
    boom for 3 Looks > Cutaway (task 0086)."""
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
    if with_decals:
        add_decals()
    cams = mod("blender.cameras")
    cam = cams.add_camera(sc, "LOW", 35.0, name="Low hero")
    if with_cut:
        mod("blender.tour").cutaway(sc)
    sc.camera = cam
    bpy.context.view_layer.update()
    cams.fit(cam, sc)                        # the raised boom too ("Fit model")
    s.out_format, s.out_resolution, s.use_gpu, s.out_folder = "presentation", "preview", False, SCRATCH
    mod("blender.render").apply_output(sc, s)
    sc.render.resolution_percentage = 100
    t = time.time()
    assert bpy.ops.fresing.render(quality="preview") == {"FINISHED"}
    log("render", s.last_render, f"{time.time() - t:.0f} s")
    name = "decals" if with_decals else "cutaway" if with_cut else "render_crane"
    path = os.path.join(OUT, name + ".jpg")
    subprocess.run(["convert", s.last_render, "-strip", "-quality", "88", path], check=True)
    log("saved", name, f"{os.path.getsize(path) // 1024} KB")


def render_flex():
    """Task 0058: renders of the hoses model and the drag-chain gantry, and the before/after pair."""
    import addon_utils
    addon_utils.enable(pkg(), default_set=True)
    joints, cams, flex = mod("blender.joints"), mod("blender.cameras"), mod("blender.flex")

    def one(step_file, setup, moves, name, items_on=True, view="ISO"):
        bpy.ops.wm.read_factory_settings(use_empty=False)
        addon_utils.enable(pkg(), default_set=True)
        assert bpy.ops.fresing.import_step(filepath=os.path.join(DATA, step_file), quality="normal") == {"FINISHED"}
        sc = bpy.context.scene
        s = sc.fresing
        setup(sc)
        bpy.context.view_layer.update()
        for jn, val in moves:
            joints.set_value(s.joints.get(jn), val)
        bpy.context.view_layer.update()
        if not items_on:
            for it in s.flex:
                it.enabled = False
        bpy.context.view_layer.update()
        flex.refresh(sc, force=True)
        s.background = "SKY"
        s.floor = "VISIBLE"
        s.floor_use_own_color = True
        s.floor_color = (0.42, 0.42, 0.4)
        cam = cams.add_camera(sc, view, 50.0, name="Guide view")
        sc.camera = cam
        bpy.context.view_layer.update()
        cams.fit(cam, sc)
        s.out_format, s.out_custom_w, s.out_custom_h, s.use_gpu, s.out_folder = "custom", 900, 600, False, SCRATCH
        mod("blender.render").apply_output(sc, s)
        t = time.time()
        assert bpy.ops.fresing.render(quality="preview") == {"FINISHED"}
        log("render", name, f"{time.time() - t:.0f} s")
        path = os.path.join(OUT, name + ".jpg")
        subprocess.run(["convert", s.last_render, "-strip", "-quality", "86", path], check=True)
        return path

    hose_moves = [("Luff", math.radians(15)), ("Slide", 0.12)]
    on = one("test_flex_hoses_a.step", flex.set_up_test_hoses, hose_moves, "view_flex_hoses")
    off = one("test_flex_hoses_a.step", flex.set_up_test_hoses, hose_moves, "view_flex_off", items_on=False)
    pair = os.path.join(OUT, "view_flex_before_after.jpg")
    subprocess.run(["montage", "-label", "Off: the stiff CAD hoses", off, "-label", "On: the hoses follow", on,
                    "-tile", "2x1", "-geometry", "+6+6", "-pointsize", "20", "-background", "white", pair], check=True)
    subprocess.run(["convert", pair, "-strip", "-quality", "86", pair], check=True)
    os.remove(off)
    os.remove(on)                               # only the pair is shown in the guide
    one("test_flex_chains_a.step", flex.set_up_test_chains, [("X", 0.2), ("Y", 0.15), ("Z", -0.06)],
        "view_flex_chains")


if MODE == "flex":
    try:
        render_flex()
    except Exception:
        log("ERROR", traceback.format_exc())
        sys.exit(1)
elif MODE in ("render", "looks", "decals", "cutaway"):
    try:
        render_looks() if MODE == "looks" else render_crane(with_decals=MODE == "decals", with_cut=MODE == "cutaway")
    except Exception:
        log("ERROR", traceback.format_exc())
        sys.exit(1)
else:
    bpy.context.preferences.view.ui_scale = float(os.environ.get("GUIDE_SCALE", "1.5" if MODE in ("panels", "update") else "1.0"))
    bpy.context.preferences.system.use_region_overlap = False      # side panel on a plain background
    bpy.app.timers.register(driver, first_interval=4.0, persistent=True)
