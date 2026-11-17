"""The demo's ROV at the touch-down (task 0173, study 0152 #3): stages of the demo project "Cable-lay vessel"
(``demo.py``) that bring in an invented work-class ROV (``demo_model/rov.py``, its own file and model) watching the
lay cable's touch-down in shot 8, with its tether to the vessel's transom.

**Where it is.** The maker puts the ROV at its station in the vessel's coordinates (``rov.station``): level with the
touch-down (horn A's leave point minus the 32 m layback), 8 m outboard of the cable's line and 2.5 m over the seabed,
looking across at the touch-down (its camera tilted 20° down). The vessel stands still in the scene and the seabed
moves aft under it with the lay, so a ROV that keeps its place in the scene keeps pace with the lay: no joint needs to
move it. Its root's basis is the vessel root's basis @ the station; **5 Scene & Render > Vessel motion** keeps it
**Still** – it does not heave, roll or pitch with the vessel (it flies on its own thrusters).

**Its tether** is a hose of 4 Motion > Hoses and drag chains: the CAD tether (a slack tube from the ROV's bend
restrictor to the transom, 4 m outboard of the cable, 1 m under water) is read as a hose whose ends stay on the
restrictor and on the hull's bottom plate, so it follows the vessel's heave and pitch at every frame (Build solves it
with the other hoses).

**When.** It is shown in shots 1–8b (the lay) and hidden from shot 9 on (the second end is laid elsewhere: the park
moves on to turbine B). Its seven thrusters' propellers turn all the time (Run motor). Its two lights glow (emission),
also in the night shot.

**Clash check.** The ROV and its tether are left out (as the wind park, task 0166): its clearances to the lay cable,
the seabed and the vessel are tested directly (``tests/test_demo_project_rov.py``).
"""

from __future__ import annotations

import math
import time

from . import demo
from .demo import Demo, stage

ROV = "rov"                            # the model key (demo_model/layout.FILES)
KEEP = "fr_rov"                        # on the ROV's model root (what the clash hook looks for)
TETHER = "ROV TETHER"                  # the CAD part, a hose in 4 Motion > Hoses and drag chains
TETHER_ITEM = "ROV tether"
THRUSTER_RPM = 90.0                    # the propellers' turn in the video (rev/min)
LOOKS = [
    # group, material, colour, part names (CAD names, the longest prefix wins)
    ("Demo: ROV frame", "aluminium_machined", "", ("ROV FRAME", "ROV MANIPULATOR")),
    ("Demo: ROV buoyancy", "paint_satin", "RAL 1003", ("ROV BUOYANCY",)),
    ("Demo: ROV dark parts", "plastic_matte", "RAL 9005", ("ROV THRUSTER DUCT", "ROV SKID", "ROV CAMERA",
                                                           "ROV TETHER")),
    ("Demo: ROV orange", "plastic_gloss", "RAL 2004", ("ROV TETHER TERMINATION",)),
    ("Demo: ROV propellers", "bronze", "", ("ROV PROPELLER",)),
    ("Demo: ROV light housings", "stainless_brushed", "", ("ROV LIGHT",)),
    ("Demo: ROV camera glass", "glass_tinted", "", ("ROV CAMERA LENS",)),
    ("Demo: ROV lights", "emission_light", "RAL 9016", ("ROV LIGHT LENS",)),
]


def root(d: Demo):
    return d.root(ROV)


def rov_root(scene):
    """The ROV's model root in a demo project (None elsewhere)."""
    from . import build
    for r in build.model_roots(scene):
        if r.get(KEEP) is not None:
            return r
    return None


def rov_parts(scene) -> list:
    from . import build, logic
    r = rov_root(scene)
    if r is None:
        return []
    return [ob for ob in logic.descendants(r) if ob.get(build.PROP_KIND) == "part"]


def _clash_hook(scene):
    """(add, leave out) for the clash check: the whole ROV with its tether (see the module docstring)."""
    if not demo.is_demo(scene):
        return (), ()
    return (), rov_parts(scene)


def _register_hook():
    from . import clash
    if _clash_hook not in clash.HOOKS:
        clash.HOOKS.append(_clash_hook)


_register_hook()


def sheet(d: Demo) -> dict:
    return d.sheet("route")["rov"]


def look_of(name: str) -> str:
    best, n = "", -1
    for group, _mat, _col, prefixes in LOOKS:
        for p in prefixes:
            if (name == p or name.startswith(p + " ") or name == p) and len(p) > n:
                best, n = group, len(p)
    return best


def station_matrix(d: Demo):
    """The ROV root's basis: the vessel root's basis @ the maker's station (vessel mm -> m)."""
    from mathutils import Matrix
    P = [list(row) for row in sheet(d)["place"]]
    for k in range(3):
        P[k][3] /= 1000.0
    return d.root().matrix_basis @ Matrix(P)


def place(d: Demo) -> None:
    from . import build, logic, vessel_motion
    sc = d.scene
    r = root(d)
    for ob in [r] + list(logic.descendants(r)):
        ob[build.PROP_SCENERY] = True
    r.matrix_basis = station_matrix(d)
    vessel_motion.add_marks(sc, [r], "STILL")
    vessel_motion.sync(sc)
    demo._update()


def looks(d: Demo) -> int:
    from . import build, logic
    n = 0
    for ob in logic.descendants(root(d)):
        if ob.get(build.PROP_KIND) != "part":
            continue
        g = look_of(ob.get(build.PROP_NAME, ""))
        if g:
            ob["fr_group_manual"] = g
            n += 1
    for group, mat, col, _p in LOOKS:
        g = logic.ensure_group(d.s, group)
        g.material = mat
        if col:
            g.color = col
    logic.apply_rules(d.scene)
    logic.refresh_group_materials(d.scene)
    return n


def tether(d: Demo):
    """The CAD tether as a hose whose ends stay on the ROV's bend restrictor and on the transom."""
    from . import build, flex, logic
    sc = d.scene
    part = next(o for o in logic.descendants(root(d)) if o.get(build.PROP_NAME) == TETHER)
    item, notes = flex.add_hose(sc, part)
    item = flex.items(sc)[len(flex.items(sc)) - 1]
    item.name = TETHER_ITEM
    item = flex.find(sc, TETHER_ITEM)
    term = next(o for o in logic.descendants(root(d)) if o.get(build.PROP_NAME) == "ROV TETHER TERMINATION")
    ends = {"A": item.a_part, "B": item.b_part}
    rov_end = "A" if ends["A"] == term else "B" if ends["B"] == term else ""
    if not rov_end:
        raise RuntimeError(f"the ROV's tether does not start at its bend restrictor: {notes}")
    hull = ends["B" if rov_end == "A" else "A"]
    if hull is None or hull.get(build.PROP_NAME) not in ("HULL BOTTOM", "HULL"):
        raise RuntimeError(f"the ROV's tether does not end on the transom (it ends on "
                           f"{hull.get(build.PROP_NAME) if hull is not None else 'nothing'}): {notes}")
    return item


@stage(ROV, "An ROV watches the touch-down: its own model, Still, its tether a hose to the transom", after="park")
def rov_stage(d: Demo):
    sc = d.scene
    t0 = time.time()
    d.progress("Importing the ROV")
    demo._import(d, ROV)
    sc.frame_set(sc.frame_start)
    place(d)
    root(d)[KEEP] = True
    n = demo.make_joints(d, d.sheet("joints")["machine_files"][sheet(d)["file"]], ROV, "", cable="")
    k = looks(d)
    it = tether(d)
    d.notes.append(f"ROV: {k} parts in ROV groups, {n} joints (thrusters), Still for vessel motion; its tether a "
                   f"hose of {it.length:.1f} m from {it.a_part.get('fr_name', it.a_part.name)} to "
                   f"{it.b_part.get('fr_name', it.b_part.name)}")
    d.timings["rov"] = time.time() - t0


@stage("rov_off", "The ROV is hidden from shot 9 on (the second end is laid elsewhere)", after="park_shift")
def rov_off(d: Demo):
    blk = demo._step(d, "HIDE", root(d), d.t, "")
    blk.name = ""


@stage("rov_thrusters", "The ROV's propellers turn", after="park_rotors")
def rov_thrusters(d: Demo):
    for j in d.sheet("joints")["machine_files"][sheet(d)["file"]]:
        blk = d.animation.blocks.add()
        blk.kind, blk.joint, blk.start, blk.duration, blk.easing = "MOTOR", j["name"], 0.0, d.t, "LINEAR"
        blk.speed_rpm = THRUSTER_RPM if j["name"].endswith(("1 turn", "3 turn", "5 turn", "7 turn")) else -THRUSTER_RPM


def clearances(scene) -> dict:
    """Task 0173: at the frame shown, the ROV's (without its tether) nearest distance (m) to the lay cable's drawn
    line (its surface, from the corners and middles of the ROV parts' boxes) and its lowest point (world z)."""
    import numpy as np

    from . import build, paths
    pts = []
    for o in rov_parts(scene):
        if o.get(build.PROP_NAME) == TETHER:
            continue
        m = np.array(o.matrix_world)
        co = np.array([tuple(c) for c in o.bound_box])
        co = np.concatenate([co, co.mean(axis=0, keepdims=True)])
        pts.append(co @ m[:3, :3].T + m[:3, 3])
    P = np.concatenate(pts)
    it = paths.find(scene, demo.CABLE_ITEM)
    line = np.array(paths.shape_now(scene, it), dtype=float)
    d_cable = float(np.min(np.linalg.norm(P[:, None, :] - line[None, :, :], axis=2))) - float(it.diameter) / 2.0
    return {"cable": d_cable, "low": float(P[:, 2].min())}
