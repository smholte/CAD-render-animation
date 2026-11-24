"""Real-app test, task 0062: the lesson highlight (blender/highlight.py) – its six looks in the real side panel.

On the test crane: points at *Import STEP…* (button looks C and D; D's label contrast at UI scale 1.0, 1.5 and 2.0),
at *Add rotate joint* and *Add slide joint* (a joined pair: only the target is marked), at a setting inside a fold
of a folded section (section looks 5 and 4 on its header, then the section is opened by a click and the fold opens
by itself), at a greyed-out button and a number field of a small stand-in panel (which look C then keeps clear, as
it will a Lesson panel), shows a part with part looks 3 and 1, and checks that ``clear()`` leaves nothing behind.
Everything is found through the highlight's own ``found()``: the test does not know where a header or a button is.

    BLENDER_USER_RESOURCES=~/fr_user UITEST_OUT=/tmp/hl xvfb-run -a -s "-screen 0 1800x1300x24" blender \\
        -p 0 0 1800 1300 --app-template fresing_render --enable-event-simulate --python tools/ui_test_highlight.py
Pictures (one per look, cropped) and the log go to $UITEST_OUT (default ~/fresing_ui_test_highlight).
Lines ``METRIC name value`` give the highlight's own time per redraw in ms (xvfb draws in software) and the
contrast of a button's label."""

import importlib
import os
import subprocess
import time
import traceback

import bpy
import numpy as np

OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_test_highlight"))
MODEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "data", "test_crane_a.step")
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "ui_test_highlight.log"), "w")
RESULTS = []
S = {}
STEPS = []
SHEET = np.array([0.23, 0.24, 0.25])                        # part look 3's grey
STAND_IN = "FRESING_PT_zz_highlight_test"


class FRESING_PT_zz_highlight_test(bpy.types.Panel):
    """Stands in for a Lesson panel (kept clear by look C) and holds a greyed-out button and a number field."""
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Fresing"
    bl_label = "Lesson (stand-in of the test)"
    bl_parent_id = "FRESING_PT_import"

    def draw_header(self, context):
        self.layout.label(icon="HELP")

    def draw(self, context):
        layout = self.layout
        layout.label(text="Click the button that is shown.")
        row = layout.row(align=True)
        row.enabled = False
        row.operator("fresing.import_mesh", text="Greyed out", icon="IMPORT")
        row.operator("fresing.import_step", text="Other", icon="IMPORT")
        layout.prop(context.scene.render, "resolution_x")


def log(*a):
    msg = " ".join(str(x) for x in a)
    print("[UITEST]", msg, flush=True)
    LOG.write(msg + "\n")
    LOG.flush()


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    log(("PASS " if ok else "FAIL ") + name + (f" ({detail})" if detail else ""))


def metric(name, value):
    log(f"METRIC {name} {value:.3f}")


def mod(name):
    import addon_utils
    pkg = next((m.__name__ for m in addon_utils.modules() if m.__name__.endswith("fresing_render")), None)
    return importlib.import_module(pkg + "." + name)


def hl():
    return mod("blender.highlight")


def ui():
    win = bpy.context.window_manager.windows[0]
    area = next(a for a in win.screen.areas if a.type == "VIEW_3D")
    return (win, area, next(r for r in area.regions if r.type == "WINDOW"),
            next(r for r in area.regions if r.type == "UI"))


def override(side=False):
    win, area, region, sb = ui()
    return bpy.context.temp_override(window=win, screen=win.screen, area=area, region=sb if side else region,
                                     scene=win.scene)


def scale():
    return bpy.context.preferences.system.ui_scale


def step(fn):
    STEPS.append(fn)
    return fn


def mouse_away():
    win, _area, region, _sb = ui()
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=region.x + 200 + int(time.time() * 10) % 9,
                       y=region.y + 200)


def click(x, y):
    win = ui()[0]
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x, y=y)
    win.event_simulate(type="LEFTMOUSE", value="PRESS", x=x, y=y)
    win.event_simulate(type="LEFTMOUSE", value="RELEASE", x=x, y=y)


def scroll(op, n=1, **kw):
    with override(side=True):
        for _ in range(n):
            getattr(bpy.ops.view2d, op)(**kw)


def redraw():
    hl().redraw()


def grab(name, x, y_top, w, h):
    """A piece of the screen as a PNG (x from the left, y from the top)."""
    path = os.path.join(OUT, name)
    subprocess.run(["import", "-window", "root", "-crop", f"{int(w)}x{int(h)}+{int(x)}+{int(y_top)}", "+repage",
                    path], check=False)
    return path


def grab_side(name, box=None, pad=70):
    """The side panel's full width round a rectangle of it (region pixels, y up); without one, all of it."""
    win, _area, _region, sb = ui()
    if box is None:
        return grab(name, sb.x, win.height - (sb.y + sb.height), sb.width, sb.height)
    y1 = min(box[3] + pad, sb.height)
    y0 = max(box[1] - pad, 0)
    return grab(name, sb.x, win.height - (sb.y + y1), sb.width, y1 - y0)


def grab_view(name):
    win, _area, region, sb = ui()
    w = (sb.x - region.x) if sb.x > region.x else region.width
    return grab(name, region.x, win.height - (region.y + region.height), w, region.height)


def picture(path):
    """A PNG as floats (rows from the bottom, r g b)."""
    img = bpy.data.images.load(path)
    w, h = img.size
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    return px.reshape(h, w, 4)[:, :, :3]


def lum(rgb):
    """Relative luminance (WCAG) of 0 … 255 pixels."""
    c = np.asarray(rgb, np.float64) / 255.0
    c = np.where(c <= 0.03928, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return c @ np.array([0.2126, 0.7152, 0.0722])


def probe():
    """(before, after): the side panel's pixels without and with the look, from the highlight's own last redraw."""
    return hl()._S.get("shot")


def want_probe(on=True):
    hl()._S["probe"] = on
    hl()._S.pop("shot", None)
    redraw()


def in_region(box):
    _w, _a, _r, sb = ui()
    return box is not None and 0 <= box[0] < box[2] <= sb.width and 0 <= box[1] < box[3] <= sb.height


# ---------------------------------------------------------------------------
# bringing a target on screen, only with what the highlight itself found
# ---------------------------------------------------------------------------

def bring(state, want="button"):
    """One step of: scroll until the target's header or button is on screen; ``want`` "button": click a folded
    header open (once), then look further down. True when what is wanted is there and stands still."""
    f = hl().found()
    _w, _a, _r, sb = ui()
    now = time.time()
    if now - state.get("t", 0) < 0.45:
        return False
    state["t"] = now
    box = f.get("button") if f else None
    head = f.get("header") if f else None
    target = box if want == "button" else (head if box is None else None)
    if target is not None:
        was, state["was"] = state.get("was"), tuple(target)
        if was == tuple(target):                            # it stands still (at an edge: no further to scroll)
            return True
        if target[1] < 60:
            scroll("scroll_down", 3)
        elif target[3] > sb.height - 60:
            scroll("scroll_up", 3)
        return False
    if want == "header" and box is not None:
        return False                                        # the section is open: this target shows no header look
    if want == "button" and head is not None and not state.get("clicked"):
        was, state["head_was"] = state.get("head_was"), tuple(head)
        if head[3] < sb.height - 150 * scale() and was != tuple(head):
            scroll("scroll_down", 5)                        # the header up to the top: an open section then shows
            return False                                    # its button below it
        click(sb.x + int(f["hmark"][2] + 40 * scale()), sb.y + int((head[1] + head[3]) / 2))    # folded: the title
        state["clicked"] = True                             # opens it
        state["t"] = now + 0.5
        return False
    n = state.get("scrolls", 0)
    if n == 0 and not state.get("clicked"):
        scroll("scroll_up", 20, page=True)
    elif n < 80:
        scroll("scroll_down", 5)
    state["scrolls"] = n + 1
    redraw()
    return False


def wait_for(name, want="button", limit=45.0):
    """A step that brings the current target on screen."""
    state = {}

    def fn():
        state.setdefault("t0", time.time())
        if bring(state, want):
            mouse_away()
            return 0.6
        if time.time() - state["t0"] > limit:
            f = hl().found()
            check(f"{name}: the target came on screen", False,
                  f"button {f.get('button')}, header {f.get('header')}, note {hl()._S['note']!r}")
            return 0.2
        return "again"
    fn.__name__ = "wait_" + name
    STEPS.append(fn)


# ---------------------------------------------------------------------------
# what a look must do to the side panel's pixels
# ---------------------------------------------------------------------------

def outside(shape, box, m=6):
    mask = np.ones(shape[:2], bool)
    mask[max(box[1] - m, 0):box[3] + m + 1, max(box[0] - m, 0):box[2] + m + 1] = False
    return mask


def check_c(tag, key, f, before, after):
    box = f["button"]
    out = outside(before.shape, box)
    for b, t in f["bands"]:
        out[max(b - 3, 0):t + 4] = False
    mk = f["mark"]
    out[mk[1] - 3:mk[3] + 4, mk[0] - 3:mk[2] + 4] = False
    lb, la = before[:, :, :3][out].mean(), after[:, :, :3][out].mean()
    want = 0.38 * lb + 0.62 * 255 * np.mean(hl().CHARCOAL)
    check(f"{tag}: look C dims the rest of the side panel", la < lb - 8 and abs(la - want) < 4,
          f"mean {lb:.1f} -> {la:.1f}, 62 % towards charcoal would be {want:.1f}")
    x0, y0, x1, y1 = box
    inner = np.ones((y1 - y0 - 3, x1 - x0 - 3), bool)
    if mk[0] >= x0:
        inner[max(mk[1] - 3 - y0 - 2, 0):mk[3] + 3 - y0 - 2, max(mk[0] - 3 - x0 - 2, 0):mk[2] + 3 - x0 - 2] = False
    d = np.abs(after[y0 + 2:y1 - 1, x0 + 2:x1 - 1, :3] - before[y0 + 2:y1 - 1, x0 + 2:x1 - 1, :3]).max(axis=2)
    check(f"{tag}: look C leaves the button itself clear", d[inner].mean() < 2.0, f"mean change {d[inner].mean():.2f}")
    col = np.array(hl().colour()) * 255
    edge = after[y1 + 1:y1 + 5, x0 + 10:x1 - 10, :3].reshape(-1, 3)
    near = np.abs(edge - col).max(axis=1).min() if len(edge) else 999
    check(f"{tag}: look C draws a thin outline in the colour", near < 60, f"nearest {near:.0f}")
    S["band_change"] = [float(np.abs(after[b + 4:t - 3, 8:-40, :3] - before[b + 4:t - 3, 8:-40, :3]).mean())
                        for b, t in f["bands"]]


def contrast(before, after, f):
    """The label against the button, WCAG ratio: (as Blender draws it, with look D, with a plain tint laid over
    the label too – what the look would be without its mask)."""
    box, mark, s = f["button"], f["mark"], scale()
    x0, y0, x1, y1 = box
    m = int(round(5 * s))
    a = hl().tint_mask(before.astype(np.uint8), box, mark, f["own"])[m:-m, m:-m]
    a[:, :max(mark[2] + 4 - x0 - m, 0)] = 0.5               # the icon's place is neither label nor plain button
    col = np.array(hl().colour()) * 255
    over = before[:, :, :3] * 0.62 + col * 0.38
    out = []
    for px in (before, after, over):
        sub = lum(px[y0 + m:y1 + 1 - m, x0 + m:x1 + 1 - m, :3])
        label, plain = sub[a < 0.25], sub[a > 0.97]
        if len(label) < 20 or len(plain) < 50:
            return None
        lab, bg = np.percentile(label, 90 if np.median(label) > np.median(plain) else 10), np.median(plain)
        out.append((max(lab, bg) + 0.05) / (min(lab, bg) + 0.05))
    return out


def check_d(tag, key, f, before, after):
    box, mk = f["button"], f["mark"]
    x0, y0, x1, y1 = box
    col = np.array(hl().colour()) * 255
    s = scale()
    bar = after[(y0 + y1) // 2, x0 + 1, :3]
    check(f"{tag}: look D has a bar in the colour on the button's left edge", np.abs(bar - col).max() < 30, str(bar))
    a = hl().tint_mask(before.astype(np.uint8), box, mk, f["own"])
    plain = a > 0.97
    plain[:, :int(8 * s)] = False
    shift = (after[y0:y1 + 1, x0:x1 + 1, :3] - before[y0:y1 + 1, x0:x1 + 1, :3])[plain].mean(axis=0)
    toward = (col - before[y0:y1 + 1, x0:x1 + 1, :3][plain].mean(axis=0))
    check(f"{tag}: look D tints the button towards the colour", float(shift @ toward) > 0 and np.abs(shift).max() > 8,
          f"shift {np.round(shift, 1)}")
    out = outside(before.shape, box)
    out[mk[1] - 3:mk[3] + 4, mk[0] - 3:mk[2] + 4] = False
    change = np.abs(after[:, :, :3] - before[:, :, :3])[out].mean()
    check(f"{tag}: look D leaves the rest of the side panel as it is", change < 0.5, f"mean change {change:.2f}")
    return s


def check_d_label(tag, key, f, before, after):
    s = check_d(tag, key, f, before, after)
    c = contrast(before, after, f)
    if c is None:
        check(f"{tag}: look D label contrast could be measured", False)
        return
    metric(f"contrast_{tag}_as_blender_draws_it", c[0])
    metric(f"contrast_{tag}_with_look_D", c[1])
    metric(f"contrast_{tag}_if_the_tint_lay_over_the_label", c[2])
    check(f"{tag}: look D keeps the label readable at UI scale {s:.1f}", c[1] >= 4.0 and c[1] > c[2],
          f"contrast {c[0]:.1f} : 1 as Blender draws it, {c[1]:.1f} : 1 with the tint at its strongest "
          f"({c[2]:.1f} : 1 if the tint lay over the label too)")


def look_steps(tag, key, checks):
    def set_it():
        hl().set_look("button", key)
        return 0.9                                          # look C fades in over 0.4 s

    def ask():
        want_probe()
        return 0.4

    def see():
        f = hl().found()
        box = f.get("button")
        pr = probe()
        want_probe(False)
        if box is None or pr is None:
            check(f"{tag}: look {key} found its button", False, f"found {f}, note {hl()._S['note']!r}")
            return 0.2
        check(f"{tag}: look {key}: the marker was found and its button lies inside the side panel",
              in_region(box), f"box {box} in {f['region'][2]} x {f['region'][3]}")
        checks(tag, key, f, pr[0].astype(np.int16), pr[1].astype(np.int16))
        grab_side(f"{tag}_{key}.png", box)
        return 0.2
    for fn in (set_it, ask, see):
        fn.__name__ = f"{fn.__name__}_{tag}_{key}"
        STEPS.append(fn)


def peak_on():
    h = hl()
    h.begin_clip()
    h.set_clock(h.BEAT / 4)                                 # the breath at its strongest
    return 0.1


def peak_off():
    hl().end_clip()
    return 0.1


# ---------------------------------------------------------------------------
# steps
# ---------------------------------------------------------------------------

@step
def s_esc_press():
    ui()[0].event_simulate(type="ESC", value="PRESS", x=700, y=500)
    return 0.3


@step
def s_esc_release():
    ui()[0].event_simulate(type="ESC", value="RELEASE", x=700, y=500)
    return 0.5


KEPT = {}


@step
def s_import():
    # (both are put back at the end: Blender saves changed preferences when it closes, and the next real-app test
    # in the same settings folder would start with them – its clicks in the view are worked out with the overlap on)
    KEPT.update(overlap=bpy.context.preferences.system.use_region_overlap,
                scale=bpy.context.preferences.view.ui_scale)
    bpy.context.preferences.system.use_region_overlap = False      # else the side panel is see-through
    bpy.context.preferences.view.ui_scale = 1.0
    with override():
        bpy.ops.fresing.import_step(filepath=MODEL, quality="draft")
    return 1.0


@step
def s_imported():
    if bpy.context.scene.fresing.model_count == 0:
        return "wait"
    h = hl()
    S["own_register"] = mod("blender.ui").HOOKS.get("fold") is not h.fold_open
    if S["own_register"]:
        h.register()
    try:                                                    # the app's own title rows, where it has them
        mod("blender.panels").install([FRESING_PT_zz_highlight_test])
    except ImportError:
        pass
    bpy.utils.register_class(FRESING_PT_zz_highlight_test)
    names = [n for n in dir(bpy.types) if n.startswith("FRESING_PT_")]
    S["draws"] = {n: (getattr(bpy.types, n).__dict__.get("draw"), getattr(bpy.types, n).__dict__.get("draw_header"))
                  for n in names}
    check("the crane is imported and nothing is pointed at", not h.active() and h.handlers_left() == [],
          str(h.handlers_left()))
    return 0.5


# ----- button looks on the main button -----

@step
def s_point_import():
    hl().set_look("button", "C")
    hl().point_function("import.step")
    return 0.6


wait_for("import")
look_steps("import", "C", check_c)

for ui_scale in (1.0, 1.5, 2.0):
    def set_scale(ui_scale=ui_scale):
        bpy.context.preferences.view.ui_scale = ui_scale
        hl().set_look("button", "D")
        hl().point_function("import.step")
        return 1.2
    set_scale.__name__ = f"scale_{ui_scale}"
    STEPS.append(set_scale)
    wait_for(f"import_x{ui_scale}")
    STEPS.append(peak_on)
    look_steps(f"import_x{ui_scale}", "D", check_d_label)
    STEPS.append(peak_off)


@step
def s_scale_back():
    bpy.context.preferences.view.ui_scale = 1.0
    return 1.0


# ----- a joined pair: only the target -----

@step
def s_point_rotate():
    part = next(o for o in bpy.context.scene.objects if o.type == "MESH" and o.get("fr_name"))
    with override():
        bpy.ops.object.select_all(action="DESELECT")
        part.select_set(True)
        bpy.context.view_layer.objects.active = part
    hl().set_look("button", "C")
    try:                                                    # task 0290: the buttons sit in 4 Motion > Joints (a fold)
        mod("blender.panels").open_to("FRESING_PT_joints")
    except (ImportError, AttributeError):
        pass
    hl().point_function("joints.rotate")
    return 0.6


wait_for("rotate")


def check_pair(tag, key, f, before, after):
    box = f["button"]
    w = f["region"][2]
    S.setdefault("pair", {})[tag] = box
    check(f"{tag}: of the joined pair only the target is marked (look {key})", box[2] - box[0] < 0.55 * w,
          f"{box[2] - box[0]} of {w} px wide")
    (check_c if key == "C" else check_d_label)(tag, key, f, before, after)


look_steps("rotate", "C", check_pair)
STEPS.append(peak_on)
look_steps("rotate", "D", check_pair)
STEPS.append(peak_off)


def side_cost(tag, key):
    def fn():
        h = hl()
        h.set_look("button", key)
        with override(side=True):
            bpy.ops.wm.redraw_timer(type="DRAW", iterations=5)
            h.stats(reset=True)
            t = time.perf_counter()
            bpy.ops.wm.redraw_timer(type="DRAW", iterations=30)
            total = 1000 * (time.perf_counter() - t) / 30
        st = h.stats()
        metric(f"side_panel_look_{key}_ms_per_redraw", st["side"][1])
        metric(f"side_panel_look_{key}_of_that_reading_the_pixels_ms", st["read"][1])
        metric(f"side_panel_whole_redraw_with_look_{key}_ms", total)
        check(f"look {key}: the highlight's share of a side-panel redraw was measured", st["side"][0] >= 30,
              f"{st['side'][0]} redraws of a {ui()[3].width} x {ui()[3].height} px side panel")
        return 0.2
    fn.__name__ = f"cost_{tag}_{key}"
    STEPS.append(fn)


side_cost("rotate", "C")
side_cost("rotate", "D")


@step
def s_point_slide():
    hl().set_look("button", "C")
    hl().point_function("joints.stack")                     # "Add slide joint": the pair's other button
    return 0.6


wait_for("slide")
look_steps("slide", "C", check_pair)


@step
def s_pair():
    a, b = S.get("pair", {}).get("rotate"), S.get("pair", {}).get("slide")
    check("the pair's two buttons are told apart: rotate left of slide, no overlap",
          a is not None and b is not None and a[2] < b[0] and abs(a[1] - b[1]) <= 2, f"{a} / {b}")
    return 0.2


# ----- a folded section: its header, then a setting inside a fold -----

@step
def s_point_fold():
    hl().set_look("section", "5")
    hl().point(panel="FRESING_PT_animation", prop="pv_seconds", fold="fr_product_video")
    S["fold_asked"] = hl().fold_open("fr_product_video") and not hl().fold_open("fr_queue_schemes")
    return 0.6


wait_for("section", want="header")


def section_steps(key):
    def set_it():
        hl().set_look("section", key)
        hl().begin_clip()
        hl().set_clock(hl().BEAT / 2)                       # the arrow half-way through its nod: pointing down
        return 0.3

    def ask():
        want_probe()
        return 0.4

    def see():
        f = hl().found()
        head, pr = f.get("header"), probe()
        want_probe(False)
        hl().end_clip()
        if head is None or pr is None or f.get("button") is not None:
            check(f"section look {key}: a folded header is shown", False, f"found {f}, note {hl()._S['note']!r}")
            return 0.2
        before, after = pr[0].astype(np.int16), pr[1].astype(np.int16)
        l, b, r, t = head
        col = np.array(hl().colour()) * 255
        check(f"section look {key}: the header marker was found and the header lies inside the side panel",
              in_region(head) and r - l > 100, f"header {head}")
        sub_b, sub_a = before[b:t + 1, l:r + 1, :3], after[b:t + 1, l:r + 1, :3]
        shift = (sub_a - sub_b).reshape(-1, 3).mean(axis=0)
        check(f"section look {key}: the header takes the colour",
              float(shift @ (col - sub_b.reshape(-1, 3).mean(axis=0))) > 0
              and np.abs(shift).max() > (10 if key == "5" else 1.5), f"shift {np.round(shift, 1)}")
        if key == "4":
            bar = after[(b + t) // 2, l + 2, :3]
            check("section look 4: a bar in the colour on the header's left edge", np.abs(bar - col).max() < 30, str(bar))
        else:
            white = (sub_a.min(axis=2) > 235).sum()
            check("section look 5: the fold arrow is drawn (white on a disc in the colour)", white > 8, f"{white} px")
        out = outside(before.shape, head)
        change = np.abs(after[:, :, :3] - before[:, :, :3])[out].mean()
        check(f"section look {key}: nothing else in the side panel changes", change < 0.5, f"mean change {change:.2f}")
        grab_side(f"section_{key}.png", head)
        return 0.2
    for fn in (set_it, ask, see):
        fn.__name__ = f"{fn.__name__}_section_{key}"
        STEPS.append(fn)


section_steps("5")
section_steps("4")


@step
def s_section_cost():
    h = hl()
    with override(side=True):
        bpy.ops.wm.redraw_timer(type="DRAW", iterations=5)
        h.stats(reset=True)
        bpy.ops.wm.redraw_timer(type="DRAW", iterations=30)
    metric("side_panel_section_look_4_ms_per_redraw", h.stats()["side"][1])
    h.set_look("button", "C")
    return 0.2


wait_for("fold")                                            # clicks the header open; the fold opens by itself


@step
def s_fold_open():
    f = hl().found()
    check("the fold the target sits in says it must be open, another fold does not", S.get("fold_asked"))
    check("after the section was opened the setting inside its fold is found (the fold opened by itself)",
          in_region(f.get("button")), f"setting {f.get('button')}")
    if f.get("button"):
        grab_side("fold_setting_C.png", f["button"], pad=110)
    return 0.2


# ----- a greyed-out button, a number field, a panel kept clear (the stand-in panel) -----

@step
def s_point_greyed():
    hl().set_look("button", "D")
    hl().point(panel=STAND_IN, button="fresing.import_mesh", text="Greyed out", open_panels=True)
    return 0.6


wait_for("greyed")
STEPS.append(peak_on)
look_steps("greyed", "D", check_d)
STEPS.append(peak_off)


@step
def s_point_number():
    hl().set_look("button", "C")
    hl().point(panel=STAND_IN, prop="resolution_x", open_panels=True)
    return 0.6


wait_for("number")


def check_number(tag, key, f, before, after):
    box, mk = f["button"], f["mark"]
    check("a number field: the marker stands in front of it and the look is on the field",
          mk[2] < box[0] and box[2] - box[0] > 100 and box[2] <= f["region"][2] - 25, f"marker {mk}, field {box}")
    check_c(tag, key, f, before, after)


look_steps("number", "C", check_number)


@step
def s_keep_clear():
    hl().keep_clear((STAND_IN,))
    hl().set_look("button", "C")
    hl().point_function("import.step")
    return 0.6


wait_for("clear")
look_steps("clear", "C", check_c)


@step
def s_kept_clear():
    f = hl().found()
    change = S.get("band_change")
    check("look C with a panel kept clear: the panel's band was found (its header to its last row)",
          len(f.get("bands", [])) == 1 and f["bands"][0][1] - f["bands"][0][0] > 60 * scale(), str(f.get("bands")))
    check("look C with a panel kept clear: that panel is not dimmed", bool(change) and max(change) < 3.0, str(change))
    if f.get("bands"):
        b, t = f["bands"][0]
        grab_side("clear_C_panel_kept.png", (0, b, 10, max(t, f["button"][3])), pad=40)
    hl().keep_clear(())
    return 0.4


# ----- a part in the 3D view -----

@step
def s_part_plain():
    hl().clear()
    parts = [o for o in bpy.context.scene.objects if o.type == "MESH" and o.get("fr_name")]
    with override():
        bpy.ops.object.select_all(action="DESELECT")
        for o in parts:
            o.select_set(True)
        bpy.ops.view3d.view_selected()
        bpy.ops.object.select_all(action="DESELECT")
        bpy.context.view_layer.objects.active = None
    mouse_away()
    return 1.5


@step
def s_part_before():
    S["view_plain"] = picture(grab_view("view_plain.png"))
    with override():
        t = time.perf_counter()
        bpy.ops.wm.redraw_timer(type="DRAW", iterations=20)
        metric("view_whole_redraw_plain_ms", 1000 * (time.perf_counter() - t) / 20)
    parts = [o for o in bpy.context.scene.objects if o.type == "MESH" and o.get("fr_name")]
    part = max(parts, key=lambda o: max(o.dimensions))
    S["part"] = part.name
    nothing = bpy.data.objects.new("highlight test: a part without faces", bpy.data.meshes.new("no faces"))
    bpy.context.scene.collection.objects.link(nothing)      # found on the demo vessel: it must not stop the others
    nothing.parent = part
    hl().set_look("part", "3")
    hl().point(parts=(part.name,))
    return 1.2


def part_steps(key):
    def set_it():
        h = hl()
        h.set_look("part", key)
        h.begin_clip()
        h.set_clock(h.BEAT / 4 + (h.BEAT if key == "3" else 0.0))   # look 1 at its strongest, look 3 faded in
        redraw()
        return 0.8

    def see():
        h = hl()
        from bpy_extras.view3d_utils import location_3d_to_region_2d
        from mathutils import Vector
        _w, area, region, _sb = ui()
        rv3d = area.spaces.active.region_3d
        ob = bpy.data.objects[S["part"]]
        pts = [location_3d_to_region_2d(region, rv3d, ob.matrix_world @ Vector(c)) for c in ob.bound_box]
        pts = [p for p in pts if p is not None]
        now = picture(grab_view(f"part_{key}.png"))
        plain = S["view_plain"]
        hgt, wid = now.shape[:2]
        bx0, bx1 = int(max(min(p.x for p in pts) - 6, 0)), int(min(max(p.x for p in pts) + 6, wid))
        by0, by1 = int(max(min(p.y for p in pts) - 6, 0)), int(min(max(p.y for p in pts) + 6, hgt))
        diff = np.abs(now - plain).max(axis=2)
        inside = np.zeros(diff.shape, bool)
        inside[by0:by1, bx0:bx1] = True
        col = np.array(h.colour())
        if key == "3":
            rest = ~inside & (np.abs(plain - SHEET).max(axis=2) > 0.15)     # the other parts, as they were
            d0 = np.median(np.abs(plain[rest] - SHEET).max(axis=1)) if rest.any() else 0.0
            d1 = np.median(np.abs(now[rest] - SHEET).max(axis=1)) if rest.any() else 1.0
            check("part look 3: everything else is faded towards grey", rest.sum() > 500 and d1 < 0.7 * d0,
                  f"{int(rest.sum())} px of other parts, their distance from the grey {d0:.3f} -> {d1:.3f}")
            sub = now[by0:by1, bx0:bx1].reshape(-1, 3)
            own = np.array(h._part_colour(ob))
            near = (np.abs(sub / np.maximum(sub.max(axis=1, keepdims=True), 1e-6)
                           - own / max(own.max(), 1e-6)).max(axis=1) < 0.12) & (sub.max(axis=1) > 0.2)
            check("part look 3: the part stands clear in its own colour, lit (several shades of it)",
                  near.sum() > 300 and np.ptp(sub[near].max(axis=1)) > 0.1,
                  f"{int(near.sum())} px of its colour, brightness spread "
                  f"{np.ptp(sub[near].max(axis=1)) if near.any() else 0:.2f}")
        else:
            changed = diff > 0.03
            check("part look 1: only the part changes", changed[inside].sum() > 200 and changed[~inside].mean() < 0.002,
                  f"{int(changed[inside].sum())} px on the part, {100 * changed[~inside].mean():.2f} % elsewhere")
            pick = changed & inside
            shift = (now - plain)[pick].mean(axis=0) if pick.any() else np.zeros(3)
            base = plain[pick].mean(axis=0) if pick.any() else np.zeros(3)
            check("part look 1: the part glows in the colour", float(shift @ (col - base)) > 0,
                  f"shift {np.round(shift, 3)}")
        with override():
            bpy.ops.wm.redraw_timer(type="DRAW", iterations=3)
            h.stats(reset=True)
            t = time.perf_counter()
            bpy.ops.wm.redraw_timer(type="DRAW", iterations=20)
            total = 1000 * (time.perf_counter() - t) / 20
        n, ms = h.stats()["parts"]
        metric(f"part_look_{key}_ms_per_redraw_crane_1_part", ms)
        metric(f"view_whole_redraw_with_part_look_{key}_ms", total)
        check(f"part look {key}: the 3D view's draw handler ran and was timed", n >= 20 and not h._S["note"],
              f"{n} redraws, note {h._S['note']!r}")
        h.end_clip()
        return 0.2
    for fn in (set_it, see):
        fn.__name__ = f"{fn.__name__}_part_{key}"
        STEPS.append(fn)


part_steps("3")
part_steps("1")


@step
def s_whole_crane():
    h = hl()
    root = next(o for o in bpy.context.scene.objects if o.parent is None and o.children)
    h.set_look("part", "3")
    h.point(parts=(root.name,))
    S["n_whole"] = len(h._S["parts"])
    return 1.0


def whole_cost(key):
    def fn():
        h = hl()
        h.set_look("part", key)
        with override():
            bpy.ops.wm.redraw_timer(type="DRAW", iterations=3)
            h.stats(reset=True)
            bpy.ops.wm.redraw_timer(type="DRAW", iterations=20)
        metric(f"part_look_{key}_ms_per_redraw_crane_all_{S['n_whole']}_parts", h.stats()["parts"][1])
        return 0.2
    fn.__name__ = f"whole_cost_{key}"
    STEPS.append(fn)


whole_cost("3")
whole_cost("1")


# ----- nothing left behind -----

@step
def s_clear():
    hl().point_function("joints.rotate", parts=(S["part"],))
    return 0.6


@step
def s_cleared():
    h = hl()
    check("while pointing: draw handlers, a timer and wrapped draws are there", h.active() and len(h.handlers_left()) >= 5,
          str(h.handlers_left()))
    h.clear()
    left = h.handlers_left()
    same = all(S["draws"][n] == (getattr(bpy.types, n).__dict__.get("draw"),
                                 getattr(bpy.types, n).__dict__.get("draw_header")) for n in S["draws"])
    check("after clear() no handler, timer or wrapped draw is left", not h.active() and left == [], str(left))
    check("after clear() every panel has exactly the draw and draw_header it had", same)
    check("the highlight reported no drawing error", not h._S["note"], h._S["note"])
    redraw()
    return 0.8


@step
def s_after():
    grab_side("after_clear.png")
    bpy.utils.unregister_class(FRESING_PT_zz_highlight_test)
    try:
        for table in (mod("blender.panels").PARENT, mod("blender.panels").TITLE):
            table.pop(STAND_IN, None)
    except ImportError:
        pass
    if S.get("own_register"):
        hl().unregister()
    return 0.2


@step
def s_finish():
    failed = [r for r in RESULTS if not r[1]]
    log(f"RESULT {len(RESULTS) - len(failed)}/{len(RESULTS)} passed")
    LOG.close()
    if KEPT:
        bpy.context.preferences.system.use_region_overlap = KEPT["overlap"]
        bpy.context.preferences.view.ui_scale = KEPT["scale"]
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
    if r == "again":                                        # the step goes on by itself (it has its own limit)
        return 0.15
    if r == "wait":
        if not _w[0]:
            _w[0] = time.time()
        if time.time() - _w[0] > 120:
            check(fn.__name__ + " timeout", False)
            _i[0] += 1
            _w[0] = 0.0
        return 1.0
    _w[0] = 0.0
    _i[0] += 1
    return r


bpy.app.timers.register(driver, first_interval=3.0, persistent=True)
