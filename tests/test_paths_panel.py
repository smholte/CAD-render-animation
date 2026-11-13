"""Task 0078: the panel 4 Motion > Cables and paths and its buttons (blender/ui_paths.py, ops_paths.py).

The buttons are pressed the way a script presses them, on the test model of tools/make_test_paths.py (a wire rope
from a winch drum over two sheaves, through a V-roller cradle and over a chute); what a cable then does is tested
in tests/test_paths.py. The same buttons clicked with the mouse in the real app, and undo: tools/ui_test_paths.py.

A button that refuses reports an error; pressed from a script that is a RuntimeError with the sentence.
"""

import math
import os
import sys

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
sys.path.insert(0, HERE)

import fresing_render  # noqa: E402
import test_paths as T  # noqa: E402  (its helpers: the model, a part by name, the drawn tube's rings)
from fresing_render.blender import animation, build, joints, ops_paths, paths, ui_paths  # noqa: E402
from test_blender import FakeLayout  # noqa: E402

MM = 0.001
ROPE = "WIRE ROPE"
SPEED = "Cable WIRE ROPE"
OPS = ("cable_add", "cable_add_all", "cable_remove", "cable_read", "cable_select", "cable_motor_step",
       "cable_contact_add", "cable_contact_remove", "cable_contact_flip", "cable_end")
FIRST = "Cable 'WIRE ROPE': 3 sheaves, 2 rollers, 1 chute; Ø 24 mm, 7.02 m; the path is at most "


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture(scope="module")
def folder(tmp_path_factory):
    return str(tmp_path_factory.mktemp("paths_panel"))


@pytest.fixture()
def model(folder):
    """The test model as the user finds it: imported, no cable in the list, nothing selected."""
    sc = T.load(folder, T.MODEL_A)
    ui_paths.forget()
    sc.fresing.pick_mode = "PART"
    sc.fresing.last_message = ""
    pick([])
    return sc


@pytest.fixture()
def added(model):
    """… and the rope added with the button."""
    pick([T.ob(model, ROPE)])
    assert bpy.ops.fresing.cable_add() == {"FINISHED"}
    return model


def pick(obs, active=None):
    """Select exactly these objects; the first (or ``active``) is the active one, as after a click."""
    for o in list(bpy.context.selected_objects):
        o.select_set(False)
    for o in obs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = active if active is not None else (obs[0] if obs else None)


def cable(sc):
    return paths.active(sc)


def names(sc):
    return [it.name for it in paths.items(sc)]


def contacts(sc):
    return [c.name for c in cable(sc).contacts]


def said(sc) -> str:
    return sc.fresing.last_message


def choose(sc, name, k=0) -> int:
    """Choose a contact under "What it touches" by its name; returns its place."""
    index = [i for i, c in enumerate(cable(sc).contacts) if c.name == name][k]
    cable(sc).contacts_index = index
    return index


def polls() -> dict:
    return {name: getattr(bpy.ops.fresing, name).poll() for name in OPS}


def refused(op, match, **kw):
    """The button refuses with an error whose sentence matches."""
    with pytest.raises(RuntimeError, match=match):
        op(**kw)


def state(sc) -> tuple:
    return len(paths.items(sc)), len(sc.fresing.joints), sc.fresing.cables_index


# ---------------------------------------------------------------------------
# buttons that cannot work are grey
# ---------------------------------------------------------------------------

def test_buttons_are_grey_when_they_cannot_work(folder):
    bpy.ops.wm.read_factory_settings(use_empty=True)                 # no model at all
    assert not any(polls().values()), polls()
    assert not ui_paths.FRESING_PT_cables.poll(bpy.context)
    sc = T.load(folder, T.MODEL_A)
    assert ui_paths.FRESING_PT_cables.poll(bpy.context)
    pick([])                                                         # a model, no cable yet: only the two Add buttons
    assert polls() == {name: name in ("cable_add", "cable_add_all") for name in OPS}
    pick([T.ob(sc, ROPE)])
    assert bpy.ops.fresing.cable_add() == {"FINISHED"}
    assert all(polls().values()), polls()                            # a cable, its first contact (the drum) chosen
    choose(sc, "V ROLLER")                                           # a roller has no other side to lie on
    assert not bpy.ops.fresing.cable_contact_flip.poll() and bpy.ops.fresing.cable_contact_remove.poll()
    choose(sc, "CHUTE")
    assert bpy.ops.fresing.cable_contact_flip.poll()
    cable(sc).contacts_index = 99                                    # nothing chosen under "What it touches"
    assert not bpy.ops.fresing.cable_contact_flip.poll() and not bpy.ops.fresing.cable_contact_remove.poll()
    assert bpy.ops.fresing.cable_contact_add.poll() and bpy.ops.fresing.cable_end.poll()
    choose(sc, "SHEAVE 1")
    cable(sc).enabled = False                                        # switched off: its path cannot be changed
    assert polls() == {name: name in ("cable_add", "cable_add_all", "cable_remove", "cable_read", "cable_select",
                                      "cable_motor_step") for name in OPS}
    cable(sc).enabled = True
    assert all(polls().values())


# ---------------------------------------------------------------------------
# Add cable, Find cables and add all
# ---------------------------------------------------------------------------

def test_add_cable_reads_the_selected_part(model):
    sc = model
    rope = T.ob(sc, ROPE)
    pick([T.ob(sc, "BASE FRAME"), rope], active=rope)                # the part that was clicked last is meant
    assert ops_paths.meant(bpy.context) == rope and ops_paths.cable_target(bpy.context) == rope
    assert bpy.ops.fresing.cable_add() == {"FINISHED"}
    it = cable(sc)
    assert names(sc) == [ROPE] and it.part == rope and it.joint == SPEED and it.made_joint
    assert contacts(sc) == T.ORDER and [c.kind for c in it.contacts] == T.KINDS
    assert said(sc).startswith(FIRST) and said(sc).endswith(" mm off the cable as drawn in CAD")
    assert paths.status(sc, it) == ("7.02 m over 6 contacts", "OK")
    assert it.look == "ROPE" and it.pitch == pytest.approx(paths.ROPE_LAY * it.diameter, rel=1e-6)   # named a rope
    assert rope.modifiers.get(paths.MOD) is not None
    T.update()
    assert np.isfinite(T.rings(rope)[0]).all()
    for c in it.contacts:                                            # everything round it touches turns with it
        assert (c.kind == "CHUTE" and not c.joint) or joints.find(sc, c.joint).follows == SPEED
    count = state(sc)

    # the same part again, a part that is no cable, a subassembly, nothing at all: refused, nothing added
    assert ops_paths.cable_target(bpy.context) is None               # (it is a cable already: the button would ask)
    refused(bpy.ops.fresing.cable_add, "'WIRE ROPE' is cable 'WIRE ROPE' already")
    assert said(sc) == "'WIRE ROPE' is cable 'WIRE ROPE' already." and state(sc) == count
    refused(bpy.ops.fresing.cable_add, "This part is not a cable", part=T.ob(sc, "BASE FRAME").name)
    assert said(sc).startswith("This part is not a cable") and state(sc) == count
    refused(bpy.ops.fresing.cable_add, "not a cable: it has no shape to read", part=T.ob(sc, "A-FRAME.ASM").name)
    pick([T.ob(sc, "SHEAVE 1")])
    assert ops_paths.cable_target(bpy.context) is None
    refused(bpy.ops.fresing.cable_add, "This part is not a cable")
    assert state(sc) == count and names(sc) == [ROPE]
    pick([])
    assert bpy.ops.fresing.cable_add() == {"CANCELLED"} and said(sc).startswith("First click the cable")
    assert bpy.ops.fresing.cable_add(part="no such part") == {"CANCELLED"} and "no part 'no such part'" in said(sc)
    assert state(sc) == count and contacts(sc) == T.ORDER
    assert not any(j.name.startswith("Cable ") and j.name != SPEED for j in sc.fresing.joints)


def stray(sc, name, k=0):
    """A block beside the model with a name of its own."""
    o = T.ob(sc, "CHUTE STAND").copy()
    o[build.PROP_NAME], o[build.PROP_UID] = name, f"TEST.PATHS#1/STRAY{k}#1"
    sc.collection.objects.link(o)
    return o


def test_find_cables_and_add_all(model, monkeypatch):
    sc = model
    assert ui_paths.found_count(sc) == 1
    assert bpy.ops.fresing.cable_add_all() == {"FINISHED"}
    assert names(sc) == [ROPE] and said(sc) == "1 cable added: 'WIRE ROPE'" and contacts(sc) == T.ORDER
    assert ui_paths.found_count(sc) == 0
    assert bpy.ops.fresing.cable_add_all() == {"CANCELLED"}          # nothing left to find
    assert said(sc).startswith("No part is named like a cable or a wire rope. Click the cable yourself")

    # a part that is only named like a cable is left out and named; the real one is still added
    assert bpy.ops.fresing.cable_remove() == {"FINISHED"} and names(sc) == []
    stray(sc, "POWER CABLE 3x240")
    assert ui_paths.found_count(sc) == 2
    assert bpy.ops.fresing.cable_add_all() == {"FINISHED"}
    assert names(sc) == [ROPE] and len(sc.fresing.joints) == 6       # the rope's speed and its five wheels
    assert said(sc).startswith("1 cable added: 'WIRE ROPE'. 'POWER CABLE 3x240': This part is not a cable")
    refused(bpy.ops.fresing.cable_add_all, "'POWER CABLE 3x240': This part is not a cable")     # only that one left
    assert names(sc) == [ROPE] and len(sc.fresing.joints) == 6

    # a fault in the app while reading: named with the part, nothing half made stays
    assert bpy.ops.fresing.cable_remove() == {"FINISHED"} and len(sc.fresing.joints) == 0

    def trips(scene, item, part):
        raise ZeroDivisionError("division by zero")

    monkeypatch.setattr(paths, "read_cad", trips)
    pick([T.ob(sc, ROPE)])
    refused(bpy.ops.fresing.cable_add, "'WIRE ROPE' could not be read \\(a fault in the app: ZeroDivisionError")
    assert state(sc) == (0, 0, 0)


# ---------------------------------------------------------------------------
# the chosen cable: From CAD cable again, Select, Add a Run motor step, Remove
# ---------------------------------------------------------------------------

def test_read_again_select_and_remove(added):
    sc = added
    rope = T.ob(sc, ROPE)
    T.update()
    before = T.rings(rope)[0]
    choose(sc, "SHEAVE 1")
    assert bpy.ops.fresing.cable_contact_remove() == {"FINISHED"} and len(contacts(sc)) == 5
    cable(sc).look = "POWER"
    assert bpy.ops.fresing.cable_read() == {"FINISHED"}              # what was removed is read again
    assert contacts(sc) == T.ORDER and said(sc).startswith(FIRST) and len(sc.fresing.joints) == 6
    assert cable(sc).look == "POWER"                                 # a setting of the user's stays
    T.update()
    assert np.abs(T.rings(rope)[0] - before).max() < 0.05 * MM

    pick([T.ob(sc, "BASE FRAME")])
    assert bpy.ops.fresing.cable_select() == {"FINISHED"}
    assert list(bpy.context.selected_objects) == [rope] and bpy.context.view_layer.objects.active == rope

    assert bpy.ops.fresing.cable_remove() == {"FINISHED"}
    assert names(sc) == [] and len(sc.fresing.joints) == 0 and rope.modifiers.get(paths.MOD) is None
    assert said(sc) == "Cable 'WIRE ROPE' removed from the list: it shows as in the CAD file again"
    assert not bpy.ops.fresing.cable_remove.poll() and not bpy.ops.fresing.cable_read.poll()

    pick([rope])                                                     # a cable whose part is gone from the model
    assert bpy.ops.fresing.cable_add() == {"FINISHED"}
    bpy.data.objects.remove(rope)
    refused(bpy.ops.fresing.cable_read, "Cable 'WIRE ROPE': its part is gone from the model")
    assert bpy.ops.fresing.cable_select() == {"CANCELLED"} and "nothing to select" in said(sc)
    assert bpy.ops.fresing.cable_remove() == {"FINISHED"} and names(sc) == []


def test_add_a_run_motor_step(added):
    sc = added
    s = sc.fresing
    assert len(s.animations) == 0
    assert bpy.ops.fresing.cable_motor_step() == {"FINISHED"}
    a = animation.active(sc)
    assert len(s.animations) == 1 and a.name == "Animation" and len(a.blocks) == 1
    b = a.blocks[0]
    assert (b.kind, b.joint, b.start, b.duration, b.easing) == ("MOTOR", SPEED, 0.0, 5.0, "LINEAR")
    assert b.speed_mmin == pytest.approx(10.0) and a.blocks_index == 0
    assert animation.motor_total(joints.find(sc, SPEED), b) == pytest.approx(10.0 / 60.0 * 5.0, rel=1e-6)   # metres
    assert said(sc).startswith("Step 'Run motor' added to animation 'Animation': 'WIRE ROPE' runs at 10 m/min for 5 s")
    assert bpy.ops.fresing.cable_motor_step() == {"FINISHED"}        # the next one starts where the last one ends
    assert len(s.animations) == 1 and len(a.blocks) == 2 and a.blocks[1].start == pytest.approx(5.0)
    assert a.blocks_index == 1
    r = animation.bake(sc, a)                                        # … and it runs: 10 s at 10 m/min
    assert not r["warnings"], r["warnings"]
    sc.frame_set(sc.frame_end)
    assert joints.get_value(joints.find(sc, SPEED)) == pytest.approx(10.0 / 60.0 * 10.0, rel=1e-4)
    animation.clear_keys(sc)
    joints.remove(sc, joints.find(sc, SPEED))                        # its speed joint removed by hand: grey
    assert not bpy.ops.fresing.cable_motor_step.poll() and ui_paths.short_status(sc, cable(sc)) == ("no speed", True)
    assert "Add a Run motor step" not in draw_panel()[0]


# ---------------------------------------------------------------------------
# what it touches: Remove, Add, Flip side; the two ends
# ---------------------------------------------------------------------------

def test_remove_a_contact_and_add_it_back(added):
    sc = added
    it = cable(sc)
    T.update()
    before = T.rings(it.part)[0]
    k = choose(sc, "SHEAVE 2")                                       # without it the rope has no path: refused
    refused(bpy.ops.fresing.cable_contact_remove, "Without 'SHEAVE 2' the cable has no path: ")
    assert contacts(sc) == T.ORDER and len(sc.fresing.joints) == 6 and said(sc).startswith("Without 'SHEAVE 2'")

    k = choose(sc, "SHEAVE 1")
    c = cable(sc).contacts[k]
    centre = np.array(T.N["contacts"]["SHEAVE 1"]["axis_point"]) * MM
    middle = before[np.linalg.norm(before - centre, axis=1) < c.radius + 1 * MM]
    middle = middle[len(middle) // 2]
    hit = centre + (middle - centre) * (c.surface / c.radius)       # on the groove's bottom, under the rope
    ratio = c.ratio
    assert bpy.ops.fresing.cable_contact_remove() == {"FINISHED"}
    assert contacts(sc) == T.ORDER[:1] + T.ORDER[2:] and joints.find(sc, "SHEAVE 1 rotate") is None
    assert said(sc) == "'SHEAVE 1' removed: cable 'WIRE ROPE' no longer runs over it"
    assert cable(sc).contacts_index == 1 and paths.status(sc, cable(sc))[1] == "OK"

    sheave = T.ob(sc, "SHEAVE 1")                                    # "click" it where the rope lay
    assert bpy.ops.fresing.cable_contact_add(part=sheave.name, point=tuple(hit)) == {"FINISHED"}
    assert contacts(sc) == T.ORDER and cable(sc).contacts_index == k
    assert said(sc) == "'SHEAVE 1' added as a sheave: number 2 of 6 along 'WIRE ROPE'"
    c = cable(sc).contacts[k]
    assert c.kind == "SHEAVE" and c.user and c.ratio == pytest.approx(ratio, rel=1e-4)
    assert joints.find(sc, c.joint).follows == SPEED
    T.update()
    assert np.abs(T.rings(cable(sc).part)[0] - before).max() < 0.05 * MM

    refused(bpy.ops.fresing.cable_contact_add, "'SHEAVE 1' is in the cable's list already", part=sheave.name,
            point=tuple(hit))
    refused(bpy.ops.fresing.cable_contact_add, "not a part the cable can run over", part=T.ob(sc, ROPE).name)
    refused(bpy.ops.fresing.cable_contact_add, "'CHUTE STAND' has no round face", part=T.ob(sc, "CHUTE STAND").name)
    assert bpy.ops.fresing.cable_contact_add() == {"CANCELLED"} and "click a roller, sheave or chute" in said(sc)
    assert contacts(sc) == T.ORDER and len(sc.fresing.joints) == 6

    k = choose(sc, "V ROLLER", 1)                                    # a roller the rope runs over: no click needed
    roller = cable(sc).contacts[k].part
    assert bpy.ops.fresing.cable_contact_remove() == {"FINISHED"} and len(contacts(sc)) == 5
    assert bpy.ops.fresing.cable_contact_add(part=roller.name) == {"FINISHED"}
    assert said(sc) == "'V ROLLER' added as a roller: number 5 of 6 along 'WIRE ROPE'" and contacts(sc) == T.ORDER

    # what the picker would refuse, said while the mouse is over it
    op = ops_paths.FRESING_OT_cable_contact_add
    assert op.refuse(None, bpy.context, T.ob(sc, ROPE)).startswith("is the cable itself")
    assert op.refuse(None, bpy.context, sheave) == "" and op.note(None, bpy.context, sheave, "S") == "Cable over S"
    op = ops_paths.FRESING_OT_cable_add
    assert op.refuse(None, bpy.context, T.ob(sc, ROPE)) == "is cable 'WIRE ROPE' already"
    assert op.refuse(None, bpy.context, sheave) == ""


def test_flip_side_and_its_refusal(folder):
    sc = T.load(folder, T.MODEL_A)
    paths.set_up_test_model(sc)                                      # the cable "Wire rope" and the joint "Luff"
    ui_paths.forget()
    T.update()
    before = T.rings(cable(sc).part)[0]
    k = choose(sc, "SHEAVE 2")
    assert ui_paths.pass_word(sc, cable(sc), k) == "under"
    assert bpy.ops.fresing.cable_contact_flip() == {"FINISHED"}
    c = cable(sc).contacts[k]
    assert c.side == 1 and c.user and math.degrees(c.wrap) > 180.0
    assert said(sc) == "Cable 'Wire rope' now goes round the other side of 'SHEAVE 2'"
    T.update()
    assert ui_paths.pass_word(sc, cable(sc), k) == "round" and paths.status(sc, cable(sc))[1] == "OK"   # over its top
    # and on round its bottom: more than half a turn
    assert bpy.ops.fresing.cable_contact_flip() == {"FINISHED"}      # and back: the rope lies as before
    T.update()
    assert cable(sc).contacts[k].side == -1 and np.abs(T.rings(cable(sc).part)[0] - before).max() < 1e-6
    # a side the cable cannot take: with the A-frame laid back over the drum no rope crosses over to sheave 2's top
    joints.find(sc, "Luff").use_limits = False
    joints.set_value(joints.find(sc, "Luff"), math.radians(-110.0))
    T.update()
    refused(bpy.ops.fresing.cable_contact_flip, "The cable cannot go round the other side of 'SHEAVE 2': ")
    assert cable(sc).contacts[k].side == -1 and said(sc).startswith("The cable cannot go round the other side")


def test_an_end_on_a_part_and_free_again(added):
    sc = added
    T.update()
    before = T.rings(cable(sc).part)[0]
    assert ui_paths.end_text(cable(sc), "A") == ("Start: lies on WINCH DRUM", False)
    assert ui_paths.end_text(cable(sc), "B") == ("End: free, stays with CHUTE", False)
    stand = T.ob(sc, "CHUTE STAND")
    assert bpy.ops.fresing.cable_end(end="B", part=stand.name) == {"FINISHED"}
    it = cable(sc)
    assert it.b_part == stand and not it.b_free_end and ui_paths.end_text(it, "B") == ("End on: CHUTE STAND", False)
    assert said(sc) == "The end of 'WIRE ROPE' now moves with 'CHUTE STAND'"
    T.update()
    assert np.abs(T.rings(it.part)[0] - before).max() < 0.01 * MM    # it stays where it is
    assert bpy.ops.fresing.cable_end(end="B", free=True) == {"FINISHED"}
    it = cable(sc)
    assert it.b_free_end and it.b_part == T.ob(sc, "CHUTE") and said(sc) == "The end of 'WIRE ROPE' is a free end again"
    assert ui_paths.end_text(it, "B") == ("End: free, stays with CHUTE", False)

    base = T.ob(sc, "BASE FRAME")                                    # the start: off the drum, onto the base
    assert bpy.ops.fresing.cable_end(end="A", part=base.name) == {"FINISHED"}
    assert cable(sc).a_part == base and cable(sc).a_kind == "FIXED"
    assert said(sc) == "The start of 'WIRE ROPE' now moves with 'BASE FRAME'"
    assert ui_paths.end_text(cable(sc), "A") == ("Start on: BASE FRAME", False)

    refused(bpy.ops.fresing.cable_end, "not a part of the model the end can sit on", end="B", part=T.ob(sc, ROPE).name)
    assert bpy.ops.fresing.cable_end(end="B") == {"CANCELLED"} and "click the part the end is fixed to" in said(sc)
    assert bpy.ops.fresing.cable_end(end="B", part="no such part") == {"CANCELLED"}
    op = ops_paths.FRESING_OT_cable_end
    assert op.refuse(None, bpy.context, T.ob(sc, ROPE)).startswith("is the cable itself")
    assert op.refuse(None, bpy.context, base) == ""


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
        self.ui_units_x = 0.0

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
    """Draw the panel, its header and every row of its two lists: (the panel's texts, the header's, the cable
    rows', the contact rows')."""
    cls = ui_paths.FRESING_PT_cables
    errors, texts, head, rows, touched = [], [], [], [], []
    assert cls.poll(bpy.context)
    cls.draw(type("P", (), {"layout": Layout(errors, texts)})(), bpy.context)
    fake = type("P", (), {"layout": Layout(errors, head)})()
    cls.draw_header(fake, bpy.context)
    cls.draw_header_preset(fake, bpy.context)
    s = bpy.context.scene.fresing
    for i, item in enumerate(s.cables):
        ui_paths.FRESING_UL_cables.draw_item(None, bpy.context, Layout(errors, rows), s, item, 0, s, "cables_index", i)
    cb = paths.active(bpy.context.scene)
    for i, c in enumerate(cb.contacts if cb is not None else []):
        ui_paths.FRESING_UL_cable_contacts.draw_item(None, bpy.context, Layout(errors, touched), cb, c, 0, cb,
                                                     "contacts_index", i)
    assert not errors, errors
    return texts, head, rows, touched


def test_the_panel_draws_empty_and_with_a_cable(model):
    sc = model
    texts, head, rows, touched = draw_panel()                        # no cable yet: the steps and the buttons
    assert texts[0].startswith("1.  Click the cable or wire rope") and head == ["–"] and rows == [] == touched
    assert "Add cable" in texts and "Add all 1 found by name" in texts and "What it touches" not in " ".join(texts)

    pick([T.ob(sc, ROPE)])
    assert bpy.ops.fresing.cable_add() == {"FINISHED"}
    it = cable(sc)
    T.update()
    texts, head, rows, touched = draw_panel()
    joined = " ".join(texts)
    assert head == ["1 cable"] and rows == [] and ui_paths.counts(sc) == ("1 cable", False)
    assert "7.02 m over 6 contacts" in texts and "Cable speed: joint 'Cable WIRE ROPE'" in joined
    assert "Animate it in 6 Animation with the step Run motor: speed in m/min" in joined
    for label in ("Add cable", "Add a Run motor step", "Look", "Lay length", "From CAD cable again",
                  "What it touches (6)", "Add", "Remove", "Flip side", "More", "Diameter", "Min. bend (MBR)",
                  "Free at end",
                  "Runs the other way", "Stays as drawn", "Turns with the cable"):
        assert label in texts, label
    assert not any(t in texts for t in ("Stripe distance", "Free at start", "Add all 1 found by name"))
    assert "Start: lies on WINCH DRUM" in texts and "End: free, stays with CHUTE" in joined
    # the rows of "What it touches": name, Ø at the rope's middle, wrap; and where the rope lies on each
    assert touched == ["WINCH DRUM", "Ø 424", "147°", "SHEAVE 1", "Ø 500", "192°", "SHEAVE 2", "Ø 360", "135°",
                       "V ROLLER", "Ø 144", "–", "V ROLLER", "Ø 144", "–", "CHUTE", "Ø 1200", "50°"]
    assert ui_paths.passes(sc, it) == ["under", "over", "under", "over", "over", "over"]
    # the chosen contact under the list: the drum first
    assert "Sheave: the cable bends round it and turns it; the cable runs under it" in joined
    for line in ("Ø 424 mm at the cable's middle", "Wrap 147°", "Turns 0.270° per mm",
                 "Its joint: WINCH DRUM rotate"):
        assert line in texts, line
    choose(sc, "CHUTE")
    texts = draw_panel()[0]
    assert "Does not turn" in texts and "Wrap 50°" in texts and "Turns with the cable" not in texts
    assert "Chute: the cable bends round it and slides over it; the cable runs over it" in " ".join(texts)
    k = choose(sc, "V ROLLER")
    texts = draw_panel()[0]
    assert "Turns 0.955° per mm" in texts and not any(t.startswith("Wrap ") for t in texts)
    it.contacts[k].turns = False
    assert "Stands still" in draw_panel()[0]
    it.contacts[k].turns = True
    with paths._quiet(it.contacts[k]):                               # a note of the reading: said under the list
        it.contacts[k].note = "its own joint 'Roller drive' follows 'Winch', not the cable"
    assert "Its own joint 'Roller drive' follows 'Winch', not the cable" in " ".join(draw_panel()[0])
    with paths._quiet(it.contacts[k]):
        it.contacts[k].note = ""

    it.look = "POWER"                                                # the power cable's stripes
    texts = draw_panel()[0]
    for label in ("Stripe distance", "Stripe angle", "Stripe width"):
        assert label in texts, label
    assert "Lay length" not in texts
    it.look = "PLAIN"
    assert not any(t in draw_panel()[0] for t in ("Stripe distance", "Lay length"))

    it.mbr = 0.25                                                    # sheave 2 bends it tighter: a warning
    texts, head, rows, touched = draw_panel()
    assert paths.status(sc, it)[1] == "WARN" and ui_paths.short_status(sc, it) == ("tight bend", True)
    assert head == ["1 warning"] and rows == ["tight bend"] and ui_paths.counts(sc) == ("1 warning", True)
    assert "Cable bends tighter than its smallest bend (MBR 250 mm) at 'SHEAVE 2': 180 mm" in " ".join(texts)
    it.mbr = 0.0
    it.enabled = False                                               # off: said so, and no warning
    texts, head, rows, touched = draw_panel()
    assert rows == ["off"] and head == ["1 cable"]
    assert any(t.startswith("Off: it shows as in the CAD file") for t in texts)
    it.enabled = True
    T.update()
    assert draw_panel()[1] == ["1 cable"] and paths.status(sc, cable(sc))[1] == "OK"

    assert bpy.ops.fresing.cable_end(end="B", part=T.ob(sc, "CHUTE STAND").name) == {"FINISHED"}
    texts = draw_panel()[0]
    assert "End on: CHUTE STAND" in texts and "Free at end" not in texts

    bpy.data.objects.remove(cable(sc).part)                          # its part gone from the model
    paths.forget()
    texts, head, rows, touched = draw_panel()
    assert rows == ["no path"] and head == ["1 warning"] and "Cable: its part is gone" in " ".join(texts)


def test_every_warning_has_its_word_in_the_list(added, monkeypatch):
    """The sentences paths.status gives, and the word or two the list row shows for each."""
    sc = added
    it = cable(sc)
    for text, level, word in (
            ("7.02 m over 6 contacts", "OK", ("", False)), ("off", "OFF", ("off", False)),
            ("its part is gone", "ERROR", ("no path", True)),
            ("bends tighter than its smallest bend (MBR 250 mm) at 'SHEAVE 2': 180 mm", "WARN", ("tight bend", True)),
            ("no longer touches 'SHEAVE 1' at frame 40", "WARN", ("lifted off", True)),
            ("goes 261° round 'SHEAVE 2' (drawn: 135°): check its side and the order of the contacts", "WARN",
             ("check side", True)),
            ("cannot go round 'SHEAVE 1' in this pose: 'WINCH DRUM' and 'SHEAVE 1' overlap", "WARN", ("no path", True)),
            ("its speed joint is gone: nothing moves it (remove the cable and add it again)", "WARN",
             ("no speed", True)),
            ("something new", "WARN", ("check", True))):
        monkeypatch.setattr(paths, "status", lambda scene, item, got=(text, level): got)
        assert ui_paths.short_status(sc, it) == word, text
        texts, head, rows, _touched = draw_panel()
        assert head == (["1 warning"] if level in ("WARN", "ERROR") else ["1 cable"]), text
        assert rows == ([word[0]] if word[0] else []), text
        joined = " ".join(texts)
        if level == "WARN":                                          # the whole sentence, under the list
            assert (f"Cable: {text}" if text.startswith("its ") else f"Cable {text}") in joined, text
        elif level == "ERROR":
            assert f"Cable: {text}" in joined


# ---------------------------------------------------------------------------
# tooltips
# ---------------------------------------------------------------------------

def sentences(text: str) -> int:
    return len([part for part in text.replace(": ", ". ").split(". ") if len(part.strip()) > 12])


def test_every_button_and_setting_has_a_tooltip():
    for name in OPS:
        rna = getattr(bpy.ops.fresing, name).get_rna_type()
        text = rna.description
        assert "\n" not in text and "  " not in text, name
        assert len(text) >= 100 and sentences(text) >= 2, (name, text)       # what it does, then how to use it
        for p in rna.properties:
            if p.identifier != "rna_type":
                assert len(p.description) >= 30 and "\n" not in p.description, (name, p.identifier)
    # one button, four jobs: each has its own text
    cls = ops_paths.FRESING_OT_cable_end
    texts = [cls.description(bpy.context, type("Props", (), {"end": end, "free": free})())
             for end in ("A", "B") for free in (False, True)]
    assert len(set(texts)) == 4 and all(len(t) >= 100 and "\n" not in t and sentences(t) >= 2 for t in texts)
    assert "start" in texts[0] and "end" in texts[2] and "free end" in texts[1]
    from fresing_render.blender import props as P
    props = P.FRCable.bl_rna.properties
    for name in ("name", "enabled", "diameter", "look", "pitch", "angle", "stripe", "mbr", "still", "reverse",
                 "a_free", "b_free"):                                        # every setting the panel draws
        text = props[name].description
        assert len(text) >= 40 and "\n" not in text, (name, text)
    for choice in props["look"].enum_items:
        assert len(choice.description) >= 30, choice.identifier
    assert len(P.FRCableContact.bl_rna.properties["turns"].description) >= 40


def test_the_tooltip_check_finds_nothing_in_this_panel(monkeypatch):
    """tools/tooltip_report.py over ui_paths.py: every button and setting drawn there says what it does."""
    import tooltip_report as t
    monkeypatch.setattr(t, "UI_FILES", ["fresing_render/blender/ui_paths.py"])
    monkeypatch.setitem(t.LANE_OF_PANEL, "Cables and paths", "Flex parts lane")
    for key, value in (("cb", "FRCable"), ("ct", "FRCableContact")):
        monkeypatch.setitem(t.OWNER_TYPES, key, value)
    for key, value in (("FRESING_UL_cables", "FRCable"), ("FRESING_UL_cable_contacts", "FRCableContact")):
        monkeypatch.setitem(t.ITEM_TYPES, key, value)
    fresing_render.unregister()
    try:
        items = t.collect()
    finally:
        fresing_render.register()
    assert len(items) >= 25 and {i.kind for i in items} >= {"button", "setting"}
    drawn = {i.ident.split(" ")[0] for i in items}
    assert {"fresing." + name for name in OPS} <= drawn, {"fresing." + name for name in OPS} - drawn
    bad = [(i.label or i.ident, i.verdict, i.tooltip) for i in items if i.verdict != "ok"]
    assert not bad, bad
