"""Write the made-up Fresing assets test pack (task 0354) – the command line of
``fresing_render/pccheck/assets_test_pack.make`` (no second copy of the maker).

    ~/venv/bin/python tools/make_test_assets_pack.py <folder> [--version 1.0.0|1.1.0] [--app-min 0.0.1] [--app-max ""]
    blender -b --factory-startup --python tools/make_test_assets_pack.py -- <folder> [--version 1.1.0]

``<folder>`` is the pack folder itself (it will hold ``pack.json``); an earlier test pack there is replaced. The pack is
never committed: tests and the PC check make it when they need it.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fresing_render.pccheck import assets_test_pack  # noqa: E402


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--" in argv:                           # inside Blender: only what follows "--"
        argv = argv[argv.index("--") + 1:]
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("folder")
    ap.add_argument("--version", default="1.0.0", choices=assets_test_pack.VERSIONS)
    ap.add_argument("--app-min", default="0.0.1")
    ap.add_argument("--app-max", default="")
    a = ap.parse_args(argv)
    got = assets_test_pack.make(a.folder, a.version, a.app_min, a.app_max)
    print(f"test pack {a.version}: {got['files']} files, {got['bytes'] / 1e6:.2f} MB, {got['seconds']} s "
          f"-> {got['folder']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
