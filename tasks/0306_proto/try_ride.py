import sys, os, time, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ground as G, ride as R
from spec import CAR, TRUCK
for kind in ("sine", "short"):
  g = G.speed_bump(G.flat(), 20.0, 0.075 if kind=="sine" else 0.07, 3.7, kind)
  for veh, share in ((CAR, .55), (TRUCK, .35)):
    for v in (15/3.6, 30/3.6, 50/3.6):
        r = R.drive(veh, [(-10,0),(50,0)], g, v, front_share=share, v_start=v, v_end=v)
        print(kind, veh.name, f"{v*3.6:.0f} km/h", "pitch %.2f..%.2f deg" % (np.degrees(r.pitch.min()), np.degrees(r.pitch.max())),
              "heave %.0f..%.0f mm" % (r.body_z.min()*1e3, r.body_z.max()*1e3),
              "travel %.0f..%.0f mm" % (r.travel.min()*1e3, r.travel.max()*1e3), "airborne frames", int(r.airborne.any(0).sum()),
              "| %.2f s for %d frames" % (sum(r.timings.values()), len(r.t)))
