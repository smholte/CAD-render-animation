"""The lesson highlight (blender/highlight.py, task 0062): what it reads from the side panel's pixels (made-up
pictures), what ``point`` / ``clear`` do to the panels, the fold hook, looks and colour. The looks themselves are
seen in the real app: tools/ui_test_highlight.py."""

import math
import os
import types

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")

import fresing_render  # noqa: E402
from fresing_render.blender import highlight as hl  # noqa: E402
from fresing_render.blender import ui  # noqa: E402
from fresing_render.core import functions  # noqa: E402

GROUND = (48, 48, 48)               # a panel
BUTTON = (84, 84, 84)
LINE = (40, 40, 40)                 # the one-pixel line between two joined buttons
TEXT = (230, 230, 230)


# ---------------------------------------------------------------------------
# made-up pictures of a side panel (pixels[y, x] = r, g, b, a; y up)
# ---------------------------------------------------------------------------

def canvas(h=200, w=300, colour=GROUND):
    px = np.empty((h, w, 4), np.uint8)
    px[:, :, :3] = colour
    px[:, :, 3] = 255
    return px


def rect(px, box, colour):
    x0, y0, x1, y1 = box
    px[y0:y1 + 1, x0:x1 + 1, :3] = colour


def icon(px, x, y, kind="button", size=12):
    """A marker icon with its lower left corner at (x, y); returns its rectangle."""
    box = (x, y, x + size - 1, y + size - 1)
    rect(px, box, hl.MARKS[kind])
    return box


def text(px, x0, x1, y0, y1):
    px[y0:y1 + 1, x0:x1 + 1:3, :3] = TEXT           # stripes: pixels of another colour, as letters are


def test_a_single_button_is_found_by_its_own_edges():
    px = canvas()
    box = (20, 80, 250, 99)
    rect(px, box, BUTTON)
    mark = icon(px, 60, 84)
    text(px, 80, 200, 84, 95)                       # its label, with descenders below the icon's lowest row
    text(px, 80, 200, 83, 83)                       # (the row walked is the second above the bottom edge)
    assert hl.find_marks(px, hl.MARKS["button"]) == [mark]
    assert hl.button_box(px, mark) == box
    seen = hl.locate(px)
    assert seen["mark"] == mark and seen["button"] == box and seen["own"] == BUTTON
    assert seen["header"] is None and seen["bands"] == []


def test_of_a_joined_pair_only_the_target_is_marked():
    for target in (0, 1):
        px = canvas()
        left, right = (20, 80, 134, 99), (136, 80, 250, 99)
        rect(px, left, BUTTON)
        rect(px, right, BUTTON)
        rect(px, (135, 80, 135, 99), LINE)          # joined buttons: one pixel between them
        mine = (left, right)[target]
        mark = icon(px, mine[0] + 8, 84)
        text(px, mine[0] + 30, mine[2] - 10, 85, 94)
        assert hl.locate(px)["button"] == mine, f"target {target}"


def test_round_corners_do_not_shorten_the_button():
    px = canvas()
    box = (20, 80, 250, 103)
    rect(px, box, BUTTON)
    for r, cut in enumerate((4, 2, 1, 1)):          # corners cut away as a round button's are
        for y in (box[1] + r, box[3] - r):
            px[y, box[0]:box[0] + cut, :3] = GROUND
            px[y, box[2] - cut + 1:box[2] + 1, :3] = GROUND
    mark = icon(px, 40, 86)
    assert hl.button_box(px, mark) == box


def test_a_marker_without_a_button_round_it_gives_the_icons_place():
    px = canvas()
    mark = icon(px, 40, 90)                         # on the bare panel: no frame (emboss off)
    x0, y0, x1, y1 = hl.button_box(px, mark)
    assert x0 <= mark[0] and y0 <= mark[1] and y1 >= mark[3] and x1 > mark[2]
    assert y1 - y0 < 3 * 12 and x1 - x0 < 150, "not the whole panel"


def test_marker_colours_are_found_exactly_enough():
    px = canvas()
    rect(px, (30, 50, 41, 61), (250, 5, 252))       # nearly the button marker's colour: a marker
    rect(px, (30, 100, 41, 111), (255, 0, 200))     # another pink: not one
    rect(px, (100, 150, 101, 151), hl.MARKS["button"])      # four pixels: too few to be an icon
    assert hl.find_marks(px, hl.MARKS["button"]) == [(30, 50, 41, 61)]
    assert hl.find_marks(px, hl.MARKS["header"]) == []
    for a in hl.MARKS.values():                     # every marker colour is told from every other
        assert 0 in a and set(a) <= {0, 255}
        assert sum(1 for b in hl.MARKS.values() if b == a) == 1


def test_a_greyed_out_button_is_found_too():
    px = canvas()
    box = (20, 80, 134, 99)
    rect(px, box, (73, 73, 73))
    mark = (28, 84, 39, 95)
    rect(px, mark, (118, 55, 118))                  # the marker at a quarter strength over the button (measured)
    assert hl.find_marks(px, hl.MARKS["button"]) == []
    assert hl.find_marks(px, hl.MARKS["button"], greyed=True) == [mark]
    assert hl.locate(px)["button"] == box
    rect(px, (200, 20, 230, 40), (71, 114, 179))    # Blender's blue and a paint's orange are no markers
    rect(px, (200, 50, 230, 70), (249, 168, 0))
    assert hl.find_marks(px, hl.MARKS["button"], greyed=True) == [mark]
    assert hl.find_marks(px, hl.MARKS["field"], greyed=True) == []


def test_the_lowest_marked_header_is_the_one_shown():
    px = canvas(h=240)
    top, low = (8, 190, 260, 213), (8, 120, 260, 143)
    rect(px, top, (60, 60, 60))
    rect(px, low, (60, 60, 60))
    m_top, m_low = icon(px, 30, 197, "header", 10), icon(px, 50, 127, "header", 10)
    assert hl.find_marks(px, hl.MARKS["header"]) == [m_top, m_low]          # the highest first
    seen = hl.locate(px)
    assert seen["hmark"] == m_low and seen["header"] == low
    assert seen["button"] is None and sorted(seen["cover"]) == sorted([m_top, m_low])
    assert hl.header_box(px, m_top) == top


def test_a_setting_is_boxed_right_of_its_marker():
    px = canvas(w=300)
    rect(px, (270, 0, 299, 199), (30, 30, 30))      # the tabs at the side panel's edge: not part of the row
    mark = icon(px, 20, 84, "field")
    field = (120, 80, 250, 99)
    rect(px, field, (29, 29, 29))
    text(px, 50, 110, 86, 93)                       # the setting's name left of its field
    box = hl.field_box(px, mark)
    assert box[0] == mark[2] + 3 and box[2] == field[2]
    assert box[1] <= mark[1] - 2 and box[3] >= mark[3] + 2 and box[3] - box[1] < 24
    seen = hl.locate(px, "field")
    assert seen["button"] == box and seen["own"] == (29, 29, 29)    # the colour most of it has: the field's
    assert hl.locate(px, "button")["button"] is None and hl.locate(px, "")["button"] is None


def test_kept_clear_panels_are_bands_from_header_to_last_row():
    px = canvas(h=400)
    head_a, head_b = (8, 340, 260, 363), (8, 200, 260, 223)
    rect(px, head_a, (60, 60, 60))
    rect(px, head_b, (60, 60, 60))
    icon(px, 30, 347, "top", 10)
    icon(px, 30, 207, "top", 10)
    end_a = icon(px, 20, 262, "end", 8)             # panel A is open: its last row
    assert hl.locate(px)["bands"] == []             # not asked for
    bands = hl.locate(px, clear=True)["bands"]
    assert len(bands) == 2
    assert bands[0][1] >= head_a[3] and bands[0][0] <= end_a[1]             # A: header down to its last row
    assert bands[1][1] >= head_b[3] and head_b[1] - 4 <= bands[1][0] <= head_b[1]       # B is folded: its header
    assert len(hl.locate(px, clear=True)["cover"]) == 3


def test_dim_rects_cover_everything_but_the_holes():
    rw, rh = 60, 50
    holes = [(10, 20, 30, 30), (0, 35, 60, 45), (25, 25, 40, 40)]
    grid = np.zeros((rh, rw), int)
    for x0, y0, x1, y1 in hl.dim_rects(rw, rh, holes):
        assert 0 <= x0 < x1 <= rw and 0 <= y0 < y1 <= rh
        grid[int(y0):int(y1), int(x0):int(x1)] += 1
    want = np.ones((rh, rw), int)
    for x0, y0, x1, y1 in holes:
        want[y0:y1, x0:x1] = 0
    assert (grid == want).all(), "each pixel outside the holes once, none inside"
    assert sum((x1 - x0) * (y1 - y0) for x0, y0, x1, y1 in hl.dim_rects(rw, rh, [])) == rw * rh


def test_look_d_tints_the_button_not_its_label():
    px = canvas()
    box = (20, 80, 250, 99)
    rect(px, box, BUTTON)
    mark = icon(px, 60, 84)
    px[86:94, 100:160, :3] = TEXT
    a = hl.tint_mask(px, box, mark, BUTTON)
    assert a.shape == (20, 231)
    assert a[10, 5] == 1.0 and a[2, 200] == 1.0                     # the button's own colour
    assert (a[86 - 80:94 - 80, 100 - 20:160 - 20] == 0.0).all()     # its label
    assert (a[84 - 80:96 - 80, 60 - 20:72 - 20] == 1.0).all()       # the marker's place is painted over and tinted
    px[80, 20, :3] = GROUND                                         # a round corner: the panel shows
    assert hl.tint_mask(px, box, mark, BUTTON)[0, 0] == 0.0


# ---------------------------------------------------------------------------
# looks, colour, breath (no panels needed)
# ---------------------------------------------------------------------------

def test_exactly_six_looks_with_the_owners_defaults():
    assert {k: list(v) for k, v in hl.LOOKS.items()} == {"button": ["C", "D"], "section": ["5", "4"],
                                                         "part": ["3", "1"]}
    assert set(hl._BUTTON) == {"C", "D"} and set(hl._SECTION) == {"5", "4"} and set(hl._PART) == {"3", "1"}


def test_set_look_and_colour():
    try:
        assert (hl.look("button"), hl.look("section"), hl.look("part")) == ("C", "5", "3")
        hl.set_look("button", "D")
        hl.set_look("section", "4")
        hl.set_look("part", "1")
        assert (hl.look("button"), hl.look("section"), hl.look("part")) == ("D", "4", "1")
        hl.set_look("button", "")
        assert hl.look("button") == "C"
        for kind, key in (("button", "A"), ("section", "1"), ("part", "2"), ("card", "1")):
            with pytest.raises(KeyError):
                hl.set_look(kind, key)
        assert hl.colour() == hl.GREEN
        hl.set_colour("#479B29")
        assert hl.colour() == pytest.approx(hl.GREEN, abs=0.002)
        hl.set_colour((1.0, 0.5, 0.0))
        assert hl.colour() == (1.0, 0.5, 0.0)
        with pytest.raises(ValueError):
            hl.set_colour("green")
        hl.set_colour(None)
        assert hl.colour() == hl.GREEN
    finally:
        for kind in hl.LOOKS:
            hl.set_look(kind, "")
        hl.set_colour(None)


def test_a_breath_is_never_faster_than_one_per_second():
    assert hl.BEAT >= 1.0 and hl.BEAT == 1.5 and hl.LOOP == 3.0
    t = np.arange(0.0, 30.0, 0.001)
    v = np.array([hl.breath(x) for x in t])
    assert v.min() >= 0.0 and v.max() <= 1.0 and v.max() - v.min() > 0.99
    peaks = int(((v[1:-1] > v[:-2]) & (v[1:-1] >= v[2:])).sum())
    assert peaks == 20, "30 s hold 20 breaths of 1.5 s"
    for x in (0.0, 0.4, 1.1, 2.9):
        assert hl.breath(x) == pytest.approx(hl.breath(x + hl.LOOP), abs=1e-9), "a 3 s clip joins its start"
    hl.begin_clip()
    try:
        hl.set_clock(hl.BEAT / 4)
        assert hl._pulse() == pytest.approx(1.0) and hl._out() == 1.0
        hl.set_clock(hl.LOOP - 0.1)
        assert hl._out() == pytest.approx(0.25)          # a once-only fade goes out before the clip starts again
    finally:
        hl.end_clip()
    assert hl._S["clock"] is None


# ---------------------------------------------------------------------------
# pointing: the panels (Blender as a module)
# ---------------------------------------------------------------------------

class Rec:
    """A layout that writes down what is drawn into it."""

    def __init__(self, log, where=""):
        self.__dict__["log"] = log
        self.__dict__["where"] = where

    def __setattr__(self, name, value):
        self.__dict__[name] = value

    def _child(self, *a, **k):
        return Rec(self.log, self.where)

    row = column = box = split = column_flow = grid_flow = _child

    def label(self, **k):
        self.log.append(("label", self.where, k))

    def operator(self, idname, **k):
        self.log.append(("operator", self.where, idname, k))
        return types.SimpleNamespace()

    def prop(self, data, name, **k):
        self.log.append(("prop", self.where, name, k))

    def panel(self, idname, default_closed=False):
        self.log.append(("panel", self.where, idname))
        return Rec(self.log, self.where), (None if default_closed else Rec(self.log, idname))

    def panel_prop(self, data, name):
        self.log.append(("panel_prop", self.where, name))
        return Rec(self.log, self.where), Rec(self.log, "forced open")

    def separator(self, **k):
        pass


class HLTEST_PT_main(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Highlight test"
    bl_label = "Main"

    def draw_header(self, context):
        self.layout.label(text="", icon="INFO")

    def draw(self, context):
        layout = self.layout
        row = layout.row(align=True)
        row.operator("object.select_all", text="Left", icon="IMPORT")
        row.operator("object.select_all", text="Right", icon="EXPORT")
        self._more(context)
        body = ui.fold(layout, "hl_test_fold", "More")
        if body is not None:
            body.operator("view3d.view_all", text="In the fold")
            body.prop(context.scene.render, "resolution_y")
        layout.operator("view3d.view_all", text="Beside the fold")
        layout.operator("view3d.view_selected", text="Only beside the fold")
        layout.prop(context.scene.render, "resolution_x", text="Width")

    def _more(self, context):
        self.layout.operator("wm.url_open", text="From a helper of the panel")


class HLTEST_PT_child(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Highlight test"
    bl_label = "Child"
    bl_parent_id = "HLTEST_PT_main"

    def draw(self, context):
        self.layout.operator("object.select_all", text="In the child")


def panel_names():
    return [n for n in dir(bpy.types) if n.startswith(("FRESING_PT_", "HLTEST_PT_"))]


def draws():
    return {n: (getattr(bpy.types, n).__dict__.get("draw"), getattr(bpy.types, n).__dict__.get("draw_header"))
            for n in panel_names()}


def draw(cls, attr="draw"):
    """What the panel class draws now, as a list of what went into the layout."""
    log = []
    fake = type("P", (), {"layout": Rec(log), "_more": getattr(cls, "_more", None)})()
    getattr(cls, attr)(fake, bpy.context)
    return log


def marked(log, kind="button"):
    icon_id = hl._S["icons"][kind].icon_id
    return [e for e in log if isinstance(e[-1], dict) and e[-1].get("icon_value") == icon_id]


@pytest.fixture(scope="module")
def app():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    fresing_render.register()
    mine = ui.HOOKS.get("fold") is not hl.fold_open         # until the app registers the highlight itself
    if mine:
        hl.register()
    for cls in (HLTEST_PT_main, HLTEST_PT_child):
        bpy.utils.register_class(cls)
    icons = hl._icons()                                     # the real marker icons: one per marker colour
    assert all(os.path.isfile(os.path.join(bpy.app.tempdir, f"fr_highlight_{k}.png")) for k in hl.MARKS)
    assert set(icons.keys()) == set(hl.MARKS)
    hl._free_icons()                                        # without a window every icon has the number 0:
    hl._S["icons"] = {k: types.SimpleNamespace(icon_id=7000 + i) for i, k in enumerate(hl.MARKS)}   # stand-ins
    yield
    hl._S["icons"] = None
    hl.clear()
    for cls in (HLTEST_PT_child, HLTEST_PT_main):
        bpy.utils.unregister_class(cls)
    if mine:
        hl.unregister()
    fresing_render.unregister()


@pytest.fixture()
def pointing(app):
    assert not hl.active() and hl.handlers_left() == []
    before = draws()
    yield before
    hl.clear()
    hl.keep_clear(())
    assert draws() == before
    assert hl.handlers_left() == []


def test_point_and_clear_leave_every_panel_exactly_as_it_was(pointing):
    before = pointing
    assert len([n for n in before if n.startswith("FRESING_PT_")]) > 40
    targets = [dict(panel="FRESING_PT_import", button="fresing.import_step"),
               dict(panel="FRESING_PT_cylinders", button="fresing.cylinder_add"),
               dict(panel="FRESING_PT_animation", prop="pv_seconds", fold="fr_product_video"),
               dict(panel="HLTEST_PT_child", button="object.select_all"),
               dict(parts=("no such object",)),
               dict(panel="FRESING_PT_no_such_panel", button="fresing.import_step")]
    for t in targets:
        hl.point(**t)
        assert hl.active()
        left = hl.handlers_left()
        assert "draw handler UI" in left and "draw handler WINDOW" in left and "timer" in left
        if t.get("panel", "").startswith("FRESING_PT_") and hasattr(bpy.types, t["panel"]):
            assert draws() != before
            wrapped = {w.split(" ")[1].split(".")[0] for w in left if w.startswith("wrapped")}
            assert t["panel"] in wrapped and len(wrapped) <= 4, "only the target panel and the panels it sits in"
        hl.point(**targets[0])                      # pointing again without clear() in between
    hl.keep_clear(("FRESING_PT_structure", "HLTEST_PT_main", "FRESING_PT_no_such_panel"))
    hl.point(**targets[1])
    hl.clear()
    assert not hl.active() and hl.handlers_left() == []
    after = draws()
    for name in before:                             # identity, class by class
        assert after[name][0] is before[name][0], f"{name}.draw"
        assert after[name][1] is before[name][1], f"{name}.draw_header"
    assert "draw_header" not in HLTEST_PT_child.__dict__, "a draw_header that was added is taken off again"
    hl.clear()                                      # twice does no harm
    assert hl.found() == {}


def test_only_the_target_button_gets_the_marker(pointing):
    plain = draw(HLTEST_PT_main)
    hl.point(panel="HLTEST_PT_main", button="object.select_all", text="Right")
    log = draw(HLTEST_PT_main)
    hits = marked(log)
    assert len(hits) == 1 and hits[0][0] == "operator" and hits[0][3]["text"] == "Right"
    assert "icon" not in hits[0][3], "the marker takes the icon's place: nothing is added, nothing moves"
    assert [e[:3] for e in log] == [e[:3] for e in plain], "the same things drawn in the same order"
    hl.point(panel="HLTEST_PT_main", button="object.select_all")            # no text: the first one drawn
    hits = marked(draw(HLTEST_PT_main))
    assert len(hits) == 1 and hits[0][3]["text"] == "Left"
    hl.point(panel="HLTEST_PT_main", button="wm.url_open")                  # drawn by a helper method of the panel
    assert len(marked(draw(HLTEST_PT_main))) == 1
    hl.point(panel="HLTEST_PT_child", button="object.select_all")
    assert marked(draw(HLTEST_PT_main)) == [], "another panel's button of the same name is left alone"
    assert len(marked(draw(HLTEST_PT_child))) == 1
    hl.clear()
    assert draw(HLTEST_PT_main) == plain


def test_a_setting_gets_its_marker_in_front(pointing):
    hl.point(panel="HLTEST_PT_main", prop="resolution_x")
    log = draw(HLTEST_PT_main)
    hits = marked(log, "field")
    assert len(hits) == 1 and hits[0][0] == "label"
    after = log[log.index(hits[0]) + 1]
    assert after[0] == "prop" and after[2] == "resolution_x" and after[3] == {"text": "Width"}, "the setting itself " \
        "is drawn as it was"
    assert marked(log, "button") == []


def test_headers_of_the_target_and_of_what_it_sits_in_are_marked(pointing):
    plain = draw(HLTEST_PT_main, "draw_header")
    hl.point(panel="HLTEST_PT_child", button="object.select_all")
    assert hl._S["target"]["chain"] == ["HLTEST_PT_child", "HLTEST_PT_main"]
    for cls in (HLTEST_PT_main, HLTEST_PT_child):
        log = draw(cls, "draw_header")
        assert len(marked(log, "header")) == 1 and log[0] == marked(log, "header")[0], "first: next to the fold arrow"
    assert draw(HLTEST_PT_main, "draw_header")[1:] == plain
    hl.point(panel="FRESING_PT_cnc_tools", button="fresing.cnc_tool_add")
    chain = hl._S["target"]["chain"]
    assert chain[0] == "FRESING_PT_cnc_tools" and chain[-1] == "FRESING_PT_motion" and len(chain) == 3
    assert marked(draw(HLTEST_PT_main, "draw_header"), "header") == []
    log = []
    hl.mark_header(Rec(log), "FRESING_PT_motion")           # for a title row that calls no draw_header
    hl.mark_header(Rec(log), "FRESING_PT_looks")
    assert len(log) == 1 and len(marked(log, "header")) == 1
    hl._HOOKED.clear()


def test_the_fold_the_target_sits_in_opens_by_itself(pointing):
    assert ui.HOOKS["fold"] is hl.fold_open
    assert not hl.fold_open("hl_test_fold")
    plain = draw(HLTEST_PT_main)
    assert ("panel", "", "hl_test_fold") in plain and not any(e[1] == "hl_test_fold" for e in plain), "folded"
    hl.point(panel="HLTEST_PT_main", button="view3d.view_all", fold="hl_test_fold")
    assert hl.fold_open("hl_test_fold") and not hl.fold_open("hl_other_fold") and not hl.fold_open("")
    log = draw(HLTEST_PT_main)
    assert ("panel_prop", "", "fresing_fold_open") in log and ("panel", "", "hl_test_fold") not in log
    hits = marked(log)
    assert len(hits) == 1 and hits[0][3]["text"] == "In the fold", "not the same button beside the fold"
    assert bpy.context.window_manager.fresing_fold_open is True
    hl.point(panel="HLTEST_PT_main", prop="resolution_y", fold="hl_test_fold")
    assert len(marked(draw(HLTEST_PT_main), "field")) == 1
    hl.point(panel="HLTEST_PT_main", button="view3d.view_selected", fold="hl_test_fold")
    assert marked(draw(HLTEST_PT_main)) == [], "first draw: it may still turn up inside the fold"
    assert "UI" in hl.moving(), "so the side panel is drawn once more"
    hits = marked(draw(HLTEST_PT_main))
    assert len(hits) == 1 and hits[0][3]["text"] == "Only beside the fold", "a button that belongs to the fold " \
        "but is drawn beside it (Make a product video)"
    hl.clear()
    assert not hl.fold_open("hl_test_fold")
    assert draw(HLTEST_PT_main) == plain


def test_keep_clear_marks_a_panels_top_and_end(pointing):
    hl.keep_clear(("HLTEST_PT_child",))
    assert draw(HLTEST_PT_child) == [("operator", "", "object.select_all", {"text": "In the child"})], \
        "nothing while nothing is pointed at"
    hl.point(panel="HLTEST_PT_main", button="object.select_all")
    log = draw(HLTEST_PT_child)
    assert len(marked(log, "end")) == 1 and log[-1] == marked(log, "end")[0], "after its last row"
    head = draw(HLTEST_PT_child, "draw_header")
    assert len(marked(head, "top")) == 1 and len(marked(head, "header")) == 0
    assert marked(draw(HLTEST_PT_main), "end") == [] and len(marked(draw(HLTEST_PT_main))) == 1
    hl.keep_clear(())
    assert marked(draw(HLTEST_PT_child), "end") == [] and hl.active()


def test_point_function_reads_the_function_list(pointing):
    for fid in ("import.step", "joints.rotate", "offshore.sea_cable", "cnc.acceleration"):
        f = functions.FUNCTIONS[fid]
        assert hl.point_function(fid) is True
        t = hl._S["target"]
        assert (t["panel"], t["button"], t["text"], t["prop"], t["fold"]) == (f.panel, f.button, f.text, f.prop, f.fold)
        assert t["chain"][0] == f.panel and not getattr(getattr(bpy.types, t["chain"][-1]), "bl_parent_id", "")
        assert hl.fold_open(f.fold) is bool(f.fold)
    f = functions.FUNCTIONS["joints.rotate"]
    assert (f.button, f.text) == ("fresing.joint_pick_axis", "Add rotate joint")
    for fid in functions.FUNCTIONS:                 # every entry can be pointed at
        hl.point_function(fid)
        assert hl.active()
    with pytest.raises(KeyError):
        hl.point_function("no.such_function")
    panels = pytest.importorskip("fresing_render.blender.panels")
    panels.fold_sections()
    assert not panels.is_open("FRESING_PT_cnc_tools") or not panels.is_open("FRESING_PT_motion")
    hl.point_function("joints.rotate")
    assert not panels.is_open("FRESING_PT_motion"), "pointing alone opens nothing: the header shows the way"
    hl.point(panel="FRESING_PT_cnc_tools", button="fresing.cnc_tool_add", open_panels=True)
    assert all(panels.is_open(n) for n in ("FRESING_PT_cnc_tools", "FRESING_PT_cnc", "FRESING_PT_motion"))
    panels.fold_sections()


def test_parts_are_named_with_everything_that_hangs_on_them(pointing):
    made = []
    try:
        top = bpy.data.objects.new("hl assembly", None)
        mesh = bpy.data.meshes.new("hl mesh")
        mesh.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 1, 2)])
        a, b = bpy.data.objects.new("hl part a", mesh), bpy.data.objects.new("hl part b", mesh)
        made += [top, a, b]
        for ob in made:
            bpy.context.scene.collection.objects.link(ob)
        a.parent = top
        b.parent = a
        hl.point(parts=("hl assembly", "no such part"))
        assert sorted(hl._S["parts"]) == ["hl part a", "hl part b"]
        assert hl.handlers_left().count("draw handler WINDOW") == 1
        assert not [w for w in hl.handlers_left() if w.startswith("wrapped")], "no panel is touched for a part"
        assert "WINDOW" in hl.moving()
        hl.point(parts=(b,))
        assert hl._S["parts"] == ["hl part b"]
        hl.set_look("part", "3")
        hl.begin_clip()
        hl.end_clip()
        hl._S["t"] -= 5.0                           # long after the fade in
        assert "WINDOW" not in hl.moving(), "look 3 stands still: the view is not drawn again and again"
        hl.set_look("part", "1")
        hl._S["t"] -= 5.0
        assert hl.moving() == ("WINDOW",), "look 1 breathes"
    finally:
        hl.set_look("part", "")
        hl.clear()
        for ob in made:
            bpy.data.objects.remove(ob)


def test_looks_come_from_the_preferences_at_point(pointing, monkeypatch):
    from fresing_render.blender import prefs
    fake = types.SimpleNamespace(lesson_button="D", lesson_section="4", lesson_part="1", lesson_colour=(0.1, 0.2, 0.3))
    monkeypatch.setattr(prefs, "get", lambda: fake)
    assert hl.look("button") == "C"
    hl.point(panel="HLTEST_PT_main", button="object.select_all")
    assert (hl.look("button"), hl.look("section"), hl.look("part")) == ("D", "4", "1")
    assert hl.colour() == pytest.approx((0.1, 0.2, 0.3))
    hl.set_look("button", "C")                      # what a lesson (or a test) sets wins
    hl.set_colour("#FF6A13")
    assert hl.look("button") == "C" and hl.colour() == pytest.approx((1.0, 0.416, 0.075), abs=0.002)
    hl.set_look("button", "")
    hl.set_colour(None)
    fake.lesson_button = "C"
    assert hl.look("button") == "D", "read at point(), not at every redraw"
    hl.point(panel="HLTEST_PT_main", button="object.select_all")
    assert hl.look("button") == "C"
    for name in ("lesson_button", "lesson_section", "lesson_part", "lesson_colour"):
        assert name in prefs.FRESING_AP_prefs.__annotations__, name


def test_nothing_is_left_after_another_project_opens(pointing, tmp_path):
    before = pointing
    path = os.path.join(str(tmp_path), "hl.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    hl.point(panel="FRESING_PT_import", button="fresing.import_step")
    assert hl._before_load in bpy.app.handlers.load_pre and hl._after_undo in bpy.app.handlers.undo_post
    bpy.ops.wm.open_mainfile(filepath=path)
    assert not hl.active() and draws() == before
    left = hl.handlers_left()
    assert left in ([], ["app handler _before_load"]), left     # that one leaves by a timer right after the load
    hl._drop_load_handler()
    assert hl.handlers_left() == []
    hl.point(panel="FRESING_PT_import", button="fresing.import_step")
    hl._after_undo()                                # undo while pointing: still pointing, meshes read again
    assert hl.active() and hl._GEO == {}


def test_the_time_a_redraw_takes_stays_small():
    """Finding the markers in a side panel of 300 x 1,100 pixels (and of a 4K screen at scale 2: 600 x 2,000)."""
    import time
    for (h, w), limit in (((1100, 300), 0.02), ((2000, 600), 0.06)):
        px = canvas(h, w)
        rect(px, (20, 500, 250, 519), BUTTON)
        icon(px, 24, 504)
        rect(px, (8, 600, 260, 623), (60, 60, 60))
        icon(px, 30, 607, "header", 10)
        t = time.perf_counter()
        for _ in range(10):
            seen = hl.locate(px, clear=True)
        each = (time.perf_counter() - t) / 10
        assert seen["button"] == (20, 500, 250, 519) and seen["header"] == (8, 600, 260, 623)
        assert each < limit, f"{1000 * each:.1f} ms for {w} x {h}"
    assert math.isclose(hl.TICK, 0.05), "20 redraws a second while a look moves"
