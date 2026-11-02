"""'In use by…' lock for projects on a shared folder.

While a saved project is open, a small file ``<project>.blend.inuse`` next to it says
who has it open (user, computer, since when) and is refreshed every few minutes.
Someone else opening the project sees a warning in the side panel. A lock that has
not been refreshed for a while (crash, computer off) is ignored.
"""

from __future__ import annotations

import getpass
import json
import os
import platform
import time

import bpy
from bpy.app.handlers import persistent

HEARTBEAT_SECONDS = 120
STALE_SECONDS = 15 * 60
_STATE = {"path": "", "other": None}


def lock_path(blend_path: str) -> str:
    return blend_path + ".inuse"


def me() -> dict:
    try:
        user = getpass.getuser()
    except Exception:
        user = os.environ.get("USERNAME") or os.environ.get("USER") or "someone"
    return {"user": user, "computer": platform.node(), "pid": os.getpid()}


def _is_me(info: dict) -> bool:
    m = me()
    return info.get("user") == m["user"] and info.get("computer") == m["computer"]


def read(blend_path: str) -> dict | None:
    try:
        with open(lock_path(blend_path), encoding="utf-8") as fh:
            info = json.load(fh)
    except (OSError, ValueError):
        return None
    if time.time() - float(info.get("heartbeat", 0)) > STALE_SECONDS:
        return None
    return info


def other_user(blend_path: str) -> dict | None:
    """The lock of someone else (or this user on another computer), if fresh."""
    info = read(blend_path)
    if info is None or _is_me(info):
        return None
    return info


def write(blend_path: str, since: float | None = None) -> None:
    info = me()
    old = read(blend_path)
    info["since"] = since or (old.get("since") if old and _is_me(old) else None) or time.time()
    info["heartbeat"] = time.time()
    try:
        with open(lock_path(blend_path), "w", encoding="utf-8") as fh:
            json.dump(info, fh)
    except OSError:
        pass                                   # read-only share: no lock, no problem


def release(blend_path: str) -> None:
    info = read(blend_path)
    if info is not None and _is_me(info) and info.get("pid") == os.getpid():
        try:
            os.remove(lock_path(blend_path))
        except OSError:
            pass


def describe(info: dict) -> str:
    since = time.strftime("%H:%M", time.localtime(float(info.get("since", time.time()))))
    day = time.strftime("%d %b", time.localtime(float(info.get("since", time.time()))))
    today = time.strftime("%d %b")
    when = since if day == today else f"{day} {since}"
    return f"{info.get('user', 'someone')} on {info.get('computer', '?')} since {when}"


def warning() -> str:
    info = _STATE.get("other")
    return describe(info) if info else ""


def _take(path: str) -> None:
    if not path or bpy.app.background:
        return
    _STATE["other"] = other_user(path)
    if _STATE["other"] is None:
        write(path)
    _STATE["path"] = path


def _heartbeat():
    path = _STATE.get("path")
    if path and bpy.data.filepath == path:
        other = other_user(path)
        _STATE["other"] = other
        if other is None:
            write(path)
    return HEARTBEAT_SECONDS


@persistent
def _after_load(_dummy=None):
    _take(bpy.data.filepath)


@persistent
def _before_load(_dummy=None):
    if _STATE.get("path"):
        release(_STATE["path"])
    _STATE.update(path="", other=None)


@persistent
def _after_save(_dummy=None):
    path = bpy.data.filepath
    if path != _STATE.get("path"):
        if _STATE.get("path"):
            release(_STATE["path"])         # "Save as": the old file is free again
        _take(path)
    elif _STATE.get("other") is None:
        write(path)


def _at_exit():
    if _STATE.get("path"):
        release(_STATE["path"])


def register():
    import atexit
    for lst, fn in ((bpy.app.handlers.load_post, _after_load), (bpy.app.handlers.load_pre, _before_load),
                    (bpy.app.handlers.save_post, _after_save)):
        if fn not in lst:
            lst.append(fn)
    if not bpy.app.background and not bpy.app.timers.is_registered(_heartbeat):
        bpy.app.timers.register(_heartbeat, first_interval=HEARTBEAT_SECONDS, persistent=True)
    atexit.register(_at_exit)


def unregister():
    import atexit
    for lst, fn in ((bpy.app.handlers.load_post, _after_load), (bpy.app.handlers.load_pre, _before_load),
                    (bpy.app.handlers.save_post, _after_save)):
        while fn in lst:
            lst.remove(fn)
    if bpy.app.timers.is_registered(_heartbeat):
        bpy.app.timers.unregister(_heartbeat)
    atexit.unregister(_at_exit)
