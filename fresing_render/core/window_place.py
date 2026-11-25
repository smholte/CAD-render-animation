"""Where an app window opens the first time (0328 row 12, task 0331) – plain numbers, no Blender, no Windows.

Blender opens every app window (the set-up, Settings, a function window, an output window of Make, the Set-up window)
where the piece of the 3D view it was copied from stood: the view's top-left corner, over the left panel and over each
other. The first time a window opens (no place kept from last time, ``ops_make.kept_place``) it goes instead:

* **beside the side panel** – its right edge a little left of the main view's side panel, its top a little under the
  view's top edge (the view's header stays visible);
* **over the middle of the view** when it does not fit between the left panel and the side panel;
* **the next one offset** by ``STEP`` px (left and down, so it never slides over the side panel) for every other app
  window already open, starting again after ``CYCLE``.

All rectangles are in Blender's window coordinates: x from the left, y from the BOTTOM of the desktop (``Window.x``,
``Window.y``; an area's ``x`` / ``y`` added to its window's). ``first_place`` gives the top-left corner of the new
window's inside (its client area); ``moved`` turns that into the outer rectangle Windows moves (``winplace.place``).
"""

from __future__ import annotations

STEP = 30          # px at UI scale 1 between two windows opened one after the other
CYCLE = 6          # … the seventh starts at the first place again
MARGIN = 12        # px left free beside the side panel / the left panel
TOP = 36           # px under the view's top edge: its header stays visible


def first_place(view, size, side: int = 0, left: int = 0, n: int = 0, scale: float = 1.0) -> tuple:
    """(x, top) of the new window's client area. ``view`` = (x, y, width, height) of the main 3D view (y = its
    bottom), ``size`` = (width, height) of the new window, ``side`` / ``left`` = the widths of the view's side panel
    and left panel (0 when closed), ``n`` = how many app windows are open already."""
    vx, vy, vw, vh = (int(v) for v in view)
    w, h = (int(v) for v in size)
    k = int(n) % CYCLE
    step, margin, top_gap = int(STEP * scale), int(MARGIN * scale), int(TOP * scale)
    lo = vx + int(left) + margin                      # the window's left edge may not cover the left panel
    hi = vx + vw - int(side) - margin                 # … nor its right edge the side panel
    if hi - lo >= w + step * k:
        x = hi - w - step * k
    else:                                             # no room beside the side panel: over the view's middle
        x = vx + (vw - w) // 2 + step * k
        x = min(x, vx + vw - w)
        x = max(x, vx)
    top = vy + vh - top_gap - step * k
    if top - h < vy:                                  # it would hang below the view: as low as it goes
        top = min(vy + vh, vy + h)
    return x, top


def moved(outer, win, x: int, top: int) -> tuple:
    """The outer rectangle (left, top, right, bottom; Windows' screen pixels, y from the top) that puts the client
    area's top-left at Blender's (``x``, ``top``). ``outer`` = the window's outer rectangle now, ``win`` = Blender's
    numbers for its client area now (x, y, width, height; y from the bottom). Blender's and the screen's pixels are
    the same size: only the direction of y differs."""
    left, otop, right, bottom = (int(v) for v in outer)
    bx, by, _bw, bh = (int(v) for v in win)
    dx = int(x) - bx                                  # Blender's x and the screen's x run the same way
    dy = (by + bh) - int(top)                         # Blender's y runs up, the screen's down
    return left + dx, otop + dy, right + dx, bottom + dy
