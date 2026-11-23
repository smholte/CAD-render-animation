"""A 20 ft container (half full), a buoy and a pallet of debris float on a moderate sea; the tug drives through
the container (study 0312). Writes out/floaters.json and out/floaters_*.npy."""
import json, math, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from vessels_proto import floaters as F, presets as P, drive as D
from fresing_render.core import sea as sea_core, vessel_work

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
BFT = 4.0
comps = sea_core.components(BFT, 0.0)
print("sea Bft", BFT, "Hs", round(sea_core.hs(comps), 2), "m, peak wavelength", round(sea_core.peak_wavelength(comps), 1))

# still checks: how deep each floats in still water vs. the formula
res = {"sea": {"bft": BFT, "hs": sea_core.hs(comps)}}
still = []
for name, size, mass, cg in (("container 20 ft empty", (6.06, 2.44, 2.59), 2300.0, 0.0),
                         ("container 20 ft, 10 t inside", (6.06, 2.44, 2.59), 12300.0, -0.645),
                         ("container 20 ft, 30 t inside", (6.06, 2.44, 2.59), 32300.0, -0.55),
                         ("container 20 ft, 40 t (sinks)", (6.06, 2.44, 2.59), 40000.0, -0.5),
                         ("pallet 1.2 x 0.8 (wood, 25 kg)", (1.2, 0.8, 0.144), 25.0, 0.0),
                         ("person in a life jacket (lying, as a box)", (1.75, 0.45, 0.25), 85.0, -0.03)):
    f = F.Floater(name, size, mass, np.array([0.0, 0.0, 0.0]), np.zeros(3), cg=cg)
    w = F.World([], [f])
    for _ in range(60 * 40):
        w.step()
    bottom = f.pos[2] - cg - size[2] / 2 if abs(f.R[2, 2]) > 0.9 else float("nan")
    still.append({"what": name, "floats": bool(f.floats), "tilt_deg": float(np.degrees(math.acos(min(1, abs(f.R[2, 2]))))), "formula_draught": f.draught_still() if f.floats else None,
                  "solved_draught": -bottom if f.floats else None, "z_after_40s": float(f.pos[2])})
    print(still[-1])
res["still"] = still

# the scene: the tug follows a straight line at 7 knots through a half-full container; a buoy and a pallet nearby
tug = P.BY_KEY["TUG"]
m = D.Model.of(tug)
track, _, _ = D.follow(m, np.array([(-160.0, -5.5), (200.0, -5.5)]), 7.0, stop_at_end=False, start_speed=7.0)
hull = F.Hull(F.hull_outline(tug.length, tug.beam), tug.draught, track)
box = F.Floater("container", (6.06, 2.44, 2.59), 12300.0, np.array([0.0, 0.0, 0.0]), np.array([0, 0, 0.5]), cg=-0.645)
buoy = F.Floater("buoy", (1.6, 1.6, 2.2), 900.0, np.array([10.0, 14.0, 0.0]), np.zeros(3), cd=0.8)
pal = F.Floater("pallet", (1.2, 0.8, 0.144), 25.0, np.array([20.0, -9.0, 0.0]), np.zeros(3))


def tug_waves(x, y, t, _hull=hull, _kn=7.0):
    """The tug's own Kelvin waves (core/vessel_work) at world points: rocks the floaters it passes."""
    c, psi, _, _ = _hull.at(t)
    rx, ry = x - c[0], y - c[1]
    ca, sa = math.cos(psi), math.sin(psi)
    u = ca * rx + sa * ry
    v = -sa * rx + ca * ry
    xb = _hull_bow - u
    return vessel_work.kelvin(xb, v, _kn)


_hull_bow = tug.length / 2
world = F.World(comps, [box, buoy, pal], [hull], current=(0.2, 0.05), wind=(6.0, 1.0), extra_height=tug_waves)
n = int(60 / F.DT)
rows = []
t0 = time.perf_counter()
for k in range(n):
    world.step()
    if k % 2 == 0:
        rows.append([world.t] + [v for b in world.f for v in (*b.pos, *b.rpy)])
dt = time.perf_counter() - t0
rows = np.array(rows)
np.save(os.path.join(OUT, "floaters.npy"), rows)
np.save(os.path.join(OUT, "floaters_tug.npy"), track)
res["scene"] = {"seconds": 60, "steps": n, "floaters": 3, "ms_per_frame_30fps": dt / 60 / 30 * 1000,
                "ms_per_floater_step": dt / n / 3 * 1000, "hits": world.hits[:6], "n_hits": len(world.hits),
                "container_moved_m": float(np.hypot(*(rows[-1, 1:3] - rows[0, 1:3]))),
                "container_heave_m": float(rows[:, 3].max() - rows[:, 3].min()),
                "container_roll_deg": float(np.degrees(np.abs(rows[:, 4]).max())),
                "pallet_drift_m": float(np.hypot(*(rows[-1, 13:15] - rows[0, 13:15])))}
print(res["scene"])
json.dump(res, open(os.path.join(OUT, "floaters.json"), "w"), indent=1)
