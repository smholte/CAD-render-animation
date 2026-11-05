"""Install the extension the way users get it, but on Linux, and run the self-test.

This checks the packaging itself: manifest, bundled wheels, extension module
paths (bl_ext.<repo>.fresing_render), the importer subprocess finding OpenCascade
from the installed wheels, and the self-test.

    BLENDER_USER_RESOURCES=/tmp/fr_user python tools/test_install_linux.py <linux wheels dir> [report.txt]

Without a graphics card the "graphics card" lines fail, unless FRESING_SELFTEST_NO_GPU=1 is
set (the automatic tests on GitHub do that); then they say "skipped: no graphics card".
"""

import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def build_linux_zip(wheel_dir: str, out_dir: str, blender: str | None = None) -> str:
    """Build the extension zip with Linux wheels. With `blender` (path of a real Blender
    program) the zip is built by that Blender, otherwise by the bpy module's blender_ext.py."""
    stage = os.path.join(out_dir, "fresing_render")
    shutil.copytree(os.path.join(ROOT, "fresing_render"), stage, ignore=shutil.ignore_patterns("__pycache__"))
    os.makedirs(os.path.join(stage, "wheels"))
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import build_guide                                     # the guide ships inside the extension
    build_guide.build(os.path.join(stage, "guide", build_guide.GUIDE_FILE))
    names = []
    for whl in glob.glob(os.path.join(wheel_dir, "*.whl")):
        shutil.copy2(whl, os.path.join(stage, "wheels"))
        names.append(f'"./wheels/{os.path.basename(whl)}"')
    man = open(os.path.join(stage, "blender_manifest.toml"), encoding="utf-8").read()
    man = man.replace('platforms = ["windows-x64"]', 'platforms = ["linux-x64"]')
    man = re.sub(r"wheels = \[[^\]]*\]", "wheels = [" + ", ".join(names) + "]", man, flags=re.S)
    open(os.path.join(stage, "blender_manifest.toml"), "w", encoding="utf-8").write(man)
    if blender:
        subprocess.check_call([blender, "--factory-startup", "--command", "extension", "build",
                               "--source-dir", stage, "--output-dir", out_dir])
    else:
        import importlib.util
        base = list(importlib.util.find_spec("bpy").submodule_search_locations)[0]
        tool = glob.glob(os.path.join(base, "*", "scripts", "addons_core", "bl_pkg", "cli", "blender_ext.py"))[0]
        subprocess.check_call([sys.executable, tool, "build", "--source-dir", stage, "--output-dir", out_dir])
    return glob.glob(os.path.join(out_dir, "fresing_render-*.zip"))[0]


def main():
    wheel_dir = sys.argv[1]
    tmp = tempfile.mkdtemp(prefix="fr_build_")
    zip_path = build_linux_zip(wheel_dir, tmp)
    print("built", zip_path)

    import importlib

    import bpy
    import addon_utils
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    res = bpy.ops.extensions.package_install_files(filepath=zip_path, repo="user_default", enable_on_install=True)
    print("install:", res)
    mods = [m.__name__ for m in addon_utils.modules() if m.__name__.endswith("fresing_render")]
    print("installed module:", mods)
    assert mods and mods[0].startswith("bl_ext."), mods
    pkg_dir = os.path.dirname(importlib.import_module(mods[0]).__file__)
    guide = os.path.join(pkg_dir, "guide", "user_guide.html")
    assert os.path.isfile(guide), "user guide missing in the installed extension"
    print("user guide:", guide, f"({os.path.getsize(guide) / 1e6:.1f} MB)")
    st = importlib.import_module(mods[0] + ".selftest")
    report = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else os.path.join(tmp, "report.txt")
    os.makedirs(os.path.dirname(report), exist_ok=True)
    ok = st.main(report_path=report)
    print(open(report, encoding="utf-8").read())
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
