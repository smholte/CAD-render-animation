"""Installs the extension + app template into a settings folder, for local guide pictures (task 0031).

    ~/venv/bin/python tools/web_install_app.py [--user ~/fr_user]
then use BLENDER_USER_RESOURCES=~/fr_user with tools/guide_screens.py (see its docstring). Needs the set-up of
tools/web_setup.sh (Blender in ~/blender-<ver>, wheels in ~/linux-wheels)."""
import argparse
import glob
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ci_real_app  # noqa: E402

home = os.path.expanduser("~")
ap = argparse.ArgumentParser()
ap.add_argument("--user", default=os.path.join(home, "fr_user"))
ap.add_argument("--blender", default=(glob.glob(os.path.join(home, "blender-*", "blender-*-linux-x64", "blender")) or [""])[0])
ap.add_argument("--wheels", default=os.path.join(home, "linux-wheels"))
a = ap.parse_args()
os.makedirs(a.user, exist_ok=True)
ci_real_app.install(a.blender, a.wheels, a.user, tempfile.mkdtemp())
print("installed in", a.user)
