"""The Fresing icon on Windows (task 0169), checked inside the installed app's Blender on GitHub's Windows job.

    blender.exe --background --python-exit-code 1 --python tools/appicon_test.py -- <out.json>

tools/ci_windows_install.ps1 first turns two of the installed shortcuts back into what Install.bat made before 0169
(Blender's icon, no app ID) and deletes the icon copy in the install folder. This script then
1. runs what the app runs at start on such a PC (``appicon.refresh_installed``) and reads the shortcuts back;
2. checks that the start-up hook never runs here (a background run);
3. sets the icon and the app's ID on a window of its own (there is no Blender window in the background) and reads
   them back with WM_GETICON and the window's property store; sets and reads the process' ID.
The .ps1 reads the shortcuts once more with WScript.Shell / Shell.Application (another way in).
Writes {"checks": [[name, ok, detail], ...]} to <out.json>.
"""

from __future__ import annotations

import importlib
import json
import os
import sys
import traceback

import bpy

OUT = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "appicon_test.json"
CHECKS: list[list] = []


def check(name, ok, detail=""):
    CHECKS.append([name, bool(ok), str(detail)])
    print(("PASS " if ok else "FAIL ") + name + (f" ({detail})" if detail else ""), flush=True)


def module():
    import addon_utils
    name = next(m.__name__ for m in addon_utils.modules() if m.__name__.endswith("fresing_render"))
    return importlib.import_module(name + ".appicon")


def main():
    ai = module()
    exe = bpy.app.binary_path
    folder = ai.install_dir(exe)
    check("install folder found from blender.exe", folder, folder)
    desktop, programs, appdata = ai.known_folders()
    paths = ai.shortcut_paths(desktop, programs, appdata)
    check("shortcuts found", len(paths) >= 5, f"{len(paths)}: " + ", ".join(os.path.basename(p) for p in paths))
    before = {os.path.basename(p): ai.read_shortcut(p) for p in paths}
    old = [n for n, i in before.items() if "blender.exe" in i["icon"].lower()]
    check("an older install's shortcuts are there to refresh", old, ", ".join(old))

    done = ai.refresh_installed(exe)
    check("refresh: icon copied into the install folder", os.path.isfile(os.path.join(folder, ai.ICON_FILE)))
    check("refresh changed the older shortcuts", all(any(d.startswith(n + ":") for d in done) for n in old),
          "; ".join(done))
    icon = os.path.join(folder, ai.ICON_FILE)
    for p in paths:
        info = ai.read_shortcut(p)
        name = os.path.basename(p)
        check(f"{name}: Fresing icon", os.path.normcase(info["icon"]) == os.path.normcase(icon)
              and info["icon_index"] == 0, f'{info["icon"]},{info["icon_index"]}')
        if ai.is_app_shortcut(info["arguments"]):
            check(f"{name}: app ID", info["app_id"] == ai.APP_ID, info["app_id"])
    again = ai.refresh_installed(exe)
    check("a second refresh writes nothing", not again, "; ".join(again))

    check("start-up hook does not run in the background", ai.startup() is False)
    check("start-up hook only for the app on Windows",
          ai.wanted("win32", False, "fresing_render", {}) and not ai.wanted("win32", True, "fresing_render", {})
          and not ai.wanted("win32", False, "", {}) and not ai.wanted("linux", False, "fresing_render", {})
          and not ai.wanted("win32", False, "fresing_render", {"FRESING_NO_APPICON": "1"}))

    # a window of our own: a plain STATIC control as a top-level window
    import ctypes
    from ctypes import wintypes as wt
    u = ctypes.WinDLL("user32")
    u.CreateWindowExW.argtypes = [wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD, ctypes.c_int, ctypes.c_int,
                                  ctypes.c_int, ctypes.c_int, wt.HWND, wt.HMENU, wt.HINSTANCE, wt.LPVOID]
    u.CreateWindowExW.restype = wt.HWND
    u.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]
    u.DestroyWindow.argtypes = [wt.HWND]
    hwnd = u.CreateWindowExW(0, "STATIC", "Fresing icon test", 0x00CF0000, 10, 10, 300, 200, None, None, None, None)
    check("test window made", hwnd)
    if hwnd:
        try:
            u.ShowWindow(hwnd, 4)                                   # SW_SHOWNOACTIVATE
            check("own_windows finds it", hwnd in ai.own_windows(), ai.own_windows())
            h = ai.set_window_icon(hwnd, icon, relaunch=ai.relaunch_command(exe))
            check("window icon (big) = the Fresing icon", h["big"] and ai.window_icon(hwnd, True) == h["big"],
                  f'{ai.window_icon(hwnd, True)} vs {h["big"]}')
            check("window icon (small) = the Fresing icon", h["small"] and ai.window_icon(hwnd, False) == h["small"])
            check("window app ID", ai.window_app_id(hwnd) == ai.APP_ID, ai.window_app_id(hwnd))
        finally:
            u.DestroyWindow(hwnd)
    ai.set_process_app_id()
    check("process app ID", ai.process_app_id() == ai.APP_ID, ai.process_app_id())


try:
    main()
except Exception:  # noqa: BLE001
    check("no error", False, traceback.format_exc()[-1500:])
os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as fh:
    json.dump({"checks": CHECKS}, fh, indent=1)
print(f"RESULT {sum(c[1] for c in CHECKS)}/{len(CHECKS)} passed", flush=True)
sys.exit(0 if all(c[1] for c in CHECKS) else 1)
