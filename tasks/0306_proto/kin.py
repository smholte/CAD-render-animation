"""Study 0306 – suspension kinds as the app's planar mechanisms (core/linkages.py, task 0014). No Blender.

Each kind is a mechanism in one plane, with the arm's pivot on the body as the input (a normal joint, as 0014 has
it) and the wheel centre's height as the measure (``linkages.Height``): ``value_for(height)`` gives the arm angle for
a wheel travel, and the other links follow. At Build the ride solve gives each wheel's travel per frame; a table
travel -> arm angle (``table``) makes the arm a *table follower* of a "wheel travel" joint (``joints.set_table``),
so the suspension plays with plain keys and drivers – scripts off.

* DOUBLE_WISHBONE  front view (y, z): body, lower arm, upright, upper arm – a four-bar; input = lower arm pivot.
* MACPHERSON       front view: body, lower arm, upright (+ strut tube), the strut's top mount pins it to the body
                   and the upright slides along the strut; input = lower arm pivot.
* TRAILING_ARM     side view (x, z): body, arm – the arm alone turns; input = its pivot.
* SOLID axle       not a mechanism of one input: heave + roll of the axle = two stacked joints (a slide up and a
                   turn about the vehicle's x), set from the two wheels' travel; a leaf spring's bend = 0300's springs.
* MULTILINK        five links in space – not planar. Proposed: the user picks the wheel carrier and its travel axis;
                   the app moves it along a straight or arc path fitted to its links (camber/toe change ignored).

Out come, per kind: the travel range (both stops), the camber change and track change over the travel (to show the
user that the rig moves like the CAD design), and the table.
"""

from __future__ import annotations

import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for p in (ROOT, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

from fresing_render.core import linkages as LK    # noqa: E402


def double_wishbone(pt: dict):
    """Front view: (y, z) of the hard points; links 0 body, 1 lower arm, 2 upright, 3 upper arm."""
    yz = lambda k: (pt[k][1], pt[k][2])                       # noqa: E731
    lca_in = ((pt["lca_in_f"][1] + pt["lca_in_r"][1]) / 2, (pt["lca_in_f"][2] + pt["lca_in_r"][2]) / 2)
    uca_in = ((pt["uca_in_f"][1] + pt["uca_in_r"][1]) / 2, (pt["uca_in_f"][2] + pt["uca_in_r"][2]) / 2)
    lk = LK.Linkage(["Body", "Lower arm", "Upright", "Upper arm"],
                    pins=[LK.Pin(0, 1, lca_in), LK.Pin(1, 2, yz("lca_out")), LK.Pin(2, 3, yz("uca_out")),
                          LK.Pin(3, 0, uca_in)], input=("pin", 0))
    return lk, 2, yz("wheel"), (yz("lca_out"), yz("uca_out"))


def macpherson(pt: dict):
    """Front view: links 0 body, 1 lower arm, 2 upright (with the strut tube), 3 the strut rod (pinned to the body at
    the top mount); the upright slides along the rod."""
    yz = lambda k: (pt[k][1], pt[k][2])                       # noqa: E731
    lca_in = ((pt["lca_in_f"][1] + pt["lca_in_r"][1]) / 2, (pt["lca_in_f"][2] + pt["lca_in_r"][2]) / 2)
    top = yz("strut_top")
    low = yz("lca_out")
    d = (top[0] - low[0], top[1] - low[1])
    lk = LK.Linkage(["Body", "Lower arm", "Upright", "Strut rod"],
                    pins=[LK.Pin(0, 1, lca_in), LK.Pin(1, 2, low), LK.Pin(3, 0, top)],
                    slides=[LK.Slide(2, 3, top, d)], input=("pin", 0))
    return lk, 2, yz("wheel"), (low, top)


def trailing_arm(pt: dict):
    """Side view: (x, z); links 0 body, 1 arm."""
    xz = lambda k: (pt[k][0], pt[k][2])                       # noqa: E731
    lk = LK.Linkage(["Body", "Arm"], pins=[LK.Pin(0, 1, xz("arm_pivot"))], input=("pin", 0))
    return lk, 1, xz("wheel"), None


KINDS = {"DOUBLE_WISHBONE": double_wishbone, "MACPHERSON": macpherson, "TRAILING_ARM": trailing_arm}


def table(kind: str, pt: dict, travel=(-0.09, 0.09), n: int = 37):
    """Wheel travel -> arm angle (rad), and per row the camber change (deg, + = top outwards) and the wheel centre's
    sideways (front view) or fore-aft (side view) move (mm). Raises linkages.Unreachable when the travel is beyond
    what the mechanism can reach."""
    lk, wl, wheel, kp = KINDS[kind](pt)
    up = (0.0, 1.0)
    meas = LK.Height(wl, wheel, (0.0, wheel[1]), up)
    rows = []
    for tr in np.linspace(travel[0], travel[1], n):
        s = LK.Solver(lk)
        s.reset()
        ang = s.value_for(meas, tr) if abs(tr) > 1e-12 else 0.0
        if abs(tr) <= 1e-12:
            s.solve(0.0)
        poses = s.poses
        w = LK.place(poses[wl], wheel)
        cam = 0.0
        if kp:
            a0 = math.atan2(kp[1][0] - kp[0][0], kp[1][1] - kp[0][1])
            q0, q1 = LK.place(poses[wl], kp[0]), LK.place(poses[wl], kp[1])
            a1 = math.atan2(q1[0] - q0[0], q1[1] - q0[1])
            cam = math.degrees(a1 - a0)         # left wheel (y > 0): + = top of the upright towards +y = outwards
        rows.append((float(tr), float(ang), cam, (w[0] - wheel[0]) * 1000.0))
    return np.array(rows)


if __name__ == "__main__":
    from spec import CAR
    fr = CAR.axles[0].points
    mac = dict(fr)
    mac["strut_top"] = (0.0, 0.62, 0.90)       # an invented MacPherson on the same lower arm
    for kind, pt, tr in (("DOUBLE_WISHBONE", fr, CAR.axles[0].travel), ("MACPHERSON", mac, (-0.09, 0.08)),
                         ("TRAILING_ARM", CAR.axles[1].points, CAR.axles[1].travel)):
        import time
        t0 = time.perf_counter()
        t = table(kind, pt, tr)
        dt = time.perf_counter() - t0
        print(f"{kind}: {len(t)} rows in {dt * 1000:.0f} ms; arm {math.degrees(t[0, 1]):+.1f} .. "
              f"{math.degrees(t[-1, 1]):+.1f} deg; camber {t[0, 2]:+.2f} .. {t[-1, 2]:+.2f} deg; "
              f"wheel moves sideways / fore-aft {t[0, 3]:+.1f} .. {t[-1, 3]:+.1f} mm over the travel")
