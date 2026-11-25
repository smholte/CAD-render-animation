"""Side panel: 5 Scene & Render > Web 3D model (task 0099). Same layout rules as ui.py."""

from __future__ import annotations

import os

import bpy

from ..core import web3d as core
from . import animation, ui, vessel_motion, web3d, web3d_env, web3d_film
from .ui import BIG, MEDIUM, _has_model, _Panel, big, big_row, gap, header_status, hint, split_props, wrap


class FRESING_PT_web3d(_Panel, bpy.types.Panel):
    bl_label = "Web 3D model"
    bl_parent_id = "FRESING_PT_scene"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return _has_model(context)

    def draw_header(self, context):
        self.layout.label(icon="WORLD")

    def draw_header_preset(self, context):
        w = web3d.settings(context.scene)
        if web3d.runtime(context.scene).get("running"):
            header_status(self.layout, "exporting")
        elif w.last_size and os.path.exists(w.last_path):
            header_status(self.layout, core.header(w.last_size))
        else:
            header_status(self.layout, "not exported")

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        w = web3d.settings(scene)
        rt = web3d.runtime(scene)
        hint(layout, context, "One 3D file of the machine as it is shown now, with its looks, and a page that shows "
                              "it in any web browser: drag to turn, scroll to zoom.")
        from . import ui_locations
        ui_locations.draw_save_to(layout, context, scene)            # task 0272
        gap(layout)
        col = split_props(layout)
        row = col.row(align=True)
        row.prop(w, "texture_size", text="Texture size", expand=True)
        col.prop(w, "hide_names", text="Hide part names")
        col.prop(w, "view_names", text="View names")
        draw_views(context, layout, scene, w)     # task 0336: tick which cameras become views
        col = split_props(layout)
        col.prop(w, "measure_faces", text="Faces for measuring")
        col.prop(w, "compress", text="Smaller file")
        built = animation.has_keys(scene)
        if built:
            col.prop(w, "animation", text="Include animation")
        else:                                     # task 0336 (0328 row 15): say why it is greyed, offer the Build
            row = col.split(factor=0.4, align=True)
            left = row.row()
            left.alignment = "RIGHT"
            left.label(text="Include animation")
            row.operator("fresing.anim_build", text="Build & play first", icon="PLAY")
        if built and web3d_film.camera(scene) is None:
            wrap(col, context, "No Film button: the built animation's camera does not move.", icon="SEQUENCE")
        if web3d_film.camera(scene) is not None:  # task 0252: the page's Film button and what it shows over it
            sub = col.column(align=True)
            sub.enabled = w.animation
            sub.prop(w, "film_captions", text="Film: captions")
            sub.prop(w, "film_labels", text="Film: labels")
            sub.prop(w, "film_cards", text="Film: title and end card")
            wrap(col, context, "The page gets a Film button: the motion seen through the video's camera"
                 + ("" if w.animation else " (tick Include animation)") + ".", icon="SEQUENCE")
        from . import web3d_lead                  # task 0310: the lead motions as sliders on the page
        lms = web3d_lead.wanted(scene)
        if lms:
            col.prop(w, "lead_sliders", text="Lead motions as sliders")
            if w.lead_sliders:
                from ..core.words import plural
                shown = ", ".join(lm.name for lm in lms[:3]) + (", …" if len(lms) > 3 else "")
                wrap(col, context, f"Motions on the page ({plural(len(lms), 'slider')}): {shown}", icon="OPTIONS")
        gap(layout)
        draw_surroundings(context, layout, w)
        draw_light(context, layout, w)
        draw_player(context, layout)

        gap(layout)
        if rt.get("running"):
            row = big_row(layout, MEDIUM)
            row.label(text=f"{rt.get('text', 'Working')} … {rt.get('progress', 0.0) * 100:.0f}%", icon="SORTTIME")
            row.operator("fresing.web3d_cancel", text="Cancel", icon="CANCEL")
            return
        # task 0336 (0328 row 14): Open page and the folder on Export's own row – after an export they are where the
        # eye is (in the Make window the box under it lay below the window's edge); greyed until there is a page
        done = bool(w.last_text and os.path.exists(w.last_path))
        page = bool(done and w.last_html and os.path.exists(w.last_html))
        row = big_row(layout, BIG)
        big(row, "fresing.web3d_export", "Export…", "EXPORT", BIG)   # through big(): tools/ui_test_panel.py spies on it
        sub = row.row(align=True)
        sub.enabled = page
        sub.operator("fresing.open_file", text="Open page", icon="URL").path = w.last_html if page else ""
        sub = row.row(align=True)
        sub.enabled = done
        sub.operator("fresing.show_in_folder", text="", icon="FILE_FOLDER").path = w.last_path if done else ""
        if done:
            box = layout.box()
            box.label(text=os.path.basename(w.last_path), icon="FILE_3D")
            wrap(box, context, w.last_text, inset=12)
        gap(layout)
        wrap(layout, context, "Not in the web model: edge wear, the shine along brushed or turned metal, tool marks, "
                              "the cutaway of parts (the sea's cut-away is on the page), milling, chips and coolant (as at the frame shown)"
                              + (", the halls and the quay." if w.env_mode == "PROJECT" else
                                 ", the surroundings (see Surroundings on the page)."), icon="INFO")
        if web3d.has_marine_looks():              # task 0161: those parts are baked one by one
            gap(layout)
            wrap(layout, context, "Marine looks (growth, streaks, worn blade edge) are baked part by part where the "
                                  "parts stand: slower, a bigger file; the line above says how fine.", icon="INFO")
            layout.label(text="Marine detail")
            layout.row(align=True).prop(w, "marine_detail", expand=True)
            est = web3d.marine_estimate(context.scene)
            if est:
                n, f = est["NORMAL"], est["FINE"]
                cur = est[w.marine_detail]
                from ..core.words import plural
                from . import lightbake
                text = (f"{w.marine_detail.capitalize()}: about {cur['mm']:.0f} mm per pixel, file about "
                        f"+{core.mb(cur['bytes'])}, {plural(cur.get('bakes', 0), 'part')} baked (copies share one), "
                        f"bake {lightbake.duration(cur['seconds'])} (estimate)")
                if w.marine_detail == "NORMAL" and f["mm"] < n["mm"] * 0.8:
                    text += (f". Fine: {f['mm']:.0f} mm per pixel, +{core.mb(f['bytes'] - n['bytes'])}, "
                             f"+{f['seconds'] - n['seconds']:.0f} s; heavier on phones")
                wrap(layout, context, text, inset=12, icon="TIME")


def draw_views(context, layout, scene, w):
    """The fold "Page views" (task 0336, 0328 row 31): a tick per camera; folded, the header says how many
    and the line under it names them (task 0179: nothing goes out unseen)."""
    cams = web3d.all_cameras(scene)
    if not cams:
        return
    on = [ob for ob in cams if web3d.on_page(ob)]
    head, body = layout.panel("fr_web3d_views", default_closed=True)
    head.label(text="Page views")
    head.label(text=f"{len(on)} of {len(cams)}")
    numbered = w.view_names == "NUMBERED"
    if body is None:
        names = web3d.view_names(scene, numbered=numbered)
        if names:
            shown = ", ".join(names[:3]) + (", …" if len(names) > 3 else "")
            wrap(layout, context, f"On the page: {shown}", inset=12)
        else:
            wrap(layout, context, "No saved views on the page: open this fold to tick cameras.", inset=12)
        return
    col = body.column(align=True)
    k = 0
    for ob in cams:
        tick = web3d.on_page(ob)
        k += tick
        text = ob.name + (" (the app's)" if web3d.app_camera(ob) else "")
        if tick and numbered:
            text = f"View {k}: {text}"
        op = col.operator("fresing.web3d_view", text=text, emboss=False,
                          icon="CHECKBOX_HLT" if tick else "CHECKBOX_DEHLT")
        op.name = ob.name
    row = body.row(align=True)
    op = row.operator("fresing.web3d_view", text="All", icon="CHECKBOX_HLT")
    op.every, op.on = True, True
    op = row.operator("fresing.web3d_view", text="None", icon="CHECKBOX_DEHLT")
    op.every, op.on = True, False


PLAYER = (                                # task 0134: what the page offers the visitor (one short list)
    ("PREFERENCES", "Gear: surroundings on/off, quality, pictures a second, graphics card, auto-turn, sun"),
    ("PLAY", "Motion: Space plays and pauses, a time line to drag, speed ½× 1× 2×"),
    ("SEQUENCE", "Film: the motion seen through the video's camera (only with Include animation and a built "
                 "Animation camera); a drag leaves it, Film takes you back"),
    ("OPTIONS", "Motions: one slider per lead motion (top bar > Lead motions) with ▶ and Back to start; a slider "
                "pauses the animation, Play gives it back"),
    ("CAMERA_DATA", "Saved views: one per ticked camera (Page views), by its name or numbered (View names); "
                    "a phone (upright or sideways) shows one ‹ name › control and a list of all"),
    ("FULLSCREEN_ENTER", "Fullscreen (F), Reset view (R), Screenshot (S), Copy link to this view (L), keys (?)"),
    ("HIDE_ON", "Clean look (H): every control hidden, a faint button brings them back"),
    ("ERROR", "Says so when the browser draws without the graphics card, and how to fix it"),
)

def draw_player(context, layout):
    """The fold "On the page" (task 0134): what the exported page lets the visitor do."""
    head, body = layout.panel("fr_web3d_player", default_closed=True)
    head.label(text="On the page")
    if body is None:
        return
    for icon, text in PLAYER:
        wrap(body, context, text, icon=icon)
    wrap(body, context, "The page draws only when something moves, at most 60 pictures a second, and remembers "
                        "the visitor's choices.", inset=12)

def draw_light(context, layout, w):
    """The fold "Baked light" (task 0107): folded, its choice in the header."""
    from . import lightbake
    head, body = layout.panel("fr_web3d_light", default_closed=not ui._OPEN_FOLDS)
    head.label(text="Light")
    head.label(text={"LIVE": "live", "SOFT": "soft light baked", "ALL": "all baked"}[w.light])
    if body is None:
        return
    body.prop(w, "light", text="")
    if w.light == "LIVE":
        wrap(body, context, "The page lights the parts itself: smallest file, fastest export.", inset=12)
        return
    body.label(text="Bake quality")
    body.row(align=True).prop(w, "light_quality", expand=True)
    col = split_props(body)
    col.prop(w, "light_texels", text="Points per metre")
    est = web3d.light_estimate(context.scene)
    where = "graphics card" if est["gpu"] else "processor"
    wrap(body, context, f"Bake {lightbake.duration(est['seconds'])} on this PC's {where} (estimate), file about "
                        f"+{core.mb(est['bytes'])}; {est['texels_per_m']:.0f} points per metre.", inset=12,
         icon="TIME")
    if web3d.needs_light_question(context.scene):
        wrap(body, context, "Everything baked: the shadows stay where they are while the parts or the vessel "
                            "move. Soft light baked keeps the sun's shadows moving.", inset=12, icon="ERROR")

def draw_surroundings(context, layout, w):
    """The fold "Surroundings on the page" (task 0106): folded, its state in the header."""
    scene = context.scene
    head, body = layout.panel("fr_web3d_env", default_closed=not ui._OPEN_FOLDS)
    head.label(text="Surroundings on the page")
    if body is None:
        return
    body.row().prop(w, "env_mode", expand=True)
    if w.env_mode != "PROJECT":
        wrap(body, context, "The machine alone on a light background, as before.", inset=12)
        return
    col = split_props(body)
    col.prop(w, "env_sea", text="Sea")
    sub = col.row(align=True)
    sub.enabled = w.env_sea
    sub.prop(w, "env_sea_state", expand=True)
    sub = col.row()
    sub.enabled = w.env_sea and vessel_motion.effective(scene)
    sub.prop(w, "env_vessel", text="Vessel motion")
    col.prop(w, "env_sky", text="Sky")
    if w.env_sky:
        col.prop(w, "env_sky_source", text="Sky from")
        photo = web3d_env.light_kind(scene.fresing) not in ("SKY", "OVERCAST")
        if w.env_sky_source == "TIME" or not photo:
            sub = col.column(align=True)
            sub.enabled = w.env_sky_source == "TIME"
            sub.prop(w, "env_sun_height", text="Sun height")
            sub.prop(w, "env_sun_direction", text="Sun direction")
            col.prop(w, "env_clouds", text="Clouds")
    row = col.row(align=True)
    row.prop(w, "env_haze", text="Haze")
    sub = row.row(align=True)
    sub.enabled = w.env_haze
    sub.prop(w, "env_haze_strength", text="")
    row = col.row(align=True)
    row.prop(w, "env_rain", text="Rain")
    sub = row.row(align=True)
    sub.enabled = w.env_rain
    sub.prop(w, "env_rain_strength", text="")
    col.prop(w, "env_shadows", text="Live sun shadows")
    body.label(text="Page quality")
    body.row(align=True).prop(w, "env_quality", expand=True)
    col = split_props(body)
    col.prop(w, "env_auto", text="Auto quality")
    body.operator("fresing.web3d_env_from_project", text="Take from the project", icon="FILE_REFRESH")


PANELS = (FRESING_PT_web3d,)
CLASSES = PANELS
