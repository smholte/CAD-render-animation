"""Start ``make.py`` as its own program (task 0204): ``python run.py <out> --params <spec.json> --progress <p.json>``.

The extension is imported as a package from its own folder (in Blender it is ``bl_ext.<repo>.fresing_render``; here
it is the folder's own name), so the maker's relative imports (``..demo_model``, ``..core``) work without Blender.
"""

import importlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG_DIR = os.path.dirname(HERE)


def main() -> int:
    sys.path.insert(0, os.path.dirname(PKG_DIR))
    make = importlib.import_module(os.path.basename(PKG_DIR) + ".lifting_model.make")
    return make.main(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
