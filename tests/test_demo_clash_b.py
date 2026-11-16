"""Task 0145: the second part of the demo project's clash check (``tests/test_demo_clash.py``: the first part, the proof
that the windows of both parts follow on each other, and how the windows are as strict as one whole check).

The check had grown to ~14 min on GitHub in one job, about 5 of them this process building and reading the animation
before the workers could start; the two parts run in two jobs at once, each with the made demo project
(``tests/demo_made.py``) and four workers.
"""

import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

bpy = pytest.importorskip("bpy")
pytest.importorskip("OCP")

import demo_made  # noqa: E402,F401  (the made demo project, shared: tests/demo_made.py)
from test_demo_clash import addon, check_part, made  # noqa: E402,F401  (addon: autouse)


def test_no_clash_in_the_animation_part_2(made, tmp_path):  # noqa: F811
    """The clash check over the whole animation: 0 rows – its second part (the odd windows)."""
    check_part(made, tmp_path, 1)
