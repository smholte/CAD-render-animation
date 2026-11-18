"""Real-app test, Set up a crane (task 0203): the AT-40, the CC-750 with its luffing jib and the KB-50, each imported
from its bare STEP into a new project and rigged through the Set-up window's buttons only, by names
(``blender/crane_example.py``: the names, limits and numbers a user reads off the maker's sheet); the Set-up window
opens on the crane's kind and every step draws (a picture of each); Check finds nothing wrong (with the clash check for
the AT-40); Save into a library → the file equals the built-in rig of the class (joints, roles, couplings, limits,
axes within 1 mm / 0.1°, hook point, poses, masses, CoG, charts); Place it in a new project → Hook to here gives the
built-in crane's answer (and 0201's class solver's, from tests/lifting_reach_class.py).

Install the extension and the app template first (see ui_test_app.py), then run:
    xvfb-run -a -s "-screen 0 1800x2600x24" blender --app-template fresing_render --enable-event-simulate \\
        --python tools/ui_test_setup_crane.py
Screenshots and ui_test_setup_crane.log go to $UITEST_OUT (default ~/fresing_ui_test_setup_crane).
"""

import importlib
import json
import os
import shutil
import subprocess
import sys
import time
import traceback

import bpy
import numpy as np

OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_test_setup_crane"))
HERE = os.path.dirname(os.path.abspath(__file__))
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "ui_test_setup_crane.log"), "w")
RESULTS = []
STEPS = []
S = {}
CRANES = [("AT-40", ""), ("CC-750", ""), ("KB-50", ""), ("KB-50", "CRANE_OTHER")]   # the last: roles by hand


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


def main_window():
    wm = bpy.context.window_manager
    setup = mod("blender.ops_setup")
    return next(w for w in wm.windows if not setup.is_setup_window(w))


def override(win=None):
    win = win or main_window()
    area = next(a for a in win.screen.areas if a.type == "VIEW_3D")
    region = next(r for r in area.regions if r.type == "WINDOW")
    return bpy.context.temp_override(window=win, screen=win.screen, area=area, region=region, scene=win.scene)


def op(idname, **kw):
    group, name = idname.split(".")
    with override():
        return getattr(getattr(bpy.ops, group), name)("EXEC_DEFAULT", True, **kw)


def redraw():
    for w in bpy.context.window_manager.windows:
        for a in w.screen.areas:
            a.tag_redraw()


def shot_window(win, name):
    """A picture of one window (the Set-up window: its side panel fills it)."""
    full = os.path.join(OUT, "_full.png")
    subprocess.run(["import", "-window", "root", full], check=False)
    try:
        x, y, w, h = win.x, win.y, win.width, win.height
        main = main_window()
        top = main.height - (y + h) if y >= 0 else 0
        subprocess.run(["convert", full, "-crop", f"{w}x{h}+{x}+{max(0, top)}", "+repage",
                        os.path.join(OUT, name + ".png")], check=False)
    except Exception:  # noqa: BLE001
        shutil.copyfile(full, os.path.join(OUT, name + ".png"))


def step(fn):
    STEPS.append(fn)
    return fn


def new_project(step_path=None):
    with override():
        bpy.ops.wm.read_homefile(use_empty=True)
    sc = main_window().scene          # (in a timer right after a load, bpy.context.scene can still be None)
    mod("blender.workspaces").use_all(sc)
    sc.fresing.out_folder = os.path.join(OUT, "work")
    mod("blender.lifting").forget()
    mod("blender.setup_crane").forget()
    if step_path:
        res = op("fresing.import_step", filepath=step_path, quality="normal")
        S["import"] = (os.path.basename(step_path), res, time.time())


def import_done():
    """The real app imports in the background (the button returns at once): wait for the model."""
    name, res, t0 = S["import"]
    roots = mod("blender.build").model_roots(bpy.context.scene)
    if not roots and time.time() - t0 < 300:
        return False
    check(f"{name} imported", len(roots) == 1, f"{res}, {time.time() - t0:.0f} s")
    return True
    return bpy.context.scene


def class_answer(data, target):
    """0201's class solver (tests/lifting_reach_class.py), else None."""
    sys.path.insert(0, os.path.join(HERE, "..", "tests"))
    try:
        import lifting_reach_class as RC
    except ImportError:
        return None
    LL = mod("core.lifting_library")
    return RC.class_hook_to(data, target, {}, LL.charts_of(LL.from_data(data)))


@step
def s_start():
    log("extension", pkg())
    win = bpy.context.window_manager.windows[0]
    win.event_simulate(type="ESC", value="PRESS", x=700, y=500)      # the splash screen first (CLAUDE.md 8)
    win.event_simulate(type="ESC", value="RELEASE", x=700, y=500)
    L = mod("blender.lifting")
    S["understood"] = L.understood(background=False)
    L.set_understood(True)
    S["lib"] = os.path.join(OUT, "library")
    shutil.rmtree(S["lib"], ignore_errors=True)
    os.makedirs(S["lib"], exist_ok=True)
    S["i"] = 0
    return 1.0


def _cls():
    return CRANES[S["i"]][0]


@step
def s_import():
    cls = _cls()
    LL = mod("core.lifting_library")
    new_project(os.path.join(LL.BUILTIN_DIR, cls, cls + ".step"))
    return 1.0


@step
def s_imported():
    if not import_done():
        return "again"
    cls = _cls()
    ex = mod("blender.crane_example")
    kind = CRANES[S["i"]][1] or ex.KINDS[ex.builtin(cls)["kind"]]
    S["kind"] = kind
    with override():
        res = bpy.ops.fresing.crane_setup("EXEC_DEFAULT", True, kind=kind)
    check(f"{cls}: Set up a crane… opens on '{kind}'", "FINISHED" in res and
          bpy.context.scene.fresing.setup_kind == kind, str(res))
    return 3.0


@step
def s_window():
    cls = _cls()
    setup = mod("blender.ops_setup")
    wins = setup.setup_windows()
    check(f"{cls}: the Set-up window is open", len(wins) == 1, f"{len(wins)} windows")
    if wins:
        setup.restore_tabs()
        S["win"] = wins[0]
    return 2.0


@step
def s_rig():
    cls = _cls()
    sc = bpy.context.scene
    ex = mod("blender.crane_example")
    t0 = time.time()
    with override():
        made = ex.rig(sc, cls, kind_override=S["kind"], check=not os.environ.get("UITEST_NO_CHECK"),
                      clash=(cls == "AT-40"))
    S["made"] = made
    SC = mod("blender.setup_crane")
    red = [p.text for p in SC.settings(sc).problems if p.severity == "red"]
    check(f"{cls}: rigged through the steps by names, Check finds nothing wrong"
          + (" (clash check included)" if cls == "AT-40" else ""), not red,
          f"{time.time() - t0:.1f} s; " + "; ".join(red[:3]))
    S["shots"] = 0
    S["k"] = 0
    return 1.0


@step
def s_steps():
    """Every step of the kind drawn in the Set-up window, a picture each."""
    sc = bpy.context.scene
    SC = mod("blender.setup_crane")
    setup = mod("blender.ops_setup")
    steps = SC.STEP_LISTS[S["kind"]]
    k = S["k"]
    if k > 0 and S.get("win") is not None:
        shot_window(S["win"], f"{_cls()}_{S['kind']}_step_{k:02d}_{steps[k - 1][0]}")
        S["shots"] += 1
    if k < len(steps):
        setup.go(sc, k)
        redraw()
        S["k"] += 1
        return "again"
    check(f"{_cls()}: all {len(steps)} steps of '{S['kind']}' drawn in the Set-up window", S["shots"] == len(steps)
          or S.get("win") is None, f"{S['shots']} pictures")
    return 0.5


@step
def s_save():
    cls = _cls()
    sc = bpy.context.scene
    RO = mod("blender.lifting_rig_out")
    ex = mod("blender.crane_example")
    with override():
        res = bpy.ops.fresing.crane_save("EXEC_DEFAULT", True, library=S["lib"])
    path = mod("blender.setup_crane").settings(sc).saved_path
    ok = res == {"FINISHED"} and os.path.isfile(path)
    diffs = ["not saved"]
    if ok:
        with open(path, encoding="utf-8") as fh:
            saved = json.load(fh)
        diffs = ex.compare(cls, saved, S["made"])
    check(f"{cls}: Save to library – the file is the built-in rig (joints, roles, couplings, limits, axes, hook point, "
          "poses, masses, CoG, charts)", ok and not diffs, "; ".join(diffs[:4]))
    S["path"] = path
    del RO
    with override():
        bpy.ops.fresing.setup_close("EXEC_DEFAULT", True)
    return 2.0


@step
def s_place_project():
    new_project()                                  # (the window's scene is there only after this timer step)
    return 1.0


@step
def s_place():
    cls = _cls()
    sc = main_window().scene
    L = mod("blender.lifting")
    S["lib_n"] = S.get("lib_n", 0) + 1
    LR = mod("core.lifting_reach")
    ex = mod("blender.crane_example")
    with override():
        own = L.place(bpy.context, S["path"], (0.0, 0.0, 0.0), 0.0)
        ref = L.place(bpy.context, os.path.join(mod("core.lifting_library").BUILTIN_DIR, cls), (0.0, 400.0, 0.0), 0.0)
    with open(S["path"], encoding="utf-8") as fh:
        saved = json.load(fh)
    names = {j.name for j in L.own_joints(sc, own)}
    check(f"{cls}: placed from the library – its joints and poses as saved",
          names == {L.prefix(own) + j["name"] for j in saved["rig"]["joints"]}
          and set(L.pose_names(own)) == {p["name"] for p in saved["rig"]["poses"]})
    data = ex.builtin(cls)
    rig = LR.Rig(data)
    rng = np.random.default_rng(3)
    bad, n, cls_n = [], 0, 0
    for _k in range(30):
        vals = {j["name"]: float(rng.uniform(*j["limits"])) for j in rig.driven() if j.get("limits")}
        target = rig.hook(vals)
        want = L.hook_to(sc, ref, L.to_world(ref, target))
        if not want.ok:
            continue
        got = L.hook_to(sc, own, L.to_world(own, target))
        n += 1
        if not got.ok or abs(got.boom - want.boom) > 0.002 or (want.use is not None and
                                                              abs((got.use or 0) - want.use) > 1e-6):
            bad.append(f"{np.round(target)}: {got.reason or (got.boom, want.boom, got.use, want.use)}")
        c = class_answer(data, target)
        if c is not None and c.ok:
            cls_n += 1
            if abs(got.boom - c.boom) > 0.002 or (c.use is not None and abs((got.use or 0) - c.use) > 1e-6):
                bad.append(f"class {np.round(target)}: {got.boom} != {c.boom}")
    check(f"{cls}: Hook to here on the own crane = the built-in crane's answer (and the class solver's)",
          n >= 10 and not bad, f"{n} targets, {cls_n} against the class solver; " + "; ".join(bad[:3]))
    return 1.0


@step
def s_next():
    S["i"] += 1                                     # (here, not in s_place: a failed step must not repeat a crane)
    if S["i"] < len(CRANES):
        _i[0] = STEPS.index(s_import) - 1          # the next crane: from its import again
    return 0.5


@step
def s_finish():
    L = mod("blender.lifting")
    L.set_understood(S.get("understood", False))     # preferences as they were (CLAUDE.md 8)
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
    if r == "again":
        return 0.6
    _w[0] = 0.0
    _i[0] += 1
    return r


bpy.app.timers.register(driver, first_interval=3.0, persistent=True)
