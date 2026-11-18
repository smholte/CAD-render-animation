"""Blender's own extension repositories do not sync at start (task 0206, owner 18 Nov 2026).

Blender checks its online extension repository (extensions.blender.org) at every start when "Check for Updates on
Start" is on; the installer switches Blender's online access on for Fresing Render's own update check, and with it that
sync would run. So the app contacts nothing at start except its own update check: the installer sets
``use_sync_on_startup = False`` on every remote repository, and an install made before this does the same ONCE at the
first start after the update. The step is remembered in a small file next to the other settings, so a user who turns
the sync back on keeps it on.
"""

from __future__ import annotations

import json
import os

import bpy

FILE_NAME = "fresing_ext_sync.json"
FILE_ENV = "FRESING_EXT_SYNC_FILE"           # tests


def state_path() -> str:
    path = os.environ.get(FILE_ENV, "")
    if path:
        return path
    return os.path.join(bpy.utils.user_resource("CONFIG"), FILE_NAME)


def remote_repos():
    return [r for r in bpy.context.preferences.extensions.repos if r.use_remote_url]


def synced() -> list[str]:
    """Names of the remote repositories that sync at start now."""
    return [r.name for r in remote_repos() if r.use_sync_on_startup]


def switch_off_once() -> list[str]:
    """Switch the sync off on every remote repository, the first time only. Returns the names it changed."""
    path = state_path()
    if os.path.isfile(path):
        return []
    from .. import __version__
    changed = []
    for repo in remote_repos():
        if repo.use_sync_on_startup:
            repo.use_sync_on_startup = False
            changed.append(repo.name)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"done": __version__, "changed": changed}, fh)
    except OSError:
        pass
    if changed and not bpy.app.background:
        try:
            bpy.ops.wm.save_userpref()
        except Exception:  # noqa: BLE001 - Blender saves changed preferences when it closes anyway
            pass
    return changed
