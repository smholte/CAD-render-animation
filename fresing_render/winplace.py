"""Where an app window sits on the screen – Windows only (task 0260, the output windows of Make).

Blender gives a script no way to move a window or bring it to the front. On Windows the app finds the window's own
handle (HWND) among this process's top-level windows by its client area – the same size and place Blender reports
for it (``Window.width`` / ``height`` / ``x`` / ``y``; Blender counts y from the bottom of the screen) – and asks
Windows directly:

* ``raise_window(win)``  – brings it to the front (restored if it was minimised);
* ``rect(win)``          – its outer rectangle (left, top, right, bottom) in screen pixels;
* ``place(win, rect)``   – moves and sizes it there, only when its title bar lands on a monitor that is there now.

The handle is looked for once, when the window is new (``find(win, key)``), and kept per output (``_HWND``): later the
window may be minimised (no client area to compare) or stand on another monitor. A kept handle is checked again
(``IsWindow``, this process) before each use. Blender counts a window's y from the bottom of the desktop; which
desktop height it uses with several monitors is not certain (the main monitor's, the virtual screen's with or without
its top offset), so every one of those readings is accepted (``matches``; independent review, task 0260).

Every function returns False / None when it is not Windows, when no window or more than one window matches, or when
Windows refuses – nothing else happens then. Nothing here runs at import time; ``ctypes`` is loaded on first use.
"""

from __future__ import annotations

import sys

_API: dict = {}

SWP_NOZORDER, SWP_NOACTIVATE = 0x0004, 0x0010
SW_RESTORE = 9
MONITOR_DEFAULTTONULL = 0
SM_CYVIRTUALSCREEN, SM_YVIRTUALSCREEN, SM_CYSCREEN = 79, 77, 1
SWP_NOSIZE, SWP_NOMOVE = 0x0001, 0x0002
TITLE = 15                    # px below a window's top edge: a point of its title bar
INSET = 60                    # px in from its left and right edge
TOLERANCE = 2                 # px: Blender's and Windows' numbers for the same client area may differ by rounding


def available() -> bool:
    return sys.platform == "win32"


def _u():
    """user32 with the argument types set (64-bit handles must not be cut to 32 bits)."""
    if "u" in _API:
        return _API["u"]
    import ctypes
    from ctypes import wintypes as wt
    u = ctypes.WinDLL("user32", use_last_error=True)
    u.GetClientRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
    u.GetClientRect.restype = wt.BOOL
    u.ClientToScreen.argtypes = [wt.HWND, ctypes.POINTER(wt.POINT)]
    u.ClientToScreen.restype = wt.BOOL
    u.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
    u.GetWindowRect.restype = wt.BOOL
    u.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
    u.SetWindowPos.restype = wt.BOOL
    u.SetForegroundWindow.argtypes = [wt.HWND]
    u.SetForegroundWindow.restype = wt.BOOL
    u.BringWindowToTop.argtypes = [wt.HWND]
    u.BringWindowToTop.restype = wt.BOOL
    u.IsIconic.argtypes = [wt.HWND]
    u.IsIconic.restype = wt.BOOL
    u.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]
    u.ShowWindow.restype = wt.BOOL
    u.MonitorFromPoint.argtypes = [wt.POINT, wt.DWORD]
    u.MonitorFromPoint.restype = wt.HANDLE
    u.IsWindow.argtypes = [wt.HWND]
    u.IsWindow.restype = wt.BOOL
    u.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
    u.GetWindowThreadProcessId.restype = wt.DWORD
    u.GetSystemMetrics.argtypes = [ctypes.c_int]
    u.GetSystemMetrics.restype = ctypes.c_int
    _API.update(u=u, ct=ctypes, wt=wt)
    return u


def _client(hwnd) -> tuple | None:
    """(x, y_top, width, height) of a window's client area in screen pixels."""
    u = _u()
    ct, wt = _API["ct"], _API["wt"]
    r = wt.RECT()
    if not u.GetClientRect(hwnd, ct.byref(r)):
        return None
    p = wt.POINT(0, 0)
    if not u.ClientToScreen(hwnd, ct.byref(p)):
        return None
    return p.x, p.y, r.right - r.left, r.bottom - r.top


def matches(client, x: int, y: int, w: int, h: int, bottoms=()) -> bool:
    """Is this client area (x, y_top, width, height) the Blender window at (x, y, w, h)? Blender's y counts from the
    bottom of a desktop height: any of ``bottoms`` (or y counted from the top). Plain numbers, tested without
    Windows."""
    if client is None:
        return False
    cx, cy, cw, ch = client
    if abs(cw - w) > TOLERANCE or abs(ch - h) > TOLERANCE or abs(cx - x) > TOLERANCE:
        return False
    return abs(cy - y) <= TOLERANCE or any(abs(cy - (b - y - h)) <= TOLERANCE for b in bottoms)


def bottoms(cy_virtual: int, y_virtual: int, cy_screen: int) -> tuple:
    """The desktop heights Blender may count y from (see the top of this file)."""
    return tuple(sorted({cy_virtual, y_virtual + cy_virtual, cy_screen}))


_HWND: dict = {}              # output key -> the window's handle (found when the window was new)


def forget() -> None:
    """A project was opened: its windows are new ones."""
    _HWND.clear()


def _alive(hwnd) -> bool:
    if not hwnd:
        return False
    u = _u()
    ct, wt = _API["ct"], _API["wt"]
    if not u.IsWindow(hwnd):
        return False
    pid = wt.DWORD()
    u.GetWindowThreadProcessId(hwnd, ct.byref(pid))
    import os
    return pid.value == os.getpid()


def find(win, key: str = "") -> int:
    """The HWND of this Blender window (0 when it is not Windows or not exactly one window matches). With ``key``
    the handle is kept for that output and used again while the window lives; handles kept for other outputs are not
    taken (two new windows can open at the same place)."""
    if not available():
        return 0
    try:
        if key and _alive(_HWND.get(key)):
            return _HWND[key]
        from . import appicon
        u = _u()
        bs = bottoms(u.GetSystemMetrics(SM_CYVIRTUALSCREEN), u.GetSystemMetrics(SM_YVIRTUALSCREEN),
                     u.GetSystemMetrics(SM_CYSCREEN))
        taken = {h for k, h in _HWND.items() if k != key}
        hits = [h for h in appicon.own_windows()
                if h not in taken and matches(_client(h), win.x, win.y, win.width, win.height, bs)]
    except Exception as exc:  # noqa: BLE001 - a window that cannot be found is left where it is
        print("Fresing Render (window place):", exc)
        return 0
    if len(hits) != 1:
        return 0
    if key:
        _HWND[key] = hits[0]
    return hits[0]


def raise_window(win, key: str = "") -> bool:
    hwnd = find(win, key)
    if not hwnd:
        return False
    u = _u()
    if u.IsIconic(hwnd):
        u.ShowWindow(hwnd, SW_RESTORE)
    u.BringWindowToTop(hwnd)
    return bool(u.SetForegroundWindow(hwnd))


def rect(win, key: str = "") -> tuple | None:
    hwnd = find(win, key)
    if hwnd and _u().IsIconic(hwnd):
        return None                           # minimised: its rectangle says nothing about where it stood
    if not hwnd:
        return None
    u = _u()
    ct, wt = _API["ct"], _API["wt"]
    r = wt.RECT()
    if not u.GetWindowRect(hwnd, ct.byref(r)):
        return None
    return r.left, r.top, r.right, r.bottom


def usable(r) -> bool:
    """A rectangle worth restoring: at least 120 x 80 px and not absurdly large (plain numbers)."""
    try:
        left, top, right, bottom = (int(v) for v in r)
    except (TypeError, ValueError):
        return False
    return 120 <= right - left <= 8000 and 80 <= bottom - top <= 8000


def title_points(r) -> list:
    """Two points of a window's title bar (left and right part): both must lie on a monitor (plain numbers)."""
    left, top, right, _bottom = (int(v) for v in r)
    inset = min(INSET, max(1, (right - left) // 4))
    return [(left + inset, top + TITLE), (right - inset, top + TITLE)]


def place(win, r, key: str = "") -> bool:
    """Move and size the window to ``r`` = (left, top, right, bottom) – only when its title bar lands on a monitor
    that is there now (a window only a few pixels on screen could not be grabbed). It is moved first and sized
    after, so a monitor with another scaling does not make it grow."""
    if not usable(r):
        return False
    hwnd = find(win, key)
    if not hwnd:
        return False
    u = _u()
    wt = _API["wt"]
    left, top, right, bottom = (int(v) for v in r)
    if not all(u.MonitorFromPoint(wt.POINT(x, y), MONITOR_DEFAULTTONULL) for x, y in title_points(r)):
        return False                          # that monitor is not there any more: Blender's place stays
    flags = SWP_NOZORDER | SWP_NOACTIVATE
    ok = u.SetWindowPos(hwnd, None, left, top, 0, 0, flags | SWP_NOSIZE)
    return bool(u.SetWindowPos(hwnd, None, 0, 0, right - left, bottom - top, flags | SWP_NOMOVE) and ok)
