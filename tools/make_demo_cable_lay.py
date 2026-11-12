"""Write the invented cable-lay vessel spread (tasks 0076, 0084) as STEP files + two JSON sheets into a folder.

    python tools/make_demo_cable_lay.py <out folder> [--cable-d 200] [--only assembly,quay_loading]

Files (AP214, part names and colours, mm, waterline z = 0, transom at x = 0, x to the bow, y to port):
  demo_cable_lay.step          everything placed, the owner's deck layout (task 0084): vessel, carousel (flat coil
                               layers, the cable end through a hole at the foot of the core) + loading tower with the
                               overhead arch that only slews, side lanes A (starboard) and B (port) of V roller
                               highways with walkways, the lower path beside and below side A, the stern turn under
                               the quadrant's rails, cable engine + tensioner 1 on side B, tensioner 2 on side A
                               (top track lifts and tilts), the D-quadrant on rail bogies at the middle lane's forward
                               end, the quadrant handler at the stern, horns A and B, the quadrant handling winch in
                               front of the carousel, tipping winches with swivel sheaves, two handling winches, the
                               CPS rack with five sets + orange ramp and slide, the static CABLE along the oval
  demo_vessel.step             the vessel alone (about 120 m x 27 m; hull, deck, bulwark, deckhouse, carousel well)
  demo_carousel.step           carousel (Ø24 m) + the loading tower with its arch
  demo_storage_carousel.step   the quay's standalone storage carousel (Ø16 m, on a base frame)
  demo_tensioner.step          one two-track tensioner (36 pads per track, lift + tilt of the top track)
  demo_handling_winch.step     a handling winch: spiral-groove drum, spooled wire, fairlead sheave
  demo_drum_lebus.step         a winch drum with Lebus grooving (two 35° crossovers per turn, risers at the flanges)
  demo_quadrant.step           quadrant system: D-quadrant, rails, handler, handling winch, tipping winches, wires
  demo_quay_loading.step       the quay (vessel moored starboard side to, same coordinates), the storage carousel,
                               the quay tower with its arch, the cable from it onto side A's highway
  demo_cable_route.json        the cable's centrelines (the oval, the end at the core, the CPS slide, the quay
                               route), what they lie on, sheaves, tracks, ropes, quadrant, arch, CPS store, quay
  demo_joints.json             every joint a set-up should make (task 0077 makes them by script)

The model maker ships with the app (task 0077): ``fresing_render/demo_model/`` (``make.py`` is the same command;
``--only assembly,quay_loading`` writes only those files). Nothing of it is a real vessel or a company's design. The files are big (tens of MB): they are made at run time,
not kept in the repository. Needs OpenCascade (OCP), as the other tools/make_test_*.py.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fresing_render.demo_model import make  # noqa: E402


def main(argv=None) -> int:
    return make.main(argv)


if __name__ == "__main__":
    sys.exit(main())
