"""The Set-up window's content (task 0062, the owner's pick "float 2" of study 0200): a set-up one step at a time.

A second app window shows a side-panel tab "Set-up" (``FRESING_PT_setup``; the window itself: ops_setup.py). Each
set-up is a short list of steps – ``SETUPS = {kind: (title, [(step title, draw(layout, context)), …])}`` – and
``draw_setup`` shows one of them: the kind picker, the step numbers, the step's hint and buttons, Back / Next.

* **Nothing is copied.** A step draws the app's own operators and settings (4 Motion > CNC machine, 4 Motion >
  Mechanisms): what is done here shows in the side panel, and the other way round.
* The kind and the step live in the project (``scene.fresing.setup_kind``, ``setup_step``): the window opens where
  the user left off. ``current(scene)`` is the one place that reads them: the step counts only for the kind it was
  set for (``STEP_OF``), so a kind changed anywhere starts at its first step.
* A step that is already done in the project says so in one line with a green tick (``CHECKS``: cheap to know –
  names picked, a part picked), and its number gets the tick too.
* Only **Next** is blue (one blue button, as in a section); every button of a step is big and grey.
* A button that picks by a click in the 3D view (the work zero) is started in the main window
  (``fresing.setup_in_view``): the Set-up window has no view to click in.

A new set-up (cylinders, cables …): its step functions, its checks, one entry in ``SETUPS`` and ``CHECKS``, and its
item in ``props.py``'s ``setup_kind``.
"""

from __future__ import annotations

import os
import textwrap

import bpy

from ..core.words import plural
from . import animation, gcode, linkages, ui

TAB = "Set-up"                 # the side-panel tab's name
STEP_OF = "fr_setup_of"        # scene ID property: the kind that ``setup_step`` counts in
MARK = "fr_setup"              # screen ID property: this screen is a Set-up window's (ops_setup.py sets it)


# ---------------------------------------------------------------------------------------------------------------
# the green tick (Blender has no coloured text: an icon drawn here, no picture file)
# ---------------------------------------------------------------------------------------------------------------

_ICONS = {"coll": None, "tick": 0}
GREEN = (0.36, 0.74, 0.22)     # the Fresing green, a little lighter: it has to read on the dark panel


def _tick_pixels(n: int = 32) -> list:
    """A tick of two strokes, soft edges, ``n`` x ``n`` RGBA floats (rows from the bottom). Blender wants an
    icon's colour already multiplied by its alpha: plain green with alpha 0 drew a light green square."""
    def dist(px, py, a, b):
        ax, ay = a
        bx, by = b
        dx, dy = bx - ax, by - ay
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
        return ((px - ax - t * dx) ** 2 + (py - ay - t * dy) ** 2) ** 0.5
    low, knee, high = (0.14, 0.50), (0.40, 0.22), (0.88, 0.80)
    half = 0.10
    out = []
    for y in range(n):
        for x in range(n):
            px, py = (x + 0.5) / n, (y + 0.5) / n
            d = min(dist(px, py, low, knee), dist(px, py, knee, high))
            alpha = max(0.0, min(1.0, (half - d) * n + 0.5))
            out.extend((GREEN[0] * alpha, GREEN[1] * alpha, GREEN[2] * alpha, alpha))    # colour times alpha
    return out


def tick() -> int:
    """The green tick's icon number (``icon_value=``); 0 where no icon can be made (the plain tick is used)."""
    if _ICONS["tick"]:
        return _ICONS["tick"]
    if _ICONS["coll"] is not None:          # tried before: no second try at every redraw
        return 0
    try:
        import bpy.utils.previews
        coll = bpy.utils.previews.new()
        _ICONS["coll"] = coll
        icon = coll.new("fr_setup_tick")
        icon.icon_size = (32, 32)
        icon.icon_pixels_float = _tick_pixels(32)
        _ICONS["tick"] = icon.icon_id
    except Exception:  # noqa: BLE001 - drawing never fails over an icon
        _ICONS["coll"] = _ICONS["coll"] or False
    return _ICONS["tick"]


def _free_icons() -> None:
    coll, _ICONS["coll"], _ICONS["tick"] = _ICONS["coll"], None, 0
    if coll:
        try:
            import bpy.utils.previews
            bpy.utils.previews.remove(coll)
        except Exception:  # noqa: BLE001
            pass


def done_line(layout, context, text: str):
    """The one green line of a step that is already done in the project."""
    value = tick()
    lines = textwrap.wrap(text, ui._chars_per_line(context, 22)) or [""]
    col = layout.column(align=True)
    for i, line in enumerate(lines):
        if i == 0 and value:
            col.label(text=line, icon_value=value)
        else:
            col.label(text=line, icon="CHECKMARK" if i == 0 else "BLANK1")
    return col


# ---------------------------------------------------------------------------------------------------------------
# set up a CNC mill: the buttons of 4 Motion > CNC machine
# ---------------------------------------------------------------------------------------------------------------

def _joint(scene, name: str):
    return scene.fresing.joints.get(name) if name else None


def _gcode_step(scene):
    """The first 'Run G-code program' step of the active animation, or None."""
    a = animation.active(scene)
    if a is None:
        return None
    return next((b for b in a.blocks if b.kind == "GCODE"), None)


def _cnc_axes_done(context) -> str:
    scene = context.scene
    cnc = gcode.settings(scene)
    if all(_joint(scene, n) is not None for n in gcode.axis_joint_names(cnc)):
        return "X, Y and Z are picked"
    return ""


def _cnc_axes(layout, context):
    scene = context.scene
    s = scene.fresing
    cnc = gcode.settings(scene)
    slides = sum(1 for j in s.joints if j.kind == "SLIDE")
    ui.wrap(layout, context, f"Each axis is a slide joint: make them in {ui.where('motion')} > Add joint "
                             f"({plural(slides, 'slide joint')} so far). Then let the app find which is X, Y and Z, "
                             "or pick them below.", icon="INFO")
    ui.big(layout, "fresing.cnc_find_axes", "Find the axes", "VIEWZOOM")
    box = layout.box()
    for ax in "xyz":
        row = box.row(align=True)
        row.prop_search(cnc, f"{ax}_joint", s, "joints", text=ax.upper(), icon="CON_LOCLIKE")
        row.prop(cnc, f"{ax}_reverse", text="", icon="ARROW_LEFTRIGHT", toggle=True)
    text = _cnc_axes_done(context)
    if text:
        done_line(layout, context, text)


def _cnc_spindle_done(context) -> str:
    j = _joint(context.scene, gcode.settings(context.scene).spindle_joint)
    return f"Spindle: {j.name}" if j is not None else ""


def _cnc_spindle(layout, context):
    scene = context.scene
    s = scene.fresing
    cnc = gcode.settings(scene)
    ui.wrap(layout, context, f"The spindle is a rotate joint with Motor ticked ({ui.where('motion')}). 'Find the "
                             "axes' picks it too. Without one the tool does not turn in the video.", icon="INFO")
    layout.prop_search(cnc, "spindle_joint", s, "joints", text="Spindle", icon="FORCE_VORTEX")
    text = _cnc_spindle_done(context)
    if text:
        done_line(layout, context, text)


def _cnc_parts_done(context) -> str:
    cnc = gcode.settings(context.scene)
    return "Tool and workpiece are picked" if cnc.tool is not None and cnc.workpiece is not None else ""


def _cnc_parts(layout, context):
    from .ops_machining import clicked_part
    cnc = gcode.settings(context.scene)
    ui.wrap(layout, context, "Click the cutter in the spindle in the main window, then press Use as tool. Click "
                             "the block, then press Use as workpiece.", icon="INFO")
    ob = clicked_part(context)
    if ob is not None:
        ui.wrap(layout, context, f"Clicked: {gcode.label(ob)}", icon="RESTRICT_SELECT_OFF")
    else:
        ui.wrap(layout, context, "Nothing clicked yet", icon="RESTRICT_SELECT_ON")
    for op, prop, word in (("fresing.cnc_use_tool", "tool", "tool"),
                           ("fresing.cnc_use_workpiece", "workpiece", "workpiece")):
        ui.gap(layout, size=0.5)
        ui.big(layout, op, f"Use as {word}", "RESTRICT_SELECT_OFF")
        val = getattr(cnc, prop)
        if val is not None:
            done_line(layout, context, f"{word.capitalize()}: {gcode.label(val)}")
        else:
            ui.hint(layout, context, f"{word.capitalize()}: not picked yet")


def _cnc_zero_done(context) -> str:
    cnc = gcode.settings(context.scene)
    if cnc.workpiece is None or gcode.problem(context.scene):
        return ""
    return "The machine is ready"


def _cnc_zero(layout, context):
    scene = context.scene
    cnc = gcode.settings(scene)
    ui.wrap(layout, context, "Where the program's X0 Y0 Z0 is on the workpiece: the same point as in your CAM "
                             "set-up.", icon="INFO")
    col = ui.split_props(layout)
    col.prop(cnc, "zero_mode", text="Work zero")
    if cnc.zero_mode == "POINT":
        op = ui.big(layout, "fresing.setup_in_view", "Click the zero point", "EYEDROPPER")
        op.op = "fresing.cnc_zero_click"
    why = gcode.problem(scene)
    if why:
        ui.wrap(layout, context, why, icon="ERROR", alert=True)
    else:
        done_line(layout, context, "The machine is ready. The work zero shows as arrows on the workpiece.")


def _cnc_program_done(context) -> str:
    b = _gcode_step(context.scene)
    if b is None or not b.gcode_file:
        return ""
    return f"The animation runs {os.path.basename(bpy.path.abspath(b.gcode_file))}"


def _cnc_program(layout, context):
    scene = context.scene
    b = _gcode_step(scene)
    if b is None:
        ui.wrap(layout, context, "The animation needs a step that runs your program. Add it here, then pick the "
                                 "program file your CAM wrote (LinuxCNC: .ngc).", icon="INFO")
        ui.big(layout, "fresing.block_add", "Add 'Run G-code program'", "FILE_SCRIPT").kind = "GCODE"
        return
    ui.wrap(layout, context, "Pick the program file your CAM wrote for the machine (LinuxCNC: .ngc).", icon="INFO")
    layout.prop(b, "gcode_file", text="")
    text = _cnc_program_done(context)
    if text:
        done_line(layout, context, text)
        ui.hint(layout, context, f"Its speed and the tools are in {ui.where('animation')}. Then Build & play.")


# ---------------------------------------------------------------------------------------------------------------
# set up a mechanism: the buttons of 4 Motion > Mechanisms
# ---------------------------------------------------------------------------------------------------------------

MECH_BASE = {
    "SCISSOR": "Click the base in the main window: the frame the lift stands on.",
    "FOURBAR": "Click the base in the main window: the part the two arms turn on.",
    "SLIDER": "Click the base in the main window: the part with the crank's bearing and the guide.",
    "OTHER": "Click the base in the main window: the part that stands still.",
}
MECH_LINKS = {
    "SCISSOR": "Select every arm and the platform: Ctrl+click them in the main window.",
    "FOURBAR": "Select the crank, the coupler and the rocker: Ctrl+click them in the main window, the one that "
               "drives last.",
    "SLIDER": "Select the crank, the rod and the slider: Ctrl+click them in the main window, the crank last.",
    "OTHER": "Select every moving link (each a subassembly): Ctrl+click them in the main window, the one that "
             "drives last.",
}


def _kind_text(s, prop: str = "mech_kind") -> str:
    """The description of the picked item of an enum setting (its tooltip text)."""
    try:
        text = s.bl_rna.properties[prop].enum_items[getattr(s, prop)].description.strip()
    except (KeyError, AttributeError):
        return ""
    return text + "." if text and text[-1] not in ".!?" else text


def _mech_kind(layout, context):
    s = context.scene.fresing
    ui.wrap(layout, context, "Pick what it is: the app then knows which pins, rollers and slides to look for.",
            icon="INFO")
    layout.prop(s, "mech_kind", text="Type")
    text = _kind_text(s)
    if text:
        ui.hint(layout, context, text)


def _mech_base_done(context) -> str:
    base = context.scene.fresing.mech_base
    return f"Base: {linkages.label(base)}" if base is not None else ""


def _mech_base(layout, context):
    s = context.scene.fresing
    ui.wrap(layout, context, MECH_BASE.get(s.mech_kind, MECH_BASE["OTHER"]) + " Then press Use as base.",
            icon="INFO")
    row = layout.row(align=True)
    row.scale_y = ui.MEDIUM
    row.operator("fresing.mechanism_pick_base", text="Use as base", icon="RESTRICT_SELECT_OFF")
    if s.mech_base is not None:
        row.operator("fresing.mechanism_pick_base", text="", icon="X").clear = True
    text = _mech_base_done(context)
    if text:
        done_line(layout, context, text)
    else:
        ui.hint(layout, context, "No base picked: the rest of the subassembly the links are in is the base.")


def _picked(context) -> list:
    from .ops_linkages import picked_links
    try:
        return picked_links(context)
    except (AttributeError, RuntimeError):      # no view layer (a background script)
        return []


def _mech_links(layout, context):
    s = context.scene.fresing
    ui.wrap(layout, context, MECH_LINKS.get(s.mech_kind, MECH_LINKS["OTHER"]), icon="INFO")
    links = _picked(context)
    if links:
        names = ", ".join(linkages.label(o) for o in links[:6]) + (" …" if len(links) > 6 else "")
        ui.wrap(layout, context, f"{plural(len(links), 'subassembly')} selected: {names}",
                icon="RESTRICT_SELECT_OFF")          # (no tick: a selection is not "done")
    else:
        ui.wrap(layout, context, "Nothing selected yet", icon="RESTRICT_SELECT_ON")


def _mech_add_done(context) -> str:
    s = context.scene.fresing
    if not s.mechanisms:
        return ""
    m = s.mechanisms[max(0, min(s.mechanisms_index, len(s.mechanisms) - 1))]
    return f"Made: {m.name}"


def _mech_add(layout, context):
    ui.wrap(layout, context, "Makes the mechanism from the selected links: the pins are found where two links "
                             "share a hole or a shaft.", icon="INFO")
    ui.big(layout, "fresing.mechanism_add", "Add mechanism", "LINKED")
    text = _mech_add_done(context)
    if text:
        done_line(layout, context, text)
        ui.hint(layout, context, f"Move it in {ui.where('mechanisms')}: its height or its drive angle.")


# ---------------------------------------------------------------------------------------------------------------
# the set-ups
# ---------------------------------------------------------------------------------------------------------------

SETUPS = {
    "CNC": ("Set up a CNC mill", [("Axes X, Y, Z", _cnc_axes), ("Spindle", _cnc_spindle),
                                  ("Tool and workpiece", _cnc_parts), ("Work zero", _cnc_zero),
                                  ("G-code program", _cnc_program)]),
    "MECH": ("Set up a mechanism", [("Type", _mech_kind), ("Base", _mech_base), ("Moving links", _mech_links),
                                    ("Add it", _mech_add)]),
}

# per step: fn(context) -> the green line's text when the step is done in the project ('' = not yet); None = no check
CHECKS = {
    "CNC": [_cnc_axes_done, _cnc_spindle_done, _cnc_parts_done, _cnc_zero_done, _cnc_program_done],
    "MECH": [None, _mech_base_done, None, _mech_add_done],     # (the links: a selection is not "done")
}

KIND_ICONS = {"CNC": "FILE_SCRIPT", "MECH": "LINKED"}


def current(scene) -> tuple:
    """(kind, step, steps) the Set-up window shows: the step is clamped to the kind's steps, and counts only for
    the kind it was set for – after a change of kind it is the first step."""
    s = scene.fresing
    kind = s.setup_kind if s.setup_kind in SETUPS else next(iter(SETUPS))
    steps = SETUPS[kind][1]
    k = s.setup_step if scene.get(STEP_OF, kind) == kind else 0
    return kind, max(0, min(k, len(steps) - 1)), steps


def is_done(context, kind: str, k: int) -> bool:
    """True when step ``k`` of ``kind`` is already done in the project (never raises: a check is only a hint)."""
    checks = CHECKS.get(kind, [])
    fn = checks[k] if 0 <= k < len(checks) else None
    if fn is None:
        return False
    try:
        return bool(fn(context))
    except Exception:  # noqa: BLE001
        return False


def draw_setup(layout, context) -> None:
    """The whole Set-up: the kind, the step numbers, the current step, Back / Next."""
    scene = context.scene
    kind, k, steps = current(scene)
    n = len(steps)
    title = SETUPS[kind][0]

    layout.operator_menu_enum("fresing.setup_kind", "kind", text=title, icon=KIND_ICONS.get(kind, "PREFERENCES"))

    value = tick()
    row = layout.row(align=True)
    for i in range(n):
        if i != k and is_done(context, kind, i):
            if value:
                op = row.operator("fresing.setup_go", text=str(i + 1), icon_value=value)
            else:
                op = row.operator("fresing.setup_go", text=str(i + 1), icon="CHECKMARK")
        else:
            op = row.operator("fresing.setup_go", text=str(i + 1), depress=(i == k))
        op.step = i

    box = layout.box()
    box.label(text=f"Step {k + 1} of {n}: {steps[k][0]}")
    steps[k][1](box, context)

    ui.gap(layout)
    row = layout.row(align=False)
    back = row.row(align=True)
    back.enabled = k > 0
    ui.big(back, "fresing.setup_go", "Back", "TRIA_LEFT").step = k - 1
    if k < n - 1:
        ui.primary(row, "fresing.setup_go", "Next", "TRIA_RIGHT", ui.MEDIUM).step = k + 1
    else:
        op = ui.primary(row, "fresing.setup_go", "Done", "CHECKMARK", ui.MEDIUM)
        op.step = k
        op.done = True


class FRESING_PT_setup(bpy.types.Panel):
    """The Set-up window's panel: a tab of its own, shown only in a Set-up window."""
    bl_label = "Set-up"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = TAB

    @classmethod
    def poll(cls, context):
        win = context.window
        try:
            return bool(win is not None and win.screen.get(MARK))
        except (AttributeError, ReferenceError):
            return False

    @classmethod
    def unregister(cls):
        _free_icons()

    def draw_header(self, context):
        self.layout.label(icon="PREFERENCES")

    def draw_header_preset(self, context):
        _kind, k, steps = current(context.scene)
        ui.header_status(self.layout, f"{k + 1} of {len(steps)}")

    def draw(self, context):
        draw_setup(self.layout, context)


CLASSES = (FRESING_PT_setup,)
