"""Drive the CTV with the keyboard (a scripted person), smooth the record into an editable path, and let a tug, a
PSV and the CTV follow drawn paths (study 0312). Writes out/drive.json + pictures in ../../tasks/0312_page/img/."""
import json, math, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from vessels_proto import presets as P, drive as D

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)

# a person drives the CTV: out of the harbour mouth, a long curve to the turbine, slows down, a correction
EV = [(0.5, "press", "UP"), (0.6, "release", "UP")] + [(0.8 + 0.25 * i, "press", "UP") for i in range(6)] + \
     [(0.85 + 0.25 * i, "release", "UP") for i in range(6)] + [
    (14.0, "press", "LEFT"), (19.0, "release", "LEFT"),
    (33.0, "press", "RIGHT"), (36.5, "release", "RIGHT"),
    (44.0, "press", "LEFT"), (45.2, "release", "LEFT"),
    (52.0, "press", "DOWN"), (52.1, "release", "DOWN"), (52.6, "press", "DOWN"), (52.7, "release", "DOWN"),
    (53.2, "press", "DOWN"), (53.3, "release", "DOWN"), (53.8, "press", "DOWN"), (53.9, "release", "DOWN"),
    (58.0, "press", "RIGHT"), (60.0, "release", "RIGHT"),
    (66.0, "press", "SPACE"), (66.1, "release", "SPACE")]

ctv = P.BY_KEY["CTV"]
m = D.Model.of(ctv)
t0 = time.perf_counter()
rec = D.drive(m, EV, 80.0)
t_drive = time.perf_counter() - t0
t0 = time.perf_counter()
ep = D.smooth(rec, ctv.length)
t_smooth = time.perf_counter() - t0
res = {"drive": {"samples": len(rec), "seconds": 80.0, "sim_ms_per_s": t_drive / 80 * 1000,
                 "path_points": len(ep.points), "speed_keys": len(ep.speed_keys), "crab_keys": len(ep.crab_keys),
                 "max_off_m": ep.max_off, "mean_off_m": ep.mean_off, "smooth_ms": t_smooth * 1000,
                 "top_knots": float(rec[:, 4].max() / D.KNOT), "length_m": float(ep.path.length)}}
print("drive", res["drive"])

# drawn paths: an S-bend into a corner (a quay approach) for a tug, a PSV and the CTV
drawn = np.array([(0, 0), (120, 0), (200, 40), (230, 120), (200, 190), (120, 210), (60, 260)], float)
fol = {}
for key, kn in (("TUG", 9), ("PSV", 11), ("CTV", 20)):
    p = P.BY_KEY[key]
    mm = D.Model.of(p)
    t0 = time.perf_counter()
    r, notes, dense = D.follow(mm, drawn, kn)
    fol[key] = {"seconds": float(r[-1, 0]), "notes": notes, "ms": (time.perf_counter() - t0) * 1000,
                "r_min": mm.r_min}
    np.save(os.path.join(OUT, f"follow_{key}.npy"), r)
    print(key, fol[key])
np.save(os.path.join(OUT, "drive_rec.npy"), rec)
np.save(os.path.join(OUT, "drive_points.npy"), ep.points)
np.save(os.path.join(OUT, "drawn.npy"), drawn)
res["follow"] = fol
json.dump(res, open(os.path.join(OUT, "drive.json"), "w"), indent=1)
