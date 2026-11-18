"""Real-app test, 8 Lifting plan > Equipment > Make a crane… (task 0204): the button in Equipment, the dialog (type,
start from a class, the numbers in folds, the "fits" line, the name), a refused set of numbers (the rule in red, Make
starts nothing), Make with Return in the dialog: the maker runs in the background while the app keeps drawing, the
crane lands in the library folder "Lifting equipment" (model, equipment file with a SAMPLE chart, picture) and is
picked; Place now places it with its joints where its own kinematics say; a second Make cancelled leaves nothing
behind; the same name again is refused. Writes the guide's picture of the dialog (dialog_8_make_crane.png).

Install the extension and the app template first (see ui_test_app.py), then run:
    xvfb-run -a -s "-screen 0 1800x2600x24" blender --app-template fresing_render --enable-event-simulate \\
        --python tools/ui_test_lifting_make.py
Screenshots and ui_test_lifting_make.log go to $UITEST_OUT (default ~/fresing_ui_test_lifting_make).
"""

import importlib
import os
import subprocess
import tempfile
import time
import traceback

import bpy

OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_test_lifting_make"))
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "data")
CRANE = os.path.join(DATA, "test_crane_a.step")
GUIDE_SHOT = os.environ.get("UITEST_GUIDE_SHOT", "")      # where to put the guide's picture (tools: docs/img)
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "ui_test_lifting_make.log"), "w")
RESULTS = []
S = {}
LIB_ROOT = tempfile.mkdtemp(prefix="fr make lib é ")          # a space and an accent, as on the owner's PC


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
    return importlib.import_module(pkg() + "." + name)


def L():
    return mod("blender.lifting")


def O():
    return mod("blender.ops_lifting_make")


def ui():
    win = bpy.context.window_manager.windows[0]
    area = next(a for a in win.screen.areas if a.type == "VIEW_3D")
    region = next(r for r in area.regions if r.type == "WINDOW")
    sidebar = next(r for r in area.regions if r.type == "UI")
    return win, area, region, sidebar


def override():
    win, area, region, _sb = ui()
    return bpy.context.temp_override(window=win, screen=win.screen, area=area, region=region, scene=win.scene)


def can(idname) -> bool:
    group, name = idname.split(".")
    with override():
        return bool(getattr(getattr(bpy.ops, group), name).poll())


def op(idname, **kw):
    group, name = idname.split(".")
    with override():
        return getattr(getattr(bpy.ops, group), name)("EXEC_DEFAULT", True, **kw)


def refused(idname, **kw):
    """Run an operator that should refuse: (result, the error it reported)."""
    try:
        return op(idname, **kw), ""
    except RuntimeError as exc:                       # an operator that reports an ERROR raises in a script
        return {"CANCELLED"}, str(exc)


def invoke(idname, **kw):
    group, name = idname.split(".")
    with override():
        return getattr(getattr(bpy.ops, group), name)("INVOKE_DEFAULT", True, **kw)


def redraw():
    for a in bpy.context.window_manager.windows[0].screen.areas:
        a.tag_redraw()


def press(key):
    win = bpy.context.window_manager.windows[0]
    win.event_simulate(type=key, value="PRESS")
    win.event_simulate(type=key, value="RELEASE")


def shot(name):
    subprocess.run(["import", "-window", "root", os.path.join(OUT, name + ".png")], check=False)


def dialog_shot(name, mouse, size=(506, 678)):
    """The dialog: Blender opens it with its top a little above the mouse, left of it."""
    win = bpy.context.window_manager.windows[0]
    full = os.path.join(OUT, "_full.png")
    subprocess.run(["import", "-window", "root", full], check=False)
    x = max(0, mouse[0] - 452)
    top = max(0, win.height - mouse[1] - 60)
    out = os.path.join(OUT, name + ".png")
    subprocess.run(["convert", full, "-crop", f"{size[0]}x{size[1]}+{x}+{top}", "+repage", out], check=False)
    return out


def made_items():
    lib = os.path.join(LIB_ROOT, "Lifting equipment")
    return sorted(os.listdir(lib)) if os.path.isdir(lib) else []


STEPS = []


def step(fn):
    STEPS.append(fn)
    return fn


@step
def s_start():
    log("extension", pkg())
    press("ESC")                                      # the splash screen first (CLAUDE.md 8)
    L().set_understood(True)
    mod("blender.prefs").get().library_path = LIB_ROOT
    return 2.0


@step
def s_import():
    with override():
        bpy.ops.fresing.import_step(filepath=CRANE, quality="draft")
    return 1.0


@step
def s_model():
    if bpy.context.scene.fresing.model_count == 0:
        return "wait"
    bpy.context.preferences.system.use_region_overlap = False
    mod("blender.panels").open_to("FRESING_PT_lifting_equipment")
    redraw()
    check("Equipment has Make a crane… (the button can be pressed)", can("fresing.lifting_make"))
    return 1.0


@step
def s_open_dialog():
    win, _area, region, _sb = ui()
    S["centre"] = (region.x + region.width // 2, region.y + region.height // 2 + 300)
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=S["centre"][0], y=S["centre"][1])
    m = mod("blender.ui_lifting_make").settings(bpy.context)
    m.kind = "AT"
    m.start = "AT-40"
    check("Start from fills the dialog with the class's numbers", m.at_sections == 4 and abs(m.at_Lmax - 34.0) < 1e-4,
          f"{m.at_sections} sections, {m.at_Lmax} m")
    m.at_sections = 3
    m.at_Lmax = 26.0
    m.name = "My AT-40 with 3 sections"
    m.replace = False
    res = invoke("fresing.lifting_make")
    check("Make a crane… opens a dialog", res in ({"RUNNING_MODAL"}, {"INTERFACE"}), str(res))
    return 1.5


@step
def s_dialog_drawn():
    m = mod("blender.ui_lifting_make").settings(bpy.context)
    probs = mod("blender.ui_lifting_make").problems_of(m)
    check("the dialog's line says Fits for 3 sections and 26 m", probs == [], str([p.rule for p in probs]))
    out = dialog_shot("make_dialog", S["centre"])
    if GUIDE_SHOT:
        subprocess.run(["cp", out, GUIDE_SHOT], check=False)
    S["t_make"] = time.time()
    S["ticks"] = []
    press("RET")                                      # Make (the dialog's OK)
    return 0.2


@step
def s_making():
    S["ticks"].append(time.time())
    if O().running() is not None or (not O().STATE.get("made") and not O().STATE.get("error")
                                     and time.time() - S["t_make"] < 2.0):
        if len(S["ticks"]) == 3:
            shot("making")
        return "wait"
    S["seconds"] = time.time() - S["t_make"]
    gaps = [b - a for a, b in zip(S["ticks"], S["ticks"][1:])]
    check("the app keeps running while the crane is made (timer steps < 1.5 s)", gaps and max(gaps) < 1.5,
          f"{len(gaps)} steps, longest {max(gaps) if gaps else 0:.2f} s, made in {S['seconds']:.1f} s")
    check("Make finished without an error", not O().STATE.get("error"), O().STATE.get("message", ""))
    return 1.0


@step
def s_in_library():
    made = O().STATE.get("made", "")
    folder = os.path.dirname(made)
    files = sorted(os.listdir(folder)) if os.path.isdir(folder) else []
    check("the crane is in the library folder 'Lifting equipment': model, equipment file, picture",
          files == ["My AT-40 with 3 sections.json", "My AT-40 with 3 sections.png", "My AT-40 with 3 sections.step"],
          str(files))
    it = L().item_at(made) if made else None
    check("the made crane is read by the library as SAMPLE, its own item", it is not None and it.ok and it.sample
          and not it.builtin and it.data.get("made_from", {}).get("class") == "AT-40")
    names = [i.name for i in L().library(force=True)]
    check("the library list shows it under Your own equipment", "My AT-40 with 3 sections" in names)
    check("the new crane is picked (Place… shows it)", L().plan(bpy.context.scene).pick == made)
    shot("made")
    return 0.5


@step
def s_place_now():
    made = O().STATE.get("made", "")
    res = op("fresing.lifting_place", path=made, location=(9.0, 0.0, 0.0), heading=3.14159)
    sc = bpy.context.scene
    c = L().active_crane(sc)
    check("Place now places the made crane", res == {"FINISHED"} and c is not None
          and c.item_name == "My AT-40 with 3 sections", str(res))
    if c is not None:
        tele = [j.name for j in L().own_joints(sc, c) if "Telescope" in j.name]
        check("its boom has 3 sections: two telescope joints", len(tele) == 2, str(tele))
        try:
            msg = L().check_rig(sc)
            check("every pose puts its hook block where its own kinematics say", True, msg)
        except ValueError as exc:
            check("every pose puts its hook block where its own kinematics say", False, str(exc))
    return 1.0


@step
def s_same_name():
    m = mod("blender.ui_lifting_make").settings(bpy.context)
    from_ui = O().J.name_problem(O().make_library(), m.name, False)
    check("the same name again is refused unless Replace", "already in your library" in from_ui, from_ui)
    res, err = refused("fresing.lifting_make")
    check("Make with that name starts nothing and says why", res == {"CANCELLED"} and O().running() is None
          and "already in your library" in err, err)
    return 0.5


@step
def s_refused():
    m = mod("blender.ui_lifting_make").settings(bpy.context)
    m.name = "Odd falls"
    m.at_hook_falls = 5
    probs = mod("blender.ui_lifting_make").problems_of(m)
    check("an odd number of falls is refused with its rule", [p.rule for p in probs] == ["falls"],
          str([p.text for p in probs]))
    before = made_items()
    res, err = refused("fresing.lifting_make")
    check("Make with refused numbers starts nothing, writes nothing and names the rule",
          res == {"CANCELLED"} and made_items() == before and "even number" in err, err)
    m.at_hook_falls = 4
    return 0.5


@step
def s_cancel_start():
    m = mod("blender.ui_lifting_make").settings(bpy.context)
    m.kind = "CC"
    m.start = "CC-1600"
    m.name = "Cancelled crawler"
    S["before"] = made_items()
    res = invoke("fresing.lifting_make")
    check("the dialog opens again", res in ({"RUNNING_MODAL"}, {"INTERFACE"}), str(res))
    return 1.0


@step
def s_cancel_make():
    press("RET")
    return 0.4


@step
def s_cancel():
    job = O().running()
    check("the second Make runs", job is not None)
    S["tmp"] = job.tmp if job is not None else ""
    mod("blender.panels").open_to("FRESING_PT_lifting_equipment")
    redraw()
    shot("making_cancel")
    res = op("fresing.lifting_make_cancel")
    check("Cancel stops it", res == {"FINISHED"} and O().running() is None, str(res))
    return 1.0


@step
def s_cancelled():
    check("Cancel leaves nothing behind (library and temporary folder)",
          made_items() == S["before"] and not (S["tmp"] and os.path.exists(S["tmp"])),
          f"{made_items()} vs {S['before']}")
    check("the panel says it was cancelled", "cancelled" in O().STATE.get("message", ""), O().STATE.get("message", ""))
    bpy.context.preferences.system.use_region_overlap = True        # put back (CLAUDE.md 8: preferences are saved)
    return 0.5


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
        if time.time() - _w[0] > 300:
            check(fn.__name__ + " timeout", False)
            _i[0] += 1
            _w[0] = 0.0
        return 0.3
    _w[0] = 0.0
    _i[0] += 1
    return r


bpy.app.timers.register(driver, first_interval=3.0, persistent=True)
