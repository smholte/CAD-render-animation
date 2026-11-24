"""Real-app test, task 0294: workspaces round 2.

A new user (nothing chosen) starts in Essentials; the Workspace drop-down opens with a star beside every workspace;
starred ones and the workspace for new projects sit on top, above a line; Sales hides import, structure and motion;
"Use for new projects" makes the next new project start there; the stars and the choice are kept over a real restart
(the app started again in the same settings folder: this file with FR_WS2_CHILD set). Everything is put back at the
end, so the next test in this settings folder starts as before.

    FRESING_WORKSPACE_START= xvfb-run -a -s "-screen 0 1800x1300x24" blender -p 0 0 1800 1300 \\
        --app-template fresing_render --enable-event-simulate --python tools/ui_test_workspaces2.py
Screenshots and the log go to $UITEST_OUT (default ~/fresing_ui_test_workspaces2)."""

import json
import os
import subprocess
import tempfile
import time
import traceback

import bpy

CHILD = os.environ.get("FR_WS2_CHILD", "")
OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_test_workspaces2"))
os.makedirs(OUT, exist_ok=True)
RESULTS = []
TMP = tempfile.mkdtemp(prefix="fr_ws2 é ")
S = {}
LOG = None if CHILD else open(os.path.join(OUT, "ui_test_workspaces2.log"), "w")


def log(*a):
    msg = " ".join(str(x) for x in a)
    print("[UITEST]", msg, flush=True)
    if LOG:
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
    return importlib.import_module(pkg() + ("." + name if name else ""))


def view():
    win = bpy.context.window_manager.windows[0]
    area = max((a for a in win.screen.areas if a.type == "VIEW_3D"), key=lambda a: a.width * a.height)
    return win, area, next(r for r in area.regions if r.type == "WINDOW")


def override():
    win, area, region = view()
    return bpy.context.temp_override(window=win, screen=win.screen, area=area, region=region, scene=win.scene)


def shot(name):
    path = os.path.join(OUT, name + ".png")
    subprocess.run(["import", "-window", "root", path], check=False)
    return path


def redraw():
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            area.tag_redraw()


STEPS = []


def step(fn):
    STEPS.append(fn)
    return fn


# ----- the drop-down's draw, recorded (the real menu, drawn by Blender) -----
DRAWS = {"n": 0, "rows": [], "error": ""}


def _record():
    ow = mod("blender.ops_workspace")
    cls = ow.FRESING_MT_workspaces
    if getattr(cls, "_fr_test", False):
        return
    orig = cls.draw

    def draw(self, context):
        try:
            top, rest = mod("blender.workspaces").menu()
            DRAWS["rows"] = [[r[0] for r in top], [r[0] for r in rest]]
            orig(self, context)
            DRAWS["n"] += 1
        except Exception as exc:  # noqa: BLE001
            DRAWS["error"] = repr(exc)
            raise
    cls.draw = draw
    cls._fr_test = True


def open_menu(name):
    win, area, region = view()
    x, y = region.x + region.width // 2, region.y + region.height // 2
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x, y=y)
    with override():
        bpy.ops.wm.call_menu(name="FRESING_MT_workspaces")
    S["menu_at"] = (x, y)


def close_menu():
    view()[0].event_simulate(type="ESC", value="PRESS")


@step
def s_new_user():
    """An earlier test in this settings folder (the welcome's, which plays an update from an older version) may have
    made this an existing user, who keeps All functions: be a new user again – nothing chosen, a new project."""
    ws = mod("blender.workspaces")
    log("chosen at the start:", repr(ws.chosen()))
    p = mod("blender.prefs").get()
    p.default_workspace, p.workspace_stars = "", ""
    mod("blender.settings_store").save()
    with override():
        bpy.ops.wm.read_homefile("EXEC_DEFAULT")
    return 2.0


@step
def s_start():
    ws = mod("blender.workspaces")
    sc = bpy.context.scene
    check("a new user has not chosen a workspace", ws.chosen() == "", repr(ws.chosen()))
    check("a new user's new project starts in Essentials", ws.name_of(sc) == "Essentials", ws.name_of(sc))
    check("Essentials shows 1 Import and hides the CNC machine",
          not ws.panel_hidden(sc, "FRESING_PT_import") and ws.panel_hidden(sc, "FRESING_PT_cnc"))
    check("Essentials is first in the drop-down's list", ws.names()[0][0] == "Essentials")
    _record()
    return 0.5


@step
def s_menu_first():
    open_menu("first")
    return 1.0


@step
def s_menu_first_seen():
    redraw()
    shot("01_dropdown_new_user")
    check("the real drop-down drew", DRAWS["n"] > 0 and not DRAWS["error"], DRAWS["error"] or str(DRAWS["n"]))
    check("on top: the workspace for new projects (Essentials)", DRAWS["rows"][:1] == [["Essentials"]],
          str(DRAWS["rows"][:1]))
    close_menu()
    return 0.5


@step
def s_star():
    with override():
        r1 = bpy.ops.fresing.workspace_star("EXEC_DEFAULT", name="Reviewer")
        r2 = bpy.ops.fresing.workspace_star("EXEC_DEFAULT", name="Sales")
    check("two stars pressed", r1 == r2 == {"FINISHED"})
    check("the stars are kept in the order they were pressed",
          mod("blender.workspaces").stars() == ["Reviewer", "Sales"], str(mod("blender.workspaces").stars()))
    DRAWS["n"] = 0
    open_menu("starred")
    return 1.0


@step
def s_menu_starred_seen():
    redraw()
    shot("02_dropdown_starred")
    top, rest = DRAWS["rows"] if DRAWS["rows"] else ([], [])
    check("starred ones on top, above the line", top == ["Essentials", "Reviewer", "Sales"], str(top))
    check("under the line the others, starred ones not twice", "Sales" not in rest and "All functions" in rest
          and rest[-1] == "Full access", str(rest))
    close_menu()
    return 0.5


@step
def s_sales():
    ws = mod("blender.workspaces")
    with override():
        bpy.ops.fresing.workspace_pick("EXEC_DEFAULT", True, name="Sales")
    sc = bpy.context.scene
    check("Sales: import, structure and motion hidden; looks, saved scenes, Make and the 3D page shown",
          all(ws.panel_hidden(sc, "FRESING_PT_" + p) for p in ("import", "structure", "motion"))
          and not any(ws.panel_hidden(sc, "FRESING_PT_" + p) for p in ("looks", "shots", "web" + "3d", "output")))   # (not the module's name as a word: lane runs)
    check("Sales does not lock the project (unlike the Client view)", not ws.locked(sc))
    with override():
        bpy.ops.fresing.workspace_default("EXEC_DEFAULT", current=True)
    check("Use for new projects: Sales", ws.chosen() == "Sales" and ws.default_name() == "Sales")
    mod("blender.settings_store").save()
    with override():
        bpy.ops.wm.read_homefile("EXEC_DEFAULT")
    return 2.0


@step
def s_new_project():
    ws = mod("blender.workspaces")
    sc = bpy.context.scene
    check("the next new project starts in Sales", ws.name_of(sc) == "Sales", ws.name_of(sc))
    shot("03_new_project_sales")
    return 0.3


@step
def s_restart():
    out = os.path.join(TMP, "restart.json")
    env = dict(os.environ, FR_WS2_CHILD=out, UITEST_OUT=os.path.join(OUT, "restart"))
    t = time.time()
    try:
        subprocess.run([bpy.app.binary_path, "--app-template", "fresing_render", "--enable-event-simulate",
                        "-p", "0", "0", "1280", "900", "--python", os.path.abspath(__file__)], env=env, timeout=240,
                       check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        log("the restarted app did not finish in 240 s")
    try:
        got = json.load(open(out, encoding="utf-8"))
    except (OSError, ValueError):
        got = {}
    log(f"restarted app ({time.time() - t:.0f} s):", got)
    check("after a restart the stars are kept, in order", got.get("stars") == ["Reviewer", "Sales"],
          str(got.get("stars")))
    check("after a restart the workspace for new projects is kept", got.get("chosen") == "Sales", str(got))
    check("after a restart the drop-down's top is the same", got.get("top") == ["Sales", "Reviewer"],
          str(got.get("top")))
    check("after a restart the first project is in Sales", got.get("project") == "Sales", str(got.get("project")))
    return 0.3


@step
def s_back():
    """Put everything back: the next real-app test in this settings folder starts as before (CLAUDE.md 8)."""
    from_p = mod("blender.prefs").get()
    from_p.default_workspace, from_p.workspace_stars = "", ""
    mod("blender.settings_store").save()
    ws = mod("blender.workspaces")
    check("put back: nothing chosen, no stars", ws.chosen() == "" and ws.stars() == [])
    return 0.3


@step
def s_finish():
    failed = [r for r in RESULTS if not r[1]]
    log(f"RESULT {len(RESULTS) - len(failed)}/{len(RESULTS)} passed")
    LOG.close()
    bpy.ops.wm.quit_blender()
    return None


def child():
    """The restarted app: what it kept, written to FR_WS2_CHILD, then quit."""
    S["n"] = S.get("n", 0) + 1
    if pkg() is None and S["n"] < 40:
        return 0.5
    data = {}
    try:
        ws = mod("blender.workspaces")
        top, _rest = ws.menu()
        data = {"stars": ws.stars(), "chosen": ws.chosen(), "top": [r[0] for r in top],
                "project": ws.name_of(bpy.context.scene)}
    except Exception as exc:  # noqa: BLE001
        data["error"] = repr(exc)
    with open(CHILD, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    bpy.ops.wm.quit_blender()
    return None


_i = [0]


def driver():
    if _i[0] >= len(STEPS):
        return None
    fn = STEPS[_i[0]]
    try:
        r = fn()
    except Exception:  # noqa: BLE001
        log("ERROR in", fn.__name__, traceback.format_exc())
        check(fn.__name__, False, "exception")
        r = 0.5
    if r == "again":
        return 0.2
    _i[0] += 1
    return r


bpy.app.timers.register(child if CHILD else driver, first_interval=3.0, persistent=True)
