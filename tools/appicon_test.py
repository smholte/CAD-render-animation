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


w = None


def module():
    import addon_utils
    name = next(m.__name__ for m in addon_utils.modules() if m.__name__.endswith("fresing_render"))
    return importlib.import_module(name + ".appicon")


def updates_restart(exe):
    import addon_utils
    name = next(m.__name__ for m in addon_utils.modules() if m.__name__.endswith("fresing_render"))
    return importlib.import_module(name + ".blender.updates").build_restart(exe, "fresing_render", "", True)


def main():
    global w
    ai = module()
    w = importlib.import_module(ai.__name__.rsplit(".", 1)[0] + ".winexe")
    exe = bpy.app.binary_path
    folder = ai.install_dir(exe)
    check("install folder found from blender.exe", folder, folder)
    desktop, programs, appdata = ai.known_folders()
    paths = ai.shortcut_paths(desktop, programs, appdata, ai.tools_dir(folder))
    check("shortcuts found", len(paths) >= 7, f"{len(paths)}: " + ", ".join(os.path.basename(p) for p in paths))
    before = {p: ai.read_shortcut(p) for p in paths}
    old = sorted({os.path.basename(p) for p, i in before.items()
                  if "blender.exe" in i["icon"].lower() and ai.is_inside(i["target"], folder)})
    check("an older install's shortcuts are there to refresh", old, ", ".join(old))

    # task 0212: an older install's extra Desktop shortcut (ours) and one with an old name that points elsewhere
    old_pc = os.path.join(desktop, "Fresing Render - PC check.lnk")
    foreign = os.path.join(desktop, "Fresing Render - PC check (heavy).lnk")
    notepad = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "notepad.exe")
    ai.make_shortcut(old_pc, w.console_exe(exe), "--background", os.path.dirname(exe), "", "old PC check")
    ai.make_shortcut(foreign, notepad, "", "", "", "someone else's")

    # task 0329: an install before 0329 has no "Uninstall Fresing Render" in the install folder / next to the app
    ia = importlib.import_module(ai.__name__.rsplit(".", 1)[0] + ".core.installed_apps")
    unlinks = ia.uninstall_shortcuts(folder, os.path.dirname(os.path.abspath(exe)))
    for p in unlinks:
        if os.path.isfile(p):
            os.remove(p)

    done = ai.refresh_installed(exe)
    check("refresh: an older install's extra Desktop shortcut removed", not os.path.isfile(old_pc), "; ".join(done))
    check("refresh: a shortcut with an old name that points elsewhere left alone",
          os.path.isfile(foreign) and ai.read_shortcut(foreign)["target"].lower() == notepad.lower())
    check("refresh: the Tools folder holds the six extras",
          sorted(n for n in os.listdir(ai.tools_dir(folder)) if n.endswith('.lnk')) == sorted(ai.TOOLS.values()),
          os.listdir(ai.tools_dir(folder)))
    check("refresh: the uninstaller and the Installed-apps entry are made (task 0265)",
          os.path.isfile(os.path.join(ai.tools_dir(folder), 'Uninstall-FresingRender.ps1')), "; ".join(done))
    check("refresh: icon copied into the install folder", os.path.isfile(os.path.join(folder, ai.ICON_FILE)))
    entry = ia.Registry().read() or {}
    check("refresh: two uninstall shortcuts to make (task 0329)", len(unlinks) == 2, unlinks)
    for p in unlinks:
        where = os.path.basename(os.path.dirname(p))
        if not os.path.isfile(p):
            check(f"refresh: {ia.UNINSTALL_LNK} made in {where}", False, "; ".join(done))
            continue
        info = ai.read_shortcut(p)
        cmd = "powershell.exe " + info["arguments"]
        # task 0339: the entry's command + -Ask (the shortcut asks Y/N first; Settings asks itself)
        check(f"refresh: {ia.UNINSTALL_LNK} in {where} runs the Installed-apps entry's command + -Ask",
              os.path.isfile(info["target"]) and os.path.basename(info["target"]).lower() == "powershell.exe"
              and cmd == (entry.get("UninstallString") or "") + ia.ASK, f"{info['target']} {info['arguments']}")
    check("refresh changed the older shortcuts", all(any(d.startswith(n + ":") for d in done) for n in old),
          "; ".join(done))
    icon = os.path.join(folder, ai.ICON_FILE)
    for p in paths:
        info = ai.read_shortcut(p)
        name = os.path.basename(p)
        if not ai.is_inside(before[p]["target"], folder):        # someone else's (the runner's pinned Edge)
            check(f"{name}: not ours, left as it was", info == before[p], info["icon"])
            continue
        check(f"{name}: Fresing icon", os.path.normcase(info["icon"]) == os.path.normcase(icon)
              and info["icon_index"] == 0, f'{info["icon"]},{info["icon_index"]}')
        if ai.is_app_shortcut(info["arguments"]):
            check(f"{name}: app ID", info["app_id"] == ai.APP_ID, info["app_id"])
            if name.lower() == ai.SAFE_START.lower():
                check(f"{name}: stays on blender-launcher.exe", info["target"].lower().endswith("blender-launcher.exe"),
                      info["target"])
            else:
                check(f"{name}: starts Fresing Render.exe", w.is_copy(info["target"]), info["target"])
        elif ai.is_inside(info["target"], folder) and info["target"].lower().endswith(".exe"):
            check(f"{name}: console run stays on blender.exe", os.path.basename(info["target"]).lower() == "blender.exe",
                  info["target"])
    again = ai.refresh_installed(exe)
    check("a second refresh writes nothing", not again, "; ".join(again))
    os.remove(foreign)

    # task 0177: the copy the refresh made
    copy = w.copy_path(exe)
    check("Fresing Render.exe made again by the app", os.path.isfile(copy) and w.usable(exe), copy)
    check("safe-start shortcut there (Tools folder)", os.path.isfile(os.path.join(ai.tools_dir(folder), ai.SAFE_START)))
    s = w.strings(w.parse_version(w.read_resource(copy, w.RT_VERSION, 1)))
    check("its version resource says Fresing Render", s.get("FileDescription") == "Fresing Render"
          and s.get("ProductName") == "Fresing Render" and s.get("OriginalFilename") == "blender.exe", s)
    with open(copy, "rb") as fh:
        head = bytearray(fh.read(4096))
    check("no console window (GUI subsystem)", w.subsystem(head) == 2, w.subsystem(head))
    with open(copy, "rb") as fh:
        whole = bytearray(fh.read())
    check("no signature left in it", w.signature(whole) == (0, 0), w.signature(whole))
    ok, said = w.answers(copy)
    check("it starts and says Blender", ok, said)
    check("restart after Update now starts it", updates_restart(exe)[0].lower() == copy.lower(), updates_restart(exe))
    check("the PC check's console run stays on blender.exe", w.console_exe(copy).lower() == exe.lower())

    # Smart App Control on (simulated): the copy is taken out of use, the shortcuts go back to Blender's launcher
    os.environ["FRESING_SAC"] = "1"
    try:
        ai.refresh_installed(exe)
        desk = os.path.join(desktop, "Fresing Render.lnk")
        t = ai.read_shortcut(desk)["target"]
        check("Smart App Control on: shortcut back on blender-launcher.exe", t.lower().endswith("blender-launcher.exe"), t)
        check("Smart App Control on: copy taken out of use", not os.path.isfile(copy) and not w.usable(exe))
    finally:
        del os.environ["FRESING_SAC"]
    ai.refresh_installed(exe)
    t = ai.read_shortcut(os.path.join(desktop, "Fresing Render.lnk"))["target"]
    check("Smart App Control off again: copy and shortcut back", w.is_copy(t) and w.usable(exe), t)

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
    memory_family(ai)


def memory_family(ai):
    """Task 0379 (Windows-only code of the Stress run's memory column): ``stress.family_memory_mb`` finds a child
    program of this one with Toolhelp, reads its working set, and stops counting it when it ends."""
    import subprocess
    import time
    base = ai.__name__.rsplit(".", 1)[0]
    stress = importlib.import_module(base + ".pccheck.stress")
    runner = importlib.import_module(base + ".importer.runner")
    own0, helpers0, count0 = stress.family_memory_mb()
    check("memory: this program's own size is read", own0 > 20, f"{own0:.0f} MB")
    code = ("import time\nb = bytearray(200 * 2**20)\n"
            "for i in range(0, len(b), 4096): b[i] = 1\n"
            "print('up', flush=True)\ntime.sleep(120)\n")
    child = subprocess.Popen([runner.python_executable(), "-c", code], stdout=subprocess.PIPE, text=True,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    try:
        said = child.stdout.readline().strip()
        check("memory: the helper program holds its 200 MB", said == "up", said)
        own, helpers, count = stress.family_memory_mb()
        check("memory: a child program is counted with its working set", helpers - helpers0 >= 150 and count > count0,
              f"helpers {helpers0:.0f} -> {helpers:.0f} MB, {count0} -> {count} programs")
        with stress.MemoryWatch(every=0.05) as watch:
            time.sleep(0.4)
        check("memory: the watch keeps the peak of the sum with its two parts",
              watch.helpers_seen and watch.peak_total >= watch.peak + 150 and watch.at_peak[1] >= 150
              and watch.most_helpers >= 1, f"{watch.metrics()}")
    finally:
        child.kill()
        child.wait()
    time.sleep(0.3)
    gone = stress.family_memory_mb()
    check("memory: an ended child program is not counted any more", gone[1] < helpers0 + 100 and gone[2] <= count0,
          f"{gone[1]:.0f} MB, {gone[2]} programs")


try:
    main()
except Exception:  # noqa: BLE001
    check("no error", False, traceback.format_exc()[-1500:])
os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as fh:
    json.dump({"checks": CHECKS}, fh, indent=1)
print(f"RESULT {sum(c[1] for c in CHECKS)}/{len(CHECKS)} passed", flush=True)
sys.exit(0 if all(c[1] for c in CHECKS) else 1)
