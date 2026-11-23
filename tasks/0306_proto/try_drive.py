"""Study 0306 – a keyboard drive and a controller drive, recorded at an irregular ~60 Hz, turned into paths.

Prints: the number of points per piece, the largest distance between the drive and the editable path, the speed keys,
the time to fit, and how far a replay of the path ends from where the user stopped. Writes drives.json for the page.
"""
import json
import math
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drive as D                       # noqa: E402
import gamepad as GP                    # noqa: E402
import ride as R                        # noqa: E402
from spec import CAR, TRUCK             # noqa: E402

rng = np.random.default_rng(7)


def ticks(T, hz=60.0):
    """Timer ticks as Blender gives them: ~1/60 s with jitter, now and then a hitch (a redraw of a big model)."""
    t, out = 0.0, []
    while t < T:
        dt = 1.0 / hz + rng.normal(0, 0.003)
        if rng.random() < 0.01:
            dt += rng.uniform(0.04, 0.12)
        dt = max(dt, 0.004)
        t += dt
        out.append(dt)
    return out


def keys_script(t):
    """A keyboard drive: off, a left bend, a right bend, a stop, back up into a bay (reverse, steering), forward out."""
    th = br = st = 0.0
    if t < 6.0:
        th = 1.0
    elif t < 9.0:
        th, st = 0.3, 1.0 if t < 7.4 else 0.0
    elif t < 13.0:
        th, st = 0.3, -1.0 if 9.5 < t < 11.2 else 0.0
    elif t < 18.0:
        br = 0.7                                         # stop, then (held) reverse
    elif t < 23.0:
        br, st = 0.5, (1.0 if 18.5 < t < 21.0 else 0.0)  # reversing: brake key = backwards
    elif t < 24.5:
        th = 0.0
    elif t < 31.0:
        th, st = 0.8, (-1.0 if 25.0 < t < 26.2 else 0.0)
    else:
        br = 1.0
    return D.Inputs(throttle=th, brake=br, steer=st)


def pad_script(t):
    """A controller drive: a slow S-bend on the stick with a shaky thumb."""
    steer = 0.55 * math.sin(t * 0.45) + 0.06 * math.sin(t * 7.3) + rng.normal(0, 0.03)
    thr = 0.55 if t < 26 else 0.0
    brk = 0.0 if t < 26 else 0.8
    return GP.State(steer=steer, throttle=thr, brake=brk)


def run(veh, name, script, T, analog):
    d = D.Driver(veh)
    t = 0.0
    for dt in ticks(T):
        t += dt
        if analog:
            s = script(t)
            inp = D.Inputs(throttle=s.throttle, brake=s.brake, steer=D.stick(s.steer), analog=True)
        else:
            inp = script(t)
        d.tick(inp, dt)
    smp = d.array()
    t0 = time.perf_counter()
    pieces = D.to_path(smp, tol=0.05 if veh is CAR else 0.08, r_min=veh.min_radius)
    fit = time.perf_counter() - t0
    res = {"name": name, "vehicle": veh.name, "ticks": len(smp), "seconds": round(float(smp[-1, 0]), 1),
           "fit_s": round(fit, 3), "pieces": []}
    for p in pieces:
        xy, T_rep = D.replay(p)
        end_err = float(np.linalg.norm(xy[-1] - p.points[-1]))
        res["pieces"].append({
            "reverse": bool(p.reverse), "driven_m": round(p.driven_length, 1), "points": len(p.points),
            "max_dev_mm": round(p.max_dev * 1000, 1), "speed_keys": len(p.speed_keys), "wait_s": round(p.wait, 2),
            "replay_s": round(T_rep, 1), "end_mm": round(end_err * 1000, 1),
            "xy_points": np.round(p.points, 3).tolist(),
            "drive": np.round(smp[:, 1:3][::6], 3).tolist() if not res["pieces"] else None,
            "route": np.round(R.Route(p.points, start_dir=p.ends[0], end_dir=p.ends[1]).xy[::5], 3).tolist()})
    r_min = veh.min_radius
    tight = sum(len(R.Route(p.points, start_dir=p.ends[0], end_dir=p.ends[1]).too_tight(r_min * 0.95)) for p in pieces)
    res["too_tight_stretches"] = tight
    print(f"{name}: {len(smp)} ticks over {smp[-1, 0]:.1f} s, fit {fit * 1000:.0f} ms, {len(pieces)} pieces;"
          f" more than 5 % tighter than full lock: {tight} stretches")
    for p in res["pieces"]:
        print(f"   {'reverse' if p['reverse'] else 'forward'} {p['driven_m']} m: {p['points']} points,"
              f" max {p['max_dev_mm']} mm off, {p['speed_keys']} speed keys, waits {p['wait_s']} s")
    return res, smp


if __name__ == "__main__":
    out = []
    for veh, name, script, T, analog in ((CAR, "car, keyboard", keys_script, 33.0, False),
                                         (CAR, "car, controller", pad_script, 30.0, True),
                                         (TRUCK, "truck, keyboard", keys_script, 33.0, False)):
        r, smp = run(veh, name, script, T, analog)
        out.append(r)
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "drives.json"), "w") as f:
        json.dump(out, f)
