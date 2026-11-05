"""Real-app test, rule sets (task 0015): pick, copy, change, save, switch with the preview dialog,
undo/redo, start empty – in the real app with dialogs confirmed by key presses, plus screenshots
of 3 Looks and of every dialog.

Install the extension and the app template first (see ui_test_app.py), then run:
    FRESING_RULE_SETS_DIR=/tmp/rs_lib FRESING_UI_OPEN_FOLDS=1 xvfb-run -a -s "-screen 0 1700x2600x24" \\
        blender -p 0 0 1700 2600 --app-template fresing_render --enable-event-simulate \\
        --python tools/ui_test_rule_sets.py
FRESING_RULE_SETS_DIR keeps the test away from a real library. Screenshots and ui_test_rule_sets.log
go to $UITEST_OUT (default ~/fresing_ui_test_rule_sets).
"""

import json
import os
import subprocess
import time
import traceback

import bpy

OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_test_rule_sets"))
MODEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "data", "test_machine.step")
LIB = os.environ.get("FRESING_RULE_SETS_DIR", "")
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "ui_test_rule_sets.log"), "w")
RESULTS = []


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


def shot(name, sidebar=False):
    full = os.path.join(OUT, name + ".png")
    subprocess.run(["import", "-window", "root", full], check=False)
    if sidebar:
        win, area, region, sb = ui()
        top = win.height - (sb.y + sb.height)
        subprocess.run(["convert", full, "-crop", f"{sb.width}x{sb.height}+{sb.x}+{top}", "+repage",
                        os.path.join(OUT, name + "_sidebar.png")], check=False)


def key(k):
    win, area, region, sb = ui()
    x, y = region.x + region.width // 2, region.y + region.height // 2
    win.event_simulate(type=k, value="PRESS", x=x, y=y)
    win.event_simulate(type=k, value="RELEASE", x=x, y=y)


def redraw():
    win, area, region, sb = ui()
    for k in range(6):
        win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=sb.x + 40 + k, y=sb.y + 300 + 20 * k)
    for a in win.screen.areas:
        a.tag_redraw()


def find(name, n=0):
    hits = sorted((o for o in bpy.context.scene.objects if o.get("fr_name") == name), key=lambda o: o.get("fr_uid"))
    return hits[n] if len(hits) > n else None


def lib_file(name):
    return os.path.join(LIB, name + ".json")


STEPS = []


def step(fn):
    STEPS.append(fn)
    return fn


@step
def s_start():
    key("ESC")                                          # closes the splash screen
    return 1.0


@step
def s_import():
    log("extension", pkg(), "library", LIB)
    check("test library folder set", bool(LIB))
    with override():
        bpy.ops.fresing.import_step(filepath=MODEL, quality="normal")
    return 1.0


@step
def s_wait():
    if bpy.context.scene.fresing.model_count == 0:
        redraw()
        return "wait"
    s = bpy.context.scene.fresing
    rs = mod("blender.rule_sets")
    check("a new project uses Standard", s.rule_set == "Standard" and not rs.is_changed(s), s.rule_set)
    redraw()
    return 1.5


@step
def s_copy_dialog():
    shot("01_looks_standard", sidebar=True)
    with override():
        res = bpy.ops.fresing.rule_set_save_as("INVOKE_DEFAULT")        # 'Copy…'
    check("'Copy…' opens its dialog", res == {"RUNNING_MODAL"}, res)
    return 1.0


@step
def s_copy_confirm():
    shot("02_copy_dialog")
    key("RET")
    return 1.0


@step
def s_copied():
    s = bpy.context.scene.fresing
    check("Enter in the dialog makes 'Standard copy' and the project uses it",
          s.rule_set == "Standard copy" and os.path.isfile(lib_file("Standard copy")), s.rule_set)
    s.groups["Fasteners black"].material = "paint_gloss"           # change a group's material
    s.groups["Fasteners black"].color = "RAL 3000"
    redraw()
    return 1.5


@step
def s_changed():
    s = bpy.context.scene.fresing
    rs = mod("blender.rule_sets")
    check("the panel knows the rule set changed", rs.differences(s)["looks"] == 1, rs.differences(s))
    shot("03_changed", sidebar=True)
    with override():
        res = bpy.ops.fresing.rule_set_save("INVOKE_DEFAULT")
    check("'Save to …' asks first", res == {"RUNNING_MODAL"}, res)
    return 1.0


@step
def s_save_confirm():
    shot("04_save_confirm")
    key("RET")
    return 1.0


@step
def s_saved():
    shot("04b_after_save", sidebar=True)                # no forced redraw: the panel must follow by itself
    s = bpy.context.scene.fresing
    rs = mod("blender.rule_sets")
    data = json.load(open(lib_file("Standard copy"), encoding="utf-8"))
    check("saved to the library, no longer 'changed'",
          not rs.is_changed(s) and data["groups"]["Fasteners black"] == {"material": "paint_gloss",
                                                                          "color": "RAL 3000"},
          data["groups"].get("Fasteners black"))
    with override():
        res = bpy.ops.fresing.rule_set_switch("INVOKE_DEFAULT", name="Standard")
    check("switching shows the preview dialog", res == {"RUNNING_MODAL"}, res)
    return 1.0


@step
def s_switch_confirm():
    shot("05_switch_preview")
    key("RET")
    return 1.0


@step
def s_switched():
    s = bpy.context.scene.fresing
    g = s.groups["Fasteners black"]
    check("switched to Standard: its look is back", s.rule_set == "Standard" and g.material == "black_oxide",
          (s.rule_set, g.material))
    with override():
        res = bpy.ops.ed.undo()
    s = bpy.context.scene.fresing                       # undo replaces the data: fetch it again
    g = s.groups["Fasteners black"]
    check("undo goes back to 'Standard copy'", res == {"FINISHED"} and s.rule_set == "Standard copy"
          and g.material == "paint_gloss", (res, s.rule_set, g.material))
    with override():
        bpy.ops.ed.redo()
    s = bpy.context.scene.fresing
    check("redo switches again", s.rule_set == "Standard" and s.groups["Fasteners black"].material == "black_oxide",
          s.rule_set)
    with override():
        res = bpy.ops.fresing.rule_set_new_empty("INVOKE_DEFAULT")
    check("'New, empty…' opens its dialog", res == {"RUNNING_MODAL"}, res)
    return 1.0


@step
def s_empty_confirm():
    shot("06_new_empty_dialog")
    key("RET")
    return 1.0


@step
def s_empty():
    s = bpy.context.scene.fresing
    parts = list(mod("blender.build").iter_parts(bpy.context.scene))
    check("an empty rule set: every part unsorted", s.rule_set == "New rule set" and len(s.rules) == 0
          and s.unmatched == len(parts) and [g.name for g in s.groups] == ["Unsorted"],
          (s.rule_set, s.unmatched, [g.name for g in s.groups]))
    redraw()
    return 1.5


@step
def s_final_shot():
    shot("07_empty_rule_set_and_manage", sidebar=True)
    with override():
        res = bpy.ops.fresing.rule_set_switch("INVOKE_DEFAULT", name="Standard copy")
    check("switch back opens the preview", res == {"RUNNING_MODAL"}, res)
    return 1.0


@step
def s_back():
    key("RET")
    return 1.0


@step
def s_back_done():
    s = bpy.context.scene.fresing
    check("back on 'Standard copy' with its saved look", s.rule_set == "Standard copy"
          and s.groups["Fasteners black"].color == "RAL 3000", s.rule_set)
    redraw()
    return 1.5


@step
def s_library_newer():
    shot("08_back_on_copy", sidebar=True)
    core = mod("core.rule_sets")
    rs = mod("blender.rule_sets")
    newer = core.RuleSet.load(lib_file("Standard copy"))     # a colleague saves a change
    newer.rules = newer.rules[1:]
    newer.save(lib_file("Standard copy"))
    rs.forget_scan()
    check("the panel sees the newer library version", rs.library_differs(bpy.context.scene.fresing))
    redraw()
    return 1.5


@step
def s_only_here():
    shot("09_library_newer", sidebar=True)
    os.remove(lib_file("Standard copy"))
    rs = mod("blender.rule_sets")
    rs.forget_scan()
    check("deleted from the library: the project keeps its copy",
          rs.kind(bpy.context.scene.fresing) == "project" and bpy.context.scene.fresing.rule_set == "Standard copy")
    redraw()
    return 1.5


@step
def s_finish():
    shot("10_only_in_this_project", sidebar=True)
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
        return 1.0
    _w[0] = 0.0
    _i[0] += 1
    return r


bpy.context.preferences.view.ui_scale = float(os.environ.get("UITEST_SCALE", "1.5"))
bpy.app.timers.register(driver, first_interval=3.0, persistent=True)
