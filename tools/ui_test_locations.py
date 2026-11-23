"""Real-app test, Locations and Exports (task 0272): two set-up files (a company one, copied, and a department one,
linked) plus the user's own folder; a logo and a rule set from each show with their badges in the app's lists (the
same logo name twice: both shown); a rule set from the company is used; saving a rule set asks where (own folders
first); Fresing Settings opens on Locations and on Exports; a renamed newer department file updates it with a change
list; an own folder on a server that does not answer does not slow the start's reading (time in the log); an output's
Save to and "Also save a copy to" put a still into both places.

Install the extension and the app template first (see ui_test_app.py), then run:
    xvfb-run -a -s "-screen 0 1920x1080x24" blender --app-template fresing_render --enable-event-simulate \\
        -p 0 0 1920 1080 --python tools/ui_test_locations.py
Screenshots and ui_test_locations.log go to $UITEST_OUT (default ~/fresing_ui_test_locations).
"""

import os
import subprocess
import tempfile
import time
import traceback

import bpy

OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_test_locations"))
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "ui_test_locations.log"), "w")
RESULTS = []
TMP = tempfile.mkdtemp(prefix="fr_locations é ")
S = {}


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
    return importlib.import_module(pkg() + ("." + name if name else ""))


def view():
    sm = mod("blender.ops_setup")
    win = next(w for w in bpy.context.window_manager.windows if not sm.tab_of(w))
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


def folder(*parts, files=None):
    d = os.path.join(TMP, *parts)
    os.makedirs(d, exist_ok=True)
    for name, text in (files or {}).items():
        with open(os.path.join(d, name), "w", encoding="utf-8") as fh:
            fh.write(text)
    return d


def rule_set(where, name):
    RS = mod("core.rule_sets")
    os.makedirs(where, exist_ok=True)
    RS.save_in(where, RS.empty(name))


STEPS = []


def step(fn):
    STEPS.append(fn)
    return fn


@step
def s_start():
    check("the extension is on", pkg() is not None)
    win, area, _r = view()
    win.event_simulate(type="ESC", value="PRESS", x=area.x + 30, y=area.y + 30)     # the splash swallows keys
    win.event_simulate(type="ESC", value="RELEASE", x=area.x + 30, y=area.y + 30)
    loc, L = mod("blender.locations"), mod("core.locations")
    st = loc.state()
    check("the first start made the user's own folders, switched on", st["migrated"] and all(
        any(f["on"] and f.get("ready") for f in st["mine"][k.key]) for k in L.KINDS), loc.mine_list("logos"))
    mine = loc.mine_list("logos")[0]["path"]
    with open(os.path.join(mine, "acme.png"), "wb") as fh:            # the same name as the company's logo
        fh.write(b"mine")
    rule_set(loc.mine_list("rule_sets")[0]["path"], "My rules")
    share = folder("server é", "Rule sets")
    rule_set(share, "Acme rules")
    c = os.path.join(TMP, "Company set-up.frsetup")
    L.write_setup(c, L.Setup(id="acme-co", name="Acme standard", level="company", version=3,
                             locations={"rule_sets": [share]}, settings={"keep_howto": True}),
                  {"logos": folder("c logos", files={"acme.png": "company"})})
    d = os.path.join(TMP, "net é", "Offshore.frsetup")
    os.makedirs(os.path.dirname(d))
    dep_rules = folder("d rules")
    rule_set(dep_rules, "Offshore rules")
    L.write_setup(d, L.Setup(id="acme-off", name="Offshore", level="department", label="Offshore department",
                             version=1), {"logos": folder("d logos", files={"buoy.png": "d"}),
                                          "rule_sets": dep_rules})
    S.update(c=c, d=d, share=share)
    with override():
        r1 = bpy.ops.fresing.loc_setup_add("EXEC_DEFAULT", True, filepath=c, mode="COPY")
        r2 = bpy.ops.fresing.loc_setup_add("EXEC_DEFAULT", True, filepath=d, mode="LINK")
    check("Add a set-up file…: the company's (copied) and the department's (linked)",
          r1 == r2 == {"FINISHED"} and [e["mode"] for e in loc.state()["setups"]] == ["copy", "link"], (r1, r2))
    p = mod("blender.prefs").get()
    check("the company set-up's settings are in use", p.keep_howto is True)
    loc.wait_reach()
    return 0.5


@step
def s_lists():
    decals, rule_sets, ops_rs = mod("blender.decals"), mod("blender.rule_sets"), mod("blender.ops_rule_sets")
    pics = [label for label, _p in decals.library_pictures()]
    log("logos:", pics)
    check("logos of every folder with their badges, the same name twice shown twice",
          "Logos: acme  ·  Company" in pics and "Logos: acme  ·  Mine" in pics
          and "Logos: buoy  ·  Offshore department" in pics, pics)
    labels = [e[1] for e in ops_rs._library_entries()]
    log("rule sets:", labels)
    check("rule sets of every folder with their badges", "Acme rules  ·  Company" in labels
          and "Offshore rules  ·  Offshore department" in labels and "My rules  ·  Mine" in labels, labels)
    s = bpy.context.scene.fresing
    with override():
        r = bpy.ops.fresing.rule_set_switch("EXEC_DEFAULT", True, name="Acme rules")
    check("a rule set from the company's folder is used", r == {"FINISHED"} and s.rule_set == "Acme rules", r)
    ch = mod("blender.locations").save_choices("rule_sets")
    check("saving a rule set asks where: own folder first, then the company's share; never inside a set-up",
          [lbl.split(":")[0] for _p, lbl in ch] == ["Mine", "Company"], ch)
    with override():
        r = bpy.ops.fresing.decal_library("EXEC_DEFAULT", True,
                                          picture=next(p for lbl, p in decals.library_pictures() if "Company" in lbl))
    check("a company logo can be picked for a decal", r == {"FINISHED"}
          and "acme" in bpy.context.scene.fresing_decal.picture, r)
    return 0.3


@step
def s_open_locations():
    with override():
        r = bpy.ops.fresing.settings("INVOKE_DEFAULT", tab="locations")
    check("Fresing Settings opens on Locations", r == {"FINISHED"} and mod("blender.ui_settings").current()
          == "locations", r)
    S["t"] = time.time()
    return 1.5


@step
def s_locations_shot():
    st = mod("blender.ops_settings")
    if not st.settings_windows() and time.time() - S["t"] < 20:
        return "again"
    check("the Settings window is open", bool(st.settings_windows()))
    drawn = mod("blender.ui_settings").draw_all(bpy.context)
    check("Locations and Exports draw", "locations" in drawn and "exports" in drawn, drawn)
    redraw()
    shot("10_locations")
    st.set_tab("exports")
    redraw()
    return 1.0


@step
def s_exports_shot():
    shot("11_exports")
    return 0.2


@step
def s_update():
    loc, L = mod("blender.locations"), mod("core.locations")
    renamed = os.path.join(os.path.dirname(S["d"]), "Offshore department NEW.frsetup")      # another file name
    L.write_setup(renamed, L.Setup(id="acme-off", name="Offshore", level="department", label="Offshore department",
                                   version=2, locations={"logos": [folder("d more logos")]}))
    new, old, lines = loc.check(renamed)
    check("a renamed newer file is the same set-up: the change list says what changes",
          old is not None and old.version == 1 and new.version == 2 and "Version 1 → 2" in lines, lines)
    with override():
        r = bpy.ops.fresing.loc_setup_update("EXEC_DEFAULT", True, filepath=renamed, mode="LINK")
    check("Update: the department set-up is at version 2", r == {"FINISHED"}
          and loc.setup_of("acme-off").version == 2, r)
    return 0.3


@step
def s_dead_folder():
    loc, L = mod("blender.locations"), mod("core.locations")
    dead = os.path.join(TMP, "server that does not answer")
    os.environ[L.SLOW_ENV] = f"{dead}=20"
    loc.add_mine("logos", os.path.join(dead, "Logos"))
    loc.forget()
    t0 = time.perf_counter()
    loc.load()
    pics = mod("blender.decals").library_pictures()
    took = time.perf_counter() - t0
    log(f"start's reading with a folder on a server that does not answer (20 s): {took * 1000:.0f} ms")
    states = [f.reach for f in loc.folders("logos") if f.path.startswith(dead)]
    check("an own folder on a server that does not answer does not slow the start (< 0.5 s)", took < 0.5
          and states == [None] and pics, f"{took:.3f} s, {states}")
    os.environ.pop(L.SLOW_ENV, None)
    loc.remove_mine("logos", len(loc.mine_list("logos")) - 1)
    return 0.3


@step
def s_outputs():
    loc = mod("blender.locations")
    scene = bpy.context.scene
    share = folder("marketing é")
    with override():
        bpy.ops.fresing.loc_place_add("EXEC_DEFAULT", True, directory=share, name="Marketing", project_sub=False)
        bpy.ops.fresing.out_place("EXEC_DEFAULT", True, place="pictures")
        bpy.ops.fresing.loc_also_to("EXEC_DEFAULT", True, place="mine:Marketing")
    render = mod("blender.render")
    check("Save to: the project's place decides the folder of every output",
          render.default_output_dir(scene) == loc.output_dir(scene)
          and loc.output_dir(scene).startswith(os.path.join(render.pictures_dir(), "Fresing Render")),
          loc.output_dir(scene))
    still = os.path.join(TMP, "still.png")
    with open(still, "wb") as fh:
        fh.write(b"png")
    copy = loc.copy_also(scene, still)
    check("Also save a copy to: the still is copied into the second place", copy and os.path.isfile(copy)
          and os.path.dirname(copy) == share, copy)
    with override():
        bpy.ops.fresing.loc_also("EXEC_DEFAULT", True, on=False)
        bpy.ops.fresing.out_place("EXEC_DEFAULT", True, place="DEFAULT")
    return 0.2


@step
def s_finish():
    failed = [r for r in RESULTS if not r[1]]
    log(f"RESULT {len(RESULTS) - len(failed)}/{len(RESULTS)} passed")
    LOG.close()
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


bpy.app.timers.register(driver, first_interval=3.0, persistent=True)
