"""Vessel at work (task 0154): what the vessel does – still, ahead, sideways (DP), turning – and what follows from it:
the propellers and the azimuths' steer joints, a wake with the Kelvin wave pattern, a bow wave and hull wash, the
thrusters' white jets.

The setting lives in ``scene.fresing.vessel_work`` (5 Scene & Render > Vessel at work; the speed ahead is the vessel
speed of Weather & time); a **Vessel at work** step in 6 Animation changes it during a video. ``core/vessel_work.py``
turns it into a command per thruster; that command is written as **channels** – the scene's custom properties
``fr_vw_ahead``, ``fr_vw_t<i>`` (load), ``fr_vw_a<i>`` (jet angle) – which a step keys at Build. The sea's materials
read them with View Layer attributes (``water_nodes``, ``hull_nodes``): no drivers, no Python while playing or
rendering, scripts off is fine.

The thrusters' places and kinds are read when the sea is built (``layout``) and baked into the water material as
numbers; the sea is built again when the thruster list changes, or when the vessel first sails or pushes at all
(``sea_key``).

At Build (``bake``) the propellers' joints get keys: the angle is the integral of each propeller's turning rate, one key
per frame while the rate changes and none in between where it is even; an azimuth's steer joint follows its command.
A joint another step moves already is left to that step (a warning says so).
"""

from __future__ import annotations

import json
import math

import bpy
import numpy as np

from ..core import vessel_work as core

STEP_TAG = "fr_vw_step"                 # on the scene: a Vessel at work step was built
LAYOUT_KEY = "fr_vw_layout"             # on the sea object: the layout the water material was built with
WORDS = ("propel", "screw", "schroef", "schraube", "helice", "hélice")


def settings(scene):
    return scene.fresing.vessel_work


def rows(scene) -> list:
    """The thruster rows the effects use (at most ``core.MAX_THRUSTERS``, with a joint)."""
    return [r for r in settings(scene).thrusters if r.joint][:core.MAX_THRUSTERS]


def _speed(scene) -> float:
    w = getattr(scene.fresing, "weather", None)
    return float(w.vessel_speed) if w is not None else 0.0


def setting(scene) -> core.Setting:
    """The panel's setting (the speed ahead: Weather & time's vessel speed)."""
    v = settings(scene)
    return core.Setting(mode=v.mode, speed=_speed(scene), side=v.side, thrust=float(v.thrust))


def block_setting(b) -> core.Setting:
    return core.Setting(mode=b.vw_mode, speed=float(b.vw_speed), side=b.vw_side, thrust=float(b.vw_thrust))


def speed_now(scene) -> float:
    """Knots ahead the panel sets (0 unless Ahead)."""
    st = setting(scene)
    return st.speed if core.effective_mode(st) == "AHEAD" else 0.0


# ---------------------------------------------------------------------------
# the vessel frame and the thrusters' places
# ---------------------------------------------------------------------------

def _bow_sign(scene) -> float:
    from . import surroundings
    return 1.0 if abs(surroundings.bow_az(scene)) < 90.0 else -1.0


def _joint(scene, name):
    return scene.fresing.joints.get(name) if name else None


def _root_xy(scene):
    from . import surroundings
    root = surroundings.root_object()
    if root is None:
        return np.zeros(2)
    return np.array(root.location)[:2]


def layout(scene, outline=None, bow_sign: float | None = None) -> dict:
    """The vessel frame and the thrusters, in the surroundings' frame (the sea object's x, y): ``mid`` the hull's
    middle, ``sign`` +1 when the bow points to +x, ``hl`` / ``hb`` half its length / beam at the waterline, and per
    thruster [kind, u, v] (u to the bow, v to port, m from the middle). ``outline``: the waterline (the sea's build);
    without it the model's box."""
    from . import joints, surroundings
    sign = _bow_sign(scene) if bow_sign is None else float(bow_sign)
    if outline is not None and len(outline) >= 3:
        mn, mx = outline.min(axis=0), outline.max(axis=0)
    else:
        root = surroundings.root_object()
        if root is None or root.get("fr_min") is None:
            mn, mx = np.zeros(2), np.ones(2)
        else:
            mn = np.array(root["fr_min"])[:2] - np.array(root.location)[:2]
            mx = np.array(root["fr_max"])[:2] - np.array(root.location)[:2]
    mid = (np.asarray(mn, float) + np.asarray(mx, float)) / 2
    half = np.maximum((np.asarray(mx, float) - np.asarray(mn, float)) / 2, 0.5)
    origin = _root_xy(scene)
    th = []
    for r in rows(scene):
        j = _joint(scene, r.joint)
        if j is None or j.frame is None:
            continue
        p, _d = joints.axis_world(j)
        x, y = float(p[0] - origin[0] - mid[0]), float(p[1] - origin[1] - mid[1])
        th.append([r.kind, round(sign * x, 3), round(sign * y, 3)])
    return {"mid": [round(float(mid[0]), 3), round(float(mid[1]), 3)], "sign": sign,
            "hl": round(float(half[0]), 3), "hb": round(float(half[1]), 3), "thrusters": th}


def thrusters(scene, lay: dict | None = None) -> list[core.Thruster]:
    lay = lay or stored_layout(scene) or layout(scene)
    return [core.Thruster(k, u, v) for k, u, v in lay["thrusters"]]


def stored_layout(scene) -> dict | None:
    for ob in bpy.data.objects:
        if ob.get("fr_env") == "sea" and ob.get(LAYOUT_KEY):
            try:
                return json.loads(ob[LAYOUT_KEY])
            except ValueError:
                return None
    return None


def _steps(scene):
    for a in scene.fresing.animations:
        for b in a.blocks:
            if b.kind == "VESSEL" and b.enabled:
                yield b


def may_sail(scene) -> bool:
    """The vessel sails ahead somewhere: in the panel or in a step of any animation."""
    if speed_now(scene) > 0.0:
        return True
    return any(core.effective_mode(block_setting(b)) == "AHEAD" for b in _steps(scene))


def may_push(scene) -> bool:
    """A thruster runs somewhere (ahead, sideways or turning)."""
    if core.effective_mode(setting(scene)) != "STILL":
        return True
    return any(core.effective_mode(block_setting(b)) != "STILL" for b in _steps(scene))


def sea_key(scene) -> dict:
    """What of this the sea's build depends on (part of the surroundings' settings key)."""
    out = {}
    if may_sail(scene):
        out["ahead"] = 1
    rs = rows(scene)
    if rs and may_push(scene):
        out["thr"] = [[r.kind, r.joint] for r in rs]
    return out


# ---------------------------------------------------------------------------
# channels
# ---------------------------------------------------------------------------

def _scene_curves(scene) -> list:
    from . import weather
    return weather._scene_curves(scene)


def keyed(scene) -> set:
    out = set()
    for fc in _scene_curves(scene):
        p = fc.data_path
        if p.startswith('["' + core.PREFIX) and p.endswith('"]'):
            out.add(p[2 + len(core.PREFIX):-2])
    return out


def write_channels(scene, ch: dict) -> None:
    """The channels as the scene's custom properties (the keyed ones are left to their keys)."""
    skip = keyed(scene)
    for name, v in ch.items():
        if name in skip:
            continue
        key = core.prop(name)
        if scene.get(key) != float(v):
            scene[key] = float(v)
            try:                     # wide limits: Blender clamps keyed values to a property's min/max
                scene.id_properties_ui(key).update(min=-1.0e6, max=1.0e6)
            except (TypeError, KeyError):
                pass


def command_now(scene, lay: dict | None = None) -> core.Command:
    return core.command(setting(scene), thrusters(scene, lay))


def sync(scene) -> None:
    """The channels follow the panel (the sea's build and every surroundings update call it; cheap)."""
    write_channels(scene, core.channels(command_now(scene)))


def _axis_sign(j) -> float:
    from . import joints
    _p, d = joints.axis_world(j)
    return -1.0 if d[2] < 0.0 else 1.0


def pose(scene) -> int:
    """The azimuths' steer joints turned to the panel's command (the propellers' turn is only seen in a video).
    Returns how many joints moved."""
    from . import joints
    c = command_now(scene)
    moved = 0
    for r, kind, jet in zip(rows(scene), [t.kind for t in thrusters(scene)], c.jets):
        if r.kind != "AZIMUTH" or kind != "AZIMUTH":
            continue
        j = _joint(scene, r.steer)
        if j is None or j.follows:
            continue
        v = core.steer(jet) * _axis_sign(j)
        if abs(joints.get_value(j) - v) > 1e-6:
            joints.set_value(j, v)
            moved += 1
    return moved


def changed(scene, layout: bool = False) -> None:
    """A setting of the panel changed: channels, steer joints, and the sea when what it needs changed."""
    sync(scene)
    if pose(scene):
        try:
            bpy.context.view_layer.update()
        except Exception:
            pass
    from . import surroundings
    s = scene.fresing
    if s.live_update and surroundings.wanted(s):
        surroundings.ensure(scene, s)


# ---------------------------------------------------------------------------
# finding the thrusters
# ---------------------------------------------------------------------------

def _is_propeller(name: str) -> bool:
    n = name.lower()
    return any(w in n for w in WORDS)


def carrier(scene, j):
    """The joint that carries ``j``: the one it rides on in a stack, or the one that moves a part ``j`` sits on."""
    from . import joints
    below = joints.rides_on(scene, j)
    if below is not None:
        return below
    movers = {}
    for o in scene.fresing.joints:
        if o != j:
            for ob in joints.members(o):
                movers.setdefault(ob.name, o)
    ob = j.frame.parent if j.frame is not None else None
    while ob is not None:
        if ob.name in movers:
            return movers[ob.name]
        ob = ob.parent
    return None


def classify(scene, j) -> tuple[str, str]:
    """(kind, steer joint name) of a propeller's joint: riding on a joint that turns about an upright axis = an
    azimuth (that joint steers it); its axis across the vessel = a tunnel; else a shaft."""
    from . import joints
    below = carrier(scene, j)
    if below is not None and below.kind == "ROTATE":
        _p, d = joints.axis_world(below)
        if abs(d[2]) > 0.9:
            return "AZIMUTH", below.name
    _p, d = joints.axis_world(j)
    across = abs(d[1]) if abs(_bow_sign(scene)) > 0 else 0.0     # (the bow is along x: across = y)
    if across > 0.8:
        return "TUNNEL", ""
    return "SHAFT", ""


def find(scene) -> int:
    """Fill the thruster list from the joints whose names say propeller (screw, schroef, Schraube …): kind and steer
    joint read from the joints. Rows already there are kept. Returns how many were added."""
    v = settings(scene)
    have = {r.joint for r in v.thrusters}
    added = 0
    for j in scene.fresing.joints:
        if j.kind != "ROTATE" or j.name in have or not _is_propeller(j.name):
            continue
        if len(v.thrusters) >= core.MAX_THRUSTERS:
            break
        add(scene, j)
        added += 1
    return added


def label_of(name: str) -> str:
    """A short name for a thruster from its joint's name: the part of the path that says thruster or propeller."""
    parts = [p.strip() for p in name.split(":") if p.strip()]
    for p in parts:
        low = p.lower()
        if "thruster" in low or ("propeller" in low and low != "propeller turn"):
            return p
    return parts[-2] if len(parts) > 1 else name


def add(scene, j):
    from . import joints
    v = settings(scene)
    kind, steer = classify(scene, j)
    r = v.thrusters.add()
    r["joint"] = j.name                     # (set without the update: one rebuild after the whole list)
    r["kind"] = core.KINDS.index(kind)
    r["steer"] = steer
    r.name = label_of(j.name)
    if not joints.is_motor(j):
        j.is_motor = True                   # a propeller turns without end
    v.thrusters_index = len(v.thrusters) - 1
    return r


# ---------------------------------------------------------------------------
# animation steps
# ---------------------------------------------------------------------------

def step_label(b) -> str:
    return "Vessel: " + core.words(block_setting(b)).lower()


def step_init(scene, anim, b) -> None:
    """A new step starts from the panel: Still becomes Ahead, anything else Still (a change worth a step)."""
    st = setting(scene)
    if core.effective_mode(st) == "STILL":
        b.vw_mode, b.vw_speed = "AHEAD", st.speed if st.speed > 0 else 8.0
    else:
        b.vw_mode = "STILL"
    b.vw_side, b.vw_thrust = st.side, st.thrust


def state_before(scene, anim, b) -> core.Setting:
    """What the vessel does right before step ``b``: the panel's setting, or the last step that ended before it."""
    st = setting(scene)
    for o in sorted((x for x in anim.blocks if x.enabled and x.kind == "VESSEL"), key=lambda x: x.start):
        if o == b or o.start >= b.start:
            break
        st = block_setting(o)
    return st


def busy_joints(scene) -> set:
    """Joints the vessel's setting moves (propellers, steer joints)."""
    out = set()
    for r in rows(scene):
        out.add(r.joint)
        if r.kind == "AZIMUTH" and r.steer:
            out.add(r.steer)
    return out


def bake(scene, anim, blocks, frame_of, ease, jkeys: dict, jstate: dict, f_end: int, fps: float) -> list[str]:
    """Keys of what the vessel does over the animation: the channels (while a step changes them) and the propellers' and
    steer joints' values (the whole animation, whenever a propeller turns at all). Returns warnings."""
    warnings: list[str] = []
    rs = rows(scene)
    lay = stored_layout(scene) or layout(scene)
    ths = thrusters(scene, lay)
    kinds = [t.kind for t in ths]
    if len(ths) != len(rs):              # (a row whose joint is gone)
        rs = [r for r in rs if _joint(scene, r.joint) is not None][:len(ths)]
    base = setting(scene)
    steps = []
    for b in sorted(blocks, key=lambda x: x.start):
        f0, f1 = frame_of(b.start), frame_of(b.start + b.duration)
        steps.append((b, f0, max(f1, f0 + 1)))
    if not steps and core.effective_mode(base) == "STILL":
        return warnings
    c_base = core.command(base, ths)

    def at(f):
        c = c_base
        for b, f0, f1 in steps:
            if f <= f0:
                continue
            c = core.mix(c, core.command(block_setting(b), ths), ease(b.easing, (f - f0) / (f1 - f0)), kinds)
        return c

    frames = list(range(1, max(f_end, 1) + 1))
    cmds = [at(f) for f in frames]
    # ---- channels: keyed while they change
    if steps:
        from . import animation
        ch_rows = {n: [core.channels(c)[n] for c in cmds] for n in core.CHANNEL_NAMES}
        write_channels(scene, core.channels(c_base))
        cb = None
        for n, vals in ch_rows.items():
            if max(vals) - min(vals) < 1e-9:
                continue
            if n.startswith("a"):
                vals = list(np.unwrap(vals))     # (an angle that goes round keys the short way)
            cb = cb or animation._channelbag(scene, "SCENE")
            keys = [(frames[i], vals[i], "LINEAR", "AUTO") for i in core.thin(vals)]
            keys[-1] = (keys[-1][0], keys[-1][1], "CONSTANT", "AUTO")
            animation._write(cb, f'["{core.prop(n)}"]', 0, keys)
        scene[STEP_TAG] = True
    # ---- joints
    if not rs:
        if steps:
            warnings.append("Vessel at work: no thrusters in 5 Scene & Render > Vessel at work, so no propeller turns "
                            "(Find thrusters)")
        return warnings
    dt = 1.0 / float(fps)
    for i, (r, t) in enumerate(zip(rs, ths)):
        j = _joint(scene, r.joint)
        rates = [core.rate(t.kind, c.loads[i], c.jets[i], r.rpm, r.reverse) for c in cmds]
        if j is not None and not j.follows and max(abs(x) for x in rates) > 0.0:
            if j.name in jkeys:
                warnings.append(f"Vessel at work: '{j.name}' is moved by another step, so the vessel's setting "
                                "leaves it alone")
            else:
                vals = core.turns(rates, dt, jstate.get(j.name, 0.0))
                keys = [(frames[k], float(vals[k]), "LINEAR", "AUTO") for k in core.thin(vals)]
                keys[-1] = (keys[-1][0], keys[-1][1], "CONSTANT", "AUTO")
                jkeys[j.name] = keys
        if t.kind != "AZIMUTH" or not r.steer:
            continue
        sj = _joint(scene, r.steer)
        if sj is None or sj.follows:
            continue
        sign = _axis_sign(sj)
        vals = np.unwrap([core.steer(c.jets[i]) for c in cmds]) * sign
        if max(vals) - min(vals) < 1e-9 and abs(vals[0] - jstate.get(sj.name, 0.0)) < 1e-9:
            continue
        if sj.name in jkeys:
            warnings.append(f"Vessel at work: '{sj.name}' is moved by another step, so the vessel's setting "
                            "leaves it alone")
            continue
        keys = [(frames[k], float(vals[k]), "LINEAR", "AUTO") for k in core.thin(vals)]
        keys[-1] = (keys[-1][0], keys[-1][1], "CONSTANT", "AUTO")
        jkeys[sj.name] = keys
    return warnings


def after_clear(scene) -> None:
    """'Clear keys': the channels and the steer joints go back to the panel's setting."""
    if scene.get(STEP_TAG):
        del scene[STEP_TAG]
        from . import animation
        ad = scene.animation_data
        act = ad.action if ad is not None else None
        if act is not None and act.get(animation.TAG):
            animation._drop_action(scene)    # (as the weather's: a scene action of the user's own comes back)
            if act.users == 0:
                bpy.data.actions.remove(act)
        if scene.get(animation.TAG):
            del scene[animation.TAG]
    sync(scene)
    pose(scene)


# ---------------------------------------------------------------------------
# the header, words
# ---------------------------------------------------------------------------

def header(scene) -> str:
    """The panel header's state, short: "Ahead 8 kn", "Sideways 60%", "Turning 60%", "Still"."""
    st = setting(scene)
    mode = core.effective_mode(st)
    if mode in ("DP", "TURN"):
        return f"{'Sideways' if mode == 'DP' else 'Turning'} {st.thrust * 100:.0f}%"
    return core.words(st)


def words(scene) -> str:
    """One line under the panel's setting: what the water shows."""
    st = setting(scene)
    mode = core.effective_mode(st)
    n = len(rows(scene))
    if mode == "AHEAD":
        lam = core.wavelength(st.speed)
        return (f"A wake behind the stern, waves 19.5° each side, {lam:.1f} m apart; a bow wave"
                + (f"; {n} propeller{'s' if n != 1 else ''} turn" if n else ""))
    if mode in ("DP", "TURN"):
        if not n:
            return "No thrusters yet: Find thrusters below (the jets need them)"
        return f"White water where the thrusters' jets leave the hull; {n} thruster{'s' if n != 1 else ''} run"
    return "Calm water round the hull: no wake, no jets"


# ---------------------------------------------------------------------------
# the sea's nodes (``blender/surroundings.py`` calls these while it writes its materials)
# ---------------------------------------------------------------------------

def _channel(b, name):
    return b.new("ShaderNodeAttribute", attribute_type="VIEW_LAYER",
                 attribute_name=core.prop(name)).outputs["Fac"]


def _smooth(b, x, a, c):
    """smoothstep(a, c, x) (a, c: numbers or sockets)."""
    return b.ramp(x, a, c, 0.0, 1.0, smooth=True)


def speed_socket(b):
    return _channel(b, "ahead")


def _kelvin_nodes(b, u, v, V, hl, dist):
    """``core.kelvin`` in nodes: the height of the wave pattern."""
    xb = b.math("SUBTRACT", hl, u)
    xp = b.math("MAXIMUM", xb, 1e-3)
    ay = b.math("ABSOLUTE", v)
    ta = b.math("DIVIDE", ay, xp)
    disc = b.math("MULTIPLY_ADD", b.math("MULTIPLY", ta, ta), -8.0, 1.0)
    inside = _smooth(b, disc, 0.0, core.KELVIN_EDGE)
    q = b.math("SQRT", b.math("MAXIMUM", disc, 0.0))
    tc = b.math("MAXIMUM", ta, core.TAN_MIN)
    tt = b.math("DIVIDE", b.math("MULTIPLY", tc, 2.0), b.math("ADD", q, 1.0))
    td = b.math("DIVIDE", b.math("ADD", q, 1.0), b.math("MULTIPLY", tc, 4.0))
    vms = b.math("MULTIPLY", V, core.KNOT)
    v2 = b.math("MAXIMUM", b.math("MULTIPLY", vms, vms), 1e-4)
    k0 = b.math("DIVIDE", core.G, v2)

    def phase(t):
        s = b.math("SQRT", b.math("MULTIPLY_ADD", t, t, 1.0))
        return b.math("MULTIPLY", b.math("MULTIPLY", k0, s), b.math("MULTIPLY_ADD", ay, t, xp))
    pt, pd = phase(tt), phase(td)
    lam_t = b.math("DIVIDE", 2 * math.pi, k0)
    lam_d = b.math("DIVIDE", lam_t, b.math("MULTIPLY_ADD", td, td, 1.0))

    def pixel(lam):                       # a wave smaller than about a pixel fades out (as the sea's own waves)
        return b.ramp(dist, b.math("MULTIPLY", lam, 150.0), b.math("MULTIPLY", lam, 400.0), 1.0, 0.0)
    near = b.math("SQRT", b.math("DIVIDE", core.KELVIN_NEAR, b.math("ADD", xp, core.KELVIN_NEAR)))
    far = b.math("EXPONENT", b.math("DIVIDE", b.math("MULTIPLY", xp, -1.0),
                                    b.math("MULTIPLY_ADD", V, core.KELVIN_FADE[1], core.KELVIN_FADE[0])))
    amp = b.math("MINIMUM", b.math("MULTIPLY", v2, core.KELVIN_AMP), core.KELVIN_AMP_MAX)
    wd = b.math("MULTIPLY", _smooth(b, b.math("MULTIPLY", ta, math.sqrt(8.0)), *core.DIVERGENT_FROM),
                core.DIVERGENT)
    waves = b.math("MULTIPLY_ADD", b.math("MULTIPLY", b.math("COSINE", pt), pixel(lam_t)), 1.0 - core.DIVERGENT,
                   b.math("MULTIPLY", b.math("MULTIPLY", b.math("COSINE", pd), pixel(lam_d)), wd))
    h = b.math("MULTIPLY", b.math("MULTIPLY", amp, b.math("MULTIPLY", near, far)), b.math("MULTIPLY", inside, waves))
    on = b.math("MULTIPLY", b.math("GREATER_THAN", xb, 0.0), b.ramp(V, 0.1, 0.6, 0.0, 1.0))
    return b.math("MULTIPLY", h, on)


def _jet_nodes(b, u, v, V, i, tu, tv, hl, hb):
    """``core.jet_at`` in nodes for thruster slot ``i`` at (tu, tv): its foam."""
    load = _channel(b, f"t{i}")
    ang = _channel(b, f"a{i}")
    du, dv = b.math("COSINE", ang), b.math("SINE", ang)

    def reach(h, p, d):
        return b.math("DIVIDE", b.math("SUBTRACT", h, b.math("MULTIPLY", b.math("SIGN", d), p)),
                      b.math("MAXIMUM", b.math("ABSOLUTE", d), core.TAN_MIN))
    r = b.math("MAXIMUM", b.math("MINIMUM", reach(hl, tu, du), reach(hb, tv, dv)), 0.0)
    pu = b.math("SUBTRACT", u, b.math("MULTIPLY_ADD", du, r, tu))
    pv = b.math("SUBTRACT", v, b.math("MULTIPLY_ADD", dv, r, tv))
    s = b.math("MULTIPLY_ADD", pu, du, b.math("MULTIPLY", pv, dv))
    q = b.math("ABSOLUTE", b.math("SUBTRACT", b.math("MULTIPLY", pv, du), b.math("MULTIPLY", pu, dv)))
    a0, a1, a2 = core.JET_LENGTH
    length = b.math("MULTIPLY_ADD", V, a2, b.math("MULTIPLY_ADD", load, a1, a0))
    sp = b.math("MAXIMUM", s, 0.0)
    w = b.math("MULTIPLY_ADD", sp, core.JET_WIDTH[1], core.JET_WIDTH[0])
    along = b.math("MULTIPLY", b.math("EXPONENT", b.math("DIVIDE", b.math("MULTIPLY", sp, -1.0), length)),
                   b.math("SUBTRACT", 1.0, _smooth(b, b.math("MULTIPLY", s, -1.0), 0.0, core.JET_BACK)))
    across = b.math("SUBTRACT", 1.0, _smooth(b, q, b.math("MULTIPLY", w, 0.45), w))
    return b.math("MULTIPLY", b.math("MINIMUM", b.math("MAXIMUM", load, 0.0), 1.0), b.math("MULTIPLY", along, across))


def water_nodes(b, x, y, time, dist, lay: dict):
    """The vessel's water in the sea's shader: (foam of the jets or None, height for a bump or None). ``x``, ``y``:
    the sea object's coordinates; ``lay``: ``layout`` as built."""
    sign, (mx, my) = float(lay["sign"]), lay["mid"]
    hl, hb = float(lay["hl"]), float(lay["hb"])
    u = b.math("MULTIPLY", b.math("SUBTRACT", x, mx), sign)
    v = b.math("MULTIPLY", b.math("SUBTRACT", y, my), sign)
    V = speed_socket(b)
    height, foam = None, None
    if lay.get("ahead"):
        height = _kelvin_nodes(b, u, v, V, hl, dist)
    jets = None
    for i, (_kind, tu, tv) in enumerate(lay.get("thrusters", [])[:core.MAX_THRUSTERS]):
        j = _jet_nodes(b, u, v, V, i, float(tu), float(tv), hl, hb)
        jets = j if jets is None else b.math("MAXIMUM", jets, j)
    if jets is not None:
        boil = b.new("ShaderNodeTexNoise", noise_dimensions="4D")
        boil.inputs["Scale"].default_value = 0.6
        boil.inputs["Detail"].default_value = 3.0
        b.put(boil.inputs["Vector"], b.comb(x, y, 0.0))
        b.put(boil.inputs["W"], b.math("MULTIPLY", time, 0.8))
        heave = b.math("MULTIPLY", b.math("SUBTRACT", boil.outputs["Fac"], 0.5), 2.0 * core.JET_BOIL)
        hj = b.math("MULTIPLY", heave, jets)
        height = hj if height is None else b.math("ADD", height, hj)
        lace = b.new("ShaderNodeTexNoise", noise_dimensions="4D")
        lace.inputs["Scale"].default_value = 0.8
        lace.inputs["Detail"].default_value = 6.0
        lace.inputs["Roughness"].default_value = 0.65
        b.put(lace.inputs["Vector"], b.comb(x, y, 0.0))
        b.put(lace.inputs["W"], b.math("MULTIPLY", time, 0.5))
        foam = b.math("MULTIPLY", b.ramp(jets, 0.0, 0.7, 0.0, 1.0),
                      b.ramp(lace.outputs["Fac"], 0.34, 0.66, 0.08, 1.0))
    return foam, height


def hull_nodes(b, u_attr, k_static):
    """The hull foam's strength and reach with the vessel's speed (``core.bow_wave``): (strength, reach factor)."""
    V = speed_socket(b)
    s = _smooth(b, V, 0.5, 8.0)
    bow = _smooth(b, u_attr, 0.75, 1.0)
    strength = b.math("MAXIMUM", k_static, b.math("MULTIPLY", s, b.math("MULTIPLY_ADD", bow, 0.45, 0.55)))
    reach = b.math("MULTIPLY_ADD", b.math("MULTIPLY", bow, s), core.BOW_REACH, 1.0)
    return strength, reach


def layout_json(lay: dict) -> str:
    return json.dumps(lay, sort_keys=True)


# ---------------------------------------------------------------------------
# the test model (test_thrusters.step, tools/make_test_thrusters.py)
# ---------------------------------------------------------------------------

TEST_JOINTS = ("Azimuth PS: Steer", "Azimuth PS: Propeller turn", "Azimuth SB: Steer", "Azimuth SB: Propeller turn",
               "Bow thruster: Propeller turn")


def set_up_test_model(scene) -> dict:
    """The set-up of the thrusters test model, already imported: the open sea (Simple, Calm, waterline at the model's
    z = 0), the joints (two azimuths: Steer + Propeller turn riding on it; the bow thruster's Propeller turn), the
    thrusters found, the setting Ahead 8 kn. Returns {"joints": names}."""
    from mathutils import Vector

    from . import build, joints

    def uid(u):
        for ob in scene.objects:
            if ob.get(build.PROP_UID) == u:
                return ob
        raise RuntimeError(f"The model has no part '{u}'.")

    t = core.TEST
    root = uid("TEST.THRUSTERS#1")
    m = root.matrix_world
    mm = 0.001

    def at(x, y, z):
        return m @ Vector((x * mm, y * mm, z * mm))

    def d(x, y, z):
        return (m.to_3x3() @ Vector((x, y, z))).normalized()
    with joints._batch(scene):
        for label, side, y in (("Azimuth PS", "PS", t["az_y"]), ("Azimuth SB", "SB", -t["az_y"])):
            base = f"TEST.THRUSTERS#1/AZIMUTH {side}#1/"
            joints.create(scene, "ROTATE", [uid(base + "STEERING UNIT#1")], at(t["az_x"], y, t["bottom"]),
                          d(0, 0, 1), name=f"{label}: Steer")
            joints.create(scene, "ROTATE", [uid(base + "STEERING UNIT#1/PROPELLER#1")],
                          at(t["az_x"] + t["az_prop_x"], y, t["bottom"] + t["az_drop"]), d(-1, 0, 0),
                          name=f"{label}: Propeller turn")
        joints.create(scene, "ROTATE", [uid("TEST.THRUSTERS#1/BOW THRUSTER#1/PROPELLER#1")],
                      at(t["bow_x"], 0.0, t["bow_z"]), d(0, 1, 0), name="Bow thruster: Propeller turn")
    for name in TEST_JOINTS:
        j = joints.find(scene, name)
        j.is_motor = True
    s = scene.fresing
    s.background, s.env_detail, s.sea_state = "SEA", "SIMPLE", "CALM"
    bpy.context.view_layer.update()
    low = min((ob.matrix_world @ Vector(c)).z for ob in build.iter_parts(scene) for c in ob.bound_box)
    s.water_level = float(m.translation.z - low)        # the model's z = 0 is its waterline
    s.weather.vessel_speed = 8.0
    v = settings(scene)
    v.mode = "AHEAD"
    find(scene)
    changed(scene, layout=True)
    return {"joints": list(TEST_JOINTS)}
