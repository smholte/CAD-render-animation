"""The demo's files (task 0247: "Vessel in a wind park"): the ship, the wind park and the quay, each a STEP file of
its own, and two sheets.

``build(params)`` makes the scene (no files); ``write(out_dir, params)`` writes the STEP files and the two JSON sheets.
Model coordinates: mm, x to the bow (transom at 0), y to port, z up (waterline 0).

- ``demo_vessel.step``: the ship (``vessel.py``) – hull, superstructure, thrusters, lifeboats, its own deck crane with
  its hoist – under the root "DEMO VESSEL";
- ``demo_park.step``: the wind park (``park.py``) in its own coordinates, with the power cable from turbine A's J-tube
  down onto the seabed and along it;
- ``demo_quay.step``: the quay the ship moors at (starboard side to);
- ``demo_route.json``: where the park lies under the ship (``place``), its numbers, the quay's;
- ``demo_joints.json``: every joint a set-up should make – the ship's (thrusters, propellers, radars, the crane's slew,
  luff, hoist drum, head sheave and hook) and the park's (in its own file's coordinates).
"""

from __future__ import annotations

import json
import os
import time

import numpy as np

from . import deck as dk
from . import geom as g
from . import park as pk
from . import vessel as vs
from .geom import Asm
from .params import ParkParams, ShipParams

ROOT = "DEMO VESSEL"
FILES = {
    "assembly": "demo_vessel.step",     # the ship (the demo's main model)
    "park": "demo_park.step",           # task 0166: the wind park round the ship (park.py), its own model in the demo
    "quay": "demo_quay.step",           # the quay of the scene "At the quay"
}
MACHINE_FILES = ("park", "quay")        # files whose joints the sheet also gives in their own coordinates
ROUTE_JSON = "demo_route.json"
JOINTS_JSON = "demo_joints.json"

# where the park lies (model mm): its origin (where the cable from turbine A's J-tube meets the seabed) this far aft of
# the transom on the centre line, its +x along the ship's +x. Turbine A then stands ~130 m aft of the transom, so its
# rotor (120 m blades, its plane along the cable) never reaches over the ship.
PARK_X = -105000.0
PARK_Y = 0.0
QUAY_EDGE = 1500.0                       # the quay's edge this far off the ship's starboard side
QUAY_ABOVE = 500.0                       # its top this far above the ship's deck


def _r(v, n=4):
    return [round(float(x), n) for x in v]


class Scene:
    """The built model: the files' root assemblies and the numbers the sheets give."""

    def __init__(self, p: ShipParams):
        self.p = p
        self.files: dict = {}            # key -> root Asm
        self.info: dict = {}
        self.timings: dict = {}
        self.root = None


def quay_positions(p) -> dict:
    """The quay (model coordinates, the ship moored starboard side to)."""
    return {"edge_y": -(p.beam / 2.0 + QUAY_EDGE), "z": p.deck_z + QUAY_ABOVE}


def build(p: ShipParams | None = None, with_park: bool = True, with_quay: bool = True) -> Scene:
    """The ship (always), the park and the quay."""
    p = p or ShipParams()
    S = Scene(p)
    t0 = time.time()
    root = Asm(ROOT)
    ves = vs.vessel(p)
    root.add(ves, instance="VESSEL")
    S.info["vessel"] = ves.info
    S.files["assembly"] = S.root = root
    S.timings["vessel"] = time.time() - t0
    if with_park:
        t = time.time()
        S.files["park"], S.info["park"] = pk.build(p, ParkParams())
        S.timings["park"] = time.time() - t
    if with_quay:
        q = quay_positions(p)
        a = Asm("DEMO QUAY")
        a.add(dk.quay(-30000.0, 140000.0, q["edge_y"], 30000.0, q["z"]), np.eye(4), "QUAY")
        S.files["quay"] = a
        S.info["quay"] = q
    S.timings["total"] = time.time() - t0
    return S


def _clean(v):
    """NumPy arrays as lists, mm rounded to 0.1 µm."""
    if isinstance(v, dict):
        return {k: _clean(x) for k, x in v.items()}
    if isinstance(v, (list, tuple, np.ndarray)):
        return [_clean(x) for x in v]
    if isinstance(v, (float, np.floating)):
        return round(float(v), 4)
    return v


def _park_sheet(info: dict) -> dict:
    """The park's numbers as JSON (kept for the old name)."""
    return _clean(info)


def route_sheet(S: Scene) -> dict:
    p, vi = S.p, S.info["vessel"]
    q = S.info.get("quay")
    return {
        "about": "task 0247: the demo 'Vessel in a wind park' – model coordinates (mm) of demo_vessel.step: x to the "
                 "bow (transom 0), y to port, z up (waterline 0). place: where the park's origin lies under the ship "
                 "(the park file's own coordinates: origin where the cable from turbine A meets the seabed, +x along "
                 "the cable, which lies on along the seabed under the ship). park: its numbers (park mm).",
        "units": {"length": "mm", "angle": "deg"},
        "cable": {"d": p.cable_d, "mbr": p.mbr, "bend_r": p.bend_r},
        "vessel": {"file": FILES["assembly"], "length": p.length, "beam": p.beam, "deck_z": p.deck_z,
                   "keel_z": p.keel_z, "thrusters": _clean([{k: v for k, v in t.items() if k != "path"}
                                                             for t in vi["thrusters"]]),
                   "boards": _clean(vi["boards"]), "crane": _clean(vi["crane"]),
                   "sheer_from": vi["sheer_from"]},
        "place": {"origin": [PARK_X, PARK_Y, 0.0], "heading": 0.0},
        "quay": ({"file": FILES["quay"], "edge_y": q["edge_y"], "top_z": q["z"], "moored": "starboard side to the quay"}
                 if q else None),
        "park": _park_sheet(S.info["park"]) if "park" in S.info else None,
    }


def joint_sheet(S: Scene) -> dict:
    joints = g.resolve_joints(S.root)
    machines = {}
    for key in MACHINE_FILES:
        if key in S.files:
            machines[FILES[key]] = g.resolve_joints(S.files[key])
    return {
        "about": "Every joint a set-up should make (task 0247: the ship's own – thrusters, propellers, radars, the deck "
                 "crane – and the park's). Axis point and direction in model coordinates (mm) of demo_vessel.step; "
                 "parts are the importer's uids (the node path NAME#n/…). A rotate joint turns the parts right-handed "
                 "about the axis direction (degrees), a slide joint moves them along it (mm); 0 = as modelled. "
                 "drive.by: 'operator' / 'winch' = driven on its own. rides_on: the joint whose parts carry this "
                 "joint's axis (a stacked joint). machine_files: the joints of the other files in their own "
                 "coordinates.",
        "units": {"length": "mm", "angle": "deg"},
        "model": FILES["assembly"],
        "joints": joints,
        "machine_files": machines,
    }


def write(out_dir: str, p: ShipParams | None = None, log=print, only: tuple = (), progress=None) -> Scene:
    """Write the files (``only``: these keys of FILES – the ship always –, else all) and the two sheets.
    ``progress(done, total)`` is called before each file (the app's demo project shows "Writing the model 2/3")."""
    os.makedirs(out_dir, exist_ok=True)
    S = build(p, with_park=not only or "park" in only, with_quay=not only or "quay" in only)
    keys = [k for k in FILES if k in S.files and (not only or k in only or k == "assembly")]
    for i, key in enumerate(keys):
        fname = FILES[key]
        if progress:
            progress(i, len(keys))
        t = time.time()
        g.write_step(S.files[key], os.path.join(out_dir, fname))
        S.timings["write " + fname] = time.time() - t
        log(f"{fname}: {os.path.getsize(os.path.join(out_dir, fname)) / 1e6:.2f} MB, "
            f"{g.count_parts(S.files[key])} placed parts")
    with open(os.path.join(out_dir, ROUTE_JSON), "w", encoding="utf-8") as fh:
        json.dump(route_sheet(S), fh, indent=1)
    with open(os.path.join(out_dir, JOINTS_JSON), "w", encoding="utf-8") as fh:
        json.dump(joint_sheet(S), fh, indent=1)
    log(f"{ROUTE_JSON}, {JOINTS_JSON}: written")
    return S
