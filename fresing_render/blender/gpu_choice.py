"""Always the graphics card (task 0296): the start check, the calm notice, "Show me how" and Settings > General's
"Graphics" line. The rules are in ``core/gpu_choice.py``, Windows' adapter list and preference in ``wingpu.py``,
Cycles' devices in ``render.setup_gpu``.

**At the start** (a window, not the background; a timer once the window is there): on Windows, started from the
installed app, Windows' graphics preference "High performance" is written for the app's programs where the user has
not chosen (``wingpu.ensure``); then the GPU that draws the window (``gpu.platform.renderer_get``) is judged against
the adapter list and kept in ``<config>/fresing_gpu.json`` (the self-test and the PC check run in the background and
read it there).

**The notice** – one small window, at most once per start, never in the background, the tests (``FRESING_NO_WELCOME``,
simulated events unless ``FRESING_GPU_TEST``), the PC check or the kit; never at a start that shows the welcome or
What's new (it waits for the next start); never after "Don't ask again" until the set of GPUs changes:

* built-in graphics draw the window while the PC has a card -> **Use the graphics card** (writes the preference for
  the app's programs, asks to start the app again) · **Show me how** · Cancel = **Not now** · **Don't ask again**;
* the 3D view is clearly slow (``core.DrawTimes``: three frames in a row over 2 s) -> the same window with Show me how.
  It does not show again in that start, and not on a start where a preference just written waits for the next start.
"""

from __future__ import annotations

import os
import sys
import time

import bpy
from bpy.props import BoolProperty, EnumProperty, StringProperty

from ..core import gpu_choice as core
from ..core import start as start_core

TEST_ENV = "FRESING_GPU_TEST"         # the notice's own test: show it although events are simulated
GUIDE_ANCHOR = "graphics-card"
_RUN = {"done": False, "shown": False, "pending": False, "window": {}, "sig": "", "slow_s": 0.0, "written": [],
        "handlers": [], "t": 0.0, "waits": 0}
_TIMES = core.DrawTimes()


# ---------------------------------------------------------------------------
# The state file, the adapters, the window
# ---------------------------------------------------------------------------

def state_path() -> str:
    return os.path.join(bpy.utils.user_resource("CONFIG"), core.FILE_NAME)


def load() -> dict:
    return core.load(state_path())


def save(state: dict) -> None:
    try:
        core.save(state_path(), state)
    except OSError as exc:
        print("Fresing Render: could not save the graphics settings:", exc)


def render_choice() -> str:
    """The render device picked in Settings > General > Graphics (AUTO, CPU or a Cycles device id)."""
    try:
        return load().get("render_device") or core.AUTO
    except Exception:  # noqa: BLE001 - never break a render over this file
        return core.AUTO


def adapters() -> list:
    """Windows' list of graphics adapters ([] elsewhere)."""
    if sys.platform != "win32":
        return []
    from .. import wingpu
    return wingpu.adapters()


def renderer() -> str:
    """The GPU that draws this window, as its driver names it ('' in the background or when not known)."""
    if bpy.app.background:
        return ""
    try:
        import gpu
        return str(gpu.platform.renderer_get() or "")
    except Exception:  # noqa: BLE001
        return ""


def backend() -> str:
    try:
        import gpu
        return str(gpu.platform.backend_type_get())
    except Exception:  # noqa: BLE001
        return ""


def programs() -> list:
    """The app's programs (Windows): the running one, ``blender.exe`` and ``Fresing Render.exe`` next to it."""
    if sys.platform != "win32":
        return []
    from .. import wingpu
    return wingpu.programs(bpy.app.binary_path)


def installed() -> bool:
    """Started from the app's own install (Install.bat), not from another Blender."""
    try:
        from .. import appicon
        return bool(appicon.install_dir(bpy.app.binary_path))
    except Exception:  # noqa: BLE001
        return False


def preference_of(exe: str) -> str | None:
    if sys.platform != "win32" or not exe:
        return None
    from .. import wingpu
    return wingpu.preferences([exe]).get(exe)


def look(drawn: str | None = None) -> dict:
    """What draws the window now: ``core.window_state`` plus the cable check and the running program's preference."""
    found = adapters()
    info = core.window_state(renderer() if drawn is None else drawn, found)
    info["cable"] = core.cable_in_motherboard(found)
    info["backend"] = backend()
    pref = preference_of(os.path.abspath(bpy.app.binary_path or ""))
    info["preference"] = core.preference_name(pref) if sys.platform == "win32" else ""
    return info


def record(info: dict) -> None:
    """Keep what this start saw (the self-test and the PC check run in the background and read it here)."""
    state = load()
    state["window"] = {"state": info.get("state", ""), "drawn": info.get("drawn", ""), "card": info.get("card", ""),
                       "kind": info.get("kind", ""), "when": time.strftime("%Y-%m-%d %H:%M"),
                       "program": os.path.basename(bpy.app.binary_path or ""), "preference": info.get("preference", ""),
                       "cable": bool(info.get("cable"))}
    save(state)


def suppressed() -> bool:
    """Nothing pops up: background runs, the tests, the PC check and the kit (``FRESING_NO_WELCOME``), simulated events
    (real-app tests) unless this notice's own test asks for it."""
    if bpy.app.background or os.environ.get(start_core.NO_POPUP_ENV):
        return True
    return bool(getattr(bpy.app, "use_event_simulate", False)) and not os.environ.get(TEST_ENV)


def _welcome_shows() -> bool:
    """The welcome or What's new shows at this start: the notice waits for the next one (one window at a time)."""
    try:
        from . import welcome
        return bool(welcome._RUN.get("shows"))
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------------------
# The start check
# ---------------------------------------------------------------------------

def at_start() -> str:
    """The check after the start: the preference, what draws the window, the notice. Returns what it shows."""
    _RUN["done"] = True
    if sys.platform == "win32" and installed():
        from .. import wingpu
        state = load()
        done = [p for p in state.get("auto_done", []) if isinstance(p, str)]
        exes = programs()
        # once per program: a later "Let Windows decide" in Windows' settings is the user's choice (independent review)
        written = wingpu.ensure([p for p in exes if os.path.normcase(p) not in {os.path.normcase(d) for d in done}])
        now = wingpu.preferences(exes)
        done += [p for p in exes if core.parse_preference(now.get(p)).get("GpuPreference") == core.HIGH_PERFORMANCE
                 and os.path.normcase(p) not in {os.path.normcase(d) for d in done}]
        if done != state.get("auto_done"):
            state["auto_done"] = done
            save(state)
        _RUN["written"] = written
        running = os.path.normcase(os.path.abspath(bpy.app.binary_path or ""))
        _RUN["pending"] = any(os.path.normcase(p) == running for p in written)
        if written:
            print("Fresing Render (graphics): Windows' graphics preference set to High performance for",
                  ", ".join(os.path.basename(p) for p in written), "(used from the next start)")
    info = look()
    _RUN["window"] = info
    _RUN["sig"] = core.signature(adapters(), names=() if adapters() else (info.get("drawn", ""),))
    record(info)
    print(f"Fresing Render (graphics): the window is drawn by {info.get('drawn') or '?'} ({info.get('state')})")
    if suppressed():
        return ""
    _add_timing()
    if _welcome_shows():
        return ""
    kind = core.decide_notice(load(), _RUN["sig"], info, shown=_RUN["shown"], pending=_RUN["pending"])
    if kind:
        show(kind)
    return kind


def _tick():
    if _RUN["done"]:
        return None
    try:
        wm = bpy.context.window_manager
        if wm is None or not wm.windows:
            return 0.5
        if not renderer() and _RUN["waits"] < 20:          # the window's GPU context is not up yet
            _RUN["waits"] += 1
            return 0.5
        at_start()
    except Exception as exc:  # noqa: BLE001 - never break the start of the app
        print("Fresing Render (graphics): start check:", exc)
    return None


# --- the 3D view's frame time (clearly slow) -----------------------------------

def _pre():
    _RUN["t"] = time.perf_counter()


def _post():
    t0 = _RUN.get("t") or 0.0
    if not t0:
        return
    _RUN["t"] = 0.0
    if _TIMES.add(time.perf_counter() - t0) and not _RUN["shown"]:
        _RUN["slow_s"] = _TIMES.worst
        _remove_timing()
        bpy.app.timers.register(_slow_notice, first_interval=0.2)


def _slow_notice():
    try:
        kind = core.decide_notice(load(), _RUN["sig"], _RUN.get("window") or {}, slow=True, shown=_RUN["shown"],
                                  pending=_RUN["pending"])
        if kind and not suppressed():
            show(kind)
    except Exception as exc:  # noqa: BLE001
        print("Fresing Render (graphics): slow-view notice:", exc)
    return None


def _add_timing() -> None:
    if _RUN["handlers"]:
        return
    sv = bpy.types.SpaceView3D
    _RUN["handlers"] = [sv.draw_handler_add(_pre, (), "WINDOW", "PRE_VIEW"),
                        sv.draw_handler_add(_post, (), "WINDOW", "POST_PIXEL")]


def _remove_timing() -> None:
    for h in _RUN["handlers"]:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(h, "WINDOW")
        except (ValueError, RuntimeError):
            pass
    _RUN["handlers"] = []


# ---------------------------------------------------------------------------
# The notice and its buttons
# ---------------------------------------------------------------------------

def _override():
    wm = bpy.context.window_manager
    win = wm.windows[0] if wm and wm.windows else None
    if win is None:
        return None
    area = next((a for a in win.screen.areas if a.type == "VIEW_3D"), None)
    kw = {"window": win, "screen": win.screen}
    if area is not None:
        kw.update(area=area, region=next((r for r in area.regions if r.type == "WINDOW"), None))
    return kw


def show(kind: str) -> bool:
    kw = _override()
    if kw is None:
        return False
    _RUN["shown"] = True
    _remove_timing()
    try:
        with bpy.context.temp_override(**kw):
            bpy.ops.fresing.gpu_notice("INVOKE_DEFAULT", kind=kind)
        return True
    except Exception as exc:  # noqa: BLE001
        print("Fresing Render (graphics): could not show the notice:", exc)
        return False


def _wrap(layout, text: str, width: int = 86, icon: str = "NONE") -> None:
    import textwrap
    for i, line in enumerate(textwrap.wrap(text, width) or [""]):
        layout.label(text=line, icon=icon if i == 0 else "NONE")


def use_card() -> list:
    """Windows: "High performance" for the app's programs, whatever was set. Returns the programs written."""
    if sys.platform != "win32":
        return []
    from .. import wingpu
    done = wingpu.force(programs())
    _RUN["pending"] = True
    return done


def never_again() -> None:
    state = load()
    state["never_for"] = _RUN.get("sig") or core.signature(adapters(), names=(renderer(),))
    save(state)


class FRESING_OT_gpu_notice(bpy.types.Operator):
    """Fresing Render runs on the processor's built-in graphics or the 3D view is slow: use the graphics card, or see
    how to set it in Windows"""

    bl_idname = "fresing.gpu_notice"
    bl_label = "Graphics card"
    bl_options = {"INTERNAL"}

    kind: StringProperty(options={"HIDDEN", "SKIP_SAVE"})
    never: BoolProperty(name="Don't ask again", options={"SKIP_SAVE"},
                        description="Tick it and close: this window does not show again (until a graphics card is "
                                    "added or changed). Settings > General > Graphics shows the same any time")

    def _card(self) -> bool:
        return (_RUN.get("window") or {}).get("state") == "built_in_with_card" and sys.platform == "win32"

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(
            self, width=600, title="Graphics card",
            confirm_text="Use the graphics card" if self._card() else "Show me how")

    def draw(self, context):
        col = self.layout.column()
        for line in core.notice_text(self.kind or "built_in", _RUN.get("window") or {}, _RUN.get("slow_s", 0.0)):
            _wrap(col, line)
        col.separator()
        if self._card():
            col.operator("fresing.gpu_how", text="Show me how", icon="QUESTION")
        _wrap(col, "Cancel = not now: asked again at the next start.", icon="TIME")
        col.prop(self, "never")

    def execute(self, context):
        if self.never:
            never_again()
        if self._card():
            bpy.ops.fresing.gpu_use_card("INVOKE_DEFAULT")
        else:
            bpy.ops.fresing.gpu_how("INVOKE_DEFAULT")
        return {"FINISHED"}

    def cancel(self, context):
        if self.never:
            never_again()


class FRESING_OT_gpu_use_card(bpy.types.Operator):
    """Ask Windows to run Fresing Render on the graphics card: sets Windows' graphics preference for the app to High
    performance. It takes effect when you start the app again"""

    bl_idname = "fresing.gpu_use_card"
    bl_label = "Use the graphics card"

    @classmethod
    def poll(cls, context):
        return sys.platform == "win32"

    def invoke(self, context, event):
        self.execute(context)
        card = (_RUN.get("window") or {}).get("card") or "the graphics card"

        def draw(menu, _context):
            menu.layout.label(text="Done. Save your project, close Fresing Render and start it again:", icon="CHECKMARK")
            menu.layout.label(text=f"from then on {card} draws the window.")
        context.window_manager.popup_menu(draw, title="Use the graphics card", icon="INFO")
        return {"FINISHED"}

    def execute(self, context):
        try:
            done = use_card()
        except Exception as exc:  # noqa: BLE001
            self.report({"ERROR"}, f"Could not set Windows' graphics preference: {exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, "Windows' graphics preference: High performance"
                    + (f" ({len(done)} program{'s' if len(done) != 1 else ''})" if done else " (already set)")
                    + ". Start the app again to use it")
        return {"FINISHED"}


class FRESING_OT_gpu_how(bpy.types.Operator):
    """How to make Fresing Render use the graphics card: Windows' Graphics settings, NVIDIA Control Panel, AMD Software
    and the monitor cable, step by step"""

    bl_idname = "fresing.gpu_how"
    bl_label = "Show me how"

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=640)

    def draw(self, context):
        info = _RUN.get("window") or look()
        col = self.layout.column()
        col.label(text="Use the graphics card – step by step", icon="QUESTION")
        exes = programs() or ["Fresing Render.exe"]
        for i, step in enumerate(core.guide_steps(info.get("card", ""), exes, bool(info.get("cable"))), 1):
            _wrap(col, f"{i}. {step}", 96)
        col.separator()
        row = col.row()
        if sys.platform == "win32":
            row.operator("fresing.gpu_windows_page", icon="PREFERENCES")
        row.operator("fresing.whats_new_guide", text="Open the user guide", icon="HELP").anchor = GUIDE_ANCHOR

    def execute(self, context):
        return {"FINISHED"}


class FRESING_OT_gpu_windows_page(bpy.types.Operator):
    """Open Windows' Graphics settings (Settings > System > Display > Graphics), where a program's GPU is chosen"""

    bl_idname = "fresing.gpu_windows_page"
    bl_label = "Open Windows' Graphics settings"

    @classmethod
    def poll(cls, context):
        return sys.platform == "win32"

    def execute(self, context):
        try:
            os.startfile(core.SETTINGS_URI)         # noqa: S606 - Windows' own Settings page
        except OSError as exc:
            self.report({"ERROR"}, f"Could not open Windows' Settings: {exc}")
            return {"CANCELLED"}
        return {"FINISHED"}


def _device_items(self, context):
    from . import render
    items = core.choices(render.cycles_devices())
    _device_items.keep = [(i, label, desc) for i, label, desc in items]     # Blender needs the strings kept alive
    return _device_items.keep


class FRESING_OT_gpu_render_device(bpy.types.Operator):
    """Pick what Cycles renders on: Automatic uses the graphics card (only the card when the PC also has built-in
    graphics), or one device, or the processor"""

    bl_idname = "fresing.gpu_render_device"
    bl_label = "Render on"
    bl_property = "device"

    device: EnumProperty(name="Render on", items=_device_items)

    def execute(self, context):
        from . import render
        state = load()
        state["render_device"] = self.device or core.AUTO
        save(state)
        info = render.setup_gpu()
        self.report({"INFO"}, f"Renders on: {info}")
        return {"FINISHED"}


class FRESING_OT_gpu_look(bpy.types.Operator):
    """Look for the devices Cycles can render on (the graphics card, built-in graphics), so you can pick one. It takes
    a few seconds the first time"""

    bl_idname = "fresing.gpu_look"
    bl_label = "Look for devices"

    def execute(self, context):
        from . import render
        render.cycles_devices(fresh=True)
        self.report({"INFO"}, f"Renders on: {render.setup_gpu()}")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Settings > General > Graphics
# ---------------------------------------------------------------------------

def summary() -> dict:
    """The lines of Settings > General > Graphics: {"draws", "draws_kind", "renders", "choice", "state", "card"}."""
    from . import render
    info = _RUN.get("window") or (look() if not bpy.app.background else dict(load().get("window") or {}))
    plan = render.LAST.get("plan")
    devices = render.known_devices()           # never read from a draw: switching backends writes the preferences
    choice = render_choice()
    if plan is None and devices is not None:
        plan = core.render_plan(devices, choice)
    label = next((lab for i, lab, _d in core.choices(devices or []) if i == choice), "Automatic")
    return {"draws": info.get("drawn") or "not known", "draws_kind": info.get("kind", ""), "state": info.get("state", ""),
            "card": info.get("card", ""), "renders": plan.text() if plan else "CPU", "choice": label,
            "note": plan.note if plan else "", "preference": info.get("preference", ""),
            "known": devices is not None}


_KIND_WORDS = {core.CARD: "graphics card", core.BUILT_IN: "built-in graphics", core.SOFTWARE: "the processor, no GPU"}


def draw_settings(layout) -> None:
    """Settings > General: which GPU draws the window, which renders, the list to pick the render device."""
    box = layout.box()
    col = box.column()
    col.label(text="Graphics", icon="DESKTOP")
    try:
        s = summary()
    except Exception as exc:  # noqa: BLE001 - never break the settings page
        col.label(text=f"Not known here: {exc}", icon="ERROR")
        return
    kind = _KIND_WORDS.get(s["draws_kind"], "")
    row = col.row()
    row.alert = s["state"] == "built_in_with_card"
    row.label(text=f"Draws the window: {s['draws']}" + (f" ({kind})" if kind else ""))
    if not s["known"]:
        col.label(text="Renders (Cycles): looked up at the first render")
    elif s["renders"].startswith("GPU"):
        col.label(text="Renders (Cycles): " + s["renders"].replace("GPU (", "graphics card (", 1))
    else:
        col.label(text="Renders (Cycles): the processor")
    if s["note"]:
        hint = col.row()
        hint.active = False
        hint.label(text=s["note"])
    if s["preference"]:
        hint = col.row()
        hint.active = False
        hint.label(text=f"Windows' graphics preference for this program: {s['preference']}")
    row = col.row(align=True)
    row.label(text="Render on")
    if s["known"]:
        row.operator_menu_enum("fresing.gpu_render_device", "device", text=s["choice"], icon="RENDER_STILL")
    else:
        row.operator("fresing.gpu_look", text=f"{s['choice']} · Look for devices", icon="VIEWZOOM")
    row = col.row(align=True)
    if s["state"] == "built_in_with_card" and sys.platform == "win32":
        row.operator("fresing.gpu_use_card", icon="CHECKMARK")
    row.operator("fresing.gpu_how", icon="QUESTION")


# ---------------------------------------------------------------------------
# The self-test's and the PC check's line "Graphics card used"
# ---------------------------------------------------------------------------

def check(no_gpu_expected: bool = False) -> tuple:
    """("ok" | "skip" | "problem", text). Background runs cannot see the window: they read what the app's last start
    saw (``record``). A problem: the window drawn by built-in graphics while the PC has a card, Cycles rendering on
    built-in graphics while a card exists, or Windows' preference set to Power saving for the app."""
    from . import render
    found = adapters()
    best = core.cards(found)
    rend = render.setup_gpu()
    plan = render.LAST.get("plan")
    win = look() if not bpy.app.background else dict(load().get("window") or {})
    card_names = [core.short(a.name) for a in best]
    if not card_names and plan is not None and plan.gpu:
        card_names = sorted({core.short(n) for n in plan.names if core.kind(n) == core.CARD})
    has_card = bool(card_names) or win.get("state") in ("card", "built_in_with_card")
    if not has_card and not (plan is not None and plan.gpu) and no_gpu_expected:
        return "skip", "skipped: no graphics card"
    drawn = win.get("drawn") or ""
    when = "" if not bpy.app.background else (f", at the app's start {win.get('when')}" if win.get("when") else "")
    kind = _KIND_WORDS.get(win.get("kind", ""), "")
    text = [f"draws: {drawn} ({kind}{when})" if drawn else "draws: not known yet (start the app once)",
            f"renders: {rend}"]
    if win.get("preference"):
        text.append(f"Windows' preference: {win['preference']}")
    problems = []
    if win.get("state") == "built_in_with_card":
        problems.append(f"the window is drawn by the built-in {drawn} although this PC has {win.get('card') or 'a card'}"
                        ": start the app and press Use the graphics card (Fresing > Settings > General > Graphics)"
                        + (" and plug the monitor into the graphics card" if win.get("cable") else ""))
    if card_names and plan is not None and plan.gpu and render_choice() == core.AUTO and             all(core.kind(n) == core.BUILT_IN for n in plan.names):
        problems.append(f"Cycles renders on built-in graphics although this PC has {card_names[0]}: update the "
                        "graphics card's driver")
    if card_names and plan is not None and not plan.gpu and render_choice() == core.AUTO:
        problems.append(f"Cycles finds no device on {card_names[0]}: update the graphics card's driver")
    if win.get("preference") == "Power saving" and card_names:
        problems.append("Windows' graphics preference for Fresing Render is Power saving: set it to High performance "
                        "(Show me how)")
    if not card_names and not has_card:
        text.append("this PC has no graphics card (built-in graphics only)")
    if problems:
        return "problem", "; ".join(problems) + " | " + "; ".join(text)
    return "ok", "; ".join(text)


CLASSES = (FRESING_OT_gpu_notice, FRESING_OT_gpu_use_card, FRESING_OT_gpu_how, FRESING_OT_gpu_windows_page,
           FRESING_OT_gpu_render_device, FRESING_OT_gpu_look)


def register_handlers() -> None:
    if not bpy.app.background and not bpy.app.timers.is_registered(_tick):
        bpy.app.timers.register(_tick, first_interval=3.0, persistent=True)


def unregister_handlers() -> None:
    _remove_timing()
    if bpy.app.timers.is_registered(_tick):
        bpy.app.timers.unregister(_tick)
