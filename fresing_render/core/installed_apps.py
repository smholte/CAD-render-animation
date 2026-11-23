"""Fresing Render in Windows' "Installed apps" (task 0265) - no Blender, no network.

The installer writes one per-user key, ``HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\FresingRender``
(no admin rights), so Settings > Apps > Installed apps lists the app and its Uninstall button runs the uninstaller kept
in the install folder (``Tools\\Uninstall-FresingRender.ps1``; a copy ships inside the extension, so an update and
the app's start bring it to an older install). This module works out what the key holds and what has to change; the
registry itself is read and written through a small ``Registry`` object (``winreg`` on Windows, a dict in tests).
"""
from __future__ import annotations

import datetime
import os

KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\FresingRender"
DISPLAY_NAME = "Fresing Render"
PUBLISHER = "Fresing"
ABOUT_URL = "https://github.com/smholte/CAD-render-animation"
HELP_URL = "https://smholte.github.io/CAD-render-animation/"
UNINSTALLER = "Uninstall-FresingRender.ps1"
TOOLS_FOLDER = "Tools"
SHIPPED_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "installer_files")
SHIPPED_UNINSTALLER = os.path.join(SHIPPED_DIR, UNINSTALLER)
# the values that change with an update; the rest is written once (and again by a repair)
VERSION_VALUES = ("DisplayVersion", "EstimatedSize")


def uninstaller_path(folder: str) -> str:
    return os.path.join(folder, TOOLS_FOLDER, UNINSTALLER)


def uninstall_string(folder: str, quiet: bool = False) -> str:
    """The command Settings runs. ``-FromSettings`` shows the window and waits for a key at the end; quiet = no wait."""
    cmd = (f'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "{uninstaller_path(folder)}" '
           f'-InstallDir "{folder}"')
    return cmd if quiet else cmd + " -Pause"


def folder_size_kb(folder: str) -> int:
    """Size of the install folder in KB (what Windows shows as "Size"); files only, links not followed."""
    total = 0
    for root, _dirs, files in os.walk(folder, followlinks=False):
        for name in files:
            try:
                p = os.path.join(root, name)
                if not os.path.islink(p):
                    total += os.path.getsize(p)
            except OSError:
                pass
    return max(1, (total + 1023) // 1024)


def wanted(folder: str, version: str, icon: str = "", size_kb: int = 0, today: datetime.date | None = None) -> dict:
    """The key's values for this install."""
    today = today or datetime.date.today()
    return {
        "DisplayName": DISPLAY_NAME,
        "DisplayVersion": str(version),
        "Publisher": PUBLISHER,
        "DisplayIcon": icon or "",
        "InstallLocation": folder,
        "InstallDate": today.strftime("%Y%m%d"),
        "EstimatedSize": int(size_kb),
        "URLInfoAbout": ABOUT_URL,
        "HelpLink": HELP_URL,
        "NoModify": 1,
        "NoRepair": 1,
        "UninstallString": uninstall_string(folder),
        "QuietUninstallString": uninstall_string(folder, quiet=True),
    }


def _same_place(a: str, b: str) -> bool:
    return os.path.normcase(os.path.normpath(a or "")) == os.path.normcase(os.path.normpath(b or ""))


def changes(current: dict | None, want: dict) -> dict:
    """What to write: everything when the key is missing or belongs to another folder; else only values that differ
    (``InstallDate`` is kept as it was; ``EstimatedSize`` only changes with the version)."""
    if not current or not _same_place(str(current.get("InstallLocation", "")), want["InstallLocation"]):
        return dict(want)
    out = {}
    for name, value in want.items():
        if name == "InstallDate":
            if not current.get(name):
                out[name] = value
        elif name == "EstimatedSize":
            if current.get("DisplayVersion") != want["DisplayVersion"] or not current.get(name):
                out[name] = value
        elif current.get(name) != value:
            out[name] = value
    return out


def needs_size(current: dict | None, folder: str, version: str) -> bool:
    """Whether the folder has to be measured (a walk over the install folder): only for a new key or a new version."""
    return (not current or not _same_place(str(current.get("InstallLocation", "")), folder)
            or current.get("DisplayVersion") != str(version) or not current.get("EstimatedSize"))


class Registry:
    """The per-user key through ``winreg`` (Windows only)."""

    def read(self) -> dict | None:
        import winreg
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY, 0, winreg.KEY_READ)
        except OSError:
            return None
        out = {}
        with key:
            i = 0
            while True:
                try:
                    name, value, _kind = winreg.EnumValue(key, i)
                except OSError:
                    break
                out[name] = value
                i += 1
        return out

    def write(self, values: dict) -> None:
        import winreg
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, KEY, 0, winreg.KEY_SET_VALUE) as key:
            for name, value in values.items():
                kind = winreg.REG_DWORD if isinstance(value, int) else winreg.REG_SZ
                winreg.SetValueEx(key, name, 0, kind, value)


def copy_uninstaller(folder: str, source: str = SHIPPED_UNINSTALLER) -> str:
    """The uninstaller the extension ships goes to ``<install>\\Tools``; '' when it is already the same file."""
    dst = uninstaller_path(folder)
    if not os.path.isfile(source):
        return ""
    data = open(source, "rb").read()
    try:
        if open(dst, "rb").read() == data:
            return ""
    except OSError:
        pass
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    tmp = dst + ".new"
    with open(tmp, "wb") as fh:
        fh.write(data)
    os.replace(tmp, dst)
    return dst


def ensure(folder: str, version: str, icon: str = "", registry=None, source: str = SHIPPED_UNINSTALLER) -> list[str]:
    """The entry is there and right (the app at its start; an install before 0265 gets it once). Returns what was done."""
    reg = registry or Registry()
    done = []
    if copy_uninstaller(folder, source):
        done.append("uninstaller copied into the Tools folder")
    if not os.path.isfile(uninstaller_path(folder)):
        return done                                    # nothing to run from Settings: no entry rather than a dead one
    current = reg.read()
    size = folder_size_kb(folder) if needs_size(current, folder, version) else int((current or {}).get("EstimatedSize") or 0)
    todo = changes(current, wanted(folder, version, icon, size))
    if not icon:
        todo.pop("DisplayIcon", None)                  # never wipe a good icon with nothing
    if todo:
        reg.write(todo)
        done.append("Installed apps entry: " + ("made" if not current else "updated (" + ", ".join(sorted(todo)) + ")"))
    return done
