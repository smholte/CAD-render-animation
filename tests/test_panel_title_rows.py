"""Task 0335 (0328 row 17): every part of a panel's title row opens / folds it - the icon, the title, the state."""
import pytest

pytest.importorskip("bpy")

from fresing_render.blender import panels  # noqa: E402


class Rec:
    """A layout that records what is drawn into it."""

    def __init__(self, log, kind="row"):
        object.__setattr__(self, "log", log)

    def row(self, *a, **k):
        return Rec(self.log)

    box = column = row

    def label(self, *a, **k):
        self.log.append(("label", k))

    def operator(self, idname, **k):
        self.log.append(("operator", idname, k))
        return type("Op", (), {})()

    def separator(self, **k):
        pass

    def __setattr__(self, k, v):
        pass




def test_icon_and_state_labels_become_toggles():
    log = []
    t = panels._Toggling(Rec(log), "FRESING_PT_looks", False)
    t.label(icon="BRUSH_DATA")                       # a header's icon
    t.row(align=True).label(text="3 removed", icon="NONE")      # header_status's label
    t.label(text="x", icon_value=5)                  # the lesson marker keeps being a label
    assert [e[0] for e in log] == ["operator", "operator", "label"]
    assert log[0][1] == "fresing.panel_toggle" and log[0][2]["icon"] == "BRUSH_DATA" and log[0][2]["emboss"] is False
    assert log[1][2]["text"] == "3 removed"


def test_the_tabs_own_section_keeps_plain_labels():
    log = []
    t = panels._Toggling(Rec(log), "FRESING_PT_looks", True)
    t.label(icon="BRUSH_DATA")
    assert log[0][0] == "label"
