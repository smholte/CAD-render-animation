"""Task 0373: the guide-picture tool refuses a blank picture or one of Blender's own tab (no Fresing panel drawn)."""
import ast
import os

import numpy as np

SRC = os.path.join(os.path.dirname(__file__), "..", "tools", "guide_screens.py")


def _check():
    tree = ast.parse(open(SRC, encoding="utf-8").read())
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "picture_problem")
    ns: dict = {}
    exec(compile(ast.Module([fn], []), SRC, "exec"), ns)
    return ns["picture_problem"]


def _panel(h=300, w=300):
    im = np.full((h, w, 3), 60, np.uint8)
    for y in range(10, h - 20, 40):                 # rows of labels and buttons
        im[y:y + 14, 20:w - 20] = 120
    return im


def test_a_drawn_panel_passes():
    assert _check()(_panel(), 3) == ""


def test_nothing_drawn_is_refused():
    assert "Item tab" in _check()(_panel(), 0)


def test_a_blank_picture_is_refused():
    assert _check()(np.full((300, 300, 3), 60, np.uint8), 1)


def test_a_tiny_picture_is_refused():
    assert "px" in _check()(_panel(20, 100), 1)


def test_start_code_sets_the_workspace_itself():
    src = open(SRC, encoding="utf-8").read()
    assert "def all_functions" in src and src.count("all_functions()") >= 3
