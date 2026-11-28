"""Real-app test, task 0228: demo kits in Help > Make demo project….

* the Make window opens with the list (the app's own demo; a screenshot next to the log);
* Add a demo kit… with the made-up test kit (``fresing_render/data/demo_kit_test.zip``): it is in the list, the Make
  window's choice and the Help menu; a zip that is no kit and a kit made for another app version are refused;
* the Client view switches Add and Remove off (Make and Open stay);
* with no app demo in the list (``demo.PUBLIC`` off, as after the cut) the list holds only the kit;
* Make it with the kit: the background Blender (``demobuild … --kit test-kit``) makes the kit's demo, Help shows
  "Open Test kit box", it opens with the box's slide joint and the saved camera;
* Remove: the kit leaves the list, its made demo stays.

    xvfb-run -a -s "-screen 0 1800x1300x24" blender -p 0 0 1800 1300 --app-template fresing_render \\
        --enable-event-simulate --python tools/ui_test_demo_kits.py
The log goes to $UITEST_OUT (default ~/fresing_ui_test_demo_kits); the kits folder and the demo go there too."""

import importlib
import os
import subprocess
import time
import traceback
import zipfile

import bpy

OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_test_demo_kits"))
os.makedirs(OUT, exist_ok=True)
KITS = os.path.join(OUT, "kits é")
DEMO = os.path.join(OUT, "Demo é")
os.environ["FRESING_DEMO_KITS"] = KITS              # the background build inherits it
LOG = open(os.path.join(OUT, "ui_test_demo_kits.log"), "w", encoding="utf-8")
RESULTS = []
S = {}


def log(*a):
    msg = " ".join(str(x) for x in a)
    print("[UITEST]", msg, flush=True)
    LOG.write(msg + "\n")
    LOG.flush()


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    log(("PASS " if ok else "FAIL ") + name + (f" ({detail})" if detail else ""))


def mod(name):
    import addon_utils
    pkg = next((m.__name__ for m in addon_utils.modules() if m.__name__.endswith("fresing_render")), None)
    return importlib.import_module(pkg + "." + name)


def view():
    win = bpy.context.window_manager.windows[0]
    area = next(a for a in win.screen.areas if a.type == "VIEW_3D")
    region = next(r for r in area.regions if r.type == "WINDOW")
    return win, area, region


def override():
    win, area, region = view()
    return bpy.context.temp_override(window=win, screen=win.screen, area=area, region=region, scene=win.scene)


def shipped_kit():
    return os.path.join(mod("pccheck.checks").DATA, "demo_kit_test.zip")


def run_op(op, *a, **kw):
    """An operator called like a button; a refusal (report ERROR) comes back as {'CANCELLED'}, not as an error."""
    try:
        with override():
            return op(*a, **kw)
    except RuntimeError as exc:
        log("refused:", str(exc)[:200])
        return {"CANCELLED"}


def menu_texts():
    """The Help menu's demo entries, as ops_demo draws them (a stand-in layout records them)."""
    class Rec:
        def __init__(self):
            self.rows = []

        def operator(self, idname, text="", icon=""):
            self.rows.append((idname, text))

            class Props:
                pass
            return Props()

        def label(self, text="", icon=""):
            self.rows.append(("label", text))
    rec = Rec()
    mod("blender.ops_demo").draw_help(rec)
    return rec.rows


def screenshot(name):
    path = os.path.join(OUT, name)
    try:
        subprocess.run(["import", "-window", "root", path], timeout=30, capture_output=True)
    except (OSError, subprocess.SubprocessError):
        pass


S0 = {}
def _fs():
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import form_shots
    return form_shots


STEPS = []


def step(fn):
    STEPS.append(fn)
    return fn


@step
def s_esc():
    win, _area, region = view()
    win.event_simulate(type="ESC", value="PRESS", x=region.x + 300, y=region.y + 300)
    win.event_simulate(type="ESC", value="RELEASE", x=region.x + 300, y=region.y + 300)
    return 0.8


@step
def s_dialog():
    ops_demo = mod("blender.ops_demo")
    items = [i[0] for i in ops_demo._which_items(None, bpy.context)]
    check("Make list: the app's own demo first, no kit yet", items == [ops_demo.PUBLIC_ID], str(items))
    with override():
        r = bpy.ops.fresing.demo_make("INVOKE_DEFAULT", folder=DEMO)
    check("Make demo project… opens its window", r in ({"FINISHED"}, {"RUNNING_MODAL"}), str(r))   # task 0282
    return 1.5


@step
def s_dialog_shot():
    if not _fs().ready_one(mod("blender.form_window").windows("fresing.demo_make")) \
            and time.time() - S0.setdefault("t", time.time()) < 15:
        return "wait"                                            # task 0282: the window opens a moment later
    S0.clear()
    screenshot("make_window_app_demo.png")
    check("… in a window of its own (task 0282)", mod("blender.form_window").is_open("fresing.demo_make"))
    mod("blender.form_window").close("fresing.demo_make")        # task 0282: a window now, not a dialog
    return 0.8


@step
def s_add():
    ops_demo = mod("blender.ops_demo")
    with override():
        r = bpy.ops.fresing.demo_kit_add("EXEC_DEFAULT", True, filepath=shipped_kit())
    check("Add a demo kit…: the test kit is added", r == {"FINISHED"}, str(r))
    kits = [k.id for k in ops_demo.kits()]
    check("the kit is unpacked into the kits folder", kits == ["test-kit"] and
          os.path.isfile(os.path.join(KITS, "test-kit", "kit.json")), str(kits))
    items = [(i[0], i[1]) for i in ops_demo._which_items(None, bpy.context)]
    check("Make list: the app's own demo, then 'Test kit box (kit 1)'",
          items == [(ops_demo.PUBLIC_ID, "Vessel in a wind park"), ("test-kit", "Test kit box (kit 1)")], str(items))
    with override():
        r = bpy.ops.fresing.demo_make("INVOKE_DEFAULT", folder=DEMO, which="test-kit")
    return 1.5


@step
def s_kit_shot():
    if not _fs().ready_one(mod("blender.form_window").windows("fresing.demo_make")) \
            and time.time() - S0.setdefault("t", time.time()) < 15:
        return "wait"                                            # task 0282: the window opens a moment later
    S0.clear()
    screenshot("make_window_kit.png")
    check("… in a window of its own (task 0282)", mod("blender.form_window").is_open("fresing.demo_make"))
    mod("blender.form_window").close("fresing.demo_make")        # task 0282: a window now, not a dialog
    return 0.8


@step
def s_refused():
    ops_demo = mod("blender.ops_demo")
    bad = os.path.join(OUT, "not a kit.zip")
    with zipfile.ZipFile(bad, "w") as zf:
        zf.writestr("stuff/readme.txt", "hello")
    r = run_op(bpy.ops.fresing.demo_kit_add, "EXEC_DEFAULT", True, filepath=bad)
    check("a zip that is no kit is refused", r == {"CANCELLED"}, str(r))
    old = os.path.join(OUT, "old kit.zip")
    with zipfile.ZipFile(shipped_kit()) as src, zipfile.ZipFile(old, "w") as dst:
        for i in src.infolist():
            raw = src.read(i)
            if i.filename.endswith("/kit.json"):
                raw = raw.replace(b'"app_max": ""', b'"app_max": "0.2.1"').replace(b'"id": "test-kit"',
                                                                                  b'"id": "old-kit"')
            dst.writestr(i.filename, raw)
    r = run_op(bpy.ops.fresing.demo_kit_add, "EXEC_DEFAULT", True, filepath=old)
    check("a kit made for older app versions is refused", r == {"CANCELLED"}, str(r))
    check("the list still holds only the test kit", [k.id for k in ops_demo.kits()] == ["test-kit"])
    return 0.3


@step
def s_client():
    with override():
        bpy.ops.fresing.workspace_pick("EXEC_DEFAULT", True, name="Client view")
    return 0.8


@step
def s_client_check():
    add, rem, make = bpy.ops.fresing.demo_kit_add, bpy.ops.fresing.demo_kit_remove, bpy.ops.fresing.demo_make
    with override():
        check("Client view: Add a demo kit… and Remove are switched off", not add.poll() and not rem.poll(),
              f"add {add.poll()}, remove {rem.poll()}")
        check("Client view: Make demo project… still works", make.poll())
        bpy.ops.fresing.workspace_pick("EXEC_DEFAULT", True, name="Full access")
    return 0.8


@step
def s_no_public():
    ops_demo = mod("blender.ops_demo")
    demo = mod("blender.demo")
    demo.PUBLIC = False
    try:
        items = [i[0] for i in ops_demo._which_items(None, bpy.context)]
        check("no app demo in the list (after the cut): only the kit", items == ["test-kit"], str(items))
        demo_kits = mod("core.demo_kits")
        demo_kits.remove(KITS, "test-kit")
        items = [i[0] for i in ops_demo._which_items(None, bpy.context)]
        r = run_op(bpy.ops.fresing.demo_make, "EXEC_DEFAULT", True, folder=DEMO, which=items[0])
        check("no app demo and no kit: the list says so, Make makes nothing", items == ["NONE"] and r == {"CANCELLED"},
              f"{items} {r}")
    finally:
        demo.PUBLIC = True
    with override():
        bpy.ops.fresing.demo_kit_add("EXEC_DEFAULT", True, filepath=shipped_kit())
    return 0.3


@step
def s_make():
    S["t0"] = time.time()
    with override():
        r = bpy.ops.fresing.demo_make("EXEC_DEFAULT", True, folder=DEMO, which="test-kit")
    check("Make it with the kit starts the background build", r == {"RUNNING_MODAL"}, str(r))
    return 2.0


@step
def s_made():
    ops_demo = mod("blender.ops_demo")
    if ops_demo.running():
        S.setdefault("seen", set()).add(ops_demo.progress_text())
        return "wait"
    return 0.5


@step
def s_made_check():
    demo = mod("blender.demo")
    version = mod("blender.ops_demo")._version()
    folder = demo.kit_folder(DEMO, "test-kit")
    ok = demo.exists(folder, version, "Test kit box")
    detail = ""
    if not ok:
        try:
            detail = open(os.path.join(folder, "Make demo log.txt"), encoding="utf-8", errors="replace").read()[-600:]
        except OSError:
            detail = "no log"
    check("the kit's demo is made in the background", ok, f"{time.time() - S['t0']:.0f} s {detail}")
    check("the status line named the kit while it was made",
          any("Making Test kit box" in t for t in S.get("seen", ())), str(sorted(S.get("seen", ()))[:3]))
    keep = demo.default_folder
    demo.default_folder = lambda: DEMO            # Help looks in the default folder; the test made it in its own
    try:
        rows = menu_texts()
    finally:
        demo.default_folder = keep
    check("Help shows 'Open Test kit box'", ("fresing.demo_open", "Open Test kit box") in rows, str(rows))
    S["path"] = demo.project_path(folder, version, "Test kit box")
    with override():
        bpy.ops.fresing.demo_open("EXEC_DEFAULT", True, filepath=S["path"])
    return 1.5


@step
def s_opened():
    sc = bpy.context.scene
    joints = mod("blender.joints")
    jt = sc.fresing.joints.get("Box slide")
    box = next((o for o in sc.objects if o.get("fr_name") == "TEST BOX"), None)
    check("the kit's demo opens with the box and its joint", jt is not None and box is not None,
          bpy.data.filepath)
    if jt is not None and box is not None:
        x0 = box.matrix_world.translation.x
        joints.set_value(jt, 1.0)
        bpy.context.view_layer.update()
        check("the joint slides the box", abs(box.matrix_world.translation.x - x0 - 1.0) < 1e-3)
    check("the saved camera 'Box from the side' is there", any(s.name == "Box from the side" for s in sc.fresing.shots))
    check("the project is marked as the kit's demo", sc.get("fr_demo_kit") == "test-kit")
    return 0.5


@step
def s_cancel_make():
    """Task 0371: Make it → Cancel → Make it again, with the real buttons."""
    with override():
        bpy.ops.wm.read_homefile("EXEC_DEFAULT", use_empty=True)      # the made demo is open: it is replaced
    S["t1"] = time.time()
    with override():
        r = bpy.ops.fresing.demo_make("EXEC_DEFAULT", True, folder=DEMO, which="test-kit")
    check("Make it again starts a build", r == {"RUNNING_MODAL"}, str(r))
    return 0.5


@step
def s_cancel():
    demo, ops_demo = mod("blender.demo"), mod("blender.ops_demo")
    folder = demo.kit_folder(DEMO, "test-kit")
    if not demo.read_progress(folder, ops_demo._version()).get("stage") and time.time() - S["t1"] < 120:
        return "wait"                                                   # cancelled while it builds, not before
    with override():
        r = bpy.ops.fresing.demo_cancel("EXEC_DEFAULT", True)
    check("Cancel while the kit's demo is made", r == {"FINISHED"}, str(r))
    return 0.5


@step
def s_cancelled():
    demo, ops_demo = mod("blender.demo"), mod("blender.ops_demo")
    if ops_demo.running() or ops_demo._BUILD:
        return "wait"
    folder = demo.kit_folder(DEMO, "test-kit")
    check("Cancel: nothing of the build runs and nothing is left behind",
          not os.path.exists(demo.project_dir(folder, ops_demo._version())), folder)
    with override():
        r = bpy.ops.fresing.demo_make("EXEC_DEFAULT", True, folder=DEMO, which="test-kit")
    check("… then Make it again starts at once", r == {"RUNNING_MODAL"}, str(r))
    with override():
        bpy.ops.wm.read_homefile("EXEC_DEFAULT", use_empty=True)      # another project: Blender drops the modal
    return 1.0


@step
def s_made_again():
    demo, ops_demo = mod("blender.demo"), mod("blender.ops_demo")
    if ops_demo.running() or ops_demo._BUILD:
        return "wait"
    folder = demo.kit_folder(DEMO, "test-kit")
    check("the demo is made again after Cancel, also with another project opened meanwhile",
          demo.exists(folder, ops_demo._version(), "Test kit box"), folder)
    return 0.3


@step
def s_remove():
    ops_demo = mod("blender.ops_demo")
    with override():
        r = bpy.ops.fresing.demo_kit_remove("EXEC_DEFAULT", True, kit="test-kit")
    check("Remove: the kit leaves the list", r == {"FINISHED"} and not ops_demo.kits(), str(r))
    check("its made demo stays", os.path.isfile(S.get("path", "")))
    demo = mod("blender.demo")
    keep = demo.default_folder
    demo.default_folder = lambda: DEMO
    try:
        rows = menu_texts()
    finally:
        demo.default_folder = keep
    check("Help no longer offers it", not any("Test kit box" in t for _i, t in rows), str(rows))
    return 0.3


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
        return 1.0
    _w[0] = 0.0
    _i[0] += 1
    return r


bpy.app.timers.register(driver, first_interval=3.0, persistent=True)
