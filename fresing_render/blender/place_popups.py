"""The quick unlock popup by the mouse and the "Lock it again" popup after the move (task 0338).

G / R (or right-click > Move / turn…) on a model or subassembly that is **locked in place** used to stop with a line in
the status bar ("… right-click it > Unlock so it can move …"). Now a small popup opens **by the mouse**: the name, an
**Unlock** button and an **×**. Unlock unlocks what held the move (every locked owner of the selection, as
``place.lock_owner`` finds them) and starts the same move at once (Blender's G / R, or the Move / turn window). After
that move is **confirmed** (not cancelled) a second popup shows in the **top left of the 3D view**, below the view's own
text: the name, **Lock it again** (locks exactly what the first popup unlocked) and **×**.

**How it is built** – both popups are drawn by a POST_PIXEL draw handler in the 3D view's window region (only in the
area they belong to) and their clicks are read by a modal operator in that window, because Blender's own popups close
as soon as the mouse leaves them and the owner wants *click outside / × / Esc* instead:

* ``FRESING_OT_unlock_popup`` – started by ``fresing.move_key`` / ``fresing.place_window`` when the refusal is "locked
  in place". While it is up it takes the keyboard (Esc closes, Return = Unlock) and clicks (Unlock, ×, inside: nothing,
  outside: closes – the click does nothing else, so nothing changes); mouse moves, the wheel and the middle button
  pass on (the view can still be turned).
* ``FRESING_OT_lock_again`` – started from a timer once the move is done. It passes **every** event on (it never takes
  a key or a click from the view) apart from clicks on its own buttons and Esc; it stays at least ``STAY`` seconds;
  after them any click in that window (the 3D view, a menu, a side panel) closes it and still does its own job. A move
  started on top of it (G again) gets the events first, so an Esc that cancels that move only cancels the move.

The draw handler is added only while a popup is up and removed when it closes: nothing is drawn per frame otherwise.

**Undo:** Unlock is one undo step ("Unlock …") and the move its own ("Move" / "Rotate", Blender's); Lock it again is
one step ("Lock … again"). The plain functions (``unlock``, ``after_move``, ``lock_again``, ``close``) are what the
operators do; the tests and the PC check call them where no mouse exists.
"""

from __future__ import annotations

import time

import bpy
from bpy.props import EnumProperty, IntProperty, StringProperty

STAY = 5.0                                     # seconds the Lock it again popup stays before a click closes it

UNLOCK_TIP = "Unlock it so it can move. You can lock it again afterwards"
AGAIN_TIP = "Locks it in place again: it moves only with the subassembly it is in, as before"

BG = (0.12, 0.12, 0.13, 0.97)
EDGE = (0.36, 0.36, 0.40, 1.0)
TEXT = (0.93, 0.93, 0.93, 1.0)
GREY = (0.66, 0.66, 0.68, 1.0)
BTN = (0.30, 0.30, 0.33, 1.0)
BTN_HOVER = (0.40, 0.40, 0.45, 1.0)
BTN_MAIN = (0.18, 0.46, 0.84, 1.0)
BTN_MAIN_HOVER = (0.26, 0.55, 0.95, 1.0)

MODES = (("TRANSLATE", "Move", "G"), ("ROTATE", "Turn", "R"), ("WINDOW", "Move / turn window", "Move / turn…"))

# one popup of each kind at a time
UNLOCK: dict = {"on": False, "owners": [], "mode": "", "at": (0.0, 0.0), "area": 0, "hover": "", "gen": 0}
AGAIN: dict = {"on": False, "owners": [], "since": 0.0, "area": 0, "hover": "", "gen": 0}
PENDING: dict = {"owners": [], "mode": "", "area": 0, "window": 0, "start": {}}     # unlocked, its move not done yet
HANDLE = [None]
SHOWN = [0, 0]                 # times each popup was opened (tests, the PC check): unlock, again


def _name(ob) -> str:
    from . import place
    return place._name(ob)


def _obs(names) -> list:
    return [bpy.data.objects[n] for n in names if n in bpy.data.objects]


def title(names) -> str:
    obs = _obs(names)
    if not obs:
        return ""
    head = f"'{_name(obs[0])}'"
    return head + (f" and {len(obs) - 1} more" if len(obs) > 1 else "")


def held_owners(context, mode: str) -> list:
    """The locked owners (subassemblies, else the parts) that hold a G / R of the selection: [] when nothing does."""
    from . import place
    out = []
    for ob in place.movers(context):
        if mode in ("TRANSLATE", "ROTATE"):
            if not place._locked(ob, mode):
                continue
        elif not place.locked(ob):
            continue
        owner = place.lock_owner(ob) or ob
        if owner.name not in out:
            out.append(owner.name)
    return out


# ---------------------------------------------------------------------------
# what the buttons do (plain functions: operators, tests, the PC check)
# ---------------------------------------------------------------------------

def _undo_push(message: str) -> None:
    if bpy.app.background:
        return
    try:
        bpy.ops.ed.undo_push(message=message)
    except RuntimeError:
        pass


def unlock(context, owners, mode: str) -> list:
    """Unlock button: unlock ``owners`` (names) and remember them for the Lock it again popup after the move."""
    from . import ops_place, place
    obs = _obs(owners)
    for ob in obs:
        ops_place.set_lock(ob, False)
    if AGAIN["on"] and set(AGAIN["owners"]) != set(owners):
        close("again")                                          # unlocking something else replaces it
    start = {o.name: o.matrix_world.copy() for o in place.movers(context)}
    PENDING.update(owners=[o.name for o in obs], mode=mode, start=start)
    _undo_push(f"Unlock {title(owners)}")
    place.LAST[0] = f"{title(owners)} is unlocked: it moves now"
    return [o.name for o in obs]


def after_move(names, moved: bool = True) -> bool:
    """A move ended (``moved`` False: cancelled). True when it starts the Lock it again popup."""
    owners = list(PENDING["owners"])
    if not owners:
        return False
    if AGAIN["on"] and set(AGAIN["owners"]) == set(owners):
        return False                                            # a second move: one popup
    if not moved:
        PENDING["owners"] = []
        return False
    from . import place
    touched = set(names)
    for n in names:
        ob = bpy.data.objects.get(n)
        o = place.lock_owner(ob) if ob is not None else None
        if o is not None:
            touched.add(o.name)
    if not touched & set(owners):
        return False
    PENDING["owners"] = []
    show_again(owners, PENDING.get("area", 0), PENDING.get("window", 0))
    return True


def show_again(owners, area=0, window=0) -> None:
    AGAIN.update(on=True, owners=list(owners), since=time.time(), area=area, hover="", gen=AGAIN["gen"] + 1)
    SHOWN[1] += 1
    _handler(True)
    if bpy.app.background:
        return
    gen = AGAIN["gen"]

    def start():
        if AGAIN["gen"] != gen or not AGAIN["on"]:
            return None
        win, ar, reg = _find(window, area)
        if win is None:
            return None
        if RUNNING_AGAIN[0]:
            _redraw()
            return None
        try:
            with bpy.context.temp_override(window=win, screen=win.screen, area=ar, region=reg):
                bpy.ops.fresing.lock_again("INVOKE_DEFAULT")
        except RuntimeError:
            pass
        _redraw()
        return None
    bpy.app.timers.register(start, first_interval=0.01)


def lock_again() -> list:
    """Lock it again: lock exactly what the unlock popup unlocked."""
    from . import ops_place, place
    obs = _obs(AGAIN["owners"])
    for ob in obs:
        ops_place.set_lock(ob, True)
    msg = f"{title(AGAIN['owners'])} is locked in place again"
    close("again")
    _undo_push(msg)
    place.LAST[0] = msg
    return [o.name for o in obs]


def close(which: str = "both") -> None:
    if which in ("unlock", "both"):
        UNLOCK.update(on=False, hover="")
    if which in ("again", "both"):
        AGAIN.update(on=False, hover="", owners=[])
    if not UNLOCK["on"] and not AGAIN["on"]:
        _handler(False)
    _redraw()


def can_close_by_click(now: float | None = None) -> bool:
    return AGAIN["on"] and ((now or time.time()) - AGAIN["since"]) >= STAY


# ---------------------------------------------------------------------------
# where they are (region pixels: x, y = bottom left)
# ---------------------------------------------------------------------------

def _scale() -> float:
    try:
        return bpy.context.preferences.system.ui_scale or 1.0
    except AttributeError:
        return 1.0


def _text_w(text: str, size: float) -> float:
    try:
        import blf
        blf.size(0, size)
        return blf.dimensions(0, text)[0]
    except Exception:                                           # noqa: BLE001 – no font: a fair guess
        return len(text) * size * 0.55


def card(text: str, button: str, x: float, y_top: float, region_w: float, region_h: float, s: float,
         clamp: bool = True) -> dict:
    """The card of a popup: {"box", "button", "x", "text"} as (x, y, w, h) in region pixels; ``x``/``y_top`` = its top
    left (clamped into the region when ``clamp``)."""
    pad, gap = 10 * s, 8 * s
    th = 13 * s                                                 # text size
    bh, xw = 26 * s, 20 * s
    bw = _text_w(button, th) + 28 * s
    w = max(_text_w(text, th) + 2 * pad + xw + gap, bw + 2 * pad, 200 * s)
    h = pad + 18 * s + gap + bh + pad
    if clamp:
        x = min(max(x, 4 * s), max(4 * s, region_w - w - 4 * s))
        y_top = min(max(y_top, h + 4 * s), region_h - 4 * s)
    y = y_top - h
    return {"box": (x, y, w, h), "button": (x + pad, y + pad, bw, bh),
            "x": (x + w - xw - 4 * s, y + h - xw - 4 * s, xw, xw), "text": (x + pad, y + h - pad - 13 * s, th),
            "scale": s}


def unlock_card(region, mouse_xy, names, s=None) -> dict:
    """By the mouse: its top left a little right of and above the pointer, kept inside the view."""
    s = s or _scale()
    mx, my = mouse_xy
    return card(f"{title(names)} is locked in place", "Unlock", mx + 14 * s, my + 60 * s, region.width,
                region.height, s)


def top_clear(area, region, s=None) -> tuple:
    """(left, top) in region pixels where nothing of the view's own is drawn in its top left: right of a toolbar or
    side panel that lies over the view, below an overlapping header and below the view's text (its name, the object's
    name, the frame rate while it plays, the statistics when they are on)."""
    s = s or _scale()
    left, top = 0.0, float(region.height)
    for r in area.regions:
        if r.type in ("TOOLS", "UI") and r.width > 1 and r.alignment == "LEFT" and r.x <= region.x + 1:
            left = max(left, r.x + r.width - region.x)
        if r.type in ("HEADER", "TOOL_HEADER") and r.height > 1 and r.y < region.y + region.height:
            top = min(top, r.y - region.y)
    lines = 3                                                   # view name, object name, frame rate (playing)
    space = area.spaces.active
    ov = getattr(space, "overlay", None)
    if ov is not None and getattr(ov, "show_stats", False):
        lines += 9
    if ov is not None and not getattr(ov, "show_text", True):
        lines = 9 if getattr(ov, "show_stats", False) else 0
    return left, top - (14 + lines * 19) * s


def again_card(area, region, names, s=None) -> dict:
    s = s or _scale()
    left, top = top_clear(area, region, s)
    return card(f"{title(names)} was unlocked to move it", "Lock it again", left + 10 * s, top - 6 * s,
                region.width, region.height, s, clamp=False)


def _inside(r, x, y) -> bool:
    return r[0] <= x <= r[0] + r[2] and r[1] <= y <= r[1] + r[3]


def hit(c: dict, x: float, y: float) -> str:
    """'button', 'x', 'card' or '' for a point in region pixels."""
    if _inside(c["x"], x, y):
        return "x"
    if _inside(c["button"], x, y):
        return "button"
    if _inside(c["box"], x, y):
        return "card"
    return ""


def _find(window_ptr, area_ptr):
    wm = bpy.context.window_manager
    for win in wm.windows:
        if window_ptr and win.as_pointer() != window_ptr:
            continue
        for ar in win.screen.areas:
            if ar.type == "VIEW_3D" and (not area_ptr or ar.as_pointer() == area_ptr):
                reg = next((r for r in ar.regions if r.type == "WINDOW"), None)
                if reg is not None:
                    return win, ar, reg
    return None, None, None


def geometry(which: str) -> tuple:
    """(area, region, card) of a popup that is up, else (None, None, None) – the real-app test clicks from this."""
    st = UNLOCK if which == "unlock" else AGAIN
    if not st["on"]:
        return None, None, None
    _win, ar, reg = _find(0, st["area"])
    if ar is None:
        return None, None, None
    c = unlock_card(reg, st["at"], st["owners"]) if which == "unlock" else again_card(ar, reg, st["owners"])
    return ar, reg, c


def point(which: str, part: str = "button") -> tuple | None:
    """Window pixels of a popup's button / × middle."""
    ar, reg, c = geometry(which)
    if c is None:
        return None
    x, y, w, h = c[part]
    return int(reg.x + x + w / 2), int(reg.y + y + h / 2)


# ---------------------------------------------------------------------------
# drawing
# ---------------------------------------------------------------------------

def _redraw() -> None:
    try:
        for win in bpy.context.window_manager.windows:
            for ar in win.screen.areas:
                if ar.type == "VIEW_3D":
                    ar.tag_redraw()
    except (AttributeError, ReferenceError):
        pass


def _handler(on: bool) -> None:
    if on and HANDLE[0] is None and not bpy.app.background:
        HANDLE[0] = bpy.types.SpaceView3D.draw_handler_add(_draw, (), "WINDOW", "POST_PIXEL")
    elif not on and HANDLE[0] is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(HANDLE[0], "WINDOW")
        except (ValueError, RuntimeError):
            pass
        HANDLE[0] = None


def _rect(shader, batch_for_shader, r, col, grow=0.0) -> None:
    x, y, w, h = r
    x, y, w, h = x - grow, y - grow, w + 2 * grow, h + 2 * grow
    shader.uniform_float("color", col)
    batch_for_shader(shader, "TRI_FAN", {"pos": [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]}).draw(shader)


def _draw_card(c: dict, text: str, button: str, hover: str, note: str = "") -> None:
    import blf
    import gpu
    from gpu_extras.batch import batch_for_shader
    s = c["scale"]
    flat = gpu.shader.from_builtin("UNIFORM_COLOR")
    gpu.state.blend_set("ALPHA")
    _rect(flat, batch_for_shader, c["box"], EDGE, grow=1.0)
    _rect(flat, batch_for_shader, c["box"], BG)
    _rect(flat, batch_for_shader, c["button"], BTN_MAIN_HOVER if hover == "button" else BTN_MAIN)
    if hover == "x":
        _rect(flat, batch_for_shader, c["x"], BTN_HOVER)
    tx, ty, size = c["text"]
    blf.size(0, size)
    blf.color(0, *TEXT)
    blf.position(0, tx, ty, 0)
    blf.draw(0, text)
    bx, by, bw, bh = c["button"]
    tw = _text_w(button, size)
    blf.color(0, *TEXT)
    blf.position(0, bx + (bw - tw) / 2, by + (bh - size * 0.72) / 2, 0)
    blf.draw(0, button)
    if note:
        blf.size(0, size * 0.85)
        blf.color(0, *GREY)
        blf.position(0, bx + bw + 10 * s, by + (bh - size * 0.62) / 2, 0)
        blf.draw(0, note)
    xx, xy, xw, xh = c["x"]
    blf.size(0, size * 1.1)
    blf.color(0, *(TEXT if hover == "x" else GREY))
    w = _text_w("×", size * 1.1)
    blf.position(0, xx + (xw - w) / 2, xy + xh * 0.28, 0)
    blf.draw(0, "×")
    gpu.state.blend_set("NONE")


def _draw() -> None:
    try:
        area = bpy.context.area
        if area is None:
            return
        ptr = area.as_pointer()
        if AGAIN["on"] and AGAIN["area"] in (0, ptr):
            ar, reg, c = area, bpy.context.region, None
            if reg is not None:
                c = again_card(ar, reg, AGAIN["owners"])
                note = "Esc closes" if not can_close_by_click() else "a click closes"
                _draw_card(c, f"{title(AGAIN['owners'])} was unlocked to move it", "Lock it again", AGAIN["hover"],
                           note)
        if UNLOCK["on"] and UNLOCK["area"] == ptr and bpy.context.region is not None:
            c = unlock_card(bpy.context.region, UNLOCK["at"], UNLOCK["owners"])
            _draw_card(c, f"{title(UNLOCK['owners'])} is locked in place", "Unlock", UNLOCK["hover"])
    except Exception:                                          # noqa: BLE001 – a draw must never raise
        pass


# ---------------------------------------------------------------------------
# the two modals
# ---------------------------------------------------------------------------

PASS = {"MOUSEMOVE", "INBETWEEN_MOUSEMOVE", "MIDDLEMOUSE", "WHEELUPMOUSE", "WHEELDOWNMOUSE", "WHEELINMOUSE",
        "WHEELOUTMOUSE", "TRACKPADPAN", "TRACKPADZOOM", "MOUSEROTATE", "MOUSESMARTZOOM", "TIMER", "TIMER_REPORT",
        "NDOF_MOTION", "WINDOW_DEACTIVATE"}
RUNNING_AGAIN = [False]


def _start_move(context, mode: str, win, area, region) -> None:
    """Starts the move the user asked for, as if the key had worked."""
    with context.temp_override(window=win, screen=win.screen, area=area, region=region):
        if mode == "WINDOW":
            bpy.ops.fresing.place_window("INVOKE_DEFAULT")
            return
        op = bpy.ops.transform.translate if mode == "TRANSLATE" else bpy.ops.transform.rotate
        op("INVOKE_DEFAULT", release_confirm=False)
    names = list(PENDING["start"])
    wptr = win.as_pointer()
    seen = [False]
    t0 = time.time()

    def watch():
        w = next((x for x in bpy.context.window_manager.windows if x.as_pointer() == wptr), None)
        if w is None:
            PENDING["owners"] = []
            return None
        running = any(o.bl_idname.startswith("TRANSFORM_OT") for o in w.modal_operators)
        if running:
            seen[0] = True
            return 0.1
        if not seen[0] and time.time() - t0 < 1.0:
            return 0.05
        after_move(names, any(_moved(n) for n in names))
        return None
    bpy.app.timers.register(watch, first_interval=0.05)


def _moved(name: str) -> bool:
    ob = bpy.data.objects.get(name)
    was = PENDING["start"].get(name)
    if ob is None or was is None:
        return False
    a, b = ob.matrix_world, was
    return any(abs(a[i][j] - b[i][j]) > 1e-7 for i in range(4) for j in range(4))


class FRESING_OT_unlock_popup(bpy.types.Operator):
    """A small popup by the mouse when G / R or Move / turn… is refused because it is locked in place: Unlock unlocks it
    and the move goes on; a click outside, × or Esc closes it and nothing changes"""

    bl_idname = "fresing.unlock_popup"
    bl_label = "Unlock"
    bl_options = {"INTERNAL"}

    owners: StringProperty(options={"SKIP_SAVE", "HIDDEN"})          # names, one per line
    mode: EnumProperty(items=MODES, options={"SKIP_SAVE", "HIDDEN"})
    x: IntProperty(default=-1, options={"SKIP_SAVE", "HIDDEN"})       # window pixels (default: the mouse)
    y: IntProperty(default=-1, options={"SKIP_SAVE", "HIDDEN"})

    @classmethod
    def description(cls, context, properties):
        return UNLOCK_TIP

    def invoke(self, context, event):
        from . import ops_place
        names = [n for n in self.owners.split("\n") if n in bpy.data.objects]
        if not names:
            return {"CANCELLED"}
        area, region, _rv = ops_place._view(context)
        if region is None:
            return {"CANCELLED"}
        mx = self.x if self.x >= 0 else event.mouse_x
        my = self.y if self.y >= 0 else event.mouse_y
        at = (mx - region.x, my - region.y)
        if not (0 <= at[0] <= region.width and 0 <= at[1] <= region.height):
            at = (region.width / 2, region.height / 2)
        self._win, self._area, self._region = context.window, area, region
        UNLOCK.update(on=True, owners=names, mode=self.mode, at=at, area=area.as_pointer(), hover="",
                      gen=UNLOCK["gen"] + 1)
        self._gen = UNLOCK["gen"]
        SHOWN[0] += 1
        _handler(True)
        context.window_manager.modal_handler_add(self)
        area.tag_redraw()
        return {"RUNNING_MODAL"}

    def _card(self):
        try:
            return unlock_card(self._region, UNLOCK["at"], UNLOCK["owners"])
        except ReferenceError:
            return None

    def cancel(self, context):
        if UNLOCK["gen"] == self._gen:
            close("unlock")

    def _go(self, context):
        names = UNLOCK["owners"]
        mode = UNLOCK["mode"] or self.mode
        close("unlock")
        unlock(context, names, mode)
        PENDING.update(area=self._area.as_pointer(), window=self._win.as_pointer())
        try:
            _start_move(context, mode, self._win, self._area, self._region)
        except RuntimeError as exc:
            self.report({"WARNING"}, f"Unlocked, but the move did not start: {exc}")
        return {"FINISHED"}

    def modal(self, context, event):
        if not UNLOCK["on"] or UNLOCK["gen"] != self._gen:
            return {"FINISHED"}
        c = self._card()
        if c is None:
            close("unlock")
            return {"CANCELLED"}
        t, v = event.type, event.value
        try:
            x, y = event.mouse_x - self._region.x, event.mouse_y - self._region.y
            inside_view = context.window == self._win
        except ReferenceError:
            close("unlock")
            return {"CANCELLED"}
        where = hit(c, x, y) if inside_view else ""
        if t in PASS:
            if t == "MOUSEMOVE" and UNLOCK["hover"] != where:
                UNLOCK["hover"] = where
                self._area.tag_redraw()
            return {"PASS_THROUGH"}
        if v != "PRESS":
            return {"RUNNING_MODAL"}
        if t == "ESC":
            close("unlock")
            return {"FINISHED"}
        if t in ("RET", "NUMPAD_ENTER"):
            return self._go(context)
        if t in ("LEFTMOUSE", "RIGHTMOUSE"):
            if t == "LEFTMOUSE" and where == "button":
                return self._go(context)
            if where == "card":
                return {"RUNNING_MODAL"}
            close("unlock")                           # ×, or a click outside: closed, nothing else happens
            return {"FINISHED"}
        return {"RUNNING_MODAL"}                      # other keys: held while it is up (nothing else happens)


class FRESING_OT_lock_again(bpy.types.Operator):
    """The Lock it again popup in the top left of the 3D view after a move of something the unlock popup unlocked:
    Lock it again locks exactly that; × or Esc closes it; after 5 seconds any click closes it too"""

    bl_idname = "fresing.lock_again"
    bl_label = "Lock it again"
    bl_options = {"INTERNAL"}

    @classmethod
    def description(cls, context, properties):
        return AGAIN_TIP

    def invoke(self, context, event):
        if not AGAIN["on"]:
            return {"CANCELLED"}
        if not context.window:
            return {"CANCELLED"}
        self._win = context.window
        RUNNING_AGAIN[0] = True
        context.window_manager.modal_handler_add(self)
        _redraw()
        return {"RUNNING_MODAL"}

    def execute(self, context):                       # scripts and tests: the button alone
        if not AGAIN["on"]:
            return {"CANCELLED"}
        lock_again()
        return {"FINISHED"}

    def cancel(self, context):
        RUNNING_AGAIN[0] = False
        close("again")

    def _end(self):
        RUNNING_AGAIN[0] = False

    def modal(self, context, event):
        if not AGAIN["on"]:
            self._end()
            return {"FINISHED"}
        try:
            same = context.window == self._win
        except ReferenceError:
            self._end()
            close("again")
            return {"CANCELLED"}
        _w, ar, reg = _find(self._win.as_pointer(), AGAIN["area"])
        where = ""
        if same and ar is not None:
            c = again_card(ar, reg, AGAIN["owners"])
            where = hit(c, event.mouse_x - reg.x, event.mouse_y - reg.y)
        t, v = event.type, event.value
        if t == "MOUSEMOVE":
            if AGAIN["hover"] != where:
                AGAIN["hover"] = where
                if ar is not None:
                    ar.tag_redraw()
            return {"PASS_THROUGH"}
        if v != "PRESS":
            return {"PASS_THROUGH"}
        if t == "ESC":
            self._end()
            close("again")
            return {"FINISHED"}
        if t in ("LEFTMOUSE", "RIGHTMOUSE"):
            if t == "LEFTMOUSE" and where == "button":
                self._end()
                lock_again()
                return {"FINISHED"}
            if where == "x":
                self._end()
                close("again")
                return {"FINISHED"}
            if where == "card":
                return {"RUNNING_MODAL"}
            if can_close_by_click():
                self._end()
                close("again")
                return {"FINISHED", "PASS_THROUGH"}   # the click still does its own job
        return {"PASS_THROUGH"}


CLASSES = (FRESING_OT_unlock_popup, FRESING_OT_lock_again)
