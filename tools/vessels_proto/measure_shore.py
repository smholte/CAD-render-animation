import json, math, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import numpy as np
from vessels_proto import shore as S
from fresing_render.core import sea as sea_core
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
res = {}
for bft, tow in ((3.0, 20.0), (5.0, 20.0)):
    comps = sea_core.components(bft, tow)
    sh = S.Shore(comps)
    t0 = time.perf_counter()
    tb = sh.tables()
    t_tab = time.perf_counter() - t0
    xs, Phi, A, KX, foam, q, hs = tb
    surf = xs[foam > 0.05]
    X, Y = np.meshgrid(np.linspace(-200, 0, 400), np.linspace(-50, 50, 200), indexing="ij")
    t0 = time.perf_counter()
    sh.surface(X, Y, 10.0, tb)
    t_s = time.perf_counter() - t0
    res[f"bft{bft:g}"] = {"hs_open": sea_core.hs(comps), "hs_at_h0": float(hs[0]), "surf_zone_m": float(-surf.min()) if len(surf) else 0,
                       "breaks_at_depth_m": float(sh.depth(surf.min())) if len(surf) else 0,
                       "hs_max": float(hs.max()), "x_hs_max": float(xs[np.argmax(hs)]),
                       "flux_spread_outside_surf": S.flux_check(sh), "tables_ms": t_tab * 1000,
                       "points": X.size, "surface_ms": t_s * 1000,
                       "ns_per_point_per_comp": t_s / X.size / len(comps) * 1e9}
    print(bft, res[f"bft{bft:g}"])
json.dump(res, open(os.path.join(OUT, "shore.json"), "w"), indent=1)
