"""Study 0306 – the same clicked points as the camera path's curve (Catmull-Rom, C1) and as a C2 spline:
steering angle along the path and the steering-wheel speed it needs at 30 km/h (test car)."""
import os, sys, json, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ride as R
from spec import CAR
clicks = [(0, 0), (12, 0.5), (22, 4), (30, 11), (34, 20), (40, 26), (52, 28), (64, 27)]   # a road with two bends, uneven clicks
out = {}
for curve in ("catmull", "spline"):
    rt = R.Route(clicks, curve=curve)
    d = np.degrees(np.arctan(CAR.wheelbase * rt.kappa))
    ds = np.diff(rt.ss)
    rate = np.abs(np.diff(d)) / ds * (30 / 3.6)            # deg/s of road-wheel angle at 30 km/h
    jump = np.abs(d[2:] - d[:-2]).max()                      # over 10 cm
    out[curve] = dict(max_steer=round(float(np.abs(d).max()), 1), max_rate=round(float(rate.max()), 1),
                      jump_10cm=round(float(jump), 2), length=round(rt.length, 2),
                      steer=np.round(d[::10], 2).tolist(), s=np.round(rt.ss[::10], 2).tolist(),
                      xy=np.round(rt.xy[::10], 3).tolist())
    print(curve, {k: v for k, v in out[curve].items() if k not in ("steer", "s", "xy")})
out["clicks"] = clicks
json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "curves.json"), "w"))
