"""Write the invented cable-lay vessel spread (task 0076) as STEP files + two JSON sheets into a folder.

    python tools/make_demo_cable_lay.py <out folder> [--cable-d 200] [--no-lebus]

Files (AP214, part names and colours, mm, waterline z = 0, transom at x = 0, x to the bow):
  demo_cable_lay.step          everything placed: vessel + carousel with loading arm + cable route + 2 tensioners +
                               2 handling winches + chute + quadrant system (+ its winches, wires, cable end, CPS)
                               + the static CABLE along the route
  demo_vessel.step             the vessel alone (about 120 m x 27 m; hull, deck, bulwark, deckhouse, carousel well)
  demo_carousel.step           carousel (Ø24 m) + loading tower and slewing arm with the guide sheave
  demo_storage_carousel.step   a smaller standalone storage carousel (quay or deck)
  demo_tensioner.step          one two-track tensioner (48 pads per track, squeeze cylinders)
  demo_handling_winch.step     a handling winch: spiral-groove drum, spooled wire, fairlead sheave
  demo_drum_lebus.step         a winch drum with Lebus-style grooving
  demo_quadrant.step           quadrant + hinge, stern frame, quadrant handling + tipping winches, wires, cable end + CPS
  demo_cable_route.json        the cable's centreline (straights + arcs), what it lies on, sheaves, tracks, ropes
  demo_joints.json             every joint a set-up should make (task 0077 makes them by script)

Nothing of it is a real vessel or a company's design. The files are big (tens of MB): they are made at run time,
not kept in the repository. Needs OpenCascade (OCP), as the other tools/make_test_*.py.
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from demo_cable_lay import layout  # noqa: E402
from demo_cable_lay.params import Params  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("out", help="folder to write into (made if missing)")
    ap.add_argument("--cable-d", type=float, default=200.0, help="cable Ø in mm (50 … 500)")
    a = ap.parse_args(argv)
    t = time.time()
    S = layout.write(a.out, Params(cable_d=a.cable_d))
    print(f"done in {time.time() - t:.0f} s: " + ", ".join(f"{k} {v:.1f} s" for k, v in S.timings.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
