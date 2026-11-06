"""Starts the PC check: ``blender --background --python launcher.py -- [Desktop] [quick|full] [model.step]``

The Start-menu shortcuts "Fresing Render - PC check (quick)" / "(full)" point here (the file inside the
installed extension, so an update brings the new version along), and so does Help > Fresing Render PC
check… in the app. A STEP file dropped on a shortcut is added at the end of the command line by Windows.
"""

import importlib
import sys


def main() -> None:
    import addon_utils
    for mod in addon_utils.modules():
        if mod.__name__ == "fresing_render" or mod.__name__.endswith(".fresing_render"):
            addon_utils.enable(mod.__name__, default_set=True)
            importlib.import_module(mod.__name__ + ".pccheck.runner").run_from_argv(sys.argv)
            return
    print("Fresing Render is not installed in this Blender: run Install.bat again")


if __name__ == "__main__":
    main()
