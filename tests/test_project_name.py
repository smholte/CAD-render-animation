"""Task 0291: the project-name rule (core/project_name.py), no Blender."""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fresing_render.core import project_name as P  # noqa: E402


@pytest.mark.parametrize("raw, want", [
    ("Test crane", "Test crane"),
    ("Crane v8", "Crane"),                       # Inventor's version
    ("Crane V12", "Crane"),
    ("Crane v8.iam", "Crane"),
    ("Crane.iam:1", "Crane"),                    # an occurrence number
    ("Crane v8.iam:1.001", "Crane"),             # Blender's .001 too
    ("Gearbox.STEP", "Gearbox"),
    ("frame.stp", "frame"),
    ("Mill.blend", "Mill"),
    ("Server v2 rack", "Server v2 rack"),        # a "v2" inside the name stays
    ("Valve 3/4\" <DN20>", "Valve 3_4_ _DN20_"),  # characters Windows does not allow
    ("a:b|c?d*e", "a_b_c_d_e"),
    ("tab\there", "tab_here"),
    ("  lots   of   space  ", "lots of space"),
    ("dots at the end...", "dots at the end"),
    ("CON", "CON_"),                             # names Windows keeps for itself
    ("aux.x", "aux_.x"),
    ("COM1", "COM1_"),
    ("Concrete", "Concrete"),
    ("", ""),
    ("???", ""),
    (".stp", "stp"),
    (".hidden", "hidden"),
    ("Hus é ø", "Hus é ø"),
])
def test_clean(raw, want):
    assert P.clean(raw) == want


def test_clean_is_short_enough():
    assert len(P.clean("x" * 500)) == P.MAX_LEN


def test_proposal_and_the_setting():
    assert P.proposal("Crane v8") == "Crane"
    assert P.proposal("") == P.UNTITLED == "Untitled project"     # nothing imported yet
    assert P.proposal("???") == P.UNTITLED
    assert P.proposal("Crane", "empty") == ""                       # Settings > General: Leave empty
    assert P.proposal("", "empty") == ""
    assert P.DEFAULT_MODE == "model" and set(P.MODES) == {"model", "empty"}


@pytest.mark.parametrize("stem, taken, want", [
    ("Crane", [], "Crane (1)"),
    ("Crane", ["Crane.blend", "Crane (1).blend"], "Crane (2)"),
    ("Crane", ["crane (1).BLEND", "Crane (2).blend"], "Crane (3)"),          # no case, as on Windows
    ("Crane", ["Crane (2).blend"], "Crane (1)"),                              # the first free one
    ("Crane (1)", ["Crane (1).blend"], "Crane (2)"),                         # past an existing (1)
    ("Crane (1)", ["Crane (1).blend", "Crane (2).blend", "Crane (3).blend"], "Crane (4)"),
    ("Crane (7)", [], "Crane (8)"),
    ("Crane (1) (2)", [], "Crane (1) (3)"),
    ("(3)", [], "(3) (1)"),                                                  # nothing before the number
    ("Crane (1).blend1", ["Crane (1).blend"], "Crane (1).blend1 (1)"),
    ("Crane", ["Crane (1).blend1", "Crane (1)"], "Crane (1)"),               # only .blend files count
])
def test_next_free(stem, taken, want):
    assert P.next_free(stem, taken) == want


def test_next_free_in_a_folder(tmp_path):
    for n in ("Crane é.blend", "Crane é (1).blend", "notes.txt"):
        (tmp_path / n).write_bytes(b"x")
    assert P.next_free_in(str(tmp_path), "Crane é") == "Crane é (2)"
    assert P.next_free_in(str(tmp_path / "missing"), "Crane") == "Crane (1)"


def test_file_names_and_typed_names():
    assert P.stem_of(os.path.join("C:", "jobs", "Crane.blend")) == "Crane"
    assert P.stem_of("Crane.BLEND") == "Crane"
    assert P.file_name("Crane (1)") == "Crane (1).blend"
    assert P.file_name("Crane.blend") == "Crane.blend"
    assert P.file_name("  ") == ""
    assert P.typed_problem("Crane (1)") == ""
    assert P.typed_problem("Crane (1).blend") == ""
    assert P.typed_problem("") != "" and P.typed_problem("   ") != ""
    assert "/" in P.typed_problem("a/b")
    assert P.typed_problem("name.") != "" and P.typed_problem("name ") == ""     # (a space at the end is dropped)
    assert "Windows" in P.typed_problem("nul")
