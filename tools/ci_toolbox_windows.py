"""The Toolbox folder on Windows (task 0217), run by tools/ci_windows_install.ps1 with the INSTALLED app's Blender:

    blender.exe --background --python-exit-code 1 --python tools/ci_toolbox_windows.py -- <expected Toolbox folder>

What only Windows can show: the folder found under %USERPROFILE% (a user folder with a space and an accent), the
manifest the installer wrote, a file still short not read early, a status write while another handle holds
status.json open (Windows refuses the replace) tried again at the next look instead of crashing, a delete refused
while a file is open tried again, and a junction in the inbox never followed. Prints one line per check; exits 1 when
one fails. Works in a folder of its own inside the Toolbox folder's inbox and removes its jobs again.
"""

import json
import os
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

import addon_utils

mod = next((m for m in addon_utils.modules() if m.__name__.endswith("fresing_render")), None)
if mod is None:
    sys.exit("Fresing Render is not installed in this Blender")
import importlib  # noqa: E402

tb = importlib.import_module(mod.__name__ + ".core.toolbox")
DATA = Path(mod.__file__).parent / "data"
want = Path(sys.argv[sys.argv.index("--") + 1]) if "--" in sys.argv else None
FAILED = []


def check(name, ok, detail=""):
    print(f"TOOLBOX {'OK  ' if ok else 'FAIL'} {name}" + (f" ({detail})" if detail else ""))
    if not ok:
        FAILED.append(name)


def status(root, jid):
    return json.loads((root / "tools" / tb.ME / "inbox" / jid / "status.json").read_text("utf-8"))


try:
    root = tb.home()
    check("the folder is %USERPROFILE%\\Toolbox (a user folder with a space and an accent)", want is None or os.path.normcase(str(root)) == os.path.normcase(str(want)),
          str(root))
    import bpy
    from importlib import import_module
    ver = import_module(mod.__name__).__version__
    exe = import_module(mod.__name__ + ".winexe").app_exe(bpy.app.binary_path)
    man = tb.install(root, ver, exe, ["--app-template", "fresing_render"])   # as the app does at its start
    doc = tb.read_doc(man, "tool")
    prog = doc.get("start", {}).get("program", "")
    check("start is what the shortcut starts", prog.lower().endswith(("fresing render.exe", "blender-launcher.exe")), prog)
    check("toolbox-folder.json", (root / "toolbox-folder.json").is_file())

    ib = tb.Inbox(root, doc["app_version"], keep_dir=root.parent / "Toolbox kept (ci)")
    check("the inbox starts", ib.start(), ib.problem)
    house = DATA / "sample-house.hpscene"
    data = house.read_bytes()

    # a file still short is not read early
    jid = tb.play_house_planner(root, house, "CI – short file")
    f = root / "tools" / tb.ME / "inbox" / jid / house.name
    f.write_bytes(data[:200])
    ib.look()
    check("a short file is not read early", not (f.parent / "status.json").exists())
    f.write_bytes(data)
    ib.look()
    check("once whole it waits for Bake now", status(root, jid)["state"] == "waiting")

    # Windows refuses to replace status.json while another handle has it open: tried again at the next look
    sp = f.parent / "status.json"
    holder = open(sp, "rb")
    try:
        why = ib.begin(jid, "Importing the house")
        refused = status(root, jid)["state"] == "waiting"
        check("begin with status.json held open does not crash", why == "", why)
        ib.look()
    finally:
        holder.close()
    ib.look()
    check("the refused status write was done at the next look", status(root, jid)["state"] == "working",
          f"refused at first: {refused}")

    # a delete refused while the file is open is tried again
    holder = open(f, "rb")
    try:
        ib.finish(jid, "cancelled", "CI: cancelled")
        held = f.exists()
    finally:
        holder.close()
    ib.look()
    check("the job's file goes once it is let go", not f.exists(), f"kept while open: {held}")
    check("the final status is there", status(root, jid)["state"] == "cancelled")

    # a junction in the inbox, and one inside a finished job, are never followed nor deleted through
    outside = root.parent / "Toolbox outside (ci)"
    junction = root / "tools" / tb.ME / "inbox" / "20261118-000000-junction"
    inner = f.parent / "inner"
    try:
        outside.mkdir(exist_ok=True)
        (outside / "keep.txt").write_text("keep")
        for j in (junction, inner):
            subprocess.run(["cmd", "/d", "/c", "mklink", "/J", str(j), str(outside)], check=False, capture_output=True)
        check("the junctions were made", junction.exists() and inner.exists())
        check("a junction is seen as a link", tb.is_link(junction) and tb.is_link(inner))
        ib.clean(at=tb.time.time() + 40 * tb.DAY)
        check("cleaning up does not go through a junction", (outside / "keep.txt").is_file())
        check("a finished job holding a junction is left, not emptied through it", inner.exists())
    finally:
        for j in (junction, inner):
            if tb.is_link(j):
                os.rmdir(j)                       # removes the junction itself, never its target
        shutil.rmtree(outside, ignore_errors=True)
        shutil.rmtree(root / "tools" / tb.ME / "inbox" / jid, ignore_errors=True)
        shutil.rmtree(root.parent / "Toolbox kept (ci)", ignore_errors=True)
except Exception:  # noqa: BLE001
    traceback.print_exc()
    FAILED.append("crashed")

print(f"TOOLBOX checks: {len(FAILED)} failed")
sys.exit(1 if FAILED else 0)
