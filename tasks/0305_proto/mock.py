"""Task 0305: mock-ups of the changed panels, drawn in the real app with the app's own panel helpers (``ui.py``), and
two drawings over the real model: step blocks on the time line, numbers + a parts list on an exploded picture.

    BLENDER_USER_RESOURCES=~/fr_user xvfb-run -a -s "-screen 0 1600x1400x24" blender -p 0 0 1600 1400 \
        --app-template fresing_render --enable-event-simulate --python tasks/0305_proto/mock.py

Env: MOCK_OUT (folder, default /tmp/mock0305). Nothing here is app code: the panels only draw (their buttons do
nothing), the drawings are gpu draw handlers of this script. The exploded places are the app's own (an Assembly
sequence step, Take apart along +Z, at the frame where every part is out).
"""
import math
import os
import subprocess
import time
import traceback

import blf
import bpy
import gpu
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty
from bpy_extras import view3d_utils
from gpu_extras.batch import batch_for_shader
from mathutils import Vector

OUT = os.environ.get("MOCK_OUT", "/tmp/mock0305")
os.makedirs(OUT, exist_ok=True)
HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.join(HERE, "..", "..", "fresing_render", "data", "test_sequence.step")
LOG = open(os.path.join(OUT, "mock.log"), "w")


def log(*a):
    msg = " ".join(str(x) for x in a)
    print("[MOCK]", msg, flush=True)
    LOG.write(msg + "\n")
    LOG.flush()


def pkg():
    import addon_utils
    return next(m.__name__ for m in addon_utils.modules() if m.__name__.endswith("fresing_render"))


def mod(name):
    import importlib
    return importlib.import_module(pkg() + "." + name)


def win():
    return bpy.context.window_manager.windows[0]


def area_of(kind):
    return next(a for a in win().screen.areas if a.type == kind)


def override(kind="VIEW_3D"):
    w = win()
    area = area_of(kind)
    region = next(r for r in area.regions if r.type == "WINDOW")
    return bpy.context.temp_override(window=w, screen=w.screen, area=area, region=region, scene=w.scene)


def settle():
    for _ in range(12):
        for a in win().screen.areas:
            a.tag_redraw()
        bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)
        time.sleep(0.05)


def grab(name, area, region_type=None):
    """Screenshot of an area (or one region of it)."""
    settle()
    w = win()
    r = next(r for r in area.regions if r.type == region_type) if region_type else area
    geo = f"{r.width}x{r.height}+{r.x}+{w.height - (r.y + r.height)}"
    p = os.path.join(OUT, name + ".png")
    subprocess.run(["import", "-window", "root", "-crop", geo, "+repage", p], check=False)
    log("shot", p, geo)
    return p


# ---------------------------------------------------------------------------
# mock settings (only for drawing)
# ---------------------------------------------------------------------------

class FRMock(bpy.types.PropertyGroup):
    starts: EnumProperty(name="Starts", default="WITH", items=[
        ("AFTER", "After the one above", "Starts when the step above ends"),
        ("WITH", "With the one above", "Starts together with the step above"),
        ("AT", "At a time", "Starts at the time you type")])
    lasts: EnumProperty(name="Lasts", default="OWN", items=[
        ("OWN", "Its own time", ""), ("WHOLE", "The whole animation", ""), ("ABOVE", "As long as the one above", "")])
    preview: FloatProperty(name="Preview", default=62.0, min=0.0, max=100.0, subtype="PERCENTAGE")
    hold: FloatProperty(name="Hold apart (s)", default=3.0, min=0.0)
    how: EnumProperty(name="Pieces", default="ONE", items=[
        ("ONE", "One level", "The subassemblies and parts directly inside"),
        ("ALL", "Every part", "Every single part, all levels down")])
    direction: EnumProperty(name="Direction", default="AUTO", items=[
        ("AUTO", "Along the stack (found: +Z)", "Pieces on one axis leave along it, the others outwards"),
        ("OUT", "Outwards from the centre", ""), ("AXIS", "Along X / Y / Z", ""),
        ("PART", "Along a part's axis (click a round face)", ""),
        ("AROUND", "Around an axis (radial)", "")])
    spacing: EnumProperty(name="Spacing", default="EVEN", items=[
        ("EVEN", "Even gaps", "The same gap between neighbours"), ("SIZE", "By size", "Bigger parts further")])
    distance: FloatProperty(name="Gap", default=0.04, min=0.0, soft_max=0.2, subtype="DISTANCE")
    fasteners: BoolProperty(name="Screws and nuts out along their own axis first", default=True)
    trails: BoolProperty(name="Trail lines from each part's place", default=True)
    numbers: EnumProperty(name="Numbers", default="POS", items=[
        ("POS", "One per kind of part", "Like a drawing: 8 numbers for 12 parts"),
        ("EACH", "One per part", "")])
    plist: EnumProperty(name="Parts list", default="RIGHT", items=[
        ("RIGHT", "Right", ""), ("BELOW", "Below", ""), ("OFF", "None", "")])
    cols_name: BoolProperty(name="Name", default=True)
    cols_qty: BoolProperty(name="Quantity", default=True)
    cols_mat: BoolProperty(name="Material", default=False)
    kind: EnumProperty(name="Kind", default="REAL", items=[
        ("REAL", "Realistic: the way parts come out", "Each part leaves the way it really can: out of its bore, "
         "bolts unscrewed head first, in the order nothing blocks"),
        ("AXIS", "Straight along one axis", "Every part the same way (today's Take apart)"),
        ("SPREAD", "Spread for a picture", "Outwards round the middle, even gaps: a catalogue picture"),
        ("LEVEL", "By assembly level", "Whole subassemblies first, then each one apart"),
        ("SERVICE", "Service: only these parts", "Only the parts of one job come out; the rest stays")])
    unscrew: EnumProperty(name="Screws and nuts", default="SHOW3", items=[
        ("SHOW3", "Unscrew: 3 turns, then out", ""), ("ALL", "Unscrew all the way", ""),
        ("STRAIGHT", "Straight out, no turning", "")])


class MOCK_OT_button(bpy.types.Operator):
    """(mock-up: does nothing)"""
    bl_idname = "mock.button"
    bl_label = "Mock"

    def execute(self, context):
        return {"FINISHED"}


def _ui():
    return mod("blender.ui")


def _bar(layout, start, dur, total, text):
    """A step's block on its row: an empty part for its start, a filled bar for its duration."""
    total = max(total, 1e-6)
    s = layout.split(factor=max(0.001, min(0.999, start / total)), align=True)
    s.label(text="")
    rest = max(total - start, 1e-6)
    s2 = s.split(factor=max(0.02, min(1.0, dur / rest)), align=True)
    if hasattr(s2, "progress"):
        s2.progress(factor=1.0, type="BAR", text=text)
    else:
        s2.box().label(text=text)
    s2.label(text="")


STEPS = [  # (icon, name, start, duration, ticked)
    ("VIEW_CAMERA", "Turn around 360°", 0.0, 20.0),
    ("MOD_EXPLODE", "Take apart SPINDLE.UNIT", 3.0, 6.5),
    ("PAUSE", "Hold apart", 9.5, 3.0),
    ("MOD_EXPLODE", "Put back SPINDLE.UNIT", 12.5, 6.5),
]


def _mock_anim_draw(self, context):
    ui = _ui()
    layout = self.layout
    m = context.window_manager.fr_mock
    row = layout.row(align=True)
    row.scale_y = 1.3
    row.operator("mock.button", text="Build & play", icon="PLAY")
    row.operator("mock.button", text="Render video", icon="RENDER_ANIMATION")
    ui.hint(layout, context, "Both stay on top: no scrolling down to Render animation.")
    ui.gap(layout)
    box = layout.box()
    r = box.row()
    r.label(text="Product animation", icon="RENDER_ANIMATION")
    sub = r.row()
    sub.alignment = "RIGHT"
    sub.label(text="20.0 s")
    ui.gap(layout)
    layout.label(text="Steps", icon="SEQ_STRIP_DUPLICATE")
    col = layout.column(align=True)
    ui.hint(layout, context, "Drag a bar on the time line at the bottom to move it, its ends to change its length.")
    for i, (icon, name, start, dur) in enumerate(STEPS):
        b = col.box() if i == 1 else col
        r = b.row(align=True)
        r.label(text=name, icon=icon)
        sub = r.row()
        sub.alignment = "RIGHT"
        sub.label(text=f"{start:g}–{start + dur:g} s")
        _bar(b, start, dur, 20.0, "")
    row = layout.row(align=True)
    row.operator("mock.button", text="Add step", icon="ADD")
    row.operator("mock.button", text="", icon="REMOVE")
    row.operator("mock.button", text="", icon="DUPLICATE")
    ui.gap(layout)
    box = layout.box()
    ui.wrap(box, context, "Take apart SPINDLE.UNIT", icon="MOD_EXPLODE", inset=12)
    c = ui.split_props(box)
    c.prop(m, "starts", text="Starts")
    c.prop(m, "lasts", text="Lasts")
    c.prop(m, "hold", text="Hold apart (s)")
    box.prop(m, "preview", text="Scrub this step", slider=True)
    ui.hint(box, context, "Scrub shows the step at once – no Build needed; let go and the model is back", inset=12)


def _mock_add_draw(self, context):
    ui = _ui()
    layout = self.layout
    ui.hint(layout, context, "The + of the steps opens this: what most videos need first, each one click.")
    layout.label(text="Ready-made", icon="SOLO_ON")
    col = layout.column(align=True)
    for text, icon in (("Take apart · hold · put back", "MOD_EXPLODE"),
                       ("Exploded view · hold · back (all at once)", "FULLSCREEN_EXIT"),
                       ("Turn around for the whole animation", "VIEW_CAMERA"),
                       ("Fly through the saved cameras", "OUTLINER_OB_CAMERA"),
                       ("Run the G-code program, camera on the tool", "FILE_SCRIPT")):
        r = col.row()
        r.scale_y = 1.2
        r.operator("mock.button", text=text, icon=icon)
    ui.gap(layout, line=True)
    layout.label(text="Move a joint", icon="CON_PIVOT")
    g = layout.grid_flow(columns=2, align=True)
    for n in ("Boom", "Trolley", "Slew", "Hook"):
        g.operator("mock.button", text=n)
    layout.label(text="Go to pose", icon="ARMATURE_DATA")
    g = layout.grid_flow(columns=2, align=True)
    for n in ("Exploded", "Transport", "Working"):
        g.operator("mock.button", text=n)
    layout.label(text="More", icon="DOWNARROW_HLT")
    g = layout.grid_flow(columns=2, align=True)
    for n, ic in (("Camera", "VIEW_CAMERA"), ("Show / hide", "HIDE_OFF"), ("Fade", "MOD_OPACITY"),
                  ("Cylinder", "CON_STRETCHTO"), ("Motor", "FORCE_VORTEX"), ("Weather", "OUTLINER_DATA_LIGHTPROBE"),
                  ("Back to CAD", "LOOP_BACK"), ("Lift height", "SORT_DESC")):
        g.operator("mock.button", text=n, icon=ic)


def _mock_explode_draw(self, context):
    ui = _ui()
    layout = self.layout
    m = context.window_manager.fr_mock
    r = layout.row(align=True)
    r.label(text="Explodes: SPINDLE.UNIT", icon="OUTLINER_OB_GROUP_INSTANCE")
    r.operator("mock.button", text="Use selected", icon="EYEDROPPER")
    c = ui.split_props(layout)
    c.prop(m, "how", text="Pieces")
    c.prop(m, "direction", text="Direction")
    c.prop(m, "spacing", text="Spacing")
    r = layout.row(align=True)
    r.scale_y = 1.4
    r.prop(m, "distance", text="Gap", slider=True)
    ui.hint(layout, context, "Drag: the pieces move as you drag, always from their CAD places (drag back to 0 and "
                             "they are home).")
    layout.prop(m, "fasteners")
    layout.prop(m, "trails")
    ui.gap(layout)
    r = layout.row(align=True)
    r.scale_y = 1.3
    r.operator("mock.button", text="Save as pose 'Exploded'", icon="ADD")
    r.operator("mock.button", text="Back", icon="LOOP_BACK")
    ui.gap(layout, line=True)
    layout.label(text="Make from it", icon="RENDER_STILL")
    col = layout.column(align=True)
    col.operator("mock.button", text="Picture with numbers and parts list", icon="LINENUMBERS_ON")
    col.operator("mock.button", text="Exploded turntable video", icon="FILE_MOVIE")
    col.operator("mock.button", text="Take apart · hold · put back (steps)", icon="MOD_EXPLODE")


def _mock_balloons_draw(self, context):
    ui = _ui()
    layout = self.layout
    m = context.window_manager.fr_mock
    ui.hint(layout, context, "From the pose 'Exploded' and the camera 'Front iso'. The numbers stay with their parts "
                             "when the camera moves.")
    c = ui.split_props(layout)
    c.prop(m, "numbers", text="Numbers")
    c.prop(m, "plist", text="Parts list")
    r = layout.row(align=True)
    r.prop(m, "cols_name", toggle=True)
    r.prop(m, "cols_qty", toggle=True)
    r.prop(m, "cols_mat", toggle=True)
    ui.gap(layout)
    ui.big(layout, "mock.button", "Render picture", "RENDER_STILL")
    layout.operator("mock.button", text="Save the parts list (Excel / CSV)", icon="SPREADSHEET")
    ui.hint(layout, context, "8 numbers · 12 parts · fasteners counted, not drawn twice")


def _mock_kind_draw(self, context):
    ui = _ui()
    layout = self.layout
    m = context.window_manager.fr_mock
    r = layout.row(align=True)
    r.label(text="Takes apart: SPINDLE.UNIT", icon="OUTLINER_OB_GROUP_INSTANCE")
    c = ui.split_props(layout)
    c.prop(m, "kind", text="Kind")
    c.prop(m, "unscrew", text="Screws, nuts")
    r = layout.row(align=True)
    r.label(text="Stays: HOUSING (the biggest)", icon="PINNED")
    r.operator("mock.button", text="Change", icon="EYEDROPPER")
    ui.gap(layout)
    box = layout.box()
    ui.wrap(box, context, "Found: 12 parts in 5 rounds, every one along its bore (+Z). 4 bolts head first, "
                          "M8 = 1.25 mm a turn; the locknut off its thread. Nothing stuck.", icon="CHECKMARK", inset=12)
    col = box.column(align=True)
    for rnd, name, way in (("1", "4 × ISO 4762 M8x30", "unscrew, up"), ("1", "Locknut M25x1.5", "unscrew, up"),
                           ("2", "PULLEY", "up"), ("3", "COVER, SHAFT", "up"), ("4", "BEARING 6205", "up"),
                           ("5", "SPACER, BEARING 6205", "up")):
        r = col.split(factor=0.1)
        r.label(text=rnd)
        r2 = r.split(factor=0.66)
        r2.label(text=name)
        r2.label(text=way)
    ui.gap(layout)
    ui.hint(layout, context, "Not right? Right-click a part in the view: Its way out… · Keep in place · Leaves "
                             "together with…")


MOCKS = []


def _mock_panel(idname, label, icon, status, draw):
    def draw_header(self, context):
        self.layout.label(icon=icon)

    def draw_header_preset(self, context):
        if status:
            _ui().header_status(self.layout, status)

    cls = type(idname, (bpy.types.Panel,), {
        "bl_space_type": "VIEW_3D", "bl_region_type": "UI", "bl_category": "Fresing", "bl_label": label,
        "bl_order": 50, "draw_header": draw_header, "draw_header_preset": draw_header_preset, "draw": draw})
    MOCKS.append(cls)
    return cls


def register_mocks():
    bpy.utils.register_class(FRMock)
    bpy.types.WindowManager.fr_mock = bpy.props.PointerProperty(type=FRMock)
    bpy.utils.register_class(MOCK_OT_button)
    for args in (("FRESING_PT_mock_anim", "6  Animation (mock-up)", "RENDER_ANIMATION", "20.0 s", _mock_anim_draw),
                 ("FRESING_PT_mock_add", "Add a step (mock-up)", "ADD", "", _mock_add_draw),
                 ("FRESING_PT_mock_explode", "Exploded view (mock-up)", "FULLSCREEN_EXIT", "40 mm",
                  _mock_explode_draw),
                 ("FRESING_PT_mock_balloons", "Numbered picture (mock-up)", "LINENUMBERS_ON", "8",
                  _mock_balloons_draw),
                 ("FRESING_PT_mock_kind", "Take apart (mock-up)", "MOD_EXPLODE", "5 rounds", _mock_kind_draw)):
        _mock_panel(*args)
    mod("blender.panels").install(MOCKS)
    for c in MOCKS:
        bpy.utils.register_class(c)


# ---------------------------------------------------------------------------
# drawings over the model
# ---------------------------------------------------------------------------

SH = None
BLUE = (0.30, 0.52, 0.85, 1.0)
DRAW = {"balloons": [], "plist": [], "blocks": [], "trails": [], "arrows": []}


def _rect(x0, y0, x1, y1, col):
    b = batch_for_shader(SH, "TRIS", {"pos": [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]}, indices=[(0, 1, 2), (0, 2, 3)])
    SH.uniform_float("color", col)
    b.draw(SH)


def _lines(pts, col, width=1.5):
    gpu.state.line_width_set(width)
    b = batch_for_shader(SH, "LINES", {"pos": pts})
    SH.uniform_float("color", col)
    b.draw(SH)


def _circle(cx, cy, r, col, fill=True, n=32):
    pts = [(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n)) for k in range(n)]
    if fill:
        b = batch_for_shader(SH, "TRI_FAN", {"pos": [(cx, cy)] + pts + [pts[0]]})
    else:
        b = batch_for_shader(SH, "LINE_LOOP", {"pos": pts})
    SH.uniform_float("color", col)
    b.draw(SH)


def _text(x, y, s, size=14, col=(1, 1, 1, 1), centre=False):
    blf.size(0, size)
    blf.color(0, *col)
    if centre:
        w, h = blf.dimensions(0, s)
        x, y = x - w / 2, y - h / 2 + 1
    blf.position(0, x, y, 0)
    blf.draw(0, s)


def draw_view():
    gpu.state.blend_set("ALPHA")
    region = bpy.context.region
    rv3d = bpy.context.region_data
    for a, b in DRAW["trails"]:
        pa = view3d_utils.location_3d_to_region_2d(region, rv3d, a)
        pb = view3d_utils.location_3d_to_region_2d(region, rv3d, b)
        if pa and pb:
            # dashed trail from the CAD place to the exploded place
            n = max(2, int((pb - pa).length / 8))
            pts = []
            for k in range(0, n, 2):
                pts += [pa.lerp(pb, k / n), pa.lerp(pb, min(1, (k + 1) / n))]
            _lines([tuple(p) for p in pts], (1.0, 0.55, 0.1, 0.9), 2.0)
    for a, b, text, spin in DRAW["arrows"]:
        pa = view3d_utils.location_3d_to_region_2d(region, rv3d, a)
        pb = view3d_utils.location_3d_to_region_2d(region, rv3d, b)
        if not (pa and pb):
            continue
        col = (0.95, 0.5, 0.08, 1.0)
        _lines([tuple(pa), tuple(pb)], col, 3.0)
        d = (pb - pa).normalized()
        nrm = Vector((-d.y, d.x))
        tip = [tuple(pb), tuple(pb - d * 12 + nrm * 6), tuple(pb - d * 12 - nrm * 6)]
        bt = batch_for_shader(SH, "TRIS", {"pos": tip})
        SH.uniform_float("color", col)
        bt.draw(SH)
        if spin:                                   # a turning arrow round the axis: the bolt unscrews
            pts = [(pa.x + 11 * math.cos(t / 10 * 5.5), pa.y + 4 * math.sin(t / 10 * 5.5)) for t in range(11)]
            _lines([p for k in range(10) for p in (pts[k], pts[k + 1])], (0.2, 0.75, 1.0, 1.0), 2.5)
        _circle(pb.x + d.x * 14, pb.y + d.y * 14 + 4, 11, (1, 1, 1, 1))
        _text(pb.x + d.x * 14, pb.y + d.y * 14 + 4, text, 13, (0.05, 0.05, 0.08, 1), centre=True)
    for num, pt, side in DRAW["balloons"]:
        p = view3d_utils.location_3d_to_region_2d(region, rv3d, pt)
        if p is None:
            continue
        bx, by = side
        _lines([(p.x, p.y), (bx, by)], (0.08, 0.08, 0.1, 1.0), 1.6)
        _circle(p.x, p.y, 3.0, (0.08, 0.08, 0.1, 1.0))
        _circle(bx, by, 15, (1, 1, 1, 1))
        _circle(bx, by, 15, (0.08, 0.08, 0.1, 1.0), fill=False)
        _text(bx, by, str(num), 15, (0.05, 0.05, 0.08, 1), centre=True)
    if DRAW["plist"]:
        rows = DRAW["plist"]
        x0, w = region.width - 330, 310
        top = region.height - 70
        h = 24
        _rect(x0, top - h * (len(rows) + 1) - 6, x0 + w, top + 4, (1, 1, 1, 0.94))
        _text(x0 + 10, top - 16, "Pos", 13, (0.1, 0.1, 0.12, 1))
        _text(x0 + 52, top - 16, "Part", 13, (0.1, 0.1, 0.12, 1))
        _text(x0 + w - 44, top - 16, "Qty", 13, (0.1, 0.1, 0.12, 1))
        _lines([(x0 + 6, top - h + 2), (x0 + w - 6, top - h + 2)], (0.1, 0.1, 0.12, 1), 1.2)
        for i, (pos, name, qty) in enumerate(rows):
            y = top - h * (i + 2) + 8
            _text(x0 + 16, y, str(pos), 13, (0.1, 0.1, 0.12, 1))
            _text(x0 + 52, y, name[:30], 13, (0.1, 0.1, 0.12, 1))
            _text(x0 + w - 34, y, str(qty), 13, (0.1, 0.1, 0.12, 1))


def draw_timeline():
    if not DRAW["blocks"]:
        return
    gpu.state.blend_set("ALPHA")
    region = bpy.context.region
    v2d = region.view2d
    lane_h, top = 17, region.height - 23
    cols = {"VIEW_CAMERA": (0.35, 0.55, 0.85, 0.95), "MOD_EXPLODE": (0.90, 0.55, 0.15, 0.95),
            "PAUSE": (0.45, 0.45, 0.48, 0.95)}
    for lane, (icon, name, f0, f1) in DRAW["blocks"]:
        x0 = v2d.view_to_region(f0, 0, clip=False)[0]
        x1 = v2d.view_to_region(f1, 0, clip=False)[0]
        y1 = top - lane * (lane_h + 3)
        y0 = y1 - lane_h
        _rect(x0, y0, x1, y1, cols.get(icon, (0.5, 0.5, 0.5, 0.9)))
        _rect(x0, y0, x0 + 4, y1, (1, 1, 1, 0.55))           # the handles a drag grabs
        _rect(x1 - 4, y0, x1, y1, (1, 1, 1, 0.55))
        _text(x0 + 8, y0 + 4, name, 11, (1, 1, 1, 1))


# ---------------------------------------------------------------------------
# the run
# ---------------------------------------------------------------------------

STATE = {"n": 0}


def start():
    try:
        w = win()
        w.event_simulate(type="ESC", value="PRESS", x=700, y=700)
        w.event_simulate(type="ESC", value="RELEASE", x=700, y=700)
        bpy.context.preferences.system.use_region_overlap = False
        mod("blender.workspaces").use_all(bpy.context.scene)
        bpy.app.timers.register(do_import, first_interval=1.0)
    except Exception:
        log(traceback.format_exc())
        bpy.ops.wm.quit_blender()


def do_import():
    with override():
        log("import", bpy.ops.fresing.import_step(filepath=MODEL, quality="normal"))
    bpy.app.timers.register(after_import, first_interval=1.0)


def after_import():
    if bpy.context.scene.fresing.model_count == 0:
        STATE["n"] += 1
        return 0.5 if STATE["n"] < 400 else None
    try:
        run()
    except Exception:
        log(traceback.format_exc())
    bpy.ops.wm.quit_blender()
    return None


def run():
    global SH
    sc = bpy.context.scene
    s = sc.fresing
    animation, sequence, build, logic = (mod("blender.animation"), mod("blender.sequence"), mod("blender.build"),
                                         mod("blender.logic"))
    unit = next(o for o in sc.objects if o.get("fr_name") == "SPINDLE.UNIT")
    a = s.animations.add()
    a.name, a.tail = "Product animation", 0.0
    s.animations_index = 0
    b = a.blocks.add()
    b.kind, b.camera_mode, b.orbit_angle, b.start, b.duration = "CAMERA", "ORBIT", math.radians(360), 0.0, 20.0
    for mode, st in (("APART", 3.0), ("TOGETHER", 12.5)):
        b = a.blocks.add()
        b.kind, b.seq_mode, b.seq_id = "SEQUENCE", mode, "mock" + mode
        b.target_uid, b.target_name = unit[build.PROP_UID], unit[build.PROP_NAME]
        b.seq_direction, b.seq_axis, b.seq_order, b.seq_overlap = "AXIS", "Z", "OUTSIDE_IN", 50.0
        sequence.count(sc, b)
        b.start = st
    a.blocks[2].start = a.blocks[1].start + a.blocks[1].duration + 3.0
    with override():
        log("build", bpy.ops.fresing.anim_build())
    fps = sc.render.fps
    hold = animation.frame_of(a, a.blocks[1].start + a.blocks[1].duration + 1.5)
    log("frames", sc.frame_start, sc.frame_end, "hold at", hold, "blocks",
        [(x.kind, x.start, x.duration) for x in a.blocks])
    register_mocks()
    panels = mod("blender.panels")
    for name in ("FRESING_PT_mock_anim", "FRESING_PT_mock_add", "FRESING_PT_mock_explode",
                 "FRESING_PT_mock_balloons", "FRESING_PT_mock_kind"):
        panels.show_only([name])
        grab("panel_" + name.split("_")[-1], area_of("VIEW_3D"), "UI")
    panels.show_only()
    # -- the time line with step blocks
    SH = gpu.shader.from_builtin("UNIFORM_COLOR")
    blocks = []
    for lane, (icon, name, st, du) in enumerate(STEPS):
        lane_i = 0 if icon == "VIEW_CAMERA" else 1
        blocks.append((lane_i, (icon, name, animation.frame_of(a, st), animation.frame_of(a, st + du))))
    DRAW["blocks"] = blocks
    tl = area_of("DOPESHEET_EDITOR")
    h_tl = bpy.types.SpaceDopeSheetEditor.draw_handler_add(draw_timeline, (), "WINDOW", "POST_PIXEL")
    sc.frame_set(hold)
    with bpy.context.temp_override(window=win(), screen=win().screen, area=tl):
        try:
            log("grow timeline", bpy.ops.screen.area_move(x=tl.x + 200, y=tl.y + tl.height, delta=90))
        except Exception as exc:
            log("area_move", exc)
    settle()
    tl = area_of("DOPESHEET_EDITOR")
    with bpy.context.temp_override(window=win(), screen=win().screen, area=tl,
                                   region=next(r for r in tl.regions if r.type == "WINDOW")):
        for op in (bpy.ops.action.view_all, bpy.ops.view2d.reset):
            try:
                log("view all", op())
                break
            except Exception as exc:
                log("view_all", exc)
    grab("timeline", tl)
    log("timeline area", tl.width, tl.height)
    # -- the exploded picture: numbers + parts list + trails
    tree = logic.Tree(sc)
    parts = [d for d in tree.descendants(unit) if d.get(build.PROP_KIND) == "part"]
    sc.frame_set(sc.frame_start)
    home = {p.name: _centre(p) for p in parts}
    sc.frame_set(hold)
    out = {p.name: _centre(p) for p in parts}
    kinds = {}
    for p in sorted(parts, key=lambda p: -out[p.name].z):
        kinds.setdefault(p.get(build.PROP_NAME, p.name), []).append(p)
    DRAW["plist"] = [(i + 1, n, len(ps)) for i, (n, ps) in enumerate(kinds.items())]
    DRAW["trails"] = [(home[p.name], out[p.name]) for p in parts]
    v3d = area_of("VIEW_3D")
    region = next(r for r in v3d.regions if r.type == "WINDOW")
    rv3d = v3d.spaces[0].region_3d
    for o in bpy.context.selected_objects:
        o.select_set(False)
    for p in parts:
        p.select_set(True)
    with override():
        bpy.ops.view3d.view_selected()
    v3d.spaces[0].overlay.show_floor = False
    v3d.spaces[0].overlay.show_axis_x = v3d.spaces[0].overlay.show_axis_y = False
    v3d.spaces[0].overlay.show_outline_selected = False
    for p in parts:
        p.select_set(False)
    rv3d.view_distance *= 1.25
    settle()
    # balloons: one per kind, in a column left of the model, ordered by height on screen
    pts = []
    for i, (n, ps) in enumerate(kinds.items()):
        p3 = out[ps[0].name]
        p2 = view3d_utils.location_3d_to_region_2d(region, rv3d, p3)
        pts.append((i + 1, p3, p2))
    pts.sort(key=lambda t: -t[2].y)
    x_col = min(t[2].x for t in pts) - 140
    ys, last = [], None
    for num, p3, p2 in pts:
        y = p2.y if last is None else min(p2.y, last - 36)
        ys.append((num, p3, (x_col, y)))
        last = y
    DRAW["balloons"] = ys
    h_v = bpy.types.SpaceView3D.draw_handler_add(draw_view, (), "WINDOW", "POST_PIXEL")
    grab("exploded_numbers", v3d, "WINDOW")
    # -- the ways out found (freeways.py on this unit: every part +Z, rounds 1-5; the housing stays)
    saved = (DRAW["balloons"], DRAW["plist"], DRAW["trails"])
    DRAW["balloons"], DRAW["plist"], DRAW["trails"] = [], [], []
    sc.frame_set(sc.frame_start)
    rnd = {"ISO 4762 M8x30": 1, "SKF KM 5 Locknut M25x1.5": 1, "PULLEY": 2, "COVER": 3, "SHAFT": 3,
           "BEARING 6205": 4, "SPACER": 5}
    arrows, seen = [], set()
    for p in parts:
        n = p.get(build.PROP_NAME, p.name)
        if n not in rnd:
            continue
        c = _centre(p)
        if n == "BEARING 6205" and "BEARING 6205" in seen:
            r = 5
        else:
            r = rnd[n]
        seen.add(n)
        wpts = [p.matrix_world @ Vector(v) for v in p.bound_box]
        top = max(v.z for v in wpts)
        half = (max(v.x for v in wpts) - min(v.x for v in wpts)) / 2.0
        right = rv3d.view_rotation @ Vector((1, 0, 0))
        right.z = 0
        right.normalize()
        a = Vector((c.x, c.y, top)) + right * (half * 0.8 if half > 0.02 else 0.0)
        arrows.append((a, a + Vector((0, 0, 0.035 + 0.012 * r)), str(r), n.startswith("ISO") or "Locknut" in n))
    DRAW["arrows"] = arrows
    for p in parts:
        p.select_set(True)
    with override():
        bpy.ops.view3d.view_selected()
    for p in parts:
        p.select_set(False)
    rv3d.view_distance *= 2.1
    grab("ways_found", v3d, "WINDOW")
    DRAW["arrows"] = []
    DRAW["balloons"], DRAW["plist"], DRAW["trails"] = saved
    sc.frame_set(hold)
    DRAW["balloons"], DRAW["plist"] = [], []
    grab("exploded_trails", v3d, "WINDOW")
    bpy.types.SpaceView3D.draw_handler_remove(h_v, "WINDOW")
    bpy.types.SpaceDopeSheetEditor.draw_handler_remove(h_tl, "WINDOW")
    log("done")


def _centre(ob):
    from mathutils import Vector as V
    pts = [ob.matrix_world @ V(c) for c in ob.bound_box]
    return sum(pts, V()) / 8.0


bpy.app.timers.register(start, first_interval=2.0)
