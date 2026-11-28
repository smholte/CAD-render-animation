"""The lift path and the checks along it (task 0348, Lifting lane L6a): 8 Lifting plan > Lift path & checks.

* **Propose**: the pick is where the load hangs now; the set-down point is clicked (or typed). ``core/lifting_path``
  works out the steps – hoist clear, slew, luff / telescope, travel (a crawler that cannot reach otherwise), lower –
  and they become ordinary "Move joint" steps of an animation "Lift <load>" (6 Animation): the user can change them,
  drag their keys in the timeline (0330 keeps them) or use any animation of their own (poses, steps) instead.
* **Check along the path**: Build, then the crane's driven joints are read from their keys (no frame is set) and every
  check is worked out at the keys and searched between them for its worst moment (``core/lifting_path.search``). The
  result (one row per check: worst value, limit, use, status, frame) is kept on the plan as JSON; Go there shows that
  frame. The rows go out of date when the path, the load, the crane's set-up or the ground change (``stale``).
* **Live**: the current pose's rows (``live_rows``), cached on the readout's key and worked out at most ``LIVE_EVERY``
  seconds apart while a joint or the load is dragged (the drag itself does no work for the plan); a use-% bar beside
  the hook (POST_PIXEL, drawn where the Lifting plan shows, never in a camera's picture).
* **Lift data box**: one tick puts a label with live fields on the hook block (``core/callouts`` ``load``, ``radius``,
  ``use``, ``worst``); labels are drawn frame by frame in renders and videos (0173's lay-data label).
"""

from __future__ import annotations

import json
import math
import time

import bpy
import numpy as np
from mathutils import Vector

from ..core import lifting as core
from ..core import lifting_path as P
from . import joints, lifting

PREFIX = "Lift · "                   # the steps Propose writes (their names)
LIVE_EVERY = 0.2                     # s: the pose looked at (and the rows worked out) at most this often
DATA_BOX = "Lift data\nLoad {load} t\nRadius {radius} m\nCrane use {use} %\nWorst so far: {worst}"
DATA_TAG = "fr_lift_data_box"        # on the label's part (the hook block): the crane's name
FIELDS = ("load", "radius", "use", "worst", "hook")


# ---------------------------------------------------------------------------------------------------------------------
# the plan's numbers for the checks

def _crane_and_load(scene, crane=None, load=None):
    crane = crane if crane is not None else lifting.active_crane(scene)
    load = load if load is not None else lifting.active_load(scene)
    return crane, load


def numbers(scene, crane, load, clearance: bool = True) -> P.Plan:
    """The plan's numbers for ``core/lifting_path.Checks`` (SI)."""
    from . import lifting_rig as RG
    L = lifting.plan(scene)
    m = lifting.load_mass(scene, load)[0] if load is not None else 0.0
    hung = bool(load is not None and load.rig_state == "HUNG" and load.hung_on == crane.name)
    r = RG.result(load) if hung else None
    mat = tuple(L.mat_size) if min(L.mat_size) > 0 else None
    return P.Plan(load_kg=m, contingency=float(load.contingency) if load is not None else 1.0,
                  hook_block_kg=lifting.hook_block_kg(crane),
                  rigging_kg=RG.rigging_mass(load) if load is not None else 0.0,
                  counterweight_kg=core.kg(crane.counterweight),
                  spread=None if crane.spread_from_pose else float(crane.outriggers),
                  hung=hung, rig_checks=(r or {}).get("checks", []), rig_stale=bool(hung and RG.stale(scene, load)),
                  allowable_pa=L.allowable_kpa * 1000.0 if L.allowable_kpa > 0 else None, mat=mat,
                  line_pull=lambda g, s=scene, c=crane: lifting.line_pull(s, c, g),
                  clearance=_clearance(scene, crane, load) if clearance else None)


def _clearance(scene, crane, load):
    """The clearance row's function (task 0349), or None when it cannot be made (then the row is grey)."""
    from . import lifting_zones
    try:
        return lifting_zones.row_function(scene, crane, load)
    except Exception as exc:  # noqa: BLE001 - a part without a mesh, a crane being set up
        msg = str(exc).rstrip(".").lower()
        return lambda values: P.grey("CLR", msg)


def _plan_key(scene, crane, load) -> tuple:
    L = lifting.plan(scene)
    rk = None
    if load is not None:
        rk = (load.rig_state, load.hung_on, load.rig_result)
    from . import lifting_zones
    return (round(L.allowable_kpa, 6), tuple(round(x, 6) for x in L.mat_size), rk,
            lifting_zones.fingerprint(scene, crane, load))


_CHECKS: dict = {}


def checks(scene, crane, load, clearance: bool = True) -> P.Checks:
    """The crane's checks (its rig and charts read once per key); ``clearance`` False: without the clearance row (the
    live rows add it themselves when the pose stands still)."""
    key = (crane.name, lifting.path_of(crane), lifting._mtime(lifting.item_at(lifting.path_of(crane)).path or ""),
           lifting._key(scene, crane, load)[3:], _plan_key(scene, crane, load), clearance)
    got = _CHECKS.get((crane.name, clearance))
    if got is not None and got[0] == key:
        return got[1]
    c = P.Checks(lifting.item_at(lifting.path_of(crane)).data, lifting.charts_of(crane),
                 numbers(scene, crane, load, clearance))
    _CHECKS[(crane.name, clearance)] = (key, c)
    return c


# ---------------------------------------------------------------------------------------------------------------------
# live: the pose shown now

_LIVE: dict = {"key": None, "rows": None, "at": 0.0, "timer": False, "count": 0}


def _live_key(scene, crane, load):
    return (lifting._key(scene, crane, load), _plan_key(scene, crane, load))


def live_rows(scene, crane=None, load=None, force: bool = False):
    """The checks at the pose shown now: [Row], or a sentence why there are none. A redraw costs next to nothing:
    the pose is looked at (``_live_key``) at most every ``LIVE_EVERY`` s – between, the last rows are given and one
    redraw is asked for when the time is up – and the rows are worked out again only when it changed. ``force``: look
    now (tests, the data box, a render)."""
    crane, load = _crane_and_load(scene, crane, load)
    if crane is None:
        return "No crane yet: place one under Equipment."
    now = time.perf_counter()
    if not force and _LIVE["rows"] is not None and now - _LIVE["at"] < LIVE_EVERY:
        _later()
        return _LIVE["rows"]
    if load is not None and load.kind == "PARTS" and not any(r.obj is not None for r in load.parts):
        return lifting.NO_PARTS.format(name=load.name)
    try:
        key = _live_key(scene, crane, load)
    except Exception as exc:  # noqa: BLE001
        return str(exc)
    _LIVE["at"] = now
    if _LIVE["key"] == key and _LIVE["rows"] is not None:
        return _LIVE["rows"]
    try:
        lifting.check_joints(scene, crane)
        rows = checks(scene, crane, load, clearance=False).at(lifting.values(scene, crane))
        from . import lifting_zones                  # task 0349: once the pose stands still
        rows.append(lifting_zones.live_row(scene, crane, load, key, force=force))
        rows = P.ordered({r.id: r for r in rows})
    except lifting.LR.ReachError as exc:
        rows = str(exc)
    _LIVE.update(key=key, rows=rows, at=time.perf_counter(), count=_LIVE["count"] + 1)
    return rows


def _later() -> None:
    if _LIVE["timer"] or bpy.app.background:
        return
    _LIVE["timer"] = True

    def tick():
        _LIVE["timer"] = False
        _redraw()
        return None
    bpy.app.timers.register(tick, first_interval=LIVE_EVERY)


def _redraw() -> None:
    try:
        for win in bpy.context.window_manager.windows:
            for area in win.screen.areas:
                if area.type == "VIEW_3D":
                    area.tag_redraw()
    except Exception:  # noqa: BLE001
        pass


def forget() -> None:
    _LIVE.update(key=None, rows=None, at=0.0)
    _CHECKS.clear()


def forget_live() -> None:
    """Only the live rows (the next look works them out again)."""
    _LIVE.update(key=None, rows=None, at=0.0)


# ---------------------------------------------------------------------------------------------------------------------
# propose the steps

def load_bottom(load) -> float | None:
    """The lowest point of the load (world z, m)."""
    lows = []
    for ob in lifting.load_parts(load):
        M = ob.matrix_world
        lows += [(M @ Vector(c)).z for c in ob.bound_box]
    return min(lows) if lows else None


def hook_target(scene, crane, load, point) -> np.ndarray:
    """Where the hook must end for the load to stand on ``point`` (world, m): the load hangs plumb under the hook, so
    the hook ends above the point by as far as it is above the load's bottom now. Without a hung load: the point."""
    p = np.asarray(point, float)
    if load is None or load.rig_state != "HUNG" or load.hung_on != crane.name:
        return p
    bottom = load_bottom(load)
    if bottom is None:
        return p
    hook = lifting.hook_world(scene, crane)
    return p + np.array([0.0, 0.0, float(hook[2]) - bottom])


def set_point(scene, point) -> None:
    L = lifting.plan(scene)
    L.set_down = tuple(float(x) for x in point)
    L.has_set_down = True


def _anim_named(scene, name: str):
    return scene.fresing.animations.get(name) if name else None


def path_anim(scene):
    """The animation the checks go along (None: none chosen, or it was deleted)."""
    return _anim_named(scene, lifting.plan(scene).path_anim)


def is_proposed(anim) -> bool:
    return anim is not None and len(anim.blocks) > 0 and all(b.name.startswith(PREFIX) for b in anim.blocks)


def propose(scene, crane=None, load=None, point=None) -> P.Proposal:
    """Work out the steps from the hook where it is to the set-down point and write them as an animation. The crane
    stays where it is."""
    from . import animation
    crane, load = _crane_and_load(scene, crane, load)
    L = lifting.plan(scene)
    if crane is None:
        return P.Proposal(False, reason="No crane yet: place one under Equipment.")
    if point is not None:
        set_point(scene, point)
    if not L.has_set_down:
        return P.Proposal(False, reason="No set-down point yet: click Set-down point and click where the load goes.")
    lifting.check_joints(scene, crane)
    if animation.has_keys(scene):                  # the pick is the pose before Build, not a built frame
        animation.clear_keys(scene)
    world = hook_target(scene, crane, load, L.set_down)
    rig = lifting.rig_of(crane)
    data = lifting.item_at(lifting.path_of(crane)).data
    m = lifting.load_mass(scene, load)[0] * float(load.contingency) if load is not None else 0.0
    pr = P.propose(rig, data, lifting.values(scene, crane), lifting.to_model(crane, world),
                   L.path_clearance * 1000.0, lifting.charts_of(crane), lifting.setup(scene, crane), load_kg=m,
                   hook_block_kg=lifting.hook_block_kg(crane))
    if not pr.ok:
        L.message = f"Lift path: {pr.reason}"
        return pr
    a = _write(scene, crane, load, pr)
    L.path_anim = a.name
    L.path_result = ""
    secs = sum(s.seconds for s in pr.steps)
    L.message = (f"Lift path: {len(pr.steps)} steps, {secs:.0f} s, in the animation '{a.name}' (6 Animation). "
                 + " ".join(pr.notes)).strip()
    return pr


def _write(scene, crane, load, pr):
    """The steps as "Move joint" steps of the path's animation (made, or its own steps replaced)."""
    s = scene.fresing
    a = path_anim(scene)
    if not is_proposed(a):
        from . import animation
        a = s.animations.add()
        a.name = animation.unique_name(scene, f"Lift {load.name}" if load is not None else f"Lift {crane.name}")
        a.tail = 1.0
        a.quality, a.out_resolution, a.out_format = "preview", "hd", "presentation"
    a.blocks.clear()
    p = lifting.prefix(crane)
    t = 0.0
    for st in pr.steps:
        for name, v in st.values.items():
            j = joints.find(scene, p + name)
            if j is None:
                continue
            b = a.blocks.add()
            b.kind = "JOINT"
            b.name = PREFIX + st.label
            b.joint = j.name
            b.start, b.duration = round(t, 2), st.seconds
            b.easing = st.easing
            b.use_from = True
            if j.kind == "ROTATE":
                b.to_angle = math.radians(v)
            else:
                b.to_dist = v / 1000.0
        t = round(t + st.seconds, 2)
    a.blocks_index = 0
    s.animations_index = list(s.animations).index(a)
    return a


def use_animation(scene, name: str) -> None:
    """Check along one of the project's own animations (poses, steps) instead of a proposed path."""
    L = lifting.plan(scene)
    L.path_anim = name
    L.path_result = ""
    L.message = f"Lift path: the checks go along '{name}'." if name else ""


# ---------------------------------------------------------------------------------------------------------------------
# along the path

def _fp(anim) -> str:
    """The animation's steps as text: a change of a step makes the checks out of date."""
    rows = []
    for b in anim.blocks:
        row = []
        for p in b.bl_rna.properties:
            if p.identifier in ("rna_type",) or p.type in ("POINTER", "COLLECTION"):
                continue
            v = getattr(b, p.identifier)
            row.append(round(v, 6) if isinstance(v, float) else (tuple(v) if hasattr(v, "__len__") and
                                                                  not isinstance(v, str) else v))
        rows.append(row)
    return json.dumps(rows, default=lambda x: list(x) if hasattr(x, "__iter__") else str(x))


def _key_now(scene, crane, load, anim) -> str:
    try:
        k = (crane.name, _fp(anim), anim.fps, repr(lifting._key(scene, crane, load)[2:]),
             repr(_plan_key(scene, crane, load)))
    except Exception:  # noqa: BLE001
        return ""
    return json.dumps(k, default=str)


def reader(scene, crane):
    """(values at a frame, the key frames, (first, last frame)) of the crane's driven joints along the built
    animation: read from their keys, no frame is set."""
    from . import paths
    p = lifting.prefix(crane)
    curves, still = {}, {}
    keys = set()
    for j in scene.fresing.joints:
        if not j.name.startswith(p) or j.follows or j.motion is None:
            continue
        name = j.name[len(p):]
        f = 180.0 / math.pi if j.kind == "ROTATE" else 1000.0
        fc = next((c for c in paths._fcurves(j.motion) if c.data_path == joints.COUPLING_PATH), None)
        if fc is None or len(fc.keyframe_points) == 0:
            still[name] = joints.get_value(j) * f
            continue
        curves[name] = (fc, f)
        keys |= {float(k.co[0]) for k in fc.keyframe_points}

    def at(frame: float) -> dict:
        out = dict(still)
        for n, (fc, f) in curves.items():
            out[n] = float(fc.evaluate(frame)) * f
        return out
    return at, sorted(keys), (float(scene.frame_start), float(scene.frame_end))


def check(scene, crane=None, load=None, build: bool = True, reference: bool = False) -> dict:
    """Build the path's animation and work out every check along it: the result (also kept on the plan)."""
    from . import animation
    crane, load = _crane_and_load(scene, crane, load)
    L = lifting.plan(scene)
    a = path_anim(scene)
    if crane is None:
        raise ValueError("No crane yet: place one under Equipment.")
    if a is None:
        raise ValueError("No lift path yet: Propose the steps, or pick one of your animations.")
    lifting.check_joints(scene, crane)
    t_build = 0.0
    if build or scene.fresing.anim_baked != a.name:
        t0 = time.perf_counter()
        s = scene.fresing
        s.animations_index = list(s.animations).index(a)
        animation.bake(scene, a)
        t_build = time.perf_counter() - t0
    at_vals, keys, (f0, f1) = reader(scene, crane)
    from . import lifting_zones
    ck = checks(scene, crane, load)
    try:                                    # what the load stands on at the pick and the set-down (task 0349)
        lifting_zones.clearance_for(scene, crane, load).leave_out_touching([at_vals(f0), at_vals(f1)])
    except Exception:  # noqa: BLE001 - the row says why it is grey
        pass
    t0 = time.perf_counter()
    found = P.search(lambda t: ck.at(at_vals(t)), f0, f1, keys=keys, step=0.01, inner=1,
                     spacing=max(float(a.fps) / 5.0, 1.0))          # the grid at least every 0.2 s
    t_search = time.perf_counter() - t0
    out = {"key": _key_now(scene, crane, load, a), "anim": a.name, "crane": crane.name,
           "load": load.name if load is not None else "", "frames": [f0, f1],
           "rows": [r.to_dict() for r in P.ordered(found.worst)],
           "moments": [[round(t, 3), st] for t, st in found.moments],
           "evaluations": found.evaluations, "seconds": round(t_search, 4), "build_seconds": round(t_build, 3)}
    try:
        out["view"] = lifting_zones.path_view(scene, crane, load, at_vals, f0, f1, found)
    except Exception as exc:  # noqa: BLE001 - the plan sheet then draws the pose shown
        out["view_error"] = str(exc)
    if reference:
        t0 = time.perf_counter()
        ref = P.every(lambda t: ck.at(at_vals(t)), np.arange(f0, f1 + 0.5))
        out["every"] = {"evaluations": ref.evaluations, "seconds": round(time.perf_counter() - t0, 4),
                        "rows": [r.to_dict() for r in P.ordered(ref.worst)]}
    L.path_result = json.dumps(out, default=float)
    worst = core.worst_status(r["status"] for r in out["rows"]) if out["rows"] else core.NOT_CHECKED
    L.message = (f"Checked along '{a.name}': worst {P.COLOUR[worst]} ({core.STATUS_WORDS[worst].lower()}), "
                 f"{found.evaluations} moments worked out in {t_search * 1000:.0f} ms.")
    return out


def result(scene) -> dict | None:
    L = lifting.plan(scene)
    try:
        return json.loads(L.path_result) if L.path_result else None
    except ValueError:
        return None


def rows(scene) -> list:
    r = result(scene)
    return [P.Row.from_dict(d) for d in (r or {}).get("rows", [])]


def stale(scene) -> bool:
    """The checks along the path no longer fit the path, the crane, the load or the plan."""
    r = result(scene)
    if r is None:
        return False
    crane = next((c for c in lifting.plan(scene).cranes if c.name == r.get("crane")), None)
    load = next((ld for ld in lifting.plan(scene).loads if ld.name == r.get("load")), None)
    a = _anim_named(scene, r.get("anim", ""))
    if crane is None or a is None or (r.get("load") and load is None):
        return True
    return _key_now(scene, crane, load, a) != r.get("key")


def go_to(scene, check_id: str) -> float | None:
    """Show the worst moment of a check (its frame): the frame, or None."""
    from . import animation
    r = result(scene)
    row = next((x for x in (r or {}).get("rows", []) if x["id"] == check_id), None)
    if row is None or row.get("t") is None:
        return None
    if scene.fresing.anim_baked != r.get("anim"):
        a = _anim_named(scene, r.get("anim", ""))
        if a is None:
            return None
        s = scene.fresing
        s.animations_index = list(s.animations).index(a)
        animation.bake(scene, a)
    t = float(row["t"])
    f = int(math.floor(t))
    scene.frame_set(f, subframe=t - f)
    forget()
    return t


def worst_so_far(scene, frame: float | None = None) -> str:
    """The worst status up to ``frame`` along the checked path (the live status when there is none)."""
    r = result(scene)
    f = scene.frame_current + scene.frame_subframe if frame is None else frame
    live = live_rows(scene, force=True)
    now = P.worst_of(live) if isinstance(live, list) else core.NOT_CHECKED
    if r is None or scene.fresing.anim_baked != r.get("anim"):
        return now
    return core.worst_status([P.worst_so_far([tuple(m) for m in r.get("moments", [])], f), now])


# ---------------------------------------------------------------------------------------------------------------------
# the lift data box (a label with live fields on the hook block)

def _hook_part(scene, crane):
    from . import logic, sheet
    data = lifting.item_at(lifting.path_of(crane)).data
    m = sheet.Model(scene, lifting.sheet_of(data), root=crane.root, prefix=lifting.prefix(crane))
    hits = m.by_name.get((data["rig"].get("hook") or {}).get("assembly", ""), [])
    if not hits:
        return None
    ob = hits[0]
    if ob.type != "MESH":
        ob = next((o for o in logic.descendants(ob) if o.type == "MESH"), ob)
    return ob


def data_box_label(scene):
    return next((c for c in scene.fresing.callouts if c.part is not None and c.part.get(DATA_TAG)
                 and c.text == DATA_BOX), None)


def data_box_changed(scene) -> None:
    """The tick: on – a label with the lift's live numbers on the active crane's hook block; off – it goes."""
    if scene is None:
        return
    from . import callouts
    L = lifting.plan(scene)
    have = data_box_label(scene)
    if not L.data_box:
        if have is not None:
            s = scene.fresing
            i = list(s.callouts).index(have)
            have.part.pop(DATA_TAG, None)
            s.callouts.remove(i)
            s.callouts_index = max(0, min(s.callouts_index, len(s.callouts) - 1))
        return
    if have is not None:
        return
    crane = lifting.active_crane(scene)
    part = _hook_part(scene, crane) if crane is not None else None
    if part is None:
        L.message = "Lift data box: the crane's hook block is not found."
        return
    part[DATA_TAG] = crane.name
    callouts.add(scene, part, part.matrix_world.translation, DATA_BOX)
    scene.fresing.callouts_on = True


def live_values(scene, part) -> dict:
    """The numbers the lift data box shows at the frame shown ({} for any other part)."""
    if part is None or not part.get(DATA_TAG):
        return {}
    crane = next((c for c in lifting.plan(scene).cranes if c.name == part.get(DATA_TAG)), None)
    if crane is None:
        return {}
    load = lifting.active_load(scene)
    ro = lifting.readout(scene, crane, load)
    if isinstance(ro, str):
        return {"worst": "–"}
    return {"load": core.tonnes(ro.load + ro.rigging), "radius": ro.radius,
            "use": None if ro.use is None else ro.use * 100.0, "hook": ro.height,
            "worst": core.STATUS_WORDS[worst_so_far(scene)]}


# ---------------------------------------------------------------------------------------------------------------------
# the use bar beside the hook

_DRAW = {"handle": None}
BAR_RGB = {core.OK: (0.30, 0.69, 0.31), core.AMBER: (0.98, 0.66, 0.15), core.RED: (0.90, 0.22, 0.21),
           core.NOT_CHECKED: (0.6, 0.6, 0.6)}


def bar_numbers(scene):
    """(C1 use or None, the worst status now, its words) for the bar; None when nothing to draw."""
    crane = lifting.active_crane(scene)
    if crane is None or crane.root is None:
        return None
    rs = live_rows(scene)
    if isinstance(rs, str):
        return None
    c1 = next((r for r in rs if r.id == "C1"), None)
    worst = P.worst_of(rs)
    bad = [r for r in rs if r.status == worst and r.id != "C1"]
    words = f"{TITLE_SHORT.get(bad[0].id, bad[0].id)}: {P.COLOUR[worst]}" if bad and worst in (core.RED, core.AMBER) \
        else ""
    return (c1.use if c1 is not None else None), worst, words


TITLE_SHORT = {"C5": "outriggers", "C6": "tracks", "SETUP": "set-up", "BACK": "backward stability", "C10": "line pull",
               "CLR": "clearance",
               "C2": "sling legs", "C3": "sling legs", "C4": "gear"}


def _draw_bar():
    ctx = bpy.context
    scene = getattr(ctx, "scene", None)
    if scene is None or not hasattr(scene, "fresing") or not scene.fresing.lifting.cranes:
        return
    region, rv3d = ctx.region, ctx.region_data
    if region is None or rv3d is None or rv3d.view_perspective == "CAMERA":
        return
    if not lifting.cog_shown(scene) or not lifting.understood():
        return
    got = bar_numbers(scene)
    if got is None:
        return
    use, worst, words = got
    crane = lifting.active_crane(scene)
    from bpy_extras.view3d_utils import location_3d_to_region_2d
    try:
        hook = lifting.hook_world(scene, crane)
    except Exception:  # noqa: BLE001
        return
    p = location_3d_to_region_2d(region, rv3d, Vector(hook))
    if p is None:
        return
    import blf
    import gpu
    from gpu_extras.batch import batch_for_shader
    x, y, w, h = p.x + 18, p.y + 10, 90.0, 9.0
    sh = gpu.shader.from_builtin("UNIFORM_COLOR")
    gpu.state.blend_set("ALPHA")

    def rect(x0, y0, x1, y1, col):
        b = batch_for_shader(sh, "TRIS", {"pos": [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]}, indices=[(0, 1, 2), (0, 2, 3)])
        sh.uniform_float("color", col)
        b.draw(sh)
    rect(x - 1, y - 1, x + w + 1, y + h + 1, (0.05, 0.05, 0.05, 0.85))
    rect(x, y, x + w, y + h, (0.2, 0.2, 0.2, 0.9))
    if use is not None:
        rect(x, y, x + w * min(max(use, 0.0), 1.0), y + h, (*BAR_RGB[worst], 1.0))
    lim = core.DEFAULT_LIMITS.crane
    rect(x + w * lim - 1, y - 2, x + w * lim + 1, y + h + 2, (1.0, 1.0, 1.0, 0.9))
    blf.size(0, 12)
    blf.color(0, 1.0, 1.0, 1.0, 1.0)
    blf.position(0, x + w + 6, y, 0)
    blf.draw(0, (f"{use * 100:.0f} %" if use is not None else "no chart") + (f" · {words}" if words else ""))
    gpu.state.blend_set("NONE")


def register():
    if _DRAW["handle"] is None and not bpy.app.background:
        _DRAW["handle"] = bpy.types.SpaceView3D.draw_handler_add(_draw_bar, (), "WINDOW", "POST_PIXEL")
    if _load_post not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_load_post)


def unregister():
    if _DRAW["handle"] is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_DRAW["handle"], "WINDOW")
        _DRAW["handle"] = None
    if _load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_load_post)


@bpy.app.handlers.persistent
def _load_post(_dummy=None):
    forget()
