"""The demo's wind park (task 0166): stages of the demo project "Cable-lay vessel" (``demo.py``) that bring in the
park round the vessel – nine turbines and an offshore substation (``demo_model/park.py``, its own file and model) –
and its three shots.

**How the park moves (scripts off, no Python per frame).** The vessel stands still in the scene and the seabed moves
aft under it with the lay: the empty "FR seabed motion" (``paths_sea.BED``), driven by the cable's payout. The park
stands on the seabed, so its model root gets, first in its constraint stack, a Child Of "FR park on the seabed" on
that empty (no inverse: root = seabed's place @ the root's own basis); the basis puts the park's origin on the lay
cable's end on the seabed (``sea_start``) with its +x along the lay line towards the vessel. Vessel motion puts its own
Child Of on every model root; the park is marked **Still** (5 Scene & Render > Vessel motion, ``add_marks``), whose
Child Of on the inverse rig comes right after it and takes the vessel's heave, roll and pitch exactly out again.

**Per shot.** The shots before shot 9 show the first end (turbine A, its cable piece meeting the lay cable on the
seabed); shots 9–12 lay the second end beside turbine B, 1.2 km further. One frame before shot 9's cut, a one-frame
"Move joint" step of the park's slide joint "Park: on to turbine B" takes the park the rest of the way (the payout
stands still in shots 9–12, so B stays beside the vessel); Build re-times it with the animation.

**Clash check.** The parts far from anything that moves are left out of it (``clash.HOOKS``, ``_clash_hook``):
every nacelle with its rotor (they only turn in place, 150 m up: nine turning rotors made the demo's check four to five
times slower – the blade tips move 4 m a frame, so it looks between frames ten times as often), the seven turbines
that never come near the vessel, and the substation. Turbine A's and B's foundations, towers and platforms and A's
cable piece stay in: they pass the vessel, the cable and the D. The rotors' room is checked in
``tests/test_demo_park_model.py`` instead.

**Lights.** The red aviation lights on the nacelles and the yellow marine lights on the platforms and the substation's
corners flash together: one simple-expression driver per group material on its emission strength (``fmod`` of the
time). The substation's deck lights are steady.
"""

from __future__ import annotations

import math
import time

from . import demo
from .demo import Demo, stage

PARK = "park"                         # the model key (demo_model/layout.FILES)
CON = "FR park on the seabed"         # the park root's Child Of on the seabed's motion
SHIFT = "Park: on to turbine B"
BESIDE_A = "Beside turbine A"         # saved cameras
PARK_OVERVIEW = "Park overview"
PARK_NIGHT = "Park at night"
OVERVIEW_LAPSE = 30                   # time-lapse of the overview shot (10 m/min x 30)
OVERVIEW_SECONDS = 8.0
B_X = -8.0                            # m: turbine B's tower axis in shots 9–12, along the vessel (transom = 0)
NIGHT_FADE, NIGHT_HOLD = 4.0, 7.0     # s: the Weather & time step to Night shift, then the lights in the dark

# (group, material, colour, CAD-name prefixes) – a park part takes the longest prefix that matches
LOOKS = [
    ("Demo: turbine white", "paint_marine", "RAL 7035",
     ("TOWER", "NACELLE", "BLADE", "SPINNER", "HELI DECK", "SENSOR", "DOOR", "HANDLE", "CLADDING")),
    ("Demo: foundation yellow", "paint_marine_growth", "RAL 1023",
     ("MONOPILE", "TP SLEEVE", "J-TUBE", "CLAMP", "BOAT LANDING", "JACKET", "PILE SLEEVE", "DAVIT", "CABINET")),
    ("Demo: grating and rails", "galvanized", "", ("GRATING", "RAIL", "LADDER", "PLATFORM BEAM", "STEP", "HOOK")),
    ("Demo: topside grey", "paint_marine", "RAL 7037", ("TOPSIDE",)),
    ("Demo: helideck", "paint_marine", "RAL 6005", ("HELIDECK",)),
    ("Demo: fenders", "rubber_black", "", ("FENDER", "YAW SEAL")),
    ("Demo: scour rock", "concrete", "RAL 7006", ("SCOUR",)),
    ("Demo: steel", "steel_raw", "", ("MAIN SHAFT", "TOWER FLANGE")),
    ("Demo: power cable", "cable_black", "", ("CABLE FIRST END",)),
    ("Demo: yellow structure", "paint_marine", "RAL 1003", ("CRANE",)),
    ("Demo: aviation lights", "emission_light", "RAL 3026", ("AVIATION LIGHT",)),
    ("Demo: marine lights", "emission_light", "RAL 1026", ("MARINE LIGHT",)),
    ("Demo: deck lights", "emission_light", "RAL 9016", ("DECK LIGHT",)),
]
# flashing: group -> (period s, on s, strength): together, all of a kind (one driver per material)
FLASH = {"Demo: aviation lights": (2.0, 1.0, 150.0),   # medium-intensity red, ~30 flashes a minute
         "Demo: marine lights": (2.5, 0.5, 80.0)}       # yellow, "Fl Y 2.5s"


KEEP = "fr_park_clash"                # on the park root: the turbines (and parts) the clash check keeps
KEEP_OUT = ("NACELLE",)               # … but not these subassemblies of theirs (nacelle and rotor)


def root(d: Demo):
    return d.root(PARK)


def park_root(scene):
    """The park's model root in a demo project (None elsewhere)."""
    from . import build
    for r in build.model_roots(scene):
        if r.get(KEEP) is not None:
            return r
    return None


def _clash_hook(scene):
    """(add, leave out) for the clash check: see the module docstring."""
    r = park_root(scene) if demo.is_demo(scene) else None
    if r is None:
        return (), ()
    from . import build, logic
    keep = set(r.get(KEEP))
    leave = []
    for ob in logic.descendants(r):
        if ob.get(build.PROP_KIND) != "part":
            continue
        names = [ob.get(build.PROP_NAME, "")]
        p = build.logical_parent(ob)
        while p is not None and p is not r:
            names.append(p.get(build.PROP_NAME, ""))
            p = build.logical_parent(p)
        if not (keep.intersection(names) and not set(KEEP_OUT).intersection(names)):
            leave.append(ob)
    return (), leave


def _register_hook():
    from . import clash
    if _clash_hook not in clash.HOOKS:
        clash.HOOKS.append(_clash_hook)


_register_hook()


def sheet(d: Demo) -> dict:
    return d.sheet("route")["park"]


def sheet_of(route_json: str) -> dict:
    """The park's numbers from a route sheet file (demo_cable_route.json)."""
    import json
    with open(route_json, encoding="utf-8") as fh:
        return json.load(fh)["park"]


def look_of(name: str) -> str:
    best, n = "", -1
    for group, _mat, _col, prefixes in LOOKS:
        for p in prefixes:
            if name.startswith(p) and len(p) > n:
                best, n = group, len(p)
    return best


def park_matrix(d: Demo):
    """The park root's basis (world = seabed's place @ basis): its origin on the lay cable's end on the seabed (in the
    seabed's coordinates), +x along the lay line towards the vessel (-sea_dir), z 0 at the seabed motion's height
    (the waterline)."""
    from mathutils import Matrix

    from . import paths
    it = paths.find(d.scene, demo.CABLE_ITEM)
    st, u = it.sea_start, it.sea_dir
    a = math.atan2(-float(u[1]), -float(u[0]))
    return Matrix.Translation((float(st[0]), float(st[1]), 0.0)) @ Matrix.Rotation(a, 4, "Z")


def place(d: Demo) -> None:
    """The park on the seabed's motion, its basis, Still for vessel motion (see the module docstring)."""
    from mathutils import Matrix

    from . import build, logic, paths_sea, vessel_motion
    sc = d.scene
    r = root(d)
    for ob in [r] + list(logic.descendants(r)):
        ob[build.PROP_SCENERY] = True
    r.matrix_basis = park_matrix(d)
    bed = paths_sea.bed(sc, create=True)
    con = r.constraints.get(CON)
    if con is None:
        con = r.constraints.new("CHILD_OF")
        con.name = CON
    con.set_inverse_pending = False
    con.target = bed
    con.inverse_matrix = Matrix.Identity(4)
    con.show_expanded = False
    i = list(r.constraints).index(con)
    if i:
        r.constraints.move(i, 0)             # first: vessel motion's pair after it cancels exactly
    vessel_motion.add_marks(sc, [r], "STILL")
    vessel_motion.sync(sc)
    demo._update()


def joints_(d: Demo) -> int:
    """The park's joints from the sheet (its file's own coordinates: placed by the root's matrix)."""
    from . import joints
    js = d.sheet("joints")["machine_files"][sheet(d)["file"]]
    n = demo.make_joints(d, js, PARK, "", cable="")
    joints.refresh_couplings(d.scene)
    return n


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
        if group.startswith("Demo: power cable") or group.startswith("Demo: yellow structure"):
            continue                                   # (the vessel's own groups: as demo.LOOKS made them)
        g.material = mat
        if col:
            g.color = col
    logic.apply_rules(d.scene)
    logic.refresh_group_materials(d.scene)
    return n


def flash_expression(period: float, on: float, strength: float) -> str:
    """Emission strength: ``strength`` for the first ``on`` seconds of every ``period`` (video time), else 0."""
    return f"{strength!r} * (fmod((frame - f0) * b / max(fps, 1), {period!r}) < {on!r})"


def lights(d: Demo) -> list:
    """The flashing lights' drivers (one per group material). Returns the materials."""
    from . import materials
    sc = d.scene
    out = []
    for group, (period, on, strength) in FLASH.items():
        mat = materials.ensure_material(group, "emission_light", next(c for g, _m, c, _p in LOOKS if g == group))
        bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        inp = bsdf.inputs["Emission Strength"]
        path = inp.path_from_id("default_value")
        nt = mat.node_tree
        if nt.animation_data is not None:
            old = nt.animation_data.drivers.find(path)
            if old is not None:
                nt.animation_data.drivers.remove(old)
        fc = nt.driver_add(path)
        drv = fc.driver
        drv.type = "SCRIPTED"
        for name, path_ in (("fps", "render.fps"), ("b", "render.fps_base"), ("f0", "frame_start")):
            v = drv.variables.new()
            v.name, v.type = name, "SINGLE_PROP"
            v.targets[0].id_type = "SCENE"
            v.targets[0].id = sc
            v.targets[0].data_path = path_
        drv.expression = flash_expression(period, on, strength)
        if not drv.is_simple_expression:
            raise RuntimeError(f"the light driver of {group} is not a simple expression")
        out.append(mat)
    return out


def world_of(d: Demo, p_mm):
    """A park point (mm) in the world as the park stands now (the frame shown)."""
    from mathutils import Vector
    return root(d).matrix_world @ (Vector(p_mm) / 1000.0)


def turbine(d: Demo, role: str) -> dict:
    return next(t for t in sheet(d)["turbines"] if t["role"] == role)


@stage(PARK, "The wind park round the vessel: turbines, substation, on the seabed", after="sea")
def park_stage(d: Demo):
    """Import, place, Still, joints, looks, lights. Weather & time goes on here (from the project's own sky, as its
    first switch-on does), before the saved cameras: the animation's start scene keeps it, and the night shot's Weather
    & time step leads from it (Build would otherwise switch it off at the start and on again for the step)."""
    from . import weather
    sc = d.scene
    t0 = time.time()
    w = weather.settings(sc)
    if not w.enabled:
        w.enabled = True
    d.progress("Importing the wind park")
    demo._import(d, PARK)
    d.timings["park import"] = time.time() - t0
    sc.frame_set(sc.frame_start)
    place(d)
    root(d)[KEEP] = [turbine(d, "A")["name"], turbine(d, "B")["name"], "CABLE FIRST END"]
    n = joints_(d)
    k = looks(d)
    lights(d)
    d.notes.append(f"park: {len(sheet(d)['turbines'])} turbines + the substation, {k} parts in park groups, "
                   f"{n} joints, on the seabed's motion (Still for vessel motion)")
    d.timings["park"] = time.time() - t0


def _cam(d: Demo, name: str, at, target, lens: float):
    """A saved camera at ``at`` looking at ``target`` (world, m)."""
    from mathutils import Matrix, Vector

    from . import cameras, states
    cam = cameras.add_camera(d.scene, "ISO", lens, name)
    loc, tgt = Vector(at), Vector(target)
    cam.matrix_world = Matrix.Translation(loc) @ (tgt - loc).to_track_quat("-Z", "Y").to_matrix().to_4x4()
    cam.data.clip_end = max(cam.data.clip_end, 8000.0)
    d.scene.camera = cam
    states.save_shot(d.scene, name)
    return cam


@stage("park_cameras", "Saved cameras of the wind park", after="cameras")
def park_cameras(d: Demo):
    """Cameras placed by the park as it stands at the animation's start (A) and after the shift (B: abeam the stern)."""
    from mathutils import Vector
    sc = d.scene
    sc.frame_set(sc.frame_start)
    demo._update()
    a = turbine(d, "A")
    foot = world_of(d, (a["xy"][0], a["xy"][1], 8000.0))
    vessel = d.mm((40000.0, 0.0, 6000.0))
    # beside turbine A: off its boat landing side, low, looking past its foot to the vessel laying away from it
    side = (foot - vessel).normalized()
    port = Vector((side.y, -side.x, 0.0))              # (side points aft: this is to port, where its boat landing is)
    _cam(d, BESIDE_A, foot + side * 40.0 + port * 45.0 + Vector((0, 0, -2.0)),
         foot.lerp(vessel, 0.15) + Vector((0, 0, 6.0)), 22.0)
    # the park overview: high over the starboard row, looking across the rows to port – the rotors' fronts, the vessel
    # laying in the middle row, the substation and the port row beyond
    _cam(d, PARK_OVERVIEW, d.mm((150000.0, -2250000.0, 520000.0)), d.mm((450000.0, 350000.0, 0.0)), 30.0)
    sc.camera = sc.objects.get("Overview")


def shift_value(d: Demo, t9: float) -> float:
    """m along the park's +x that takes turbine B to ``B_X`` (world x) at ``t9`` (the payout then stands still)."""
    import numpy as np
    from mathutils import Vector

    from . import paths
    it = paths.find(d.scene, demo.CABLE_ITEM)
    u = np.array(it.sea_dir[:2], dtype=float)
    u /= np.linalg.norm(u)
    pay = demo._cable_value_at(d, t9)
    b = turbine(d, "B")
    B = park_matrix(d) @ Vector((b["xy"][0] / 1000.0, b["xy"][1] / 1000.0, 0.0))
    bx = float(B.x + pay * u[0])                        # the seabed has moved payout x the lay direction by then
    return (B_X - bx) / -u[0]                           # (the park's +x is -u)


@stage("park_shift", "The park moves on to turbine B (between shot 8b and shot 9)", after="shot_cps")
def park_shift(d: Demo):
    a = d.animation
    step = 1.0 / float(a.fps)
    L = shift_value(d, d.t)
    d.joint(SHIFT, d.t - step, step, L, slide=True, easing="LINEAR",
            label="")
    d.park_shift = round(L, 3)
    d.notes.append(f"park: on to turbine B by {L:.1f} m one frame before shot 9")


@stage("shot_turbine_a", "Shot 2b: beside turbine A – the cable's first end goes up its J-tube", after="shot_deck")
def shot_turbine_a(d: Demo):
    cam = d.scene.objects.get(BESIDE_A)
    a = turbine(d, "A")
    d.camera_step("CUT", d.t, 0.0, "", camera=cam)
    d.camera_step("ORBIT", d.t, 7.0, f"In a wind park: the cable's first end comes up turbine {a['name']}'s J-tube; "
                  "the vessel lays it on to the next turbine", orbit_angle=math.radians(-12.0), easing="SMOOTH")
    d.t += 7.0


@stage("shot_park", "Shot 8a: the park from above – the vessel lays on through the rows", after="shot_sea")
def shot_park(d: Demo):
    cam = d.scene.objects.get(PARK_OVERVIEW)
    d.camera_step("CUT", d.t, 0.0, "", camera=cam)
    d.camera_step("ORBIT", d.t, OVERVIEW_SECONDS, f"The wind park: {len(sheet(d)['turbines'])} turbines, the "
                  f"substation between the rows (x {OVERVIEW_LAPSE})", orbit_angle=math.radians(6.0), easing="SMOOTH")
    blk = d.animation.blocks.add()
    blk.kind, blk.joint, blk.start, blk.duration, blk.easing = "MOTOR", demo.CABLE, d.t, OVERVIEW_SECONDS, "LINEAR"
    blk.speed_mmin = demo.SPEED * OVERVIEW_LAPSE
    d.t += OVERVIEW_SECONDS


@stage("shot_night", "Shot 13: the park at night – the lights flash together", after="shot_back")
def shot_night(d: Demo):
    from mathutils import Vector

    from . import weather
    sc = d.scene
    b = turbine(d, "B")
    sc.frame_set(sc.frame_start)
    # where B stands in shots 9-12: its place now moved by the shift
    L = getattr(d, "park_shift", 0.0)
    ex = root(d).matrix_world.to_3x3() @ Vector((1.0, 0.0, 0.0))
    foot = world_of(d, (b["xy"][0], b["xy"][1], 20000.0)) + ex * L
    pay = demo._cable_value_at(d, d.t)
    from . import paths
    it = paths.find(sc, demo.CABLE_ITEM)
    foot += Vector((float(it.sea_dir[0]), float(it.sea_dir[1]), 0.0)) * pay
    eye = foot + Vector((-70.0, -300.0, 35.0))         # 300 m to starboard of B, in front of its rotor
    cam = _cam(d, PARK_NIGHT, eye, foot.lerp(d.mm((60000.0, 0.0, 0.0)), 0.3) + Vector((0, 0, 55.0)), 24.0)
    sc.camera = sc.objects.get("Overview")
    d.camera_step("CUT", d.t, 0.0, "", camera=cam)
    blk = d.animation.blocks.add()
    blk.kind, blk.start, blk.duration, blk.easing = "WEATHER", d.t, NIGHT_FADE, "SMOOTH"
    weather.step_from_preset(sc, blk, "NIGHT_SHIFT")
    blk.wx_preset = "NIGHT_SHIFT"
    blk.name = "Night falls: the turbines' red aviation lights and the yellow marine lights flash together"
    d.camera_step("ORBIT", d.t + NIGHT_FADE, NIGHT_HOLD, "", orbit_angle=math.radians(-8.0), easing="SMOOTH")
    d.t += NIGHT_FADE + NIGHT_HOLD


@stage("park_rotors", "The turbines' rotors turn", after="propulsion")
def park_rotors(d: Demo):
    """Every rotor turns through the whole animation (Run motor, rev/min in video time; + = clockwise from the front)."""
    rpm = float(sheet(d)["rpm"])
    for t in sheet(d)["turbines"]:
        blk = d.animation.blocks.add()
        blk.kind, blk.joint, blk.start, blk.duration, blk.easing = "MOTOR", f"{t['name']}: Rotor", 0.0, d.t, "LINEAR"
        blk.speed_rpm = rpm
