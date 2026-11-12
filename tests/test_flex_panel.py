"""Task 0058: the panel 4 Motion > Hoses and drag chains and its buttons (blender/ui_flex.py, ops_flex.py).

The buttons are pressed the way a script presses them, on the two test models of tools/make_test_flex.py; what a
hose or chain then does is tested in tests/test_flex.py. The same buttons clicked with the mouse in the real app:
tools/ui_test_flex.py.
"""

import math
import os
import sys

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from mathutils import Vector  # noqa: E402

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
sys.path.insert(0, HERE)

import fresing_render  # noqa: E402
import test_flex as T  # noqa: E402  (its helpers: the drawn tube, a chain's pins, the band drawn as one solid)
from fresing_render.blender import build, flex, logic, ops_flex, ui_flex  # noqa: E402
from test_blender import FakeLayout  # noqa: E402

HOSES = ("HYDRAULIC HOSE ARM", "HYDRAULIC HOSE CYL A", "HYDRAULIC HOSE CYL B")
CHAIN_LINKS = {"CHAIN X.ASM": 18, "CHAIN Y.ASM": 16, "CHAIN Z.ASM": 13}
OPS = ("flex_add_hose", "flex_add_chain", "flex_find", "flex_remove", "flex_fit", "flex_set_end",
       "flex_swap_ends", "flex_select")


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture(scope="module")
def folder(tmp_path_factory):
    return str(tmp_path_factory.mktemp("flex_panel"))


def strip(sc):
    """The joints of the test set-up stay, its hoses and chains go: the model as the user finds it."""
    while len(flex.items(sc)):
        flex.remove(sc, 0)
    sc.fresing.pick_mode = "PART"
    sc.fresing.last_message = ""
    return sc


@pytest.fixture()
def hoses(folder):
    """The hoses model with its joints "Luff" and "Slide" and the cylinder, and no hose added yet."""
    sc = T.load(folder, T.HOSES_A)
    flex.set_up_test_hoses(sc)
    return strip(sc)


@pytest.fixture()
def chains(folder):
    """The gantry with its joints "X", "Y", "Z", and no drag chain added yet."""
    sc = T.load(folder, T.CHAINS)
    flex.set_up_test_chains(sc)
    return strip(sc)


def pick(sc, obs, active=None):
    """Select exactly these objects; the first (or ``active``) is the active one, as after a click."""
    for o in list(bpy.context.selected_objects):
        o.select_set(False)
    for o in obs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = active if active is not None else (obs[0] if obs else None)


def click(sc, part):
    """A click on ``part`` with 'Click selects: Subassembly': its whole subassembly is selected, the part itself
    is the active object (what blender/handlers.py does after a real click)."""
    sc.fresing.pick_mode = "SUBASSEMBLY"
    tree = logic.Tree(sc)
    sub = logic.subassembly_for_pick(part, tree)
    pick(sc, [part] if sub is part else [sub] + logic.descendants(sub, tree), active=part)


def names(sc):
    return [it.name for it in flex.items(sc)]


def said(sc) -> str:
    return sc.fresing.last_message


def choose(sc, name):
    sc.fresing.flex_index = flex.index_of(sc, flex.find(sc, name))
    return flex.find(sc, name)


def polls() -> dict:
    return {name: getattr(bpy.ops.fresing, name).poll() for name in OPS}


# ---------------------------------------------------------------------------
# buttons that cannot work are grey
# ---------------------------------------------------------------------------

def test_buttons_are_grey_when_they_cannot_work(folder):
    bpy.ops.wm.read_factory_settings(use_empty=True)                 # no model at all
    assert not any(polls().values()), polls()
    assert not ui_flex.FRESING_PT_flex.poll(bpy.context)
    sc = strip(T.load(folder, T.HOSES_A))
    assert ui_flex.FRESING_PT_flex.poll(bpy.context)
    pick(sc, [])                                                     # a model, nothing selected, nothing in the list
    assert polls() == {name: name == "flex_find" for name in OPS}
    pick(sc, [T.ob(sc, "ARM.ASM")])                                  # a subassembly is no part
    assert not bpy.ops.fresing.flex_add_hose.poll() and not bpy.ops.fresing.flex_add_chain.poll()
    hose = T.ob(sc, "HYDRAULIC HOSE ARM")
    pick(sc, [hose])
    assert polls() == {name: name in ("flex_find", "flex_add_hose", "flex_add_chain") for name in OPS}
    assert bpy.ops.fresing.flex_add_hose() == {"FINISHED"}
    got = polls()                                                    # one hose in the list, the hose itself selected
    assert got["flex_remove"] and got["flex_fit"] and got["flex_select"]
    assert not got["flex_swap_ends"]                                 # a hose has no fixed end to swap
    assert not got["flex_set_end"]                                   # the hose cannot be its own end part
    pick(sc, [T.ob(sc, "VALVE BLOCK")])
    assert bpy.ops.fresing.flex_set_end.poll()
    pick(sc, [])
    assert not bpy.ops.fresing.flex_set_end.poll()


# ---------------------------------------------------------------------------
# Add hose, Add cable
# ---------------------------------------------------------------------------

def test_add_hose_takes_the_selected_parts_and_names_what_is_no_hose(hoses):
    sc = hoses
    pick(sc, [T.ob(sc, n) for n in ("HYDRAULIC HOSE ARM", "BASE", "HYDRAULIC HOSE CYL A")])
    assert bpy.ops.fresing.flex_add_hose() == {"FINISHED"}
    assert names(sc) == ["HYDRAULIC HOSE ARM", "HYDRAULIC HOSE CYL A"]
    assert said(sc).startswith("2 hoses added: move a joint and they follow. 'BASE' is not a hose")
    for it in flex.items(sc):
        assert it.kind == "HOSE" and it.stiffness == pytest.approx(0.6) and it.sag == pytest.approx(0.5)
    assert sc.fresing.flex_index == 1                                # the last one added is the chosen one

    assert bpy.ops.fresing.flex_add_hose() == {"CANCELLED"}          # the same selection again: nothing twice
    assert names(sc) == ["HYDRAULIC HOSE ARM", "HYDRAULIC HOSE CYL A"] and said(sc).startswith("'BASE' is not a hose")
    pick(sc, [T.ob(sc, "HYDRAULIC HOSE ARM")])
    assert bpy.ops.fresing.flex_add_hose() == {"CANCELLED"}
    assert "already follows the motion" in said(sc) and len(names(sc)) == 2

    pick(sc, [T.ob(sc, "BASE")])                                     # a block alone: refused, in plain words
    assert bpy.ops.fresing.flex_add_hose() == {"CANCELLED"}
    assert said(sc).startswith("'BASE' is not a hose") and len(names(sc)) == 2

    pick(sc, [T.ob(sc, "HYDRAULIC HOSE CYL B")])
    assert bpy.ops.fresing.flex_add_hose() == {"FINISHED"}
    assert said(sc) == "1 hose added: move a joint and it follows"
    T.set_joint(sc, "Luff", math.radians(15))                        # the arm goes up: the hoses' ends go along
    T.update()
    assert T.arm_deg(sc) == pytest.approx(15, abs=1e-3)
    assert T.end_errors(sc, HOSES) < T.END_TOL


def test_add_cable_starts_soft(hoses):
    sc = hoses
    pick(sc, [T.ob(sc, "CABLE")])
    assert bpy.ops.fresing.flex_add_hose(soft=True) == {"FINISHED"}
    assert said(sc) == "1 cable added: move a joint and it follows"
    cable = flex.find(sc, "CABLE")
    assert cable.kind == "HOSE" and cable.stiffness == pytest.approx(0.2) and cable.sag == pytest.approx(0.8)
    pick(sc, [T.ob(sc, "HYDRAULIC HOSE CYL A")])                     # "Add cable" on a hose: soft, as asked
    assert bpy.ops.fresing.flex_add_hose(soft=True) == {"FINISHED"}
    assert flex.find(sc, "HYDRAULIC HOSE CYL A").stiffness == pytest.approx(0.2)
    flex.remove(sc, 0)                                               # "Add hose" on a part named cable: a cable
    pick(sc, [T.ob(sc, "CABLE")])
    assert bpy.ops.fresing.flex_add_hose() == {"FINISHED"}
    assert flex.find(sc, "CABLE").stiffness == pytest.approx(0.2) and said(sc).startswith("1 cable added")
    T.set_joint(sc, "Slide", 0.1)
    T.update()
    assert T.end_errors(sc, ("CABLE", "HYDRAULIC HOSE CYL A")) < T.END_TOL


def test_a_click_that_selects_the_subassembly_adds_the_clicked_part_only(hoses, folder):
    sc = hoses
    # the hoses of this model lie directly under the top: put one into the arm's subassembly, as in a real model
    hose = T.ob(sc, "HYDRAULIC HOSE CYL B")
    click(sc, T.ob(sc, "FITTING ARM"))
    assert len(bpy.context.selected_objects) > 3 and ops_flex.clicked(bpy.context) == T.ob(sc, "FITTING ARM")
    assert ops_flex.targets(bpy.context) == [T.ob(sc, "FITTING ARM")]
    assert bpy.ops.fresing.flex_add_hose() == {"CANCELLED"}          # the fitting is no hose; nothing else is tried
    assert said(sc).startswith("'FITTING ARM' is not a hose") and names(sc) == []
    click(sc, hose)
    assert bpy.ops.fresing.flex_add_hose() == {"FINISHED"} and names(sc) == ["HYDRAULIC HOSE CYL B"]

    # a chain link clicked: the click selects the whole gantry, the button takes the link's own row
    sc = strip(T.load(folder, T.CHAINS))
    link = T.links_of(sc, "CHAIN X.ASM")[5]
    click(sc, link)
    assert len(ops_flex.selected_parts(bpy.context)) > 18 and ops_flex.clicked(bpy.context) == link
    assert bpy.ops.fresing.flex_add_chain() == {"FINISHED"}
    assert names(sc) == ["CHAIN X.ASM"] and len(flex.items(sc)[0].links) == 18
    assert said(sc) == "1 drag chain added: move a joint and it follows"


def test_a_fault_while_adding_names_the_part_and_leaves_nothing_half_made(hoses, monkeypatch):
    """"Find and add all" meets shapes nobody tested: one that trips the app must not stop the others."""
    sc = hoses
    real = flex.add_hose

    def trips_on_the_cable(scene, part, soft=False):
        if part.get(build.PROP_NAME) == "CABLE":
            scene.fresing.flex.add().name = "half made"
            raise ZeroDivisionError("division by zero")
        return real(scene, part, soft=soft)

    monkeypatch.setattr(flex, "add_hose", trips_on_the_cable)
    assert bpy.ops.fresing.flex_find(add=True) == {"FINISHED"}
    assert sorted(names(sc)) == sorted(HOSES)
    assert said(sc) == ("3 hoses added: move a joint and they follow. 'CABLE' could not be read (a fault in the "
                        "app: ZeroDivisionError: division by zero)")
    part = flex.find(sc, "HYDRAULIC HOSE ARM").part                  # a hose whose part is gone cannot be fitted
    bpy.data.objects.remove(part)
    choose(sc, "HYDRAULIC HOSE ARM")
    assert bpy.ops.fresing.flex_fit() == {"CANCELLED"}
    assert said(sc) == "Hose 'HYDRAULIC HOSE ARM': its part is gone"


# ---------------------------------------------------------------------------
# Add drag chain
# ---------------------------------------------------------------------------

def moving_end_gap(sc, it) -> float:
    """How far the chain's last pin is from its place on the moving part (metres)."""
    pins = flex.pins_now(sc, it)
    want = it.b_part.matrix_world @ Vector(it.b_point)
    return float(np.linalg.norm(pins[-1] - np.array(want)))


def test_add_drag_chain_from_one_link_all_links_or_one_solid(chains):
    sc = chains
    pick(sc, [T.links_of(sc, "CHAIN Z.ASM")[3]])                     # one link: the whole row
    assert bpy.ops.fresing.flex_add_chain() == {"FINISHED"}
    z = flex.find(sc, "CHAIN Z.ASM")
    assert z.kind == "CHAIN" and len(z.links) == 13 and not z.made_links
    assert bpy.ops.fresing.flex_add_chain() == {"CANCELLED"} and "already follows the motion" in said(sc)

    pick(sc, T.links_of(sc, "CHAIN Y.ASM"))                          # all its links, selected by hand
    assert bpy.ops.fresing.flex_add_chain() == {"FINISHED"}
    assert len(flex.find(sc, "CHAIN Y.ASM").links) == 16

    pick(sc, T.links_of(sc, "CHAIN X.ASM")[:3])                      # three parts are no chain
    assert bpy.ops.fresing.flex_add_chain() == {"CANCELLED"}
    assert said(sc).startswith("A drag chain has 4 links or more") and len(names(sc)) == 2

    # bought-in links are often named by a part number: no name says "chain", the same shape in a row does
    for o in T.links_of(sc, "CHAIN X.ASM"):
        o[build.PROP_NAME] = "LK-2650-B"
    assert not any(kind == "CHAIN" for _o, kind in flex.candidates(sc))
    one = T.links_of(sc, "CHAIN X.ASM")[9]
    assert len(ops_flex.row_of(sc, one)) == 18
    pick(sc, [one])
    assert bpy.ops.fresing.flex_add_chain() == {"FINISHED"}
    x = flex.find(sc, "CHAIN X.ASM")
    assert len(x.links) == 18 and T.ob(sc, "CHAIN BRACKET X FIXED") == x.a_part

    band = T.u_band_part(sc)                                         # a chain drawn as one solid: the app draws links
    pick(sc, [band])
    assert bpy.ops.fresing.flex_add_chain() == {"FINISHED"}
    solid = flex.find(sc, "ENERGY CHAIN")
    assert solid.made_links and solid.part == band and len(solid.links) == 0
    assert names(sc) == ["CHAIN Z.ASM", "CHAIN Y.ASM", "CHAIN X.ASM", "ENERGY CHAIN"]

    pick(sc, [T.ob(sc, "BED")])                                      # a block: refused, in plain words
    assert bpy.ops.fresing.flex_add_chain() == {"CANCELLED"}
    assert "'BED': No bend found" in said(sc) and len(names(sc)) == 4

    for axis, value in (("X", 0.12), ("Y", -0.08), ("Z", 0.05)):     # the axes move: every moving end stays on
        T.set_joint(sc, axis, value)
    T.update()
    for name in CHAIN_LINKS:
        it = flex.find(sc, name)
        assert it.problem == "" and moving_end_gap(sc, it) < T.PIN_TOL, name


# ---------------------------------------------------------------------------
# Find hoses and chains
# ---------------------------------------------------------------------------

def test_find_selects_and_find_and_add_all_adds(hoses, folder):
    sc = hoses
    pick(sc, [T.ob(sc, "BASE")])
    assert bpy.ops.fresing.flex_find() == {"FINISHED"}
    assert {o.get(build.PROP_NAME) for o in bpy.context.selected_objects} == set(T.HOSE_NAMES)
    assert bpy.context.view_layer.objects.active.get(build.PROP_NAME) in T.HOSE_NAMES
    assert said(sc) == "4 hoses and cables found and selected: press Add hose" and names(sc) == []
    assert bpy.ops.fresing.flex_add_hose() == {"FINISHED"}           # … and that button takes them all
    assert sorted(names(sc)) == sorted(T.HOSE_NAMES)
    assert said(sc) == "3 hoses and 1 cable added: move a joint and they follow"
    assert flex.find(sc, "CABLE").stiffness == pytest.approx(0.2)    # the part named cable is the soft one
    assert flex.find(sc, "HYDRAULIC HOSE ARM").stiffness == pytest.approx(0.6)
    assert bpy.ops.fresing.flex_find() == {"CANCELLED"}              # nothing left to find
    assert said(sc).startswith("No part is named like a hose, a cable or a drag chain. Click the part yourself")

    strip(sc)
    assert bpy.ops.fresing.flex_find(add=True) == {"FINISHED"}       # all at once
    assert sorted(names(sc)) == sorted(T.HOSE_NAMES)
    assert said(sc) == "3 hoses and 1 cable added: move a joint and they follow"
    T.set_joint(sc, "Luff", math.radians(-10))
    T.update()
    assert T.end_errors(sc) < T.END_TOL

    # hoses and a chain found together: each button takes its own kind from the selection
    strip(sc)
    band = T.u_band_part(sc)
    assert bpy.ops.fresing.flex_find() == {"FINISHED"}
    assert said(sc) == "4 hoses and cables and 1 drag chain found and selected: press Add hose / Add drag chain"
    assert len(bpy.context.selected_objects) == 5
    assert bpy.ops.fresing.flex_add_hose() == {"FINISHED"} and sorted(names(sc)) == sorted(T.HOSE_NAMES)
    assert bpy.ops.fresing.flex_add_chain() == {"FINISHED"} and flex.find(sc, "ENERGY CHAIN").part == band
    assert len(names(sc)) == 5 and said(sc).startswith("1 drag chain added")

    sc = T.load(folder, T.CHAINS)
    flex.set_up_test_chains(sc)
    strip(sc)
    assert bpy.ops.fresing.flex_find() == {"FINISHED"}
    assert len(bpy.context.selected_objects) == 47
    assert said(sc) == "47 chain links found and selected: press Add drag chain"
    assert bpy.ops.fresing.flex_add_hose() == {"CANCELLED"}          # the wrong button says which is the right one
    assert said(sc) == "These parts are the links of a drag chain: press Add drag chain" and names(sc) == []
    assert bpy.ops.fresing.flex_add_chain() == {"FINISHED"}          # every row of links is one chain
    assert {it.name: len(it.links) for it in flex.items(sc)} == CHAIN_LINKS
    assert said(sc) == "3 drag chains added: move a joint and they follow"
    strip(sc)
    T.u_band_part(sc)                                                # … and a chain that is one solid
    assert bpy.ops.fresing.flex_find(add=True) == {"FINISHED"}
    assert {it.name: len(it.links) for it in flex.items(sc)} == dict(CHAIN_LINKS, **{"ENERGY CHAIN": 0})
    assert said(sc).startswith("4 drag chains added: move a joint and they follow")
    T.set_joint(sc, "X", -0.1)
    T.update()
    assert moving_end_gap(sc, flex.find(sc, "CHAIN X.ASM")) < T.PIN_TOL


# ---------------------------------------------------------------------------
# the chosen item: Fit to the CAD pose, an end on another part, Swap ends, Select, Remove
# ---------------------------------------------------------------------------

def test_fit_set_end_select_and_remove_a_hose(hoses):
    sc = hoses
    assert bpy.ops.fresing.flex_find(add=True) == {"FINISHED"}
    it = choose(sc, "HYDRAULIC HOSE ARM")
    part = it.part
    cad_length, cad_diameter = it.cad_length, it.diameter
    assert cad_length == pytest.approx(1.00854, rel=3e-3)
    it.length, it.diameter, it.stiffness = cad_length * 1.2, cad_diameter * 2, 0.33
    assert bpy.ops.fresing.flex_fit() == {"FINISHED"}
    it = choose(sc, "HYDRAULIC HOSE ARM")
    assert it.length == pytest.approx(cad_length) and it.diameter == pytest.approx(cad_diameter)
    assert it.stiffness == pytest.approx(0.33)                       # how it bends is the user's: it stays
    assert said(sc) == "Hose 'HYDRAULIC HOSE ARM' is as drawn in the CAD file again"

    # end A sits on its fitting; the user fixes it to the valve block instead: the end stays where it is
    assert it.a_part == T.ob(sc, "FITTING VALVE C") and it.b_part == T.ob(sc, "FITTING ARM")
    before = np.array(it.a_part.matrix_world @ Vector(it.a_point))
    block = T.ob(sc, "VALVE BLOCK")
    pick(sc, [block])
    assert bpy.ops.fresing.flex_set_end(end="A") == {"FINISHED"}
    it = choose(sc, "HYDRAULIC HOSE ARM")
    assert it.a_part == block and it.b_part == T.ob(sc, "FITTING ARM")
    assert np.linalg.norm(np.array(block.matrix_world @ Vector(it.a_point)) - before) < 1e-6
    assert said(sc) == "End A of 'HYDRAULIC HOSE ARM' now moves with 'VALVE BLOCK'"
    arm = T.ob(sc, "ARM")
    pick(sc, [arm])
    assert bpy.ops.fresing.flex_set_end(end="B") == {"FINISHED"} and choose(sc, "HYDRAULIC HOSE ARM").b_part == arm
    T.set_joint(sc, "Luff", math.radians(12))
    T.update()
    assert T.end_errors(sc, ("HYDRAULIC HOSE ARM",)) < T.END_TOL     # … and still follows the arm
    pick(sc, [T.ob(sc, "CABLE")])                                    # another hose is no place for an end
    assert bpy.ops.fresing.flex_set_end(end="A") == {"CANCELLED"} and "is a hose or chain itself" in said(sc)
    assert bpy.ops.fresing.flex_fit() == {"FINISHED"}                # Fit to the CAD pose: the ends found by the app
    assert choose(sc, "HYDRAULIC HOSE ARM").a_part == T.ob(sc, "FITTING VALVE C")

    pick(sc, [T.ob(sc, "BASE")])
    assert bpy.ops.fresing.flex_select() == {"FINISHED"}
    assert list(bpy.context.selected_objects) == [part] and bpy.context.view_layer.objects.active == part

    assert part.modifiers.get(flex.MOD) is not None
    assert bpy.ops.fresing.flex_remove() == {"FINISHED"}
    assert "HYDRAULIC HOSE ARM" not in names(sc) and len(names(sc)) == 3
    assert part.modifiers.get(flex.MOD) is None and flex.TAG not in part
    assert said(sc) == "Hose 'HYDRAULIC HOSE ARM' removed from the list: it shows as in the CAD file again"


def test_swap_ends_select_and_remove_a_chain(chains):
    sc = chains
    assert bpy.ops.fresing.flex_find(add=True) == {"FINISHED"}
    it = choose(sc, "CHAIN X.ASM")
    fixed, moving = T.ob(sc, "CHAIN BRACKET X FIXED"), T.ob(sc, "CHAIN BRACKET X MOVING")
    assert (it.a_part, it.b_part) == (fixed, moving)
    assert bpy.ops.fresing.flex_swap_ends() == {"FINISHED"}
    it = choose(sc, "CHAIN X.ASM")
    assert (it.a_part, it.b_part) == (moving, fixed)
    assert said(sc) == "Drag chain 'CHAIN X.ASM': the fixed end is now on 'CHAIN BRACKET X MOVING'"
    assert bpy.ops.fresing.flex_swap_ends() == {"FINISHED"}
    it = choose(sc, "CHAIN X.ASM")
    assert (it.a_part, it.b_part) == (fixed, moving)

    pick(sc, [])
    assert bpy.ops.fresing.flex_select() == {"FINISHED"}
    assert set(bpy.context.selected_objects) == set(T.links_of(sc, "CHAIN X.ASM"))

    carriage = T.ob(sc, "CARRIAGE")                                  # the moving end on the carriage itself
    pick(sc, [carriage])
    assert bpy.ops.fresing.flex_set_end(end="B") == {"FINISHED"}
    assert choose(sc, "CHAIN X.ASM").b_part == carriage
    assert said(sc) == "Moving end of 'CHAIN X.ASM' now moves with 'CARRIAGE'"
    T.set_joint(sc, "X", 0.1)
    T.update()
    assert moving_end_gap(sc, choose(sc, "CHAIN X.ASM")) < T.PIN_TOL
    pick(sc, [T.links_of(sc, "CHAIN X.ASM")[0]])                     # a link of the chain itself: the button is grey
    assert not bpy.ops.fresing.flex_set_end.poll()

    assert bpy.ops.fresing.flex_remove() == {"FINISHED"}
    assert sorted(names(sc)) == ["CHAIN Y.ASM", "CHAIN Z.ASM"]
    assert all(o.modifiers.get(flex.MOD) is None for o in T.links_of(sc, "CHAIN X.ASM"))


# ---------------------------------------------------------------------------
# the panel
# ---------------------------------------------------------------------------

ICONS = set(bpy.types.UILayout.bl_rna.functions["label"].parameters["icon"].enum_items.keys())


class Layout(FakeLayout):
    """The fake layout of tests/test_blender.py, which also writes down the texts and checks the icons."""

    def __init__(self, errors, texts=None):
        super().__init__(errors)
        self.texts = texts if texts is not None else []
        self.alert = False
        self.enabled = True

    def _child(self, *a, **k):
        return Layout(self.errors, self.texts)

    row = column = box = split = grid_flow = _child

    def panel(self, idname, default_closed=False):
        return Layout(self.errors, self.texts), Layout(self.errors, self.texts)

    def _note(self, k):
        if k.get("icon", "NONE") not in ICONS:
            self.errors.append(f"no icon {k.get('icon')}")
        if k.get("text"):
            self.texts.append(k["text"])

    def label(self, *a, **k):
        self._note(k)

    def prop(self, data, name, *a, **k):
        self._note(k)
        super().prop(data, name, *a, **k)

    def operator(self, idname, *a, **k):
        self._note(k)
        return super().operator(idname, *a, **k)


def draw_panel():
    """Draw the panel, its header and every list row; returns (the texts drawn, the header's texts)."""
    cls = ui_flex.FRESING_PT_flex
    errors, texts, head = [], [], []
    assert cls.poll(bpy.context)
    cls.draw(type("P", (), {"layout": Layout(errors, texts)})(), bpy.context)
    fake = type("P", (), {"layout": Layout(errors, head)})()
    cls.draw_header(fake, bpy.context)
    cls.draw_header_preset(fake, bpy.context)
    s = bpy.context.scene.fresing
    rows = []
    for i, item in enumerate(s.flex):
        ui_flex.FRESING_UL_flex.draw_item(None, bpy.context, Layout(errors, rows), s, item, 0, s, "flex_index", i)
    assert not errors, errors
    return texts, head, rows


def test_the_panel_draws_empty_and_with_hoses_and_chains(hoses, folder):
    sc = hoses
    texts, head, rows = draw_panel()                                 # nothing added yet: the steps and the buttons
    assert texts[0].startswith("1.  Click the hose or cable in the") and head == [] and rows == []
    for button in ("Add hose", "Add cable", "Add drag chain", "Find hoses and chains", "Find and add all"):
        assert button in texts, button

    assert bpy.ops.fresing.flex_find(add=True) == {"FINISHED"}
    it = choose(sc, "HYDRAULIC HOSE ARM")
    texts, head, rows = draw_panel()
    assert head == ["4 hoses"] and rows == []                        # a row spells out only a problem, or "off"
    assert [ui_flex.short_status(sc, x) for x in flex.items(sc)] == [(f"{x.length * 1000:.0f} mm", False)
                                                                     for x in flex.items(sc)]
    assert "Find and add all" not in texts and "Follows the motion" in texts
    for label in ("Stiffness", "Sag", "Smallest bend", "Length", "Diameter", "More"):
        assert label in texts, label
    assert "End A on: FITTING VALVE C" in texts and "End B on: FITTING ARM" in texts
    assert not any(t.startswith("In the CAD file") for t in texts)

    it.length = 0.6                                                  # shorter than its ends are apart: a warning
    texts, head, rows = draw_panel()
    assert rows == ["too short"] and head == ["1 of 4"] and f"In the CAD file: {it.cad_length * 1000:.1f} mm" in texts
    joined = " ".join(texts)
    assert "Hose too short in this pose: needs" in joined and "Make 'Length' longer" in joined
    assert ui_flex.counts(sc) == ("1 of 4", True)
    it.length = it.cad_length
    it.enabled = False                                               # off: said so, and no warning
    texts, head, rows = draw_panel()
    assert rows == ["off"] and ui_flex.counts(sc) == ("4 hoses", False)
    assert any(t.startswith("Off: it shows stiff") for t in texts)
    it.enabled = True

    band = T.u_band_part(sc)                                         # a chain drawn as one solid, beside the hoses
    pick(sc, [band])
    assert bpy.ops.fresing.flex_add_chain() == {"FINISHED"}
    texts, head, rows = draw_panel()
    assert head == ["5 items"] and rows == []                        # (the title is long: no room for more)
    assert ui_flex.short_status(sc, flex.find(sc, "ENERGY CHAIN"))[0].endswith(" links")
    for label in ("Upper run", "Bend radius", "Links", "Link length", "Width", "Height", "Swap ends",
                  "Fit to the CAD pose"):
        assert label in texts, label
    assert any(t.startswith("Fixed end on: ") for t in texts) and any(t.startswith("Moving end on: ") for t in texts)

    sc = T.load(folder, T.CHAINS)                                    # chains of CAD links
    flex.set_up_test_chains(sc)
    choose(sc, "CHAIN Y.ASM")
    texts, head, rows = draw_panel()
    assert head == ["3 chains"] and rows == []
    assert [ui_flex.short_status(sc, x)[0] for x in flex.items(sc)] == ["18 links", "16 links", "13 links"]
    joined = " ".join(texts)                                         # (a long line is drawn on two)
    assert "Fixed end on: CHAIN BRACKET Y FIXED" in joined and "Moving end on: CHAIN BRACKET Y MOVING" in joined
    assert "Width" not in texts and "Link length" in texts           # the links are the CAD ones: no size to set


# ---------------------------------------------------------------------------
# tooltips
# ---------------------------------------------------------------------------

def sentences(text: str) -> int:
    return len([part for part in text.replace(": ", ". ").split(". ") if len(part.strip()) > 12])


def test_every_button_and_setting_has_a_tooltip():
    for name in OPS:
        text = getattr(bpy.ops.fresing, name).get_rna_type().description
        assert "\n" not in text and "  " not in text, name
        assert len(text) >= 100 and sentences(text) >= 2, (name, text)       # what it does, then how to use it
    # one button, two jobs: each has its own text
    for cls, option in ((ops_flex.FRESING_OT_flex_add_hose, "soft"), (ops_flex.FRESING_OT_flex_find, "add")):
        texts = [cls.description(bpy.context, type("Props", (), {option: value})()) for value in (False, True)]
        assert texts[0] != texts[1] and all(len(t) >= 100 and "\n" not in t and sentences(t) >= 2 for t in texts)
    for option in ("soft", "add", "end"):
        owner = {"soft": "flex_add_hose", "add": "flex_find", "end": "flex_set_end"}[option]
        assert getattr(bpy.ops.fresing, owner).get_rna_type().properties[option].description
    from fresing_render.blender import props as P
    props = P.FRFlex.bl_rna.properties
    for name in ("name", "enabled", "length", "diameter", "stiffness", "sag", "min_radius", "pitch", "radius", "count",
                 "mode", "width", "height"):                                 # every setting the panel draws
        text = props[name].description
        assert len(text) >= 40 and "\n" not in text, (name, text)
    for choice in props["mode"].enum_items:
        assert len(choice.description) >= 40, choice.identifier
