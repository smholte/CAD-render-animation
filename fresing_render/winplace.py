"""Where an app window sits on the screen – Windows only (task 0260, the output windows of Make).

Blender gives a script no way to move a window or bring it to the front. On Windows the app finds the window's own
handle (HWND) among this process's top-level windows by its client area – the same size and place Blender reports
for it (``Window.width`` / ``height`` / ``x`` / ``y``; Blender counts y from the bottom of the screen) – and asks
Windows directly:

* ``raise_window(win)``  – brings it to the front (restored if it was minimised);
* ``rect(win)``          – its outer rectangle (left, top, right, bottom) in screen pixels;
* ``place(win, rect)``   – moves and sizes it there, only when that rectangle lies on a monitor that is there now.

Every function returns False / None when it is not Windows, when no window or more than one window matches, or when
Windows refuses – nothing else happens then. Nothing here runs at import time; ``ctypes`` is loaded on first use.
"""

from __future__ import annotations

import sys

_API: dict = {}

SWP_NOZORDER, SWP_NOACTIVATE = 0x0004, 0x0010
SW_RESTORE = 9
MONITOR_DEFAULTTONULL = 0
SM_CYVIRTUALSCREEN, SM_YVIRTUALSCREEN = 79, 77
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
    u.MonitorFromRect.argtypes = [ctypes.POINTER(wt.RECT), wt.DWORD]
    u.MonitorFromRect.restype = wt.HANDLE
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


def matches(client, x: int, y: int, w: int, h: int, screen_bottom: int) -> bool:
    """Is this client area (x, y_top, width, height) the Blender window at (x, y counted from the bottom, w, h)?
    Plain numbers, tested without Windows."""
    if client is None:
        return False
    cx, cy, cw, ch = client
    if abs(cw - w) > TOLERANCE or abs(ch - h) > TOLERANCE or abs(cx - x) > TOLERANCE:
        return False
    return abs(cy - y) <= TOLERANCE or abs(cy - (screen_bottom - y - h)) <= TOLERANCE


def find(win) -> int:
    """The HWND of this Blender window (0 when it is not Windows or not exactly one window matches)."""
    if not available():
        return 0
    try:
        from . import appicon
        u = _u()
        bottom = u.GetSystemMetrics(SM_YVIRTUALSCREEN) + u.GetSystemMetrics(SM_CYVIRTUALSCREEN)
        hits = [h for h in appicon.own_windows()
                if matches(_client(h), win.x, win.y, win.width, win.height, bottom)]
    except Exception as exc:  # noqa: BLE001 - a window that cannot be found is left where it is
        print("Fresing Render (window place):", exc)
        return 0
    return hits[0] if len(hits) == 1 else 0


def raise_window(win) -> bool:
    hwnd = find(win)
    if not hwnd:
        return False
    u = _u()
    if u.IsIconic(hwnd):
        u.ShowWindow(hwnd, SW_RESTORE)
    u.BringWindowToTop(hwnd)
    return bool(u.SetForegroundWindow(hwnd))


def rect(win) -> tuple | None:
    hwnd = find(win)
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


def place(win, r) -> bool:
    """Move and size the window to ``r`` = (left, top, right, bottom) – only when that lies on a monitor now."""
    if not usable(r):
        return False
    hwnd = find(win)
    if not hwnd:
        return False
    u = _u()
    ct, wt = _API["ct"], _API["wt"]
    left, top, right, bottom = (int(v) for v in r)
    want = wt.RECT(left, top, right, bottom)
    if not u.MonitorFromRect(ct.byref(want), MONITOR_DEFAULTTONULL):
        return False                          # that monitor is not there any more: Blender's place stays
    return bool(u.SetWindowPos(hwnd, None, left, top, right - left, bottom - top, SWP_NOZORDER | SWP_NOACTIVATE))
