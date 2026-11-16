"""Moved to ``fresing_render/demo_model/turbine_parts.py`` (task 0166): the demo project's wind park uses it too, and the demo's
maker ships with the extension (``tools/`` does not). This name stays for the site's converter and its tests: it IS
that module (the same object in ``sys.modules``), so nothing changes for them."""

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from fresing_render.demo_model import turbine_parts as _moved  # noqa: E402

sys.modules[__name__] = _moved
