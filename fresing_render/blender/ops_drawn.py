"""Operators that draw hoses, cables and drag chains by clicking points (task 0240).

Three click pickers with the hover highlight of the other pickers (``hover.py``: the face under the mouse lights up
with its axis, the status line says what a click takes):

* **Draw hose / Draw cable** (``fresing.flex_draw`` kind HOSE / CABLE, 4 Motion > Hoses and drag chains): the
  fitting at end A, then any clips the hose runs through, then the fitting at end B; Enter finishes.
* **Draw drag chain** (``fresing.flex_draw`` kind CHAIN): the fixed end's bracket, then the moving end's bracket; it
  finishes by itself.
* **Draw cable route** (``fresing.cable_draw``, 4 Motion > Cables and paths): where it starts (a drum, or a point on a
  part), each sheave, roller or chute in order (on the side the cable passes – the same part again: the other side),
  then a flat face where it ends, or Enter for a free end.

In every picker: Backspace or Ctrl+Z takes the last click back, Esc or a right-click stops without drawing anything,
the middle mouse and the wheel move the view. The work is in ``flex.draw_hose``, ``flex.draw_chain`` and
``paths.draw_cable``; a whole drawing is one undo step.

Also here: **Replaces CAD part** / **Show it again** for a drawn item (``drawn.replace`` / ``drawn.unreplace``) and
**Flip bend** for a drawn chain.
"""

from __future__ import annotations

import bpy
import numpy as np
from bpy.props import BoolProperty, EnumProperty, StringProperty

from ..core.words import plural
from . import build, drawn, flex, hover, logic, paths
from .ops_motion import over_panel

HELP = "Backspace: undo the last click.  Esc / right-click: stop.  Middle mouse / scroll: move the view"


def _say(context, op, text: str, level: str = "INFO") -> None:
    context.scene.fresing.last_message = text
    op.report({level}, text)


def _name(ob) -> str:
    return ob.get(build.PROP_NAME, ob.name) if ob is not None else ""


def _refuse(scene):
    """What a draw picker will not take: a drawn object, a hose, chain or cable part (their own shapes)."""
    taken = {ob.name for ob in flex.flex_parts(scene)} | {ob.name for ob in paths.cable_parts(scene)}

    def refuse(ob, _o, _d):
        if drawn.is_drawn(ob) or ob.name in taken:
            return "a hose, cable or chain itself – click the part it is fixed to"
        return ""
    return refuse


class _Picker:
    """The modal part the three pickers share: hover, keys, the clicks kept as object names + numbers."""

    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        scene = context.scene
        return scene is not None and hasattr(scene, "fresing") and scene.fresing.model_count > 0

    def _begin(self, context, prompt: str):
        if context.area is None or context.area.type != "VIEW_3D":
            self.report({"WARNING"}, "Use this from the 3D view")
            return {"CANCELLED"}
        self._clicks = []                       # [(object name, polygon, location, normal)]
        self._hidden = []                       # the CAD part it will replace: hidden while clicking (it lies on the
        target = _replace_target(context, getattr(self, "replace", ""))      # fittings and brackets)
        for p in (drawn.replace_targets(context.scene, target) if target is not None else []):
            if p.visible_get():
                logic.set_visible_flags(p, True)
                self._hidden.append(p.name)
        context.window.cursor_modal_set("EYEDROPPER")
        hover.start(context, self, "", refuse=_refuse(context.scene))
        self._status(context, prompt)
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def _status(self, context, text: str) -> None:
        hover.prompt(context, f"{text}.  {HELP}")

    def _end(self, context) -> None:
        hover.end(self, context)
        for name in getattr(self, "_hidden", []):
            ob = context.scene.objects.get(name)
            if ob is not None and not ob.get(build.PROP_EXCLUDED):
                logic.set_visible_flags(ob, False)
        self._hidden = []
        try:
            context.window.cursor_modal_restore()
            context.workspace.status_text_set(None)
        except Exception:                       # noqa: BLE001 - the window may be gone (file closed)
            pass

    def _spots(self, scene) -> list:
        """The clicks as spots, worked out now (the parts may have moved meanwhile: the view was turned only)."""
        out = []
        for name, poly, loc, nrm in self._clicks:
            ob = scene.objects.get(name)
            if ob is None:
                raise drawn.DrawError("A part you clicked is gone: draw it again.")
            out.append(drawn.spot(ob, poly, loc, nrm))
        return out

    def modal(self, context, event):
        if not hover.active():                  # undo, a file opened: the pick has ended under us
            self._end(context)
            return {"CANCELLED"}
        hover.on_event(self, context, event)
        if event.value == "PRESS" and (event.type in {"ESC", "RIGHTMOUSE"}):
            self._end(context)
            _say(context, self, "Stopped: nothing was drawn")
            return {"CANCELLED"}
        if event.value == "PRESS" and (event.type == "BACK_SPACE" or (event.type == "Z" and event.ctrl)):
            if self._clicks:
                self._clicks.pop()
            self._status(context, self._next_prompt(context))
            return {"RUNNING_MODAL"}
        if event.value == "PRESS" and event.type in {"RET", "NUMPAD_ENTER", "SPACE"}:
            return self._enter(context)
        if event.type != "LEFTMOUSE" or event.value != "PRESS" or over_panel(context, event):
            return {"PASS_THROUGH"}
        res = hover.pick(context, event)
        if res is None:
            self._status(context, "Missed the model: " + self._next_prompt(context)[0].lower()
                         + self._next_prompt(context)[1:])
            return {"RUNNING_MODAL"}
        ob, index, loc, normal = res
        why = _refuse(context.scene)(ob, None, None)
        if why:
            self._status(context, f"'{_name(ob)}' is {why}")
            return {"RUNNING_MODAL"}
        return self._click(context, ob, index, tuple(loc), tuple(normal))

    # each picker: _next_prompt(context), _click(...), _enter(context), _make(context)

    def _click(self, context, ob, index, loc, normal):
        try:
            sp = drawn.spot(ob, index, loc, normal)
        except drawn.DrawError as exc:
            self._status(context, str(exc))
            return {"RUNNING_MODAL"}
        self._clicks.append((ob.name, index, loc, normal))
        self._status(context, drawn.spot_words(sp, "Taken") + ". " + self._next_prompt(context))
        return self._after_click(context)

    def _after_click(self, context):
        return {"RUNNING_MODAL"}

    def _enter(self, context):
        return {"RUNNING_MODAL"}

    def _finish(self, context):
        self._end(context)
        try:
            return self._make(context)
        except (flex.FlexError, paths.PathError, drawn.DrawError) as exc:
            _say(context, self, str(exc), "WARNING")
            return {"CANCELLED"}


def _replace_target(context, name: str):
    ob = context.scene.objects.get(name) if name else None
    return ob if ob is not None and ob.get(build.PROP_KIND) == "part" else None


class FRESING_OT_flex_draw(_Picker, bpy.types.Operator):
    """Draws a hose by clicking: first the fitting at end A, then (if you like) the clips it runs through, then the
    fitting at end B, then press Enter. The hose gets a sensible length and follows the motion like a hose read from
    the CAD file. For hoses and cables your CAD model does not have"""

    bl_idname = "fresing.flex_draw"
    bl_label = "Draw hose"

    kind: EnumProperty(name="Kind", default="HOSE", options={"SKIP_SAVE"},
                       items=[("HOSE", "Hose", "A hose: click its two fittings (and clips between)"),
                              ("CABLE", "Cable", "A soft cable that hangs: click its two ends (and clips between)"),
                              ("CHAIN", "Drag chain", "A drag chain: click its two brackets")],
                       description="What to draw")
    replace: StringProperty(name="Replaces", default="", options={"SKIP_SAVE"},
                            description="The simplified CAD part the drawn one replaces (hidden while it is drawn)")

    @classmethod
    def description(cls, context, properties):
        if properties.replace:
            what = "drag chain: click its two brackets" if properties.kind == "CHAIN" else \
                "hose: click its fitting at end A, any clips, its fitting at end B, then press Enter"
            return (f"Draws a {what}. It replaces the simplified CAD part you selected: that part hides while you "
                    "click, so the parts under it can be clicked, and stays hidden for good while the drawn one is "
                    "there")
        if properties.kind == "CHAIN":
            return ("Draws a drag chain by clicking its two brackets: first the bracket of the fixed end, then the "
                    "bracket on the part that moves. The app draws the links; they roll with the axis. Then set the "
                    "bend radius and the links under the list")
        if properties.kind == "CABLE":
            return ("Draws a soft cable that hangs between two ends: click where it starts, then (if you like) the "
                    "clips it runs through, then where it ends, then press Enter. It follows the motion")
        return " ".join(cls.__doc__.split())

    def invoke(self, context, event):
        return self._begin(context, self._next_prompt(context))

    def _next_prompt(self, context) -> str:
        n = len(getattr(self, "_clicks", []))
        if self.kind == "CHAIN":
            return ("1 of 2: click the bracket of the chain's FIXED end" if n == 0 else
                    "2 of 2: click the bracket on the part that MOVES")
        word = "cable" if self.kind == "CABLE" else "hose"
        if n == 0:
            return f"Click the fitting at end A of the {word}"
        if n == 1:
            return f"Click a clip the {word} runs through, or the fitting at end B"
        return (f"{plural(n, 'point')} clicked: click another clip or end B, or press Enter: the last click is "
                "end B")

    def _after_click(self, context):
        if self.kind == "CHAIN" and len(self._clicks) >= 2:
            return self._finish(context)
        return {"RUNNING_MODAL"}

    def _enter(self, context):
        if self.kind == "CHAIN" or len(self._clicks) < 2:
            self._status(context, "Not yet: " + self._next_prompt(context)[0].lower() + self._next_prompt(context)[1:])
            return {"RUNNING_MODAL"}
        return self._finish(context)

    def _make(self, context):
        scene = context.scene
        spots = self._spots(scene)
        target = _replace_target(context, self.replace)
        if self.kind == "CHAIN":
            item, notes = flex.draw_chain(scene, spots[0], spots[1], replace=target)
            what = f"Drag chain '{item.name}' drawn: {plural(item.count, 'link')}, bend radius " \
                   f"{item.radius * 1000.0:.0f} mm – move the axis and it rolls"
        else:
            item, notes = flex.draw_hose(scene, spots, soft=self.kind == "CABLE", replace=target)
            word = "Cable" if self.kind == "CABLE" else "Hose"
            clips = f", through {plural(len(item.clips), 'clip')}" if len(item.clips) else ""
            what = f"{word} '{item.name}' drawn: {item.length * 1000.0:.0f} mm long{clips} – move a joint and it " \
                   "follows"
        for note in notes:
            self.report({"WARNING"}, note)
        _say(context, self, what)
        return {"FINISHED"}


class FRESING_OT_cable_draw(_Picker, bpy.types.Operator):
    """Draws a cable route by clicking: where it starts (a drum, or a point on a part), then each sheave, roller or
    chute it runs over, in order (on the side the cable passes; click a part again for the other side), then a flat
    face where it ends, or press Enter for a free end. It runs, turns its wheels and pays out like a cable read from
    the CAD file"""

    bl_idname = "fresing.cable_draw"
    bl_label = "Draw cable route"

    replace: StringProperty(name="Replaces", default="", options={"SKIP_SAVE"},
                            description="The simplified CAD part the drawn cable replaces (hidden while it is drawn)")
    wind: BoolProperty(name="Layers on the drum", default=False, options={"SKIP_SAVE"},
                       description="A drum or carousel the cable starts on also gets its layers of cable "
                                   "(4 Motion > Drums and carousels)")

    def invoke(self, context, event):
        self._ended = False
        return self._begin(context, self._next_prompt(context))

    def _next_prompt(self, context) -> str:
        n = len(getattr(self, "_clicks", []))
        if n == 0:
            return "Click where the cable starts: a drum, or a point on a part"
        return (f"{plural(n - 1, 'wheel')} so far: click the next sheave, roller or chute (the same one again: the other "
                "side), a flat face where the cable ends, or press Enter for a free end")

    def _click(self, context, ob, index, loc, normal):
        if self._clicks and self._clicks[-1][0] == ob.name and len(self._clicks) > 1:
            self._clicks.append((ob.name, index, loc, normal))          # the same part again: the other side
            self._status(context, f"'{_name(ob)}': the cable passes on its other side. " + self._next_prompt(context))
            return {"RUNNING_MODAL"}
        if self._clicks:                        # a flat face (as the hover shows it) is the end; a round one a wheel
            try:
                sp = drawn.spot(ob, index, loc, normal)
            except drawn.DrawError as exc:
                self._status(context, str(exc))
                return {"RUNNING_MODAL"}
            if sp["round"] and paths._axis_of(ob, loc) is not None:
                return super()._click(context, ob, index, loc, normal)
            self._clicks.append((ob.name, index, loc, normal))
            self._ended = True
            return self._finish(context)
        return super()._click(context, ob, index, loc, normal)

    def _enter(self, context):
        if len(self._clicks) < 2:
            self._status(context, "Not yet: click the start and at least one sheave, roller or chute (or a flat "
                         "face where the cable ends)")
            return {"RUNNING_MODAL"}
        return self._finish(context)

    def _make(self, context):
        scene = context.scene
        clicks = list(self._clicks)
        name, poly, loc, nrm = clicks[0]
        ob = scene.objects.get(name)
        if ob is None:
            raise drawn.DrawError("A part you clicked is gone: draw it again.")
        start = drawn.spot(ob, poly, loc, nrm)
        end = None
        if self._ended:
            n2, p2, l2, m2 = clicks.pop()
            end = drawn.spot(scene.objects[n2], p2, l2, m2)
        wheels = []
        flips = 0
        for k, (n2, _p2, l2, _m2) in enumerate(clicks[1:]):
            if wheels and wheels[-1][0].name == n2:
                wheels[-1] = (wheels[-1][0], wheels[-1][1], not wheels[-1][2])
                flips += 1
                continue
            if k == 0 and n2 == name:           # the drum clicked again: it wraps the other way
                start["flip"] = not start.get("flip", False)
                continue
            wheels.append((scene.objects[n2], np.asarray(l2, dtype=float), False))
        target = _replace_target(context, self.replace)
        item, notes = paths.draw_cable(scene, start, wheels, end, joint=scene.fresing.cable_speed, replace=target,
                                       wind=self.wind)
        for note in notes[2:]:
            self.report({"WARNING"}, note)
        _say(context, self, f"Cable '{item.name}' drawn over {plural(len(paths._wheels(item)), 'wheel')}"
             f" ({item.length:.2f} m): give it a speed with a Run motor step")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# replace a simplified CAD part, flip a drawn chain's bend
# ---------------------------------------------------------------------------

def _drawn_item(context, target: str):
    scene = context.scene
    it = paths.active(scene) if target == "CABLE" else flex.active(scene)
    return it if it is not None and it.drawn else None


def _picked_part(context):
    ob = context.view_layer.objects.active
    if ob is None or ob.get(build.PROP_KIND) != "part" or drawn.is_drawn(ob) or not ob.select_get():
        return None
    return ob


class FRESING_OT_drawn_replace(bpy.types.Operator):
    """Hides the simplified CAD part you selected for good – in the view, in renders, in the clash check and in the
    web 3D model – while this drawn hose, cable or chain takes its place. Click the CAD part in the 3D view first
    (one link of a chain is enough). It shows again when you remove the drawn one"""

    bl_idname = "fresing.drawn_replace"
    bl_label = "Replaces selected CAD part"
    bl_options = {"REGISTER", "UNDO"}

    target: EnumProperty(name="List", default="FLEX", options={"SKIP_SAVE"},
                         items=[("FLEX", "Hoses and drag chains", ""), ("CABLE", "Cables", "")],
                         description="Which list's chosen item replaces the part")

    @classmethod
    def poll(cls, context):
        return _drawn_item(context, "FLEX") is not None or _drawn_item(context, "CABLE") is not None

    def execute(self, context):
        item = _drawn_item(context, self.target)
        ob = _picked_part(context)
        if item is None:
            _say(context, self, "Choose a drawn hose, cable or chain in the list first", "WARNING")
            return {"CANCELLED"}
        if ob is None:
            _say(context, self, "First click the simplified CAD part in the 3D view, then press this", "WARNING")
            return {"CANCELLED"}
        try:
            parts = drawn.replace(context.scene, item, ob)
        except drawn.DrawError as exc:
            _say(context, self, str(exc), "WARNING")
            return {"CANCELLED"}
        _say(context, self, f"'{_name(ob)}'" + (f" and {plural(len(parts) - 1, 'more link')}" if len(parts) > 1
                                                else "") + f" hidden for good: '{item.name}' takes its place")
        return {"FINISHED"}


class FRESING_OT_drawn_unreplace(bpy.types.Operator):
    """Shows the CAD parts this drawn hose, cable or chain replaces again (they are no longer hidden for good). The
    drawn one stays"""

    bl_idname = "fresing.drawn_unreplace"
    bl_label = "Show the CAD part again"
    bl_options = {"REGISTER", "UNDO"}

    target: EnumProperty(name="List", default="FLEX", options={"SKIP_SAVE"},
                         items=[("FLEX", "Hoses and drag chains", ""), ("CABLE", "Cables", "")],
                         description="Which list's chosen item")

    @classmethod
    def poll(cls, context):
        return any(it is not None and len(it.replaces) for it in (_drawn_item(context, "FLEX"),
                                                                    _drawn_item(context, "CABLE")))

    def execute(self, context):
        item = _drawn_item(context, self.target)
        if item is None or not len(item.replaces):
            return {"CANCELLED"}
        n = drawn.unreplace(context.scene, item)
        _say(context, self, f"{plural(n, 'CAD part')} shown again")
        return {"FINISHED"}


class FRESING_OT_flex_flip_bend(bpy.types.Operator):
    """Puts the drawn drag chain's bend on the other side: the fixed run then runs the other way along the travel.
    Use it when the chain rolls away from where it should"""

    bl_idname = "fresing.flex_flip_bend"
    bl_label = "Flip bend"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        it = _drawn_item(context, "FLEX")
        return it is not None and it.kind == "CHAIN"

    def execute(self, context):
        item = _drawn_item(context, "FLEX")
        flex.flip_bend(context.scene, item)
        _say(context, self, f"Drag chain '{item.name}': the bend is on the other side now")
        return {"FINISHED"}


CLASSES = (FRESING_OT_flex_draw, FRESING_OT_cable_draw, FRESING_OT_drawn_replace, FRESING_OT_drawn_unreplace,
           FRESING_OT_flex_flip_bend)
