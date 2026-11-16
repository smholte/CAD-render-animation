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
built. In the background (tests, the render queue) the re-bake still runs at once, as before.
"""

from __future__ import annotations

import bpy

from . import flex

WAIT = flex.MOTION_WAIT                  # s: a slider rests this long before the job starts
READ_SHARE = 0.85                        # of the progress bar: the pass through the frames
CANCELLED = ("Cables and hoses not worked out again for the new sea: the built animation was taken off. "
             "Press Build again")

_STATE = {"pending": {}, "running": False, "progress": 0.0, "cancel": False, "scene": "", "text": ""}


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
    """Which of the two still need it (a Build or another re-bake may have done it meanwhile)."""
    from . import paths, vessel_motion
    out = {}
    if "flex" in want and len(scene.fresing.flex) and flex._baked(scene) and \
            (want["flex"] or vessel_motion.moved_since(scene, flex.MOTION_KEY, seabed=False)):
        out["flex"] = True
    if "paths" in want and paths._baked(scene) and \
            any(it.enabled and it.b_kind == "SEA" for it in scene.fresing.cables) and \
            (want["paths"] or vessel_motion.moved_since(scene, paths.MOTION_KEY)):
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
                    if bpy.ops.fresing.rebake("INVOKE_DEFAULT", flex="flex" in todo, cables="paths" in todo) \
                            == {"RUNNING_MODAL"}:
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


def _paths_objects(scene) -> tuple[list, bool]:
    from . import paths, paths_swivel
    _notes, _its, _can, animated, obs = paths._plan(scene)
    return list(obs) + list(paths_swivel.objects(scene)), bool(animated)


def steps(scene, todo: dict, notes: list | None = None):
    """The re-bake as a generator: yields progress (0 … 1). ``todo``: {"flex": True, "paths": True} – which to work
    out again. ``notes`` gets what the bakes said."""
    from . import paths
    notes = [] if notes is None else notes
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
        if not obs and also:                    # (no hose to read: the cables' objects, as the cables read them)
            obs, also, keep_shown = also, [], False
        if obs:
            with flex.at_first_frame(scene):
                for p in flex.read_steps(scene, obs, first, frames, keep_shown=keep_shown, also=also, keep=True):
                    yield READ_SHARE * p
        yield READ_SHARE
        if todo.get("flex"):
            notes += flex._motion_bake(scene, kept=True)
            yield READ_SHARE + 0.5 * (1.0 - READ_SHARE)
        if todo.get("paths"):
            notes += paths._motion_bake(scene, kept=True)
        yield 1.0
    finally:
        flex.drop_read()


def cancelled(scene) -> None:
    """Cancel: the built animation comes off – its hoses and cables were worked out for the old sea."""
    from . import animation
    animation.clear_keys(scene)
    scene.fresing.last_message = CANCELLED
