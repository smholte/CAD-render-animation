"""Real-app tests (task 0282): pictures and clicks of a function window – the app's own window that a function's form
opens in (``blender/form_window.py``). Imported by the ``ui_test_*.py`` scripts that open one.
"""

import subprocess


def page(win):
    """(area, region) of the window's page: the 3D view's toolbar region that fills the window."""
    area = next(a for a in win.screen.areas if a.type == "VIEW_3D")
    return area, next(r for r in area.regions if r.type == "TOOLS")


def ready(win) -> bool:
    """The window's page fills it (the app widens the page a moment after the window opened)."""
    try:
        area, reg = page(win)
    except StopIteration:
        return False
    return reg.width > 1 and area.width - reg.width <= 24


def ready_one(windows) -> bool:
    return len(windows) == 1 and ready(windows[0])


def centre(win):
    """A point in the middle of the window (event coordinates of that window)."""
    _area, reg = page(win)
    return reg.x + reg.width // 2, reg.y + reg.height // 2


def title_point(win):
    """A point on the window's title row, right of the title: no button there (a key over a field goes to the field –
    Return would start typing in it, as in a dialog)."""
    _area, reg = page(win)
    import bpy
    scale = bpy.context.preferences.system.ui_scale or 1.0
    return reg.x + int(reg.width * 0.62), reg.y + reg.height - int(16 * scale)


def crop(path, win, dst, trim=True):
    """Cut the window's page out of a root screenshot ``path`` into ``dst`` (down to its last line when ``trim``)."""
    _area, reg = page(win)
    screen_h = int(subprocess.run(["identify", "-format", "%h", path], capture_output=True, text=True).stdout or 1080)
    left = win.x + reg.x
    top = screen_h - (win.y + reg.y + reg.height)
    subprocess.run(["convert", path, "-crop", f"{reg.width}x{reg.height}+{left}+{top}", "+repage", dst], check=False)
    if not trim:
        return dst
    got = subprocess.run(["convert", dst, "-fuzz", "3%", "-trim", "-format", "%h %Y", "info:"],
                         capture_output=True, text=True).stdout.split()
    if len(got) == 2:
        h = min(reg.height, int(got[0]) + int(got[1].split("+")[-1]) + 10)
        subprocess.run(["convert", dst, "-crop", f"{reg.width}x{h}+0+0", "+repage", dst], check=False)
    return dst


def key(win, kind, x=None, y=None):
    """A key pressed with the mouse over the window's title row (Esc closes it, Return is its Make / OK)."""
    if x is None:
        x, y = title_point(win)
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x, y=y)
    win.event_simulate(type=kind, value="PRESS", x=x, y=y)
    win.event_simulate(type=kind, value="RELEASE", x=x, y=y)
