"""The re-bake after Build as a long job (task 0160, bug hunt 0147 row 19).

When the sea, the vessel motion, its speed or the water level change after Build, the built hoses, drag chains and
cables into the sea are worked out again for the new motion (task 0137, ``flex.motion_changed``,
``paths.motion_changed``). On the small demo that took 63–90 s in one go: Blender froze with no progress and no way
out. In the window it now runs as a long job (``FRESING_OT_rebake`` in ``ops_paths.py``):

1. the pass through the frames that reads where the parts are (most of the time) runs a few frames per tick
   (``flex.read_steps``), with a progress line in 4 Motion > Cables and paths and in the status bar;
2. then the hoses and the cables are solved from what was read (``flex._motion_bake`` / ``paths._motion_bake`` with
   ``kept``: the pass is not repeated).

**Cancel** (or Esc) stops it and takes the built animation off ("Build again"): half-worked shapes are never shown as
built. In the background (tests, the render queue) the re-bake still runs at once.

Task 0192 (bug hunt 6 rows 7 and 10):

- camera steps that ride on a part, fly a path or keep a part in the middle were worked out at Build for the old motion
  (a camera riding the hull kept the old sea's heave, up to 1.48 m off): the re-bake takes their keys again
  (``cameras``), as Build does – also when there is no hose or sea cable;
- in the background every change goes through ONE pass (``run_now``): a setting change gathers what flex, the cables
  and the cameras want (``gathered``) and runs it once at its end (before: the hoses' pass, then the cables' own,
  606 s on the small demo against 221 s for a Build);
- the cables' solve is a step per cable (``paths.motion_steps``), so the window's job redraws between them.
"""

from __future__ import annotations

import bpy

from contextlib import contextmanager
from functools import wraps

from . import flex

WAIT = flex.MOTION_WAIT                  # s: a slider rests this long before the job starts
READ_SHARE = 0.85                        # of the progress bar: the pass through the frames
CANCELLED = ("Cables and hoses not worked out again for the new sea: the built animation was taken off. "
             "Press Build again")

_STATE = {"pending": {}, "running": False, "progress": 0.0, "cancel": False, "scene": "", "text": ""}


_GATHER = {"depth": 0, "todo": {}}       # the background: what a setting change asked for, run once at its end


@contextmanager
def gathered():
    """In the background, re-bakes asked for meanwhile (flex, cables, cameras) run as one pass at the end."""
    _GATHER["depth"] += 1
    try:
        yield
    finally:
        _GATHER["depth"] -= 1
        if not _GATHER["depth"] and _GATHER["todo"]:
            todo, _GATHER["todo"] = _GATHER["todo"], {}
            for name, want in todo.items():
                scene = bpy.data.scenes.get(name)
                if scene is None:
                    continue
                try:
                    run_now(scene, _needed(scene, want))
                except Exception as exc:         # never break a setting's change over this
                    print("Fresing Render: cables and hoses not worked out again:", exc)


def gathering(fn):
    """A property's update function: the re-bakes it causes run once, at its end (``gathered``)."""
    @wraps(fn)
    def run(*args, **kw):
        with gathered():
            return fn(*args, **kw)
    return run


def background(scene, what: str, force: bool) -> None:
    """``flex`` / ``paths`` / ``cameras`` wants a re-bake with no window to show it in: at the end of the setting's
    change when one is going on (``gathered``), else now – one pass either way."""
    if _GATHER["depth"]:
        want = _GATHER["todo"].setdefault(scene.name, {})
        want[what] = bool(want.get(what, False) or force)
        return
    run_now(scene, _needed(scene, {what: force}))


def running(scene=None) -> bool:
    return bool(_STATE["running"]) and (scene is None or _STATE["scene"] == scene.name)


def progress() -> float:
    return float(_STATE["progress"])


def request(scene, what: str, force: bool) -> None:
    """``flex`` or ``paths`` wants its built shapes worked out again (in the window): one job for both, started
    once the change has rested ``WAIT`` s."""
    want = _STATE["pending"].setdefault(scene.name, {})
    want[what] = bool(want.get(what, False) or force)
    if bpy.app.timers.is_registered(_timer):
        bpy.app.timers.unregister(_timer)
    bpy.app.timers.register(_timer, first_interval=WAIT)


def _needed(scene, want: dict) -> dict:
    """Which still need it (a Build or another re-bake may have done it meanwhile). The cameras come along with any
    re-bake when their keys were worked out for another vessel motion."""
    from . import paths, vessel_motion
    out = {}
    if moving_cameras(scene) and (want.get("cameras") or
                                  vessel_motion.moved_since(scene, _camera_key(), seabed=False)):
        out["cameras"] = True
    if "flex" in want and len(scene.fresing.flex) and flex._baked(scene) and \
            (want["flex"] or vessel_motion.moved_since(scene, flex.MOTION_KEY, seabed=False)):
        out["flex"] = True
    if "paths" in want and paths._baked(scene) and \
            any(it.enabled and it.b_kind == "SEA" for it in scene.fresing.cables) and \
            (want["paths"] or paths.sea_moved(scene)):
        out["paths"] = True
    return out


def _window():
    wm = bpy.context.window_manager
    for win in (wm.windows if wm is not None else ()):
        for area in win.screen.areas:
            if area.type == "VIEW_3D":
                return win, area
    return None, None


def _timer():
    pending, _STATE["pending"] = _STATE["pending"], {}
    for name, want in pending.items():
        scene = bpy.data.scenes.get(name)
        if scene is None:
            continue
        try:
            todo = _needed(scene, want)
            if not todo:
                continue
            if _STATE["running"]:                # one job at a time: this one again once that one is done
                _STATE["pending"][name] = want
                return 1.0
            win, area = _window()
            if win is not None:
                with bpy.context.temp_override(window=win, area=area, scene=scene):
                    if bpy.ops.fresing.rebake("INVOKE_DEFAULT", flex="flex" in todo, cables="paths" in todo,
                                              cameras="cameras" in todo) == {"RUNNING_MODAL"}:
                        continue
            run_now(scene, todo)                 # (no window to show the job in)
            flex._redraw_views()
        except Exception as exc:                 # never break the UI over this
            print("Fresing Render: cables and hoses not worked out again:", exc)
    return None


def run_now(scene, todo: dict) -> list[str]:
    """The whole re-bake in one go (the background, a window-less moment)."""
    out = []
    for _p in steps(scene, todo, out):
        pass
    return out


def _camera_key() -> str:
    from . import camera_path
    return camera_path.MOTION_KEY


def _camera_blocks(scene):
    """(the built animation, its camera steps in Build's order)."""
    s = scene.fresing
    anim = s.animations.get(s.anim_baked) if s.anim_baked else None
    if anim is None:
        return None, []
    return anim, sorted((b for b in anim.blocks if b.enabled and b.kind == "CAMERA"), key=lambda b: b.start)


def moving_cameras(scene) -> bool:
    """The built animation has camera steps that ride on a part, fly a path or keep a part in the middle."""
    from . import camera_path
    _anim, blocks = _camera_blocks(scene)
    return any(b.camera_mode in camera_path.MODES for b in blocks) and _anim_camera() is not None


def _anim_camera():
    return next((o for o in bpy.data.objects if o.get("fr_anim_camera")), None)


def _fcurve_values(id_block, path: str, n: int, frame: float):
    ad = id_block.animation_data
    act = ad.action if ad is not None else None
    if act is None:
        return None
    from bpy_extras import anim_utils
    cb = anim_utils.action_get_channelbag_for_slot(act, ad.action_slot) if ad.action_slot is not None else None
    if cb is None:
        return None
    out = []
    for i in range(n):
        fc = cb.fcurves.find(path, index=i)
        if fc is None:
            return None
        out.append(fc.evaluate(frame))
    return out


def camera_objects(scene) -> list:
    """The parts the built camera steps ride on or keep in the middle (task 0238): read in the re-bake's pass through
    the frames with the hoses' and cables' parts, a frame per job step. Not a part drawn by nodes (the pass hides
    those and works their place out from the parent's, without constraints): the camera reads that one itself."""
    from . import camera_path, states
    _anim, blocks = _camera_blocks(scene)
    uids = states.by_uid(scene)
    out = {}
    for b in blocks:
        if b.camera_mode not in camera_path.MODES:
            continue
        for uid in ((b.target_uid if b.camera_mode == "RIDE" else ""),
                    (b.aim_uid if camera_path.looks_at_part(b) else "")):
            ob = uids.get(uid) if uid else None
            if ob is not None and not any(m.type == "NODES" for m in getattr(ob, "modifiers", ())):
                out[ob.name] = ob
    return list(out.values())


def cameras(scene, places: dict | None = None) -> list[str]:
    """The Animation camera's keys worked out again as Build works them out (``animation._camera_track``), from its
    own state at frame 1 (the start camera, as Build had it) and the model centre of that Build: the steps that ride
    or watch a part read where it is now. Returns Build's warnings of the camera steps."""
    from mathutils import Matrix, Quaternion, Vector

    from . import animation, camera_path, states
    anim, blocks = _camera_blocks(scene)
    cam = _anim_camera()
    if anim is None or cam is None or not any(b.camera_mode in camera_path.MODES for b in blocks):
        return []
    first = int(scene.frame_start)
    loc = _fcurve_values(cam, "location", 3, first)
    rot = _fcurve_values(cam, "rotation_quaternion", 4, first)
    if loc is None or rot is None:
        return []
    lens = _fcurve_values(cam.data, "lens", 1, first)
    ortho = _fcurve_values(cam.data, "ortho_scale", 1, first)
    focus = _fcurve_values(cam.data, "dof.focus_distance", 1, first)
    start = animation.CamState(Matrix.Translation(Vector(loc)) @ Quaternion(rot).normalized().to_matrix().to_4x4(),
                               lens[0] if lens else cam.data.lens, ortho[0] if ortho else cam.data.ortho_scale,
                               focus[0] if focus else cam.data.dof.focus_distance, cam.data.type)
    c = scene.get(camera_path.CENTRE)
    centre = Vector([float(v) for v in c]) if c is not None and len(c) == 3 else animation._model_centre(scene)
    warnings: list[str] = []
    ctx = camera_path.Context(scene, anim, blocks, states.by_uid(scene), centre, warnings, places=places,
                              first=int(scene.frame_start))
    track = animation._camera_track(anim, blocks, start, centre, int(scene.frame_end), ctx, warnings)
    cb = animation._channelbag(cam, "OBJECT")
    rows, q_prev = [], None
    for f, st in enumerate(track, start=1):
        loc_, rot_, _sc = st.matrix.decompose()
        if q_prev is not None and q_prev.dot(rot_) < 0:
            rot_ = Quaternion((-rot_.w, -rot_.x, -rot_.y, -rot_.z))
        q_prev = rot_
        rows.append((f, loc_, rot_, st))
    for i in range(3):
        animation._write(cb, "location", i, [(f, lo[i], "LINEAR", "AUTO") for f, lo, _r, _s in rows])
    for i in range(4):
        animation._write(cb, "rotation_quaternion", i, [(f, ro[i], "LINEAR", "AUTO") for f, _l, ro, _s in rows])
    dcb = animation._channelbag(cam.data, "CAMERA")
    animation._write(dcb, "lens", 0, [(f, st.lens, "LINEAR", "AUTO") for f, _l, _r, st in rows])
    animation._write(dcb, "ortho_scale", 0, [(f, st.ortho_scale, "LINEAR", "AUTO") for f, _l, _r, st in rows])
    if focus is not None:
        animation._write(dcb, "dof.focus_distance", 0, [(f, st.focus, "LINEAR", "AUTO") for f, _l, _r, st in rows])
    return warnings


def _paths_objects(scene) -> tuple[list, bool]:
    from . import paths, paths_swivel
    _notes, _its, _can, animated, obs = paths._plan(scene)
    return list(obs) + list(paths_swivel.objects(scene)), bool(animated)


TRIES = 3                                # the job starts over when what it reads was deleted meanwhile (0192)


def steps(scene, todo: dict, notes: list | None = None):
    """The re-bake as a generator: yields progress (0 … 1). ``todo``: {"flex": True, "paths": True, "cameras": True} –
    which to work out again. ``notes`` gets what the bakes said. Task 0192 (the owner's "StructRNA of type Object has
    been removed"): a setting changed during the job can make objects it reads again (the sea, the vessel rig); the
    job then starts over (a newer change asks for another re-bake anyway)."""
    notes = [] if notes is None else notes
    for attempt in range(TRIES):
        try:
            yield from _steps_once(scene, todo, notes)
            return
        except flex.ReadLost as exc:
            flex.drop_read()
            if attempt == TRIES - 1:
                raise RuntimeError(f"'{exc}' was deleted while the cables were worked out again") from exc
            yield 0.0


def _steps_once(scene, todo: dict, notes: list):
    from . import paths
    first, end = int(scene.frame_start), int(max(scene.frame_start, scene.frame_end))
    frames = end - first + 1
    try:
        obs, also, keep_shown = [], [], True
        if todo.get("flex"):
            its = flex._usable(scene)
            obs = [ob for _i, it in its for ob in (it.a_part, it.b_part) if ob is not None]
            for fn in flex.READ_HOOKS:
                try:
                    also += [ob for ob in (fn(scene) or ()) if ob is not None]
                except Exception as exc:         # never stop over another module's wish
                    print("Fresing Render: read hook failed:", exc)
        if todo.get("paths"):
            pobs, animated = _paths_objects(scene)
            if animated:
                also += pobs
        cam_names = []
        if todo.get("cameras"):                 # task 0238: the riding camera's parts, read in the same pass
            cam_obs = camera_objects(scene)
            cam_names = [ob.name for ob in cam_obs]
            also += cam_obs
        if not obs and also:                    # (no hose to read: the cables' objects, as the cables read them)
            obs, also, keep_shown = also, [], False
        if obs:
            with flex.at_first_frame(scene):
                for p in flex.read_steps(scene, obs, first, frames, keep_shown=keep_shown, also=also, keep=True):
                    yield READ_SHARE * p
        # (taken now: the cables' bake lets go of what the pass read)
        cam_places = {n: a for n, a in flex.kept_read(scene, first, frames).items() if n in cam_names}
        yield READ_SHARE
        share = (1.0 - READ_SHARE) / max(1, sum(1 for k in ("flex", "paths", "cameras") if todo.get(k)))
        done = READ_SHARE
        if todo.get("flex"):
            notes += flex._motion_bake(scene, kept=True)
            done += share
            yield done
        if todo.get("paths"):                   # a step per cable (task 0192: the window redraws between them)
            for p in paths.motion_steps(scene, notes, kept=True):
                yield done + share * p
            done += share
            yield done
        if todo.get("cameras"):                 # task 0192 (bug hunt 6 row 7): the steps that ride on a part
            with flex.at_first_frame(scene):
                notes += cameras(scene, places=cam_places)
        yield 1.0
    finally:
        flex.drop_read()


def cancelled(scene) -> None:
    """Cancel: the built animation comes off – its hoses and cables were worked out for the old sea."""
    from . import animation
    animation.clear_keys(scene)
    scene.fresing.last_message = CANCELLED
