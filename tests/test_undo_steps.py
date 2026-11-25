"""Task 0334: Ctrl+Z undoes one action – every operator of ops_main.py that writes scene data has UNDO."""
import ast
import pathlib

from fresing_render.core import words

# Operators that write nothing into the scene (files, windows, the folder, a modal that other code undoes).
NO_SCENE_WRITE = {"tree_refresh", "template_export", "preview", "render", "open_folder"}
# Known gaps in files other tasks run in (0334 does not change them): rule_set_delete / rule_set_default
# (ops_rule_sets.py: library file / preferences, no scene data).


def _ops(path):
    tree = ast.parse(pathlib.Path(path).read_text())
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name.startswith("FRESING_OT_"):
            src = ast.unparse(node)
            yield node.name[len("FRESING_OT_"):], '"UNDO"' in src.replace("'", '"')


def test_ops_main_operators_that_write_have_undo():
    missing = [n for n, undo in _ops("fresing_render/blender/ops_main.py") if not undo and n not in NO_SCENE_WRITE]
    assert missing == []


def test_triangle_words():
    assert words.triangles(4200) == "4,200 triangles"
    assert words.triangles(1) == "1 triangle"
    assert words.triangles(1_400_000) == "1.4 M triangles"
