"""The buttons of lead motions (task 0309): the menu's ▶, + and Back to start, its two windows (Keep open, Edit lead
motions…), and the editor's buttons (new, remove, order, from two poses, Record, a joint's row, Order by stages,
Test). Everything they change is in ``lead_motions.py``.

The Client view keeps ▶, Back to start and Keep open (``lock.ALLOWED``): looking at the functions moves the model,
nothing else is changed. Edit lead motions…, + Add to animation and Show every function change the project and are
refused there, as every other edit.
"""

from __future__ import annotations

import time

import bpy
from bpy.props import EnumProperty, IntProperty

from ..core import lead_motions as core
from ..core.words import plural
from . import lead_motions

_PLAYING: dict = {}                 # lead motion name -> the play's token (a newer ▶ on it stops the older one)


def _lm(context, index: int):
    s = context.scene.fresing
    if 0 <= index < len(s.lead_motions):
        return s.lead_motions[index]
    return lead_motions.active(context.scene)


def _redraw(context=None) -> None:
    wm = bpy.context.window_manager
    for win in (wm.windows if wm is not None else ()):
        for area in win.screen.areas:
            area.tag_redraw()


# ---------------------------------------------------------------------------
# the menu
# ---------------------------------------------------------------------------

class FRESING_OT_lead_play(bpy.types.Operator):
    """Plays this lead motion to 100 % over its seconds (from where its slider is). Pressed again at 100 %: plays it
    back to 0 %"""

    bl_idname = "fresing.lead_play"
    bl_label = "Play"
    bl_options = {"REGISTER", "UNDO"}

    index: IntProperty(default=-1, options={"HIDDEN", "SKIP_SAVE"})
    TEST = False                     # Test: there and back again (FRESING_OT_lead_test)

    @classmethod
    def poll(cls, context):
        return context.scene is not None and len(context.scene.fresing.lead_motions) > 0

    def _legs(self, lm):
        if self.TEST:
            return [(lm.position, 100.0), (100.0, 0.0)]
        return [(lm.position, core.play_target(lm.position))]

    def execute(self, context):
        """Without a window (scripts, tests): straight to where the play would end."""
        lm = _lm(context, self.index)
        if lm is None:
            return {"CANCELLED"}
        for _a, b in self._legs(lm):
            lead_motions.set_position(lm, b)
        return {"FINISHED"}

    def invoke(self, context, event):
        lm = _lm(context, self.index)
        if lm is None:
            return {"CANCELLED"}
        if bpy.app.background or context.window is None:
            return self.execute(context)
        self._name = lm.name
        self._legs_left = self._legs(lm)
        self._t0 = time.perf_counter()
        self._token = object()
        _PLAYING[lm.name] = self._token
        self._timer = context.window_manager.event_timer_add(1.0 / 30.0, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def _end(self, context):
        try:
            context.window_manager.event_timer_remove(self._timer)
        except (AttributeError, ReferenceError, ValueError):
            pass
        if _PLAYING.get(self._name) is self._token:
            _PLAYING.pop(self._name, None)

    def modal(self, context, event):
        if event.type != "TIMER":
            return {"PASS_THROUGH"}
        s = context.scene.fresing
        lm = s.lead_motions.get(self._name)
        if lm is None or _PLAYING.get(self._name) is not self._token:
            self._end(context)
            return {"FINISHED"}
        a, b = self._legs_left[0]
        t = time.perf_counter() - self._t0
        p = core.play_position(a, b, lm.seconds, t, "LINEAR")
        lead_motions.set_position(lm, p)
        if abs(p - b) < 1e-6:
            self._legs_left.pop(0)
            self._t0 = time.perf_counter()
            if not self._legs_left:
                self._end(context)
                _redraw(context)
                return {"FINISHED"}
        _redraw(context)
        return {"RUNNING_MODAL"}


class FRESING_OT_lead_test(bpy.types.Operator):
    """Plays this lead motion from 0 to 100 % and back to 0 %, so you see the whole function once"""

    bl_idname = "fresing.lead_test"
    bl_label = "Test"
    bl_options = {"REGISTER", "UNDO"}

    index: IntProperty(default=-1, options={"HIDDEN", "SKIP_SAVE"})
    TEST = True

    poll = FRESING_OT_lead_play.poll
    _legs = FRESING_OT_lead_play._legs
    execute = FRESING_OT_lead_play.execute
    invoke = FRESING_OT_lead_play.invoke
    _end = FRESING_OT_lead_play._end
    modal = FRESING_OT_lead_play.modal


class FRESING_OT_lead_back_to_start(bpy.types.Operator):
    """Puts every lead motion back to 0 %: the machine stands where all its functions start"""

    bl_idname = "fresing.lead_back_to_start"
    bl_label = "Back to start"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.scene is not None and len(context.scene.fresing.lead_motions) > 0

    def execute(self, context):
        _PLAYING.clear()
        lead_motions.back_to_start(context.scene)
        _redraw(context)
        return {"FINISHED"}


class FRESING_OT_lead_add_step(bpy.types.Operator):
    """Adds a Lead motion step at the end of the animation (6 Animation): this lead motion from 0 to 100 % over its
    seconds. Build & play then shows it"""

    bl_idname = "fresing.lead_add_step"
    bl_label = "Add to animation"
    bl_options = {"REGISTER", "UNDO"}

    index: IntProperty(default=-1, options={"HIDDEN", "SKIP_SAVE"})

    @classmethod
    def poll(cls, context):
        return context.scene is not None and len(context.scene.fresing.lead_motions) > 0

    def execute(self, context):
        lm = _lm(context, self.index)
        if lm is None:
            return {"CANCELLED"}
        anim = _anim(context)
        b = lead_motions.add_step(context.scene, anim, lm, 0.0, 100.0)
        self.report({"INFO"}, f"Added '{lm.name}' to '{anim.name}' at {b.start:.1f} s: Build & play shows it")
        return {"FINISHED"}


def _anim(context):
    """The animation steps go into: the one picked in 6 Animation, or a new one."""
    s = context.scene.fresing
    if not (0 <= s.animations_index < len(s.animations)):
        bpy.ops.fresing.anim_add()
    return s.animations[s.animations_index]


class FRESING_OT_lead_show_all(bpy.types.Operator):
    """Adds one step per lead motion to the animation, each out and back, one after another: a film of every
    function in one click. With Captions on (6 Animation > Finishing) each one shows its name"""

    bl_idname = "fresing.lead_show_all"
    bl_label = "Show every function"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.scene is not None and len(context.scene.fresing.lead_motions) > 0

    def execute(self, context):
        anim = _anim(context)
        n = lead_motions.show_every_function(context.scene, anim)
        if not n:
            self.report({"WARNING"}, "No lead motion has a joint it can move")
            return {"CANCELLED"}
        self.report({"INFO"}, f"Added {n} steps to '{anim.name}': Build & play shows every function")
        return {"FINISHED"}


class FRESING_OT_lead_keep_open(bpy.types.Operator):
    """Shows the lead motions' sliders in a small window that stays open: put it beside the model, or on a second
    screen"""

    bl_idname = "fresing.lead_keep_open"
    bl_label = "Keep open"

    def invoke(self, context, event):
        from . import form_window
        return form_window.open(self, context, width=420, height=110 + 34 * len(context.scene.fresing.lead_motions),
                                title="Lead motions", confirm=None, icon="CON_ACTION")

    def execute(self, context):
        return {"FINISHED"}

    def draw(self, context):
        from .ui_lead_motions import draw_menu
        draw_menu(self.layout, context, in_window=True)


# ---------------------------------------------------------------------------
# the editor
# ---------------------------------------------------------------------------

class FRESING_OT_lead_edit(bpy.types.Operator):
    """Opens the lead motions' editor in a window of its own: make a lead motion from two poses, by recording, or by
    picking joints; set each joint's part of the slider; order, rename and test them"""

    bl_idname = "fresing.lead_edit"
    bl_label = "Edit lead motions…"

    def invoke(self, context, event):
        from . import form_window
        return form_window.open(self, context, width=560, height=640, title="Lead motions", confirm=None,
                                icon="CON_ACTION")

    def execute(self, context):
        return {"FINISHED"}

    def draw(self, context):
        from .ui_lead_motions import draw_editor
        draw_editor(self.layout, context)


class FRESING_OT_lead_make_one(bpy.types.Operator):
    """Makes a new, empty lead motion and opens the editor: give it its joints from two poses, by recording, or by
    picking them"""

    bl_idname = "fresing.lead_make_one"
    bl_label = "Make one…"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        lead_motions.add(context.scene)
        return {"FINISHED"}

    def invoke(self, context, event):
        self.execute(context)
        return bpy.ops.fresing.lead_edit("INVOKE_DEFAULT")


class FRESING_OT_lead_new(bpy.types.Operator):
    """Adds a new, empty lead motion at the end of the list. Then give it its joints below"""

    bl_idname = "fresing.lead_new"
    bl_label = "New lead motion"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        lead_motions.add(context.scene)
        return {"FINISHED"}


class FRESING_OT_lead_remove(bpy.types.Operator):
    """Deletes the lead motion picked in the list. The joints stay where they are; animation steps that use it say
    so when you Build"""

    bl_idname = "fresing.lead_remove"
    bl_label = "Delete lead motion"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return lead_motions.active(context.scene) is not None

    def execute(self, context):
        s = context.scene.fresing
        s.lead_motions.remove(s.lead_index)
        s.lead_index = min(s.lead_index, len(s.lead_motions) - 1)
        return {"FINISHED"}


class FRESING_OT_lead_move(bpy.types.Operator):
    """Moves the picked lead motion up or down: the Lead motions menu lists them in this order"""

    bl_idname = "fresing.lead_move"
    bl_label = "Move lead motion"
    bl_options = {"REGISTER", "UNDO"}

    direction: EnumProperty(items=[("UP", "Up", "One place up"), ("DOWN", "Down", "One place down")],
                            options={"SKIP_SAVE"})

    @classmethod
    def poll(cls, context):
        return lead_motions.active(context.scene) is not None

    def execute(self, context):
        s = context.scene.fresing
        i = s.lead_index
        k = i - 1 if self.direction == "UP" else i + 1
        if 0 <= k < len(s.lead_motions):
            s.lead_motions.move(i, k)
            s.lead_index = k
        return {"FINISHED"}


class FRESING_OT_lead_from_poses(bpy.types.Operator):
    """Gives the picked lead motion every joint that differs between the two poses: the start pose is 0 %, the end
    pose 100 %. The machine goes to the start pose"""

    bl_idname = "fresing.lead_from_poses"
    bl_label = "Use these poses"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return len(context.scene.fresing.poses) >= 2

    def execute(self, context):
        sc = context.scene
        lm = lead_motions.active(sc) or lead_motions.add(sc, f"{sc.fresing.lead_pose_b}" or "Lead motion")
        try:
            n = lead_motions.from_poses(sc, lm, sc.fresing.lead_pose_a, sc.fresing.lead_pose_b)
        except RuntimeError as exc:
            self.report({"WARNING"}, str(exc))
            return {"CANCELLED"}
        self.report({"INFO"}, f"'{lm.name}' moves {plural(n, 'joint')}")
        return {"FINISHED"}


class FRESING_OT_lead_record_start(bpy.types.Operator):
    """Record, step 1: put the machine where the motion starts, then press Set start. Then move the joints (4 Motion's
    joint box, or G / R on a joint's part) to where it ends and press Set end"""

    bl_idname = "fresing.lead_record_start"
    bl_label = "Set start"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        n = lead_motions.record_start(context.scene)
        if not n:
            self.report({"WARNING"}, "This project has no joints yet: make them in 4 Motion first")
            return {"CANCELLED"}
        self.report({"INFO"}, "Start set: now move the joints to where the motion ends, then press Set end")
        return {"FINISHED"}


class FRESING_OT_lead_record_end(bpy.types.Operator):
    """Record, step 2: the joints that moved since Set start become the picked lead motion's joints, from where they
    were to where they are now (a new lead motion when none is picked)"""

    bl_idname = "fresing.lead_record_end"
    bl_label = "Set end"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return lead_motions.recording(context.scene)

    def execute(self, context):
        sc = context.scene
        lm = lead_motions.active(sc) or lead_motions.add(sc)
        try:
            n = lead_motions.record_end(sc, lm)
        except RuntimeError as exc:
            self.report({"WARNING"}, str(exc))
            return {"CANCELLED"}
        self.report({"INFO"}, f"'{lm.name}' moves {plural(n, 'joint')}")
        return {"FINISHED"}


class FRESING_OT_lead_row_add(bpy.types.Operator):
    """Adds the joint picked next to it as a row of the lead motion: from where it is now to its upper limit. Change
    its values and its part of the slider below"""

    bl_idname = "fresing.lead_row_add"
    bl_label = "Add joint"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return bool(context.scene.fresing.lead_pick)

    def execute(self, context):
        sc = context.scene
        lm = lead_motions.active(sc) or lead_motions.add(sc)
        try:
            lead_motions.add_row(sc, lm, sc.fresing.lead_pick)
        except RuntimeError as exc:
            self.report({"WARNING"}, str(exc))
            return {"CANCELLED"}
        return {"FINISHED"}


class FRESING_OT_lead_row_remove(bpy.types.Operator):
    """Takes the picked joint out of this lead motion (the joint itself stays)"""

    bl_idname = "fresing.lead_row_remove"
    bl_label = "Remove joint"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        lm = lead_motions.active(context.scene)
        return lm is not None and 0 <= lm.rows_index < len(lm.rows)

    def execute(self, context):
        lm = lead_motions.active(context.scene)
        lm.rows.remove(lm.rows_index)
        lm.rows_index = min(lm.rows_index, len(lm.rows) - 1)
        return {"FINISHED"}


class FRESING_OT_lead_row_move(bpy.types.Operator):
    """Moves the picked joint up or down in the list (the order only changes how it reads; the slider's parts set
    when each joint moves)"""

    bl_idname = "fresing.lead_row_move"
    bl_label = "Move joint"
    bl_options = {"REGISTER", "UNDO"}

    direction: EnumProperty(items=[("UP", "Up", "One place up"), ("DOWN", "Down", "One place down")],
                            options={"SKIP_SAVE"})

    @classmethod
    def poll(cls, context):
        lm = lead_motions.active(context.scene)
        return lm is not None and len(lm.rows) > 1

    def execute(self, context):
        lm = lead_motions.active(context.scene)
        i = lm.rows_index
        k = i - 1 if self.direction == "UP" else i + 1
        if 0 <= k < len(lm.rows):
            lm.rows.move(i, k)
            lm.rows_index = k
        return {"FINISHED"}


class FRESING_OT_lead_row_here(bpy.types.Operator):
    """Takes where the joint is now as its value at 0 % (or at 100 %): move the joint in 4 Motion, then press it"""

    bl_idname = "fresing.lead_row_here"
    bl_label = "Use where it is"
    bl_options = {"REGISTER", "UNDO"}

    end: EnumProperty(items=[("V0", "At 0 %", "Its value at 0 %"), ("V1", "At 100 %", "Its value at 100 %")],
                      options={"SKIP_SAVE"})

    @classmethod
    def poll(cls, context):
        lm = lead_motions.active(context.scene)
        return lm is not None and 0 <= lm.rows_index < len(lm.rows)

    def execute(self, context):
        from . import joints
        sc = context.scene
        lm = lead_motions.active(sc)
        r = lm.rows[lm.rows_index]
        j = joints.find(sc, r.joint)
        if j is None:
            self.report({"WARNING"}, f"The joint '{r.joint}' is missing")
            return {"CANCELLED"}
        with lead_motions.quiet():
            r[self.end.lower()] = float(joints.get_value(j))
        lead_motions.set_position(lm, 0.0 if self.end == "V0" else 100.0, move=False)
        return {"FINISHED"}


class FRESING_OT_lead_stages(bpy.types.Operator):
    """Order by stages: gives every joint its part of the slider from its stage – stage 1 first, then 2, 3 … – each
    stage running a little into the next (Overlap)"""

    bl_idname = "fresing.lead_stages"
    bl_label = "Order by stages"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        lm = lead_motions.active(context.scene)
        return lm is not None and len(lm.rows) > 0

    def execute(self, context):
        lm = lead_motions.active(context.scene)
        lead_motions.apply_stages(lm, context.scene.fresing.lead_overlap)
        return {"FINISHED"}


CLASSES = (FRESING_OT_lead_play, FRESING_OT_lead_test, FRESING_OT_lead_back_to_start, FRESING_OT_lead_add_step,
           FRESING_OT_lead_show_all, FRESING_OT_lead_keep_open, FRESING_OT_lead_edit, FRESING_OT_lead_make_one,
           FRESING_OT_lead_new, FRESING_OT_lead_remove, FRESING_OT_lead_move, FRESING_OT_lead_from_poses,
           FRESING_OT_lead_record_start, FRESING_OT_lead_record_end, FRESING_OT_lead_row_add,
           FRESING_OT_lead_row_remove, FRESING_OT_lead_row_move, FRESING_OT_lead_row_here, FRESING_OT_lead_stages)
