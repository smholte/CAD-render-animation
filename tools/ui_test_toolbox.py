"""Real-app test, task 0217: a house from House Planner by itself, in the app with a window. The app's own watcher
(started with the app, folder ``TOOLBOX_HOME``) sees a job made the way House Planner makes it; Bake now (the
operator as its button calls it) switches the window to the house's own scene, bakes with the House panel's modal
operator (progress, Cancel), sends the package back, and the window shows the owner's scene again – the house scene
gone, the project unchanged. Then a second job is cancelled with cancel.json while it bakes.

    TOOLBOX_HOME=/tmp/tb xvfb-run -a -s "-screen 0 1800x2600x24" blender --app-template fresing_render \\
        --enable-event-simulate --python tools/ui_test_toolbox.py
Screenshots and the log go to $UITEST_OUT (default ~/fresing_ui_test_toolbox)."""

import importlib
import json
import os
import time
import traceback
from pathlib import Path

import bpy

OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_test_toolbox"))
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "ui_test_toolbox.log"), "w")
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


def ui():
    win = bpy.context.window_manager.windows[0]
    area = next(a for a in win.screen.areas if a.type == "VIEW_3D")
    region = next(r for r in area.regions if r.type == "WINDOW")
    return win, area, region


def override():
    win, area, region = ui()
    return bpy.context.temp_override(window=win, screen=win.screen, area=area, region=region, scene=win.scene)


def wiggle():
    win, _area, region = ui()
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=region.x + 300 + int(time.time()) % 7, y=region.y + 300)


def status(jid):
    p = S["root"] / "tools" / "nl.fresing.render" / "inbox" / jid / "status.json"
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return {}


def project():
    sc = bpy.data.scenes.get(S["orig"])
    return {"scenes": sorted(s.name for s in bpy.data.scenes), "objects": sorted(o.name for o in sc.objects),
            "world": sc.world.name if sc.world else None}


STEPS = []


def step(fn):
    STEPS.append(fn)
    return fn


@step
def s_setup():
    tb, ti = mod("core.toolbox"), mod("blender.toolbox_inbox")
    root = tb.home()
    S["root"] = root
    ib = ti.inbox()
    check("the app watches the Toolbox folder from its start", ib is not None and Path(ib.root) == root, str(root))
    check("the app wrote its manifest and the folder's mark", (root / "tools" / tb.ME / "toolbox.json").is_file()
          and (root / "toolbox-folder.json").is_file())
    ti.use_folder(root, samples=4, photo_samples=4, quick=True)          # the same folder; bake small
    sc = bpy.context.window.scene
    S["orig"] = sc.name
    me = bpy.data.meshes.new("Owner part")
    me.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 1, 2)])
    sc.collection.objects.link(bpy.data.objects.new("Owner part", me))
    S["before"] = project()
    house = Path(mod("blender.tour").DATA) / "sample-house.hpscene"
    S["house"] = house
    S["job"] = tb.play_house_planner(root, house, "Sample house – real app")
    S["t"] = time.time()
    return 1.0


@step
def s_waiting():
    ti = mod("blender.toolbox_inbox")
    if status(S["job"]).get("state") != "waiting":
        wiggle()
        return "wait"
    check("the timer took the job: waiting for Bake now", status(S["job"])["text"].endswith("press Bake now"),
          f"{time.time() - S['t']:.1f} s")
    with override():
        card = bpy.types.FRESING_PT_next.poll(bpy.context) and mod("blender.ui_top")._toolbox_here(bpy.context)
    check("with no model open the What's next card shows the house with Bake now", card)
    mod("blender.panels").open_to("FRESING_PT_house")
    with override():
        shown = bpy.types.FRESING_PT_house.poll(bpy.context)
    check("the House panel shows it with no house in the project", shown and [j.id for j in ti.waiting()] == [S["job"]])
    alive = S["root"] / "tools" / "nl.fresing.render" / "alive.json"
    check("alive.json is written while the app is open", alive.is_file())
    for area in bpy.context.window_manager.windows[0].screen.areas:
        area.tag_redraw()
    return 1.5


@step
def s_bake_now():
    import subprocess
    subprocess.run(["import", "-window", "root", os.path.join(OUT, "01_waiting.png")], check=False)
    with override():
        res = bpy.ops.fresing.toolbox_start(job=S["job"])
    check("Bake now starts", res == {"FINISHED"}, str(res))
    win = bpy.context.window_manager.windows[0]
    check("the window shows the house's own scene", win.scene.name.startswith("House – "), win.scene.name)
    check("the House panel's bake runs (progress, Cancel)", mod("blender.ops_house").runtime(win.scene).get("running"))
    S["t"] = time.time()
    S["fractions"] = []
    return 0.5


@step
def s_baking_shot():
    import subprocess
    subprocess.run(["import", "-window", "root", os.path.join(OUT, "02_baking.png")], check=False)
    return 0.1


@step
def s_done():
    st = status(S["job"])
    if st.get("state") == "working":
        S["fractions"].append(st.get("fraction", 0))
    if st.get("state") in (None, "waiting", "working") or mod("blender.toolbox_inbox")._S["bake"] is not None:
        wiggle()
        return "wait"
    check("done and sent back", st.get("state") == "done" and st.get("reply") and
          st.get("text", "").endswith("sent back to House Planner"), str(st))
    check("progress reached House Planner while it baked", len(set(S["fractions"])) >= 2, str(S["fractions"][:6]))
    reply = S["root"] / "tools" / "nl.fresing.house-planner" / "inbox" / st.get("reply", "-")
    job = json.loads((reply / "job.json").read_text("utf-8")) if (reply / "job.json").is_file() else {}
    check("the reply job carries the .hpbake", job.get("files", [{}])[0].get("type") == "hpbake")
    hs = mod("core.house_scene")
    bake = reply / job["files"][0]["name"] if job else reply / "-"
    check("the package is right", bake.is_file() and not hs.structure_problems(str(bake), hs.read_scene(str(S["house"]))))
    win = bpy.context.window_manager.windows[0]
    check("the window shows the owner's scene again", win.scene.name == S["orig"], win.scene.name)
    check("the house scene is gone and the project is as it was", project() == S["before"], str(project()))
    check("the panel says Sent back", mod("blender.toolbox_inbox").last_result() == "Sent back to House Planner")
    tb = mod("core.toolbox")
    S["job2"] = tb.play_house_planner(S["root"], S["house"], "Sample house – cancelled")
    return 1.0


@step
def s_cancel_start():
    if status(S["job2"]).get("state") != "waiting":
        wiggle()
        return "wait"
    with override():
        bpy.ops.fresing.toolbox_start(job=S["job2"])
    tb = mod("core.toolbox")
    tb.write_json(S["root"] / "tools" / tb.ME / "inbox" / S["job2"] / "cancel.json",
                  {"format": "toolbox-cancel", "version": "0.1", "job": S["job2"], "asked": tb.now()})
    return 0.5


@step
def s_cancelled():
    st = status(S["job2"])
    if st.get("state") in (None, "waiting", "working") or mod("blender.toolbox_inbox")._S["bake"] is not None:
        wiggle()
        return "wait"
    check("cancel.json stops the bake: cancelled, nothing sent", st.get("state") == "cancelled" and "reply" not in st,
          str(st))
    replies = os.listdir(S["root"] / "tools" / "nl.fresing.house-planner" / "inbox")
    check("only the first job's reply is in House Planner's inbox", len(replies) == 1, str(replies))
    check("the project is as it was after Cancel", project() == S["before"], str(project()))
    return 1.0


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
        if time.time() - _w[0] > 400:
            check(fn.__name__ + " timeout", False)
            _i[0] += 1
            _w[0] = 0.0
        return 1.0
    _w[0] = 0.0
    _i[0] += 1
    return r


bpy.app.timers.register(driver, first_interval=3.0, persistent=True)
