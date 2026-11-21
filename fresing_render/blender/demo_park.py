"""The demo's wind park (task 0166; task 0247: the demo "Vessel in a wind park"): stages of the demo project
(``demo.py``) that bring in the park round the ship – nine turbines, an offshore substation and the power cable from
turbine A's J-tube down onto the seabed and along it, under the ship (``demo_model/park.py``, its own file and model) –
and its three shots.

**Where the park lies.** Its model root is placed by the route sheet's ``place`` (where the park's origin lies in the
ship's model coordinates: aft of the transom on the centre line, its +x along the ship's): turbine A stands ~130 m aft
of the transom, the cable runs along the seabed right under the ship, its sealed end abeam turbine B 1.2 km on.
Vessel motion puts its own Child Of on every model root; the park is marked **Still** (5 Scene & Render > Vessel motion,
``add_marks``), whose Child Of on the inverse rig takes the vessel's heave, roll and pitch exactly out again.

**Clash check.** The park is left out of the clash check by a tag stored on its model root (``clash.NO_CLASH``, task
0247; kept with the project): its nine turning rotors, whose blade tips move 4 m a frame, would make the check take
several times as long, and the park never comes near the ship (``tests/test_demo_project_park.py`` tests that
directly).

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
SHIFT = "Park: on to turbine B"
BESIDE_A = "Beside turbine A"         # saved cameras
PARK_OVERVIEW = "Park overview"
PARK_NIGHT = "Park at night"
OVERVIEW_SECONDS = 8.0
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
    ("Demo: power cable", "cable_black", "", ("CABLE FIRST END", "CABLE ON THE SEABED", "CABLE END")),
    ("Demo: yellow structure", "paint_marine", "RAL 1003", ("CRANE",)),
    ("Demo: aviation lights", "emission_light", "RAL 3026", ("AVIATION LIGHT",)),
    ("Demo: marine lights", "emission_light", "RAL 1026", ("MARINE LIGHT",)),
    ("Demo: deck lights", "emission_light", "RAL 9016", ("DECK LIGHT",)),
]
# flashing: group -> (period s, on s, strength): together, all of a kind (one driver per material)
FLASH = {"Demo: aviation lights": (2.0, 1.0, 150.0),   # medium-intensity red, ~30 flashes a minute
         "Demo: marine lights": (2.5, 0.5, 80.0)}       # yellow, "Fl Y 2.5s"


KEEP = "fr_park"                      # on the park's model root (how a project finds it)


def root(d: Demo):
    return d.root(PARK)


def park_root(scene):
    """The park's model root in a demo project (None elsewhere)."""
    from . import build
    for r in build.model_roots(scene):
        if r.get(KEEP) is not None:
            return r
    return None


def sheet(d: Demo) -> dict:
    return d.sheet("route")["park"]


def sheet_of(route_json: str) -> dict:
    """The park's numbers from a route sheet file (demo_route.json)."""
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
    """The park root's world matrix: the route sheet's ``place`` (the park's origin in the ship's model mm, its heading
    about z) on the ship's model root as it stands at rest."""
    from mathutils import Matrix, Vector
    pl = d.sheet("route")["place"]
    M = d.root().matrix_world
    o = M @ (Vector(pl["origin"]) / 1000.0)
    turn = M.to_euler("XYZ").z + math.radians(float(pl.get("heading", 0.0)))
    return Matrix.Translation(o) @ Matrix.Rotation(turn, 4, "Z")


def place(d: Demo) -> None:
    """The park in its place, scenery, Still for vessel motion, left out of the clash check (see the docstring)."""
    from . import build, clash, logic, vessel_motion
    sc = d.scene
    r = root(d)
    for ob in [r] + list(logic.descendants(r)):
        ob[build.PROP_SCENERY] = True
    with vessel_motion.at_rest(sc):
        demo._update()
        r.matrix_basis = park_matrix(d)
    clash.leave_out(r)
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
    root(d)[KEEP] = True
    place(d)
    n = joints_(d)
    k = looks(d)
    lights(d)
    d.notes.append(f"park: {len(sheet(d)['turbines'])} turbines + the substation, {k} parts in park groups, "
                   f"{n} joints, Still for vessel motion, left out of the clash check")
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
    """Cameras placed by the park as it stands at the animation's start: beside turbine A and over the park."""
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


@stage("shot_turbine_a", "Shot 2: beside turbine A – the power cable comes down its J-tube", after="shot_fly")
def shot_turbine_a(d: Demo):
    cam = d.scene.objects.get(BESIDE_A)
    a = turbine(d, "A")
    d.camera_step("CUT", d.t, 0.0, "", camera=cam)
    d.camera_step("ORBIT", d.t, 7.0, f"In a wind park: the power cable comes down turbine {a['name']}'s J-tube "
                  "and runs along the seabed to the next turbine", orbit_angle=math.radians(-12.0), easing="SMOOTH")
    d.t += 7.0


@stage("shot_park", "Shot 6: the park from above – the ship among the rows", after="shot_seabed")
def shot_park(d: Demo):
    cam = d.scene.objects.get(PARK_OVERVIEW)
    d.camera_step("CUT", d.t, 0.0, "", camera=cam)
    d.camera_step("ORBIT", d.t, OVERVIEW_SECONDS, f"The wind park: {len(sheet(d)['turbines'])} turbines, the "
                  "substation between the rows", orbit_angle=math.radians(6.0), easing="SMOOTH")
    d.t += OVERVIEW_SECONDS


@stage("shot_night", "Shot 7: the park at night – the lights flash together", after="shot_park")
def shot_night(d: Demo):
    from mathutils import Vector

    from . import weather
    sc = d.scene
    b = turbine(d, "B")
    sc.frame_set(sc.frame_start)
    foot = world_of(d, (b["xy"][0], b["xy"][1], 20000.0))
    eye = foot + Vector((-70.0, -300.0, 35.0))         # 300 m to starboard of B, in front of its rotor
    cam = _cam(d, PARK_NIGHT, eye, foot.lerp(world_of(d, (0.0, 0.0, 0.0)), 0.3) + Vector((0, 0, 55.0)), 24.0)
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
