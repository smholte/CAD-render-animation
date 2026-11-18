"""The by-names driver of Set up a crane lives in the app (``fresing_render/blender/crane_example.py``: the tour and
the PC check use it too); the tests import it from here."""

from fresing_render.blender.crane_example import *  # noqa: F401,F403
from fresing_render.blender.crane_example import _role, builtin, chart_csv, compare, rig  # noqa: F401
