"""Real-app test, the material picker (task 0273): 3 Looks > More materials… opens the Materials window (one window,
only its page); a click on a material's name picks it, a second click gives the picked group that material; the star
puts it on this project's list and the short list in 3 Looks shows it; Use for the group; the filters narrow the
list; Save as my material… (a folder with material.json and a picture made by a background Blender); From a Blender
material… (appended into the project); the window follows the group picked in 3 Looks; its draw stays quick with
every material; Close. Guide picture of the window when GUIDE_OUT is set.

Install the extension and the app template first (see ui_test_app.py), then run:
    xvfb-run -a -s "-screen 0 1920x1080x24" blender --app-template fresing_render \\
        --enable-event-simulate -p 0 0 1920 1080 --python tools/ui_test_material_picker.py
Screenshots and ui_test_material_picker.log go to $UITEST_OUT (default ~/fresing_ui_test_material_picker).
"""

import os
import shutil
import subprocess
import tempfile
import time
import traceback

import bpy

OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_test_material_picker"))
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "ui_test_material_picker.log"), "w")
RESULTS = []
TMP = tempfile.mkdtemp(prefix="fr_materials é ")
MINE = os.path.join(TMP, "Materials")
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


def main_win():
    sm = mod("blender.ops_setup")
    return next(w for w in bpy.context.window_manager.windows if not sm.tab_of(w))


def view():
    win = main_win()
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


def mat_wins():
    return mod("blender.ops_material_picker").materials_windows()


def page(win):
    area = mod("blender.ops_settings").settings_area(win)
    return area, next(r for r in area.regions if r.type == "TOOLS")


def state():
    return bpy.context.window_manager.fresing_matpick


def group():
    s = bpy.context.scene.fresing
    return s.groups[s.groups_index]


STEPS = []


def step(fn):
    STEPS.append(fn)
    return fn


def wait_until(name, cond, seconds=30.0):
    def fn():
        if "t_wait" not in S:
            S["t_wait"] = time.time()
        try:
            ok = cond()
        except Exception:  # noqa: BLE001
            ok = False
        if ok or time.time() - S["t_wait"] > seconds:
            check(name, ok, f"{time.time() - S.pop('t_wait'):.1f} s")
            return 0.3
        redraw()
        return "again"
    fn.__name__ = "wait_" + name[:30].replace(" ", "_")
    STEPS.append(fn)


@step
def s_start():
    check("the extension is on", pkg() is not None)
    win, area, _r = view()
    win.event_simulate(type="ESC", value="PRESS", x=area.x + 30, y=area.y + 30)     # the splash swallows keys
    win.event_simulate(type="ESC", value="RELEASE", x=area.x + 30, y=area.y + 30)
    return 1.0


@step
def s_import():
    data = os.path.join(os.path.dirname(mod("").__file__), "data", "test_crane_a.step")
    with override():
        r = bpy.ops.fresing.import_step("EXEC_DEFAULT", filepath=data, quality="draft")
    log("import:", r)
    return 1.0


wait_until("the test crane is imported", lambda: len(bpy.context.scene.fresing.groups) >= 3, 120)


@step
def s_folders():
    loc = mod("blender.locations")
    os.makedirs(MINE, exist_ok=True)
    loc.add_mine("materials", MINE)
    loc.wait_reach()
    bpy.context.scene.fresing.groups_index = 0
    mod("blender.panels").open_to("FRESING_PT_looks")
    return 1.0


@step
def s_open():
    S["t_open"] = time.time()
    mod("blender.ui_material_picker").FIRST_DRAW.clear()
    with override():
        r = bpy.ops.fresing.materials("EXEC_DEFAULT", True)
    check("More materials… starts the Materials window", r == {"FINISHED"})
    return 0.3


wait_until("the Materials window opens", lambda: len(mat_wins()) == 1, 20)


@step
def s_settle():
    w = mat_wins()[0]
    ok, other = mod("blender.ops_settings").shows_only_the_page(w)
    if not ok and S.setdefault("tries", 0) < 40:
        S["tries"] += 1
        return "again"
    check("the window shows only its page: no tab, no 3D view, no header", ok, other)
    first = mod("blender.ui_material_picker").FIRST_DRAW
    check("its first draw (the pictures load after it, a few at a time)", bool(first),
          f"{first[0] - S['t_open']:.1f} s after the click" if first else "never drawn")
    with override():
        bpy.ops.fresing.materials("EXEC_DEFAULT", True)
    return 1.0


@step
def s_one_window():
    check("opening it again brings the same window (one at a time)", len(mat_wins()) == 1, len(mat_wins()))
    UI = mod("blender.ui_material_picker")
    st = state()
    check("it shows the group's own material picked", st.picked == mod("blender.material_picker").group_key(group()),
          st.picked)
    st.picked = ""
    st.size = 4.0
    S["visible"] = len(UI.visible(bpy.context))
    check("the window lists every material", S["visible"] >= 100, S["visible"])
    S["first"] = UI.visible(bpy.context)[0].key
    S["probe"] = 0
    return 2.0


def cell_points(win):
    """Points over the first picture's name button (the grid's first cell), from top to bottom: the grid starts under
    the window's title row and its count row; its exact place depends on Blender's layout, so a few are tried."""
    _area, reg = page(win)
    scale = bpy.context.preferences.system.ui_scale or 1.0
    left = reg.x + reg.width * 0.2 + 14 * scale
    x = int(left + 30 * scale)
    top = reg.y + reg.height
    pic = state().size * 20 * scale
    first = top - (24 + 20 + 8) * scale - pic        # title, count row, gaps, the picture
    return [(x, int(first - dy * scale)) for dy in (2, 8, 14, 20, 26, 32, -4, 38)]


@step
def s_click_name():
    win = mat_wins()[0]
    pts = cell_points(win)
    if S["probe"] >= len(pts) * 2:
        check("a click on a material's name picks it", False, "no point picked a material")
        with override():
            bpy.ops.fresing.mat_pick("EXEC_DEFAULT", True, key=S["first"])
        return 0.5
    x, y = pts[S["probe"] // 2]
    S["probe"] += 1
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x, y=y)
    win.event_simulate(type="LEFTMOUSE", value="PRESS", x=x, y=y)
    win.event_simulate(type="LEFTMOUSE", value="RELEASE", x=x, y=y)
    S["at"] = (x, y)
    return 0.9                       # longer than a double click: the next try is a new first click


@step
def s_picked():
    if not state().picked and S["probe"] < len(cell_points(mat_wins()[0])) * 2:
        STEPS_BACK[0] = True
        return 0.1
    check("a click on a material's name picks it (shown large on the right)", bool(state().picked),
          f"{state().picked} at {S.get('at')}")
    S["picked"] = state().picked
    return 0.3


STEPS_BACK = [False]


@step
def s_double():
    g = group()
    S["before"] = (g.material, g.mat_key)
    win = mat_wins()[0]
    x, y = S["at"]
    win.event_simulate(type="LEFTMOUSE", value="PRESS", x=x, y=y)       # pick it again …
    win.event_simulate(type="LEFTMOUSE", value="RELEASE", x=x, y=y)
    return 0.5


@step
def s_double_2():
    win = mat_wins()[0]
    x, y = S["at"]
    win.event_simulate(type="LEFTMOUSE", value="PRESS", x=x, y=y)       # … and a second click within a second
    win.event_simulate(type="LEFTMOUSE", value="RELEASE", x=x, y=y)
    return 0.8


@step
def s_double_check():
    g = group()
    e = mod("blender.material_picker").find(bpy.context.scene, S["picked"])
    check("a second click on the name gives the group that material", g.mat_key == S["picked"]
          and e is not None and g.material == mod("core.material_files").values_of(e)["material"],
          f"{S['before']} -> {(g.material, g.mat_key)}")
    path = shot("10_window")
    S["shot"] = path
    return 0.3


@step
def s_star():
    with override():
        r = bpy.ops.fresing.mat_star("EXEC_DEFAULT", True, key="preset:paint_5010")
        r2 = bpy.ops.fresing.mat_star("EXEC_DEFAULT", True, key="builtin:knurl_diamond")
    MP = mod("blender.material_picker")
    listed = [e.key for e, on, _u in MP.short_list(bpy.context.scene) if on]
    check("the star puts materials on this project's list", r == r2 == {"FINISHED"}
          and listed == ["preset:paint_5010", "builtin:knurl_diamond"], listed)
    with override():
        r = bpy.ops.fresing.mat_use("EXEC_DEFAULT", True, key="preset:paint_5010")
    g = group()
    check("Use for the group: blue paint RAL 5010", r == {"FINISHED"} and (g.material, g.color) ==
          ("paint_satin", "RAL 5010"), (g.material, g.color))
    with override():
        bpy.ops.ed.undo()
    check("Ctrl+Z takes it back", group().mat_key != "preset:paint_5010", group().mat_key)
    with override():
        bpy.ops.ed.redo()
    return 0.5


@step
def s_filters():
    UI = mod("blender.ui_material_picker")
    st = state()
    st.kind = "Stainless"
    a = UI.visible(bpy.context)
    st.kind = UI.ALL
    st.look = "see-through"
    b = UI.visible(bpy.context)
    st.look = UI.ALL
    st.search = "knurl"
    c = UI.visible(bpy.context)
    st.search = ""
    check("the filters narrow the list (Stainless, see-through, 'knurl')",
          a and all(e.kind == "Stainless" for e in a) and b and all("see-through" in e.looks for e in b)
          and c and all("knurl" in (e.name + e.description).lower() for e in c), f"{len(a)}, {len(b)}, {len(c)}")
    return 0.3


@step
def s_save():
    g = group()
    g.material, g.color, g.wear = "paint_satin", "RAL 5015", 0.2
    with override():
        r = bpy.ops.fresing.mat_save("EXEC_DEFAULT", True, name="Test blue", description="made by the test",
                                     where=MINE)
    F = mod("core.material_files")
    folder = os.path.join(MINE, "Test blue")
    check("Save as my material… writes its folder", r == {"FINISHED"}
          and os.path.isfile(os.path.join(folder, F.JSON_NAME)), r)
    check("the group then uses it", group().mat_key.startswith("own:"), group().mat_key)
    S["own"] = group().mat_key
    S["t_pic"] = time.time()
    return 0.5


wait_until("its picture is made by a background Blender (the app does not wait)",
           lambda: os.path.isfile(os.path.join(MINE, "Test blue", "picture.png"))
           and not mod("blender.material_picker").busy_pictures(), 180)


@step
def s_badge():
    MP = mod("blender.material_picker")
    e = MP.find(bpy.context.scene, S["own"])
    check("it is listed under Mine with its picture", e is not None and e.badge == "Mine" and bool(e.picture),
          (e.badge, e.picture) if e else None)
    log(f"picture made {time.time() - S['t_pic']:.1f} s after Save")
    mat = bpy.data.materials.new("Test shop red")
    mat.use_nodes = True
    mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.8, 0.05, 0.03, 1.0)
    s = bpy.context.scene.fresing
    s.groups_index = 1
    with override():
        r = bpy.ops.fresing.mat_from_blender("EXEC_DEFAULT", True, material=mat.name, name="Test shop red",
                                             use=True, where=MINE)
    g = group()
    gm = bpy.data.materials.get("FR " + g.name)
    check("From a Blender material…: saved, appended and used", r == {"FINISHED"} and g.material == "blender_material"
          and gm is not None and gm.get("fr_material") == "blender_material", (r, g.material))
    check("the window follows the group picked in 3 Looks", "Test shop red" in
          (MP.find(bpy.context.scene, MP.group_key(g)).name if MP.group_key(g) else ""), MP.group_key(g))
    redraw()
    return 1.0


@step
def s_draw_time():
    times = sorted(mod("blender.ui_material_picker").DRAW_TIMES[-20:])
    med = times[len(times) // 2] * 1000 if times else -1
    check(f"the window's draw stays quick with {S['visible']} materials (median under 20 ms)", 0 <= med < 20,
          f"{med:.1f} ms over {len(times)} draws")
    w = mat_wins()[0]
    path = shot("20_window_end")
    out = os.environ.get("GUIDE_OUT")
    if out:                                            # the guide's picture: the window as it stands
        sh = int(subprocess.run(["identify", "-format", "%h", path], capture_output=True, text=True).stdout or 1080)
        dst = os.path.join(out, "material_picker.png")
        subprocess.run(["convert", path, "-crop", f"{w.width}x{w.height}+{w.x}+{sh - w.y - w.height}", "+repage",
                        "-resize", "900x>", dst], check=False)
        log("guide picture:", dst)
    return 0.3


@step
def s_close():
    with override():
        bpy.ops.fresing.materials_close("EXEC_DEFAULT", True)
    return 1.0


wait_until("Close closes the window", lambda: not mat_wins(), 10)


@step
def s_finish():
    loc = mod("blender.locations")
    for i, f in enumerate(loc.mine_list("materials")):
        if f["path"] == MINE:
            loc.remove_mine("materials", i)
            break
    shutil.rmtree(TMP, ignore_errors=True)
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
    if STEPS_BACK[0]:                         # s_picked asks for another click
        STEPS_BACK[0] = False
        _i[0] = STEPS.index(s_click_name)
        return r
    if r == "again":
        return 0.2
    _i[0] += 1
    return r


bpy.app.timers.register(driver, first_interval=3.0, persistent=True)
