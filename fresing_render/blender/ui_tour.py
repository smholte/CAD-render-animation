"""The Test tour panel (task 0059): shown only in a test tour project, at the top of the Fresing tab.

Stops in four folds (Look, Motion, Machining, Pictures and videos); the stop picked is shown under the list with
what you should see, Go, OK / Problem and its note; at the end Copy results and the automatic run.
"""

from __future__ import annotations

import bpy

from ..core.words import plural
from . import tour, ui
from .ui_left import LeftPanel


def _since() -> str:
    try:
        from . import welcome
        return welcome.since_for_marks()
    except Exception:  # noqa: BLE001
        return ""


def stop_mark(st, since: str) -> str:
    """"New" / "Changed" for a stop seen by a user who ran ``since`` before this update (task 0199), else ''."""
    from .. import __version__
    from ..core import start
    return {"new": "New", "changed": "Changed"}.get(start.mark(st.since, st.changed, since, __version__), "")


# task 0281: one chapter open at a time. ``open`` = the chapter the user opened or closed by hand (None: follow the
# picked stop's chapter); ``seen`` = the picked stop's chapter at the last draw, so a pick or Go into another chapter
# opens that one and closes the rest.
CHAPTER = {"open": None, "seen": None}


def open_chapter(current_group: str) -> str:
    """The one chapter shown open ('' = none)."""
    if CHAPTER["seen"] != current_group:
        CHAPTER["seen"] = current_group
        CHAPTER["open"] = None
    return current_group if CHAPTER["open"] is None else CHAPTER["open"]


def _state_icon(state: str) -> str:
    return {tour.OK_STATE: "CHECKMARK", tour.PROBLEM: "ERROR"}.get(state, "LAYER_USED")


class FRESING_PT_tour(LeftPanel, bpy.types.Panel):
    bl_label = "Learning hub stops"
    bl_order = 0

    @classmethod
    def poll(cls, context):
        return tour.is_tour(context.scene)

    def draw_header(self, context):
        self.layout.label(icon="VIEW_CAMERA")

    def draw_header_preset(self, context):
        folder, version = tour.tour_of_file(context.scene)
        rows = tour.load_results(folder, version)["stops"] if folder else {}
        done = sum(1 for s in tour.STOPS if rows.get(s.id, {}).get("state"))
        bad = sum(1 for s in tour.STOPS if rows.get(s.id, {}).get("state") == tour.PROBLEM)
        ui.header_status(self.layout, f"{bad} problem" if bad else f"{done} of {len(tour.STOPS)}", alert=bool(bad))

    def draw(self, context):
        layout = self.layout
        folder, version = tour.tour_of_file(context.scene)
        if not folder:
            ui.wrap(layout, context, "Save this project first.", icon="INFO")
            return
        data = tour.load_results(folder, version)
        rows = data["stops"]
        current = tour.find(data.get("current", "")) or tour.STOPS[0]
        ui.wrap(layout, context, f"Learning hub {version}: pick a stop, press Go, look, then OK or Problem.")
        since = _since()
        made = tour.made_sets(folder, version)
        if len(made) < len(tour.SETS):            # task 0199: a tour of only the new and changed test models
            ui.wrap(layout, context, f"Only {plural(len(made), 'test model project')} of {len(tour.SETS)} are made "
                                     "(the new and changed ones). The other stops need the whole tour.", icon="INFO")
            layout.operator("fresing.tour_make", text="Make the whole tour", icon="FILE_REFRESH")
        if since:
            from ..core import start
            from .. import __version__
            sets = [ts for ts in tour.SETS.values() if start.mark(ts.added, ts.changed, since, __version__)]
            if sets:
                ui.wrap(layout, context, f"New or changed since {since}: " + ", ".join(ts.title for ts in sets) + ".",
                        icon="ADD")
        for group in tour.GROUPS:
            stops = [s for s in tour.STOPS if s.group == group]
            n_ok = sum(1 for s in stops if rows.get(s.id, {}).get("state"))
            is_open = open_chapter(current.group) == group
            head = layout.row(align=True)
            head.alignment = "LEFT"
            head.operator("fresing.tour_chapter", emboss=False, text=f"{tour.GROUP_TITLES[group]}  ({n_ok}/{len(stops)})",
                          icon="DISCLOSURE_TRI_DOWN" if is_open else "DISCLOSURE_TRI_RIGHT").group = group
            if not is_open:
                continue
            body = layout
            col = body.column(align=True)
            for s in stops:
                row = col.row(align=True)
                row.alignment = "LEFT"
                m = stop_mark(s, since) if since else ""
                op = row.operator("fresing.tour_pick", text=f"{s.number}. {s.title}" + (f"  – {m}" if m else ""),
                                  icon=_state_icon(rows.get(s.id, {}).get("state", "")), emboss=s is current,
                                  depress=s is current)
                op.stop = s.id
        box = layout.box()
        st = current
        state = rows.get(st.id, {}).get("state", "")
        note = rows.get(st.id, {}).get("note", "")
        ui.wrap(box, context, f"{st.number}. {st.title}", icon=_state_icon(state))
        m = stop_mark(st, since) if since else ""
        if m:
            ui.wrap(box, context, f"New in {st.since}" if m == "New" else f"Changed in {st.changed}", inset=12)
        if st.set not in made:
            ui.wrap(box, context, "Its project is not made yet: Make the whole tour (above).", inset=12)
        ui.wrap(box, context, st.see, inset=12)
        if st.where:
            ui.wrap(box, context, f"Where: {st.where}", inset=12)
        ui.primary(box, "fresing.tour_go", "Go", "PLAY").stop = st.id
        row = box.row(align=True)
        op = row.operator("fresing.tour_mark", text="OK", icon="CHECKMARK", depress=state == tour.OK_STATE)
        op.stop, op.state = st.id, tour.OK_STATE
        op = row.operator("fresing.tour_mark", text="Problem", icon="ERROR", depress=state == tour.PROBLEM)
        op.stop, op.state = st.id, tour.PROBLEM
        row = box.row()
        row.operator("fresing.tour_note", text="Note…" if not note else "Change note…", icon="TEXT").stop = st.id
        if note:
            ui.wrap(box, context, f"Note: {note}", inset=12)
        nxt = next((s for s in tour.STOPS if s.number == st.number + 1), None)
        if nxt is not None:
            box.operator("fresing.tour_go", text=f"Next: {nxt.number}. {nxt.title}", icon="FORWARD").stop = nxt.id

        done = sum(1 for s in tour.STOPS if rows.get(s.id, {}).get("state"))
        layout.separator()
        ui.wrap(layout, context, f"{plural(done, 'stop')} of {len(tour.STOPS)} marked.")
        ui.big_row(layout, ui.MEDIUM).operator("fresing.tour_copy", icon="COPYDOWN")
        body = ui.fold(layout, "fresing_tour_more", "More", icon="DOWNARROW_HLT")
        if body is not None:
            body.operator("fresing.tour_run", icon="PLAY")
            body.operator("fresing.tour_folder", icon="FILE_FOLDER")
            body.operator("fresing.tour_make", text="Make the tour again…", icon="FILE_REFRESH")


class FRESING_OT_tour_chapter(bpy.types.Operator):
    """Opens this chapter of the Learning hub stops and closes the other one, or closes it again"""

    bl_idname = "fresing.tour_chapter"
    bl_label = "Open or close a chapter"
    bl_options = {"INTERNAL"}

    group: bpy.props.StringProperty(options={"HIDDEN", "SKIP_SAVE"})

    def execute(self, context):
        shown = CHAPTER["open"] if CHAPTER["open"] is not None else CHAPTER["seen"]
        CHAPTER["open"] = "" if shown == self.group else self.group
        from . import panels
        panels.redraw()
        return {"FINISHED"}


CLASSES = (FRESING_PT_tour, FRESING_OT_tour_chapter)
