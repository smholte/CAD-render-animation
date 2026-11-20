"""Start a demo kit's model maker as its own program (task 0228; ``blender/demo.py`` ``_run_kit_maker``).

    python demo_kit_run.py <kit folder> <maker module> <model folder> [--small] [--progress <file.json>]

Runs with Blender's Python (no bpy), like the app's own ``demo_model/make.py``. Puts the kit's folder on ``sys.path``,
makes the app importable as ``fresing_app`` (the folder this file lies in, two levels up, whatever its name), then runs
``<maker module>`` as ``__main__`` with the remaining arguments. See ``core/demo_kits.py``.
"""

from __future__ import annotations

import os
import runpy
import sys


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    kit_folder, maker, rest = argv[0], argv[1], argv[2:]
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, os.path.dirname(app_dir))
    sys.path.insert(0, os.path.abspath(kit_folder))
    import importlib
    app = importlib.import_module(os.path.basename(app_dir))
    demo_kits = importlib.import_module(app.__name__ + ".core.demo_kits")
    sys.meta_path.insert(0, demo_kits._Alias(demo_kits.ALIAS, app.__name__))
    sys.argv = [maker] + rest
    runpy.run_module(maker, run_name="__main__", alter_sys=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
