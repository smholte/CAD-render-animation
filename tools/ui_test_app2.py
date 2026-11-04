"""Real-app test, part 2: the remaining buttons (phase 1) and undo/redo with joints and animation.

Run: xvfb-run -a -s "-screen 0 1800x2600x24" blender --app-template fresing_render --enable-event-simulate --python ui_test2.py
"""

import math
import os
import subprocess
import time
import traceback

import bpy
from bpy_extras import view3d_utils
from mathutils import Vector

OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_test2"))
CRANE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "data", "test_crane_a.step")
CRANE_B = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "data", "test_crane_b.step")
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "ui_test2.log"), "w")
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
    return win, area, region


def override():
    win, area, region = ui()
    return bpy.context.temp_override(window=win, screen=win.screen, area=area, region=region, scene=win.scene)


def shot(name):
    subprocess.run(["import", "-window", "root", os.path.join(OUT, name + ".png")], check=False)


def to_window(world_pt):
    win, area, region = ui()
    co = view3d_utils.location_3d_to_region_2d(region, region.data, Vector(world_pt))
    return int(region.x + co.x), int(region.y + co.y)


def click(x, y):
    win = bpy.context.window_manager.windows[0]
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x, y=y)
    win.event_simulate(type="LEFTMOUSE", value="PRESS", x=x, y=y)
    win.event_simulate(type="LEFTMOUSE", value="RELEASE", x=x, y=y)


def key(k, ctrl=False, shift=False):
    win = bpy.context.window_manager.windows[0]
    win.event_simulate(type=k, value="PRESS", x=700, y=900, ctrl=ctrl, shift=shift)
    win.event_simulate(type=k, value="RELEASE", x=700, y=900, ctrl=ctrl, shift=shift)


def wiggle():
    win, area, region = ui()
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=region.x + 300 + int(time.time()) % 7, y=region.y + 300)


def find(name, n=0):
    hits = sorted((o for o in bpy.context.scene.objects if o.get("fr_name") == name), key=lambda o: o.get("fr_uid"))
    return hits[n] if len(hits) > n else None


def op(_idname, *args, undo=True, **kw):
    """Call an operator like a button press (EXEC, with an undo step)."""
    group, op_name = _idname.split(".")
    with override():
        return getattr(getattr(bpy.ops, group), op_name)("EXEC_DEFAULT", undo, **kw)


def tip():
    return find("BOOM").matrix_world @ Vector((1.5, 0, 0))


STEPS = []


def step(fn):
    STEPS.append(fn)
    return fn


@step
def s_start():
    win, area, region = ui()
    key("ESC")
    with override():
        bpy.ops.fresing.import_step(filepath=CRANE, quality="normal")
    return 1.0


@step
def s_wait():
    if bpy.context.scene.fresing.model_count == 0:
        return "wait"
    check("import", True)
    return 0.5


@step
def s_looks():
    s = bpy.context.scene.fresing
    with override():
        res = bpy.ops.fresing.pick_ral("INVOKE_DEFAULT")
    check("RAL picker opens", res in ({"RUNNING_MODAL"}, {"FINISHED"}, {"CANCELLED"}), res)
    return 0.8


@step
def s_looks2():
    shot("01_ral_popup")
    key("ESC")
    s = bpy.context.scene.fresing
    g = s.groups[s.groups_index]
    with override():
        bpy.ops.fresing.pick_ral("EXEC_DEFAULT", True, ral="RAL 5010") if "ral" in bpy.ops.fresing.pick_ral.get_rna_type().properties else None
    g.color = "RAL 5010"
    g.material = "paint_gloss"
    check("group colour + material change", g.color == "RAL 5010")
    r1 = op("fresing.scheme_save", name="Blue")
    g.color = "RAL 1003"
    r2 = op("fresing.scheme_apply", name="Blue")
    check("paint scheme save + apply", r1 == {"FINISHED"} and r2 == {"FINISHED"} and g.color == "RAL 5010", (r1, r2, g.color))
    path = os.path.join(OUT, "template.json")
    r3 = op("fresing.template_export", filepath=path)
    r4 = op("fresing.template_import", filepath=path)
    check("template export + import", r3 == {"FINISHED"} and r4 == {"FINISHED"} and os.path.isfile(path), (r3, r4))
    with override():
        r5 = bpy.ops.fresing.pick_hdri("INVOKE_DEFAULT", target="BACKGROUND")
        r6 = bpy.ops.fresing.template_from_library("INVOKE_DEFAULT")
    check("library pickers without a library say so (no crash)", True, (r5, r6))
    return 0.5


@step
def s_world():
    s = bpy.context.scene.fresing
    ok = True
    for bg in ("SKY", "TRANSPARENT", "HDRI", "COLOR"):
        try:
            s.background = bg
        except Exception as exc:
            ok = False
            log("background", bg, exc)
    s.floor = "VISIBLE"
    s.floor = "SHADOW"
    s.out_format = "brochure_a4"
    s.out_format = "presentation"
    check("background / floor / format switches", ok and bpy.context.scene.render.resolution_x == 1920)
    r = op("fresing.preview")
    check("live preview on", r == {"FINISHED"} and ui()[1].spaces.active.shading.type == "RENDERED")
    return 4.0


@step
def s_preview_shot():
    shot("02_live_preview")
    r = op("fresing.preview")
    check("live preview off", ui()[1].spaces.active.shading.type == "SOLID", r)
    return 0.5


@step
def s_cameras():
    s = bpy.context.scene
    n0 = len(mod("blender.cameras").fr_cameras(s))
    r1 = op("fresing.camera_add", view="FRONT")
    r2 = op("fresing.camera_add", view="VIEW")
    r3 = op("fresing.camera_fit")
    r4 = op("fresing.camera_dof")
    cams = mod("blender.cameras").fr_cameras(s)
    r5 = op("fresing.camera_activate", name=cams[0].name)
    r6 = op("fresing.camera_remove", name=cams[-1].name)
    check("cameras: add front / from view, fit, blur, switch, remove",
          len(cams) == n0 + 2 and all(r == {"FINISHED"} for r in (r1, r2, r3, r4, r5, r6)), (r1, r2, r3, r4, r5, r6))
    return 0.5


@step
def s_structure():
    s = bpy.context.scene.fresing
    s.small_part_mm = 45.0
    r1 = op("fresing.select_small")
    n_sel = len(bpy.context.selected_objects)
    r2 = op("fresing.exclude_selected")
    excluded = sum(1 for o in bpy.context.scene.objects if o.get("fr_excluded"))
    r3 = op("fresing.restore_excluded")
    trolley = find("TROLLEY.ASM")
    r4 = op("fresing.toggle_hide", name=trolley.name)
    hidden = trolley.hide_render
    r5 = op("fresing.show_all")
    r6 = op("fresing.toggle_lock", name=trolley.name)
    unlocked = not trolley.get("fr_locked", True)
    r7 = op("fresing.toggle_lock", name=trolley.name)
    check("clean-up, hide/show, lock/unlock",
          n_sel > 0 and excluded > 0 and hidden and unlocked and not trolley.hide_render,
          f"small {n_sel}, excluded {excluded}, results {(r1, r2, r3, r4, r5, r6, r7)}")
    return 0.5


@step
def s_joint_undo():
    s = bpy.context.scene.fresing
    boom = find("BOOM.ASM")
    with override():
        for o in bpy.context.selected_objects:
            o.select_set(False)
        boom.select_set(True)
        bpy.context.view_layer.objects.active = boom
    globals()["tip0"] = tip().copy()
    r = op("fresing.joint_add", kind="ROTATE", axis="Y", origin="CENTER")
    check("joint added (button)", r == {"FINISHED"} and len(s.joints) == 1, r)
    j = s.joints[0]
    j.motion["fr_value"] = math.radians(30)
    j.motion.update_tag()
    bpy.context.view_layer.update()
    globals()["tip30"] = tip().copy()
    with override():
        bpy.ops.ed.undo_push(message="slider")
        bpy.ops.ed.undo()
    return 0.8


@step
def s_after_undo1():
    s = bpy.context.scene.fresing
    with override():
        bpy.ops.ed.undo()                    # undo the joint itself
    return 0.8


@step
def s_after_undo2():
    s = bpy.context.scene.fresing
    bpy.context.view_layer.update()
    ok = len(s.joints) == 0 and (tip() - globals()["tip0"]).length < 1e-4 and find("BOOM.ASM").parent is not None \
        and find("BOOM.ASM").parent.get("fr_kind") == "assembly"
    check("undo removes the joint, boom back in the CAD tree", ok, f"joints {len(s.joints)}, tip {tuple(round(v, 3) for v in tip())}")
    with override():
        bpy.ops.ed.redo()
    return 0.8


@step
def s_after_redo():
    s = bpy.context.scene.fresing
    joints = mod("blender.joints")
    ok = len(s.joints) == 1 and joints.is_valid(s.joints[0])
    detail = ""
    if ok:
        joints.set_value(s.joints[0], math.radians(30))
        bpy.context.view_layer.update()
        detail = f"tip {tuple(round(v, 3) for v in tip())}"
        ok = (tip() - globals()["tip30"]).length < 1e-3
    check("redo brings the joint back and the slider still works", ok, detail)
    shot("03_after_redo")
    return 0.5


@step
def s_anim_undo():
    s = bpy.context.scene.fresing
    op("fresing.pose_save", name="Up")
    op("fresing.pose_reset")
    op("fresing.anim_add")
    op("fresing.block_add", kind="POSE")
    a = s.animations[0]
    a.blocks[0].pose = "Up"
    a.blocks[0].duration = 1.0
    r = op("fresing.anim_build")
    built = bool(s.anim_baked)
    bpy.context.scene.frame_set(20)
    with override():
        bpy.ops.ed.undo()                    # undo the build
    return 0.8


@step
def s_after_anim_undo():
    s = bpy.context.scene.fresing
    sc = bpy.context.scene
    sc.frame_set(20)
    bpy.context.view_layer.update()
    joints = mod("blender.joints")
    v = joints.get_value(s.joints[0]) if len(s.joints) else None
    check("undo after Build animation: no keys left, joint back at 0", not s.anim_baked and v is not None and abs(v) < 1e-6,
          f"baked '{s.anim_baked}', value {v}")
    with override():
        bpy.ops.ed.redo()
    return 0.8


@step
def s_after_anim_redo():
    s = bpy.context.scene.fresing
    sc = bpy.context.scene
    sc.frame_set(sc.frame_end)
    bpy.context.view_layer.update()
    joints = mod("blender.joints")
    v = joints.get_value(s.joints[0])
    check("redo Build animation: keys back, joint moves", s.anim_baked == "Animation" and abs(abs(v) - math.radians(30)) < 1e-3,
          f"baked '{s.anim_baked}', value {math.degrees(v):.1f}")
    op("fresing.anim_clear")
    return 0.5


@step
def s_explode_undo():
    root = mod("blender.build").model_roots(bpy.context.scene)[0]
    before = find("COVER").matrix_world.translation.copy()
    s = bpy.context.scene.fresing
    s.tree_index = 0
    with override():
        for o in bpy.context.selected_objects:
            o.select_set(False)
    r = op("fresing.explode")
    moved = (find("COVER").matrix_world.translation - before).length
    with override():
        bpy.ops.ed.undo()
    bpy.context.view_layer.update()
    back = (find("COVER").matrix_world.translation - before).length
    check("explode + undo", r == {"FINISHED"} and moved > 0.01 and back < 1e-4, f"moved {moved:.3f}, back {back:.5f}")
    return 0.5


@step
def s_update_model():
    root = mod("blender.build").model_roots(bpy.context.scene)[0]
    with override():
        bpy.ops.fresing.import_step(filepath=CRANE_B, quality="normal", update_root=root.name)
    globals()["_t_up"] = time.time()
    return 1.0


@step
def s_update_wait():
    s = bpy.context.scene.fresing
    if not s.report_title and time.time() - globals()["_t_up"] < 600:
        return "wait"
    check("update to revision B in the app (report shown)", "Model updated" in s.report_title and
          [x.text for x in s.report_new] == ["BOOM.LAMP"], s.report_title)
    check("joint survives the update", len(s.joints) == 1 and mod("blender.joints").is_valid(s.joints[0]))
    wiggle()
    return 1.0


@step
def s_report_shot():
    shot("04_update_report")
    r = op("fresing.report_select_new")
    sel = [o.get("fr_name") for o in bpy.context.selected_objects]
    check("select new parts", "BOOM.LAMP" in sel, sel)
    with override():
        bpy.ops.ed.undo()
    return 1.0


@step
def s_undo_update():
    # undoing a model update must leave a working project (either state is fine, no crash)
    s = bpy.context.scene.fresing
    joints = mod("blender.joints")
    check("undo after model update leaves a working project",
          len(mod("blender.build").model_roots(bpy.context.scene)) == 1 and all(joints.is_valid(j) for j in s.joints))
    return 0.5


@step
def s_structure_rows():
    """2 Structure / 3 Looks (task 0009) in the real window: row click, zoom, show only, find & group."""
    s = bpy.context.scene.fresing
    row = next(i for i, it in enumerate(s.tree) if it.label == "BOOM.ASM")
    s.tree_index = row
    sel = {o.get("fr_name") for o in bpy.context.selected_objects}
    check("a row click highlights its subassembly", {"BOOM", "BOOM.PIN"} <= sel and "BASE" not in sel, sorted(sel))
    win, area, region = ui()
    globals()["_view0"] = (region.data.view_location.copy(), region.data.view_distance)
    r = op("fresing.tree_row", index=row, action="FRAME")
    check("zoom to it (button runs)", r == {"FINISHED"}, r)
    return 1.5


@step
def s_structure_zoom_check():
    s = bpy.context.scene.fresing
    win, area, region = ui()
    loc0, dist0 = globals()["_view0"]
    moved = (region.data.view_location - loc0).length + abs(region.data.view_distance - dist0)
    check("zoom to it moves the view onto the row", moved > 1e-3, f"{moved:.4f}")
    row = next(i for i, it in enumerate(s.tree) if it.label == "BOOM.ASM")
    op("fresing.tree_row", index=row, action="ONLY")
    base = find("BASE")
    check("show only this hides the rest", s.isolated == "BOOM.ASM" and base.hide_get() and not find("BOOM").hide_get())
    wiggle()
    return 1.0


@step
def s_structure_find():
    shot("05_show_only")
    s = bpy.context.scene.fresing
    base = find("BASE")
    op("fresing.show_all")
    check("show all brings it back", not s.isolated and not base.hide_get())
    # find & group
    s.find_text = "boom"
    names = sorted(it.part_name for it in s.found)
    check("find parts by name", "BOOM" in names and "BOOM.PIN" in names, names)
    r = op("fresing.find_new_group")
    check("ticked parts go into a new group", r == {"FINISHED"} and find("BOOM").get("fr_group") == "Boom",
          find("BOOM").get("fr_group"))
    r = op("fresing.find_rule")
    check("search made into a rule (on top)", r == {"FINISHED"} and s.rules[0].value == "BOOM", s.rules[0].value)
    wiggle()
    return 1.0


@step
def s_structure_shot():
    shot("06_find_group")
    return 0.5


# ---- task 0011: two joints on one subassembly (a stack) --------------------


def wheel():
    return find("WHEEL", 1).matrix_world.translation.copy()


@step
def s_stack_first():
    sc = bpy.context.scene
    s = sc.fresing
    joints = mod("blender.joints")
    op("fresing.pose_reset")                     # boom down: nothing in front of the trolley
    tr = find("TROLLEY.ASM")
    with override():
        for o in bpy.context.selected_objects:
            o.select_set(False)
        tr.select_set(True)
        bpy.context.view_layer.objects.active = tr
    bpy.context.view_layer.update()
    globals()["w0"] = wheel()
    globals()["n0"] = len(s.joints)
    r = op("fresing.joint_add", kind="SLIDE", axis="Y", origin="CENTER")
    check("stack: first joint on the trolley (Add slide joint)", r == {"FINISHED"} and len(s.joints) == n0 + 1, r)
    j1 = s.joints[-1]
    globals()["j1name"] = j1.name
    joints.set_value(j1, 0.1)                    # slid out 100 mm along Y before the second joint is added
    bpy.context.view_layer.update()
    below, reason = joints.stack_info(sc, [tr])
    check("stack: the panel says the next joint goes on top", below is not None and below.name == j1.name and not reason,
          reason)
    with override():
        res = bpy.ops.fresing.joint_pick_axis("INVOKE_DEFAULT", mode="NEW", kind="ROTATE")
    check("stack: Add rotate joint starts the pick tool", "RUNNING_MODAL" in res, res)
    return 0.5


@step
def s_stack_click():
    # the trolley's top face (150 x 150 x 60 mm box), 30 mm in from a corner: a flat face -> vertical axis
    pt = find("TROLLEY").matrix_world @ Vector((0.03, 0.03, 0.06))
    globals()["pick_pt"] = pt.copy()
    x, y = to_window(pt)
    click(x, y)
    return 0.8


def _turned(q, c, angle):
    from mathutils import Matrix
    return c + Matrix.Rotation(angle, 3, "Z") @ (q - c)


@step
def s_stack_made():
    sc = bpy.context.scene
    s = sc.fresing
    joints = mod("blender.joints")
    tops = [j for j in s.joints if joints.rides_on(sc, j) is not None and joints.rides_on(sc, j).name == j1name]
    check("stack: click on the moved trolley adds a joint riding on the first", len(tops) == 1, s.last_message)
    if not tops:
        return 0.5
    j2 = tops[0]
    globals()["j2name"] = j2.name
    o, d = joints.axis_world(j2)
    check("stack: its axis goes through the clicked point", (o - pick_pt).length < 2e-3 and abs(abs(d.z) - 1) < 1e-3,
          f"{tuple(round(v, 4) for v in o)} dir {tuple(round(v, 3) for v in d)}")
    sign = 1 if d.z > 0 else -1
    globals()["sign"] = sign
    joints.set_value(j2, math.radians(90))
    bpy.context.view_layer.update()
    c = pick_pt - Vector((0, 0.1, 0))             # the axis point in the CAD position of the slide
    want = _turned(w0, c, sign * math.pi / 2) + Vector((0, 0.1, 0))
    check("stack: moves add up (100 mm slide, then 90° turn on it)", (wheel() - want).length < 1e-4,
          f"{tuple(round(v, 4) for v in wheel())} want {tuple(round(v, 4) for v in want)}")
    s.joints_index = list(s.joints).index(j2)
    shot("07_stack")
    with override():
        bpy.ops.ed.undo_push(message="values")
        bpy.ops.ed.undo()
    return 0.8


@step
def s_stack_undo():
    with override():
        bpy.ops.ed.undo()                         # undo the second joint
    return 0.8


@step
def s_stack_after_undo():
    sc = bpy.context.scene
    s = sc.fresing
    joints = mod("blender.joints")
    bpy.context.view_layer.update()
    j1 = joints.find(sc, j1name)
    ok = len(s.joints) == n0 + 1 and j1 is not None and joints.members(j1) == [find("TROLLEY.ASM")] \
        and (wheel() - (w0 + Vector((0, 0.1, 0)))).length < 1e-4
    check("stack: undo takes the second joint off, the trolley stays on the first", ok,
          f"joints {len(s.joints)}, wheel {tuple(round(v, 4) for v in wheel())}")
    with override():
        bpy.ops.ed.redo()
    return 0.8


@step
def s_stack_after_redo():
    sc = bpy.context.scene
    s = sc.fresing
    joints = mod("blender.joints")
    j2 = joints.find(sc, j2name) if "j2name" in globals() else None
    ok = j2 is not None and joints.rides_on(sc, j2) is not None and joints.rides_on(sc, j2).name == j1name
    check("stack: redo brings the second joint back on top", ok)
    if not ok:
        return 0.5
    joints.set_value(j2, math.radians(90))
    bpy.context.view_layer.update()
    s.joints_index = list(s.joints).index(j2)
    r = op("fresing.joint_swap")
    bpy.context.view_layer.update()
    j1, j2 = joints.find(sc, j1name), joints.find(sc, j2name)
    c = pick_pt - Vector((0, 0.1, 0))
    want = _turned(w0 + Vector((0, 0.1, 0)), c, sign * math.pi / 2)     # now: slide first, then everything turns
    ok = r == {"FINISHED"} and joints.rides_on(sc, j1) is not None and joints.rides_on(sc, j1).name == j2name \
        and (wheel() - want).length < 1e-4
    check("stack: Swap order (button) – the slide now rides on the turn", ok,
          f"{r} {tuple(round(v, 4) for v in wheel())} want {tuple(round(v, 4) for v in want)}")
    shot("08_stack_swapped")
    s.joints_index = list(s.joints).index(j2)    # the bottom one
    r = op("fresing.joint_remove")
    bpy.context.view_layer.update()
    j1 = joints.find(sc, j1name)
    ok = r == {"FINISHED"} and j1 is not None and joints.rides_on(sc, j1) is None \
        and (wheel() - (w0 + Vector((0, 0.1, 0)))).length < 1e-4
    check("stack: removing the bottom joint keeps the one on it (button)", ok, s.last_message)
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
        if time.time() - _w[0] > 900:
            check(fn.__name__ + " timeout", False)
            _i[0] += 1
            _w[0] = 0.0
        wiggle()
        return 1.0
    _w[0] = 0.0
    _i[0] += 1
    return r


bpy.app.timers.register(driver, first_interval=3.0, persistent=True)
